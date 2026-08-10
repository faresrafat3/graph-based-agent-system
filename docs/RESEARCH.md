# Research Foundation

## Overview

Research base for the Software Builder Agents system: papers, frameworks, and methodologies that informed the design decisions.

## 1. Karpathy's Agentic Engineering

### Source

**Andrej Karpathy** - AI researcher and educator

**Talks and Writings:** "Agentic Engineering" - Sequoia Capital, 2024; "Software 2.0" - Various talks, 2017-2024; Twitter/X posts on AI agents, 2024-2025.

### Key Principles

#### 1.1 Specialization Over Generalization

> "Agents should be specialized, not general. Each agent should have a clear, single responsibility."

8 specialized agents, one responsibility each — Task Decomposer only decomposes requirements, Agent Assigner only assigns tasks. No agent tries to do everything.

#### 1.2 Permission Boundaries

> "Each agent should have explicit READ/WRITE/NEVER permissions. Agents should fail loudly when they encounter something outside their scope."

Explicit per​-agent permissions (Task Decomposer: READ requirements, WRITE tasks, NEVER touch code). Agents fail loudly outside their scope; human escalation is explicit, not implicit.

#### 1.3 The Karpathy Loop

> "Agents should follow a loop: Propose, Execute, Evaluate, Commit, Refine."

Every agent implements it — Propose (generate a plan or hypothesis), Execute (implement it), Evaluate (check if it worked), Commit (on success), Refine (on failure, retry).

#### 1.4 Failure Handling

> "Fail loudly, not silently. Surface errors to humans when outside scope. Never assume, always validate."

Clear error messages, escalation to humans when out of scope, validation of all inputs and outputs, no silent failures.

#### 1.5 Human​-in​-the​-Loop

> "Humans should be in the loop for critical decisions. Agents should escalate when they're unsure."

Human Escalation Agent handles edge cases; agents escalate after 3 failed retries; humans can override agent decisions; the system exposes agent decisions transparently.

## 2. Multi​-Agent Systems Research

### 2.1 MAAD Framework

**Paper:** "MAAD: Multi​-Agent Architecture Design" (2024)

Key ideas → application: specialized agents per role (Analyst, Modeler, Designer, Evaluator) and hierarchical organization → both adopted (8 agents); clear communication protocols → LangGraph; quality gates between stages → the evaluate step.

### 2.2 MetaGPT

**Paper:** "MetaGPT: Meta Programming for Multi​-Agent Collaborative Framework" (2023)

Key ideas → application: role​-based agents (Product Manager, Architect, Engineer, QA) → adopted; sequential workflow with feedback loops → adopted; Standard Operating Procedures (SOPs) → Karpathy Loop is our SOP; QA at each stage → the evaluate step.

### 2.3 AutoGen

**Paper:** "AutoGen: Enabling Next​-Gen LLM Applications via Multi​-Agent Conversation" (Microsoft Research, 2024)

Key ideas → application: conversational multi​-agent systems and group chat patterns → considered, but state​-based coordination chosen for simplicity; human​-in​-the​-loop → Human Escalation Agent; flexible agent coordination → LangGraph.

### 2.4 CrewAI

**Paper:** "CrewAI: Role​-Based Agent Crews" (2024)

Key ideas → application: role​-based agent crews → adopted; task delegation → Agent Assigner; parallel execution → supported; crew management → LangGraph.

## 3. LangGraph and Stepfun

### 3.1 LangGraph

**Source:** LangChain Team (2024)

**Key Features:** stateful workflows; conditional routing; parallel execution; human​-in​-the​-loop; checkpointing.

**Why We Chose LangGraph:** production​-ready (34.5M monthly downloads); stateful workflows with checkpointing; conditional routing for dynamic workflows; parallel execution for efficiency; human​-in​-the​-loop support; active community and documentation.

**Application:** all orchestration runs on LangGraph — each agent is a node, conditional routing drives the Karpathy Loop, state management carries agent communication.

### 3.2 Stepfun Native REST Integration

**Source:** Stepfun chat completions API

**Key Features:** single​-provider production path; chat completions data​-bundle shape; native stdlib HTTP via `urllib.request`; fail​-loud behavior for missing credentials or invalid API payloads.

**Why We Chose Stepfun​-Only Integration:** the current quality target favors one controlled provider path over broad provider abstraction; removing synthetic fallback responses prevents hidden quality regressions; native REST keeps the LLM boundary simple, inspectable, and dependency​-light.

**Application:** Stepfun for all production LLM calls; tests monkeypatch the HTTP boundary or imported `call_llm` symbol explicitly; custom memory and custom tools for full control.

## 4. Software Engineering Methodologies

### 4.1 Agile Development

**Source:** Agile Manifesto (2001)

Principles → application: individuals and interactions over processes and tools; working software over comprehensive documentation → agents produce output; customer collaboration over contract negotiation → Human Escalation Agent; responding to change over following a plan → agents refine and retry.

### 4.2 Domain​-Driven Design

**Source:** Eric Evans, "Domain​-Driven Design" (2003)

Principles → application: bounded contexts → each agent is one; ubiquitous language → task types, priorities, etc.; domain models → task structure; context mapping → state passing between agents.

### 4.3 Clean Architecture

**Source:** Robert C. Martin, "Clean Architecture" (2017)

Principles → application: separation of concerns and single responsibility → one job per agent; dependency inversion → agents depend on abstractions; interface segregation → each agent has a clear interface.

## 5. AI and Machine Learning

### 5.1 Large Language Models

**Source:** Stepfun and contemporary large language model research (2023-2026)

**Key Production Model:** Stepfun model configured by `STEPFUN_MODEL` (default: `step-3.7-flash`)

**Application:** LLMs for natural language understanding, task decomposition, decision making, and quality assessment.

### 5.2 Prompt Engineering

**Source:** Various research papers (2023-2025)

Techniques, all in use: few​-shot learning (examples in prompts); chain​-of​-thought reasoning (step​-by​-step prompts); role​-playing (agent roles); structured output (JSON format).

### 5.3 Reinforcement Learning

**Source:** Sutton & Barto, "Reinforcement Learning" (2018)

**Key Concepts:** agents learn from feedback; reward signals; policy optimization.

**Future Application:** agents could learn from user feedback, optimize their prompts, and improve over time.

## 6. Software Quality

### 6.1 Test​-Driven Development

**Source:** Kent Beck, "Test​-Driven Development" (2003)

Principles, all in use: write tests first (tests for all components); Red​-Green​-Refactor cycle; continuous testing.

### 6.2 Code Review

**Source:** Various industry practices (2010-2025)

Principles → application: peer review → Quality Reviewer Agent; quality gates → evaluate step; continuous improvement → agents are continuously improved.

### 6.3 Continuous Integration/Continuous Deployment

**Source:** Martin Fowler, "Continuous Integration" (2006)

Principles → application: automated testing → implemented; automated deployment → possible, not yet built; continuous feedback → provided.

## 7. Decision Making

### 7.1 Why LangGraph Over Other Frameworks?

**Alternatives Considered:**
1. **CrewAI** - Simpler but less flexible
2. **AutoGen** - More conversational, less structured
3. **Custom Framework** - More work, less community support

**Decision:** LangGraph — production​-ready, stateful workflows, conditional routing, parallel execution, human​-in​-the​-loop, active community.

### 7.2 Why Custom Memory Over LangChain Memory?

**Alternatives Considered:**
1. **LangChain Memory** - Less control, more dependencies
2. **Vector Database** - More complex, overkill for our use case
3. **Custom Memory** - Full control, no dependencies

**Decision:** custom memory — full control over memory management, no external dependencies, optimized for our use case, simpler implementation.

### 7.3 Why Custom Tools Over LangChain Tools?

**Alternatives Considered:**
1. **LangChain Tools** - Less control, more dependencies
2. **External APIs** - More complex, network dependencies
3. **Custom Tools** - Full control, no dependencies

**Decision:** custom tools — full control over tool implementation, no external dependencies, optimized for our use case, simpler implementation.

### 7.4 Why 8 Agents Instead of Fewer or More?

**Alternatives Considered:**
1. **3 Agents** (Decomposer, Executor, Reviewer) - Too few, not specialized enough
2. **5 Agents** (Decomposer, Assigner, Executor, Reviewer, Integrator) - Better, but missing some roles
3. **8 Agents** (Current) - Good balance of specialization and complexity
4. **12 Agents** (More specialized) - Too many, too complex

**Decision:** 8 agents — good balance of specialization and complexity; each agent has a clear, single responsibility; covers all major roles in software development; manageable complexity.

## 8. Limitations and Future Work

### 8.1 Current Limitations

1. **Single Project Focus**: System is designed for single projects, not multiple concurrent projects
2. **No Learning**: Agents don't learn from feedback yet
3. **No Visualization**: No web UI for monitoring agents
4. **Limited Tools**: Only basic MCP tools implemented
5. **No Distributed Execution**: All agents run on single machine

### 8.2 Future Work

1. **Reinforcement Learning**: Agents learn from user feedback
2. **Multi​-Modal Support**: Support for images, audio, video
3. **Web UI**: Visualization and monitoring interface
4. **More Tools**: Additional MCP tools for different use cases
5. **Distributed Execution**: Run agents on multiple machines
6. **Collaborative Agents**: Agents that can negotiate and collaborate
7. **Self​-Improving Agents**: Agents that improve their own prompts

## 9. Ethical Considerations

### 9.1 Bias and Fairness

**Concern:** LLMs can exhibit biases from their training data. **Mitigation:** validate all outputs; provide transparency into agent decisions; allow human override.

### 9.2 Transparency

**Concern:** AI systems can be opaque and hard to understand. **Mitigation:** clear visibility into agent decisions; log all agent actions; provide explanations for decisions.

### 9.3 Accountability

**Concern:** AI systems can make mistakes without accountability. **Mitigation:** human​-in​-the​-loop; escalate to humans when needed; provide audit trails.

### 9.4 Privacy

**Concern:** AI systems can expose sensitive information. **Mitigation:** permission boundaries; validate all inputs and outputs; don't store sensitive information.

## 10. Conclusion

Foundations of the Software Builder Agents system:

1. **Karpathy's Agentic Engineering** - Core principles for building reliable AI agents
2. **Multi​-Agent Systems Research** - MAAD, MetaGPT, AutoGen, CrewAI
3. **LangGraph and Stepfun** - Production​-ready orchestration and Stepfun​-only LLM integration
4. **Software Engineering Methodologies** - Agile, DDD, Clean Architecture
5. **AI and Machine Learning** - LLMs, prompt engineering, reinforcement learning
6. **Software Quality** - TDD, code review, CI/CD

Design optimized for: **Simplicity** (easy to understand and use), **Flexibility** (easy to extend and customize), **Reliability** (fault​-tolerant), **Transparency** (clear visibility into agent decisions), **Scalability** (can handle complex requirements).

## References

1. Karpathy, A. (2024). "Agentic Engineering". Sequoia Capital.
2. Karpathy, A. (2017). "Software 2.0". Medium.
3. MAAD Framework. (2024). "Multi​-Agent Architecture Design". arXiv.
4. Hong, S., et al. (2023). "MetaGPT: Meta Programming for Multi​-Agent Collaborative Framework". arXiv.
5. Wu, Q., et al. (2024). "AutoGen: Enabling Next​-Gen LLM Applications via Multi​-Agent Conversation". Microsoft Research.
6. CrewAI. (2024). "Role​-Based Agent Crews". GitHub.
7. LangChain Team. (2024). "LangGraph Documentation". langchain.com.
9. Beck, K. (2001). "Manifesto for Agile Software Development". agilemanifesto.org.
10. Evans, E. (2003). "Domain​-Driven Design". Addison​-Wesley.
11. Martin, R. C. (2017). "Clean Architecture". Prentice Hall.
14. Sutton, R. S., & Barto, A. G. (2018). "Reinforcement Learning: An Introduction". MIT Press.
15. Beck, K. (2003). "Test​-Driven Development". Addison​-Wesley.
16. Fowler, M. (2006). "Continuous Integration". martinfowler.com.

---

**Last Updated**: July 31, 2025
