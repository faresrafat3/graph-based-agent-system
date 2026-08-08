# P7 Agent Reachability Audit

**Principle under enforcement:** CONSTITUTION.md P7 — *Least Sufficient Intervention*: "Remove any checkpoint, agent, or rule that has not changed an outcome in observed runs; justify each surviving control by the failure it demonstrably catches."

**Audit type:** READ-ONLY static forensic analysis (AST import graph + grep). No repo file was modified; this document is the only artifact created.
**Repo state:** `git HEAD = 307cc18` ("auto(multi): sync 5 paths — docs, system, tests")
**Method:** Python `ast` walk over every non-vendored `.py` file (excluding `.venv`, `__pycache__`, `.pytest_cache`), building a module-level import graph, then transitive closure from each real entry point.

> **Scope warning, stated up front:** this audit establishes **reachability only**. Reachability is a *necessary* but *not sufficient* condition for an agent to be worth keeping. See [§6 What This Audit Cannot Prove](#6-what-this-audit-cannot-prove).

---

## 1. Counting note — "37 agents"

`ls agents/*.py` returns **37 files**, but one of them is `agents/__init__.py` (1 line, a bare comment). This audit therefore classifies **36 real agent modules**. The 37th file is listed separately below and is excluded from all bucket counts.

| Item | Count |
|---|---|
| Files matching `agents/*.py` | 37 |
| `agents/__init__.py` (package marker, not an agent) | 1 |
| **Real agent modules classified** | **36** |

---

## 2. Bucket definitions

| Bucket | Definition used |
|---|---|
| **LIVE** | Transitively reachable from at least one production entry point: `main.py`, `kernel/dispatch_kernel.py`, a benchmark harness (`benchmark_suite`, `humaneval_harness`, `swebench_harness`, `decomposition_bench`), or a `scripts/` runner wired into the `Makefile`. |
| **TEST-ONLY** | Imported only from `tests/`. No production entry point reaches it. Registry metadata strings do **not** count as a caller. |
| **ORPHAN** | No importer anywhere outside its own file — including tests. |
| **DEMO** | Reached only from a `*_demo.py` module or documentation, and that demo is itself not on a production path. |

**Deliberate methodological choice:** `system/governance_checks.py` `importlib`-imports every module named in `system/agent_registry.py` (`system/governance_checks.py:88`, `:143`). That makes almost every registered agent *importable* during `make audit`, but importing a module is not calling its agent function. Counting that as LIVE would make the audit vacuous — it would mark all 28 registered agents LIVE regardless of whether any logic runs. **Registry import is therefore recorded as evidence but does not confer LIVE status.** This is called out explicitly because it is the single judgement call that most affects the counts.

---

## 3. Evidence table — all 36 agent modules

Callers listed are non-self importers. `tests/*` callers are abbreviated where numerous.

### 3.1 LIVE (22)

| # | Agent | LOC | Callers (file:line) | Reached via |
|---|---|---|---|---|
| 1 | `karpathy_pipeline.py` | 508 | `main.py:21`; `benchmarks/benchmark_suite.py:9`; `scripts/run_benchmarks.py:39`; `scripts/ab_cir_study.py:27` | main pipeline head (`LIVE_ENTRYPOINT`) |
| 2 | `context_curator.py` | 217 | `agents/karpathy_pipeline.py:21`; `kernel/dispatch_kernel.py:17`; `benchmarks/humaneval_harness.py:43`; `benchmarks/swebench_harness.py:46`; `agents/competitive_slice.py:23`; `agents/domain_context_managers.py:13` | main, kernel, humaneval, swebench |
| 3 | `task_decomposer.py` | 565 | `agents/karpathy_pipeline.py:22`; `kernel/dispatch_kernel.py:18`; `benchmarks/decomposition_bench.py:345`; `scripts/run_improvement_cycle.py:64` | main, kernel, decomposition_bench |
| 4 | `deterministic_validator.py` | 514 | `agents/karpathy_pipeline.py:23`; `kernel/dispatch_kernel.py:19,20`; + 8 sibling agents (`agent_assigner.py:16`, `code_executor.py:22`, `episodic_memory_agent.py:27`, `integration_agent.py:13`, `reflexion_agent.py:36`, `semantic_memory_agent.py:27`, `task_decomposer.py:19`, `test_runner_agent.py:26`, `working_memory_agent.py:26`) | main, kernel — **most-depended-on module (13 importers)** |
| 5 | `surgical_refiner.py` | 201 | `agents/karpathy_pipeline.py:24`; `kernel/dispatch_kernel.py:21`; `benchmarks/swebench_harness.py:844` | main, kernel, swebench |
| 6 | `agent_assigner.py` | 378 | `agents/karpathy_pipeline.py:25` | main (`assign` node) |
| 7 | `domain_dispatcher.py` | 230 | `agents/karpathy_pipeline.py:26`; `agents/graph_execution_orchestrator.py:17` | main `--dispatch-domains` |
| 8 | `graph_execution_orchestrator.py` | 382 | `agents/karpathy_pipeline.py:27` | main `--orchestrate-graph` |
| 9 | `quality_reviewer.py` | 230 | `agents/karpathy_pipeline.py:28`; `agents/graph_execution_orchestrator.py:20` | main (`quality_review` node) |
| 10 | `code_executor.py` | 377 | `agents/karpathy_pipeline.py:29`; `kernel/dispatch_kernel.py:22`; `benchmarks/humaneval_harness.py:44`; `agents/debugger_agent.py:27`; `agents/filtering_clustering_agent.py:30`; `agents/sampling_agent.py:32` | main `--execute-code`, kernel, humaneval |
| 11 | `test_runner_agent.py` | 345 | `agents/karpathy_pipeline.py:30`; `kernel/dispatch_kernel.py:23` | main `--execute-code`, kernel |
| 12 | `domain_squads.py` | 173 | `agents/domain_dispatcher.py:13`; `agents/agent_assigner.py:17` | main `--dispatch-domains` |
| 13 | `domain_context_managers.py` | 95 | `agents/domain_squads.py:12`; `agents/debugger_agent.py:28`; `agents/competitive_context_manager.py:16` | main (via squads), swebench (via debugger) |
| 14 | `integration_agent.py` | 186 | `agents/graph_execution_orchestrator.py:18` (called `:217`) | main `--orchestrate-graph` |
| 15 | `progress_monitor.py` | 210 | `agents/graph_execution_orchestrator.py:19` (called `:221`) | main `--orchestrate-graph` |
| 16 | `resource_priority_agent.py` | 186 | `agents/graph_execution_orchestrator.py:21` (called `:138`) | main `--orchestrate-graph` |
| 17 | `debugger_agent.py` | 364 | `benchmarks/swebench_harness.py:839`; `scripts/measure_thrashing.py:25`; `system/bounded_probe.py:12`; `agents/competitive_slice.py:25` | swebench `--mode loop/graph`, thrash measurement |
| 18 | `reflexion_agent.py` | 322 | `benchmarks/swebench_harness.py:834`; `scripts/measure_thrashing.py:33`; `agents/competitive_slice.py:26` | swebench, thrash measurement |
| 19 | `sampling_agent.py` | 297 | `benchmarks/humaneval_harness.py:45` (called `:182`) | humaneval `--mode alphacode` |
| 20 | `filtering_clustering_agent.py` | 223 | `benchmarks/humaneval_harness.py:46` (called `:188`) | humaneval `--mode alphacode` |
| 21 | `systems_layer.py` | 289 | `scripts/run_systems_layer.py:19` (called `:46`) | `make systems-layer` |
| 22 | `disk_saver.py` | 123 | `agents/systems_layer.py:264` (default checkpointer) | `make systems-layer` |

### 3.2 LIVE-BUT-GATED (4) — reachable, but the code path is default-denied

These are structurally wired into a production graph yet **cannot execute from any production caller** because the enabling flag is set only in tests. They are counted in LIVE totals but flagged, because under P7 they are the highest-value review targets: they carry LIVE's maintenance cost with ORPHAN's runtime behaviour.

| # | Agent | LOC | Callers (file:line) | Gate |
|---|---|---|---|---|
| 23 | `agent_forge.py` | 237 | `agents/karpathy_pipeline.py:36` (called `:206`); `scripts/forge_scale_demo.py:23`; `agents/topology_assembler.py:18`; `agents/context_system_view.py:17` | `forge_node` returns early at `karpathy_pipeline.py:189-190` unless `forge_agent_graph=True`. That kwarg defaults `False` (`:465`) and **no production caller sets it** — only `tests/test_forge_node_pipeline.py:28`. |
| 24 | `topology_assembler.py` | 99 | `agents/karpathy_pipeline.py:37` (called `:217`); `scripts/forge_scale_demo.py:24` | same `forge_agent_graph` gate |
| 25 | `context_system_view.py` | 78 | `agents/karpathy_pipeline.py:38` (called `:215-216`) | same `forge_agent_graph` gate |
| 26 | `sage_council.py` | 284 | `agents/karpathy_pipeline.py:39` (called `:222`, gated); `agents/systems_layer.py:72,79` (called `:83/:85`, **ungated**) | Reachable ungated via `make systems-layer`, but subject to a complexity threshold (`systems_layer.py:90` — council convenes only when `complexity >= 4`, else `council.skip()`). |

> `sage_council` is genuinely LIVE via `scripts/run_systems_layer.py`; the gate note applies only to its `karpathy_pipeline` call site.

### 3.3 TEST-ONLY (9)

No production entry point reaches these. Where the repo's own registry claims otherwise, the discrepancy is recorded.

| # | Agent | LOC | Callers (file:line) | Registry claim vs. reality |
|---|---|---|---|---|
| 27 | `episodic_memory_agent.py` | 290 | `tests/test_episodic_memory_agent.py:4,62,83,95` only | Registered (`agent_registry.py:229`, entry `store_episode`). `store_episode` has **0** non-test callers; `retrieve_episodes` has **0** references anywhere outside its own `def`. |
| 28 | `semantic_memory_agent.py` | 291 | `tests/test_semantic_memory_agent.py:4,6,100,140` only | Registered (`:239`, entry `extract_semantic_rule`). **0** non-test callers; `get_semantic_rules` never called outside its `def`. |
| 29 | `working_memory_agent.py` | 270 | `tests/test_working_memory_agent.py:4,64,94` only | Registered (`:249`, entry `assemble_working_memory`). **0** non-test callers. |
| 30 | `decision_conflict_agent.py` | 172 | `tests/test_decision_conflict_agent.py:1` only | Registered (`:107`). `resolve_conflicts` has **0** non-test callers. Declared in `EXTERNAL_ALLOWED` (`governance_checks.py:300`) as "optional, not default-wired". |
| 31 | `human_escalation.py` | 164 | `tests/test_human_escalation.py:1` only | Registered (`:127`). `handle_escalation` has **0** non-test callers. Declared external (`governance_checks.py:301`). |
| 32 | `competitive_slice.py` | 181 | `tests/test_competitive_slice.py:4,5` only | Registered (`:218`). **Governance claim is false** — see §5.1. |
| 33 | `competitive_context_manager.py` | 105 | `tests/test_competitive_context_manager.py:4` only | Registered (`:259`). Reached only via `competitive_slice`, which is itself TEST-ONLY. Transitively dead. |
| 34 | `prime_agent_adapter.py` | 327 | `tests/test_prime_agent_adapter.py:12,138`; `tests/test_prime_agent_adapter_protocol.py:17` | **Not in registry.** `prime_agent_node` has **0** references outside its own `def` — the LangGraph node function is never added to any graph. |
| 35 | `cynefin_classifier.py` | 134 | `tests/test_cynefin_classifier.py:8` only | **Not in registry.** `classify_domain` has **0** references outside its own `def`. Referenced in CONSTITUTION.md and 3 docs, but no code path. |

### 3.4 DEMO (1)

| # | Agent | LOC | Callers (file:line) | Note |
|---|---|---|---|---|
| 36 | `intelligence_forge_demo.py` | 89 | `tests/test_intelligence_forge_demo.py:7` only | Self-identifies as a demo. **Zero doc references** and not in the registry. It *imports* four real agents (`agent_forge:18`, `context_system_view:19`, `topology_assembler:20`, `sage_council:21`, `systems_layer:22`) but nothing imports it except its own test. |

### 3.5 ORPHAN (0)

**No agent module has zero importers.** Every one of the 36 is imported by at least its own test file. This is a real finding, not an absence of one: the repo's test suite provides universal import coverage, which means **`import`-graph reachability alone can never produce an ORPHAN under this repo's conventions.** Dead code here manifests as TEST-ONLY, not ORPHAN.

### 3.6 Excluded

| File | LOC | Reason |
|---|---|---|
| `agents/__init__.py` | 1 | Package marker (`# agents/__init__.py`), contains no agent. |

---

## 4. `agents/forged/` — separate finding

**`agents/forged/` contains zero `.py` files.**

```
agents/forged/
└── __pycache__/
    ├── temp_probe_a.cpython-311.pyc
    ├── temp_probe_b.cpython-311.pyc
    ├── txn_agent.cpython-311.pyc
    └── txn_agent2.cpython-311.pyc
```

| Question | Answer |
|---|---|
| Forged `.py` agents present | **0** |
| Stale `.pyc` artifacts | 4 (`temp_probe_a`, `temp_probe_b`, `txn_agent`, `txn_agent2`) |
| Anything imports them | **No** — zero importers of `agents.forged.*` anywhere in the tree |
| `__init__.py` present | No (not an importable package) |
| Companion `docs/reconciliation/forged/` | Exists, **empty** |

**Interpretation:** the four `.pyc` files are residue from transient `forge_agent()` / `extend_registry()` test runs (cf. `tests/test_extend_registry_transactional.py`, `tests/test_forge_scale_demo.py`) whose `.py` sources were correctly cleaned up while the bytecode cache was not. Names `temp_probe_*` and `txn_agent*` match transactional-rollback test fixtures. This is consistent with the design intent recorded at `governance_checks.py:306-310` ("re-forged-per-task"): forged agents are **not** meant to persist on disk. The `.pyc` files are harmless but are untracked build residue.

> Note: the `.pyc` files were left untouched, per the read-only constraint of this audit.

---

## 5. Governance discrepancies discovered

These are secondary findings surfaced by the audit. They are recorded because P7 enforcement depends on the accuracy of the repo's own reachability bookkeeping.

### 5.1 `EXTERNAL_ALLOWED` contains a factually false justification

`system/governance_checks.py:289` declares:

```python
"run_competitive_slice": "Invoked only by benchmarks/humaneval_harness.py (AlphaCode/competitive eval)."
```

**This is false.** `grep -n "competitive" benchmarks/humaneval_harness.py` returns **no matches**. The AlphaCode arm is implemented by `solve_alphacode()` (`humaneval_harness.py:165`), which calls `sample_candidates` and `filter_and_cluster` **directly** (`:182`, `:188`) and never touches `run_competitive_slice`. `agents/competitive_slice.py` is reached by nothing but its own test.

Consequence: an agent that governance believes is exercised by the benchmark suite is in fact dead, and the declared reason suppresses the breach that `check_entrypoints_reachable` would otherwise raise. `competitive_context_manager` inherits the same false status transitively (`governance_checks.py:290`).

### 5.2 The `forge_agent_graph` subgraph is structurally live but unreachable in production

`forge_node` is a registered LangGraph node (`karpathy_pipeline.py:434`, edge `assign → forge → dispatch_orchestrate` at `:447-448`), so static analysis marks `agent_forge`, `topology_assembler`, and `context_system_view` as reachable. But `forge_node` short-circuits at `:189-190` unless `forge_agent_graph=True`, the kwarg defaults to `False` at `:465`, and **no production caller sets it** — `main.py:165-174` does not pass it and offers no CLI flag. The only `True` is `tests/test_forge_node_pipeline.py:28`.

This is precisely the failure mode `benchmarks/governance_adversarial.py:11` already documents ("the audit was green while `forge_agent_graph` output was silently dropped"). ~414 LOC (`agent_forge` 237 + `topology_assembler` 99 + `context_system_view` 78) is reachable on paper and inert in practice.

### 5.3 Registry coverage gap

28 of 36 agent modules are registered in `system/agent_registry.py`. **8 are not:** `agent_forge`, `context_system_view`, `cynefin_classifier`, `disk_saver`, `intelligence_forge_demo`, `prime_agent_adapter`, `sage_council`, `topology_assembler`. Unregistered agents bypass `check_entrypoints`, `check_permission_matrices`, and `check_entrypoints_reachable` entirely — so `cynefin_classifier` and `prime_agent_adapter` (461 LOC combined, both fully dead) are invisible to every existing governance check.

---

## 6. Summary counts per bucket

| Bucket | Count | LOC |
|---|---:|---:|
| **LIVE** | 26 | 7,149 |
| ├─ of which fully active | 22 | 6,451 |
| └─ of which LIVE-BUT-GATED (§3.2) | 4 | 698 |
| **TEST-ONLY** | 9 | 1,934 |
| **ORPHAN** | 0 | 0 |
| **DEMO** | 1 | 89 |
| **Total classified** | **36** | **9,172** |
| *Excluded:* `__init__.py` | 1 | 1 |

**Dead-weight share:** 10 of 36 modules (27.8%) and 2,023 of 9,172 LOC (22.1%) are unreachable from any production entry point. Including the LIVE-BUT-GATED subgraph, **2,721 LOC (29.7%) cannot execute in a default production run.**

> **LOC drift note:** a sibling process modified `agents/systems_layer.py` and `scripts/audit_stepfun_policy.py` at 13:06/13:10 while this audit was running. LOC figures above were recomputed at 13:15 against the working tree. `systems_layer.py` is 289 LOC in the §3.1 table (read at audit start) and 291 in this total. No classification is affected.

---

## 7. Ranked removal candidates

Ranked by strength of the P7 case: no production reachability first, then LOC (larger dead modules first, since they carry more maintenance and review cost), with governance-invisibility as a tiebreaker.

**ORPHAN tier: empty** — see §3.5. No module has zero importers.

### Tier 1 — TEST-ONLY and unregistered (invisible to all governance checks)

| Rank | Agent | LOC | Case for removal |
|---:|---|---:|---|
| 1 | `prime_agent_adapter.py` | 327 | Largest fully-dead module. Not registered; `prime_agent_node` never added to any graph; only its own 2 test files import it. |
| 2 | `cynefin_classifier.py` | 134 | Not registered. `classify_domain` has zero references outside its `def`. Cited in CONSTITUTION.md but never executed — doctrine without an implementation path. |

### Tier 2 — TEST-ONLY, registered, declared external but with a false or transitive justification

| Rank | Agent | LOC | Case for removal |
|---:|---|---:|---|
| 3 | `competitive_slice.py` | 181 | Justification at `governance_checks.py:289` is **demonstrably false** (§5.1). Nothing but its own test imports it. |
| 4 | `competitive_context_manager.py` | 105 | Only reachable via `competitive_slice` (dead) — transitively dead. Its justification inherits the same false premise. |

### Tier 3 — TEST-ONLY memory trio (registered, entrypoints never called)

| Rank | Agent | LOC | Case for removal |
|---:|---|---:|---|
| 5 | `semantic_memory_agent.py` | 291 | `extract_semantic_rule` 0 non-test callers; `get_semantic_rules` never called. |
| 6 | `episodic_memory_agent.py` | 290 | `store_episode` 0 non-test callers; `retrieve_episodes` never referenced outside its `def`. |
| 7 | `working_memory_agent.py` | 270 | `assemble_working_memory` 0 non-test callers. |

> All three are declared external as "invoked by other agents' commit steps" (`governance_checks.py:297-299`). **No such commit step exists in code.** Each defines a `commit()` method, but no production caller invokes it. Treat as one 851-LOC decision, not three.

### Tier 4 — TEST-ONLY governance escalation agents

| Rank | Agent | LOC | Case for removal |
|---:|---|---:|---|
| 8 | `decision_conflict_agent.py` | 172 | `resolve_conflicts` 0 non-test callers. Honestly declared optional — but P7 asks what failure it demonstrably catches; answer is currently none observed. |
| 9 | `human_escalation.py` | 164 | `handle_escalation` 0 non-test callers. Same reasoning. **Caution:** a human-escalation checkpoint may be justified by risk posture rather than by observed firing; P7 removal here is a governance decision, not a mechanical one. |

### Tier 5 — DEMO

| Rank | Agent | LOC | Case for removal |
|---:|---|---:|---|
| 10 | `intelligence_forge_demo.py` | 89 | Demo module with zero doc references, not registered, imported only by its own test. Lowest risk removal on this list. |

### Not removal candidates, but flagged for justification

`agent_forge` (237), `topology_assembler` (99), `context_system_view` (78) — 414 LOC that is structurally wired yet default-denied (§5.2). **The correct P7 action is a decision, not a deletion:** either expose `forge_agent_graph` as a production flag and measure it, or retire the subgraph. Leaving it reachable-but-inert is the state P7 exists to prevent.

---

## 8. What this audit CANNOT prove

**This audit measures reachability. It does not measure effect.** P7 asks whether an agent "has not changed an outcome in observed runs" — that is a *runtime* claim, and no amount of static analysis can settle it. Specifically:

1. **A LIVE agent may change nothing.** Every one of the 26 LIVE agents is reachable, but this audit provides **zero evidence** that any of them alters a final outcome. An agent can be called on every run, consume tokens and latency, and return a result that never flips a decision, never changes a score, and never catches a failure. Under P7 such an agent is *just as removable* as a dead one — and this audit cannot identify it. **Do not read "LIVE" as "justified."**

2. **Reachability is necessary, not sufficient.** The correct reading of this table is: *TEST-ONLY/DEMO agents are provably not changing production outcomes* (they never run). LIVE agents are **unproven in both directions**.

3. **Static analysis cannot see dynamic dispatch.** `system/governance_checks.py:88,143` resolves modules by string via `importlib`. Any additional string-keyed dispatch, `getattr` routing, plugin loading, or config-driven wiring would be invisible here. I found no such mechanism beyond the registry, but absence of evidence in a grep is not proof of absence.

4. **Conditional gates are not evaluated.** §5.2 was caught by reading the code, not by the import graph — which happily marked a default-denied subgraph as reachable. Other runtime conditions (env vars, complexity thresholds like `systems_layer.py:90`, `--mode` selection) may similarly render nominally-LIVE paths inert. Only the gates I inspected by hand are reported; **there may be others.**

5. **Test coverage is not outcome evidence.** That `tests/test_*.py` exercises an agent proves the code runs, not that it matters in production.

6. **No runs were executed.** Per the audit's constraints, `make test` and all benchmarks were deliberately not run. Every claim rests on `git HEAD = 307cc18` source text. **Nothing here is measured behaviour.**

### What closing the gap requires

To make P7 fully enforceable, reachability must be joined to observed effect:

- **Per-agent invocation counters** on a real benchmark run (`make benchmark`, `humaneval_harness --mode agent`, `swebench_harness --mode graph`) — separates "reachable" from "actually called."
- **Ablation A/B**: remove or no-op one agent, re-run the same suite, diff the score. If the metric is unchanged within noise, P7 says remove it. This is the *only* method that produces the evidence P7 actually demands.
- **Outcome-change ledger**: the machinery already half-exists — `system/self_pruning.py:66-80` reads `system/measurements/measurements.jsonl` for accepted proposals. That ledger is the right home for per-agent effect records; it currently tracks proposal kinds, not agent invocations.

Until those runs exist, the defensible enforcement action is limited to **the 10 candidates in §7**, whose removal is safe *precisely because* they never execute in production — the one thing this audit can prove.

---

*Generated by static AST + grep analysis at `git HEAD = 307cc18`. Read-only: no repository file was modified in producing this report.*
