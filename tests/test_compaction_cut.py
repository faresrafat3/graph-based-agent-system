# version: v1 | 2026-08-08 | verdict: pending-review
"""Tests for system/compaction_cut.py (M3).

Ported behaviour: prime-agent `packages/coding-agent/src/core/compaction/compaction.ts`
`findValidCutPoints` (:310-347), `findTurnStartIndex` (:354-369), `findCutPoint` (:402-458).

The invariant that matters most: A CUT MUST NEVER LAND ON A TOOL RESULT. An orphaned
tool result is rejected by most providers, so this is a correctness property, not a
preference. `test_never_cuts_at_a_tool_result_property` asserts it exhaustively over
generated histories rather than on hand-picked examples.
"""

from __future__ import annotations

import itertools

import pytest

from system.compaction_cut import (
    Entry,
    Role,
    find_cut_point,
    find_turn_start_index,
    find_valid_cut_points,
)


def msg(role: Role, tokens: int = 10, eid: str | None = None) -> Entry:
    return Entry(type="message", role=role, tokens=tokens, id=eid)


def non_msg(kind: str) -> Entry:
    return Entry(type=kind, role=None, tokens=0)


# --- findValidCutPoints (compaction.ts:310-347) ---------------------------


def test_tool_results_are_never_valid_cut_points():
    """compaction.ts:326-327 — the toolResult case falls through without pushing."""
    entries = [msg("user"), msg("assistant"), msg("toolResult"), msg("assistant")]
    assert find_valid_cut_points(entries, 0, len(entries)) == [0, 1, 3]


def test_assistant_messages_are_valid_cut_points():
    """Deliberate: an assistant's tool results follow it and are kept (:305-307)."""
    assert 1 in find_valid_cut_points([msg("user"), msg("assistant")], 0, 2)


@pytest.mark.parametrize("role", ["user", "assistant", "bashExecution", "custom",
                                  "branchSummary", "compactionSummary"])
def test_all_six_valid_roles(role):
    assert find_valid_cut_points([msg(role)], 0, 1) == [0]


def test_structural_entries_are_not_cut_points():
    """thinking_level_change / model_change / compaction / label / session_info."""
    entries = [non_msg("model_change"), non_msg("compaction"), non_msg("label")]
    assert find_valid_cut_points(entries, 0, len(entries)) == []


def test_branch_summary_and_custom_message_entry_types_are_cut_points():
    """compaction.ts:343-345 — pushed by the post-switch check, not the switch."""
    entries = [non_msg("branch_summary"), non_msg("custom_message")]
    assert find_valid_cut_points(entries, 0, len(entries)) == [0, 1]


def test_range_is_half_open():
    entries = [msg("user"), msg("user"), msg("user")]
    assert find_valid_cut_points(entries, 1, 2) == [1]


# --- findTurnStartIndex (compaction.ts:354-369) ---------------------------


def test_turn_start_finds_nearest_user_scanning_backwards():
    entries = [msg("user"), msg("assistant"), msg("toolResult"), msg("assistant")]
    assert find_turn_start_index(entries, 3, 0) == 0


def test_turn_start_treats_bash_execution_as_a_turn_start():
    """:365 — bashExecution is user-initiated context."""
    entries = [msg("user"), msg("bashExecution"), msg("assistant")]
    assert find_turn_start_index(entries, 2, 0) == 1


def test_turn_start_returns_minus_one_when_none_found():
    assert find_turn_start_index([msg("assistant"), msg("toolResult")], 1, 0) == -1


def test_turn_start_respects_start_index_floor():
    entries = [msg("user"), msg("assistant"), msg("assistant")]
    assert find_turn_start_index(entries, 2, 1) == -1


# --- findCutPoint (compaction.ts:402-458) --------------------------------


def test_no_valid_cut_points_returns_start_index_and_no_split():
    entries = [non_msg("model_change")]
    r = find_cut_point(entries, 0, 1, keep_recent_tokens=5)
    assert (r.first_kept_entry_index, r.turn_start_index, r.is_split_turn) == (0, -1, False)


def test_divergence_no_cut_points_and_start_is_a_tool_result_cuts_nothing():
    """DELIBERATE DIVERGENCE from compaction.ts:414 — see the comment in find_cut_point.

    Upstream returns `startIndex` unconditionally here, which hands back a toolResult
    and violates the module's own invariant. It never trips upstream because sessions
    always open with a user message; our histories carry no such guarantee. With no
    legal cut point, cutting nothing is the only safe answer.
    """
    entries = [msg("toolResult", 10), msg("toolResult", 10)]
    r = find_cut_point(entries, 0, 2, keep_recent_tokens=5)
    assert r.first_kept_entry_index == len(entries), "must keep everything, cutting nothing"
    assert r.is_split_turn is False
    assert r.turn_start_index == -1


def test_budget_never_exceeded_keeps_everything_from_first_cut_point():
    """:419 default — cutIndex starts at cutPoints[0]."""
    entries = [msg("user", 1), msg("assistant", 1)]
    r = find_cut_point(entries, 0, 2, keep_recent_tokens=10_000)
    assert r.first_kept_entry_index == 0


def test_snaps_to_closest_cut_point_at_or_after_the_budget_entry():
    """:422-429 — 'at or after', so a toolResult at the budget edge moves the cut forward."""
    entries = [msg("user", 10), msg("assistant", 10), msg("toolResult", 100), msg("assistant", 10)]
    r = find_cut_point(entries, 0, 4, keep_recent_tokens=50)
    assert r.first_kept_entry_index == 3, "must not cut at the toolResult"


def test_cut_at_user_message_is_not_a_split_turn():
    """:450-452 — isUserMessage short-circuits the turn scan."""
    entries = [msg("user", 100), msg("user", 10)]
    r = find_cut_point(entries, 0, 2, keep_recent_tokens=5)
    assert r.is_split_turn is False
    assert r.turn_start_index == -1


def test_cut_at_assistant_message_is_a_split_turn_and_records_turn_start():
    entries = [msg("user", 10), msg("assistant", 10), msg("assistant", 100)]
    r = find_cut_point(entries, 0, 3, keep_recent_tokens=50)
    assert r.first_kept_entry_index == 2
    assert r.is_split_turn is True
    assert r.turn_start_index == 0


def test_non_message_entries_travel_with_the_kept_block():
    """:433-446 — rewind over non-message entries so settings apply to kept messages."""
    entries = [msg("user", 100), non_msg("model_change"), msg("user", 10)]
    r = find_cut_point(entries, 0, 3, keep_recent_tokens=5)
    assert r.first_kept_entry_index == 1, "model_change must be kept with the message it affects"


def test_rewind_stops_at_a_compaction_boundary():
    """:437-439 — never rewind across a previous compaction."""
    entries = [msg("user", 100), non_msg("compaction"), msg("user", 10)]
    r = find_cut_point(entries, 0, 3, keep_recent_tokens=5)
    assert r.first_kept_entry_index == 2


def test_split_turn_requires_both_non_user_and_a_found_turn_start():
    """:456 — isSplitTurn = !isUserMessage && turnStartIndex !== -1."""
    entries = [msg("assistant", 100), msg("assistant", 10)]
    r = find_cut_point(entries, 0, 2, keep_recent_tokens=5)
    assert r.turn_start_index == -1
    assert r.is_split_turn is False


# --- the property that makes this worth porting --------------------------


@pytest.mark.parametrize("roles", [
    combo for n in (3, 4)
    for combo in itertools.product(["user", "assistant", "toolResult"], repeat=n)
])
@pytest.mark.parametrize("budget", [1, 15, 45])
def test_never_cuts_at_a_tool_result_property(roles, budget):
    """Exhaustive over every 3- and 4-message history: the cut is never a toolResult.

    This is the whole reason M3 was ported. If it can fail on ANY history, the
    compactor can emit an orphaned tool result and the provider will reject it.
    """
    entries = [msg(r, 10) for r in roles]
    r = find_cut_point(entries, 0, len(entries), keep_recent_tokens=budget)
    if r.first_kept_entry_index >= len(entries):
        return  # "cut nothing" — vacuously safe, covered by the divergence test
    cut = entries[r.first_kept_entry_index]
    if cut.type == "message":
        assert cut.role != "toolResult", f"cut landed on toolResult in {roles} @ budget={budget}"


@pytest.mark.parametrize("roles", [
    combo for combo in itertools.product(["user", "assistant", "toolResult"], repeat=4)
])
def test_split_turn_start_is_always_a_turn_starting_role(roles):
    """When a split is reported, turn_start_index must point at a real turn start."""
    entries = [msg(r, 10) for r in roles]
    r = find_cut_point(entries, 0, len(entries), keep_recent_tokens=15)
    if r.is_split_turn:
        assert r.turn_start_index >= 0
        assert entries[r.turn_start_index].role in ("user", "bashExecution")
        assert r.turn_start_index <= r.first_kept_entry_index


def test_is_pure():
    entries = [msg("user", 10), msg("assistant", 100)]
    a = find_cut_point(entries, 0, 2, keep_recent_tokens=50)
    b = find_cut_point(entries, 0, 2, keep_recent_tokens=50)
    assert a == b
