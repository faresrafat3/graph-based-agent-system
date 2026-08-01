import json
import urllib.error

import pytest

from llm.llm_integration import (
    StepfunAPIError,
    StepfunConfigurationError,
    call_llm,
    get_stepfun_config,
)


class FakeHTTPResponse:
    """Minimal context-manager response object for urllib.request.urlopen tests."""

    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_get_stepfun_config_requires_real_key(monkeypatch):
    """Missing or placeholder Stepfun keys fail loudly; no fallback is allowed."""
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)

    with pytest.raises(StepfunConfigurationError):
        get_stepfun_config()

    monkeypatch.setenv("STEPFUN_API_KEY", "your-stepfun-api-key-here")
    with pytest.raises(StepfunConfigurationError):
        get_stepfun_config()


def test_call_llm_stepfun_success(monkeypatch):
    """call_llm sends a Stepfun request and returns assistant content."""
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-stepfun-realistic-test-key")
    monkeypatch.setenv("STEPFUN_BASE_URL", "https://stepfun.test/v1")
    monkeypatch.setenv("STEPFUN_MODEL", "step-test-model")

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {"choices": [{"message": {"content": "Stepfun response"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = call_llm(
        "Build login page with email auth",
        system_prompt="You are a task decomposer.",
        timeout=7,
    )

    assert response == "Stepfun response"
    assert captured["url"] == "https://stepfun.test/v1/chat/completions"
    assert captured["timeout"] == 7
    assert captured["body"]["model"] == "step-test-model"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["role"] == "user"


def test_call_llm_http_error_fails_loudly(monkeypatch):
    """Stepfun HTTP failures raise typed API errors instead of synthetic output."""
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-stepfun-realistic-test-key")

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            402,
            "Payment Required",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(StepfunAPIError):
        call_llm("Hello")


def test_call_llm_invalid_payload_fails_loudly(monkeypatch):
    """Malformed Stepfun payloads are rejected deterministically."""
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-stepfun-realistic-test-key")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse({"unexpected": []}),
    )

    with pytest.raises(StepfunAPIError):
        call_llm("Hello")


def test_call_llm_sanitizes_prompt_before_stepfun(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-stepfun-realistic-test-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse(
            {"choices": [{"message": {"content": "Sanitized"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    noisy = "Build page\nTraceback (most recent call last):\n  File 'x.py', line 1\nRuntimeError: crash\n\nContinue"
    assert call_llm(noisy, max_retries=0) == "Sanitized"
    sent_prompt = captured["body"]["messages"][-1]["content"]
    assert "RuntimeError: crash" not in sent_prompt
    assert "Traceback Omitted" in sent_prompt


def test_call_llm_retries_retryable_http_error(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-stepfun-realistic-test-key")
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                hdrs=None,
                fp=None,
            )
        return FakeHTTPResponse(
            {"choices": [{"message": {"content": "Recovered"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert call_llm("Hello", max_retries=1, backoff_seconds=0) == "Recovered"
    assert calls["count"] == 2
