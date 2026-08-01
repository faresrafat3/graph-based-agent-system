# Context Curator Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/context_curator.py` |
| Public Entrypoint | `curate_context(...)` |
| Graph | `context_curator_graph` |
| Status | Implemented |
| Primary Role | Sanitize raw context and compact history logs |

## Responsibility Boundary

The Context Curator prepares text context for downstream agents. It does not decompose requirements, generate code, assign tasks, execute code, or approve quality.

## Permissions

```python
CONTEXT_CURATOR_PERMISSIONS = {
    "READ": ["raw_state", "history_logs", "memory_entries", "raw_requirements"],
    "WRITE": ["sanitized_context", "context_summary", "signal_to_noise_ratio"],
    "NEVER": ["source_code_edit", "execute_deployment", "credentials_access"],
    "HUMAN_CHECKPOINT": ["context_window_overflow", "unrecoverable_context_rot"]
}
```

## Input Contract

```python
raw_prompt: str
history_logs: list[dict] | None = None
max_token_budget: int = 4000
thread_id: str = "curator_session"
```

## Output Contract

```python
{
  "sanitized_prompt": str,
  "compacted_summary": str,
  "signal_to_noise_ratio": float,
  "success": bool
}
```

## Full Lifecycle

### Propose

- Inspect raw prompt.
- Check forbidden credential override instruction.
- Initialize sanitation fields.

### Execute

- Remove obvious tracebacks.
- Collapse excessive whitespace.
- Compact recent history logs to a small summary.
- Calculate signal-to-noise ratio.

### Evaluate

- Estimate token count by character approximation.
- Pass only when prompt is non-empty and within budget.

### Commit

- Mark sanitized context ready for downstream use.

### Refine

- Truncate raw prompt and retry if budget is exceeded.

### Escalate

- Escalate after repeated context budget failures.

## Failure Modes

| Failure | Result |
|---|---|
| Empty prompt | `success=False` |
| Oversized prompt | refine/truncate |
| Credential override phrase | permission error |
| Repeated overflow | escalation |

## Tests

- `tests/test_context_curator.py`

## Usage

```python
from agents.context_curator import curate_context

result = curate_context("Build a dashboard", max_token_budget=1000)
```

## Improvement Plan

- Add tokenizer-backed budget estimation.
- Add secret redaction.
- Add structured context sections.
- Add domain-aware sanitation profiles.
