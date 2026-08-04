import json

import pytest

import agents.domain_squads as domain_squads_module
from agents.domain_dispatcher import (
    DOMAIN_DISPATCHER_PERMISSIONS,
    dispatch_domain_tasks,
)


def task(task_id="task_1", title="Implement JWT login", description="JWT auth", dependencies=None):
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


def plan_item(task_id="task_1", agent="AuthSquadAgent", depends_on=None, group=0):
    return {
        "task_id": task_id,
        "assigned_agent": agent,
        "domain": "auth",
        "depends_on": depends_on or [],
        "parallel_group": group,
        "priority": "high",
        "rationale": "test",
    }


def valid_code_response(filename="auth.py"):
    return json.dumps({
        "filename": filename,
        "code": "def login(): pass",
        "test_filename": "test_auth.py",
        "test_code": "def test_login(): pass",
    })


def test_permissions_matrix():
    assert "execution_plan" in DOMAIN_DISPATCHER_PERMISSIONS["READ"]
    assert "dispatch_results" in DOMAIN_DISPATCHER_PERMISSIONS["WRITE"]
    assert "credentials" in DOMAIN_DISPATCHER_PERMISSIONS["NEVER"]


def test_dispatch_auth_squad_success(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: valid_code_response(),
    )

    result = dispatch_domain_tasks([task()], [plan_item()], global_context="Auth app")

    assert result["success"] is True
    assert result["parsed_outputs"]["task_1"]["filename"] == "auth.py"
    assert result["results"][0]["parse_success"] is True


def test_dispatch_parse_failure(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: "not json",
    )

    result = dispatch_domain_tasks([task()], [plan_item()], global_context="Auth app")

    assert result["success"] is False
    assert any("output parse breach" in v for v in result["breaches"])


def test_dispatch_skips_non_domain_agent():
    result = dispatch_domain_tasks(
        [task(title="Design architecture", description="Architecture")],
        [plan_item(agent="ArchitectAgent")],
    )

    assert result["success"] is True
    assert result["skipped_tasks"] == ["task_1"]
    assert result["results"][0]["stage"] == "skipped_non_domain_agent"


def test_dispatch_blocks_incomplete_dependency(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: valid_code_response(),
    )

    result = dispatch_domain_tasks(
        [task("task_2", dependencies=["task_1"])],
        [plan_item("task_2", depends_on=["task_1"], group=1)],
    )

    assert result["success"] is False
    assert result["blocked_tasks"] == ["task_2"]
    assert any("blocked by incomplete dependencies" in v for v in result["breaches"])


def test_dispatch_unknown_plan_task_fails():
    result = dispatch_domain_tasks([], [plan_item("missing")])

    assert result["success"] is False
    assert any("unknown task id" in v for v in result["breaches"])


def test_dispatch_respects_completed_dependencies(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: valid_code_response(),
    )

    result = dispatch_domain_tasks(
        [task("task_2", dependencies=["task_1"])],
        [plan_item("task_2", depends_on=["task_1"], group=1)],
        completed_task_ids={"task_1"},
    )

    assert result["success"] is True
    assert "task_2" in result["completed_task_ids"]


def test_dispatch_max_tasks_skips_remaining(monkeypatch):
    monkeypatch.setattr(
        domain_squads_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: valid_code_response(),
    )
    
    tasks = [
        task("task_1", title="JWT login"),
        task("task_2", title="DB setup")
    ]
    plan = [
        plan_item("task_1", agent="AuthSquadAgent", group=0),
        plan_item("task_2", agent="DatabaseSquadAgent", group=0)
    ]
    
    result = dispatch_domain_tasks(tasks, plan, max_tasks=1)
    
    assert result["success"] is True
    # The first task is processed
    assert result["results"][0]["stage"] == "domain_squad_execution"
    # The second task is skipped because of max_tasks limit
    assert result["results"][1]["stage"] == "skipped_max_tasks"
    assert "task_2" in result["skipped_tasks"]


def test_dispatch_squad_execution_error(monkeypatch):
    from agents.domain_squads import AuthSquadAgent
    
    def fake_execute_auth_task(*args, **kwargs):
        raise RuntimeError("squad runtime crash")
        
    monkeypatch.setattr(AuthSquadAgent, "execute_auth_task", fake_execute_auth_task)
    
    result = dispatch_domain_tasks([task()], [plan_item()])
    
    assert result["success"] is False
    assert result["results"][0]["stage"] == "squad_execution"
    assert any("dispatch failed in AuthSquadAgent: squad runtime crash" in v for v in result["breaches"])

