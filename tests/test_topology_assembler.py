"""TDD tests for Task 4 — Topology Assembler (typed focus edges, EXTEND systems_layer).

Verifies: each forged agent gets a FOCUS edge (structural binding) + VERIFY edge (P2),
untyped edges are HARD-rejected, and the assembler is pure (no global mutation).
"""

import pytest

from agents.agent_forge import forge_agent
from agents.topology_assembler import (
    build_focus_edges,
    assemble_topology,
    GraphEdge,
    ALLOWED_EDGE_TYPES,
)


def _agents():
    a = forge_agent("topo_a", ["P3"], "probe auth", {"bounded_probe": True, "verify_node": True})
    b = forge_agent("topo_b", ["P6"], "route contradiction", {"peer_review": True})
    return [a, b]


def test_focus_edge_structurally_binds_agent_to_task():
    edges = build_focus_edges(_agents())
    focus = [e for e in edges if e.kind == "focus"]
    assert len(focus) == 2  # one per agent
    assert any(e.src == "topo_a" and e.dst == "task:probe auth" for e in focus)
    # the focus payload carries the governance profile (the structural constraint)
    topo_a_focus = next(e for e in focus if e.src == "topo_a")
    assert "bounded_probe" in topo_a_focus.payload["governance_profile"]


def test_verify_edge_closes_every_write_p2():
    edges = build_focus_edges(_agents())
    verify = [e for e in edges if e.kind == "verify"]
    assert len(verify) == 2
    assert any(e.dst == "verify:topo_a" for e in verify)


def test_peer_review_and_escalate_edges_conditional():
    edges = build_focus_edges(_agents())
    kinds = {e.kind for e in edges}
    assert "peer-review" in kinds       # topo_b has peer_review=True
    assert "escalate" in kinds           # topo_a has bounded_probe -> escalate edge


def test_untyped_edge_hard_rejected():
    with pytest.raises(ValueError):
        GraphEdge(src="x", dst="y", kind="illegal_edge")


def test_assemble_topology_is_pure_and_extends():
    topo = assemble_topology(_agents())
    assert topo["extends"] == "systems_layer"   # P-NO-FORK
    assert topo["edge_count"] >= 4
    assert "topo_a" in topo["nodes"]
    assert "task:probe auth" in topo["nodes"]
    # all emitted edges are typed (constitution-enforced)
    assert all(e["kind"] in ALLOWED_EDGE_TYPES for e in topo["edges"])
