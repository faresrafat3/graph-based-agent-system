# Agent Lifecycle Documentation

## Purpose

This document is the canonical lifecycle reference for every agent in the Graph-Based Agent System. It is intended for:

- Day-to-day usage
- System planning
- New agent development
- Future refactoring and quality improvements
- Permission-boundary reviews
- Testing and CI maintenance
- Human escalation and operational handoff

The core rule is simple: **an agent is not complete unless its lifecycle is explicit, testable, deterministic where possible, and governed by the Constitution and Laws.**

---

## Global Agent Lifecycle Standard

Every agent SHOULD be documented and implemented according to this lifecycle model.

```text
Identity
  ↓
Permission Boundary
  ↓
Input Contract
  ↓
Context Preparation
  ↓
Propose
  ↓
Execute
  ↓
Evaluate
  ↓
Commit or Refine
  ↓
Escalate if needed
  ↓
Observability + Tests + Future Improvement
```

### Lifecycle Phases

| Phase | Meaning | LLM Allowed? | Deterministic Required? |
|---|---|---:|---:|
| Identity | Defines the agent name, purpose, owner module, and responsibility | No | Yes |
| Permission Boundary | Defines READ/WRITE/NEVER/HUMAN_CHECKPOINT | No | Yes |
| Input Contract | Defines expected inputs and validation requirements | No | Yes |
| Context Preparation | Sanitizes and filters context before any LLM call | No preferred; deterministic sanitation | Yes |
| Propose | Builds a plan or hypothesis | Sometimes | Prefer deterministic when possible |
| Execute | Performs the primary work | Sometimes | Depends on agent |
| Evaluate | Validates output against hard criteria | No | Yes, always |
| Commit | Persists or returns accepted output | No | Yes |
| Refine | Applies targeted correction | Sometimes | Validation remains deterministic |
| Escalate | Stops automation and surfaces human decision point | No | Yes |
| Observe | Logs metrics, quality, and failures safely | No | Yes |
| Test | Unit/integration/security tests | No | Yes |

### Universal Rules

1. **Single responsibility**: each agent owns one clear job.
2. **No silent success**: failures must be visible in returned state or raised exceptions.
3. **No LLM-as-judge**: evaluation must be deterministic.
4. **Stepfun-only LLM gateway**: any LLM invocation must go through the approved Stepfun integration path.
5. **No fallback response path**: production code must not synthesize successful LLM outputs.
6. **Surgical refinement only**: failed outputs should be corrected precisely, not regenerated blindly.
7. **Permission boundaries before action**: NEVER/HUMAN_CHECKPOINT rules must be checked before execution.
8. **Tests are lifecycle artifacts**: each implemented lifecycle must have tests.

---

## Agent Inventory

### Implemented Agents and Engines

| Agent / Engine | Module | Status | Primary Role |
|---|---|---:|---|
| Context Curator | `agents/context_curator.py` | Implemented | Sanitize and compact context |
| Task Decomposer | `agents/task_decomposer.py` | Implemented | Convert requirements into structured tasks |
| Deterministic Validator | `agents/deterministic_validator.py` | Implemented | Validate task outputs without LLMs |
| Surgical Refiner | `agents/surgical_refiner.py` | Implemented | Generate targeted correction instructions |
| Agent Assigner | `agents/agent_assigner.py` | Implemented | Route tasks to agents and build DAG plans |
| Code Executor | `agents/code_executor.py` | Implemented | Generate code packages through LLM and validate syntax/security |
| Test Runner | `agents/test_runner_agent.py` | Implemented | Execute generated code/tests in constrained local harness |
| Domain Context Managers | `agents/domain_context_managers.py` | Implemented | Isolate subsystem context windows |
| Domain Dispatcher | `agents/domain_dispatcher.py` | Implemented | Dispatch execution-plan items to implemented domain squads |
| Graph Execution Orchestrator | `agents/graph_execution_orchestrator.py` | Implemented | Execute DAG groups and fan-in governance reports |
| Auth Squad Agent | `agents/domain_squads.py` | Implemented | Auth/security code generation boundary |
| Database Squad Agent | `agents/domain_squads.py` | Implemented | Database/schema code generation boundary |
| API Squad Agent | `agents/domain_squads.py` | Implemented | API route/payload code generation boundary |
| UI Squad Agent | `agents/domain_squads.py` | Implemented | UI/component generation boundary |
| Karpathy Pipeline | `agents/karpathy_pipeline.py` | Implemented | Integrates implemented agents into pipeline |

### Planned Meta-Agents

| Agent | Status | Intended Role |
|---|---:|---|
| Progress Monitor | Implemented | Monitor execution health, timeouts, and stuck states |
| Quality Reviewer | Implemented | Enforce global quality gates |
| Integration Agent | Implemented | Merge artifacts into cohesive system bundles |
| Decision & Conflict Agent | Implemented | Resolve cross-agent conflicts |
| Resource & Priority Agent | Implemented | Manage token budgets, rate limits, and execution priority |
| Human Escalation Agent | Implemented | Present critical decisions to humans and resume safely |

---

# Implemented Agent Lifecycles

---

## 1. Context Curator Agent

### Identity

- **Module**: `agents/context_curator.py`
- **Public entrypoint**: `curate_context(...)`
- **Graph object**: `context_curator_graph`
- **Primary responsibility**: sanitize raw user/context payloads and compact history logs.

### Responsibility Boundary

The Context Curator prepares context. It does **not** decompose requirements, assign tasks, generate code, validate schemas, or execute tests.

### Permission Boundary

```python
CONTEXT_CURATOR_PERMISSIONS = {
    "READ": ["raw_state", "history_logs", "memory_entries", "raw_requirements"],
    "WRITE": ["sanitized_context", "context_summary", "signal_to_noise_ratio"],
    "NEVER": ["source_code_edit", "execute_deployment", "credentials_access"],
    "HUMAN_CHECKPOINT": ["context_window_overflow", "unrecoverable_context_rot"]
}
```

### Input Contract

```python
raw_prompt: str
history_logs: list[dict] | None
max_token_budget: int
thread_id: str
```

### Output Contract

```python
{
  "sanitized_prompt": str,
  "compacted_summary": str,
  "signal_to_noise_ratio": float,
  "success": bool
}
```

### Lifecycle

#### Propose

- Reads `raw_prompt`.
- Checks permission invariants.
- Initializes output placeholders.

#### Execute

Uses `ContextCuratorEngine`:

- `sanitize_raw_text`: removes noisy tracebacks and excessive whitespace.
- `compact_history_logs`: keeps recent logs concise.
- `calculate_signal_to_noise`: computes retained signal ratio.

#### Evaluate

- Estimates token usage by character count.
- Requires sanitized text to fit `max_token_budget`.
- Requires sanitized text to be non-empty.

#### Commit

- Marks context as committed and ready for downstream agents.

#### Refine

- Truncates prompt when budget is exceeded.
- Retries up to the configured loop threshold.

#### Escalate

Escalates when context cannot fit budget or sanitation cannot recover a usable prompt.

### Deterministic Validation

All evaluation is deterministic. No LLM calls occur in this agent.

### Failure Modes

| Failure | Behavior |
|---|---|
| Empty raw prompt | Fails evaluation |
| Oversized prompt | Refines/truncates then retries |
| Credential override attempt | Raises permission error |
| Persistent overflow | Escalates |

### Tests

- `tests/test_context_curator.py`

### Usage Example

```python
from agents.context_curator import curate_context

result = curate_context(
    raw_prompt="Build dashboard...",
    history_logs=[{"action": "init", "status": "ok"}],
    max_token_budget=1000,
)
```

### Future Improvements

- Tokenizer-backed budget estimation.
- Structured context sections with priorities.
- Domain-aware context sanitation.
- Redaction of high-risk secrets before logging or LLM routing.

---

## 2. Task Decomposer Agent

### Identity

- **Module**: `agents/task_decomposer.py`
- **Public entrypoint**: `decompose_requirements(...)`
- **Graph object**: `task_decomposer_graph`
- **Primary responsibility**: convert natural-language requirements into structured task JSON.

### Responsibility Boundary

The Task Decomposer creates task definitions only. It does not write source code, deploy systems, or perform architecture implementation.

### Permission Boundary

```python
TASK_DECOMPOSER_PERMISSIONS = {
    "READ": ["requirements", "project_context", "constraints"],
    "WRITE": ["tasks", "metadata", "clarifications_needed"],
    "NEVER": ["code", "architecture_design", "deployment", "credentials"],
    "HUMAN_CHECKPOINT": ["vague_requirements", "ambiguous_scope"]
}
```

### Input Contract

```python
requirements: str
project_context: str = ""
constraints: str = ""
thread_id: str = "default_session"
```

### Output Contract

```python
{
  "tasks": list[dict],
  "metadata": dict,
  "clarifications_needed": list[str],
  "success": bool
}
```

### Expected Task Schema

```json
{
  "id": "task_1",
  "title": "...",
  "description": "...",
  "type": "feature|architecture|requirements|testing|bugfix|refactor",
  "priority": "high|medium|low",
  "dependencies": [],
  "estimated_effort": "small|medium|large|xlarge",
  "assigned_system": "pm|architect|developer|reviewer|tester",
  "acceptance_criteria": ["..."]
}
```

### Lifecycle

#### Propose

- Checks NEVER permission triggers.
- Searches long-term memory for similar decompositions.
- If a high-confidence memory match exists, sets `use_cached=True` and returns cached tasks.
- Otherwise, parses requirements through MCP tools.

#### Execute

- If `use_cached=True`, short-circuits LLM execution and returns cached output.
- Otherwise, builds a Stepfun prompt and calls the LLM through `call_llm`.
- Extracts JSON deterministically.
- Normalizes `assigned_system` values.
- Runs dependency analysis for circular dependencies.

#### Evaluate

- Checks dependency cycles.
- Estimates coverage by matching requirements keywords against task titles/descriptions.
- Checks valid assigned systems.
- Fails when clarifications remain.

#### Commit

- Stores successful decomposition in memory.

#### Refine

- Clears current tasks.
- Increments retry count.
- Re-enters propose/execute.

#### Escalate

Escalates when task decomposition fails repeatedly.

### Deterministic Validation

Local evaluation is heuristic. Strict output validation is performed downstream by `DeterministicValidator`.

### Failure Modes

| Failure | Behavior |
|---|---|
| Production delete/deployment instruction | Raises permission error |
| Invalid LLM JSON | Returns clarification failure |
| Circular dependency | Adds clarification/breach |
| Low coverage | Refines/retries |
| Vague requirements | Returns clarifications |

### Tests

- `tests/test_task_decomposer.py`
- Pipeline coverage through `tests/test_karpathy_pipeline.py`

### Usage Example

```python
from agents.task_decomposer import decompose_requirements

result = decompose_requirements(
    requirements="Build login page with email authentication",
    project_context="Web app",
    constraints="Use React",
)
```

### Future Improvements

- Replace simple coverage heuristic with normalized token scoring.
- Add bilingual requirement parsing support.
- Move JSON extraction into a shared parser utility.
- Use structured validation report feedback during refinement.

---

## 3. Deterministic Validator Agent

### Identity

- **Module**: `agents/deterministic_validator.py`
- **Public entrypoint**: `validate_output(...)`
- **Graph object**: `deterministic_validator_graph`
- **Primary responsibility**: validate output structures with zero LLM calls.

### Responsibility Boundary

The validator only reads and reports. It does not mutate target output, grant exceptions, or bypass schema rules.

### Permission Boundary

```python
DETERMINISTIC_VALIDATOR_PERMISSIONS = {
    "READ": ["target_output", "expected_schema", "invariant_rules"],
    "WRITE": ["validation_report", "quality_score", "breaches"],
    "NEVER": ["modify_target_output", "grant_exceptions", "bypass_schema"],
    "HUMAN_CHECKPOINT": ["fatal_schema_corruption"]
}
```

### Input Contract

```python
target_output: Any
required_keys: list[str] | None
thread_id: str
```

### Output Contract

```python
{
  "quality_score": float,
  "breaches": list[str],
  "validation_report": dict,
  "success": bool
}
```

### Lifecycle

#### Propose

- Checks that target output exists.
- Initializes clean validation state.

#### Execute

Performs deterministic checks:

- top-level schema keys
- strict task object schema
- allowed enums
- duplicate task IDs
- dependency references
- self-dependencies
- circular dependencies
- metadata count consistency

#### Evaluate

- Passes only if quality score is above threshold and breaches are empty.

#### Commit

- Marks validation report committed.

#### Refine

- Increments retry count for graph-loop compatibility.
- Does not self-correct target output.

#### Escalate

Escalates when validation cannot pass after retry budget.

### Deterministic Validation

All validation is deterministic and local. LLM calls are forbidden in `evaluate`.

### Failure Modes

| Failure | Behavior |
|---|---|
| Missing schema key | Adds breach |
| Invalid task field | Adds breach |
| Unknown dependency | Adds breach |
| Circular dependency | Adds breach |
| Metadata mismatch | Adds breach |

### Tests

- `tests/test_deterministic_validator.py`

### Usage Example

```python
from agents.deterministic_validator import validate_output

report = validate_output(task_payload, required_keys=["tasks", "metadata"])
```

### Future Improvements

- Replace plain strings with structured `ValidationBreach` objects.
- Add severity levels.
- Add machine-readable breach codes.
- Add schema versioning.

---

## 4. Surgical Refiner Agent

### Identity

- **Module**: `agents/surgical_refiner.py`
- **Public entrypoint**: `generate_refinement_feedback(...)`
- **Graph object**: `surgical_refiner_graph`
- **Primary responsibility**: transform deterministic breaches into precise correction instructions.

### Responsibility Boundary

The Surgical Refiner does not regenerate outputs directly. It only creates targeted feedback.

### Permission Boundary

```python
SURGICAL_REFINER_PERMISSIONS = {
    "READ": ["validation_report", "breaches", "previous_output"],
    "WRITE": ["surgical_feedback", "pinpoint_corrections"],
    "NEVER": ["regenerate_entire_system", "override_validation_report"],
    "HUMAN_CHECKPOINT": ["persistent_unsolvable_breaches"]
}
```

### Input Contract

```python
breaches: list[str]
previous_output: Any | None
thread_id: str
```

### Output Contract

```python
{
  "surgical_feedback": str,
  "target_keys_to_fix": list[str],
  "success": bool
}
```

### Lifecycle

#### Propose

- Reads breaches.
- Extracts target keys from quoted breach strings.

#### Execute

- Generates instructions beginning with the invariant phrase:

```text
SURGICAL CORRECTION REQUIRED
```

#### Evaluate

- Confirms feedback is non-empty and contains the invariant phrase.

#### Commit

- Marks feedback committed.

#### Refine

- Increments retry count.

#### Escalate

Escalates after repeated inability to produce valid surgical feedback.

### Tests

- `tests/test_surgical_refiner.py`

### Usage Example

```python
from agents.surgical_refiner import generate_refinement_feedback

feedback = generate_refinement_feedback([
    "Missing mandatory schema key: 'metadata'"
])
```

### Future Improvements

- Accept structured validation breaches.
- Preserve and reference exact JSON paths.
- Generate patch-style correction instructions.

---

## 5. Agent Assigner Agent

### Identity

- **Module**: `agents/agent_assigner.py`
- **Public entrypoint**: `assign_tasks(...)`
- **Graph object**: `agent_assigner_graph`
- **Primary responsibility**: route validated tasks to specialized agents and build a deterministic DAG execution plan.

### Responsibility Boundary

The Agent Assigner assigns and schedules only. It does not execute tasks, generate code, run tests, or modify task definitions.

### Permission Boundary

```python
AGENT_ASSIGNER_PERMISSIONS = {
    "READ": ["tasks", "task_dependencies", "agent_capabilities"],
    "WRITE": ["assignments", "execution_plan", "routing_breaches"],
    "NEVER": ["source_code", "credentials", "deployment", "database_access"],
    "HUMAN_CHECKPOINT": ["unknown_domain_task", "conflicting_agent_roles"]
}
```

### Input Contract

```python
tasks: list[dict]
thread_id: str
```

Tasks are expected to have already passed strict deterministic validation.

### Output Contract

```python
{
  "success": bool,
  "assignments": dict[str, dict],
  "execution_plan": list[dict],
  "breaches": list[str]
}
```

### Assignment Output

```json
{
  "task_1": {
    "task_id": "task_1",
    "assigned_agent": "ArchitectAgent",
    "domain": "auth",
    "task_type": "architecture",
    "rationale": "architecture/design task"
  }
}
```

### Execution Plan Output

```json
[
  {
    "task_id": "task_2",
    "assigned_agent": "APISquadAgent",
    "domain": "api",
    "depends_on": ["task_1"],
    "parallel_group": 1,
    "priority": "high",
    "rationale": "api domain implementation task"
  }
]
```

### Lifecycle

#### Propose

- Validates task structure using `DeterministicValidatorEngine.validate_tasks_structure`.

#### Execute

- Classifies each task into an agent.
- Detects task domain.
- Builds topological execution plan.
- Computes deterministic `parallel_group` levels.

#### Evaluate

- Ensures every task has an assignment.
- Ensures every task appears in execution plan.
- Validates agent names.
- Enforces domain squad boundaries.

#### Commit

- Marks assignment plan ready for downstream orchestration.

#### Refine

- Increments retry count.
- Since routing is deterministic, unresolved assignment failures escalate quickly.

#### Escalate

Escalates when tasks are invalid, cyclic, unknown, or cross-domain ambiguous.

### Routing Rules

| Task Evidence | Agent |
|---|---|
| `type=requirements` or `assigned_system=pm` | ProductManagerAgent |
| `type=architecture` or `assigned_system=architect` | ArchitectAgent |
| `type=testing` or `assigned_system=tester` | TestRunnerAgent |
| `assigned_system=reviewer` | ReviewerAgent |
| auth/security/JWT/login/OAuth keywords | AuthSquadAgent |
| database/schema/migration/model/sql keywords | DatabaseSquadAgent |
| api/route/endpoint/rest/http keywords | APISquadAgent |
| ui/frontend/component/react/css keywords | UISquadAgent |
| generic implementation | CodeExecutorAgent |

### Tests

- `tests/test_agent_assigner.py`
- Pipeline integration: `tests/test_karpathy_pipeline.py`

### Usage Example

```python
from agents.agent_assigner import assign_tasks

result = assign_tasks(validated_tasks)
print(result["execution_plan"])
```

### Future Improvements

- Add resource-aware scheduling.
- Add critical-path analysis.
- Add human checkpoint for ambiguous multi-domain tasks.
- Add direct LangGraph fan-out from `parallel_group` levels.

---

## 6. Code Executor Agent

### Identity

- **Module**: `agents/code_executor.py`
- **Public entrypoint**: `execute_task(...)`
- **Primary responsibility**: generate a Python code package for a validated task and run deterministic pre-execution validation.

### Responsibility Boundary

The Code Executor generates code and tests. It does not deploy, access credentials, or modify production infrastructure.

### Permission Boundary

```python
CODE_EXECUTOR_PERMISSIONS = {
    "READ": ["task_specification", "project_context", "file_structure"],
    "WRITE": ["source_code", "test_code", "file_structure"],
    "NEVER": ["credentials", "deployment", "database_migrations", "production_config"],
    "HUMAN_CHECKPOINT": ["security_critical_code", "payment_logic", "auth_bypass"]
}
```

### Input Contract

```python
task: dict
project_context: str = ""
max_retries: int = 3
```

### Output Contract

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
  "code_breaches": list[str],
  "test_valid": bool,
  "test_breaches": list[str],
  "breaches": list[str],
  "refinement_attempts": int
}
```

### Lifecycle

#### Propose

- Checks task text against NEVER boundaries.
- Builds code-generation prompt.

#### Execute

- Calls Stepfun through `call_llm`.
- Requests strict JSON containing source and test code.

#### Extract

- Parses JSON from raw response.
- Handles markdown fences and surrounding prose.

#### Evaluate

- Validates source filename.
- Validates test filename.
- Parses source with AST.
- Parses tests with AST.
- Checks security patterns such as hardcoded secrets, `eval`, `exec`, `os.system`, and shell subprocesses.

#### Refine

- If package validation fails, requests surgical correction using exact deterministic breaches.

#### Commit

- Returns accepted code package to pipeline.
- Does not write to project files directly.

### Tests

- `tests/test_code_executor.py`

### Usage Example

```python
from agents.code_executor import execute_task

result = execute_task(task, project_context="Python service")
```

### Future Improvements

- Move code package validation into dedicated validator module.
- Add import allowlist.
- Add richer static security scanner.
- Add support for non-Python package validation through pluggable validators.

---

## 7. Test Runner Agent

### Identity

- **Module**: `agents/test_runner_agent.py`
- **Public entrypoint**: `run_code_and_tests(...)`
- **Primary responsibility**: execute generated Python source and pytest tests in a constrained temporary environment.

### Responsibility Boundary

The Test Runner executes only local generated code in a defensive harness. It does not deploy, access production environments, or execute arbitrary binaries.

### Permission Boundary

```python
TEST_RUNNER_PERMISSIONS = {
    "READ": ["source_code", "test_code", "project_structure"],
    "WRITE": ["test_reports", "execution_logs"],
    "NEVER": ["production_environment", "external_network_call", "credentials_file"],
    "HUMAN_CHECKPOINT": ["destructive_file_operations", "untrusted_binary_execution"]
}
```

### Input Contract

```python
filename: str
code: str
test_filename: str
test_code: str
timeout_seconds: int = 15
```

### Output Contract

```python
{
  "success": bool,
  "stage": str,
  "error": str | None,
  "stdout": str,
  "stderr": str,
  "passed_tests": int,
  "failed_tests": int,
  "traceback": str,
  "breaches": list[str]
}
```

### Lifecycle

#### Preflight

- Validates safe filenames.
- Rejects path traversal.
- Scans source/test code for risky patterns.
- Rejects unsafe code before execution.

#### Execute Compilation

- Writes files inside a temporary directory.
- Runs `python -I -m py_compile`.
- Uses cleaned environment.
- Applies timeout and best-effort resource limits.

#### Execute Tests

- Runs `python -I -m pytest` against generated tests.
- Counts pass/fail results.

#### Evaluate

- Success requires compile success and pytest success when tests exist.

#### Cleanup

- Removes temporary sandbox directory.

### Security Note

This is a defensive local harness, not a kernel/container sandbox. Fully untrusted code should run in a container/VM with network disabled.

### Tests

- `tests/test_test_runner_agent.py`

### Usage Example

```python
from agents.test_runner_agent import run_code_and_tests

result = run_code_and_tests(
    filename="calculator.py",
    code="def add(a, b): return a + b",
    test_filename="test_calculator.py",
    test_code="from calculator import add\ndef test_add(): assert add(2, 2) == 4",
)
```

### Future Improvements

- Docker/gVisor/nsjail backend.
- Network namespace isolation.
- Import allowlist.
- Structured execution duration metrics.

---

## 8. Domain Context Managers

### Identity

- **Module**: `agents/domain_context_managers.py`
- **Classes**:
  - `BaseDomainContextManager`
  - `AuthContextManager`
  - `DBContextManager`
  - `APIContextManager`
  - `UIContextManager`
- **Primary responsibility**: filter global context into subsystem-specific context windows.

### Responsibility Boundary

Domain Context Managers filter and sanitize context only. They do not call LLMs or generate outputs.

### Input Contract

```python
global_prompt: str
domain_specific_data: str = ""
```

### Output Contract

```python
{
  "domain": str,
  "filtered_context": str,
  "signal_to_noise_ratio": float,
  "success": bool
}
```

### Lifecycle

#### Prepare

- Sanitize global prompt using Context Curator engine.

#### Filter

- Combine sanitized global context with domain-specific details.
- Remove obvious cross-domain noise in specialized managers.

#### Budget

- Truncate context to domain token budget approximation.

#### Return

- Return filtered context and signal-to-noise ratio.

### Tests

- `tests/test_domain_context_managers.py`

### Future Improvements

- Domain-specific keyword scoring.
- Structured context sections.
- Tokenizer-backed budget enforcement.
- Shared secret redaction.

---

## 9. Domain Squad Agents

### Identity

- **Module**: `agents/domain_squads.py`
- **Agents**:
  - `AuthSquadAgent`
  - `DatabaseSquadAgent`
  - `APISquadAgent`
  - `UISquadAgent`
- **Primary responsibility**: generate domain-specific artifacts under strict squad boundaries.

### Shared Lifecycle

#### Boundary Enforcement

- `_enforce_squad_boundary` scans task id/title/description/type.
- Rejects forbidden cross-domain keywords.
- Requires allowed domain evidence.

#### Context Filtering

- Uses the matching Domain Context Manager.

#### Execute

- Calls Stepfun via `call_llm` using domain-specific system prompt.

#### Return

- Returns raw response and squad metadata.

### Shared Output Contract

```python
{
  "squad": str,
  "task_id": str,
  "response": str,
  "success": bool
}
```

### Auth Squad

- **Allowed domain**: auth, authentication, security, JWT, login, OAuth, password.
- **Forbidden examples**: CSS, JSX, database migrations, raw SQL indexes.
- **Context manager**: `AuthContextManager`.

### Database Squad

- **Allowed domain**: database, schema, migration, model, SQL, table, index.
- **Forbidden examples**: React components, JWT token logic, HTTP routing.
- **Context manager**: `DBContextManager`.

### API Squad

- **Allowed domain**: API, route, endpoint, controller, REST, HTTP, Pydantic.
- **Forbidden examples**: database migration, CSS styling, bcrypt hashing.
- **Context manager**: `APIContextManager`.

### UI Squad

- **Allowed domain**: UI, frontend, component, layout, view, React, CSS, HTML.
- **Forbidden examples**: raw SQL, JWT token logic, bcrypt hashing.
- **Context manager**: `UIContextManager`.

### Tests

- `tests/test_domain_squads.py`

### Future Improvements

- Parse squad response through shared JSON parser.
- Validate generated code packages before returning success.
- Add squad-specific deterministic validators.
- Integrate dispatcher into execution plan processing.

---

## 10. Karpathy Pipeline

### Identity

- **Module**: `agents/karpathy_pipeline.py`
- **Public entrypoint**: `run_karpathy_pipeline(...)`
- **Primary responsibility**: orchestrate implemented agents into a full processing path.

### Current Pipeline

```text
Context Curator
  ↓
Task Decomposer
  ↓
Deterministic Validator
  ↓
Surgical Refiner loop if needed
  ↓
Agent Assigner
  ↓
Optional Code Executor + Test Runner
```

### Input Contract

```python
requirements: str
project_context: str = ""
constraints: str = ""
history_logs: list | None = None
execute_code: bool = False
max_retries: int = 3
```

### Output Contract

```python
{
  "stage": "complete",
  "success": bool,
  "tasks": list[dict],
  "metadata": dict,
  "quality_score": float,
  "breaches": list[str],
  "refinement_attempts": int,
  "context_signal_to_noise": float,
  "agent_assignments": dict,
  "execution_plan": list[dict],
  "assignment_success": bool,
  "executed_modules": list[dict]
}
```

### Success Definition

Pipeline success currently requires:

```text
Deterministic validation success
AND
Agent assignment success
```

If code execution is enabled, executed modules include their own test execution results.

### Tests

- `tests/test_karpathy_pipeline.py`
- `tests/test_benchmarks.py`

### Future Improvements

- Add Domain Squad Dispatcher stage.
- Add Quality Reviewer stage.
- Add Integration Agent stage.
- Add Human Escalation checkpoints.
- Convert optional code execution into a graph branch with explicit approval.

---

# Governance Agent Lifecycle Specifications

The following governance agents now have deterministic implementations. Their standalone lifecycle documents remain the source of truth for continued development.

---

## 11. Progress Monitor Agent (Planned)

### Intended Responsibility

Monitor active graph execution, detect stalls/timeouts, and surface operational health.

### Proposed Input

```python
active_graph_state: dict
agent_logs: list[dict]
timeouts: dict
```

### Proposed Output

```python
{
  "progress_metrics": dict,
  "stalled_tasks": list[str],
  "success": bool,
  "breaches": list[str]
}
```

### Lifecycle

- **Propose**: identify tasks expected to be running or completed.
- **Execute**: compute progress metrics and timeout deltas.
- **Evaluate**: fail if tasks exceed timeout or graph is deadlocked.
- **Commit**: publish progress report.
- **Refine**: request retry or reroute.
- **Escalate**: human checkpoint for unresponsive execution.

### Future Tests

- no stalled task
- stalled task detected
- deadlock detected
- retry budget exceeded

---

## 12. Quality Reviewer Agent (Planned)

### Intended Responsibility

Enforce global quality gates across validation reports, execution results, and acceptance criteria.

### Proposed Input

```python
validation_reports: list[dict]
execution_results: list[dict]
acceptance_criteria: list[str]
```

### Proposed Output

```python
{
  "approved": bool,
  "quality_score": float,
  "rejection_reasons": list[str]
}
```

### Lifecycle

- **Propose**: collect quality evidence.
- **Execute**: compute aggregate deterministic quality score.
- **Evaluate**: require no critical breaches and passing tests.
- **Commit**: approve output.
- **Refine**: send targeted feedback to failing agents.
- **Escalate**: human checkpoint for critical quality gate failure.

### Future Tests

- all gates pass
- critical breach blocks approval
- failing tests block approval
- missing acceptance evidence blocks approval

---

## 13. Integration Agent (Planned)

### Intended Responsibility

Merge validated artifacts into a coherent system manifest.

### Proposed Input

```python
software_agent_artifacts: list[dict]
module_exports: dict
```

### Proposed Output

```python
{
  "integration_manifest": dict,
  "conflicts": list[str],
  "success": bool
}
```

### Lifecycle

- **Propose**: inventory artifacts.
- **Execute**: build integration manifest and detect collisions.
- **Evaluate**: check no filename/import conflicts.
- **Commit**: emit unified bundle manifest.
- **Refine**: request targeted artifact rename/fix.
- **Escalate**: human checkpoint for major integration conflict.

---

## 14. Decision & Conflict Agent (Planned)

### Intended Responsibility

Resolve conflicting outputs or recommendations between agents.

### Proposed Input

```python
agent_disputes: list[dict]
constitution_rules: dict
tradeoff_logs: list[dict]
```

### Proposed Output

```python
{
  "binding_decisions": list[dict],
  "unresolved_conflicts": list[dict],
  "success": bool
}
```

### Lifecycle

- **Propose**: classify conflict type.
- **Execute**: apply Constitution/Laws priority rules.
- **Evaluate**: ensure no rule breach.
- **Commit**: publish decision.
- **Refine**: request missing evidence.
- **Escalate**: unresolved architectural dispute.

---

## 15. Resource & Priority Agent (Planned)

### Intended Responsibility

Manage token budget, Stepfun request budget, task priority, and queue order.

### Proposed Input

```python
token_usage: dict
api_rate_limits: dict
queue: list[dict]
```

### Proposed Output

```python
{
  "queue_order": list[str],
  "rate_limit_actions": list[str],
  "success": bool
}
```

### Lifecycle

- **Propose**: inspect resource state.
- **Execute**: reprioritize queue.
- **Evaluate**: ensure budget constraints are not exceeded.
- **Commit**: publish queue order.
- **Refine**: reduce scope or defer low-priority work.
- **Escalate**: token or request budget exhaustion.

---

## 16. Human Escalation Agent (Planned)

### Intended Responsibility

Pause automation and present structured decision points to humans.

### Proposed Input

```python
escalation_reason: str
blocked_state: dict
available_options: list[str]
```

### Proposed Output

```python
{
  "requires_human": bool,
  "decision": str | None,
  "resume_signal": dict | None
}
```

### Lifecycle

- **Propose**: summarize blocked condition.
- **Execute**: present decision options.
- **Evaluate**: validate human decision is allowed.
- **Commit**: persist decision log.
- **Refine**: request clarification.
- **Escalate**: remains active until valid response.

---

# Development Checklist for New Agents

A new agent is not ready unless all items below are complete.

## Required Code

- [ ] Module-level docstring.
- [ ] Permission matrix.
- [ ] Typed state or explicit input/output dataclasses.
- [ ] `propose` implementation.
- [ ] `execute` implementation.
- [ ] `evaluate` implementation with no LLM calls.
- [ ] `commit` implementation.
- [ ] `refine` implementation.
- [ ] `should_continue` routing.
- [ ] Public entrypoint function.
- [ ] Tests for success, failure, boundary breaches, and edge cases.

## Required Documentation

- [ ] Identity.
- [ ] Responsibility boundary.
- [ ] Permission boundary.
- [ ] Input contract.
- [ ] Output contract.
- [ ] Full lifecycle.
- [ ] Failure modes.
- [ ] Tests.
- [ ] Usage example.
- [ ] Future improvements.

## Required Quality Gates

- [ ] `python -m compileall ...` passes.
- [ ] Unit tests pass.
- [ ] Coverage remains above threshold.
- [ ] Stepfun-only policy audit passes.
- [ ] No production fallback response path.
- [ ] No LLM call inside `evaluate`.

---

# Operational Runbook

## Standard Local Verification

```bash
make compile
make audit
make test
make coverage
```

## CI Verification

CI runs:

```bash
python -m compileall llm agents memory tools benchmarks tests scripts main.py
python scripts/audit_stepfun_policy.py
pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

## Debugging Failed Agent Output

1. Check returned `breaches`.
2. Confirm whether failure occurred in:
   - context sanitation
   - decomposition
   - validation
   - assignment
   - code generation
   - test execution
3. If validation failed, send breaches to Surgical Refiner.
4. If permission boundary failed, do not retry automatically.
5. If human checkpoint is required, stop automation.

---

# Current Next Best Improvements

1. Validate domain-dispatched code packages immediately after JSON parsing.
2. Add `QualityReviewerAgent` as a deterministic global gate.
3. Add a real container-backed execution backend for untrusted code.
4. Convert validation breach strings into structured breach objects.
5. Upgrade Graph Execution Orchestrator from group-loop execution to true runtime-parallel fan-out/fan-in.

---

# Individual Agent Documents

For focused maintenance and future development, each agent also has its own standalone lifecycle document:

- [Context Curator](agents/context-curator.md)
- [Task Decomposer](agents/task-decomposer.md)
- [Deterministic Validator](agents/deterministic-validator.md)
- [Surgical Refiner](agents/surgical-refiner.md)
- [Agent Assigner](agents/agent-assigner.md)
- [Code Executor](agents/code-executor.md)
- [Test Runner](agents/test-runner.md)
- [Domain Context Managers](agents/domain-context-managers.md)
- [Domain Dispatcher](agents/domain-dispatcher.md)
- [Graph Execution Orchestrator](agents/graph-execution-orchestrator.md)
- [Auth Squad Agent](agents/auth-squad-agent.md)
- [Database Squad Agent](agents/database-squad-agent.md)
- [API Squad Agent](agents/api-squad-agent.md)
- [UI Squad Agent](agents/ui-squad-agent.md)
- [Karpathy Pipeline](agents/karpathy-pipeline.md)
- [Progress Monitor](agents/progress-monitor.md)
- [Quality Reviewer](agents/quality-reviewer.md)
- [Integration Agent](agents/integration-agent.md)
- [Decision & Conflict Agent](agents/decision-conflict-agent.md)
- [Resource & Priority Agent](agents/resource-priority-agent.md)
- [Human Escalation Agent](agents/human-escalation-agent.md)
