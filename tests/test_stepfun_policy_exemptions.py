# version: v1 | 2026-08-08 | verdict: pending-review
"""Exempting a file from the provider policy must not blunt the policy.

The Stepfun-only audit governs which providers this code CALLS, not which ones it may
NAME. Study docs are therefore exempt: a digest of an external codebase has to name
that codebase's real files, and a charter has to be able to say "<vendor>-compatible"
about a wire protocol.

That exemption is a real risk: every skip-listed path is a place a genuine breach
could hide. These tests pin the boundary — the deny list must still fire on
PRODUCTION code, and the skip list must stay narrow and intentional.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_stepfun_policy import DENY_MARKERS, SKIP_FILES, should_scan

REPO = Path(__file__).resolve().parent.parent

# Directories where a provider reference is a genuine policy breach, never a citation.
PRODUCTION_DIRS = ("agents", "system", "graph")


def test_production_dirs_are_never_skipped():
    """No exemption may cover executable code."""
    for entry in SKIP_FILES:
        top = entry.split("/")[0]
        assert top not in PRODUCTION_DIRS, (
            f"{entry} exempts production code from the provider policy; "
            "exemptions are for documentation only"
        )


def test_skip_list_covers_only_docs_and_the_auditor_itself():
    allowed_suffixes = {".md", ".py", ""}
    for entry in SKIP_FILES:
        assert Path(entry).suffix in allowed_suffixes, entry
        if entry.endswith(".py"):
            assert entry == "scripts/audit_stepfun_policy.py", (
                f"{entry}: the only exempt .py file may be the auditor itself "
                "(it necessarily contains the deny markers)"
            )


def test_every_skip_entry_still_exists():
    """A stale exemption is an exemption nobody is reviewing."""
    for entry in SKIP_FILES:
        if entry == ".env":  # gitignored local state, legitimately absent
            continue
        assert (REPO / entry).exists(), (
            f"{entry} is skip-listed but does not exist — remove the dead exemption "
            "so the skip list stays a reviewable list of real decisions"
        )


def test_production_files_are_scanned():
    for d in PRODUCTION_DIRS:
        target = REPO / d
        if not target.exists():
            continue
        for py in target.rglob("*.py"):
            rel = py.relative_to(REPO)
            assert should_scan(rel), f"{rel} must be scanned by the provider policy"


@pytest.mark.parametrize("marker", DENY_MARKERS)
def test_deny_markers_are_absent_from_production_code(marker: str):
    """The actual invariant: no production file names a forbidden provider/param."""
    offenders = []
    for d in PRODUCTION_DIRS:
        target = REPO / d
        if not target.exists():
            continue
        for py in target.rglob("*.py"):
            if marker in py.read_text(encoding="utf-8"):
                offenders.append(str(py.relative_to(REPO)))
    assert not offenders, f"marker {marker!r} found in production code: {offenders}"


def test_skip_list_is_small():
    """Guardrail against exemption creep: the list should stay reviewable by eye."""
    assert len(SKIP_FILES) <= 12, (
        f"skip list has grown to {len(SKIP_FILES)} entries; if exemptions keep "
        "accumulating, the policy is being worked around rather than satisfied"
    )
