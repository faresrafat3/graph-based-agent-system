# version: v1 | 2026-08-08 | verdict: pending-review
"""Autonomy Budget — bounded self-continuation with non-self-reported termination.

WHY THIS EXISTS
---------------
The system can measure itself (system/self_improvement.py) and be governed
(system/governance_checks.py), but it has no runtime that lets it keep working
without a human while remaining safe to leave alone. `system/bounded_probe.py`
caps *reflection attempts* (max_attempts=4); it does not bound turns, tokens, or
wall-clock, and it does not verify anything before stopping.

THE FAILURE MODE THIS TARGETS
-----------------------------
The dominant failure of long-running agents is not crashing -- it is *narrating
success*: the agent declares the task complete and stops, with nothing verified.
CONSTITUTION Article VI Section 2 names this explicitly as a thing we reject:

    "Wu-wei as default -- self-organization here has no benign attractor; without
     declared postconditions, unmonitored agents drift and narrate success."
    -- CONSTITUTION.md, Article VI Section 2

So this module enforces a single hard invariant:

    AN AUTONOMOUS RUN NEVER TERMINATES ON THE AGENT'S OWN CLAIM OF COMPLETION.

Termination has exactly two legitimate causes:
  * LIMIT_REACHED  -- a declared budget (continuations/turns/tokens/wall-clock) is spent
  * GATES_PASSED   -- every configured quality gate command exited 0

`agent_claims_done` is accepted as *input*, and is deliberately insufficient on its
own: when the agent says it is done but gates have not passed, `decide()` returns
CONTINUE with reason MISSING_TERMINAL_EVIDENCE. That mirrors prime-agent's
continuation prompt ("Do not end the session yourself; the verifier/evaluator decides
completion when configured gates pass" -- packages/coding-agent/src/core/autonomous.ts)
but promotes it from *prompt text* to an *architectural* rule: here it is a state
machine that cannot be talked out of, not an instruction a model may ignore.

That distinction is the whole point. A constraint expressed in a prompt is a request;
a constraint expressed in the control flow is a property.

RELATION TO EXISTING GOVERNANCE (Ruling C1: propose-only, default-deny)
----------------------------------------------------------------------
This module decides only whether to CONTINUE or STOP a run it was given. It never
applies a config change, never edits governance files, and never escalates its own
budget. Budget exhaustion surfaces as an escalation for a human (Article I.3
"Surface to Human"), not as a silent stop -- `AutonomyDecision.escalate` is True on
exhaustion so callers can emit HUMAN_CHECKPOINT.

Gate failures carry an evidence snapshot (see GateAttempt.output / worktree_snapshot)
because Law 16 forbids self-report: "the gate failed" is a claim; the captured exit
code and output are the evidence.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence


class BudgetError(Exception):
    """Raised on structurally invalid budget configuration."""


class StopReason(str, Enum):
    """Why an autonomous run ended. Note what is absent: no AGENT_SAID_DONE."""

    RUNNING = "running"
    GATES_PASSED = "gates_passed"
    LIMIT_CONTINUATIONS = "limit_continuations"
    LIMIT_TURNS = "limit_turns"
    LIMIT_TOKENS = "limit_tokens"
    LIMIT_WALL_CLOCK = "limit_wall_clock"
    GATE_RETRIES_EXHAUSTED = "gate_retries_exhausted"


class ContinueReason(str, Enum):
    """Why a run was told to keep going."""

    MISSING_TERMINAL_EVIDENCE = "missing_terminal_evidence"
    GATE_FAILED = "gate_failed"
    WORK_IN_PROGRESS = "work_in_progress"


#: Defaults are deliberately small. An autonomy budget that is generous by default
#: is a budget nobody tunes, and the first runaway run is discovered by its bill.
#: Callers running a long job must raise these explicitly -- an explicit act that
#: shows up in code review.
DEFAULT_MAX_CONTINUATIONS = 3
DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_TOKENS = 80_000
DEFAULT_TIMEOUT_SECONDS = 30 * 60
DEFAULT_GATE_MAX_RETRIES = 3
DEFAULT_GATE_TIMEOUT_SECONDS = 5 * 60


@dataclass
class GateAttempt:
    """One execution of one quality-gate command. This IS the evidence."""

    command: str
    attempt: int
    exit_code: int
    output: str
    duration_s: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorktreeSnapshot:
    """Repository state captured at gate failure, so a failure is reproducible.

    Ported in spirit from prime-agent's GitWorktreeSnapshot (autonomous.ts:93-97).
    `untracked_hash` fingerprints untracked filenames so a failure caused by a file
    that exists only in the working tree is still attributable.
    """

    status: str = ""
    diff: str = ""
    untracked_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AutonomyBudget:
    """Declared limits for one autonomous run. All limits are hard."""

    max_continuations: int = DEFAULT_MAX_CONTINUATIONS
    max_turns: int = DEFAULT_MAX_TURNS
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    # Accepts any sequence; normalized to a tuple in __post_init__ so the stored
    # config is immutable (a caller mutating a list it passed in must not silently
    # change the budget of a run already in flight).
    gate_commands: Sequence[str] = ()
    gate_max_retries: int = DEFAULT_GATE_MAX_RETRIES
    gate_timeout_seconds: float = DEFAULT_GATE_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        for name in ("max_continuations", "max_turns", "max_tokens", "gate_max_retries"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise BudgetError(f"{name} must be a non-negative int, got {value!r}")
        for name in ("timeout_seconds", "gate_timeout_seconds"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or value <= 0:
                raise BudgetError(f"{name} must be a positive number, got {value!r}")
        self.gate_commands = tuple(self.gate_commands)


@dataclass
class AutonomyDecision:
    """The verdict of one decision point."""

    should_continue: bool
    stop_reason: StopReason = StopReason.RUNNING
    continue_reason: ContinueReason | None = None
    escalate: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_continue": self.should_continue,
            "stop_reason": self.stop_reason.value,
            "continue_reason": self.continue_reason.value if self.continue_reason else None,
            "escalate": self.escalate,
            "detail": self.detail,
        }


@dataclass
class AutonomyState:
    """Mutable accounting for one run."""

    continuations_used: int = 0
    turns_used: int = 0
    tokens_used: int = 0
    started_at: float = field(default_factory=time.monotonic)
    gate_attempts: dict[str, int] = field(default_factory=dict)
    last_gate_failure: GateAttempt | None = None
    last_gate_snapshot: WorktreeSnapshot | None = None

    def elapsed_s(self, now: float | None = None) -> float:
        return (now if now is not None else time.monotonic()) - self.started_at


def _run_command(command: str, cwd: str, timeout_s: float) -> tuple[int, str, float]:
    """Execute one gate command, returning (exit_code, combined_output, duration).

    A timeout is a FAILURE, not an exception: a gate that hangs has not passed, and
    the run must be told to continue or escalate rather than crash. Exit code 124
    matches GNU coreutils `timeout` so downstream tooling reads it correctly.
    """
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output, time.monotonic() - start
    except subprocess.TimeoutExpired:
        return 124, f"gate command timed out after {timeout_s}s", time.monotonic() - start
    except OSError as exc:
        return 127, f"gate command could not be executed: {exc}", time.monotonic() - start


def capture_worktree_snapshot(cwd: str, runner: Callable[..., Any] | None = None) -> WorktreeSnapshot:
    """Capture git status/diff plus a hash of untracked paths. Never raises.

    A snapshot is best-effort evidence: if git is unavailable the run must not die,
    it must simply record less. Failing loudly here would convert a diagnostic aid
    into a new failure mode.
    """
    run = runner or subprocess.run

    def _capture(args: list[str]) -> str:
        try:
            proc = run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
            return (getattr(proc, "stdout", "") or "").strip()
        except Exception:
            return ""

    status = _capture(["git", "status", "--porcelain"])
    diff = _capture(["git", "diff"])
    untracked = _capture(["git", "ls-files", "--others", "--exclude-standard"])
    untracked_hash = hashlib.sha256(untracked.encode("utf-8")).hexdigest()[:16] if untracked else ""
    return WorktreeSnapshot(status=status, diff=diff, untracked_hash=untracked_hash)


def run_gates(
    budget: AutonomyBudget,
    state: AutonomyState,
    cwd: str = ".",
    *,
    command_runner: Callable[[str, str, float], tuple[int, str, float]] | None = None,
) -> tuple[bool, list[GateAttempt]]:
    """Run every configured gate command. Returns (all_passed, attempts).

    Gates run in declaration order and stop at the first failure: a later gate's
    result is meaningless once an earlier one failed, and running it wastes the
    budget the caller is trying to conserve.

    A run with NO configured gates returns False. This is deliberate and is the
    module's second safety property: without a gate there is no evidence of
    completion, so the run can only ever end by exhausting a limit. Returning True
    here would silently restore exactly the self-declared completion this module
    exists to forbid.
    """
    runner = command_runner or _run_command
    if not budget.gate_commands:
        return False, []

    attempts: list[GateAttempt] = []
    for command in budget.gate_commands:
        state.gate_attempts[command] = state.gate_attempts.get(command, 0) + 1
        attempt_no = state.gate_attempts[command]
        exit_code, output, duration = runner(command, cwd, budget.gate_timeout_seconds)
        attempt = GateAttempt(
            command=command,
            attempt=attempt_no,
            exit_code=exit_code,
            output=output[-6000:],  # tail: the failure is at the end, and context is finite
            duration_s=duration,
            passed=exit_code == 0,
        )
        attempts.append(attempt)
        if not attempt.passed:
            state.last_gate_failure = attempt
            return False, attempts
    return True, attempts


def decide(
    budget: AutonomyBudget,
    state: AutonomyState,
    *,
    agent_claims_done: bool = False,
    gates_passed: bool | None = None,
    now: float | None = None,
) -> AutonomyDecision:
    """Decide whether the run continues. THE core invariant lives here.

    Order of evaluation matters and is itself a policy:

      1. HARD LIMITS FIRST. A spent budget stops the run even if gates would have
         passed on the next turn -- the budget is the outer contract.
      2. GATES SECOND. Passing gates is the only evidence-based completion.
      3. AGENT CLAIM LAST, and never sufficient. When the agent says done but gates
         have not passed, we continue with MISSING_TERMINAL_EVIDENCE.

    `gates_passed=None` means "not evaluated this turn" and is treated as not-passed:
    absence of evidence is not evidence.
    """
    if state.continuations_used >= budget.max_continuations:
        return AutonomyDecision(
            False, StopReason.LIMIT_CONTINUATIONS, escalate=True,
            detail=f"continuations {state.continuations_used}/{budget.max_continuations} exhausted",
        )
    if state.turns_used >= budget.max_turns:
        return AutonomyDecision(
            False, StopReason.LIMIT_TURNS, escalate=True,
            detail=f"turns {state.turns_used}/{budget.max_turns} exhausted",
        )
    if state.tokens_used >= budget.max_tokens:
        return AutonomyDecision(
            False, StopReason.LIMIT_TOKENS, escalate=True,
            detail=f"tokens {state.tokens_used}/{budget.max_tokens} exhausted",
        )
    elapsed = state.elapsed_s(now)
    if elapsed >= budget.timeout_seconds:
        return AutonomyDecision(
            False, StopReason.LIMIT_WALL_CLOCK, escalate=True,
            detail=f"elapsed {elapsed:.1f}s >= timeout {budget.timeout_seconds}s",
        )

    if gates_passed:
        return AutonomyDecision(
            False, StopReason.GATES_PASSED, escalate=False,
            detail="all configured quality gates exited 0",
        )

    exhausted = [
        cmd for cmd, count in state.gate_attempts.items()
        if count >= budget.gate_max_retries and (
            state.last_gate_failure is not None and state.last_gate_failure.command == cmd
        )
    ]
    if exhausted:
        return AutonomyDecision(
            False, StopReason.GATE_RETRIES_EXHAUSTED, escalate=True,
            detail=f"gate {exhausted[0]!r} failed {budget.gate_max_retries} times; escalating with evidence",
        )

    if agent_claims_done:
        # THE invariant. The agent's word is input, never authority.
        return AutonomyDecision(
            True, StopReason.RUNNING,
            continue_reason=ContinueReason.MISSING_TERMINAL_EVIDENCE,
            detail="agent reported completion but no gate has verified it; continuing",
        )
    if state.last_gate_failure is not None:
        return AutonomyDecision(
            True, StopReason.RUNNING,
            continue_reason=ContinueReason.GATE_FAILED,
            detail=f"gate {state.last_gate_failure.command!r} exited {state.last_gate_failure.exit_code}",
        )
    return AutonomyDecision(
        True, StopReason.RUNNING,
        continue_reason=ContinueReason.WORK_IN_PROGRESS,
        detail="budget remains and no terminal evidence yet",
    )


#: Continuation text handed to an agent that tried to stop without evidence.
#: Kept beside the state machine on purpose: the prompt is a courtesy that explains
#: the rule, while `decide()` is what actually enforces it. If the two ever
#: disagree, `decide()` wins.
CONTINUATION_PROMPT = (
    "No human input is available in autonomous mode. Continue working until a "
    "configured quality gate passes or a declared budget limit is reached. Do not "
    "end the run on your own assessment that the task is complete -- completion is "
    "decided by the gates, not by your report. If you believe you are blocked, "
    "prove it with host-observable evidence (a command, its exit code, and its "
    "output), preserve that evidence, and keep looking for safe progress while "
    "budget remains."
)


def record_turn(state: AutonomyState, *, tokens: int = 0) -> AutonomyState:
    """Account one turn. Callers must call this once per model turn."""
    state.turns_used += 1
    state.tokens_used += max(0, int(tokens))
    return state


def record_continuation(state: AutonomyState) -> AutonomyState:
    """Account one continuation (one 'keep going' after the agent tried to stop)."""
    state.continuations_used += 1
    return state
