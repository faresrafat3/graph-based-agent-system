#!/usr/bin/env python3
"""A/B study: Context-Isolated Reasoning (CIR) vs Fused reasoning on the Karpathy pipeline.

Fares's open question (COMPARATIVE-STUDY-2026-08-05.md): all 3 models noted "no controlled
A/B exists -> salience, not superiority." This script runs a REAL A/B:

  - FUSED mode: decompose_requirements gets requirements + project_context + constraints
    together (standard pipeline - reasoning contaminated by execution-context noise).
  - CIR mode: a pure-strategy thinker (opus-5, no context/constraints) emits a STRATEGY
    buffer; decompose_requirements gets requirements + strategy only (context-isolated).

Metric (zero-LLM, deterministic): decomposition validator breach count + task count +
metadata completeness. Lower breaches + richer tasks = better framing.

Outputs JSONL to benchmarks/results/ab_cir_<timestamp>.jsonl

Run: python scripts/ab_cir_study.py --scenarios 8
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from agents.karpathy_pipeline import decompose_requirements, validate_output
from benchmarks.benchmark_suite import BENCHMARK_SCENARIOS

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from system.opus5_consult import consult_opus5  # agent-driven opus-5 channel

STRATEGY_PROMPT = """You are a PURE STRATEGY thinker. No code, no tool schemas, no constraints.
Given only a product requirement, output a concise STRATEGY FRAMING: the 3-5 key architectural
or methodological decisions that should guide any implementation. Plain prose, no code.
Max 120 words."""


def _safe_decompose(requirements: str, project_context: str, constraints: str) -> dict:
    """Call decompose_requirements with a timeout-safe wrapper (stepfun can flake)."""
    import time as _t
    last = {}
    for attempt in range(3):
        try:
            return decompose_requirements(
                requirements=requirements,
                project_context=project_context,
                constraints=constraints,
            )
        except Exception as exc:  # StepfunAPIError / timeout — flaky infra, not logic
            last = {"_error": f"{type(exc).__name__}: {exc}"}
            _t.sleep(2 * (attempt + 1))
    return last


def _fused_decompose(scn: dict) -> dict:
    """Standard pipeline: requirements + context + constraints mixed (fused)."""
    return _safe_decompose(
        requirements=scn["requirements"],
        project_context=scn.get("project_context", ""),
        constraints=scn.get("constraints", ""),
    )


def _cir_decompose(scn: dict) -> tuple[dict, str]:
    """CIR: pure-strategy thinker emits framing, then decompose on requirements+strategy only
    (context-isolated: no execution-context noise). Strategy is INJECTED as project_context
    to simulate the Reconciler handoff."""
    strategy = consult_opus5(f"{STRATEGY_PROMPT}\n\nREQUIREMENT:\n{scn['requirements']}")
    if strategy.startswith("[opus5: channel-unavailable]"):
        strategy = ""
    decomp = _safe_decompose(
        requirements=scn["requirements"],
        project_context=f"[STRATEGY FRAMING]\n{strategy}" if strategy else "",
        constraints="",
    )
    if isinstance(decomp, dict) and strategy:
        decomp = dict(decomp)
        decomp["_cir_strategy"] = strategy
    return decomp, strategy


def _score(decomp: dict) -> dict:
    val = validate_output(target_output=decomp, required_keys=["tasks", "metadata"])
    tasks = decomp.get("tasks", []) if isinstance(decomp, dict) else []
    meta = decomp.get("metadata", {}) if isinstance(decomp, dict) else {}
    return {
        "valid": val["success"],
        "breaches": len(val.get("breaches", [])),
        "task_count": len(tasks),
        "metadata_keys": len(meta) if isinstance(meta, dict) else 0,
    }


def main(args=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=8)
    ap.add_argument("--no-opus5", action="store_true", help="skip CIR opus-5 call (fast mock)")
    args = ap.parse_args(args)

    scns = BENCHMARK_SCENARIOS[: args.scenarios]

    out_path = PROJECT_ROOT / "benchmarks" / "results" / f"ab_cir_{int(time.time())}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for scn in scns:
        fused = _fused_decompose(scn)
        fused_score = _score(fused)

        if args.no_opus5:
            cir = dict(fused)
            cir["_cir_strategy"] = "(mock - no opus5)"
            strategy = "(mock)"
        else:
            cir, strategy = _cir_decompose(scn)
        cir_score = _score(cir)

        row = {
            "scenario": scn["id"],
            "fused": fused_score,
            "cir": cir_score,
            "cir_strategy_len": len(strategy),
        }
        rows.append(row)
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{scn['id']:35s} fused_breaches={fused_score['breaches']:2d} "
              f"cir_breaches={cir_score['breaches']:2d} "
              f"cir_tasks={cir_score['task_count']:2d}")

    # Summary
    f_b = sum(r["fused"]["breaches"] for r in rows)
    c_b = sum(r["cir"]["breaches"] for r in rows)
    f_t = sum(r["fused"]["task_count"] for r in rows)
    c_t = sum(r["cir"]["task_count"] for r in rows)
    verdict = "CIR wins" if (c_b < f_b or c_t > f_t) else "no clear CIR advantage"
    print(f"\n=== A/B SUMMARY (n={len(rows)}) ===")
    print(f"FUSED: total_breaches={f_b}, total_tasks={f_t}")
    print(f"CIR  : total_breaches={c_b}, total_tasks={c_t}")
    print(f"VERDICT: {verdict}")
    print(f"Results: {out_path}")


if __name__ == "__main__":
    main()
