# Domain Context Managers Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/domain_context_managers.py` |
| Classes | `BaseDomainContextManager`, `AuthContextManager`, `DBContextManager`, `APIContextManager`, `UIContextManager` |
| Status | Implemented |
| Primary Role | Create isolated domain-specific context windows |

## Responsibility Boundary

Domain Context Managers filter context only. They do not call LLMs, generate code, validate generated code, or execute tasks.

## Input Contract

```python
global_prompt: str
domain_specific_data: str = ""
```

Specialized methods:

```python
filter_auth_context(global_prompt, schemas="")
filter_db_context(global_prompt, db_specs="")
```

## Output Contract

```python
{
  "domain": str,
  "filtered_context": str,
  "signal_to_noise_ratio": float,
  "success": bool
}
```

## Full Lifecycle

### Prepare

- Sanitize global prompt using Context Curator logic.

### Filter

- Add domain-specific data.
- Remove known irrelevant noise for specialized managers.

### Budget

- Truncate to domain token budget approximation.

### Return

- Return filtered context with signal-to-noise ratio.

## Tests

- `tests/test_domain_context_managers.py`

## Usage

```python
from agents.domain_context_managers import AuthContextManager

ctx = AuthContextManager().filter_auth_context(global_prompt, schemas="User schema")
```

## Improvement Plan

- Tokenizer-backed budgets.
- Domain scoring.
- Structured context sections.
- Secret redaction.
