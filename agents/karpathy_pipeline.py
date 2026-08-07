"""
Karpathy Pipeline - Integrated Pipeline connecting Context Curator → Task Decomposer → Deterministic Validator → Code Executor → Test Runner → Surgical Refiner.

Implements the full Karpathy Engineering Loop with zero-LLM governance and empirical ground-truth execution.

Orchestration: per CONSTITUTION Article III, the pipeline is orchestrated as a LangGraph
``StateGraph`` (stateful workflow orchestration). Each stage is a pure (state) -> state
node; the graph threads a typed state object through the stages and terminates in a
finalize node that emits the same result dict the old procedural pipeline returned.
"""

from __future__ import annotations

import logging
import uuid
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

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
# Intelligence Forge (opt-in, default-deny): the pipeline can forge bespoke agents for
# the task at hand, assemble their topology, expose the whole system as their context,
# and put the resulting spec through the real Sage Council. Wired behind
# `forge_agent_graph` so the default run is unchanged (P7: least sufficient
# intervention) while the modules sit on a real call path, not an amputated one.
from agents.agent_forge import forge_agent, assert_distinct
from agents.topology_assembler import assemble_topology
from agents.context_system_view import build_context_view, context_includes_system
from agents.sage_council import build_council_from_registry

logger = logging.getLogger(__name__)

# Bounded execution budget: code-gen + sandbox runs are LLM/CPU expensive, so the
# pipeline executes at most this many tasks per run. This is a DELIBERATE cap, not a
# silent bug — when the plan exceeds it we log loudly (Law 3) instead of dropping
# work with no trace (the old `tasks[:3]` slice did exactly that).
MAX_EXEC_TASKS = 3


class KarpathyPipelineState(TypedDict):
    """State threaded through the Karpathy pipeline StateGraph.

    Every stage reads the fields it needs and returns only the fields it changes;
    LangGraph merges the returned partial into the running state.
    """

    requirements: str
    project_context: str
    constraints: str
    history_logs: list
    execute_code: bool
    dispatch_domains: bool
    orchestrate_graph: bool
    forge_agent_graph: bool  # Intelligence Forge opt-in (default False, P7)
    max_retries: int

    curated: dict
    decomposition: dict
    validation: dict
    attempt: int
    assignment: dict
    pipeline_success: bool
    combined_breaches: list
    domain_dispatch_result: dict
    graph_execution_result: dict
    forge_result: dict
    squad_test_results: dict
    executed_modules: list
    acceptance_criteria: list
    execution_results: list
    quality_review: dict
    early_error: dict | None
    final_result: dict | None


# ---- Stage 1: Context Curator (Deterministic - Zero LLM) ----

def context_curate_node(state: KarpathyPipelineState) -> dict:
    curated = curate_context(
        raw_prompt=state["requirements"],
        history_logs=state["history_logs"] or [],
        max_token_budget=4000,
    )
    if not curated.get("success"):
        error = {
            "stage": "context_curation",
            "success": False,
            "error": "Context sanitation failed. Input may be too large or corrupted.",
        }
        return {"curated": curated, "early_error": error}
    return {"curated": curated, "early_error": None}


def route_after_context(state: KarpathyPipelineState) -> str:
    """Branch to the finalize node early if context curation failed."""
    return "finalize" if state.get("early_error") is not None else "decompose_and_refine"


# ---- Stages 2-4: Decompose -> Validate -> Surgical Refiner loop ----

def decompose_refine_node(state: KarpathyPipelineState) -> dict:
    curated = state["curated"]
    decomposition = decompose_requirements(
        requirements=curated["sanitized_prompt"],
        project_context=state["project_context"],
        constraints=state["constraints"],
    )
    validation = validate_output(
        target_output=decomposition,
        required_keys=["tasks", "metadata"],
    )
    attempt = 0
    while not validation["success"] and attempt < state["max_retries"]:
        attempt += 1
        refinement = generate_refinement_feedback(
            breaches=validation["breaches"],
            previous_output=decomposition,
        )
        enhanced_requirements = (
            f"{curated['sanitized_prompt']}\n\n"
            f"CORRECTION INSTRUCTIONS:\n{refinement['surgical_feedback']}"
        )
        decomposition = decompose_requirements(
            requirements=enhanced_requirements,
            project_context=state["project_context"],
            constraints=state["constraints"],
        )
        validation = validate_output(
            target_output=decomposition,
            required_keys=["tasks", "metadata"],
        )
    return {"decomposition": decomposition, "validation": validation, "attempt": attempt}


# ---- Stage 5: Agent Assigner (Deterministic DAG Routing) ----

def assign_node(state: KarpathyPipelineState) -> dict:
    tasks = state["decomposition"].get("tasks", [])
    assignment = {
        "success": False,
        "assignments": {},
        "execution_plan": [],
        "breaches": [],
    }
    if state["validation"]["success"] and tasks:
        assignment = assign_tasks(tasks)
    pipeline_success = state["validation"]["success"] and assignment["success"]
    combined_breaches = list(state["validation"]["breaches"]) + list(assignment.get("breaches", []))
    return {
        "assignment": assignment,
        "pipeline_success": pipeline_success,
        "combined_breaches": combined_breaches,
    }


# ---- Stage 5b: Intelligence Forge (opt-in) ----

def forge_node(state: KarpathyPipelineState) -> dict:
    """Forge bespoke agents for THIS task's plan, then review the topology (opt-in).

    Default-deny (P7 / C1-rev1): with `forge_agent_graph=False` this is a no-op, so the
    default pipeline behaviour is untouched. When enabled it exercises the real forge
    path end-to-end:

      1. forge_agent()          — one BESPOKE agent per planned task (no role-play clones:
                                  distinct task + distinct spec slice => distinct agent,
                                  asserted by assert_distinct).
      2. build_context_view()   — each agent's context IS the managed system (peers +
                                  cycle_log + constitution binding), bounded by design.
      3. assemble_topology()    — constraints live in the TOPOLOGY layer, not in a prompt.
      4. SageCouncil            — the REAL council built from the project registry
                                  (build_council_from_registry, not the mock default),
                                  reconciled through ConsensusMechanism.

    Emits a proposal only. Nothing here mutates the global registry and nothing is
    applied to the run: the council's spec is reported for review, matching the
    meta-loop rule that proposals are held unless independently opted in.
    """
    if not state.get("forge_agent_graph"):
        return {"forge_result": {"enabled": False, "reason": "forge_agent_graph=False (default-deny)"}}

    tasks = state["decomposition"].get("tasks", [])
    if not (state["pipeline_success"] and tasks):
        return {"forge_result": {"enabled": True, "forged": 0, "reason": "no validated plan to forge against"}}

    assignments = state["assignment"].get("assignments", {})
    forged = []
    for task in tasks[:MAX_EXEC_TASKS]:
        title = str(task.get("title") or task.get("id") or "task")
        # spec_slice: the constitutional slice this agent is bound to. Derived from the
        # task's own shape so two different tasks cannot forge the same agent.
        criteria = [str(c) for c in (task.get("acceptance_criteria") or [])]
        spec_slice: list[str] = sorted(set(criteria) | {
            f"assigned_to:{assignments.get(task.get('id'), 'unassigned')}"
        }) or [f"task:{title}"]
        forged.append(forge_agent(
            name=f"forged::{title}",
            spec_slice=spec_slice,
            focused_task=str(task.get("description") or title),
        ))

    # P-NO-ROLE-PLAY, enforced not asserted: raises if the forge produced clones.
    assert_distinct(forged)

    contexts = [build_context_view(a, dict(state)) for a in forged]
    context_is_system = all(context_includes_system(a, dict(state)) for a in forged)
    topology = assemble_topology(forged)

    # The REAL council (registry-backed, not the 3-sage mock). It reasons on
    # context-isolated signals only (CIR) and is complexity-gated, so a trivial plan
    # skips deliberation instead of over-philosophizing it.
    council = build_council_from_registry()
    measurement = {
        "complexity_score": len(tasks),
        "breach_count": len(state["combined_breaches"]),
        "repeated_hypothesis_count": state["attempt"],
        "success_rate": 100.0 if state["pipeline_success"] else 0.0,
    }
    council_out = (
        council.convene(measurement) if council.should_convene(measurement)
        else council.skip(measurement)
    )

    return {
        "forge_result": {
            "enabled": True,
            "forged": len(forged),
            "agent_names": [a.name for a in forged],
            "context_is_system": context_is_system,
            "context_peer_counts": [len(c["system_context"]["peer_agents"]) for c in contexts],
            "topology": topology,
            "council_size": len(council.sages),
            "council_convened": council_out["convened"],
            "reconciled_spec": council_out["reconciled_spec"],
            "conflicts": (council_out.get("consensus") or {}).get("conflicts", []),
            "applied": False,  # proposal only — held for review (C1-rev1)
        }
    }


# ---- Stage 6 + 6.5: Graph DAG Orchestration or Domain Squad Dispatch ----

def dispatch_orchestrate_node(state: KarpathyPipelineState) -> dict:
    tasks = state["decomposition"].get("tasks", [])
    assignment = state["assignment"]
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
    pipeline_success = state["pipeline_success"]
    combined_breaches = list(state["combined_breaches"])

    if state["orchestrate_graph"] and pipeline_success and tasks:
        graph_execution_result = orchestrate_graph_execution(
            tasks=tasks,
            execution_plan=assignment.get("execution_plan", []),
            global_context=state["project_context"],
            dispatch_domains=state["dispatch_domains"],
        )
        domain_dispatch_result = graph_execution_result.get("dispatch_result", domain_dispatch_result)
        pipeline_success = pipeline_success and graph_execution_result["success"]
        combined_breaches.extend(graph_execution_result.get("breaches", []))
    elif state["dispatch_domains"] and pipeline_success and tasks:
        domain_dispatch_result = dispatch_domain_tasks(
            tasks=tasks,
            execution_plan=assignment.get("execution_plan", []),
            global_context=state["project_context"],
        )
        graph_execution_result["dispatch_result"] = domain_dispatch_result
        pipeline_success = pipeline_success and domain_dispatch_result["success"]
        combined_breaches.extend(domain_dispatch_result.get("breaches", []))

    # Stage 6.5: execution-ground the squad code (only when execute_code).
    squad_test_results = {}
    if state["execute_code"] and domain_dispatch_result.get("parsed_outputs"):
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

    return {
        "domain_dispatch_result": domain_dispatch_result,
        "graph_execution_result": graph_execution_result,
        "pipeline_success": pipeline_success,
        "combined_breaches": combined_breaches,
        "squad_test_results": squad_test_results,
    }


# ---- Stage 7: Code Execution & Test Runner Loop (if enabled) ----

def execute_node(state: KarpathyPipelineState) -> dict:
    tasks = state["decomposition"].get("tasks", [])
    executed_modules = []
    if state["execute_code"] and state["pipeline_success"] and tasks:
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
            code_res = execute_task(task, project_context=state["project_context"])
            if code_res["success"] and code_res["code"]:
                # Physically run tests in isolated sandbox
                test_res = run_code_and_tests(
                    filename=code_res["filename"],
                    code=code_res["code"],
                    test_filename=code_res["test_filename"],
                    test_code=code_res["test_code"],
                )
                code_res["test_execution"] = test_res
                executed_modules.append(code_res)
    return {"executed_modules": executed_modules}


# ---- Stage 8: Quality Reviewer (Deterministic Global Gate) ----

def quality_review_node(state: KarpathyPipelineState) -> dict:
    tasks = state["decomposition"].get("tasks", [])
    acceptance_criteria = [
        criterion
        for task in tasks
        for criterion in task.get("acceptance_criteria", [])
    ]
    execution_results = [
        module.get("test_execution")
        for module in state["executed_modules"]
        if module.get("test_execution") is not None
    ]
    pipeline_success = state["pipeline_success"]
    if state["orchestrate_graph"] and state["graph_execution_result"].get("quality_review"):
        quality_review = state["graph_execution_result"]["quality_review"]
        return {
            "quality_review": quality_review,
            "acceptance_criteria": acceptance_criteria,
            "execution_results": execution_results,
        }
    quality_review = review_quality(
        validation_reports=[state["validation"]],
        assignment_result=state["assignment"],
        dispatch_result=state["domain_dispatch_result"],
        execution_results=execution_results,
        acceptance_criteria=acceptance_criteria,
    )
    pipeline_success = pipeline_success and quality_review["approved"]
    combined_breaches = list(state["combined_breaches"]) + list(quality_review.get("rejection_reasons", []))
    return {
        "quality_review": quality_review,
        "pipeline_success": pipeline_success,
        "combined_breaches": combined_breaches,
        "acceptance_criteria": acceptance_criteria,
        "execution_results": execution_results,
    }


# ---- Finalize ----

def finalize_node(state: KarpathyPipelineState) -> dict:
    if state.get("early_error") is not None:
        return {"final_result": state["early_error"]}
    curated = state["curated"]
    decomposition = state["decomposition"]
    return {
        "final_result": {
            "stage": "complete",
            "success": state["pipeline_success"],
            "tasks": state["decomposition"].get("tasks", []),
            "metadata": decomposition.get("metadata", {}),
            "quality_score": state["validation"]["quality_score"],
            "final_quality_score": state["quality_review"].get("quality_score", 0.0),
            "breaches": state["combined_breaches"],
            "refinement_attempts": state["attempt"],
            "context_signal_to_noise": curated["signal_to_noise_ratio"],
            "agent_assignments": state["assignment"].get("assignments", {}),
            "execution_plan": state["assignment"].get("execution_plan", []),
            "assignment_success": state["assignment"].get("success", False),
            "domain_dispatch": state["domain_dispatch_result"],
            "graph_execution": state["graph_execution_result"],
            "forge": state["forge_result"],
            "quality_review": state["quality_review"],
            "executed_modules": state["executed_modules"],
        }
    }


def build_pipeline_graph():
    """Compile the Karpathy pipeline as a LangGraph StateGraph (Article III)."""
    workflow = StateGraph(KarpathyPipelineState)
    workflow.add_node("context_curate", context_curate_node)
    workflow.add_node("decompose_and_refine", decompose_refine_node)
    workflow.add_node("assign", assign_node)
    workflow.add_node("forge", forge_node)
    workflow.add_node("dispatch_orchestrate", dispatch_orchestrate_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("quality_review", quality_review_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "context_curate")
    workflow.add_conditional_edges(
        "context_curate",
        route_after_context,
        {"decompose_and_refine": "decompose_and_refine", "finalize": "finalize"},
    )
    workflow.add_edge("decompose_and_refine", "assign")
    workflow.add_edge("assign", "forge")
    workflow.add_edge("forge", "dispatch_orchestrate")
    workflow.add_edge("dispatch_orchestrate", "execute")
    workflow.add_edge("execute", "quality_review")
    workflow.add_edge("quality_review", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=MemorySaver())


def run_karpathy_pipeline(
    requirements: str,
    project_context: str = "",
    constraints: str = "",
    history_logs: list | None = None,
    execute_code: bool = False,
    dispatch_domains: bool = False,
    orchestrate_graph: bool = False,
    forge_agent_graph: bool = False,
    max_retries: int = 3,
) -> dict:
    """
    Full Karpathy Pipeline (LangGraph-orchestrated):
    Curate → Decompose → Validate → Execute Code (optional) → Run Pytest → Refine (if needed)

    Returns the same result dict as the previous procedural implementation so the
    CLI and the test suite are unaffected by the orchestration change.
    """
    initial_state: KarpathyPipelineState = {
        "requirements": requirements,
        "project_context": project_context,
        "constraints": constraints,
        "history_logs": history_logs or [],
        "execute_code": execute_code,
        "dispatch_domains": dispatch_domains,
        "orchestrate_graph": orchestrate_graph,
        "forge_agent_graph": forge_agent_graph,
        "max_retries": max_retries,
        "curated": {},
        "decomposition": {},
        "validation": {},
        "attempt": 0,
        "assignment": {},
        "pipeline_success": False,
        "combined_breaches": [],
        "domain_dispatch_result": {},
        "graph_execution_result": {},
        "forge_result": {},
        "squad_test_results": {},
        "executed_modules": [],
        "acceptance_criteria": [],
        "execution_results": [],
        "quality_review": {},
        "early_error": None,
        "final_result": None,
    }
    graph = build_pipeline_graph()
    result = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )
    return result["final_result"]
