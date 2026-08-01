# Code Executor Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/code_executor.py` |
| Public Entrypoint | `execute_task(...)` |
| Status | Implemented |
| Primary Role | Generate Python code packages and validate them before execution |

## Responsibility Boundary

The Code Executor generates source and tests. It must not deploy, modify production configuration, perform database migrations, or handle credentials.

## Permissions

```python
CODE_EXECUTOR_PERMISSIONS = {
    "READ": ["task_specification", "project_context", "file_structure"],
    "WRITE": ["source_code", "test_code", "file_structure"],
    "NEVER": ["credentials", "deployment", "database_migrations", "production_config"],
    "HUMAN_CHECKPOINT": ["security_critical_code", "payment_logic", "auth_bypass"]
}
```

## Input Contract

```python
task: dict
project_context: str = ""
max_retries: int = 3
```

## Output Contract

```python
{
  "success": bool,
  "filename": str,
  "code": str,
  "test_filename": str,
  "test_code": str,
  "imports_required": list[str],
  "description": str,
  "code_metrics": dict,
  "code_violations": list[str],
  "test_valid": bool,
  "test_violations": list[str],
  "violations": list[str],
  "refinement_attempts": int
}
```

## Full Lifecycle

### Propose

- Check task text against NEVER boundaries.
- Build code generation prompt from task and acceptance criteria.

### Execute

- Call Stepfun through approved gateway.
- Request strict JSON code package.

### Extract

- Remove markdown fences if present.
- Extract JSON object.
- Pull filename, code, test filename, test code, imports, and description.

### Evaluate

- Validate source filename.
- Validate test filename.
- Parse source code with AST.
- Parse test code with AST.
- Check basic dangerous patterns.

### Refine

- If validation fails, request surgical package correction with exact violations.

### Commit

- Return package only; do not write to repository files.

## Failure Modes

| Failure | Result |
|---|---|
| Task hits NEVER permission | fail immediately |
| Invalid LLM JSON | `success=False` |
| Invalid source syntax | validation failure |
| Invalid test syntax | package failure |
| Unsafe filename | package failure |
| Risky pattern | package failure |

## Tests

- `tests/test_code_executor.py`

## Usage

```python
from agents.code_executor import execute_task

package = execute_task(task, project_context="Python service")
```

## Improvement Plan

- Dedicated code package validator module.
- Import allowlist.
- More complete static security analysis.
- Support multiple language backends with separate validators.
