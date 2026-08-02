# Debugger Agent - Test-Driven Surgical Repair

**Category:** repair | **Layer:** 3 Verification & Repair | **Inspired by:** Reflexion + AlphaCode Debug Loop

## Role

Fixes failing code based on test failure output. This was the missing piece that prevented HumanEval from reaching 100% (tasks 76, 116, 145 failed without test-driven repair).

Unlike Surgical Refiner which fixes AST violations, Debugger fixes **runtime failures** (assertions, tracebacks).

## Permission Matrix (Law 2)

```python
READ: [failed_code, test_failure, traceback, problem_spec, past_reflections]
WRITE: [fixed_code, debug_summary, fix_attempts]
NEVER: [credentials, deployment, production_config, database_migration]
HUMAN_CHECKPOINT: [security_critical_fix, infinite_retry_loop]
```

## Karpathy Loop

- **Propose:** Sanitize failure output, check NEVER permissions (no hardcoded secrets)
- **Execute:** Call Stepfun with surgical prompt: failed_code + test_failure + past_reflections -> fixed_code
- **Evaluate:** ZERO-LLM AST validation only (validate_python_syntax)
- **Commit/Refine:** Commit if AST valid, else retry max 3

## Inputs / Outputs

- Input: failed_code (str), test_failure (str), problem_spec (str), past_reflections (List[str])
- Output: fixed_code (str), success (bool), violations, debug_summary, fix_attempts

## Context Integration

Works with existing `AuthContextManager`, `DBContextManager` etc via `DebugContextManager.filter_debug_context()` which keeps only relevant traceback lines (assert, error, expected/got).

## Example

```
Failed: assert sort_array([1,5,2]) == [1,2,5] got [2,1,5]
Past reflection: "Failed because I didn't handle binary ones count ordering"
Fixed: Correct implementation with key=lambda x: (bin(x).count('1'), x)
```

## Governance

- Law 3: Fails loudly if code empty, max retries 3 then escalates
- Law 11: Evaluate never calls LLM
- Law 12: Sanitizes failure output (last 800 chars, collapse newlines)

## Relation to Full Graph

In Ultimate Graph: `CODE_GENERATED -> TESTS_FAILED -> DEBUGGER_AGENT -> TESTS_PASSED`
In Competitive Slice: Inner loop for each candidate after execution filter fails.

## Tests

`tests/test_debugger_agent.py` - permission matrix, sanitization, fix prompt building, AST validation gate.
