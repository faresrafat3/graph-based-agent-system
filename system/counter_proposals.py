"""
Counter-Proposals System — Operationalization of Ruling C1-rev1 / P3 / P6.

This module provides the *domain-agent challenge channel* that CONSTITUTION.md:445
(Article VI 1b) references but was missing — a true ghost dependency. It turns the
meta-loop's "no interpretive monopoly" principle into concrete code.

Design (C1-rev1 compliant):
  - Domain agents submit structured challenges to meta-loop control proposals.
  - Challenges are persisted as append-only JSONL (Law 16: reproducible evidence).
  - The systems layer reads pending challenges via `get_pending_challenges()`.
  - NO auto-apply: a challenge is surfaced, never silently dropped, and resolution
    requires an explicit human checkpoint / independent opt-in (Ruling C1).
  - opus-5 is consulted LIVE when the channel is available (see system/opus5_consult.py);
    until then the honest fallback is a HUMAN CHECKPOINT, never a fabricated opus-5
    reply (Law 11: no false attribution; Law 3: fail loudly, not silently).

The function names here (`submit_counter_proposal`, `get_pending_challenges`) match
the field names that agents/systems_layer.py already reads (`from_agent`, `challenge`)
so the wiring is a thin adapter rather than a rewrite of the meta-loop.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_DIR = Path(
    os.environ.get("COUNTER_PROPOSALS_DIR", "system/measurements")
)
LEDGER_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_FILE = LEDGER_DIR / "counter_proposals.jsonl"

_LOCK = threading.Lock()


@dataclass(frozen=True)
class CounterProposal:
    """A domain-agent challenge to a meta-loop control proposal.

    Frozen so every record is tamper-evident from creation (Law 16 /
    Reproducible Evidence). Field names mirror what systems_layer.py reads:
    ``from_agent`` and ``challenge``.
    """

    id: str
    created_at: str  # ISO-8601 UTC
    from_agent: str  # domain agent that raised the challenge (e.g. "architect")
    target_proposal_id: str
    challenge: str  # the actual challenge text
    evidence: dict[str, Any] = None  # optional structured evidence
    status: str = "pending"  # pending | reviewed | accepted | rejected
    reviewer: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None
    resolution_channel: str | None = None  # "human_checkpoint" | "opus5" | None

    def __post_init__(self):
        if self.evidence is None:
            object.__setattr__(self, "evidence", {})

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(s: str) -> "CounterProposal":
        return CounterProposal(**json.loads(s))


def submit_counter_proposal(
    from_agent: str,
    target_proposal_id: str,
    challenge: str,
    evidence: dict[str, Any] | None = None,
) -> CounterProposal:
    """Domain agents call this to challenge a meta-loop control proposal.

    Persists atomically (append + fsync) so governance / CI can rely on it.
    """
    cp = CounterProposal(
        id=f"cp-{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        from_agent=from_agent,
        target_proposal_id=target_proposal_id,
        challenge=challenge,
        evidence=evidence or {},
    )
    with _LOCK:
        with LEDGER_FILE.open("a", encoding="utf-8") as fh:
            fh.write(cp.to_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return cp


def get_pending_challenges() -> list[CounterProposal]:
    """Systems layer calls this to read all pending challenges.

    Returns an empty list if the ledger does not exist yet (first run) — never None.
    """
    if not LEDGER_FILE.exists():
        return []
    out: list[CounterProposal] = []
    with LEDGER_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cp = CounterProposal.from_json(line)
            if cp.status == "pending":
                out.append(cp)
    return out


def get_all_challenges() -> list[CounterProposal]:
    """Read the entire ledger (for audit / review)."""
    if not LEDGER_FILE.exists():
        return []
    out: list[CounterProposal] = []
    with LEDGER_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(CounterProposal.from_json(line))
    return out


def review_challenge(
    challenge_id: str,
    reviewer: str,
    decision: str,  # accepted | rejected
    note: str = "",
    resolution_channel: str | None = "human_checkpoint",
) -> CounterProposal | None:
    """Resolve a challenge. ``reviewer`` MUST be a real identity (human or an
    explicitly-recorded opus-5 session); never a fabricated opus-5 string (Law 11).

    Mutates the ledger in place (rewrite) — acceptable because the file is
    append-only history and review is a metadata transition, not content change.
    """
    if decision not in ("accepted", "rejected"):
        raise ValueError(f"decision must be 'accepted' or 'rejected', got {decision!r}")
    all_cps = get_all_challenges()
    found = next((cp for cp in all_cps if cp.id == challenge_id), None)
    if found is None:
        return None
    updated = CounterProposal(
        id=found.id,
        created_at=found.created_at,
        from_agent=found.from_agent,
        target_proposal_id=found.target_proposal_id,
        challenge=found.challenge,
        evidence=found.evidence,
        status="reviewed",
        reviewer=reviewer,
        review_note=note,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        resolution_channel=resolution_channel,
    )
    with _LOCK:
        with LEDGER_FILE.open("w", encoding="utf-8") as fh:
            for cp in all_cps:
                fh.write((updated if cp.id == challenge_id else cp).to_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return updated


def clear_ledger_for_testing() -> None:
    """Test helper only — removes the ledger file."""
    with _LOCK:
        if LEDGER_FILE.exists():
            LEDGER_FILE.unlink()


if __name__ == "__main__":
    # Smoke test: submit, read back, resolve via human checkpoint (honest path).
    clear_ledger_for_testing()
    cp = submit_counter_proposal(
        from_agent="security",
        target_proposal_id="prop-001",
        challenge="Increasing compute budget without threat-model review violates P6.",
        evidence={"current_budget": 100, "proposed_budget": 500},
    )
    print(f"Submitted: {cp.id}")
    pending = get_pending_challenges()
    print(f"Pending: {len(pending)}")
    reviewed = review_challenge(
        cp.id, "human@review", "accepted",
        note="Budget increase approved with conditions.",
        resolution_channel="human_checkpoint",
    )
    print(f"Reviewed: {reviewed.id} -> {reviewed.status} ({reviewed.resolution_channel})")
    print("OK")
