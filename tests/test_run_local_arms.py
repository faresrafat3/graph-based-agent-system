"""Tests for the local arm runner (benchmarks/run_local_arms.py).

The harness decides what counts as a model failure, so a bug here corrupts every number
downstream. Two defects already shipped in this file and were caught only by running it:

  1. `judge()` applied patches with a plain `git apply`, while the official grader (and
     `validate_patch`) escalate through --recount / --ignore-whitespace / -C1. Patches the
     real grader accepts were scored `no_apply` — the harness charging the model for its
     own strictness. Measured on django-14725.
  2. `main()` ran units serially. 74 instances x 2 arms at ~2 min each is not a run you
     can finish; the 11-key pool exists precisely so units can go concurrently.

Everything here is offline: no LLM, no network, no repo clone.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from benchmarks.run_local_arms import (
    apply_patch,
    is_infra_error,
    judge,
    mcnemar,
    summarise,
)


@pytest.fixture
def git_repo(tmp_path):
    """A real git repo — apply_patch shells out to git, so faking it would test nothing."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=root, check=True)
    return str(root)


GOOD_PATCH = """--- a/mod.py
+++ b/mod.py
@@ -1,2 +1,2 @@
 def f():
-    return 1
+    return 2
"""

# Same edit, deliberately wrong hunk counts (@@ says 9 lines). git rejects this with a
# plain apply and accepts it with --recount. This is the exact shape that made the real
# grader and this harness disagree.
BAD_COUNTS_PATCH = """--- a/mod.py
+++ b/mod.py
@@ -1,9 +1,9 @@
 def f():
-    return 1
+    return 2
"""


class TestApplyPatch:
    def test_applies_a_well_formed_patch(self, git_repo):
        ok, how = apply_patch(git_repo, GOOD_PATCH)
        assert ok and how == "plain"
        assert "return 2" in open(f"{git_repo}/mod.py", encoding="utf-8").read()

    def test_recovers_a_patch_with_wrong_hunk_counts(self, git_repo):
        """django-14725: plain apply says 'corrupt patch', --recount lands it."""
        ok, how = apply_patch(git_repo, BAD_COUNTS_PATCH)
        assert ok, "escalating tolerance must accept what the official grader accepts"
        assert how != "plain"
        assert "return 2" in open(f"{git_repo}/mod.py", encoding="utf-8").read()

    def test_rejects_a_patch_targeting_a_missing_file(self, git_repo):
        ok, _ = apply_patch(git_repo, GOOD_PATCH.replace("mod.py", "ghost.py"))
        assert not ok

    def test_rejects_garbage(self, git_repo):
        ok, _ = apply_patch(git_repo, "this is not a diff at all")
        assert not ok


class TestJudge:
    def test_empty_patch_is_no_apply_not_a_crash(self, git_repo):
        assert judge({"test_patch": ""}, git_repo, "")["outcome"] == "no_apply"
        assert judge({"test_patch": ""}, git_repo, "   \n ")["outcome"] == "no_apply"

    def test_unapplicable_patch_is_no_apply(self, git_repo):
        out = judge({"test_patch": ""}, git_repo, "not a diff")
        assert out["outcome"] == "no_apply"


class TestInfraClassification:
    @pytest.mark.parametrize("err", [
        "429 Too Many Requests",
        "The read operation timed out",
        "ConnectionError: connection reset",
        "StepfunAPIError: failed after 3 attempts",
    ])
    def test_transport_failures_are_infra(self, err):
        assert is_infra_error(err)

    @pytest.mark.parametrize("err", [
        "AssertionError: expected 2 got 1",
        "SyntaxError: invalid syntax",
        "patch does not apply",
    ])
    def test_capability_failures_are_not_infra(self, err):
        assert not is_infra_error(err)


class TestDiagnosticsSurviveFailure:
    """Evidence must outlive the failure it describes.

    16 infra records landed with no `localized` field: the exception inside the arm
    skipped the success-path `record.update(...)`, taking the localizer output with it.
    That erased the evidence needed to separate "the localizer failed" from "the LLM call
    timed out" — precisely the infra-vs-capability distinction the harness exists to keep.
    """

    def test_localized_is_recorded_before_the_arm_runs(self):
        import inspect

        import benchmarks.run_local_arms as mod

        src = inspect.getsource(mod.run_one)
        set_localized = src.index('record["localized"]')
        call_arm = src.index("ARMS[arm](")
        assert set_localized < call_arm, (
            "localizer output must be recorded before the arm is invoked, or an "
            "exception in the arm discards it"
        )


def _rec(iid, arm, outcome, calls=1):
    return {"instance_id": iid, "arm": arm, "outcome": outcome,
            "llm_calls": calls, "seconds": 1.0}


class TestSummarise:
    def test_infra_is_excluded_from_the_denominator(self):
        """An infra failure is not a wrong answer; counting it as one understates capability."""
        recs = [_rec("a", "x", "resolved"), _rec("b", "x", "not_resolved"),
                _rec("c", "x", "infra")]
        s = summarise(recs, "x")
        assert s["total"] == 3 and s["infra_excluded"] == 1 and s["scored"] == 2
        assert s["resolve_rate_raw"] == pytest.approx(33.33, abs=0.01)   # 1/3
        assert s["resolve_rate_adjusted"] == 50.0                        # 1/2

    def test_apply_rate_counts_resolved_plus_not_resolved(self):
        recs = [_rec("a", "x", "resolved"), _rec("b", "x", "not_resolved"),
                _rec("c", "x", "no_apply")]
        assert summarise(recs, "x")["apply_rate"] == pytest.approx(66.67, abs=0.01)

    def test_llm_calls_are_summed_not_estimated(self):
        recs = [_rec("a", "x", "resolved", calls=3), _rec("b", "x", "no_apply", calls=2)]
        assert summarise(recs, "x")["llm_calls"] == 5

    def test_empty_arm_does_not_divide_by_zero(self):
        s = summarise([], "x")
        assert s["total"] == 0 and s["resolve_rate_raw"] == 0.0


class TestMcNemar:
    def test_only_discordant_pairs_carry_signal(self):
        recs = [
            _rec("a", "A", "resolved"),     _rec("a", "B", "resolved"),      # concordant
            _rec("b", "A", "not_resolved"), _rec("b", "B", "resolved"),      # B gains
            _rec("c", "A", "not_resolved"), _rec("c", "B", "resolved"),      # B gains
        ]
        m = mcnemar(recs, "A", "B")
        assert m["both"] == 1 and m["only_B"] == 2 and m["only_A"] == 0
        assert m["discordant"] == 2

    def test_identical_arms_give_p_of_one(self):
        recs = [_rec("a", "A", "resolved"), _rec("a", "B", "resolved"),
                _rec("b", "A", "not_resolved"), _rec("b", "B", "not_resolved")]
        assert mcnemar(recs, "A", "B")["mcnemar_exact_p"] == 1.0

    def test_instances_where_either_arm_hit_infra_are_dropped(self):
        """Pairing requires both arms to have actually attempted the instance."""
        recs = [_rec("a", "A", "infra"), _rec("a", "B", "resolved"),
                _rec("b", "A", "resolved"), _rec("b", "B", "resolved")]
        m = mcnemar(recs, "A", "B")
        assert m["n_paired"] == 1  # only instance "b"

    def test_delta_sign_favours_the_second_arm(self):
        recs = [_rec("a", "A", "not_resolved"), _rec("a", "B", "resolved")]
        assert mcnemar(recs, "A", "B")["delta_pp"] > 0
