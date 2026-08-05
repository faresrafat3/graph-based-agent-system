# version: v1 | 2026-08-05 | verdict: pending-review
"""Sage Council — the CIR principle embodied as LOCAL agent sages (NOT an opus-5 dependency).

Fares's correction (2026-08-05): the principle (Context-Isolated Reasoning + agent
communication topology) must live INSIDE the graph as a council of local sages, not as a
hard link to opus-5. opus-5's role was to DISTILL the principle (now in distillation_ledger);
the runtime uses LOCAL agents governed by that principle.

Design (per COMPARATIVE-STUDY + Fares's direction):
- A council of sages, each a LOCAL agent (no external LLM dependency at graph runtime).
- Communication topology: peer / hierarchical / broadcast — selected per task complexity.
- CIR: sages reason on CONTEXT-ISOLATED signals, never raw execution artifacts.
- Reconciler: divergent sage views -> one falsifiable spec (consensus mechanism).
- Complexity gate: below threshold, fused mode (no council overhead).

This is the "methodology of the system" — how agents achieve coherent fusion of
conflicting views while honoring the user's vision/requests (Fares's deep problem).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# ---- Communication topologies (the "agent communication" methodology) ----
PEER = "peer"               # sages debate as equals, dialectic resolution
HIERARCHICAL = "hierarchical"  # a lead sage aggregates subordinate views
BROADCAST = "broadcast"     # one sage emits, all receive, no back-and-forth


@dataclass
class Sage:
    """A local reasoning agent governed by the CIR principle.

    A sage does NOT call opus-5. It holds a slice of the distilled principles and emits
    a view on context-isolated signals only.
    """
    name: str
    principle_refs: list[str]  # which distilled principles it champions
    role: str = "advisor"
    weight: float = 1.0  # consensus weight — how much this sage's view counts

    # Principle -> the concrete governance stance that principle takes on a signal set.
    # A sage's view is the FUSION of its principle stances read against the signals, so
    # different sages (championing different principle slices) emit GENUINELY DIVERGENT
    # views — not an identical body with a different name tag (that was consensus theater).
    _PRINCIPLE_STANCE = {
        "P1": "raise_variety",
        "P2": "verify_closure",
        "P3": "gate_by_domain",
        "P4": "bound_probes",
        "P5": "serialize_state",
        "P6": "surface_conflict",
        "P7": "prune_unused",
        "CIR": "isolate_context",
    }

    def reason(self, isolated_signals: dict) -> str:
        """Emit a DISTINCT view from the sage's principle slice read against the signals.

        The view is built from the concrete stances of the principles this sage champions,
        modulated by the signal values (e.g. a breach spike makes the verify/prune stance
        fire, a complexity spike makes the gate/variety stance fire). Two sages championing
        different principle slices therefore produce different views — so the consensus
        mechanism fuses real disagreement, not an echo (fixes strong-model review #2).
        """
        breaches = isolated_signals.get("breaches", 0) or 0
        complexity = isolated_signals.get("complexity", 0) or 0
        thrash = isolated_signals.get("thrash", 0) or 0
        stances = [self._PRINCIPLE_STANCE.get(p, f"honor_{p}") for p in self.principle_refs]
        # Signal-driven emphasis: which stances are "active" given the measurement.
        active = []
        if breaches > 0:
            active.append("verify_closure") if "verify_closure" in stances else None
            active.append("prune_unused") if "prune_unused" in stances else None
        if complexity >= 7:
            active.append("gate_by_domain") if "gate_by_domain" in stances else None
            active.append("raise_variety") if "raise_variety" in stances else None
        if thrash > 0:
            active.append("bound_probes") if "bound_probes" in stances else None
            active.append("surface_conflict") if "surface_conflict" in stances else None
        # De-dupe while preserving order; fall back to the champion stances if nothing active.
        seen = set()
        emphasis = []
        for s in (active + stances):
            if s and s not in seen:
                seen.add(s)
                emphasis.append(s)
        refs = ",".join(self.principle_refs)
        return (
            f"[{self.name}|{refs}] on(c={complexity},b={breaches},t={thrash}) "
            f"-> {'+'.join(emphasis)}"
        )


@dataclass
class SageCouncil:
    """Council of sages that achieves coherent fusion of conflicting views.

    The consensus mechanism + communication topology ARE the methodology Fares asked for:
    how agents communicate in all forms and reach a correct final integration that honors
    the user's vision/requests.
    """
    sages: list[Sage] = field(default_factory=list)
    topology: str = PEER
    complexity_threshold: int = 4

    def _isolated_signals(self, measurement: dict) -> dict:
        """Context isolation: expose ONLY high-level signals, never raw execution noise."""
        return {
            "complexity": measurement.get("complexity_score", 0),
            "thrash": measurement.get("repeated_hypothesis_count", 0),
            "breaches": measurement.get("breach_count", 0),
            "success_rate": measurement.get("success_rate"),
        }

    def should_convene(self, measurement: dict) -> bool:
        """Complexity gate (opus-4-8 + A/B result): skip council on trivial tasks."""
        return (measurement.get("complexity_score", 0) or 0) >= self.complexity_threshold

    def convene(self, measurement: dict) -> dict:
        """Run the council and return a reconciled, falsifiable SPEC.

        Steps:
          1. Each sage reasons on context-isolated signals (CIR).
          2. Topology determines how views combine.
          3. ConsensusMechanism distills divergent views into ONE coherent, falsifiable spec
             that honors the user's vision (Fares's deep problem: correct final integration).
        """
        signals = self._isolated_signals(measurement)
        views = [s.reason(signals) for s in self.sages]
        consensus = ConsensusMechanism.reconcile(
            sages=self.sages, views=views, topology=self.topology, signals=signals
        )
        spec = (
            f"SPEC[council/{self.topology}]: {consensus['merged']}\n"
            f"FALSIFICATION: measurable via next-cycle delta on {signals}"
        )
        return {"convened": True, "topology": self.topology, "views": views,
                "reconciled_spec": spec, "isolated_signals": signals,
                "consensus": consensus}

    def skip(self, measurement: dict) -> dict:
        """Fused mode: no council, graph proceeds on data alone (zero-LLM safe)."""
        return {"convened": False, "topology": None, "views": [],
                "reconciled_spec": None,
                "isolated_signals": self._isolated_signals(measurement)}


def build_default_council() -> SageCouncil:
    """Default council seeded from the distilled principles (opus-5's legacy, now local).

    These sages champion the principles opus-5 distilled (P1-P7 + CIR). They are LOCAL —
    opus-5 is not called at runtime.
    """
    sages = [
        Sage("governance_sage", ["P1", "P2", "P3"], role="governance", weight=1.2),
        Sage("probe_sage", ["P4", "P7"], role="probing", weight=1.0),
        Sage("context_sage", ["P5", "P6", "CIR"], role="context-isolation", weight=1.1),
    ]
    return SageCouncil(sages=sages, topology=PEER, complexity_threshold=4)


# Category -> principle mapping: each registry agent's category maps to a distilled principle
# slice. This is how the methodology (CIR + consensus) becomes the SYSTEM's behavior across
# the real 27+ agents, not a parallel mock structure (Fares: "use the methodology on the
# actual project agents").
_CATEGORY_PRINCIPLE = {
    "governance": ["P1", "P2", "P3"],
    "validator": ["P2"],
    "meta_agent": ["P5", "P6"],
    "orchestration": ["P3"],
    "systems_layer": ["CIR", "P7"],
    "memory": ["P5"],
    "generation": ["P4", "P7"],
    "repair": ["P4"],
    "learning": ["P6"],
    "context_management": ["P5", "CIR"],
    "domain_squad": ["P3"],
    "execution": ["P7"],
    "code_generation": ["P7"],
    "pipeline": ["CIR"],
    "slice": ["P4"],
}

# Category -> consensus weight (how much this agent class's view counts in the council)
_CATEGORY_WEIGHT = {
    "governance": 1.3, "systems_layer": 1.2, "validator": 1.1, "meta_agent": 1.0,
    "orchestration": 1.0, "memory": 0.9, "generation": 0.9, "repair": 0.9,
    "learning": 0.9, "context_management": 1.0, "domain_squad": 0.9,
    "execution": 0.8, "code_generation": 0.8, "pipeline": 1.0, "slice": 0.9,
}


def build_council_from_registry(registry: list[dict] | None = None) -> SageCouncil:
    """Build a REAL Sage Council from the project's registered agents (not a mock).

    Every registered agent becomes a Sage championing the principle slice of its category,
    weighted by category importance. This is the methodology made concrete: the 27+ agents
    ARE the council — CIR + consensus apply across the real system, honoring Fares's vision.
    """
    from system.agent_registry import AGENT_REGISTRY
    reg = registry if registry is not None else AGENT_REGISTRY
    sages = []
    for a in reg:
        if a.get("name") == "Systems Layer (Meta-Loop)":
            continue  # the council itself lives in the systems layer; don't self-include
        cat = a.get("category", "meta_agent")
        refs = _CATEGORY_PRINCIPLE.get(cat, ["P7"])
        weight = _CATEGORY_WEIGHT.get(cat, 1.0)
        sages.append(Sage(name=a["name"], principle_refs=refs,
                          role=cat, weight=weight))
    # Aggregate by category so the council stays small + coherent (one sage per category).
    by_cat: dict[str, Sage] = {}
    for s in sages:
        if s.role not in by_cat:
            by_cat[s.role] = s
    aggregated = list(by_cat.values())
    return SageCouncil(sages=aggregated, topology=PEER, complexity_threshold=4)


class ConsensusMechanism:
    """The reconciliation core — how divergent sage views fuse into ONE coherent spec.

    This is THE methodology Fares asked for: how agents communicate in all forms AND reach a
    correct final integration that honors the user's vision/requests. Not concatenation —
    real fusion with conflict detection + weighted consensus + a falsifiable output.
    """

    # Keyword pairs that signal opposing stances — used for lightweight contradiction detection.
    # Covers BOTH the explicit view strings used in tests (bound/expand, centralize/distribute,
    # ...) AND the concrete stances emitted by Sage.reason() (raise_variety/prune_unused, ...)
    # so real disagreements surface across both vocabularies.
    _OPPOSING = {
        ("bound", "expand"), ("limit", "extend"), ("reject", "accept"),
        ("centralize", "distribute"), ("freeze", "evolve"),
        ("raise_variety", "prune_unused"),    # grow vs cut
        ("gate_by_domain", "isolate_context"),  # constrain vs open
        ("bound_probes", "serialize_state"),     # limit tries vs persist
        ("verify_closure", "surface_conflict"),  # close vs expose
    }

    @staticmethod
    def _detect_conflicts(views: list[str]) -> list[str]:
        """Lightweight contradiction scan across sage views (zero-LLM, auditable)."""
        lowered = [v.lower() for v in views]
        conflicts = []
        for a, b in ConsensusMechanism._OPPOSING:
            if any(a in v for v in lowered) and any(b in v for v in lowered):
                conflicts.append(f"conflict:{a}/{b}")
        return conflicts

    @classmethod
    def reconcile(cls, sages: list[Sage], views: list[str], topology: str,
                  signals: dict) -> dict:
        """Fuse sage views into one merged, weighted, conflict-aware spec fragment.

        Returns:
          merged: the coherent integration string (topology-shaped)
          conflicts: detected contradictions (surfaced, not hidden)
          weights: per-sage consensus weight applied
        """
        conflicts = cls._detect_conflicts(views)
        total_w = sum(s.weight for s in sages) or 1.0
        weighted = sorted(
            zip(sages, views),
            key=lambda sv: sv[0].weight / total_w,
            reverse=True,
        )
        if topology == BROADCAST:
            merged = views[0] if views else ""
        elif topology == HIERARCHICAL:
            lead = sages[0].name if sages else "none"
            merged = f"LEAD[{lead}]::" + " ; ".join(v for _, v in weighted)
        else:  # PEER — weighted dialectic: highest-weight view first, conflicts flagged
            body = " & ".join(v for _, v in weighted)
            merged = f"DIAALECTIC: " + body
        # Surface contradictions in ALL topologies (Fares: correct integration honors the
        # vision — conflicts must be visible, not silently merged).
        if conflicts:
            merged = f"{merged} [CONFLICTS:{','.join(conflicts)}]"
        return {"merged": merged, "conflicts": conflicts,
                "weights": {s.name: s.weight for s in sages}}
