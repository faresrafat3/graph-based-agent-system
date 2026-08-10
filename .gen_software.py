from pathlib import Path
import sys
sys.path.insert(0, "/home/fares/Projects/graph-based-agent-system")
from importlib.machinery import SourceFileLoader
w = SourceFileLoader("w", "/home/fares/Projects/graph-based-agent-system/.compress_worker.py").load_module()

TPL = """# Software Agents Documentation

## Overview

The **Software Agents** perform the actual software development work, supervised by the **Karpathy Agents** (meta-agents) that manage the system.

## Architecture
{B0}

## The 7 Software Agents

Every agent implements the same Karpathy Loop (`propose` → `execute` → `evaluate` → `commit` → `refine`), carries an explicit `PERMISSIONS` dict, and reaches quality gate `>= 0.8` before commit. Per-agent detail follows.

### 1. Product Manager Agent

**Role:** Manages product requirements and priorities

**Responsibilities:** gather/analyze stakeholder requirements; create and maintain the product backlog; prioritize features by business value; write user stories with acceptance criteria; communicate with stakeholders; make product decisions.

**Karpathy Loop Implementation:**

{B1}

**Permissions:**

{B2}

**Tools:** requirements parser, stakeholder communication, market research, backlog management.

**Integration with Karpathy Agents:** receives tasks from Task Decomposer; outputs go to Architect and Agent Assigner.

### 2. Architect Agent

**Role:** Designs system architecture

**Responsibilities:** design architecture from requirements; choose the technology stack; define component interactions; create architecture diagrams; make and document architectural decisions.

**Karpathy Loop Implementation:**

{B3}

**Permissions:**

{B4}

**Tools:** architecture design, diagram creation, technology research, architecture evaluation.

**Integration with Karpathy Agents:** receives user stories from Product Manager; outputs go to Developer and Agent Assigner.

### 3. Developer Agent

**Role:** Writes code

**Responsibilities:** write code from the architecture; implement features; write unit tests; fix bugs; refactor; document code.

**Karpathy Loop Implementation:**

{B5}

**Permissions:**

{B6}

**Tools:** code generation, testing, code quality, documentation.

**Integration with Karpathy Agents:** receives architecture from Architect; outputs go to Reviewer, Tester, and Agent Assigner.

### 4. Reviewer Agent

**Role:** Reviews code

**Responsibilities:** review code for quality, bugs, security issues, and best practices; provide feedback; approve or reject code.

**Karpathy Loop Implementation:**

{B7}

**Permissions:**

{B8}

**Tools:** code review, static analysis, security scanning, best-practices checkers.

**Integration with Karpathy Agents:** receives code from Developer; outputs go to Developer (for fixes) or Quality Reviewer.

### 5. Tester Agent

**Role:** Tests code

**Responsibilities:** write integration and end-to-end tests; run tests; report bugs; verify fixes; ensure test coverage.

**Karpathy Loop Implementation:**

{B9}

**Permissions:**

{B10}

**Tools:** test generation, test execution, coverage analysis, bug reporting.

**Integration with Karpathy Agents:** receives code from Developer; outputs go to Developer (for fixes) or Quality Reviewer.

### 6. DevOps Agent

**Role:** Manages deployment

**Responsibilities:** set up CI/CD pipelines; manage deployment; monitor systems; handle infrastructure; ensure availability; manage scaling.

**Karpathy Loop Implementation:**

{B11}

**Permissions:**

{B12}

**Tools:** CI/CD, deployment, monitoring, infrastructure management.

**Integration with Karpathy Agents:** receives approved code from Reviewer; outputs go to Progress Monitor.

### 7. Security Agent

**Role:** Ensures system security

**Responsibilities:** perform security audits; identify vulnerabilities; implement security measures; monitor for security issues; respond to incidents; ensure compliance.

**Karpathy Loop Implementation:**

{B13}

**Permissions:**

{B14}

**Tools:** security scanning, vulnerability assessment, security implementation, monitoring.

**Integration with Karpathy Agents:** receives code from Developer and Reviewer; outputs go to Developer (for fixes) or DevOps (for deployment).

## Integration with Karpathy Agents

### Workflow

{B15}

### Communication

Software agents communicate through state passing:

{B16}

### Testing

Each Software Agent has tests covering propose/execute/evaluate:

{B17}

## Summary

The 7 Software Agents perform the actual development, under supervision of the 8 Karpathy Agents that manage the system:

- **Product Manager** - Manages requirements
- **Architect** - Designs architecture
- **Developer** - Writes code
- **Reviewer** - Reviews code
- **Tester** - Tests code
- **DevOps** - Deploys code
- **Security** - Ensures security

**Last Updated**: July 31, 2025
"""

w.render(Path("/home/fares/Projects/graph-based-agent-system/docs/SOFTWARE-AGENTS.md"), TPL)
