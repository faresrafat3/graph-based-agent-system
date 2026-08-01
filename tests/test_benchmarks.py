import json

import pytest

import agents.task_decomposer as task_decomposer_module
from benchmarks.benchmark_suite import run_benchmarks


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


def test_agent_benchmark_suite(monkeypatch):
    monkeypatch.setattr(task_decomposer_module, "call_llm", fake_task_decomposition_response)

    res = run_benchmarks()
    assert "summary" in res
    assert res["summary"]["total_scenarios"] == 4
    # 3 standard pass + 1 adversarial blocked
    assert res["summary"]["success_rate_percent"] >= 75.0
