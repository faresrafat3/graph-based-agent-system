"""
Graph Execution Orchestrator - DAG group fan-out/fan-in coordinator.

This agent turns the deterministic execution plan produced by Agent Assigner
into an executable, group-by-group graph lifecycle. It coordinates Resource &
Priority, optional Domain Dispatch, Progress Monitor, Integration, and Quality
Reviewer. It performs no LLM calls directly; LLM use only occurs inside domain
squads when domain dispatch is explicitly enabled.
"""

from collections import defaultdict
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.domain_dispatcher import dispatch_domain_tasks
from agents.integration_agent import integrate_artifacts
from agents.progress_monitor import monitor_progress
from agents.quality_reviewer import review_quality
from agents.resource_priority_agent import prioritize_resources


GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS = {
    "READ": ["tasks", "execution_plan", "global_context", "resource_budgets"],
    "WRITE": ["graph_execution_report", "completed_task_ids", "group_results"],
    "NEVER": ["credentials", "deployment", "production_environment", "provider_override"],
    "HUMAN_CHECKPOINT": ["blocked_graph_dependencies", "quality_gate_failure", "resource_exhaustion"],
}


class GraphExecutionOrchestratorState(TypedDict):
    """LangGraph state for the graph execution orchestrator."""

    tasks: list[dict]
    execution_plan: list[dict]
    global_context: str
    dispatch_domains: bool
    token_usage: dict
    api_rate_limits: dict
    timeout_seconds: int
    graph_execution_report: dict
    completed_task_ids: list[str]
    group_results: list[dict]
    dispatch_result: dict
    integration_result: dict
    progress_report: dict
    quality_review: dict
    violations: list[str]
    retry_count: int
    success: bool


class GraphExecutionOrchestratorEngine:
    """Deterministic DAG group orchestration helpers."""

    @staticmethod
    def group_execution_plan(execution_plan: list[dict]) -> dict[int, list[dict]]:
        """Group execution-plan items by deterministic parallel_group."""
        groups: dict[int, list[dict]] = defaultdict(list)
        for item in execution_plan or []:
            groups[int(item.get("parallel_group", 0) or 0)].append(item)
        return {
            group: sorted(items, key=lambda i: (i.get("priority", "medium"), i.get("task_id", "")))
            for group, items in sorted(groups.items())
        }

    @staticmethod
    def _task_acceptance_criteria(tasks: list[dict]) -> list[str]:
        """Flatten task acceptance criteria into one evidence list."""
        return [
            criterion
            for task in tasks or []
            for criterion in task.get("acceptance_criteria", [])
            if isinstance(criterion, str) and criterion.strip()
        ]

    @staticmethod
    def _empty_dispatch_result() -> dict[str, Any]:
        """Create an aggregate dispatch result container."""
        return {
            "success": True,
            "results": [],
            "parsed_outputs": {},
            "violations": [],
            "skipped_tasks": [],
            "blocked_tasks": [],
            "completed_task_ids": [],
        }

    @staticmethod
    def _merge_dispatch(aggregate: dict, partial: dict) -> dict:
        """Merge one domain-dispatch group result into the aggregate result."""
        aggregate["results"].extend(partial.get("results", []))
        aggregate["parsed_outputs"].update(partial.get("parsed_outputs", {}))
        aggregate["violations"].extend(partial.get("violations", []))
        aggregate["skipped_tasks"].extend(partial.get("skipped_tasks", []))
        aggregate["blocked_tasks"].extend(partial.get("blocked_tasks", []))
        aggregate["completed_task_ids"] = sorted(set(
            aggregate.get("completed_task_ids", []) + partial.get("completed_task_ids", [])
        ))
        aggregate["success"] = aggregate["success"] and partial.get("success", False)
        return aggregate

    @classmethod
    def execute_graph(
        cls,
        tasks: list[dict],
        execution_plan: list[dict],
        global_context: str = "",
        dispatch_domains: bool = False,
        token_usage: dict | None = None,
        api_rate_limits: dict | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Execute a DAG plan group-by-group and fan-in reports."""
        if not isinstance(execution_plan, list):
            return {
                "success": False,
                "violations": ["execution_plan must be a list."],
                "completed_task_ids": [],
            }
        if not isinstance(tasks, list):
            return {
                "success": False,
                "violations": ["tasks must be a list."],
                "completed_task_ids": [],
            }

        groups = cls.group_execution_plan(execution_plan)
        completed: set[str] = set()
        group_results = []
        agent_logs = []
        violations = []
        dispatch_aggregate = cls._empty_dispatch_result()

        for group_id, group_items in groups.items():
            resource_result = prioritize_resources(
                queue=group_items,
                completed_task_ids=sorted(completed),
                token_usage=token_usage or {},
                api_rate_limits=api_rate_limits or {},
                thread_id=f"graph_resource_group_{group_id}",
            )

            group_record = {
                "parallel_group": group_id,
                "resource_result": resource_result,
                "dispatched": False,
                "task_ids": [item.get("task_id") for item in group_items],
                "completed_after_group": [],
                "violations": [],
            }

            if resource_result.get("violations"):
                group_record["violations"].extend(resource_result["violations"])
                violations.extend(resource_result["violations"])
                for task_id in group_record["task_ids"]:
                    agent_logs.append({"task_id": task_id, "status": "failed", "duration_seconds": 0})
                group_results.append(group_record)
                break

            if resource_result.get("deferred_tasks"):
                message = (
                    f"Parallel group {group_id} has tasks deferred by incomplete dependencies: "
                    f"{resource_result['deferred_tasks']}"
                )
                group_record["violations"].append(message)
                violations.append(message)
                for task_id in resource_result["deferred_tasks"]:
                    agent_logs.append({"task_id": task_id, "status": "failed", "duration_seconds": 0})

            ready_ids = set(resource_result.get("queue_order", []))
            ready_items = [item for item in group_items if item.get("task_id") in ready_ids]

            if dispatch_domains:
                dispatch_result = dispatch_domain_tasks(
                    tasks=tasks,
                    execution_plan=ready_items,
                    global_context=global_context,
                    completed_task_ids=completed,
                )
                cls._merge_dispatch(dispatch_aggregate, dispatch_result)
                group_record["dispatched"] = True
                group_record["dispatch_result"] = dispatch_result
                group_record["violations"].extend(dispatch_result.get("violations", []))
                violations.extend(dispatch_result.get("violations", []))
                completed = set(dispatch_result.get("completed_task_ids", []))

                for result in dispatch_result.get("results", []):
                    agent_logs.append({
                        "task_id": result.get("task_id"),
                        "status": "completed" if result.get("success") else "failed",
                        "duration_seconds": 0,
                    })
            else:
                for item in ready_items:
                    task_id = item.get("task_id")
                    completed.add(task_id)
                    dispatch_aggregate["results"].append({
                        "task_id": task_id,
                        "assigned_agent": item.get("assigned_agent"),
                        "success": True,
                        "stage": "planned_only",
                        "violations": [],
                    })
                    agent_logs.append({"task_id": task_id, "status": "completed", "duration_seconds": 0})

            group_record["completed_after_group"] = sorted(completed)
            group_results.append(group_record)

        dispatch_aggregate["completed_task_ids"] = sorted(completed)
        if dispatch_aggregate["violations"]:
            dispatch_aggregate["success"] = False

        artifacts = list(dispatch_aggregate.get("parsed_outputs", {}).values())
        integration_result = integrate_artifacts(artifacts, thread_id="graph_execution_integration")
        if not integration_result.get("success"):
            violations.extend(integration_result.get("conflicts", []))

        progress_report = monitor_progress(
            execution_plan=execution_plan,
            agent_logs=agent_logs,
            timeout_seconds=timeout_seconds,
            thread_id="graph_execution_progress",
        )
        if not progress_report.get("success"):
            violations.extend(progress_report.get("violations", []))

        quality_review = review_quality(
            validation_reports=[],
            assignment_result={"success": True, "violations": []},
            dispatch_result=dispatch_aggregate,
            execution_results=[],
            acceptance_criteria=cls._task_acceptance_criteria(tasks),
            security_reports=[],
            thread_id="graph_execution_quality",
        )
        if not quality_review.get("approved"):
            violations.extend(quality_review.get("rejection_reasons", []))

        graph_success = (
            not violations
            and integration_result.get("success", False)
            and progress_report.get("success", False)
            and quality_review.get("approved", False)
        )

        report = {
            "success": graph_success,
            "dispatch_domains": dispatch_domains,
            "parallel_groups": len(groups),
            "completed_task_ids": sorted(completed),
            "group_results": group_results,
            "dispatch_result": dispatch_aggregate,
            "integration_result": integration_result,
            "progress_report": progress_report,
            "quality_review": quality_review,
            "violations": violations,
        }
        return report


# Karpathy Loop

def propose(state: GraphExecutionOrchestratorState) -> dict:
    """Step 1: Propose - verify execution-plan readiness."""
    if not isinstance(state.get("execution_plan", []), list):
        return {"violations": ["execution_plan must be a list."], "success": False}
    if not isinstance(state.get("tasks", []), list):
        return {"violations": ["tasks must be a list."], "success": False}
    return {"violations": [], "success": True}


def execute(state: GraphExecutionOrchestratorState) -> dict:
    """Step 2: Execute - process DAG groups and fan-in reports."""
    report = GraphExecutionOrchestratorEngine.execute_graph(
        tasks=state.get("tasks", []),
        execution_plan=state.get("execution_plan", []),
        global_context=state.get("global_context", ""),
        dispatch_domains=state.get("dispatch_domains", False),
        token_usage=state.get("token_usage", {}),
        api_rate_limits=state.get("api_rate_limits", {}),
        timeout_seconds=state.get("timeout_seconds", 300),
    )
    return {
        "graph_execution_report": report,
        "completed_task_ids": report.get("completed_task_ids", []),
        "group_results": report.get("group_results", []),
        "dispatch_result": report.get("dispatch_result", {}),
        "integration_result": report.get("integration_result", {}),
        "progress_report": report.get("progress_report", {}),
        "quality_review": report.get("quality_review", {}),
        "violations": report.get("violations", []),
        "success": report.get("success", False),
    }


def evaluate(state: GraphExecutionOrchestratorState) -> dict:
    """Step 3: Evaluate - graph execution succeeds only with no violations."""
    return {"success": bool(state.get("success", False)) and not state.get("violations", [])}


def commit(state: GraphExecutionOrchestratorState) -> dict:
    """Step 4: Commit - graph execution report is final."""
    return {"committed": True}


def refine(state: GraphExecutionOrchestratorState) -> dict:
    """Step 5: Refine - deterministic orchestrator does not auto-repair graph failures."""
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: GraphExecutionOrchestratorState) -> str:
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= 1:
        return "escalate"
    return "refine"


workflow = StateGraph(GraphExecutionOrchestratorState)
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

graph_execution_orchestrator_graph = workflow.compile(checkpointer=MemorySaver())


def orchestrate_graph_execution(
    tasks: list[dict],
    execution_plan: list[dict],
    global_context: str = "",
    dispatch_domains: bool = False,
    token_usage: dict | None = None,
    api_rate_limits: dict | None = None,
    timeout_seconds: int = 300,
    thread_id: str = "graph_execution_orchestrator_session",
) -> dict[str, Any]:
    """Run group-based DAG orchestration over an execution plan."""
    result = graph_execution_orchestrator_graph.invoke(
        {
            "tasks": tasks,
            "execution_plan": execution_plan,
            "global_context": global_context,
            "dispatch_domains": dispatch_domains,
            "token_usage": token_usage or {},
            "api_rate_limits": api_rate_limits or {},
            "timeout_seconds": timeout_seconds,
            "graph_execution_report": {},
            "completed_task_ids": [],
            "group_results": [],
            "dispatch_result": {},
            "integration_result": {},
            "progress_report": {},
            "quality_review": {},
            "violations": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    return {
        "success": result.get("success", False),
        "graph_execution_report": result.get("graph_execution_report", {}),
        "completed_task_ids": result.get("completed_task_ids", []),
        "group_results": result.get("group_results", []),
        "dispatch_result": result.get("dispatch_result", {}),
        "integration_result": result.get("integration_result", {}),
        "progress_report": result.get("progress_report", {}),
        "quality_review": result.get("quality_review", {}),
        "violations": result.get("violations", []),
    }
