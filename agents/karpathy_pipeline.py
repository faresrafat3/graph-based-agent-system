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
import logging

logger = logging.getLogger(__name__)

# Bounded execution budget: code-gen + sandbox runs are LLM/CPU expensive, so the
# pipeline executes at most this many tasks per run. This is a DELIBERATE cap, not a
# silent bug — when the plan exceeds it we log loudly (Law 3) instead of dropping
# work with no trace (the old `tasks[:3]` slice did exactly that).
MAX_EXEC_TASKS = 3


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
            breaches=validation["breaches"],
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
        "breaches": [],
    }
    if validation["success"] and tasks:
        assignment = assign_tasks(tasks)

    pipeline_success = validation["success"] and assignment["success"]
    combined_breaches = validation["breaches"] + assignment.get("breaches", [])
    domain_dispatch_result = {
        "success": True,
        "results": [],
        "parsed_outputs": {},
        "breaches": [],
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
        "breaches": [],
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
        combined_breaches.extend(graph_execution_result.get("breaches", []))
    elif dispatch_domains and pipeline_success and tasks:
        domain_dispatch_result = dispatch_domain_tasks(
            tasks=tasks,
            execution_plan=assignment.get("execution_plan", []),
            global_context=project_context,
        )
        graph_execution_result["dispatch_result"] = domain_dispatch_result
        pipeline_success = pipeline_success and domain_dispatch_result["success"]
        combined_breaches.extend(domain_dispatch_result.get("breaches", []))

    # === Stage 6.5: Execution-ground squad code (only when execute_code) ===
    # Domain-squad outputs are parsed into {code, test_code} by domain_dispatcher,
    # but unlike the main tasks loop (Stage 7) they were NEVER physically run in the
    # sandbox. That asymmetry breachs the project's execution-grounded thesis (F7).
    # When execute_code is set we run the parsed squad artifacts through the same
    # isolated pytest sandbox used by Stage 7, so squad output is verified, not assumed.
    squad_test_results = {}
    if execute_code and domain_dispatch_result.get("parsed_outputs"):
        for task_id, parsed in domain_dispatch_result["parsed_outputs"].items():
            code = parsed.get("code")
            test_code = parsed.get("test_code")
            if not code:
                continue
            squad_test_results[task_id] = run_code_and_tests(
                filename=parsed.get("filename", f"squad_{task_id}.py"),
                code=code,
                test_filename=parsed.get("test_filename", f"test_squad_{task_id}.py"),
                test_code=test_code or "",
            )
        domain_dispatch_result["test_execution"] = squad_test_results
        if any(not r.get("success") for r in squad_test_results.values()):
            combined_breaches.append(
                "Domain-squad code failed the execution sandbox for some tasks."
            )

    executed_modules = []

    # === Stage 7: Code Execution & Test Runner Loop (if enabled) ===
    if execute_code and pipeline_success and tasks:
        exec_budget = min(len(tasks), MAX_EXEC_TASKS)
        if len(tasks) > MAX_EXEC_TASKS:
            # Law 3: never drop work silently. The old `tasks[:3]` slice hid this.
            logger.warning(
                "Execution budget capped at %d of %d decomposed tasks; "
                "tasks %d..%d were NOT executed this run (raise MAX_EXEC_TASKS "
                "or process them in a follow-up run).",
                MAX_EXEC_TASKS, len(tasks), MAX_EXEC_TASKS + 1, len(tasks),
            )
        for task in tasks[:exec_budget]:  # Execute within the explicit budget
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
        combined_breaches.extend(quality_review.get("rejection_reasons", []))

    # === Final Result ===
    return {
        "stage": "complete",
        "success": pipeline_success,
        "tasks": tasks,
        "metadata": decomposition.get("metadata", {}),
        "quality_score": validation["quality_score"],
        "final_quality_score": quality_review.get("quality_score", 0.0),
        "breaches": combined_breaches,
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
