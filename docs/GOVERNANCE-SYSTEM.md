# Distributed Governance System

## Purpose

This project intentionally avoids giving one agent, one LLM, or one subsystem a
supreme architectural decision role. Governance is distributed across narrow,
deterministic checks and human review points.

## Design Rule

```text
No single governance agent owns the big decision.
```

Instead, governance is split into independent systems:

| Governance System | Responsibility |
|---|---|
| Stepfun Policy Audit | Prevent unsupported LLM providers and fallback response paths |
| Agent Registry | Catalog implemented agents and lifecycle artifacts |
| Lifecycle Artifact Check | Verify docs and tests exist |
| Entrypoint Check | Verify modules and public APIs are importable/callable |
| Permission Matrix Check | Verify standard READ/WRITE/NEVER/HUMAN_CHECKPOINT shape |
| No-LLM-in-Evaluate Check | Verify deterministic evaluation boundaries |
| Pytest/Coverage Gate | Verify behavior and coverage threshold |
| Human Escalation | Handle critical decisions explicitly |

## Why Not a Governance Agent?

Large organizations, states, and mature companies do not put all constitutional
power in one person. They split authority across checks, courts, audits, boards,
procedures, and human escalation.

The same principle applies here. A single governance agent would become a risky
central authority. Even if deterministic today, it would create the wrong mental
model and could later be backed by an LLM or overloaded with policy decisions.

## Implementation

The distributed checks live in:

```text
system/governance_checks.py
scripts/audit_governance.py
system/agent_registry.py
```

They are not agents. They do not call LLMs. They only report deterministic facts.
CI fails on hard invariant breaches, but design decisions remain distributed
across specialized agents, deterministic validators, and human checkpoints.

## Local Usage

```bash
make audit
```

or:

```bash
.venv/bin/python scripts/audit_governance.py
```

## Current Scope

The checks verify:

- registry entry shape
- lifecycle docs exist
- tests exist
- modules import
- public entrypoints exist
- standard permission matrices are shaped correctly
- no `evaluate()` function calls `call_llm`

## Future Improvements

- Registry drift detection against `docs/agents/INDEX.md`
- Required lifecycle section checks
- Structured report output for CI annotations
- Separate hard-blocking checks from advisory checks
- Human approval workflow for changing governance rules
