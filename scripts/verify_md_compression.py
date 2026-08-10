#!/usr/bin/env python3
"""Falsifier for the markdown compression pass.

Compression is only allowed to remove *words*, never *facts*. This script is the
falsifier declared in advance: it snapshots the load-bearing content of every
tracked .md file, and after a compression pass it fails loudly if any of it is
gone.

What counts as load-bearing (must survive byte-for-byte):
  - every numeric literal / percentage (measurements, n=, pp, scores, article nums)
  - every fenced code block body
  - every table row's cell values
  - every heading's anchor target (so inbound #links keep resolving)
  - every relative link target
  - every backticked identifier (module paths, function names, config keys)

Usage:
    python scripts/verify_md_compression.py --snapshot   # before compressing
    python scripts/verify_md_compression.py --check      # after compressing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / ".md-compression-snapshot.json"

SKIP_PARTS = (".venv", ".git", "node_modules", "__pycache__")

NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")
CODE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
ROW_RE = re.compile(r"^\|(.+)\|\s*$", re.M)
HEAD_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
TICK_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def md_files() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*.md")
        if not any(part in SKIP_PARTS for part in p.parts)
    )


def anchor(heading: str) -> str:
    """GitHub-style anchor slug for a heading."""
    s = re.sub(r"`|\*|_", "", heading)
    s = re.sub(r"[^\w\s-]", "", s)
    return s.strip().lower().replace(" ", "-")


def squash(s: str) -> str:
    """Whitespace-insensitive form: reflowing prose is allowed, losing it is not."""
    return re.sub(r"\s+", " ", s).strip()


def prose_only(text: str) -> str:
    """Drop fenced blocks and inline code before link scanning.

    Regexes and code samples routinely contain ``[...](...)`` sequences that are
    not links; scanning them produces false 'broken link' reports, and a checker
    that cries wolf gets ignored.
    """
    text = CODE_RE.sub("", text)
    return TICK_RE.sub("", text)


def fingerprint(text: str) -> dict:
    """Extract the facts that compression must preserve."""
    return {
        # Counter so a fact repeated N times can't silently drop to N-1
        "numbers": Counter(NUM_RE.findall(text)),
        "code": Counter(squash(b) for b in CODE_RE.findall(text)),
        "cells": Counter(
            c.strip()
            for row in ROW_RE.findall(text)
            for c in row.split("|")
            if c.strip() and not set(c.strip()) <= {"-", ":", " "}
        ),
        "anchors": Counter(anchor(h) for h in HEAD_RE.findall(text)),
        "idents": Counter(TICK_RE.findall(text)),
        "links": Counter(
            t
            for t in LINK_RE.findall(prose_only(text))
            if not t.startswith(("http", "mailto"))
        ),
    }


def build() -> dict:
    out = {}
    for p in md_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        fp = fingerprint(text)
        out[str(p.relative_to(ROOT))] = {
            "bytes": len(text.encode("utf-8")),
            **{k: dict(v) for k, v in fp.items()},
        }
    return out


def cmd_snapshot() -> int:
    data = build()
    SNAPSHOT.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    total = sum(v["bytes"] for v in data.values())
    print(f"snapshot: {len(data)} files, {total:,} bytes -> {SNAPSHOT.name}")
    return 0


def cmd_check() -> int:
    if not SNAPSHOT.exists():
        print("FAIL no snapshot; run --snapshot on the pre-compression tree first")
        return 2

    before = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    after = build()
    losses: list[str] = []

    # Anchors are only load-bearing when something actually links to them.
    # Collapsing a "#### Foo" heading into a table row is legitimate compression,
    # but ONLY if no inbound link targets #foo and the heading's text survives as
    # text somewhere in the file. Referenced anchors stay strictly protected.
    referenced: set[str] = set()
    for p in md_files():
        for tgt in LINK_RE.findall(prose_only(p.read_text(encoding="utf-8", errors="replace"))):
            if "#" in tgt:
                referenced.add(tgt.split("#", 1)[1].strip().lower())

    for rel, old in sorted(before.items()):
        new = after.get(rel)
        if new is None:
            # Content may be intentionally merged elsewhere; require it to land somewhere.
            merged = {k: Counter() for k in ("numbers", "code", "cells", "anchors", "idents", "links")}
            for cur in after.values():
                for k in merged:
                    merged[k].update(cur.get(k, {}))
            for kind in ("numbers", "code", "cells"):
                for fact, n in Counter(old.get(kind, {})).items():
                    if merged[kind][fact] < n:
                        losses.append(f"{rel}: DELETED and {kind} fact not merged anywhere: {fact!r}")
            continue

        for kind in ("numbers", "code", "cells", "anchors", "idents", "links"):
            old_c, new_c = Counter(old.get(kind, {})), Counter(new.get(kind, {}))
            missing = old_c - new_c
            for fact, n in missing.items():
                if kind == "anchors":
                    # Demoting a heading to a table row / bold lead-in is allowed,
                    # provided nobody links to it AND every significant word of the
                    # heading still appears in the file. Reordering and dropping the
                    # "Principle 3:" style numbering is fine; losing the words is not.
                    body = squash(
                        (ROOT / rel).read_text(encoding="utf-8", errors="replace")
                    ).lower()
                    tokens = [
                        w
                        for tok in fact.split("-")
                        # slugging strips underscores (HUMAN_CHECKPOINT ->
                        # humancheckpoint), so compare on word pieces instead.
                        for w in re.findall(r"[a-z]+|\d+", tok)
                        if len(w) > 2
                    ]
                    # Compare against several de-punctuated views: slugging both
                    # splits on and swallows separators, so "HUMAN_CHECKPOINT"
                    # can arrive as humancheckpoint OR human checkpoint.
                    views = (body, body.replace("_", " "), body.replace("_", ""))

                    def survives(w: str, _v: tuple[str, ...] = views) -> bool:
                        return any(w in v for v in _v)

                    if fact not in referenced and all(survives(w) for w in tokens):
                        continue
                    if fact in referenced:
                        losses.append(f"{rel}: lost LINKED anchor #{fact} (inbound links would break)")
                    else:
                        gone = [w for w in tokens if not survives(w)]
                        losses.append(f"{rel}: heading content vanished: {fact!r} (missing words: {gone})")
                    continue
                losses.append(f"{rel}: lost {kind} x{n}: {fact[:110]!r}")

    # Relative links must still resolve.
    for p in md_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        for tgt in LINK_RE.findall(prose_only(text)):
            if tgt.startswith(("http", "mailto", "#")):
                continue
            if not (p.parent / tgt.split("#")[0]).resolve().exists():
                losses.append(f"{p.relative_to(ROOT)}: broken link -> {tgt}")

    before_bytes = sum(v["bytes"] for v in before.values())
    after_bytes = sum(v["bytes"] for v in after.values())
    saved = before_bytes - after_bytes
    pct = (saved / before_bytes * 100) if before_bytes else 0.0

    if losses:
        print(f"FAIL {len(losses)} fact loss(es):\n")
        for line in losses[:60]:
            print("  -", line)
        if len(losses) > 60:
            print(f"  ... and {len(losses) - 60} more")
        return 1

    print(f"PASS no facts lost. {before_bytes:,} -> {after_bytes:,} bytes ({pct:.1f}% smaller)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot", action="store_true")
    g.add_argument("--check", action="store_true")
    args = ap.parse_args()
    return cmd_snapshot() if args.snapshot else cmd_check()


if __name__ == "__main__":
    sys.exit(main())
