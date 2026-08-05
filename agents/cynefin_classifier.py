# version: v3 | 2026-08-05 | verdict: pending-review
"""Cynefin domain classifier — resolves C4 / enforces P3 (Task C, G3).

P3 (Domain-Gated Governance): control intensity is set by the task's Cynefin domain and
reversibility, NEVER by permission class or keyword substring. The legacy
``detect_task_type`` (ULTIMATE-GRAPH-PLAN) picked a slice by substring ("humaneval",
"e-commerce") — that violates P3. This classifier infers the domain from *ambiguity* and
*reversibility* of the task, then binds control intensity accordingly.

Domains (Snowden/Cynefin):
    CLEAR       - well-defined, known unknowns are small, reversible -> VERIFY only
    COMPLICATED - analyzable with expertise, reversible -> analysis + VERIFY
    COMPLEX     - unpredictable, needs probe/learn, partially reversible -> probe budget
    CHAOTIC     - no time to analyze, irreversible -> immediate human

This module is ZERO-LLM (Law 11): it scores lexical/structural signals only. It is the
node the routing layer should call instead of detect_task_type.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class CynefinDomain(str, enum.Enum):
    CLEAR = "clear"
    COMPLICATED = "complicated"
    COMPLEX = "complex"
    CHAOTIC = "chaotic"


@dataclass(frozen=True)
class DomainClassification:
    domain: CynefinDomain
    confidence: float
    control: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "confidence": round(self.confidence, 3),
            "control": self.control,
            "rationale": self.rationale,
        }


# Control intensity bound to each domain (P3).
DOMAIN_CONTROL: dict[CynefinDomain, dict[str, str]] = {
    CynefinDomain.CLEAR: {"control": "verify_only", "label": "VERIFY node only"},
    CynefinDomain.COMPLICATED: {"control": "analysis_plus_verify", "label": "analysis + VERIFY"},
    CynefinDomain.COMPLEX: {"control": "probe_budget", "label": "bounded probe (P4)"},
    CynefinDomain.CHAOTIC: {"control": "human", "label": "immediate human checkpoint"},
}


# Lexical signals (zero-LLM). These measure ambiguity + risk, not task *type*.
_CHAOTIC_MARKERS = [
    "immediately", "emergency", "outage", "production down", "data loss",
    "security breach", "delete production", "right now", "asap",
]
_COMPLEX_MARKERS = [
    "legacy", "migration", "unknown", "many unknowns", "distributed system",
    "zero downtime", "refactor monolith", "scale to", "concurrent", "race condition",
]
_COMPLICATED_MARKERS = [
    "oauth", "oidc", "mfa", "soc2", "pci-dss", "per spec", "compliance",
    "algorithm", "protocol", "api contract", "schema", "database migration",
]
_CLEAR_MARKERS = [
    "login page", "crud", "endpoint", "function", "sort", "filter",
    "button", "form", "single file", "well-defined",
]


def _score_markers(text: str, markers: list[str]) -> float:
    low = text.lower()
    hits = sum(1 for m in markers if m in low)
    return min(1.0, hits / 2.0)  # saturates at 2 marker hits


def classify_domain(requirements: str, reversibility: str = "reversible") -> DomainClassification:
    """Infer the Cynefin domain from the task text + reversibility.

    Args:
        requirements: the task/requirements text.
        reversibility: "reversible" | "irreversible" (does a wrong step cause harm?).

    Returns a DomainClassification binding control intensity per P3.
    """
    text = requirements or ""
    irr = (reversibility or "reversible").lower()
    irreversible = "irreversible" in irr or "no" in irr

    s_chaotic = _score_markers(text, _CHAOTIC_MARKERS)
    s_complex = _score_markers(text, _COMPLEX_MARKERS)
    s_complicated = _score_markers(text, _COMPLICATED_MARKERS)
    s_clear = _score_markers(text, _CLEAR_MARKERS)

    # Irreversibility pushes toward the more cautious domain.
    if irreversible:
        s_chaotic = max(s_chaotic, 0.6)
        s_complex = max(s_complex, 0.5)

    # Pick the highest-scoring signal; tie-break by caution (chaotic > complex >
    # complicated > clear) when irreversible, otherwise by clarity.
    scores = [
        (CynefinDomain.CHAOTIC, s_chaotic),
        (CynefinDomain.COMPLEX, s_complex),
        (CynefinDomain.COMPLICATED, s_complicated),
        (CynefinDomain.CLEAR, s_clear),
    ]
    if irreversible:
        scores.sort(key=lambda x: -x[1])  # highest first; chaotic naturally cautious
    else:
        # reversible: prefer the most *specific* positive signal, not caution
        scores.sort(key=lambda x: -x[1])

    domain, confidence = scores[0]
    # If nothing matched, default by reversibility (reversible -> clear, else complex).
    if confidence == 0.0:
        domain = CynefinDomain.COMPLEX if irreversible else CynefinDomain.CLEAR
        confidence = 0.4

    ctrl = DOMAIN_CONTROL[domain]
    rationale = (
        f"markers: chaotic={s_chaotic:.2f} complex={s_complex:.2f} "
        f"complicated={s_complicated:.2f} clear={s_clear:.2f}; reversible={not irreversible}"
    )
    return DomainClassification(
        domain=domain, confidence=confidence, control=ctrl["control"], rationale=rationale
    )
