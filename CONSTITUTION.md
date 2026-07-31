# Constitution - Graph-Based Agent System

## Preamble

We, the builders and operators of the **Graph-Based Agent System**, establish this Constitution to govern the design, development, and operation of our multi-agent system. This Constitution is based on **Karpathy's Agentic Engineering** principles and reflects our commitment to building reliable, transparent, and ethical AI systems.

---

## Article I: Core Principles

### Section 1: Karpathy's Four Principles

All agents and system components **MUST** adhere to Karpathy's Four Principles:

#### Principle 1: Think Before Acting
- **Requirement**: All agents MUST analyze inputs thoroughly before taking action
- **Implementation**: Each agent implements a `propose` step in the Karpathy Loop
- **Validation**: Agents MUST validate inputs before processing
- **Violation**: Agents that act without thinking MUST be flagged and corrected

#### Principle 2: Simplicity First
- **Requirement**: All agents MUST break tasks into minimum necessary steps
- **Implementation**: Agents MUST prefer simple solutions over complex ones
- **Validation**: Code reviews MUST check for unnecessary complexity
- **Violation**: Over-engineered solutions MUST be refactored

#### Principle 3: Surgical Changes
- **Requirement**: All agents MUST only modify what is necessary
- **Implementation**: Agents MUST have explicit permission boundaries
- **Validation**: Agents MUST validate outputs before committing
- **Violation**: Agents that modify outside their scope MUST be stopped

#### Principle 4: Goal-Driven Execution
- **Requirement**: All agents MUST work towards clear, measurable goals
- **Implementation**: Each agent MUST have explicit success criteria
- **Validation**: Agents MUST evaluate their outputs against success criteria
- **Violation**: Agents that fail to meet goals MUST refine and retry

---

### Section 2: Permission Boundaries

All agents **MUST** have explicit permission boundaries:

#### READ Permissions
- Agents MUST explicitly declare what they can READ
- Agents MUST NOT read outside their declared permissions
- Violation: Agents that read outside permissions MUST be stopped

#### WRITE Permissions
- Agents MUST explicitly declare what they can WRITE
- Agents MUST NOT write outside their declared permissions
- Violation: Agents that write outside permissions MUST be stopped

#### NEVER Permissions
- Agents MUST explicitly declare what they can NEVER do
- Agents MUST NEVER perform actions in their NEVER list
- Violation: Agents that violate NEVER permissions MUST be stopped immediately

#### HUMAN_CHECKPOINT Permissions
- Agents MUST explicitly declare when they need human approval
- Agents MUST NOT proceed without human approval when required
- Violation: Agents that bypass human checkpoints MUST be stopped

---

### Section 3: Failure Handling

All agents **MUST** implement proper failure handling:

#### Fail Loudly
- **Requirement**: Agents MUST fail loudly, not silently
- **Implementation**: Agents MUST raise exceptions with clear error messages
- **Validation**: All errors MUST be logged and reported
- **Violation**: Silent failures MUST be treated as critical bugs

#### Surface to Human
- **Requirement**: Agents MUST surface errors to humans when outside their scope
- **Implementation**: Agents MUST escalate after 3 failed retries
- **Validation**: Escalation MUST be logged and tracked
- **Violation**: Agents that fail to escalate MUST be corrected

#### Never Assume
- **Requirement**: Agents MUST NEVER assume, always validate
- **Implementation**: Agents MUST validate all inputs and outputs
- **Validation**: Validation MUST be explicit and logged
- **Violation**: Agents that make assumptions MUST be corrected

---

## Article II: Agent Architecture

### Section 1: The Karpathy Loop

All agents **MUST** implement the Karpathy Loop:
Propose → Execute → Evaluate → Commit → Refine

#### Propose Step
- **Requirement**: Generate a plan or hypothesis
- **Implementation**: Use memory and tools to analyze inputs
- **Validation**: Plan MUST be validated before execution
- **Violation**: Invalid plans MUST be refined

#### Execute Step
- **Requirement**: Implement the plan
- **Implementation**: Use LLM and tools to execute
- **Validation**: Execution MUST be validated
- **Violation**: Failed executions MUST be refined

#### Evaluate Step
- **Requirement**: Check if the plan worked
- **Implementation**: Validate outputs against success criteria
- **Validation**: Evaluation MUST be explicit and logged
- **Violation**: Invalid evaluations MUST be corrected

#### Commit Step
- **Requirement**: Commit if successful
- **Implementation**: Store results in memory
- **Validation**: Commit MUST be validated
- **Violation**: Invalid commits MUST be rolled back

#### Refine Step
- **Requirement**: Refine if failed
- **Implementation**: Adjust plan and retry
- **Validation**: Refinement MUST be logged
- **Violation**: Failed refinements MUST escalate after 3 retries

---

### Section 2: Agent Specialization

All agents **MUST** be specialized:

#### Single Responsibility
- **Requirement**: Each agent MUST have a single, well-defined responsibility
- **Implementation**: Each agent MUST do only one thing
- **Validation**: Code reviews MUST check for single responsibility
- **Violation**: Agents with multiple responsibilities MUST be split

#### Clear Interface
- **Requirement**: Each agent MUST have a clear interface
- **Implementation**: Each agent MUST define input and output schemas
- **Validation**: Interfaces MUST be validated
- **Violation**: Unclear interfaces MUST be clarified

#### Loose Coupling
- **Requirement**: Agents MUST be loosely coupled
- **Implementation**: Agents MUST communicate through state passing
- **Validation**: Code reviews MUST check for tight coupling
- **Violation**: Tightly coupled agents MUST be decoupled

---

### Section 3: Agent Communication

All agents **MUST** communicate properly:

#### State Passing
- **Requirement**: Agents MUST communicate through state passing
- **Implementation**: Use LangGraph state management
- **Validation**: State MUST be validated before passing
- **Violation**: Invalid state MUST be corrected

#### Explicit Dependencies
- **Requirement**: Agent dependencies MUST be explicit
- **Implementation**: Use LangGraph edges to define dependencies
- **Validation**: Dependencies MUST be validated
- **Violation**: Implicit dependencies MUST be made explicit

#### No Side Effects
- **Requirement**: Agents MUST NOT have side effects
- **Implementation**: Agents MUST only modify their output state
- **Validation**: Code reviews MUST check for side effects
- **Violation**: Agents with side effects MUST be corrected

---

## Article III: System Architecture

### Section 1: LangGraph Orchestration

The system **MUST** use LangGraph for orchestration:

#### State Management
- **Requirement**: System MUST use LangGraph state management
- **Implementation**: Define TypedDict for each agent state
- **Validation**: State MUST be validated at each step
- **Violation**: Invalid state MUST be corrected

#### Conditional Routing
- **Requirement**: System MUST use conditional routing
- **Implementation**: Use LangGraph conditional edges
- **Validation**: Routing MUST be validated
- **Violation**: Invalid routing MUST be corrected

#### Parallel Execution
- **Requirement**: System MUST support parallel execution
- **Implementation**: Use LangGraph parallel edges
- **Validation**: Parallel execution MUST be tested
- **Violation**: Failed parallel execution MUST be corrected

---

### Section 2: LLM Integration

The system **MUST** use LangChain for LLM integration:

#### Provider Agnostic
- **Requirement**: System MUST support multiple LLM providers
- **Implementation**: Use LangChain LLM abstraction
- **Validation**: System MUST be tested with multiple providers
- **Violation**: Provider-specific code MUST be abstracted

#### Error Handling
- **Requirement**: System MUST handle LLM errors gracefully
- **Implementation**: Implement retry logic with exponential backoff
- **Validation**: Error handling MUST be tested
- **Violation**: Unhandled errors MUST be fixed

#### Rate Limiting
- **Requirement**: System MUST respect rate limits
- **Implementation**: Implement rate limiting
- **Validation**: Rate limiting MUST be tested
- **Violation**: Rate limit violations MUST be fixed

---

### Section 3: Memory Management

The system **MUST** implement custom memory:

#### Short-Term Memory
- **Requirement**: System MUST maintain short-term memory
- **Implementation**: Use in-memory dictionary
- **Validation**: Short-term memory MUST be tested
- **Violation**: Memory leaks MUST be fixed

#### Long-Term Memory
- **Requirement**: System MUST maintain long-term memory
- **Implementation**: Use persistent storage
- **Validation**: Long-term memory MUST be tested
- **Violation**: Memory corruption MUST be fixed

#### Similarity Search
- **Requirement**: System MUST support similarity search
- **Implementation**: Use Jaccard similarity
- **Validation**: Similarity search MUST be tested
- **Violation**: Inaccurate similarity MUST be corrected

---

## Article IV: Quality Assurance

### Section 1: Testing

All code **MUST** be tested:

#### Unit Tests
- **Requirement**: All functions MUST have unit tests
- **Implementation**: Use pytest
- **Validation**: Coverage MUST be > 80%
- **Violation**: Untested code MUST NOT be merged

#### Integration Tests
- **Requirement**: All agents MUST have integration tests
- **Implementation**: Test full agent workflow
- **Validation**: Integration tests MUST pass
- **Violation**: Failed integration tests MUST be fixed

#### Edge Case Tests
- **Requirement**: All agents MUST have edge case tests
- **Implementation**: Test edge cases and error conditions
- **Validation**: Edge case tests MUST pass
- **Violation**: Failed edge case tests MUST be fixed

---

### Section 2: Code Review

All code **MUST** be reviewed:

#### Peer Review
- **Requirement**: All code MUST be reviewed by peers
- **Implementation**: Use pull requests
- **Validation**: Reviews MUST be documented
- **Violation**: Unreviewed code MUST NOT be merged

#### Quality Gates
- **Requirement**: All code MUST pass quality gates
- **Implementation**: Use automated checks
- **Validation**: Quality gates MUST be enforced
- **Violation**: Code that fails quality gates MUST NOT be merged

#### Documentation
- **Requirement**: All code MUST be documented
- **Implementation**: Use docstrings and comments
- **Validation**: Documentation MUST be reviewed
- **Violation**: Undocumented code MUST NOT be merged

---

### Section 3: Continuous Integration

All code **MUST** use CI/CD:

#### Automated Testing
- **Requirement**: All tests MUST run automatically
- **Implementation**: Use CI/CD pipeline
- **Validation**: CI/CD MUST be tested
- **Violation**: Failed CI/CD MUST be fixed

#### Automated Deployment
- **Requirement**: All deployments MUST be automated
- **Implementation**: Use CI/CD pipeline
- **Validation**: Deployments MUST be tested
- **Violation**: Failed deployments MUST be rolled back

#### Continuous Monitoring
- **Requirement**: System MUST be monitored continuously
- **Implementation**: Use monitoring tools
- **Validation**: Monitoring MUST be tested
- **Violation**: Monitoring failures MUST be fixed

---

## Article V: Ethics and Responsibility

### Section 1: Bias and Fairness

The system **MUST** be fair:

#### Bias Detection
- **Requirement**: System MUST detect bias
- **Implementation**: Implement bias detection tools
- **Validation**: Bias detection MUST be tested
- **Violation**: Biased outputs MUST be corrected

#### Fairness Validation
- **Requirement**: System MUST validate fairness
- **Implementation**: Test with diverse inputs
- **Validation**: Fairness MUST be documented
- **Violation**: Unfair outputs MUST be corrected

#### Transparency
- **Requirement**: System MUST be transparent
- **Implementation**: Log all decisions
- **Validation**: Transparency MUST be tested
- **Violation**: Opaque decisions MUST be explained

---

### Section 2: Privacy and Security

The system **MUST** protect privacy:

#### Data Protection
- **Requirement**: System MUST protect user data
- **Implementation**: Implement data protection measures
- **Validation**: Data protection MUST be tested
- **Violation**: Data breaches MUST be reported

#### Access Control
- **Requirement**: System MUST control access
- **Implementation**: Implement access control
- **Validation**: Access control MUST be tested
- **Violation**: Unauthorized access MUST be blocked

#### Encryption
- **Requirement**: System MUST encrypt sensitive data
- **Implementation**: Use encryption
- **Validation**: Encryption MUST be tested
- **Violation**: Unencrypted data MUST be encrypted

---

### Section 3: Accountability

The system **MUST** be accountable:

#### Audit Trail
- **Requirement**: System MUST maintain audit trail
- **Implementation**: Log all actions
- **Validation**: Audit trail MUST be tested
- **Violation**: Missing audit trail MUST be added

#### Human Oversight
- **Requirement**: System MUST have human oversight
- **Implementation**: Implement human-in-the-loop
- **Validation**: Human oversight MUST be tested
- **Violation**: Lack of oversight MUST be corrected

#### Responsibility
- **Requirement**: System MUST have clear responsibility
- **Implementation**: Document responsibilities
- **Validation**: Responsibilities MUST be reviewed
- **Violation**: Unclear responsibilities MUST be clarified

---

## Article VI: Amendments

### Section 1: Amendment Process

This Constitution **MAY** be amended:

#### Proposal
- **Requirement**: Amendments MUST be proposed in writing
- **Implementation**: Use pull requests
- **Validation**: Proposals MUST be reviewed
- **Violation**: Unreviewed proposals MUST NOT be merged

#### Approval
- **Requirement**: Amendments MUST be approved
- **Implementation**: Use consensus or voting
- **Validation**: Approval MUST be documented
- **Violation**: Unapproved amendments MUST NOT be merged

#### Implementation
- **Requirement**: Amendments MUST be implemented
- **Implementation**: Update code and documentation
- **Validation**: Implementation MUST be tested
- **Violation**: Unimplemented amendments MUST be completed

---

## Article VII: Interpretation

### Section 1: Interpretation Authority

This Constitution **SHALL** be interpreted:

#### Primary Authority
- **Authority**: The system operators have primary authority
- **Implementation**: Operators make final decisions
- **Validation**: Decisions MUST be documented
- **Violation**: Undocumented decisions MUST be documented

#### Secondary Authority
- **Authority**: The community has secondary authority
- **Implementation**: Community provides input
- **Validation**: Input MUST be considered
- **Violation**: Ignored input MUST be addressed

#### Tertiary Authority
- **Authority**: Karpathy's principles have tertiary authority
- **Implementation**: Use Karpathy's principles as guidance
- **Validation**: Guidance MUST be followed
- **Violation**: Ignored guidance MUST be addressed

---

## Ratification

This Constitution is ratified by the builders and operators of the Graph-Based Agent System on **July 31, 2025**.

**Signed:**
- System Operators
- System Builders
- Community Members

---

## Appendix A: Glossary

### Agent
An autonomous software component that performs a specific task.

### Karpathy Loop
A loop pattern: Propose → Execute → Evaluate → Commit → Refine

### Permission Boundaries
Explicit declarations of what an agent can READ, WRITE, NEVER do, and when it needs HUMAN_CHECKPOINT.

### LangGraph
A framework for building stateful, multi-agent applications.

### LangChain
A framework for building applications powered by large language models.

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

---

## Appendix B: References

1. Karpathy, A. (2024). "Agentic Engineering". Sequoia Capital.
2. LangChain Team. (2024). "LangGraph Documentation".
3. LangChain Team. (2023). "LangChain Documentation".
4. MAAD Framework. (2024). "Multi-Agent Architecture Design".
5. MetaGPT. (2023). "Meta-Programming for Multi-Agent Collaborative Framework".
6. AutoGen. (2024). "Microsoft Research".
7. CrewAI. (2024). "Role-Based Agent Crews".

---

**Last Updated**: July 31, 2025

**Version**: 1.0

**Status**: Ratified
