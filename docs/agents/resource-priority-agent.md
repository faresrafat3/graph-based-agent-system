# Resource & Priority Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/resource_priority_agent.py` |
| Status | Implemented |
| Primary Role | Manage request budgets, task priority, and execution ordering |

## Responsibility Boundary

This agent schedules resources. It must not disable rate limits, exceed hard budgets, or approve unsafe work.

## Proposed Permissions

```python
RESOURCE_PRIORITY_PERMISSIONS = {
    "READ": ["token_usage", "api_rate_limits", "queue_priority", "execution_plan"],
    "WRITE": ["rate_limit_actions", "queue_order", "deferred_tasks"],
    "NEVER": ["exceed_hard_budget", "disable_rate_limiters"],
    "HUMAN_CHECKPOINT": ["request_budget_exhaustion"]
}
```

## Proposed Input Contract

```python
token_usage: dict
api_rate_limits: dict
queue: list[dict]
execution_plan: list[dict]
```

## Proposed Output Contract

```python
{
  "success": bool,
  "queue_order": list[str],
  "rate_limit_actions": list[str],
  "deferred_tasks": list[str]
}
```

## Lifecycle

### Propose

- Inspect current budgets and queued work.

### Execute

- Reorder queue by priority and dependency readiness.

### Evaluate

- Ensure no budget or rate-limit breach.

### Commit

- Publish queue order and deferrals.

### Refine

- Defer low-priority work or reduce scope.

### Escalate

- Escalate exhausted budgets.

## Required Tests

- High priority first.
- Dependency-ready ordering.
- Budget exhaustion.
- Rate-limit deferral.
