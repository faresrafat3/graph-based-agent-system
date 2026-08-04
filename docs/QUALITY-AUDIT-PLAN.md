# Quality Audit & Hardening Plan

## Objective

Raise the system quality bar after adopting the Stepfun-only LLM policy by removing silent success paths, strengthening deterministic validation, and reducing risk around generated-code execution.

---

## Phase 1 — LLM Gateway Hardening

Status: Implemented

- Keep Stepfun as the only production LLM provider.
- Keep missing credentials/API failures fail-loud.
- Sanitize direct LLM text payloads at the gateway.
- Add bounded retry/backoff for transient Stepfun failures only.
- Log safe request metadata without credentials.

Validation:

- Unit tests monkeypatch the HTTP boundary.
- No alternate-provider routing remains.
- No production response fallback exists.

---

## Phase 2 — Generated-Code Execution Safety

Status: Implemented as a defensive local harness

- Validate generated filenames before writing files.
- Reject absolute paths, nested paths, and path traversal.
- Clean subprocess environment to avoid leaking secrets.
- Apply subprocess timeout and best-effort OS resource limits.
- Reject common risky runtime patterns before physical execution:
  - external network libraries
  - subprocess execution
  - dynamic eval/exec/import
  - environment reads
  - host filesystem access
  - destructive operations
  - unsafe modules such as ctypes/pickle/multiprocessing

Important limitation:

- The Test Runner is not a kernel/container security sandbox. Fully untrusted code should still run inside a container or VM boundary.

---

## Phase 3 — Code Executor Package Validation

Status: Implemented

- Treat generated code and generated tests as one package.
- Require source filename, test filename, code syntax, and test syntax to pass.
- Mark package failure if tests are invalid, even when source code is valid.
- Preserve surgical-refinement behavior with exact deterministic breaches.

---

## Phase 4 — Strict Deterministic Output Validation

Status: Implemented

- Validate full task schema:
  - id
  - title
  - description
  - type
  - priority
  - dependencies
  - estimated_effort
  - assigned_system
  - acceptance_criteria
- Validate allowed enum values.
- Validate dependency references.
- Detect self-dependencies and circular dependencies.
- Validate metadata count consistency against physical task list.

---

## Phase 5 — Agent Boundary Improvements

Status: Implemented

- Strengthen Domain Squad Law 20 enforcement.
- Scan task id/title/description/type, not title only.
- Enforce allowed-domain evidence and forbidden cross-domain keywords for Auth, DB, API, and UI squads.

---

## Phase 6 — Correctness Fixes

Status: Implemented

- Fix Task Decomposer cache path so high-confidence memory matches can short-circuit LLM execution.
- Fix MCP requirements parser so lowercase `api` and `ui` are detected correctly.
- Store `code_modules` in session snapshots so verified state can actually be restored/merged.

---

## Phase 7 — Agent Assigner & DAG Routing

Status: Implemented

- Add Karpathy Meta-Agent #2: Agent Assigner.
- Route validated tasks deterministically without LLM calls.
- Detect task domain while preserving architecture/requirements/testing precedence.
- Enforce Law 20 before routing to domain squads.
- Build topological DAG execution plans with deterministic `parallel_group` values.
- Integrate assignment results into the main pipeline output.

---

## Phase 8 — Domain Dispatcher & Shared JSON Parser

Status: Implemented

- Add shared deterministic JSON object parser for LLM-produced JSON.
- Reuse shared parser in Code Executor extraction.
- Add Domain Dispatcher for execution-plan items routed to implemented domain squads.
- Enforce dependency completion before dispatching a domain task.
- Parse squad raw responses and surface missing/invalid JSON as explicit breaches.
- Add optional pipeline flag `dispatch_domains=True`.

---

## Phase 9 — Remaining Governance Agents

Status: Implemented

- Add Progress Monitor for deterministic graph execution health checks.
- Add Quality Reviewer as deterministic global approval gate and integrate it into the main pipeline.
- Add Integration Agent for artifact manifest construction and conflict detection.
- Add Decision & Conflict Agent for governance-priority dispute resolution.
- Add Resource & Priority Agent for queue ordering and budget exhaustion checks.
- Add Human Escalation Agent for explicit checkpoint decision modeling.

---

## Phase 10 — Graph Execution Orchestration

Status: Implemented

- Add Graph Execution Orchestrator over Agent Assigner DAG plans.
- Process execution plans by deterministic `parallel_group` batches.
- Coordinate Resource & Priority, optional Domain Dispatcher, Integration, Progress Monitor, and Quality Reviewer.
- Add optional pipeline flag `orchestrate_graph=True`.
- Add explicit graph execution reports to final pipeline output.

---

## Phase 11 — Distributed Governance Checks & Agent Registry

Status: Implemented

- Add canonical `AGENT_REGISTRY` for implemented agents and lifecycle artifacts.
- Add distributed governance check suite to enforce methodology compliance without centralizing decision authority.
- Verify lifecycle docs, tests, public entrypoints, permission matrices, imports, and no LLM calls in `evaluate` functions.
- Add CI governance check gate.

---

## Verification Commands

```bash
python -m compileall llm agents memory tools benchmarks tests scripts system main.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --cov=. --cov-report=term-missing --cov-fail-under=80 -q
python scripts/audit_stepfun_policy.py
python scripts/audit_governance.py
```

Latest verification result:

- Test suite: 120 passed
- Coverage: 88%
- Provider-rerouting audit: clean
- Distributed governance checks: clean

---

## Remaining Future Work

- Run generated code in a real container/VM sandbox before enabling broad untrusted execution.
- Add centralized structured logging for all agent stage transitions.
- Add explicit Stepfun request budget/rate-limit manager for high-volume production use.
- Expand integration tests for `execute_code=True` in a hardened CI sandbox.
