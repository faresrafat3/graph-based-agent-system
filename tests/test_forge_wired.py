"""TDD tests for T1-fix#1 — check_forge_wired (governance sees the Forge pieces, opus-5 #1).

Verifies the governance layer has no blind spot: the Intelligence Forge modules
(agent_forge, topology_assembler, context_system_view, bounded_probe, sage_council) must be
reachable from the LIVE production path.

The gap is now CLOSED (all five are wired: the first four via the forge node in
karpathy_pipeline, bounded_probe via surgical_refiner's refinement loop). These tests
therefore assert the DETECTOR's behaviour, not the state of the moment:

  1. wired   -> silent (no warning invented to look busy)
  2. unwired -> warning (falsifiable: break the wiring, the check must notice)

Asserting "a warning is currently present" would pin the gap open forever and make the
suite fail the moment it was fixed — a test that punishes the repair it exists to drive.
"""

from system.governance_checks import check_forge_wired, run_governance_checks

FORGE_MODULES = [
    "agents.agent_forge",
    "agents.topology_assembler",
    "agents.context_system_view",
    "system.bounded_probe",
    "agents.sage_council",
]


def test_forge_wired_is_clean_now_that_all_modules_are_wired():
    res = check_forge_wired()
    assert res.success is True
    assert not res.warnings, f"unexpected forge-wiring warning: {res.warnings}"


def test_forge_wired_detects_an_unwired_module(monkeypatch):
    """Falsifiability: hide the live path and the check must surface the gap."""
    import system.governance_checks as gc

    monkeypatch.setattr(gc, "_live_path_source", lambda *_a, **_k: "x = 1")
    res = check_forge_wired()
    assert res.success is True  # tracked gap, not a hard sweep-reddening breach
    assert res.warnings
    warning = " ".join(res.warnings)
    assert "Forge-wiring gap" in warning
    for module in FORGE_MODULES:
        assert module in warning


def test_forge_wired_is_wired_into_run_governance_checks():
    out = run_governance_checks()
    names = {c["check_name"] for c in out["checks"]}
    assert "forge_wired" in names
    # Closed gap => the aggregate warnings channel carries no forge-wiring entry.
    assert not any("Forge-wiring gap" in w for w in out.get("warnings", []))
