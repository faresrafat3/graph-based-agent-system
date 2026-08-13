"""
Surgical Refiner Agent - Meta-Agent for Targeted Refinement & Surgical Corrections
Implements Karpathy's 3rd Engineering Pillar: Surgical Changes & Pinpoint Self-Correction.
"""

from typing import TypedDict, List, Any

from kernel.karpathy_loop import build_karpathy_loop, standard_refine, standard_should_continue
from system.bounded_probe import enforce_bounded_probe

# Permission Boundaries (Law 2 & Constitution Article I, Section 2)
SURGICAL_REFINER_PERMISSIONS = {
    "READ": ["validation_report", "breaches", "previous_output"],
    "WRITE": ["surgical_feedback", "pinpoint_corrections"],
    "NEVER": ["regenerate_entire_system", "override_validation_report"],
    "HUMAN_CHECKPOINT": ["persistent_unsolvable_breaches"]
}


# State Definition
class SurgicalRefinerState(TypedDict):
    # Inputs
    breaches: List[str]
    previous_output: Any
    
    # Outputs
    surgical_feedback: str
    target_keys_to_fix: List[str]
    
    # Control
    retry_count: int
    success: bool


class SurgicalRefinerEngine:
    """Core logic for extracting pinpoint surgical feedback from deterministic breaches"""
    
    @staticmethod
    def extract_target_keys(breaches: List[str]) -> List[str]:
        """Extracts specific failing keys from deterministic breaches list"""
        failing_keys = []
        for v in breaches:
            if "'" in v:
                parts = v.split("'")
                if len(parts) >= 2:
                    failing_keys.append(parts[1])
        return list(set(failing_keys))

    @staticmethod
    def generate_surgical_instructions(breaches: List[str], failing_keys: List[str]) -> str:
        """Constructs surgical, non-destructive feedback instructions"""
        if not breaches:
            return "No surgical corrections required."
            
        instructions = [
            "SURGICAL CORRECTION REQUIRED:",
            "Do NOT regenerate unchanged parts. Focus ONLY on fixing the following specific issues:"
        ]
        
        for i, breach in enumerate(breaches, 1):
            instructions.append(f"  {i}. {breach}")
            
        if failing_keys:
            instructions.append(f"Target Keys to Fix: {', '.join(failing_keys)}")
            
        return "\n".join(instructions)


# Karpathy Loop Implementation

def propose(state: SurgicalRefinerState) -> dict:
    """Step 1: Propose - Inspect breaches and identify target keys"""
    breaches = state.get("breaches", [])
    
    if not breaches:
        return {
            "surgical_feedback": "No breaches detected.",
            "target_keys_to_fix": [],
            "success": True
        }
        
    failing_keys = SurgicalRefinerEngine.extract_target_keys(breaches)
    return {
        "target_keys_to_fix": failing_keys,
        "success": False
    }


def execute(state: SurgicalRefinerState) -> dict:
    """Step 2: Execute - Generate targeted surgical feedback instructions"""
    breaches = state.get("breaches", [])
    failing_keys = state.get("target_keys_to_fix", [])
    
    feedback = SurgicalRefinerEngine.generate_surgical_instructions(breaches, failing_keys)
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
    return standard_refine(state)


def should_continue(state: SurgicalRefinerState) -> str:
    """Determine next step in Karpathy Loop"""
    return standard_should_continue(state, retry_cap=3)


surgical_refiner_graph = build_karpathy_loop(
    SurgicalRefinerState,
    execute_fn=execute,
    propose_fn=propose,
    evaluate_fn=evaluate,
    retry_cap=3,
)


def generate_refinement_feedback(
    breaches: List[str],
    previous_output: Any = None,
    thread_id: str = "refiner_session",
    max_probe_attempts: int = 4,
) -> dict:
    """
    Generates pinpoint surgical feedback for targeted LLM self-correction.
    
    Args:
        breaches: List of breach strings from DeterministicValidator
        previous_output: Previous output object
        thread_id: Session thread ID for LangGraph checkpointer
        max_probe_attempts: P4 bounded-probing budget over the breach set
    
    Returns:
        Dict containing surgical_feedback, target_keys_to_fix, success, probe
    """
    # P4 (Bounded Probing): the refinement loop is where a system thrashes — it keeps
    # re-proposing the same hypothesis against the same breaches. enforce_bounded_probe
    # scores the breach set by HYPOTHESIS IDENTITY (not raw text) and escalates instead
    # of looping forever. Deterministic and zero-LLM, so it cannot inflate its own budget.
    probe = enforce_bounded_probe(list(breaches), max_attempts=max_probe_attempts)

    result = surgical_refiner_graph.invoke(
        {
            "breaches": breaches,
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
        "success": result.get("success", False),
        "probe": probe,
    }
