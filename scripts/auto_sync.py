#!/usr/bin/env python3
"""Auto-sync working tree -> auto-sync branch -> main (when CI green).

Run after any session change (via cron or a session-end hook). It:
  1. Detects uncommitted/untracked changes that are NOT gitignored.
  2. Commits them with a descriptive conventional-commit message.
  3. Pushes to the `auto-sync` branch (unprotected, fast path).
  4. Opens/updates a PR auto-sync -> main and lets CI gate the merge.

Design rules (see repo CONSTITUTION / CONTRIBUTING):
  - Never force-pushes or touches `main` directly.
  - Skips if the only diffs are gitignored junk (.hermes/, __pycache__, logs/...).
  - Merge into `main` is gated by the required `test` status check, so bad
    changes can never reach `main` without a green CI run.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC_BRANCH = "auto-sync"
BASE_BRANCH = "main"
REMOTE = "origin"


def run(cmd: list[str], check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed {cmd}: {r.stderr.strip()}")
    return r.stdout.strip()


def _status_paths() -> list[str]:
    """Changed paths from `git status --porcelain -z`.

    Deliberately does NOT go through run(): that strips stdout, which ate the
    leading space of a ' M path' record so a blind rec[3:] slice dropped the
    first character ("scripts" -> "cripts") and skewed the commit type to misc.
    -z also makes paths with spaces/newlines safe (no quoting/escaping).
    Each record is `XY<space><path>`; rename/copy emits a second record with
    the old path, which we consume and discard so only the new name counts.
    """
    r = subprocess.run(
        ["git", "status", "--porcelain", "-z"],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    records = [rec for rec in r.stdout.split("\0") if rec]
    paths: list[str] = []
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 4:
            continue
        paths.append(rec[3:])
        if rec[0] in ("R", "C"):
            i += 1  # skip the paired old path
    return paths


def main() -> int:
    # 0. Safety: must be on the sync branch.
    cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if cur != SYNC_BRANCH:
        # Always rebuild the sync branch fresh from main so the resulting PR
        # is from a clean branch (a PR from a stale/already-merged branch
        # does not trigger CI reliably). Carries working-tree changes over.
        run(["git", "checkout", "-B", SYNC_BRANCH, f"{REMOTE}/{BASE_BRANCH}"], check=False)

    # 1. Fetch latest main so the fresh branch is up to date. We do NOT merge
    #    origin/auto-sync here: the branch was just rebuilt from main, and
    #    pulling the old remote auto-sync would create a false divergence.
    #    --prune is required: when a previous PR merged with --delete-branch,
    #    GitHub deletes the remote branch but our stale refs/remotes/origin/
    #    auto-sync survives. --force-with-lease then compares against that
    #    stale ref, sees a mismatch against a branch that no longer exists,
    #    and rejects the push -- silently, because check=False.
    run(["git", "fetch", "--prune", REMOTE, BASE_BRANCH], check=False)

    # 2. What changed that is NOT gitignored? (git already excludes ignored
    #    paths, so every record here is a real change.)
    paths = _status_paths()
    if not paths:
        print(f"[{_ts()}] auto-sync: nothing to sync — tree clean")
        return 0
    n = len(paths)
    print(f"[{_ts()}] auto-sync: {n} changed paths detected")

    # 3. Classify a rough "type" from the paths for the commit message.
    ctype = _classify(paths)

    # 4. Stage everything that is not gitignored, commit, push.
    #    The sync branch is rebuilt fresh from main every run (step 0), so a
    #    force-with-lease push is safe and avoids "tip behind" rejections from
    #    a stale remote auto-sync left over after a previous PR merge.
    run(["git", "add", "-A"])
    msg = f"auto({ctype}): sync {n} paths — {_short_summary(paths)}"
    run(["git", "commit", "-m", msg], check=False)

    # The push MUST be verified. It was previously check=False, so a rejected
    # push (see the --prune note above) left the commit local-only while this
    # script still printed "pushed ... pending CI" and exited 0 -- the failure
    # was invisible to the cron agent.
    push = subprocess.run(
        ["git", "push", "--force-with-lease", REMOTE, SYNC_BRANCH],
        cwd=REPO, capture_output=True, text=True,
    )
    if push.returncode != 0:
        raise RuntimeError(f"push to {SYNC_BRANCH} failed: {push.stderr.strip()}")

    # Confirm the remote actually has our commit before claiming success.
    local = run(["git", "rev-parse", "HEAD"])
    ls = run(["git", "ls-remote", REMOTE, SYNC_BRANCH], check=False)
    remote_sha = ls.split("\t")[0] if ls.strip() else ""
    if remote_sha != local:
        raise RuntimeError(
            f"push reported success but {REMOTE}/{SYNC_BRANCH} is at {remote_sha or '<absent>'}, expected {local}"
        )

    # 5. Open or reuse an auto-sync -> main PR; CI gates the merge.
    _ensure_pr()
    print(f"[{_ts()}] auto-sync: pushed to {SYNC_BRANCH}; PR auto-sync->{BASE_BRANCH} pending CI")
    return 0


def _classify(paths: list[str]) -> str:
    cats = {
        "agents": "agents", "system": "system", "tests": "tests",
        "scripts": "scripts", "docs": "docs", "benchmarks": "bench",
        "kernel": "kernel", "llm": "llm",
    }
    seen = {cats.get(p.split("/")[0], "misc") for p in paths}
    if len(seen) == 1:
        return next(iter(seen))
    return "multi"


def _short_summary(paths: list[str]) -> str:
    top = sorted({p.split("/")[0] for p in paths})
    if len(top) <= 3:
        return ", ".join(top)
    return f"{', '.join(top[:3])} (+{len(top) - 3} more)"


def _ensure_pr() -> None:
    try:
        existing = run([
            "gh", "pr", "list", "--head", SYNC_BRANCH, "--base", BASE_BRANCH,
            "--json", "number", "--jq", ".[0].number",
        ], check=False)
    except Exception:
        existing = ""
    if existing.strip().isdigit():
        return  # PR already open; CI will gate it
    # Verified: a swallowed `gh pr create` failure previously meant no PR was
    # ever opened while the run still reported success.
    created = subprocess.run([
        "gh", "pr", "create", "--base", BASE_BRANCH, "--head", SYNC_BRANCH,
        "--title", "auto-sync: continuous working-tree sync",
        "--body", "Automated sync of accumulated session work.\n"
                  "Merges only when the `test` CI check is green (branch protection).\n"
                  "This PR is kept open and updated; do not close it manually.",
    ], cwd=REPO, capture_output=True, text=True)
    if created.returncode != 0:
        raise RuntimeError(f"gh pr create failed: {created.stderr.strip()}")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never crash the cron silently
        print(f"[{_ts()}] auto-sync ERROR: {e}", file=sys.stderr)
        sys.exit(1)
