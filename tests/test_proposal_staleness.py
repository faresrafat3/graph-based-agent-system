# version: v1 | 2026-08-08 | verdict: pending-review
"""A control proposal must carry the state version it was computed against.

TRANSPLANT-1 (from prime-agent `agent-session.ts:2556`, branch-version
invalidation): a plan computed against one history must never be applied to a
mutated one. prime-agent re-checks `branchVersion` after review AND after
planning, downgrading the result to `invalidated` rather than returning a plan.

Our exposure is the same shape but slower and therefore easier to miss. Ruling C1
means a HUMAN applies `control_proposals`, so the gap between propose-time and
apply-time is minutes-to-days rather than milliseconds. A proposal read off an
old measurement looks identical to a fresh one, and applying it moves a control
based on evidence that no longer holds.

We do not auto-apply, so the fix is not invalidation-then-abort; it is making
staleness VISIBLE and CHECKABLE at apply time.
"""

from __future__ import annotations

from system.self_improvement import Measurement, compare, measurement_version, propose


def _m(**kw) -> Measurement:
    """Complete Measurement shape (Law 3: short shapes must not be papered over).

    NOTE the scale: `compare()` treats `capability` as a signal at
    `abs(success_delta) >= 5.0` and `health` at `>= 2.0`, so these metrics are
    PERCENTAGES (0-100), not fractions. Writing 0.5 here and expecting a signal
    was my own error, caught by this test failing — recorded so the next reader
    does not repeat it.
    """
    return Measurement(
        success_rate=kw.get("success_rate", 50.0),
        defense_rate=kw.get("defense_rate", 50.0),
        quality=kw.get("quality", 50.0),
        health=kw.get("health", 50.0),
        thrash_count=kw.get("thrash_count", 0),
    )


def test_measurement_version_is_stable_for_identical_measurements():
    """Same evidence must produce the same version, or every read looks stale."""
    a, b = _m(), _m()
    assert measurement_version(a) == measurement_version(b)


def test_measurement_version_changes_when_evidence_changes():
    assert measurement_version(_m()) != measurement_version(_m(success_rate=90.0))


def test_proposal_is_stamped_with_the_version_it_was_computed_against():
    after = _m(success_rate=90.0)
    delta = compare(_m(), after)
    proposals = propose(delta, measured=after)
    assert proposals, "a meaningful delta must produce at least one proposal"
    for p in proposals:
        assert p["measurement_version"] == measurement_version(after)


def test_unstamped_proposal_is_still_produced_for_backward_compatibility():
    """propose(delta) without `measured` must keep working; the stamp is None so
    a reader can tell 'unknown provenance' from 'verified fresh'. Silently
    inventing a version would be worse than admitting we don't have one."""
    proposals = propose(compare(_m(), _m(success_rate=90.0)))
    assert proposals
    assert proposals[0]["measurement_version"] is None


def test_stale_proposal_is_detected_against_current_evidence():
    from system.self_improvement import is_proposal_stale

    old = _m(success_rate=90.0)
    proposal = propose(compare(_m(), old), measured=old)[0]

    assert is_proposal_stale(proposal, _m(success_rate=40.0)) is True
    assert is_proposal_stale(proposal, old) is False


def test_unstamped_proposal_reads_as_stale_not_fresh():
    """Fail SAFE: unknown provenance must never be reported as fresh (Law 3)."""
    from system.self_improvement import is_proposal_stale

    unstamped = propose(compare(_m(), _m(success_rate=90.0)))[0]
    assert is_proposal_stale(unstamped, _m(success_rate=90.0)) is True
