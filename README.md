# Graph-Based Agent System

## Multi-Agent Orchestration System using Karpathy's Agentic Engineering

A production-ready, graph-based multi-agent orchestration system that implements **Andrej Karpathy's Agentic Engineering** principles for building reliable, transparent, and ethical AI systems.

---

## 🎯 Vision

### Problem Statement

Building reliable multi-agent systems is complex. Traditional approaches suffer from:

- **Lack of structure** - Agents work in ad-hoc ways without clear governance
- **Poor coordination** - Agents don't communicate effectively or respect boundaries
- **Unclear responsibilities** - Agents have overlapping or missing responsibilities
- **No accountability** - No clear rules, principles, or enforcement mechanisms
- **Opaque decisions** - Hard to understand why agents made certain choices

### Solution

A **graph-based multi-agent orchestration system** that:
- Uses **LangGraph** for stateful workflow orchestration with full visibility
- Implements **Karpathy's Agentic Engineering** principles systematically
- Provides **clear governance** through a Constitution and Laws
- Ensures **transparency and accountability** at every step
- Scales reliably from simple to complex multi-agent workflows

### Core Principles (Karpathy's Agentic Engineering)

Based on Andrej Karpathy's framework for building reliable AI agents:

1. **Think before acting** - Analyze inputs thoroughly before taking action
2. **Simplicity first** - Break into minimum necessary steps, avoid over-engineering
3. **Surgical changes** - Only modify what is necessary, respect permission boundaries
4. **Goal-driven execution** - Work towards clear, measurable goals with validation

### Why Graph-Based?

Unlike traditional multi-agent systems that use message-passing or shared state, our **graph-based approach** provides:

- **Explicit dependencies** - Clear visibility into agent relationships and data flow
- **Deterministic execution** - Predictable workflows with conditional routing
- **Stateful checkpoints** - Resume from any point, debug any step
- **Parallel execution** - Run independent agents concurrently
- **Human-in-the-loop** - Pause and resume with human approval

---

## 🏛️ Governance

### Constitution

The system is governed by a comprehensive **Constitution** ([CONSTITUTION.md](CONSTITUTION.md)) that defines:

- **Core Principles** - Karpathy's Four Principles with detailed requirements
- **Permission Boundaries** - READ/WRITE/NEVER/HUMAN_CHECKPOINT for each agent
- **Failure Handling** - Fail loudly, surface to human, never assume
- **Agent Architecture** - Karpathy Loop, specialization, communication
- **System Architecture** - LangGraph orchestration, LLM integration, memory
- **Quality Assurance** - Testing, code review, CI/CD
- **Ethics and Responsibility** - Bias, privacy, accountability

**Key Articles:**
- Article I: Core Principles
- Article II: Agent Architecture
- Article III: System Architecture
- Article IV: Quality Assurance
- Article V: Ethics and Responsibility
- Article VI: Amendments
- Article VII: Interpretation

### Laws

The system operates under **20 Laws** ([LAWS.md](LAWS.md)) that govern all implementation:

1. **Law of Specialization** - Every agent MUST have a single, well-defined responsibility
2. **Law of Permission Boundaries** - Every agent MUST have explicit permission boundaries
3. **Law of Failure Handling** - Every agent MUST handle failures properly
4. **Law of the Karpathy Loop** - Every agent MUST implement the Karpathy Loop
5. **Law of Testing** - All code MUST be tested (unit, integration, edge cases)
6. **Law of Documentation** - All code MUST be documented
7. **Law of Simplicity** - All code MUST be as simple as possible
8. **Law of Transparency** - All decisions MUST be transparent
9. **Law of Human Oversight** - All critical decisions MUST have human oversight
10. **Law of Continuous Improvement** - The system MUST continuously improve

**Enforcement:**
- Breaches are detected through code reviews, testing, and monitoring
- Penalties: Warning → Code review rejection → Temporary suspension
- Appeals: Offenders may appeal to system operators

---

## 🏗️ Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────┐
│ User Input (Requirements)                                   │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ LangGraph Orchestration Layer                               │
│ • State Management (TypedDict)                              │
│ • Conditional Routing (dynamic workflows)                    │
│ • Parallel Execution (independent agents)                   │
│ • Checkpointing (resume from any point)                     │
│ • Human-in-the-Loop (pause/resume with approval)            │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ 8 Karpathy Agents                                           │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ 1. Task Decomposer (✅ Done)                         │    │
│ │ - Converts requirements to structured tasks          │    │
│ │ - Implements Karpathy Loop (5 steps)                 │    │
│ │ - Uses LLM + Memory + MCP Tools                      │    │
│ └──────────────────────────────────────────────────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ 2. Agent Assigner (✅ Done)                          │    │
│ │ - Assigns tasks to appropriate agents                │    │
│ │ - Builds deterministic DAG execution plans           │    │
│ └──────────────────────────────────────────────────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ 3-8. Governance Agents (✅ Done)                      │    │
│ │ - Monitor, review, integrate, resolve, prioritize    │    │
│ └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer                                        │
│ • Stepfun Native REST LLM Integration (fail-loud only)      │
│ • Custom Memory (short-term + long-term)                    │
│ • Custom MCP Tools (requirements parser, etc.)              │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Final Output                                                │
└─────────────────────────────────────────────────────────────┘
```

### The 8 Karpathy Agents

| # | Agent | Role | Status | Karpathy Loop |
|---|-------|------|--------|---------------|
| 1 | **Task Decomposer** | Converts requirements to structured tasks | ✅ Done | ✅ Implemented |
| 2 | **Agent Assigner** | Assigns tasks to appropriate agents and builds DAG plans | ✅ Done | ✅ Implemented |
| 3 | **Progress Monitor** | Monitors task progress and detects issues | ✅ Done | ✅ Implemented |
| 4 | **Quality Reviewer** | Reviews output quality | ✅ Done | ✅ Implemented |
| 5 | **Integration** | Integrates outputs from all agents | ✅ Done | ✅ Implemented |
| 6 | **Decision & Conflict** | Resolves conflicts between agents | ✅ Done | ✅ Implemented |
| 7 | **Resource & Priority** | Manages resources and priorities | ✅ Done | ✅ Implemented |
| 8 | **Human Escalation** | Escalates to human when needed | ✅ Done | ✅ Implemented |

### Technology Stack

- **Orchestration**: LangGraph 1.2.x (currently installed; `requirements.txt` pins `langgraph>=0.2.0`) — the only orchestration framework in use
- **LLM Integration**: Stepfun native REST API only (`STEPFUN_MODEL`, default `step-3.7-flash`)
- **Provider Policy**: Stepfun-only execution with no fallback response path; missing credentials fail loudly
- **Memory**: Custom implementation (short-term dict + long-term list)
- **Tools**: Custom MCP tools (requirements parser, dependency analyzer)
- **Governance**: Constitution + Laws (enforced through code reviews)
- **No External Dependencies**: No Hermes Agent, no AutoGen, no CrewAI

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/graph-based-agent-system.git
cd graph-based-agent-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set API keys
cp .env.example .env
# Edit .env and add STEPFUN_API_KEY

# Review governance documents
cat CONSTITUTION.md
cat LAWS.md
```

### Usage

```bash
# 1) Put your real Stepfun credentials in .env (do not paste keys into chat)
cp .env.example .env
# Edit .env and set STEPFUN_API_KEY

# 2) Run the pipeline on inline requirements
python main.py \
  --requirements "Build a login page with email authentication" \
  --project-context "Web application" \
  --orchestrate-graph

# 3) Or run from a requirements file and write full JSON output
python main.py \
  --requirements-file product-requirements.txt \
  --project-context "FastAPI service" \
  --orchestrate-graph \
  --output run-result.json

# 4) Run benchmark suite (NEW - with auto reports)
python main.py --benchmark
python main.py --benchmark-extended
python main.py --benchmark --benchmark-reports-dir reports --output benchmark.json --json

# Using dedicated runner
python scripts/run_benchmarks.py
python scripts/run_benchmarks.py --extended
python scripts/run_benchmarks.py --live-only
```

### Benchmarks & Reports

The system includes a production-ready benchmark harness:

- **Base Suite (4 scenarios)**: E-commerce, Fintech MFA, Noisy Input, Adversarial Injection
- **Extended Suite (8 scenarios)**: + Rate Limits, ETL DAG, Empty Input, Long Context
- **Auto Reports**: JSON + Markdown saved to `reports/` with advanced metrics
- **Health Score**: Weighted composite (success 40% + quality 30% + defense 20% + hygiene 10%)

```bash
# Generate report
python scripts/run_benchmarks.py
cat reports/latest_benchmark.md

# Compare two runs
python scripts/compare_reports.py reports/old.json reports/new.json --output diff.md
```

See [docs/BENCHMARK-GUIDE.md](docs/BENCHMARK-GUIDE.md) for full guide.

Expected healthy metrics:
- Raw Success: 75% (4-suite) with adversarial blocked
- Effective Success: 100% (security-aware)
- Defense Rate: 100%
- Avg Quality: >=0.7, Health Score >=80

### Example

```python
from agents.task_decomposer import decompose_requirements

result = decompose_requirements(
    requirements="Build a login page with authentication",
    project_context="Web application",
    constraints="Use React and Node.js"
)

print(result['tasks'])
print(result['metadata'])
```

## 📖 Documentation

- [CONSTITUTION.md](CONSTITUTION.md) - System governance and principles
- [LAWS.md](LAWS.md) - 20 Laws governing implementation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Detailed architecture documentation
- [docs/RESEARCH.md](docs/RESEARCH.md) - Research foundation and references
- [docs/KARPATHY-AGENTS.md](docs/KARPATHY-AGENTS.md) - Specifications for the 8 Karpathy Meta-Agents
- [docs/SOFTWARE-AGENTS.md](docs/SOFTWARE-AGENTS.md) - Specifications for the 7 Software Domain Agents
- [docs/QUALITY-AUDIT-PLAN.md](docs/QUALITY-AUDIT-PLAN.md) - Quality audit plan and hardening status
- [docs/GOVERNANCE-SYSTEM.md](docs/GOVERNANCE-SYSTEM.md) - Distributed governance checks without a supreme decision agent
- [docs/SYSTEM-LIFECYCLE.md](docs/SYSTEM-LIFECYCLE.md) - Complete end-to-end system lifecycle documentation
- [docs/AGENT-LIFECYCLE.md](docs/AGENT-LIFECYCLE.md) - Combined lifecycle reference for implemented and planned agents
- [docs/agents/INDEX.md](docs/agents/INDEX.md) - Individual lifecycle documentation for each agent
- [docs/SWEBENCH-REPORT.md](docs/SWEBENCH-REPORT.md) - Honest SWE-bench Verified status + resolve-rate numbers
- [docs/SOTA-POSITION.md](docs/SOTA-POSITION.md) - System placed on the SWE-bench Verified SOTA ladder + decision #3
- [docs/META-SYSTEM.md](docs/META-SYSTEM.md) - Governed self-improvement meta-loop (measure->propose->gate by P7)
- `orchestrate_graph=True` enables group-based DAG execution orchestration over assigned tasks

---

Built with ❤️ using Karpathy's Agentic Engineering principles

Governed by Constitution and 20 Laws

<!-- auto-sync smoke test: 2026-08-05T15:00:25Z -->
