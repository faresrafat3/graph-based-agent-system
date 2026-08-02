"""
Re-runs ONLY the failed problems from a previous results file and merges the outcome.

Used after a harness-level fix (e.g. re-attaching the HumanEval prompt preamble) so we
do not burn quota re-running the 157 problems that already passed.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from humaneval_harness import load_problems, evaluate_problem


def rerun(path: str, mode: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    problems = {p["task_id"]: p for p in load_problems()}
    failed_ids = [r["task_id"] for r in payload["results"] if not r["passed"]]
    print(f"Re-running {len(failed_ids)} failures for mode={mode}: {failed_ids}")

    updated = {}
    for tid in failed_ids:
        res = evaluate_problem(problems[tid], mode)
        updated[tid] = res
        print(f"  {tid:<18} {'PASS' if res['passed'] else 'FAIL'}  {res['duration']}s")

    merged = [updated.get(r["task_id"], r) for r in payload["results"]]

    total = len(merged)
    passed = sum(1 for r in merged if r["passed"])
    infra = sum(1 for r in merged if r.get("failure_class") == "infrastructure")
    capability = sum(1 for r in merged if r.get("failure_class") == "capability")
    scored = total - infra

    summary = dict(payload["summary"])
    summary.update(
        {
            "passed": passed,
            "failed": total - passed,
            "capability_failures": capability,
            "infrastructure_failures": infra,
            "pass_at_1_percent": round((passed / total) * 100, 2),
            "pass_at_1_adjusted_percent": round((passed / scored) * 100, 2) if scored else 0.0,
            "scored_problems": scored,
            "harness_version": "prompt-preamble-fixed",
        }
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": merged}, f, indent=2)

    print(f"\n  pass@1 (raw):      {summary['pass_at_1_percent']}%  ({passed}/{total})")
    print(f"  pass@1 (adjusted): {summary['pass_at_1_adjusted_percent']}%  ({passed}/{scored})")
    print(f"  capability fails: {capability} | infra fails: {infra}")
    print(f"  Saved -> {path}")
    return summary


if __name__ == "__main__":
    rerun(sys.argv[1], sys.argv[2])
