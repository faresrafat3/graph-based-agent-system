"""Tests for the forge node on the live pipeline path (P7 opt-in).

These exist because an exercise run found a real defect that the whole suite missed:
forge_node populated state["forge_result"], but finalize_node built final_result from an
explicit field list that omitted it — so the node ran and its output was silently dropped
before reaching the caller. Wiring a module in is not the same as exercising it; nothing
here was covered by any test until that run.

Kept LLM-free: forge_node's council is local (build_council_from_registry), so the node
is tested directly against a synthetic state rather than through a full pipeline run.
"""

from typing import cast

from agents.karpathy_pipeline import KarpathyPipelineState, finalize_node, forge_node

TASKS = [
    {"id": "task_1", "description": "Design the schema", "acceptance_criteria": ["schema designed"]},
    {"id": "task_2", "description": "Implement registration", "acceptance_criteria": ["passwords hashed"]},
]


def _state(**over) -> KarpathyPipelineState:
    base = {
        "requirements": "Build an API",
        "project_context": "FastAPI",
        "constraints": "",
        "forge_agent_graph": True,
        "decomposition": {"tasks": TASKS},
        "assignment": {"assignments": {}, "execution_plan": []},
        "pipeline_success": True,
        "combined_breaches": [],
        "attempt": 0,
        "forge_result": {},
    }
    base.update(over)
    return cast(KarpathyPipelineState, base)


def test_forge_node_default_deny_when_flag_off():
    out = forge_node(_state(forge_agent_graph=False))
    assert out["forge_result"]["enabled"] is False
    assert "default-deny" in out["forge_result"]["reason"]


def test_forge_node_forges_bespoke_agents_when_enabled():
    res = forge_node(_state())["forge_result"]
    assert res["enabled"] is True
    assert res["forged"] >= 1
    # Bespoke, not role-play clones: one distinct agent per task, named from the task.
    assert len(set(res["agent_names"])) == res["forged"]


def test_forge_node_context_is_the_whole_system_not_a_prompt_blob():
    res = forge_node(_state())["forge_result"]
    assert res["context_is_system"] is True
    assert all(c > 0 for c in res["context_peer_counts"])


def test_forge_node_topology_carries_verify_and_escalate_edges():
    topo = forge_node(_state())["forge_result"]["topology"]
    kinds = {e["kind"] for e in topo["edges"]}
    # Constraints are architectural (edges), not instructions in a prompt.
    assert {"focus", "verify", "escalate"} <= kinds
    assert topo["extends"] == "systems_layer"  # extends governance, never a 2nd authority


def test_forge_node_uses_the_real_registry_council_not_the_mock():
    """council_size reflects the project registry, not sage_council's 3-sage default."""
    res = forge_node(_state())["forge_result"]
    assert res["council_size"] > 3


def test_council_is_complexity_gated_in_both_directions():
    """A trivial plan must not summon the council; a complex one must.

    The gate is the point: deliberation is spent where variety demands it, so a
    2-task plan staying silent is correct behaviour, not a missing convening.
    """
    trivial = forge_node(_state())["forge_result"]
    assert trivial["council_convened"] is False

    many = [
        {"id": f"task_{i}", "description": f"Step {i}", "acceptance_criteria": [f"crit {i}"]}
        for i in range(6)
    ]
    complex_ = forge_node(_state(decomposition={"tasks": many}))["forge_result"]
    assert complex_["council_convened"] is True
    assert complex_["reconciled_spec"]


def test_finalize_node_surfaces_forge_result_to_the_caller():
    """Regression: the exercise-run defect — forge ran, output dropped by finalize."""
    forged = forge_node(_state())["forge_result"]
    final = finalize_node(
        _state(
            forge_result=forged,
            curated={"signal_to_noise_ratio": 1.0},
            validation={"quality_score": 1.0},
            quality_review={"quality_score": 1.0},
            combined_breaches=[],
            attempt=0,
            domain_dispatch_result={},
            graph_execution_result={},
            executed_modules=[],
            early_error=None,
        )
    )["final_result"]
    assert final["forge"] == forged
    assert final["forge"]["enabled"] is True
