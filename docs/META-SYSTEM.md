# META-SYSTEM — Governed Self-Improvement Loop

**Date:** 2026-08-04
**Status:** Implemented (`system/self_improvement.py`) + driver (`scripts/run_improvement_cycle.py`)
**Derivation:** Distilled from the Karpathy method + opus-5 philosophical audit (CONSTITUTION Article VI, P1–P7) + the empirical loops run on SWE-bench Verified and the benchmark suite.

## 0. Thesis

The graph-based agent system should not be hand-tuned by a human. It should **measure
itself, propose control changes, and accept/reject them by observed effect** — exactly
the discipline opus-5 prescribed in P7 (Least Sufficient Intervention): *no control
survives unless it demonstrably catches a failure.*

This file is the **system** that automates the reasoning we already did manually:
- We measured SWE-bench honestly and found the ceiling is the *generator*, not the graph.
- We isolated one variable per probe (loop mode = "does test-feedback help?").
- We gated controls behind observation (thrashing harness measures before adding a budget).
- We distilled opus-5's philosophy into frozen Laws/Constitution, never letting it author live code.

The META-SYSTEM makes that a **repeatable, autonomous loop**.

## 1. The Loop (5 stages, zero-LLM control plane)

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1 — MEASURE                                            │
│   Run benchmark suite + SWE-bench slice + thrashing harness.  │
│   Emit a Measurement (success, defense, quality, health,      │
│   thrash_count, postcondition_pass_rate).                     │
└───────────────────────────┬─────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2 — COMPARE                                            │
│   Diff against last Measurement. Classify delta:             │
│     capability↑ | capability↓ | variance↓ | defense↑/↓ |      │
│     thrash↑ | postcondition_gap↑                              │
└───────────────────────────┬─────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3 — PROPOSE (P1/P4/P7)                                 │
│   For each meaningful delta, propose ONE control change:      │
│     - new outcome at a routing point (P1)                    │
│     - probe budget where thrash↑ (P4)                        │
│     - remove a control that has not caught a failure (P7)    │
│   Each proposal carries a FALSIFIABLE hypothesis.            │
└───────────────────────────┬─────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4 — GATE (P7 / opus-5 distillation)                    │
│   A proposal is applied ONLY if it is observable + reversible │
│   (reversible = config/flag, not architecture rewrite).       │
│   If the delta touches governance philosophy, route the       │
│   proposal text through the opus-5 distillation prompt;        │
│   accept only the distilled principle, not raw text.           │
└───────────────────────────┬─────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 5 — RECORD                                             │
│   Append to measurements log + deltas log. CI re-runs         │
│   `make test` + `make audit`. A control that changes no        │
│   outcome in N cycles is flagged for removal (P7).            │
└─────────────────────────────────────────────────────────────┘
```

**Hard rules (enforced in code, not just docs):**
1. One variable per probe. Never change two controls and measure.
2. Every proposal is reversible (config/flag) unless explicitly up-leveled by a distilled principle.
3. No control is added that cannot be observed catching a failure.
4. opus-5 output is distilled to a principle and frozen; it never edits code directly.

## 2. Lessons distilled (the judgment we earned)

| # | Lesson | Source | Now encoded as |
|---|---|---|---|
| L1 | Measure capability vs infra separately; publish variance | SWE-bench 4/8 vs 1/8 swing | `measure()` splits runs; `compare()` reports variance |
| L2 | The ceiling was the generator, not the graph | SOTA-POSITION.md | `propose()` refuses architecture rewrites unless generator swapped |
| L3 | Isolate one variable per probe | AGENT-LOOP-EXPERIMENT.md | `STAGE 3` emits exactly one control change per delta |
| L4 | Gate controls behind observation (P7) | thrashing harness | `gate()` blocks non-observable controls |
| L5 | Distill opus-5, don't let it author | CONSTITUTION Article VI | `distill_opus5()` returns principle text only |
| L6 | Silent breaches are the dangerous class | scenario_4 fix (Task 1) | `measure()` asserts breaches are non-empty on block |
| L7 | Sibling sessions own live paths; avoid them | cleanup pass 2026-08-04 | `run_improvement_cycle.py --safe-only` flag |

## 3. How this reflects onto the graph

The graph's agents are themselves **controls**. Each agent = a checkpoint that should
catch a specific failure mode (P1: requisite variety). The META-SYSTEM treats the agent
registry as a set of candidate controls and asks, every cycle:

> "Which agent demonstrably changed an outcome this run? Which is silent dead weight?"

That is P7 applied to the graph itself. When the system can answer that with evidence,
the graph has become **self-governing** — not by a supreme decision agent, but by the
measurement loop. This is the distributed-governance thesis from GOVERNANCE-SYSTEM.md,
operationalized.

## 4. Usage

```bash
# One safe cycle (benchmark measure + record; no edits to sibling-owned files)
python scripts/run_improvement_cycle.py --safe-only

# Full cycle (benchmark measure + thrash_count=0 + propose + gate + record)
python scripts/run_improvement_cycle.py --measurements-dir system/measurements

# Full cycle WITH the (token-expensive) thrashing harness -> real thrash_count -> P4
python scripts/run_improvement_cycle.py --with-thrashing

# P7 self-pruning report (advisory; never deletes)
python system/self_pruning.py
# or: make prune

# Cron (autonomous, safe-only, every 30 min) — see ~/.hermes/scripts/gbas_improvement_cycle.sh
```

Output: `system/measurements/measurements.jsonl` (append-only) + `system/measurements/deltas.jsonl`.

**Make targets:** `make improve`, `make improve-safe`, `make prune`.

## 5. Open questions (feed back into the loop)

- Do we expand the SWE-bench slice to 50+ instances for statistical power? (L1 says yes, but cost.)
- When the generator is swapped, does the graph's control set need to shrink? (L2 predicts yes — P7 will remove now-redundant agents.)
- Should the loop itself be an agent in the graph, or stay external? (Kept external: the measurer must not be measured by what it measures — Ashby/L1.)
