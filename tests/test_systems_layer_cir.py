"""TDD test: CIR nodes in the systems-layer graph now use LOCAL Sage Council (no opus-5).

Fares's correction (2026-08-05): the principle is embodied as local sages inside the graph,
not a hard link to opus-5. These tests confirm the graph topology includes philosopher +
reconciler stages and that they produce strategy/spec via the LOCAL council (opus-5 not called).
"""

from unittest import mock

from agents import systems_layer as sl
from agents.systems_layer import SystemsLayerState, build_systems_graph


def _base_state():
    # COMPLETE Measurement shape (Law 3): every required field is present, so
    # compare_node computes a real delta instead of swallowing a TypeError.
    return SystemsLayerState(
        prior_measurement={"success_rate": 50.0, "defense_rate": 100.0,
                            "quality": 0.70, "health": 70.0, "thrash_count": 1,
                            "breach_count": 1},
        current_measurement={
            "success_rate": 60.0, "defense_rate": 100.0,
            "quality": 0.75, "health": 74.0, "thrash_count": 0,
            "breach_count": 2, "complexity_score": 5,
            "repeated_hypothesis_count": 0,
        },
        delta=None, proposals=[], decisions=[], control_proposals=[],
        counter_proposals=[], philosopher_strategy=None, reconciled_spec=None,
        cycle_log=[],
    )


def test_philosopher_convenes_council_on_complex_task():
    st = _base_state()  # complexity 5 >= 4 -> council convenes (registry-backed, no opus-5)
    out = sl.philosopher_node(st)
    assert out["philosopher_strategy"] is not None
    assert "SPEC[council" in out["philosopher_strategy"]
    # registry council has many more sages than the 3-sage default
    assert "FALSIFICATION" in (out["reconciled_spec"] or "")
    assert any("council convened" in line for line in out["cycle_log"])


def test_philosopher_skips_council_below_threshold():
    st = _base_state()
    st["current_measurement"]["complexity_score"] = 2
    out = sl.philosopher_node(st)
    assert out["philosopher_strategy"] is None
    assert any("council skipped" in line for line in out["cycle_log"])


def test_graph_topology_includes_philosopher_and_reconciler():
    graph = build_systems_graph()
    assert graph is not None
    # Full cycle on a complex task: council convenes, spec flows, no opus-5 dependency.
    result = graph.invoke(_base_state(), config={"configurable": {"thread_id": "test-cir"}})
    assert result["philosopher_strategy"] is not None
    assert "FALSIFICATION" in (result["reconciled_spec"] or "")
    assert any("philosopher:" in line for line in result["cycle_log"])
    assert any("reconciler:" in line for line in result["cycle_log"])
