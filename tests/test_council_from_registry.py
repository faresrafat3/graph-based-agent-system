"""TDD test: Sage Council built from the REAL agent registry (not a mock).

Fares's direction: apply the methodology (CIR + consensus) to the ACTUAL project agents, not
a parallel mock. These tests confirm build_council_from_registry reads AGENT_REGISTRY and
produces a coherent council of category-sages weighted by category.
"""

from agents.sage_council import build_council_from_registry, SageCouncil
from system.agent_registry import AGENT_REGISTRY


def test_council_from_registry_has_multiple_category_sages():
    c = build_council_from_registry()
    assert isinstance(c, SageCouncil)
    assert len(c.sages) >= 5  # several categories represented
    roles = {s.role for s in c.sages}
    # governance + at least one execution-type category should be present
    assert "governance" in roles


def test_council_from_registry_excludes_self_systems_layer():
    c = build_council_from_registry()
    names = {s.name for s in c.sages}
    # the council lives inside the systems layer; it must not self-include
    assert "Systems Layer (Meta-Loop)" not in names


def test_council_from_registry_weights_by_category():
    c = build_council_from_registry()
    by_role = {s.role: s.weight for s in c.sages}
    # governance should out-weight execution per _CATEGORY_WEIGHT
    if "governance" in by_role and "execution" in by_role:
        assert by_role["governance"] > by_role["execution"]


def test_council_from_registry_convenes_on_complex_signal():
    c = build_council_from_registry()
    out = c.convene({"complexity_score": 9, "repeated_hypothesis_count": 1,
                     "breach_count": 1, "success_rate": 60})
    assert out["convened"] is True
    assert len(out["views"]) == len(c.sages)
    assert "FALSIFICATION" in out["reconciled_spec"]
