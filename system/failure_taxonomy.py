# version: v1 | 2026-08-08 | verdict: pending-review
"""Failure taxonomy: classify a provider failure by CAUSE, not by status code.

PORTED-FROM: prime-agent `packages/ai/src/utils/stream-failure.ts:66-88`
(`classifyStreamFailure`), MIT, Prime Intellect 2026.

Why this exists, concretely. Five delegated digest runs in this project failed with
`HTTP 500: sensitive words detected` and `HTTP 400 content-blocked`. Because the status
was 5xx, they were recorded as transient infrastructure failures — the class you retry.
They are not. They are a provider-side content refusal: retrying can never succeed.

The load-bearing detail is BRANCH ORDER. The upstream classifier tests the error TEXT for
safety/refusal markers *before* it looks at the status code, precisely because a refusal
routinely arrives wearing a 5xx. Reverse the order and every refusal is misfiled as a
server error, and the caller burns its retry budget on a request that is dead on arrival.

This module is deliberately zero-LLM and pure (Law 14): same input, same classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FailureKind(str, Enum):
    """The nine causes upstream distinguishes (stream-failure.ts:11-20)."""

    REFUSAL = "refusal"
    SAFETY = "safety"
    OVERLOADED = "overloaded"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN = "unknown"


# Retrying these can plausibly succeed; everything else is dead on arrival.
# Splitting this way is what stops a retry loop from hammering a refusal.
RETRYABLE: frozenset[FailureKind] = frozenset({
    FailureKind.OVERLOADED,
    FailureKind.RATE_LIMIT,
    FailureKind.SERVER_ERROR,
})

# stream-failure.ts:69 — matched against the error text BEFORE any status check.
_SAFETY_RE = re.compile(
    r"sensitive|safety|prohibited_content|blocklist|spii|recitation|content.?filter|guardrail|flagged",
    re.I,
)
_AUTH_RE = re.compile(r"authentication|permission|unauthorized", re.I)


@dataclass(frozen=True)
class FailureInfo:
    """A classified failure. `request_id` is what makes a post-mortem possible (M29)."""

    kind: FailureKind
    provider_error_type: str | None = None
    status: int | None = None
    request_id: str | None = None

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


def classify_failure(provider_error_type: str | None = None,
                     status: int | None = None) -> FailureKind:
    """Classify by cause. Order mirrors stream-failure.ts:66-88 exactly.

    TEXT IS CHECKED BEFORE STATUS. That is the whole point: `HTTP 500: sensitive
    words detected` is a SAFETY refusal, not a server error, and must not be retried.
    """
    text = (provider_error_type or "").lower()

    if text.strip() == "refusal":
        return FailureKind.REFUSAL
    if _SAFETY_RE.search(text):
        return FailureKind.SAFETY
    if "overloaded" in text or status == 529:
        return FailureKind.OVERLOADED
    if "rate_limit" in text or "throttl" in text or status == 429:
        return FailureKind.RATE_LIMIT
    if _AUTH_RE.search(text) or status in (401, 403):
        return FailureKind.AUTH
    if "invalid_request" in text or "not_found_error" in text or status in (400, 404):
        return FailureKind.INVALID_REQUEST
    if "malformed" in text:
        return FailureKind.MALFORMED_RESPONSE
    if (
        "api_error" in text
        or "server_error" in text
        or "unavailable" in text
        or (status is not None and status >= 500)
    ):
        return FailureKind.SERVER_ERROR
    return FailureKind.UNKNOWN


def classify(provider_error_type: str | None = None, status: int | None = None,
             request_id: str | None = None) -> FailureInfo:
    """Full classification carrying the provider's own identifiers for post-mortems."""
    return FailureInfo(
        kind=classify_failure(provider_error_type, status),
        provider_error_type=provider_error_type,
        status=status,
        request_id=request_id,
    )


def should_retry(provider_error_type: str | None = None, status: int | None = None) -> bool:
    """True only when retrying could plausibly succeed.

    Fails SAFE toward NOT retrying: UNKNOWN is not retryable, because an unrecognised
    failure repeated N times is how a quota gets burned on a permanent error.
    """
    return classify_failure(provider_error_type, status) in RETRYABLE
