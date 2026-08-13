"""
Regression tests for the Law 3 (Failure Handling) defects found during the
HumanEval benchmark run of 2026-08-01, extended with the SWE-bench Verified
defects of 2026-08-02.

Each test pins a real bug that silently converted an infrastructure failure into a
reported capability failure — the exact class of defect Law 3 exists to prevent.

Measured impact of the retry gap: the first full 164-problem HumanEval run produced
99 failures, 96 of which were HTTP 429. Measured pass@1 was 39.63%. With retry and
backoff in place the same code on the same model scored 98.17% — a 58.5-point swing
unrelated to model capability.
"""

import urllib.error

import pytest

from agents.test_runner_agent import run_code_and_tests
from benchmarks.swebench_harness import repair_hunk_counts
from llm import llm_integration
from llm.llm_integration import StepfunAPIError, _RETRYABLE_HTTP_STATUS


def _http_error(code: str, status: int) -> urllib.error.HTTPError:
    """Build an HTTPError with a readable body, as urllib produces in practice."""
    import email.message
    import io

    headers = email.message.Message()
    return urllib.error.HTTPError(
        "https://api.stepfun.ai/step_plan/v1/chat/completions",
        status,
        code,
        headers,
        io.BytesIO(b'{"error":"transient"}'),
    )


# --- Bug 1 & 2: Test Runner sandbox honesty -----------------------------------


def test_sandbox_survives_a_hostile_pythonpath(monkeypatch):
    """
    The Test Runner originally overwrote PYTHONPATH, which made pytest itself
    unimportable inside the sandbox. Every generated module then looked like a test
    failure when the harness was actually broken.

    The sandbox must produce a correct verdict regardless of the caller's PYTHONPATH.
    """
    monkeypatch.setenv("PYTHONPATH", "/nonexistent/hostile/path")

    source = "def add(a: int, b: int) -> int:\n    return a + b\n"
    tests = "from mod import add\n\ndef test_add():\n    assert add(2, 2) == 4\n"

    res = run_code_and_tests("mod.py", source, "test_mod.py", tests)

    assert res["success"] is True, f"sandbox broke under a hostile PYTHONPATH: {res}"
    assert res["passed_tests"] == 1
    assert res["stage"] == "testing"


def test_harness_error_is_not_reported_as_a_test_failure():
    """
    pytest exit codes 2/3/4/5 (no tests collected, usage error, internal error) were
    indistinguishable from a genuine assertion failure. A test file containing no test
    functions must surface as 'harness_error', never as a capability failure.
    """
    source = "def noop() -> None:\n    return None\n"
    empty_tests = "# no test functions here at all\nX = 1\n"

    res = run_code_and_tests("noop_mod.py", source, "test_noop_mod.py", empty_tests)

    assert res["success"] is False
    assert res["stage"] == "harness_error"
    assert res["failed_tests"] == 0
    assert "not a code defect" in res["error"]


def test_genuine_test_failure_is_still_reported_as_testing():
    """The harness_error branch must NOT swallow real assertion failures."""
    source = "def add(a: int, b: int) -> int:\n    return a - b  # intentional bug\n"
    tests = "from bad import add\n\ndef test_add():\n    assert add(2, 2) == 4\n"

    res = run_code_and_tests("bad.py", source, "test_bad.py", tests)

    assert res["success"] is False
    assert res["stage"] == "testing"
    assert res["failed_tests"] == 1


# --- Bug 3: LLM transport retry / backoff -------------------------------------


def test_rate_limit_and_5xx_are_classified_retryable():
    """429 and 5xx must be retryable; auth/schema errors must not be."""
    assert 429 in _RETRYABLE_HTTP_STATUS
    assert 500 in _RETRYABLE_HTTP_STATUS
    assert 503 in _RETRYABLE_HTTP_STATUS
    assert 401 not in _RETRYABLE_HTTP_STATUS
    assert 400 not in _RETRYABLE_HTTP_STATUS


def test_transient_429_is_retried_then_succeeds(monkeypatch):
    """A transient 429 must be retried, not surfaced as a permanent failure."""
    monkeypatch.setenv("STEPFUN_API_KEY", "k" * 40)
    monkeypatch.setattr(llm_integration.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"RECOVERED"}}]}'

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error("Too Many Requests", 429)
        return _Resp()

    monkeypatch.setattr(llm_integration.urllib.request, "urlopen", fake_urlopen)

    out = llm_integration.call_stepfun_native("ping", max_retries=3)

    assert out == "RECOVERED"
    assert calls["n"] == 3, "should have retried twice before succeeding"


def test_auth_error_is_not_retried(monkeypatch):
    """A 401 must fail immediately — retrying an auth error only burns quota."""
    monkeypatch.setenv("STEPFUN_API_KEY", "k" * 40)
    monkeypatch.setattr(llm_integration.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise _http_error("Unauthorized", 401)

    monkeypatch.setattr(llm_integration.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(StepfunAPIError):
        llm_integration.call_stepfun_native("ping", max_retries=3)

    assert calls["n"] == 1, "auth errors must not be retried"


def test_escalates_loudly_after_retry_budget_exhausted(monkeypatch):
    """Law 3: escalate loudly once the retry budget is spent. Never return silently."""
    monkeypatch.setenv("STEPFUN_API_KEY", "k" * 40)
    monkeypatch.setattr(llm_integration.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_429(request, timeout=None):
        calls["n"] += 1
        raise _http_error("Too Many Requests", 429)

    monkeypatch.setattr(llm_integration.urllib.request, "urlopen", always_429)

    with pytest.raises(StepfunAPIError):
        llm_integration.call_stepfun_native("ping", max_retries=2)

    assert calls["n"] == 3, "max_retries=2 means 3 total attempts"


def test_transport_timeout_is_retried(monkeypatch):
    """Read timeouts are transient and must be retried, not reported as a defect."""
    monkeypatch.setenv("STEPFUN_API_KEY", "k" * 40)
    monkeypatch.setattr(llm_integration.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"OK"}}]}'

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("The read operation timed out")
        return _Resp()

    monkeypatch.setattr(llm_integration.urllib.request, "urlopen", fake_urlopen)

    assert llm_integration.call_stepfun_native("ping", max_retries=2) == "OK"
    assert calls["n"] == 2


# --- Bug 4: SWE-bench hunk-count repair -------------------------------------


def test_repair_hunk_counts_fixes_declared_count():
    """
    The LLM emits `@@ -403,8 +403,8 @@` but only 7 body lines. git rejects the
    whole patch as 'corrupt' even though the edit is correct. This false negative in
    the validator discards good work (Law 11). repair_hunk_counts recomputes the
    counts arithmetically.

    Original patch body (8 lines):
        ctx, ctx, ctx, del, add, ctx, ctx, ctx
    -> old = 7 (all except the single addition), new = 7 (all except the single deletion)
    """
    bad_patch = (
        "--- a/requests/sessions.py\n"
        "+++ b/requests/sessions.py\n"
        "@@ -403,8 +403,8 @@ class Session(SessionRedirectMixin):\n"
        "         :param cert: (optional) if String, path to ssl client cert file (.pem).\n"
        "             If Tuple, ('cert', 'key') pair.\n"
        '         """\n'
        "-        method = builtin_str(method)\n"
        "+        method = to_native_string(method)\n"
        " \n"
        "         # Create the Request.\n"
        "         req = Request(\n"
    )
    fixed = repair_hunk_counts(bad_patch)
    header = [l for l in fixed.split("\n") if l.startswith("@@")][0]
    assert "@@ -403,7 +403,7 @@" in header, f"expected repaired count, got {header}"


def test_repair_hunk_counts_leaves_correct_patch_unchanged():
    good = (
        "--- a/x.py\n+++ b/x.py\n"
        "@@ -1,3 +1,3 @@ def f():\n"
        "     a = 1\n"
        "-    b = 2\n"
        "+    b = 3\n"
        "     c = 4\n"
    )
    assert repair_hunk_counts(good) == good
