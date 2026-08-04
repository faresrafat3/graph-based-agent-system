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
    violations = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(violations) == 0


def test_validate_schema_missing_key():
    data = {"tasks": []}
    violations = DeterministicValidatorEngine.validate_schema(data, ["tasks", "metadata"])
    assert len(violations) == 1
    assert "metadata" in violations[0]


def test_validate_tasks_structure_strict_schema():
    tasks = [
        {"id": "task_1", "title": "Design UI", "type": "architecture"},
        {**valid_task("task_2"), "type": "invalid_type"},
    ]
    violations = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert any("description" in v for v in violations)
    assert any("acceptance_criteria" in v for v in violations)
    assert any("invalid_type" in v for v in violations)


def test_validate_dependencies_unknown_and_cycle():
    tasks = [
        valid_task("task_1", dependencies=["task_2"]),
        valid_task("task_2", dependencies=["task_1", "task_missing"]),
    ]
    violations = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert any("Circular dependency" in v for v in violations)
    assert any("unknown task id 'task_missing'" in v for v in violations)


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
    assert len(res["violations"]) == 0


def test_validate_metadata_mismatch_fails():
    payload = {
        "tasks": [valid_task("task_1")],
        "metadata": {"total_tasks": 99, "high_priority": 0},
    }
    res = validate_output(payload, thread_id="validator_metadata_mismatch_test")
    assert res["success"] is False
    assert any("Metadata" in v for v in res["violations"])


def test_validate_schema_non_dict_and_empty_value():
    # When data is not a dict
    violations = DeterministicValidatorEngine.validate_schema("not a dict", ["tasks"])
    assert "not a valid JSON dictionary" in violations[0]
    
    # When mandatory key is empty or None
    violations2 = DeterministicValidatorEngine.validate_schema({"tasks": None}, ["tasks"])
    assert "is empty" in violations2[0]


def test_validate_tasks_structure_type_checks():
    # Tasks is not a list
    v_list = DeterministicValidatorEngine.validate_tasks_structure("not a list")
    assert "must be a list" in v_list[0]
    
    # Task is not a dict
    v_dict = DeterministicValidatorEngine.validate_tasks_structure([None])
    assert "not a valid dictionary" in v_dict[0]
    
    # Task ID is not a string
    task_bad_id = {**valid_task("task_1"), "id": 123}
    v_id = DeterministicValidatorEngine.validate_tasks_structure([task_bad_id])
    assert "invalid or empty 'id'" in v_id[0]
    
    # Title and description are not string/empty
    task_bad_fields = {**valid_task("task_1"), "title": "", "description": 123}
    v_fields = DeterministicValidatorEngine.validate_tasks_structure([task_bad_fields])
    assert "has invalid or empty 'title'" in v_fields[0]
    assert "has invalid or empty 'description'" in v_fields[1]


def test_validate_tasks_field_violations():
    # Invalid estimated_effort and assigned_system and priority
    task_bad_vals = {**valid_task("task_1"), "estimated_effort": "huge", "assigned_system": "unassigned", "priority": "super_high"}
    v_vals = DeterministicValidatorEngine.validate_tasks_structure([task_bad_vals])
    assert any("has invalid estimated_effort" in v for v in v_vals)
    assert any("has invalid assigned_system" in v for v in v_vals)
    assert any("has invalid priority" in v for v in v_vals)
    
    # Dependencies is not a list
    task_bad_deps = {**valid_task("task_1"), "dependencies": "not a list"}
    v_deps = DeterministicValidatorEngine.validate_tasks_structure([task_bad_deps])
    assert "dependencies must be a list" in v_deps[0]
    
    # Dependency value is not a string
    task_bad_dep_val = {**valid_task("task_1"), "dependencies": [123]}
    v_dep_val = DeterministicValidatorEngine.validate_tasks_structure([task_bad_dep_val])
    assert "has invalid dependency value" in v_dep_val[0]
    
    # Acceptance criteria is not a list or is empty
    task_bad_criteria = {**valid_task("task_1"), "acceptance_criteria": []}
    v_criteria = DeterministicValidatorEngine.validate_tasks_structure([task_bad_criteria])
    assert "acceptance_criteria must be a non-empty list" in v_criteria[0]
    
    # Acceptance criterion value is not a string
    task_bad_criterion_val = {**valid_task("task_1"), "acceptance_criteria": [123]}
    v_criterion_val = DeterministicValidatorEngine.validate_tasks_structure([task_bad_criterion_val])
    assert "has invalid acceptance criterion" in v_criterion_val[0]


def test_validate_duplicate_ids_and_self_dependency():
    tasks = [
        valid_task("task_1"),
        {**valid_task("task_1"), "dependencies": ["task_1"]}  # Duplicate ID and self dependency
    ]
    violations = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    assert any("Duplicate task id detected" in v for v in violations)
    assert any("depends on itself" in v for v in violations)
    
    # Direct test for validate_dependencies to cover list comprehension generator and non-list tasks
    direct_v = DeterministicValidatorEngine.validate_dependencies([None, {"id": 123}, {"id": "t1"}])
    assert len(direct_v) == 0
    
    non_list_v = DeterministicValidatorEngine.validate_dependencies("not a list")
    assert len(non_list_v) == 0



def test_validate_metadata_consistency_type_checks():
    # Not a dict
    violations = DeterministicValidatorEngine.validate_metadata_consistency("not a dict")
    assert len(violations) == 0
    
    # Tasks not a list or metadata not a dict
    violations2 = DeterministicValidatorEngine.validate_metadata_consistency({"tasks": "not list", "metadata": {}})
    assert len(violations2) == 0
    
    # Invalid estimated_total_effort
    target = {
        "tasks": [valid_task("task_1")],
        "metadata": {
            "total_tasks": 1,
            "high_priority": 1,
            "medium_priority": 0,
            "low_priority": 0,
            "estimated_total_effort": "invalid"
        }
    }
    violations3 = DeterministicValidatorEngine.validate_metadata_consistency(target)
    assert any("estimated_total_effort has invalid value" in v for v in violations3)


def test_validate_output_null_propose():
    res = validate_output(None, thread_id="validator_null_test")
    assert res["success"] is False
    assert res["quality_score"] == 0.9
    assert "not a valid JSON dictionary" in res["violations"][0]


def test_validate_output_refinement_escalation(monkeypatch):
    import agents.deterministic_validator as val_module
    
    # Always fail propose/evaluate step so that refinement count increases and eventually escalates
    # We can do this by forcing violations and failing success threshold
    payload = {
        "tasks": [{"id": "t1"}], # Failing task structure
        "metadata": {}
    }
    
    # We should let the validator run but mock refine count
    res = validate_output(payload, thread_id="validator_escalate_test")
    assert res["success"] is False

