# version: v1 | 2026-08-05 | verdict: pending-review
"""Task 4 — Topology Assembler (Intelligence Forge plan).

Wires bespoke forged agents into the big graph with TYPED FOCUS EDGES derived from each
agent's governance_profile. This is where "among other agents → focused task" becomes
STRUCTURAL (P-FOCUS), not emergent hope.

EXTENDS the existing systems_layer (P-NO-FORK): the assembler emits edge specs that the
live graph can consume; it does not replace the meta-loop. Edges are typed so the
constitution can enforce who may message whom (architectural constraint, not a prompt).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.agent_forge import ForgedAgent

# Edge types permitted by the constitution. Anything else is rejected (architectural gate).
ALLOWED_EDGE_TYPES = {
    "focus",        # agent -> its focused task (the binding that prevents open-ended work)
    "peer-review",  # agent -> agent (P6 productive contradiction routing)
    "verify",       # agent -> verify node (P2 verified closure)
    "escalate",     # agent -> human (P3/P4 escalation)
}


@dataclass
class GraphEdge:
    """A typed, governance-bound edge between two nodes in the big graph."""

    src: str
    dst: str
    kind: str  # one of ALLOWED_EDGE_TYPES
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ALLOWED_EDGE_TYPES:
            raise ValueError(
                f"Edge kind '{self.kind}' not in ALLOWED_EDGE_TYPES {sorted(ALLOWED_EDGE_TYPES)}. "
                f"Constitution forbids untyped edges (architectural constraint)."
            )


def build_focus_edges(agents: list[ForgedAgent]) -> list[GraphEdge]:
    """For each forged agent, emit its FOCUS edge (agent -> its focused task) + VERIFY edge.

    The focus edge is the structural binding: being among other agents assigns a concentrated
    task, not an open-ended one. VERIFY closes the write (P2). Peer-review/escalate edges are
    added only when the governance_profile permits (P6/P3-P4).
    """
    edges: list[GraphEdge] = []
    for a in agents:
        # FOCUS: the agent is structurally bound to its focused task (P-FOCUS)
        edges.append(GraphEdge(
            src=a.name,
            dst=f"task:{a.focused_task}",
            kind="focus",
            payload={"governance_profile": a.governance_profile, "binding": a.spec_slice},
        ))
        # VERIFY: every write terminates in a verify node (P2 verified closure)
        edges.append(GraphEdge(
            src=f"task:{a.focused_task}",
            dst=f"verify:{a.name}",
            kind="verify",
            payload={"postcondition": "next-cycle delta observable"},
        ))
        prof = a.governance_profile or {}
        if prof.get("peer_review"):
            edges.append(GraphEdge(src=a.name, dst="council", kind="peer-review",
                                   payload={"for": a.focused_task}))
        if prof.get("bounded_probe"):
            edges.append(GraphEdge(src=a.name, dst="human", kind="escalate",
                                   payload={"trigger": "budget_exhausted_or_repeat"}))
    return edges


def assemble_topology(agents: list[ForgedAgent]) -> dict[str, Any]:
    """Assemble the topology spec (extends systems_layer; does not replace it).

    Returns an auditable structure: nodes (agents + tasks + verify) and typed edges.
    The live graph consumes this; the assembler is pure (no mutation of global state).
    """
    nodes = set()
    for a in agents:
        nodes.add(a.name)
        nodes.add(f"task:{a.focused_task}")
        nodes.add(f"verify:{a.name}")
    edges = build_focus_edges(agents)
    return {
        "nodes": sorted(nodes),
        "edges": [
            {"src": e.src, "dst": e.dst, "kind": e.kind, "payload": e.payload}
            for e in edges
        ],
        "edge_count": len(edges),
        "extends": "systems_layer",  # P-NO-FORK: augments, does not replace
    }
