# version: v4 | 2026-08-05 | verdict: pending-review
"""Distillation ledger — provenance for opus-5-sourced principles (Task D, G4, C5).

Ruling C5 (CONSTITUTION Article VI 1b): every principle attributed to opus-5 MUST have a
ledger entry (source, date, frozen text, status). A principle without a ledger entry is
*advisory only*, never enforced. This makes "distilled" mean *ledger-recorded*, not
*merely written by a human who read opus-5's output*.

The ledger is append-only JSONL (one row per record/transition). Status flows:
    proposed -> distilled -> enforced   (or back to proposed if contested)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


class LedgerError(Exception):
    """Raised when a principle is recorded without required provenance."""


@dataclass(frozen=True)
class PrincipleEntry:
    ref: str
    text: str
    source: str
    status: str
    date: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DistillationLedger:
    """Append-only ledger of opus-5-derived principles with provenance."""

    VALID_STATUS = {"proposed", "distilled", "enforced"}

    def __init__(self, path: str = "system/distillation_ledger.jsonl"):
        self.path = Path(path)
        self._entries: dict[str, PrincipleEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            e = PrincipleEntry(**{k: d.get(k, "") for k in ("ref", "text", "source", "status", "date")})
            self._entries[e.ref] = e  # latest wins

    def record(self, ref: str, text: str, source: str, status: str, date: str = "") -> PrincipleEntry:
        if not source or not source.strip():
            raise LedgerError(f"principle {ref} has no source — C5 requires provenance")
        if status not in self.VALID_STATUS:
            raise LedgerError(f"invalid status {status!r} for {ref}")
        entry = PrincipleEntry(ref=ref, text=text, source=source, status=status, date=date)
        self._entries[ref] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
        return entry

    def status_of(self, ref: str) -> str | None:
        entry = self._entries.get(ref)
        return entry.status if entry is not None else None

    def is_enforced(self, ref: str) -> bool:
        entry = self._entries.get(ref)
        return entry is not None and entry.status == "enforced"

    def all(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self._entries.values()]


def attach_opus5_review(ledger: "DistillationLedger", ruling_id: str,
                        ruling_text: str) -> dict[str, Any]:
    """Consult opus-5 LIVE and append its review to the ledger as independent provenance.

    This is the real 'opus-5 participates' channel (Fares's requirement), not a frozen text.
    The review is advisory + recorded; it never auto-edits the ruling.
    """
    from system.opus5_consult import review_ruling
    review = review_ruling(ruling_id, ruling_text)
    # Append the opus-5 review to the ledger file as a provenance line.
    provenance = {
        "type": "opus5_review",
        "ruling_id": ruling_id,
        "channel": review.get("channel", "unknown"),
        "reply": review.get("opus5_reply", ""),
    }
    ledger.path.parent.mkdir(parents=True, exist_ok=True)
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(provenance, ensure_ascii=False) + "\n")
    return provenance
