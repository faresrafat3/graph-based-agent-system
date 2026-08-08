#!/usr/bin/env python3
"""Run SWE-bench arms against the LOCALLY-VERIFIED instance set and judge them here.

WHY A SECOND RUNNER
-------------------
`swebench_harness.run()` grades through Docker. The verified set produced by
`triage_local.py` is 74 django instances judged with django's own `tests/runtests.py`
in a git worktree — no Docker, no image pulls. This module reuses the ARMS from
swebench_harness unchanged (`solve_baseline`, `solve_agent`, `solve_agent_graph`) and
supplies the local judgement, so the only thing that differs between arms is the arm.

PAIRED DESIGN
-------------
Every arm sees the SAME instance, the SAME worktree contents, and the SAME localizer
output. Results are keyed by instance_id so the comparison is paired — McNemar on the
discordant pairs, not two independent proportions. Anything else throws away the
pairing and widens the interval for nothing.

HONEST DENOMINATOR
------------------
Failures are classified, never merged:
    resolved      patch applied AND the gold FAIL_TO_PASS test passes
    not_resolved  patch applied, test still fails      -> capability
    no_apply      patch did not apply                  -> capability
    infra         LLM transport error / timeout        -> EXCLUDED from the denominator
An infra failure is not a model failure. Reporting them together understates capability;
reporting only the adjusted number overstates it — both are printed.

COST TELEMETRY
--------------
Real LLM call counts come back from each arm (not estimates), plus wall-clock per
instance. All calls route through `llm.llm_integration.call_llm`, which rotates the
11-key pool with per-key 429 cooldown, so throughput is pool-wide.

RESUME
------
Results append to a JSONL checkpoint after every instance. Re-running skips what is
already recorded; `--reset` starts over. A crash costs one instance, not the run.
"""

from __future__ import annotations

import argparse
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
    checkout_worktree,
    remove_worktree,
    solve_agent,
    solve_agent_graph,
    solve_baseline,
)
from benchmarks.localizer_graph import localize_ensemble  # noqa: E402
from benchmarks.triage_local import _target_of  # noqa: E402

DATASET = os.path.join(ROOT, "benchmarks", "results", "swebench_verified_local.json")
VERIFIED = os.path.join(ROOT, "benchmarks", "results", "swebench_local_verified.json")
PY = os.path.join(ROOT, ".venv", "bin", "python")

ARMS = {
    "baseline": solve_baseline,      # control: retrieval + one raw LLM call
    "agent": solve_agent,            # governance: curate -> validate -> refine
    "graph": solve_agent_graph,      # decomposition: diagnose -> generate -> analyse -> refine
}

# Transport-level failures. These mean the request never produced a usable answer, so
# counting them as "the model got it wrong" would be a lie about capability.
INFRA_MARKERS = (
    "429", "rate limit", "RateLimit", "timed out", "TimeoutError", "Timeout",
    "Connection", "ConnectionError", "StepfunAPIError", "EmptyStream", "failed after",
)


def is_infra_error(err: str) -> bool:
    return any(m.lower() in err.lower() for m in INFRA_MARKERS)


def load_verified() -> list[dict]:
    """The instances triage proved can judge a model honestly."""
    recs = json.load(open(VERIFIED, encoding="utf-8"))
    usable = {r["instance_id"] for r in recs if r["status"] == "USABLE"}
    rows = json.load(open(DATASET, encoding="utf-8"))
    return [r for r in rows if r["instance_id"] in usable]


def run_gold_test(worktree: str, target: str, timeout: int = 900) -> tuple[int, str]:
    """Run one django test label inside the worktree. Zero LLM."""
    env = dict(os.environ)
    env["PYTHONPATH"] = worktree
    try:
        p = subprocess.run(
            [PY, "tests/runtests.py", "--verbosity", "0", target],
            cwd=worktree, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def apply_patch(worktree: str, patch: str) -> tuple[bool, str]:
    """Apply a patch with the SAME escalating tolerance the official grader uses.

    `validate_patch` in swebench_harness tries five levels (plain, --recount,
    --ignore-whitespace, -C1, --unidiff-zero) because a hunk whose counts drifted still
    describes a correct edit. Judging with a plain `git apply` would reject patches the
    real grader accepts and charge the model for the harness's strictness — measured on
    django-14725, whose baseline patch failed plain apply with "corrupt patch at line 21".
    """
    attempts = (
        [],
        ["--recount"],
        ["--ignore-whitespace", "--recount"],
        ["--ignore-whitespace", "--recount", "-C1"],
        ["--ignore-whitespace", "--recount", "--unidiff-zero", "-C0"],
    )
    last = ""
    for flags in attempts:
        p = subprocess.run(["git", "apply", *flags, "-"], cwd=worktree, input=patch,
                           text=True, capture_output=True, timeout=300)
        if p.returncode == 0:
            return True, " ".join(flags) or "plain"
        last = p.stderr[:300]
    return False, last


def judge(instance: dict, worktree: str, patch: str) -> dict:
    """Apply the model patch + gold test, then run the test. Exit code decides."""
    if not patch or not patch.strip():
        return {"outcome": "no_apply", "detail": "empty patch"}

    ok, how = apply_patch(worktree, patch)
    if not ok:
        return {"outcome": "no_apply", "detail": how}

    gold = subprocess.run(["git", "apply", "-"], cwd=worktree, input=instance["test_patch"],
                          text=True, capture_output=True, timeout=300)
    if gold.returncode != 0:
        # The model's patch collided with the gold test patch — treat as not resolved,
        # not as infrastructure: the model changed something the test file depends on.
        return {"outcome": "not_resolved", "detail": f"gold test patch conflicted: {gold.stderr[:200]}"}

    target = _target_of(instance, worktree)
    if target is None:
        return {"outcome": "infra", "detail": "no resolvable test target"}

    rc, out = run_gold_test(worktree, target)
    if rc == 0:
        return {"outcome": "resolved", "detail": f"{target} (applied: {how})"}
    if rc == 124:
        return {"outcome": "infra", "detail": "gold test timed out"}
    return {"outcome": "not_resolved", "detail": _tail(out)}


def _tail(out: str, n: int = 3) -> str:
    lines = [l for l in out.splitlines() if l.strip()]
    return " | ".join(lines[-n:])[:300]


def run_one(instance: dict, arm: str, top_k: int) -> dict:
    """One instance, one arm: localize -> solve -> judge. Never raises."""
    iid = instance["instance_id"]
    started = time.time()
    worktree = os.path.join("/tmp", f"bench-{arm}-{iid}")
    remove_worktree(instance["repo"], worktree)

    record = {"instance_id": iid, "arm": arm, "repo": instance["repo"],
              "version": instance.get("version")}
    try:
        checkout_worktree(instance["repo"], instance["base_commit"], worktree)
    except Exception as exc:
        record.update(outcome="infra", detail=f"checkout: {exc}"[:200],
                      llm_calls=0, seconds=round(time.time() - started, 1))
        return record

    try:
        files = localize_ensemble(instance["problem_statement"], worktree, top_k=top_k)
        # Recorded BEFORE the arm runs: an exception inside the arm skips the success-path
        # update, and 16 infra records landed with no `localized` field at all — losing the
        # evidence needed to tell "the localizer failed" from "the LLM call timed out".
        # Diagnostics must survive the failure they describe.
        record["localized"] = files[:5]
        out = ARMS[arm](instance, worktree, files)
        verdict = judge(instance, worktree, out.get("patch", ""))
        record.update(
            outcome=verdict["outcome"],
            detail=verdict["detail"],
            llm_calls=out.get("llm_calls", 0),
            refinements=out.get("refinements", 0),
            graph_rounds=out.get("graph_rounds"),
        )
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        record.update(outcome="infra" if is_infra_error(err) else "error",
                      detail=err[:300], llm_calls=0)
    finally:
        remove_worktree(instance["repo"], worktree)

    record["seconds"] = round(time.time() - started, 1)
    return record


def run_parallel(todo: list[tuple[dict, str]], top_k: int, workers: int, sink) -> list[dict]:
    """Run (instance, arm) units concurrently, bounded by the KEY POOL not the CPU.

    11 StepFun keys rotate with per-key 429 cooldown, so ~8 requests in flight keeps the
    pool busy without stacking retries on one account. Going wider converts capability
    into rate limits — this project already measured that failure mode: 96 of 99 HumanEval
    failures in an earlier run were 429s, not wrong answers.

    Each unit owns its own worktree (`/tmp/bench-{arm}-{iid}`), so parallel units never
    share mutable state. Results stream to `sink` as they land, which is what makes the
    JSONL checkpoint crash-safe: a kill costs the in-flight units, not the run.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    out: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, inst, arm, top_k): (inst, arm) for inst, arm in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                rec = fut.result()
            except Exception as exc:  # a worker crash must not kill the batch
                inst, arm = futures[fut]
                rec = {"instance_id": inst["instance_id"], "arm": arm, "repo": inst["repo"],
                       "outcome": "error", "detail": f"worker: {type(exc).__name__}: {exc}"[:300],
                       "llm_calls": 0, "seconds": 0}
            out.append(rec)
            sink(rec)
            print(f"  [{n}/{len(todo)}] {rec['arm']:8} {rec['instance_id']:28} "
                  f"{rec['outcome']:13} calls={rec.get('llm_calls', 0):2} "
                  f"{rec.get('seconds', 0):6.1f}s  (elapsed {time.time()-t0:.0f}s)", flush=True)
    return out


def summarise(records: list[dict], arm: str) -> dict:
    """Raw and infra-adjusted rates, with the taxonomy kept visible."""
    rows = [r for r in records if r["arm"] == arm]
    cnt = Counter(r["outcome"] for r in rows)
    total = len(rows)
    infra = cnt.get("infra", 0) + cnt.get("error", 0)
    scored = total - infra
    resolved = cnt.get("resolved", 0)
    applied = resolved + cnt.get("not_resolved", 0)
    return {
        "arm": arm,
        "total": total,
        "infra_excluded": infra,
        "scored": scored,
        "resolved": resolved,
        "resolve_rate_raw": round(100 * resolved / total, 2) if total else 0.0,
        "resolve_rate_adjusted": round(100 * resolved / scored, 2) if scored else 0.0,
        "apply_rate": round(100 * applied / scored, 2) if scored else 0.0,
        "llm_calls": sum(r.get("llm_calls", 0) for r in rows),
        "wall_seconds": round(sum(r.get("seconds", 0) for r in rows)),
        "outcomes": dict(cnt),
    }


def mcnemar(records: list[dict], a: str, b: str) -> dict:
    """Exact McNemar over instances both arms attempted and neither hit infra on."""
    import math

    by_arm = {arm: {r["instance_id"]: r for r in records if r["arm"] == arm} for arm in (a, b)}
    shared = set(by_arm[a]) & set(by_arm[b])
    both = a_only = b_only = neither = 0
    gained, lost = [], []
    for iid in sorted(shared):
        ra, rb = by_arm[a][iid], by_arm[b][iid]
        if ra["outcome"] in ("infra", "error") or rb["outcome"] in ("infra", "error"):
            continue
        ha, hb = ra["outcome"] == "resolved", rb["outcome"] == "resolved"
        if ha and hb:
            both += 1
        elif ha:
            a_only += 1
            lost.append(iid)
        elif hb:
            b_only += 1
            gained.append(iid)
        else:
            neither += 1

    n_disc = a_only + b_only
    if n_disc == 0:
        p = 1.0
    else:
        smaller = min(a_only, b_only)
        tail = sum(math.comb(n_disc, i) for i in range(smaller + 1)) / (2 ** n_disc)
        p = min(1.0, 2 * tail)
    n = both + a_only + b_only + neither
    return {
        "pair": f"{a} vs {b}", "n_paired": n,
        "both": both, "neither": neither,
        f"only_{a}": a_only, f"only_{b}": b_only,
        "discordant": n_disc, "mcnemar_exact_p": round(p, 6),
        "delta_pp": round(100 * (b_only - a_only) / n, 2) if n else 0.0,
        f"{b}_gained": gained[:10], f"{b}_lost": lost[:10],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run arms on the locally-verified set")
    ap.add_argument("--arms", default="baseline,agent", help="Comma-separated: baseline,agent,graph")
    ap.add_argument("--limit", type=int, default=0, help="Cap instances (0 = all verified)")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8,
                    help="Concurrent units. Bounded by the 11-key pool, not the CPU; "
                         "going much wider converts capability into 429s.")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "benchmarks", "results", "local_arms.jsonl"))
    ns = ap.parse_args(argv)

    arms = [a.strip() for a in ns.arms.split(",") if a.strip()]
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        print(f"Unknown arm(s): {unknown}. Available: {sorted(ARMS)}", file=sys.stderr)
        return 1

    instances = load_verified()
    if ns.limit:
        instances = instances[: ns.limit]

    if ns.reset and os.path.exists(ns.out):
        os.remove(ns.out)
    done = set()
    records: list[dict] = []
    if os.path.exists(ns.out):
        for line in open(ns.out, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                records.append(r)
                done.add((r["instance_id"], r["arm"]))

    todo = [(inst, arm) for inst in instances for arm in arms
            if (inst["instance_id"], arm) not in done]
    print(f"Verified instances: {len(instances)} | arms: {arms} | "
          f"to run: {len(todo)} (recorded: {len(done)})", flush=True)

    if not todo:
        print("Nothing to run — all requested (instance, arm) units already recorded.")
    else:
        # One lock around the append so concurrent workers cannot interleave a line.
        import threading
        write_lock = threading.Lock()
        with open(ns.out, "a", encoding="utf-8") as fh:
            def sink(rec: dict) -> None:
                with write_lock:
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()

            records.extend(run_parallel(todo, ns.top_k, max(1, ns.workers), sink))

    print("\n=== ARM SUMMARIES ===")
    summaries = []
    for arm in arms:
        s = summarise(records, arm)
        summaries.append(s)
        print(f"\n--- {arm} ---")
        print(f"  total={s['total']}  infra_excluded={s['infra_excluded']}  scored={s['scored']}")
        print(f"  resolved     : {s['resolved']}")
        print(f"  resolve raw  : {s['resolve_rate_raw']}%")
        print(f"  resolve adj  : {s['resolve_rate_adjusted']}%  (infra excluded)")
        print(f"  apply rate   : {s['apply_rate']}%")
        print(f"  llm calls    : {s['llm_calls']}   wall: {s['wall_seconds']}s")
        print(f"  outcomes     : {s['outcomes']}")

    pairs = []
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            m = mcnemar(records, arms[i], arms[j])
            pairs.append(m)
            print(f"\n=== PAIRED: {m['pair']} (n={m['n_paired']}, McNemar exact) ===")
            print(f"  both={m['both']}  neither={m['neither']}  discordant={m['discordant']}")
            print(f"  delta={m['delta_pp']:+.2f} pp   exact p={m['mcnemar_exact_p']}")
            print(f"  verdict: {'SIGNIFICANT' if m['mcnemar_exact_p'] < 0.05 else 'not significant'} at alpha=0.05")

    report = ns.out.replace(".jsonl", "_summary.json")
    with open(report, "w", encoding="utf-8") as fh:
        json.dump({"summaries": summaries, "paired": pairs}, fh, indent=1)
    print(f"\nsaved -> {ns.out}\nsummary -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
