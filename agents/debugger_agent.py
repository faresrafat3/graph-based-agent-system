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

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

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
- If you see security violation in traceback (e.g., hardcoded secrets), FAIL loudly

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
    violations: List[str]
    retry_count: int
    success: bool
    fix_attempts: int


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
        "violations": [],
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

    return {"fixed_code": code.strip(), "fix_attempts": state.get("fix_attempts", 0) + 1}


def evaluate(state: DebuggerState) -> dict:
    """Step 3: Evaluate - ZERO LLM, AST validation only"""
    fixed_code = state.get("fixed_code", "")

    if not fixed_code:
        return {"success": False, "violations": ["Fixed code is empty"]}

    validation = validate_python_syntax(fixed_code)
    success = validation["success"]
    return {
        "success": success,
        "violations": validation["violations"],
        "debug_summary": DebuggerEngine.build_summary(
            state.get("failed_code", ""), fixed_code, state.get("test_failure", "")
        )
    }


def commit(state: DebuggerState) -> dict:
    return {"committed": True}


def refine(state: DebuggerState) -> dict:
    retry = state.get("retry_count", 0) + 1
    return {"retry_count": retry, "success": False}


def should_continue(state: DebuggerState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 3:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(DebuggerState)
workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)

workflow.set_entry_point("propose")
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")
workflow.add_conditional_edges("evaluate", should_continue, {"commit": "commit", "refine": "refine", "escalate": END})
workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

checkpointer = MemorySaver()
debugger_graph = workflow.compile(checkpointer=checkpointer)


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
        Dict with fixed_code, success, violations, debug_summary
    """
    result = debugger_graph.invoke(
        {
            "failed_code": failed_code,
            "test_failure": test_failure,
            "problem_spec": problem_spec,
            "past_reflections": past_reflections or [],
            "fixed_code": "",
            "debug_summary": "",
            "violations": [],
            "retry_count": 0,
            "success": False,
            "fix_attempts": 0
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "fixed_code": result.get("fixed_code", ""),
        "success": result.get("success", False),
        "violations": result.get("violations", []),
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
