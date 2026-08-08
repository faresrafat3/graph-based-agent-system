# CRITICAL: The measured results are an artifact of three defects, not of the system

**Date:** 2026-08-08
**Status:** ALL THREE VERIFIED, FIXED, AND THE FIXES VERIFIED
**Consequence:** Every arm-to-arm comparison in `docs/AGENT-LOOP-EXPERIMENT.md` is void.

---

## 0. Summary

Three independent defects — two in the harness/client, one in how the response was read —
jointly manufactured the numbers the project has been reasoning from. None is a model failure
and none is an architecture failure. All were verified directly, not inferred.

| # | Defect | Location | Effect | Status |
|---|---|---|---|---|
| D1 | `FAIL_TO_PASS` is a JSON **string**, guarded as if it were a nested list | `swebench_harness.py:1050-1055` | Grading command built **character by character**. Local grading never ran as intended. | FIXED + verified |
| D2 | Request body omitted `max_tokens` while the client timeout was 30s | `llm_integration.py:331-335` vs `:289` | Unbounded generation (135.5s / 16,122 tokens) killed at 30s, recorded as "infrastructure". | FIXED + verified |
| D3 | Only `message.content` was read; empty content returned as success | `llm_integration.py:408` | **The reasoning model's entire output was silently discarded.** | FIXED + verified |

**D3 is the most important finding in this document** and is described in §2b.

---

## 2b. D3 — the model's reasoning was being thrown away

`step-3.7-flash` is a **reasoning model**. Its response places internal reasoning in
`message.reasoning` / `message.reasoning_content` and the final answer in `message.content`.
When the token budget is exhausted by reasoning, the API returns `finish_reason="length"`
with **`content=""`** and the entire body of thought in `reasoning`.

The client did this:

```python
return data["choices"][0]["message"]["content"]      # :408 (before)
```

An empty string was returned as a **successful result**. Measured directly:

| Field | Value |
|---|---|
| `prompt_tokens` | 45 |
| `completion_tokens` | 4096 (budget fully consumed) |
| `finish_reason` | `length` |
| `content` length | **0** |
| `reasoning` length | **20,022 chars** |

So 20,022 characters of correct, relevant reasoning were produced and then dropped on the
floor, and every downstream agent observed "the model produced nothing."

**This is the architect's diagnosis, found in the code:** good reasoning was being generated
and then not captured. It was not a metaphor about graph topology — it was a single line
reading the wrong field.

It also explains the loop arm. Feedback was returned for 4 rounds and "the output never
changed": each round the model reasoned, the answer was discarded, and the caller saw
emptiness. That was recorded as evidence the model cannot use feedback.

### The budget was also wrong, and only measurement showed it

| `max_tokens` | Elapsed | completion_tokens | `finish_reason` | content | Usable? |
|---|---|---|---|---|---|
| 4096 | 33.5s | 4096 | `length` | 0 chars | NO |
| 8192 | 60.3s | 8192 | `length` | 9,594 chars | yes |
| **16384** | 88.5s | **12,550** | **`stop`** | 24,960 chars | **yes, complete** |

This model needs ~12.5k tokens to actually finish. `finish_reason="stop"` first appears at
16384. A 4096 default would have kept truncating every non-trivial call.

**Fix applied:** read `content`; if empty, inspect `reasoning` and raise a loud, specific
`StepfunAPIError` instead of returning `""`. Defaults set from the measurements:
`max_tokens=16384`, `timeout=300`. Honors the project's own Fail-Loud principle — an empty
answer is never silently reported as success.

---

## 1. D1 — the grader was iterating characters

`run_commands` received `ftp_cmds` and only flattened when the first element was a *list*:

```python
ftp_cmds = instance.get("FAIL_TO_PASS", [])
if ftp_cmds and isinstance(ftp_cmds[0], list):     # :1050 (before)
    ftp_cmds = [c for sub in ftp_cmds for c in sub]
```

In SWE-bench Verified, `FAIL_TO_PASS` is a **JSON-encoded string**. So `ftp_cmds[0]` is the
character `'['`, the guard is False, and the string is iterated one character at a time. Each
character becomes a test command at `:1035`:

```python
full = cmd if cmd.strip().startswith(("python","pytest","python3")) else f"python -m pytest {cmd} -x -q"
```

**Verified against the live dataset — all 8 `psf/requests` instances used in every arm had
`type=str`, guard `False`, first command `python -m pytest [ -x -q`. 8 of 8, not an edge case.**

For 5414 and 6028 the string contains `/`, so the harness ran `python -m pytest /`, walking
the entire filesystem until the 120s timeout at `:1037`, then stamped
`failure_class="infrastructure"` at `:1206-1208`. These are **exactly** the two instances
recorded as `TimeoutExpired: Command 'python -m pytest /'`. A harness defect was scored as
"not the model's fault" and silently removed from the denominator.

**Fix applied and verified** — `_normalize_test_commands` handles JSON strings, plain strings,
nested lists and flat lists:

| instance | commands before | commands after |
|---|---|---|
| psf__requests-1142 | chars of a JSON string | 1 real node ID |
| psf__requests-1724 | chars | 6 |
| psf__requests-1766 | chars | 6 |
| psf__requests-1921 | chars | 6 |
| psf__requests-2317 | chars | 8 |
| psf__requests-2931 | chars | 1 |
| psf__requests-5414 | chars (incl. `/`) | 1 |
| psf__requests-6028 | chars (incl. `/`) | 2 |

Instances still yielding single-character commands: **0/8** (was 8/8).

## 2. D2 — unbounded generation against a 30-second timeout

The request body never set `max_tokens` (`:331-335`) while the client timeout defaulted to 30s
(`:289`).

**Reproduced. Same prompt, only `max_tokens` varied:**

| Setting | Elapsed | Completion tokens | Result |
|---|---|---|---|
| **unbounded (what the code sent)** | **135.5s** | **16,122** | exceeds the 30s timeout |
| `max_tokens=400` | 5.2s | 400 | fine |
| `max_tokens=1500` | 23.8s | 1500 | fine |

Through the project's own `call_stepfun_native`: a trivial prompt returned in 3.3s; a realistic
decomposition prompt failed at **30.4s and 30.6s** on two consecutive attempts.

**The provider was cleared of blame by measurement:**

| Hypothesis | Test | Result |
|---|---|---|
| API down | direct call | 200 OK |
| API slow | 800-token request | ~9s |
| Concurrency limit | 8 parallel requests | 8/8 succeeded |
| Keys exhausted | pool check | 1 usable key, working |

The API was healthy. The client asked for something unbounded and then refused to wait.

**D2 and D3 are both biased toward the hardest cases.** Simple prompts finish inside the
budget; complex multi-step reasoning — precisely what the arms were built to measure —
generates more tokens and is either killed (D2) or returned empty (D3). The instrument
deleted exactly the cases carrying the signal.

---

## 3. Why this invalidates the arm comparison

`AGENT-LOOP-EXPERIMENT.md` reports many "infra-fails" (5/8 in the loop arm, 4/8 in the graph
arm) and interprets them as network loss. They were not network loss. They were D1, D2 and D3.

The published conclusions do not hold:

- "Applicability rose 3→4→5→7" — measured through a grader that never graded correctly.
- "Resolve rate is stuck at 1/8" — the local resolve signal came from character-wise pytest runs.
- "The generator is the ceiling" — untestable while three defects were live.
- "The loop arm proves feedback does not help" — the model's answers were being discarded (D3).

**Nothing here shows the architecture is good or bad. It shows the instrument was broken.**

This is the project's own lesson repeating: 4 parser defects previously misclassified sound
cases as infrastructure failures, all biased toward flattering the system. Same pattern,
larger blast radius.

---

## 4. Fixes applied and verified

Two files, 72 lines changed, additive only:

```
benchmarks/swebench_harness.py | 41 ++++++++++++------
llm/llm_integration.py         | 40 +++++++++++++++---
```

Verification actually run:

| Check | Result |
|---|---|
| D1 normalization on the live dataset | 0/8 single-char commands (was 8/8) |
| D3 end-to-end via `call_llm` | 18,781 and 21,629 chars of real JSON (was `chars=0`) |
| `pytest -q` | **1184 passed, 1 skipped, 0 failed** (23.4s) |
| `make compile` | pass |
| `make audit-strict` | Stepfun-only policy pass; governance strict pass, 28 items |

Note the Stepfun-only policy audit still passes: no provider routing was added, consistent
with the standing ruling.

---

## 5. Required next step

**Re-run every arm** with the same harness and unchanged architecture, then interpret. Until
that completes, no claim about the graph, the model, or the ceiling is supported by evidence.

## 6. What this does NOT prove

- Does not prove the resolve rate rises after the fixes. It may not. It proves only that the
  previous numbers cannot support any conclusion.
- Does not prove there are no further defects; three were found by looking, and the apparatus
  audit catalogued ~14 sites where errors are quietly absorbed.
- The 135.5s and 88.5s figures are single measurements on one day; latency varies. The
  invariant findings are structural: no token bound against a fixed timeout, and a reasoning
  model's output read from the wrong field.
