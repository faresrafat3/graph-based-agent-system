import pytest
from benchmarks.benchmark_suite import run_benchmarks


def test_agent_benchmark_suite():
    res = run_benchmarks()
    assert "summary" in res
    assert res["summary"]["total_scenarios"] == 4
    # 3 standard pass + 1 adversarial blocked
    assert res["summary"]["success_rate_percent"] >= 75.0
