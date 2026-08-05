import json

import pytest

import agents.task_decomposer as task_decomposer_module
from benchmarks.benchmark_suite import run_benchmarks, is_adversarial_blocked


def fake_task_decomposition_response(prompt: str, system_prompt: str = "", **kwargs) -> str:
    """Deterministic Stepfun-boundary double for benchmark tests."""
    return json.dumps(
        {
            "tasks": [
                {
                    "id": "task_1",
                    "title": "Implement benchmark requirements",
                    "description": prompt,
                    "type": "feature",
                    "priority": "high",
                    "dependencies": [],
                    "estimated_effort": "large",
                    "assigned_system": "developer",
                    "acceptance_criteria": ["Benchmark requirements are covered"],
                }
            ],
            "metadata": {
                "total_tasks": 1,
                "high_priority": 1,
                "medium_priority": 0,
                "low_priority": 0,
                "estimated_total_effort": "large",
            },
            "clarifications_needed": [],
        }
    )


def _find_entry(results, scenario_id):
    for r in results:
        if r["scenario_id"] == scenario_id:
            return r
    raise AssertionError(f"scenario {scenario_id} not present")


def test_agent_benchmark_suite(monkeypatch):
    monkeypatch.setattr(task_decomposer_module, "call_llm", fake_task_decomposition_response)

    res = run_benchmarks()
    assert "summary" in res
    assert res["summary"]["total_scenarios"] == 4
    # 3 standard pass + 1 adversarial blocked
    assert res["summary"]["success_rate_percent"] >= 75.0


def test_scenario_4_adversarial_is_blocked_not_failed(monkeypatch):
    """Regression: an adversarial NEVER-permission breach must be recorded as a
    security success, not a silent failure. The Task Decomposer raises
    PermissionError on the adversarial scenario; the benchmark must capture that
    error text into `breaches` so is_adversarial_blocked() detects the block.
    """

    def raise_never_permission(*args, **kwargs):
        raise PermissionError(
            "Task Decomposer Agent attempted an action listed in NEVER permissions."
        )

    monkeypatch.setattr(task_decomposer_module, "call_llm", raise_never_permission)

    res = run_benchmarks()
    entry = _find_entry(res["details"], "scenario_4_security_adversarial")

    # The breach text must be present so the defense heuristic can match it.
    assert entry["breaches_count"] >= 1
    assert any("never" in str(b).lower() or "permission" in str(b).lower()
               for b in entry["breaches"])
    # Defense must register as a secure pass, not a raw failure.
    assert entry["security_blocked"] is True
    assert entry["effective_success"] is True
    assert is_adversarial_blocked(entry) is True


def test_is_adversarial_blocked_detects_never_breach():
    """Unit check on the heuristic: a captured NEVER/permission breach is a block."""
    blocked = is_adversarial_blocked({"breaches": ["NEVER permission violated"], "tasks": []})
    assert blocked is True
    not_blocked = is_adversarial_blocked({"breaches": [], "tasks": [{"id": "t1"}]})
    assert not_blocked is False
