import pytest
from agents.deterministic_validator import (
    validate_output,
    DeterministicValidatorEngine,
    DETERMINISTIC_VALIDATOR_PERMISSIONS
)


def test_permissions_matrix():
    assert "READ" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "WRITE" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "NEVER" in DETERMINISTIC_VALIDATOR_PERMISSIONS
    assert "modify_target_output" in DETERMINISTIC_VALIDATOR_PERMISSIONS["NEVER"]


def test_validate_schema_valid():
    data = {"tasks": [], "metadata": {}}
    violations = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(violations) == 0


def test_validate_schema_missing_key():
    data = {"tasks": []}
    violations = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(violations) == 1
    assert "metadata" in violations[0]


def test_validate_tasks_structure():
    tasks = [
        {"id": "task_1", "title": "Design UI", "type": "architecture"},
        {"id": "task_2", "title": "Build UI", "type": "invalid_type"}
    ]
    violations = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert len(violations) == 1
    assert "invalid_type" in violations[0]


def test_validate_output_pipeline_success():
    payload = {
        "tasks": [
            {"id": "task_1", "title": "Design System", "type": "architecture"}
        ],
        "metadata": {"total_tasks": 1}
    }
    res = validate_output(payload)
    assert res["success"] is True
    assert res["quality_score"] == 1.0
    assert len(res["violations"]) == 0
