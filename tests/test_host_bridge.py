"""Tests for system/host_bridge.py — permission interposition.

Central claims under test:
  1. A mutation is impossible without a declared WRITE scope.
  2. NEVER beats WRITE when a matrix contradicts itself (fail closed).
  3. HUMAN_CHECKPOINT never executes.
  4. Every decision, including every refusal, lands in the audit trail.
  5. The bypass linter actually detects a direct harness mutation.

No network, no LLM.
"""

from __future__ import annotations

import json

import pytest

from system.host_bridge import (
    GOVERNED_ACTIONS,
    REQUIRED_PERMISSION_KEYS,
    BridgeError,
    HostBridge,
    HostRequest,
    Outcome,
    PermissionRefused,
    atomic_append_jsonl,
    check_bridge_interposition,
    find_bridge_bypasses,
    make_harness_handlers,
    validate_matrix,
)

# --------------------------------------------------------------------------
# fixtures / helpers
# --------------------------------------------------------------------------

WRITER_MATRIX = {
    "READ": ["trajectory"],
    "WRITE": ["harness_upsert"],
    "NEVER": ["constitution", "laws"],
    "HUMAN_CHECKPOINT": ["harness_rollback"],
}

CONTRADICTORY_MATRIX = {
    "READ": [],
    # the same scope appears under both WRITE and NEVER
    "WRITE": ["harness_upsert"],
    "NEVER": ["harness_upsert"],
    "HUMAN_CHECKPOINT": [],
}


@pytest.fixture
def bridge():
    b = HostBridge({"refiner": WRITER_MATRIX})
    b.register_handler("harness_upsert", lambda req: {"stored": req.payload.get("title")})
    b.register_handler("harness_rollback", lambda req: True)
    return b


def req(**overrides) -> HostRequest:
    base = dict(actor="refiner", action="harness_upsert", target="harness_upsert", payload={"title": "t"})
    base.update(overrides)
    return HostRequest(**base)


# --------------------------------------------------------------------------
# matrix validation — fail closed
# --------------------------------------------------------------------------


def test_valid_matrix_normalizes_to_string_lists():
    out = validate_matrix({"READ": [1], "WRITE": ["a"], "NEVER": [], "HUMAN_CHECKPOINT": []})
    assert out["READ"] == ["1"]
    assert set(out) == set(REQUIRED_PERMISSION_KEYS)


@pytest.mark.parametrize(
    "matrix",
    [
        None,
        [],
        "READ",
        {"READ": [], "WRITE": []},                                   # missing keys
        {"READ": [], "WRITE": "a", "NEVER": [], "HUMAN_CHECKPOINT": []},  # non-list
    ],
)
def test_malformed_matrix_is_refused_not_coerced(matrix):
    """A permission bug must cost a refused operation, never an unauthorized one."""
    with pytest.raises(BridgeError):
        validate_matrix(matrix, "someone")


def test_register_actor_rejects_a_malformed_matrix():
    b = HostBridge()
    with pytest.raises(BridgeError):
        b.register_actor("bad", {"READ": []})


# --------------------------------------------------------------------------
# request validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [{"actor": ""}, {"action": "   "}, {"target": ""}, {"actor": None}, {"payload": "not a dict"}],
)
def test_request_rejects_structurally_invalid_fields(kwargs):
    with pytest.raises(BridgeError):
        req(**kwargs)


def test_submit_rejects_a_non_request():
    b = HostBridge()
    with pytest.raises(BridgeError):
        b.submit({"actor": "x"})  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# THE core authorization claims
# --------------------------------------------------------------------------


def test_declared_write_scope_is_allowed_and_executes(bridge):
    decision = bridge.submit(req())
    assert decision.outcome is Outcome.ALLOWED
    assert decision.result == {"stored": "t"}


def test_undeclared_target_is_refused_and_does_not_execute(bridge):
    executed = []
    bridge.register_handler("harness_delete", lambda r: executed.append(r))
    decision = bridge.submit(req(action="harness_delete", target="harness_delete"))
    assert decision.outcome is Outcome.REFUSED_NOT_DECLARED
    assert executed == [], "a refused request must never reach its handler"


def test_never_scope_is_refused(bridge):
    decision = bridge.submit(req(target="constitution"))
    assert decision.outcome is Outcome.REFUSED_NEVER
    assert "constitution" in decision.detail


def test_never_beats_write_when_the_matrix_contradicts_itself():
    """Fail closed. A contradictory matrix must refuse, not permit."""
    b = HostBridge({"confused": CONTRADICTORY_MATRIX})
    b.register_handler("harness_upsert", lambda r: "executed")
    decision = b.submit(req(actor="confused"))
    assert decision.outcome is Outcome.REFUSED_NEVER
    assert decision.result is None


def test_human_checkpoint_escalates_and_never_executes(bridge):
    executed = []
    bridge.register_handler("harness_rollback", lambda r: executed.append("ran"))
    decision = bridge.submit(req(action="harness_rollback", target="harness_rollback"))
    assert decision.outcome is Outcome.ESCALATE_HUMAN
    assert decision.needs_human is True
    assert executed == [], "a checkpoint must not be satisfiable by proceeding"


def test_unknown_actor_is_refused(bridge):
    decision = bridge.submit(req(actor="ghost"))
    assert decision.outcome is Outcome.REFUSED_UNKNOWN_ACTOR


def test_missing_handler_is_refused_even_when_authorized():
    b = HostBridge({"refiner": WRITER_MATRIX})  # no handler registered
    decision = b.submit(req())
    assert decision.outcome is Outcome.REFUSED_NO_HANDLER


def test_wildcard_scope_authorizes_broadly():
    b = HostBridge({"orchestrator": {"READ": ["*"], "WRITE": ["*"], "NEVER": [], "HUMAN_CHECKPOINT": []}})
    b.register_handler("anything", lambda r: "ok")
    decision = b.submit(HostRequest(actor="orchestrator", action="anything", target="whatever"))
    assert decision.allowed is True


def test_wildcard_does_not_override_never():
    b = HostBridge({"orchestrator": {"READ": ["*"], "WRITE": ["*"], "NEVER": ["constitution"], "HUMAN_CHECKPOINT": []}})
    b.register_handler("edit", lambda r: "ok")
    decision = b.submit(HostRequest(actor="orchestrator", action="edit", target="constitution"))
    assert decision.outcome is Outcome.REFUSED_NEVER


def test_scope_may_match_action_or_composite_form():
    matrix = {"READ": [], "WRITE": ["harness_upsert:memory"], "NEVER": [], "HUMAN_CHECKPOINT": []}
    b = HostBridge({"a": matrix})
    b.register_handler("harness_upsert", lambda r: "ok")
    assert b.submit(HostRequest(actor="a", action="harness_upsert", target="memory")).allowed is True
    assert b.submit(HostRequest(actor="a", action="harness_upsert", target="skill")).allowed is False


def test_check_is_pure_and_does_not_execute(bridge):
    calls = []
    bridge.register_handler("harness_upsert", lambda r: calls.append(1))
    decision = bridge.check(req())
    assert decision.allowed is True
    assert calls == [], "check() must authorize without executing"


def test_raise_on_refusal_raises_permission_refused(bridge):
    with pytest.raises(PermissionRefused):
        bridge.submit(req(target="constitution"), raise_on_refusal=True)


# --------------------------------------------------------------------------
# failure propagation — Article I.3 "Fail Loudly"
# --------------------------------------------------------------------------


def test_handler_exception_propagates_and_is_recorded(bridge):
    def boom(r):
        raise RuntimeError("disk full")

    bridge.register_handler("harness_upsert", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        bridge.submit(req())
    trail = bridge.audit_trail()
    assert "RuntimeError" in trail[-1].detail, "a raised handler must still be audited"


# --------------------------------------------------------------------------
# audit trail
# --------------------------------------------------------------------------


def test_every_decision_is_audited_including_refusals(bridge):
    bridge.submit(req())                       # allowed
    bridge.submit(req(target="constitution"))  # refused NEVER
    bridge.submit(req(actor="ghost"))          # refused unknown actor
    trail = bridge.audit_trail()
    assert len(trail) == 3
    assert [d.outcome for d in trail] == [
        Outcome.ALLOWED, Outcome.REFUSED_NEVER, Outcome.REFUSED_UNKNOWN_ACTOR,
    ]
    assert len(bridge.refusals()) == 2


def test_audit_trail_is_persisted_as_jsonl(tmp_path):
    path = tmp_path / "bridge-audit.jsonl"
    b = HostBridge({"refiner": WRITER_MATRIX}, audit_path=path)
    b.register_handler("harness_upsert", lambda r: "ok")
    b.submit(req())
    b.submit(req(target="constitution"))

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["outcome"] for r in rows] == ["allowed", "refused_never"]
    assert all(r["actor"] == "refiner" and r["created_at"] for r in rows)


def test_unwritable_audit_path_does_not_abort_the_run(tmp_path):
    """A broken audit log degrades observability; it must not become a new failure."""
    blocked = tmp_path / "file"
    blocked.write_text("x")
    b = HostBridge({"refiner": WRITER_MATRIX}, audit_path=blocked / "nested" / "a.jsonl")
    b.register_handler("harness_upsert", lambda r: "ok")
    assert b.submit(req()).allowed is True
    assert len(b.audit_trail()) == 1


def test_decision_to_dict_is_json_serializable(bridge):
    payload = json.loads(json.dumps(bridge.submit(req()).to_dict()))
    assert payload["outcome"] == "allowed"


# --------------------------------------------------------------------------
# harness integration
# --------------------------------------------------------------------------


class _StubHarness:
    def __init__(self):
        self.upserts = []
        self.refinements = []
        self.rollbacks = []

    def upsert(self, kind, title, content, **kw):
        self.upserts.append((kind, title, kw.get("require_evidence")))
        return {"id": "e1"}

    def record_refinement(self, trigger, changes, **kw):
        self.refinements.append((trigger, changes, kw.get("evidence")))
        return {"id": "refine_0001"}

    def rollback(self, refinement_id):
        self.rollbacks.append(refinement_id)
        return True


def _wired(harness, matrix=None):
    b = HostBridge({"refiner": matrix or {
        "READ": [], "WRITE": list(GOVERNED_ACTIONS), "NEVER": ["constitution"], "HUMAN_CHECKPOINT": [],
    }})
    for action, handler in make_harness_handlers(harness).items():
        b.register_handler(action, handler)
    return b


def test_harness_upsert_through_bridge_passes_evidence_through():
    h = _StubHarness()
    b = _wired(h)
    decision = b.submit(HostRequest(
        actor="refiner", action="harness_upsert", target="harness_upsert",
        payload={"kind": "memory", "title": "t", "content": "c", "evidence": "exit code 1"},
    ))
    assert decision.allowed is True
    assert h.upserts == [("memory", "t", "exit code 1")]


def test_harness_upsert_without_evidence_is_refused_by_the_handler():
    """Law 16: evidence is not optional, even for an authorized actor."""
    h = _StubHarness()
    b = _wired(h)
    with pytest.raises(PermissionRefused):
        b.submit(HostRequest(
            actor="refiner", action="harness_upsert", target="harness_upsert",
            payload={"kind": "memory", "title": "t", "content": "c", "evidence": "  "},
        ))
    assert h.upserts == []


def test_all_governed_actions_are_wired():
    h = _StubHarness()
    b = _wired(h)
    for action in GOVERNED_ACTIONS:
        assert action in b.known_actions(), f"{action} has no handler"


def test_rollback_routes_through_the_bridge():
    h = _StubHarness()
    b = _wired(h)
    b.submit(HostRequest(
        actor="refiner", action="harness_rollback", target="harness_rollback",
        payload={"refinement_id": "refine_0001"},
    ))
    assert h.rollbacks == ["refine_0001"]


# --------------------------------------------------------------------------
# bypass linter
# --------------------------------------------------------------------------


def test_bypass_linter_flags_a_direct_harness_mutation(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "rogue.py").write_text(
        "from system.continual_harness import ContinualHarness\n"
        "def go():\n"
        "    harness = ContinualHarness('s.json')\n"
        "    harness.upsert('memory', 't', 'c')\n"
    )
    findings = find_bridge_bypasses(tmp_path)
    assert any("rogue.py" in f and "upsert(" in f for f in findings)


def test_bypass_linter_ignores_comments_and_exempt_modules(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "continual_harness.py").write_text("harness.upsert('a','b','c')\n")
    (tmp_path / "system" / "host_bridge.py").write_text("harness.rollback('x')\n")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "clean.py").write_text("# harness.upsert(...) is routed via the bridge\n")
    assert find_bridge_bypasses(tmp_path) == []


def test_bypass_linter_skips_files_that_never_mention_harness(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "other.py").write_text("def upsert(a):\n    return a\n")
    assert find_bridge_bypasses(tmp_path) == []


def test_check_bridge_interposition_returns_governance_check_shape(tmp_path):
    result = check_bridge_interposition(tmp_path)
    assert set(result) == {"name", "passed", "breaches"}
    assert result["name"] == "bridge_interposition"
    assert result["passed"] is True


def test_check_bridge_interposition_reports_breaches(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "rogue.py").write_text("harness.record_refinement('t', [])\n")
    result = check_bridge_interposition(tmp_path)
    assert result["passed"] is False
    assert any("outside HostBridge" in b for b in result["breaches"])


# --------------------------------------------------------------------------
# durable append
# --------------------------------------------------------------------------


def test_atomic_append_jsonl_appends_without_truncating(tmp_path):
    path = tmp_path / "trail.jsonl"
    atomic_append_jsonl(path, {"n": 1})
    atomic_append_jsonl(path, {"n": 2})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["n"] for r in rows] == [1, 2]


def test_atomic_append_creates_parent_directories(tmp_path):
    path = tmp_path / "deep" / "nested" / "trail.jsonl"
    atomic_append_jsonl(path, {"ok": True})
    assert path.exists()
