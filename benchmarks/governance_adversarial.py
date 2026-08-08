#!/usr/bin/env python3
"""Adversarial governance benchmark — mutation testing for the audit itself.

WHY THIS EXISTS
---------------
The repo has 12 static governance checks and they report "28 registered items, zero
warnings". That is a statement about the CURRENT tree, not about the audit's power. A
check that never fires is indistinguishable from a check that CANNOT fire, and this
project has already been burned by exactly that class of illusion twice:

  * the audit was green while `forge_agent_graph` output was silently dropped by
    `finalize_node` — the audit measured the WIRE, not the FLOW through it;
  * a connectivity check inspected a single file, so a genuine depth-2 connection read as
    "not wired" and the tempting fix was to add a cosmetic unused import.

So: stop asking "is the tree clean?" and start asking "if someone broke a rule, would we
find out?" Each scenario below introduces a real violation into a THROWAWAY COPY of the
repo, runs the real audit against it, and records whether the audit failed. Detection rate
is the score. An undetected mutation is a hole in the constitution's enforcement, named
and located.

SAFETY — this is the part that matters
--------------------------------------
Mutations are applied to a `git worktree`-style full copy under a temp directory. The
working tree is NEVER modified: every scenario asserts its target file is inside the
sandbox before writing, the sandbox is created per-scenario and deleted in a `finally`,
and the runner refuses to start if the sandbox path resolves inside the repo root.

SCORING
-------
detected      audit exits non-zero on the mutated copy  -> the rule has teeth
undetected    audit still passes                        -> a real enforcement gap
inconclusive  the mutation broke imports/syntax, so failure proves nothing about the rule

`inconclusive` exists on purpose. A mutation that crashes the interpreter would score as
"detected" for the wrong reason and inflate the result — the same flattering-bias failure
mode the triage parser bugs had. Detection rate is computed over conclusive scenarios only,
and both denominators are printed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, "benchmarks", "results")
AUDIT = os.path.join("scripts", "audit_governance.py")


@dataclass
class Scenario:
    """One rule, one way to break it, one prediction about the audit's response."""

    id: str
    rule: str                    # which constitutional principle this attacks
    severity: str                # high | medium | low
    target: str                  # repo-relative file to mutate
    find: str                    # exact snippet to replace (must be unique)
    replace: str
    why: str                     # what a real regression of this shape would look like
    requires_strict: bool = False
    tags: list[str] = field(default_factory=list)


SCENARIOS: list[Scenario] = [
    Scenario(
        id="silent-except-reintroduced",
        rule="Law 3 — no silent failure",
        severity="high",
        target="agents/task_decomposer.py",
        find="def evaluate(state: TaskDecomposerState) -> dict:",
        replace=(
            "def _swallow_everything(state):\n"
            "    try:\n"
            "        raise RuntimeError('boom')\n"
            "    except Exception:\n"
            "        pass\n\n\n"
            "def evaluate(state: TaskDecomposerState) -> dict:"
        ),
        why=(
            "This is the exact defect that killed 54% of meta-loop cycles: a bare except "
            "with pass, so a TypeError vanishes and the loop reports success. If the audit "
            "cannot see this shape re-enter a registered module, that failure can recur."
        ),
        tags=["silent-except", "regression-of-known-bug"],
    ),
    Scenario(
        id="llm-call-inside-evaluate",
        rule="P2 — evaluation must not be judged by the thing being evaluated",
        severity="high",
        target="agents/task_decomposer.py",
        find="def evaluate(state: TaskDecomposerState) -> dict:",
        replace=(
            "def evaluate(state: TaskDecomposerState) -> dict:\n"
            "    from llm.llm_integration import call_llm\n"
            "    _verdict = call_llm(prompt='did I do well?', system_prompt='judge')\n"
        ),
        why=(
            "LLM-as-judge inside evaluate() lets an agent grade its own homework. The repo "
            "bans it and grades SWE-bench programmatically; the audit must enforce the same "
            "standard in code, not only in the report."
        ),
        tags=["self-grading"],
    ),
    Scenario(
        id="entrypoint-deleted",
        rule="Registry integrity — declared entrypoints must exist",
        severity="high",
        target="agents/task_decomposer.py",
        find="def decompose_requirements(",
        replace="def decompose_requirements_RENAMED(",
        why=(
            "A registered entrypoint that no longer exists means the registry describes a "
            "system that is not there. This is the drift the audit exists to catch."
        ),
        tags=["registry-drift"],
    ),
    Scenario(
        id="postcondition-removed",
        rule="P2 — Verified Closure declared before execution",
        severity="high",
        target="agents/task_decomposer.py",
        find='postcondition = {"kind": "non_empty", "path": None}',
        replace="postcondition = None  # declared after the fact",
        why=(
            "The postcondition is declared BEFORE the graph runs precisely so the agent "
            "cannot pick a convenient assertion after seeing its own output. Removing it "
            "restores the ability to self-flatter."
        ),
        tags=["verified-closure"],
    ),
    Scenario(
        id="never-list-emptied",
        rule="Least privilege — NEVER is the architectural boundary",
        severity="high",
        target="agents/context_curator.py",
        find='"NEVER": ["source_code_edit", "execute_deployment", "credentials_access"],',
        replace='"NEVER": ["execute_deployment", "credentials_access"],',
        why=(
            "NEVER is where the constraint actually lives: it is the list of things the "
            "agent cannot do by construction. Quietly commenting an entry out widens "
            "capability while leaving the matrix well-formed, so a shape-only check still "
            "passes. This is privilege escalation that looks like a formatting change."
        ),
        tags=["privilege-escalation", "never-boundary"],
    ),
    Scenario(
        id="never-entry-promoted-to-write",
        rule="Least privilege — a forbidden capability must not become a granted one",
        severity="high",
        target="agents/context_curator.py",
        find='"WRITE": ["sanitized_context", "context_summary", "signal_to_noise_ratio"],',
        replace=('"WRITE": ["source_code_edit", "sanitized_context", "context_summary", '
                 '"signal_to_noise_ratio"],'),
        why=(
            "Moving a capability from NEVER into WRITE is the exact inversion the "
            "permission matrix exists to prevent. The matrix stays a dict of lists, so "
            "shape validation cannot see it — only a check that reads NEVER against the "
            "other keys can."
        ),
        tags=["privilege-escalation", "never-boundary"],
    ),
]


def _repo_is_clean() -> tuple[bool, str]:
    p = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                       capture_output=True, text=True)
    return True, p.stdout.strip()


def _make_sandbox() -> str:
    """Full copy of the repo in a temp dir. Heavy dirs are skipped for speed, EXCEPT
    .venv is not needed: the audit runs under the host interpreter with cwd=sandbox."""
    dest = tempfile.mkdtemp(prefix="gov_adv_")
    sandbox = os.path.join(dest, "repo")
    ignore = shutil.ignore_patterns(
        ".venv", ".git", "__pycache__", "*.pyc", ".pytest_cache",
        "logs", "benchmarks/results", "*.jsonl", "node_modules", ".mypy_cache",
    )
    shutil.copytree(ROOT, sandbox, ignore=ignore, symlinks=True)
    return sandbox


def _run_audit(sandbox: str, strict: bool, python: str) -> tuple[int, str]:
    cmd = [python, AUDIT] + (["--strict"] if strict else [])
    env = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run(cmd, cwd=sandbox, capture_output=True, text=True,
                           timeout=300, env=env)
        return p.returncode, (p.stdout + p.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT after 300s"


def _syntax_ok(sandbox: str, rel: str, python: str) -> bool:
    """Distinguish 'audit caught the rule' from 'file no longer parses'."""
    p = subprocess.run([python, "-c",
                        f"import ast,sys; ast.parse(open({os.path.join(sandbox, rel)!r},"
                        f" encoding='utf-8').read())"],
                       capture_output=True, text=True, timeout=60)
    return p.returncode == 0


def run_scenario(sc: Scenario, baseline_rc: int, python: str) -> dict:
    t0 = time.time()
    sandbox = _make_sandbox()
    row = {"id": sc.id, "rule": sc.rule, "severity": sc.severity, "target": sc.target,
           "tags": sc.tags, "why": sc.why}
    try:
        path = os.path.realpath(os.path.join(sandbox, sc.target))
        # Hard safety gate: never write outside the sandbox, never touch the real repo.
        if not path.startswith(os.path.realpath(sandbox) + os.sep):
            row.update(verdict="inconclusive", detail="path escaped sandbox")
            return row
        if os.path.realpath(ROOT) in (os.path.realpath(sandbox),):
            row.update(verdict="inconclusive", detail="sandbox resolved to repo root")
            return row

        src = open(path, encoding="utf-8").read()
        n = src.count(sc.find)
        if n != 1:
            row.update(verdict="inconclusive",
                       detail=f"anchor found {n} times (need exactly 1) — scenario is stale")
            return row
        open(path, "w", encoding="utf-8").write(src.replace(sc.find, sc.replace, 1))

        parses = _syntax_ok(sandbox, sc.target, python)
        rc, out = _run_audit(sandbox, sc.requires_strict, python)

        if not parses:
            verdict = "inconclusive"
            detail = "mutation broke syntax — audit failure proves nothing about the rule"
        elif rc != 0 and baseline_rc == 0:
            verdict = "detected"
            detail = "audit failed on the mutated tree"
        elif rc == 0:
            verdict = "undetected"
            detail = "audit still passed — enforcement gap"
        else:
            verdict = "inconclusive"
            detail = f"baseline_rc={baseline_rc}, rc={rc}"

        row.update(verdict=verdict, detail=detail, audit_rc=rc, syntax_ok=parses,
                   audit_tail=out[-600:])
        return row
    except Exception as exc:
        row.update(verdict="inconclusive", detail=f"{type(exc).__name__}: {exc}"[:200])
        return row
    finally:
        row["seconds"] = round(time.time() - t0, 1)
        shutil.rmtree(os.path.dirname(sandbox), ignore_errors=True)


def run(strict: bool, only: list[str] | None, out_path: str, python: str) -> dict:
    print("=== ADVERSARIAL GOVERNANCE BENCHMARK ===")
    print("mutating throwaway copies; the working tree is never modified\n")

    _, dirty = _repo_is_clean()
    baseline_sandbox = _make_sandbox()
    try:
        baseline_rc, baseline_out = _run_audit(baseline_sandbox, strict, python)
    finally:
        shutil.rmtree(os.path.dirname(baseline_sandbox), ignore_errors=True)

    print(f"baseline audit on unmutated copy: rc={baseline_rc} "
          f"({'clean' if baseline_rc == 0 else 'ALREADY FAILING'})")
    if baseline_rc != 0:
        print("  baseline is not clean, so every 'detected' would be unattributable:")
        print("  " + baseline_out[-500:].replace("\n", "\n  "))
        return {"error": "baseline_not_clean", "baseline_rc": baseline_rc,
                "baseline_tail": baseline_out[-1500:]}

    scenarios = [s for s in SCENARIOS if not only or s.id in only]
    rows = []
    for i, sc in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] {sc.id:32} ({sc.severity:6} | {sc.rule[:34]}) ",
              end="", flush=True)
        row = run_scenario(sc, baseline_rc, python)
        rows.append(row)
        mark = {"detected": "DETECTED    ", "undetected": "UNDETECTED <<",
                "inconclusive": "inconclusive"}[row["verdict"]]
        print(f"{mark} {row['seconds']}s")
        if row["verdict"] != "detected":
            print(f"      -> {row['detail']}")

    detected = [r for r in rows if r["verdict"] == "detected"]
    undetected = [r for r in rows if r["verdict"] == "undetected"]
    inconclusive = [r for r in rows if r["verdict"] == "inconclusive"]
    conclusive = len(detected) + len(undetected)

    print("\n=== SUMMARY ===")
    print(f"  scenarios      {len(rows)}")
    print(f"  detected       {len(detected)}")
    print(f"  UNDETECTED     {len(undetected)}")
    print(f"  inconclusive   {len(inconclusive)}")
    if conclusive:
        print(f"  detection rate {100*len(detected)/conclusive:.1f}%  "
              f"(over {conclusive} conclusive; {len(rows)} attempted)")
    else:
        print("  detection rate n/a — no conclusive scenario")

    if undetected:
        print("\n  ENFORCEMENT GAPS (a real regression of this shape would ship silently):")
        for r in undetected:
            print(f"    - [{r['severity']}] {r['id']}: {r['rule']}")
            print(f"        {r['why']}")

    hi = [r for r in undetected if r["severity"] == "high"]
    if hi:
        print(f"\n  {len(hi)} HIGH-severity rule(s) are unenforced.")

    payload = {
        "baseline_rc": baseline_rc, "strict": strict,
        "working_tree_dirty_at_start": bool(dirty),
        "counts": {"total": len(rows), "detected": len(detected),
                   "undetected": len(undetected), "inconclusive": len(inconclusive)},
        "detection_rate_conclusive": (round(100*len(detected)/conclusive, 2)
                                      if conclusive else None),
        "scenarios": rows,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print(f"\nsaved -> {out_path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adversarial governance benchmark")
    ap.add_argument("--strict", action="store_true", help="run the audit in --strict mode")
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--python", default=os.path.join(ROOT, ".venv", "bin", "python"))
    ap.add_argument("--out", default=os.path.join(RESULTS, "governance_adversarial.json"))
    ns = ap.parse_args(argv)
    only = [s.strip() for s in ns.only.split(",") if s.strip()]
    py = ns.python if os.path.exists(ns.python) else sys.executable
    res = run(ns.strict, only, ns.out, py)
    return 1 if res.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
