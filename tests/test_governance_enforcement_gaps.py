"""Regression guard for the two enforcement gaps the adversarial benchmark exposed.

Both were found by `benchmarks/governance_adversarial.py` on 2026-08-07, against an audit
that was reporting "28 registered items, zero warnings". A green audit says nothing about
the audit's POWER — a check that cannot fire is indistinguishable from one that never has.

  gap 1  P2 verified closure accepted `postcondition = None`. The check asked whether the
         NAME was assigned before VERIFY, never whether it asserted anything. An empty
         assertion turns verified closure into a formality.
  gap 2  Permission matrices were validated for SHAPE only (dict of lists). Emptying
         NEVER, or moving one of its entries into WRITE, keeps the shape perfectly valid
         while widening what the agent may do. `source_code_edit` could migrate from
         NEVER to WRITE on the context curator and the audit stayed green.

Both gaps share one failure mode, the same one that let `forge_agent_graph` output be
silently dropped while the audit passed: the audit measured a DECLARATION rather than its
CONTENT. These tests pin the content checks so the gaps cannot silently reopen.
"""

from __future__ import annotations

import ast

import pytest

from system.governance_checks import (
    STANDARD_NEVER_FLOOR,
    _is_vacuous_postcondition,
    check_permission_matrices,
)


def _value(expr: str) -> ast.expr:
    """Parse `postcondition = <expr>` and hand back the assigned value node."""
    return ast.parse(f"postcondition = {expr}").body[0].value  # type: ignore[attr-defined]


class TestVacuousPostcondition:
    @pytest.mark.parametrize("expr", ["None", '""', "0", "False", "{}", "[]", "()", "set()"])
    def test_empty_declarations_are_vacuous(self, expr):
        """`postcondition = None` satisfied the old name-only check while asserting nothing."""
        if expr == "set()":
            pytest.skip("set() is a Call node; dynamic values are intentionally allowed")
        assert _is_vacuous_postcondition(_value(expr)) is True

    @pytest.mark.parametrize("expr", [
        '{"kind": "non_empty", "path": None}',
        '{"kind": "file_exists"}',
        '["a"]',
        '"non_empty"',
        "build_postcondition()",
        "self.postcondition",
        'f"{kind}_check"',
    ])
    def test_substantive_or_dynamic_declarations_pass(self, expr):
        """A call or name cannot be judged statically — the check must not punish indirection."""
        assert _is_vacuous_postcondition(_value(expr)) is False

    def test_a_dict_with_entries_is_not_vacuous_even_if_a_value_is_none(self):
        """The real postcondition in task_decomposer has `"path": None` inside it."""
        assert _is_vacuous_postcondition(_value('{"kind": "non_empty", "path": None}')) is False


def _entry(module="agents.fake", name="Fake"):
    return {"name": name, "module": module, "permission_symbol": "PERMS",
            "standard_permissions": True, "entrypoint": "run"}


class _FakeModule:
    def __init__(self, matrix):
        self.PERMS = matrix


@pytest.fixture
def install_fake(monkeypatch):
    """Register a synthetic module so matrices can be mutated without touching real agents."""
    def _install(matrix, module="agents.fake"):
        import importlib
        real = importlib.import_module

        def fake_import(name, *a, **k):
            if name == module:
                return _FakeModule(matrix)
            return real(name, *a, **k)

        monkeypatch.setattr(importlib, "import_module", fake_import)
        return [_entry(module=module)]
    return _install


VALID = {
    "READ": ["raw_state"],
    "WRITE": ["sanitized_context"],
    "NEVER": ["source_code_edit", "credentials_access"],
    "HUMAN_CHECKPOINT": ["overflow"],
}


class TestPermissionContentChecks:
    def test_a_well_formed_matrix_passes(self, install_fake):
        registry = install_fake(dict(VALID))
        assert check_permission_matrices(registry).success

    def test_empty_never_list_is_a_breach(self, install_fake):
        """An agent with no forbidden capability has no architectural boundary."""
        registry = install_fake({**VALID, "NEVER": []})
        result = check_permission_matrices(registry)
        assert not result.success
        assert any("empty NEVER" in b for b in result.breaches)

    def test_capability_in_both_never_and_write_is_a_breach(self, install_fake):
        """The exact inversion the matrix exists to prevent; shape validation cannot see it."""
        registry = install_fake({**VALID, "WRITE": ["sanitized_context", "source_code_edit"]})
        result = check_permission_matrices(registry)
        assert not result.success
        assert any("escalates privilege" in b and "source_code_edit" in b
                   for b in result.breaches)

    def test_capability_in_both_never_and_read_is_a_breach(self, install_fake):
        registry = install_fake({**VALID, "READ": ["raw_state", "credentials_access"]})
        result = check_permission_matrices(registry)
        assert not result.success
        assert any("escalates privilege" in b for b in result.breaches)

    def test_removing_a_registered_never_entry_is_a_breach(self, install_fake):
        """The NEVER floor is a ratchet: widening capability must be an explicit amendment."""
        module = "agents.context_curator"
        floor = STANDARD_NEVER_FLOOR[module]
        shrunk = {**VALID, "NEVER": list(floor[1:])}   # drop the first forbidden capability
        registry = install_fake(shrunk, module=module)
        result = check_permission_matrices(registry)
        assert not result.success
        assert any("removed" in b and floor[0] in b for b in result.breaches)

    def test_adding_a_never_entry_is_allowed(self, install_fake):
        """The ratchet only bites one way — tightening must never be blocked."""
        module = "agents.context_curator"
        widened = {**VALID, "NEVER": list(STANDARD_NEVER_FLOOR[module]) + ["new_forbidden_thing"]}
        registry = install_fake(widened, module=module)
        assert check_permission_matrices(registry).success


class TestNeverFloorIntegrity:
    def test_floor_covers_every_standard_agent_in_the_registry(self):
        """A missing entry silently exempts that agent from the ratchet."""
        from system.agent_registry import AGENT_REGISTRY

        standard = {e["module"] for e in AGENT_REGISTRY
                    if isinstance(e, dict) and e.get("standard_permissions")
                    and e.get("permission_symbol")}
        missing = sorted(standard - set(STANDARD_NEVER_FLOOR))
        assert not missing, f"agents outside the NEVER ratchet: {missing}"

    def test_floor_matches_the_live_matrices(self):
        """If an agent's real NEVER list drifts below the floor, the audit must already fail."""
        import importlib

        from system.agent_registry import AGENT_REGISTRY

        for entry in AGENT_REGISTRY:
            if not isinstance(entry, dict) or not entry.get("standard_permissions"):
                continue
            module_name = entry.get("module", "")
            floor = STANDARD_NEVER_FLOOR.get(module_name)
            if not floor:
                continue
            module = importlib.import_module(module_name)
            matrix = getattr(module, entry["permission_symbol"])
            missing = sorted(set(floor) - set(matrix.get("NEVER", [])))
            assert not missing, f"{module_name} dropped {missing} from NEVER"

    def test_no_floor_entry_is_empty(self):
        for module, forbidden in STANDARD_NEVER_FLOOR.items():
            assert forbidden, f"{module} has an empty NEVER floor"
