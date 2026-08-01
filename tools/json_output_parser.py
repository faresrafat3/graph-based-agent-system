"""
Shared JSON Output Parser.

LLM responses often wrap JSON in markdown fences or explanatory prose. This
module provides one deterministic parser for all agents that need to extract a
single JSON object from model output. It does not call an LLM and never repairs
invalid JSON silently.
"""

import json
import re
from typing import Any, Iterable


JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _candidate_texts(response: str) -> list[str]:
    """Return parse candidates in priority order."""
    raw = response.strip()
    candidates = []

    for match in JSON_FENCE_RE.finditer(raw):
        fenced = match.group(1).strip()
        if fenced:
            candidates.append(fenced)

    if raw:
        candidates.append(raw)

    return candidates


def extract_first_json_object(response: str) -> dict[str, Any]:
    """
    Extract the first syntactically valid JSON object from response text.

    The implementation uses ``json.JSONDecoder.raw_decode`` from every object
    start marker instead of greedy regular expressions, so braces inside JSON
    strings are handled correctly.

    Raises:
        ValueError: If no JSON object can be decoded.
    """
    if not isinstance(response, str) or not response.strip():
        raise ValueError("Response must be a non-empty string.")

    decoder = json.JSONDecoder()
    errors = []

    for candidate in _candidate_texts(response):
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
                continue
            if isinstance(value, dict):
                return value

    detail = errors[-1] if errors else "no JSON object start found"
    raise ValueError(f"No valid JSON object found in response: {detail}")


def parse_json_object_response(
    response: str,
    required_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """
    Parse one JSON object response and validate optional required keys.

    Args:
        response: Raw LLM or tool response text.
        required_keys: Top-level keys that must exist in the parsed object.

    Returns:
        A result dictionary with ``success``, ``data``, and ``violations``.
    """
    try:
        data = extract_first_json_object(response)
    except ValueError as exc:
        return {
            "success": False,
            "data": {},
            "violations": [str(exc)],
        }

    violations = []
    for key in required_keys or []:
        if key not in data:
            violations.append(f"Missing required JSON key: '{key}'")

    return {
        "success": not violations,
        "data": data,
        "violations": violations,
    }
