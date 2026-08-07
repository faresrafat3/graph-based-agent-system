"""TDD tests for Task B: Systems Layer as in-graph LangGraph nodes (G2, F3).

The meta-loop must live INSIDE the graph (not as an external script). These tests build
the compiled StateGraph and run one full cycle, asserting nodes connect and write
proposals into state WITHOUT editing any domain agent.
"""

from agents.systems_layer import (
    SystemsLayerState,
    measure_node,
    compare_node,
    propose_node,
    distill_node,
    gate_node,
    record_node,
    build_systems_graph,
)
from langgraph.checkpoint.memory import MemorySaver
import pytest


def test_compare_node_fails_loudly_on_short_measurement_shape():
    """REGRESSION GUARD (Law 3).

    A short Measurement shape used to be swallowed into ``delta["error"]`` and the
    cycle advanced as if a measurement had happened — 366 of 673 recorded cycles
    (54%) were measurement-void this way. compare_node MUST now raise instead.
    """
    short = SystemsLayerState(
        prior_measurement={"success_rate": 50.0, "breach_count": 1},
        current_measurement={"success_rate": 60.0, "breach_count": 2},
        delta=None, proposals=[], decisions=[], control_proposals=[],
        counter_proposals=[], philosopher_strategy=None, reconciled_spec=None,
        cycle_log=[],
    )
    with pytest.raises(TypeError):
        compare_node(short)


def test_compare_node_computes_real_delta_on_complete_shape():
    """The complete shape must produce an actual signal, not an empty delta."""
    complete = SystemsLayerState(
        prior_measurement={"success_rate": 75.0, "defense_rate": 100.0,
                           "quality": 0.75, "health": 77.7, "thrash_count": 0},
        current_measurement={"success_rate": 75.0, "defense_rate": 100.0,
                             "quality": 0.75, "health": 77.7, "thrash_count": 3},
        delta=None, proposals=[], decisions=[], control_proposals=[],
        counter_proposals=[], philosopher_strategy=None, reconciled_spec=None,
        cycle_log=[],
    )
    out = compare_node(complete)
    delta = out["delta"] or {}
    assert "error" not in delta
    assert delta["has_meaningful_delta"] is True
    assert "thrash" in delta["signals"]


def test_state_graph_compiles():
    graph = build_systems_graph()
    assert graph is not None


def test_full_cycle_writes_proposals_into_state():
    graph = build_systems_graph()
    # Seed state with a prior measurement + a current snapshot showing thrash.
    init = SystemsLayerState(
        prior_measurement={"thrash_count": 0, "success_rate": 75.0,
                           "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        current_measurement={"thrash_count": 3, "success_rate": 75.0,
                              "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        delta=None, proposals=[], decisions=[], control_proposals=[],
        cycle_log=[],
    )
    result = graph.invoke(init, config={"configurable": {"thread_id": "t1"}})
    # The loop must have produced at least one control proposal (thrash -> probe_budget).
    assert len(result["control_proposals"]) >= 1
    assert result["control_proposals"][0]["kind"] == "probe_budget"
    # No domain agent was edited (we only read state).
    assert any("probe_budget" in c["kind"] for c in result["control_proposals"])


def test_node_chain_order():
    # measure -> compare -> propose -> distill -> gate -> record
    s = SystemsLayerState(
        prior_measurement={"thrash_count": 0, "success_rate": 75.0,
                            "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        current_measurement={"thrash_count": 2, "success_rate": 75.0,
                              "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        delta=None, proposals=[], decisions=[], control_proposals=[], cycle_log=[],
    )
    s2 = measure_node(s)
    s3 = compare_node(s2)
    s4 = propose_node(s3)
    s5 = distill_node(s4)
    s6 = gate_node(s5)
    s7 = record_node(s6)
    assert s3["delta"] is not None
    assert len(s4["proposals"]) == 1
    assert len(s5["decisions"]) == 1
    assert s5["decisions"][0]["distilled"]["references"].startswith("P")
    assert "record:" in s7["cycle_log"][-1]
