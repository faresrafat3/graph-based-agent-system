#!/usr/bin/env python3
"""Per-file fingerprint diff against the repo snapshot (dry-run friendly)."""
import json
import sys
from collections import Counter
from pathlib import Path

from scripts.verify_md_compression import ROOT, SNAPSHOT, fingerprint

KINDS = ("numbers", "code", "cells", "anchors", "idents", "links")


def diff(rel: str, text: str | None = None) -> int:
    before = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[rel]
    p = ROOT / rel
    if text is None:
        text = p.read_text(encoding="utf-8")
    new = fingerprint(text)
    bad = 0
    for kind in KINDS:
        missing = Counter(before.get(kind, {})) - Counter(new[kind])
        for fact, n in missing.items():
            print(f"  LOST {kind} x{n}: {fact[:160]!r}")
            bad += 1
    ob, nb = before["bytes"], len(text.encode("utf-8"))
    print(f"{rel}: {ob} -> {nb} bytes ({(ob-nb)/ob*100:.1f}% smaller), {bad} loss(es)")
    return bad


if __name__ == "__main__":
    sys.exit(1 if sum(diff(r) for r in sys.argv[1:]) else 0)
