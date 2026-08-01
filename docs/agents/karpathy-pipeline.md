# Karpathy Pipeline Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/karpathy_pipeline.py` |
| Public Entrypoint | `run_karpathy_pipeline(...)` |
| Status | Implemented |
| Primary Role | Integrate implemented agents into a full pipeline |

## Responsibility Boundary

The pipeline orchestrates agents. It should not hide failures, invent fallback outputs, or bypass validation/assignment gates.

## Input Contract

```python
requirements: str
project_context: str = ""
constraints: str = ""
history_logs: list | None = None
execute_code: bool = False
dispatch_domains: bool = False
orchestrate_graph: bool = False
max_retries: int = 3
```

## Output Contract

```python
{
  "stage": "complete",
  "success": bool,
  "tasks": list[dict],
  "metadata": dict,
  "quality_score": float,
  "final_quality_score": float,
  "violations": list[str],
  "refinement_attempts": int,
  "context_signal_to_noise": float,
  "agent_assignments": dict,
  "execution_plan": list[dict],
  "assignment_success": bool,
  "domain_dispatch": dict,
  "graph_execution": dict,
  "quality_review": dict,
  "executed_modules": list[dict]
}
```

## Full Lifecycle

### Stage 1: Context Curator

- Sanitize requirements.
- Fail if context cannot be prepared.

### Stage 2: Task Decomposer

- Convert requirements into tasks.

### Stage 3: Deterministic Validator

- Strictly validate task output.

### Stage 4: Surgical Refiner Loop

- If validation fails, create targeted correction instructions and retry decomposition.

### Stage 5: Agent Assigner

- Build assignments and execution plan.

### Stage 6: Optional Graph Execution Orchestrator

- If `orchestrate_graph=True`, execute execution-plan groups through Resource Priority, optional Domain Dispatcher, Integration, Progress Monitor, and Quality Reviewer fan-in.

### Stage 7: Optional Domain Dispatcher

- If `dispatch_domains=True` and graph orchestration is not enabled, dispatch implemented domain-squad tasks from the execution plan.
- Parse domain squad JSON outputs with the shared JSON parser.

### Stage 8: Optional Code Executor/Test Runner

- If `execute_code=True`, generate and test selected modules.

### Stage 8: Quality Reviewer

- Review validation, assignment, optional dispatch, optional execution, and acceptance evidence.
- Reject final success when deterministic quality evidence fails.

### Final Report

- Return combined success, tasks, assignments, execution plan, quality review, violations, and executed modules.

## Current Success Definition

```text
validation.success
AND
assignment.success
```

## Tests

- `tests/test_karpathy_pipeline.py`
- `tests/test_benchmarks.py`

## Usage

```python
from agents.karpathy_pipeline import run_karpathy_pipeline

result = run_karpathy_pipeline("Build a task management app")
```

## Improvement Plan

- Validate domain-dispatched code packages immediately after parsing.
- Add Quality Reviewer.
- Add Integration Agent.
- Execute DAG groups through graph fan-out/fan-in.
- Add human approval branch before high-risk code execution.
