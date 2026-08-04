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
    "WRITE": ["validation_report", "quality_score", "breaches"],
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
  "breaches": list[str],
  "validation_report": dict,
  "success": bool
}
```

## Full Lifecycle

### Propose

- Reject null target output.
- Initialize empty breaches and baseline score.

### Execute

- Validate top-level required keys.
- Validate strict task schema.
- Validate enum values.
- Detect duplicates.
- Validate dependencies.
- Detect cycles.
- Validate metadata consistency.

### Evaluate

- Pass only when score is high enough and breaches list is empty.

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
| Missing required key | breach |
| Invalid enum | breach |
| Unknown dependency | breach |
| Circular dependency | breach |
| Metadata mismatch | breach |

## Tests

- `tests/test_deterministic_validator.py`

## Usage

```python
from agents.deterministic_validator import validate_output

report = validate_output(payload)
```

## Improvement Plan

- Structured breach objects.
- Severity levels.
- JSON path locations.
- Schema versioning.
