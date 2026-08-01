from agents.resource_priority_agent import RESOURCE_PRIORITY_PERMISSIONS, prioritize_resources


def test_permissions_matrix():
    assert "token_usage" in RESOURCE_PRIORITY_PERMISSIONS["READ"]
    assert "queue_order" in RESOURCE_PRIORITY_PERMISSIONS["WRITE"]
    assert "exceed_hard_budget" in RESOURCE_PRIORITY_PERMISSIONS["NEVER"]


def test_prioritize_ready_tasks_by_priority():
    queue = [
        {"task_id": "low", "priority": "low"},
        {"task_id": "high", "priority": "high"},
        {"task_id": "medium", "priority": "medium"},
    ]
    res = prioritize_resources(queue, thread_id="resource_priority")
    assert res["success"] is True
    assert res["queue_order"] == ["high", "medium", "low"]


def test_prioritize_defers_dependency_blocked_task():
    queue = [
        {"task_id": "child", "priority": "high", "depends_on": ["parent"]},
        {"task_id": "ready", "priority": "medium"},
    ]
    res = prioritize_resources(queue, completed_task_ids=[], thread_id="resource_dependency")
    assert res["success"] is True
    assert res["queue_order"] == ["ready"]
    assert res["deferred_tasks"] == ["child"]


def test_prioritize_blocks_exhausted_budget():
    queue = [{"task_id": "task_1", "priority": "high"}]
    res = prioritize_resources(
        queue,
        token_usage={"used": 100, "budget": 100},
        api_rate_limits={"remaining": 0},
        thread_id="resource_exhausted",
    )
    assert res["success"] is False
    assert "task_1" in res["deferred_tasks"]
    assert "token_budget_exhausted" in res["rate_limit_actions"]
    assert "api_rate_limit_exhausted" in res["rate_limit_actions"]
