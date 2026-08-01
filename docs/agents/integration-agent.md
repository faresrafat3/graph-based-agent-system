# Integration Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/integration_agent.py` |
| Status | Implemented |
| Primary Role | Merge validated artifacts into a coherent integration manifest |

## Responsibility Boundary

The Integration Agent creates manifests and detects conflicts. It must not deploy, bypass validation, or execute unverified bundles.

## Proposed Permissions

```python
INTEGRATION_AGENT_PERMISSIONS = {
    "READ": ["software_agent_artifacts", "module_exports", "test_reports"],
    "WRITE": ["integration_manifest", "conflict_report"],
    "NEVER": ["deploy_untested_bundle", "override_security_blocks"],
    "HUMAN_CHECKPOINT": ["major_integration_conflict"]
}
```

## Proposed Input Contract

```python
software_agent_artifacts: list[dict]
module_exports: dict
test_reports: list[dict]
```

## Proposed Output Contract

```python
{
  "success": bool,
  "integration_manifest": dict,
  "conflicts": list[str]
}
```

## Lifecycle

### Propose

- Inventory modules, tests, exports, and dependencies.

### Execute

- Build integration manifest.
- Detect filename/import collisions.

### Evaluate

- Require no collisions or missing modules.

### Commit

- Emit final manifest.

### Refine

- Request targeted artifact renames or dependency fixes.

### Escalate

- Escalate unresolved integration conflicts.

## Required Tests

- Clean manifest generation.
- Filename collision detection.
- Missing module detection.
- Conflicting export detection.
