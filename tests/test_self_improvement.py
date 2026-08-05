"""TDD tests for the governed self-improvement meta-loop (META-SYSTEM.md)."""

import json

from system.self_improvement import (
    Measurement,
    compare,
    propose,
    gate,
    distill_opus5,
    CONTROL_PROPOSAL_SCHEMA,
)


def test_measurement_is_comparable():
    m1 = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                     health=77.7, thrash_count=0, postcond_pass=None)
    m2 = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                     health=77.7, thrash_count=0, postcond_pass=None)
    assert m1 == m2
    assert m1.as_dict()["success_rate"] == 75.0


def test_compare_detects_thrash_delta():
    before = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                         health=77.7, thrash_count=0, postcond_pass=None)
    after = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                        health=77.7, thrash_count=3, postcond_pass=None)
    delta = compare(before, after)
    assert delta["deltas"]["thrash_delta"] == 3
    assert delta["has_meaningful_delta"] is True
    assert "thrash" in delta["signals"]


def test_compare_no_meaningful_delta_is_false():
    m = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                    health=77.7, thrash_count=0, postcond_pass=None)
    delta = compare(m, m)
    assert delta["has_meaningful_delta"] is False


def test_propose_emits_one_control_per_delta():
    before = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                         health=77.7, thrash_count=0, postcond_pass=None)
    after = Measurement(success_rate=75.0, defense_rate=100.0, quality=0.75,
                        health=77.7, thrash_count=2, postcond_pass=None)
    delta = compare(before, after)
    proposals = propose(delta)
    # Exactly one control change per meaningful delta (L3: one variable per probe)
    assert len(proposals) == 1
    p = proposals[0]
    assert p["kind"] in CONTROL_PROPOSAL_SCHEMA
    assert p["hypothesis"]  # falsifiable
    assert p["reversible"] is True  # hard rule 2
    assert p["observability"] is not None  # hard rule 3


def test_gate_blocks_non_observable_control():
    bad = {
        "kind": "probe_budget",
        "hypothesis": "thrash drops with budget",
        "reversible": True,
        "observability": None,  # not observable -> must be blocked (P7/L4)
    }
    decision = gate(bad)
    assert decision["accepted"] is False
    assert "observable" in decision["reason"].lower()


def test_gate_accepts_observable_reversible_control():
    good = {
        "kind": "probe_budget",
        "hypothesis": "thrash drops with N<=3",
        "reversible": True,
        "observability": "repeated_hypothesis_count in reflexion/debugger state",
    }
    decision = gate(good)
    assert decision["accepted"] is True


def test_distill_opus5_returns_principle_not_code():
    proposal = {
        "kind": "domain_governance",
        "hypothesis": "control intensity should follow Cynefin domain",
        "reversible": True,
        "observability": "domain field on dispatch result",
    }
    out = distill_opus5(proposal)
    # Distilled output must be a short principle, never executable code.
    assert isinstance(out["principle"], str)
    assert len(out["principle"]) < 400
    assert out["is_code"] is False
    assert "P" in out["references"] or "principle" in out["references"]
