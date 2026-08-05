"""TDD tests for the Sage Council — CIR as LOCAL sages (no opus-5 dependency).

Fares's correction: the principle lives INSIDE the graph as a council of local sages,
not a hard link to opus-5. These tests verify the council convenes/skips correctly,
uses context-isolated signals, and produces a falsifiable spec via its topology.
"""

from agents.sage_council import (
    SageCouncil, Sage, build_default_council, PEER, HIERARCHICAL, BROADCAST,
)


def test_council_skips_below_complexity_threshold():
    c = SageCouncil(complexity_threshold=4)
    out = c.skip({"complexity_score": 2})
    assert out["convened"] is False
    assert out["reconciled_spec"] is None
    assert c.should_convene({"complexity_score": 2}) is False
    assert c.should_convene({"complexity_score": 7}) is True


def test_council_convenes_with_peer_dialectic():
    c = SageCouncil(sages=[Sage("a", ["P1"]), Sage("b", ["P2"])],
                    topology=PEER, complexity_threshold=4)
    out = c.convene({"complexity_score": 9, "repeated_hypothesis_count": 2,
                     "breach_count": 1, "success_rate": 50})
    assert out["convened"] is True
    assert out["topology"] == PEER
    assert len(out["views"]) == 2
    assert "DIAALECTIC" in out["reconciled_spec"]
    assert "FALSIFICATION" in out["reconciled_spec"]
    # context isolation: signals only, no raw artifacts
    assert "complexity" in out["isolated_signals"]


def test_council_topologies_differ():
    sages = [Sage("lead", ["P1"]), Sage("sub", ["P2"])]
    base_m = {"complexity_score": 9, "repeated_hypothesis_count": 0,
              "breach_count": 0, "success_rate": 80}
    peer = SageCouncil(sages=list(sages), topology=PEER).convene(base_m)
    hier = SageCouncil(sages=list(sages), topology=HIERARCHICAL).convene(base_m)
    bc = SageCouncil(sages=list(sages), topology=BROADCAST).convene(base_m)
    assert "DIAALECTIC" in peer["reconciled_spec"]
    assert "LEAD[lead]" in hier["reconciled_spec"]
    assert "LEAD[lead]" not in bc["reconciled_spec"]  # broadcast != hierarchical


def test_default_council_seeded_from_distilled_principles():
    c = build_default_council()
    refs = [r for s in c.sages for r in s.principle_refs]
    # opus-5's distilled legacy (P1-P7 + CIR) is now LOCAL, not a call
    assert "P1" in refs and "CIR" in refs
    assert c.complexity_threshold == 4
