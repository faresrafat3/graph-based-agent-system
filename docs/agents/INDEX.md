# Per-Agent Lifecycle Documentation Index

This directory contains one lifecycle document per agent/component.

## Implemented Agents

| Agent | Document |
|---|---|
| Context Curator | [context-curator.md](context-curator.md) |
| Task Decomposer | [task-decomposer.md](task-decomposer.md) |
| Deterministic Validator | [deterministic-validator.md](deterministic-validator.md) |
| Surgical Refiner | [surgical-refiner.md](surgical-refiner.md) |
| Agent Assigner | [agent-assigner.md](agent-assigner.md) |
| Code Executor | [code-executor.md](code-executor.md) |
| Test Runner | [test-runner.md](test-runner.md) |
| Domain Context Managers | [domain-context-managers.md](domain-context-managers.md) |
| Domain Dispatcher | [domain-dispatcher.md](domain-dispatcher.md) |
| Graph Execution Orchestrator | [graph-execution-orchestrator.md](graph-execution-orchestrator.md) |
| Auth Squad Agent | [auth-squad-agent.md](auth-squad-agent.md) |
| Database Squad Agent | [database-squad-agent.md](database-squad-agent.md) |
| API Squad Agent | [api-squad-agent.md](api-squad-agent.md) |
| UI Squad Agent | [ui-squad-agent.md](ui-squad-agent.md) |
| Karpathy Pipeline | [karpathy-pipeline.md](karpathy-pipeline.md) |

## Governance Agents

| Agent | Document |
|---|---|
| Progress Monitor | [progress-monitor.md](progress-monitor.md) |
| Quality Reviewer | [quality-reviewer.md](quality-reviewer.md) |
| Integration Agent | [integration-agent.md](integration-agent.md) |
| Decision & Conflict Agent | [decision-conflict-agent.md](decision-conflict-agent.md) |
| Resource & Priority Agent | [resource-priority-agent.md](resource-priority-agent.md) |
| Human Escalation Agent | [human-escalation-agent.md](human-escalation-agent.md) |

## Related System Docs

- [System Lifecycle](../SYSTEM-LIFECYCLE.md)
- [Combined Agent Lifecycle Reference](../AGENT-LIFECYCLE.md) — includes the shared `build_karpathy_loop` factory contract
- [Architecture](../ARCHITECTURE.md) — Karpathy Loop factory + installed-package layout
- [Quality Audit Plan](../QUALITY-AUDIT-PLAN.md)

## Shared Agent Structure

All agents build their Karpathy Loop graph through the shared factory in
`kernel/karpathy_loop.py` (`build_karpathy_loop`), supplying their `execute` node
and overriding only the nodes their lifecycle specialises. See the
[Global Agent Lifecycle Standard](../AGENT-LIFECYCLE.md) for the factory contract
and the per-node defaults.
