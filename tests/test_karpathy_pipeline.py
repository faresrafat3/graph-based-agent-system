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


def test_pipeline_domain_squad_code_is_execution_grounded(monkeypatch):
    """When execute_code=True, squad-parsed code must be run in the sandbox (F7 fix).

    Without this, squad output was parsed but never physically executed — an
    asymmetry against the project's execution-grounded thesis. The test stubs the
    network (call_llm) and the sandbox runner, and asserts the squad artifacts are
    actually handed to run_code_and_tests.
    """
    import importlib


    import llm.llm_integration as llm_mod

    kp_module = importlib.import_module("agents.karpathy_pipeline")

    fake_llm = lambda prompt, system_prompt="", **kwargs: json.dumps(
        {"tasks": [], "metadata": {}, "clarifications_needed": []}
    )
    monkeypatch.setattr(llm_mod, "call_llm", fake_llm)
    # Re-bind call_llm in every module the pipeline can reach (F13: not hermetic by default).
    for mod in (
        task_decomposer_module,
        domain_squads_module,
        __import__("agents.code_executor", fromlist=["call_llm"]),
        __import__("agents.semantic_memory_agent", fromlist=["call_llm"]),
        __import__("agents.reflexion_agent", fromlist=["call_llm"]),
        __import__("agents.sampling_agent", fromlist=["call_llm"]),
        __import__("agents.debugger_agent", fromlist=["call_llm"]),
    ):
        if hasattr(mod, "call_llm"):
            monkeypatch.setattr(mod, "call_llm", fake_llm)

    # The squad LLM must return parsed {code, test_code} so parsed_outputs is populated.
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
    # The squad task decomposition must yield a domain-assigned task so dispatch fires.
    # NOTE: task `type` is constrained to {feature,architecture,requirements,testing,
    # bugfix,refactor} by the deterministic validator; domain routing is by keyword
    # detection on the text, so we use type="feature" + api-rich description.
    monkeypatch.setattr(
        task_decomposer_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: json.dumps(
            {
                "tasks": [
                    {
                        "id": "task_1",
                        "title": "Build an API endpoint for status checks",
                        "description": "implement api rest endpoint route with fastapi",
                        "type": "feature",
                        "priority": "high",
                        "dependencies": [],
                        "estimated_effort": "small",
                        "assigned_system": "developer",
                        "acceptance_criteria": ["ok"],
                    }
                ],
                "metadata": {"total_tasks": 1},
                "clarifications_needed": [],
            }
        ),
    )

    squad_ran = []
    monkeypatch.setattr(
        kp_module,
        "run_code_and_tests",
        lambda *a, **k: squad_ran.append(k.get("filename")) or {"success": True, "passed_tests": 1, "failed_tests": 0},
    )
    # Stub the main-loop executor so it doesn't also hit the network.
    monkeypatch.setattr(
        kp_module,
        "execute_task",
        lambda task, project_context="": {"success": True, "filename": f"{task['id']}.py", "code": "x",
                                          "test_filename": f"test_{task['id']}.py", "test_code": "def test_x(): pass"},
    )

    result = run_karpathy_pipeline(
        requirements="Build an API endpoint for status checks",
        project_context="FastAPI application",
        dispatch_domains=True,
        execute_code=True,
    )

    assert result["domain_dispatch"]["success"] is True
    # The squad parsed code was handed to the sandbox runner.
    assert "test_execution" in result["domain_dispatch"]
    assert any("routes.py" in (f or "") for f in squad_ran)


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


def test_pipeline_execution_budget_is_loud_not_silent(monkeypatch, caplog):
    """karpathy_pipeline must NOT silently drop tasks beyond the exec budget.

    The old code did `for task in tasks[:3]` with no trace. This asserts the
    budget is explicit (MAX_EXEC_TASKS) and that exceeding it emits a warning
    (Law 3) and still attempts every in-budget task.

    The pipeline is NOT hermetically testable by default (memory/quality agents
    bind `call_llm` from `llm.llm_integration`); we patch it at the source module
    AND re-bind it in every importer so the test never touches the network (F13).
    """
    import llm.llm_integration as llm_mod

    fake_llm = lambda prompt, system_prompt="", **kwargs: json.dumps(
        {"tasks": [], "metadata": {}, "clarifications_needed": []}
    )
    monkeypatch.setattr(llm_mod, "call_llm", fake_llm)
    # Re-bind the already-imported local names in every module the pipeline can reach.
    for mod in (
        task_decomposer_module,
        domain_squads_module,
        __import__("agents.code_executor", fromlist=["call_llm"]),
        __import__("agents.semantic_memory_agent", fromlist=["call_llm"]),
        __import__("agents.reflexion_agent", fromlist=["call_llm"]),
        __import__("agents.sampling_agent", fromlist=["call_llm"]),
        __import__("agents.debugger_agent", fromlist=["call_llm"]),
    ):
        if hasattr(mod, "call_llm"):
            monkeypatch.setattr(mod, "call_llm", fake_llm)

    from agents.karpathy_pipeline import MAX_EXEC_TASKS, run_karpathy_pipeline, execute_task, run_code_and_tests
    import importlib

    kp_module = importlib.import_module("agents.karpathy_pipeline")

    # Force a decomposition that yields more tasks than the execution budget.
    big_tasks = [
        {
            "id": f"task_{i}",
            "title": f"Task {i}",
            "description": f"desc {i}",
            "type": "feature",
            "priority": "high" if i % 2 == 0 else "medium",
            "dependencies": [],
            "estimated_effort": "small",
            "assigned_system": "developer",
            "acceptance_criteria": ["ok"],
        }
        for i in range(1, MAX_EXEC_TASKS + 3)  # 2 more than the budget
    ]
    # The task_decomposer.call_llm must return the BIG plan (overrides the fake above).
    monkeypatch.setattr(
        task_decomposer_module,
        "call_llm",
        lambda prompt, system_prompt="", **kwargs: json.dumps(
            {"tasks": big_tasks, "metadata": {"total_tasks": len(big_tasks)}, "clarifications_needed": []}
        ),
    )
    # Stub the expensive code-gen/sandbox stage at the NAMES the pipeline binds
    # (it does `from agents.code_executor import execute_task`), so the module-level
    # attribute patch would NOT reach them. Patch the pipeline's own bindings.
    attempted = []
    monkeypatch.setattr(
        kp_module,
        "execute_task",
        lambda task, project_context="": attempted.append(task["id"])
        or {"success": True, "filename": f"{task['id']}.py", "code": "x",
            "test_filename": f"test_{task['id']}.py", "test_code": "def test_x(): pass"},
    )
    monkeypatch.setattr(
        kp_module,
        "run_code_and_tests",
        lambda *a, **k: {"success": True, "passed_tests": 1, "failed_tests": 0},
    )

    with caplog.at_level("WARNING"):
        result = run_karpathy_pipeline(
            requirements="Build many small features",
            execute_code=True,
        )

    # All decomposed tasks survive into the plan (no silent drop from the plan).
    assert len(result["tasks"]) == len(big_tasks)
    # The budget warning fired because the plan exceeded MAX_EXEC_TASKS.
    assert any("Execution budget capped" in r.message for r in caplog.records)
    # Every in-budget task was actually attempted for execution.
    assert len(attempted) == MAX_EXEC_TASKS
