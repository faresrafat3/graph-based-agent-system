#!/usr/bin/env python3
"""Mechanical, SAFE-ONLY code-hygiene scanner for the graph-based-agent-system.

Design contract (see CONSTITUTION Article VI / governed-self-improvement-loop):
  * OBSERVE ONLY. This script NEVER edits a file. It prints findings as JSONL so a
    human (or a gated meta-loop) can decide. It must be safe to run on every tick.
  * 100%-CERTAIN categories only. Every emitted finding is mechanically verifiable and
    behavior-preserving by construction. No heuristics, no "probably".
  * SCOPE-AWARE. A duplicate import is a real (safe) finding ONLY if the imported name
    already has an earlier binding in an OUTER-or-EQUAL scope (AST prefix check), so the
    duplicate is redundant. If the duplicate is the only binding in its own function
    scope, it is NOT reported (removing it would break that function).

Categories emitted:
  1. duplicate_import  -- exact same import statement text appears 2+ times AND the
                          imported name(s) are already bound in an outer/equal scope
                          before the later occurrence.
  2. missing_final_newline -- file does not end with '\\n' (a real, safe, mechanical fix).

Explicitly NOT emitted (would violate the 100%-safe rule):
  * trailing whitespace inside code/strings (may be inside string literals / code fences)
  * "unused" imports (cannot be certain without data-flow analysis)
  * anything requiring intent inference
"""
from __future__ import annotations

import ast
import json
import os
import sys

# Directories that are never source-of-truth for this project's own code.
SKIP_ROOTS = (".venv", ".git", "__pycache__", "logs", ".pytest_cache", ".hermes",
              "reports", "benchmarks/results", "system/measurements")
SKIP_FILE = ("localizer_ensemble.json",)  # untracked result artifact


def _imported_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, ast.Import):
        for a in node.names:
            names.add(a.asname or a.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for a in node.names:
            names.add(a.asname or a.name)
    return names


def _scope_prefix(scope: tuple[str, ...], other: tuple[str, ...]) -> bool:
    return len(other) <= len(scope) and scope[: len(other)] == other


def _iter_imports_with_scope(tree: ast.AST):
    """Yield (lineno, names_set, scope_path) for every import in file order."""
    out: list[tuple[int, set[str], tuple[str, ...]]] = []

    def visit(node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            new_scope = scope + (node.name,)
        else:
            new_scope = scope
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append((node.lineno, _imported_names(node), scope))
        for child in ast.iter_child_nodes(node):
            visit(child, new_scope)

    visit(tree, ())
    out.sort(key=lambda x: x[0])
    return out


def scan_file(path: str) -> list[dict]:
    findings: list[dict] = []
    try:
        src = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return findings

    # 2. missing final newline
    if src and not src.endswith("\n"):
        findings.append({
            "kind": "missing_final_newline",
            "path": path,
            "line": src.count("\n") + 1,
            "detail": "file does not end with a newline",
        })

    # 1. duplicate imports (scope-aware)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return findings  # don't crash the whole scan on one bad file

    imports = _iter_imports_with_scope(tree)
    lines = src.split("\n")
    seen_text: dict[str, int] = {}
    for ln, names, scope in imports:
        text = lines[ln - 1].strip()
        if text in seen_text:
            first_ln = seen_text[text]
            # available iff an earlier import (line<ln) binds a name in `names`
            # in an outer-or-equal scope.
            available = any(
                oln < ln
                and len(onames.intersection(names)) > 0
                and _scope_prefix(scope, osp)
                for (oln, onames, osp) in imports
            )
            if available:
                findings.append({
                    "kind": "duplicate_import",
                    "path": path,
                    "line": ln,
                    "first_occurrence_line": first_ln,
                    "text": text,
                    "scope": list(scope),
                    "detail": "import is redundant: name(s) already bound in outer/equal scope",
                })
        else:
            seen_text[text] = ln

    return findings


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    results: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_ROOTS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if fn in SKIP_FILE:
                continue
            full = os.path.join(dirpath, fn)
            for f in scan_file(full):
                results.append(f)

    # stable order
    results.sort(key=lambda r: (r["path"], r["line"]))
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
