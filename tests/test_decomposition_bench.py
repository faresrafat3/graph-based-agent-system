"""Tests for the decomposition benchmark scorer.

The scorer decides what "correct decomposition" means, so a bug here silently rewrites
every result the suite produces. This project already learned that lesson the expensive
way: four consecutive parser bugs in the SWE-bench triage tool each misclassified SOUND
instances as infra failures, and every one of them was biased toward FLATTERING the
system. So the scorer is tested before it is trusted, and the tests below deliberately
include cases where a plausible-looking plan must LOSE points.

All offline: no LLM, no network.
"""

from __future__ import annotations

import pytest

from benchmarks.decomposition_bench import (
    FIXTURES,
    _order_by_dependencies,
    _parse_steps,
    score_plan,
)

CSV = next(f for f in FIXTURES if f["id"] == "csv-etl")
CONTROL = next(f for f in FIXTURES if f["id"] == "single-unit-control")

PERFECT_CSV = [
    "Read and parse the sales CSV file",
    "Validate each row has a positive amount and a valid ISO date",
    "Aggregate totals per region",
    "Write the aggregated result to JSON output",
]


class TestFixtureIntegrity:
    """A fixture that cannot be satisfied would make an arm look bad for no reason."""

    def test_every_fixture_declares_the_required_shape(self):
        for fx in FIXTURES:
            assert fx["required"], f"{fx['id']} has no required concepts"
            assert fx["expected_units"] >= 1
            assert 1 <= fx["tier"] <= 4
            for concept in fx["required"]:
                assert isinstance(concept, set) and concept

    def test_fixture_ids_are_unique(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    def test_ordering_constraints_reference_real_concepts(self):
        """An ordering pair whose concepts appear in no `required` entry is unscoreable."""
        for fx in FIXTURES:
            flat = [syn for c in fx["required"] for syn in c]
            for before, after in fx["ordering"]:
                assert any(s in flat for s in before), f"{fx['id']}: dangling {before}"
                assert any(s in flat for s in after), f"{fx['id']}: dangling {after}"

    def test_the_ladder_covers_more_than_one_difficulty(self):
        """Averaging over a single tier would hide the effect the suite exists to measure."""
        assert len({f["tier"] for f in FIXTURES}) >= 3


class TestScoring:
    def test_a_correct_plan_scores_one(self):
        s = score_plan(PERFECT_CSV, CSV)
        assert s["coverage"] == 1.0
        assert s["order_accuracy"] == 1.0
        assert s["separation"] == 1.0
        assert s["granularity"] == 1.0
        assert s["composite"] == 1.0

    def test_a_missing_unit_lowers_coverage_and_is_named(self):
        s = score_plan(PERFECT_CSV[:3], CSV)          # drops the write step
        assert s["coverage"] == pytest.approx(0.75)
        assert any("write" in m or "output" in m or "export" in m for m in s["missing"])

    def test_inverted_order_is_caught_even_when_coverage_is_perfect(self):
        """The whole point: right units, wrong sequence is still a wrong plan."""
        inverted = [PERFECT_CSV[2], PERFECT_CSV[1], PERFECT_CSV[0], PERFECT_CSV[3]]
        s = score_plan(inverted, CSV)
        assert s["coverage"] == 1.0
        assert s["order_accuracy"] < 1.0
        assert s["order_violations"]

    def test_a_concept_split_across_prepare_and_execute_is_not_an_inversion(self):
        """Found by running the benchmark: a SOUND plan scored 0.2 on ordering.

        Real plans split one concept over several units — "create the backfill process"
        (prepare) legitimately precedes dual-write, while "run the backfill" (execute)
        follows it. First-occurrence-vs-first-occurrence read that as an inversion and
        punished the correct plan. The constraint is "prerequisite starts before the
        dependent finishes", so the dependent's LAST occurrence is the right anchor.
        """
        plan = [
            "Create the validation routine",      # dependent, prepared early
            "Read and parse the sales CSV file",  # prerequisite
            "Run validation over every row",      # dependent, executed after
            "Aggregate totals per region",
            "Write the result to JSON output",
        ]
        s = score_plan(plan, CSV)
        assert s["order_accuracy"] == 1.0, s["order_violations"]

    def test_a_genuine_inversion_still_fails_under_the_last_occurrence_rule(self):
        """Guard against the fix being too permissive: a real inversion must still fail."""
        plan = [
            "Write the result to JSON output",
            "Aggregate totals per region",
            "Validate each row",
            "Read and parse the CSV",
        ]
        s = score_plan(plan, CSV)
        assert s["order_accuracy"] < 0.5, s["order_violations"]

    def test_merging_forbidden_concepts_lowers_separation(self):
        merged = [
            "Read the CSV",
            "Validate rows and aggregate totals per region",   # forbidden merge
            "Write JSON",
        ]
        s = score_plan(merged, CSV)
        assert s["separation"] < 1.0
        assert s["merged"]

    def test_dumping_everything_into_one_unit_is_punished(self):
        s = score_plan(["Read validate aggregate and write the CSV to JSON"], CSV)
        assert s["granularity"] < 0.5
        assert s["composite"] < 0.8

    def test_over_decomposition_is_punished_on_the_control_fixture(self):
        """Inventing 6 steps for a one-line bug fix is miscalibration, not thoroughness."""
        bloated = [f"Step {i}: investigate pagination offset" for i in range(6)]
        s = score_plan(bloated, CONTROL)
        assert s["coverage"] == 1.0, "keywords are present, so only granularity should bite"
        assert s["granularity"] == 0.0
        assert s["composite"] < 1.0

    def test_the_control_fixture_rewards_a_single_unit(self):
        s = score_plan(["Fix the off-by-one error in the pagination offset"], CONTROL)
        assert s["composite"] == 1.0

    def test_empty_plan_scores_zero_without_crashing(self):
        s = score_plan([], CSV)
        assert s["coverage"] == 0.0 and s["granularity"] == 0.0
        assert s["composite"] < 0.6

    def test_blank_entries_are_not_counted_as_units(self):
        assert score_plan(PERFECT_CSV + ["", "   "], CSV)["n_units"] == 4

    def test_scoring_is_case_and_punctuation_insensitive(self):
        shouty = [u.upper() + " !!!" for u in PERFECT_CSV]
        assert score_plan(shouty, CSV)["composite"] == 1.0

    def test_padding_with_irrelevant_units_cannot_raise_the_score(self):
        """Guards against gaming: verbosity must not buy points."""
        base = score_plan(PERFECT_CSV, CSV)["composite"]
        padded = score_plan(PERFECT_CSV + ["Refactor unrelated helpers"] * 4, CSV)["composite"]
        assert padded <= base


class TestDependencyOrdering:
    def test_declared_dependencies_override_emission_order(self):
        tasks = [
            {"id": "3", "description": "write output", "dependencies": ["2"]},
            {"id": "1", "description": "read csv", "dependencies": []},
            {"id": "2", "description": "validate rows", "dependencies": ["1"]},
        ]
        assert _order_by_dependencies(tasks) == ["read csv", "validate rows", "write output"]

    def test_a_cycle_falls_back_to_emission_order_instead_of_hanging(self):
        tasks = [
            {"id": "a", "description": "first", "dependencies": ["b"]},
            {"id": "b", "description": "second", "dependencies": ["a"]},
        ]
        assert _order_by_dependencies(tasks) == ["first", "second"]

    def test_unknown_dependency_ids_are_ignored(self):
        tasks = [{"id": "1", "description": "only", "dependencies": ["ghost"]}]
        assert _order_by_dependencies(tasks) == ["only"]

    def test_plain_string_tasks_pass_through(self):
        assert _order_by_dependencies(["a", "b"]) == ["a", "b"]

    def test_depends_on_is_accepted_as_an_alias(self):
        tasks = [
            {"id": "2", "description": "second", "depends_on": "1"},
            {"id": "1", "description": "first"},
        ]
        assert _order_by_dependencies(tasks) == ["first", "second"]

    def test_empty_task_list_is_safe(self):
        assert _order_by_dependencies([]) == []


class TestStepParsing:
    def test_numbered_bulleted_and_plain_lines_all_parse(self):
        text = "1. Read the file\n2) Validate rows\n- Aggregate totals\n* Write JSON\nStep 5: Done"
        assert _parse_steps(text) == [
            "Read the file", "Validate rows", "Aggregate totals", "Write JSON", "Done",
        ]

    def test_blank_lines_and_headings_are_dropped(self):
        assert _parse_steps("# Plan\n\n1. Only step\n\n") == ["Only step"]

    def test_empty_input_yields_no_units(self):
        assert _parse_steps("") == []
        assert _parse_steps(None) == []
