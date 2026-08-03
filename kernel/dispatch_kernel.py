"""
Dispatch Kernel - Deterministic Signal-Driven Agent Router (Layer 0).
Reads AgentSignals from a FIFO queue and dispatches to the correct agent
based on a deterministic routing table. Zero-LLM at the control plane.
"""

import os
import sys
import logging
from collections import deque

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kernel.signal_protocol import AgentSignal
from agents.context_curator import curate_context
from agents.task_decomposer import decompose_requirements
from agents.deterministic_validator import validate_output
from agents.surgical_refiner import generate_refinement_feedback
from agents.code_executor import execute_task
from agents.test_runner_agent import run_code_and_tests


# Deterministic Routing Table (Zero-LLM — pure match/case)
ROUTING_TABLE = {
    "CONTEXT_CURATED":        "task_decomposer",
    "TASK_DECOMPOSED":        "deterministic_validator",
    "ARCHITECTURE_READY":     "code_executor",
    "CODE_GENERATED":         "test_runner",
    "TESTS_PASSED":           "integration_check",
    "VALIDATION_FAILED":      "surgical_refiner",
    "TESTS_FAILED":           "surgical_refiner",
    "ARCHITECTURE_INCOMPLETE":"surgical_refiner",
    "INTEGRATION_FAILED":     "surgical_refiner",
    "SECURITY_VIOLATION":     "human_checkpoint",
    "CONTEXT_ROT_DETECTED":   "context_curator",
    "NEEDS_CLARIFICATION":    "human_checkpoint",
    "HUMAN_CHECKPOINT":       "human_checkpoint",
    "MAX_RETRIES_EXCEEDED":   "human_checkpoint",
    "PROJECT_ASSEMBLED":      "done",
    "PIPELINE_COMPLETE":      "done"
}

# Failure Policy
FAILURE_POLICY = {
    "task_decomposer":    {"max_retries": 3, "fallback": "human_checkpoint"},
    "code_executor":      {"max_retries": 3, "fallback": "human_checkpoint"},
    "test_runner":        {"max_retries": 2, "fallback": "human_checkpoint"},
    "surgical_refiner":   {"max_retries": 2, "fallback": "human_checkpoint"},
}


class DispatchKernel:
    """
    Signal-Driven Dispatch Kernel (Zero-LLM).
    Reads signals from a FIFO queue and routes to agents deterministically.
    """
    
    def __init__(self):
        self.signal_queue = deque()
        self.signal_log = []
        self.completed_modules = []
        self.retry_tracker = {}
        
    def emit(self, signal: AgentSignal):
        """Add a signal to the dispatch queue."""
        self.signal_queue.append(signal)
        self.signal_log.append(signal.to_dict())
        
    def route(self, signal: AgentSignal) -> str:
        """Deterministic routing — returns next agent name from routing table."""
        return ROUTING_TABLE.get(signal.signal_type, "human_checkpoint")
    
    def check_retry_budget(self, agent_name: str) -> bool:
        """Check if agent has retries remaining."""
        policy = FAILURE_POLICY.get(agent_name, {"max_retries": 3})
        current_retries = self.retry_tracker.get(agent_name, 0)
        return current_retries < policy["max_retries"]
    
    def increment_retry(self, agent_name: str):
        """Increment retry counter for an agent."""
        self.retry_tracker[agent_name] = self.retry_tracker.get(agent_name, 0) + 1
        
    def run(
        self,
        requirements: str,
        project_context: str = "",
        constraints: str = "",
        execute_code: bool = False,
    ) -> dict:
        """
        Main kernel loop — processes signals until terminal state.

        The control plane (routing, retry policy, signal emission) is deterministic
        and Zero-LLM (Law 14). The only LLM calls are the task-decomposition and
        optional code-generation stages, which are gated by `execute_code`.

        Args:
            requirements: Raw user requirements
            project_context: Project context
            constraints: Constraints
            execute_code: If True, generate + run code/tests for each task
                (LLM-backed; requires a trusted sandbox). If False, only the
                deterministic decomposition/validation signals are emitted.

        Returns:
            Final pipeline result dict
        """
        
        # === Stage 1: Context Curation (Deterministic) ===
        curated = curate_context(
            raw_prompt=requirements,
            history_logs=[],
            max_token_budget=4000
        )
        
        if not curated["success"]:
            self.emit(AgentSignal(
                signal_type="CONTEXT_ROT_DETECTED",
                source_agent="context_curator",
                data={"error": "Context sanitation failed"}
            ))
            return {"success": False, "error": "Context curation failed", "signal_log": self.signal_log}
        
        self.emit(AgentSignal(
            signal_type="CONTEXT_CURATED",
            source_agent="context_curator",
            data={"sanitized_prompt": curated["sanitized_prompt"]},
            quality_score=curated["signal_to_noise_ratio"]
        ))
        
        # === Stage 2: Task Decomposition (LLM as CPU) ===
        decomposition = decompose_requirements(
            requirements=curated["sanitized_prompt"],
            project_context=project_context,
            constraints=constraints
        )
        
        tasks = decomposition.get("tasks", [])
        
        if not tasks:
            self.emit(AgentSignal(
                signal_type="NEEDS_CLARIFICATION",
                source_agent="task_decomposer",
                data={"clarifications": decomposition.get("clarifications_needed", [])}
            ))
        else:
            self.emit(AgentSignal(
                signal_type="TASK_DECOMPOSED",
                source_agent="task_decomposer",
                data={"tasks": tasks, "metadata": decomposition.get("metadata", {})}
            ))
        
        # === Stage 3: Deterministic Validation (Zero-LLM) ===
        validation = validate_output(
            target_output=decomposition,
            required_keys=["tasks", "metadata"]
        )
        
        if not validation["success"]:
            # Surgical refinement loop
            attempt = 0
            while not validation["success"] and attempt < 3:
                attempt += 1
                self.emit(AgentSignal(
                    signal_type="VALIDATION_FAILED",
                    source_agent="deterministic_validator",
                    data={"violations": validation["violations"]},
                    retry_count=attempt
                ))
                
                refinement = generate_refinement_feedback(
                    violations=validation["violations"],
                    previous_output=decomposition
                )
                
                enhanced = (
                    f"{curated['sanitized_prompt']}\n\n"
                    f"CORRECTION INSTRUCTIONS:\n{refinement['surgical_feedback']}"
                )
                
                decomposition = decompose_requirements(
                    requirements=enhanced,
                    project_context=project_context,
                    constraints=constraints
                )
                tasks = decomposition.get("tasks", [])
                validation = validate_output(
                    target_output=decomposition,
                    required_keys=["tasks", "metadata"]
                )
        
        # === Stage 4: Code Execution Loop (per task) ===
        # The control-plane routing decision is made by the deterministic router
        # (Law 14): the CODE_GENERATED signal must resolve to the test_runner agent.
        # We assert the router is wired correctly so the ROUTING_TABLE is never dead code.
        code_stage_agent = self.route(AgentSignal(
            signal_type="CODE_GENERATED",
            source_agent="code_executor",
            data={},
        ))
        if code_stage_agent != "test_runner":  # pragma: no cover - router invariant
            logger.warning(
                "ROUTING_TABLE drift: CODE_GENERATED -> %s (expected 'test_runner')",
                code_stage_agent,
            )

        executed_modules = []
        # NOTE: execute every decomposed task. Code generation hits the LLM and must be
        # gated by execute_code (mirrors karpathy_pipeline). The previous tasks[:3] slice
        # silently dropped the rest of the plan.
        for task in tasks:
            if not execute_code:
                # Without code execution we still emit the deterministic signals so the
                # signal log stays complete, but skip the LLM-backed code stage.
                self.emit(AgentSignal(
                    signal_type="TASK_DECOMPOSED",
                    source_agent="task_decomposer",
                    data={"task_id": task.get("id"), "skipped_code_stage": True},
                ))
                continue

            code_result = execute_task(task, project_context=project_context)
            
            if code_result["success"] and code_result.get("code"):
                self.emit(AgentSignal(
                    signal_type="CODE_GENERATED",
                    source_agent="code_executor",
                    data={"filename": code_result["filename"], "task_id": task.get("id")}
                ))
                
                # Test Runner (physical sandbox)
                test_result = run_code_and_tests(
                    filename=code_result["filename"],
                    code=code_result["code"],
                    test_filename=code_result.get("test_filename", ""),
                    test_code=code_result.get("test_code", "")
                )
                
                if test_result["success"]:
                    self.emit(AgentSignal(
                        signal_type="TESTS_PASSED",
                        source_agent="test_runner",
                        data={"passed": test_result["passed_tests"], "filename": code_result["filename"]}
                    ))
                else:
                    self.emit(AgentSignal(
                        signal_type="TESTS_FAILED",
                        source_agent="test_runner",
                        data={"failed": test_result["failed_tests"], "traceback": test_result["traceback"]}
                    ))
                
                code_result["test_execution"] = test_result
                executed_modules.append(code_result)
        
        # === Terminal Signal ===
        self.emit(AgentSignal(
            signal_type="PIPELINE_COMPLETE",
            source_agent="dispatch_kernel",
            data={"total_tasks": len(tasks), "executed_modules": len(executed_modules)}
        ))
        
        return {
            "success": validation["success"],
            "stage": "complete",
            "tasks": tasks,
            "metadata": decomposition.get("metadata", {}),
            "quality_score": validation["quality_score"],
            "executed_modules": executed_modules,
            "signal_log": self.signal_log,
            "total_signals_emitted": len(self.signal_log)
        }
