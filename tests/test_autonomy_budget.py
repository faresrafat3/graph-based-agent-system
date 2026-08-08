"""Tests for system/autonomy_budget.py — bounded autonomy with non-self-reported exit.

The central assertion class is `TestSelfReportInvariant`: no combination of agent
claims may terminate a run. Everything else pins the individual limits so a future
change to one cannot silently disable another.

No network, no LLM, no real subprocesses except where explicitly marked.
"""

from __future__ import annotations

import pytest

from system.autonomy_budget import (
    CONTINUATION_PROMPT,
    AutonomyBudget,
    AutonomyState,
    BudgetError,
    ContinueReason,
    GateAttempt,
    StopReason,
    WorktreeSnapshot,
    capture_worktree_snapshot,
    decide,
    record_continuation,
    record_turn,
    run_gates,
)

# --------------------------------------------------------------------------
# configuration validation
# --------------------------------------------------------------------------


def test_budget_defaults_are_conservative():
    """A default budget must be small enough that a runaway run is cheap."""
    b = AutonomyBudget()
    assert b.max_continuations <= 5
    assert b.max_turns <= 20
    assert b.max_tokens <= 200_000
    assert b.timeout_seconds <= 3600
    assert b.gate_commands == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_turns": -1},
        {"max_tokens": -5},
        {"max_continuations": "3"},
        {"gate_max_retries": -1},
        {"timeout_seconds": 0},
        {"gate_timeout_seconds": -10},
    ],
)
def test_budget_rejects_invalid_configuration(kwargs):
    with pytest.raises(BudgetError):
        AutonomyBudget(**kwargs)


def test_gate_commands_normalized_to_tuple():
    b = AutonomyBudget(gate_commands=["make test", "make audit"])
    assert isinstance(b.gate_commands, tuple)


# --------------------------------------------------------------------------
# THE invariant
# --------------------------------------------------------------------------


class TestSelfReportInvariant:
    """An autonomous run never ends because the agent said so."""

    def test_agent_claim_alone_does_not_stop_the_run(self):
        decision = decide(AutonomyBudget(), AutonomyState(), agent_claims_done=True)
        assert decision.should_continue is True
        assert decision.continue_reason is ContinueReason.MISSING_TERMINAL_EVIDENCE

    def test_agent_claim_with_failing_gates_does_not_stop_the_run(self):
        decision = decide(
            AutonomyBudget(gate_commands=("make test",)),
            AutonomyState(),
            agent_claims_done=True,
            gates_passed=False,
        )
        assert decision.should_continue is True

    def test_agent_claim_with_unevaluated_gates_does_not_stop_the_run(self):
        """gates_passed=None means 'not checked'. Absence of evidence is not evidence."""
        decision = decide(
            AutonomyBudget(gate_commands=("make test",)),
            AutonomyState(),
            agent_claims_done=True,
            gates_passed=None,
        )
        assert decision.should_continue is True
        assert decision.continue_reason is ContinueReason.MISSING_TERMINAL_EVIDENCE

    def test_no_stop_reason_exists_for_a_self_report(self):
        """Structural guarantee: the enum has no AGENT_SAID_DONE member."""
        names = {member.name for member in StopReason}
        for forbidden in ("AGENT_SAID_DONE", "SELF_REPORTED", "AGENT_COMPLETE", "MODEL_DONE"):
            assert forbidden not in names

    def test_only_gates_or_limits_can_terminate(self):
        """Every terminal reason is either a passed gate or a spent limit."""
        terminal = {m for m in StopReason if m is not StopReason.RUNNING}
        for member in terminal:
            assert member is StopReason.GATES_PASSED or member.value.startswith(
                ("limit_", "gate_retries_")
            ), f"{member} is neither gate-based nor limit-based"


# --------------------------------------------------------------------------
# limits, each independently
# --------------------------------------------------------------------------


def test_continuation_limit_stops_and_escalates():
    budget = AutonomyBudget(max_continuations=2)
    state = AutonomyState(continuations_used=2)
    d = decide(budget, state)
    assert d.should_continue is False
    assert d.stop_reason is StopReason.LIMIT_CONTINUATIONS
    assert d.escalate is True


def test_turn_limit_stops_and_escalates():
    d = decide(AutonomyBudget(max_turns=4), AutonomyState(turns_used=4))
    assert d.stop_reason is StopReason.LIMIT_TURNS
    assert d.escalate is True


def test_token_limit_stops_and_escalates():
    d = decide(AutonomyBudget(max_tokens=1000), AutonomyState(tokens_used=1000))
    assert d.stop_reason is StopReason.LIMIT_TOKENS
    assert d.escalate is True


def test_wall_clock_limit_stops_and_escalates():
    """Injected `now` keeps the test deterministic — no sleeping, no flakes."""
    state = AutonomyState(started_at=1000.0)
    d = decide(AutonomyBudget(timeout_seconds=60), state, now=1061.0)
    assert d.stop_reason is StopReason.LIMIT_WALL_CLOCK
    assert d.escalate is True


def test_wall_clock_not_yet_reached_continues():
    state = AutonomyState(started_at=1000.0)
    d = decide(AutonomyBudget(timeout_seconds=60), state, now=1030.0)
    assert d.should_continue is True


def test_limits_take_precedence_over_passing_gates():
    """The budget is the outer contract: exhaustion wins even if gates passed."""
    d = decide(
        AutonomyBudget(max_turns=3, gate_commands=("make test",)),
        AutonomyState(turns_used=3),
        gates_passed=True,
    )
    assert d.should_continue is False
    assert d.stop_reason is StopReason.LIMIT_TURNS


def test_each_limit_is_checked_independently():
    """A generous budget on three axes must not mask exhaustion on the fourth."""
    budget = AutonomyBudget(
        max_continuations=999, max_turns=999, max_tokens=999_999, timeout_seconds=9999
    )
    axes = [
        ("continuations_used", 999, StopReason.LIMIT_CONTINUATIONS),
        ("turns_used", 999, StopReason.LIMIT_TURNS),
        ("tokens_used", 999_999, StopReason.LIMIT_TOKENS),
    ]
    for attr, value, expected in axes:
        state = AutonomyState()
        setattr(state, attr, value)
        assert decide(budget, state).stop_reason is expected


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def test_gates_passed_terminates_without_escalation():
    d = decide(AutonomyBudget(gate_commands=("make test",)), AutonomyState(), gates_passed=True)
    assert d.should_continue is False
    assert d.stop_reason is StopReason.GATES_PASSED
    assert d.escalate is False


def test_no_configured_gates_means_gates_never_pass():
    """Safety property: without a gate there is no evidence, so no gate-based exit.

    Returning True here would silently restore self-declared completion.
    """
    passed, attempts = run_gates(AutonomyBudget(gate_commands=()), AutonomyState())
    assert passed is False
    assert attempts == []


def test_all_gates_passing_returns_true_with_evidence():
    calls: list[str] = []

    def runner(cmd, cwd, timeout):
        calls.append(cmd)
        return 0, "ok", 0.01

    passed, attempts = run_gates(
        AutonomyBudget(gate_commands=("make test", "make audit")),
        AutonomyState(),
        command_runner=runner,
    )
    assert passed is True
    assert calls == ["make test", "make audit"]
    assert [a.passed for a in attempts] == [True, True]


def test_gates_stop_at_first_failure():
    """A later gate's result is meaningless once an earlier one failed."""
    calls: list[str] = []

    def runner(cmd, cwd, timeout):
        calls.append(cmd)
        return (1, "assertion failed", 0.01) if cmd == "make test" else (0, "ok", 0.01)

    passed, attempts = run_gates(
        AutonomyBudget(gate_commands=("make test", "make audit")),
        AutonomyState(),
        command_runner=runner,
    )
    assert passed is False
    assert calls == ["make test"], "second gate must not run after the first failed"
    assert len(attempts) == 1


def test_gate_failure_is_recorded_as_evidence_not_a_claim():
    state = AutonomyState()

    def runner(cmd, cwd, timeout):
        return 2, "E   AssertionError: lost 3 rows", 1.5

    run_gates(AutonomyBudget(gate_commands=("make test",)), state, command_runner=runner)
    failure = state.last_gate_failure
    assert isinstance(failure, GateAttempt)
    assert failure.exit_code == 2
    assert "AssertionError" in failure.output
    assert failure.passed is False
    assert failure.duration_s == 1.5


def test_gate_output_is_tail_truncated_to_bound_context():
    state = AutonomyState()

    def runner(cmd, cwd, timeout):
        return 1, "x" * 20_000 + "THE_REAL_ERROR", 0.1

    run_gates(AutonomyBudget(gate_commands=("make test",)), state, command_runner=runner)
    assert state.last_gate_failure is not None
    output = state.last_gate_failure.output
    assert len(output) <= 6000
    assert output.endswith("THE_REAL_ERROR"), "tail must be kept — the failure is at the end"


def test_gate_retry_exhaustion_escalates_with_evidence():
    budget = AutonomyBudget(gate_commands=("make test",), gate_max_retries=2)
    state = AutonomyState()

    def runner(cmd, cwd, timeout):
        return 1, "still failing", 0.1

    run_gates(budget, state, command_runner=runner)
    assert decide(budget, state).should_continue is True  # one retry left

    run_gates(budget, state, command_runner=runner)
    d = decide(budget, state)
    assert d.should_continue is False
    assert d.stop_reason is StopReason.GATE_RETRIES_EXHAUSTED
    assert d.escalate is True


def test_failing_gate_below_retry_cap_continues_with_gate_failed_reason():
    budget = AutonomyBudget(gate_commands=("make test",), gate_max_retries=3)
    state = AutonomyState()
    run_gates(budget, state, command_runner=lambda c, w, t: (1, "boom", 0.1))
    d = decide(budget, state)
    assert d.should_continue is True
    assert d.continue_reason is ContinueReason.GATE_FAILED
    assert "make test" in d.detail


def test_gate_timeout_is_a_failure_not_an_exception():
    """A hanging gate has not passed. It must not crash the run."""
    import subprocess

    def runner(cmd, cwd, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    # the real _run_command handles this; here we verify via the real implementation
    budget = AutonomyBudget(gate_commands=("sleep 5",), gate_timeout_seconds=0.05)
    state = AutonomyState()
    passed, attempts = run_gates(budget, state, cwd=".")
    assert passed is False
    assert attempts[0].exit_code == 124, "timeout must surface as exit 124"


def test_unexecutable_gate_command_fails_cleanly():
    budget = AutonomyBudget(gate_commands=("this_command_does_not_exist_xyz",))
    state = AutonomyState()
    passed, attempts = run_gates(budget, state, cwd=".")
    assert passed is False
    assert attempts[0].exit_code != 0


# --------------------------------------------------------------------------
# accounting
# --------------------------------------------------------------------------


def test_record_turn_accumulates_turns_and_tokens():
    state = AutonomyState()
    record_turn(state, tokens=500)
    record_turn(state, tokens=250)
    assert state.turns_used == 2
    assert state.tokens_used == 750


def test_record_turn_ignores_negative_tokens():
    """A provider reporting a negative count must not refund budget."""
    state = AutonomyState()
    record_turn(state, tokens=-999)
    assert state.tokens_used == 0
    assert state.turns_used == 1


def test_record_continuation_accumulates():
    state = AutonomyState()
    record_continuation(state)
    record_continuation(state)
    assert state.continuations_used == 2


def test_elapsed_uses_injected_now():
    state = AutonomyState(started_at=100.0)
    assert state.elapsed_s(now=175.0) == 75.0


# --------------------------------------------------------------------------
# worktree snapshot
# --------------------------------------------------------------------------


def test_snapshot_captures_status_diff_and_untracked_hash():
    class _Proc:
        def __init__(self, out):
            self.stdout = out

    def runner(args, **kwargs):
        if args[:2] == ["git", "status"]:
            return _Proc(" M system/refine_gate.py\n")
        if args[:2] == ["git", "diff"]:
            return _Proc("@@ -1 +1 @@\n-old\n+new\n")
        return _Proc("tests/new_file.py\n")

    snap = capture_worktree_snapshot(".", runner=runner)
    assert "refine_gate.py" in snap.status
    assert "+new" in snap.diff
    assert len(snap.untracked_hash) == 16


def test_snapshot_untracked_hash_is_stable_and_content_sensitive():
    class _Proc:
        def __init__(self, out):
            self.stdout = out

    def make_runner(untracked):
        def runner(args, **kwargs):
            if args[:2] == ["git", "status"]:
                return _Proc("")
            if args[:2] == ["git", "diff"]:
                return _Proc("")
            return _Proc(untracked)
        return runner

    a1 = capture_worktree_snapshot(".", runner=make_runner("a.py\n")).untracked_hash
    a2 = capture_worktree_snapshot(".", runner=make_runner("a.py\n")).untracked_hash
    b = capture_worktree_snapshot(".", runner=make_runner("b.py\n")).untracked_hash
    assert a1 == a2, "same untracked set must hash identically"
    assert a1 != b, "different untracked set must hash differently"


def test_snapshot_never_raises_when_git_is_unavailable():
    """A missing git degrades the snapshot; it must not become a new failure mode."""

    def runner(args, **kwargs):
        raise FileNotFoundError("git not installed")

    snap = capture_worktree_snapshot(".", runner=runner)
    assert isinstance(snap, WorktreeSnapshot)
    assert snap.status == "" and snap.diff == "" and snap.untracked_hash == ""


# --------------------------------------------------------------------------
# serialization + prompt
# --------------------------------------------------------------------------


def test_decision_is_json_serializable():
    import json

    payload = json.loads(json.dumps(decide(AutonomyBudget(), AutonomyState()).to_dict()))
    assert payload["should_continue"] is True
    assert payload["stop_reason"] == "running"


def test_continuation_prompt_forbids_self_declared_completion():
    low = CONTINUATION_PROMPT.lower()
    assert "do not end the run on your own" in low
    assert "gates" in low
    assert "evidence" in low


def test_continuation_prompt_matches_the_state_machine():
    """The prompt must not promise behaviour `decide()` does not implement."""
    d = decide(AutonomyBudget(), AutonomyState(), agent_claims_done=True)
    assert d.should_continue is True, "prompt says gates decide; decide() must agree"
