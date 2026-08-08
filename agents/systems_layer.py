# version: v2 | 2026-08-05 | verdict: pending-review
"""Systems Layer — the meta-loop as FIRST-CLASS LangGraph nodes (META-SYSTEM v2, Task B).

This is the reconciliation of F3: the self-improvement loop is no longer an external
script; it is a StateGraph whose nodes read the domain layer's state (breaches, success,
thrash) and write ``control_proposals`` back into graph state. The domain agents are
never edited by these nodes — the layer OBSERVES and PROPOSES only (Ruling C1).

Pipeline (per docs/META-SYSTEM.md + CONSTITUTION Article VI 1b):
    measure -> compare -> propose -> distill -> gate -> apply_or_escalate -> record

Nodes here: measure, compare, propose, distill, gate, record.
``apply_or_escalate`` is added in Task E (v5); until then ``gate`` confirms the proposal
is reversible/observable and the layer stops at propose (per C1: proposes, does not apply).

Reuses the deterministic core from system.self_improvement (compare/propose/gate/distill)
so the logic stays in one place and stays zero-LLM.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from system.self_improvement import (
    Measurement,
    compare,
    distill_opus5,
    gate,
    measurement_version,
    propose,
)


class SystemsLayerState(TypedDict):
    """State threaded through the systems-layer graph.

    prior_measurement / current_measurement carry the domain layer's health snapshot.
    control_proposals is the layer's OUTPUT — read by a human or a reversible flag, never
    auto-applied by this graph (Ruling C1).
    philosopher_strategy: pure-reasoning output (CIR) — isolated from execution noise.
    reconciled_spec: philosopher_strategy distilled into an executable spec (Reconciler).
    """
    prior_measurement: dict[str, Any]
    current_measurement: dict[str, Any]
    delta: dict[str, Any] | None
    proposals: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    control_proposals: list[dict[str, Any]]
    counter_proposals: list[dict[str, Any]]
    philosopher_strategy: str | None
    reconciled_spec: str | None
    cycle_log: list[str]


# ---- Nodes (each is a pure (state) -> state transition) ----

def measure_node(state: SystemsLayerState) -> SystemsLayerState:
    """Record that a measurement was taken. The actual numbers arrive via
    current_measurement (fed by the cron runner or the domain layer). This node just
    logs the act of measuring so the cycle is auditable."""
    log = list(state.get("cycle_log", []))
    log.append("measure: captured domain-layer snapshot")
    return {**state, "cycle_log": log}


def philosopher_node(state: SystemsLayerState) -> SystemsLayerState:
    """CIR (Context-Isolated Reasoning) as a LOCAL Sage Council — NOT an opus-5 call.

    Per Fares's correction (2026-08-05): the principle lives INSIDE the graph as a council
    of local sages, not a hard link to opus-5. opus-5's role was to DISTILL the principle
    (now in distillation_ledger); the runtime uses LOCAL sages governed by it.

    COMPLEXITY GATE (opus-4-8 + A/B result): council convenes only when complexity >= 4.
    Below that, fused mode (no council overhead, no over-philosophizing on trivial tasks).
    """
    from agents.sage_council import build_default_council, build_council_from_registry
    # Prefer the REAL registry-backed council (Fares: methodology on actual project agents).
    # Falls back to the 3-sage default only if the registry import is unavailable.
    try:
        council = build_council_from_registry()
    except Exception as exc:  # registry import can fail in isolation; fall back loudly
        council = build_default_council()
        # surface the reason so the silent path is audible, not swallowed
        import logging
        logging.warning("SageCouncil fell back to default: %s", exc)
    m = state.get("current_measurement", {})
    if not council.should_convene(m):
        out = council.skip(m)
        log = list(state.get("cycle_log", [])) + [
            f"philosopher: council skipped (complexity={m.get('complexity_score', 0)} < "
            f"{council.complexity_threshold}, fused mode)"
        ]
        return {**state, "philosopher_strategy": None,
                "reconciled_spec": out["reconciled_spec"], "cycle_log": log}
    result = council.convene(m)
    log = list(state.get("cycle_log", [])) + [
        f"philosopher: council convened ({result['topology']}, {len(result['views'])} sages)"
    ]
    # The council's reconciled spec IS the philosopher's strategy output (local, no opus-5)
    return {**state, "philosopher_strategy": result["reconciled_spec"],
            "reconciled_spec": result["reconciled_spec"], "cycle_log": log}


def reconciler_node(state: SystemsLayerState) -> SystemsLayerState:
    """Reconciler — ensures the philosopher's output is a falsifiable SPEC (opus-5 clause).

    The SageCouncil already produces a reconciled_spec in philosopher_node; this node is the
    explicit checkpoint that the spec carries a falsification hook and is non-empty when the
    council convened. If the council was skipped (fused mode), spec stays None — no fabrication.
    """
    strategy = state.get("philosopher_strategy")
    spec = state.get("reconciled_spec")
    if strategy and (not spec or "FALSIFICATION" not in (spec or "")):
        # Defensive: guarantee the falsification hook even if a sage omitted it.
        spec = f"{strategy}\nFALSIFICATION: measurable via next-cycle delta."
    log = list(state.get("cycle_log", [])) + [
        f"reconciler: spec ({'yes' if spec else 'none'})"
    ]
    return {**state, "reconciled_spec": spec, "cycle_log": log}


def compare_node(state: SystemsLayerState) -> SystemsLayerState:
    """Diff prior vs current into a delta of observable signals.

    LAW 3 (Fail Loudly): the caller MUST supply the complete Measurement shape
    (success_rate, defense_rate, quality, health, thrash_count).  Short shapes
    that produce a TypeError are NOT caught here — they propagate and the
    cycle is recorded as a failure, not silently swallowed.
    """
    from system.self_improvement import Measurement
    before = Measurement(**{k: v for k, v in state["prior_measurement"].items()
                             if k in Measurement.__dataclass_fields__})
    after = Measurement(**{k: v for k, v in state["current_measurement"].items()
                            if k in Measurement.__dataclass_fields__})
    delta = compare(before, after)
    log = list(state.get("cycle_log", [])) + [f"compare: signals={delta['signals']}"]
    return {**state, "delta": delta, "cycle_log": log}


def propose_node(state: SystemsLayerState) -> SystemsLayerState:
    """Emit exactly one control change per meaningful signal (L3 / one variable per probe).

    Each proposal is stamped with the version of the measurement it was computed
    against (TRANSPLANT-1, prime-agent agent-session.ts:2556). Under Ruling C1 a
    human applies these by hand, so propose-time and apply-time can be days apart;
    the stamp is what makes `is_proposal_stale` able to answer honestly.
    """
    from system.self_improvement import Measurement

    delta = state.get("delta") or {"has_meaningful_delta": False}
    current = state.get("current_measurement", {})
    measured = None
    if current:
        measured = Measurement(**{k: v for k, v in current.items()
                                  if k in Measurement.__dataclass_fields__})
    proposals = propose(delta, measured=measured)
    log = list(state.get("cycle_log", [])) + [
        f"propose: {len(proposals)} control(s) for signals"
    ]
    return {**state, "proposals": proposals, "cycle_log": log}


def distill_node(state: SystemsLayerState) -> SystemsLayerState:
    """Route each proposal through opus-5 distillation -> frozen principle (L5)."""
    decisions = []
    for p in state.get("proposals", []):
        decisions.append({"proposal": p, "distilled": distill_opus5(p)})
    log = list(state.get("cycle_log", [])) + [
        f"distill: {len(decisions)} principle(s) distilled"
    ]
    return {**state, "decisions": decisions, "cycle_log": log}


def gate_node(state: SystemsLayerState) -> SystemsLayerState:
    """Gate each proposal: observable + reversible + falsifiable (P7). Accepted proposals
    become control_proposals. Per C1 this graph NEVER applies them — it only proposes.

    STALENESS IS CHECKED HERE, at the point of use (M1). `propose_node` stamps each
    proposal with the measurement version it was computed from; this node re-derives the
    version from the CURRENT measurement and compares. A proposal whose evidence has
    since moved is flagged `stale=True` rather than dropped: under C1 a human decides,
    and deleting the row would hide the signal instead of qualifying it.

    Fails safe (Law 3): a proposal with no stamp, or a state with no current
    measurement, reads as stale. "Not verified fresh" is never reported as fresh.
    """
    current_raw = state.get("current_measurement") or {}
    current_version = ""
    if current_raw:
        try:
            current_version = measurement_version(Measurement(**current_raw))
        except (TypeError, ValueError):
            current_version = ""

    control_proposals = []
    stale_count = 0
    for d in state.get("decisions", []):
        decision = gate(d["proposal"])
        stamped = d["proposal"].get("measurement_version")
        # No stamp, or no comparable current evidence -> not verified fresh.
        stale = (not stamped) or (not current_version) or (stamped != current_version)
        if stale:
            stale_count += 1
        # C1: even if accepted, we record it as a PROPOSAL, not an applied change.
        control_proposals.append({
            "kind": d["proposal"]["kind"],
            "hypothesis": d["proposal"]["hypothesis"],
            "principle_ref": d["distilled"]["references"],
            "gated_accepted": decision["accepted"],
            "gated_reason": decision["reason"],
            "measurement_version": stamped or "",
            "stale": stale,
            "status": "proposed",  # never "applied" by this graph
        })
    log = list(state.get("cycle_log", [])) + [
        f"gate: {len(control_proposals)} control proposal(s) emitted (propose-only, C1)"
    ]
    if stale_count:
        log.append(
            f"gate: {stale_count} proposal(s) flagged STALE — evidence moved since "
            f"propose-time; re-measure before applying (M1)"
        )
    return {**state, "control_proposals": control_proposals, "cycle_log": log}


def apply_or_escalate_node(state: SystemsLayerState) -> SystemsLayerState:
    """Resolve each proposed control (C1-rev1, opus-5 live review).

    Defaults to DENY (propose-only). The meta-loop NEVER auto-applies — application needs
    an *independent* opt-in (human/flag) judged by an external criterion, never self-assessed
    (opus-5 fix #2 + #1). Domain-agent counter-proposals are surfaced, not dropped (#4).

    Counter-proposals are read from the real persistence layer (system.counter_proposals),
    never from an empty placeholder — Ruling C1-rev1 requires the channel to be live.
    """
    # Surface counter-proposals first (opus-5 fix #4): meta-loop has no interpretive monopoly.
    from system.counter_proposals import get_pending_challenges

    pending_challenges = get_pending_challenges()
    resolved = []
    log_lines = []
    for cp in pending_challenges:
        log_lines.append(
            f"counter-proposal from {getattr(cp, 'from_agent', '?')}: "
            f"{getattr(cp, 'challenge', '')}"
        )

    for cp in state.get("control_proposals", []):
        # opus-5 fix #1: reversibility judged by external criterion, not self-assessed.
        independently_reversible = (
            cp.get("opt_in_apply")
            and cp.get("reversibility_judged_by") not in (None, "self")
        )
        if cp.get("gated_accepted") and independently_reversible:
            new_cp = {**cp, "status": "applied"}
            log_lines.append(f"apply: {cp['kind']} applied (independent opt-in)")
        elif cp.get("gated_accepted") and not independently_reversible:
            # DEFAULT-DENY: even if reversible + accepted, stays proposed unless opt-in set.
            new_cp = {**cp, "status": "proposed"}
            log_lines.append(f"propose: {cp['kind']} held (default-deny, no independent opt-in)")
        else:
            new_cp = {**cp, "status": "rejected"}
            log_lines.append(f"reject: {cp['kind']} failed gate ({cp.get('gated_reason')})")
        resolved.append(new_cp)

    log = list(state.get("cycle_log", [])) + log_lines
    return {**state, "control_proposals": resolved, "cycle_log": log}


def record_node(state: SystemsLayerState) -> SystemsLayerState:
    """Append the cycle evidence to the measurement log (append-only, like the script)."""
    import json
    from pathlib import Path

    out_dir = Path("system/measurements")
    out_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "prior": state["prior_measurement"],
        "current": state["current_measurement"],
        "delta": state["delta"],
        "control_proposals": state["control_proposals"],
    }
    with (out_dir / "systems_layer_cycles.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    log = list(state.get("cycle_log", [])) + ["record: cycle appended to systems_layer_cycles.jsonl"]
    return {**state, "cycle_log": log}


def build_systems_graph(saver=None):
    """Compile the systems-layer StateGraph.

    measure -> compare -> propose -> distill -> gate -> record -> END
    (apply_or_escalate is added in Task E / v5; until then the graph stops at propose.)

    ``saver`` defaults to a DISK-BACKED JsonlCheckpointSaver (fixes strong-model review #3:
    the prior MemorySaver was volatile — all cycle_log / graph state was lost on restart).
    Pass an explicit saver (e.g. MemorySaver) only for ephemeral test runs.
    """
    from agents.disk_saver import JsonlCheckpointSaver
    if saver is None:
        saver = JsonlCheckpointSaver()
    workflow = StateGraph(SystemsLayerState)
    workflow.add_node("measure", measure_node)
    workflow.add_node("philosopher", philosopher_node)
    workflow.add_node("reconciler", reconciler_node)
    workflow.add_node("compare", compare_node)
    workflow.add_node("propose", propose_node)
    workflow.add_node("distill", distill_node)
    workflow.add_node("gate", gate_node)
    workflow.add_node("apply_or_escalate", apply_or_escalate_node)
    workflow.add_node("record", record_node)

    workflow.add_edge(START, "measure")
    workflow.add_edge("measure", "philosopher")
    workflow.add_edge("philosopher", "reconciler")
    workflow.add_edge("reconciler", "compare")
    workflow.add_edge("compare", "propose")
    workflow.add_edge("propose", "distill")
    workflow.add_edge("distill", "gate")
    workflow.add_edge("gate", "apply_or_escalate")
    workflow.add_edge("apply_or_escalate", "record")
    workflow.add_edge("record", END)

    return workflow.compile(checkpointer=MemorySaver())
