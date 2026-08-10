# Constitution - Graph-Based Agent System

## Preamble

We, the builders and operators of the **Graph-Based Agent System**, establish this Constitution to govern the design, development, and operation of our multi-agent system. This Constitution is based on **Karpathy's Agentic Engineering** principles and reflects our commitment to building reliable, transparent, and ethical AI systems.

## Article I: Core Principles

### Section 1: Karpathy's Four Principles

All agents and system components **MUST** adhere to Karpathy's Four Principles.

| # | Principle | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|---|
| 1 | Think Before Acting | Analyze inputs thoroughly before acting | `propose` step in the Karpathy Loop | Validate inputs before processing | Acting without thinking MUST be flagged and corrected |
| 2 | Simplicity First | Break tasks into the minimum necessary steps | Prefer simple solutions over complex ones | Code reviews check for unnecessary complexity | Over-engineered solutions MUST be refactored |
| 3 | Surgical Changes | Modify only what is necessary | Explicit permission boundaries | Validate outputs before committing | Modifying outside scope MUST be stopped |
| 4 | Goal-Driven Execution | Work towards clear, measurable goals | Explicit success criteria per agent | Evaluate outputs against success criteria | Failing goals MUST refine and retry |

### Section 2: Permission Boundaries

All agents **MUST** declare explicit permission boundaries. Agents MUST NOT act outside
what they declare.

| Permission Class | Rule | Breach |
|---|---|---|
| READ Permissions | MUST declare what they can READ; MUST NOT read outside it | Stopped |
| WRITE Permissions | MUST declare what they can WRITE; MUST NOT write outside it | Stopped |
| NEVER Permissions | MUST declare what they can NEVER do; MUST NEVER do it | Stopped immediately |
| HUMAN_CHECKPOINT Permissions | MUST declare when human approval is needed; MUST NOT proceed without it | Stopped |

### Section 3: Failure Handling

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Fail Loudly | Fail loudly, never silently | Raise exceptions with clear error messages | All errors logged and reported | Silent failures are critical bugs |
| Surface to Human | Surface errors outside agent scope | Escalate after 3 failed retries | Escalation logged and tracked | Failure to escalate MUST be corrected |
| Never Assume | NEVER assume, always validate | Validate all inputs and outputs | Validation explicit and logged | Assumptions MUST be corrected |

## Article II: Agent Architecture

### Section 1: The Karpathy Loop

All agents **MUST** implement the Karpathy Loop:
Propose → Execute → Evaluate → Commit → Refine

| Step | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Propose | Generate a plan or hypothesis | Use memory and tools to analyze inputs | Plan validated before execution | Invalid plans MUST be refined |
| Execute | Implement the plan | Use LLM and tools to execute | Execution MUST be validated | Failed executions MUST be refined |
| Evaluate | Check if the plan worked | Validate outputs against success criteria | Evaluation explicit and logged | Invalid evaluations MUST be corrected |
| Commit | Commit if successful | Store results in memory | Commits validated and logged | Invalid commits MUST be rolled back |

#### Refine Step
- **Requirement**: Refine if failed
- **Implementation**: Adjust plan and retry
- **Validation**: Refinement MUST be logged
- **Breach**: Failed refinements MUST escalate after 3 retries

### Section 2: Agent Specialization

All agents **MUST** be specialized:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Single Responsibility | Each agent MUST have a single, well-defined responsibility | Each agent MUST do only one thing | Code reviews MUST check for single responsibility | Agents with multiple responsibilities MUST be split |
| Clear Interface | Each agent MUST have a clear interface | Each agent MUST define input and output schemas | Interfaces MUST be validated | Unclear interfaces MUST be clarified |
| Loose Coupling | Agents MUST be loosely coupled | Agents MUST communicate through state passing | Code reviews MUST check for tight coupling | Tightly coupled agents MUST be decoupled |

### Section 3: Agent Communication

All agents **MUST** communicate properly:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| State Passing | Agents MUST communicate through state passing | Use LangGraph state management | State MUST be validated before passing | Invalid state MUST be corrected |
| Explicit Dependencies | Agent dependencies MUST be explicit | Use LangGraph edges to define dependencies | Dependencies MUST be validated | Implicit dependencies MUST be made explicit |
| No Side Effects | Agents MUST NOT have side effects | Agents MUST only modify their output state | Code reviews MUST check for side effects | Agents with side effects MUST be corrected |

## Article III: System Architecture

### Section 1: LangGraph Orchestration

The system **MUST** use LangGraph for orchestration:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| State Management | System MUST use LangGraph state management | Define TypedDict for each agent state | State MUST be validated at each step | Invalid state MUST be corrected |
| Conditional Routing | System MUST use conditional routing | Use LangGraph conditional edges | Routing MUST be validated | Invalid routing MUST be corrected |
| Parallel Execution | System MUST support parallel execution | Use LangGraph parallel edges | Parallel execution MUST be tested | Failed parallel execution MUST be corrected |

### Section 2: LLM Integration

The system **MUST** use Stepfun as the only active LLM provider in the current production path:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Stepfun-Only Provider Policy | System MUST route all LLM calls through the Stepfun native REST integration | Use `llm.llm_integration.call_llm`, backed only by Stepfun chat completions | Tests MUST monkeypatch the Stepfun HTTP boundary rather than using production fallback responses | Adding alternate provider routing or silent dry-run fallbacks MUST be rejected |
| Fail-Loud Error Handling | System MUST fail loudly when Stepfun credentials, quota, network, or response payloads are invalid | Raise typed configuration/API exceptions with actionable messages | Error paths MUST be covered by tests | Silent fallback responses MUST be removed immediately |
| Rate Limiting | System MUST respect Stepfun rate limits | Implement rate limiting/retry controls before high-volume usage | Rate limiting MUST be tested | Rate limit breaches MUST be fixed |

### Section 3: Memory Management

The system **MUST** implement custom memory:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Short-Term Memory | System MUST maintain short-term memory | Use in-memory dictionary | Short-term memory MUST be tested | Memory leaks MUST be fixed |
| Long-Term Memory | System MUST maintain long-term memory | Use persistent storage | Long-term memory MUST be tested | Memory corruption MUST be fixed |
| Similarity Search | System MUST support similarity search | Use Jaccard similarity | Similarity search MUST be tested | Inaccurate similarity MUST be corrected |

## Article IV: Quality Assurance

### Section 1: Testing

All code **MUST** be tested:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Unit Tests | All functions MUST have unit tests | Use pytest | Coverage MUST be > 80% | Untested code MUST NOT be merged |
| Integration Tests | All agents MUST have integration tests | Test full agent workflow | Integration tests MUST pass | Failed integration tests MUST be fixed |
| Edge Case Tests | All agents MUST have edge case tests | Test edge cases and error conditions | Edge case tests MUST pass | Failed edge case tests MUST be fixed |

### Section 2: Code Review

All code **MUST** be reviewed:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Peer Review | All code MUST be reviewed by peers | Use pull requests | Reviews MUST be documented | Unreviewed code MUST NOT be merged |
| Quality Gates | All code MUST pass quality gates | Use automated checks | Quality gates MUST be enforced | Code that fails quality gates MUST NOT be merged |
| Documentation | All code MUST be documented | Use docstrings and comments | Documentation MUST be reviewed | Undocumented code MUST NOT be merged |

### Section 3: Continuous Integration

All code **MUST** use CI/CD:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Automated Testing | All tests MUST run automatically | Use CI/CD pipeline | CI/CD MUST be tested | Failed CI/CD MUST be fixed |
| Automated Deployment | All deployments MUST be automated | Use CI/CD pipeline | Deployments MUST be tested | Failed deployments MUST be rolled back |
| Continuous Monitoring | System MUST be monitored continuously | Use monitoring tools | Monitoring MUST be tested | Monitoring failures MUST be fixed |

## Article V: Ethics and Responsibility

### Section 1: Bias and Fairness

The system **MUST** be fair:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Bias Detection | System MUST detect bias | Implement bias detection tools | Bias detection MUST be tested | Biased outputs MUST be corrected |
| Fairness Validation | System MUST validate fairness | Test with diverse inputs | Fairness MUST be documented | Unfair outputs MUST be corrected |
| Transparency | System MUST be transparent | Log all decisions | Transparency MUST be tested | Opaque decisions MUST be explained |

### Section 2: Privacy and Security

The system **MUST** protect privacy:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Data Protection | System MUST protect user data | Implement data protection measures | Data protection MUST be tested | Data breaches MUST be reported |
| Access Control | System MUST control access | Implement access control | Access control MUST be tested | Unauthorized access MUST be blocked |
| Encryption | System MUST encrypt sensitive data | Use encryption | Encryption MUST be tested | Unencrypted data MUST be encrypted |

### Section 3: Accountability

The system **MUST** be accountable:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Audit Trail | System MUST maintain audit trail | Log all actions | Audit trail MUST be tested | Missing audit trail MUST be added |
| Human Oversight | System MUST have human oversight | Implement human-in-the-loop | Human oversight MUST be tested | Lack of oversight MUST be corrected |
| Responsibility | System MUST have clear responsibility | Document responsibilities | Responsibilities MUST be reviewed | Unclear responsibilities MUST be clarified |

## Article VI (PROPOSED — not yet enforced): Systems-Governance Principles

> **Status: PROPOSED.** These principles were derived from a philosophical audit
> (Hegel, Spinoza, Lao Tzu, Leibniz, Ashby, Meadows, Cynefin) reflected onto this
> system. They are recorded here for review; they become enforced only after the
> corresponding code changes are implemented and observed. (Per P7: no control
> survives unless it demonstrably catches a failure.)

### Section 1: Proposed Principles

- **P1 — Requisite Response Variety.** Every routing point MUST expose at least as many distinct outcomes as the failure modes reaching it; add outcomes before adding agents. *(Ashby)*
- **P2 — Verified Closure.** No WRITE agent returns to the orchestrator on its own report; every write edge terminates in a VERIFY node checking a postcondition declared at propose time, evaluated without an LLM. *(see DeterministicValidatorEngine.verify_execution_postcondition)*
- **P3 — Domain-Gated Governance.** Control intensity is set by the task's Cynefin domain and reversibility, never by permission class: Clear + high confidence → VERIFY only; Complicated → analysis + VERIFY; Complex → probe budget; Chaotic → immediate human. *(Snowden)*
- **P4 — Bounded Probing.** Complex work runs N attempts, each stating a NEW falsifiable hypothesis; a repeated hypothesis or exhausted budget escalates to a human with the hypothesis trail attached. *(Cynefin)*
- **P5 — Custodial Context.** Specialization stands, but every handoff MUST serialize its reasoning into graph state; context that cannot be written down is treated as nonexistent. *(Leibniz)*
- **P6 — Productive Contradiction.** Disagreement between agents is a first-class routed signal, never suppressed by last-writer-wins; only *unrecorded* contradiction is a defect. *(Hegel)*
- **P7 — Least Sufficient Intervention.** Remove any checkpoint, agent, or rule that has not changed an outcome in observed runs; justify each surviving control by the failure it demonstrably catches. *(Lao Tzu)*

> **Operationalized by:** `system/self_improvement.py` (META-SYSTEM.md) — the autonomous
> loop that measures, proposes one control per delta, and gates every change by observed
> effect. A control that changes no outcome in N cycles is flagged for removal.

### Section 1b: Reconciliation Rulings (2026-08-05, v1)

These resolve contradictions surfaced in `docs/reconciliation/METHODOLOGY-RECONCILIATION.md`
between the five governing methodologies (Karpathy, opus-5 P1–P7, Cynefin, reflexive
loops, distributed governance).

- **Ruling C1 (meta-loop authority).** The meta-loop is a *proposer only*. It never
  applies a control unilaterally. Application of any control change requires either (a) a
  reversible config/flag flip, or (b) an explicit human checkpoint. This preserves the
  distributed-governance axiom: *no supreme governor*.
  - **C1-rev1 (opus-5 live review, 2026-08-05).** The original C1 mislocated power:
    proposal-setting *is* authority (it owns the Overton window). Four hardening fixes:
    1. **Independent reversibility.** "Reversible" is judged by an *external* criterion
       (governance ledger / human), never self-assessed by the meta-loop.
    2. **Default-deny application.** The meta-loop defaults to *propose-only*; it never
       auto-applies. Application is opt-IN (human/flag), never opt-out. The human is a
       co-governor, not a bottleneck to override.
    3. **Separate streams.** The proposal stream and the apply pipeline are distinct and
       auditable; the meta-loop's observe/diagnose/frame context travels with each proposal.
    4. **Counter-proposal channel.** Any domain agent may challenge the meta-loop's framing
       (counter-proposal); the meta-loop has no interpretive monopoly.
  - **Operationalized by:** `agents/systems_layer.py` `apply_or_escalate_node` (default-deny),
    `system/distillation_ledger.py` (independent provenance + opus-5 live review entries),
    `system/counter_proposals.py` (domain-agent challenges).
- **Ruling C2 (simplicity vs growth).** Law 7 (Simplicity) permits agent growth ONLY when
  P1 (Requisite Variety) forces it — a routing point has more failure modes than outcomes.
  Every added agent must later pass P7 (demonstrably catches a failure) or be pruned.
  "Small core" = *no redundant agent*, not *few agents at all costs*.
- **Ruling C3 (LLM boundary).** Law 11 forbids LLM in the *accept/reject verdict* only.
  LLM-generated reflections are permitted as *input to propose* (tagged
  `llm_reflection_input`), never as evaluation. The verdict (pass/fail, breaches) stays
  zero-LLM.
- **Ruling C4 (Cynefin router).** The keyword `detect_task_type` is a legacy pre-filter,
  not P3. Control intensity MUST derive from a `CynefinClassifier` (domain + reversibility),
  which overrides the keyword router. (Implemented: `agents/cynefin_classifier.py`.)
- **Ruling C5 (distillation provenance).** Every principle attributed to opus-5 MUST have
  a `system/distillation_ledger.py` entry (source, date, frozen text, status). A principle
  without a ledger entry is *advisory only*, never enforced.
- **Ruling F2 (metric honesty).** `governance_score` (does the system obey its rules?) is
  reported SEPARATELY from `success_rate` (does it solve the task?). Loops improve
  governance, not necessarily capability; never conflate the two.

> **Operationalized by:** `docs/reconciliation/METHODOLOGY-RECONCILIATION.md` (full
> contradiction + fallacy analysis), `system/distillation_ledger.py`,
> `agents/cynefin_classifier.py`, `agents/systems_layer.py`.

### Section 2: What We Reject (proposed)

- **Pure generalist monads** — one agent holding all context wins on tacit continuity but loses cost, parallelism, and the per-role audit trail we need for accountability.
- **Unbounded human gating** — attention decays under volume; a human asked to approve everything approves everything, converting a safeguard into a signature.
- **Wu-wei as default** — self-organization here has no benign attractor; without declared postconditions, unmonitored agents drift and narrate success.

### Section 3: Highest-Leverage Change (proposed)

Move the Constitution's unit of authority from *permission to write* to *proof of effect* — "done" = a verified postcondition under a domain-appropriate control budget. This is a paradigm change (Meadows), not a rule tweak.

## Article VII: Amendments

### Section 1: Amendment Process

This Constitution **MAY** be amended:

| Rule | Requirement | Implementation | Validation | Breach |
|---|---|---|---|---|
| Proposal | Amendments MUST be proposed in writing | Use pull requests | Proposals MUST be reviewed | Unreviewed proposals MUST NOT be merged |
| Approval | Amendments MUST be approved | Use consensus or voting | Approval MUST be documented | Unapproved amendments MUST NOT be merged |
| Implementation | Amendments MUST be implemented | Update code and documentation | Implementation MUST be tested | Unimplemented amendments MUST be completed |

## Article VII: Interpretation

### Section 1: Interpretation Authority

This Constitution **SHALL** be interpreted:

#### Primary Authority
- **Authority**: The system operators have primary authority
- **Implementation**: Operators make final decisions
- **Validation**: Decisions MUST be documented
- **Breach**: Undocumented decisions MUST be documented

#### Secondary Authority
- **Authority**: The community has secondary authority
- **Implementation**: Community provides input
- **Validation**: Input MUST be considered
- **Breach**: Ignored input MUST be addressed

#### Tertiary Authority
- **Authority**: Karpathy's principles have tertiary authority
- **Implementation**: Use Karpathy's principles as guidance
- **Validation**: Guidance MUST be followed
- **Breach**: Ignored guidance MUST be addressed

## Ratification

This Constitution is ratified by the builders and operators of the Graph-Based Agent System on **July 31, 2025**.

**Signed:**
- System Operators
- System Builders
- Community Members

## Appendix A: Glossary

### Agent
An autonomous software component that performs a specific task.

### Karpathy Loop
A loop pattern: Propose → Execute → Evaluate → Commit → Refine

### Permission Boundaries
Explicit declarations of what an agent can READ, WRITE, NEVER do, and when it needs HUMAN_CHECKPOINT.

### LangGraph
A framework for building stateful, multi-agent applications.

### Stepfun
The single supported LLM provider for current production execution.

### MCP Tools
Model Context Protocol tools for interacting with external systems.

### Memory
Storage for agent context and past experiences.

### State
Data passed between agents in the graph.

### Edge
Connection between agents in the graph.

### Node
Agent in the graph.

## Appendix B: References

1. Karpathy, A. (2024). "Agentic Engineering". Sequoia Capital.
2. LangChain Team. (2024). "LangGraph Documentation".
4. MAAD Framework. (2024). "Multi-Agent Architecture Design".
5. MetaGPT. (2023). "Meta-Programming for Multi-Agent Collaborative Framework".
6. AutoGen. (2024). "Microsoft Research".
7. CrewAI. (2024). "Role-Based Agent Crews".

---

**Last Updated**: July 31, 2025

**Version**: 1.0

**Status**: Ratified
