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

from benchmarks.swebench_harness import (  # noqa: E402
    checkout_worktree,
    localize,
    remove_worktree,
    repo_path,
)
from benchmarks.localizer_graph import localize_ensemble, localize_graph  # noqa: E402

DATASET = "benchmarks/results/swebench_verified_local.json"
DEFAULT_KS = (1, 3, 5, 10)

# Arms over the SAME instances: the flat scorer in swebench_harness, the staged graph,
# and their interleaved ensemble. Same worktree, same top_k — only the ranker varies.
ARMS = {"flat": localize, "graph": localize_graph, "ensemble": localize_ensemble}


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


def paired_comparison(results: list[dict], a: str, b: str, k: int = 3) -> dict:
    """McNemar's exact test over the SAME instances — the honest way to compare arms.

    Two rankers on the same 336 instances are paired data. Comparing two independent
    proportions would throw away that pairing and widen the interval for no reason.
    Only the DISCORDANT pairs (one arm hits, the other misses) carry information.
    """
    scored = [r for r in results if not r.get("error") and "arms" in r]
    def hit(r, arm):
        return bool(set(r["gold"]) & set(r["arms"][arm]["ranked"][:k]))

    both = a_only = b_only = neither = 0
    gained, lost = [], []
    for r in scored:
        ha, hb = hit(r, a), hit(r, b)
        if ha and hb:
            both += 1
        elif ha:
            a_only += 1
            lost.append(r["instance_id"])   # b lost what a had
        elif hb:
            b_only += 1
            gained.append(r["instance_id"])
        else:
            neither += 1

    # Exact binomial two-sided p on the discordant pairs.
    n_disc = a_only + b_only
    if n_disc == 0:
        p = 1.0
    else:
        smaller = min(a_only, b_only)
        tail = sum(math.comb(n_disc, i) for i in range(smaller + 1)) / (2 ** n_disc)
        p = min(1.0, 2 * tail)

    n = len(scored) or 1
    return {
        "n": len(scored),
        f"{a}_hit@{k}": round(100 * (both + a_only) / n, 2),
        f"{b}_hit@{k}": round(100 * (both + b_only) / n, 2),
        "delta_pp": round(100 * (b_only - a_only) / n, 2),
        "both": both, "neither": neither,
        f"only_{a}": a_only, f"only_{b}": b_only,
        "discordant": n_disc,
        "mcnemar_exact_p": round(p, 6),
        "gained_examples": gained[:8],
        "lost_examples": lost[:8],
    }


def main(args: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure localizer recall (zero LLM)")
    ap.add_argument("--limit", type=int, default=0, help="Cap instances (0 = all available)")
    ap.add_argument("--repo", default=None, help="Restrict to one repo slug")
    ap.add_argument("--max-k", type=int, default=10)
    ap.add_argument("--arms", default="flat",
                    help="Comma-separated ranker arms to run: flat, graph")
    ap.add_argument("--out", default="benchmarks/results/localizer_recall.json")
    ns = ap.parse_args(args)

    arms = tuple(a.strip() for a in ns.arms.split(",") if a.strip())
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        print(f"Unknown arm(s): {unknown}. Available: {sorted(ARMS)}", file=sys.stderr)
        return 1

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
          f"{len(Counter(r['repo'] for r in pool))} repos | arms={list(arms)} (zero LLM)...",
          flush=True)

    results = []
    for i, inst in enumerate(pool, 1):
        res = measure_instance(inst, ns.max_k, arms)
        if res is None:
            continue
        results.append(res)
        if i % 10 == 0 or i == len(pool):
            done = [r for r in results if not r.get("error")]
            parts = []
            for arm in arms:
                h = sum(1 for r in done
                        if set(r["gold"]) & set(r["arms"][arm]["ranked"][:3]))
                parts.append(f"{arm}={100 * h / len(done):.1f}%" if done else f"{arm}=-")
            print(f"  [{i}/{len(pool)}] hit@3 " + "  ".join(parts), flush=True)

    ks = tuple(k for k in DEFAULT_KS if k <= ns.max_k)
    per_arm_summary = {}
    for arm in arms:
        view = [
            {**r, **r["arms"][arm]} if not r.get("error") else r
            for r in results
        ]
        per_arm_summary[arm] = aggregate(view, ks)
    summary = per_arm_summary[arms[0]]

    payload = {"summary": summary, "arms": per_arm_summary, "results": results}
    if len(arms) == 2:
        payload["paired"] = paired_comparison(results, arms[0], arms[1])

    os.makedirs(os.path.dirname(ns.out), exist_ok=True)
    with open(ns.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)

    print("\n=== LOCALIZER MEASUREMENT ===")
    for arm in arms:
        s = per_arm_summary[arm]
        print(f"\n--- arm: {arm} ---")
        print(f"instances scored       : {s['instances_scored']}")
        print(f"infrastructure failures: {s['infrastructure_failures']}")
        print(f"MRR                    : {s['mrr']}")
        for k in ks:
            ci = s[f"hit@{k}_ci95"]
            print(f"  k={k:<3} recall={s[f'recall@{k}']:6.2f}%  "
                  f"hit={s[f'hit@{k}']:6.2f}% (95% CI {ci[0]:.1f}-{ci[1]:.1f})  "
                  f"precision={s[f'precision@{k}']:6.2f}%")

    if "paired" in payload:
        p = payload["paired"]
        a, b = arms
        print(f"\n=== PAIRED COMPARISON ({a} vs {b}, n={p['n']}, McNemar exact) ===")
        print(f"  {a:6} hit@3 : {p[f'{a}_hit@3']:6.2f}%")
        print(f"  {b:6} hit@3 : {p[f'{b}_hit@3']:6.2f}%")
        print(f"  delta        : {p['delta_pp']:+.2f} pp")
        print(f"  discordant   : {p['discordant']}  "
              f"(only-{a}={p[f'only_{a}']}, only-{b}={p[f'only_{b}']})")
        print(f"  exact p      : {p['mcnemar_exact_p']}")
        verdict = "SIGNIFICANT" if p["mcnemar_exact_p"] < 0.05 else "not significant"
        print(f"  verdict      : {verdict} at alpha=0.05")

    print("\nby repo (hit@3, primary arm):")
    for repo, s in sorted(summary["by_repo"].items()):
        print(f"  {repo:28} n={s['n']:4d}  hit@3={s['hit@3']:6.2f}%  mrr={s['mrr']}")
    print("\nby gold-file count (primary arm):")
    for bucket, s in sorted(summary["by_gold_count"].items()):
        print(f"  {bucket:8} n={s['n']:4d}  recall@3={s['recall@3']:6.2f}%  hit@3={s['hit@3']:6.2f}%")
    print(f"\nsaved -> {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
