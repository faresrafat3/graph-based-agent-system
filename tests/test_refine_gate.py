"""Tests for system/refine_gate.py — the zero-LLM refinement admission gate.

The headline assertions are CORPUS-LEVEL, not single-case: the gate must reject the
overwhelming majority of a noise corpus and admit the overwhelming majority of a
genuine-repeat corpus. Single-case tests below exist to pin *why* each signal fires,
so a future refactor that changes a threshold fails with a readable reason.

No API keys, no network, no LLM. Every verdict here is reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from system.refine_gate import (
    DUPLICATE_JACCARD,
    MIN_CONTENT_CHARS,
    MIN_RECURRENCE,
    GateVerdict,
    RefinementCandidate,
    RefineGateError,
    TrajectoryEvent,
    cited_paths,
    cites_artifact,
    jaccard,
    normalize_signature,
    review,
    signal_grounding,
    signal_novelty,
    signal_recurrence,
    signal_resolution,
    signal_specificity,
)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def fail(n: str, d: str) -> TrajectoryEvent:
    return TrajectoryEvent(kind="test_result", name=n, status="fail", detail=d)


def ok(n: str) -> TrajectoryEvent:
    return TrajectoryEvent(kind="test_result", name=n, status="pass", detail="")


def resolved_trajectory(name: str, detail: str, repeats: int = 2) -> list[TrajectoryEvent]:
    """A failure that recurs `repeats` times and is then fixed."""
    return [fail(name, detail) for _ in range(repeats)] + [ok(name)]


def pytest_trajectory(node_id: str, detail: str, repeats: int = 2) -> list[TrajectoryEvent]:
    """A REALISTIC pytest trajectory: the node id carries the file path.

    Real pytest output always names the file (`tests/test_x.py::test_y`) and
    tracebacks name the source file. An earlier version of this corpus used bare
    test names, which made T3 corroboration impossible to satisfy and produced a
    misleading 10% admission rate on genuine lessons -- the fixture was wrong, not
    the gate. Traces here mirror what the harness actually observes.
    """
    return [fail(node_id, detail) for _ in range(repeats)] + [ok(node_id)]


def good_candidate(**overrides) -> RefinementCandidate:
    base = dict(
        kind="memory",
        title="atomic write needed on shared jsonl",
        content=(
            "benchmarks/results/local_arms.jsonl loses rows when two arms append "
            "concurrently; wrap writes in a lock and use os.replace for atomicity."
        ),
        evidence="tests/test_metrics.py::test_concurrent_append exit code 1",
    )
    base.update(overrides)
    return RefinementCandidate(**base)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------


def test_normalize_signature_collapses_volatile_fragments():
    """The same logical failure at different times/addresses/lines is ONE signature.

    This is the load-bearing property: if it fails, recurrence always reads 1 and
    the gate admits nothing.
    """
    a = "AssertionError at 0x7ffab12 line 44 pid=901 2026-08-08T03:00:01 took 1.5s"
    b = "AssertionError at 0x9cc0011 line 87 pid=1422 2026-08-07T19:12:44 took 9.8s"
    assert normalize_signature(a) == normalize_signature(b)


def test_normalize_signature_distinguishes_different_failures():
    assert normalize_signature("KeyError: harness") != normalize_signature("TimeoutError: kernel")


def test_normalize_signature_empty_input_is_empty():
    assert normalize_signature("") == ""
    assert normalize_signature("0x1 123 /tmp/x") == ""


def test_jaccard_bounds():
    assert jaccard("alpha beta", "alpha beta") == 1.0
    assert jaccard("alpha", "beta") == 0.0
    assert 0.0 < jaccard("alpha beta gamma", "alpha beta delta") < 1.0


@pytest.mark.parametrize(
    "text",
    [
        "system/refine_gate.py raised",
        "exit code 2 returned",
        "tests/test_kernel.py::test_route_signal failed",
        "HUMAN_CHECKPOINT emitted instead",
        "PermissionError on write",
        "a18809e00ea30638584d87b3afea7285a9d7296c",
    ],
)
def test_cites_artifact_detects_checkable_references(text):
    assert cites_artifact(text)


@pytest.mark.parametrize(
    "text",
    ["we should be more careful next time", "the agent seemed confused", ""],
)
def test_cites_artifact_rejects_unfalsifiable_prose(text):
    assert not cites_artifact(text)


# --------------------------------------------------------------------------
# S1 recurrence
# --------------------------------------------------------------------------


def test_recurrence_requires_a_repeat():
    single = [fail("test_a", "KeyError: harness_state")]
    assert signal_recurrence(single).passed is False

    repeated = [fail("test_a", "KeyError: harness_state") for _ in range(MIN_RECURRENCE)]
    assert signal_recurrence(repeated).passed is True


def test_recurrence_fails_with_no_failures_at_all():
    report = signal_recurrence([ok("test_a"), ok("test_b")])
    assert report.passed is False
    assert "nothing recurred" in report.reason


def test_recurrence_counts_the_dominant_signature_not_the_total():
    """Three distinct one-off failures must NOT read as recurrence 3."""
    events = [
        fail("t1", "KeyError: alpha"),
        fail("t2", "TimeoutError: beta"),
        fail("t3", "ValueError: gamma"),
    ]
    report = signal_recurrence(events)
    assert report.value == 1.0
    assert report.passed is False


# --------------------------------------------------------------------------
# S2 grounding
# --------------------------------------------------------------------------


def test_grounding_accepts_evidence_only_citation():
    cand = good_candidate(content="a" * (MIN_CONTENT_CHARS + 5), evidence="exit code 3")
    assert signal_grounding(cand).passed is True


def test_grounding_rejects_when_neither_field_cites_anything():
    cand = good_candidate(
        content="the run felt slower than usual and the agent seemed unsure of itself",
        evidence="looked wrong",
    )
    assert signal_grounding(cand).passed is False


# --- REGRESSION: the hallucinated-citation attack (adversarial review 2026-08-08) ---
# A candidate citing a plausible-but-nonexistent path passed the FULL conjunctive gate
# with zero failing signals. Shape is not grounding. These tests pin the fix.


def test_grounding_rejects_a_fabricated_path_when_repo_root_is_given(tmp_path):
    cand = good_candidate(
        content="The bug lives in system/quantum_flux_resolver.py and breaks dispatch.",
        evidence="tests/test_quantum_flux.py::test_nonexistent exit code 1",
    )
    report = signal_grounding(cand, repo_root=tmp_path)
    assert report.passed is False
    assert "do not exist on disk" in report.reason


def test_grounding_accepts_paths_that_actually_exist(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "real_module.py").write_text("x = 1\n")
    cand = good_candidate(
        content="system/real_module.py mishandles the empty case and returns None silently.",
        evidence="exit code 1",
    )
    assert signal_grounding(cand, repo_root=tmp_path).passed is True


def test_grounding_extracts_the_path_from_a_pytest_node_id(tmp_path):
    """A node id like tests/x.py::test_y must have its file checked for existence."""
    cand = good_candidate(content="a" * 60, evidence="tests/ghost.py::test_missing exit code 1")
    assert signal_grounding(cand, repo_root=tmp_path).passed is False


def test_grounding_without_paths_still_passes_on_exit_code_alone(tmp_path):
    """Not every real lesson names a file; an exit code is still checkable evidence."""
    cand = good_candidate(
        content="The gate command returns exit code 124 on timeout, which must count as a failure.",
        evidence="exit code 124",
    )
    assert signal_grounding(cand, repo_root=tmp_path).passed is True


def test_review_blocks_the_hallucinated_citation_end_to_end(tmp_path):
    """The full gate, not just the signal, must refuse a fabricated citation."""
    cand = good_candidate(
        content="The bug lives in system/quantum_flux_resolver.py and breaks the kernel.",
        evidence="tests/test_quantum_flux.py::test_nonexistent exit code 1",
    )
    verdict = review(cand, resolved_trajectory("t", "AssertionError: nope"), [], repo_root=tmp_path)
    assert verdict.should_refine is False
    assert "grounding" in verdict.failed_signals()


def test_shape_only_tier_is_reachable_but_documented_as_weaker():
    """repo_root=None keeps the old shape-only behaviour for context-free callers."""
    cand = good_candidate(content="Fabricated system/nowhere_at_all.py reference here.", evidence="")
    report = signal_grounding(cand, repo_root=None)
    assert report.passed is True
    # The reason must disclose WHICH tier ran, so a weak pass is never mistaken for a
    # strong one. Assert the disclosure, not the exact wording.
    assert "T1" in report.reason and "existence" in report.reason


def test_cited_paths_finds_both_plain_paths_and_node_ids():
    text = "see system/a.py and tests/b.py::test_c and docs/d.md"
    assert cited_paths(text) == ["docs/d.md", "system/a.py", "tests/b.py"]


# --- REGRESSION: the MISATTRIBUTION attack (adversarial review round 2, 2026-08-08) ---
# The existence check (T2) is defeated by citing a file that is REAL but had nothing to
# do with the observed failure. The path resolves, so T2 passes; the lie is the causal
# claim. T3 requires the citation to actually appear in the trajectory.


def test_grounding_rejects_a_real_path_absent_from_the_trajectory(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "self_pruning.py").write_text("x = 1\n")
    cand = good_candidate(
        content="The failure originates in system/self_pruning.py which mishandles the empty list.",
        evidence="exit code 1",
    )
    # the trajectory blames a completely different component
    events = resolved_trajectory("test_continual_harness", "AssertionError: scope mismatch")
    report = signal_grounding(cand, repo_root=tmp_path, events=events)
    assert report.passed is False
    assert "T3 failed" in report.reason
    assert "misattribution" in report.reason


def test_grounding_accepts_a_path_corroborated_by_the_trajectory(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "continual_harness.py").write_text("x = 1\n")
    cand = good_candidate(
        content="system/continual_harness.py load() defaults scope to the parent directory name.",
        evidence="exit code 1",
    )
    events = [
        fail("test_scope", "AssertionError in system/continual_harness.py: scope == system"),
        fail("test_scope", "AssertionError in system/continual_harness.py: scope == system"),
        ok("test_scope"),
    ]
    report = signal_grounding(cand, repo_root=tmp_path, events=events)
    assert report.passed is True
    assert "T3 passed" in report.reason


def test_t3_matches_on_basename_so_path_prefix_differences_do_not_reject(tmp_path):
    """A trace saying 'test_kernel.py' must corroborate a lesson citing 'tests/test_kernel.py'."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_kernel.py").write_text("x = 1\n")
    cand = good_candidate(
        content="tests/test_kernel.py asserts the wrong signal name after the rename landed.",
        evidence="exit code 1",
    )
    events = [
        fail("test_kernel.py::test_route", "AssertionError: signal mismatch"),
        fail("test_kernel.py::test_route", "AssertionError: signal mismatch"),
        ok("test_kernel.py::test_route"),
    ]
    assert signal_grounding(cand, repo_root=tmp_path, events=events).passed is True


def test_t3_is_skipped_when_no_trajectory_is_supplied(tmp_path):
    """Missing input must skip a tier, never silently fail it."""
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "real.py").write_text("x = 1\n")
    cand = good_candidate(content="system/real.py mishandles the empty case entirely.", evidence="")
    report = signal_grounding(cand, repo_root=tmp_path, events=None)
    assert report.passed is True
    assert "T2 passed" in report.reason


def test_review_blocks_misattribution_end_to_end(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "self_pruning.py").write_text("x = 1\n")
    cand = good_candidate(
        content="The failure originates in system/self_pruning.py which mishandles the empty list.",
        evidence="exit code 1",
    )
    verdict = review(
        cand,
        resolved_trajectory("test_continual_harness", "AssertionError: scope mismatch"),
        [],
        repo_root=tmp_path,
    )
    assert verdict.should_refine is False
    assert "grounding" in verdict.failed_signals()


# --------------------------------------------------------------------------
# S3 novelty
# --------------------------------------------------------------------------


class _Entry:
    """Duck-typed stand-in for HarnessEntry (gate must not import the harness)."""

    def __init__(self, kind, content, id="e1"):
        self.kind = kind
        self.content = content
        self.id = id


def test_novelty_rejects_a_restatement():
    cand = good_candidate()
    existing = [_Entry("memory", cand.content)]
    report = signal_novelty(cand, existing)
    assert report.passed is False
    assert report.value >= DUPLICATE_JACCARD


def test_novelty_ignores_similar_entries_of_a_different_kind():
    """A memory and a skill may legitimately describe the same fact."""
    cand = good_candidate(kind="memory")
    existing = [_Entry("skill", cand.content)]
    assert signal_novelty(cand, existing).passed is True


def test_novelty_accepts_dict_shaped_entries():
    cand = good_candidate()
    existing = [{"kind": "memory", "content": cand.content, "id": "d1"}]
    assert signal_novelty(cand, existing).passed is False


def test_novelty_passes_against_empty_store():
    assert signal_novelty(good_candidate(), []).passed is True


# --------------------------------------------------------------------------
# S4 resolution
# --------------------------------------------------------------------------


def test_resolution_detects_fail_then_pass_on_same_check():
    events = [fail("test_x", "boom"), ok("test_x")]
    report = signal_resolution(events)
    assert report.passed is True
    assert "fail -> pass" in report.reason


def test_resolution_rejects_still_broken_trajectory():
    events = [fail("test_x", "boom"), fail("test_x", "boom")]
    assert signal_resolution(events).passed is False


def test_resolution_accepts_failures_ceasing_before_a_later_success():
    events = [fail("test_x", "boom"), fail("test_x", "boom"), ok("test_y")]
    assert signal_resolution(events).passed is True


def test_resolution_rejects_success_that_precedes_the_failure():
    """Order matters: passing first and breaking after is not a resolution."""
    events = [ok("test_y"), fail("test_x", "boom"), fail("test_x", "boom")]
    assert signal_resolution(events).passed is False


# --------------------------------------------------------------------------
# S5 specificity
# --------------------------------------------------------------------------


def test_specificity_rejects_too_short_content():
    assert signal_specificity(good_candidate(content="too short")).passed is False


def test_specificity_rejects_generic_filler():
    cand = good_candidate(content="Be careful and handle errors properly next time.")
    assert signal_specificity(cand).passed is False


def test_specificity_allows_a_generic_phrase_beside_a_concrete_instruction():
    """'add more tests' is filler alone, but fine when the instruction is concrete."""
    cand = good_candidate(
        content=(
            "add more tests for system/host_bridge.py: specifically assert that a direct "
            "harness.upsert() from a non-privileged actor raises PermissionError, since "
            "the audit check only covers the bridge path today."
        )
    )
    assert signal_specificity(cand).passed is True


# --------------------------------------------------------------------------
# the gate itself
# --------------------------------------------------------------------------


def test_review_admits_a_grounded_recurrent_resolved_candidate():
    verdict = review(
        good_candidate(),
        pytest_trajectory(
                "tests/test_metrics.py::test_concurrent_append",
                "AssertionError: lost 3 rows writing benchmarks/results/local_arms.jsonl",
            ),
        [],
    )
    assert isinstance(verdict, GateVerdict)
    assert verdict.should_refine is True
    assert verdict.failed_signals() == []
    assert verdict.signature  # a dominant signature was identified
    assert verdict.rationale.startswith("admitted:")


def test_review_is_deterministic():
    """Same inputs -> byte-identical verdict. This is the property an LLM gate lacks."""
    events = resolved_trajectory("test_x", "AssertionError: lost rows")
    first = review(good_candidate(), events, []).to_dict()
    second = review(good_candidate(), events, []).to_dict()
    assert first == second


def test_review_is_conjunctive_one_failing_signal_blocks_admission():
    """Strong recurrence + grounding must NOT compensate for an unresolved failure."""
    events = [fail("test_x", "AssertionError: lost rows") for _ in range(9)]
    verdict = review(good_candidate(), events, [])
    assert verdict.should_refine is False
    assert "resolution" in verdict.failed_signals()


def test_review_reports_every_failing_signal_not_just_the_first():
    verdict = review(
        RefinementCandidate(kind="memory", title="x", content="be careful", evidence=""),
        [],
        [],
    )
    assert verdict.should_refine is False
    failed = set(verdict.failed_signals())
    assert {"recurrence", "grounding", "resolution", "specificity"} <= failed


def test_review_rejects_unknown_kind():
    with pytest.raises(RefineGateError):
        review(RefinementCandidate(kind="constitution", title="t", content="c"), [], [])


def test_review_rejects_non_candidate_input():
    with pytest.raises(RefineGateError):
        review({"kind": "memory"}, [], [])  # type: ignore[arg-type]


def test_verdict_to_dict_is_json_serializable_and_explains_itself():

    verdict = review(good_candidate(), resolved_trajectory("t", "AssertionError: x"), [])
    payload = json.loads(json.dumps(verdict.to_dict()))
    assert payload["should_refine"] is True
    assert len(payload["signals"]) == 5
    for sig in payload["signals"]:
        assert sig["reason"]  # every signal explains itself


# --------------------------------------------------------------------------
# CORPUS-LEVEL assertions — the acceptance criteria that actually matter
# --------------------------------------------------------------------------


def _noise_corpus() -> list[tuple[RefinementCandidate, list[TrajectoryEvent]]]:
    """Ten realistic candidates that a store-everything loop would wrongly persist."""
    return [
        # 1. one-off transient network blip
        (
            good_candidate(content="the provider returned 429 once; maybe retry more. see llm/llm_integration.py"),
            [fail("call_llm", "HTTPError 429 rate limited"), ok("call_llm")],
        ),
        # 2. generic advice, no artifact
        (
            RefinementCandidate(kind="memory", title="care", content="Be careful with the harness state."),
            resolved_trajectory("test_x", "AssertionError: boom"),
        ),
        # 3. unresolved failure -> guess
        (
            good_candidate(content="probably the kernel/dispatch_kernel.py router is wrong somewhere"),
            [fail("test_route", "KeyError: domain") for _ in range(4)],
        ),
        # 4. empty trajectory, nothing observed
        (good_candidate(), []),
        # 5. too short
        (good_candidate(content="fix it"), resolved_trajectory("t", "AssertionError: x")),
        # 6. no failures at all — nothing to learn
        (good_candidate(), [ok("test_a"), ok("test_b"), ok("test_c")]),
        # 7. unfalsifiable vibe report
        (
            RefinementCandidate(
                kind="memory",
                title="vibes",
                content="the agent seemed to lose focus during the middle of the run and drifted",
            ),
            resolved_trajectory("test_x", "AssertionError: boom"),
        ),
        # 8. three unrelated one-offs masquerading as a pattern
        (
            good_candidate(content="several different errors appeared in tests/test_kernel.py this run"),
            [
                fail("t1", "KeyError: alpha"),
                fail("t2", "TimeoutError: beta"),
                fail("t3", "ValueError: gamma"),
                ok("t4"),
            ],
        ),
        # 9. generic + short
        (
            RefinementCandidate(kind="memory", title="tests", content="add more tests"),
            resolved_trajectory("t", "AssertionError: x"),
        ),
        # 10. broke after passing (not a resolution)
        (
            good_candidate(content="system/self_pruning.py started failing after the refactor landed"),
            [ok("t1"), fail("t2", "AssertionError: pruned too much"), fail("t2", "AssertionError: pruned too much")],
        ),
    ]


def _genuine_corpus() -> list[tuple[RefinementCandidate, list[TrajectoryEvent]]]:
    """Ten candidates that encode a real, recurrent, resolved, grounded lesson."""
    return [
        (
            good_candidate(),
            resolved_trajectory("test_concurrent_append", "AssertionError: lost 3 rows"),
        ),
        (
            good_candidate(
                title="pytest cov exceeds timeout",
                content=(
                    "Makefile target coverage exceeds the 600s foreground cap on this repo; "
                    "run pytest -q for iteration and reserve coverage for background runs."
                ),
                evidence="make coverage exit code 124 after 600s",
            ),
            pytest_trajectory("make coverage", "TimeoutError: exceeded 600s", repeats=3),
        ),
        (
            good_candidate(
                title="harness scope defaults wrong",
                content=(
                    "system/continual_harness.py load() defaults scope to the parent dir name, "
                    "which yields 'system' rather than 'local' for the default store path."
                ),
                evidence="tests/test_continual_harness.py::test_scope_default exit code 1",
            ),
            pytest_trajectory(
                "tests/test_continual_harness.py::test_scope_default",
                'AssertionError: scope == system\n  File "system/continual_harness.py", line 167',
            ),
        ),
        (
            good_candidate(
                title="signal not terminal",
                content=(
                    "kernel/signal_protocol.py CODE_GENERATED is not in TERMINAL_SIGNALS, so gating "
                    "adapter returns on is_terminal silently drops successful runs."
                ),
                evidence="agents/prime_agent_adapter.py returned HUMAN_CHECKPOINT",
            ),
            pytest_trajectory(
                "tests/test_prime_agent_adapter.py::test_adapter_run",
                'AssertionError: HUMAN_CHECKPOINT\n  File "kernel/signal_protocol.py", line 40',
            ),
        ),
        (
            good_candidate(
                title="never hints case mismatch",
                content=(
                    "_check_never lowercases the haystack but compared mixed-case needles, so "
                    "'export API_KEY' never matched; lowercase the hint before comparing."
                ),
                evidence="tests/test_prime_agent_adapter.py::test_check_never exit code 1",
            ),
            pytest_trajectory(
                "tests/test_prime_agent_adapter.py::test_check_never",
                "AssertionError: no PermissionError raised",
            ),
        ),
        (
            good_candidate(
                title="parser misclassifies infra failure",
                content=(
                    "benchmarks/swebench_harness.py counts a missing container as a capability "
                    "failure, biasing scores downward; split infra from capability failures."
                ),
                evidence="benchmarks/results/swebench_local_verified.json shows 18 infra rows",
            ),
            pytest_trajectory(
                "tests/test_metric_split.py::test_split",
                "AssertionError: infra counted as capability in benchmarks/swebench_harness.py",
                repeats=4,
            ),
        ),
        (
            good_candidate(
                title="atomic ledger write",
                content=(
                    "system/distillation_ledger.jsonl is appended without a lock; two writers "
                    "interleave partial lines. Use a lock plus sha256 verification on write."
                ),
                evidence="tests/test_distillation_ledger.py::test_concurrent exit code 1",
            ),
            pytest_trajectory(
                "tests/test_distillation_ledger.py::test_concurrent",
                "JSONDecodeError: unterminated string in system/distillation_ledger.jsonl",
            ),
        ),
        (
            good_candidate(
                title="registry shape drift",
                content=(
                    "system/governance_checks.py check_registry_shape assumes a list, but "
                    "agents/forged writes a dict, so the check silently passes on drift."
                ),
                evidence="tests/test_governance_checks.py::test_registry_shape exit code 1",
            ),
            pytest_trajectory(
                "tests/test_governance_checks.py::test_registry_shape",
                'TypeError: dict has no attribute append\n  File "system/governance_checks.py", line 45',
            ),
        ),
        (
            good_candidate(
                title="cynefin router bypassed",
                content=(
                    "agents/agent_assigner.py classify_task uses keyword detect_domain and never "
                    "calls cynefin_classifier.classify_domain, so P3 control intensity is unset."
                ),
                evidence="agents/cynefin_classifier.py never appears in the call path",
            ),
            pytest_trajectory(
                "tests/test_cynefin_classifier.py::test_routing",
                "AssertionError: domain is None; agents/agent_assigner.py never called classify_domain",
            ),
        ),
        (
            good_candidate(
                title="verify node reads stale path",
                content=(
                    "agents/test_runner_agent.py returned the requested path rather than the real "
                    "on-disk source_path, so VERIFY checked a file that was never written."
                ),
                evidence="kernel/dispatch_kernel.py emitted VERIFY_FAILED with exit code 0",
            ),
            pytest_trajectory(
                "tests/test_test_runner_agent.py::test_verified_closure",
                'AssertionError: file missing on disk\n  File "agents/test_runner_agent.py", line 88',
            ),
        ),
    ]


def test_noise_corpus_is_overwhelmingly_rejected():
    """AC: >=70% of noise must be rejected, else the harness fills with garbage."""
    corpus = _noise_corpus()
    rejected = [
        (cand, verdict)
        for cand, events in corpus
        if not (verdict := review(cand, events, [])).should_refine
    ]
    rate = len(rejected) / len(corpus)
    assert rate >= 0.70, (
        f"only {rate:.0%} of noise rejected; admitted: "
        + "; ".join(c.title for c, e in corpus if review(c, e, []).should_refine)
    )


def test_genuine_corpus_is_overwhelmingly_admitted():
    """AC: >=80% of real lessons must be admitted, else the gate is decorative."""
    corpus = _genuine_corpus()
    admitted = [cand for cand, events in corpus if review(cand, events, []).should_refine]
    rate = len(admitted) / len(corpus)
    rejected_reasons = [
        f"{cand.title}: {review(cand, events, []).rationale}"
        for cand, events in corpus
        if not review(cand, events, []).should_refine
    ]
    assert rate >= 0.80, f"only {rate:.0%} of genuine lessons admitted. Rejected -> {rejected_reasons}"


def test_gate_separates_the_two_corpora():
    """The discriminative claim: admission rate on real lessons must far exceed noise."""
    noise = _noise_corpus()
    genuine = _genuine_corpus()
    noise_rate = sum(review(c, e, []).should_refine for c, e in noise) / len(noise)
    genuine_rate = sum(review(c, e, []).should_refine for c, e in genuine) / len(genuine)
    assert genuine_rate - noise_rate >= 0.60, (
        f"gate does not discriminate: genuine={genuine_rate:.0%} noise={noise_rate:.0%}"
    )


# --- STRICT PATH: the same corpora with repo_root supplied (T2 + T3 active) ---
# These exist because the lenient-path corpus tests stayed green while the strict
# path admitted only 10% of genuine lessons. A gate is only as trustworthy as its
# HARDEST configuration, so the corpus claims must hold there too.

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_genuine_corpus_survives_the_strict_path():
    """T3 must not reject real lessons: over-tightening is as broken as under-tightening."""
    corpus = _genuine_corpus()
    admitted = sum(1 for c, e in corpus if review(c, e, [], repo_root=REPO_ROOT).should_refine)
    rate = admitted / len(corpus)
    rejected = [
        f"{c.title}: {review(c, e, [], repo_root=REPO_ROOT).rationale[:100]}"
        for c, e in corpus
        if not review(c, e, [], repo_root=REPO_ROOT).should_refine
    ]
    assert rate >= 0.80, f"strict path admits only {rate:.0%} of genuine lessons. Rejected -> {rejected}"


def test_noise_corpus_stays_rejected_on_the_strict_path():
    corpus = _noise_corpus()
    rejected = sum(1 for c, e in corpus if not review(c, e, [], repo_root=REPO_ROOT).should_refine)
    assert rejected / len(corpus) >= 0.70


def test_strict_path_separation_holds():
    noise = _noise_corpus()
    genuine = _genuine_corpus()
    n = sum(review(c, e, [], repo_root=REPO_ROOT).should_refine for c, e in noise) / len(noise)
    g = sum(review(c, e, [], repo_root=REPO_ROOT).should_refine for c, e in genuine) / len(genuine)
    assert g - n >= 0.60, f"strict path does not discriminate: genuine={g:.0%} noise={n:.0%}"


def test_strict_path_is_at_least_as_strict_as_the_lenient_path():
    """Adding repo_root may only ever remove admissions, never add them."""
    for cand, events in _genuine_corpus() + _noise_corpus():
        lenient = review(cand, events, []).should_refine
        strict = review(cand, events, [], repo_root=REPO_ROOT).should_refine
        if strict:
            assert lenient, f"{cand.title!r} admitted under strict but not lenient — tiers inverted"


def test_novelty_blocks_the_second_submission_of_an_admitted_lesson():
    """End-to-end anti-accretion property: admit once, reject the restatement."""
    cand = good_candidate()
    events = resolved_trajectory("test_concurrent_append", "AssertionError: lost rows")
    assert review(cand, events, []).should_refine is True

    stored = [_Entry(cand.kind, cand.content, id="stored_1")]
    second = review(cand, events, stored)
    assert second.should_refine is False
    assert "novelty" in second.failed_signals()
