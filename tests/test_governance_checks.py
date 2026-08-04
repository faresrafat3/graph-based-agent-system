from system.governance_checks import (
    check_entrypoints,
    check_lifecycle_artifacts,
    run_governance_checks,
)


def test_governance_checks_current_registry_passes():
    result = run_governance_checks()
    assert result["success"] is True
    assert result["registered_items"] >= 10
    assert result["breaches"] == []


def test_lifecycle_check_detects_missing_doc():
    registry = [
        {
            "name": "Broken Item",
            "module": "agents.context_curator",
            "entrypoint": "curate_context",
            "permission_symbol": "CONTEXT_CURATOR_PERMISSIONS",
            "lifecycle_doc": "docs/agents/does-not-exist.md",
            "test_file": "tests/test_context_curator.py",
            "category": "test",
            "standard_permissions": True,
        }
    ]
    result = check_lifecycle_artifacts(registry)
    assert result.success is False
    assert any("missing lifecycle doc" in v for v in result.breaches)


def test_entrypoint_check_detects_missing_entrypoint():
    registry = [
        {
            "name": "Broken Item",
            "module": "agents.context_curator",
            "entrypoint": "missing_entrypoint",
            "permission_symbol": "CONTEXT_CURATOR_PERMISSIONS",
            "lifecycle_doc": "docs/agents/context-curator.md",
            "test_file": "tests/test_context_curator.py",
            "category": "test",
            "standard_permissions": True,
        }
    ]
    result = check_entrypoints(registry)
    assert result.success is False
    assert any("missing entrypoint" in v for v in result.breaches)


def test_entrypoints_reachable_flags_undeclared_dead_agent():
    """A registered agent unreachable from the live path AND not in EXTERNAL_ALLOWED
    must fail the check (catches silent dead registrations / orphaned pipelines)."""
    from system.governance_checks import check_entrypoints_reachable

    registry = [
        {
            "name": "Orphan Agent",
            "module": "agents.context_curator",
            "entrypoint": "curate_context",  # reachable (fine)
            "permission_symbol": "CONTEXT_CURATOR_PERMISSIONS",
            "lifecycle_doc": "docs/agents/context-curator.md",
            "test_file": "tests/test_context_curator.py",
            "category": "test",
            "standard_permissions": True,
        },
        {
            "name": "Silent Dead Agent",
            "module": "agents.context_curator",
            "entrypoint": "missing_entrypoint",  # unreachable AND not in EXTERNAL_ALLOWED
            "permission_symbol": "CONTEXT_CURATOR_PERMISSIONS",
            "lifecycle_doc": "docs/agents/context-curator.md",
            "test_file": "tests/test_context_curator.py",
            "category": "test",
            "standard_permissions": True,
        },
    ]
    result = check_entrypoints_reachable(registry)
    assert result.success is False
    assert any("Silent Dead Agent" in v for v in result.breaches)


def test_entrypoints_reachable_passes_current_registry():
    """The real registry: 18 reachable + 9 intentionally external (declared)."""
    from system.governance_checks import check_entrypoints_reachable

    result = check_entrypoints_reachable()
    assert result.success is True
    assert result.detail["total_registered"] == 27
    assert result.detail["reachable_count"] >= 15
