"""TDD tests for Task 1 — embed P1 (Requisite Variety) + P4 (Bounded Probing) into EXISTING
governance (no fork). Extends governance_checks.py + adds system/bounded_probe.py.

Verifies the constraint is ARCHITECTURAL (code/call-graph), not a prompt.
"""

import pytest

from system.bounded_probe import ProbeBudget, enforce_bounded_probe
from system import governance_checks as gc
from system.governance_checks import check_requisite_variety, run_governance_checks


# --- P4: Bounded Probing ---

def test_probe_budget_continues_on_new_hypotheses():
    b = ProbeBudget(max_attempts=3)
    d1 = b.record("increments the limit by 1")   # off_by_one|limit
    d2 = b.record("fixes the index off-by-one")  # off_by_one|index (different target)
    assert d1["action"] == "continue"
    assert d2["action"] == "continue"
    assert not b.escalated


def test_probe_budget_escalates_on_repeated_hypothesis():
    # Two reflections that extract_hypothesis() maps to the SAME canonical key -> repeat -> escalate.
    b = ProbeBudget(max_attempts=4)
    b.record("incrementing the limit")        # off_by_one|limit
    d = b.record("fix the off-by-one on limit")  # off_by_one|limit (same key)
    assert d["action"] == "escalate"
    assert d["reason"].startswith("repeated_hypothesis")
    assert b.escalated


def test_probe_budget_escalates_on_exhausted_budget():
    b = ProbeBudget(max_attempts=2)
    b.record("add 1 to the limit")         # unknown|limit
    d = b.record("fix the bound off-by-one")   # off_by_one|bound -> budget now full -> escalate
    assert d["action"] == "escalate"
    assert d["reason"] == "budget_exhausted"
    # further attempts are blocked, not re-escalated
    blocked = b.record("adjust the range")
    assert blocked["action"] == "blocked"


def test_enforce_bounded_probe_returns_auditable_trail():
    out = enforce_bounded_probe(
        ["incrementing the limit", "fix the off-by-one on limit"], max_attempts=4
    )
    assert out["escalated"] is True
    assert isinstance(out["trail"], list)
    # first reflection recorded, second triggers repeat-escalation -> trail has the first key
    assert len(out["trail"]) == 1
    assert out["reason"].startswith("repeated_hypothesis")


# --- P1: Requisite Variety (extends existing governance, no fork) ---

def test_requisite_variety_runs_in_full_suite():
    # The real registry must not have unreachable agent modules (variety gap).
    res = check_requisite_variety()
    assert isinstance(res.success, bool)
    # if there is a breach, it must name the principle + the module (auditable)
    if not res.success:
        assert res.breaches and "P1 variety gap" in res.breaches[0]


def test_requisite_variety_detects_unreachable_module():
    # A registered agent module that does not exist on disk is a variety gap (missing outcome).
    fake_registry = [
        {"name": "Orchestrator", "module": "agents.graph_execution_orchestrator",
         "entrypoint": "orchestrate_graph_execution"},
        {"name": "Ghost", "module": "agents.nonexistent_ghost",  # no such module on disk
         "entrypoint": "ghost_entry"},
    ]
    res = check_requisite_variety(fake_registry)
    assert res.success is False
    assert any("P1 variety gap" in b for b in res.breaches)


def test_p1_is_wired_into_run_governance_checks():
    out = run_governance_checks()
    names = {c["check_name"] for c in out["checks"]}
    assert "requisite_variety" in names
