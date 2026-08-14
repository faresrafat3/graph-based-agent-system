# Directed Survey — Inert Agents & Measurement Honesty

> generated_at: 20260814_050029  |  live_entrypoint: `run_karpathy_pipeline`
> Mode: **propose-only** (C1 default-deny) — no source mutated.

## Governance Score (F2): `0.5`
> Judges rule-adherence, NOT task success (success_rate intentionally not measured here).

## Structural Findings
- Registry size: **28**
- Name-graph reachable (system's own, upper bound): **18**
- **Call-site reachable (real invocation): 18**
- Honest inert (registered, never called, not external): **1**
- External-declared but never called: 9
- Reachable AND external (contradiction): **7**
- Live-only-via-beta (competitive subtree): 5
- Genuinely live (pipeline/orchestrator): 13
- Measurement mis-calibrated: **False**
- Classification contradiction: **True**

## Breaches (Law 3 — fail loudly)
- ⚠️ 7 agents classified BOTH reachable AND external (contradiction).
- ⚠️ 1 agents registered but never called and not declared external (silent dead weight).

## Genuinely Live (called from pipeline/orchestrator)
- ✅ Agent Assigner
- ✅ Code Executor
- ✅ Context Curator
- ✅ Deterministic Validator
- ✅ Domain Dispatcher
- ✅ Graph Execution Orchestrator
- ✅ Integration Agent
- ✅ Progress Monitor
- ✅ Quality Reviewer
- ✅ Resource & Priority Agent
- ✅ Surgical Refiner
- ✅ Task Decomposer
- ✅ Test Runner

## Live-only-via-beta (competitive_slice subtree)
- 🟡 Competitive Slice Graph
- 🟡 Debugger Agent
- 🟡 Reflexion Agent
- 🟡 Sampling Agent (AlphaCode)
- 🟡 Systems Layer (Meta-Loop)

## Honest Inert (registered, never called, not external) — P7 candidates
- ❌ Karpathy Pipeline (`run_karpathy_pipeline`)

## External-declared but never called (honest silence)
- ⚪ Competitive Context Manager
- ⚪ Decision & Conflict Agent
- ⚪ Domain Context Managers
- ⚪ Domain Squad Agents
- ⚪ Episodic Memory Agent
- ⚪ Filtering & Clustering Agent (AlphaCode)
- ⚪ Human Escalation Agent
- ⚪ Semantic Memory Agent
- ⚪ Working Memory Agent

## ⚠️ Contradiction: reachable AND external (fix double-count)
- 🔴 Competitive Slice Graph
- 🔴 Debugger Agent
- 🔴 Integration Agent
- 🔴 Progress Monitor
- 🔴 Reflexion Agent
- 🔴 Resource & Priority Agent
- 🔴 Sampling Agent (AlphaCode)

## Proposals (propose-only — apply is opt-in)
- P0: add check_entrypoints_called() to governance_checks.py (strict ast.Call) and fail/ warn-loud when name-graph reachable != call-site reachable.
- P0: enforce EXACTLY-ONE-SET invariant (reachable XOR external); fix AuthSquadAgent double-count.
- P1 (CONNECT or DELETE per P7): the inert agents below must be wired into the live path or removed from AGENT_REGISTRY.
- P1: wire self_pruning.py to the STRICT call-site reachable set so P7 prunes real silent controls.

## Inert Action Items (CONNECT | DELETE | KEEP-EXTERNAL)
- **Karpathy Pipeline** (`run_karpathy_pipeline`): CONNECT (preferred for memory/escalation) | DELETE (P7) | KEEP-EXTERNAL-ONLY-IF-JUSTIFIED

## Falsifiers (declared per dimension)
- `name_graph_reachable`: count(from _transitive_reachable) must be >= call_site_reachable; if equal AND external set empty, no gap (fails loud otherwise).
- `call_site_reachable`: count(agents with >=1 real ast.Call from another module) must be > 0; if 0, the live head is dead (critical bug).
- `inert_honest`: subset of registered NOT in call_site_reachable and NOT in EXTERNAL_ALLOWED; must be non-empty OR system's 0-inert claim is false — this is the failure we surface.
- `external_overlap`: len(reachable & EXTERNAL_ALLOWED) must == 0 (Ruling: an agent is in EXACTLY one set). Non-zero = classification bug.
- `governance_vs_success`: governance_score (does it obey rules?) reported separately from success_rate; never conflated (F2).

## Compliance
- C1_propose_only: True
- C1_no_source_mutation: True
- F2_governance_vs_success_separated: True
- Law3_fail_loud: True
