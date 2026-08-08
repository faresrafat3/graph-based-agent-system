"""
Grade AlphaCode SWE-bench predictions by calling run_instance sequentially.

The upstream `run_evaluation` hangs inside `run_threadpool` (ThreadPoolExecutor +
shared docker client → C-level futex deadlock in this environment). Running
`run_instance` directly, sequentially, works (verified: 1142 resolves). This script
replicates the grader's per-instance logic without the deadlocking threadpool so we
get a real Docker-grade resolve rate for the AlphaCode arm.

Usage:
    python benchmarks/grade_alphacode.py \
        --dataset benchmarks/results/swebench_verified_local.json \
        --preds benchmarks/results/swebench_alphacode_requests_preds.jsonl \
        --run_id gbas_alphacode_final
"""
import argparse
import json
import logging
import time
from pathlib import Path

import docker

from swebench.harness.run_evaluation import get_dataset_from_preds, run_instance
from swebench.harness.test_spec.test_spec import make_test_spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--preds", required=True)
    ap.add_argument("--run_id", default="gbas_alphacode")
    ap.add_argument("--instance_image_tag", default="latest")
    ap.add_argument("--env_image_tag", default="latest")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    preds = {p["instance_id"]: p for p in (json.loads(l) for l in open(args.preds))}
    instances = get_dataset_from_preds(
        args.dataset, "test", None, preds, args.run_id, False
    )
    client = docker.from_env()
    test_specs = [make_test_spec(i) for i in instances]

    logging.basicConfig(level=logging.INFO)

    results = []
    resolved = 0
    for spec in test_specs:
        iid = spec.instance_id
        t = time.time()
        try:
            res = run_instance(
                spec,
                preds[iid],
                False,  # should_remove
                False,  # force_rebuild
                client,
                args.run_id,
                args.timeout,
                False,  # rewrite_reports
            )
            ok = bool(res.get("resolved"))
            resolved += 1 if ok else 0
            print(f"[graded] {iid}: resolved={ok} ({round(time.time()-t,1)}s)")
            results.append({"instance_id": iid, "resolved": ok})
        except Exception as e:  # surface infra failures honestly (Law 3)
            import traceback

            traceback.print_exc()
            print(f"[graded] {iid}: ERROR {type(e).__name__}: {str(e)[:200]}")
            results.append({"instance_id": iid, "resolved": False, "error": str(e)})

    total = len(results)
    print(f"\n=== AlphaCode Docker grade: {resolved}/{total} resolved ===")
    for r in results:
        print(f"  {r['instance_id']:<32} {'RESOLVED' if r['resolved'] else 'not resolved'}")

    out = Path("benchmarks/results") / f"alphacode_grade_{args.run_id}.json"
    out.write_text(json.dumps({"total": total, "resolved": resolved, "results": results}, indent=2))
    print(f"Report -> {out}")


if __name__ == "__main__":
    main()
