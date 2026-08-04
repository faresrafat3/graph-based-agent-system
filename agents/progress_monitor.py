"""
Progress Monitor Agent - Deterministic graph execution health monitor.

Karpathy Meta-Agent #3. Tracks task state, completion progress, failures, and
stalls from execution-plan items and agent logs. It performs no LLM calls.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


PROGRESS_MONITOR_PERMISSIONS = {
    "READ": ["active_graph_state", "agent_logs", "timeouts", "execution_plan"],
    "WRITE": ["progress_metrics", "stalled_task_flags", "health_report"],
    "NEVER": ["modify_code", "override_permissions", "force_success"],
    "HUMAN_CHECKPOINT": ["unresponsive_agent_execution", "system_timeout"],
}


class ProgressMonitorState(TypedDict):
    """LangGraph state for Progress Monitor Agent."""

    execution_plan: list[dict]
    agent_logs: list[dict]
    timeout_seconds: int
    progress_metrics: dict
    stalled_tasks: list[str]
    failed_tasks: list[str]
    breaches: list[str]
    retry_count: int
    success: bool


class ProgressMonitorEngine:
    """Pure deterministic progress-analysis methods."""

    TERMINAL_SUCCESS = {"completed", "success", "passed"}
    TERMINAL_FAILURE = {"failed", "error", "timeout"}
    ACTIVE = {"running", "started", "in_progress"}

    @staticmethod
    def latest_logs_by_task(agent_logs: list[dict]) -> dict[str, dict]:
        """Return the latest log per task by timestamp/order."""
        latest = {}
        for index, log in enumerate(agent_logs or []):
            task_id = log.get("task_id")
            if not task_id:
                continue
            sortable = log.get("timestamp", index)
            previous = latest.get(task_id)
            if previous is None or sortable >= previous.get("_sortable", -1):
                latest[task_id] = {**log, "_sortable": sortable}
        return latest

    @classmethod
    def analyze(cls, execution_plan: list[dict], agent_logs: list[dict], timeout_seconds: int) -> dict[str, Any]:
        """Compute progress metrics, stalled tasks, failures, and breaches."""
        latest = cls.latest_logs_by_task(agent_logs)
        planned_ids = [item.get("task_id") for item in execution_plan if item.get("task_id")]
        planned_set = set(planned_ids)

        completed = []
        running = []
        failed = []
        pending = []
        stalled = []
        breaches = []

        for task_id in planned_ids:
            log = latest.get(task_id)
            if not log:
                pending.append(task_id)
                continue

            status = str(log.get("status", "unknown")).lower()
            duration = float(log.get("duration_seconds", 0) or 0)
            if status in cls.TERMINAL_SUCCESS:
                completed.append(task_id)
            elif status in cls.TERMINAL_FAILURE:
                failed.append(task_id)
                breaches.append(f"Task '{task_id}' failed with status '{status}'.")
            elif status in cls.ACTIVE:
                running.append(task_id)
                if duration > timeout_seconds:
                    stalled.append(task_id)
                    breaches.append(
                        f"Task '{task_id}' stalled after {duration}s (timeout {timeout_seconds}s)."
                    )
            else:
                pending.append(task_id)

        unknown_log_tasks = sorted(set(latest) - planned_set)
        for task_id in unknown_log_tasks:
            breaches.append(f"Agent log references unknown task id '{task_id}'.")

        total = len(planned_ids)
        completion_rate = round(len(completed) / total, 4) if total else 1.0
        metrics = {
            "total_tasks": total,
            "completed_tasks": len(completed),
            "running_tasks": len(running),
            "pending_tasks": len(pending),
            "failed_tasks": len(failed),
            "stalled_tasks": len(stalled),
            "completion_rate": completion_rate,
        }

        return {
            "progress_metrics": metrics,
            "stalled_tasks": stalled,
            "failed_tasks": failed,
            "breaches": breaches,
            "success": len(breaches) == 0,
        }


# Karpathy Loop

def propose(state: ProgressMonitorState) -> dict:
    """Step 1: Propose - verify there is an execution plan to monitor."""
    plan = state.get("execution_plan", [])
    if not isinstance(plan, list):
        return {"breaches": ["execution_plan must be a list."], "success": False}
    return {"breaches": [], "success": True}


def execute(state: ProgressMonitorState) -> dict:
    """Step 2: Execute - compute deterministic progress metrics."""
    return ProgressMonitorEngine.analyze(
        execution_plan=state.get("execution_plan", []),
        agent_logs=state.get("agent_logs", []),
        timeout_seconds=state.get("timeout_seconds", 300),
    )


def evaluate(state: ProgressMonitorState) -> dict:
    """Step 3: Evaluate - fail on stalls, failures, or unknown log references."""
    return {"success": len(state.get("breaches", [])) == 0}


def commit(state: ProgressMonitorState) -> dict:
    """Step 4: Commit - health report is ready."""
    return {"committed": True}


def refine(state: ProgressMonitorState) -> dict:
    """Step 5: Refine - deterministic monitor has no automatic repair."""
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: ProgressMonitorState) -> str:
    """Route monitor lifecycle."""
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= 1:
        return "escalate"
    return "refine"


workflow = StateGraph(ProgressMonitorState)
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

progress_monitor_graph = workflow.compile(checkpointer=MemorySaver())


def monitor_progress(
    execution_plan: list[dict],
    agent_logs: list[dict] | None = None,
    timeout_seconds: int = 300,
    thread_id: str = "progress_monitor_session",
) -> dict[str, Any]:
    """Monitor execution-plan health deterministically."""
    result = progress_monitor_graph.invoke(
        {
            "execution_plan": execution_plan,
            "agent_logs": agent_logs or [],
            "timeout_seconds": timeout_seconds,
            "progress_metrics": {},
            "stalled_tasks": [],
            "failed_tasks": [],
            "breaches": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "success": result.get("success", False),
        "progress_metrics": result.get("progress_metrics", {}),
        "stalled_tasks": result.get("stalled_tasks", []),
        "failed_tasks": result.get("failed_tasks", []),
        "breaches": result.get("breaches", []),
    }
