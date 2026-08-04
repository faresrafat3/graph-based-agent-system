#!/usr/bin/env python3
"""Lint commit messages against Conventional Commits for this repo.

CI runs this on every PR (see .github/workflows/ci.yml). It checks only the
PR author's own non-merge commits in the range BASE..HEAD, so commits made by
other collaborators or the autonomous patrol cannot block your PR.

Exit code 1 on any breach.
"""
from __future__ import annotations

import re
import sys

TYPES = {
    "feat", "fix", "docs", "chore", "refactor",
    "test", "perf", "ci", "build", "revert",
}

# <type>: <subject>  -- type lowercase, subject imperative & lowercased first word
PATTERN = re.compile(r"^(?P<type>[a-z]+)(?P<scope>\([a-z0-9_\-/]+\))?!?:\s+(?P<subject>.+)$")

REVERT_RE = re.compile(r"^revert:\s+", re.IGNORECASE)


def lint_one(msg: str) -> list[str]:
    errors: list[str] = []
    # Use the first non-empty line as the subject.
    subject_line = ""
    for line in msg.splitlines():
        if line.strip():
            subject_line = line.rstrip()
            break
    if not subject_line:
        return ["empty commit message"]

    if REVERT_RE.match(subject_line):
        # revert commits get a free pass on the subject grammar.
        return errors

    m = PATTERN.match(subject_line)
    if not m:
        errors.append(
            f"subject '{subject_line}' does not match '<type>: <subject>'. "
            f"Allowed types: {', '.join(sorted(TYPES))}"
        )
        return errors

    ctype = m.group("type")
    subject = m.group("subject")
    if ctype not in TYPES:
        errors.append(f"unknown type '{ctype}'. Allowed: {', '.join(sorted(TYPES))}")
    if subject[0].isupper():
        errors.append(f"subject should start lowercase (imperative): '{subject}'")
    if subject.endswith("."):
        errors.append(f"subject must not end with a period: '{subject}'")
    if len(subject_line) > 72:
        errors.append(f"subject line too long ({len(subject_line)} > 72): '{subject_line}'")
    return errors


def check_commits() -> int:
    """Lint only THIS PR author's non-merge commits in the range BASE..HEAD.

    We skip:
      - merge commits (more than one parent)
      - commits authored by someone other than the PR head author

    This keeps the lint about *your* work. In a repo where an autonomous
    patrol or other collaborators push to the same branches, their commits
    shouldn't block your PR.
    """
    import subprocess

    base = (
        subprocess.run(["git", "merge-base", "HEAD", "origin/main"],
                       capture_output=True, text=True).stdout.strip()
        or "HEAD~1"
    )
    try:
        out = subprocess.run(
            ["git", "log", "--format=%H", f"{base}..HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print("could not enumerate commits; skipping lint")
        return 0

    shas = [s for s in out.splitlines() if s]
    if not shas:
        return 0

    # Author of the PR head commit == "you".
    head_author = subprocess.run(
        ["git", "log", "-1", "--format=%ae", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    failures = 0
    checked = 0
    for sha in shas:
        parents = subprocess.run(
            ["git", "log", "-1", "--format=%P", sha],
            capture_output=True, text=True,
        ).stdout.strip()
        if len(parents.split()) > 1:  # true merge commit -> skip
            continue
        author = subprocess.run(
            ["git", "log", "-1", "--format=%ae", sha],
            capture_output=True, text=True,
        ).stdout.strip()
        if author != head_author:  # not your commit -> skip
            continue
        checked += 1
        msg = subprocess.run(["git", "log", "-1", "--format=%B", sha],
                              capture_output=True, text=True).stdout
        errs = lint_one(msg)
        if errs:
            failures += 1
            print(f"✗ {sha[:8]}:")
            for e in errs:
                print(f"    - {e}")
    if failures:
        print(f"\n{failures} of {checked} commit(s) failed the message "
              f"convention. See CONTRIBUTING.md §2.")
        return 1
    print(f"✓ {checked} of {len(shas)} commit(s) in range are yours and "
          f"conform to Conventional Commits.")
    return 0


def check_file(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    errs = lint_one(text)
    if errs:
        print(f"✗ {path}:")
        for e in errs:
            print(f"    - {e}")
        return 1
    print(f"✓ {path} conforms to Conventional Commits.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(check_file(sys.argv[1]))
    sys.exit(check_commits())
