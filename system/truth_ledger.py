"""Truth ledger: one measured source for every contested number.

Why this exists
---------------
A scan of this repo's 88 markdown files found **15 different values** asserted for
"how many agents" and **5** for "how many tests". Nothing was lying; each number was
true when written and never retired. A model reading those docs cannot tell which is
current, so it picks one -- effectively at random.

That is a context defect, not a documentation defect: wrong information reaching the
model is worse than less information.

The rule enforced here: a number that cannot be re-derived by running a command is
not a fact, it is a rumour. Every claim therefore carries the command that produced
it, and a contradiction is surfaced loudly instead of being averaged away.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


class UnmeasuredClaimError(ValueError):
    """Raised when a claim has no reproducing command, or an uncomparable value."""


@dataclass(frozen=True)
class Claim:
    key: str
    value: int | float | str
    command: str

    def validate(self) -> None:
        if not self.key:
            raise UnmeasuredClaimError("claim needs a key")
        if not str(self.command).strip():
            raise UnmeasuredClaimError(
                f"claim {self.key!r} has no measuring command: a number that cannot be "
                "re-derived is a rumour, not a fact"
            )
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float, str)):
            raise UnmeasuredClaimError(
                f"claim {self.key!r} must hold a comparable scalar, got {type(self.value).__name__}"
            )


class TruthLedger:
    """Append-only store of measured claims, one JSON object per line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -- writing ---------------------------------------------------------
    def record(self, claim: Claim) -> None:
        claim.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {"key": claim.key, "value": claim.value, "command": claim.command}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # -- reading ---------------------------------------------------------
    def _rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def history(self, key: str) -> list[Claim]:
        """Every value ever recorded for ``key``, oldest first. Nothing is dropped."""
        return [
            Claim(r["key"], r["value"], r["command"]) for r in self._rows() if r["key"] == key
        ]

    def get(self, key: str) -> Claim | None:
        """The most recent measurement, or ``None`` if never measured."""
        hist = self.history(key)
        return hist[-1] if hist else None

    def contradictions(self) -> list[str]:
        """Keys recorded with more than one distinct value -- surfaced, never averaged."""
        seen: dict[str, set] = {}
        for r in self._rows():
            seen.setdefault(r["key"], set()).add(r["value"])
        return sorted(k for k, v in seen.items() if len(v) > 1)

    # -- auditing prose --------------------------------------------------
    def verify_text(self, text: str, key: str, subject: str | None = None) -> list[int]:
        """Return numbers in ``text`` that contradict the measured value of ``key``.

        A number only counts as a contradiction when it is asserted about the SAME
        subject. "8 inert agents" and "7 agents call a model" are both true and are
        not in conflict, so a bare "<n> agents" match is not sufficient evidence.

        Args:
            text: prose to audit.
            key: ledger key holding the measured truth.
            subject: the exact noun phrase the claim is about. Defaults to the key
                with underscores/"_count" stripped. Qualified counts (an adjective
                sitting between the number and the subject, e.g. "8 inert agents")
                are deliberately ignored -- they are a different claim.
        """
        claim = self.get(key)
        if claim is None:
            return []
        try:
            truth = int(claim.value)
        except (TypeError, ValueError):
            return []

        subject = subject or key.replace("_count", "").replace("_", " ")
        # \s+ only -- an intervening word means it is a qualified, different claim.
        pattern = rf"(\d+)\s+{re.escape(subject)}s?\b"
        found = [int(m.group(1)) for m in re.finditer(pattern, text, re.IGNORECASE)]
        return [n for n in found if n != truth]
