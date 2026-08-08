# version: v1 | 2026-08-08 | verdict: pending-review
"""Port-fidelity tests for system/continual_harness.py.

These assert that our Python-native port preserves the load-bearing semantics of
prime-agent's `prime-agent-runtime/src/rlm/harness.py` (MIT, Prime Intellect 2026).
Each test names the upstream file:line it is protecting, so a future edit that
"simplifies" the port fails loudly instead of silently diverging.

PORTED-FROM: prime-agent-runtime/src/rlm/harness.py @ prime-agent v0.7.x
"""

from __future__ import annotations

import json

import pytest

from system.continual_harness import (
    VALID_SCOPES,
    ContinualHarness,
    HarnessError,
)


def _write_state(path, entries: dict, refinements: list | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": 1, "entries": entries, "refinements": refinements or []}),
        encoding="utf-8",
    )


# --- fidelity: value coercion (harness.py:237-245) ---------------------------


def test_version_string_is_coerced_to_int(tmp_path):
    """harness.py:238-245 coerces a str version to int; a bad str falls back to 1."""
    state = tmp_path / "harness_state.json"
    _write_state(state, {"memory": {"m1": {"title": "t", "content": "c", "version": "3"}}})
    h = ContinualHarness(state)
    entry = h.get("memory", "m1")
    assert entry is not None
    assert entry.version == 3, "string version must coerce to int, not reset to 1"


def test_unparseable_version_falls_back_to_one(tmp_path):
    """harness.py:239-244: int() failure degrades to 1 rather than raising."""
    state = tmp_path / "harness_state.json"
    _write_state(state, {"memory": {"m1": {"title": "t", "content": "c", "version": "abc"}}})
    h = ContinualHarness(state)
    entry = h.get("memory", "m1")
    assert entry is not None
    assert entry.version == 1


# --- fidelity: scope must stay a valid HarnessScope (harness.py:233-234) -----


def test_missing_scope_defaults_to_a_valid_scope(tmp_path):
    """harness.py:233-234 falls back to the store's own scope, never to a stray string.

    Regression: the port used `state_path.parent.name`, so an entry stored under a
    directory named e.g. `sub/` loaded with scope='sub' — not a member of VALID_SCOPES.
    """
    state = tmp_path / "sub" / "harness_state.json"
    _write_state(state, {"memory": {"m1": {"title": "t", "content": "c"}}})
    h = ContinualHarness(state)
    entry = h.get("memory", "m1")
    assert entry is not None
    assert entry.scope in VALID_SCOPES, f"scope {entry.scope!r} is not a valid HarnessScope"


def test_invalid_scope_value_is_normalised(tmp_path):
    """An explicit but bogus scope on disk must not survive the load."""
    state = tmp_path / "harness_state.json"
    _write_state(state, {"memory": {"m1": {"title": "t", "content": "c", "scope": "wobble"}}})
    h = ContinualHarness(state)
    entry = h.get("memory", "m1")
    assert entry is not None
    assert entry.scope in VALID_SCOPES


# --- fidelity: create is create-or-FAIL (harness.py:437-482) ----------------


def test_create_rejects_an_existing_id(tmp_path):
    """harness.py:470-471 raises when the id already exists; upsert is the lenient path."""
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.create("memory", "Title", "body", id="m1")
    with pytest.raises(HarnessError):
        h.create("memory", "Other", "other body", id="m1")


def test_create_then_get_roundtrip(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    created = h.create("memory", "Title", "body", id="m1")
    assert created.version == 1
    fetched = h.get("memory", "m1")
    assert fetched is not None and fetched.content == "body"


# --- fidelity: update is update-or-FAIL, and preserves omitted fields --------


def test_update_rejects_a_missing_id(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    with pytest.raises(HarnessError):
        h.update("memory", "nope", "Title", "body")


def test_update_preserves_omitted_fields(tmp_path):
    """harness.py:369-380: None preserves path/reference/arguments/metadata."""
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.create(
        "skill",
        "Sk",
        "body",
        id="s1",
        path="grouped",
        reference={"type": "python", "import": "x", "callable": "y"},
        arguments={"a": 1},
        metadata={"m": 2},
    )
    h.update("skill", "s1", "Sk2", "body2")
    entry = h.get("skill", "s1")
    assert entry is not None
    assert entry.title == "Sk2" and entry.content == "body2"
    assert entry.path == "grouped", "omitted path must be preserved"
    assert entry.reference == {"type": "python", "import": "x", "callable": "y"}
    assert entry.arguments == {"a": 1}
    assert entry.metadata == {"m": 2}
    assert entry.version == 2, "an update bumps the version"


def test_update_with_explicit_empty_dict_overrides(tmp_path):
    """harness.py:372-373: an explicit value — including {} — still overwrites."""
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.create("memory", "M", "body", id="m1", metadata={"m": 2})
    h.update("memory", "m1", "M", "body", metadata={})
    entry = h.get("memory", "m1")
    assert entry is not None
    assert entry.metadata == {}, "explicit {} must override, not be treated as omitted"


# --- fidelity: scope-prefixed ids (harness.py:59-67) ------------------------


def test_scope_prefixed_id_is_accepted_verbatim(tmp_path):
    """harness.py:59-67 accepts the `local:`/`global:` ids that overview() renders."""
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.create("memory", "M", "body", id="m1")
    assert h.get("memory", "local:m1") is not None, "a local: prefix must resolve"


# --- fidelity: python skill reference validation (harness.py:128-138) -------


def test_skill_reference_requires_python_contract(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    with pytest.raises(HarnessError):
        h.create("skill", "Sk", "body", id="s1", reference={"type": "shell"})
    with pytest.raises(HarnessError):
        h.create("skill", "Sk", "body", id="s2", reference={"type": "python"})
    ok = h.create(
        "skill", "Sk", "body", id="s3",
        reference={"type": "python", "import": "pkg.mod", "callable": "fn"},
    )
    assert ok.reference["import"] == "pkg.mod"


# --- governance: the harness may never touch the authority documents --------


def test_harness_never_writes_authority_files(tmp_path):
    """CONSTITUTION/LAWS are immutable; the harness is a complementary layer only."""
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.create("prompt", "P", "body", id="p1")
    h.record_refinement("t", ["c"], evidence="e")
    written = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert "CONSTITUTION.md" not in written
    assert "LAWS.md" not in written
