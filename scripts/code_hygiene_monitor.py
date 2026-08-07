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
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER_PATH = os.path.join(ROOT, "scripts", "code_hygiene_scan.py")

# Categories that are 100%-safe to act on (proven across v21/v22 work).
ACTIONABLE = {"duplicate_import", "trailing_whitespace_code", "missing_final_newline"}

# User's active WIP — do not report (we deliberately never touch these).
WIP_EXCLUDE = {
    os.path.join(ROOT, "benchmarks", "swebench_harness.py"),
}


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
    if not actionable:
        return 0  # silent — watchdog pattern

    actionable.sort(key=lambda r: (r["path"], r.get("line", 0)))
    print(f"SAFE-ACTIONABLE CODE-HYGIENE FINDINGS: {len(actionable)}")
    for f in actionable:
        line = f.get("line", "?")
        print(f"  {f['path']}:{line} [{f['kind']}] {f.get('detail', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
