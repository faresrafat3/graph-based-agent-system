"""TDD tests for thrash signal hardening (Task H / opus-5 P4 finding).

opus-5: thrash_count uses Jaccard on reflection TEXT (word reuse), not hypothesis identity.
step-3.7-flash rephrases one theory (false negative) or reuses traceback while narrowing
(true positive). Fix: compare extracted HYPOTHESIS (structured claim), not raw text.
"""

from agents.debugger_agent import _similarity, extract_hypothesis


def test_extract_hypothesis_normalizes_rephrasing():
    # Same theory, different words -> same extracted hypothesis (fixes false negative).
    r1 = "I think the bug is an off-by-one in the loop boundary, we should add 1 to the limit."
    r2 = "The loop's upper bound is wrong by one; incrementing the limit fixes it."
    h1 = extract_hypothesis(r1)
    h2 = extract_hypothesis(r2)
    assert h1 == h2, f"rephrasing should map to same hypothesis: {h1!r} vs {h2!r}"


def test_extract_hypothesis_distinguishes_different_theories():
    # Different theories -> different hypotheses (no false merging).
    r1 = "The bug is an off-by-one in the loop boundary."
    r2 = "We are dividing by zero because b can be 0."
    assert extract_hypothesis(r1) != extract_hypothesis(r2)


def test_similarity_on_hypothesis_catches_rephrased_thrash():
    r1 = "I think the bug is an off-by-one in the loop boundary, we should add 1 to the limit."
    r2 = "The loop's upper bound is wrong by one; incrementing the limit fixes it."
    # With extracted hypotheses equal, similarity must be high (thrash detected).
    assert _similarity(extract_hypothesis(r1), extract_hypothesis(r2)) >= 0.99


def test_similarity_on_raw_text_misses_rephrasing():
    # Documenting the OLD weak behavior: raw-text Jaccard is low for rephrasing.
    r1 = "I think the bug is an off-by-one in the loop boundary, we should add 1 to the limit."
    r2 = "The loop's upper bound is wrong by one; incrementing the limit fixes it."
    raw = _similarity(r1, r2)
    # This proves why text-Jaccard is the wrong signal (it misses the rephrase).
    assert raw < 0.6, f"raw text Jaccard should be low for rephrasing: {raw}"
