"""Self-pruning report (P7: Least Sufficient Intervention) for the agent graph.

Reads the agent registry + governance checks (no LLM) and produces a report of which
registered agents have NOT demonstrably changed an outcome in observed runs. Per P7,
those are candidates for removal — but this module only REPORTS; it never deletes. The
META-SYSTEM loop records the recommendation; a human (or a reviewed PR) acts on it.

This is the graph applying P7 to itself: each agent is a control that should catch a
specific failure mode (P1: requisite variety). If measurement shows it is silent dead
weight, it is flagged.

Safe: reads only registry + governance state; never imports live agent code paths owned
by sibling sessions (debugger/reflexion/deterministic_validator/domain_dispatcher).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from system.agent_registry import AGENT_REGISTRY
from system.governance_checks import run_governance_checks, _transitive_reachable, LIVE_ENTRYPOINT


# Agents explicitly declared external (benchmark-only, base classes, optional
# governance/escalation, memory-write helpers). Mirrors the audit's EXTERNAL_ALLOWED.
# Keys MUST match registry `entrypoint` values (see system/agent_registry.py).
EXTERNAL_ALLOWED: set[str] = {
    "sample_candidates",        # AlphaCode sampling arm
    "run_competitive_slice",    # humaneval-selected slice
    "CompetitiveContextManager",  # selected by dispatch, not live by default
    "run_karpathy_pipeline",    # orchestrator, not a per-failure control
}


@dataclass(frozen=True)
class PruningCandidate:
    agent: str
    category: str
    reason: str
    observed_effect: str = "none recorded"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_pruning_report(measurements_dir: str = "system/measurements") -> dict[str, Any]:
    """Return a P7 pruning report over the registered agent graph.

    Logic:
      - governance checks tell us reachability (reachable vs external-declared).
      - a reachable agent with no recorded outcome change in the measurements log is a
        pruning candidate (silent control).
      - external-declared agents are reported separately (intentionally not live).
    """
    gov = run_governance_checks()
    checks = gov.get("checks", [])
    # reachability: compute the live reachable set directly (names, not just a count)
    entry_names = {e["entrypoint"] for e in AGENT_REGISTRY}
    reachable_eps = _transitive_reachable(LIVE_ENTRYPOINT, entry_names)
    reachable = {e["name"] for e in AGENT_REGISTRY if e["entrypoint"] in reachable_eps}

    # Read measurements log to see which controls ever changed an outcome.
    caught: set[str] = set()
    mdir = Path(measurements_dir)
    mlog = mdir / "measurements.jsonl"
    if mlog.exists():
        for line in mlog.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for d in row.get("decisions", []):
                if d.get("decision", {}).get("accepted"):
                    # A control was accepted -> it caught/proposed a change.
                    caught.add(d["proposal"]["kind"])

    candidates: list[PruningCandidate] = []
    external: list[str] = []
    for entry in AGENT_REGISTRY:
        name = entry["name"]
        ep = entry["entrypoint"]
        if ep in EXTERNAL_ALLOWED:
            external.append(name)
            continue
        # P7: a LIVE (reachable) agent that has never demonstrably changed an outcome
        # is a silent control -> pruning candidate. External-declared agents are not
        # candidates (intentionally off the live path).
        if name in reachable and name not in caught:
            candidates.append(PruningCandidate(
                agent=name, category=entry.get("category", "?"),
                reason="reachable from live path but no observed outcome change in measurements",
            ))

    return {
        "pruning_candidates": [c.as_dict() for c in candidates],
        "external_declared": external,
        "controls_with_observed_effect": sorted(caught),
        "recommendation": (
            "Remove or justify each candidate by the failure it demonstrably catches (P7). "
            "This report is advisory; no agent was deleted."
        ),
    }


def main() -> None:
    rep = build_pruning_report()
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
