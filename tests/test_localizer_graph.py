"""Tests for the staged graph localizer (benchmarks/localizer_graph.py).

Every test targets a behaviour that the measured failure profile
(`docs/LOCALIZER-MEASUREMENT.md`, n=336) says matters, and each builds a tiny real
repo on disk rather than mocking the filesystem — the stages read files, so faking
that away would test nothing.

Zero LLM, zero network.
"""

import os

import pytest

from benchmarks.localizer_graph import (
    Candidate,
    localize_graph,
    localize_graph_traced,
    rerank,
    retrieve,
    split_identifier,
    verify,
)


@pytest.fixture
def repo(tmp_path):
    """A miniature repo with the shape that defeats flat lexical scoring.

    `forms/models.py` DEFINES `model_to_dict`; `db/query.py` merely mentions it a lot.
    A bag-of-words scorer prefers the file with more mentions — which is the exact
    failure mode measured on django__django-11163.
    """
    def w(rel, text):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    w("forms/models.py", "def model_to_dict(instance, fields=None):\n    return {}\n")
    w("db/query.py", "# model_to_dict model_to_dict model_to_dict\n"
                     "def unrelated():\n    return model_to_dict\n")
    w("db/base.py", "# generic base module\n" + "filler word\n" * 50)
    w("core/enums.py", "class IntegerChoices:\n    pass\n\nclass TextChoices:\n    pass\n")
    w("tests/test_models.py", "def test_model_to_dict(): pass\n")
    return str(tmp_path)


def test_split_identifier_bridges_code_and_prose():
    """Prose says 'integer choices'; the code says `IntegerChoices`."""
    assert split_identifier("model_to_dict") == ["model", "dict"]
    assert split_identifier("IntegerChoices") == ["integer", "choices"]


def test_symbol_definition_outranks_mere_mentions(repo):
    """The measured lexical gap: define-vs-mention must not score the same."""
    ranked = localize_graph("model_to_dict returns the wrong fields", repo, top_k=3)
    assert ranked[0] == "forms/models.py"


def test_prose_reaches_a_camelcase_definition(repo):
    """An issue that never types `IntegerChoices` still finds the file defining it."""
    ranked = localize_graph("integer choices behave incorrectly", repo, top_k=3)
    assert "core/enums.py" in ranked


def test_explicit_path_hint_wins(repo):
    """A file the issue names outright is the strongest evidence available."""
    ranked = localize_graph("crash in db/base.py during startup", repo, top_k=3)
    assert ranked[0] == "db/base.py"


def test_test_files_are_never_candidates(repo):
    """The gold patch edits source, not the test suite that exercises it."""
    ranked = localize_graph("model_to_dict is broken", repo, top_k=10)
    assert not any(r.startswith("tests/") for r in ranked)


def test_generic_module_is_not_penalised(repo):
    """MEASURED: 11.2% of gold files are generically named (`base.py` is gold 20 times).

    An earlier revision demoted `base.py`/`utils.py`/`__init__.py` on the assumption that
    they only accumulate lexical mass from being widely imported. The data refuted it —
    the penalty pushed the correct file down roughly 1 instance in 9. Only positive
    evidence may move a candidate.
    """
    pool, _ = retrieve("filler word problem", repo)
    before = {c.path: c.score for c in pool}
    reranked, info = rerank(pool, "filler word problem")
    after = {c.path: c.score for c in reranked}
    base = next((c for c in reranked if c.path == "db/base.py"), None)
    assert base is not None and not base.matched_symbols
    assert after["db/base.py"] >= before["db/base.py"]  # never demoted
    assert "promoted_by_symbols" in info


def test_verify_drops_empty_files(repo):
    """An empty file cannot be an edit target (P2: closure, not self-report)."""
    open(os.path.join(repo, "forms/empty.py"), "w").close()
    pool, _ = retrieve("model_to_dict", repo)
    pool.append(Candidate(path="forms/empty.py", lexical=999.0))
    kept, info = verify(pool, repo)
    assert "forms/empty.py" not in [c.path for c in kept]
    assert info["dropped_count"] >= 1


def test_trace_attributes_the_answer_to_a_stage(repo):
    """A wrong answer must be traceable to the stage that caused it, not to 'the localizer'."""
    ranked, trace = localize_graph_traced("model_to_dict is broken", repo, top_k=3)
    assert [s["stage"] for s in trace["stages"]] == ["retrieve", "rerank", "verify"]
    top = trace["evidence"][0]
    assert top["path"] == ranked[0]
    assert "model_to_dict" in top["matched_symbols"]


def test_returns_at_most_top_k(repo):
    assert len(localize_graph("model_to_dict", repo, top_k=2)) <= 2


def test_empty_problem_statement_does_not_crash(repo):
    assert isinstance(localize_graph("", repo, top_k=3), list)
