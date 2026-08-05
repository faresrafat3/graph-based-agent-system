"""TDD tests for C1-rev1 (opus-5 live review fixes): default-deny + counter-proposal.

After opus-5 reviewed C1, four fixes were required. This test asserts the apply node:
  - defaults to DENY (proposes only), never auto-applies even when reversible
  - supports an independent reversibility judgment (not self-assessed)
  - supports a counter-proposal channel from domain agents
"""

from agents.systems_layer import (
    SystemsLayerState,
    gate_node,
    apply_or_escalate_node,
)
from system.self_improvement import Measurement, compare, propose, distill_opus5


def _seeded_state(reversible_self_assessed: bool = True):
    before = Measurement(75.0, 100.0, 0.75, 77.7, 0, None)
    after = Measurement(75.0, 100.0, 0.75, 77.7, 3, None)
    delta = compare(before, after)
    proposals = propose(delta)
    decisions = [{"proposal": p, "distilled": distill_opus5(p)} for p in proposals]
    s = SystemsLayerState(
        prior_measurement={}, current_measurement={},
        delta=delta, proposals=proposals, decisions=decisions,
        control_proposals=[], cycle_log=[],
    )
    s = gate_node(s)
    s["control_proposals"][0]["reversible"] = reversible_self_assessed
    s["control_proposals"][0]["gated_accepted"] = True
    return s


def test_default_deny_even_if_reversible():
    # opus-5 fix #2: meta-loop NEVER auto-applies. Reversible + accepted -> still PROPOSED,
    # not APPLIED, unless an independent opt-in flag is set.
    s = _seeded_state(reversible_self_assessed=True)
    out = apply_or_escalate_node(s)
    assert out["control_proposals"][0]["status"] == "proposed"
    assert "propose:" in out["cycle_log"][-1].lower()
    assert out["control_proposals"][0]["status"] != "applied"


def test_opt_in_apply_requires_independent_flag():
    # Application only happens with an explicit opt-in flag that is externally judged.
    s = _seeded_state(reversible_self_assessed=True)
    s["control_proposals"][0]["opt_in_apply"] = True  # independent/human-set, not self
    s["control_proposals"][0]["reversibility_judged_by"] = "governance_ledger"
    out = apply_or_escalate_node(s)
    assert out["control_proposals"][0]["status"] == "applied"


def test_counter_proposal_channel_present():
    # opus-5 fix #4: domain agents can challenge the meta-loop framing.
    # The challenge is submitted through the real channel (system.counter_proposals),
    # persisted, and then surfaced by apply_or_escalate_node via get_pending_challenges()
    # (not an in-memory state placeholder). We start from a clean ledger so the test is
    # deterministic and does not depend on order-of-execution across the suite.
    from system.counter_proposals import (
        clear_ledger_for_testing,
        submit_counter_proposal,
    )

    clear_ledger_for_testing()
    submit_counter_proposal(
        from_agent="Task Decomposer",
        target_proposal_id="prop-001",
        challenge="probe_budget too high for CLEAR domain",
    )
    s = _seeded_state()
    out = apply_or_escalate_node(s)
    # Counter-proposals are surfaced in the cycle, not silently dropped.
    assert any("counter" in line.lower() for line in out["cycle_log"])
    # And the real channel must confirm it read the persisted challenge.
    from system.counter_proposals import get_pending_challenges

    assert len(get_pending_challenges()) >= 1
