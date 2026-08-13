"""
Measurement harness for decision #3 (probe budget).

Goal: empirically observe whether the debugger/reflexion loops repeat a
near-identical hypothesis across retries (thrashing) on REAL broken code.

We do NOT change any control flow. We only run the existing Karpathy loops
and report `repeated_hypothesis_count` so the architect can decide whether
a probe budget (P4) is warranted.

Run: export PYTHONPATH= && source .env && python scripts/measure_thrashing.py
"""
import os

# Load project .env if present (does not print keys)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    from dotenv import dotenv_values
    for k, v in dotenv_values(env_path).items():
        os.environ.setdefault(k, v)

from agents.debugger_agent import (
    DebuggerState,
    propose as dbg_propose,
    execute as dbg_execute,
    evaluate as dbg_evaluate,
    refine as dbg_refine,
    should_continue as dbg_should_continue,
)
from agents.reflexion_agent import (
    ReflexionState,
    propose as ref_propose,
    execute as ref_execute,
    evaluate as ref_evaluate,
    refine as ref_refine,
    should_continue as ref_should_continue,
)


# --- A few REAL broken-code samples (small, deterministic) ---
SAMPLES = [
    {
        "name": "off_by_one_sum",
        "failed_code": "def sum_to_n(n):\n    total = 0\n    i = 1\n    while i < n:\n        total += i\n        i += 1\n    return total\n",
        "test_failure": "assert sum_to_n(5) == 15  # got 10",
        "problem_spec": "Return the sum of integers from 1 to n inclusive.",
    },
    {
        "name": "wrong_sort_condition",
        "failed_code": "def is_sorted(arr):\n    for i in range(len(arr) - 1):\n        if arr[i] < arr[i + 1]:\n            return False\n    return True\n",
        "test_failure": "assert is_sorted([3, 1, 2]) == False  # got True",
        "problem_spec": "Return True if arr is sorted ascending, else False.",
    },
    {
        "name": "div_by_zero_guard",
        "failed_code": "def safe_div(a, b):\n    return a / b\n",
        "test_failure": "safe_div(1, 0) raised ZeroDivisionError",
        "problem_spec": "Return a/b, or 0.0 when b is 0.",
    },
]


def run_debugger(sample):
    state = DebuggerState(
        failed_code=sample["failed_code"],
        test_failure=sample["test_failure"],
        problem_spec=sample["problem_spec"],
        traceback="",
        past_reflections=[],
        fixed_code="",
        debug_summary="",
        breaches=[],
        retry_count=0,
        success=False,
        fix_attempts=0,
        repeated_hypothesis_count=0,
    )
    rounds = []
    for _ in range(5):
        p = dbg_propose(state)
        state.update(p)
        e = dbg_execute(state)
        state.update(e)
        ev = dbg_evaluate(state)
        state.update(ev)
        rounds.append({
            "success": state.get("success"),
            "fix_attempts": state.get("fix_attempts"),
            "repeated_hypothesis_count": state.get("repeated_hypothesis_count"),
        })
        if state.get("success"):
            break
        r = dbg_refine(state)
        state.update(r)
        if dbg_should_continue(state) == "escalate":
            break
    return rounds


def run_reflexion(sample):
    # Reflexion needs an execution_history with reflections; simulate minimal
    state = ReflexionState(
        failed_code=sample["failed_code"],
        test_failure=sample["test_failure"],
        problem_spec=sample["problem_spec"],
        execution_history=[],
        verbal_reflection="",
        reflection_summary="",
        breaches=[],
        retry_count=0,
        success=False,
        repeated_hypothesis_count=0,
    )
    rounds = []
    for _ in range(5):
        p = ref_propose(state)
        state.update(p)
        e = ref_execute(state)
        # Append this reflection to history so next round can compare
        state.setdefault("execution_history", []).append(
            {"reflection": state.get("verbal_reflection", "")}
        )
        state.update(e)
        ev = ref_evaluate(state)
        state.update(ev)
        rounds.append({
            "success": state.get("success"),
            "repeated_hypothesis_count": state.get("repeated_hypothesis_count"),
        })
        if state.get("success"):
            break
        r = ref_refine(state)
        state.update(r)
        if ref_should_continue(state) == "escalate":
            break
    return rounds


def main():
    print("=== THRASHING MEASUREMENT (observability only, no control change) ===\n")
    report = {"debugger": {}, "reflexion": {}}
    for sample in SAMPLES:
        print(f"[sample] {sample['name']}")
        dbg = run_debugger(sample)
        ref = run_reflexion(sample)
        report["debugger"][sample["name"]] = dbg
        report["reflexion"][sample["name"]] = ref
        print(f"  debugger repeated_hypothesis_count: "
              f"{[r['repeated_hypothesis_count'] for r in dbg]}")
        print(f"  reflexion repeated_hypothesis_count: "
              f"{[r['repeated_hypothesis_count'] for r in ref]}\n")

    # Aggregate: did ANY run show repeated hypotheses?
    dbg_max = max(
        (r["repeated_hypothesis_count"] for runs in report["debugger"].values() for r in runs),
        default=0,
    )
    ref_max = max(
        (r["repeated_hypothesis_count"] for runs in report["reflexion"].values() for r in runs),
        default=0,
    )
    print("=== VERDICT ===")
    print(f"  Max repeated_hypothesis_count (debugger): {dbg_max}")
    print(f"  Max repeated_hypothesis_count (reflexion): {ref_max}")
    if dbg_max > 0 or ref_max > 0:
        print("  -> THRASHING OBSERVED: a probe-budget (P4) control is justified.")
    else:
        print("  -> NO THRASHING on these samples: defer probe budget (P7).")
    return dbg_max, ref_max


if __name__ == "__main__":
    main()
