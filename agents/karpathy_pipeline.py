"""
Karpathy Pipeline - Integrated Pipeline connecting Context Curator → Task Decomposer → Deterministic Validator → Code Executor → Test Runner → Surgical Refiner
Implements the full Karpathy Engineering Loop with zero-LLM governance and empirical ground-truth execution.
"""

from agents.context_curator import curate_context
from agents.task_decomposer import decompose_requirements
from agents.deterministic_validator import validate_output
from agents.surgical_refiner import generate_refinement_feedback
from agents.agent_assigner import assign_tasks
from agents.domain_dispatcher import dispatch_domain_tasks
from agents.graph_execution_orchestrator import orchestrate_graph_execution
from agents.quality_reviewer import review_quality
from agents.code_executor import execute_task
from agents.test_runner_agent import run_code_and_tests


def run_karpathy_pipeline(
    requirements: str,
    project_context: str = "",
    constraints: str = "",
    history_logs: list = None,
    execute_code: bool = False,
    dispatch_domains: bool = False,
    orchestrate_graph: bool = False,
    max_retries: int = 3
) -> dict:
    """
    Full Karpathy Pipeline:
    Curate → Decompose → Validate → Execute Code (optional) → Run Pytest → Refine (if needed)
    
    Args:
        requirements: Raw user requirements
        project_context: Project context
        constraints: Constraints
        history_logs: Historical execution logs
        execute_code: Whether to execute Code Executor + Test Runner for each task
        dispatch_domains: Whether to dispatch domain-squad tasks from the execution plan
        orchestrate_graph: Whether to execute the DAG plan through graph group orchestration
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
    
    # === Stage 4: Surgical Refiner Loop for Decomposition ===
    attempt = 0
    while not validation["success"] and attempt < max_retries:
        attempt += 1
        
        refinement = generate_refinement_feedback(
            violations=validation["violations"],
            previous_output=decomposition
        )
        
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
        
    tasks = decomposition.get("tasks", [])

    # === Stage 5: Agent Assigner (Deterministic DAG Routing) ===
    assignment = {
        "success": False,
        "assignments": {},
        "execution_plan": [],
        "violations": [],
    }
    if validation["success"] and tasks:
        assignment = assign_tasks(tasks)

    pipeline_success = validation["success"] and assignment["success"]
    combined_violations = validation["violations"] + assignment.get("violations", [])
    domain_dispatch_result = {
        "success": True,
        "results": [],
        "parsed_outputs": {},
        "violations": [],
        "skipped_tasks": [],
        "blocked_tasks": [],
        "completed_task_ids": [],
    }
    graph_execution_result = {
        "success": True,
        "graph_execution_report": {},
        "completed_task_ids": [],
        "group_results": [],
        "dispatch_result": domain_dispatch_result,
        "integration_result": {},
        "progress_report": {},
        "quality_review": {},
        "violations": [],
    }

    # === Stage 6: Graph DAG Orchestration or Domain Squad Dispatch (optional) ===
    if orchestrate_graph and pipeline_success and tasks:
        graph_execution_result = orchestrate_graph_execution(
            tasks=tasks,
            execution_plan=assignment.get("execution_plan", []),
            global_context=project_context,
            dispatch_domains=dispatch_domains,
        )
        domain_dispatch_result = graph_execution_result.get("dispatch_result", domain_dispatch_result)
        pipeline_success = pipeline_success and graph_execution_result["success"]
        combined_violations.extend(graph_execution_result.get("violations", []))
    elif dispatch_domains and pipeline_success and tasks:
        domain_dispatch_result = dispatch_domain_tasks(
            tasks=tasks,
            execution_plan=assignment.get("execution_plan", []),
            global_context=project_context,
        )
        graph_execution_result["dispatch_result"] = domain_dispatch_result
        pipeline_success = pipeline_success and domain_dispatch_result["success"]
        combined_violations.extend(domain_dispatch_result.get("violations", []))

    executed_modules = []
    
    # === Stage 7: Code Execution & Test Runner Loop (if enabled) ===
    if execute_code and pipeline_success and tasks:
        for task in tasks[:3]:  # Execute top tasks
            code_res = execute_task(task, project_context=project_context)
            if code_res["success"] and code_res["code"]:
                # Physically run tests in isolated sandbox
                test_res = run_code_and_tests(
                    filename=code_res["filename"],
                    code=code_res["code"],
                    test_filename=code_res["test_filename"],
                    test_code=code_res["test_code"]
                )
                code_res["test_execution"] = test_res
                executed_modules.append(code_res)
    
    # === Stage 8: Quality Reviewer (Deterministic Global Gate) ===
    acceptance_criteria = [
        criterion
        for task in tasks
        for criterion in task.get("acceptance_criteria", [])
    ]
    execution_results = [
        module.get("test_execution")
        for module in executed_modules
        if module.get("test_execution") is not None
    ]
    if orchestrate_graph and graph_execution_result.get("quality_review"):
        quality_review = graph_execution_result["quality_review"]
    else:
        quality_review = review_quality(
            validation_reports=[validation],
            assignment_result=assignment,
            dispatch_result=domain_dispatch_result,
            execution_results=execution_results,
            acceptance_criteria=acceptance_criteria,
        )
        pipeline_success = pipeline_success and quality_review["approved"]
        combined_violations.extend(quality_review.get("rejection_reasons", []))

    # === Final Result ===
    return {
        "stage": "complete",
        "success": pipeline_success,
        "tasks": tasks,
        "metadata": decomposition.get("metadata", {}),
        "quality_score": validation["quality_score"],
        "final_quality_score": quality_review.get("quality_score", 0.0),
        "violations": combined_violations,
        "refinement_attempts": attempt,
        "context_signal_to_noise": curated["signal_to_noise_ratio"],
        "agent_assignments": assignment.get("assignments", {}),
        "execution_plan": assignment.get("execution_plan", []),
        "assignment_success": assignment.get("success", False),
        "domain_dispatch": domain_dispatch_result,
        "graph_execution": graph_execution_result,
        "quality_review": quality_review,
        "executed_modules": executed_modules
    }
