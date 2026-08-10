from pathlib import Path
from importlib.machinery import SourceFileLoader
w = SourceFileLoader("w", "/home/fares/Projects/graph-based-agent-system/.compress_worker.py").load_module()

TPL = """# Software Agents Documentation

## Overview

The **Software Agents** do the software development work, supervised by the **Karpathy Agents** (meta-agents) managing the system.

## Architecture
{B0}

## The 7 Software Agents

Every agent implements the same Karpathy Loop (`propose` → `execute` → `evaluate` → `commit` → `refine`), declares an explicit `PERMISSIONS` dict, and must clear its quality gate (`>= 0.8`) before `commit`; `refine` increments `retry_count`. Each section below gives role, responsibilities, loop code, permissions, tools, and upstream/downstream wiring.

### 1. Product Manager Agent

**Role:** Manages product requirements and priorities

**Responsibilities:** gather/analyze stakeholder requirements; create and maintain the product backlog; prioritize features by business value; write user stories with acceptance criteria; communicate with stakeholders; make product decisions.

**Karpathy Loop Implementation:**

{B1}

**Permissions:**

{B2}

**Tools:** requirements parser; stakeholder communication; market research; backlog management.

**Integration with Karpathy Agents:** in ← Task Decomposer; out → Architect, Agent Assigner.

### 2. Architect Agent

**Role:** Designs system architecture

**Responsibilities:** design architecture from requirements; choose tech stack; define component interactions; create architecture diagrams; make and document architectural decisions.

**Karpathy Loop Implementation:**

{B3}

**Permissions:**

{B4}

**Tools:** architecture design; diagram creation; technology research; architecture evaluation.

**Integration with Karpathy Agents:** in ← Product Manager (user stories); out → Developer, Agent Assigner.

### 3. Developer Agent

**Role:** Writes code

**Responsibilities:** write code from the architecture; implement features; write unit tests; fix bugs; refactor; document code.

**Karpathy Loop Implementation:**

{B5}

**Permissions:**

{B6}

**Tools:** code generation; testing; code quality; documentation.

**Integration with Karpathy Agents:** in ← Architect (architecture); out → Reviewer, Tester, Agent Assigner.

### 4. Reviewer Agent

**Role:** Reviews code

**Responsibilities:** review code for quality, bugs, security issues and best practices; provide feedback; approve or reject code.

**Karpathy Loop Implementation:**

{B7}

**Permissions:**

{B8}

**Tools:** code review; static analysis; security scanning; best-practices checkers.

**Integration with Karpathy Agents:** in ← Developer (code); out → Developer (fixes) or Quality Reviewer.

### 5. Tester Agent

**Role:** Tests code

**Responsibilities:** write integration and end-to-end tests; run tests; report bugs; verify fixes; ensure test coverage.

**Karpathy Loop Implementation:**

{B9}

**Permissions:**

{B10}

**Tools:** test generation; test execution; coverage analysis; bug reporting.

**Integration with Karpathy Agents:** in ← Developer (code); out → Developer (fixes) or Quality Reviewer.

### 6. DevOps Agent

**Role:** Manages deployment

**Responsibilities:** set up CI/CD pipelines; manage deployment; monitor systems; handle infrastructure; ensure availability; manage scaling.

**Karpathy Loop Implementation:**

{B11}

**Permissions:**

{B12}

**Tools:** CI/CD; deployment; monitoring; infrastructure management.

**Integration with Karpathy Agents:** in ← Reviewer (approved code); out → Progress Monitor.

### 7. Security Agent

**Role:** Ensures system security

**Responsibilities:** perform security audits; identify vulnerabilities; implement security measures; monitor for security issues; respond to incidents; ensure compliance.

**Karpathy Loop Implementation:**

{B13}

**Permissions:**

{B14}

**Tools:** security scanning; vulnerability assessment; security implementation; monitoring.

**Integration with Karpathy Agents:** in ← Developer, Reviewer (code); out → Developer (fixes) or DevOps (deployment).

## Integration with Karpathy Agents

### Workflow

{B15}

### Communication

State passing between agents:

{B16}

### Testing

Each Software Agent is tested across propose/execute/evaluate:

{B17}

## Summary

The 7 Software Agents — **Product Manager** (requirements), **Architect** (architecture), **Developer** (code), **Reviewer** (review), **Tester** (tests), **DevOps** (deploy), **Security** (security) — run under supervision of the 8 Karpathy Agents.

**Last Updated**: July 31, 2025
"""

w.render(Path("/home/fares/Projects/graph-based-agent-system/docs/SOFTWARE-AGENTS.md"), TPL)
