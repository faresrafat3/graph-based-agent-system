# Graph Execution Orchestrator Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/graph_execution_orchestrator.py` |
| Public Entrypoint | `orchestrate_graph_execution(...)` |
| Graph | `graph_execution_orchestrator_graph` |
| Status | Implemented |
| Primary Role | Execute a DAG execution plan group-by-group and fan-in governance reports |

## Responsibility Boundary

The Graph Execution Orchestrator coordinates existing deterministic agents and optional domain dispatch. It does not directly call LLMs, deploy systems, access credentials, or override validation failures.

## Permissions

```python
GRAPH_EXECUTION_ORCHESTRATOR_PERMISSIONS = {
    "READ": ["tasks", "execution_plan", "global_context", "resource_budgets"],
    "WRITE": ["graph_execution_report", "completed_task_ids", "group_results"],
    "NEVER": ["credentials", "deployment", "production_environment", "provider_override"],
    "HUMAN_CHECKPOINT": ["blocked_graph_dependencies", "quality_gate_failure", "resource_exhaustion"]
}
```

## Input Contract

```python
tasks: list[dict]
execution_plan: list[dict]
global_context: str = ""
dispatch_domains: bool = False
token_usage: dict | None = None
api_rate_limits: dict | None = None
timeout_seconds: int = 300
thread_id: str = "graph_execution_orchestrator_session"
```

## Output Contract

```python
{
  "success": bool,
  "graph_execution_report": dict,
  "completed_task_ids": list[str],
  "group_results": list[dict],
  "dispatch_result": dict,
  "integration_result": dict,
  "progress_report": dict,
  "quality_review": dict,
  "breaches": list[str]
}
```

## Full Lifecycle

### Propose

- Validate `tasks` and `execution_plan` containers.

### Execute

- Group plan items by `parallel_group`.
- Use Resource & Priority Agent for each group.
- If `dispatch_domains=True`, dispatch ready items to Domain Dispatcher.
- If dispatch is disabled, mark ready plan items as planned/completed.
- Fan-in parsed domain outputs into Integration Agent.
- Fan-in task logs into Progress Monitor.
- Fan-in evidence into Quality Reviewer.

### Evaluate

- Success requires no breaches and passing integration, progress, and quality reports.

### Commit

- Return final graph execution report.

### Refine

- Deterministic orchestrator does not auto-repair graph failures.

### Escalate

- Escalate dependency blocks, resource exhaustion, or quality gate failures.

## Failure Modes

| Failure | Result |
|---|---|
| Incomplete dependency | graph breach |
| Resource budget exhausted | graph breach |
| Domain dispatch parse failure | graph breach |
| Integration conflict | graph breach |
| Progress failure | graph breach |
| Quality rejection | graph breach |

## Tests

- `tests/test_graph_execution_orchestrator.py`
- Optional pipeline path in `tests/test_karpathy_pipeline.py`

## Usage

```python
from agents.graph_execution_orchestrator import orchestrate_graph_execution

result = orchestrate_graph_execution(
    tasks=tasks,
    execution_plan=execution_plan,
    dispatch_domains=True,
)
```

## Improvement Plan

- Replace group loop with true dynamic LangGraph fan-out/fan-in branches.
- Run independent domain tasks concurrently where runtime supports it.
- Feed accepted artifacts into container-backed test execution.
- Add human escalation when graph execution blocks.
