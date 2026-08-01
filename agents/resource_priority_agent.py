"""
Resource & Priority Agent - Deterministic queue ordering and budget guard.

Karpathy Meta-Agent #7. Reorders tasks by priority/dependency readiness and
blocks work when request/token budgets are exhausted. No LLM calls.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


RESOURCE_PRIORITY_PERMISSIONS = {
    "READ": ["token_usage", "api_rate_limits", "queue_priority", "execution_plan"],
    "WRITE": ["rate_limit_actions", "queue_order", "deferred_tasks"],
    "NEVER": ["exceed_hard_budget", "disable_rate_limiters"],
    "HUMAN_CHECKPOINT": ["request_budget_exhaustion"],
}


class ResourcePriorityState(TypedDict):
    queue: list[dict]
    completed_task_ids: list[str]
    token_usage: dict
    api_rate_limits: dict
    queue_order: list[str]
    deferred_tasks: list[str]
    rate_limit_actions: list[str]
    violations: list[str]
    retry_count: int
    success: bool


class ResourcePriorityEngine:
    """Deterministic resource and queue management helpers."""

    PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

    @classmethod
    def prioritize(
        cls,
        queue: list[dict],
        completed_task_ids: set[str],
        token_usage: dict,
        api_rate_limits: dict,
    ) -> dict[str, Any]:
        """Order ready tasks and defer blocked or over-budget tasks."""
        violations = []
        actions = []
        deferred = []

        token_budget = int(token_usage.get("budget", token_usage.get("limit", 0)) or 0)
        tokens_used = int(token_usage.get("used", 0) or 0)
        remaining_requests = int(api_rate_limits.get("remaining", 1) or 0)

        if token_budget and tokens_used >= token_budget:
            actions.append("token_budget_exhausted")
            violations.append("Token budget exhausted; queue execution must pause.")
        if remaining_requests <= 0:
            actions.append("api_rate_limit_exhausted")
            violations.append("API request budget exhausted; queue execution must pause.")

        ready = []
        for index, item in enumerate(queue or []):
            task_id = item.get("task_id") or item.get("id")
            deps = set(item.get("depends_on", item.get("dependencies", [])) or [])
            if not task_id:
                violations.append(f"Queue item {index + 1} missing task id.")
                continue
            if deps - completed_task_ids:
                deferred.append(task_id)
                continue
            ready.append((
                cls.PRIORITY_RANK.get(item.get("priority", "medium"), 99),
                item.get("parallel_group", 0),
                index,
                task_id,
            ))

        ready.sort()
        queue_order = [] if violations else [item[-1] for item in ready]
        if violations and ready:
            deferred.extend(item[-1] for item in ready)

        return {
            "queue_order": queue_order,
            "deferred_tasks": sorted(set(deferred)),
            "rate_limit_actions": actions,
            "violations": violations,
            "success": len(violations) == 0,
        }


# Karpathy Loop

def propose(state: ResourcePriorityState) -> dict:
    if not isinstance(state.get("queue", []), list):
        return {"violations": ["queue must be a list."], "success": False}
    return {"violations": [], "success": True}


def execute(state: ResourcePriorityState) -> dict:
    return ResourcePriorityEngine.prioritize(
        queue=state.get("queue", []),
        completed_task_ids=set(state.get("completed_task_ids", [])),
        token_usage=state.get("token_usage", {}),
        api_rate_limits=state.get("api_rate_limits", {}),
    )


def evaluate(state: ResourcePriorityState) -> dict:
    return {"success": len(state.get("violations", [])) == 0}


def commit(state: ResourcePriorityState) -> dict:
    return {"committed": True}


def refine(state: ResourcePriorityState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: ResourcePriorityState) -> str:
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= 1:
        return "escalate"
    return "refine"


workflow = StateGraph(ResourcePriorityState)
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

resource_priority_graph = workflow.compile(checkpointer=MemorySaver())


def prioritize_resources(
    queue: list[dict],
    completed_task_ids: list[str] | None = None,
    token_usage: dict | None = None,
    api_rate_limits: dict | None = None,
    thread_id: str = "resource_priority_session",
) -> dict[str, Any]:
    """Order ready tasks under deterministic budget constraints."""
    result = resource_priority_graph.invoke(
        {
            "queue": queue,
            "completed_task_ids": completed_task_ids or [],
            "token_usage": token_usage or {},
            "api_rate_limits": api_rate_limits or {},
            "queue_order": [],
            "deferred_tasks": [],
            "rate_limit_actions": [],
            "violations": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "queue_order": result.get("queue_order", []),
        "deferred_tasks": result.get("deferred_tasks", []),
        "rate_limit_actions": result.get("rate_limit_actions", []),
        "violations": result.get("violations", []),
    }
