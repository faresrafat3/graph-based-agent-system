# Database Squad Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_squads.py` |
| Class | `DatabaseSquadAgent` |
| Method | `execute_db_task(...)` |
| Status | Implemented |
| Primary Role | Generate database schema/model/migration artifacts |

## Responsibility Boundary

The Database Squad handles schemas, models, migrations, SQL structures, tables, and indexing strategies. It must not generate UI components, JWT logic, or HTTP routing.

## Boundary Rules

Allowed evidence includes:

- database
- schema
- migration
- model
- SQL
- table
- index

Forbidden evidence includes:

- React component
- JSX
- CSS
- JWT token
- HTTP router

## Input Contract

```python
task: dict
global_context: str = ""
```

## Output Contract

```python
{
  "squad": "database",
  "task_id": str,
  "response": str,
  "success": bool
}
```

## Full Lifecycle

### Boundary Enforcement

- Scan task text.
- Reject unrelated domains.
- Require database evidence.

### Context Preparation

- Use `DBContextManager`.
- Keep DB-relevant descriptions/specs.

### Execute

- Call Stepfun with database-specific prompt.

### Evaluate

Current evaluation is boundary-level only. Downstream package validation should parse and validate returned JSON.

### Commit

- Return raw response and metadata.

## Tests

- `tests/test_domain_squads.py`

## Usage

```python
from agents.domain_squads import DatabaseSquadAgent

result = DatabaseSquadAgent().execute_db_task(task, global_context="PostgreSQL app")
```

## Improvement Plan

- 3NF validator.
- Migration safety validator.
- Destructive SQL detection.
- Schema compatibility checks.
