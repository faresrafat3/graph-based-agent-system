# Task Decomposer Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/task_decomposer.py` |
| Public Entrypoint | `decompose_requirements(...)` |
| Graph | `task_decomposer_graph` |
| Status | Implemented |
| Primary Role | Convert sanitized requirements into structured task JSON |

## Responsibility Boundary

The Task Decomposer owns task creation only. It must not generate source code, deploy systems, access credentials, or design full architecture beyond task descriptions.

## Permissions

```python
TASK_DECOMPOSER_PERMISSIONS = {
    "READ": ["requirements", "project_context", "constraints"],
    "WRITE": ["tasks", "metadata", "clarifications_needed"],
    "NEVER": ["code", "architecture_design", "deployment", "credentials"],
    "HUMAN_CHECKPOINT": ["vague_requirements", "ambiguous_scope"]
}
```

## Input Contract

```python
requirements: str
project_context: str = ""
constraints: str = ""
thread_id: str = "default_session"
```

## Output Contract

```python
{
  "tasks": list[dict],
  "metadata": dict,
  "clarifications_needed": list[str],
  "success": bool
}
```

## Task Schema

```json
{
  "id": "task_1",
  "title": "...",
  "description": "...",
  "type": "feature|architecture|requirements|testing|bugfix|refactor",
  "priority": "high|medium|low",
  "dependencies": [],
  "estimated_effort": "small|medium|large|xlarge",
  "assigned_system": "pm|architect|developer|reviewer|tester",
  "acceptance_criteria": ["..."]
}
```

## Full Lifecycle

### Propose

- Check hard permission blockers.
- Search memory for similar successful decompositions.
- If high-confidence match exists, set `use_cached=True`.
- Otherwise parse requirements using MCP tools.

### Execute

- If cached output is available, return it directly.
- Otherwise build a Stepfun prompt.
- Call LLM through approved gateway.
- Extract JSON deterministically.
- Normalize assigned systems.
- Run dependency analysis.

### Evaluate

- Check circular dependencies.
- Estimate coverage of requirement keywords.
- Validate assigned systems.
- Fail if clarifications are needed.

### Commit

- Save successful decomposition to memory.

### Refine

- Clear tasks and retry.

### Escalate

- Escalate after repeated decomposition failures.

## Failure Modes

| Failure | Result |
|---|---|
| Forbidden production-delete/deployment instruction | permission error |
| Invalid LLM JSON | clarification failure |
| Low coverage | retry/refine |
| Circular dependency | validation failure |
| Vague request | clarification needed |

## Tests

- `tests/test_task_decomposer.py`
- `tests/test_karpathy_pipeline.py`

## Usage

```python
from agents.task_decomposer import decompose_requirements

result = decompose_requirements("Build login with email authentication")
```

## Improvement Plan

- Shared JSON parser.
- Structured validation feedback.
- Stronger multilingual coverage checks.
- Better ambiguity detection.
