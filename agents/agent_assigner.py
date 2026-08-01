"""
Agent Assigner Agent - Deterministic task-to-agent routing and execution-plan builder.

This is Karpathy Meta-Agent #2. It converts validated task lists into a
DAG-aware execution plan without any LLM calls. The agent enforces Law 1
(Specialization), Law 2 (Permission Boundaries), Law 11 (Execution Grounding),
and Law 20 (Squad Specialization).
"""

from collections import defaultdict, deque
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.deterministic_validator import DeterministicValidatorEngine
from agents.domain_squads import SQUAD_PERMISSIONS


AGENT_ASSIGNER_PERMISSIONS = {
    "READ": ["tasks", "task_dependencies", "agent_capabilities"],
    "WRITE": ["assignments", "execution_plan", "routing_violations"],
    "NEVER": ["source_code", "credentials", "deployment", "database_access"],
    "HUMAN_CHECKPOINT": ["unknown_domain_task", "conflicting_agent_roles"],
}


class AgentAssignerState(TypedDict):
    """LangGraph state for deterministic agent assignment."""

    tasks: list[dict]
    assignments: dict[str, dict]
    execution_plan: list[dict]
    violations: list[str]
    retry_count: int
    success: bool


class AgentAssignerEngine:
    """Pure deterministic routing and DAG scheduling algorithms."""

    VALID_AGENT_NAMES = {
        "ProductManagerAgent",
        "ArchitectAgent",
        "CodeExecutorAgent",
        "AuthSquadAgent",
        "DatabaseSquadAgent",
        "APISquadAgent",
        "UISquadAgent",
        "TestRunnerAgent",
        "ReviewerAgent",
    }

    PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

    DOMAIN_KEYWORDS = {
        "auth": {
            "auth", "authentication", "security", "jwt", "login", "oauth",
            "password", "mfa", "totp", "session", "token",
        },
        "database": {
            "database", "schema", "migration", "model", "sql", "table",
            "postgres", "mysql", "index", "orm", "alembic",
        },
        "api": {
            "api", "route", "endpoint", "controller", "rest", "http",
            "pydantic", "request", "response", "fastapi",
        },
        "ui": {
            "ui", "frontend", "component", "layout", "view", "react",
            "css", "html", "dashboard", "page", "form",
        },
    }

    DOMAIN_AGENT = {
        "auth": "AuthSquadAgent",
        "database": "DatabaseSquadAgent",
        "api": "APISquadAgent",
        "ui": "UISquadAgent",
    }

    @classmethod
    def _task_text(cls, task: dict) -> str:
        """Build normalized searchable task text."""
        return " ".join(
            str(task.get(key, ""))
            for key in ("id", "title", "description", "type", "assigned_system")
        ).lower()

    @classmethod
    def detect_domain(cls, task: dict) -> str:
        """Detect a task domain from deterministic keyword evidence."""
        text = cls._task_text(task)
        scores = {
            domain: sum(1 for keyword in keywords if keyword in text)
            for domain, keywords in cls.DOMAIN_KEYWORDS.items()
        }
        best_domain, best_score = max(scores.items(), key=lambda item: item[1])
        return best_domain if best_score > 0 else "generic"

    @classmethod
    def classify_task(cls, task: dict) -> dict:
        """
        Classify one validated task into exactly one execution agent.

        Architecture and requirements/testing roles intentionally take
        precedence over domain implementation squads. Domain is still attached
        as metadata so downstream context managers can filter relevant context.
        """
        task_type = str(task.get("type", "")).lower()
        assigned_system = str(task.get("assigned_system", "")).lower()
        domain = cls.detect_domain(task)

        if task_type == "requirements" or assigned_system == "pm":
            agent = "ProductManagerAgent"
            rationale = "requirements/product ownership task"
        elif task_type == "architecture" or assigned_system == "architect":
            agent = "ArchitectAgent"
            rationale = "architecture/design task"
        elif task_type == "testing" or assigned_system == "tester":
            agent = "TestRunnerAgent"
            rationale = "testing/verification task"
        elif assigned_system == "reviewer":
            agent = "ReviewerAgent"
            rationale = "review task explicitly assigned to reviewer"
        elif domain in cls.DOMAIN_AGENT:
            agent = cls.DOMAIN_AGENT[domain]
            rationale = f"{domain} domain implementation task"
        else:
            agent = "CodeExecutorAgent"
            rationale = "generic implementation task"

        return {
            "task_id": task.get("id"),
            "assigned_agent": agent,
            "domain": domain,
            "task_type": task_type,
            "rationale": rationale,
        }

    @classmethod
    def validate_squad_scope(cls, task: dict, assignment: dict) -> list[str]:
        """Validate Law 20 scope for tasks routed to domain squads."""
        agent = assignment.get("assigned_agent")
        squad_key_by_agent = {
            "AuthSquadAgent": "auth_squad",
            "DatabaseSquadAgent": "db_squad",
            "APISquadAgent": "api_squad",
            "UISquadAgent": "ui_squad",
        }
        squad_key = squad_key_by_agent.get(agent)
        if not squad_key:
            return []

        permissions = SQUAD_PERMISSIONS[squad_key]
        text = cls._task_text(task)
        violations = []

        for keyword in permissions["FORBIDDEN_KEYWORDS"]:
            if keyword in text:
                violations.append(
                    f"Task '{task.get('id')}' routed to {agent} but contains forbidden keyword '{keyword}'."
                )

        if not any(keyword in text for keyword in permissions["ALLOWED_TYPES"]):
            violations.append(
                f"Task '{task.get('id')}' routed to {agent} without allowed domain evidence."
            )

        return violations

    @classmethod
    def build_assignments(cls, tasks: list[dict]) -> dict[str, dict]:
        """Build assignment dictionary keyed by task id."""
        assignments = {}
        for task in tasks:
            task_id = task.get("id")
            if task_id:
                assignments[task_id] = cls.classify_task(task)
        return assignments

    @classmethod
    def build_execution_plan(cls, tasks: list[dict], assignments: dict[str, dict]) -> tuple[list[dict], list[str]]:
        """Topologically schedule tasks and compute deterministic parallel groups."""
        violations = []
        task_by_id = {task.get("id"): task for task in tasks if isinstance(task, dict)}
        original_index = {task.get("id"): idx for idx, task in enumerate(tasks) if isinstance(task, dict)}

        indegree = {task_id: 0 for task_id in task_by_id}
        dependents = defaultdict(list)
        levels = {task_id: 0 for task_id in task_by_id}

        for task_id, task in task_by_id.items():
            for dep in task.get("dependencies", []):
                if dep not in task_by_id:
                    violations.append(f"Task '{task_id}' depends on unknown task id '{dep}'.")
                    continue
                indegree[task_id] += 1
                dependents[dep].append(task_id)

        queue = deque(sorted(
            [task_id for task_id, degree in indegree.items() if degree == 0],
            key=lambda tid: (cls.PRIORITY_RANK.get(task_by_id[tid].get("priority"), 99), original_index[tid]),
        ))
        ordered_ids = []

        while queue:
            task_id = queue.popleft()
            ordered_ids.append(task_id)
            for child in sorted(dependents[task_id], key=lambda tid: original_index[tid]):
                indegree[child] -= 1
                levels[child] = max(levels[child], levels[task_id] + 1)
                if indegree[child] == 0:
                    queue.append(child)
                    queue = deque(sorted(
                        queue,
                        key=lambda tid: (
                            levels[tid],
                            cls.PRIORITY_RANK.get(task_by_id[tid].get("priority"), 99),
                            original_index[tid],
                        ),
                    ))

        if len(ordered_ids) != len(task_by_id):
            unresolved = sorted(set(task_by_id) - set(ordered_ids))
            violations.append(f"Execution plan could not resolve cyclic/unreachable tasks: {unresolved}")

        plan = []
        for task_id in ordered_ids:
            task = task_by_id[task_id]
            assignment = assignments.get(task_id, {})
            plan.append({
                "task_id": task_id,
                "assigned_agent": assignment.get("assigned_agent"),
                "domain": assignment.get("domain", "generic"),
                "depends_on": list(task.get("dependencies", [])),
                "parallel_group": levels[task_id],
                "priority": task.get("priority"),
                "rationale": assignment.get("rationale", ""),
            })

        plan.sort(key=lambda item: (
            item["parallel_group"],
            cls.PRIORITY_RANK.get(item.get("priority"), 99),
            original_index[item["task_id"]],
        ))
        return plan, violations

    @classmethod
    def validate_assignments(cls, tasks: list[dict], assignments: dict[str, dict], execution_plan: list[dict]) -> list[str]:
        """Validate routing completeness, agent names, and domain boundaries."""
        violations = []
        task_ids = {task.get("id") for task in tasks if isinstance(task, dict)}
        assigned_ids = set(assignments)
        planned_ids = {item.get("task_id") for item in execution_plan}

        for missing in sorted(task_ids - assigned_ids):
            violations.append(f"Task '{missing}' has no assignment.")
        for missing in sorted(task_ids - planned_ids):
            violations.append(f"Task '{missing}' is missing from execution plan.")

        for task in tasks:
            if not isinstance(task, dict):
                continue
            assignment = assignments.get(task.get("id"), {})
            agent = assignment.get("assigned_agent")
            if agent not in cls.VALID_AGENT_NAMES:
                violations.append(f"Task '{task.get('id')}' assigned to invalid agent '{agent}'.")
            violations.extend(cls.validate_squad_scope(task, assignment))

        return violations


# Karpathy Loop Implementation

def propose(state: AgentAssignerState) -> dict:
    """Step 1: Propose - validate task structure before routing."""
    tasks = state.get("tasks", [])
    violations = DeterministicValidatorEngine.validate_tasks_structure(tasks)
    return {"violations": violations, "success": len(violations) == 0}


def execute(state: AgentAssignerState) -> dict:
    """Step 2: Execute - build assignments and DAG execution plan."""
    tasks = state.get("tasks", [])
    assignments = AgentAssignerEngine.build_assignments(tasks)
    execution_plan, plan_violations = AgentAssignerEngine.build_execution_plan(tasks, assignments)
    existing_violations = state.get("violations", [])
    return {
        "assignments": assignments,
        "execution_plan": execution_plan,
        "violations": existing_violations + plan_violations,
    }


def evaluate(state: AgentAssignerState) -> dict:
    """Step 3: Evaluate - verify complete valid routing and squad boundaries."""
    tasks = state.get("tasks", [])
    assignments = state.get("assignments", {})
    execution_plan = state.get("execution_plan", [])
    violations = state.get("violations", []) + AgentAssignerEngine.validate_assignments(
        tasks,
        assignments,
        execution_plan,
    )
    return {"violations": violations, "success": len(violations) == 0}


def commit(state: AgentAssignerState) -> dict:
    """Step 4: Commit - assignment plan is ready for downstream orchestration."""
    return {"committed": True}


def refine(state: AgentAssignerState) -> dict:
    """Step 5: Refine - deterministic assignment has no self-healing mutation."""
    return {"retry_count": state.get("retry_count", 0) + 1, "success": False}


def should_continue(state: AgentAssignerState) -> str:
    """Determine next step in Karpathy Loop."""
    if state.get("success", False):
        return "commit"
    if state.get("retry_count", 0) >= 1:
        return "escalate"
    return "refine"


workflow = StateGraph(AgentAssignerState)
workflow.add_node("propose", propose)
workflow.add_node("execute", execute)
workflow.add_node("evaluate", evaluate)
workflow.add_node("commit", commit)
workflow.add_node("refine", refine)

workflow.set_entry_point("propose")
workflow.add_edge("propose", "execute")
workflow.add_edge("execute", "evaluate")
workflow.add_conditional_edges(
    "evaluate",
    should_continue,
    {"commit": "commit", "refine": "refine", "escalate": END},
)
workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

checkpointer = MemorySaver()
agent_assigner_graph = workflow.compile(checkpointer=checkpointer)


def assign_tasks(tasks: list[dict], thread_id: str = "assigner_session") -> dict[str, Any]:
    """
    Assign validated tasks to specialized agents and build an execution plan.

    Args:
        tasks: Strictly validated task dictionaries.
        thread_id: Session thread ID for LangGraph checkpointer.

    Returns:
        Dict containing assignments, execution_plan, violations, and success.
    """
    result = agent_assigner_graph.invoke(
        {
            "tasks": tasks,
            "assignments": {},
            "execution_plan": [],
            "violations": [],
            "retry_count": 0,
            "success": False,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    return {
        "success": result.get("success", False),
        "assignments": result.get("assignments", {}),
        "execution_plan": result.get("execution_plan", []),
        "violations": result.get("violations", []),
    }
