# version: v1 | 2026-08-05 | verdict: pending-review
"""Task 3 — Context-as-System view (Intelligence Forge plan).

Fares's vision: an agent's CONTEXT is not a small prompt — it IS the managed system
(big graph / many bespoke agents / all specs). This module builds that view by EXTENDING
the existing graph state (cycle_log from systems_layer), not creating a new parallel store.

P-CONTEXT-IS-SYSTEM: the view exposes (a) the agent's own instructions/role/lifecycle,
(b) the live cycle_log (the system's "memory"/life, P5), (c) peer agents from the registry,
(d) the constitution binding (P1-P7+CIR). All sourced from EXISTING state — no fork.
"""

from __future__ import annotations

from typing import Any

from agents.agent_forge import ForgedAgent
from system import agent_registry

# Bounds that keep the context OBSERVABLE (P2) under 7x scaling — the strong-model review
# (#3) measured unbounded cycle_log growth + a silent peers[:20] cap. Both are now named,
# explicit, and auditable so the context view never silently truncates or explodes.
MAX_PEERS = 20          # cap peer list (observable window into the managed system)
MAX_CYCLE_LOG = 50      # keep only the most-recent N cycles (system "life", P5) — bounded


def build_context_view(
    agent: ForgedAgent,
    graph_state: dict[str, Any] | None = None,
    registry: list[dict] | None = None,
) -> dict[str, Any]:
    """Build the agent's CONTEXT = a view of the managed system (extends existing state).

    Combines the agent's own context_view() with the live graph state (cycle_log = the
    system's persisted life, P5) and peer agents from the registry. This is what the agent
    "sees" — the whole system, not a trimmed summary. Both the peer list and cycle_log are
    explicitly bounded (MAX_PEERS / MAX_CYCLE_LOG) so the view stays observable at scale.
    """
    own = agent.context_view()
    state = graph_state or {}
    reg = agent_registry.AGENT_REGISTRY if registry is None else registry

    # Peers = other registered agents (the "many bespoke agents" the context exposes).
    peers = [
        {"name": e.get("name"), "category": e.get("category"), "forged": e.get("forged", False)}
        for e in reg
        if isinstance(e, dict) and e.get("name") != agent.name
    ][:MAX_PEERS]  # bounded window into the managed system (P2: observable, not unbounded)

    # Cycle log = the system's persisted life (P5). Bounded to the most-recent tail so the
    # context does not grow without limit under 7x scaling (strong-model review #3).
    cycle_log_full = state.get("cycle_log", []) or []
    cycle_log = cycle_log_full[-MAX_CYCLE_LOG:]

    return {
        **own,  # instructions + role + lifecycle + what_it_will_do
        "system_context": {
            "cycle_log": cycle_log,                 # the system's persisted life (P5), bounded
            "cycle_log_truncated": len(cycle_log_full) > MAX_CYCLE_LOG,
            "peer_agents": peers,                    # other agents in the managed system
            "constitution_binding": own.get("instructions", "").split("bound to ")[-1]
                if "bound to" in own.get("instructions", "") else agent.spec_slice,
            "graph_state_keys": sorted(state.keys()),  # what the system exposes right now
        },
        "context_is_system": True,
    }


def context_includes_system(agent: ForgedAgent, graph_state: dict[str, Any] | None = None) -> bool:
    """Auditable check (P2 zero-LLM): the built context actually exposes the system, not a stub."""
    view = build_context_view(agent, graph_state)
    sc = view.get("system_context", {})
    return bool(
        view.get("context_is_system")
        and sc.get("cycle_log") is not None
        and isinstance(sc.get("peer_agents"), list)
        and sc.get("constitution_binding") is not None
    )
