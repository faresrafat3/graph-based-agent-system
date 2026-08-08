# version: v1 | 2026-08-08 | verdict: pending-review
"""Tool-result-safe compaction cut point.

PORTED-FROM: prime-agent `packages/coding-agent/src/core/compaction/compaction.ts`
  - `findValidCutPoints`  :310-347
  - `findTurnStartIndex`  :354-369
  - `findCutPoint`        :402-458
MIT, Mario Zechner 2025 + Prime Intellect 2026.

This lands BEFORE we have a compactor, deliberately. The single property it guarantees
is a correctness property, not a tuning choice:

    A CUT MUST NEVER LAND ON A TOOL RESULT.

A tool result separated from the tool call that produced it is an invalid history, and
most providers reject it outright. The naive "drop the oldest N messages" compactor
violates this on the first tool-heavy conversation it meets.

Two design points that a from-scratch implementation reliably gets wrong:

1. Cutting at an ASSISTANT message is allowed. Its tool results come after it and are
   kept, so the history stays valid. Restricting cuts to user messages only is safe but
   wastes budget.
2. When the cut lands mid-turn, this does NOT rewind the cut to the turn start. It keeps
   the cut and FLAGS the split (`is_split_turn` + `turn_start_index`), so a caller can
   summarise the split turn's prefix separately from older history. Rewinding would
   silently discard recent context the budget was meant to keep.

Zero-LLM and pure (Law 14): same entries in, same cut out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Message roles that may legally start a turn (compaction.ts:361-367).
TURN_STARTING_ROLES: frozenset[str] = frozenset({"user", "bashExecution"})

# Roles that are valid cut points (compaction.ts:316-327). `toolResult` is
# EXCLUDED by construction — it must always follow its tool call.
VALID_CUT_ROLES: frozenset[str] = frozenset({
    "user",
    "assistant",
    "bashExecution",
    "custom",
    "branchSummary",
    "compactionSummary",
})

# Non-message entry types that are themselves valid cut points (compaction.ts:343-345).
CUT_POINT_ENTRY_TYPES: frozenset[str] = frozenset({"branch_summary", "custom_message"})

Role = Literal[
    "user", "assistant", "toolResult", "bashExecution",
    "custom", "branchSummary", "compactionSummary",
]


@dataclass(frozen=True)
class Entry:
    """One session entry. `tokens` is a pre-computed estimate for the message body."""

    type: str
    role: str | None = None
    tokens: int = 0
    id: str | None = None


@dataclass(frozen=True)
class CutPointResult:
    """Where to cut, and whether that cut splits a turn (compaction.ts:371-378)."""

    first_kept_entry_index: int
    turn_start_index: int
    is_split_turn: bool


def find_valid_cut_points(entries: list[Entry], start_index: int, end_index: int) -> list[int]:
    """Indices where a cut is legal. Never a tool result (compaction.ts:310-347).

    Range is half-open: [start_index, end_index).
    """
    cut_points: list[int] = []
    for i in range(start_index, end_index):
        entry = entries[i]
        if entry.type == "message":
            if entry.role in VALID_CUT_ROLES:
                cut_points.append(i)
            # `toolResult` intentionally falls through: it must follow its tool call.
        elif entry.type in CUT_POINT_ENTRY_TYPES:
            cut_points.append(i)
    return cut_points


def find_turn_start_index(entries: list[Entry], entry_index: int, start_index: int) -> int:
    """Index of the message starting the turn containing `entry_index`, else -1.

    Scans backwards. `bashExecution` counts as a turn start because it is
    user-initiated context (compaction.ts:354-369).
    """
    for i in range(entry_index, start_index - 1, -1):
        entry = entries[i]
        if entry.type in CUT_POINT_ENTRY_TYPES:
            return i
        if entry.type == "message" and entry.role in TURN_STARTING_ROLES:
            return i
    return -1


def _is_tool_result(entries: list[Entry], index: int) -> bool:
    """True when `index` addresses a tool-result message."""
    if not (0 <= index < len(entries)):
        return False
    entry = entries[index]
    return entry.type == "message" and entry.role == "toolResult"


def find_cut_point(
    entries: list[Entry],
    start_index: int,
    end_index: int,
    keep_recent_tokens: int,
) -> CutPointResult:
    """Find the cut that keeps approximately `keep_recent_tokens` of recent history.

    Mirrors compaction.ts:402-458 step for step:
      1. Collect valid cut points; if none, keep everything from `start_index`.
      2. Walk backwards accumulating token estimates until the budget is exceeded.
      3. Snap to the closest valid cut point AT OR AFTER that entry — "at or after"
         is what moves the cut off a tool result rather than onto it.
      4. Rewind over non-message entries (model/settings changes) so they travel with
         the block they configure, stopping at any message or compaction boundary.
      5. If the cut is not a user message, flag the split turn.
    """
    cut_points = find_valid_cut_points(entries, start_index, end_index)
    if not cut_points:
        # DIVERGENCE FROM UPSTREAM (compaction.ts:414), deliberate and tested.
        #
        # Upstream returns `startIndex` here unconditionally. If the entry at
        # `startIndex` is a toolResult, that return value violates the module's own
        # central invariant and emits an orphaned tool result. Upstream never trips
        # this because its sessions always open with a user message — an invariant
        # asserted nowhere in the code, and one our graph histories do not share
        # (a compacted or replayed segment can legitimately begin with a toolResult).
        #
        # With no legal cut point, the only safe answer is "cut nothing".
        if _is_tool_result(entries, start_index):
            return CutPointResult(first_kept_entry_index=end_index,
                                  turn_start_index=-1, is_split_turn=False)
        return CutPointResult(first_kept_entry_index=start_index,
                              turn_start_index=-1, is_split_turn=False)

    accumulated = 0
    cut_index = cut_points[0]

    for i in range(end_index - 1, start_index - 1, -1):
        entry = entries[i]
        if entry.type != "message":
            continue
        accumulated += entry.tokens
        if accumulated >= keep_recent_tokens:
            for c in cut_points:
                if c >= i:
                    cut_index = c
                    break
            break

    # Non-message entries preceding the cut belong with the kept block: a model or
    # settings change applies to the messages that follow it.
    while cut_index > start_index:
        prev = entries[cut_index - 1]
        if prev.type == "compaction" or prev.type == "message":
            break
        cut_index -= 1

    cut_entry = entries[cut_index]
    is_user_message = cut_entry.type == "message" and cut_entry.role == "user"
    turn_start_index = -1 if is_user_message else find_turn_start_index(
        entries, cut_index, start_index
    )

    return CutPointResult(
        first_kept_entry_index=cut_index,
        turn_start_index=turn_start_index,
        is_split_turn=(not is_user_message) and turn_start_index != -1,
    )
