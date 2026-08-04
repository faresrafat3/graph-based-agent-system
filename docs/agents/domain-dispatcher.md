# Domain Dispatcher Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_dispatcher.py` |
| Public Entrypoint | `dispatch_domain_tasks(...)` |
| Status | Implemented |
| Primary Role | Execute execution-plan items routed to implemented domain squad agents |

## Responsibility Boundary

The Domain Dispatcher dispatches only implemented domain squad tasks. It does not invent outputs, does not execute unsupported agents, does not bypass dependencies, and does not approve generated code quality.

## Permissions

```python
DOMAIN_DISPATCHER_PERMISSIONS = {
    "READ": ["tasks", "execution_plan", "global_context", "completed_task_ids"],
    "WRITE": ["dispatch_results", "parsed_outputs", "dispatch_breaches"],
    "NEVER": ["deployment", "credentials", "production_environment"],
    "HUMAN_CHECKPOINT": ["blocked_dependencies", "unsupported_agent", "squad_boundary_breach"]
}
```

## Input Contract

```python
tasks: list[dict]
execution_plan: list[dict]
global_context: str = ""
completed_task_ids: set[str] | None = None
max_tasks: int | None = None
```

## Output Contract

```python
{
  "success": bool,
  "results": list[dict],
  "parsed_outputs": dict[str, dict],
  "breaches": list[str],
  "skipped_tasks": list[str],
  "blocked_tasks": list[str],
  "completed_task_ids": list[str]
}
```

## Full Lifecycle

### Prepare

- Index tasks by task id.
- Sort execution plan deterministically by parallel group, priority, and task id.
- Initialize completed task set from `completed_task_ids`.

### Dependency Check

- Before dispatching a task, verify all `depends_on` ids are completed.
- Block task if dependencies are incomplete.

### Dispatch

- If assigned agent is one of the implemented domain squads, call the matching squad method.
- If assigned agent is not implemented by this dispatcher, mark the task as skipped and completed for incremental adoption.

### Parse

- Parse raw squad LLM response through shared JSON parser.
- Require code-package keys: `filename`, `code`, `test_filename`, `test_code`.

### Evaluate

- Success requires squad execution success and JSON parse success.
- Parse failures and dependency blocks become explicit breaches.

### Commit

- Add successfully dispatched task ids to completed set.
- Return parsed outputs keyed by task id.

## Failure Modes

| Failure | Result |
|---|---|
| Unknown task in execution plan | dispatch failure |
| Incomplete dependency | blocked task |
| Squad boundary exception | dispatch breach |
| Non-JSON squad response | parse breach |
| Missing required output key | parse breach |

## Tests

- `tests/test_domain_dispatcher.py`
- Optional pipeline path in `tests/test_karpathy_pipeline.py`

## Usage

```python
from agents.domain_dispatcher import dispatch_domain_tasks

result = dispatch_domain_tasks(tasks, execution_plan, global_context="FastAPI app")
```

## Improvement Plan

- Add support for non-domain planned agents once implemented.
- Validate parsed code packages immediately after parsing.
- Execute DAG parallel groups through LangGraph fan-out/fan-in.
- Feed outputs into Quality Reviewer and Integration Agent.
