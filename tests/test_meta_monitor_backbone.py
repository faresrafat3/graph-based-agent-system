"""TDD tests for Task 5 — Meta monitor IS the existing systems_layer (extension, NOT a new loop).

Fares's plan (Q from opus-5 review): the meta-loop is the LIVE BACKBONE, not an "extension"
we bolt on. These tests prove the existing systems_layer graph runs end-to-end (measure ->
philosopher -> ... -> record) and that the forge/context/topology pieces assemble ON TOP of it
(P-NO-FORK). No second governor is created.
"""

import json
import pytest

from agents.systems_layer import build_systems_graph
from agents.agent_forge import forge_agent
from agents.context_system_view import build_context_view
from agents.topology_assembler import assemble_topology


def _base_state():
    return {
        "prior_measurement": {"complexity_score": 3, "repeated_hypothesis_count": 0,
                               "breach_count": 0, "success_rate": 80},
        "current_measurement": {"complexity_score": 9, "repeated_hypothesis_count": 2,
                                 "breach_count": 1, "success_rate": 60},
        "delta": None, "proposals": [], "decisions": [], "control_proposals": [],
        "counter_proposals": [], "philosopher_strategy": None, "reconciled_spec": None,
        "cycle_log": [],
    }


def test_systems_layer_runs_end_to_end_is_live_backbone():
    graph = build_systems_graph()
    result = graph.invoke(_base_state(), config={"configurable": {"thread_id": "t5-e2e"}})
    # the meta-loop actually executed its full pipeline (auditable cycle_log proves it ran)
    assert any("measure:" in line for line in result["cycle_log"])
    assert any("philosopher:" in line for line in result["cycle_log"])
    assert any("record:" in line for line in result["cycle_log"])
    # high complexity -> council convened (the local sage council is live)
    assert any("convened" in line for line in result["cycle_log"])


def test_forge_context_topology_assemble_on_top_of_backbone_no_fork():
    # The three Task 2/3/4 pieces compose WITHOUT replacing the meta-loop (P-NO-FORK).
    a = forge_agent("meta_a", ["P1", "P4"], "bounded probe", {"bounded_probe": True, "verify_node": True})
    ctx = build_context_view(a, {"cycle_log": ["measure: x"]})
    topo = assemble_topology([a])
    assert ctx["context_is_system"] is True
    assert topo["extends"] == "systems_layer"
    # the meta-loop graph still compiles independently (it is THE backbone)
    assert build_systems_graph() is not None
