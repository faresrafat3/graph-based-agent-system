# version: v1 | 2026-08-08 | verdict: pending-review
"""The staleness stamp must be CONSUMED, not merely written.

M1 (branch-version invalidation) landed `measurement_version()` and
`is_proposal_stale()`, and `propose_node` stamps every proposal. But nothing ever
called `is_proposal_stale`. A stamp nobody checks is decoration: the proposal still
reaches a human looking exactly as authoritative as a fresh one.

This is the "wired but not flowing" failure mode — the node ran, the field was set,
the audit was green, and the mechanism did nothing. These tests exercise the
end-to-end path so the check cannot silently become inert again.

Upstream analogue: prime-agent re-checks `branchVersion` at APPLY time
(agent-session.ts:2556, :2569) and downgrades the plan to `invalidated`. The check
lives at the point of use, not at the point of creation.
"""

from __future__ import annotations

from typing import cast

from agents.systems_layer import (
    SystemsLayerState,
    distill_node,
    gate_node,
    propose_node,
)
from system.self_improvement import Measurement, compare, measurement_version


def _m(**kw) -> Measurement:
    """Metrics are PERCENTAGES (0-100): compare() signals capability at >= 5.0."""
    return Measurement(
        success_rate=kw.get("success_rate", 50.0),
        defense_rate=kw.get("defense_rate", 50.0),
        quality=kw.get("quality", 50.0),
        health=kw.get("health", 50.0),
        thrash_count=kw.get("thrash_count", 0),
    )


def _state(prior: Measurement, current: Measurement) -> SystemsLayerState:
    return cast(SystemsLayerState, {
        "prior_measurement": prior.as_dict(),
        "current_measurement": current.as_dict(),
        "delta": compare(prior, current),
        "proposals": [],
        "decisions": [],
        "control_proposals": [],
        "counter_proposals": [],
        "philosopher_strategy": None,
        "reconciled_spec": None,
        "cycle_log": [],
    })


def test_gate_marks_a_proposal_fresh_when_evidence_still_holds():
    current = _m(success_rate=90.0)
    state = propose_node(_state(_m(), current))
    out = gate_node(distill_node(state))

    assert out["control_proposals"], "a meaningful delta must produce a control proposal"
    for p in out["control_proposals"]:
        assert p["stale"] is False
        assert p["measurement_version"] == measurement_version(current)


def test_gate_marks_a_proposal_stale_when_evidence_moved():
    """The core scenario: propose against one measurement, gate against another."""
    proposed_against = _m(success_rate=90.0)
    state = propose_node(_state(_m(), proposed_against))

    # Evidence moves before the gate runs (a later cycle, a re-measurement).
    moved = _m(success_rate=40.0)
    state["current_measurement"] = moved.as_dict()

    out = gate_node(distill_node(state))
    assert out["control_proposals"], "staleness must not silently drop the proposal"
    for p in out["control_proposals"]:
        assert p["stale"] is True, "evidence moved; the proposal must be flagged stale"


def test_stale_proposals_are_flagged_not_deleted():
    """C1 default-deny: a human decides. Deleting would hide the signal entirely."""
    state = propose_node(_state(_m(), _m(success_rate=90.0)))
    before = len(state["proposals"])
    state["current_measurement"] = _m(success_rate=40.0).as_dict()
    out = gate_node(distill_node(state))
    assert len(out["control_proposals"]) <= before
    assert all("stale" in p for p in out["control_proposals"])


def test_staleness_is_recorded_in_the_cycle_log():
    """An operator reading the log must see it without inspecting the dicts."""
    state = propose_node(_state(_m(), _m(success_rate=90.0)))
    state["current_measurement"] = _m(success_rate=40.0).as_dict()
    out = gate_node(distill_node(state))
    assert any("stale" in line.lower() for line in out["cycle_log"]), out["cycle_log"]


def test_unstamped_proposal_reaching_the_gate_reads_as_stale():
    """Fail safe: unknown provenance is never reported as fresh (Law 3)."""
    state = propose_node(_state(_m(), _m(success_rate=90.0)))
    for p in state["proposals"]:
        p.pop("measurement_version", None)
    out = gate_node(distill_node(state))
    for p in out["control_proposals"]:
        assert p["stale"] is True


def test_gate_without_a_current_measurement_does_not_crash():
    """A partial state must not take the cycle down (defensive, but no fabrication)."""
    state = propose_node(_state(_m(), _m(success_rate=90.0)))
    state["current_measurement"] = {}
    out = gate_node(distill_node(state))
    for p in out["control_proposals"]:
        assert p["stale"] is True, "no evidence to compare against means not-verified-fresh"
