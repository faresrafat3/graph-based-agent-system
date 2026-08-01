"""
Surgical Refiner Agent - Meta-Agent for Targeted Refinement & Surgical Corrections
Implements Karpathy's 3rd Engineering Pillar: Surgical Changes & Pinpoint Self-Correction.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any

# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
SURGICAL_REFINER_PERMISSIONS = {
    "READ": ["validation_report", "violations", "previous_output"],
    "WRITE": ["surgical_feedback", "pinpoint_corrections"],
    "NEVER": ["regenerate_entire_system", "override_validation_report"],
    "HUMAN_CHECKPOINT": ["persistent_unsolvable_violations"]
}


# State Definition
class SurgicalRefinerState(TypedDict):
    # Inputs
    violations: List[str]
    previous_output: Any
    
    # Outputs
    surgical_feedback: str
    target_keys_to_fix: List[str]
    
    # Control
    retry_count: int
    success: bool


class SurgicalRefinerEngine:
    """Core logic for extracting pinpoint surgical feedback from deterministic violations"""
    
    @staticmethod
    def extract_target_keys(violations: List[str]) -> List[str]:
        """Extracts specific failing keys from deterministic violations list"""
        failing_keys = []
        for v in violations:
            if "'" in v:
                parts = v.split("'")
                if len(parts) >= 2:
                    failing_keys.append(parts[1])
        return list(set(failing_keys))

    @staticmethod
    def generate_surgical_instructions(violations: List[str], failing_keys: List[str]) -> str:
        """Constructs surgical, non-destructive feedback instructions"""
        if not violations:
            return "No surgical corrections required."
            
        instructions = [
            "SURGICAL CORRECTION REQUIRED:",
            "Do NOT regenerate unchanged parts. Focus ONLY on fixing the following specific issues:"
        ]
        
        for i, violation in enumerate(violations, 1):
            instructions.append(f"  {i}. {violation}")
            
        if failing_keys:
            instructions.append(f"Target Keys to Fix: {', '.join(failing_keys)}")
            
        return "\n".join(instructions)


# Karpathy Loop Implementation

def propose(state: SurgicalRefinerState) -> dict:
    """Step 1: Propose - Inspect violations and identify target keys"""
    violations = state.get("violations", [])
    
    if not violations:
        return {
            "surgical_feedback": "No violations detected.",
            "target_keys_to_fix": [],
            "success": True
        }
        
    failing_keys = SurgicalRefinerEngine.extract_target_keys(violations)
    return {
        "target_keys_to_fix": failing_keys,
        "success": False
    }


def execute(state: SurgicalRefinerState) -> dict:
    """Step 2: Execute - Generate targeted surgical feedback instructions"""
    violations = state.get("violations", [])
    failing_keys = state.get("target_keys_to_fix", [])
    
    feedback = SurgicalRefinerEngine.generate_surgical_instructions(violations, failing_keys)
    return {"surgical_feedback": feedback}


def evaluate(state: SurgicalRefinerState) -> dict:
    """Step 3: Evaluate - Ensure surgical feedback is concise and non-empty"""
    feedback = state.get("surgical_feedback", "")
    success = len(feedback) > 0 and "SURGICAL CORRECTION" in feedback
    return {"success": success}


def commit(state: SurgicalRefinerState) -> dict:
    """Step 4: Commit - Save surgical feedback"""
    return {"committed": True}


def refine(state: SurgicalRefinerState) -> dict:
    """Step 5: Refine - Escalate if refinement loop exceeds retry budget"""
    retry_count = state.get("retry_count", 0) + 1
    return {
        "retry_count": retry_count,
        "success": False
    }


def should_continue(state: SurgicalRefinerState) -> str:
    """Determine next step in Karpathy Loop"""
    if state.get("success", False):
        return "commit"
    elif state.get("retry_count", 0) >= 3:
        return "escalate"
    else:
        return "refine"


# Build LangGraph Workflow
workflow = StateGraph(SurgicalRefinerState)

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
surgical_refiner_graph = workflow.compile(checkpointer=checkpointer)


def generate_refinement_feedback(
    violations: List[str],
    previous_output: Any = None,
    thread_id: str = "refiner_session"
) -> dict:
    """
    Generates pinpoint surgical feedback for targeted LLM self-correction.
    
    Args:
        violations: List of violation strings from DeterministicValidator
        previous_output: Previous output object
        thread_id: Session thread ID for LangGraph checkpointer
    
    Returns:
        Dict containing surgical_feedback, target_keys_to_fix, success
    """
    result = surgical_refiner_graph.invoke(
        {
            "violations": violations,
            "previous_output": previous_output,
            "surgical_feedback": "",
            "target_keys_to_fix": [],
            "retry_count": 0,
            "success": False
        },
        config={"configurable": {"thread_id": thread_id}}
    )
    
    return {
        "surgical_feedback": result.get("surgical_feedback", ""),
        "target_keys_to_fix": result.get("target_keys_to_fix", []),
        "success": result.get("success", False)
    }
