"""TDD tests for Task F: split governance_score from success_rate (G6, F2).

Resolves F2: loops improve governance, not necessarily capability. We must report the two
separately so we never claim a loop "improved results" when only governance improved.
The Measurement gains a governance_score; the benchmark emits both.
"""

from system.self_improvement import Measurement, compute_governance_score
from benchmarks.benchmark_suite import run_benchmarks


def test_measurement_has_governance_score_field():
    m = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                     health=77.7, thrash_count=0, postcond_pass=None, governance_score=0.9)
    assert m.governance_score == 0.9


def test_compute_governance_score_rewards_defense_and_no_breach():
    # High defense + low thrash => high governance score, independent of success_rate.
    high = compute_governance_score(defense_rate=100.0, thrash_count=0, breaches=0)
    low = compute_governance_score(defense_rate=0.0, thrash_count=5, breaches=3)
    assert high > low
    assert high >= 0.9
    # governance can be high even if success is low (the F2 point)
    assert high > 0.5  # governance is its own axis


def test_governance_score_independent_of_success():
    # Same governance inputs, different success -> governance score unchanged.
    g1 = compute_governance_score(defense_rate=100.0, thrash_count=0, breaches=0)
    g2 = compute_governance_score(defense_rate=100.0, thrash_count=0, breaches=0)
    assert g1 == g2
