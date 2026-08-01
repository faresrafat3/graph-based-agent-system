# Deterministic Validator Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/deterministic_validator.py` |
| Public Entrypoint | `validate_output(...)` |
| Graph | `deterministic_validator_graph` |
| Status | Implemented |
| Primary Role | Validate output structures without LLM calls |

## Responsibility Boundary

The validator reports validity only. It does not mutate target output, approve exceptions, or generate replacement content.

## Permissions

```python
DETERMINISTIC_VALIDATOR_PERMISSIONS = {
    "READ": ["target_output", "expected_schema", "invariant_rules"],
    "WRITE": ["validation_report", "quality_score", "violations"],
    "NEVER": ["modify_target_output", "grant_exceptions", "bypass_schema"],
    "HUMAN_CHECKPOINT": ["fatal_schema_corruption"]
}
```

## Input Contract

```python
target_output: Any
required_keys: list[str] | None = None
thread_id: str = "validator_session"
```

## Output Contract

```python
{
  "quality_score": float,
  "violations": list[str],
  "validation_report": dict,
  "success": bool
}
```

## Full Lifecycle

### Propose

- Reject null target output.
- Initialize empty violations and baseline score.

### Execute

- Validate top-level required keys.
- Validate strict task schema.
- Validate enum values.
- Detect duplicates.
- Validate dependencies.
- Detect cycles.
- Validate metadata consistency.

### Evaluate

- Pass only when score is high enough and violations list is empty.

### Commit

- Mark validation report complete.

### Refine

- Increment retry count for loop compatibility.
- Does not alter invalid output.

### Escalate

- Escalate when target output remains invalid.

## Failure Modes

| Failure | Result |
|---|---|
| Missing required key | violation |
| Invalid enum | violation |
| Unknown dependency | violation |
| Circular dependency | violation |
| Metadata mismatch | violation |

## Tests

- `tests/test_deterministic_validator.py`

## Usage

```python
from agents.deterministic_validator import validate_output

report = validate_output(payload)
```

## Improvement Plan

- Structured violation objects.
- Severity levels.
- JSON path locations.
- Schema versioning.
