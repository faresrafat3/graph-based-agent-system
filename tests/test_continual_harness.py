"""Tests for system/continual_harness.py (Track B / ADR-0001).

Covers: CRUD, mtime resync, field protection, corrupt-JSON, evidence gate,
rollback, ledger mirror, and the hard governance invariant that the harness
NEVER mutates CONSTITUTION.md / LAWS.md (Ruling C1: no second authority).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from system.continual_harness import ContinualHarness, HarnessError, _atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
CONSTITUTION = ROOT / "CONSTITUTION.md"
LAWS = ROOT / "LAWS.md"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_atomic_write_never_leaves_partial(tmp_path):
    target = tmp_path / "h.json"
    _atomic_write_json(target, {"x": 1})
    assert target.exists()
    assert json.loads(target.read_text()) == {"x": 1}


def test_upsert_and_get(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    e = h.upsert("memory", "login tip", "use OAuth", id="m1")
    assert e.id == "m1"
    assert h.get("memory", "m1").content == "use OAuth"
    assert len(h.list()) == 1


def test_evidence_required_gate(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    with pytest.raises(HarnessError):
        h.record_refinement("loop", ["change x"], evidence="")  # Law 16
    ev = h.record_refinement("loop", ["change x"], evidence="benchmark delta +3%")
    assert ev.evidence
    assert h.refinements[0].id == ev.id


def test_field_protection_none_keeps_existing(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.upsert("memory", "t", "v1", id="x", reference={"a": 1})
    h.upsert("memory", "t", "v2", id="x")  # no reference passed -> kept
    assert h.get("memory", "x").reference == {"a": 1}
    assert h.get("memory", "x").content == "v2"
    h.upsert("memory", "t", "v3", id="x", reference={})  # explicit overrides
    assert h.get("memory", "x").reference == {}


def test_mtime_resync_picks_up_external_edit(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.upsert("memory", "a", "1", id="a")
    data = {"schema": 1, "entries": {"memory": {"b": {"id": "b", "kind": "memory",
            "title": "b", "content": "2", "path": "general", "scope": "local",
            "reference": {}, "arguments": {}, "metadata": {}, "source": "agent"}},
            "prompt": {}, "skill": {}, "subagent": {}}, "refinements": []}
    (tmp_path / "harness_state.json").write_text(json.dumps(data))
    os.utime(tmp_path / "harness_state.json", None)
    h2 = ContinualHarness(tmp_path / "harness_state.json")
    assert h2.get("memory", "b") is not None
    assert h2.get("memory", "a") is None


def test_corrupt_json_does_not_crash(tmp_path):
    p = tmp_path / "harness_state.json"
    p.write_text("{not valid json")
    h = ContinualHarness(p)  # must not raise
    assert h.list() == []
    h.upsert("memory", "recovered", "yes", id="r")
    assert h.get("memory", "r") is not None


def test_rollback_restores_snapshot(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.upsert("memory", "orig", "v1", id="o")
    ev = h.record_refinement("loop", ["edit o"], evidence="delta ok")
    h.upsert("memory", "orig", "v2-changed", id="o")
    assert h.get("memory", "o").content == "v2-changed"
    assert h.rollback(ev.id)
    assert h.get("memory", "o").content == "v1"


def test_ledger_mirror_is_proposed_only(tmp_path):
    ledger = tmp_path / "distillation_ledger.jsonl"
    h = ContinualHarness(tmp_path / "harness_state.json", ledger_path=ledger)
    h.record_refinement("loop", ["x"], evidence="bench +2%")
    lines = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert lines
    assert lines[0]["type"] == "harness_refinement"
    assert lines[0]["status"] == "proposed"  # Ruling C1: propose-only


def test_harness_never_mutates_constitution_or_laws(tmp_path):
    """Hard governance invariant (Ruling C1 / Law 2)."""
    c_before = _sha(CONSTITUTION)
    l_before = _sha(LAWS)
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.upsert("prompt", "p", "content", id="p1")
    h.record_refinement("loop", ["anything"], evidence="evidence")
    h.upsert("subagent", "s", "spec", id="s1")
    h.rollback(h.refinements[0].id)
    assert _sha(CONSTITUTION) == c_before
    assert _sha(LAWS) == l_before


def test_flagged_for_review_on_untrusted_source(tmp_path):
    h = ContinualHarness(tmp_path / "harness_state.json")
    h.upsert("memory", "ok", "v", id="ok", source="agent")
    h.upsert("memory", "untrusted", "v", id="u", source="external")
    flagged = {e.id for e in h.flagged_for_review()}
    assert "u" in flagged
    assert "ok" not in flagged
