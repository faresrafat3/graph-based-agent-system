# version: v1 | 2026-08-08 | verdict: pending-review
"""Tests for system/failure_taxonomy.py.

Each test names the upstream behaviour it protects
(prime-agent `packages/ai/src/utils/stream-failure.ts:66-88`).

The centrepiece is `test_real_delegation_failures_*`: these use the ACTUAL error
strings and statuses from five failed digest delegations in this project. They are
regression tests against a mistake already made — those failures were logged as
transient infra when they were non-retryable content refusals.
"""

from __future__ import annotations

import pytest

from system.failure_taxonomy import (
    FailureKind,
    classify,
    classify_failure,
    should_retry,
)


# --- the load-bearing property: TEXT before STATUS -------------------------


def test_safety_text_beats_5xx_status():
    """stream-failure.ts:69 runs before :79-86. A refusal wearing a 500 is SAFETY."""
    assert classify_failure("sensitive words detected", 500) is FailureKind.SAFETY


def test_safety_text_beats_429_status():
    """Even a rate-limit status must not mask a content refusal."""
    assert classify_failure("content_filter triggered", 429) is FailureKind.SAFETY


def test_plain_5xx_without_safety_text_is_a_server_error():
    """The guard must not swallow genuine server errors."""
    assert classify_failure(None, 503) is FailureKind.SERVER_ERROR
    assert classify_failure("Gateway Time-out", 504) is FailureKind.SERVER_ERROR


# --- the five real failures this module exists because of -----------------


@pytest.mark.parametrize("text,status", [
    ("sensitive words detected", 500),
    ("HTTP 500: sensitive words detected", 500),
])
def test_real_delegation_failures_are_safety_not_infra(text, status):
    info = classify(text, status)
    assert info.kind is FailureKind.SAFETY
    assert info.retryable is False, "a content refusal must never be retried"


def test_real_delegation_failure_content_blocked_is_invalid_request():
    info = classify("content-blocked", 400)
    assert info.kind is FailureKind.INVALID_REQUEST
    assert info.retryable is False


def test_real_delegation_failure_gateway_timeout_is_retryable():
    """The ONLY one of the five that was genuinely transient."""
    assert should_retry("Gateway Time-out", 504) is True


# --- the rest of the taxonomy --------------------------------------------


@pytest.mark.parametrize("text,status,expected", [
    ("refusal", None, FailureKind.REFUSAL),
    ("overloaded_error", None, FailureKind.OVERLOADED),
    (None, 529, FailureKind.OVERLOADED),
    ("rate_limit_error", None, FailureKind.RATE_LIMIT),
    ("ThrottlingException", None, FailureKind.RATE_LIMIT),
    (None, 429, FailureKind.RATE_LIMIT),
    ("unauthorized", None, FailureKind.AUTH),
    (None, 401, FailureKind.AUTH),
    (None, 403, FailureKind.AUTH),
    ("invalid_request_error", None, FailureKind.INVALID_REQUEST),
    ("not_found_error", None, FailureKind.INVALID_REQUEST),
    (None, 404, FailureKind.INVALID_REQUEST),
    ("malformed json", None, FailureKind.MALFORMED_RESPONSE),
    ("api_error", None, FailureKind.SERVER_ERROR),
    (None, None, FailureKind.UNKNOWN),
])
def test_taxonomy_matches_upstream(text, status, expected):
    assert classify_failure(text, status) is expected


# --- retry policy fails safe ---------------------------------------------


def test_unknown_is_not_retryable():
    """An unrecognised failure retried N times is how a quota gets burned."""
    assert should_retry(None, None) is False


def test_auth_is_not_retryable():
    assert should_retry("unauthorized", 401) is False


@pytest.mark.parametrize("kind_text,status", [
    ("overloaded_error", 529),
    ("rate_limit_error", 429),
    ("api_error", 500),
])
def test_transient_kinds_are_retryable(kind_text, status):
    assert should_retry(kind_text, status) is True


# --- determinism (Law 14: zero-LLM routing) -------------------------------


def test_classification_is_pure():
    a = classify_failure("sensitive words detected", 500)
    b = classify_failure("sensitive words detected", 500)
    assert a is b is FailureKind.SAFETY


def test_request_id_is_preserved_for_postmortem():
    """M29: without the provider's own id a failure cannot be traced back."""
    info = classify("sensitive words detected", 500, request_id="req_abc123")
    assert info.request_id == "req_abc123"
