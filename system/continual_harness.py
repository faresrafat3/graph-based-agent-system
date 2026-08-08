# version: v1 | 2026-08-06 | verdict: pending-review
"""Continual Harness — a *complementary* governance layer above CONSTITUTION.md.

This is the missing piece that makes the META-SYSTEM's "propose -> gate -> record"
loop actually *appliable*. The constitution is immutable (Fares's hard rule: "EXTEND
existing governance, never fork a second authority"). The Continual Harness applies
small, evidence-backed refinements on top of it with snapshots and rollback, so the
self-improvement loop can change behaviour without ever editing the base constitution.

Design mirrors prime-agent's HarnessState (ADR-0001 Decision) but is Python/graph-native:
  * HarnessEntry{kind, scope, ...}  — a refinable unit (prompt|memory|skill|subagent)
  * RefinementEvent{trigger, changes[], evidence, outcome} — every change is recorded
  * mtime-synced load() — never silently clobber another writer's concurrent edits
  * field protection  — None keeps a field, an explicit value (even {}) overrides it
  * rollback(id)      — restores the pre-refinement snapshot

Storage:
  * <path>            -> harness_state.json   (entries, atomic rename writes)
  * <path>-events.jsonl (append-only refinement audit trail)
Rollbacks are also mirrored into system/distillation_ledger.jsonl when a ledger is wired.

GOVERNANCE BOUNDARY (Law 2 / CONSTITUTION Article I.2 — pending constitutional review):
  * This module is NOT a second authority. It MUST route any governance-touching
    proposal through system/self_improvement.distill_opus5 (Ruling C1: meta-loop is
    propose-only, default-deny). Janus writes via apply() are gated by require_evidence
    and never mutate CONSTITUTION.md/LAWS.md (asserted in tests).
  * Any entry whose `source` is not "agent" MUST be flagged for human review before it
    can be injected into a system prompt (poisoned-memory blast-radius control).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

VALID_KINDS: tuple[str, ...] = ("prompt", "memory", "skill", "subagent")
VALID_SCOPES: tuple[str, ...] = ("local", "global")


class HarnessError(Exception):
    """Raised on invalid harness operations (bad kind/scope, evidence missing, etc.)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(raw: str, fallback: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw.strip())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return (normalized or fallback)[:80]


def _coerce_version(raw: Any) -> int:
    """A version stored as a string must survive the round-trip.

    PORTED-FROM: harness.py:237-245 — `"3"` becomes `3`; anything unparseable
    degrades to 1 rather than raising. The earlier port checked `isinstance(int)`
    only, so every string version silently reset to 1 and lost refinement history.
    """
    if isinstance(raw, bool):  # bool is an int subclass; not a version
        return 1
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return 1
    return 1


def _coerce_scope(raw: Any, default: str = "local") -> str:
    """Scope must remain a member of VALID_SCOPES.

    PORTED-FROM: harness.py:233-234 — an absent/invalid scope falls back to the
    store's own scope. The earlier port fell back to `state_path.parent.name`, so an
    entry under a directory named `sub/` loaded with scope='sub', a value no other
    code path can interpret.
    """
    return raw if isinstance(raw, str) and raw in VALID_SCOPES else default


def _strip_scope_prefix(entry_id: str | None) -> str | None:
    """Accept the `local:`/`global:` ids that an overview rendering emits.

    PORTED-FROM: harness.py:59-67. We keep the id-normalisation half; the upstream
    scope-routing half is intentionally dropped (see class docstring: this port is
    single-store, scope is a label, not a second backing file).
    """
    if isinstance(entry_id, str):
        scope, sep, rest = entry_id.partition(":")
        if sep and rest and scope in VALID_SCOPES:
            return rest
    return entry_id


def _validate_python_skill_reference(reference: dict[str, Any] | None) -> dict[str, Any]:
    """A skill entry's reference must name a real, importable Python callable.

    PORTED-FROM: harness.py:128-138. Without this, a `skill` entry can be created
    pointing at nothing and only fails at call time, far from the write that caused it.
    """
    if not isinstance(reference, dict):
        raise HarnessError("skill entries require a Python reference")
    normalized = dict(reference)
    if normalized.get("type") != "python":
        raise HarnessError("skill reference.type must be 'python'")
    if not any(
        isinstance(normalized.get(key), str) and normalized[key]
        for key in ("import", "python_import")
    ):
        raise HarnessError("skill reference requires a Python import")
    if not any(
        isinstance(normalized.get(key), str) and normalized[key]
        for key in ("callable", "call_pattern")
    ):
        raise HarnessError("skill reference requires a callable or call_pattern")
    return normalized


@dataclass
class HarnessEntry:
    """A reusable prompt, memory, skill, or subagent record."""

    id: str
    kind: str
    title: str
    content: str
    path: str = "general"
    scope: str = "local"
    reference: dict[str, Any] = field(default_factory=dict)
    arguments: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "agent"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    version: int = 1


@dataclass
class RefinementEvent:
    """A recorded online harness-refinement pass."""

    id: str
    trigger: str
    changes: list[str]
    evidence: str = ""
    outcome: str = ""
    created_at: str = field(default_factory=_now)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically via a temp file + os.replace (rename is atomic on POSIX).

    Improvement over prime-agent's plain `write_text`: a crash mid-write leaves the
    previous file intact; readers never observe a half-written state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


class ContinualHarness:
    """CRUD store for reset-free harness refinement state (Python/graph-native port)."""

    def __init__(self, state_path: str | Path, *, ledger_path: str | Path | None = None):
        self.state_path = Path(state_path)
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.events_path = self.state_path.with_name(self.state_path.name.replace(".json", "") + "-events.jsonl")
        # entries[kind][id] -> HarnessEntry
        self.entries: dict[str, dict[str, HarnessEntry]] = {k: {} for k in VALID_KINDS}
        self.refinements: list[RefinementEvent] = []
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._loaded_mtime: int | None = None
        self.load()

    # ---- persistence -------------------------------------------------------
    def _disk_mtime(self) -> int | None:
        try:
            return self.state_path.stat().st_mtime_ns
        except OSError:
            return None

    def _sync_from_disk(self) -> None:
        """Reload if another process rewrote the state file since we last touched it."""
        if self._disk_mtime() != self._loaded_mtime:
            self.load()

    def load(self) -> "ContinualHarness":
        if not self.state_path.exists():
            self._loaded_mtime = None
            return self
        mtime = self._disk_mtime()
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            # corrupt/unreadable -> empty, never crash
            data = {}
        if not isinstance(data, dict):
            data = {}

        entries: dict[str, dict[str, HarnessEntry]] = {k: {} for k in VALID_KINDS}
        raw_entries = data.get("entries", {})
        if isinstance(raw_entries, dict):
            for kind in VALID_KINDS:
                for eid, raw in (raw_entries.get(kind, {}) or {}).items():
                    if not isinstance(raw, dict):
                        continue
                    if not isinstance(raw.get("title"), str) or not isinstance(raw.get("content"), str):
                        continue
                    entry = HarnessEntry(
                        id=str(eid),
                        kind=kind,
                        title=raw.get("title", ""),
                        content=raw.get("content", ""),
                        path=raw.get("path", "general") if isinstance(raw.get("path"), str) else "general",
                        scope=_coerce_scope(raw.get("scope")),
                        reference=cast(dict[str, Any], raw.get("reference") if isinstance(raw.get("reference"), dict) else {}),
                        arguments=cast(dict[str, Any], raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {}),
                        metadata=cast(dict[str, Any], raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
                        source=raw.get("source") if isinstance(raw.get("source"), str) else "agent",
                        created_at=raw.get("created_at", _now()),
                        updated_at=raw.get("updated_at", _now()),
                        version=_coerce_version(raw.get("version", 1)),
                    )
                    entries[kind][str(eid)] = entry
        self.entries = entries

        self.refinements = []
        for raw in (data.get("refinements", []) or []):
            if not isinstance(raw, dict):
                continue
            if not isinstance(raw.get("id"), str) or not isinstance(raw.get("trigger"), str):
                continue
            changes = raw.get("changes")
            if isinstance(changes, str):
                changes = [changes]
            elif not isinstance(changes, list):
                continue
            self.refinements.append(RefinementEvent(
                id=raw["id"], trigger=raw["trigger"], changes=[str(c) for c in changes],
                evidence=raw.get("evidence", ""), outcome=raw.get("outcome", ""),
                created_at=raw.get("created_at", _now()),
            ))
        self._loaded_mtime = mtime
        return self

    def save(self) -> None:
        data = {
            "schema": 1,
            "entries": {
                kind: {eid: asdict(e) for eid, e in records.items()}
                for kind, records in self.entries.items()
            },
            "refinements": [asdict(r) for r in self.refinements],
        }
        _atomic_write_json(self.state_path, data)
        self._loaded_mtime = self._disk_mtime()

    # ---- CRUD helpers ------------------------------------------------------
    def _upsert(self, kind: str, title: str, content: str, *, id: str | None = None,
                path: str | None = None, reference: dict | None = None,
                arguments: dict | None = None, metadata: dict | None = None,
                source: str = "agent") -> HarnessEntry:
        # Caller is responsible for syncing from disk first. create()/update() sync
        # once and then call this directly, so their existence check and the write are
        # not separated by a second reload — otherwise create-or-fail degrades into a
        # silent update. (PORTED-FROM: harness.py:357-360)
        if kind not in self.entries:
            raise HarnessError(f"unknown harness kind {kind!r}; expected one of {VALID_KINDS}")
        if kind == "skill" and reference is not None:
            reference = _validate_python_skill_reference(reference)
        eid = id or _slug(title, kind)
        existing = self.entries[kind].get(eid)
        if existing:
            existing.title = title
            existing.content = content
            if path is not None:
                existing.path = path
            if reference is not None:
                existing.reference = dict(reference)
            if arguments is not None:
                existing.arguments = dict(arguments)
            if metadata is not None:
                existing.metadata = dict(metadata)
            existing.source = source
            existing.updated_at = _now()
            existing.version += 1
            entry = existing
        else:
            entry = HarnessEntry(
                id=eid, kind=kind, title=title, content=content,
                path=path if path is not None else "general",
                reference=dict(reference or {}), arguments=dict(arguments or {}),
                metadata=dict(metadata or {}), source=source,
            )
            self.entries[kind][eid] = entry
        self.save()
        return entry

    def create(self, kind: str, title: str, content: str, *, id: str | None = None,
               path: str = "general", reference: dict | None = None,
               arguments: dict | None = None, metadata: dict | None = None,
               source: str = "agent") -> HarnessEntry:
        """Create a NEW entry; raise if the id already exists.

        PORTED-FROM: harness.py:437-482. `upsert` is the lenient path; `create` is
        the one that refuses to clobber. Collapsing the two (as the first port did)
        turns an accidental id collision into silent data loss.
        """
        entry_id = _strip_scope_prefix(id)
        self._sync_from_disk()
        if kind not in self.entries:
            raise HarnessError(f"unknown harness kind {kind!r}; expected one of {VALID_KINDS}")
        entry_id = entry_id or _slug(title, kind)
        if entry_id in self.entries[kind]:
            raise HarnessError(f"{kind} entry {entry_id!r} already exists")
        return self._upsert(kind, title, content, id=entry_id, path=path,
                            reference=reference, arguments=arguments,
                            metadata=metadata, source=source)

    def update(self, kind: str, id: str, title: str, content: str, *,
               path: str | None = None, reference: dict | None = None,
               arguments: dict | None = None, metadata: dict | None = None,
               source: str = "agent") -> HarnessEntry:
        """Update an EXISTING entry; raise if it is absent.

        Omitted (None) fields are preserved; an explicit value — including {} —
        overrides. PORTED-FROM: harness.py:484-... plus the field semantics at :369-380.
        """
        entry_id = _strip_scope_prefix(id)
        self._sync_from_disk()
        if kind not in self.entries:
            raise HarnessError(f"unknown harness kind {kind!r}; expected one of {VALID_KINDS}")
        if entry_id not in self.entries[kind]:
            raise HarnessError(f"{kind} entry {entry_id!r} does not exist")
        return self._upsert(kind, title, content, id=entry_id, path=path,
                            reference=reference, arguments=arguments,
                            metadata=metadata, source=source)

    def upsert(self, kind: str, title: str, content: str, *, id: str | None = None,
               path: str | None = None, reference: dict | None = None,
               arguments: dict | None = None, metadata: dict | None = None,
               source: str = "agent", require_evidence: str | None = None) -> HarnessEntry:
        if require_evidence is not None:
            # evidence-backed gate: a non-empty evidence string is mandatory
            if not require_evidence.strip():
                raise HarnessError("refinement requires non-empty evidence")
        self._sync_from_disk()
        return self._upsert(kind, title, content, id=_strip_scope_prefix(id), path=path,
                            reference=reference, arguments=arguments,
                            metadata=metadata, source=source)

    def get(self, kind: str, id: str) -> HarnessEntry | None:
        self._sync_from_disk()
        entry_id = _strip_scope_prefix(id)
        if entry_id is None:
            return None
        return self.entries.get(kind, {}).get(entry_id)

    def list(self, kind: str | None = None) -> list[HarnessEntry]:
        self._sync_from_disk()
        kinds = [kind] if kind else list(VALID_KINDS)
        out: list[HarnessEntry] = []
        for k in kinds:
            out.extend(self.entries.get(k, {}).values())
        return sorted(out, key=lambda e: (e.kind, e.path, e.title, e.id))

    def delete(self, kind: str, id: str) -> bool:
        self._sync_from_disk()
        if kind not in self.entries:
            raise HarnessError(f"unknown harness kind {kind!r}")
        entry_id = _strip_scope_prefix(id)
        if entry_id in self.entries[kind]:
            del self.entries[kind][entry_id]
            self.save()
            return True
        return False

    # ---- refinement + rollback --------------------------------------------
    def _snapshot(self, label: str) -> dict[str, Any]:
        snap = {
            "label": label,
            "entries": {k: {eid: asdict(e) for eid, e in rec.items()} for k, rec in self.entries.items()},
            "refinements": [asdict(r) for r in self.refinements],
        }
        self._snapshots[label] = snap
        return snap

    def record_refinement(self, trigger: str, changes: list[str] | str, *,
                          evidence: str = "", outcome: str = "",
                          id: str | None = None, require_evidence: bool = True) -> RefinementEvent:
        """Record a refinement. By default evidence is mandatory (Law 16: no self-report)."""
        if require_evidence and not evidence.strip():
            raise HarnessError("refinement requires non-empty evidence (Law 16)")
        normalized = [changes] if isinstance(changes, str) else list(changes)
        event = RefinementEvent(
            id=id or f"refine_{len(self.refinements) + 1:04d}",
            trigger=trigger, changes=normalized, evidence=evidence, outcome=outcome,
        )
        self._snapshot(event.id)
        self.refinements.append(event)
        self._append_event_jsonl(asdict(event))
        # mirror into distillation ledger if wired (Ruling C5 provenance)
        self._mirror_to_ledger(event)
        self.save()
        return event

    def _append_event_jsonl(self, row: dict[str, Any]) -> None:
        try:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _mirror_to_ledger(self, event: RefinementEvent) -> None:
        if not self.ledger_path:
            return
        try:
            row = {
                "type": "harness_refinement",
                "refinement_id": event.id,
                "trigger": event.trigger,
                "evidence": event.evidence,
                "source": "continual_harness",
                "status": "proposed",  # Ruling C1: propose-only, never enforced until reviewed
            }
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def rollback(self, refinement_id: str) -> bool:
        """Restore harness state to the snapshot taken before a refinement."""
        snap = self._snapshots.get(refinement_id)
        if not snap:
            return False
        restored: dict[str, dict[str, HarnessEntry]] = {k: {} for k in VALID_KINDS}
        for kind, recs in snap["entries"].items():
            for eid, raw in recs.items():
                restored.setdefault(kind, {})[eid] = HarnessEntry(**raw)
        self.entries = restored
        self.refinements = [RefinementEvent(**r) for r in snap["refinements"]]
        self.save()
        return True

    # ---- provenance / safety ---------------------------------------------
    def flagged_for_review(self) -> list[HarnessEntry]:
        """Entries whose source is not 'agent' are treated as untrusted (blast-radius control)."""
        return [e for e in self.list() if e.source != "agent"]
