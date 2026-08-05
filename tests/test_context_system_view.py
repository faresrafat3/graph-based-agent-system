"""TDD tests for Task 3 — Context-as-System view (extends existing graph state, no fork).

Verifies the built context exposes the WHOLE managed system (cycle_log + peers + binding),
not a trimmed stub, and reuses EXISTING state (no parallel store).
"""

from agents.agent_forge import forge_agent
from agents.context_system_view import build_context_view, context_includes_system


def _agent():
    return forge_agent("ctx_agent", ["P3", "P5"], "serialize reasoning to state")


def test_context_view_exposes_system_not_stub():
    a = _agent()
    graph_state = {"cycle_log": ["measure: x", "compare: y"], "current_measurement": {"complexity_score": 9}}
    view = build_context_view(a, graph_state)
    sc = view["system_context"]
    # system life (P5)
    assert sc["cycle_log"] == ["measure: x", "compare: y"]
    # peers from the REAL registry (many bespoke agents)
    assert len(sc["peer_agents"]) >= 5
    assert all("name" in p and "category" in p for p in sc["peer_agents"])
    # constitution binding present
    assert "P3" in str(sc["constitution_binding"]) or "P1" in str(sc["constitution_binding"])
    # graph state keys exposed
    assert "cycle_log" in sc["graph_state_keys"]


def test_context_includes_system_auditable_check_passes():
    a = _agent()
    assert context_includes_system(a, {"cycle_log": ["m"]}) is True
    # empty graph state still has a (possibly empty) cycle_log list -> still system-shaped
    assert context_includes_system(a, {}) is True


def test_context_view_extends_not_replaces_own_view():
    a = _agent()
    view = build_context_view(a, {"cycle_log": ["x"]})
    # the agent's own identity survives the merge (extends, not replaces)
    assert view["name"] == "ctx_agent"
    assert view["lifecycle"]["persistence"] == "graph_state"
    assert view["context_is_system"] is True


def test_context_peer_list_is_bounded():
    a = _agent()
    view = build_context_view(a, {"cycle_log": []})
    # capped at 20 to keep context observable (P2), not unbounded
    assert len(view["system_context"]["peer_agents"]) <= 20
