"""TDD tests for Task E / C1-rev1: apply_or_escalate node (G5, C1).

Resolves C1 per opus-5 live review: the meta-loop DEFAULTS TO DENY. Application needs an
*independent* opt-in (not self-assessed reversibility). Non-opt-in controls stay PROPOSED.
"""

from agents.systems_layer import (
    SystemsLayerState,
    gate_node,
    apply_or_escalate_node,
    build_systems_graph,
)
from system.self_improvement import Measurement, compare, propose, distill_opus5


def _seeded_state():
    before = Measurement(75.0, 100.0, 0.75, 77.7, 0, None)
    after = Measurement(75.0, 100.0, 0.75, 77.7, 3, None)
    delta = compare(before, after)
    proposals = propose(delta)
    decisions = [{"proposal": p, "distilled": distill_opus5(p)} for p in proposals]
    s = SystemsLayerState(
        prior_measurement={}, current_measurement={},
        delta=delta, proposals=proposals, decisions=decisions,
        control_proposals=[], counter_proposals=[], cycle_log=[],
    )
    return gate_node(s)


def test_reversible_but_no_opt_in_stays_proposed():
    s = _seeded_state()
    # self-assessed reversible + accepted -> still PROPOSED (default-deny, opus-5 fix #2)
    s["control_proposals"][0]["reversible"] = True
    s["control_proposals"][0]["gated_accepted"] = True
    out = apply_or_escalate_node(s)
    assert out["control_proposals"][0]["status"] == "proposed"
    assert "default-deny" in out["cycle_log"][-1]


def test_independent_opt_in_is_applied():
    s = _seeded_state()
    s["control_proposals"][0]["gated_accepted"] = True
    s["control_proposals"][0]["opt_in_apply"] = True
    s["control_proposals"][0]["reversibility_judged_by"] = "governance_ledger"
    out = apply_or_escalate_node(s)
    assert out["control_proposals"][0]["status"] == "applied"


def test_full_graph_includes_apply_node():
    graph = build_systems_graph()
    init = SystemsLayerState(
        prior_measurement={"thrash_count": 0, "success_rate": 75.0,
                           "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        current_measurement={"thrash_count": 2, "success_rate": 75.0,
                              "defense_rate": 100.0, "quality": 0.75, "health": 77.7},
        delta=None, proposals=[], decisions=[], control_proposals=[],
        counter_proposals=[], cycle_log=[],
    )
    result = graph.invoke(init, config={"configurable": {"thread_id": "apply1"}})
    assert result["control_proposals"]
    assert result["control_proposals"][0]["status"] in ("applied", "proposed", "rejected")
