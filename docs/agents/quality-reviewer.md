# Quality Reviewer Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/quality_reviewer.py` |
| Status | Implemented |
| Primary Role | Enforce final quality gates across validation, execution, security, and acceptance evidence |

## Responsibility Boundary

The Quality Reviewer approves or rejects. It must not generate code, patch artifacts, or override failed deterministic checks.

## Proposed Permissions

```python
QUALITY_REVIEWER_PERMISSIONS = {
    "READ": ["validation_reports", "execution_results", "acceptance_criteria", "security_reports"],
    "WRITE": ["approval_status", "quality_report", "rejection_reasons"],
    "NEVER": ["bypass_tests", "force_commit_failed_code", "modify_artifacts"],
    "HUMAN_CHECKPOINT": ["critical_quality_gate_failure"]
}
```

## Proposed Input Contract

```python
validation_reports: list[dict]
execution_results: list[dict]
acceptance_criteria: list[str]
security_reports: list[dict]
```

## Proposed Output Contract

```python
{
  "approved": bool,
  "quality_score": float,
  "rejection_reasons": list[str],
  "success": bool
}
```

## Lifecycle

### Propose

- Collect quality evidence.

### Execute

- Compute deterministic aggregate quality score.

### Evaluate

- Require no critical violations.
- Require passing tests when execution is requested.
- Require acceptance criteria evidence.

### Commit

- Publish approval report.

### Refine

- Send targeted rejection reasons to upstream agents.

### Escalate

- Escalate critical or ambiguous quality failures.

## Required Tests

- All gates pass.
- Failed tests block approval.
- Critical security violation blocks approval.
- Missing acceptance evidence blocks approval.

## Implementation Notes

Evaluation must be deterministic and must not use the LLM.
