"""TDD test: A/B CIR vs Fused study runs deterministically (no live LLM).

Confirms the study harness executes both modes and emits a comparable score row,
without requiring the opus-5 channel (uses --no-opus5 mock path).
"""

from unittest import mock

from scripts import ab_cir_study as ab


def test_ab_study_runs_without_opus5():
    rows = []
    # Run the core logic on one scenario with mocked decompose + validate + opus5.
    scn = {
        "id": "test_scenario",
        "requirements": "Build a cache layer.",
        "project_context": "Python",
        "constraints": "Fast",
    }
    fused = {"tasks": [{"a": 1}], "metadata": {"k": "v"}}
    cir = {"tasks": [{"a": 1}, {"b": 2}], "metadata": {"k": "v", "x": 1}}
    with mock.patch.object(ab, "decompose_requirements", side_effect=[fused, cir]), \
         mock.patch.object(ab, "consult_opus5", return_value="(mock)"), \
         mock.patch.object(ab, "validate_output", return_value={"success": True, "breaches": []}):
        f = ab._fused_decompose(scn)
        c, strat = ab._cir_decompose(scn)
        assert isinstance(f, dict)
        # With consult_opus5 mocked to return "(mock)", strategy is non-empty and injected
        assert "_cir_strategy" in c
        assert strat == "(mock)"


def test_ab_score_counts_breaches():
    decomp = {"tasks": [{"x": 1}], "metadata": {"m": 1}}
    with mock.patch.object(ab, "validate_output",
                           return_value={"success": False, "breaches": [1, 2, 3]}):
        s = ab._score(decomp)
    assert s["breaches"] == 3
    assert s["task_count"] == 1


def test_ab_study_main_emits_rows(tmp_path):
    # Patch scenarios + opus5 + decompose/validate to run main() end-to-end offline.
    scns = [{"id": "s1", "requirements": "R", "project_context": "C", "constraints": "K"}]
    with mock.patch.object(ab, "BENCHMARK_SCENARIOS", scns), \
         mock.patch.object(ab, "consult_opus5", return_value="(mock)"), \
         mock.patch.object(ab, "decompose_requirements",
                           return_value={"tasks": [{"t": 1}], "metadata": {"m": 1}}), \
         mock.patch.object(ab, "validate_output",
                           return_value={"success": True, "breaches": []}), \
         mock.patch.object(ab, "time") as mt:
        mt.time.return_value = 123
        # Clean any pre-existing result file so the assertion is deterministic.
        stale = ab.PROJECT_ROOT / "benchmarks" / "results" / "ab_cir_123.jsonl"
        if stale.exists():
            stale.unlink()
        ab.main(["--scenarios", "1", "--no-opus5"])
    # results file written
    res = list((ab.PROJECT_ROOT / "benchmarks" / "results").glob("ab_cir_123.jsonl"))
    assert res, "A/B result file not written"
    content = res[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1  # one scenario row
