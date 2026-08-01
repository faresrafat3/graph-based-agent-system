"""
Karpathy Pipeline - Integrated Pipeline connecting Context Curator → Task Decomposer → Deterministic Validator → Surgical Refiner
Implements the full Karpathy Engineering Loop with zero-LLM governance.
"""

from agents.context_curator import curate_context
from agents.task_decomposer import decompose_requirements
from agents.deterministic_validator import validate_output
from agents.surgical_refiner import generate_refinement_feedback


def run_karpathy_pipeline(
    requirements: str,
    project_context: str = "",
    constraints: str = "",
    history_logs: list = None,
    max_retries: int = 3
) -> dict:
    """
    Full Karpathy Pipeline: Curate → Decompose → Validate → Refine (if needed)
    
    The LLM is ONLY used inside decompose_requirements (the CPU).
    Everything else is deterministic Python code (the Operating System).
    
    Args:
        requirements: Raw user requirements
        project_context: Project context
        constraints: Constraints
        history_logs: Historical execution logs
        max_retries: Maximum refinement retries before escalation
    
    Returns:
        Dict with pipeline results
    """
    
    # === Stage 1: Context Curator (Deterministic - Zero LLM) ===
    curated = curate_context(
        raw_prompt=requirements,
        history_logs=history_logs or [],
        max_token_budget=4000
    )
    
    if not curated["success"]:
        return {
            "stage": "context_curation",
            "success": False,
            "error": "Context sanitation failed. Input may be too large or corrupted."
        }
    
    # === Stage 2: Task Decomposer (LLM as CPU - Sandboxed) ===
    decomposition = decompose_requirements(
        requirements=curated["sanitized_prompt"],
        project_context=project_context,
        constraints=constraints
    )
    
    # === Stage 3: Deterministic Validator (Zero LLM - Ground Truth) ===
    validation = validate_output(
        target_output=decomposition,
        required_keys=["tasks", "metadata"]
    )
    
    # === Stage 4: Surgical Refiner Loop (if validation fails) ===
    attempt = 0
    while not validation["success"] and attempt < max_retries:
        attempt += 1
        
        refinement = generate_refinement_feedback(
            violations=validation["violations"],
            previous_output=decomposition
        )
        
        # Feed surgical feedback back into decomposer
        enhanced_requirements = (
            f"{curated['sanitized_prompt']}\n\n"
            f"CORRECTION INSTRUCTIONS:\n{refinement['surgical_feedback']}"
        )
        
        decomposition = decompose_requirements(
            requirements=enhanced_requirements,
            project_context=project_context,
            constraints=constraints
        )
        
        validation = validate_output(
            target_output=decomposition,
            required_keys=["tasks", "metadata"]
        )
    
    # === Final Result ===
    return {
        "stage": "complete",
        "success": validation["success"],
        "tasks": decomposition.get("tasks", []),
        "metadata": decomposition.get("metadata", {}),
        "quality_score": validation["quality_score"],
        "violations": validation["violations"],
        "refinement_attempts": attempt,
        "context_signal_to_noise": curated["signal_to_noise_ratio"]
    }
