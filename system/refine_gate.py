# version: v1 | 2026-08-08 | verdict: pending-review
"""Refine Gate — a ZERO-LLM admission filter for continual-harness refinements.

WHY THIS EXISTS
---------------
`ContinualHarness` (system/continual_harness.py) can *store* refinements but nothing
decides which observations deserve storing. Without an admission gate a self-improving
loop degenerates in one of two ways:

  * store-everything -> the harness fills with transient noise, and injected context
    gets worse every epoch (memory poisoning by accretion);
  * store-nothing    -> the loop is decorative.

Prime Agent (PrimeIntellect, MIT) solves this with an LLM review gate that returns
{shouldRefine, rationale, instructions} -- see its
`packages/coding-agent/src/core/refinement/refinement.ts` AUTO_REFINE_REVIEW_SYSTEM_PROMPT.

WE DELIBERATELY DIVERGE FROM THAT DESIGN.

CONSTITUTION Ruling C3 (LLM boundary) forbids an LLM in the accept/reject verdict:

    "Law 11 forbids LLM in the *accept/reject verdict* only. LLM-generated
     reflections are permitted as *input to propose* (tagged `llm_reflection_input`),
     never as evaluation. The verdict (pass/fail, breaches) stays zero-LLM."
    -- CONSTITUTION.md, Article VI Section 1b, Ruling C3

So this gate computes its verdict from deterministic, reproducible features of the
trajectory. An LLM may have *written* the candidate lesson; it never *approves* it.
The same trajectory always yields the same verdict, and every verdict is explainable
by the feature vector it was derived from -- which is what makes it auditable
(Article V Section 3: Audit Trail) and testable without API keys.

THE FIVE ADMISSION SIGNALS
--------------------------
A candidate is admitted only when it is *recurrent*, *grounded*, *novel*, *resolved*,
and *specific*. Each is computed from plain data structures:

  S1 RECURRENCE  -- the same normalized failure signature appears >= 2 times.
                    One-off noise has recurrence 1. (Fixes: transient tool errors.)
  S2 GROUNDING   -- the lesson cites a verifiable artifact: a file path, an exit code,
                    a test node id, or a signal name -- AND every repo-relative file
                    path it names EXISTS ON DISK. Ungrounded prose is a hypothesis;
                    a *fabricated* citation is worse, because it looks like evidence.
                    (CONSTITUTION Article I.3 "Never Assume".)
  S3 NOVELTY     -- token-set Jaccard against every stored entry of the same kind is
                    below the duplicate threshold. Re-storing a known lesson inflates
                    the harness without adding information.
  S4 RESOLUTION  -- the trajectory shows a state transition (fail -> pass, or an error
                    that stopped recurring). A lesson drawn from an *unresolved*
                    failure encodes a guess about a bug we never actually fixed.
  S5 SPECIFICITY -- the content is not generic filler ("be careful", "handle errors").
                    Measured by banned-generic-phrase match + minimum content length.

THE HALLUCINATED-CITATION attack (found by adversarial review, 2026-08-08)
-------------------------------------------------------------------------
S2 originally checked only that the text *matched the shape* of an artifact
reference. A candidate citing `system/quantum_flux_resolver.py` -- a file that has
never existed in this repo -- passed the full conjunctive gate with zero failing
signals. Shape is not grounding: an LLM writing a plausible-looking path produces
exactly that string, and the gate was rewarding fluency instead of truth.

Grounding is therefore checked in THREE escalating tiers, because each defeats a
different fabrication:

  T1 SHAPE         -- does the text reference an artifact at all? Catches vibe reports.
  T2 EXISTENCE     -- do the repo-relative paths resolve on disk? Catches the invented
                      path (`system/quantum_flux_resolver.py`).
  T3 CORROBORATION -- does AT LEAST ONE cited artifact appear in the trajectory?
                      Catches MISATTRIBUTION: a real, existing file blamed for a
                      failure it had no part in. This attack survives T2 precisely
                      because the file is real -- the lie is the causal claim, not the
                      path. Independently identified by adversarial review as feature
                      F3 ("citation-must-appear-in-trajectory"), a strictly stronger
                      test than A-MAC's ROUGE-L confidence scoring
                      (arxiv 2603.04549) because it is a hard veto rather than a
                      soft score.
                      NOTE the "at least one" quantifier: an all-paths rule measured
                      10% admission on the genuine corpus, because a useful lesson
                      names the FIX LOCATION while the trace names the FAILING TEST.

Each tier is skipped only when its input is unavailable (no repo_root, no events),
and the SignalReport says which tier actually ran -- a weaker guarantee must never be
silently reported as a strong one.

COMBINATION RULE: conjunctive (all-of), not a weighted sum.
A weighted sum lets a strong score on one axis smuggle in a candidate that fails
another; e.g. a highly-recurrent but completely ungrounded string would pass a
0.6-threshold sum. For an *append-mostly durable store* the asymmetry of costs is
stark: a wrongly-admitted entry is injected into future context forever (and is only
removed by an explicit pruning pass), while a wrongly-rejected entry costs one
missed lesson that will recur and be re-proposed next epoch. Conjunctive admission
biases the error toward the cheap, self-correcting direction. This is the same
reasoning as CONSTITUTION Article VI P7 (Least Sufficient Intervention): a control
that does not demonstrably catch a failure should not exist -- so every signal here
must be individually load-bearing, and a weighted sum would let a signal go slack
without anyone noticing.

Ruling F2 (metric honesty) applies to how this module reports itself: the gate's
admission rate is NOT a quality metric. A high admission rate means the corpus was
clean, not that the system is learning well. Report admitted/rejected counts
separately from any capability measure.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

# --- thresholds -------------------------------------------------------------
# Each is a policy constant with a stated reason; none is a magic number.

#: A signature seen once is an incident; seen twice is a pattern. The cheapest
#: possible recurrence bar that still excludes pure one-offs.
MIN_RECURRENCE = 2

#: Token-set Jaccard at or above this against an existing entry means "we already
#: know this". 0.75 tolerates rewording while catching restatement.
DUPLICATE_JACCARD = 0.75

#: Below this many characters a lesson cannot carry a reproducible instruction.
MIN_CONTENT_CHARS = 40

#: Generic filler that reads like advice but constrains no future action.
GENERIC_PHRASES = (
    "be careful",
    "handle errors",
    "improve error handling",
    "write better code",
    "add more tests",
    "follow best practices",
    "make it more robust",
    "pay attention",
    "do better",
    "keep it simple",
)

#: Patterns that make a claim checkable by someone other than its author.
_ARTIFACT_PATTERNS = (
    re.compile(r"\b[\w./-]+\.(?:py|md|json|jsonl|toml|yaml|yml|txt|cfg|ini|sh)\b"),  # file path
    re.compile(r"\b(?:exit|return)[ _]code[ =:]*\d+\b", re.I),                       # exit code
    re.compile(r"\btests?/[\w./-]+::[\w:\[\]-]+"),                                    # pytest node id
    re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b"),                                            # SIGNAL_NAME / ERRNAME
    re.compile(r"\b[\w.]+Error\b|\b[\w.]+Exception\b"),                               # exception type
    re.compile(r"\b[0-9a-f]{7,40}\b"),                                                # commit sha
)

#: Volatile substrings stripped before hashing a failure signature, so that the
#: SAME logical failure recurring at different times/addresses/pids collapses to one
#: signature. Without this, recurrence would always read as 1 and S1 would never fire.
#: ORDER MATTERS. Composite patterns (timestamps, durations, pids) must run BEFORE
#: the bare-integer sweep, otherwise that sweep shreds them into fragments that
#: survive tokenization. A regression of exactly this shape was caught by
#: test_normalize_signature_collapses_volatile_fragments: `2026-08-08T03:00:01`
#: became the residual token `08t03`, which differs per run and defeated the whole
#: point of normalization. The final `\b\w*\d+\w*\b` sweep therefore drops ANY token
#: containing a digit, which also catches alphanumeric debris (`08t03`, `19t44`) that
#: composite removal can leave behind. Digit-bearing identifiers are volatile by
#: nature here; the discriminating content of a failure lives in its words
#: (exception type, symbol names), which this preserves -- verified by
#: test_normalize_signature_distinguishes_different_failures.
_VOLATILE_PATTERNS = (
    re.compile(r"0x[0-9a-fA-F]+"),                        # memory addresses
    re.compile(r"\d{4}-\d{2}-\d{2}[t ]?[\d:.,+-]*", re.I),  # ISO timestamps (date, optional time)
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),          # bare clock times
    re.compile(r"\bpid[= ]?\d+\b", re.I),                 # pids
    re.compile(r"\bline \d+\b", re.I),                    # shifting line numbers
    re.compile(r"\b\d+(?:\.\d+)?(?:s|ms|us|ns)\b", re.I),  # durations
    re.compile(r"/tmp/[\w./-]+"),                         # temp paths
    re.compile(r"\b\w*\d+\w*\b"),                         # any token containing a digit
)

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class RefineGateError(Exception):
    """Raised when the gate is called with structurally invalid input."""


# --- data model -------------------------------------------------------------
@dataclass
class TrajectoryEvent:
    """One observed step. Deliberately minimal so any producer can emit it.

    kind:    free-form event class, e.g. "tool_call" | "test_result" | "error".
    name:    the thing that happened, e.g. a tool name or test node id.
    status:  "pass" | "fail" | "error" | "ok" | None.
    detail:  raw text (stderr, message, assertion) used for signature extraction.
    """

    kind: str
    name: str = ""
    status: str | None = None
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefinementCandidate:
    """A proposed harness entry awaiting admission."""

    kind: str
    title: str
    content: str
    evidence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalReport:
    """One admission signal's deterministic outcome."""

    name: str
    passed: bool
    value: float
    threshold: float
    reason: str


@dataclass
class GateVerdict:
    """The gate's decision. `should_refine` is the only authoritative field.

    `signals` is the full explanation; `rationale` is a human-readable join of the
    failing (or, when admitted, the passing) signal reasons. There is no confidence
    score on purpose: a deterministic conjunctive rule either passes or does not,
    and publishing a pseudo-probability would invite treating a reject as a
    "close call" worth overriding.
    """

    should_refine: bool
    rationale: str
    signals: list[SignalReport] = field(default_factory=list)
    signature: str = ""

    def failed_signals(self) -> list[str]:
        return [s.name for s in self.signals if not s.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_refine": self.should_refine,
            "rationale": self.rationale,
            "signature": self.signature,
            "signals": [
                {
                    "name": s.name,
                    "passed": s.passed,
                    "value": s.value,
                    "threshold": s.threshold,
                    "reason": s.reason,
                }
                for s in self.signals
            ],
        }


# --- primitives -------------------------------------------------------------
def normalize_signature(text: str) -> str:
    """Collapse a raw failure string to a stable signature.

    Volatile fragments (addresses, timestamps, pids, line numbers, durations, temp
    paths, bare integers) are stripped so the same logical failure recurring under
    different runtime conditions hashes identically. This is the single most
    load-bearing helper in the module: if it under-normalizes, recurrence is always
    1 and nothing is ever admitted; if it over-normalizes, distinct failures merge
    and unrelated noise looks recurrent.
    """
    low = (text or "").lower()
    for pattern in _VOLATILE_PATTERNS:
        low = pattern.sub(" ", low)
    tokens = _TOKEN_RE.findall(low)
    if not tokens:
        return ""
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()[:16]


def tokenize(text: str) -> set[str]:
    """Lowercase alphanumeric token set, used for Jaccard similarity."""
    return set(_TOKEN_RE.findall((text or "").lower()))


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity in [0, 1]. Two empty strings are identical."""
    ta, tb = tokenize(a), tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


#: Matches a repo-relative source path. Used for the EXISTENCE check (not just shape),
#: which is what defeats a fabricated-but-plausible citation.
_FILE_PATH_RE = re.compile(r"\b((?:[\w-]+/)+[\w.-]+\.(?:py|md|json|jsonl|toml|yaml|yml|txt|cfg|ini|sh))\b")

#: Pytest node ids carry a file path before "::" — extract it for the same check.
_NODE_ID_RE = re.compile(r"\b((?:[\w-]+/)*[\w.-]+\.py)::")


def cited_paths(text: str) -> list[str]:
    """Every repo-relative file path named in the text, including pytest node ids."""
    found = set(_FILE_PATH_RE.findall(text or ""))
    found.update(_NODE_ID_RE.findall(text or ""))
    return sorted(found)


def cites_artifact(text: str) -> bool:
    """True when the text names something a third party can independently check."""
    return any(p.search(text or "") for p in _ARTIFACT_PATTERNS)


# --- signals ----------------------------------------------------------------
def _failure_texts(events: Sequence[TrajectoryEvent]) -> list[str]:
    """Text of every event that represents a failure, for signature counting."""
    out: list[str] = []
    for ev in events:
        if (ev.status or "").lower() in ("fail", "failed", "error"):
            out.append(f"{ev.name} {ev.detail}".strip())
        elif ev.kind.lower() in ("error", "failure"):
            out.append(f"{ev.name} {ev.detail}".strip())
    return out


def signal_recurrence(events: Sequence[TrajectoryEvent]) -> SignalReport:
    """S1: the dominant failure signature must appear at least MIN_RECURRENCE times."""
    signatures = [normalize_signature(t) for t in _failure_texts(events)]
    signatures = [s for s in signatures if s]
    if not signatures:
        return SignalReport(
            "recurrence", False, 0.0, float(MIN_RECURRENCE),
            "no failure events in trajectory; nothing recurred",
        )
    counts: dict[str, int] = {}
    for sig in signatures:
        counts[sig] = counts.get(sig, 0) + 1
    top_sig, top_count = max(counts.items(), key=lambda kv: kv[1])
    passed = top_count >= MIN_RECURRENCE
    return SignalReport(
        "recurrence", passed, float(top_count), float(MIN_RECURRENCE),
        (
            f"failure signature {top_sig} recurred {top_count}x"
            if passed
            else f"top signature {top_sig} seen only {top_count}x (one-off, not a pattern)"
        ),
    )


def signal_grounding(
    candidate: RefinementCandidate,
    repo_root: str | Path | None = None,
    events: Sequence["TrajectoryEvent"] | None = None,
) -> SignalReport:
    """S2: cite an artifact that (T1) is checkable, (T2) exists, and (T3) is corroborated.

    Each tier defeats a different class of fabrication:
      * T1 SHAPE -- no artifact reference at all -> a vibe report.
      * T2 EXISTENCE -- the path does not resolve on disk -> an invented citation.
      * T3 CORROBORATION -- the path is real but never appears in the trajectory ->
        MISATTRIBUTION. A real file blamed for a failure it had no part in passes T2
        by construction, because the lie is the causal claim rather than the path.

    Tiers are skipped only when their input is missing (`repo_root=None` skips T2,
    empty `events` skips T3), and the returned reason names the tier that actually
    ran. Reporting a shape-only pass with the same wording as a corroborated pass
    would be the module lying about the strength of its own guarantee.
    """
    haystack = f"{candidate.content}\n{candidate.evidence}"
    if not cites_artifact(haystack):
        return SignalReport(
            "grounding", False, 0.0, 1.0,
            "cites no checkable artifact; unfalsifiable prose is a hypothesis, not a lesson",
        )

    paths = cited_paths(haystack)

    if repo_root is None:
        return SignalReport(
            "grounding", True, 1.0, 1.0,
            "T1 only: cites a verifiable artifact (no repo_root given for existence check)",
        )

    root = Path(repo_root)
    missing = [p for p in paths if not (root / p).exists()]
    if missing:
        return SignalReport(
            "grounding", False, 0.0, 1.0,
            f"T2 failed: cites path(s) that do not exist on disk: {missing[:3]}; "
            "a fabricated citation is not evidence",
        )

    if not events:
        return SignalReport(
            "grounding", True, 1.0, 1.0,
            f"T2 passed: {len(paths)} cited path(s) verified on disk "
            "(no trajectory supplied for corroboration)",
        )

    # T3: AT LEAST ONE cited artifact must appear in the observed trajectory.
    #
    # The rule is "any", not "all", and that distinction was found empirically: an
    # all-paths rule rejected 9 of 10 genuine lessons. The reason is structural -- a
    # useful lesson names the FIX LOCATION ("wrap writes in benchmarks/... with a
    # lock") while the trace names the FAILING TEST. Those are legitimately different
    # files, so demanding every citation appear in the trace forbids exactly the
    # diagnostic content that makes a lesson worth keeping.
    #
    # One anchor is enough to defeat misattribution, which is the actual attack: the
    # misattributing candidate cites only files unconnected to the failure, so it has
    # no anchor at all. Requiring one anchor keeps the veto while allowing the lesson
    # to reach beyond what already failed.
    #
    # Matching also accepts the basename, because a trace commonly reports
    # `test_kernel.py` where the lesson writes `tests/test_kernel.py`.
    trace = "\n".join(f"{e.name} {e.detail}" for e in events)
    anchored = [
        p for p in paths
        if p in trace or p.rsplit("/", 1)[-1] in trace
    ]
    if paths and not anchored:
        return SignalReport(
            "grounding", False, 0.0, 1.0,
            f"T3 failed: none of the cited path(s) {paths[:3]} appear in the trajectory; "
            "the files are real but the causal claim is unsupported (misattribution)",
        )

    return SignalReport(
        "grounding", True, 1.0, 1.0,
        (
            f"T3 passed: {len(anchored)}/{len(paths)} cited path(s) anchored in the trajectory"
            if paths
            else "cites a verifiable artifact (exit code / signal / exception)"
        ),
    )


def signal_novelty(candidate: RefinementCandidate, existing: Iterable[Any]) -> SignalReport:
    """S3: must not restate an entry already stored under the same kind.

    `existing` accepts anything with `.kind` and `.content` (HarnessEntry) or plain
    dicts, so the gate stays decoupled from the harness implementation.
    """
    best = 0.0
    best_id = ""
    for entry in existing or []:
        e_kind = getattr(entry, "kind", None) if not isinstance(entry, dict) else entry.get("kind")
        if e_kind != candidate.kind:
            continue
        e_content = getattr(entry, "content", "") if not isinstance(entry, dict) else entry.get("content", "")
        score = jaccard(candidate.content, e_content)
        if score > best:
            best = score
            best_id = (
                getattr(entry, "id", "") if not isinstance(entry, dict) else str(entry.get("id", ""))
            )
    passed = best < DUPLICATE_JACCARD
    return SignalReport(
        "novelty", passed, best, DUPLICATE_JACCARD,
        (
            f"most similar existing entry scores {best:.2f} (below duplicate bar)"
            if passed
            else f"duplicates existing entry {best_id!r} at similarity {best:.2f}"
        ),
    )


def signal_resolution(events: Sequence[TrajectoryEvent]) -> SignalReport:
    """S4: the trajectory must show a failure that was actually resolved.

    Two accepted shapes of evidence:
      (a) a named check transitions fail -> pass within the trajectory; or
      (b) a failure signature stops appearing after some point AND a later event
          reports success.

    A lesson mined from a still-broken run encodes an unverified guess -- exactly the
    "narrate success" failure mode CONSTITUTION Article VI Section 2 rejects.
    """
    last_status: dict[str, str] = {}
    for ev in events:
        status = (ev.status or "").lower()
        if not ev.name or status not in ("pass", "passed", "ok", "fail", "failed", "error"):
            continue
        prior = last_status.get(ev.name)
        now_pass = status in ("pass", "passed", "ok")
        if prior in ("fail", "failed", "error") and now_pass:
            return SignalReport(
                "resolution", True, 1.0, 1.0,
                f"{ev.name!r} transitioned fail -> pass within the trajectory",
            )
        last_status[ev.name] = status

    failure_positions = [
        i for i, ev in enumerate(events)
        if (ev.status or "").lower() in ("fail", "failed", "error") or ev.kind.lower() in ("error", "failure")
    ]
    success_positions = [
        i for i, ev in enumerate(events)
        if (ev.status or "").lower() in ("pass", "passed", "ok")
    ]
    if failure_positions and success_positions and max(success_positions) > max(failure_positions):
        return SignalReport(
            "resolution", True, 1.0, 1.0,
            "failures ceased and a later event reported success",
        )
    return SignalReport(
        "resolution", False, 0.0, 1.0,
        "no fail -> pass transition; lesson would encode an unverified guess",
    )


def signal_specificity(candidate: RefinementCandidate) -> SignalReport:
    """S5: reject generic filler and content too short to constrain future action."""
    content = (candidate.content or "").strip()
    if len(content) < MIN_CONTENT_CHARS:
        return SignalReport(
            "specificity", False, float(len(content)), float(MIN_CONTENT_CHARS),
            f"content is {len(content)} chars; too short to carry a reproducible instruction",
        )
    low = content.lower()
    hits = [p for p in GENERIC_PHRASES if p in low]
    # Filler only disqualifies when it is the substance, not when it appears
    # alongside a concrete instruction. Proxy for "is it the substance":
    # short content whose text is dominated by the generic phrase.
    if hits and len(content) < 2 * MIN_CONTENT_CHARS:
        return SignalReport(
            "specificity", False, float(len(content)), float(MIN_CONTENT_CHARS),
            f"generic filler {hits[0]!r} with no concrete instruction attached",
        )
    return SignalReport(
        "specificity", True, float(len(content)), float(MIN_CONTENT_CHARS),
        "content is long enough and not generic filler",
    )


# --- the gate ---------------------------------------------------------------
def review(
    candidate: RefinementCandidate,
    events: Sequence[TrajectoryEvent],
    existing_entries: Iterable[Any] = (),
    repo_root: str | Path | None = None,
) -> GateVerdict:
    """Decide whether `candidate` may be persisted. Deterministic; never calls an LLM.

    Returns a GateVerdict whose `signals` list fully explains the outcome. Admission
    is conjunctive: every signal must pass.
    """
    if not isinstance(candidate, RefinementCandidate):
        raise RefineGateError("candidate must be a RefinementCandidate")
    if candidate.kind not in ("prompt", "memory", "skill", "subagent"):
        raise RefineGateError(
            f"unknown harness kind {candidate.kind!r}; expected prompt|memory|skill|subagent"
        )
    events = list(events or [])

    signals = [
        signal_recurrence(events),
        signal_grounding(candidate, repo_root, events),
        signal_novelty(candidate, existing_entries),
        signal_resolution(events),
        signal_specificity(candidate),
    ]
    admitted = all(s.passed for s in signals)

    failure_texts = _failure_texts(events)
    signature = ""
    if failure_texts:
        counts: dict[str, int] = {}
        for text in failure_texts:
            sig = normalize_signature(text)
            if sig:
                counts[sig] = counts.get(sig, 0) + 1
        if counts:
            signature = max(counts.items(), key=lambda kv: kv[1])[0]

    if admitted:
        rationale = "admitted: " + "; ".join(s.reason for s in signals)
    else:
        rationale = "rejected: " + "; ".join(s.reason for s in signals if not s.passed)

    return GateVerdict(
        should_refine=admitted,
        rationale=rationale,
        signals=signals,
        signature=signature,
    )
