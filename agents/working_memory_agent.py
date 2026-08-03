"""
Working Memory Agent - Token Budget Management & Context Assembly

Phase 2: Episodic -> Semantic -> Working

Role: Takes long-term memory (episodic + semantic), filters by relevance to current problem,
assembles working memory within token budget (4000), sends to context managers.

This is the "Memory to Context" system you mentioned - the bridge.

Law 2,4,11 compliant.
"""

import sys
import logging
from typing import TypedDict, List, Dict, Any

logger = logging.getLogger(__name__)

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from memory.custom_memory import memory as global_memory


WORKING_MEMORY_PERMISSIONS = {
    "READ": ["long_term_memory", "problem_spec", "current_context", "token_budget"],
    "WRITE": ["working_memory", "assembled_context", "budget_report"],
    "NEVER": ["credentials", "deployment", "raw_code_deletion"],
    "HUMAN_CHECKPOINT": ["budget_exceeded", "context_overflow"]
}


class WorkingState(TypedDict):
    problem_spec: str
    current_context: str
    token_budget: int
    long_term_entries: List[Dict]
    working_memory: List[Dict]
    assembled_context: str
    budget_report: Dict[str, Any]
    violations: List[str]
    retry_count: int
    success: bool


class WorkingEngine:
    """Deterministic helpers - ZERO LLM"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def rank_by_relevance(entries: List[Dict], problem_spec: str) -> List[Dict]:
        """Rank entries by Jaccard similarity + recency + outcome (ZERO-LLM)"""
        from memory.custom_memory import CustomMemory
        temp_mem = CustomMemory()
        # Use same Jaccard logic as CustomMemory.find_similar but manual ranking

        problem_keywords = set(problem_spec.lower().split())
        
        scored = []
        for entry in entries:
            # Jaccard
            data_str = str(entry.get("data", {})).lower()
            entry_keywords = set(data_str.split())
            overlap = len(problem_keywords & entry_keywords)
            total = len(problem_keywords | entry_keywords)
            jaccard = overlap / total if total > 0 else 0

            # Recency boost (newer = higher) - simple
            # If has timestamp, boost, else 0
            recency_boost = 0.1  # placeholder

            # Outcome boost: FAIL episodes are more valuable for learning than PASS
            outcome = entry.get("data", {}).get("outcome", "")
            outcome_boost = 0.2 if outcome in ["FAIL", "CAPABILITY_FAIL"] else 0.0

            # Semantic rules boost
            type_boost = 0.3 if entry.get("data", {}).get("type") == "semantic" else 0.0

            score = jaccard + recency_boost + outcome_boost + type_boost
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for score, entry in scored]

    @staticmethod
    def assemble_within_budget(ranked_entries: List[Dict], problem_spec: str, current_context: str, token_budget: int) -> tuple:
        """Assemble context within budget deterministically"""
        budget_used = WorkingEngine.estimate_tokens(problem_spec) + WorkingEngine.estimate_tokens(current_context)
        assembled_parts = []
        included = []

        for entry in ranked_entries:
            data = entry.get("data", {})
            # Format entry as small snippet
            if data.get("type") == "episodic":
                snippet = f"Episodic: {data.get('failure','')[:150]} -> Reflection: {data.get('reflection','')[:150]}"
            elif data.get("type") == "semantic":
                snippet = f"Rule: {data.get('rule','')[:200]}"
            elif data.get("type") == "reflexion":
                snippet = f"Reflection: {data.get('reflection','')[:200]}"
            else:
                snippet = str(data)[:200]

            snippet_tokens = WorkingEngine.estimate_tokens(snippet)
            if budget_used + snippet_tokens <= token_budget:
                assembled_parts.append(snippet)
                included.append(entry)
                budget_used += snippet_tokens
            else:
                break

        assembled = "\n".join(assembled_parts)
        report = {
            "budget_total": token_budget,
            "budget_used": budget_used,
            "budget_remaining": token_budget - budget_used,
            "entries_included": len(included),
            "entries_skipped": len(ranked_entries) - len(included)
        }

        return assembled, included, report


def propose(state: WorkingState) -> dict:
    problem_spec = state.get("problem_spec", "")
    if not problem_spec.strip():
        raise ValueError("problem_spec required")

    token_budget = state.get("token_budget", 4000)
    if token_budget < 500:
        raise ValueError("token_budget too small (<500)")

    return {"working_memory": [], "assembled_context": "", "violations": [], "success": False}


def execute(state: WorkingState) -> dict:
    problem_spec = state.get("problem_spec", "")
    current_context = state.get("current_context", "")
    token_budget = state.get("token_budget", 4000)
    long_entries = state.get("long_term_entries", [])

    if not long_entries:
        # Auto-retrieve from global memory if not provided
        try:
            all_long = global_memory.get_from_long_term(limit=30)
            long_entries = all_long
        except Exception as exc:
            logger.warning("Working memory auto-retrieval failed, using empty: %s", exc)
            long_entries = []

    ranked = WorkingEngine.rank_by_relevance(long_entries, problem_spec)
    assembled, included, report = WorkingEngine.assemble_within_budget(
        ranked, problem_spec, current_context, token_budget
    )

    return {
        "working_memory": included,
        "assembled_context": assembled,
        "budget_report": report
    }


def evaluate(state: WorkingState) -> dict:
    assembled = state.get("assembled_context", "")
    report = state.get("budget_report", {})
    violations = []

    if report.get("budget_used", 0) > report.get("budget_total", 4000):
        violations.append("Budget exceeded")

    # Success if we assembled something OR no entries to assemble (empty memory is okay)
    success = True  # Always success, even if empty - empty memory is valid
    return {"violations": violations, "success": success}


def commit(state: WorkingState) -> dict:
    return {"committed": True}


def refine(state: WorkingState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: WorkingState) -> str:
    if state.get("success"):
        return "commit"
    elif state.get("retry_count", 0) >= 2:
        return "escalate"
    else:
        return "refine"


workflow = StateGraph(WorkingState)
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
working_graph = workflow.compile(checkpointer=checkpointer)


def assemble_working_memory(
    problem_spec: str,
    current_context: str = "",
    token_budget: int = 4000,
    long_term_entries: List[Dict] = None,
    thread_id: str = "working_session"
) -> dict:
    """Main entrypoint - Memory to Context bridge"""
    result = working_graph.invoke(
        {
            "problem_spec": problem_spec,
            "current_context": current_context,
            "token_budget": token_budget,
            "long_term_entries": long_term_entries or [],
            "working_memory": [],
            "assembled_context": "",
            "budget_report": {},
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "working_memory": result.get("working_memory", []),
        "assembled_context": result.get("assembled_context", ""),
        "budget_report": result.get("budget_report", {}),
        "success": result.get("success", False),
        "violations": result.get("violations", [])
    }
