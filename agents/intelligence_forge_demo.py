# version: v1 | 2026-08-05 | verdict: pending-review
"""T2 — Intelligence Forge integration demo (wires ALL pieces into one real scenario).

Fares's vision, made runnable end-to-end:
  forge a bespoke agent  ->  build its context (the system)  ->  assemble its topology
  (focus/verify edges)  ->  convene the sage council on a measurement  ->  run the
  systems_layer meta-loop that records the cycle.

This is NOT a mock: it calls the real forge/context/topology/sage_council/systems_layer.
Proves the pieces COMPOSE (G1), no fork, no theater. Deterministic (no live LLM needed
for the wiring; the sage council + systems_layer run zero-LLM locally).
"""

from __future__ import annotations

from typing import Any

from agents.agent_forge import forge_agent
from agents.context_system_view import build_context_view
from agents.topology_assembler import assemble_topology
from agents.sage_council import build_council_from_registry
from agents.systems_layer import build_systems_graph


def run_intelligence_forge_scenario(
    agent_name: str = "demo_bespoke",
    spec_slice: list[str] | None = None,
    focused_task: str = "harden auth edge cases under bounded probing",
    measurement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one full Intelligence Forge scenario, composing every piece.

    Returns an auditable dict of what each stage produced. The systems_layer cycle_log
    proves the meta-loop actually ran.
    """
    spec_slice = spec_slice or ["P3", "P4", "P5"]

    # 1) FORGE — one bespoke, governed agent (no template)
    agent = forge_agent(agent_name, spec_slice, focused_task,
                        governance_profile={"complexity_gate": 4, "bounded_probe": True,
                                             "verify_node": True, "peer_review": True})
    # NOTE: we deliberately do NOT call extend_registry() here — that is a separate,
    # transactional persistence action (see test_extend_registry_transactional). This demo
    # composes the pieces in-memory to prove they wire together; persistence is opt-in.

    # 2) CONTEXT — the agent's context IS the managed system (cycle_log + peers + binding)
    graph_state = {"cycle_log": ["measure: baseline captured"], "current_measurement": measurement or {}}
    ctx = build_context_view(agent, graph_state)

    # 3) TOPOLOGY — typed focus/verify edges (structural binding, not emergent)
    topo = assemble_topology([agent])

    # 4) SAGE COUNCIL — local consensus on the measurement (CIR, no opus-5)
    council = build_council_from_registry()
    council_out = council.convene(measurement or {"complexity_score": 9,
                                                  "repeated_hypothesis_count": 1, "breach_count": 0,
                                                  "success_rate": 70})

    # 5) SYSTEMS LAYER — the live meta-loop backbone records the cycle.
    # COMPLETE Measurement shape (Law 3): compare_node now fails loudly on a short
    # shape, so the demo must supply every required field or the cycle is void.
    graph = build_systems_graph()
    sl_state = {
        "prior_measurement": {"complexity_score": 3, "repeated_hypothesis_count": 0,
                               "breach_count": 0, "success_rate": 80,
                               "defense_rate": 100.0, "quality": 0.80,
                               "health": 80.0, "thrash_count": 0},
        "current_measurement": measurement or {"complexity_score": 9, "repeated_hypothesis_count": 2,
                                                "breach_count": 1, "success_rate": 60,
                                                "defense_rate": 100.0, "quality": 0.65,
                                                "health": 66.0, "thrash_count": 2},
        "delta": None, "proposals": [], "decisions": [], "control_proposals": [],
        "counter_proposals": [], "philosopher_strategy": None, "reconciled_spec": None,
        "cycle_log": [],
    }
    sl_result = graph.invoke(sl_state, config={"configurable": {"thread_id": f"forge-{agent_name}"}})

    return {
        "forged_agent": agent.name,
        "behavior_hash": agent.behavior_hash,
        "context_is_system": ctx.get("context_is_system"),
        "context_peer_count": len(ctx["system_context"]["peer_agents"]),
        "topology_edge_count": topo["edge_count"],
        "topology_extends": topo["extends"],
        "council_convened": council_out["convened"],
        "council_topology": council_out["topology"],
        "meta_loop_ran": any("record:" in line for line in sl_result["cycle_log"]),
        "meta_loop_cycle_log": sl_result["cycle_log"],
    }
