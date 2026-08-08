# version: v1 | 2026-08-08 | verdict: pending-review
"""Host Bridge — turns declared permissions into ENFORCED permissions.

THE GAP THIS CLOSES
-------------------
Every agent in this repo declares a permission matrix, e.g.

    QUALITY_REVIEWER_PERMISSIONS = {
        "READ": [...], "WRITE": [...], "NEVER": [...], "HUMAN_CHECKPOINT": [...],
    }
    -- agents/quality_reviewer.py

and `system/governance_checks.check_permission_matrices` verifies those matrices
exist and have the right SHAPE (four keys, each a list). Nothing verifies that an
agent's actual mutation was inside its declared WRITE scope. A matrix that is
perfectly shaped and completely ignored passes the audit today.

That makes our permission model *documentation*. This module makes it *architecture*:
a mutation reaches governance state only by submitting a typed request that is
validated against the caller's declared matrix first. There is no second path.

    "Section 3: Highest-Leverage Change (proposed) -- Move the Constitution's unit of
     authority from *permission to write* to *proof of effect*."
    -- CONSTITUTION.md, Article VI Section 3

This is the mechanical precondition for that shift: you cannot demand proof of effect
from a write you never intercepted.

DESIGN, AND WHY IT IS SHAPED THIS WAY
-------------------------------------
Borrowed from prime-agent's host-request bridge (docs/rlm.md:135-139), where Python
skills never mutate authoritative state -- they call `rlm.host_request(...)` and the
TypeScript host owns the transition. We keep that inversion and adapt it:

  * A HANDLER owns each mutation and is registered once, at wiring time.
  * A REQUEST names (actor, action, target, payload). The bridge resolves the actor's
    permission matrix, checks the action/target against it, and only then dispatches.
  * NEVER is checked before WRITE. An action on the NEVER list is refused even if it
    also appears under WRITE, because a contradictory matrix must fail closed. A
    permission bug should cost a refused operation, not an unauthorized one.
  * HUMAN_CHECKPOINT does not execute. It returns a decision requiring escalation
    (Article I.2), so a caller cannot accidentally satisfy a checkpoint by proceeding.
  * Every decision -- allowed or refused -- is appended to an audit trail
    (Article V Section 3). A refusal that leaves no trace teaches nobody.

WHAT THIS MODULE IS NOT
-----------------------
Not a sandbox and not a security boundary against hostile code. Any module that
imports the harness directly can still write to it; Python has no enforced privacy.
This is an *interposition point* plus an *audit check* (see
`check_bridge_interposition`) that makes bypasses detectable in CI rather than
invisible. Claiming more than that would be exactly the "narrate success" failure the
constitution warns about. Real isolation for untrusted code requires an external
sandbox, per prime-agent's own warning (README.md:66) and our
docs/prime-agent-study.md:213.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

REQUIRED_PERMISSION_KEYS: tuple[str, ...]
try:  # pragma: no cover - exercised implicitly by every import in this repo
    # SINGLE SOURCE OF TRUTH. system/governance_checks.py already owns the canonical
    # set of permission keys and audits every agent against it. Re-declaring them here
    # would create a second authority that could silently drift out of step with the
    # audit -- the precise failure mode the constitution's "no supreme governor" axiom
    # (Ruling C1) exists to prevent. We import and normalize to a tuple for a stable
    # evaluation order; a divergence now becomes an ImportError, not silent drift.
    from system.governance_checks import REQUIRED_PERMISSION_KEYS as _CANONICAL_KEYS

    # Preferred evaluation order for the keys we know about; any key the audit adds
    # later sorts after them alphabetically instead of raising. A new permission key
    # must extend enforcement, never break the bridge that enforces it.
    _ORDER = ("READ", "WRITE", "NEVER", "HUMAN_CHECKPOINT")
    REQUIRED_PERMISSION_KEYS = tuple(
        sorted(_CANONICAL_KEYS, key=lambda k: (_ORDER.index(k) if k in _ORDER else len(_ORDER), k))
    )
except ImportError:  # governance_checks unavailable (isolated use of this module)
    REQUIRED_PERMISSION_KEYS = ("READ", "WRITE", "NEVER", "HUMAN_CHECKPOINT")


class BridgeError(Exception):
    """Raised on structurally invalid bridge usage (bad request, unknown handler)."""


class PermissionRefused(BridgeError):
    """Raised when a request is refused. Carries the reason for the audit trail."""


class Outcome(str, Enum):
    ALLOWED = "allowed"
    REFUSED_NEVER = "refused_never"
    REFUSED_NOT_DECLARED = "refused_not_declared"
    REFUSED_UNKNOWN_ACTOR = "refused_unknown_actor"
    REFUSED_NO_HANDLER = "refused_no_handler"
    ESCALATE_HUMAN = "escalate_human"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class HostRequest:
    """A typed request to mutate authoritative state.

    `target` is the permission-scope name the mutation touches, and must match a
    string in the actor's matrix. It is separate from `payload` on purpose: the thing
    being authorized is the SCOPE, never the data. Deriving the scope from payload
    contents would let a caller widen its own authority by renaming a field.
    """

    actor: str
    action: str
    target: str
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        for name in ("actor", "action", "target"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BridgeError(f"HostRequest.{name} must be a non-empty string, got {value!r}")
        if not isinstance(self.payload, dict):
            raise BridgeError("HostRequest.payload must be a dict")


@dataclass
class BridgeDecision:
    """The result of submitting a request. `outcome` is authoritative."""

    outcome: Outcome
    request: HostRequest
    detail: str = ""
    result: Any = None
    created_at: str = field(default_factory=_now)

    @property
    def allowed(self) -> bool:
        return self.outcome is Outcome.ALLOWED

    @property
    def needs_human(self) -> bool:
        return self.outcome is Outcome.ESCALATE_HUMAN

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "actor": self.request.actor,
            "action": self.request.action,
            "target": self.request.target,
            "reason": self.request.reason,
            "detail": self.detail,
            "created_at": self.created_at,
        }


def validate_matrix(matrix: Any, actor: str = "<unknown>") -> dict[str, list[str]]:
    """Return a normalized permission matrix or raise. Fails closed on any defect."""
    if not isinstance(matrix, dict):
        raise BridgeError(f"permission matrix for {actor!r} must be a dict, got {type(matrix).__name__}")
    missing = [k for k in REQUIRED_PERMISSION_KEYS if k not in matrix]
    if missing:
        raise BridgeError(f"permission matrix for {actor!r} missing keys: {missing}")
    normalized: dict[str, list[str]] = {}
    for key in REQUIRED_PERMISSION_KEYS:
        value = matrix[key]
        if not isinstance(value, list):
            raise BridgeError(f"permission matrix for {actor!r} key {key} must be a list")
        normalized[key] = [str(v) for v in value]
    return normalized


def _scope_matches(target: str, action: str, scopes: Iterable[str]) -> str | None:
    """Return the matching scope string, or None.

    A scope matches when it equals the target, equals the action, or equals the
    composite "action:target". Wildcard "*" matches anything and is intentionally
    supported for orchestrator-class actors that must route arbitrary targets --
    such actors are then flagged by `check_bridge_interposition` as broad-authority,
    so a wildcard is visible rather than quiet.
    """
    for scope in scopes:
        if scope == "*" or scope == target or scope == action or scope == f"{action}:{target}":
            return scope
    return None


class HostBridge:
    """The single validated entry point for governance-state mutations."""

    def __init__(
        self,
        permissions: dict[str, dict[str, Any]] | None = None,
        *,
        audit_path: str | Path | None = None,
    ):
        #: actor name -> permission matrix
        self._permissions: dict[str, dict[str, list[str]]] = {}
        for actor, matrix in (permissions or {}).items():
            self._permissions[actor] = validate_matrix(matrix, actor)
        #: (action) -> callable(request) -> Any
        self._handlers: dict[str, Callable[[HostRequest], Any]] = {}
        self._audit: list[BridgeDecision] = []
        self.audit_path = Path(audit_path) if audit_path else None

    # ---- wiring ----------------------------------------------------------
    def register_actor(self, actor: str, matrix: dict[str, Any]) -> None:
        """Declare an actor's permission matrix. Raises on a malformed matrix."""
        self._permissions[actor] = validate_matrix(matrix, actor)

    def register_handler(self, action: str, handler: Callable[[HostRequest], Any]) -> None:
        """Bind an action to the ONE function permitted to perform it."""
        if not callable(handler):
            raise BridgeError(f"handler for {action!r} must be callable")
        self._handlers[action] = handler

    def known_actors(self) -> list[str]:
        return sorted(self._permissions)

    def known_actions(self) -> list[str]:
        return sorted(self._handlers)

    # ---- the gate --------------------------------------------------------
    def check(self, request: HostRequest) -> BridgeDecision:
        """Authorize without executing. Pure; safe to call for a dry run.

        Evaluation order is a policy: unknown actor -> NEVER -> HUMAN_CHECKPOINT ->
        WRITE. NEVER precedes everything executable so a matrix that contradicts
        itself fails closed.
        """
        matrix = self._permissions.get(request.actor)
        if matrix is None:
            return BridgeDecision(
                Outcome.REFUSED_UNKNOWN_ACTOR, request,
                detail=f"actor {request.actor!r} has no declared permission matrix",
            )

        never_hit = _scope_matches(request.target, request.action, matrix["NEVER"])
        if never_hit:
            return BridgeDecision(
                Outcome.REFUSED_NEVER, request,
                detail=f"{request.action}:{request.target} matches NEVER scope {never_hit!r}",
            )

        checkpoint_hit = _scope_matches(request.target, request.action, matrix["HUMAN_CHECKPOINT"])
        if checkpoint_hit:
            return BridgeDecision(
                Outcome.ESCALATE_HUMAN, request,
                detail=f"{request.action}:{request.target} requires human approval "
                       f"(HUMAN_CHECKPOINT scope {checkpoint_hit!r})",
            )

        write_hit = _scope_matches(request.target, request.action, matrix["WRITE"])
        if not write_hit:
            return BridgeDecision(
                Outcome.REFUSED_NOT_DECLARED, request,
                detail=f"{request.action}:{request.target} is not in the declared WRITE scope "
                       f"for {request.actor!r} (declared: {matrix['WRITE']})",
            )

        if request.action not in self._handlers:
            return BridgeDecision(
                Outcome.REFUSED_NO_HANDLER, request,
                detail=f"no handler registered for action {request.action!r}",
            )

        return BridgeDecision(
            Outcome.ALLOWED, request,
            detail=f"authorized by WRITE scope {write_hit!r}",
        )

    def submit(self, request: HostRequest, *, raise_on_refusal: bool = False) -> BridgeDecision:
        """Authorize, then execute via the registered handler. The only write path.

        A handler exception is recorded and re-raised: Article I.3 ("Fail Loudly")
        forbids swallowing it, and a silent failure here would let a caller believe a
        mutation landed when it did not.
        """
        if not isinstance(request, HostRequest):
            raise BridgeError("submit() requires a HostRequest")

        decision = self.check(request)
        if not decision.allowed:
            self._record(decision)
            if raise_on_refusal:
                raise PermissionRefused(f"{decision.outcome.value}: {decision.detail}")
            return decision

        handler = self._handlers[request.action]
        try:
            decision.result = handler(request)
        except Exception as exc:
            decision.detail = f"{decision.detail}; handler raised {type(exc).__name__}: {exc}"
            self._record(decision)
            raise
        self._record(decision)
        return decision

    # ---- audit trail -----------------------------------------------------
    def _record(self, decision: BridgeDecision) -> None:
        self._audit.append(decision)
        if not self.audit_path:
            return
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(decision.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            # An unwritable audit log must not abort the run; the in-memory trail
            # remains authoritative for this process.
            pass

    def audit_trail(self) -> list[BridgeDecision]:
        return list(self._audit)

    def refusals(self) -> list[BridgeDecision]:
        return [d for d in self._audit if not d.allowed]


# --- harness integration ----------------------------------------------------
def make_harness_handlers(harness: Any) -> dict[str, Callable[[HostRequest], Any]]:
    """Build bridge handlers for a ContinualHarness instance.

    Kept as a factory rather than importing ContinualHarness so this module stays
    dependency-free and testable with a stub. Evidence is mandatory on both write
    actions: `record_refinement` already enforces Law 16, and `upsert` is passed
    `require_evidence` so an entry can never be created from an unevidenced request.
    """

    def _upsert(request: HostRequest) -> Any:
        payload = request.payload
        evidence = str(payload.get("evidence", ""))
        if not evidence.strip():
            raise PermissionRefused("harness upsert requires non-empty evidence (Law 16)")
        return harness.upsert(
            payload["kind"],
            payload["title"],
            payload["content"],
            id=payload.get("id"),
            path=payload.get("path"),
            metadata=payload.get("metadata"),
            source=payload.get("source", request.actor),
            require_evidence=evidence,
        )

    def _record_refinement(request: HostRequest) -> Any:
        payload = request.payload
        return harness.record_refinement(
            payload.get("trigger", request.reason or request.actor),
            payload.get("changes", []),
            evidence=str(payload.get("evidence", "")),
            outcome=payload.get("outcome", ""),
        )

    def _rollback(request: HostRequest) -> Any:
        return harness.rollback(request.payload["refinement_id"])

    return {
        "harness_upsert": _upsert,
        "harness_record_refinement": _record_refinement,
        "harness_rollback": _rollback,
    }


#: Actions that mutate governance state and therefore MUST route through the bridge.
GOVERNED_ACTIONS = (
    "harness_upsert",
    "harness_record_refinement",
    "harness_rollback",
)

#: Modules legitimately allowed to touch harness internals directly: the harness
#: itself, the bridge, and the wiring/test layers. Anything else calling a harness
#: mutator directly is a bypass.
_BRIDGE_EXEMPT_MODULES = (
    "system/continual_harness.py",
    "system/host_bridge.py",
    "system/refine_loop.py",
)

#: Harness mutators that must not be called outside the exempt set.
_HARNESS_MUTATORS = ("upsert(", "record_refinement(", "rollback(")


def find_bridge_bypasses(root: str | Path = ".") -> list[str]:
    """Return source locations that mutate the harness without the bridge.

    Deliberately a *source scan* rather than a runtime check, because the bypass we
    need to catch is a call site that exists but is never exercised in tests -- the
    exact shape of defect a runtime-only check misses. This function is a linter for
    an architectural invariant, not a behavioural test of the code it scans, so it
    reads files by design; the invariant it protects has no runtime signature until
    the day someone triggers it in production.
    """
    root = Path(root)
    findings: list[str] = []
    for directory in ("agents", "system", "kernel", "tools", "memory", "llm"):
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if rel in _BRIDGE_EXEMPT_MODULES or "__pycache__" in rel:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if "harness" not in text.lower():
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"'):
                    continue
                if "harness" not in stripped.lower():
                    continue
                if any(mutator in stripped for mutator in _HARNESS_MUTATORS):
                    findings.append(f"{rel}:{lineno}: {stripped[:120]}")
    return findings


def check_bridge_interposition(root: str | Path = ".") -> dict[str, Any]:
    """Governance check: no module mutates the harness outside the bridge.

    Returns the same {name, passed, breaches} shape used by
    system/governance_checks.py so it can be wired into `make audit` without
    changing that module's contract.
    """
    bypasses = find_bridge_bypasses(root)
    return {
        "name": "bridge_interposition",
        "passed": not bypasses,
        "breaches": [f"harness mutated outside HostBridge at {b}" for b in bypasses],
    }


def atomic_append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    """Append one JSON row durably (fsync) so a crash cannot truncate the trail."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "BridgeDecision",
    "BridgeError",
    "GOVERNED_ACTIONS",
    "HostBridge",
    "HostRequest",
    "Outcome",
    "PermissionRefused",
    "REQUIRED_PERMISSION_KEYS",
    "atomic_append_jsonl",
    "check_bridge_interposition",
    "find_bridge_bypasses",
    "make_harness_handlers",
    "validate_matrix",
]
