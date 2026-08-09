"""Tests for the truth ledger: one measured source for every contested number.

Written before the implementation (T26 vertical block, TDD).
Each test names the falsifier it enforces, per T04:
behaviour + declared falsifier + proof the production path executes.
"""

import json

import pytest

from system.truth_ledger import (
    Claim,
    TruthLedger,
    UnmeasuredClaimError,
)


@pytest.fixture()
def ledger(tmp_path):
    return TruthLedger(tmp_path / "truth.jsonl")


# --- behaviour: a claim cannot exist without the command that measured it ----


def test_claim_requires_a_measuring_command(ledger):
    """Falsifier: a number can be recorded with no way to re-derive it."""
    with pytest.raises(UnmeasuredClaimError):
        ledger.record(Claim(key="agent_count", value=28, command=""))


def test_recorded_claim_is_readable_back(ledger):
    ledger.record(Claim(key="agent_count", value=7, command="rg -c call_llm agents/"))
    assert ledger.get("agent_count").value == 7


def test_value_must_be_a_number_or_str_not_a_container(ledger):
    """Falsifier: a claim holds a blob nobody can compare across runs."""
    with pytest.raises(UnmeasuredClaimError):
        ledger.record(Claim(key="x", value={"a": 1}, command="echo"))


# --- behaviour: the ledger detects contradiction instead of absorbing it ----


def test_second_different_value_for_same_key_is_a_contradiction(ledger):
    ledger.record(Claim(key="tests", value=1184, command="pytest --collect-only -q"))
    ledger.record(Claim(key="tests", value=510, command="old count"))
    assert ledger.contradictions() == ["tests"]


def test_same_value_recorded_twice_is_not_a_contradiction(ledger):
    ledger.record(Claim(key="tests", value=1184, command="pytest -q"))
    ledger.record(Claim(key="tests", value=1184, command="pytest -q"))
    assert ledger.contradictions() == []


def test_latest_wins_but_history_is_kept(ledger):
    """Reasoning is never discarded silently (golden rule 2)."""
    ledger.record(Claim(key="pct", value=39, command="a"))
    ledger.record(Claim(key="pct", value=43, command="b"))
    assert ledger.get("pct").value == 43
    assert [c.value for c in ledger.history("pct")] == [39, 43]


# --- behaviour: persistence is real, not in-memory theatre ------------------


def test_claims_survive_a_new_instance(tmp_path):
    p = tmp_path / "truth.jsonl"
    TruthLedger(p).record(Claim(key="loc", value=33472, command="pygount"))
    assert TruthLedger(p).get("loc").value == 33472


def test_file_is_one_json_object_per_line(tmp_path):
    p = tmp_path / "truth.jsonl"
    led = TruthLedger(p)
    led.record(Claim(key="a", value=1, command="c"))
    led.record(Claim(key="b", value=2, command="c"))
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["key"] for line in lines)


def test_missing_key_returns_none_rather_than_raising(ledger):
    assert ledger.get("never_recorded") is None


# --- behaviour: the ledger can audit prose for stale numbers ---------------


def test_verify_text_flags_a_number_that_contradicts_the_ledger(ledger):
    ledger.record(Claim(key="agent_count", value=7, command="rg -c call_llm agents/"))
    stale = ledger.verify_text("The system has 28 agents.", key="agent_count")
    assert stale == [28]


def test_verify_text_passes_when_the_number_matches(ledger):
    ledger.record(Claim(key="agent_count", value=7, command="rg"))
    assert ledger.verify_text("Only 7 agents call a model.", key="agent_count") == []


def test_verify_text_ignores_unrelated_numbers(ledger):
    ledger.record(Claim(key="agent_count", value=7, command="rg"))
    assert ledger.verify_text("7 agents, measured on 2026-08-08.", key="agent_count") == []


def test_qualified_count_is_a_different_claim_not_a_contradiction(ledger):
    """Falsifier: the auditor cries wolf on a true statement about another subject.

    "8 inert agents" and "7 agents call a model" are both correct. Flagging the
    first as stale would train us to ignore the tool.
    """
    ledger.record(Claim(key="agent_count", value=7, command="rg"))
    assert ledger.verify_text("There are 8 inert agents.", key="agent_count") == []
    assert ledger.verify_text("28 registered agents exist.", key="agent_count") == []


def test_explicit_subject_targets_the_right_claim(ledger):
    ledger.record(Claim(key="inert_agents", value=8, command="ast pass"))
    assert ledger.verify_text("There are 11 inert agents.", key="inert_agents",
                              subject="inert agents") == [11]
    assert ledger.verify_text("There are 8 inert agents.", key="inert_agents",
                              subject="inert agents") == []
