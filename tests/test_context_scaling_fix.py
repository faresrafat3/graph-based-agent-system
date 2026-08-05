"""TDD tests for T1-fix#3 — context-scaling break closed.

Covers: (a) JsonlCheckpointSaver persists graph state to disk (no MemorySaver volatility),
(b) the systems_layer compiles + runs with the disk saver, (c) build_context_view bounds
cycle_log + peer list explicitly (observable at 7x scale).
"""

import os
import json

from agents.disk_saver import JsonlCheckpointSaver
from agents.context_system_view import build_context_view, MAX_PEERS, MAX_CYCLE_LOG
from agents.agent_forge import forge_agent


def _fresh_saver(tmp_path):
    p = tmp_path / "ckpts.jsonl"
    if p.exists():
        p.unlink()
    return JsonlCheckpointSaver(p)


def test_disk_saver_persists_across_instances(tmp_path):
    saver1 = _fresh_saver(tmp_path)
    cfg = {"configurable": {"thread_id": "t1", "checkpoint_id": "c0"}}
    saver1.put(cfg, {"id": "c1", "cycle_log": ["m1", "m2"]}, {"ts": 1}, {"ch": 1})
    # a brand-new saver instance (simulating a process restart) must still read the state
    saver2 = JsonlCheckpointSaver(tmp_path / "ckpts.jsonl")
    tup = saver2.get_tuple({"configurable": {"thread_id": "t1"}})
    assert tup is not None
    assert tup.checkpoint["cycle_log"] == ["m1", "m2"]
    assert os.path.exists(tmp_path / "ckpts.jsonl")


def test_systems_layer_runs_with_disk_saver(tmp_path):
    from agents.systems_layer import build_systems_graph
    graph = build_systems_graph(_fresh_saver(tmp_path))
    state = {
        "prior_measurement": {"complexity_score": 3, "repeated_hypothesis_count": 0,
                               "breach_count": 0, "success_rate": 80},
        "current_measurement": {"complexity_score": 9, "repeated_hypothesis_count": 2,
                                 "breach_count": 1, "success_rate": 60},
        "delta": None, "proposals": [], "decisions": [], "control_proposals": [],
        "counter_proposals": [], "philosopher_strategy": None, "reconciled_spec": None,
        "cycle_log": [],
    }
    out = graph.invoke(state, config={"configurable": {"thread_id": "disk-t"}})
    assert any("record:" in line for line in out["cycle_log"])


def test_context_view_bounded_cycle_log_and_peers():
    a = forge_agent("scale_a", ["P5"], "persist state")
    # 120 cycles -> bounded to most-recent MAX_CYCLE_LOG
    big_log = [f"cycle_{i}" for i in range(120)]
    view = build_context_view(a, {"cycle_log": big_log})
    sc = view["system_context"]
    assert len(sc["cycle_log"]) == MAX_CYCLE_LOG
    assert sc["cycle_log_truncated"] is True
    assert len(sc["peer_agents"]) <= MAX_PEERS
