#!/usr/bin/env python3
"""Observe-only safe-hygiene monitor.

Reuses the scanner in scripts/code_hygiene_scan.py and reports ONLY the
mechanically-actionable, behavior-preserving categories:
  - duplicate_import        (name already bound in an outer/equal scope)
  - trailing_whitespace_code (tokenize-verified not-in-string-literal)
  - missing_final_newline

Detection-only categories (unused_module_import, duplicate_definition) are
excluded on purpose: they require human/delegated confirmation before any
removal, so surfacing them here would create false alarms.

The monitor never edits files. When the repo is clean it prints NOTHING
(watchdog pattern) so a scheduled run stays silent unless something regresses.

Known user WIP paths are excluded so we don't nag about files the user is
actively editing (consistent with the zero-harm / don't-touch-WIP rule).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER_PATH = os.path.join(ROOT, "scripts", "code_hygiene_scan.py")

# Categories that are 100%-safe to act on (proven across v21/v22 work).
ACTIONABLE = {"duplicate_import", "trailing_whitespace_code", "missing_final_newline"}

# User's active WIP — do not report (we deliberately never touch these).
WIP_EXCLUDE = {
    os.path.join(ROOT, "benchmarks", "swebench_harness.py"),
}

# Files this autonomous loop has already committed safe edits to. If the user
# later starts editing one of these (it appears in the working tree as modified),
# that is a collision risk with the running auto-sync cron — surface a warning so
# we do not let auto_sync bundle our earlier commit with the user's live work.
SAFE_EDIT_FILES = [
    "main.py",
    "agents/deterministic_validator.py",
    "agents/code_executor.py",
    "agents/task_decomposer.py",
    "tests/test_karpathy_pipeline.py",
    "tests/test_task_decomposer.py",
]


def _collision_warnings() -> list[str]:
    warnings = []
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT, capture_output=True, text=True,
    )
    modified = {line[3:].strip() for line in out.stdout.splitlines() if line[:2] in (" M", "M ")}
    for f in SAFE_EDIT_FILES:
        if f in modified:
            warnings.append(
                f"WIP-COLLISION: {f} is now modified in the working tree "
                f"(user edit overlaps a file this loop committed). "
                f"auto_sync may bundle it — review before next sync."
            )
    return warnings


def _load_scanner():
    spec = importlib.util.spec_from_file_location("code_hygiene_scan", SCANNER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    chs = _load_scanner()
    findings = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in chs.SKIP_ROOTS]
        for fn in filenames:
            if not fn.endswith(".py") or fn in chs.SKIP_FILE:
                continue
            full = os.path.join(dirpath, fn)
            if full in WIP_EXCLUDE:
                continue
            findings.extend(chs.scan_file(full))

    actionable = [f for f in findings if f.get("kind") in ACTIONABLE]
    warnings = _collision_warnings()

    if not actionable and not warnings:
        return 0  # silent — watchdog pattern

    if actionable:
        actionable.sort(key=lambda r: (r["path"], r.get("line", 0)))
        print(f"SAFE-ACTIONABLE CODE-HYGIENE FINDINGS: {len(actionable)}")
        for f in actionable:
            line = f.get("line", "?")
            print(f"  {f['path']}:{line} [{f['kind']}] {f.get('detail', '')}")
    for w in warnings:
        print(f"  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
