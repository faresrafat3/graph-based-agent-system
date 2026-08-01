import json

import pytest

import agents.task_decomposer as task_decomposer_module
from agents.task_decomposer import decompose_requirements, TASK_DECOMPOSER_PERMISSIONS


def fake_task_decomposition_response(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """Deterministic test double for the Stepfun boundary."""
    return json.dumps(
        {
            "tasks": [
                {
                    "id": "task_1",
                    "title": "Implement requested requirements",
                    "description": prompt,
                    "type": "feature",
                    "priority": "high",
                    "dependencies": [],
                    "estimated_effort": "medium",
                    "assigned_system": "developer",
                    "acceptance_criteria": ["Requested requirements are covered"],
                }
            ],
            "metadata": {
                "total_tasks": 1,
                "high_priority": 1,
                "medium_priority": 0,
                "low_priority": 0,
                "estimated_total_effort": "medium",
            },
            "clarifications_needed": [],
        }
    )


def test_permission_boundaries():
    assert "READ" in TASK_DECOMPOSER_PERMISSIONS
    assert "WRITE" in TASK_DECOMPOSER_PERMISSIONS
    assert "NEVER" in TASK_DECOMPOSER_PERMISSIONS
    assert "code" in TASK_DECOMPOSER_PERMISSIONS["NEVER"]


def test_permission_violation_raises():
    with pytest.raises(PermissionError):
        decompose_requirements("Please delete production database completely")


def test_task_decomposition_pipeline(monkeypatch):
    monkeypatch.setattr(task_decomposer_module, "call_llm", fake_task_decomposition_response)

    result = decompose_requirements(
        requirements="Build a simple login page with email authentication",
        project_context="Web app",
        constraints="React",
        thread_id="test_task_decomposition_pipeline",
    )
    assert "tasks" in result
    assert "success" in result
    assert result["success"] is True
