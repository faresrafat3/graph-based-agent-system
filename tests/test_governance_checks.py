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


def test_langgraph_orchestration_check_passes():
    """Article III: the live pipeline MUST be orchestrated as a LangGraph StateGraph."""
    from system.governance_checks import check_langgraph_orchestration

    result = check_langgraph_orchestration()
    assert result.success is True, result.breaches


def test_entrypoints_reachable_passes_current_registry():
    """The real registry: N reachable + M intentionally external (declared).
    Systems Layer (build_systems_graph) was added as an intentionally-external agent
    in v2, bringing the total to 28."""
    from system.governance_checks import check_entrypoints_reachable

    result = check_entrypoints_reachable()
    assert result.success is True
    assert result.detail["total_registered"] == 28
    assert result.detail["reachable_count"] >= 15


def _registry_entry(module, entrypoint="broken"):
    return {
        "name": "Malformed Probe",
        "module": module,
        "entrypoint": entrypoint,
        "lifecycle_doc": "README.md",
        "test_file": "README.md",
        "category": "test",
    }


def _write_unparseable(tmp_path, monkeypatch):
    """Register a module whose source exists but is not valid Python."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "probe_module.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    return _registry_entry("probe_module")


def test_unparseable_module_is_reported_not_raised(tmp_path, monkeypatch):
    """A malformed agent source must become a breach, never an exception.

    Source-walking checks used to call ast.parse directly, so one unparseable module
    aborted the sweep with a traceback: every other check's findings were lost and CI
    reported a crash instead of a governance breach (Law 3, fail loudly *and* legibly).
    """
    from system.governance_checks import check_no_llm_in_evaluate

    entry = _write_unparseable(tmp_path, monkeypatch)
    result = check_no_llm_in_evaluate([entry])

    assert result.success is False
    assert any("could not parse" in breach for breach in result.breaches)


def test_sweep_survives_an_unparseable_module(tmp_path, monkeypatch):
    """run_governance_checks must still report all checks when one module is broken."""
    from system.governance_checks import run_governance_checks

    entry = _write_unparseable(tmp_path, monkeypatch)
    result = run_governance_checks([entry])

    assert result["success"] is False
    assert len(result["checks"]) == 12
    assert any("could not parse" in breach for breach in result["breaches"])


def test_missing_and_unparseable_sources_are_diagnosed_differently(tmp_path, monkeypatch):
    """An absent module is a variety gap; a broken one is a parse failure.

    Collapsing the two would report a syntax error as 'no reachable entrypoint',
    which misdiagnoses the cause and sends a maintainer looking at the call graph.
    """
    from system.governance_checks import check_requisite_variety

    broken = _write_unparseable(tmp_path, monkeypatch)
    broken_result = check_requisite_variety([broken])
    assert broken_result.success is False
    assert any("could not parse" in b for b in broken_result.breaches)
    assert not any("variety gap" in b for b in broken_result.breaches)

    missing_result = check_requisite_variety([_registry_entry("agents.does_not_exist")])
    assert missing_result.success is False
    assert any("variety gap" in b for b in missing_result.breaches)

