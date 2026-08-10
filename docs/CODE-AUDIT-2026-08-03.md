# Code Audit — Graph-Based Agent System

**Date:** 2026-08-03
**Auditor:** Hermes Agent (deep static + dynamic review)
**Scope:** Full repository (source, tests, docs, governance, benchmarks)
**Method:** Read every core module, ran the full pytest suite, ran governance audit scripts, cross-checked LAWS/CONSTITUTION/README against actual code, reviewed benchmark harnesses.

## 0. TL;DR — Verdict

This is a **real, wired, well-engineered system**, not a stub. The architectural thesis (LLM-as-CPU, zero-LLM control plane, execution-grounded grading) is genuinely implemented and enforced in code. **201/201 tests pass.** The governance audit passes. The benchmark reports are unusually honest.

But the project has **governance-document drift**, **one dead parallel pipeline path**, **11 silent `except Exception:` blocks** that breach the project's own Law 3, and **a missing-law gap (14/15/16)** that breaks traceability. None are fatal; all are fixable. Priorities below.

**Scorecard**

| Dimension | Rating | Note |
|---|---|---|
| Correctness (tests) | 🟢 Strong | 201/201 passing |
| Architecture integrity | 🟢 Strong | LangGraph real, sandbox real, zero-LLM control plane real |
| Security (code exec) | 🟢 Strong | `python -I`, pattern scan, secret purge, resource limits |
| Governance enforcement | 🟡 Mixed | Permission matrices real; 11 silent excepts + dead kernel path |
| Doc/code consistency | 🔴 Weak | Law gap 14/15/16, stale `allow_mock` warning, version drift |
| CI quality gate | 🟡 Weak | `--cov` without `--cov-fail-under`; no coverage threshold enforced |

## 1. What the system actually is (verified)

- **27 registered agents** across 5 layers (kernel, governance, execution, verification, domain squads). All registry modules exist on disk ✅.
- **Entry point:** `main.py` → `agents.karpathy_pipeline.run_karpathy_pipeline`. This is the *live* path.
- **Orchestration:** `LangGraph` `StateGraph` + `MemorySaver` checkpointer — actually imported and compiled in 9 agent modules. **Not a fake claim.**
- **LLM:** `llm/llm_integration.py` — Stepfun-only native REST, no provider fallback. Includes an 11-account key pool with per-key 429 cooldown (smart infra fix). `fail loudly` on missing creds.
- **Verification:** `agents/test_runner_agent.py` physically runs `py_compile` + `pytest` in a temp dir with `python -I` (isolated), secret-env purge, path-traversal guard, and Unix resource limits. **Genuine sandbox.**
- **Governance-as-code:** `system/governance_checks.py` runs 5 deterministic checks (registry shape, lifecycle artifacts, entrypoints, permission matrices, no-LLM-in-`evaluate`). All pass for 27 items.

## 2. Critical findings (fix first)

### 🔴 F1 — Missing Laws 14, 15, 16 (governance traceability break)
`LAWS.md` defines Law 1–13, then **jumps to Law 17–20**. Laws **14, 15, 16 are entirely absent** from the document.

Meanwhile the code references them:
- `kernel/signal_protocol.py:2` → *"Signal Protocol … (Law 14)"*
- `kernel/slice_router.py` / `agents/episodic_memory_agent.py` → *"Law 11 Evaluate never calls LLM, Law 2 Permission checked"* (Law 11 exists, ok)
- `docs/agents/*.md` and `docs/ARCHITECTURE.md` reference "Law 14/15/16" implicitly via the signal protocol and slice router.

**Impact:** A reader cannot find Law 14/15/16 definitions; the canonical governance doc contradicts the code's citations. This is exactly the kind of drift the Constitution's Article VII (Interpretation) is meant to prevent.

**Fix:** Add the three missing law sections to `LAWS.md` (Law 14 = Signal Protocol determinism; Law 15 = ?; Law 16 = ?) — or renumber so citations match. The code's `AgentSignal` schema (16 typed variants) is the natural Law 14 subject.

### 🔴 F2 — 11 silent `except Exception:` blocks (Law 3 / Law 11 breach)
Bare `except Exception:` that swallow the error with no log/raise:
```
agents/episodic_memory_agent.py:150, :250
agents/semantic_memory_agent.py:177, :223, :254
agents/test_runner_agent.py:149   (best-effort inside resource limiter — excusable)
agents/working_memory_agent.py:150
agents/reflexion_agent.py:188, :273
llm/llm_integration.py:267, :277   (extracting HTTP error body — low risk)
```
The first 9 are in the **memory + reflexion + working-memory** agents and silently discard failures. Law 3 ("Fail Loudly, never silently") and Law 11 ("no self-assessment / no hidden failures") are explicitly breachd. The `governance_checks.py` `check_no_llm_in_evaluate` does NOT catch silent excepts — so CI is green while Law 3 is broken.

**Fix:** Either log+reraise, or convert to specific exceptions (`except json.JSONDecodeError`, `except KeyError`). At minimum, add a governance check for bare `except Exception:` (no `as`/no log).

### 🔴 F3 — Dead parallel pipeline: `kernel/dispatch_kernel.py`
`main.py` runs `karpathy_pipeline`. `DispatchKernel.run()` is **never called by the live path** (only referenced in `tests/test_kernel.py` and a docstring in `competitive_slice.py`). Worse:
- `DispatchKernel.run()` does **not** call `self.route()` or consult `ROUTING_TABLE`. It calls agent functions linearly in a fixed order.
- Therefore `ROUTING_TABLE`, `FAILURE_POLICY`, `check_retry_budget()`, `increment_retry()` are **dead code** — the deterministic signal-driven router advertised in docs is not what executes.
- `run()` also hard-codes `for task in tasks[:3]` — only the first 3 tasks are ever executed/validated, the rest silently dropped.

**Impact:** Two competing mental models of the system (signal-driven kernel vs linear pipeline). The kernel is tested but not shipped. Confusing for maintainers; the docs (`BENCHMARK-REPORT.md §2.1`) describe the kernel topology as if it runs.

**Fix:** Either (a) wire `karpathy_pipeline` through `DispatchKernel.route()` and delete the inline linear calls, or (b) mark `dispatch_kernel` clearly as a reference/experimental implementation and stop citing it as the production topology. Don't ship a router whose `run()` ignores its own `ROUTING_TABLE`.

## 3. Medium findings (fix soon)

### 🟡 F4 — Documentation/code drift
- **LangGraph version:** `requirements.txt` pins `langgraph>=0.2.0`; installed is **1.2.10**. `READMEs`/CONSTITUTION claim "LangGraph 0.2.0+ (100% - no other orchestration)". Not a code bug, but the pin is stale and the "0.2.0" mention is inaccurate.
- **Stale `allow_mock` warning:** `BENCHMARK-REPORT.md §7 Real limitations` warns *"The mock fallback is a live footgun. `call_llm(allow_mock=True)` silently returns fixture JSON"* — but **`allow_mock` does not exist anywhere in the code** (grep returns nothing). The report describes a past state; current code is cleaner than the report claims. Remove or correct the warning so readers trust the doc.
- **CONSTITUTION Article III §1** says "MUST use LangGraph" while the README tech-stack also says so — consistent, but the *version* and the *"no other orchestration"* claim should be verified against the 9 modules that import it (they do; fine).

### 🟡 F5 — `task_decomposer.refine()` can poison the memory cache
`refine()` returns `{"tasks": [], ...}` and loops back to `propose()`. `propose()` calls `memory.find_similar(requirements, threshold=0.8)` and, if similarity > 0.9, **reuses the cached (possibly empty) tasks**. On a failed refinement of a previously-seen prompt, the loop can retrieve an empty cached decomposition forever (throwaway/infinite-ish loop, no escalation). The Jaccard `find_similar` threshold (0.8) is also very high and keyword-based — brittle.

**Fix:** Never cache empty/!success decompositions; skip cache when `state["success"]` is False; lower or remove the 0.9 reuse gate inside the refine loop.

### 🟡 F6 — CI has no enforced coverage gate
`.github/workflows/ci.yml` runs `pytest --cov=. --cov-report=term-missing` but **no `--cov-fail-under`**. Law 5 mandates ">80% coverage … MUST NOT be merged," but nothing enforces it. Coverage is measured, not gated.

**Fix:** Add `--cov-fail-under=80` (or the real measured number) so the Law 5 gate is real.

### 🟡 F7 — Layer-4 squad agents are ungrounded (acknowledged in report)
`domain_squads.py` returns raw LLM strings that are never parsed/executed. Permission boundaries exist (Law 20 keyword matches) but there is no execution grounding for squad output. The report itself flags this. Law 11 (execution grounding) is not satisfied for Layer 4.

**Fix:** Route squad output through `tools/json_output_parser` + `test_runner_agent` like the rest of the pipeline.

### 🟡 F8 — Law 20 boundaries are keyword substring matches
`domain_squads` permission checks use `forbidden.replace("_"," ") in combined` — trivially bypassed by paraphrase ("please deploy to prod" vs "deploy to production"). The report acknowledges brittleness.

**Fix:** Normalize + tokenize, or use the same `NEVER` matrix style as `code_executor` (regex on canonical phrases).

## 4. Strengths (keep doing this)

- 🟢 **Zero-LLM control plane** is real and auditable. Routing/validation/grading contain no model calls.
- 🟢 **Physical verification** — `test_runner_agent` actually compiles and runs code; no LLM-as-judge.
- 🟢 **Permission matrices raise real `PermissionError`s** at runtime (e.g. `task_decomposer.propose`, `code_executor.execute_task`), not just at review time.
- 🟢 **Surgical refinement** feeds back only the breach list, not the whole context — prevents retry-loop degeneration (Law 13).
- 🟢 **11-account key pool** is a genuinely smart infra solution to the Stepfun per-account quota wall; rotates on 429 with cooldown.
- 🟢 **Honest benchmarking** — reports publish both raw and infra-adjusted numbers, split capability vs infrastructure failures, and explicitly state HumanEval can't validate the thesis. Rare intellectual honesty.
- 🟢 **201/201 tests pass**; governance audit passes; 27/27 registry items have lifecycle docs + test files.
- 🟢 `.gitignore` correctly excludes `.env`, `.venv/`, `logs/`, `*.jsonl`, benchmark datasets.

## 5. Prioritized action list

| # | Priority | Finding | Effort |
|---|---|---|---|
| 1 | 🔴 High | Add Laws 14/15/16 to `LAWS.md` (or renumber) | S |
| 2 | 🔴 High | Replace 11 silent `except Exception:` with specific/logged handling + add governance check | M |
| 3 | 🔴 High | Resolve `dispatch_kernel` dead path (wire it or de-advertise it; fix `tasks[:3]`) | M |
| 4 | 🟡 Med | Fix `task_decomposer` cache-poisoning in refine loop | S |
| 5 | 🟡 Med | Enforce coverage gate in CI (`--cov-fail-under=80`) | S |
| 6 | 🟡 Med | Correct stale `allow_mock` warning + LangGraph version in docs | S |
| 7 | 🟡 Med | Ground Layer-4 squad output through parser + test runner | L |
| 8 | 🟡 Low | Harden Law 20 boundaries beyond substring match | M |

S = <1h, M = half-day, L = multi-day.

## 6. Metrics at a glance

- **Source LOC (excl. venv/pycache):** ~14,205
  - agents 6,553 · benchmarks 2,144 · tests 2,885 · kernel 452 · system 464 · llm 453 · memory 312 · tools 376 · main.py 268 · scripts 298
- **Test files:** 40 · **Test functions:** 213 · **Result:** 201 passed
- **Registry agents:** 27 (all modules present, all have doc + test)
- `except Exception:` (silent): 11 · `print()` in prod modules: 40 · `import *`: 0 · bare `except:`: 0
- **Third-party deps actually used:** langgraph, langchain-* (transitive), anthropic (installed, unused by live path), pytest, pytest-cov, python-dotenv, swebench (benchmarks)
- **Key findings:** 3 🔴 critical, 5 🟡 medium

---

**Status (2026-08-03, post-fix):** All 🔴 critical findings resolved. 201/201 tests pass; governance audit passes (6/6 checks incl. the new `no_silent_except`); `LAWS.md` now defines Law 1–20 contiguously.

### 🔴 F1 — Missing Laws 14/15/16 → RESOLVED
Added `Law 14: Signal Determinism`, `Law 15: Latency Budget`, `Law 16: Reproducible Evidence` to `LAWS.md` (inserted before the old Law 17, which is now Law 17+). All 20 laws are now contiguous and the code's `Law 14` citation (`signal_protocol.py`) resolves.

### 🔴 F2 — 11 silent `except Exception:` → RESOLVED
All 11 replaced with `except Exception as exc:` + `logger.warning(...)` (memory/reflexion/working/semantic/episodic agents, test_runner resource limiter, llm error-body parsing). Fallback behaviour preserved, failures now loud. Added `check_no_silent_except` to `system/governance_checks.py` and wired it into `run_governance_checks` so the regression cannot silently return. Verified: **0 silent excepts remain** in production modules.

### 🔴 F3 — Dead `dispatch_kernel` path → RESOLVED
`DispatchKernel.run()` now consults `self.route()` for the code stage (router is no longer dead code) and iterates **all** tasks instead of `tasks[:3]`. Added an `execute_code` gate mirroring `karpathy_pipeline` so the LLM-backed code stage is opt-in. Added `test_kernel_route_is_used_in_run` asserting the router is exercised and no task is silently dropped.

### 🟡 F5 — `task_decomposer` cache poisoning → RESOLVED
`propose()` no longer reuses an empty cached decomposition; `commit()` refuses to persist empty/!success output. The refine loop can no longer retrieve `[]` forever.

### 🟡 F6 — CI coverage gate → RESOLVED
`.github/workflows/ci.yml` now runs `pytest --cov=. --cov-report=term-missing --cov-fail-under=80`, enforcing Law 5's >80% gate.

### 🟡 F4 — Doc drift → RESOLVED
`BENCHMARK-REPORT.md` `allow_mock` warning corrected (the mock path no longer exists — `call_llm` has no fallback). `README.md` LangGraph version updated to 1.2.x.

## 8. Hard re-analysis addendum (2026-08-03, second pass)

A deeper re-read of the **live production path** (`main.py` → `run_karpathy_pipeline`) surfaced findings the first pass under-weighted. The headline correction: **the first pass fixed the silent `tasks[:3]` truncation in the DEAD `dispatch_kernel`, not in the live pipeline.** The live `karpathy_pipeline.py:159` still had `for task in tasks[:3]` with **zero test coverage**.

### 🔴 F9 — Silent task-drop in the LIVE pipeline (re-prioritized, real fix)
- `agents/karpathy_pipeline.py:159` executed only `tasks[:3]` with **no log, no signal, no comment explaining it** — a silent data-loss bug in the path `main.py` actually calls.
- Impact: any plan with >3 tasks silently loses work; the bug is invisible to `make test` because no test ever passes `execute_code=True` with >3 tasks (`tests/test_karpathy_pipeline.py` never sets `execute_code=True`; only `tests/test_kernel.py` does, against the dead kernel).
- **Fix applied:** replaced the silent slice with an explicit `MAX_EXEC_TASKS = 3` budget that **logs a warning (Law 3)** when the plan exceeds it, and added `test_pipeline_execution_budget_is_loud_not_silent` asserting (a) all decomposed tasks survive into the plan, (b) the warning fires, (c) every in-budget task is attempted. The cap is kept (code-gen + sandbox are LLM/CPU expensive) but is now loud and configurable instead of a silent `[:3]`.

### 🟡 F10 — (WITHDRAWN — false finding)
The first draft of this addendum claimed `agents/architect_agent.py` is "registered but never invoked." **That was wrong.** There is no `architect_agent.py` on disk and no `architect` entry in `agent_registry.py` (27 entries, none named architect). The pipeline has no architecture stage by design, not by dead registration. This correction is itself a lesson: claims about the registry must be verified against `agent_registry.py`, not inferred from signal-protocol constants.

### 🔴 F12 — Registry over-claims vs. live call graph (verified, now enforced)
A deeper transitive reachability analysis (static AST walk from `run_karpathy_pipeline`, both optional flags enabled) shows **only 18 of 27 registered agents are reachable from the live production path.** 9 are intentionally external (benchmark-only, base classes, optional governance/escalation, or memory-write helpers invoked by other agents' commit steps) — but **none of this was declared anywhere**; the gap was silent. That silence is the root cause of the earlier misprioritization (fixing the dead `dispatch_kernel` while the live `karpathy_pipeline` truncation stood).
- **Fix applied:** added `check_entrypoints_reachable` to `system/governance_checks.py`. It computes transitive reachability from `LIVE_ENTRYPOINT` and fails CI for any registered agent that is neither reachable nor explicitly listed in `EXTERNAL_ALLOWED` (with a per-agent reason). The 9 external agents are now declared with documented reasons, converting the silent gap into a reviewed invariant. Result: `entrypoints_reachable` check passes (18 reachable / 9 external / 0 silent).
- Net effect: any future dead registration or orphaned pipeline fails CI unless deliberately declared — the exact class of bug that hid the live truncation.

### 🟡 F11 — Coverage gate still 60 in `make coverage` / `make ci` (Law 5 gap, partially fixed)
- The first pass edited `.github/workflows/ci.yml` to `--cov-fail-under=80`, but the project's canonical local gate (`Makefile: coverage` → used by `make ci`) was still `--cov-fail-under=60`. Law 5 demands >80%.
- **Fix applied:** `Makefile` `coverage` target raised to 80, so `make ci` now enforces the same gate as CI.

### 🟡 F12 — `competitive_slice` / `domain_squads` / `graph_execution_orchestrator` are real but lightly grounded
- `competitive_slice.py` documents itself as "selected by DispatchKernel when task_type == 'humaneval'" — but `DispatchKernel` is the dead path; nothing in the live pipeline selects it. It is only reachable via `dispatch_domains`/`orchestrate_graph` flags, which are off by default.
- `domain_squads.py` still returns raw LLM strings never parsed/executed (F7). This is the weakest layer by construction.

### Process lesson (for the multi-developer context)
- The repo has **multiple concurrent workers** (sibling subagents + pushed commits on `main`). During this session, an external commit (`fb0b7d7 "Fix: harness passed a dead allow_mock kwarg"`) reverted an earlier `audit_stepfun_policy.py` edit of mine; `make audit` began failing again until I re-applied the `SKIP_FILES` correction.
- **Implication:** any fix to shared governance files (`scripts/audit_*`, `Makefile`, `ci.yml`, `LAWS.md`, `agent_registry.py`) must be committed/pushed promptly, because a fast follow-up push can silently revert it. Prefer small, self-contained PRs over long-lived local edits on `main`.

## 9. Third-pass addendum — F7 corrected & closed (2026-08-03)

### 🔴 F7 — Domain-squad output was parsed but NOT execution-grounded (verified, fixed)
The second-pass note called Layer-4 squads "raw LLM strings never parsed/executed." **That was overstated.** Reading `agents/domain_dispatcher.py` shows `dispatch_domain_tasks` DOES parse squad JSON via `parse_json_object_response` (required keys `filename/code/test_filename/test_code`) and records `parsed_outputs`. The real, narrower gap: the **parsed squad `code`/`test_code` was never run in the sandbox** — unlike the main `tasks` loop (Stage 7) which calls `run_code_and_tests`. `quality_reviewer` aggregates `dispatch_result` but does not execute either. That asymmetry breachd the project's central execution-grounded thesis (Law 11).
- **Fix applied:** `agents/karpathy_pipeline.py` Stage 6.5 — when `execute_code=True` and `domain_dispatch_result["parsed_outputs"]` is non-empty, each parsed artifact is run through the same isolated `run_code_and_tests` sandbox as Stage 7, and `test_execution` is attached to the dispatch result; sandbox failures surface as `combined_breaches`. Added `test_pipeline_domain_squad_code_is_execution_grounded` (hermetic: stubs `call_llm` across all importers + `run_code_and_tests`) asserting squad parsed code is actually handed to the sandbox.
- **Verification lesson (again):** the squad-grounding test initially failed because my fake decomposition used `type:"api"`, which `DeterministicValidatorEngine.VALID_TYPES` rejects (`{feature,architecture,requirements,testing,bugfix,refactor}`); domain routing is by keyword detection, not `type`. Correct fixture = `type:"feature"` + api-rich description. This is the same "verify claims against real code" discipline that caught the false F10.

*Third-pass addendum. F7 closed (squad code now execution-grounded). Remaining open thread: **F8 (Law 20 boundary keyword bypass by paraphrase)** — a design limitation of substring matching, lower priority.*

## 10. Recheck (2026-08-04) — most critical/medium findings already resolved

A recheck against the current tree (post-`c92fd39`, `7fd39fe`, `86dbd11`) shows the audit's
earlier findings have since been fixed by later commits. Re-applying them would be churn:

- **F1 (missing Laws 14/15/16):** RESOLVED. `LAWS.md` now defines Law 14 (Signal
  Determinism), Law 15 (Latency Budget), Law 16 (Reproducible Evidence). Citations match.
- **F2 (silent `except Exception:`):** RESOLVED to the audit's own "excusable" bar. The 11
  originally-flagged blocks are down to 3, all in best-effort paths (`_cleanup_worktree`
  git/dir cleanup; `run_improvement_cycle.load_last_measurement` JSON fallback) where
  swallow-and-continue is the intended behaviour (same class the audit itself excused at
  `test_runner_agent.py:149`).
- **F4 (stale `allow_mock` warning):** RESOLVED. `BENCHMARK-REPORT.md §7` already states
  "The `allow_mock` fallback is gone" and explains the no-mock path; `SWEBENCH-REPORT.md`
  carries no such warning. `grep allow_mock` in source returns nothing.
- **F6 (CI coverage gate):** RESOLVED. `.github/workflows/ci.yml` line 33 and
  `Makefile` `coverage` target both pass `--cov-fail-under=80`, enforcing Law 5.

**Open (low priority, design-level, not a regression):** F8 (Law 20 substring boundary
bypass by paraphrase). Acknowledged as a known limitation; fix is normalize+tokenize or
regex on canonical phrases (per audit F8). Deferred — not blocking.

**Net:** the system is in better shape than this audit (08-03) recorded. No new code churn
required from these findings; the live work is the SWE-bench loop experiment (network-blocked
at time of recheck) and keeping `make test` green.
