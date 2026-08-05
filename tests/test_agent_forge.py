"""TDD tests for Task 2 — Bespoke Agent Forge (no templates, EXTEND registry, clone-trap guard).

Verifies: forged agents are bespoke (distinct hash), extend (not rewrite) the registry,
carry a context-view (instructions + role + lifecycle), and a clone collision is HARD-failed.
"""

import os

import pytest

from agents.agent_forge import (
    forge_agent,
    extend_registry,
    assert_distinct,
    ForgedAgent,
    CONSTITUTION_BINDING,
)
from system import agent_registry as reg


def _count_forged(registry):
    return sum(1 for e in registry if e.get("forged"))


def _cleanup_forge(name):
    """Remove any forged registry entry + its on-disk artifacts (module/test/doc)."""
    reg.AGENT_REGISTRY[:] = [
        e for e in reg.AGENT_REGISTRY
        if not (e.get("forged") and e.get("name") == name)
    ]
    for p in (f"agents/forged/{name}.py", f"tests/test_forged_{name}.py",
              f"docs/reconciliation/forged/{name}.md"):
        if os.path.exists(p):
            os.remove(p)


def test_forge_produces_bespoke_agent_with_context_view():
    a = forge_agent(
        name="security_thinker",
        spec_slice=["P3", "P4"],
        focused_task="probe auth edge cases",
        governance_profile={"complexity_gate": 6, "bounded_probe": True},
    )
    view = a.context_view()
    assert view["name"] == "security_thinker"
    assert "bespoke agent bound to" in view["instructions"]
    assert "P3" in view["instructions"] and "P4" in view["instructions"]
    assert view["lifecycle"]["persistence"] == "graph_state"
    assert view["what_it_will_do"] == "probe auth edge cases"
    assert CONSTITUTION_BINDING  # bound to existing P1-P7+CIR (Q1)


def test_forge_extends_registry_does_not_rewrite():
    non_forged_before = sum(1 for e in reg.AGENT_REGISTRY if not e.get("forged"))
    forged_before = _count_forged(reg.AGENT_REGISTRY)
    try:
        a = forge_agent("temp_probe_a", ["P4"], "bounded probe X")
        extend_registry(a)
        non_forged_after = sum(1 for e in reg.AGENT_REGISTRY if not e.get("forged"))
        forged_after = _count_forged(reg.AGENT_REGISTRY)
        # exactly one NEW forged entry added; the original (non-forged) agents are untouched
        assert forged_after == forged_before + 1
        assert non_forged_after == non_forged_before
    finally:
        _cleanup_forge("temp_probe_a")


def test_forge_is_idempotent_same_name():
    try:
        a = forge_agent("temp_probe_b", ["P1"], "variety check")
        extend_registry(a)
        n1 = _count_forged(reg.AGENT_REGISTRY)
        extend_registry(a)  # same name -> no double add
        n2 = _count_forged(reg.AGENT_REGISTRY)
        assert n1 == n2
    finally:
        _cleanup_forge("temp_probe_b")


def test_distinct_inputs_yield_distinct_hashes():
    a = ForgedAgent("x", ["P1"], "task alpha", {"g": 1})
    b = ForgedAgent("y", ["P1"], "task beta", {"g": 1})  # different focused_task
    assert a.behavior_hash != b.behavior_hash
    assert_distinct([a, b])  # no collision -> passes


def test_clone_trap_guard_hard_fails_on_shared_hash():
    # Two agents with IDENTICAL inputs would collide -> must raise (no template allowed).
    a = ForgedAgent("dup1", ["P4"], "same task", {"g": 1})
    b = ForgedAgent("dup2", ["P4"], "same task", {"g": 1})
    with pytest.raises(ValueError):
        assert_distinct([a, b])


def test_context_view_persists_life_in_graph_state():
    a = forge_agent("life_agent", ["P5"], "serialize reasoning")
    view = a.context_view()
    assert view["lifecycle"]["mode"] == "re-forged-per-task"
    assert view["lifecycle"]["persistence"] == "graph_state"
