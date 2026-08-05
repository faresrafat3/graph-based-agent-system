"""TDD tests for T1-fix#1 — check_forge_wired (governance sees the Forge pieces, opus-5 #1).

Verifies the governance layer no longer has a blind spot: the Intelligence Forge modules
(agent_forge, topology_assembler, context_system_view, bounded_probe, sage_council) must be
reachable from the LIVE production path. Until they are wired in, the gap is surfaced as a
WARNING (visible, not hidden) — not a hard breach that reds the whole sweep.
"""

from system import governance_checks as gc
from system.governance_checks import check_forge_wired, run_governance_checks


def test_forge_wired_surfaces_gap_as_warning_when_live_path_unimported():
    # The live path currently does NOT import the forge modules -> warning (tracked gap).
    res = check_forge_wired()
    assert res.success is True  # not a hard regression...
    assert res.warnings  # ...but the gap is surfaced, not hidden
    assert any("Forge-wiring gap" in w for w in (res.warnings or []))


def test_forge_wired_is_wired_into_run_governance_checks():
    out = run_governance_checks()
    names = {c["check_name"] for c in out["checks"]}
    assert "forge_wired" in names
    # gap is visible at the aggregate level (warnings channel)
    assert any("Forge-wiring gap" in w for w in out.get("warnings", []))
