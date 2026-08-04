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


def test_permission_breach_raises():
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


def test_task_decomposition_cache(monkeypatch):
    """Verify that similar past decompositions are retrieved from memory to skip LLM calls"""
    from memory.custom_memory import memory
    memory.clear_long_term()
    
    cached_tasks = [
        {
            "id": "t1",
            "title": "Task 1",
            "description": "cache test requirements", # Matches query keywords for semantic gate
            "type": "feature",
            "priority": "high",
            "dependencies": [],
            "estimated_effort": "medium",
            "assigned_system": "developer",
            "acceptance_criteria": ["criteria 1"]
        }
    ]
    cached_metadata = {
        "total_tasks": 1,
        "high_priority": 1,
        "medium_priority": 0,
        "low_priority": 0,
        "estimated_total_effort": "medium"
    }
    
    memory.add_to_long_term(
        data={
            "type": "decomposition",
            "requirements": "cache test requirements",
            "tasks": cached_tasks,
            "metadata": cached_metadata,
            "clarifications_needed": []
        },
        metadata={}
    )
    
    # Mock find_similar to return cached tasks directly
    monkeypatch.setattr(
        memory, 
        "find_similar", 
        lambda *a, **k: [{"entry": {"data": {"tasks": cached_tasks, "metadata": cached_metadata}}, "similarity": 1.0}]
    )
    
    result = decompose_requirements(
        requirements="cache test requirements",
        thread_id="decomposer_cache_session"
    )
    
    assert result["success"] is True
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["id"] == "t1"


def test_task_decomposition_normalizations(monkeypatch):
    """Verify JSON extraction and assignment role normalization on successful validations"""
    import json
    
    # Return JSON with no circular dependencies wrapped in markdown fences to cover line 248-249
    # Descriptions contain "test normalizations" to satisfy semantic coverage check
    raw_response = """
    Here is your decomposition:
    ```json
    {
        "tasks": [
            {
                "id": "t1",
                "title": "Task 1",
                "description": "test normalizations logic",
                "type": "feature",
                "priority": "high",
                "dependencies": [],
                "estimated_effort": "medium",
                "assigned_system": "frontend",
                "acceptance_criteria": ["crit 1"]
            },
            {
                "id": "t2",
                "title": "Task 2",
                "description": "test normalizations logic",
                "type": "feature",
                "priority": "high",
                "dependencies": ["t1"],
                "estimated_effort": "medium",
                "assigned_system": "design",
                "acceptance_criteria": ["crit 2"]
            },
            {
                "id": "t3",
                "title": "Task 3",
                "description": "test normalizations logic",
                "type": "feature",
                "priority": "high",
                "dependencies": [],
                "estimated_effort": "medium",
                "assigned_system": "qa",
                "acceptance_criteria": ["crit 3"]
            },
            {
                "id": "t4",
                "title": "Task 4",
                "description": "test normalizations logic",
                "type": "feature",
                "priority": "high",
                "dependencies": [],
                "estimated_effort": "medium",
                "assigned_system": "product",
                "acceptance_criteria": ["crit 4"]
            },
            {
                "id": "t5",
                "title": "Task 5",
                "description": "test normalizations logic",
                "type": "feature",
                "priority": "high",
                "dependencies": [],
                "estimated_effort": "medium",
                "assigned_system": "unknown_system",
                "acceptance_criteria": ["crit 5"]
            }
        ],
        "metadata": {
            "total_tasks": 5,
            "high_priority": 5,
            "medium_priority": 0,
            "low_priority": 0,
            "estimated_total_effort": "medium"
        },
        "clarifications_needed": []
    }
    ```
    Enjoy!
    """
    
    monkeypatch.setattr(task_decomposer_module, "call_llm", lambda *a, **k: raw_response)
    
    result = decompose_requirements("test normalizations", thread_id="decomposer_norm_session")
    
    assert result["success"] is True
    # Verify assignment normalizations
    assert result["tasks"][0]["assigned_system"] == "developer"  # frontend -> developer
    assert result["tasks"][1]["assigned_system"] == "architect"  # design -> architect
    assert result["tasks"][2]["assigned_system"] == "tester"     # qa -> tester
    assert result["tasks"][3]["assigned_system"] == "pm"         # product -> pm
    assert result["tasks"][4]["assigned_system"] == "developer"  # unknown -> developer



def test_task_decomposition_circular_dependencies(monkeypatch):
    """Verify that circular dependencies are successfully analyzed and flagged"""
    import json
    
    # Return JSON with circular dependencies and NO clarifications_needed key to cover line 287
    raw_response = """
    {
        "tasks": [
            {
                "id": "t1",
                "title": "Task 1",
                "description": "Desc 1",
                "type": "feature",
                "priority": "high",
                "dependencies": ["t2"],
                "estimated_effort": "medium",
                "assigned_system": "developer",
                "acceptance_criteria": ["crit 1"]
            },
            {
                "id": "t2",
                "title": "Task 2",
                "description": "Desc 2",
                "type": "feature",
                "priority": "high",
                "dependencies": ["t1"],
                "estimated_effort": "medium",
                "assigned_system": "developer",
                "acceptance_criteria": ["crit 2"]
            }
        ],
        "metadata": {
            "total_tasks": 2,
            "high_priority": 2,
            "medium_priority": 0,
            "low_priority": 0,
            "estimated_total_effort": "medium"
        }
    }
    """
    
    monkeypatch.setattr(task_decomposer_module, "call_llm", lambda *a, **k: raw_response)
    
    result = decompose_requirements("test circular", thread_id="decomposer_circular_session")
    
    # Will fail validation because of circular dependencies, which is expected
    assert result["success"] is False
    assert any("Circular dependencies detected" in c for c in result["clarifications_needed"])


def test_task_decomposition_invalid_json(monkeypatch):
    """Verify handling of JSON decode errors during parsing"""
    monkeypatch.setattr(task_decomposer_module, "call_llm", lambda *a, **k: "completely invalid JSON")
    
    result = decompose_requirements("test invalid json", thread_id="decomposer_invalid_json_session")
    assert result["success"] is False
    assert any("Failed to parse JSON" in c for c in result["clarifications_needed"])


def test_decomposer_refine_and_should_continue():
    """Verify refine and should_continue decisions inside decomposer graph"""
    from agents.task_decomposer import refine, should_continue
    
    res = refine({"retry_count": 0})
    assert res["retry_count"] == 1
    assert res["success"] is False
    
    assert should_continue({"success": True}) == "commit"
    assert should_continue({"success": False, "retry_count": 3}) == "escalate"
    assert should_continue({"success": False, "retry_count": 0}) == "refine"


def test_decomposer_internal_demo(monkeypatch):
    """Verify execution of the built-in demo function"""
    from agents.task_decomposer import test_task_decomposer
    monkeypatch.setattr(task_decomposer_module, "call_llm", fake_task_decomposition_response)
    test_task_decomposer()

