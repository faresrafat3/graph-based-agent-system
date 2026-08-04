import json

import pytest

import agents.task_decomposer as task_decomposer_module
import agents.domain_squads as domain_squads_module
from agents.karpathy_pipeline import run_karpathy_pipeline


def fake_task_decomposition_response(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """Deterministic test double for Stepfun task decomposition calls."""
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


@pytest.fixture(autouse=True)
def patch_stepfun_boundary(monkeypatch):
    """Keep pipeline tests deterministic without reintroducing production fallback."""
    monkeypatch.setattr(task_decomposer_module, "call_llm", fake_task_decomposition_response)


def test_full_pipeline_success():
    """End-to-end pipeline: Curate → Decompose → Validate → Pass"""
    result = run_karpathy_pipeline(
        requirements="Build a login page with email authentication",
        project_context="Web application",
        constraints="Use React",
    )
    assert result["stage"] == "complete"
    assert result["success"] is True
    assert result["quality_score"] == 1.0
    assert len(result["tasks"]) > 0
    assert result["assignment_success"] is True
    assert len(result["execution_plan"]) == len(result["tasks"])


def test_pipeline_context_signal_to_noise():
    """Verify context sanitation preserves signal"""
    result = run_karpathy_pipeline(
        requirements="Simple dashboard with charts",
    )
    assert result["context_signal_to_noise"] == 1.0  # Clean input = no noise removed


def test_pipeline_with_noisy_input():
    """Verify pipeline handles noisy tracebacks in requirements"""
    noisy = """Build user profile page.
    Traceback (most recent call last):
      File "app.py", line 10
    RuntimeError: crash
    
    Also add settings page."""
    result = run_karpathy_pipeline(requirements=noisy)
    assert result["stage"] == "complete"
    assert result["success"] is True
    assert result["context_signal_to_noise"] < 1.0  # Noise was removed


def test_pipeline_optional_domain_dispatch(monkeypatch):
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

    result = run_karpathy_pipeline(
        requirements="Build an API endpoint for status checks",
        project_context="FastAPI application",
        dispatch_domains=True,
    )

    assert result["success"] is True
    assert result["domain_dispatch"]["success"] is True
    assert result["domain_dispatch"]["results"]


def test_pipeline_optional_graph_orchestration():
    result = run_karpathy_pipeline(
        requirements="Build an API endpoint for status checks",
        project_context="FastAPI application",
        orchestrate_graph=True,
    )

    assert result["success"] is True
    assert result["graph_execution"]["success"] is True
    assert result["graph_execution"]["completed_task_ids"]
    assert result["quality_review"]["approved"] is True


def test_pipeline_context_curation_fails(monkeypatch):
    """Verify pipeline failure path when context curation fails"""
    import agents.karpathy_pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, "curate_context", lambda *a, **k: {"success": False})
    
    result = run_karpathy_pipeline(requirements="test prompt")
    assert result["success"] is False
    assert result["stage"] == "context_curation"
    assert "Context sanitation failed" in result["error"]


def test_pipeline_surgical_refinement_loop(monkeypatch):
    """Verify pipeline surgical refiner loop on decomposition validation failures"""
    import agents.karpathy_pipeline as pipeline_module
    
    validation_calls = []
    
    def fake_validate_output(target_output, required_keys):
        if not validation_calls:
            validation_calls.append("fail")
            return {"success": False, "violations": ["Mock Violation"], "quality_score": 0.5}
        else:
            validation_calls.append("pass")
            return {"success": True, "violations": [], "quality_score": 1.0}
            
    monkeypatch.setattr(pipeline_module, "validate_output", fake_validate_output)
    monkeypatch.setattr(pipeline_module, "generate_refinement_feedback", lambda *a, **k: {"surgical_feedback": "Please fix"})
    
    result = run_karpathy_pipeline(requirements="test prompt")
    assert result["success"] is True
    assert len(validation_calls) == 2


def test_pipeline_code_execution_loop(monkeypatch):
    """Verify code generation, execution, and test runner loop inside the pipeline"""
    import agents.karpathy_pipeline as pipeline_module
    
    def fake_execute_task(task, **k):
        return {
            "success": True, 
            "code": "def solve(): pass", 
            "filename": "solve.py", 
            "test_filename": "test_solve.py", 
            "test_code": "def test_solve(): pass"
        }
        
    def fake_run_code_and_tests(*a, **k):
        return {"success": True, "passed_tests": 1, "failed_tests": 0}
        
    monkeypatch.setattr(pipeline_module, "execute_task", fake_execute_task)
    monkeypatch.setattr(pipeline_module, "run_code_and_tests", fake_run_code_and_tests)
    
    result = run_karpathy_pipeline(requirements="test prompt", execute_code=True)
    assert result["success"] is True
    assert len(result["executed_modules"]) == 1
    assert result["executed_modules"][0]["test_execution"]["success"] is True

