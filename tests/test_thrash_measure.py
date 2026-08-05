"""TDD test: thrash_count is MEASURED, not hardcoded (opus-5 P4 review finding).

opus-5 noted run_improvement_cycle.py hardcoded thrash_count=0 in the measure path, so the
0->3 rise couldn't be observed. This test asserts measure_benchmark wires the harness output
into thrash_count (or at least does not silently force 0).
"""

from unittest import mock

import agents.task_decomposer as td
from scripts import run_improvement_cycle as ric


def test_measure_benchmark_reads_thrash_from_harness():
    # Stub run_benchmarks summary; stub the thrashing harness to return a real count.
    fake_summary = {
        "success_rate_percent": 75.0,
        "effective_success_rate_percent": 80.0,
        "average_quality_score": 0.75,
        "average_signal_to_noise": 0.77,
    }
    with mock.patch("benchmarks.benchmark_suite.run_benchmarks", return_value={"summary": fake_summary}), \
         mock.patch.object(td, "call_llm", return_value="{}"), \
         mock.patch("scripts.measure_thrashing.main", return_value=(2, 3)):
        m = ric.measure_benchmark()
    # harness returned (dbg=2, ref=3) -> thrash = max = 3 (NOT hardcoded 0)
    assert m["thrash_count"] == 3


def test_measure_benchmark_falls_back_to_zero_only_on_harness_error():
    fake_summary = {
        "success_rate_percent": 75.0,
        "effective_success_rate_percent": 80.0,
        "average_quality_score": 0.75,
        "average_signal_to_noise": 0.77,
    }
    # Harness raises -> thrash falls back to 0 (safe), not a crash.
    with mock.patch("benchmarks.benchmark_suite.run_benchmarks", return_value={"summary": fake_summary}), \
         mock.patch.object(td, "call_llm", return_value="{}"), \
         mock.patch("scripts.measure_thrashing.main", side_effect=RuntimeError("no harness")):
        m = ric.measure_benchmark()
    assert m["thrash_count"] == 0
