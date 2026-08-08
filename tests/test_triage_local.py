"""Regression guard for SWE-bench local triage target resolution.

Every case here is a bug that shipped and was caught only by running the triage: the
label parser was wrong four times in a row, and each wrong answer silently reclassified
a SOUND instance as an infrastructure failure. That is the worst possible failure mode
for a benchmark — it shrinks the denominator in the direction that flatters the system.

The four shapes, with the instance that exposed each:
  1. "test_name (module.Class)"  -> django-14725, parsed straight from FAIL_TO_PASS
  2. docstring-only              -> django-14787, name absent; recovered via test_patch
                                    + AST class lookup (the diff's hunk header names a
                                    helper class declared inside the test body, so
                                    pattern-matching the diff yields the wrong class)
  3. bare "test_name"            -> sympy-23262, no module; not addressable by
                                    django's runtests.py, must be excluded not guessed
  4. name repeated inside parens -> django-16485, modern django puts the FULL dotted
                                    path inside the parens; appending the name again
                                    produced `...test_zero_values.test_zero_values` ->
                                    AttributeError (19 of 20 no_pass verdicts were this)

Plus the concurrency guard: two triage runs racing on the records file corrupt the
denominator silently (observed 2026-08-07), and a stale count is worse than a crash.

No network, no LLM, no repo clone: these assert on the parsing contract only.
"""

from __future__ import annotations

import ast
import os
import textwrap

import pytest

from benchmarks.triage_local import (
    _added_tests_from_patch,
    _enclosing_class,
    _target_of,
    _targets_from_field,
    _SingleRun,
)


def _instance(fail_to_pass, test_patch="") -> dict:
    return {"FAIL_TO_PASS": fail_to_pass, "test_patch": test_patch}


class TestTargetsFromField:
    def test_parses_django_name_and_class(self):
        inst = _instance(["test_edit_only (model_formsets.tests.ModelFormsetTest)"])
        assert _targets_from_field(inst) == ["model_formsets.tests.ModelFormsetTest.test_edit_only"]

    def test_parses_json_encoded_field(self):
        """SWE-bench ships FAIL_TO_PASS as a JSON string, not a list."""
        inst = _instance('["test_x (a.b.C)"]')
        assert _targets_from_field(inst) == ["a.b.C.test_x"]

    def test_keeps_trailing_docstring_out_of_the_label(self):
        """The shape that broke it: name, class, THEN a docstring on the same line."""
        inst = _instance(["test_new (decorators.tests.Tests) @method_decorator preserves it."])
        assert _targets_from_field(inst) == ["decorators.tests.Tests.test_new"]

    def test_does_not_duplicate_a_name_already_ending_the_path(self):
        """django-16485: modern django puts the FULL dotted path inside the parens.

        Appending the name again produced `...test_zero_values.test_zero_values`, which
        django resolves against a function object -> AttributeError. This shape accounted
        for 19 of 20 `no_pass` verdicts, all of them sound instances.
        """
        inst = _instance([
            "test_zero_values (template_tests.filter_tests.test_floatformat.FunctionTests.test_zero_values)"
        ])
        assert _targets_from_field(inst) == [
            "template_tests.filter_tests.test_floatformat.FunctionTests.test_zero_values"
        ]

    def test_still_appends_when_path_is_the_class_only(self):
        """The older shape must keep working: parens hold module.Class, not the method."""
        inst = _instance(["test_zero_values (template_tests.test_floatformat.FunctionTests)"])
        assert _targets_from_field(inst) == [
            "template_tests.test_floatformat.FunctionTests.test_zero_values"
        ]

    def test_skips_docstring_only_entries(self):
        inst = _instance(["@method_decorator preserves wrapper assignments."])
        assert _targets_from_field(inst) == []

    def test_scans_all_entries_not_just_the_first(self):
        """django-15268 hides the only real label behind two docstrings."""
        inst = _instance([
            "index/unique_together also triggers on ordering changes.",
            "Removed fields will be removed after updating index/unique_together.",
            "test_alter_index (migrations.test_operations.OperationTests)",
        ])
        assert _targets_from_field(inst) == ["migrations.test_operations.OperationTests.test_alter_index"]

    def test_normalizes_pytest_node_id(self):
        inst = _instance(["tests/foo/test_bar.py::test_baz"])
        assert _targets_from_field(inst) == ["tests.foo.test_bar.test_baz"]


class TestAddedTestsFromPatch:
    def test_extracts_module_and_method(self):
        patch = textwrap.dedent("""\
            diff --git a/tests/decorators/tests.py b/tests/decorators/tests.py
            --- a/tests/decorators/tests.py
            +++ b/tests/decorators/tests.py
            @@ -425,6 +425,29 @@ class Test:
            +    def test_wrapper_assignments(self):
            +        pass
            """)
        assert _added_tests_from_patch(_instance([], patch)) == [
            ("decorators.tests", "test_wrapper_assignments")
        ]

    def test_ignores_non_test_functions(self):
        patch = "+++ b/tests/a/tests.py\n+    def helper(self):\n+    def test_real(self):\n"
        assert _added_tests_from_patch(_instance([], patch)) == [("a.tests", "test_real")]

    def test_returns_empty_when_patch_adds_no_tests(self):
        patch = "+++ b/tests/a/tests.py\n+    x = 1\n"
        assert _added_tests_from_patch(_instance([], patch)) == []


class TestEnclosingClass:
    @pytest.fixture
    def tests_root(self, tmp_path):
        pkg = tmp_path / "tests" / "decorators"
        pkg.mkdir(parents=True)
        (pkg / "tests.py").write_text(textwrap.dedent("""\
            class MethodDecoratorTests:
                def test_wrapper_assignments(self):
                    class Test:            # helper declared INSIDE the test
                        def method(self): ...

            def test_module_level(): ...
            """), encoding="utf-8")
        return str(tmp_path)

    def test_finds_real_testcase_not_nested_helper(self, tests_root):
        """django-14787: the diff hunk header says `class Test:` — the wrong answer."""
        assert _enclosing_class(tests_root, "decorators.tests", "test_wrapper_assignments") == \
            "MethodDecoratorTests"

    def test_module_level_function_has_no_class(self, tests_root):
        assert _enclosing_class(tests_root, "decorators.tests", "test_module_level") is None

    def test_missing_file_is_not_an_error(self, tmp_path):
        assert _enclosing_class(str(tmp_path), "nope.nope", "test_x") is None

    def test_unparseable_file_is_not_an_error(self, tmp_path):
        pkg = tmp_path / "tests" / "broken"
        pkg.mkdir(parents=True)
        (pkg / "tests.py").write_text("class ??? bad syntax", encoding="utf-8")
        assert _enclosing_class(str(tmp_path), "broken.tests", "test_x") is None


class TestTargetOf:
    def test_prefers_the_shipped_label(self):
        inst = _instance(["test_x (a.b.C)"], "+++ b/tests/z/tests.py\n+    def test_other(self):\n")
        assert _target_of(inst) == "a.b.C.test_x"

    def test_recovers_docstring_only_instance_with_full_class_path(self, tmp_path):
        pkg = tmp_path / "tests" / "decorators"
        pkg.mkdir(parents=True)
        (pkg / "tests.py").write_text(
            "class MethodDecoratorTests:\n    def test_wrapper_assignments(self): ...\n",
            encoding="utf-8",
        )
        inst = _instance(
            ["@method_decorator preserves wrapper assignments."],
            "+++ b/tests/decorators/tests.py\n+    def test_wrapper_assignments(self):\n",
        )
        assert _target_of(inst, str(tmp_path)) == \
            "decorators.tests.MethodDecoratorTests.test_wrapper_assignments"

    def test_falls_back_to_module_path_without_a_worktree(self):
        inst = _instance(["docstring only."], "+++ b/tests/a/tests.py\n+    def test_x(self):\n")
        assert _target_of(inst) == "a.tests.test_x"

    def test_returns_none_for_bare_sympy_names(self):
        """sympy-23262: no module, no test_patch label -> excluded, never guessed."""
        assert _target_of(_instance(["test_issue_14941"], "")) is None


class TestSingleRunLock:
    def test_blocks_a_concurrent_run_and_releases(self, tmp_path):
        out = str(tmp_path / "records.json")
        with _SingleRun(out):
            assert os.path.exists(out + ".lock")
            with pytest.raises(SystemExit):
                _SingleRun(out).__enter__()   # second owner refused
        assert not os.path.exists(out + ".lock")  # released on exit

    def test_stale_lock_from_a_dead_pid_is_reclaimed(self, tmp_path):
        out = str(tmp_path / "records.json")
        with _SingleRun(out):
            pass  # first run: create + release
        with open(out + ".lock", "w") as fh:
            fh.write("999999999")  # a pid that cannot be alive
        with _SingleRun(out):      # must succeed, reclaiming the stale lock
            assert os.path.exists(out + ".lock")
