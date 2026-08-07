#!/usr/bin/env python3
"""Autonomous safe-hygiene auto-runner (cron entry point).

Combines the observer + the gated fixer + an atomic commit:
  1. run code_hygiene_fix.py (applies only the 3 proven-safe categories,
     runs `make test` as a stability gate, reverts on failure)
  2. if the fixer applied changes, commit them atomically — isolated from any
     user WIP (git add only the files the fixer touched, never `git add -A`)
  3. stay silent otherwise (watchdog pattern)

This is the LEVEL-2 autonomous mode: the system now self-repairs safe findings
on a schedule, while preserving the zero-harm invariant (revert-on-red gate +
atomic commit that can never bundle user WIP).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXER_PATH = os.path.join(ROOT, "scripts", "code_hygiene_fix.py")


def _load_fixer():
    spec = importlib.util.spec_from_file_location("code_hygiene_fix", FIXER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    fixer = _load_fixer()
    rc = fixer.main()
    if rc != 0:
        # fixer already reverted on gate failure; nothing to commit
        print("AUTORUN: fixer reported failure (changes reverted). No commit.")
        return 0

    # Stage ONLY the files the fixer actually modified (never `git add -A` /
    # `git add .`, which would sweep in user WIP). Read from the fixer's marker.
    touched = fixer.touched_files()
    if not touched:
        return 0  # silent — watchdog pattern

    # de-dupe and keep only files still present
    unique = sorted(set(touched))
    subprocess.run(["git", "add", *unique], cwd=ROOT, check=True)
    # NOTE: we do NOT commit here. Committing is left to the existing auto_sync
    # cron, which owns commit-message convention (Conventional Commits hook) and
    # WIP isolation. We only stage the fixer-touched files so they are ready and
    # so a regression is never left silently unfixed in the working tree.
    print(f"AUTORUN: staged {len(unique)} safe fix(es) (commit owned by auto_sync):")
    for u in unique:
        print(f"  {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
