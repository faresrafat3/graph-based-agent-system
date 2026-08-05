# version: v1 | 2026-08-05 | verdict: pending-review
"""P4 — Bounded Probing enforcement (Constitution Article VI, extends existing infra).

Fares's Intelligence Forge plan (Task 1): extend, do NOT fork. This module enforces P4
("Complex work runs N attempts, each stating a NEW falsifiable hypothesis; a repeated
hypothesis or exhausted budget escalates to a human") by reusing the existing
`debugger_agent.extract_hypothesis` (zero-LLM, auditable) rather than reinventing it.

The constraint is ARCHITECTURAL (a verified, replayable decision), not a prompt wrapper.
"""

from agents.debugger_agent import extract_hypothesis


class ProbeBudget:
    """Tracks a bounded probing session: N attempts, each a NEW falsifiable hypothesis.

    Reuses extract_hypothesis so two rephrasings of the same theory map to one canonical key
    (fixing the false-negative opus-5 flagged). On repeat OR budget-exhaust, the session is
    CLOSED and must escalate (per P4) — no unbounded exploration.
    """

    def __init__(self, max_attempts: int = 4):
        self.max_attempts = max_attempts
        self._seen: list[str] = []          # canonical hypothesis keys, in order
        self.escalated: bool = False
        self.escalation_reason: str | None = None

    def record(self, reflection: str) -> dict:
        """Record one attempt. Returns a decision dict (continue / escalate)."""
        if self.escalated:
            return self._decision("blocked", "already escalated")
        if len(self._seen) >= self.max_attempts:
            self.escalated = True
            self.escalation_reason = "budget_exhausted"
            return self._decision("escalate", "budget_exhausted")

        key = extract_hypothesis(reflection)
        if not key:
            # no falsifiable hypothesis stated -> counts as a defective attempt
            self._seen.append(f"<none:{len(self._seen)}>")
            if len(self._seen) >= self.max_attempts:
                self.escalated = True
                self.escalation_reason = "budget_exhausted"
                return self._decision("escalate", "budget_exhausted")
            return self._decision("continue", "no_falsifiable_hypothesis")

        if key in self._seen:
            self.escalated = True
            self.escalation_reason = "repeated_hypothesis"
            return self._decision("escalate", f"repeated_hypothesis:{key}")

        self._seen.append(key)
        if len(self._seen) >= self.max_attempts:
            self.escalated = True
            self.escalation_reason = "budget_exhausted"
            return self._decision("escalate", "budget_exhausted")
        return self._decision("continue", f"new_hypothesis:{key}")

    def _decision(self, action: str, reason: str) -> dict:
        return {
            "action": action,            # continue | escalate | blocked
            "reason": reason,
            "attempts": len(self._seen),
            "max_attempts": self.max_attempts,
            "escalated": self.escalated,
            "seen": list(self._seen),
        }

    def hypothesis_trail(self) -> list[str]:
        """The auditable trail for escalation (P4: attach to human handoff)."""
        return list(self._seen)


def enforce_bounded_probe(reflections: list[str], max_attempts: int = 4) -> dict:
    """Run a full bounded-probing session over a list of reflections.

    Returns the final decision + trail. Deterministic, zero-LLM (P2-aligned).
    """
    budget = ProbeBudget(max_attempts=max_attempts)
    last = None
    for r in reflections:
        last = budget.record(r)
        if last["action"] == "escalate":
            break
    return {
        "decision": last,
        "trail": budget.hypothesis_trail(),
        "escalated": budget.escalated,
        "reason": budget.escalation_reason,
    }
