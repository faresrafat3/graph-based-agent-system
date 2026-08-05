"""TDD tests for ConsensusMechanism — the fusion core (conflict detection + weighted merge).

Fares's deep problem: how agents reach a CORRECT final integration honoring the vision, not
just concatenate views. These tests verify conflict surfacing + weighted topology shaping.
"""

from agents.sage_council import SageCouncil, Sage, ConsensusMechanism, PEER, HIERARCHICAL, BROADCAST


def test_consensus_detects_conflict():
    views = ["bound the probing budget", "expand the search space"]
    conflicts = ConsensusMechanism._detect_conflicts(views)
    assert "conflict:bound/expand" in conflicts


def test_consensus_peer_flags_conflicts_and_weights():
    sages = [Sage("a", ["P1"], weight=2.0), Sage("b", ["P2"], weight=1.0)]
    views = ["bound the probing budget", "expand the search space"]
    out = ConsensusMechanism.reconcile(sages, views, PEER, {"complexity": 9})
    assert "CONFLICTS:conflict:bound/expand" in out["merged"]
    # highest-weight sage stated first in the weighted body
    assert out["weights"]["a"] == 2.0 and out["weights"]["b"] == 1.0
    # weighted ordering: 'a' (higher weight) appears before 'b' in the merged body
    assert out["merged"].index("bound the probing") < out["merged"].index("expand the search")


def test_consensus_hierarchical_lead_dominates():
    sages = [Sage("lead", ["P1"], weight=1.5), Sage("sub", ["P2"], weight=0.5)]
    views = ["centralize control", "distribute control"]
    out = ConsensusMechanism.reconcile(sages, views, HIERARCHICAL, {"complexity": 9})
    assert "LEAD[lead]" in out["merged"]
    assert "CONFLICTS:conflict:centralize/distribute" in out["merged"]


def test_consensus_broadcast_no_fusion():
    sages = [Sage("a", ["P1"]), Sage("b", ["P2"])]
    views = ["view one", "view two"]
    out = ConsensusMechanism.reconcile(sages, views, BROADCAST, {"complexity": 9})
    assert out["merged"] == "view one"  # broadcast = emit only, no fusion


def test_convene_returns_consensus_block():
    c = SageCouncil(sages=[Sage("g", ["P1"], weight=1.2), Sage("p", ["P4"], weight=1.0)],
                    topology=PEER, complexity_threshold=4)
    out = c.convene({"complexity_score": 8, "repeated_hypothesis_count": 1,
                     "breach_count": 0, "success_rate": 70})
    assert "consensus" in out
    assert out["consensus"]["weights"]["g"] == 1.2
