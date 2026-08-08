#!/usr/bin/env python3
"""Pre-flight triage: which SWE-bench instances can be judged LOCALLY, before any LLM.

WHY THIS EXISTS
---------------
The 8-instance psf/requests slice used for every SWE-bench comparison is (a) the easiest
repo (87.5% localization vs django's 69.7%) and (b) statistically useless (95% CI ~45pp).
We can run more locally — but "the dataset has 249 instances" is not "249 are runnable":
instances span 2013-2023, and old repos cannot import under Python 3.11 (django<3.0 needs
`gettext(codeset=)`; requests<2.27 needs `collections.MutableMapping`; astropy needs
C-extension builds). A benchmark that counts env failures as model failures is measuring
its own harness.

This script walks the LOCAL clones and judges each instance with the GOLD test and GOLD
fix — zero LLM tokens — classifying every result so infra failures are excluded before
any arm runs:

    USABLE       gold test FAILS on broken code (for the right reason) and PASSES on the
                 fix. This instance can judge a model honestly.
    no_fail      gold test passes on the BROKEN code -> the "bug" doesn't reproduce;
                 the instance is broken (bad base_commit / missing dependency) -> exclude.
    no_pass      gold test fails even AFTER the gold fix -> environment gap -> exclude.
    env_missing  import/collection error -> missing dependency or toolchain -> exclude.
    patch_fail   gold test patch didn't apply cleanly -> exclude.

USABLE / total is the honest denominator for every later measurement.

RESUME + IDEMPOTENCE
--------------------
The repo clones are shared across sessions, so each instance is judged in an isolated
git WORKTREE (never the clone's working tree). On failure, the worktree is removed.
Re-running skips instances already judged (records file acts as a checkpoint), and
`--reset` re-judges everything. Nothing here writes to the clone's working tree.

ZERO LLM: this file never calls call_llm. Tokens are spent only on the arms that use them.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmarks.swebench_harness import (  # noqa: E402
    REPO_CACHE,
    checkout_worktree,
    remove_worktree,
    repo_path,
)

DATASET = os.path.join(ROOT, "benchmarks", "results", "swebench_verified_local.json")
OUT = os.path.join(ROOT, "benchmarks", "results", "swebench_local_verified.json")
PY = os.path.join(ROOT, ".venv", "bin", "python")
TIMEOUT_PER_STAGE = 900

# Repos whose modern versions are Python-3.11-importable (verified by probe on 2026-08-07).
INCLUDE_REPOS = {
    "django/django": {"4.1", "4.2", "5.0"},
    "sympy/sympy": {"1.11", "1.12"},
}


# Django prints a test's DOCSTRING instead of its name when one exists, so FAIL_TO_PASS
# entries come in three measured shapes (counted over the 93 local candidates):
#   69  "test_name (module.Class)"           -> parse directly
#   22  "Some docstring sentence."           -> name is absent; derive from test_patch
#    2  "path/to/test.py::test_name"         -> pytest node id
# Taking ftp[0] blindly misclassified all 22 docstring cases as env_missing — a sound
# instance scored as an infrastructure failure, which biases the denominator downward.
_LABEL_RE = re.compile(r"^([A-Za-z_]\w*) \(([\w.]+)\)")


def _targets_from_field(instance: dict) -> list[str]:
    """Parse every FAIL_TO_PASS entry that carries a real test name."""
    ftp = json.loads(instance["FAIL_TO_PASS"]) if isinstance(instance["FAIL_TO_PASS"], str) else instance["FAIL_TO_PASS"]
    out = []
    for raw in ftp:
        t = raw.strip()
        m = _LABEL_RE.match(t)
        if m:
            name, path = m.group(1), m.group(2)
            # Modern django repeats the test name inside the parens as a FULL dotted path:
            #   "test_zero_values (a.b.FunctionTests.test_zero_values)"
            # Appending the name again yields `...test_zero_values.test_zero_values`, which
            # django resolves to a function attribute and reports as AttributeError — 19 of
            # 20 `no_pass` verdicts were this bug, not a broken environment.
            out.append(path if path.split(".")[-1] == name else f"{path}.{name}")
        elif "::" in t:
            out.append(t.replace("::", ".").replace(".py", "").replace("/", "."))
    return out


def _added_tests_from_patch(instance: dict) -> list[tuple[str, str]]:
    """(module, method) pairs the gold test diff adds, e.g. ('decorators.tests', 'test_x')."""
    added, module = [], None
    for line in instance["test_patch"].splitlines():
        m = re.match(r"^\+\+\+ b/tests/([\w/]+)\.py", line)
        if m:
            module = m.group(1).replace("/", ".")
            continue
        m2 = re.match(r"^\+\s*def (test_\w+)\(", line)
        if m2 and module:
            added.append((module, m2.group(1)))
    return added


def _enclosing_class(worktree: str, module: str, method: str) -> str | None:
    """Find the TestCase class holding `method`, by parsing the patched file with AST.

    The diff cannot answer this: a hunk header shows the nearest `class` line, which for
    django-14787 is a helper class declared INSIDE the test body, not the TestCase. Only
    the real file has the true nesting, so it is parsed rather than pattern-matched.
    """
    path = os.path.join(worktree, "tests", *module.split(".")) + ".py"
    if not os.path.exists(path):
        return None
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return None
    for node in tree.body:  # top-level classes only — nested helpers are not test cases
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method:
                    return node.name
    return None


def _target_of(instance: dict, worktree: str | None = None) -> str | None:
    """Best available test label, or None when the instance cannot be addressed.

    Prefers the labels SWE-bench ships; falls back to reconstructing one from the gold
    diff plus the patched file. `worktree` must be a checkout with the test patch already
    applied, otherwise the class lookup is skipped.
    """
    found = _targets_from_field(instance)
    if found:
        return found[0]
    for module, method in _added_tests_from_patch(instance):
        if worktree:
            cls = _enclosing_class(worktree, module, method)
            if cls:
                return f"{module}.{cls}.{method}"
        # module-level test function (pytest-style) — valid as-is
        return f"{module}.{method}"
    return None


def _runtests(instance: dict, root: str, target: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = root  # run from the checkout root so `import django` resolves
    try:
        p = subprocess.run(
            [PY, "tests/runtests.py", "--verbosity", "0", target],
            cwd=root, env=env, capture_output=True, text=True, timeout=TIMEOUT_PER_STAGE,
        )
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def judge_one(instance: dict) -> dict:
    """Classify one instance with gold test + gold fix. Zero LLM."""
    iid = instance["instance_id"]
    repo = instance["repo"]
    rp = repo_path(repo)
    worktree = os.path.join("/tmp", f"triage-{iid}")
    remove_worktree(repo, worktree)

    try:
        checkout_worktree(repo, instance["base_commit"], worktree)
    except Exception as exc:
        return {"instance_id": iid, "repo": repo, "status": "checkout_fail", "reason": str(exc)[:200]}

    try:
        p = subprocess.run(["git", "apply", "-"], cwd=worktree, input=instance["test_patch"],
                           text=True, capture_output=True, timeout=300)
        if p.returncode != 0:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "patch_fail", "reason": p.stderr[:200]}

        target = _target_of(instance, worktree)
        if target is None:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "no_target",
                    "reason": "FAIL_TO_PASS holds only docstrings and test_patch adds no "
                              "`def test_*` (sympy-style bare names need the pytest runner)"}

        rc_broken, out_broken = _runtests(instance, worktree, target)
        if rc_broken == 0:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "no_fail", "reason": "gold test passes on BROKEN code (bug doesn't reproduce)"}
        if rc_broken == 124:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "timeout", "reason": "gold test timed out on broken code"}
        if "ModuleNotFoundError" in out_broken or "ImportError" in out_broken:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "env_missing", "reason": _err_tail(out_broken)}

        p2 = subprocess.run(["git", "apply", "-"], cwd=worktree, input=instance["patch"],
                            text=True, capture_output=True, timeout=300)
        if p2.returncode != 0:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "patch_fail", "reason": f"fix patch: {p2.stderr[:200]}"}

        rc_fixed, out_fixed = _runtests(instance, worktree, target)
        if rc_fixed == 0:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "USABLE", "reason": "fail->pass confirmed with gold test+fix"}
        if rc_fixed == 124:
            return {"instance_id": iid, "repo": repo, "version": instance["version"],
                    "status": "timeout", "reason": "gold test timed out after fix"}
        return {"instance_id": iid, "repo": repo, "version": instance["version"],
                "status": "no_pass", "reason": _err_tail(out_fixed)}
    finally:
        remove_worktree(repo, worktree)


def _err_tail(out: str, n: int = 4) -> str:
    lines = [l for l in out.splitlines() if l.strip()]
    return " | ".join(lines[-n:])[:400]


class _SingleRun:
    """Refuse to start when another triage run owns the records file.

    Two runs racing on OUT is not hypothetical: on 2026-08-07 a superseded run finished
    after the corrected one and only the ordering kept the file honest. A stale count is
    worse than a crash — nothing downstream would flag a denominator that shrank by 18.
    """

    def __init__(self, path: str) -> None:
        self.path = path + ".lock"
        self.fd: int | None = None

    def __enter__(self) -> "_SingleRun":
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                holder = int(open(self.path, encoding="utf-8").read().strip() or 0)
            except (ValueError, OSError):
                holder = 0
            alive = False
            if holder:
                try:
                    os.kill(holder, 0)
                    alive = True
                except (OSError, ProcessLookupError):
                    alive = False
            if alive:
                raise SystemExit(
                    f"another triage run (pid {holder}) holds {self.path}; "
                    f"wait for it or kill it — concurrent runs corrupt the record"
                )
            print(f"removing stale lock from dead pid {holder}", flush=True)
            os.unlink(self.path)
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self.fd, str(os.getpid()).encode())
        return self

    def __exit__(self, *exc: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        try:
            os.unlink(self.path)
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-flight SWE-bench local triage (zero LLM)")
    ap.add_argument("--repo", default=None, help="Restrict to one repo slug")
    ap.add_argument("--reset", action="store_true", help="Re-judge everything (ignore records)")
    ap.add_argument("--limit", type=int, default=0, help="Cap instances judged this run")
    ns = ap.parse_args(argv)

    with _SingleRun(OUT):
        return _run(ns)


def _run(ns: argparse.Namespace) -> int:
    rows = json.load(open(DATASET, encoding="utf-8"))
    candidates = []
    for r in rows:
        if r["repo"] not in INCLUDE_REPOS:
            continue
        if r["version"] not in INCLUDE_REPOS[r["repo"]]:
            continue
        if ns.repo and r["repo"] != ns.repo:
            continue
        candidates.append(r)
    print(f"Candidates: {len(candidates)}  "
          f"({Counter(r['repo'] for r in candidates)})", flush=True)

    records = {}
    if os.path.exists(OUT) and not ns.reset:
        try:
            records = {r["instance_id"]: r for r in json.load(open(OUT))}
        except Exception:
            records = {}

    todo = [r for r in candidates if r["instance_id"] not in records]
    if ns.limit:
        todo = todo[: ns.limit]
    print(f"To judge: {len(todo)} (already recorded: {len(candidates) - len(todo)})", flush=True)

    t0 = time.time()
    for i, inst in enumerate(todo, 1):
        rec = judge_one(inst)
        records[rec["instance_id"]] = rec
        print(f"  [{i}/{len(todo)}] {rec['instance_id']:34} {rec['status']:12} "
              f"({time.time()-t0:.0f}s elapsed)", flush=True)

    # Atomic replace + checksum so two concurrent runs cannot silently corrupt the
    # record (observed 2026-08-07: an old run's `tail` notification arrived AFTER the
    # newer run had written, and only a lucky ordering kept the file correct).
    tmp_out = OUT + f".tmp.{os.getpid()}"
    with open(tmp_out, "w", encoding="utf-8") as fh:
        json.dump(sorted(records.values(), key=lambda r: r["instance_id"]), fh, indent=1)
    os.replace(tmp_out, OUT)

    digest = hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16]
    with open(OUT + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(digest + "\n")

    cnt = Counter(r["status"] for r in records.values())
    usable = cnt.get("USABLE", 0)
    print(f"\n=== TRIAGE RESULT ===")
    for status, n in cnt.most_common():
        print(f"  {status:14} {n}")
    print(f"\nUSABLE: {usable}/{len(records)} = {100*usable/len(records):.1f}% of judged")
    print(f"saved -> {OUT}  sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
