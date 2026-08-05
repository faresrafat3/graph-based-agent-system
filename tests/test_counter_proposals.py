"""TDD tests for the counter-proposal channel (Ruling C1-rev1 / P3 / P6).

Asserts the channel is a REAL, persisted mechanism — not a ghost dependency:
  - domain agents submit challenges via submit_counter_proposal()
  - challenges persist and are read back via get_pending_challenges()
  - the systems layer surfaces them (via get_pending_challenges, not an empty placeholder)
  - resolution requires an explicit reviewer (human checkpoint / opus-5 when live) — never
    a fabricated opus-5 reply (Law 11)
"""

from agents.systems_layer import apply_or_escalate_node
from system.counter_proposals import (
    clear_ledger_for_testing,
    get_all_challenges,
    get_pending_challenges,
    review_challenge,
    submit_counter_proposal,
)


def setup_function(_fn):
    # Each test starts from a clean ledger so results are deterministic and
    # do not depend on order-of-execution across the suite.
    clear_ledger_for_testing()


def test_submit_persists_and_is_readable():
    cp = submit_counter_proposal(
        from_agent="security",
        target_proposal_id="prop-001",
        challenge="Increasing probe budget without threat-model review violates P6.",
        evidence={"current_budget": 100, "proposed_budget": 500},
    )
    pending = get_pending_challenges()
    assert len(pending) == 1
    assert pending[0].id == cp.id
    assert pending[0].from_agent == "security"
    assert pending[0].challenge.startswith("Increasing probe budget")
    assert pending[0].status == "pending"


def test_get_pending_excludes_reviewed():
    cp = submit_counter_proposal(
        from_agent="architect",
        target_proposal_id="prop-002",
        challenge="Topology change needs a reversibility proof first.",
    )
    reviewed = review_challenge(
        cp.id, "human@review", "rejected",
        note="Deferred pending reversibility proof.",
        resolution_channel="human_checkpoint",
    )
    assert reviewed.status == "reviewed"
    assert reviewed.resolution_channel == "human_checkpoint"
    assert get_pending_challenges() == []  # reviewed items leave the pending queue
    # but the full history is preserved (Law 16)
    assert len(get_all_challenges()) == 1


def test_systems_layer_surfaces_real_channel():
    # The apply node must read from the persisted channel, not an empty state placeholder.
    submit_counter_proposal(
        from_agent="Task Decomposer",
        target_proposal_id="prop-003",
        challenge="probe_budget too high for CLEAR domain",
    )
    state = {
        "control_proposals": [],
        "cycle_log": [],
        # counter_proposals NOT injected into state — must come from the real channel
    }
    out = apply_or_escalate_node(state)
    assert any("counter" in line.lower() for line in out["cycle_log"])
    assert len(get_pending_challenges()) >= 1


def test_review_rejects_invalid_decision():
    cp = submit_counter_proposal(
        from_agent="developer",
        target_proposal_id="prop-004",
        challenge="Agent addition overlaps an existing role (P2).",
    )
    try:
        review_challenge(cp.id, "human@review", "maybe")
        assert False, "review_challenge should reject an invalid decision"
    except ValueError:
        pass
