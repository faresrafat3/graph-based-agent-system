"""
Stepfun-only LLM integration.

This module intentionally supports only Stepfun at the moment. Alternate
provider adapters and dry-run response fallbacks are not available here by
design: missing credentials or API failures must fail loudly so production
quality issues cannot be hidden by synthetic responses.
"""

import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only in minimal runtimes
    def load_dotenv(*args, **kwargs):
        """No-op fallback when python-dotenv is not installed."""
        return False

# Load environment variables once at import time. Runtime tests may still
# override os.environ directly via monkeypatch before calling functions.
load_dotenv()


DEFAULT_STEPFUN_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
DEFAULT_STEPFUN_MODEL = "step-3.7-flash"
_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Key pool (multi-account rotation)
#
# The system ships with 11 StepFun accounts. Each account has its own per-minute quota,
# so a single shared key exhausts in ~8 requests and every benchmark collapses into
# 429s (we measured this: 96/99 HumanEval failures were 429). The pool rotates keys
# so the *aggregate* quota is 11x. When a key returns 429 it is parked in cooldown for
# a short window and the next healthy key is used. This is pure load distribution — no
# key is "better", they are interchangeable step-3.7-flash endpoints.
# --------------------------------------------------------------------------------------

class _KeyPool:
    """Thread-safe round-robin pool over N API keys with per-key 429 cooldown."""

    def __init__(self, keys: list):
        self._keys = [k.strip() for k in keys if k and k.strip()]
        self._lock = threading.Lock()
        self._idx = 0
        self._cooldown_until = {k: 0.0 for k in self._keys}  # key -> monotonic cooldown expiry

    @property
    def size(self) -> int:
        return len(self._keys)

    def next_available(self) -> Optional[str]:
        """Return the next key that is not in cooldown, or None if all are cooling down.

        Picks round-robin from the cursor; if the chosen key is cooling down it keeps
        scanning forward (bounded by pool size) and returns the soonest-ready key if
        every key is parked.
        """
        if not self._keys:
            return None
        with self._lock:
            now = time.monotonic()
            n = len(self._keys)
            start = self._idx % n
            # First pass: any key not in cooldown.
            for offset in range(n):
                i = (start + offset) % n
                key = self._keys[i]
                if self._cooldown_until[key] <= now:
                    self._idx = (i + 1) % n
                    return key
            # All cooling: return the one that frees up soonest (still rotates cursor).
            soonest_i = start
            soonest_t = float("inf")
            for offset in range(n):
                i = (start + offset) % n
                t = self._cooldown_until[self._keys[i]]
                if t < soonest_t:
                    soonest_t = t
                    soonest_i = i
            self._idx = (soonest_i + 1) % n
            return self._keys[soonest_i]

    def mark_rate_limited(self, key: str, cooldown_seconds: float = 30.0) -> None:
        """Park a key that returned 429 until `cooldown_seconds` from now."""
        with self._lock:
            if key in self._cooldown_until:
                self._cooldown_until[key] = max(
                    self._cooldown_until[key], time.monotonic() + cooldown_seconds
                )


def _load_key_pool() -> _KeyPool:
    """Build the pool from STEPFUN_API_KEYS (multi-line/comma) or fall back to STEPFUN_API_KEY."""
    raw = os.getenv("STEPFUN_API_KEYS", "")
    keys = []
    for part in re.split(r"[\s,]+", raw):
        part = part.strip().strip('"').strip("'")
        if part and _is_configured_api_key(part):
            keys.append(part)
    # Also honor a single STEPFUN_API_KEY if the pool is empty or separately set.
    single = os.getenv("STEPFUN_API_KEY", "").strip()
    if single and _is_configured_api_key(single) and single not in keys:
        keys.insert(0, single)
    if not keys:
        raise StepfunConfigurationError(
            "No usable StepFun API key found. Set STEPFUN_API_KEYS (multi-line) or STEPFUN_API_KEY."
        )
    return _KeyPool(keys)


_KEY_POOL = None
_KEY_POOL_LOCK = threading.Lock()


def get_key_pool() -> _KeyPool:
    """Lazily build and cache the shared key pool (one per process)."""
    global _KEY_POOL
    if _KEY_POOL is None:
        with _KEY_POOL_LOCK:
            if _KEY_POOL is None:
                _KEY_POOL = _load_key_pool()
    return _KEY_POOL


# --------------------------------------------------------------------------------------
# Global rate limiter
#
# During the SWE-bench run we discovered the Stepfun quota admits only about 2-3
# concurrent requests and then returns 429 for tens of seconds. Per-call retry with a
# 0.5s base delay cannot recover from that: it burns its 3 attempts in ~2s and raises,
# leaving the instance marked INFRA-FAIL. The fix is a *global* throttle so the whole
# process never exceeds the quota in the first place.
#
# Token-bucket: one token per MIN_INTERVAL seconds, refilled lazily, guarded by a lock
# so all worker threads share one bucket. Threads that would exceed the rate sleep
# until a token is available. This is cooperative pacing, not a busy spin.
# --------------------------------------------------------------------------------------

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_BUCKET_TOKENS = 1.0
_RATE_BUCKET_UPDATED = 0.0
_MIN_INTERVAL_SECONDS = float(os.getenv("STEPFUN_MIN_INTERVAL", "0.9"))


def _acquire_rate_token() -> None:
    """Block until the global token bucket allows one request."""
    global _RATE_BUCKET_TOKENS, _RATE_BUCKET_UPDATED
    while True:
        with _RATE_LIMIT_LOCK:
            now = time.monotonic()
            elapsed = now - _RATE_BUCKET_UPDATED
            _RATE_BUCKET_TOKENS = min(1.0, _RATE_BUCKET_TOKENS + elapsed / _MIN_INTERVAL_SECONDS)
            _RATE_BUCKET_UPDATED = now
            if _RATE_BUCKET_TOKENS >= 1.0:
                _RATE_BUCKET_TOKENS -= 1.0
                return
            # Seconds until the bucket refills to 1.0. Guarded with max(0, ...) so a
            # large elapsed (many threads were waiting) never yields a negative wait.
            wait = max(0.0, (_MIN_INTERVAL_SECONDS - elapsed) / max(_RATE_BUCKET_TOKENS, 1e-9))
        time.sleep(min(wait, 1.0))


class StepfunConfigurationError(RuntimeError):
    """Raised when Stepfun credentials or endpoint settings are missing."""


class StepfunAPIError(RuntimeError):
    """Raised when the Stepfun API request fails or returns an invalid payload."""


def _is_configured_api_key(api_key: Optional[str]) -> bool:
    """Return True only for a non-placeholder Stepfun API key value."""
    if not api_key:
        return False

    normalized = api_key.strip()
    if not normalized:
        return False

    placeholder_fragments = (
        "your-stepfun-api-key",
        "replace-me",
        "placeholder",
        "changeme",
    )
    lowered = normalized.lower()
    return not any(fragment in lowered for fragment in placeholder_fragments)


def sanitize_llm_text(text: str) -> str:
    """
    Apply lightweight context sanitation at the LLM gateway.

    This central guard complements Context Curator agents and protects direct
    LLM callers from sending obvious tracebacks or excessive whitespace.

    """
    if not isinstance(text, str):
        raise ValueError("LLM text payload must be a string.")

    sanitized = re.sub(
        r"Traceback \(most recent call last\):.*?(?=\n\n|\Z)",
        "[Traceback Omitted for Context Hygiene]",
        text,
        flags=re.DOTALL,
    )
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()


def get_stepfun_config(model: Optional[str] = None) -> dict:
    """
    Read and validate Stepfun configuration from environment variables.

    The API key is drawn from the shared key pool (11 accounts) rather than a single
    static key. Callers must not cache the returned ``api_key`` across requests — it is
    only valid for the one call that fetched it. Rotate via the pool on 429.

    Args:
        model: Optional model override. If omitted, STEPFUN_MODEL is used.

    Returns:
        Dictionary containing ``api_key``, ``base_url``, and ``model``.

    Raises:
        StepfunConfigurationError: If no usable Stepfun key is configured.
    """
    pool = get_key_pool()
    api_key = pool.next_available()
    if not api_key:
        raise StepfunConfigurationError(
            "No usable StepFun API key available (all keys in cooldown or unset). "
            "Configure STEPFUN_API_KEYS or STEPFUN_API_KEY."
        )

    base_url = os.getenv("STEPFUN_BASE_URL", DEFAULT_STEPFUN_BASE_URL).strip().rstrip("/")
    target_model = (model or os.getenv("STEPFUN_MODEL", DEFAULT_STEPFUN_MODEL)).strip()

    if not base_url:
        raise StepfunConfigurationError("STEPFUN_BASE_URL must not be empty.")
    if not target_model:
        raise StepfunConfigurationError("STEPFUN_MODEL must not be empty.")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": target_model,
    }


def _extract_http_error_body(exc: urllib.error.HTTPError) -> str:
    """Extract a bounded, safe HTTP error body for diagnostics."""
    try:
        return exc.read().decode("utf-8", errors="replace")[:1000]
    except Exception as body_exc:
        logger.debug("Could not read HTTP error body: %s", body_exc)
        return str(getattr(exc, "reason", "no response body"))


def _retry_after_seconds(exc: urllib.error.HTTPError, default_delay: float) -> float:
    """Read Retry-After header if present, otherwise use exponential default."""
    try:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            return min(float(retry_after), 10.0)
    except Exception as ra_exc:
        logger.debug("Could not parse Retry-After header: %s", ra_exc)
        pass
    return default_delay


def call_stepfun_native(
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: float = 0.0,
    timeout: int = 300,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    max_tokens: int = 16384,
) -> str:
    """
    Call Stepfun's chat completions endpoint using stdlib HTTP.

    Args:
        prompt: User message content sent to the model.
        system_prompt: Optional system message content.
        model: Optional Stepfun model override.
        temperature: Sampling temperature.
        timeout: HTTP request timeout in seconds.
        max_retries: Retry count for transient 429/5xx/network failures.
        backoff_seconds: Initial exponential-backoff delay.

    Returns:
        Assistant message content from the Stepfun response.

    Raises:
        ValueError: If ``prompt`` is empty.
        StepfunConfigurationError: If required Stepfun config is missing.
        StepfunAPIError: If the HTTP call or response parsing fails.
    """
    sanitized_prompt = sanitize_llm_text(prompt)
    sanitized_system_prompt = sanitize_llm_text(system_prompt) if system_prompt else ""
    if not sanitized_prompt:
        raise ValueError("prompt must be a non-empty string after sanitation.")

    config = get_stepfun_config(model=model)
    base_url = config["base_url"]
    url = (
        base_url
        if base_url.endswith("/chat/completions")
        else f"{base_url}/chat/completions"
    )

    messages = []
    if sanitized_system_prompt:
        messages.append({"role": "system", "content": sanitized_system_prompt})
    messages.append({"role": "user", "content": sanitized_prompt})

    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        # Bound generation explicitly. Without max_tokens the model generates until it
        # decides to stop -- measured at 16,122 completion tokens / 135.5s on a routine
        # analysis prompt, against a 30s client timeout. Every such call died mid-flight
        # and was recorded as an "infrastructure" failure, biased toward the hardest
        # cases (long reasoning) and therefore flattering the system.
        "max_tokens": max_tokens,
    }

    last_error = None
    attempts = max(0, int(max_retries)) + 1
    for attempt in range(attempts):
        _acquire_rate_token()
        # Pull a fresh key from the pool each attempt so a 429 on one account rotates
        # to a different account rather than re-hammering the same exhausted quota.
        config = get_stepfun_config(model=model)
        used_key = config["api_key"]
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {used_key}",
            },
            method="POST",
        )

        start_time = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Stepfun request succeeded model=%s duration_ms=%s attempt=%s",
                config["model"],
                duration_ms,
                attempt + 1,
            )
        except urllib.error.HTTPError as exc:
            error_body = _extract_http_error_body(exc)
            last_error = StepfunAPIError(f"Stepfun API returned HTTP {exc.code}: {error_body}")
            if exc.code in _RETRYABLE_HTTP_STATUS and attempt < attempts - 1:
                if exc.code == 429:
                    # Rotate: park this key, let the next attempt pick a fresh one.
                    get_key_pool().mark_rate_limited(used_key, cooldown_seconds=30.0)
                delay = _retry_after_seconds(exc, backoff_seconds * (2 ** attempt))
                logger.warning(
                    "Stepfun retryable HTTP error status=%s attempt=%s/%s delay=%s",
                    exc.code,
                    attempt + 1,
                    attempts,
                    delay,
                )
                time.sleep(delay)
                continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = StepfunAPIError(f"Stepfun API request failed: {exc}")
            if attempt < attempts - 1:
                delay = backoff_seconds * (2 ** attempt)
                logger.warning(
                    "Stepfun retryable transport error attempt=%s/%s delay=%s error=%s",
                    attempt + 1,
                    attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
                continue
            raise last_error from exc

        try:
            data = json.loads(body)
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            finish_reason = choice.get("finish_reason")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise StepfunAPIError(
                f"Stepfun API returned an invalid chat-completions payload: {body[:500]}"
            ) from exc

        if content.strip():
            return content

        # Empty content is NOT success. `step-3.7-flash` is a reasoning model: when the
        # token budget is consumed by internal reasoning it returns finish_reason="length"
        # with content="" and the whole answer sitting in `reasoning` / `reasoning_content`.
        # Measured: prompt_tokens=45, completion_tokens=4096, content len=0,
        # reasoning len=20,022. Returning "" here silently discarded the model's entire
        # output and every downstream agent saw "the model produced nothing" -- the literal
        # shape of "good reasoning produced, then dropped".
        reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
        if reasoning.strip():
            raise StepfunAPIError(
                "Stepfun returned reasoning but no final content "
                f"(finish_reason={finish_reason!r}, reasoning_chars={len(reasoning)}). "
                "The token budget was consumed by reasoning before an answer was emitted. "
                "Raise max_tokens or shorten the prompt. Not retried: it would fail again."
            )
        raise StepfunAPIError(
            f"Stepfun returned empty content (finish_reason={finish_reason!r})."
        )

    raise last_error or StepfunAPIError("Stepfun API request failed without a captured error.")


def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: float = 0.0,
    timeout: int = 300,
    max_retries: int = 2,
    backoff_seconds: float = 0.5,
    max_tokens: int = 16384,
) -> str:
    """
    Call the configured Stepfun model.

    This is the single public LLM entry point for the project. It has no
    alternate-provider routing and no fallback response path. All callers
    therefore get real Stepfun output or a loud exception.
    """
    return call_stepfun_native(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        max_tokens=max_tokens,
    )


# Manual smoke test helper. Requires a real STEPFUN_API_KEY.
def test_llm() -> bool:
    """Run a manual Stepfun connectivity smoke test."""
    print("Testing Stepfun LLM integration...")
    try:
        response = call_llm(
            prompt="Say 'Hello from Stepfun REST API!'",
            system_prompt="You are a helpful assistant.",
        )
        print(f"✓ Stepfun response: {response[:100]}...")
        return True
    except Exception as exc:  # pragma: no cover - manual helper
        print(f"✗ Error: {exc}")
        return False


if __name__ == "__main__":
    test_llm()
