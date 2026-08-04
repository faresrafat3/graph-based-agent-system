# System Lifecycle Documentation

## Purpose

This document describes the full lifecycle of the Graph-Based Agent System as one coordinated product: how requirements enter, how context is prepared, how tasks are generated, validated, assigned, optionally executed, reviewed, observed, and improved.

Use this document for:

- Architecture planning
- Operational runbooks
- Future feature development
- Debugging failed pipeline runs
- Quality reviews
- Agent integration planning
- Onboarding new contributors

---

## System Identity

| Field | Value |
|---|---|
| System Name | Graph-Based Agent System |
| Primary Goal | Reliable multi-agent orchestration for software-building workflows |
| Orchestration Model | LangGraph state machines and deterministic routing |
| LLM Policy | Stepfun-only production LLM gateway |
| Validation Policy | Zero-LLM deterministic validation |
| Governance | Constitution + Laws + permission boundaries |
| Current Execution Model | Sequential pipeline with deterministic DAG assignment output |
| Future Execution Model | DAG fan-out/fan-in with quality gates and human checkpoints |

---

## System-Level Principles

1. **Think before acting**: every pipeline stage prepares, validates, and routes before execution.
2. **Simplicity first**: agents are small, specialized, and explicit.
3. **Surgical changes**: failed outputs receive targeted correction instructions.
4. **Goal-driven execution**: success is measured by deterministic reports, not model self-assessment.
5. **Fail loudly**: missing credentials, schema failures, unsafe code, or boundary breaches must surface clearly.
6. **No synthetic success**: production paths must not invent successful LLM outputs.
7. **Security before autonomy**: generated-code execution is constrained and should move to container isolation before broad untrusted usage.
8. **Everything testable**: each implemented agent has unit/integration tests.

---

## Current System Lifecycle

```text
User Requirements
  ↓
Environment and Configuration Load
  ↓
Context Curator
  ↓
Task Decomposer
  ↓
Deterministic Validator
  ↓
Surgical Refiner Loop if Needed
  ↓
Agent Assigner
  ↓
Optional Graph Execution Orchestrator
  ↓
Optional Code Executor
  ↓
Optional Test Runner
  ↓
Quality Reviewer
  ↓
Final Pipeline Report
  ↓
Memory / Snapshot / Future Improvement
```

---

## Stage 0 — Environment and Configuration

### Inputs

- `.env` or process environment
- `STEPFUN_BASE_URL`
- `STEPFUN_API_KEY`
- `STEPFUN_MODEL`
- Python dependencies from `requirements.txt`

### Checks

- Stepfun key must be present and not placeholder text.
- Unsupported provider markers are blocked by policy audit.
- Missing dependencies fail CI/test execution.

### Outputs

- Configured Stepfun LLM gateway
- LangGraph runtime dependencies
- Test and coverage tooling

### Failure Modes

| Failure | Behavior |
|---|---|
| Missing Stepfun key | `StepfunConfigurationError` when LLM is called |
| Placeholder Stepfun key | `StepfunConfigurationError` |
| Network/API failure | `StepfunAPIError`, retry only for transient failures |
| Unsupported provider marker | policy audit fails |

---

## Stage 1 — Context Curation

### Agent

- [Context Curator](agents/context-curator.md)

### Purpose

Prepare raw requirements for downstream agents by removing obvious noise and measuring context signal quality.

### Inputs

```python
requirements: str
history_logs: list[dict] | None
max_token_budget: int
```

### Outputs

```python
sanitized_prompt: str
compacted_summary: str
signal_to_noise_ratio: float
success: bool
```

### Quality Gate

- Sanitized prompt must be non-empty.
- Estimated token count must be within configured budget.

### Failure Behavior

- Retry by truncating noisy context.
- Escalate if context cannot be recovered.

---

## Stage 2 — Task Decomposition

### Agent

- [Task Decomposer](agents/task-decomposer.md)

### Purpose

Convert sanitized requirements into structured tasks.

### Inputs

```python
requirements: str
project_context: str
constraints: str
```

### Outputs

```python
tasks: list[dict]
metadata: dict
clarifications_needed: list[str]
success: bool
```

### Quality Gate

Task Decomposer local checks must pass enough for initial success, then strict validation happens in Stage 3.

### Failure Behavior

- Invalid JSON creates clarification failure.
- Vague requirements create clarification requests.
- Repeated failure triggers escalation.

---

## Stage 3 — Deterministic Validation

### Agent

- [Deterministic Validator](agents/deterministic-validator.md)

### Purpose

Reject malformed or inconsistent task outputs without using an LLM.

### Checks

- top-level keys
- full task schema
- enum values
- duplicate task IDs
- unknown dependencies
- self-dependencies
- circular dependencies
- metadata count consistency

### Outputs

```python
quality_score: float
breaches: list[str]
validation_report: dict
success: bool
```

### Quality Gate

Success requires:

```text
quality_score >= 0.8
AND
breaches == []
```

---

## Stage 4 — Surgical Refinement Loop

### Agent

- [Surgical Refiner](agents/surgical-refiner.md)

### Purpose

When validation fails, generate precise correction instructions.

### Loop

```text
Validation failure
  ↓
Generate surgical feedback
  ↓
Re-run Task Decomposer with correction instructions
  ↓
Re-run Deterministic Validator
  ↓
Repeat up to retry budget
```

### Quality Gate

Feedback must contain:

```text
SURGICAL CORRECTION REQUIRED
```

---

## Stage 5 — Agent Assignment and DAG Planning

### Agent

- [Agent Assigner](agents/agent-assigner.md)

### Purpose

Route validated tasks to specialized agents and build a deterministic DAG execution plan.

### Outputs

```python
assignments: dict[str, dict]
execution_plan: list[dict]
breaches: list[str]
success: bool
```

### Success Gate

Pipeline success currently requires:

```text
validation.success == True
AND
assignment.success == True
```

### Execution Plan Shape

```json
{
  "task_id": "task_2",
  "assigned_agent": "APISquadAgent",
  "domain": "api",
  "depends_on": ["task_1"],
  "parallel_group": 1,
  "priority": "high",
  "rationale": "api domain implementation task"
}
```

---

## Stage 6 — Optional Graph Execution Orchestration

### Agent

- [Graph Execution Orchestrator](agents/graph-execution-orchestrator.md)

### Purpose

Execute `execution_plan` groups through a deterministic graph lifecycle, coordinating resource priority, optional domain dispatch, progress monitoring, integration, and quality review.

### Current Policy

- Disabled by default: `orchestrate_graph=False`
- Can be enabled with or without domain dispatch.
- Produces `graph_execution` report in pipeline output.

---

## Stage 7 — Optional Code Generation

### Agent

- [Code Executor](agents/code-executor.md)

### Purpose

Generate Python source and pytest code for selected tasks.

### Current Policy

- Disabled by default: `execute_code=False`
- Only first few tasks are executed when enabled
- Generated package must pass filename, source syntax, test syntax, and security checks

### Failure Behavior

- Invalid package returns `success=False`
- Unsafe filename or invalid tests fail package validation
- Surgical refinement attempts are bounded

---

## Stage 8 — Optional Test Execution

### Agent

- [Test Runner](agents/test-runner.md)

### Purpose

Compile and run generated source/tests in a constrained local harness.

### Important Security Limitation

The current harness is defensive, not a full kernel/container sandbox. Broad untrusted code execution should require a container or VM backend.

---

## Stage 9 — Optional Domain Dispatch

### Agents

- [Domain Context Managers](agents/domain-context-managers.md)
- [Domain Dispatcher](agents/domain-dispatcher.md)
- [Auth Squad Agent](agents/auth-squad-agent.md)
- [Database Squad Agent](agents/database-squad-agent.md)
- [API Squad Agent](agents/api-squad-agent.md)
- [UI Squad Agent](agents/ui-squad-agent.md)

### Current State

Domain squads are implemented as specialized agents and boundaries are enforced. The main pipeline can optionally dispatch execution-plan items to implemented domain squads with `dispatch_domains=True`.

### Dispatch Flow

```text
execution_plan
  ↓
dependency check
  ↓
dispatch by assigned_agent
  ↓
domain context filtering
  ↓
squad execution
  ↓
shared JSON parser
  ↓
parsed domain outputs
```

### Next Integration Target

Add immediate code-package validation and Quality Reviewer gating after domain dispatch.

---

## Stage 10 — Memory and Session Handoff

### Components

- `memory/custom_memory.py`
- `memory/session_state_merger.py`

### Current Behavior

- Short-term memory is in-process dictionary storage.
- Long-term memory is in-process list storage.
- Session snapshots include code modules, hashes, and AST summaries.

### Future Direction

- Persistent JSONL memory.
- Snapshot manifests.
- Physical file checksum verification.
- Improved similarity search.

---

## Stage 11 — Observability and CI

### Current CI

The workflow now runs:

```bash
python -m compileall llm agents memory tools benchmarks tests scripts main.py
python scripts/audit_stepfun_policy.py
pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

### Local Commands

```bash
make compile
make audit
make test
make coverage
make ci
```

### Current Verified Baseline

```text
75 passed
coverage >= 80
Stepfun-only audit passed
```

---

## Current System Output Contract

`run_karpathy_pipeline(...)` returns:

```python
{
  "stage": "complete",
  "success": bool,
  "tasks": list[dict],
  "metadata": dict,
  "quality_score": float,
  "final_quality_score": float,
  "breaches": list[str],
  "refinement_attempts": int,
  "context_signal_to_noise": float,
  "agent_assignments": dict,
  "execution_plan": list[dict],
  "assignment_success": bool,
  "domain_dispatch": dict,
  "graph_execution": dict,
  "quality_review": dict,
  "executed_modules": list[dict]
}
```

---

## System Failure Taxonomy

| Category | Example | Handling |
|---|---|---|
| Configuration | missing Stepfun key | fail loudly |
| Context | oversized/noisy prompt | refine/truncate/escalate |
| LLM Output | invalid JSON | clarification/refinement |
| Schema | missing task key | deterministic breach |
| Dependency | cycle or unknown task | deterministic breach |
| Assignment | cross-domain routing | deterministic breach |
| Code Package | invalid filename/test syntax | package failure |
| Execution | pytest failure/timeout | execution failure report |
| Security | env/network/subprocess attempt | preflight rejection |

---

## System Development Roadmap

### Immediate Next Step

Validate parsed domain-dispatched code packages immediately after dispatch and feed accepted artifacts into the Integration Agent.

### Next Quality Gate

Expand Quality Reviewer evidence checks to include integration manifests and structured security reports.

### Next Security Upgrade

Add container-backed execution backend.

### Next Memory Upgrade

Persistent memory and snapshot manifests.

### Next Orchestration Upgrade

Execute `parallel_group` DAG stages through LangGraph fan-out/fan-in.

---

## System Definition of Done

A system-level feature is complete only when:

- It has explicit lifecycle documentation.
- It has permission boundaries or uses a component with existing boundaries.
- It has deterministic validation.
- It has tests for success and failure.
- It does not introduce unsupported provider routing.
- It does not add a production response fallback path.
- It passes compile, audit, tests, and coverage threshold.
