#!/usr/bin/env python3
"""Standalone localizer measurement: recall@k, precision@k, MRR — zero LLM.

WHY THIS EXISTS
---------------
`docs/SWEBENCH-REPORT.md` names localization as the ceiling on resolve rate: at
recall@3 = 70%, roughly 30% of instances point the generator at the wrong file, and no
amount of patch quality recovers from that. But that 70% came from a 40-instance sample,
which carries a 95% CI of roughly +/-14pp — too wide to act on, and it was only ever
reported as a by-product of a full generation run (expensive, LLM-bound, network-bound).

`localize()` is pure lexical scoring with no model call, so its accuracy can be measured
directly, offline, over every locally-cloned instance. This script does exactly that and
nothing else: no generation, no patching, no grading.

METRICS (all set operations against the gold patch — no LLM judges anything)
  recall@k     fraction of gold files that appear in the top-k ranking
  hit@k        fraction of instances where at least one gold file is in the top-k
  precision@k  fraction of the top-k that are gold files
  MRR          mean reciprocal rank of the first gold file

`hit@k` is reported separately from `recall@k` because they answer different questions
and prior reports conflated them: on a single-gold-file instance they coincide, but on a
multi-file fix (12.8% of the set) recall punishes a partial find while hit does not.

USAGE
  python benchmarks/localizer_recall.py --limit 50              # quick sample
  python benchmarks/localizer_recall.py                          # every local instance
  python benchmarks/localizer_recall.py --repo django/django     # one repo
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.swebench_harness import (  # noqa: E402
    checkout_worktree,
    localize,
    remove_worktree,
    repo_path,
)
from benchmarks.localizer_graph import localize_graph  # noqa: E402

DATASET = "benchmarks/results/swebench_verified_local.json"
DEFAULT_KS = (1, 3, 5, 10)

# Two arms over the SAME instances: the flat scorer in swebench_harness vs the staged
# graph. Same worktree, same top_k, same scoring code — the only variable is the ranker.
ARMS = {"flat": localize, "graph": localize_graph}


def gold_files(patch: str) -> list[str]:
    """Files the reference patch actually edits — the ground truth, straight from the diff."""
    return sorted({m for m in re.findall(r"^\+\+\+ b/(.+)$", patch, re.M)})


def locally_available(rows: list[dict]) -> list[dict]:
    """Instances whose repo is already cloned; anything else would need the network."""
    return [r for r in rows if os.path.isdir(os.path.join(repo_path(r["repo"]), ".git"))]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval — reported so a point estimate is never read as exact."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def measure_instance(inst: dict, max_k: int, arms: tuple[str, ...] = ("flat",)) -> dict | None:
    """Rank files for one instance and score every arm against its gold patch.

    All arms run inside ONE worktree checkout, so they see byte-identical source. That
    makes the comparison genuinely paired: any difference is the ranker, not the
    environment, and no arm can be advantaged by a different repo state.
    """
    gold = gold_files(inst["patch"])
    if not gold:
        return None

    dest = os.path.join("/tmp", f"loc-{inst['instance_id']}")
    remove_worktree(inst["repo"], dest)
    try:
        root = checkout_worktree(inst["repo"], inst["base_commit"], dest)
    except Exception as exc:  # infrastructure, NOT a localizer failure — kept separate
        return {"instance_id": inst["instance_id"], "repo": inst["repo"],
                "error": f"{type(exc).__name__}: {exc}"}

    per_arm: dict[str, dict] = {}
    try:
        for arm in arms:
            started = time.time()
            ranked = ARMS[arm](inst["problem_statement"], root, top_k=max_k)
            elapsed = time.time() - started
            first = next((i + 1 for i, f in enumerate(ranked) if f in set(gold)), None)
            per_arm[arm] = {
                "ranked": ranked,
                "first_hit_rank": first,
                "reciprocal_rank": (1.0 / first) if first else 0.0,
                "seconds": round(elapsed, 3),
            }
    finally:
        remove_worktree(inst["repo"], dest)

    primary = per_arm[arms[0]]
    return {
        "instance_id": inst["instance_id"],
        "repo": inst["repo"],
        "difficulty": inst.get("difficulty"),
        "gold": gold,
        "arms": per_arm,
        "error": None,
        **primary,  # primary arm's fields stay top-level for backward compatibility
    }


def aggregate(results: list[dict], ks: tuple[int, ...]) -> dict:
    """Fold per-instance rankings into the reported metrics."""
    scored = [r for r in results if not r.get("error")]
    infra = [r for r in results if r.get("error")]
    n = len(scored)
    summary: dict = {
        "instances_scored": n,
        "infrastructure_failures": len(infra),
        "mrr": round(sum(r["reciprocal_rank"] for r in scored) / n, 4) if n else 0.0,
    }

    for k in ks:
        recalls, hits, precisions = [], 0, []
        for r in scored:
            gold, top = set(r["gold"]), r["ranked"][:k]
            found = len(gold & set(top))
            recalls.append(found / len(gold))
            hits += 1 if found else 0
            precisions.append(found / k)
        lo, hi = wilson(hits, n)
        summary[f"recall@{k}"] = round(100 * sum(recalls) / n, 2) if n else 0.0
        summary[f"hit@{k}"] = round(100 * hits / n, 2) if n else 0.0
        summary[f"hit@{k}_ci95"] = [round(100 * lo, 2), round(100 * hi, 2)]
        summary[f"precision@{k}"] = round(100 * sum(precisions) / n, 2) if n else 0.0

    by_repo: dict[str, dict] = {}
    for repo, group in _group(scored, "repo").items():
        g = len(group)
        by_repo[repo] = {
            "n": g,
            "hit@3": round(100 * sum(1 for r in group
                                     if set(r["gold"]) & set(r["ranked"][:3])) / g, 2),
            "mrr": round(sum(r["reciprocal_rank"] for r in group) / g, 4),
        }
    summary["by_repo"] = by_repo

    by_gold: dict[str, dict] = {}
    for bucket, group in _group(scored, lambda r: "single" if len(r["gold"]) == 1 else "multi").items():
        g = len(group)
        by_gold[bucket] = {
            "n": g,
            "recall@3": round(100 * sum(len(set(r["gold"]) & set(r["ranked"][:3])) / len(r["gold"])
                                        for r in group) / g, 2),
            "hit@3": round(100 * sum(1 for r in group
                                     if set(r["gold"]) & set(r["ranked"][:3])) / g, 2),
        }
    summary["by_gold_count"] = by_gold
    return summary


def _group(rows: list[dict], key) -> dict:
    out = defaultdict(list)
    getter = key if callable(key) else (lambda r: r[key])
    for r in rows:
        out[getter(r)].append(r)
    return dict(out)


def main(args: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure localizer recall (zero LLM)")
    ap.add_argument("--limit", type=int, default=0, help="Cap instances (0 = all available)")
    ap.add_argument("--repo", default=None, help="Restrict to one repo slug")
    ap.add_argument("--max-k", type=int, default=10)
    ap.add_argument("--out", default="benchmarks/results/localizer_recall.json")
    ns = ap.parse_args(args)

    rows = json.load(open(DATASET, encoding="utf-8"))
    pool = locally_available(rows)
    if ns.repo:
        pool = [r for r in pool if r["repo"] == ns.repo]
    if ns.limit:
        pool = pool[: ns.limit]

    if not pool:
        print("No locally-cloned instances match. Nothing measured.", file=sys.stderr)
        return 1

    print(f"Measuring {len(pool)} instances across "
          f"{len(Counter(r['repo'] for r in pool))} repos (zero LLM)...", flush=True)

    results = []
    for i, inst in enumerate(pool, 1):
        res = measure_instance(inst, ns.max_k)
        if res is None:
            continue
        results.append(res)
        if i % 10 == 0 or i == len(pool):
            done = [r for r in results if not r.get("error")]
            hits = sum(1 for r in done if r["first_hit_rank"] and r["first_hit_rank"] <= 3)
            rate = (100 * hits / len(done)) if done else 0.0
            print(f"  [{i}/{len(pool)}] hit@3 so far: {rate:.1f}%", flush=True)

    summary = aggregate(results, tuple(k for k in DEFAULT_KS if k <= ns.max_k))

    os.makedirs(os.path.dirname(ns.out), exist_ok=True)
    with open(ns.out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "results": results}, fh, indent=1)

    print("\n=== LOCALIZER MEASUREMENT ===")
    print(f"instances scored      : {summary['instances_scored']}")
    print(f"infrastructure failures: {summary['infrastructure_failures']}")
    print(f"MRR                   : {summary['mrr']}")
    for k in DEFAULT_KS:
        if f"recall@{k}" not in summary:
            continue
        ci = summary[f"hit@{k}_ci95"]
        print(f"  k={k:<3} recall={summary[f'recall@{k}']:6.2f}%  "
              f"hit={summary[f'hit@{k}']:6.2f}% (95% CI {ci[0]:.1f}-{ci[1]:.1f})  "
              f"precision={summary[f'precision@{k}']:6.2f}%")
    print("\nby repo (hit@3):")
    for repo, s in sorted(summary["by_repo"].items()):
        print(f"  {repo:28} n={s['n']:4d}  hit@3={s['hit@3']:6.2f}%  mrr={s['mrr']}")
    print("\nby gold-file count:")
    for bucket, s in sorted(summary["by_gold_count"].items()):
        print(f"  {bucket:8} n={s['n']:4d}  recall@3={s['recall@3']:6.2f}%  hit@3={s['hit@3']:6.2f}%")
    print(f"\nsaved -> {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
