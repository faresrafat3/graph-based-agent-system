# Version Ledger — Methodology Reconciliation & Systems Layer

**Project:** graph-based-agent-system
**Baseline commit:** f2ca0e8
**Maintained by:** the (hy3 + opus-5) system, per Fares's direction (2026-08-05)

This ledger records every versioned change to the methodology/governance docs and the
Systems Layer. Each entry is a snapshot pointer + a one-line verdict. If a step proves
hasty, wrong, or undesirable, restore the referenced file state from git.

## Versions

| Ver | Date | Doc/File | Change | Verdict |
|---|---|---|---|---|
| v0 | 2026-08-05 | CONSTITUTION.md, LAWS.md, GOVERNANCE-SYSTEM.md, ULTIMATE-GRAPH-PLAN.md | Baseline snapshot before reconciliation. No edits. | baseline |
| v1 | 2026-08-05 | docs/METHODOLOGY-RECONCILIATION.md (NEW) | Maps 5 contradictions (C1-C5) + 3 fallacies (F1-F3) to explicit resolutions. | done |
| v1 | 2026-08-05 | CONSTITUTION.md Article VI Section 1b | Adds reconciliation rulings C1-C5 + F2; meta-loop proposes not applies. | done |
| v1 | 2026-08-05 | tests/test_reconciliation.py (NEW) | 6 tests asserting every contradiction has a recorded ruling. | done |
| v2 | 2026-08-05 | agents/systems_layer.py (NEW) | Embed measure/compare/propose/distill/gate/record as LangGraph nodes (resolves F3). | done |
| v2 | 2026-08-05 | system/agent_registry.py | Register Systems Layer as agent (category: systems_layer). | done |
| v2 | 2026-08-05 | system/governance_checks.py EXTERNAL_ALLOWED | Declare build_systems_graph intentionally external (Ruling C1). | done |
| v2 | 2026-08-05 | tests/test_systems_layer.py (NEW) | 3 tests: graph compiles, full cycle writes proposals, node order. | done |
| v3 | 2026-08-05 | agents/cynefin_classifier.py (NEW) | Cynefin domain classifier; replaces keyword router (resolves C4/P3). | done |
| v3 | 2026-08-05 | tests/test_cynefin_classifier.py (NEW) | 5 tests: clear/complicated/complex/chaotic + P3 mapping. | done |
| v4 | 2026-08-05 | system/distillation_ledger.py (NEW) | Provenance ledger for opus-5 principles (resolves C5). | done |
| v4 | 2026-08-05 | scripts/seed_distillation_ledger.py (NEW) | Seeds P1-P7 as enforced+provenanced. | done |
| v4 | 2026-08-05 | tests/test_distillation_ledger.py (NEW) | 5 tests: provenance, reject-no-source, status, advisory, persist. | done |
| v9 | 2026-08-05 | agents/debugger_agent.py extract_hypothesis (NEW) | Thrash signal hardens: compare hypothesis IDENTITY not text Jaccard (opus-5 P4 fix). | done |
| v9 | 2026-08-05 | agents/debugger_agent.py refine() thrash compare | Uses extracted hypothesis; >=0.99 identity match (was raw >=0.6). | done |
| v9 | 2026-08-05 | tests/test_thrash_signal.py (NEW) | 4 tests: rephrase→same hypothesis, distinct theories, catches rephrased thrash, raw misses. | done |
| v19 | 2026-08-05 | agents/sage_council.py Sage.reason() + _OPPOSING | Strong-model #2 fix: distinct per-principle stances (consensus no longer theater); conflict vocab covers real stances. 3 tests. | done |
| v19 | 2026-08-05 | agents/context_system_view.py MAX_PEERS/MAX_CYCLE_LOG | Strong-model #3 fix: bounded context (observable at 7x scale). 3 tests. | done |
| v19 | 2026-08-05 | agents/disk_saver.py (NEW) JsonlCheckpointSaver | Strong-model #3 fix: durable disk checkpoint (no MemorySaver volatility). systems_layer uses it. 3 tests. | done |
| v19 | 2026-08-05 | system/governance_checks.py check_forge_wired + warnings | Strong-model #1 fix: forge-wiring gap surfaced (warning, visible not hidden). 2 tests. | done |
| v19 | 2026-08-05 | scripts/forge_scale_demo.py (NEW) + tests | G2: 210 bespoke agents, 0 clones, 735 edges. 1 test. ADR written. | done |
| v20 | 2026-08-05 | agents/agent_forge.py extend_registry TRANSACTIONAL | gpt-5.6-sol #1-b fix: self-extend WITHOUT self-violating. Scaffolds module+test+doc, rolls back on breach. 2 tests. | done |
| v20 | 2026-08-05 | system/governance_checks.py EXTERNAL_ALLOWED run_forged_agent | Forged entrypoint declared intentionally-external (Q3); gap visible (Law 3), governance green. | done |
| v20 | 2026-08-05 | ALL strong-model findings resolved | #1 forge-wired warning + transactional extend; #2 distinct consensus; #3 bounded+durable context. 391 passed, audit+compile clean. | done |
| v18 | 2026-08-05 | agents/topology_assembler.py (NEW) | Task 4: typed FOCUS/VERIFY/peer/escalate edges; untyped HARD-rejected; extends systems_layer. 5 tests. | done |
| v18 | 2026-08-05 | tests/test_meta_monitor_backbone.py (NEW) | Task 5: systems_layer IS live backbone (e2e); forge/context/topology on top, no 2nd governor. 2 tests. | done |
| v18 | 2026-08-05 | ALL TASKS 1-5 DONE | Intelligence Forge: P1/P4 enforced, bespoke forge (clone-trap), context=system, focus edges, meta backbone. 372 passed. | done |
| v15 | 2026-08-05 | agents/systems_layer.py philosopher_node | Uses registry-backed council as default (loud fallback, Law 3). | done |
| v15 | 2026-08-05 | tests/test_council_from_registry.py (NEW) | 4 tests: multi-category, excludes self, weights, convenes. | done |
| v15 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md §11 | Council built from real 27+ agents, not mock. | done |
| v14 | 2026-08-05 | agents/sage_council.py Sage.weight | Per-sage consensus weight; default council weighted (1.2/1.0/1.1). | done |
| v14 | 2026-08-05 | tests/test_consensus_mechanism.py (NEW) | 5 tests: conflict detect, peer weights, hierarchical lead, broadcast, convene block. | done |
| v14 | 2026-08-05 | tests/test_sage_council.py (FIX) | Hierarchy prefix LEAD[lead] matches code. | done |
| v14 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md §10 | ConsensusMechanism = correct integration honoring vision. | done |
| v13 | 2026-08-05 | agents/systems_layer.py philosopher_node (FIX) | Uses local SageCouncil, NOT consult_opus5 (Fares correction: principle in-graph). | done |
| v13 | 2026-08-05 | tests/test_sage_council.py (NEW) | 4 tests: skip/gate, peer dialectic, topologies, seeded principles. | done |
| v13 | 2026-08-05 | tests/test_systems_layer_cir.py (REWRITE) | 3 tests: convene on complex, skip below threshold, topology+flow (no opus-5). | done |
| v13 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md §9 | Correction: CIR = local Sage Council, not opus-5 link. | done |
| v12 | 2026-08-05 | docs/reconciliation/COMPARATIVE-STUDY.md §A/B | Honest A/B: n=4, CIR no advantage on small tasks; gate added. | done |
| v11 | 2026-08-05 | agents/systems_layer.py philosopher_node + reconciler_node | CIR embedded as FIRST-CLASS graph nodes (context-isolated opus-5 + falsifiable spec). | done |
| v11 | 2026-08-05 | agents/systems_layer.py topology | measure->philosopher->reconciler->compare... (CIR in meta-loop graph). | done |
| v11 | 2026-08-05 | tests/test_systems_layer_cir.py (NEW) | 3 tests: strategy emit, safe fallback, topology+flow. | done |
| v11 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md §8 | CIR embedded in graph per Fares's scale-with-complexity request. | done |
| v10 | 2026-08-05 | docs/reconciliation/COMPARATIVE-STUDY-2026-08-05.md (NEW) | 3-model study (opus-5/gpt-5.6-sol/opus-4-8) on Context-Isolated Reasoning. | done |
| v10 | 2026-08-05 | system/distillation_ledger.jsonl (3 model_review) | Verbatin opus-5/gpt-5.6-sol/opus-4-8 replies recorded as provenance. | done |
| v10 | 2026-08-05 | scripts/record_comparative_study.py (NEW) | Records 3-model comparative replies to ledger. | done |
| v10 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md §7 | Links comparative study; renames P/E -> CIR. | done |
| v9 | 2026-08-05 | docs/reconciliation/FARES-RESEARCH-NOTES.md (NEW) | Fares's research insights on hy3+opus-5 reasoning data + open Qs. PERMANENT reference. | done |
| v8 | 2026-08-05 | scripts/run_improvement_cycle.py thrash fix | measure_benchmark reads live harness (was hardcoded 0) per opus-5 finding. | done |
| v8 | 2026-08-05 | tests/test_thrash_measure.py (NEW) | 2 tests: thrash measured not hardcoded; fallback on harness error. | done |
| v8 | 2026-08-05 | docs/METHODOLOGY-RECONCILIATION.md §5 LIVE | Records opus-5 P4 verdict + code finding + resolution. | done |
| v8 | 2026-08-05 | scripts/run_systems_layer.py + Makefile systems-layer | In-graph driver + canonical target; cron updated. | done |
| v21 | 2026-08-07 | main.py, agents/deterministic_validator.py, tests/test_karpathy_pipeline.py, tests/test_task_decomposer.py | Removed 5 duplicate module-scope import lines (AST scope-confirmed redundant; each had an earlier top-level binding). Behavior-preserving. Commit 252c04a. 95 touched tests pass. | done |
| v21 | 2026-08-07 | scripts/code_hygiene_scan.py (NEW) | SAFE-ONLY observer: scope-aware duplicate-import + missing-final-newline scanner (no edits). Re-runnable; returns JSONL. P7 Least Sufficient Intervention. | done |
| v21 | 2026-08-07 | ZERO-HARM ACCOUNTING (deliberately NOT done) | Left untracked WIP (benchmarks/swebench_harness.py, docs/LOCALIZER-MEASUREMENT.md) untouched; 12 in-function duplicate imports NOT removed (removing would break those functions); 675 trailing-whitespace lines NOT touched (may be inside string literals/code fences); 0 typo/whitespace "likely" fixes proposed. | done |
| v22 | 2026-08-07 | scripts/code_hygiene_scan.py (EXTENDED) | Added categories 3 (tokenize-verified trailing-whitespace-in-code), 4 (unused module import, detection-only), 5 (duplicate def, detection-only). Hardened: __future__ imports EXCLUDED (compiler directives, not bindings — was a dangerous false positive). Categories 4/5 are detection-only, never auto-applied. | done |
| v22 | 2026-08-07 | PHASE 8 fan-out research (2 delegated subagents, READ-ONLY) | Findings: 0 stray bytecode, 0 duplicate defs, 0 dangling test imports (2 candidates were sys.path-shim false positives), compileall exit 0. 40 unused-module-import candidates surfaced but ALL REJECTED for auto-removal: AST cannot see pytest-decorator/fixture/TYPE_CHECKING/import-time-side-effect uses; removing `import pytest` from test files risks collection breakage. Zero-harm preserved. | done |
| v22 | 2026-08-07 | FALSE-POSITIVE CORRECTION (subagent self-check) | Subagent-2 claimed a `.gitignore` typo (`swebench_verified_local.json` vs `swebench_local_verified.json`). Re-check proved NO typo: actual file is `swebench_verified_local.json` (matches the ignore rule exactly). The subagent had confused two different untracked files. No change made — good catch via independent verification. | done |
| v22 | 2026-08-07 | ZERO-HARM ACCOUNTING v22 | Did NOT remove any of the 40 unused imports (Tier A/B/C) — none reached 100% certainty after cross-checking pytest/sys.path/side-effect risks. Did NOT edit `.gitignore` (no real typo). Did NOT touch `triage_local.py` (user's untracked source). System confirmed clean of mechanically-verifiable safe findings beyond v21. | done |
| v23 | 2026-08-07 | scripts/code_hygiene_monitor.py (NEW) | Observe-only watchdog: reuses scanner, surfaces ONLY proven-safe actionable categories (duplicate_import, trailing_whitespace_code, missing_final_newline). Silent when clean. WIP excluded. Wired to recurring 30m cron (a5d84087c3a7) for continuous autonomous monitoring with zero edits. | done |
| v23 | 2026-08-07 | META-LOOP STATUS | loop=scan→delegate-verify→stability-gate(make test 444 pass)→atomic-commit→ledger→rescan. This session: 6 commits (252c04a, 6a313b7, 80b3870, 124bcb2, 94d5b10, 80f3e67), all isolated from user WIP. Zero-harm preserved across 11 mechanical edits + 2 delegated research passes. No repo damage, no residue. | done |
| v24 | 2026-08-07 | scripts/code_hygiene_monitor.py (EXTENDED) | Added `_collision_warnings()`: if any file this loop previously committed safe edits to reappears as a working-tree modification, the monitor warns (observe-only). Prevents auto_sync from bundling the loop's earlier commit with the user's live edits. Still silent when clean. | done |
| v24 | 2026-08-07 | WIP BOUNDARY OBSERVED | New untracked user artifacts appeared during this session (tests/test_triage_local.py, benchmarks/triage_local.py, *.json result dumps) — none touched by the loop. The loop's scope is strictly the 6 proven-safe files; everything else is the user's domain. Cron a5d84087c3a7 (30m, deliver=origin) now auto-surfaces any regression into this chat. | done |
| v25 | 2026-08-07 | LEVEL 1+2 — safe auto-fix pipeline (RAISED FROM observe-only) | Added code_hygiene_fix.py (applies ONLY the 3 proven-safe categories; runs `make test` as stability gate, reverts on failure) + code_hygiene_autorun.py (stages fixer-touched files only, never commits). Cron 2664633e465c (30m, forever, deliver=origin) now runs the auto-runner. unused_module_import/duplicate_definition kept detection-only (scanner reports whole import line, not the unused name -> auto-removing a multi-name line drops live names). | done |
| v25 | 2026-08-07 | ZERO-HARM LESSONS THIS PHASE | (1) `git reset --soft` keeps staged WIP -> an autorun that `git add`s blindly bundled user WIP into a commit (caught + reverted). Fix: fixer writes .hygiene_touched.txt; autorun stages ONLY those files. (2) pre-commit Conventional-Commits hook blocks autonomous commits -> autorun no longer commits; auto_sync owns commits. (3) multi-name unused imports unsafe to auto-remove. All three caught before any harm. | done |
| v26 | 2026-08-08 | LEVEL 3 — dead-code research (RAISED SCOPE) | 2 delegated subagents (AST + pyflakes/vulture) hunted dead code in scripts/ + benchmarks/ (graph core agents/llm/memory/system/kernel excluded for dynamic-dispatch safety). Removed: dead funcs/params in code_hygiene_fix.py (self-cleanup), unused `sys`/`json`/`Path` imports in 4 scripts, dead `logger` binding in benchmarks/grade_alphacode.py. 45 lines deleted, pyflakes clean on scripts/, 510 tests pass. | done |
| v26 | 2026-08-08 | ZERO-HARM ACCOUNTING v26 | REJECTED: benchmarks/localizer_graph.py:229 param `problem` (public pipeline stage, 2 call sites, documented in user WIP doc) and tests/ dead assignments (may signal missing assertions, not dead code). System confirmed clean of safe findings across all 3 levels. | done |
| v27 | 2026-08-08 | CRON PAUSED — ENV QUOTA, NOT CODE | code-hygiene-autorun cron (2664633e465c) ran once and hit HTTP 401 (API token quota exhausted: RemainQuota=-24916). The auto-fix pipeline itself is correct (verified live: inject ws -> fix -> 510 tests pass -> only touched file staged, WIP unstaged). Cron PAUSED to avoid burning the quota on repeat failures. RESUME: when quota is available, `cronjob resume 2664633e465c` — it is already repeat=forever, deliver=origin, so it will self-monitor and post regressions here. | done |
| v28 | 2026-08-08 | docs/digest/META-LOOP.md (NEW) | PRIME-AGENT DIGEST — meta-loop opened. Declares 6 loops (DIGEST/MAP/PORT/SIDECAR/MEASURE/GOVERN), 8 invariants, per-loop gates, anti-residue policy. Root cause of the earlier stall recorded honestly: breadth-first docs with no closing gate (TODO.md had 4/55 boxes checked). | done |
| v28 | 2026-08-08 | scripts/meta_loop.py (NEW) | Executable fail-closed gate for the digest loops. `inventory` generates the L1 skeleton from the real clone (302 files >=100 LOC, 12 areas, exclusions recorded not silent); `verify L1/L2/L6` gate coverage, mechanism mapping, and Constitution immutability. Verified: L1 correctly FAILS at 0/302, L6 PASSES. | done |
| v28 | 2026-08-08 | tests/test_continual_harness_fidelity.py (NEW) | 12 port-fidelity tests, each naming the upstream harness.py:line it protects. RED->GREEN proven: 11 failed before the fix, 12 pass after. | done |
| v28 | 2026-08-08 | system/continual_harness.py | THREE REAL PORT DEFECTS FIXED, each proven by execution before the fix. (A) `version:"3"` silently reset to 1 (isinstance-int-only check) -> `_coerce_version` per harness.py:237-245. (B) missing `scope` fell back to `state_path.parent.name`, loading entries with scope='sub' — not a member of VALID_SCOPES -> `_coerce_scope` per harness.py:233-234. (C) `create()`/`update()` were absent entirely, so a colliding id became a SILENT UPDATE instead of an error -> create-or-fail + update-or-fail per harness.py:437-482. Also ported `_strip_scope_prefix` (harness.py:59-67) and `_validate_python_skill_reference` (harness.py:128-138). | done |
| v28 | 2026-08-08 | ZERO-HARM ACCOUNTING v28 | Full suite 686 passed / 1 skipped after the change (was 674+12 new). CONSTITUTION.md + LAWS.md untouched (L6 gate green). Sibling-session check run before any edit: the live `graph_engine.py` + researcher worker belong to ~/Projects/fares-agent, a DIFFERENT repo — no concurrent writer here. A suspected `data-bundle` syntax error in continual_harness.py:90 was investigated at the BYTE level and proven to be a rendering artifact (zero-width chars), NOT a bug — no edit made. | done |

## How to restore
```
git show f2ca0e8:CONSTITUTION.md          # v0 baseline of CONSTITUTION
git show <commit>:docs/METHODOLOGY-RECONCILIATION.md
```
Each versioned file keeps a header comment: `<!-- version: vN | date | verdict -->`.
