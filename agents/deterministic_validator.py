"""
Deterministic Validator Agent - Meta-Agent for Execution-Grounded Validation & Ground-Truth Verification
Implements Karpathy's 4th Engineering Pillar: Execution-Grounded Grader & Zero-LLM Self-Assessment.
"""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from typing import TypedDict, List, Any

from kernel.karpathy_loop import build_karpathy_loop

logger = logging.getLogger(__name__)

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


# Karpathy Loop (shared factory; custom propose/evaluate, standard rest)

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


deterministic_validator_graph = build_karpathy_loop(
    DeterministicValidatorState,
    execute_fn=execute,
    propose_fn=propose,
    evaluate_fn=evaluate,
    retry_cap=3,
)


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


# ---------------------------------------------------------------------------
# P2 — Verified Closure toolkit (CONSTITUTION Article VI, Principle P2)
# ---------------------------------------------------------------------------
# "No WRITE agent returns to the orchestrator on its own report; every write edge
# terminates in a VERIFY node checking a postcondition declared at propose time,
# evaluated without an LLM."
#
# These helpers do NOT verify anything themselves and are NOT a second authority:
# the single verdict engine remains DeterministicValidatorEngine
# .verify_execution_postcondition, which every write agent calls directly.
# What they provide is the *effect surface*: an agent whose write lands only in
# graph state (a manifest, a memory entry, an assembled context) has nothing a
# zero-LLM verifier can inspect, so it first records the effect as a real file and
# then declares that file as its postcondition. Proof of effect, not permission.

VERIFIED_CLOSURE_FLAG = "GBAS_VERIFIED_CLOSURE"
EFFECT_LEDGER_DIR_ENV = "GBAS_EFFECT_LEDGER_DIR"
DEFAULT_EFFECT_LEDGER_DIR = "logs/effects"
_FALSE_VALUES = {"0", "false", "off", "no"}


def verified_closure_enabled() -> bool:
    """Reversibility switch (P2 rollout): set GBAS_VERIFIED_CLOSURE=0 to disable.

    When disabled, write agents skip recording/verifying effects and behave exactly
    as they did before P2 was wired. The AST governance invariant still holds because
    the VERIFY call remains in the source; only its runtime execution is gated.
    """
    return os.environ.get(VERIFIED_CLOSURE_FLAG, "1").strip().lower() not in _FALSE_VALUES


def effect_ledger_dir() -> Path:
    """Directory that holds per-write effect evidence files."""
    return Path(os.environ.get(EFFECT_LEDGER_DIR_ENV, DEFAULT_EFFECT_LEDGER_DIR))


def record_effect(agent: str, effect: dict) -> str:
    """Materialise a write effect as a file and return its path (the VERIFY target).

    This is the *write*, not the verdict. It never raises: if the write fails the
    path simply will not exist / will be empty, and the caller's
    verify_execution_postcondition call turns that into a breach — which is exactly
    the behaviour P2 requires (a failed write must never be self-reported as done).
    """
    effect_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}"
    target = effect_ledger_dir() / agent / f"{effect_id}.json"
    payload = {
        "agent": agent,
        "effect_id": effect_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "effect": effect,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, default=str), encoding="utf-8")
    except OSError as exc:
        logger.warning("P2 effect record failed for %s (%s): %s", agent, target, exc)
    return str(target)


def digest(text: str) -> str:
    """Stable content digest used inside effect records (zero-LLM, no side effects)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def apply_verify_verdict(result: dict, postcondition: dict, verify_breaches: List[str]) -> dict:
    """Attach a VERIFY verdict to an agent result and demote a false success.

    Demotion is one-way: a breach can only turn success True -> False. A passing
    postcondition never promotes a failed agent to success (P2 verifies effects,
    it does not grant permission).
    """
    result["postcondition"] = postcondition
    result["verify_breaches"] = list(verify_breaches or [])
    if verify_breaches:
        result["success"] = False
        existing = result.get("breaches")
        result["breaches"] = (list(existing) if isinstance(existing, list) else []) + list(verify_breaches)
    return result


def with_verified_closure(
    agent: str,
    output: dict,
    postcondition: dict,
    effect: dict | None = None,
    *,
    path: str | None = None,
) -> dict:
    """Close a P2 write edge: record the effect, VERIFY it, attach the verdict.

    Standard VERIFY-node block shared by every write agent. The write edge is closed
    by materialising the effect as a real file (`record_effect`) and pointing the
    postcondition at it, then letting the zero-LLM verifier decide — never the
    agent's own report. When the write produced a real artifact (`path` given, e.g.
    code_executor's output_dir), that file is verified directly instead of recording
    a new effect. Returns `output` with the verdict attached (one-way demotion).
    """
    postcondition["path"] = path if path is not None else record_effect(agent, effect or {})
    verify_breaches = DeterministicValidatorEngine.verify_execution_postcondition(postcondition)
    return apply_verify_verdict(output, postcondition, verify_breaches)

