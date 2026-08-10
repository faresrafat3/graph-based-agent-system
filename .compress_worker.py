#!/usr/bin/env python3
"""Rebuild assigned docs with dense prose, splicing fenced blocks byte-exact.

New prose is written with {B0}, {B1}, ... placeholders that are replaced by the
Nth fenced block (fence line + body + closing fence) taken verbatim from the
original file. Nothing inside a fence is ever retyped.
"""
import re
import sys
from pathlib import Path

DOCS = Path("/home/fares/Projects/graph-based-agent-system/docs")
FENCE = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.S | re.M)


def blocks(path: Path) -> list[str]:
    return FENCE.findall(path.read_text(encoding="utf-8"))


def render(path: Path, template: str) -> None:
    bs = blocks(path)
    used = sorted({int(m) for m in re.findall(r"\{B(\d+)\}", template)})
    missing = [i for i in range(len(bs)) if i not in used]
    if missing:
        sys.exit(f"{path.name}: unused fenced blocks {missing} (would lose code)")
    out = template
    for i, b in enumerate(bs):
        out = out.replace("{B%d}" % i, b)
    leftover = re.findall(r"\{B\d+\}", out)
    if leftover:
        sys.exit(f"{path.name}: unresolved placeholders {leftover}")
    before = len(path.read_bytes())
    path.write_text(out, encoding="utf-8")
    after = len(path.read_bytes())
    print(f"{path.name}: {before} -> {after} bytes ({(before-after)/before*100:.1f}% smaller)")
