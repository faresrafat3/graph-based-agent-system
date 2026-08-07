"""Graph-based localizer: a staged, auditable pipeline instead of one lexical score.

WHY THIS REPLACES THE FLAT SCORER
---------------------------------
The measured failure profile (n=336, `docs/LOCALIZER-MEASUREMENT.md`) is not one problem:

    47 ranking failures   — gold IS in the top-10, ordered 4..10
    55 retrieval failures — gold never surfaced at all

And the discriminator between success and failure is sharp:

    gold FILENAME appears in the issue text    hit@3 67.5% | rank-fail 40.4% | retr-fail 14.5%

So the flat scorer works when the issue names the file and collapses when it does not.
Issue length is irrelevant (68.8% short vs 70.0% long): the gap is LEXICAL, not
informational. Users write behaviour ("model_to_dict", "CASCADE", "IntegerChoices");
the file is named `models.py`, `deletion.py`, `enums.py`.

Measured directly: of the 102 failures, **51 name a def/class DEFINED in the gold file**
(40% of retrieval failures, 62% of ranking failures) — an upper bound of 84.8% hit@3.
`localize()` cannot see this because it scores a definition exactly like any other token
in the file body.

THE STAGES (each one responsibility, each zero-LLM, each independently measurable)

    1. RETRIEVE  — widen the candidate pool: path hints + lexical IDF + symbol index
    2. RERANK    — score candidates on evidence the retrieve stage cannot use
    3. VERIFY    — drop candidates that fail a structural check
    4. EMIT      — final top-k, with the evidence trail that produced it

This mirrors the rest of the system (decompose -> validate -> refine -> verify) rather
than being the one component that is a bare function. Every stage returns its reasoning,
so a wrong answer can be traced to the stage that caused it.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# Definitions carry far more weight than mentions: a token that a file DEFINES is
# evidence about that file; the same token used elsewhere is evidence about the caller.
SYMBOL_DEF_RE = re.compile(r"^[ \t]*(?:class|def)[ \t]+([A-Za-z_]\w{2,})", re.M)

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "you", "are", "not", "but",
    "have", "was", "were", "would", "should", "could", "when", "then", "than", "there",
    "here", "what", "which", "will", "can", "get", "set", "use", "using", "used", "one",
    "two", "how", "why", "does", "did", "doing", "any", "all", "some", "its", "it's",
    "self", "none", "true", "false", "return", "returns", "import", "python", "code",
    "issue", "bug", "error", "problem", "expected", "actual", "example", "file", "line",
}

MAX_FILE_BYTES = 400_000
HEAD_BYTES = 60_000


@dataclass
class Candidate:
    """One file under consideration, with the evidence for it kept separable."""

    path: str
    lexical: float = 0.0
    symbol: float = 0.0
    path_hint: bool = False
    matched_symbols: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        # A named path is near-decisive; symbol evidence outranks bag-of-words because a
        # definition is a statement about the file, not an incidental mention.
        return (1000.0 if self.path_hint else 0.0) + 3.0 * self.symbol + self.lexical

    def evidence(self) -> dict:
        return {
            "path": self.path,
            "score": round(self.score, 3),
            "path_hint": self.path_hint,
            "symbol": round(self.symbol, 3),
            "lexical": round(self.lexical, 3),
            "matched_symbols": self.matched_symbols[:6],
        }


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    return [t for t in raw if t not in STOP_WORDS]


def split_identifier(name: str) -> list[str]:
    """`model_to_dict` / `IntegerChoices` -> component words.

    Lets a query phrased in prose ("integer choices") reach a symbol written in code.
    """
    parts = re.split(r"[_\W]+", name)
    out: list[str] = []
    for part in parts:
        out.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", part) or [part])
    return [p.lower() for p in out if len(p) > 2]


def list_source_files(root: str, limit: int = 6000) -> list[str]:
    """Repo-relative .py paths, excluding tests, docs and vendored trees."""
    skip = {".git", "node_modules", "build", "dist", ".tox", "__pycache__", ".eggs"}
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            low = rel.lower()
            if "test" in low or low.startswith("doc"):
                continue
            out.append(rel)
            if len(out) >= limit:
                return out
    return out


def explicit_path_hints(problem: str, root: str) -> list[str]:
    """Files the issue names outright — strongest available evidence, kept in order."""
    hits: list[str] = []
    for match in re.findall(r"[\w/]+\.py", problem):
        candidate = match.lstrip("/")
        if os.path.isfile(os.path.join(root, candidate)):
            hits.append(candidate)
        else:
            # Tracebacks quote absolute or site-packages paths; match on the tail.
            tail = candidate.split("/")[-1]
            for rel in list_source_files(root):
                if rel.endswith("/" + tail) or rel == tail:
                    hits.append(rel)
                    break
    seen: set[str] = set()
    return [h for h in hits if not (h in seen or seen.add(h))]


# ---- Stage 1: RETRIEVE ---------------------------------------------------------------

def retrieve(problem: str, root: str, pool_size: int = 40) -> tuple[list[Candidate], dict]:
    """Widen the candidate pool using three independent signals.

    Returns a POOL, not an answer. Recall matters here; precision is the reranker's job.
    """
    query = Counter(tokenize(problem))
    hints = explicit_path_hints(problem, root)
    files = list_source_files(root)

    # Pass 1: per-file token hits + symbol definitions, and their document frequencies.
    doc_hits: dict[str, set[str]] = {}
    doc_syms: dict[str, set[str]] = {}
    doc_freq: Counter = Counter()
    sym_freq: Counter = Counter()

    for rel in files:
        full = os.path.join(root, rel)
        try:
            if os.path.getsize(full) > MAX_FILE_BYTES:
                continue
            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                head = fh.read(HEAD_BYTES)
        except OSError:
            continue

        hits = set(tokenize(head)) & query.keys()
        doc_hits[rel] = hits
        for token in hits:
            doc_freq[token] += 1

        syms = set(SYMBOL_DEF_RE.findall(head))
        doc_syms[rel] = syms
        for sym in syms:
            sym_freq[sym] += 1

    total = max(len(doc_hits), 1)

    def idf(freq: Counter, token: str) -> float:
        return math.log(1 + total / (1 + freq[token]))

    # Which defined symbols does the issue actually name? Exact identifier first, then
    # the split form so prose can reach camelCase/snake_case definitions.
    problem_lower = problem.lower()
    problem_tokens = set(tokenize(problem))

    candidates: dict[str, Candidate] = {}
    for rel in doc_hits:
        cand = Candidate(path=rel, path_hint=rel in hints)

        path_hits = set(tokenize(rel)) & query.keys()
        cand.lexical = (
            sum(query[t] * idf(doc_freq, t) for t in path_hits) * 6.0
            + sum(query[t] * idf(doc_freq, t) for t in doc_hits[rel])
        )

        for sym in doc_syms.get(rel, ()):  # symbol evidence, weighted by rarity
            if re.search(rf"\b{re.escape(sym)}\b", problem):
                cand.symbol += 4.0 * idf(sym_freq, sym)
                cand.matched_symbols.append(sym)
            elif len(sym) > 6 and sym.lower() in problem_lower:
                cand.symbol += 2.0 * idf(sym_freq, sym)
                cand.matched_symbols.append(sym)
            else:
                words = split_identifier(sym)
                if len(words) > 1 and set(words) <= problem_tokens:
                    cand.symbol += 1.5 * idf(sym_freq, sym)
                    cand.matched_symbols.append(sym)

        if cand.score > 0:
            candidates[rel] = cand

    for rel in hints:  # a named path enters the pool even with no lexical overlap
        candidates.setdefault(rel, Candidate(path=rel, path_hint=True))

    pool = sorted(candidates.values(), key=lambda c: (-c.score, c.path))[:pool_size]
    return pool, {
        "stage": "retrieve",
        "files_scanned": len(doc_hits),
        "path_hints": hints,
        "pool_size": len(pool),
    }


# ---- Stage 2: RERANK -----------------------------------------------------------------

def rerank(pool: list[Candidate], problem: str) -> tuple[list[Candidate], dict]:
    """Re-order the pool using evidence retrieval could not weigh.

    Targets the 47 measured ranking failures: gold was already retrieved, just ranked
    4..10. Two corrections, both derived from the failure sample:

      * dunder/private modules (`__init__.py`, `base.py`, `utils.py`) accumulate lexical
        mass because everything imports them — demoted unless they carry symbol evidence.
      * a candidate matching several distinct issue symbols is far stronger than one
        matching a single common token.
    """
    generic = {"__init__.py", "base.py", "utils.py", "core.py", "common.py", "helpers.py"}
    adjusted = []
    for cand in pool:
        bonus = 0.0
        if len(cand.matched_symbols) >= 2:
            bonus += 2.0 * len(set(cand.matched_symbols))
        if os.path.basename(cand.path) in generic and not cand.matched_symbols:
            bonus -= 0.35 * cand.lexical  # lexical mass without a definition is weak
        cand.lexical += bonus
        adjusted.append(cand)

    ranked = sorted(adjusted, key=lambda c: (-c.score, c.path))
    return ranked, {
        "stage": "rerank",
        "promoted_by_symbols": sum(1 for c in ranked if len(c.matched_symbols) >= 2),
    }


# ---- Stage 3: VERIFY -----------------------------------------------------------------

def verify(ranked: list[Candidate], root: str) -> tuple[list[Candidate], dict]:
    """Drop candidates that cannot be edit targets (P2: closure, not self-report)."""
    kept, dropped = [], []
    for cand in ranked:
        full = os.path.join(root, cand.path)
        try:
            if os.path.getsize(full) == 0:
                dropped.append(cand.path)
                continue
        except OSError:
            dropped.append(cand.path)
            continue
        kept.append(cand)
    return kept, {"stage": "verify", "dropped": dropped[:10], "dropped_count": len(dropped)}


# ---- Stage 4: EMIT -------------------------------------------------------------------

def localize_graph(problem: str, root: str, top_k: int = 5,
                   with_trace: bool = False) -> list[str] | tuple[list[str], dict]:
    """Run the staged localizer. Drop-in replacement for `localize()`.

    `with_trace=True` returns the per-stage evidence so a wrong answer can be attributed
    to the stage that produced it rather than to "the localizer".
    """
    pool, retrieve_info = retrieve(problem, root)
    ranked, rerank_info = rerank(pool, problem)
    kept, verify_info = verify(ranked, root)

    top = kept[:top_k]
    paths = [c.path for c in top]
    if not with_trace:
        return paths
    return paths, {
        "stages": [retrieve_info, rerank_info, verify_info],
        "evidence": [c.evidence() for c in top],
    }
