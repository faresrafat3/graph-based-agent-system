# Constitution - Graph-Based Agent System

## Preamble

We, the builders and operators of the **Graph-Based Agent System**, establish this Constitution to govern the design, development, and operation of our multi-agent system. This Constitution is based on **Karpathy's Agentic Engineering** principles and reflects our commitment to building reliable, transparent, and ethical AI systems.

## Article I: Core Principles

### Section 1: Karpathy's Four Principles

All agents and system components **MUST** adhere to Karpathy's Four Principles:

#### Principle 1: Think Before Acting
- **Requirement**: All agents MUST analyze inputs thoroughly before taking action
- **Implementation**: Each agent implements a `propose` step in the Karpathy Loop
- **Validation**: Agents MUST validate inputs before processing
- **Breach**: Agents that act without thinking MUST be flagged and corrected

#### Principle 2: Simplicity First
- **Requirement**: All agents MUST break tasks into minimum necessary steps
- **Implementation**: Agents MUST prefer simple solutions over complex ones
- **Validation**: Code reviews MUST check for unnecessary complexity
- **Breach**: Over-engineered solutions MUST be refactored

#### Principle 3: Surgical Changes
- **Requirement**: All agents MUST only modify what is necessary
- **Implementation**: Agents MUST have explicit permission boundaries
- **Validation**: Agents MUST validate outputs before committing
- **Breach**: Agents that modify outside their scope MUST be stopped

#### Principle 4: Goal-Driven Execution
- **Requirement**: All agents MUST work towards clear, measurable goals
- **Implementation**: Each agent MUST have explicit success criteria
- **Validation**: Agents MUST evaluate their outputs against success criteria
- **Breach**: Agents that fail to meet goals MUST refine and retry

### Section 2: Permission Boundaries

All agents **MUST** have explicit permission boundaries:

#### READ Permissions
- Agents MUST explicitly declare what they can READ
- Agents MUST NOT read outside their declared permissions
- Breach: Agents that read outside permissions MUST be stopped

#### WRITE Permissions
- Agents MUST explicitly declare what they can WRITE
- Agents MUST NOT write outside their declared permissions
- Breach: Agents that write outside permissions MUST be stopped

#### NEVER Permissions
- Agents MUST explicitly declare what they can NEVER do
- Agents MUST NEVER perform actions in their NEVER list
- Breach: Agents that breach NEVER permissions MUST be stopped immediately

#### HUMAN_CHECKPOINT Permissions
- Agents MUST explicitly declare when they need human approval
- Agents MUST NOT proceed without human approval when required
- Breach: Agents that bypass human checkpoints MUST be stopped

### Section 3: Failure Handling

All agents **MUST** implement proper failure handling:

#### Fail Loudly
- **Requirement**: Agents MUST fail loudly, not silently
- **Implementation**: Agents MUST raise exceptions with clear error messages
- **Validation**: All errors MUST be logged and reported
- **Breach**: Silent failures MUST be treated as critical bugs

#### Surface to Human
- **Requirement**: Agents MUST surface errors to humans when outside their scope
- **Implementation**: Agents MUST escalate after 3 failed retries
- **Validation**: Escalation MUST be logged and tracked
- **Breach**: Agents that fail to escalate MUST be corrected

#### Never Assume
- **Requirement**: Agents MUST NEVER assume, always validate
- **Implementation**: Agents MUST validate all inputs and outputs
- **Validation**: Validation MUST be explicit and logged
- **Breach**: Agents that make assumptions MUST be corrected

## Article II: Agent Architecture

### Section 1: The Karpathy Loop

All agents **MUST** implement the Karpathy Loop:
Propose → Execute → Evaluate → Commit → Refine

#### Propose Step
- **Requirement**: Generate a plan or hypothesis
- **Implementation**: Use memory and tools to analyze inputs
- **Validation**: Plan MUST be validated before execution
- **Breach**: Invalid plans MUST be refined

#### Execute Step
- **Requirement**: Implement the plan
- **Implementation**: Use LLM and tools to execute
- **Validation**: Execution MUST be validated
- **Breach**: Failed executions MUST be refined

#### Evaluate Step
- **Requirement**: Check if the plan worked
- **Implementation**: Validate outputs against success criteria
- **Validation**: Evaluation MUST be explicit and logged
- **Breach**: Invalid evaluations MUST be corrected

#### Commit Step
- **Requirement**: Commit if successful
- **Implementation**: Store results in memory
- **Validation**: Commit MUST be validated
- **Breach**: Invalid commits MUST be rolled back

#### Refine Step
- **Requirement**: Refine if failed
- **Implementation**: Adjust plan and retry
- **Validation**: Refinement MUST be logged
- **Breach**: Failed refinements MUST escalate after 3 retries

### Section 2: Agent Specialization

All agents **MUST** be specialized:

#### Single Responsibility
- **Requirement**: Each agent MUST have a single, well-defined responsibility
- **Implementation**: Each agent MUST do only one thing
- **Validation**: Code reviews MUST check for single responsibility
- **Breach**: Agents with multiple responsibilities MUST be split

#### Clear Interface
- **Requirement**: Each agent MUST have a clear interface
- **Implementation**: Each agent MUST define input and output schemas
- **Validation**: Interfaces MUST be validated
- **Breach**: Unclear interfaces MUST be clarified

#### Loose Coupling
- **Requirement**: Agents MUST be loosely coupled
- **Implementation**: Agents MUST communicate through state passing
- **Validation**: Code reviews MUST check for tight coupling
- **Breach**: Tightly coupled agents MUST be decoupled

### Section 3: Agent Communication

All agents **MUST** communicate properly:

#### State Passing
- **Requirement**: Agents MUST communicate through state passing
- **Implementation**: Use LangGraph state management
- **Validation**: State MUST be validated before passing
- **Breach**: Invalid state MUST be corrected

#### Explicit Dependencies
- **Requirement**: Agent dependencies MUST be explicit
- **Implementation**: Use LangGraph edges to define dependencies
- **Validation**: Dependencies MUST be validated
- **Breach**: Implicit dependencies MUST be made explicit

#### No Side Effects
- **Requirement**: Agents MUST NOT have side effects
- **Implementation**: Agents MUST only modify their output state
- **Validation**: Code reviews MUST check for side effects
- **Breach**: Agents with side effects MUST be corrected

## Article III: System Architecture

### Section 1: LangGraph Orchestration

The system **MUST** use LangGraph for orchestration:

#### State Management
- **Requirement**: System MUST use LangGraph state management
- **Implementation**: Define TypedDict for each agent state
- **Validation**: State MUST be validated at each step
- **Breach**: Invalid state MUST be corrected

#### Conditional Routing
- **Requirement**: System MUST use conditional routing
- **Implementation**: Use LangGraph conditional edges
- **Validation**: Routing MUST be validated
- **Breach**: Invalid routing MUST be corrected

#### Parallel Execution
- **Requirement**: System MUST support parallel execution
- **Implementation**: Use LangGraph parallel edges
- **Validation**: Parallel execution MUST be tested
- **Breach**: Failed parallel execution MUST be corrected

### Section 2: LLM Integration

The system **MUST** use Stepfun as the only active LLM provider in the current production path:

#### Stepfun-Only Provider Policy
- **Requirement**: System MUST route all LLM calls through the Stepfun native REST integration
- **Implementation**: Use `llm.llm_integration.call_llm`, backed only by Stepfun chat completions
- **Validation**: Tests MUST monkeypatch the Stepfun HTTP boundary rather than using production fallback responses
- **Breach**: Adding alternate provider routing or silent dry-run fallbacks MUST be rejected

#### Fail-Loud Error Handling
- **Requirement**: System MUST fail loudly when Stepfun credentials, quota, network, or response payloads are invalid
- **Implementation**: Raise typed configuration/API exceptions with actionable messages
- **Validation**: Error paths MUST be covered by tests
- **Breach**: Silent fallback responses MUST be removed immediately

#### Rate Limiting
- **Requirement**: System MUST respect Stepfun rate limits
- **Implementation**: Implement rate limiting/retry controls before high-volume usage
- **Validation**: Rate limiting MUST be tested
- **Breach**: Rate limit breaches MUST be fixed

### Section 3: Memory Management

The system **MUST** implement custom memory:

#### Short-Term Memory
- **Requirement**: System MUST maintain short-term memory
- **Implementation**: Use in-memory dictionary
- **Validation**: Short-term memory MUST be tested
- **Breach**: Memory leaks MUST be fixed

#### Long-Term Memory
- **Requirement**: System MUST maintain long-term memory
- **Implementation**: Use persistent storage
- **Validation**: Long-term memory MUST be tested
- **Breach**: Memory corruption MUST be fixed

#### Similarity Search
- **Requirement**: System MUST support similarity search
- **Implementation**: Use Jaccard similarity
- **Validation**: Similarity search MUST be tested
- **Breach**: Inaccurate similarity MUST be corrected

## Article IV: Quality Assurance

### Section 1: Testing

All code **MUST** be tested:

#### Unit Tests
- **Requirement**: All functions MUST have unit tests
- **Implementation**: Use pytest
- **Validation**: Coverage MUST be > 80%
- **Breach**: Untested code MUST NOT be merged

#### Integration Tests
- **Requirement**: All agents MUST have integration tests
- **Implementation**: Test full agent workflow
- **Validation**: Integration tests MUST pass
- **Breach**: Failed integration tests MUST be fixed

#### Edge Case Tests
- **Requirement**: All agents MUST have edge case tests
- **Implementation**: Test edge cases and error conditions
- **Validation**: Edge case tests MUST pass
- **Breach**: Failed edge case tests MUST be fixed

### Section 2: Code Review

All code **MUST** be reviewed:

#### Peer Review
- **Requirement**: All code MUST be reviewed by peers
- **Implementation**: Use pull requests
- **Validation**: Reviews MUST be documented
- **Breach**: Unreviewed code MUST NOT be merged

#### Quality Gates
- **Requirement**: All code MUST pass quality gates
- **Implementation**: Use automated checks
- **Validation**: Quality gates MUST be enforced
- **Breach**: Code that fails quality gates MUST NOT be merged

#### Documentation
- **Requirement**: All code MUST be documented
- **Implementation**: Use docstrings and comments
- **Validation**: Documentation MUST be reviewed
- **Breach**: Undocumented code MUST NOT be merged

### Section 3: Continuous Integration

All code **MUST** use CI/CD:

#### Automated Testing
- **Requirement**: All tests MUST run automatically
- **Implementation**: Use CI/CD pipeline
- **Validation**: CI/CD MUST be tested
- **Breach**: Failed CI/CD MUST be fixed

#### Automated Deployment
- **Requirement**: All deployments MUST be automated
- **Implementation**: Use CI/CD pipeline
- **Validation**: Deployments MUST be tested
- **Breach**: Failed deployments MUST be rolled back

#### Continuous Monitoring
- **Requirement**: System MUST be monitored continuously
- **Implementation**: Use monitoring tools
- **Validation**: Monitoring MUST be tested
- **Breach**: Monitoring failures MUST be fixed

## Article V: Ethics and Responsibility

### Section 1: Bias and Fairness

The system **MUST** be fair:

#### Bias Detection
- **Requirement**: System MUST detect bias
- **Implementation**: Implement bias detection tools
- **Validation**: Bias detection MUST be tested
- **Breach**: Biased outputs MUST be corrected

#### Fairness Validation
- **Requirement**: System MUST validate fairness
- **Implementation**: Test with diverse inputs
- **Validation**: Fairness MUST be documented
- **Breach**: Unfair outputs MUST be corrected

#### Transparency
- **Requirement**: System MUST be transparent
- **Implementation**: Log all decisions
- **Validation**: Transparency MUST be tested
- **Breach**: Opaque decisions MUST be explained

### Section 2: Privacy and Security

The system **MUST** protect privacy:

#### Data Protection
- **Requirement**: System MUST protect user data
- **Implementation**: Implement data protection measures
- **Validation**: Data protection MUST be tested
- **Breach**: Data breaches MUST be reported

#### Access Control
- **Requirement**: System MUST control access
- **Implementation**: Implement access control
- **Validation**: Access control MUST be tested
- **Breach**: Unauthorized access MUST be blocked

#### Encryption
- **Requirement**: System MUST encrypt sensitive data
- **Implementation**: Use encryption
- **Validation**: Encryption MUST be tested
- **Breach**: Unencrypted data MUST be encrypted

### Section 3: Accountability

The system **MUST** be accountable:

#### Audit Trail
- **Requirement**: System MUST maintain audit trail
- **Implementation**: Log all actions
- **Validation**: Audit trail MUST be tested
- **Breach**: Missing audit trail MUST be added

#### Human Oversight
- **Requirement**: System MUST have human oversight
- **Implementation**: Implement human-in-the-loop
- **Validation**: Human oversight MUST be tested
- **Breach**: Lack of oversight MUST be corrected

#### Responsibility
- **Requirement**: System MUST have clear responsibility
- **Implementation**: Document responsibilities
- **Validation**: Responsibilities MUST be reviewed
- **Breach**: Unclear responsibilities MUST be clarified

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

#### Proposal
- **Requirement**: Amendments MUST be proposed in writing
- **Implementation**: Use pull requests
- **Validation**: Proposals MUST be reviewed
- **Breach**: Unreviewed proposals MUST NOT be merged

#### Approval
- **Requirement**: Amendments MUST be approved
- **Implementation**: Use consensus or voting
- **Validation**: Approval MUST be documented
- **Breach**: Unapproved amendments MUST NOT be merged

#### Implementation
- **Requirement**: Amendments MUST be implemented
- **Implementation**: Update code and documentation
- **Validation**: Implementation MUST be tested
- **Breach**: Unimplemented amendments MUST be completed

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
