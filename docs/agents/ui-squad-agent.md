# UI Squad Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_squads.py` |
| Class | `UISquadAgent` |
| Method | `execute_ui_task(...)` |
| Status | Implemented |
| Primary Role | Generate UI/frontend component artifacts |

## Responsibility Boundary

The UI Squad handles frontend layout, components, views, HTML/CSS/JS/React-style artifacts. It must not implement database, token, hashing, or backend security logic.

## Boundary Rules

Allowed evidence includes:

- UI
- frontend
- component
- layout
- view
- React
- CSS
- HTML

Forbidden evidence includes:

- raw SQL
- database index
- JWT token
- bcrypt hashing

## Input Contract

```python
task: dict
global_context: str = ""
```

## Output Contract

```python
{
  "squad": "ui",
  "task_id": str,
  "response": str,
  "success": bool
}
```

## Full Lifecycle

### Boundary Enforcement

- Reject backend/security/database evidence.
- Require UI-domain evidence.

### Context Preparation

- Use `UIContextManager`.

### Execute

- Call Stepfun with UI-specific prompt.

### Evaluate

Current evaluation is boundary-level only. Future work should validate UI artifact format and tests.

### Commit

- Return raw response and metadata.

## Tests

- `tests/test_domain_squads.py`

## Usage

```python
from agents.domain_squads import UISquadAgent

result = UISquadAgent().execute_ui_task(task, global_context="Dashboard app")
```

## Improvement Plan

- UI test generation checks.
- Accessibility validation.
- Component boundary rules.
- Separate frontend package validator.
