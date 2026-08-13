"""
Debugger Agent - Test-Driven Surgical Repair (Reflexion + AlphaCode Debug Insight)

Inspired by Reflexion's verbal reinforcement and AlphaCode's filtering loop, but
implemented under the Graph-Based System's Constitution:

- LLM is sandboxed CPU (only generates fix)
- Evaluate is ZERO-LLM (AST + execution result check)
- Permission boundaries enforced
- Karpathy Loop: Propose -> Execute -> Evaluate -> Commit/Refine

Role: Takes a failing code + test failure traceback and produces a fixed version.
This was the missing piece that prevented HumanEval from reaching 100% (task 116, 76, 145).
"""

import os
import sys
import re
from typing import TypedDict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kernel.karpathy_loop import build_karpathy_loop, standard_refine, standard_should_continue

from llm.llm_integration import call_llm
from agents.code_executor import validate_python_syntax
from agents.domain_context_managers import BaseDomainContextManager


DEBUGGER_PERMISSIONS = {
    "READ": ["failed_code", "test_failure", "traceback", "problem_spec", "past_reflections"],
    "WRITE": ["fixed_code", "debug_summary", "fix_attempts"],
    "NEVER": ["credentials", "deployment", "production_config", "database_migration"],
    "HUMAN_CHECKPOINT": ["security_critical_fix", "infinite_retry_loop"]
}

# System prompt - strong, surgical, law-abiding
DEBUGGER_SYSTEM_PROMPT = """You are a Debugger Agent in a graph-based multi-agent system.

Your ONLY job is to fix a failing Python function based on test failure output.

RULES (Constitution + Laws):
- Think before acting - analyze traceback thoroughly
- Simplicity first - fix ONLY the failing part, preserve correct logic
- Surgical changes - do NOT regenerate entire unrelated code
- Output ONLY raw Python code, No prose, No markdown fences, No explanation
- Include complete function definition with signature
- Include any needed imports at top
- The fix MUST be runnable, complete
- NEVER output TODO, pass placeholders, or credentials
- If you see security breach in traceback (e.g., hardcoded secrets), FAIL loudly

Format: Return ONLY the fixed Python code.
"""


class DebuggerState(TypedDict):
    failed_code: str
    test_failure: str
    problem_spec: str
    traceback: str
    past_reflections: List[str]
    fixed_code: str
    debug_summary: str
    breaches: List[str]
    retry_count: int
    success: bool
    fix_attempts: int
    repeated_hypothesis_count: int


def _similarity(a: str, b: str) -> float:
    """Cheap lexical overlap ratio between two reflections/hypotheses.

    Used only for OBSERVABILITY (P7): detect when the debugger repeats a
    near-identical hypothesis across retries (thrashing). Returns 0.0-1.0.
    No control flow depends on this.

    HARDENED (v9, opus-5 P4 review): callers should pass EXTRACTED hypotheses
    (see extract_hypothesis), not raw reflection text, so rephrasing of one theory
    is detected as thrash instead of missed (false negative).
    """
    if not a or not b:
        return 0.0
    a_set, b_set = set(a.lower().split()), set(b.lower().split())
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


# Canonical hypothesis "kinds" we can detect from a reflection without an LLM.
# Each maps a set of trigger words to a normalized claim fragment. This lets us
# compare HYPOTHESIS IDENTITY (what is being tried) rather than word reuse.
_HYPOTHESIS_KINDS = [
    ("off_by_one", ["off-by-one", "off by one", "boundary", "loop limit", "off-by",
                    "upper bound", "increment", "off by", "one less", "one more"]),
    ("div_by_zero", ["divide by zero", "division by zero", "divided by", "zero division"]),
    ("wrong_sort", ["sort", "ordering", "ascending", "descending"]),
    ("index_error", ["index", "out of range", "subscript"]),
    ("type_error", ["type", "cast", "convert"]),
    ("null_none", ["none", "null", "nil", "missing"]),
    ("wrong_var", ["variable", "wrong variable", "typo in name"]),
    ("logic_flaw", ["logic", "condition", "branch", "if statement"]),
]


def extract_hypothesis(reflection: str) -> str:
    """Extract a structured HYPOTHESIS claim from a free-text reflection (zero-LLM).

    Returns a canonical string like "off_by_one|limit+1" so that two rephrasings
    of the same theory map to the SAME string (fixing the false-negative opus-5 flagged).
    Two genuinely different theories map to DIFFERENT strings.

    Method: detect the error KIND from trigger words, then capture the concrete
    TARGET of the fix (the noun after the kind keyword, e.g. "limit", "bound", "b") as
    a normalized fragment. Deterministic + auditable. Comparing TARGET not wording
    means "add 1 to the limit" == "incrementing the limit" (same hypothesis).
    """
    if not reflection:
        return ""
    low = reflection.lower()

    # 1) error kind
    kind = "unknown"
    for k, triggers in _HYPOTHESIS_KINDS:
        if any(t in low for t in triggers):
            kind = k
            break

    # 2) concrete TARGET fragment: the kind-related word itself is the fix target
    #    signature (e.g. "limit", "bound", "b"). Comparing the TARGET not surrounding
    #    wording means "add 1 to the limit" == "incrementing the limit" (same hypothesis).
    target = ""
    for marker in ("limit", "bound", "boundary", "index", "variable", "range"):
        if marker in low:
            target = marker
            break
    # special-case single-letter variables b / n
    if not target:
        for ch in ("b", "n"):
            if f" {ch} " in low or low.endswith(f" {ch}"):
                target = f"var_{ch}"
                break
    if not target:
        target = " ".join(low.split()[:3])

    return f"{kind}|{target}".strip("|")



class DebuggerEngine:
    """Deterministic helpers for debugger"""

    @staticmethod
    def sanitize_failure_output(text: str) -> str:
        """Remove noise, keep signal - Context Hygiene Law 12"""
        if not text:
            return ""
        # Keep only last 800 chars of traceback (most relevant)
        text = text[-2000:] if len(text) > 2000 else text
        # Collapse excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def build_fix_prompt(failed_code: str, test_failure: str, problem_spec: str, past_reflections: List[str]) -> str:
        """Build surgical fix prompt with reflection memory"""
        reflection_block = ""
        if past_reflections:
            reflection_block = "\n".join(f"- {r}" for r in past_reflections[-3:])  # last 3
            reflection_block = f"\nPAST REFLECTIONS (learnings from previous failures):\n{reflection_block}\n"

        return f"""PROBLEM SPECIFICATION:
{problem_spec}

FAILED CODE:
{failed_code}

TEST FAILURE:
{test_failure}
{reflection_block}
TASK: Fix ONLY the failing logic. Preserve correct parts.

Output ONLY the complete fixed Python function.
"""

    @staticmethod
    def build_summary(failed_code: str, fixed_code: str, test_failure: str) -> str:
        """Deterministic debug summary"""
        return f"Fixed code that failed with: {test_failure[:200]}... Code changed: {len(fixed_code) - len(failed_code)} chars delta"


def propose(state: DebuggerState) -> dict:
    """Step 1: Propose - Analyze failure, check NEVER permissions"""
    failed_code = state.get("failed_code", "")
    test_failure = state.get("test_failure", "")

    # Permission check - NEVER allow fixing by adding credentials
    combined = (failed_code + test_failure).lower()
    if any(x in combined for x in ["password =", "secret_key =", "hardcoded api key"]):
        # If the failure is about security, we should fail loudly, not fix silently
        if "hardcoded" in combined:
            raise PermissionError("Debugger attempted to handle credentials in NEVER permission.")

    sanitized_failure = DebuggerEngine.sanitize_failure_output(test_failure)
    return {
        "test_failure": sanitized_failure,
        "breaches": [],
        "success": False
    }


def execute(state: DebuggerState) -> dict:
    """Step 2: Execute - Call LLM to generate fix"""
    failed_code = state.get("failed_code", "")
    test_failure = state.get("test_failure", "")
    problem_spec = state.get("problem_spec", "")
    past_reflections = state.get("past_reflections", [])

    prompt = DebuggerEngine.build_fix_prompt(failed_code, test_failure, problem_spec, past_reflections)
    raw_response = call_llm(prompt, DEBUGGER_SYSTEM_PROMPT, temperature=0.2)

    # Strip fences deterministically
    code = raw_response.strip()
    fenced = re.findall(r"```(?:python|py)?\s*\n(.*?)```", code, re.DOTALL)
    if fenced:
        code = max(fenced, key=len)
    code = re.sub(r"^```(?:python|py)?\s*", "", code)
    code = re.sub(r"```\s*$", "", code)

    # Observability (P7): detect thrashing — repeated near-identical hypotheses.
    # HARDENED (v9, opus-5 P4 review): compare EXTRACTED hypotheses, not raw text, so
    # rephrasing of one theory is caught (false negative fixed), while genuinely
    # narrowing (different hypothesis) is not falsely flagged (false positive fixed).
    repeated = state.get("repeated_hypothesis_count", 0)
    if len(past_reflections) >= 2:
        prev, curr = past_reflections[-2], past_reflections[-1]
        prev_h, curr_h = extract_hypothesis(prev), extract_hypothesis(curr)
        if prev_h and curr_h and _similarity(prev_h, curr_h) >= 0.99:
            repeated += 1

    return {
        "fixed_code": code.strip(),
        "fix_attempts": state.get("fix_attempts", 0) + 1,
        "repeated_hypothesis_count": repeated,
    }


def evaluate(state: DebuggerState) -> dict:
    """Step 3: Evaluate - ZERO LLM, AST validation only"""
    fixed_code = state.get("fixed_code", "")

    if not fixed_code:
        return {"success": False, "breaches": ["Fixed code is empty"]}

    validation = validate_python_syntax(fixed_code)
    success = validation["success"]
    return {
        "success": success,
        "breaches": validation["breaches"],
        "debug_summary": DebuggerEngine.build_summary(
            state.get("failed_code", ""), fixed_code, state.get("test_failure", "")
        )
    }

def refine(state: DebuggerState) -> dict:
    return standard_refine(state)


def should_continue(state: DebuggerState) -> str:
    return standard_should_continue(state, retry_cap=3)


debugger_graph = build_karpathy_loop(
    DebuggerState,
    execute_fn=execute,
    propose_fn=propose,
    evaluate_fn=evaluate,
    retry_cap=3,
)


def debug_code(
    failed_code: str,
    test_failure: str,
    problem_spec: str = "",
    past_reflections: List[str] = None,
    thread_id: str = "debugger_session"
) -> dict:
    """
    Main entrypoint - Test-driven surgical repair.

    Args:
        failed_code: Code that failed tests
        test_failure: Traceback / assertion failure output
        problem_spec: Original problem spec (for context)
        past_reflections: List of past verbal reflections (Reflexion memory)
        thread_id: LangGraph thread id

    Returns:
        Dict with fixed_code, success, breaches, debug_summary
    """
    result = debugger_graph.invoke(
        {
            "failed_code": failed_code,
            "test_failure": test_failure,
            "problem_spec": problem_spec,
            "past_reflections": past_reflections or [],
            "fixed_code": "",
            "debug_summary": "",
            "breaches": [],
            "retry_count": 0,
            "success": False,
            "fix_attempts": 0
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "fixed_code": result.get("fixed_code", ""),
        "success": result.get("success", False),
        "breaches": result.get("breaches", []),
        "debug_summary": result.get("debug_summary", ""),
        "fix_attempts": result.get("fix_attempts", 0)
    }


# Context Manager specialization for debugger - reuses existing domain managers
class DebugContextManager(BaseDomainContextManager):
    """Specialized context manager for debugging - filters debug-relevant context only"""

    def filter_debug_context(self, global_context: str, failure_output: str) -> dict:
        # Only keep lines that contain assert, error, or function name
        filtered = super().filter_context(global_context, domain_specific_data=failure_output)
        # Additional debug-specific filtering: keep traceback lines
        lines = (failure_output or "").split("\n")
        debug_lines = [l for l in lines if any(k in l.lower() for k in ["assert", "failed", "error", "traceback", "expected", "got"])]
        debug_snippet = "\n".join(debug_lines[-10:])  # last 10 relevant
        return {
            "filtered_context": filtered["filtered_context"],
            "debug_snippet": debug_snippet,
            "signal_to_noise": filtered.get("signal_to_noise", 1.0)
        }
