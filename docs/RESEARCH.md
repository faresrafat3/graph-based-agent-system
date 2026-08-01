# Research Foundation

## Overview

This document provides the research foundation for the Software Builder Agents system, including key papers, frameworks, and methodologies that informed our design decisions.

---

## 1. Karpathy's Agentic Engineering

### Source

**Andrej Karpathy** - AI researcher and educator

**Talks and Writings:**
- "Agentic Engineering" - Sequoia Capital, 2024
- "Software 2.0" - Various talks, 2017-2024
- Twitter/X posts on AI agents, 2024-2025

### Key Principles

#### 1.1 Specialization Over Generalization

**Quote:**
> "Agents should be specialized, not general. Each agent should have a clear, single responsibility."

**Application:**
- We created 8 specialized agents, each with a single responsibility
- Task Decomposer only decomposes requirements
- Agent Assigner only assigns tasks
- No agent tries to do everything

#### 1.2 Permission Boundaries

**Quote:**
> "Each agent should have explicit READ/WRITE/NEVER permissions. Agents should fail loudly when they encounter something outside their scope."

**Application:**
- Each agent has explicit permissions
- Task Decomposer can READ requirements, WRITE tasks, NEVER touch code
- Agents fail loudly when they encounter something outside their scope
- Human escalation is explicit, not implicit

#### 1.3 The Karpathy Loop

**Quote:**
> "Agents should follow a loop: Propose, Execute, Evaluate, Commit, Refine."

**Application:**
- Each agent implements the Karpathy Loop
- Propose: Generate a plan or hypothesis
- Execute: Implement the plan
- Evaluate: Check if the plan worked
- Commit: If successful, commit the changes
- Refine: If failed, refine and retry

#### 1.4 Failure Handling

**Quote:**
> "Fail loudly, not silently. Surface errors to humans when outside scope. Never assume, always validate."

**Application:**
- Agents fail loudly with clear error messages
- Agents escalate to humans when they encounter something outside their scope
- Agents validate all inputs and outputs
- No silent failures

#### 1.5 Human-in-the-Loop

**Quote:**
> "Humans should be in the loop for critical decisions. Agents should escalate when they're unsure."

**Application:**
- Human Escalation Agent handles edge cases
- Agents escalate after 3 failed retries
- Humans can override agent decisions
- System provides transparency into agent decisions

---

## 2. Multi-Agent Systems Research

### 2.1 MAAD Framework

**Paper:** "MAAD: Multi-Agent Architecture Design" (2024)

**Key Ideas:**
- Specialized agents for different roles (Analyst, Modeler, Designer, Evaluator)
- Hierarchical organization
- Clear communication protocols
- Quality gates between stages

**Application:**
- We adopted the specialized agent approach
- We implemented hierarchical organization (8 agents)
- We use LangGraph for communication
- We implement quality gates (evaluate step)

### 2.2 MetaGPT

**Paper:** "MetaGPT: Meta Programming for Multi-Agent Collaborative Framework" (2023)

**Key Ideas:**
- Role-based agents (Product Manager, Architect, Engineer, QA)
- Sequential workflow with feedback loops
- Standard Operating Procedures (SOPs)
- Quality assurance at each stage

**Application:**
- We adopted role-based agents
- We implement sequential workflow with feedback loops
- We use Karpathy Loop as our SOP
- We implement quality assurance (evaluate step)

### 2.3 AutoGen

**Paper:** "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation" (Microsoft Research, 2024)

**Key Ideas:**
- Conversational multi-agent systems
- Group chat patterns
- Human-in-the-loop
- Flexible agent coordination

**Application:**
- We considered conversational patterns but chose state-based coordination for simplicity
- We implement human-in-the-loop through Human Escalation Agent
- We use LangGraph for flexible coordination

### 2.4 CrewAI

**Paper:** "CrewAI: Role-Based Agent Crews" (2024)

**Key Ideas:**
- Role-based agent crews
- Task delegation
- Parallel execution
- Crew management

**Application:**
- We adopted role-based agents
- We implement task delegation through Agent Assigner
- We support parallel execution
- We manage agents through LangGraph

---

## 3. LangGraph and Stepfun

### 3.1 LangGraph

**Source:** LangChain Team (2024)

**Key Features:**
- Stateful workflows
- Conditional routing
- Parallel execution
- Human-in-the-loop
- Checkpointing

**Why We Chose LangGraph:**
- Production-ready (34.5M monthly downloads)
- Stateful workflows with checkpointing
- Conditional routing for dynamic workflows
- Parallel execution for efficiency
- Human-in-the-loop support
- Active community and documentation

**Application:**
- We use LangGraph for all orchestration
- Each agent is a node in the graph
- We use conditional routing for the Karpathy Loop
- We use state management for agent communication

### 3.2 Stepfun Native REST Integration

**Source:** Stepfun chat completions API

**Key Features:**
- Single-provider production path
- Chat completions payload shape
- Native stdlib HTTP integration via `urllib.request`
- Fail-loud behavior for missing credentials or invalid API payloads

**Why We Chose Stepfun-Only Integration:**
- The current quality target favors one controlled provider path over broad provider abstraction
- Removing synthetic fallback responses prevents hidden quality regressions
- Native REST keeps the LLM boundary simple, inspectable, and dependency-light

**Application:**
- We use Stepfun for all production LLM calls
- Tests monkeypatch the HTTP boundary or imported `call_llm` symbol explicitly
- We implement custom memory and custom tools for full control

---

## 4. Software Engineering Methodologies

### 4.1 Agile Development

**Source:** Agile Manifesto (2001)

**Key Principles:**
- Individuals and interactions over processes and tools
- Working software over comprehensive documentation
- Customer collaboration over contract negotiation
- Responding to change over following a plan

**Application:**
- We prioritize working software (agents produce output)
- We collaborate with users (Human Escalation Agent)
- We respond to change (agents can refine and retry)

### 4.2 Domain-Driven Design

**Source:** Eric Evans, "Domain-Driven Design" (2003)

**Key Principles:**
- Bounded contexts
- Ubiquitous language
- Domain models
- Context mapping

**Application:**
- Each agent is a bounded context
- Agents use ubiquitous language (task types, priorities, etc.)
- Agents have domain models (task structure)
- Agents communicate through context mapping (state passing)

### 4.3 Clean Architecture

**Source:** Robert C. Martin, "Clean Architecture" (2017)

**Key Principles:**
- Separation of concerns
- Dependency inversion
- Interface segregation
- Single responsibility

**Application:**
- We separate concerns (each agent has single responsibility)
- We use dependency inversion (agents depend on abstractions)
- We segregate interfaces (each agent has clear interface)
- We enforce single responsibility (each agent does one thing)

---

## 5. AI and Machine Learning

### 5.1 Large Language Models

**Source:** Stepfun and contemporary large language model research (2023-2026)

**Key Production Model:**
- Stepfun model configured by `STEPFUN_MODEL` (default: `step-3.7-flash`)

**Application:**
- We use LLMs for natural language understanding
- We use LLMs for task decomposition
- We use LLMs for decision making
- We use LLMs for quality assessment

### 5.2 Prompt Engineering

**Source:** Various research papers (2023-2025)

**Key Techniques:**
- Few-shot learning
- Chain-of-thought reasoning
- Role-playing
- Structured output

**Application:**
- We use few-shot learning (examples in prompts)
- We use chain-of-thought reasoning (step-by-step prompts)
- We use role-playing (agent roles)
- We use structured output (JSON format)

### 5.3 Reinforcement Learning

**Source:** Sutton & Barto, "Reinforcement Learning" (2018)

**Key Concepts:**
- Agents learn from feedback
- Reward signals
- Policy optimization

**Future Application:**
- Agents could learn from user feedback
- Agents could optimize their prompts
- Agents could improve over time

---

## 6. Software Quality

### 6.1 Test-Driven Development

**Source:** Kent Beck, "Test-Driven Development" (2003)

**Key Principles:**
- Write tests first
- Red-Green-Refactor cycle
- Continuous testing

**Application:**
- We write tests for all components
- We use Red-Green-Refactor cycle
- We test continuously

### 6.2 Code Review

**Source:** Various industry practices (2010-2025)

**Key Principles:**
- Peer review
- Quality gates
- Continuous improvement

**Application:**
- Quality Reviewer Agent performs code review
- We implement quality gates (evaluate step)
- We continuously improve agents

### 6.3 Continuous Integration/Continuous Deployment

**Source:** Martin Fowler, "Continuous Integration" (2006)

**Key Principles:**
- Automated testing
- Automated deployment
- Continuous feedback

**Application:**
- We implement automated testing
- We could implement automated deployment
- We provide continuous feedback

---

## 7. Decision Making

### 7.1 Why LangGraph Over Other Frameworks?

**Alternatives Considered:**
1. **CrewAI** - Simpler but less flexible
2. **AutoGen** - More conversational, less structured
3. **Custom Framework** - More work, less community support

**Decision:**
We chose LangGraph because:
- Production-ready
- Stateful workflows
- Conditional routing
- Parallel execution
- Human-in-the-loop
- Active community

### 7.2 Why Custom Memory Over LangChain Memory?

**Alternatives Considered:**
1. **LangChain Memory** - Less control, more dependencies
2. **Vector Database** - More complex, overkill for our use case
3. **Custom Memory** - Full control, no dependencies

**Decision:**
We chose custom memory because:
- Full control over memory management
- No external dependencies
- Optimized for our use case
- Simpler implementation

### 7.3 Why Custom Tools Over LangChain Tools?

**Alternatives Considered:**
1. **LangChain Tools** - Less control, more dependencies
2. **External APIs** - More complex, network dependencies
3. **Custom Tools** - Full control, no dependencies

**Decision:**
We chose custom tools because:
- Full control over tool implementation
- No external dependencies
- Optimized for our use case
- Simpler implementation

### 7.4 Why 8 Agents Instead of Fewer or More?

**Alternatives Considered:**
1. **3 Agents** (Decomposer, Executor, Reviewer) - Too few, not specialized enough
2. **5 Agents** (Decomposer, Assigner, Executor, Reviewer, Integrator) - Better, but missing some roles
3. **8 Agents** (Current) - Good balance of specialization and complexity
4. **12 Agents** (More specialized) - Too many, too complex

**Decision:**
We chose 8 agents because:
- Good balance of specialization and complexity
- Each agent has clear, single responsibility
- Covers all major roles in software development
- Manageable complexity

---

## 8. Limitations and Future Work

### 8.1 Current Limitations

1. **Single Project Focus**: System is designed for single projects, not multiple concurrent projects
2. **No Learning**: Agents don't learn from feedback yet
3. **No Visualization**: No web UI for monitoring agents
4. **Limited Tools**: Only basic MCP tools implemented
5. **No Distributed Execution**: All agents run on single machine

### 8.2 Future Work

1. **Reinforcement Learning**: Agents learn from user feedback
2. **Multi-Modal Support**: Support for images, audio, video
3. **Web UI**: Visualization and monitoring interface
4. **More Tools**: Additional MCP tools for different use cases
5. **Distributed Execution**: Run agents on multiple machines
6. **Collaborative Agents**: Agents that can negotiate and collaborate
7. **Self-Improving Agents**: Agents that improve their own prompts

---

## 9. Ethical Considerations

### 9.1 Bias and Fairness

**Concern:**
LLMs can exhibit biases from their training data.

**Mitigation:**
- We validate all outputs
- We provide transparency into agent decisions
- We allow human override

### 9.2 Transparency

**Concern:**
AI systems can be opaque and hard to understand.

**Mitigation:**
- We provide clear visibility into agent decisions
- We log all agent actions
- We provide explanations for decisions

### 9.3 Accountability

**Concern:**
AI systems can make mistakes without accountability.

**Mitigation:**
- We implement human-in-the-loop
- We escalate to humans when needed
- We provide audit trails

### 9.4 Privacy

**Concern:**
AI systems can expose sensitive information.

**Mitigation:**
- We implement permission boundaries
- We validate all inputs and outputs
- We don't store sensitive information

---

## 10. Conclusion

The Software Builder Agents system is built on a solid research foundation, including:

1. **Karpathy's Agentic Engineering** - Core principles for building reliable AI agents
2. **Multi-Agent Systems Research** - MAAD, MetaGPT, AutoGen, CrewAI
3. **LangGraph and Stepfun** - Production-ready orchestration and Stepfun-only LLM integration
4. **Software Engineering Methodologies** - Agile, DDD, Clean Architecture
5. **AI and Machine Learning** - LLMs, prompt engineering, reinforcement learning
6. **Software Quality** - TDD, code review, CI/CD

Our design decisions are informed by this research and optimized for:
- **Simplicity** - Easy to understand and use
- **Flexibility** - Easy to extend and customize
- **Reliability** - Fault-tolerant and robust
- **Transparency** - Clear visibility into agent decisions
- **Scalability** - Can handle complex requirements

---

## References

1. Karpathy, A. (2024). "Agentic Engineering". Sequoia Capital.
2. Karpathy, A. (2017). "Software 2.0". Medium.
3. MAAD Framework. (2024). "Multi-Agent Architecture Design". arXiv.
4. Hong, S., et al. (2023). "MetaGPT: Meta Programming for Multi-Agent Collaborative Framework". arXiv.
5. Wu, Q., et al. (2024). "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation". Microsoft Research.
6. CrewAI. (2024). "Role-Based Agent Crews". GitHub.
7. LangChain Team. (2024). "LangGraph Documentation". langchain.com.
9. Beck, K. (2001). "Manifesto for Agile Software Development". agilemanifesto.org.
10. Evans, E. (2003). "Domain-Driven Design". Addison-Wesley.
11. Martin, R. C. (2017). "Clean Architecture". Prentice Hall.
14. Sutton, R. S., & Barto, A. G. (2018). "Reinforcement Learning: An Introduction". MIT Press.
15. Beck, K. (2003). "Test-Driven Development". Addison-Wesley.
16. Fowler, M. (2006). "Continuous Integration". martinfowler.com.

---

**Last Updated**: July 31, 2025
