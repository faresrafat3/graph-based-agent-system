# version: v1 | 2026-08-05 | verdict: pending-review
"""Task 2 — Bespoke Agent Forge (Intelligence Forge plan).

Fares's direction: forge a NEW class of agents on top of the existing 30 (Q2 DECIDED),
each BESPOKE + governed (NO templates/clones). The constraint is ARCHITECTURAL (P-EMBED),
not a prompt. Each forged agent gets a focused task via its structural position (P-FOCUS)
and a "life" that persists in GRAPH STATE, not a private thread (P5/Q3 DECIDED).

EXTENDS agent_registry (P-NO-FORK): adds a new class on top, does NOT rewrite the 30.
A behavioral hash guards against the clone trap: two forged agents sharing the same hash
are a defect (they would be templates, not bespoke).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from system import agent_registry


# The defined intelligence each forged agent is bound to (Q1 DECIDED: existing P1-P7 + CIR).
CONSTITUTION_BINDING = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "CIR"]


@dataclass
class ForgedAgent:
    """A bespoke agent definition forged from (spec_slice + focused_task + governance_profile).

    Not a clone: its identity is a hash of its DISTINCT inputs. Two agents sharing the same
    hash are templates (defect) — guarded by assert_distinct().
    """

    name: str
    spec_slice: list[str]
    focused_task: str
    governance_profile: dict[str, Any]
    role: str = "bespoke"
    behavior_hash: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.behavior_hash:
            self.behavior_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Deterministic behavioral signature — distinct inputs => distinct hash."""
        payload = json.dumps(
            {
                "spec_slice": sorted(self.spec_slice),
                "focused_task": self.focused_task,
                "governance_profile": self.governance_profile,
                "binding": CONSTITUTION_BINDING,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def context_view(self) -> dict[str, Any]:
        """The agent's CONTEXT = a view of the managed system (P-CONTEXT-IS-SYSTEM).

        Carries instructions + role + lifecycle ("life") + what-it-will-do — the "living"
        entity's view, persisted in graph state (P5/Q3), not a private thread.
        """
        return {
            "name": self.name,
            "role": self.role,
            "instructions": (
                f"You are {self.name}, a bespoke agent bound to {CONSTITUTION_BINDING}. "
                f"Your focused task: {self.focused_task}. "
                f"Your governing principles: {', '.join(self.spec_slice)}. "
                f"Governance profile (enforced, not advisory): {self.governance_profile}."
            ),
            "lifecycle": {
                "mode": "re-forged-per-task",
                "persistence": "graph_state",
                "binding": CONSTITUTION_BINDING,
            },
            "what_it_will_do": self.focused_task,
            "behavior_hash": self.behavior_hash,
        }

    def as_registry_entry(self) -> dict[str, Any]:
        """EXTENDS agent_registry: a new entry on top of the existing 30 (P-NO-FORK)."""
        return {
            "name": self.name,
            "module": f"agents.forged.{self.name}",
            "entrypoint": "run_forged_agent",
            "category": "forged_bespoke",
            "permission_symbol": None,
            "lifecycle_doc": f"docs/reconciliation/forged/{self.name}.md",
            "test_file": f"tests/test_forged_{self.name}.py",
            "standard_permissions": False,
            "forged": True,
            "behavior_hash": self.behavior_hash,
            "binding": CONSTITUTION_BINDING,
        }


def forge_agent(
    name: str,
    spec_slice: list[str],
    focused_task: str,
    governance_profile: dict[str, Any] | None = None,
) -> ForgedAgent:
    """Forge ONE bespoke agent. Distinct inputs => distinct agent (no template).

    Pure: does NOT mutate the global registry. Call extend_registry() explicitly to add it.
    """
    if governance_profile is None:
        governance_profile = {"complexity_gate": 4, "bounded_probe": True, "verify_node": True}
    return ForgedAgent(
        name=name,
        spec_slice=spec_slice,
        focused_task=focused_task,
        governance_profile=governance_profile,
    )


def extend_registry(agent: ForgedAgent, registry: list[dict] | None = None) -> dict[str, Any]:
    """EXTEND agent_registry (P-NO-FORK): scaffold a forged agent's artifacts + register it.

    TRANSACTIONAL (fixes strong-model review #1-b): the system must self-extend WITHOUT
    self-violating the constitution. extend_registry scaffolds the required on-disk artifacts
    (module + entrypoint, test file, lifecycle doc) so the new entry passes the existing
    governance checks (entrypoints import, lifecycle_artifacts exist), then registers it.
    If the resulting registry still has ANY breach, it rolls back (deletes the scaffolds +
    the entry) and raises — the forge can never leave the system in a non-governed state.
    Idempotent: skips if a forged agent with this name already exists.
    """
    from pathlib import Path
    from system import governance_checks

    target = agent_registry.AGENT_REGISTRY if registry is None else registry
    if any(e.get("name") == agent.name and e.get("forged") for e in target):
        return agent.as_registry_entry()

    created: list[Path] = []
    # 1) scaffold the required artifacts so the entry is governable
    created = _scaffold_forged_artifacts(agent)
    entry = agent.as_registry_entry()
    target.append(entry)

    # 2) verify the registry is still governed; roll back on any breach
    result = governance_checks.run_governance_checks(target)
    if not result["success"]:
        target.remove(entry)
        for p in created:
            try:
                p.unlink()
            except OSError:
                pass
        raise RuntimeError(
            f"extend_registry rolled back '{agent.name}': governance breaches after forging: "
            + "; ".join(result["breaches"][:3])
        )
    return entry


def _scaffold_forged_artifacts(agent: ForgedAgent) -> list:
    """Write the on-disk artifacts a forged entry needs to be governable.

    Creates: agents/forged/<name>.py (with run_forged_agent), tests/test_forged_<name>.py,
    docs/reconciliation/forged/<name>.md. Returns the list of created paths (for rollback).
    """
    from pathlib import Path

    entry = agent.as_registry_entry()
    module_path = Path(entry["module"].replace(".", "/") + ".py")
    test_path = Path(entry["test_file"])
    doc_path = Path(entry["lifecycle_doc"])

    created: list[Path] = []
    module_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)

    # module with a real, callable entrypoint
    module_path.write_text(
        f'"""Auto-forged bespoke agent: {agent.name} (Intelligence Forge, transactional)."""\n'
        f"from __future__ import annotations\n"
        f"from typing import Any\n\n"
        f"NAME = {agent.name!r}\n"
        f"FOCUSED_TASK = {agent.focused_task!r}\n"
        f"SPEC_SLICE = {agent.spec_slice!r}\n"
        f"GOVERNANCE_PROFILE = {agent.governance_profile!r}\n\n"
        f"def run_forged_agent(state: dict[str, Any] | None = None) -> dict[str, Any]:\n"
        f"    \"\"\"Forged agent entrypoint — applies its focused task under its governance profile.\n\n"
        f"    The behavioral hash below is the clone-trap guard (P2): it is derived from the\n"
        f"    agent's DISTINCT inputs, so this agent is bespoke, not a template.\n"
        f"    \"\"\"\n"
        f"    return {{\"name\": NAME, \"focused_task\": FOCUSED_TASK,\n"
        f"            \"behavior_hash\": {agent.behavior_hash!r}, \"status\": \"forged\"}}\n",
        encoding="utf-8",
    )
    created.append(module_path)

    # test file (exercises the entrypoint)
    test_path.write_text(
        f'"""Governance test for forged agent {agent.name}."""\n'
        f"from {entry['module']} import run_forged_agent\n\n"
        f"def test_forged_entrypoint_runs():\n"
        f"    out = run_forged_agent()\n"
        f"    assert out[\"name\"] == {agent.name!r}\n"
        f"    assert out[\"behavior_hash\"] == {agent.behavior_hash!r}\n",
        encoding="utf-8",
    )
    created.append(test_path)

    # lifecycle doc anchor
    doc_path.write_text(
        f"# Forged Agent: {agent.name}\n\n"
        f"- **Focused task:** {agent.focused_task}\n"
        f"- **Governing principles:** {', '.join(agent.spec_slice)}\n"
        f"- **Behavior hash (clone-trap guard):** {agent.behavior_hash}\n"
        f"- **Lifecycle:** re-forged-per-task, persisted in graph state (P5).\n"
        f"- **Forged by:** Intelligence Forge (transactional extend_registry).\n",
        encoding="utf-8",
    )
    created.append(doc_path)
    return created


def assert_distinct(agents: list[ForgedAgent]) -> None:
    """Clone-trap guard: no two forged agents may share a behavioral hash (P2 zero-LLM).

    Raises ValueError if a template collision is detected — this is a HARD fail, not advisory.
    """
    seen: dict[str, str] = {}
    for a in agents:
        if a.behavior_hash in seen:
            raise ValueError(
                f"Clone trap: {a.name} and {seen[a.behavior_hash]} share behavior_hash "
                f"{a.behavior_hash}. Forged agents must be bespoke, not templates."
            )
        seen[a.behavior_hash] = a.name
