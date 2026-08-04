# Agent Assigner Agent Lifecycle

## Identity

| Field | Value |
|---|---|
| Module | `agents/agent_assigner.py` |
| Public Entrypoint | `assign_tasks(...)` |
| Graph | `agent_assigner_graph` |
| Status | Implemented |
| Primary Role | Route validated tasks to specialized agents and build a DAG execution plan |

## Responsibility Boundary

The Agent Assigner assigns and schedules only. It does not run tasks, generate code, alter task content, or call an LLM.

## Permissions

```python
AGENT_ASSIGNER_PERMISSIONS = {
    "READ": ["tasks", "task_dependencies", "agent_capabilities"],
    "WRITE": ["assignments", "execution_plan", "routing_breaches"],
    "NEVER": ["source_code", "credentials", "deployment", "database_access"],
    "HUMAN_CHECKPOINT": ["unknown_domain_task", "conflicting_agent_roles"]
}
```

## Input Contract

```python
tasks: list[dict]
thread_id: str = "assigner_session"
```

## Output Contract

```python
{
  "success": bool,
  "assignments": dict[str, dict],
  "execution_plan": list[dict],
  "breaches": list[str]
}
```

## Full Lifecycle

### Propose

- Validate task structure with the deterministic validator engine.

### Execute

- Detect task domain from deterministic keywords.
- Classify task to one execution agent.
- Build topological execution plan.
- Compute `parallel_group` levels.

### Evaluate

- Ensure every task is assigned.
- Ensure every task appears in execution plan.
- Validate assigned agent names.
- Enforce squad domain boundaries.

### Commit

- Mark assignment and DAG plan ready for downstream orchestration.

### Refine

- Since assignment is deterministic, refinement does not mutate plan.
- Retry once for graph compatibility.

### Escalate

- Escalate invalid schemas, unknown dependencies, cycles, or cross-domain breaches.

## Routing Table

| Evidence | Assigned Agent |
|---|---|
| requirements or pm | ProductManagerAgent |
| architecture or architect | ArchitectAgent |
| testing or tester | TestRunnerAgent |
| reviewer | ReviewerAgent |
| auth/security/JWT/login/OAuth | AuthSquadAgent |
| database/schema/migration/sql | DatabaseSquadAgent |
| API/route/endpoint/REST | APISquadAgent |
| UI/frontend/react/CSS | UISquadAgent |
| generic implementation | CodeExecutorAgent |

## Tests

- `tests/test_agent_assigner.py`
- Pipeline assertions in `tests/test_karpathy_pipeline.py`

## Usage

```python
from agents.agent_assigner import assign_tasks

assignment = assign_tasks(validated_tasks)
```

## Improvement Plan

- Resource-aware scheduling.
- Critical path analysis.
- Direct LangGraph fan-out/fan-in from `parallel_group`.
- Human checkpoint for ambiguous multi-domain tasks.
