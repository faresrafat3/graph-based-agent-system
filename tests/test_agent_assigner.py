import pytest

from agents.agent_assigner import (
    AGENT_ASSIGNER_PERMISSIONS,
    AgentAssignerEngine,
    assign_tasks,
)


def valid_task(
    task_id="task_1",
    title="Implement feature",
    description="Implement generic feature logic",
    task_type="feature",
    assigned_system="developer",
    dependencies=None,
    priority="high",
):
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "type": task_type,
        "priority": priority,
        "dependencies": dependencies or [],
        "estimated_effort": "medium",
        "assigned_system": assigned_system,
        "acceptance_criteria": ["Task is complete and validated"],
    }


def test_permissions_matrix():
    assert "tasks" in AGENT_ASSIGNER_PERMISSIONS["READ"]
    assert "execution_plan" in AGENT_ASSIGNER_PERMISSIONS["WRITE"]
    assert "source_code" in AGENT_ASSIGNER_PERMISSIONS["NEVER"]


def test_classify_domain_feature_to_auth_squad():
    task = valid_task(
        title="Implement JWT login authentication",
        description="Create secure OAuth token rotation",
    )
    assignment = AgentAssignerEngine.classify_task(task)
    assert assignment["assigned_agent"] == "AuthSquadAgent"
    assert assignment["domain"] == "auth"


def test_architecture_takes_precedence_with_domain_tag():
    task = valid_task(
        title="Design auth service architecture",
        description="JWT and login architecture boundaries",
        task_type="architecture",
        assigned_system="architect",
    )
    assignment = AgentAssignerEngine.classify_task(task)
    assert assignment["assigned_agent"] == "ArchitectAgent"
    assert assignment["domain"] == "auth"


def test_assign_tasks_builds_dag_parallel_groups():
    tasks = [
        valid_task("task_1", title="Design API architecture", task_type="architecture", assigned_system="architect"),
        valid_task("task_2", title="Implement API endpoint", description="REST route", dependencies=["task_1"]),
        valid_task("task_3", title="Implement UI dashboard", description="React dashboard", dependencies=["task_1"], priority="medium"),
        valid_task("task_4", title="Run integration tests", task_type="testing", assigned_system="tester", dependencies=["task_2", "task_3"]),
    ]

    result = assign_tasks(tasks, thread_id="assigner_dag_test")

    assert result["success"] is True
    assert result["assignments"]["task_1"]["assigned_agent"] == "ArchitectAgent"
    assert result["assignments"]["task_2"]["assigned_agent"] == "APISquadAgent"
    assert result["assignments"]["task_3"]["assigned_agent"] == "UISquadAgent"
    assert result["assignments"]["task_4"]["assigned_agent"] == "TestRunnerAgent"

    plan_by_id = {item["task_id"]: item for item in result["execution_plan"]}
    assert plan_by_id["task_1"]["parallel_group"] == 0
    assert plan_by_id["task_2"]["parallel_group"] == 1
    assert plan_by_id["task_3"]["parallel_group"] == 1
    assert plan_by_id["task_4"]["parallel_group"] == 2


def test_assign_tasks_rejects_unknown_dependency():
    tasks = [valid_task("task_1", dependencies=["task_missing"])]

    result = assign_tasks(tasks, thread_id="assigner_unknown_dependency_test")

    assert result["success"] is False
    assert any("unknown task id 'task_missing'" in v for v in result["breaches"])


def test_assign_tasks_rejects_cross_domain_squad_breach():
    task = valid_task(
        "task_1",
        title="Implement auth CSS component",
        description="JWT login logic mixed with CSS styling",
    )

    result = assign_tasks([task], thread_id="assigner_cross_domain_test")

    assert result["success"] is False
    assert any("forbidden keyword 'css'" in v for v in result["breaches"])


def test_assign_tasks_rejects_incomplete_task_schema():
    result = assign_tasks([
        {"id": "task_1", "title": "Incomplete", "type": "feature"}
    ], thread_id="assigner_incomplete_schema_test")

    assert result["success"] is False
    assert any("missing 'description'" in v for v in result["breaches"])
