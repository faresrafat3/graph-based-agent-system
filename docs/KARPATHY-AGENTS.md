# Karpathy Meta-Agents Documentation

## Overview

The **Karpathy Meta-Agents** are the 8 orchestration and governance agents that oversee the multi-agent system. Each meta-agent is specialized, bound by explicit permission boundaries, and operates strictly through the **Karpathy Loop** (`Propose` → `Execute` → `Evaluate` → `Commit` → `Refine`).

## System Architecture & Interaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Karpathy Meta-Agents (8 Agents)                     │
│                                                                         │
│  1. Task Decomposer   →   2. Agent Assigner    →   3. Progress Monitor  │
│          ↑                        ↓                        ↓            │
│  8. Human Escalation  ←   6. Decision & Conflict   ←   4. Quality Reviewer│
│          ↑                        ↓                        ↓            │
│  7. Resource & Priority ← 5. Integration Agent                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                     Software Domain Agents (7 Agents)                    │
│   Product Manager, Architect, Developer, Reviewer, Tester, DevOps, Security │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailed Specifications of the 8 Karpathy Meta-Agents

### 1. Task Decomposer Agent (✅ Active & Implemented)

**Role:** Converts natural language requirements into structured tasks.

**Responsibilities:**
- Parse user requirements into discrete, unambiguous tasks.
- Detect potential circular dependencies in task definitions using DFS.
- Extract acceptance criteria and minimal effort estimates.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["requirements", "project_context", "constraints"],
    "WRITE": ["tasks", "metadata", "clarifications_needed"],
    "NEVER": ["code", "architecture_design", "deployment", "credentials"],
    "HUMAN_CHECKPOINT": ["vague_requirements", "ambiguous_scope"]
}
```

### 2. Agent Assigner Agent (✅ Active & Implemented)

**Role:** Maps validated structured tasks to the appropriate Software/Domain Agents based on specialization, permissions, and dependencies.

**Responsibilities:**
- Analyze task metadata, type, domain keywords, and explicit dependencies.
- Assign tasks to deterministic targets (`ProductManagerAgent`, `ArchitectAgent`, `CodeExecutorAgent`, `AuthSquadAgent`, `DatabaseSquadAgent`, `APISquadAgent`, `UISquadAgent`, `TestRunnerAgent`, `ReviewerAgent`).
- Build a Directed Acyclic Graph (DAG) execution plan with deterministic `parallel_group` values.
- Enforce Law 20 squad boundaries before downstream execution.

**Karpathy Loop Implementation:**
```python
class AgentAssignerMetaAgent:
    def propose(self, state):
        """Map tasks to specialized domain agents based on DAG dependencies"""
        tasks = state["tasks"]
        assignments = self.map_agent_capabilities(tasks)
        return {"assignments": assignments}

    def execute(self, state):
        """Construct execution graph nodes and state channels"""
        assignments = state["assignments"]
        execution_plan = self.build_execution_schedule(assignments)
        return {"execution_plan": execution_plan}

    def evaluate(self, state):
        """Verify that every task has a valid assigned agent and no unmapped nodes exist"""
        plan = state["execution_plan"]
        valid = all(node.get("assigned_agent") is not None for node in plan)
        return {"success": valid}

    def commit(self, state):
        """Dispatch execution plan to LangGraph orchestration layer"""
        self.dispatch_plan(state["execution_plan"])
        return {"committed": True}

    def refine(self, state):
        """Re-map unassigned nodes or resolve agent capability mismatches"""
        return {"retry_count": state.get("retry_count", 0) + 1}
```

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["tasks", "agent_capabilities", "dag_constraints"],
    "WRITE": ["agent_assignments", "execution_schedule"],
    "NEVER": ["source_code", "database_access", "production_deploy"],
    "HUMAN_CHECKPOINT": ["unassigned_custom_tasks", "conflicting_agent_roles"]
}
```

### 3. Progress Monitor Agent (✅ Active & Implemented)

**Role:** Tracks task execution, monitors system health, and detects bottlenecks or deadlocks.

**Responsibilities:**
- Monitor active state graph execution.
- Detect stalled agents or execution timeouts.
- Trigger retry or rerouting mechanisms upon failures.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["active_graph_state", "agent_logs", "timeouts"],
    "WRITE": ["progress_metrics", "stalled_task_flags"],
    "NEVER": ["modify_code", "override_permissions"],
    "HUMAN_CHECKPOINT": ["unresponsive_agent_execution", "system_timeout"]
}
```

### 4. Quality Reviewer Agent (✅ Active & Implemented)

**Role:** Evaluates global quality metrics and enforces Constitution Quality Gates before phase transitions.

**Responsibilities:**
- Enforce test coverage thresholds (> 80%).
- Ensure all acceptance criteria defined during decomposition are met.
- Reject sub-standard agent outputs before final commit.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["agent_outputs", "test_reports", "quality_metrics"],
    "WRITE": ["approval_status", "quality_reports", "rejection_reasons"],
    "NEVER": ["bypass_tests", "force_commit_failed_code"],
    "HUMAN_CHECKPOINT": ["critical_quality_gate_failure"]
}
```

### 5. Integration Agent (✅ Active & Implemented)

**Role:** Aggregates outputs from multiple Software Agents into a coherent unified system.

**Responsibilities:**
- Merge code, documentation, and configuration outputs.
- Verify end-to-end cohesion across modular components.
- Prepare complete release artifacts.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["software_agent_artifacts", "module_exports"],
    "WRITE": ["unified_bundle", "integration_manifest"],
    "NEVER": ["deploy_untested_bundle", "override_security_blocks"],
    "HUMAN_CHECKPOINT": ["major_version_release"]
}
```

### 6. Decision & Conflict Agent (✅ Active & Implemented)

**Role:** Resolves conflicting recommendations between domain agents (e.g., Security Agent vs. Developer Agent).

**Responsibilities:**
- Evaluate trade-offs between speed, security, and architectural purity.
- Apply Constitution priority rules to break deadlocks.
- Escalate unresolved architectural disputes to humans.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["agent_disputes", "constitution_rules", "tradeoff_logs"],
    "WRITE": ["conflict_resolutions", "binding_decisions"],
    "NEVER": ["breach_constitution", "grant_unauthorized_permissions"],
    "HUMAN_CHECKPOINT": ["unresolvable_architectural_dispute"]
}
```

### 7. Resource & Priority Agent (✅ Active & Implemented)

**Role:** Manages token limits, API rate limits, and task execution priorities.

**Responsibilities:**
- Throttles agent LLM requests to stay within rate limits.
- Prioritizes high-impact tasks in resource-constrained environments.
- Monitors token consumption metrics across providers.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["token_usage", "api_rate_limits", "queue_priority"],
    "WRITE": ["rate_limit_throttling", "queue_order"],
    "NEVER": ["exceed_hard_budget", "disable_rate_limiters"],
    "HUMAN_CHECKPOINT": ["token_budget_exhaustion"]
}
```

### 8. Human Escalation Agent (✅ Active & Implemented)

**Role:** Handles explicit human interventions, escalation loops, and `HUMAN_CHECKPOINT` triggers.

**Responsibilities:**
- Present structured choices to the human user when agents hit permission bounds or max retries.
- Capture human feedback and feed it back into the Karpathy Loop `refine` step.
- Resume state machine execution safely after human approval.

**Permissions:**
```python
PERMISSIONS = {
    "READ": ["escalation_reasons", "blocked_states", "human_inputs"],
    "WRITE": ["human_decision_logs", "resume_signals"],
    "NEVER": ["bypass_human_response", "auto_approve_checkpoints"],
    "HUMAN_CHECKPOINT": ["always_active"]
}
```

## Karpathy Meta-Agents Summary Table

| # | Meta-Agent | Primary Function | State | Karpathy Loop Status |
|---|------------|------------------|-------|----------------------|
| 1 | **Task Decomposer** | Converts requirements to tasks | ✅ Done | ✅ Implemented & Tested |
| 2 | **Agent Assigner** | Assigns tasks to domain agents | ✅ Done | ✅ Implemented & Tested |
| 3 | **Progress Monitor** | Tracks execution & health | ✅ Done | ✅ Implemented & Tested |
| 4 | **Quality Reviewer** | Enforces quality gates | ✅ Done | ✅ Implemented & Tested |
| 5 | **Integration** | Merges modular outputs | ✅ Done | ✅ Implemented & Tested |
| 6 | **Decision & Conflict** | Resolves agent disputes | ✅ Done | ✅ Implemented & Tested |
| 7 | **Resource & Priority** | Manages rate limits & budget | ✅ Done | ✅ Implemented & Tested |
| 8 | **Human Escalation** | Manages human checkpoints | ✅ Done | ✅ Implemented & Tested |

---

**Last Updated**: July 31, 2025
