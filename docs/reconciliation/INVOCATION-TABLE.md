# Empirical Agent Invocation Table

Measured, not inferred. Every number below came from a runtime counter wrapped around
each of the 28 `entrypoint` symbols declared in `system/agent_registry.py`.

## Headline result

- **0 of 28 agents are INERT.** All 28 entrypoints were observed executing at least once.
- **6 of 28 run on the default real pipeline** (no optional flags).
- **8 more run only when opt-in flags are passed** (`--orchestrate-graph`, `--dispatch-domains`, `--execute-code`).
- **14 of 28 executed only under the test suite** and were never reached by any real CLI run attempted here.
- Of the 9 entrypoints previously suspected inert: **1 is refuted outright** (it runs on a real flagged path),
  and **8 are reclassified from INERT to TEST-ONLY** — they do execute, but only tests call them.

⚑ marks the 9 entrypoints that static analysis flagged as suspected inert.

| # | Agent | Entrypoint | Tests | Real (default) | Real (all flags) | Verdict |
|---|-------|-----------|------:|---------------:|-----------------:|---------|
| 1 | Agent Assigner | `agent_assigner.assign_tasks` | 14 | 1 | 1 | **LIVE** |
| 2 | Context Curator | `context_curator.curate_context` | 19 | 1 | 1 | **LIVE** |
| 3 | Deterministic Validator | `deterministic_validator.validate_output` | 12 | 1 | 1 | **LIVE** |
| 4 | Karpathy Pipeline | `karpathy_pipeline.run_karpathy_pipeline` | 15 | 1 | 1 | **LIVE** |
| 5 | Quality Reviewer | `quality_reviewer.review_quality` | 24 | 1 | 1 | **LIVE** |
| 6 | Task Decomposer | `task_decomposer.decompose_requirements` | 24 | 1 | 1 | **LIVE** |
| 7 | Code Executor | `code_executor.execute_task` | 4 | 0 | 3 | **LIVE (opt-in flags)** |
| 8 | Domain Context Managers ⚑ | `domain_context_managers.BaseDomainContextManager` | 24 | 0 | 1 | **LIVE (opt-in flags)** |
| 9 | Domain Dispatcher | `domain_dispatcher.dispatch_domain_tasks` | 11 | 0 | 3 | **LIVE (opt-in flags)** |
| 10 | Graph Execution Orchestrator | `graph_execution_orchestrator.orchestrate_graph_execution` | 5 | 0 | 1 | **LIVE (opt-in flags)** |
| 11 | Integration Agent | `integration_agent.integrate_artifacts` | 11 | 0 | 1 | **LIVE (opt-in flags)** |
| 12 | Progress Monitor | `progress_monitor.monitor_progress` | 11 | 0 | 1 | **LIVE (opt-in flags)** |
| 13 | Resource & Priority Agent | `resource_priority_agent.prioritize_resources` | 13 | 0 | 3 | **LIVE (opt-in flags)** |
| 14 | Test Runner | `test_runner_agent.run_code_and_tests` | 10 | 0 | 3 | **LIVE (opt-in flags)** |
| 15 | Competitive Context Manager ⚑ | `competitive_context_manager.CompetitiveContextManager` | 6 | 0 | 0 | **TEST-ONLY** |
| 16 | Competitive Slice Graph ⚑ | `competitive_slice.run_competitive_slice` | 4 | 0 | 0 | **TEST-ONLY** |
| 17 | Debugger Agent | `debugger_agent.debug_code` | 5 | 0 | 0 | **TEST-ONLY** |
| 18 | Decision & Conflict Agent ⚑ | `decision_conflict_agent.resolve_conflicts` | 5 | 0 | 0 | **TEST-ONLY** |
| 19 | Domain Squad Agents ⚑ | `domain_squads.AuthSquadAgent` | 7 | 0 | 0 | **TEST-ONLY** |
| 20 | Episodic Memory Agent ⚑ | `episodic_memory_agent.store_episode` | 5 | 0 | 0 | **TEST-ONLY** |
| 21 | Filtering & Clustering Agent (AlphaCode) | `filtering_clustering_agent.filter_and_cluster` | 3 | 0 | 0 | **TEST-ONLY** |
| 22 | Human Escalation Agent ⚑ | `human_escalation.handle_escalation` | 3 | 0 | 0 | **TEST-ONLY** |
| 23 | Reflexion Agent | `reflexion_agent.generate_reflection` | 7 | 0 | 0 | **TEST-ONLY** |
| 24 | Sampling Agent (AlphaCode) | `sampling_agent.sample_candidates` | 6 | 0 | 0 | **TEST-ONLY** |
| 25 | Semantic Memory Agent ⚑ | `semantic_memory_agent.extract_semantic_rule` | 8 | 0 | 0 | **TEST-ONLY** |
| 26 | Surgical Refiner | `surgical_refiner.generate_refinement_feedback` | 2 | 0 | 0 | **TEST-ONLY** |
| 27 | Systems Layer (Meta-Loop) | `systems_layer.build_systems_graph` | 10 | 0 | 0 | **TEST-ONLY** |
| 28 | Working Memory Agent ⚑ | `working_memory_agent.assemble_working_memory` | 5 | 0 | 0 | **TEST-ONLY** |

Verdict tally: **LIVE 6 · LIVE (opt-in flags) 8 · TEST-ONLY 14 · INERT 0**

## Verdict definitions

| Verdict | Meaning |
|---------|---------|
| `LIVE` | Executed on the default real pipeline run (`main.py` with no optional flags). |
| `LIVE (opt-in flags)` | Never ran by default; did run on a real pipeline invocation once optional flags were enabled. Real production code path, just not the default one. |
| `TEST-ONLY` | Executed under `pytest` but not reached by any real pipeline run attempted here. The symbol is real and working; nothing on the measured runtime paths calls it. |
| `INERT` | Never executed anywhere, under tests or a real run. **No agent earned this verdict.** |

## Method

A standalone instrument at `tools/invocation_counter/` reads `AGENT_REGISTRY`, imports each
declared `module`, and replaces each `entrypoint` with a counting wrapper that increments a
tally and then delegates to the original with unchanged arguments and return value.

- **Functions** are wrapped with a `functools.wraps` passthrough.
- **Classes** (`BaseDomainContextManager`, `AuthSquadAgent`, `CompetitiveContextManager`) are
  counted by wrapping `__init__` on the class itself, so subclass instantiation is also captured
  and the class object identity, `isinstance` checks, and inheritance all keep working.
- **Alias rebinding.** A module-level patch alone is not enough: any module that had already run
  `from agents.x import func` holds a reference to the *original* function and would bypass the
  wrapper, producing false `INERT` verdicts. The instrument therefore sweeps every loaded module in
  `sys.modules` and rebinds stale aliases. This mattered: `integrate_artifacts`, `monitor_progress`,
  and `prioritize_resources` were each reached *only* through a stale alias and would have been
  misreported as never-called without it.
- **Self-validation.** Before trusting any verdict, the instrument was verified against a
  purpose-built case confirming that (a) wrapped calls are counted, (b) return values and
  signatures are unchanged, and (c) calls arriving through a pre-existing `from ... import`
  alias are captured.

### Commands run

```bash
# under tests
AGENT_INVOCATION_COUNTER=1 AGENT_COUNTER_OUT=/tmp/counts_tests.json \
  PYTHONPATH=tools/invocation_counter:. \
  .venv/bin/python -m pytest -q -p pytest_agent_counter

# real run, default path
AGENT_COUNTER_OUT=/tmp/counts_real2.json PYTHONPATH=tools/invocation_counter:. \
  .venv/bin/python tools/invocation_counter/run_real.py -- --requirements "..."

# real run, all optional flags
AGENT_COUNTER_OUT=/tmp/counts_real3.json PYTHONPATH=tools/invocation_counter:. \
  .venv/bin/python tools/invocation_counter/run_real.py -- --requirements "..." \
    --orchestrate-graph --dispatch-domains --execute-code
```

The test suite passed **1184 passed** with the instrument active, confirming the wrappers are
behaviour-preserving.

## Limitations

These bound how far the table should be read.

1. **"TEST-ONLY" is not proof of unreachability.** It means *the runs measured here* never reached
   the agent. A different requirement string, config, or flag combination could reach some of them.
   Absence of a call is evidence about the paths exercised, not a universal claim.
2. **The all-flags run did not complete.** It failed partway with a Stepfun API read timeout after
   real work (14 distinct entrypoints already counted). Counts from it are a **lower bound** — a
   fully successful flagged run could reach more agents. The default-path run did complete cleanly
   (`exit_code=0`).
3. **Only one real requirement was exercised per configuration**, and the pipeline is
   LLM-driven and non-deterministic. Routing decisions can vary between runs with identical input.
4. **Counts are per-symbol, not per-call-site.** The table shows that an entrypoint ran, not which
   caller invoked it.
5. **Class entrypoints count instantiation, not use.** `BaseDomainContextManager` counts `__init__`;
   a subclass constructed but never otherwise used still registers. Concrete subclass observed on
   the flagged real run: `['APIContextManager']`.
6. **Network-dependent.** Real runs consume live API credentials; results depend on upstream
   availability, as limitation 2 demonstrates.
7. **No import hook.** Aliases are rebound once, at install time. If a module were imported *after*
   installation and bound a function alias at import, calls through that alias would go uncounted.
   In practice the counter installs before the pipeline runs and all 28 symbols were successfully
   wrapped (`failed_to_wrap` was empty in every run), so this did not affect the results — but it
   is a real ceiling on the method, and it can only cause under-counting, never over-counting.

## Two registry claims that did not hold up

While tracing expected callers, two statements in the registry's own exemption notes were checked
against the source and found inaccurate:

- The note that `run_competitive_slice` is driven by the benchmark harness: `benchmarks/` contains
  **no reference at all** to `competitive_slice`.
- The note that the memory agents (`store_episode`, `extract_semantic_rule`,
  `assemble_working_memory`) are "invoked by other agents' commit steps": a search across
  `agents/`, `scripts/`, `benchmarks/`, `kernel/`, and `main.py` found **no non-test caller**,
  which matches their measured zero on every real run.

Also worth flagging: the CLI summary reports `domain_dispatch_success: true` even when dispatch is
skipped entirely — it is a hardcoded default, not evidence of execution. The counter recorded 0
calls to `dispatch_domain_tasks` on the same run that reported success.

## Removing the instrument

Fully additive. Delete `tools/invocation_counter/` and this file. No existing repo module was
modified; the plugin is loaded only via an explicit `-p` flag or the wrapper script, and writes
output only when `AGENT_COUNTER_OUT` is set.
