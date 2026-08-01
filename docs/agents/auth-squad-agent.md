# Auth Squad Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_squads.py` |
| Class | `AuthSquadAgent` |
| Method | `execute_auth_task(...)` |
| Status | Implemented |
| Primary Role | Generate authentication/security-focused code artifacts |

## Responsibility Boundary

The Auth Squad handles authentication, authorization-adjacent logic, JWT/OAuth/password flows, and security-focused code generation. It must not perform UI styling, database migrations, or unrelated API/database work.

## Boundary Rules

Allowed evidence includes:

- auth
- authentication
- security
- JWT
- login
- OAuth
- password

Forbidden evidence includes:

- CSS
- JSX
- React component
- database migration
- raw SQL index

## Input Contract

```python
task: dict
global_context: str = ""
```

## Output Contract

```python
{
  "squad": "auth",
  "task_id": str,
  "response": str,
  "success": bool
}
```

## Full Lifecycle

### Boundary Enforcement

- Scan task id/title/description/type.
- Reject forbidden cross-domain keywords.
- Require auth-domain evidence.

### Context Preparation

- Use `AuthContextManager`.
- Strip obvious UI/CSS noise.

### Execute

- Call Stepfun via `call_llm` with auth-specific system prompt.

### Evaluate

Current evaluation is boundary-level only. Generated output should be parsed and validated by downstream code package validators in the next integration phase.

### Commit

- Return raw LLM response and metadata.

## Tests

- `tests/test_domain_squads.py`

## Usage

```python
from agents.domain_squads import AuthSquadAgent

result = AuthSquadAgent().execute_auth_task(task, global_context="Auth service")
```

## Improvement Plan

- Shared JSON parsing.
- Auth-specific static security checks.
- Password hashing and token safety validators.
- Rate-limit requirement enforcement.
