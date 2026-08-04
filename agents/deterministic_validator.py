"""
Deterministic Validator Agent - Meta-Agent for Execution-Grounded Validation & Ground-Truth Verification
Implements Karpathy's 4th Engineering Pillar: Execution-Grounded Grader & Zero-LLM Self-Assessment.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Any

# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
DETERMINISTIC_VALIDATOR_PERMISSIONS = {
    "READ": ["target_output", "expected_schema", "invariant_rules"],
    "WRITE": ["validation_report", "quality_score", "breaches"],
    "NEVER": ["modify_target_output", "grant_exceptions", "bypass_schema"],
    "HUMAN_CHECKPOINT": ["fatal_schema_corruption"]
}


# State Definition
class DeterministicValidatorState(TypedDict):
    # Inputs
    target_output: Any
    required_keys: List[str]

    # Outputs
    validation_report: dict
    quality_score: float
    breaches: List[str]

    # Control
    retry_count: int
    success: bool


class DeterministicValidatorEngine:
    """Core zero-LLM deterministic validation algorithms."""

    VALID_TYPES = {"feature", "architecture", "requirements", "testing", "bugfix", "refactor"}
    VALID_PRIORITIES = {"high", "medium", "low"}
    VALID_EFFORTS = {"small", "medium", "large", "xlarge"}
    VALID_ASSIGNMENTS = {"pm", "architect", "developer", "reviewer", "tester"}
    REQUIRED_TASK_KEYS = {
        "id",
        "title",
        "description",
        "type",
        "priority",
        "dependencies",
        "estimated_effort",
        "assigned_system",
        "acceptance_criteria",
    }

    @staticmethod
    def validate_schema(data: Any, required_keys: List[str]) -> List[str]:
        """Verify top-level JSON schema keys deterministically without LLM assistance."""
        breaches = []

        if not isinstance(data, dict):
            return ["Target output is not a valid JSON dictionary."]

        for key in required_keys:
            if key not in data:
                breaches.append(f"Missing mandatory schema key: '{key}'")
            elif data[key] is None or data[key] == "":
                breaches.append(f"Mandatory schema key '{key}' is empty.")

        return breaches

    @classmethod
    def validate_tasks_structure(cls, tasks: List[dict]) -> List[str]:
        """Validate full task object structure and per-field invariants."""
        breaches = []
        if not isinstance(tasks, list):
            return ["Tasks property must be a list."]

        task_ids = []
        for i, task in enumerate(tasks, 1):
            if not isinstance(task, dict):
                breaches.append(f"Task {i} is not a valid dictionary.")
                continue

            missing = sorted(cls.REQUIRED_TASK_KEYS - set(task.keys()))
            for key in missing:
                breaches.append(f"Task {i} missing '{key}'.")

            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id.strip():
                breaches.append(f"Task {i} has invalid or empty 'id'.")
            else:
                task_ids.append(task_id)

            for key in ("title", "description"):
                if key in task and (not isinstance(task[key], str) or not task[key].strip()):
                    breaches.append(f"Task {i} has invalid or empty '{key}'.")

            if "type" in task and task.get("type") not in cls.VALID_TYPES:
                breaches.append(f"Task {i} has invalid type '{task.get('type')}'.")

            if "priority" in task and task.get("priority") not in cls.VALID_PRIORITIES:
                breaches.append(f"Task {i} has invalid priority '{task.get('priority')}'.")

            if "estimated_effort" in task and task.get("estimated_effort") not in cls.VALID_EFFORTS:
                breaches.append(f"Task {i} has invalid estimated_effort '{task.get('estimated_effort')}'.")

            if "assigned_system" in task and task.get("assigned_system") not in cls.VALID_ASSIGNMENTS:
                breaches.append(f"Task {i} has invalid assigned_system '{task.get('assigned_system')}'.")

            dependencies = task.get("dependencies")
            if "dependencies" in task and not isinstance(dependencies, list):
                breaches.append(f"Task {i} dependencies must be a list.")
            elif isinstance(dependencies, list):
                for dep in dependencies:
                    if not isinstance(dep, str) or not dep.strip():
                        breaches.append(f"Task {i} has invalid dependency value '{dep}'.")

            criteria = task.get("acceptance_criteria")
            if "acceptance_criteria" in task:
                if not isinstance(criteria, list) or not criteria:
                    breaches.append(f"Task {i} acceptance_criteria must be a non-empty list.")
                else:
                    for criterion in criteria:
                        if not isinstance(criterion, str) or not criterion.strip():
                            breaches.append(f"Task {i} has invalid acceptance criterion '{criterion}'.")

        duplicate_ids = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
        for task_id in duplicate_ids:
            breaches.append(f"Duplicate task id detected: '{task_id}'")

        breaches.extend(cls.validate_dependencies(tasks))
        return breaches

    @staticmethod
    def validate_dependencies(tasks: List[dict]) -> List[str]:
        """Validate dependency references and detect cycles using DFS."""
        if not isinstance(tasks, list):
            return []

        breaches = []
        task_ids = {task.get("id") for task in tasks if isinstance(task, dict) and isinstance(task.get("id"), str)}
        graph = {}

        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            dependencies = task.get("dependencies", [])
            if not isinstance(task_id, str) or not isinstance(dependencies, list):
                continue

            graph[task_id] = dependencies
            for dep in dependencies:
                if dep == task_id:
                    breaches.append(f"Task '{task_id}' depends on itself.")
                elif dep not in task_ids:
                    breaches.append(f"Task '{task_id}' depends on unknown task id '{dep}'.")

        visited = {}  # 0 absent, 1 visiting, 2 visited
        path = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in graph:
                    continue
                if visited.get(neighbor) == 1:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    breaches.append(f"Circular dependency detected: {' -> '.join(cycle)}")
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for task_id in graph:
            if visited.get(task_id, 0) == 0:
                dfs(task_id)

        return breaches

    @classmethod
    def validate_metadata_consistency(cls, target: Any) -> List[str]:
        """Validate that metadata counts match the physical task list."""
        if not isinstance(target, dict):
            return []

        tasks = target.get("tasks")
        metadata = target.get("metadata")
        if not isinstance(tasks, list) or not isinstance(metadata, dict):
            return []

        breaches = []
        expected_counts = {
            "total_tasks": len(tasks),
            "high_priority": sum(1 for task in tasks if isinstance(task, dict) and task.get("priority") == "high"),
            "medium_priority": sum(1 for task in tasks if isinstance(task, dict) and task.get("priority") == "medium"),
            "low_priority": sum(1 for task in tasks if isinstance(task, dict) and task.get("priority") == "low"),
        }

        for key, expected in expected_counts.items():
            if key in metadata and metadata.get(key) != expected:
                breaches.append(
                    f"Metadata '{key}' mismatch: expected {expected}, got {metadata.get(key)}."
                )

        if "estimated_total_effort" in metadata:
            effort = metadata.get("estimated_total_effort")
            if effort not in cls.VALID_EFFORTS and effort != "unknown":
                breaches.append(f"Metadata estimated_total_effort has invalid value '{effort}'.")

        return breaches

    @staticmethod
    def verify_execution_postcondition(postcondition: dict) -> List[str]:
        """VERIFY node (P2): check a *real* effect, not the agent's self-report.

        A postcondition is a cheap, non-LLM assertion declared by the agent at
        propose time. Supported kinds:
          - {"kind": "file_exists", "path": "..."}      -> file/dir must exist
          - {"kind": "command_ok", "command": "..."}    -> command exits 0
          - {"kind": "non_empty", "path": "..."}        -> file exists and >0 bytes
        Returns a list of breaches (empty == passed). This is the ground-truth
        channel that closes the 'silent partial completion' gap (Task 1).
        """
        import os
        import subprocess

        if not isinstance(postcondition, dict):
            return ["VERIFY postcondition must be a dict."]
        kind = postcondition.get("kind")
        if kind is None:
            return ["VERIFY postcondition missing 'kind'."]

        if kind == "file_exists":
            p = postcondition.get("path")
            if not isinstance(p, str) or not p.strip():
                return ["VERIFY file_exists requires a 'path' string."]
            if not os.path.exists(p):
                return [f"VERIFY failed: path does not exist: {p}"]
            return []

        if kind == "non_empty":
            p = postcondition.get("path")
            if not isinstance(p, str) or not p.strip():
                return ["VERIFY non_empty requires a 'path' string."]
            if not os.path.exists(p):
                return [f"VERIFY failed: path does not exist: {p}"]
            if os.path.getsize(p) == 0:
                return [f"VERIFY failed: path is empty: {p}"]
            return []

        if kind == "command_ok":
            cmd = postcondition.get("command")
            if not isinstance(cmd, str) or not cmd.strip():
                return ["VERIFY command_ok requires a 'command' string."]
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=60
                )
            except Exception as e:  # noqa: BLE001 - surface any exec error as a breach
                return [f"VERIFY command_ok error: {e}"]
            if r.returncode != 0:
                return [f"VERIFY failed: command exited {r.returncode}: {cmd}"]
            return []

        return [f"VERIFY unsupported postcondition kind: {kind}"]

    @staticmethod
    def calculate_quality_score(breaches: List[str]) -> float:
        """Calculate deterministic mathematical quality score between 0.0 and 1.0."""
        if not breaches:
            return 1.0
        penalty = len(breaches) * 0.1
        return round(max(0.0, 1.0 - penalty), 2)


# Karpathy Loop Implementation

def propose(state: DeterministicValidatorState) -> dict:
    """Step 1: Propose - Inspect target output and verify permission invariants."""
    target_output = state.get("target_output")

    if target_output is None:
        return {
            "breaches": ["Null target output provided."],
            "quality_score": 0.0,
            "success": False
        }

    return {
        "breaches": [],
        "quality_score": 1.0,
        "success": True
    }


def execute(state: DeterministicValidatorState) -> dict:
    """Step 2: Execute - Perform deterministic zero-LLM validation checks."""
    target = state.get("target_output", {})
    required_keys = state.get("required_keys", ["tasks", "metadata"])

    breaches = DeterministicValidatorEngine.validate_schema(target, required_keys)

    if isinstance(target, dict) and "tasks" in target:
        breaches.extend(DeterministicValidatorEngine.validate_tasks_structure(target["tasks"]))
        breaches.extend(DeterministicValidatorEngine.validate_metadata_consistency(target))

    score = DeterministicValidatorEngine.calculate_quality_score(breaches)

    return {
        "breaches": breaches,
        "quality_score": score,
        "validation_report": {
            "total_breaches": len(breaches),
            "score": score,
            "passed": len(breaches) == 0
        }
    }


def evaluate(state: DeterministicValidatorState) -> dict:
    """Step 3: Evaluate - Determine if quality score meets pass threshold (>= 0.8)."""
    score = state.get("quality_score", 0.0)
    breaches = state.get("breaches", [])

    success = score >= 0.8 and len(breaches) == 0
    return {"success": success}


def commit(state: DeterministicValidatorState) -> dict:
    """Step 4: Commit - Save validation report."""
    return {"committed": True}


def refine(state: DeterministicValidatorState) -> dict:
    """Step 5: Refine - Re-evaluate after correction attempt."""
    retry_count = state.get("retry_count", 0) + 1
    return {
        "retry_count": retry_count,
        "success": False
    }


def should_continue(state: DeterministicValidatorState) -> str:
    """Determine next step in Karpathy Loop."""
    if state.get("success", False):
        return "commit"
    elif state.get("retry_count", 0) >= 3:
        return "escalate"
    else:
        return "refine"


# Build LangGraph Workflow
workflow = StateGraph(DeterministicValidatorState)

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
    {
        "commit": "commit",
        "refine": "refine",
        "escalate": END
    }
)

workflow.add_edge("refine", "propose")
workflow.add_edge("commit", END)

checkpointer = MemorySaver()
deterministic_validator_graph = workflow.compile(checkpointer=checkpointer)


def validate_output(
    target_output: Any,
    required_keys: List[str] = None,
    thread_id: str = "validator_session"
) -> dict:
    """
    Validate output deterministically using zero-LLM hard assertions.

    Args:
        target_output: Output object / JSON to validate.
        required_keys: List of mandatory top-level keys.
        thread_id: Session thread ID for LangGraph checkpointer.

    Returns:
        Dict containing quality_score, breaches, validation_report, success.
    """
    if required_keys is None:
        required_keys = ["tasks", "metadata"]

    result = deterministic_validator_graph.invoke(
        {
            "target_output": target_output,
            "required_keys": required_keys,
            "validation_report": {},
            "quality_score": 0.0,
            "breaches": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )

    return {
        "quality_score": result.get("quality_score", 0.0),
        "breaches": result.get("breaches", []),
        "validation_report": result.get("validation_report", {}),
        "success": result.get("success", False)
    }
