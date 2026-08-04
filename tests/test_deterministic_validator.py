import pytest
from agents.deterministic_validator import (
    validate_output,
    DeterministicValidatorEngine,
    DETERMINISTIC_VALIDATOR_PERMISSIONS,
)


def valid_task(task_id="task_1", priority="high", dependencies=None):
    return {
        "id": task_id,
        "title": "Design System",
        "description": "Design system architecture and component boundaries",
        "type": "architecture",
        "priority": priority,
        "dependencies": dependencies or [],
        "estimated_effort": "medium",
        "assigned_system": "architect",
        "acceptance_criteria": ["Architecture document created"],
    }


def test_permissions_matrix():
    assert "READ" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "WRITE" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "NEVER" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "modify_target_output" in DETERMINISTIC_VALIDATOR_PERMISSIONS["NEVER"]


def test_validate_schema_valid():
    data = {"tasks": [], "metadata": {}}
    breaches = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(breaches) == 0


def test_validate_schema_missing_key():
    data = {"tasks": []}
    breaches = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(breaches) == 1
    assert "metadata" in breaches[0]


def test_validate_tasks_structure_strict_schema():
    tasks = [
        {"id": "task_1", "title": "Design UI", "type": "architecture"},
        {**valid_task("task_2"), "type": "invalid_type"},
    ]
    breaches = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert any("description" in v for v in breaches)
    assert any("acceptance_criteria" in v for v in breaches)
    assert any("invalid_type" in v for v in breaches)


def test_validate_dependencies_unknown_and_cycle():
    tasks = [
        valid_task("task_1", dependencies=["task_2"]),
        valid_task("task_2", dependencies=["task_1", "task_missing"]),
    ]
    breaches = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert any("Circular dependency" in v for v in breaches)
    assert any("unknown task id 'task_missing'" in v for v in breaches)


def test_validate_output_pipeline_success():
    payload = {
        "tasks": [valid_task("task_1")],
        "metadata": {
            "total_tasks": 1,
            "high_priority": 1,
            "medium_priority": 0,
            "low_priority": 0,
            "estimated_total_effort": "medium",
        },
    }
    res = validate_output(payload, thread_id="validator_success_test")
    assert res["success"] is True
    assert res["quality_score"] == 1.0
    assert len(res["breaches"]) == 0


def test_validate_metadata_mismatch_fails():
    payload = {
        "tasks": [valid_task("task_1")],
        "metadata": {"total_tasks": 99, "high_priority": 0},
    }
    res = validate_output(payload, thread_id="validator_metadata_mismatch_test")
    assert res["success"] is False
    assert any("Metadata" in v for v in res["breaches"])
