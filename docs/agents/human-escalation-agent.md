# Human Escalation Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/human_escalation.py` |
| Status | Implemented |
| Primary Role | Pause automation and collect human decisions at critical checkpoints |

## Responsibility Boundary

The Human Escalation Agent presents options and records decisions. It must not auto-approve, bypass human response, or mutate blocked state without a decision.

## Proposed Permissions

```python
HUMAN_ESCALATION_PERMISSIONS = {
    "READ": ["escalation_reason", "blocked_state", "available_options"],
    "WRITE": ["human_decision_log", "resume_signal"],
    "NEVER": ["bypass_human_response", "auto_approve_checkpoints"],
    "HUMAN_CHECKPOINT": ["always_active"]
}
```

## Proposed Input Contract

```python
escalation_reason: str
blocked_state: dict
available_options: list[str]
```

## Proposed Output Contract

```python
{
  "requires_human": bool,
  "decision": str | None,
  "resume_signal": dict | None,
  "success": bool
}
```

## Lifecycle

### Propose

- Summarize blocked condition.

### Execute

- Present structured options.

### Evaluate

- Validate human decision is one of the allowed options.

### Commit

- Persist decision log and resume signal.

### Refine

- Request clarification if decision is invalid.

### Escalate

- Remain active until valid human input is provided.

## Required Tests

- Valid approval.
- Rejection.
- Invalid option rejected.
- Missing decision keeps checkpoint active.
