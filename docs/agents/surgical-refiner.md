# Surgical Refiner Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/surgical_refiner.py` |
| Public Entrypoint | `generate_refinement_feedback(...)` |
| Graph | `surgical_refiner_graph` |
| Status | Implemented |
| Primary Role | Convert deterministic breaches into targeted correction instructions |

## Responsibility Boundary

The Surgical Refiner writes feedback only. It does not validate, execute, or fully regenerate outputs.

## Permissions

```python
SURGICAL_REFINER_PERMISSIONS = {
    "READ": ["validation_report", "breaches", "previous_output"],
    "WRITE": ["surgical_feedback", "pinpoint_corrections"],
    "NEVER": ["regenerate_entire_system", "override_validation_report"],
    "HUMAN_CHECKPOINT": ["persistent_unsolvable_breaches"]
}
```

## Input Contract

```python
breaches: list[str]
previous_output: Any | None = None
thread_id: str = "refiner_session"
```

## Output Contract

```python
{
  "surgical_feedback": str,
  "target_keys_to_fix": list[str],
  "success": bool
}
```

## Full Lifecycle

### Propose

- Inspect validation breaches.
- Extract target keys from quoted breach strings.

### Execute

- Generate concise correction instructions.
- Include invariant phrase: `SURGICAL CORRECTION REQUIRED`.

### Evaluate

- Ensure feedback is non-empty and contains invariant phrase.

### Commit

- Mark feedback ready for retry prompt.

### Refine

- Retry feedback creation if invariant is missing.

### Escalate

- Escalate after persistent failure.

## Tests

- `tests/test_surgical_refiner.py`

## Usage

```python
from agents.surgical_refiner import generate_refinement_feedback

feedback = generate_refinement_feedback(["Missing mandatory schema key: 'metadata'"])
```

## Improvement Plan

- Use structured breaches.
- Include JSON path pointers.
- Generate patch-style instructions.
