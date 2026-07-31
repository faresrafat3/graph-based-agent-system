import pytest
from tools.mcp_tools import mcp_tools


def test_requirements_parser():
    parsed = mcp_tools.requirements_parser("Build a login page with authentication and database")
    assert "features" in parsed
    assert "ambiguities" in parsed
    assert len(parsed["features"]) >= 2


def test_dependency_analyzer_no_cycles():
    tasks = [
        {"id": "task_1", "type": "architecture", "dependencies": []},
        {"id": "task_2", "type": "feature", "dependencies": ["task_1"]},
        {"id": "task_3", "type": "testing", "dependencies": ["task_2"]}
    ]
    deps = mcp_tools.dependency_analyzer(tasks)
    assert "dependencies" in deps
    assert deps["circular_dependencies"] == []


def test_dependency_analyzer_with_cycle():
    tasks = [
        {"id": "task_1", "type": "feature", "dependencies": ["task_2"]},
        {"id": "task_2", "type": "feature", "dependencies": ["task_1"]}
    ]
    deps = mcp_tools.dependency_analyzer(tasks)
    assert len(deps["circular_dependencies"]) > 0


def test_effort_estimator():
    tasks = [{"id": "task_1", "type": "architecture"}]
    efforts = mcp_tools.effort_estimator(tasks)
    assert efforts["estimates"].get("task_1") == "medium"


def test_system_assigner():
    tasks = [{"id": "task_1", "type": "architecture"}]
    assignments = mcp_tools.system_assigner(tasks)
    assert assignments["assignments"].get("task_1") == "architect"


def test_priority_assigner():
    tasks = [{"id": "task_1", "type": "architecture"}]
    priorities = mcp_tools.priority_assigner(tasks)
    assert priorities["priorities"].get("task_1") == "high"
