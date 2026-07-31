import pytest
from agents.task_decomposer import decompose_requirements, TASK_DECOMPOSER_PERMISSIONS


def test_permission_boundaries():
    assert "READ" in TASK_DECOMPOSER_PERMISSIONS
    assert "WRITE" in TASK_DECOMPOSER_PERMISSIONS
    assert "NEVER" in TASK_DECOMPOSER_PERMISSIONS
    assert "code" in TASK_DECOMPOSER_PERMISSIONS["NEVER"]


def test_permission_violation_raises():
    with pytest.raises(PermissionError):
        decompose_requirements("Please delete production database completely")


def test_task_decomposition_pipeline():
    result = decompose_requirements(
        requirements="Build a simple login page with email authentication",
        project_context="Web app",
        constraints="React"
    )
    assert "tasks" in result
    assert "success" in result
