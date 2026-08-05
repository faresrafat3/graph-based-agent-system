#!/usr/bin/env python3
"""Run one Systems Layer cycle on the live graph (in-graph meta-loop, v2+).

Feeds the prior + current measurement snapshot into the compiled LangGraph and emits
control_proposals. Per C1-rev1 the meta-loop DEFAULTS TO DENY: proposals are recorded,
never auto-applied. Optionally consults opus-5 live to pressure-review the rulings.

Usage:
    python scripts/run_systems_layer.py                 # measure + propose (safe)
    python scripts/run_systems_layer.py --opus5          # also consult opus-5 live
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.systems_layer import build_systems_graph, SystemsLayerState
from system.self_improvement import Measurement
from system.distillation_ledger import DistillationLedger, attach_opus5_review


PRIOR_SNAPSHOT = {
    "thrash_count": 0, "success_rate": 75.0, "defense_rate": 100.0,
    "quality": 0.75, "health": 77.7,
}


def _current_snapshot() -> dict:
    """Read the latest measured state. Falls back to prior if no measurement exists yet."""
    p = Path("system/measurements/measurements.jsonl")
    if not p.exists():
        return dict(PRIOR_SNAPSHOT)
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return dict(PRIOR_SNAPSHOT)
    try:
        last = json.loads(lines[-1])
        return last.get("measurement", {}).get("current", PRIOR_SNAPSHOT)
    except Exception:
        return dict(PRIOR_SNAPSHOT)


def run(consult_opus5: bool) -> dict:
    graph = build_systems_graph()
    current = _current_snapshot()
    init = SystemsLayerState(
        prior_measurement=dict(PRIOR_SNAPSHOT),
        current_measurement=current,
        delta=None, proposals=[], decisions=[],
        control_proposals=[], counter_proposals=[], cycle_log=[],
    )
    result = graph.invoke(init, config={"configurable": {"thread_id": "cron-cycle"}})

    proposals = result["control_proposals"]
    print(f"[systems_layer] cycle produced {len(proposals)} control proposal(s) "
          f"(default-deny: all held unless independently opted-in)")
    for cp in proposals:
        print(f"  - {cp['kind']}: {cp['status']} (principle {cp.get('principle_ref')})")

    if consult_opus5 and proposals:
        ledger = DistillationLedger()
        for cp in proposals:
            rid = cp.get("principle_ref", "P?")
            ruling_text = cp.get("hypothesis", "")
            try:
                prov = attach_opus5_review(ledger, rid, ruling_text)
                print(f"[opus5] reviewed {rid}: {prov.get('channel')} "
                      f"-> {str(prov.get('reply'))[:80]}...")
            except Exception as e:
                print(f"[opus5] review of {rid} failed: {e}")

    return {"proposals": proposals, "cycle_log": result["cycle_log"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run one Systems Layer in-graph cycle")
    ap.add_argument("--opus5", action="store_true", help="Consult opus-5 live to review rulings")
    args = ap.parse_args()
    run(consult_opus5=args.opus5)
