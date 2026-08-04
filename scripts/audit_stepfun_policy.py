"""Audit that production code stays on the Stepfun-only LLM policy."""

from pathlib import Path

DENY_MARKERS = [
    "Open" + "AI",
    "Anth" + "ropic",
    "allow_" + "mock",
    "get_" + "llm",
    "Chat" + "Open" + "AI",
    "Chat" + "Anth" + "ropic",
    "langchain-" + "openai",
    "langchain-" + "anthropic",
    "OPEN" + "AI_API_KEY",
    "ANTH" + "ROPIC_API_KEY",
]

SKIP_DIRS = {".git", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".example", ""}

# The policy governs which providers this code CALLS, not which ones it may name.
# Benchmark reports must be free to cite competitor scores by vendor, and .env is
# gitignored local state rather than shipped source.
# Docs/history may *name* removed params (e.g. a past `allow_mock` kwarg) for context
# without reintroducing them — skip them so the audit does not flag its own deny list
# or historical references (CONTRIBUTING.md commit log, the audit report itself).
SKIP_FILES = {
    ".env",
    "docs/BENCHMARK-REPORT.md",
    "docs/CODE-AUDIT-2026-08-03.md",
    "CONTRIBUTING.md",
    "scripts/audit_stepfun_policy.py",
}


def should_scan(path: Path) -> bool:
    """Return True for repository text files relevant to policy enforcement."""
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.is_dir():
        return False
    if path.as_posix() in SKIP_FILES or path.name in SKIP_FILES:
        return False
    return path.suffix in TEXT_SUFFIXES or path.name in {"Makefile"}


def main() -> int:
    breaches = []
    for path in Path(".").rglob("*"):
        if not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in DENY_MARKERS:
            if marker in text:
                breaches.append((str(path), marker))

    if breaches:
        print("Stepfun-only policy breaches detected:")
        for path, marker in breaches:
            print(f"- {path}: contains {marker!r}")
        return 1

    print("Stepfun-only policy audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
