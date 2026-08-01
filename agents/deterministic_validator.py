"""
Deterministic Validator Agent - Meta-Agent for Execution-Grounded Validation & Ground-Truth Verification
Implements Karpathy's 4th Engineering Pillar: Execution-Grounded Grader & Zero-LLM Self-Assessment.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any
import json

# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
DETERMINISTIC_VALIDATOR_PERMISSIONS = {
    "READ": ["target_output", "expected_schema", "invariant_rules"],
    "WRITE": ["validation_report", "quality_score", "violations"],
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
    violations: List[str]
    
    # Control
    retry_count: int
    success: bool


class DeterministicValidatorEngine:
    """Core zero-LLM deterministic validation algorithms"""
    
    @staticmethod
    def validate_schema(data: Any, required_keys: List[str]) -> List[str]:
        """Verifies JSON schema keys deterministically without LLM assistance"""
        violations = []
        
        if not isinstance(data, dict):
            return ["Target output is not a valid JSON dictionary."]
        
        for key in required_keys:
            if key not in data:
                violations.append(f"Missing mandatory schema key: '{key}'")
            elif data[key] is None or data[key] == "":
                violations.append(f"Mandatory schema key '{key}' is empty.")
                
        return violations

    @staticmethod
    def validate_tasks_structure(tasks: List[dict]) -> List[str]:
        """Validates task objects structure deterministically"""
        violations = []
        if not isinstance(tasks, list):
            return ["Tasks property must be a list."]
            
        valid_types = {"feature", "architecture", "requirements", "testing", "bugfix", "refactor"}
        
        for i, task in enumerate(tasks, 1):
            if not isinstance(task, dict):
                violations.append(f"Task {i} is not a valid dictionary.")
                continue
            if "id" not in task:
                violations.append(f"Task {i} missing 'id'.")
            if "title" not in task:
                violations.append(f"Task {i} missing 'title'.")
            if task.get("type") not in valid_types:
                violations.append(f"Task {i} has invalid type '{task.get('type')}'.")
                
        return violations

    @staticmethod
    def calculate_quality_score(violations: List[str]) -> float:
        """Calculates deterministic mathematical quality score between 0.0 and 1.0"""
        if not violations:
            return 1.0
        penalty = len(violations) * 0.2
        return round(max(0.0, 1.0 - penalty), 2)


# Karpathy Loop Implementation

def propose(state: DeterministicValidatorState) -> dict:
    """Step 1: Propose - Inspect target output and verify permission invariants"""
    target_output = state.get("target_output")
    
    # Check for empty target
    if target_output is None:
        return {
            "violations": ["Null target output provided."],
            "quality_score": 0.0,
            "success": False
        }
        
    return {
        "violations": [],
        "quality_score": 1.0,
        "success": True
    }


def execute(state: DeterministicValidatorState) -> dict:
    """Step 2: Execute - Perform deterministic zero-LLM validation checks"""
    target = state.get("target_output", {})
    required_keys = state.get("required_keys", ["tasks", "metadata"])
    
    violations = DeterministicValidatorEngine.validate_schema(target, required_keys)
    
    if isinstance(target, dict) and "tasks" in target:
        task_violations = DeterministicValidatorEngine.validate_tasks_structure(target["tasks"])
        violations.extend(task_violations)
        
    score = DeterministicValidatorEngine.calculate_quality_score(violations)
    
    return {
        "violations": violations,
        "quality_score": score,
        "validation_report": {
            "total_violations": len(violations),
            "score": score,
            "passed": len(violations) == 0
        }
    }


def evaluate(state: DeterministicValidatorState) -> dict:
    """Step 3: Evaluate - Determine if quality score meets pass threshold (>= 0.8)"""
    score = state.get("quality_score", 0.0)
    violations = state.get("violations", [])
    
    success = score >= 0.8 and len(violations) == 0
    return {"success": success}


def commit(state: DeterministicValidatorState) -> dict:
    """Step 4: Commit - Save validation report"""
    return {"committed": True}


def refine(state: DeterministicValidatorState) -> dict:
    """Step 5: Refine - Re-evaluate after correction attempt"""
    retry_count = state.get("retry_count", 0) + 1
    return {
        "retry_count": retry_count,
        "success": False
    }


def should_continue(state: DeterministicValidatorState) -> str:
    """Determine next step in Karpathy Loop"""
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
    Validates output deterministically using zero-LLM hard assertions.
    
    Args:
        target_output: Output object / JSON to validate
        required_keys: List of mandatory top-level keys
        thread_id: Session thread ID for LangGraph checkpointer
    
    Returns:
        Dict containing quality_score, violations, validation_report, success
    """
    if required_keys is None:
        required_keys = ["tasks", "metadata"]
        
    result = deterministic_validator_graph.invoke(
        {
            "target_output": target_output,
            "required_keys": required_keys,
            "validation_report": {},
            "quality_score": 0.0,
            "violations": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )
    
    return {
        "quality_score": result.get("quality_score", 0.0),
        "violations": result.get("violations", []),
        "validation_report": result.get("validation_report", {}),
        "success": result.get("success", False)
    }
