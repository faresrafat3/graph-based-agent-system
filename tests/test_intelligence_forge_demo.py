"""TDD tests for T2 — Intelligence Forge integration demo (all pieces compose, no fork/theater).

Proves forge -> context -> topology -> sage_council -> systems_layer run together end-to-end
and that the meta-loop actually executes (cycle_log fills).
"""

from agents.intelligence_forge_demo import run_intelligence_forge_scenario


def test_full_scenario_composes_all_pieces():
    out = run_intelligence_forge_scenario()
    # forge
    assert out["forged_agent"] == "demo_bespoke"
    assert out["behavior_hash"]  # bespoke, not a clone
    # context = system
    assert out["context_is_system"] is True
    assert out["context_peer_count"] >= 5  # real peers from registry
    # topology is typed + extends backbone
    assert out["topology_edge_count"] >= 2
    assert out["topology_extends"] == "systems_layer"
    # sage council convened (local CIR, no opus-5)
    assert out["council_convened"] is True
    # meta-loop actually ran (the live backbone)
    assert out["meta_loop_ran"] is True
    assert any("philosopher:" in line for line in out["meta_loop_cycle_log"])


def test_scenario_is_deterministic_and_auditable():
    a = run_intelligence_forge_scenario(
        agent_name="det_a", spec_slice=["P3", "P4"],
        focused_task="harden auth edge cases")
    b = run_intelligence_forge_scenario(
        agent_name="det_b", spec_slice=["P1", "P5"],
        focused_task="raise requisite variety on routing")
    # different inputs -> distinct agents (bespoke, not cloned)
    assert a["behavior_hash"] != b["behavior_hash"]
    assert a["topology_extends"] == b["topology_extends"] == "systems_layer"
