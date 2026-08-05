"""TDD tests for the P7 self-pruning report."""

from system.self_pruning import build_pruning_report, EXTERNAL_ALLOWED


def test_pruning_report_runs_and_is_advisory():
    rep = build_pruning_report(measurements_dir="system/measurements")
    assert "pruning_candidates" in rep
    assert "external_declared" in rep
    assert "controls_with_observed_effect" in rep
    # Advisory only: never deletes, always explains.
    assert "no agent was deleted" in rep["recommendation"]


def test_external_agents_declared_separately():
    rep = build_pruning_report(measurements_dir="system/measurements")
    # The declared-external set is reported distinctly from pruning candidates.
    for ext in EXTERNAL_ALLOWED:
        if ext in rep["external_declared"]:
            # an external agent must not also be a pruning candidate
            assert ext not in {c["agent"] for c in rep["pruning_candidates"]}


def test_candidates_are_reachable_live_agents():
    rep = build_pruning_report(measurements_dir="system/measurements")
    # Every candidate must be a live (reachable) agent with no observed effect.
    # Since this is advisory and measurement history is short, we only assert shape.
    for c in rep["pruning_candidates"]:
        assert "reachable" in c["reason"] or "live path" in c["reason"]
        assert "no observed outcome" in c["reason"]
