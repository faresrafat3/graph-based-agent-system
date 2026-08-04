# Decision & Conflict Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/decision_conflict_agent.py` |
| Status | Implemented |
| Primary Role | Resolve conflicts between agent outputs or recommendations |

## Responsibility Boundary

This agent applies governance rules to disputes. It must not breach the Constitution, grant unauthorized permissions, or hide unresolved conflicts.

## Proposed Permissions

```python
DECISION_CONFLICT_PERMISSIONS = {
    "READ": ["agent_disputes", "constitution_rules", "tradeoff_logs"],
    "WRITE": ["conflict_resolutions", "binding_decisions"],
    "NEVER": ["breach_constitution", "grant_unauthorized_permissions"],
    "HUMAN_CHECKPOINT": ["unresolvable_architectural_dispute"]
}
```

## Proposed Input Contract

```python
agent_disputes: list[dict]
constitution_rules: dict
tradeoff_logs: list[dict]
```

## Proposed Output Contract

```python
{
  "success": bool,
  "binding_decisions": list[dict],
  "unresolved_conflicts": list[dict]
}
```

## Lifecycle

### Propose

- Classify conflict type.

### Execute

- Apply Constitution/Laws priority rules.

### Evaluate

- Ensure decision does not breach boundaries.

### Commit

- Publish binding decision.

### Refine

- Request missing evidence.

### Escalate

- Escalate unresolved disputes to human review.

## Required Tests

- Security vs speed conflict.
- Architecture conflict.
- Missing evidence escalation.
- Permission-boundary protection.
