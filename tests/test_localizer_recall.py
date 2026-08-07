"""Tests for the standalone localizer measurement (benchmarks/localizer_recall.py).

The measuring instrument gets tested too. A recall number that comes out of an
unverified script is worth no more than the unverified claim it replaces — and this
whole review began by finding metrics that were quietly wrong.

Every test here is offline: `localize()` is stubbed, so nothing clones, checks out, or
calls a model. What is under test is the SCORING, not the ranker.
"""

from unittest import mock

from benchmarks.localizer_recall import aggregate, gold_files, wilson

PATCH = """diff --git a/pkg/mod.py b/pkg/mod.py
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -1,3 +1,3 @@
-old
+new
diff --git a/pkg/other.py b/pkg/other.py
--- a/pkg/other.py
+++ b/pkg/other.py
@@ -1,2 +1,2 @@
-x
+y
"""


def _result(gold, ranked, repo="a/b", err=None):
    hit = next((i + 1 for i, f in enumerate(ranked) if f in set(gold)), None)
    return {
        "instance_id": "i", "repo": repo, "difficulty": "<15 min fix",
        "gold": gold, "ranked": ranked, "first_hit_rank": hit,
        "reciprocal_rank": (1.0 / hit) if hit else 0.0,
        "seconds": 0.0, "error": err,
    }


def test_gold_files_reads_targets_from_the_diff():
    assert gold_files(PATCH) == ["pkg/mod.py", "pkg/other.py"]


def test_gold_files_empty_for_a_patchless_instance():
    assert gold_files("") == []


def test_recall_and_hit_diverge_on_multi_file_gold():
    """The distinction prior reports blurred: finding 1 of 2 gold files is a hit, not a full recall."""
    out = aggregate([_result(["a.py", "b.py"], ["a.py", "z.py", "y.py"])], (3,))
    assert out["hit@3"] == 100.0     # something gold was found
    assert out["recall@3"] == 50.0   # but only half the gold set


def test_recall_and_hit_agree_on_single_file_gold():
    out = aggregate([_result(["a.py"], ["a.py", "z.py"])], (3,))
    assert out["hit@3"] == out["recall@3"] == 100.0


def test_precision_penalises_a_padded_ranking():
    """1 gold file inside a top-3 is 100% recall but only 33% precision."""
    out = aggregate([_result(["a.py"], ["a.py", "z.py", "y.py"])], (3,))
    assert out["recall@3"] == 100.0
    assert round(out["precision@3"], 1) == 33.3


def test_mrr_tracks_the_rank_of_the_first_hit():
    out = aggregate(
        [_result(["a.py"], ["a.py"]), _result(["a.py"], ["z.py", "y.py", "a.py"])], (3,)
    )
    assert out["mrr"] == round((1.0 + 1 / 3) / 2, 4)  # 1st place and 3rd place


def test_a_complete_miss_scores_zero_not_an_error():
    out = aggregate([_result(["a.py"], ["z.py", "y.py"])], (3,))
    assert out["hit@3"] == 0.0 and out["mrr"] == 0.0


def test_infrastructure_failures_are_excluded_from_the_denominator():
    """A failed checkout is not a localizer miss; counting it as one understates accuracy."""
    out = aggregate(
        [_result(["a.py"], ["a.py"]), _result(["b.py"], [], err="OSError: clone failed")], (3,)
    )
    assert out["instances_scored"] == 1
    assert out["infrastructure_failures"] == 1
    assert out["hit@3"] == 100.0


def test_confidence_interval_is_reported_and_shrinks_with_n():
    """The CI is the guard against reading a small-sample point estimate as fact."""
    small = aggregate([_result(["a.py"], ["a.py"])] * 8, (3,))
    large = aggregate([_result(["a.py"], ["a.py"])] * 300, (3,))
    small_lo, small_hi = small["hit@3_ci95"]
    large_lo, large_hi = large["hit@3_ci95"]
    assert (small_hi - small_lo) > (large_hi - large_lo)


def test_wilson_interval_brackets_the_point_estimate():
    lo, hi = wilson(1, 8)
    assert lo < 0.125 < hi
    assert (hi - lo) > 0.3  # n=8 is wide enough to be untrustworthy, and says so


def test_breakdowns_split_by_repo_and_gold_count():
    out = aggregate(
        [
            _result(["a.py"], ["a.py"], repo="django/django"),
            _result(["a.py", "b.py"], ["z.py"], repo="sympy/sympy"),
        ],
        (3,),
    )
    assert set(out["by_repo"]) == {"django/django", "sympy/sympy"}
    assert out["by_gold_count"]["single"]["n"] == 1
    assert out["by_gold_count"]["multi"]["n"] == 1
