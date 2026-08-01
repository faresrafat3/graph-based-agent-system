"""
Domain Dispatcher Agent - Executes DAG plan items routed to domain squads.

The dispatcher consumes the deterministic execution plan produced by Agent
Assigner and invokes only implemented domain squad agents. It is intentionally
conservative: non-domain agents are skipped, dependency order is enforced, raw
LLM squad responses are parsed through the shared JSON parser, and parse errors
surface as explicit violations.
"""

from typing import Any

from agents.domain_squads import (
    APISquadAgent,
    AuthSquadAgent,
    DatabaseSquadAgent,
    UISquadAgent,
)
from tools.json_output_parser import parse_json_object_response


DOMAIN_DISPATCHER_PERMISSIONS = {
    "READ": ["tasks", "execution_plan", "global_context", "completed_task_ids"],
    "WRITE": ["dispatch_results", "parsed_outputs", "dispatch_violations"],
    "NEVER": ["deployment", "credentials", "production_environment"],
    "HUMAN_CHECKPOINT": ["blocked_dependencies", "unsupported_agent", "squad_boundary_violation"],
}


DOMAIN_AGENT_METHODS = {
    "AuthSquadAgent": (AuthSquadAgent, "execute_auth_task"),
    "DatabaseSquadAgent": (DatabaseSquadAgent, "execute_db_task"),
    "APISquadAgent": (APISquadAgent, "execute_api_task"),
    "UISquadAgent": (UISquadAgent, "execute_ui_task"),
}

DOMAIN_OUTPUT_REQUIRED_KEYS = ["filename", "code", "test_filename", "test_code"]


class DomainDispatcherEngine:
    """Deterministic dispatch helpers for domain-squad execution."""

    @staticmethod
    def _task_by_id(tasks: list[dict]) -> dict[str, dict]:
        """Index task dictionaries by id."""
        return {
            task.get("id"): task
            for task in tasks
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }

    @staticmethod
    def _sorted_plan(execution_plan: list[dict]) -> list[dict]:
        """Sort plan deterministically by parallel group and task id."""
        return sorted(
            execution_plan,
            key=lambda item: (
                item.get("parallel_group", 0),
                item.get("priority", "medium"),
                item.get("task_id", ""),
            ),
        )

    @staticmethod
    def _blocked_dependencies(plan_item: dict, completed_task_ids: set[str]) -> list[str]:
        """Return dependencies that are not completed yet."""
        return [
            dep for dep in plan_item.get("depends_on", [])
            if dep not in completed_task_ids
        ]

    @classmethod
    def dispatch(
        cls,
        tasks: list[dict],
        execution_plan: list[dict],
        global_context: str = "",
        completed_task_ids: set[str] | None = None,
        max_tasks: int | None = None,
    ) -> dict[str, Any]:
        """Dispatch domain-squad tasks from an execution plan."""
        task_by_id = cls._task_by_id(tasks)
        completed = set(completed_task_ids or set())
        results = []
        parsed_outputs = {}
        violations = []
        skipped_tasks = []
        blocked_tasks = []
        dispatched_count = 0

        for plan_item in cls._sorted_plan(execution_plan):
            task_id = plan_item.get("task_id")
            assigned_agent = plan_item.get("assigned_agent")
            task = task_by_id.get(task_id)

            if not task:
                message = f"Execution plan references unknown task id '{task_id}'."
                violations.append(message)
                results.append({
                    "task_id": task_id,
                    "assigned_agent": assigned_agent,
                    "success": False,
                    "stage": "lookup",
                    "violations": [message],
                })
                continue

            blocked = cls._blocked_dependencies(plan_item, completed)
            if blocked:
                message = f"Task '{task_id}' blocked by incomplete dependencies: {blocked}"
                violations.append(message)
                blocked_tasks.append(task_id)
                results.append({
                    "task_id": task_id,
                    "assigned_agent": assigned_agent,
                    "success": False,
                    "stage": "dependency_blocked",
                    "violations": [message],
                })
                continue

            if assigned_agent not in DOMAIN_AGENT_METHODS:
                skipped_tasks.append(task_id)
                completed.add(task_id)
                results.append({
                    "task_id": task_id,
                    "assigned_agent": assigned_agent,
                    "success": True,
                    "stage": "skipped_non_domain_agent",
                    "violations": [],
                })
                continue

            if max_tasks is not None and dispatched_count >= max_tasks:
                skipped_tasks.append(task_id)
                results.append({
                    "task_id": task_id,
                    "assigned_agent": assigned_agent,
                    "success": True,
                    "stage": "skipped_max_tasks",
                    "violations": [],
                })
                continue

            agent_cls, method_name = DOMAIN_AGENT_METHODS[assigned_agent]
            agent = agent_cls()

            try:
                raw_result = getattr(agent, method_name)(task, global_context=global_context)
            except Exception as exc:
                message = f"Task '{task_id}' dispatch failed in {assigned_agent}: {exc}"
                violations.append(message)
                results.append({
                    "task_id": task_id,
                    "assigned_agent": assigned_agent,
                    "success": False,
                    "stage": "squad_execution",
                    "violations": [message],
                })
                continue

            parsed = parse_json_object_response(
                raw_result.get("response", ""),
                required_keys=DOMAIN_OUTPUT_REQUIRED_KEYS,
            )
            result_success = bool(raw_result.get("success")) and parsed["success"]
            if result_success:
                completed.add(task_id)
                parsed_outputs[task_id] = parsed["data"]
            else:
                violations.extend([
                    f"Task '{task_id}' output parse violation: {violation}"
                    for violation in parsed["violations"]
                ])

            results.append({
                "task_id": task_id,
                "assigned_agent": assigned_agent,
                "domain": plan_item.get("domain"),
                "success": result_success,
                "stage": "domain_squad_execution",
                "raw_result": raw_result,
                "parsed_output": parsed["data"],
                "parse_success": parsed["success"],
                "violations": parsed["violations"],
            })
            dispatched_count += 1

        return {
            "success": len(violations) == 0,
            "results": results,
            "parsed_outputs": parsed_outputs,
            "violations": violations,
            "skipped_tasks": skipped_tasks,
            "blocked_tasks": blocked_tasks,
            "completed_task_ids": sorted(completed),
        }


def dispatch_domain_tasks(
    tasks: list[dict],
    execution_plan: list[dict],
    global_context: str = "",
    completed_task_ids: set[str] | None = None,
    max_tasks: int | None = None,
) -> dict[str, Any]:
    """
    Execute domain-squad items from a deterministic execution plan.

    Non-domain agents are reported as skipped/satisfied so the dispatcher can be
    used incrementally before all planned software agents are implemented.
    """
    return DomainDispatcherEngine.dispatch(
        tasks=tasks,
        execution_plan=execution_plan,
        global_context=global_context,
        completed_task_ids=completed_task_ids,
        max_tasks=max_tasks,
    )
