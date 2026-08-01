# API Squad Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_squads.py` |
| Class | `APISquadAgent` |
| Method | `execute_api_task(...)` |
| Status | Implemented |
| Primary Role | Generate REST/API route and payload validation artifacts |

## Responsibility Boundary

The API Squad handles routing, controllers, request/response logic, and payload validation. It must not perform database migrations, UI styling, or password hashing internals.

## Boundary Rules

Allowed evidence includes:

- API
- route
- endpoint
- controller
- REST
- HTTP
- Pydantic

Forbidden evidence includes:

- database migration
- CSS styling
- React component
- bcrypt hashing

## Input Contract

```python
task: dict
global_context: str = ""
```

## Output Contract

```python
{
  "squad": "api",
  "task_id": str,
  "response": str,
  "success": bool
}
```

## Full Lifecycle

### Boundary Enforcement

- Reject forbidden cross-domain evidence.
- Require API-domain evidence.

### Context Preparation

- Use `APIContextManager`.

### Execute

- Call Stepfun with API-specific system prompt.

### Evaluate

Current evaluation is boundary-level only. A future dispatcher should parse and validate generated route code.

### Commit

- Return raw response and metadata.

## Tests

- `tests/test_domain_squads.py`

## Usage

```python
from agents.domain_squads import APISquadAgent

result = APISquadAgent().execute_api_task(task, global_context="FastAPI service")
```

## Improvement Plan

- Pydantic schema validation checks.
- Route naming conventions.
- Error-response consistency checks.
- Integration with generated DB/auth modules.
