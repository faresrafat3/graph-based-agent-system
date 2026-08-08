# CRITICAL: The measured results are an artifact of two defects, not of the system

**Date:** 2026-08-08
**Status:** VERIFIED against the live dataset and by direct reproduction
**Consequence:** Every arm-to-arm comparison in `docs/AGENT-LOOP-EXPERIMENT.md` is void.

---

## 0. Summary

Two independent defects — one in the harness, one in the LLM client — jointly manufactured
the numbers the project has been reasoning from. Neither is a model failure and neither is an
architecture failure. Both were verified directly, not inferred.

| # | Defect | Location | Effect |
|---|---|---|---|
| D1 | `FAIL_TO_PASS` is a JSON **string**, guarded as if it were a nested list | `benchmarks/swebench_harness.py:1050-1055` | The grading command is built **character by character**. Grading never ran as intended. |
| D2 | The request body omits `max_tokens` while the client timeout is 30s | `llm/llm_integration.py:331-335` vs `:289` | Generation is unbounded; realistic prompts run ~135s and are killed at 30s, then recorded as "infrastructure". |

---

## 1. D1 — the grader was iterating characters

`run_commands` receives `ftp_cmds` and only flattens when the first element is a *list*:

```python
ftp_cmds = instance.get("FAIL_TO_PASS", [])
if ftp_cmds and isinstance(ftp_cmds[0], list):     # :1050
    ftp_cmds = [c for sub in ftp_cmds for c in sub]
```

In SWE-bench Verified, `FAIL_TO_PASS` is a **JSON-encoded string**. So `ftp_cmds[0]` is the
character `'['`, the guard is False, and the string falls through to be iterated one character
at a time. Each character becomes a test command at `:1035`:

```python
full = cmd if cmd.strip().startswith(("python","pytest","python3")) else f"python -m pytest {cmd} -x -q"
```

**Verified against the live dataset — all 8 `psf/requests` instances used in every arm:**

| instance | `FAIL_TO_PASS` type | guard `isinstance(f[0], list)` | first command actually run |
|---|---|---|---|
| psf__requests-1142 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-1724 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-1766 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-1921 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-2317 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-2931 | `str` | False | `python -m pytest [ -x -q` |
| psf__requests-5414 | `str` | False | `python -m pytest [ -x -q` (string contains `/`) |
| psf__requests-6028 | `str` | False | `python -m pytest [ -x -q` (string contains `/`) |

**8 of 8 — not an edge case. The local grading path never worked.**

Two consequences:

1. `ftp_total` becomes the character count of a JSON string, so `ftp_pass == ftp_total` is
   essentially unreachable. Any metric derived from local grading is meaningless.
2. For 5414 and 6028 the string contains `/`, so the harness runs `python -m pytest /` — it
   walks the entire filesystem until the 120s timeout at `:1037`, and the result is stamped
   `failure_class="infrastructure"` at `:1206-1208`. These are **exactly** the two instances
   recorded as `TimeoutExpired: Command 'python -m pytest /'`.

A harness defect was being scored as "not the model's fault" and then silently removed from
the denominator.

## 2. D2 — unbounded generation against a 30-second timeout

The request body never sets `max_tokens`:

```python
data-bundle = {"model": ..., "messages": messages, "temperature": temperature}   # :331-335
```

while the client timeout defaults to 30s (`:289`).

**Reproduced directly. Same prompt, only `max_tokens` varied:**

| Setting | Elapsed | Completion tokens | Result |
|---|---|---|---|
| **unbounded (what the code sends)** | **135.5s** | **16,122** | exceeds the 30s timeout |
| `max_tokens=400` | 5.2s | 400 | fine |
| `max_tokens=800` | 12.4s | 800 | fine |
| `max_tokens=1500` | 23.8s | 1500 | fine |

Through the project's own `call_stepfun_native`: a trivial prompt returns in 3.3s, while a
realistic decomposition prompt fails at **30.4s and 30.6s** on two consecutive attempts.

**The provider was cleared of blame by measurement**, so this cannot be attributed to Stepfun:

| Hypothesis | Test | Result |
|---|---|---|
| API down | direct call | 200 OK |
| API slow | 800-token request | ~9s |
| Concurrency limit | 8 parallel requests | 8/8 succeeded |
| Keys exhausted | pool check | 1 usable key, working |

The API is healthy. The client asks for something unbounded and then refuses to wait for it.

**This defect is biased toward the hardest cases.** Simple prompts finish inside 30s; complex
multi-step reasoning — precisely what the arms were built to measure — generates more tokens
and is killed. The measurement removes the cases that carry the signal.

---

## 3. Why this invalidates the arm comparison

`AGENT-LOOP-EXPERIMENT.md` reports large numbers of "infra-fails" (5/8 in the loop arm, 4/8 in
the graph arm) and interprets them as network loss. They are not network loss. They are D1 and
D2 firing, and both are code defects.

The published conclusions therefore do not hold:

- "Applicability rose 3→4→5→7" — measured through a grader that never graded correctly.
- "Resolve rate is stuck at 1/8" — the local resolve signal was computed from character-wise
  pytest invocations.
- "The generator is the ceiling" — untestable while the two defects are live.
- "loop arm proves feedback does not help" — the feedback path was being truncated at 30s.

**Nothing here shows the architecture is good or bad. It shows the instrument was broken.**

This is the project's own stated lesson repeating: 4 parser defects previously misclassified
sound cases as infrastructure failures, all biased toward flattering the system. Same pattern,
larger blast radius.

---

## 4. Required order of work

1. **Fix D1 and D2.** Both are small and local.
2. **Re-run every arm** with the same harness, unchanged architecture.
3. **Only then** interpret any number.

Until step 2 completes, no claim about the graph, the model, or the ceiling is supported by
evidence. Both fixes change behavior for every LLM call and every graded instance, so they
require the architect's approval before being applied.

## 5. What this does NOT prove

- Does not prove the resolve rate rises after the fixes. It may not. It proves only that the
  current numbers cannot support any conclusion.
- Does not prove there are no further defects; two were found by looking, and the audit
  catalogued ~14 sites where errors are quietly absorbed.
- D2's 135.5s figure is one prompt on one day; latency varies. The invariant finding is the
  absence of a token bound against a fixed timeout, not the specific duration.
