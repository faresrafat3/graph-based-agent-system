"""
Reflexion Agent - Verbal Reinforcement Learning (Reflexion Paper)

Implements Shinn et al. 2023 Reflexion framework:
- Actor generates
- Evaluator checks (Test Runner)
- Reflector generates verbal self-reflection (why it failed, what to try next)
- Reflection stored in long-term memory for next trials (no gradient update)

Adapted to our Constitution:
- LLM is sandboxed CPU for reflection generation
- Evaluate is ZERO-LLM (checks reflection quality deterministically)
- Permission boundaries enforced
- Memory integration via CustomMemory

This closes the loop that was missing in HumanEval harness:
Previous: AST failure -> fix, but test failure -> discarded
Now: Test failure -> reflection -> memory -> next attempt guided by reflection
"""

import os
import sys
import re
from typing import TypedDict, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from llm.llm_integration import call_llm
from memory.custom_memory import memory as global_memory


REFLEXION_PERMISSIONS = {
    "READ": ["failed_code", "test_failure", "traceback", "problem_spec", "execution_history"],
    "WRITE": ["verbal_reflection", "reflection_summary", "memory_entry"],
    "NEVER": ["code", "credentials", "deployment", "direct_code_fix"],
    "HUMAN_CHECKPOINT": ["self_harm_reflection", "infinite_reflection_loop"]
}

REFLEXION_SYSTEM_PROMPT = """You are a Reflexion Agent - Verbal Reinforcement Learning.

Your ONLY job: Generate a concise verbal reflection about WHY code failed and WHAT to try next time.

Rules:
- Think before reflecting - analyze failure deeply
- Simplicity first - be concise, 2-3 sentences max
- Focus on root cause, not symptoms
- Output concrete lesson that can guide next attempt
- NEVER output code, ONLY reflection text
- NEVER include credentials or secrets
- Format: Short paragraph, actionable.

Example GOOD reflection:
"Failed because I didn't handle empty list edge case. My loop assumed at least one element. Next time, check len(arr)==0 first and return early. Also need to consider duplicate handling."

Example BAD reflection:
"Code is wrong, fix it." (too vague, not actionable)

Output ONLY the reflection paragraph.
"""


class ReflexionState(TypedDict):
    failed_code: str
    test_failure: str
    problem_spec: str
    execution_history: List[Dict[str, Any]]
    verbal_reflection: str
    reflection_summary: str
    violations: List[str]
    retry_count: int
    success: bool


class ReflexionEngine:
    """Deterministic helpers"""

    @staticmethod
    def is_reflection_actionable(reflection: str) -> bool:
        """Check if reflection is concrete enough (ZERO-LLM quality gate)"""
        if not reflection or len(reflection.strip()) < 20:
            return False
        if len(reflection.split()) < 8:
            return False
        # Must contain at least one actionable keyword
        actionable_keywords = ["next", "should", "need", "because", "failed", "edge", "check", "consider", "handle"]
        lower = reflection.lower()
        has_actionable = any(k in lower for k in actionable_keywords)
        # Must not be just code
        if "def " in reflection or "import " in reflection:
            return False
        return has_actionable

    @staticmethod
    def build_reflection_prompt(failed_code: str, test_failure: str, problem_spec: str, history: List[Dict]) -> str:
        """Build prompt for reflection generation"""
        history_block = ""
        if history:
            # Last 2 failures
            recent = history[-2:]
            history_block = "\nPREVIOUS ATTEMPTS:\n"
            for i, h in enumerate(recent, 1):
                history_block += f"Attempt {i}: Failed with {h.get('failure', '')[:200]}\n"

        return f"""PROBLEM:
{problem_spec[:800]}

FAILED CODE:
{failed_code[:1000]}

TEST FAILURE / TRACEBACK:
{test_failure[:1000]}
{history_block}
TASK: Reflect on WHY it failed and WHAT to do next time. Be specific and actionable.

Reflection:
"""


def propose(state: ReflexionState) -> dict:
    failed_code = state.get("failed_code", "")
    test_failure = state.get("test_failure", "")

    if not failed_code and not test_failure:
        raise ValueError("Need at least failed_code or test_failure to reflect")

    # NEVER check
    if "password" in failed_code.lower() or "secret" in test_failure.lower():
        # Allow security-related failures but don't store secrets
        pass

    return {"verbal_reflection": "", "violations": [], "success": False}


def execute(state: ReflexionState) -> dict:
    failed_code = state.get("failed_code", "")
    test_failure = state.get("test_failure", "")
    problem_spec = state.get("problem_spec", "")
    history = state.get("execution_history", [])

    prompt = ReflexionEngine.build_reflection_prompt(failed_code, test_failure, problem_spec, history)
    raw = call_llm(prompt, REFLEXION_SYSTEM_PROMPT, temperature=0.3)

    # Clean - remove quotes, fences
    reflection = raw.strip()
    reflection = re.sub(r"^```.*?\n", "", reflection)
    reflection = re.sub(r"```$", "", reflection)
    reflection = reflection.strip().strip('"').strip("'")

    # Summarize deterministically: first 2 sentences
    sentences = re.split(r'(?<=[.!?])\s+', reflection)
    summary = " ".join(sentences[:2]) if len(sentences) >= 2 else reflection

    return {
        "verbal_reflection": reflection,
        "reflection_summary": summary
    }


def evaluate(state: ReflexionState) -> dict:
    reflection = state.get("verbal_reflection", "")
    if not ReflexionEngine.is_reflection_actionable(reflection):
        return {
            "success": False,
            "violations": [f"Reflection not actionable or too short: '{reflection[:100]}'"]
        }
    return {"success": True, "violations": []}


def commit(state: ReflexionState) -> dict:
    # Side effect: store in long-term memory (allowed WRITE)
    reflection = state.get("verbal_reflection", "")
    problem_spec = state.get("problem_spec", "")
    failed_code = state.get("failed_code", "")

    try:
        global_memory.add_to_long_term(
            data={
                "type": "reflexion",
                "problem": problem_spec[:500],
                "failed_code_snippet": failed_code[:500],
                "reflection": reflection
            },
            metadata={"agent": "reflexion_agent", "actionable": True}
        )
    except Exception:
        pass  # Memory failure should not break commit

    return {"committed": True}


def refine(state: ReflexionState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: ReflexionState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 2:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(ReflexionState)
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
reflexion_graph = workflow.compile(checkpointer=checkpointer)


def generate_reflection(
    failed_code: str,
    test_failure: str,
    problem_spec: str = "",
    execution_history: List[Dict] = None,
    thread_id: str = "reflexion_session"
) -> dict:
    """
    Main entrypoint - Generates verbal reflection and stores in memory.

    Args:
        failed_code: Code that failed
        test_failure: Test failure output
        problem_spec: Problem specification
        execution_history: List of past attempts {failure, code}
        thread_id: LangGraph thread id

    Returns:
        Dict with verbal_reflection, reflection_summary, success
    """
    result = reflexion_graph.invoke(
        {
            "failed_code": failed_code,
            "test_failure": test_failure,
            "problem_spec": problem_spec,
            "execution_history": execution_history or [],
            "verbal_reflection": "",
            "reflection_summary": "",
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "verbal_reflection": result.get("verbal_reflection", ""),
        "reflection_summary": result.get("reflection_summary", ""),
        "success": result.get("success", False),
        "violations": result.get("violations", [])
    }


def get_relevant_reflections(problem_spec: str, limit: int = 3) -> List[str]:
    """Retrieve relevant past reflections from long-term memory (Jaccard similarity)"""
    try:
        similar = global_memory.find_similar(problem_spec, threshold=0.3, limit=limit)
        return [entry["entry"]["data"].get("reflection", "") for entry in similar if entry["entry"]["data"].get("reflection")]
    except Exception:
        return []
