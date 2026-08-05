"""Governed self-improvement meta-loop (META-SYSTEM.md).

This module is intentionally NOT an agent and NOT a supreme decision maker. It is a
small deterministic engine that turns measurements into proposed control changes and
gates them by observed effect (P7: Least Sufficient Intervention). No LLM calls are
made here; if a proposal touches governance philosophy it is routed through
``distill_opus5`` which returns a *distilled principle*, never executable code.

Stages (see docs/META-SYSTEM.md):
    measure -> compare -> propose -> gate -> record

Hard rules (enforced):
    1. One variable per probe (propose emits exactly one control per delta).
    2. Every proposal is reversible (config/flag), unless up-leveled by a principle.
    3. No control is added that cannot be observed catching a failure.
    4. opus-5 output is distilled to a principle and frozen; never edits code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Kinds of control change the loop is allowed to propose. Each is reversible by
# construction (config/flag), satisfying hard rule 2. Architecture rewrites are NOT
# in this set — those require an explicit distilled principle (see distill_opus5).
CONTROL_PROPOSAL_SCHEMA: frozenset[str] = frozenset({
    "probe_budget",        # P4: cap N attempts in complex work
    "domain_governance",   # P3: bind control intensity to Cynefin domain
    "routing_outcome",     # P1: expose a new outcome at a routing point
    "remove_control",      # P7: drop a control that caught no failure
    "verify_postcondition",  # P2: attach a VERIFY node postcondition
})


@dataclass(frozen=True)
class Measurement:
    """One snapshot of system health. Append-only; compared across cycles.

    governance_score is reported SEPARATELY from success_rate (Ruling F2): loops improve
    governance (does the system obey its own rules?), not necessarily capability (does it
    solve the task?). Never conflate the two.
    """

    success_rate: float
    defense_rate: float
    quality: float
    health: float
    thrash_count: int
    postcond_pass: float | None = None
    governance_score: float | None = None
    timestamp: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_governance_score(defense_rate: float, thrash_count: int,
                             breaches: int) -> float:
    """Governance axis: how well the system obeys its own rules (Ruling F2).

    Independent of success_rate. High defense + low thrash + low breaches => high score.
    This is what the reflexive loops actually move; capability is the generator's job.
    """
    defense = max(0.0, min(1.0, defense_rate / 100.0))
    thrash_penalty = min(0.5, thrash_count * 0.1)
    breach_penalty = min(0.3, breaches * 0.05)
    score = defense - thrash_penalty - breach_penalty
    return round(max(0.0, min(1.0, score)), 3)


def compare(before: Measurement, after: Measurement) -> dict[str, Any]:
    """Classify the delta between two measurements into observable signals.

    Returns a dict with per-metric deltas and a boolean ``has_meaningful_delta``
    so propose() only fires on real movement (L1: publish variance, act on signal).
    """
    signals: list[str] = []
    deltas = {
        "success_delta": round(after.success_rate - before.success_rate, 4),
        "defense_delta": round(after.defense_rate - before.defense_rate, 4),
        "quality_delta": round(after.quality - before.quality, 4),
        "health_delta": round(after.health - before.health, 4),
        "thrash_delta": after.thrash_count - before.thrash_count,
    }
    if before.postcond_pass is not None and after.postcond_pass is not None:
        deltas["postcond_delta"] = round(after.postcond_pass - before.postcond_pass, 4)
    if deltas["thrash_delta"] != 0:
        signals.append("thrash")
    if deltas["defense_delta"] != 0:
        signals.append("defense")
    if abs(deltas["success_delta"]) >= 5.0:
        signals.append("capability")
    if abs(deltas["health_delta"]) >= 2.0:
        signals.append("health")
    if "postcond_delta" in deltas and abs(deltas["postcond_delta"]) >= 0.05:
        signals.append("postcondition")

    has_meaningful_delta = bool(signals)
    return {
        "deltas": deltas,
        "signals": signals,
        "has_meaningful_delta": has_meaningful_delta,
    }


def propose(delta: dict[str, Any]) -> list[dict[str, Any]]:
    """Emit exactly ONE control change per meaningful signal (L3).

    The loop isolates a single variable per probe: one signal -> one proposal.
    Multiple signals would mean multiple simultaneous changes, which violates the
    one-variable rule, so we propose for the highest-priority signal only and leave
    the rest for the next cycle.
    """
    if not delta.get("has_meaningful_delta"):
        return []

    signals = delta["signals"]
    # Priority order encodes the governance thesis: defense and thrash beat raw
    # capability, because a silent breach (L6) is the dangerous class.
    priority = ["defense", "thrash", "postcondition", "capability", "health"]
    chosen = next((s for s in priority if s in signals), signals[0])

    if chosen == "thrash":
        return [{
            "kind": "probe_budget",
            "hypothesis": "Capping repeated-hypothesis attempts reduces thrashing without dropping resolves.",
            "reversible": True,
            "observability": "repeated_hypothesis_count in reflexion/debugger state",
        }]
    if chosen == "defense":
        return [{
            "kind": "domain_governance",
            "hypothesis": "Binding control intensity to Cynefin domain closes the defense gap.",
            "reversible": True,
            "observability": "domain/confidence field on dispatch result",
        }]
    if chosen == "postcondition":
        return [{
            "kind": "verify_postcondition",
            "hypothesis": "Attaching a declared postcondition VERIFY node closes silent partial completion.",
            "reversible": True,
            "observability": "verify_execution_postcondition pass rate",
        }]
    if chosen == "capability":
        # L2: capability delta is the GENERATOR's ceiling, not the graph's.
        # Propose measurement-only; architecture rewrite blocked unless distilled.
        return [{
            "kind": "remove_control",
            "hypothesis": "Capability swing is generator variance, not a graph defect; no graph control change warranted yet.",
            "reversible": True,
            "observability": "SWE-bench single-shot vs alphacode variance band",
            "note": "generator_ceiling",
        }]
    # health-only: tighten an existing control, stay reversible
    return [{
        "kind": "routing_outcome",
        "hypothesis": "Exposing an extra routing outcome at the weakest stage lifts health.",
        "reversible": True,
        "observability": "stage-level success rate in pipeline result",
    }]


def gate(proposal: dict[str, Any]) -> dict[str, Any]:
    """Accept a proposal only if it is observable + reversible (P7 / L4).

    Hard rule 3: no control survives unless it demonstrably catches a failure.
    Hard rule 2: must be reversible by config/flag.
    """
    if proposal.get("kind") not in CONTROL_PROPOSAL_SCHEMA:
        return {"accepted": False, "reason": f"kind {proposal.get('kind')} not in schema"}
    if not proposal.get("reversible"):
        return {"accepted": False, "reason": "proposal is not reversible (hard rule 2)"}
    if not proposal.get("observability"):
        return {"accepted": False, "reason": "proposal is not observable (hard rule 3 / P7)"}
    if not proposal.get("hypothesis"):
        return {"accepted": False, "reason": "proposal lacks a falsifiable hypothesis"}
    return {"accepted": True, "reason": "observable + reversible + falsifiable"}


def distill_opus5(proposal: dict[str, Any]) -> dict[str, Any]:
    """Distill a governance-touching proposal into a frozen principle.

    This is the ONLY interface to opus-5's philosophy in the live path. It returns a
    short principle string + a reference (e.g. 'P3'), never executable code (L5).
    The distillation mapping below is the frozen record of what opus-5 prescribed in
    CONSTITUTION Article VI; it is not a network call and cannot author code.
    """
    kind = proposal.get("kind")
    if kind is None:
        return {
            "principle": "P7 — justify each surviving control by the failure it catches.",
            "references": "P7",
            "is_code": False,
            "source": "opus-5 distillation (CONSTITUTION Article VI)",
        }
    mapping = {
        "probe_budget": ("P4 — Bounded Probing: complex work runs N attempts, each a NEW falsifiable hypothesis; repeat or exhaust -> escalate.", "P4"),
        "domain_governance": ("P3 — Domain-Gated Governance: control intensity follows Cynefin domain + reversibility, never permission class.", "P3"),
        "routing_outcome": ("P1 — Requisite Response Variety: every routing point exposes >= failure modes reaching it; add outcomes before agents.", "P1"),
        "remove_control": ("P7 — Least Sufficient Intervention: drop any control that has not changed an outcome in observed runs.", "P7"),
        "verify_postcondition": ("P2 — Verified Closure: every write edge terminates in a VERIFY node checking a declared postcondition, no LLM.", "P2"),
    }
    principle, ref = mapping.get(kind, ("P7 — justify each surviving control by the failure it catches.", "P7"))
    return {
        "principle": principle,
        "references": ref,
        "is_code": False,
        "source": "opus-5 distillation (CONSTITUTION Article VI)",
    }


def record(measurement: Measurement, delta: dict[str, Any], proposals: list[dict[str, Any]],
           decisions: list[dict[str, Any]], measurements_dir: str = "system/measurements") -> Path:
    """Append-only persistence of one cycle's evidence (STAGE 5)."""
    out_dir = Path(measurements_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "measurement": measurement.as_dict(),
        "delta": delta,
        "proposals": proposals,
        "decisions": decisions,
    }
    # measurements.jsonl = one row per cycle
    m_path = out_dir / "measurements.jsonl"
    with m_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return m_path
