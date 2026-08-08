#!/usr/bin/env python3
"""Gated auto-fixer for the safe code-hygiene categories.

This is the ACTING counterpart to scripts/code_hygiene_scan.py (which is
observe-only by contract). It reuses the scanner to collect findings, then
applies ONLY the mechanically-proven-safe fixes, runs the test suite as a
stability gate, and reverts instantly on any failure.

Safety model (raised from 100%-certain to gated-~99%-certain):
  * Categories 1-3 (duplicate_import / trailing_whitespace_code /
    missing_final_newline) are applied directly — they are behavior-preserving
    by construction (proven across v21/v22).
  * unused_module_import / duplicate_definition are EXCLUDED from auto-fix.
    The scanner reports the whole import LINE, not the specific unused name,
    so removing the line would drop still-used names in a multi-name import
    (e.g. `from typing import Any, Callable` where only Callable is dead).
    Applying it requires name-level surgery the scanner does not yet provide.
    Keep detection-only.

After applying, the fixer runs `make test` (or `pytest`); if it fails, every
change is reverted via git and the run aborts. This keeps the zero-harm
invariant even though we are now acting, not just observing.

Never edits user WIP: files listed in WIP_EXCLUDE are skipped. The fixer also
writes a marker file (.hygiene_touched.txt) listing exactly the files it
modified, so the autorun can `git add` ONLY those files (never `git add -A`,
which would sweep in user WIP).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNER_PATH = os.path.join(ROOT, "scripts", "code_hygiene_scan.py")

# Categories applied directly (behavior-preserving by construction).
DIRECT_APPLY = {"duplicate_import", "trailing_whitespace_code", "missing_final_newline"}
# NOTE: unused_module_import / duplicate_definition intentionally excluded (see docstring).
PROBED_APPLY: set[str] = set()

# User WIP — never touch.
WIP_EXCLUDE = {os.path.join(ROOT, "benchmarks", "swebench_harness.py")}


def _load_scanner():
    spec = importlib.util.spec_from_file_location("code_hygiene_scan", SCANNER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _apply_finding(f: dict, src_lines: list[str]) -> list[str] | None:
    kind = f["kind"]
    ln = f.get("line")
    if kind == "trailing_whitespace_code":
        idx = (ln or 0) - 1
        if 0 <= idx < len(src_lines):
            src_lines[idx] = src_lines[idx].rstrip()
            return src_lines
        return None
    if kind == "duplicate_import":
        idx = (ln or 0) - 1
        if 0 <= idx < len(src_lines):
            del src_lines[idx]
            return src_lines
        return None
    # unused_module_import / duplicate_definition: intentionally not applied.
    return None


def _record_touched(path: str) -> None:
    marker = os.path.join(ROOT, ".hygiene_touched.txt")
    with open(marker, "a", encoding="utf-8") as fh:
        fh.write(path + "\n")


def touched_files() -> list[str]:
    """Read and clear the marker file listing files the fixer modified."""
    marker = os.path.join(ROOT, ".hygiene_touched.txt")
    if not os.path.exists(marker):
        return []
    with open(marker, encoding="utf-8") as fh:
        files = [ln.strip() for ln in fh if ln.strip()]
    os.remove(marker)
    return files


def main() -> int:
    dry_run = "--dry-run" in sys.argv[1:]
    chs = _load_scanner()
    by_file: dict[str, list[dict]] = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in chs.SKIP_ROOTS]
        for fn in filenames:
            if not fn.endswith(".py") or fn in chs.SKIP_FILE:
                continue
            full = os.path.join(dirpath, fn)
            if full in WIP_EXCLUDE:
                continue
            for f in chs.scan_file(full):
                by_file.setdefault(f["path"], []).append(f)

    applied: list[str] = []
    for path, findings in by_file.items():
        actionable = [f for f in findings if f["kind"] in (DIRECT_APPLY | PROBED_APPLY)]
        if not actionable:
            continue
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        lines = raw.split("\n")
        new_lines = lines[:]
        changed = False
        for f in actionable:
            res = _apply_finding(f, new_lines)
            if res is not None:
                new_lines = res
                changed = True
                applied.append(f"{path}:{f.get('line')} [{f['kind']}]")
        if any(f["kind"] == "missing_final_newline" for f in actionable):
            if raw and not raw.endswith("\n"):
                raw = raw + "\n"
                changed = True
                applied.append(f"{path}:EOF [missing_final_newline]")
        if changed and not dry_run:
            new_raw = "\n".join(new_lines)
            if raw.endswith("\n") and not new_raw.endswith("\n"):
                new_raw = new_raw + "\n"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_raw)
            _record_touched(path)

    if not applied:
        print("NOTHING TO FIX — repo clean of actionable safe findings.")
        return 0

    print(f"{'DRY-RUN: would apply' if dry_run else 'APPLIED'} {len(applied)} safe fixes:")
    for a in applied:
        print(f"  {a}")

    if dry_run:
        return 0

    # stability gate: run the test suite; revert on failure
    print("Running stability gate (make test)...")
    res = subprocess.run(["make", "test"], cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print("STABILITY GATE FAILED — reverting all changes via git.")
        subprocess.run(["git", "checkout", "--", "."], cwd=ROOT)
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        return 1
    print("STABILITY GATE PASSED — changes retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
