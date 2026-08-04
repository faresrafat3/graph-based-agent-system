import json

import agents.domain_squads as domain_squads_module
from agents.graph_execution_orchestrator import (
    GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS,
    orchestrate_graph_execution,
)


def task(task_id, title="Implement API endpoint", description="REST API route", dependencies=None):
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "type": "feature",
        "priority": "high",
        "dependencies": dependencies or [],
        "estimated_effort": "medium",
        "assigned_system": "developer",
        "acceptance_criteria": ["Done"],
    }


def plan(task_id, agent="APISquadAgent", depends_on=None, group=0):
    return {
        "task_id": task_id,
        "assigned_agent": agent,
        "domain": "api",
        "depends_on": depends_on or [],
        "parallel_group": group,
        "priority": "high",
        "rationale": "test",
    }


def test_permissions_matrix():
    assert "execution_plan" in GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS["READ"]
    assert "graph_execution_report" in GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS["WRITE"]
    assert "deployment" in GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS["NEVER"]


def test_orchestrate_plan_only_dag_success():
    tasks = [task("task_1"), task("task_2", dependencies=["task_1"])]
    execution_plan = [
        plan("task_1", agent="ArchitectAgent", group=0),
        plan("task_2", agent="APISquadAgent", depends_on=["task_1"], group=1),
    ]

    result = orchestrate_graph_execution(
        tasks=tasks,
        execution_plan=execution_plan,
        dispatch_domains=False,
        thread_id="graph_plan_only",
    )

    assert result["success"] is True
    assert result["completed_task_ids"] == ["task_1", "task_2"]
    assert result["progress_report"]["progress_metrics"]["completion_rate"] == 1.0
    assert result["quality_review"]["approved"] is True


def test_orchestrate_domain_dispatch_success(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: json.dumps(
            {
                "filename": "routes.py",
                "code": "def route(): pass",
                "test_filename": "test_routes.py",
                "test_code": "def test_route(): pass",
            }
        ),
    )

    tasks = [task("task_1")]
    execution_plan = [plan("task_1")]
    result = orchestrate_graph_execution(
        tasks=tasks,
        execution_plan=execution_plan,
        dispatch_domains=True,
        thread_id="graph_domain_dispatch",
    )

    assert result["success"] is True
    assert result["dispatch_result"]["parsed_outputs"]["task_1"]["filename"] == "routes.py"
    assert result["integration_result"]["integration_manifest"]["modules"] == ["routes.py"]


def test_orchestrate_blocks_unready_dependency():
    tasks = [task("task_2", dependencies=["task_1"])]
    execution_plan = [plan("task_2", depends_on=["task_1"], group=0)]

    result = orchestrate_graph_execution(
        tasks=tasks,
        execution_plan=execution_plan,
        dispatch_domains=False,
        thread_id="graph_blocked_dependency",
    )

    assert result["success"] is False
    assert any("deferred by incomplete dependencies" in v for v in result["breaches"])


def test_orchestrate_blocks_resource_exhaustion():
    tasks = [task("task_1")]
    execution_plan = [plan("task_1")]

    result = orchestrate_graph_execution(
        tasks=tasks,
        execution_plan=execution_plan,
        token_usage={"used": 10, "budget": 10},
        api_rate_limits={"remaining": 0},
        thread_id="graph_resource_block",
    )

    assert result["success"] is False
    assert any("budget exhausted" in v.lower() for v in result["breaches"])
