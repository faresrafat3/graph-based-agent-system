# Progress Monitor Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/progress_monitor.py` |
| Status | Implemented |
| Primary Role | Monitor graph execution progress, stalls, retries, and timeouts |

## Responsibility Boundary

The Progress Monitor observes and reports. It must not modify generated code, override validations, or bypass permissions.

## Proposed Permissions

```python
PROGRESS_MONITOR_PERMISSIONS = {
    "READ": ["active_graph_state", "agent_logs", "timeouts", "execution_plan"],
    "WRITE": ["progress_metrics", "stalled_task_flags", "health_report"],
    "NEVER": ["modify_code", "override_permissions", "force_success"],
    "HUMAN_CHECKPOINT": ["unresponsive_agent_execution", "system_timeout"]
}
```

## Proposed Input Contract

```python
active_graph_state: dict
agent_logs: list[dict]
timeouts: dict
execution_plan: list[dict]
```

## Proposed Output Contract

```python
{
  "success": bool,
  "progress_metrics": dict,
  "stalled_tasks": list[str],
  "breaches": list[str]
}
```

## Lifecycle

### Propose

- Identify expected running/completed tasks from execution plan.

### Execute

- Compute durations, retries, blocked tasks, and completion percentage.

### Evaluate

- Fail if tasks exceed timeout, graph is deadlocked, or required events are missing.

### Commit

- Publish progress report.

### Refine

- Request retry or reroute recommendation.

### Escalate

- Escalate unresponsive execution or system timeout.

## Required Tests

- Healthy execution plan.
- Stalled task detection.
- Timeout detection.
- Deadlock detection.

## Implementation Notes

This agent should be deterministic and should not call the LLM.
