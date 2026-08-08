# Orchestration Charter — the reasoning spine

**Owner:** Fares (architect). **Orchestrator:** Hermes (this file is its memory).
**Created:** 2026-08-08
**Purpose:** Hold the logic, philosophy, and method OUTSIDE the orchestrator's context
window so that long sessions, compaction, or a fresh session never lose the thread.
Agents do the heavy lifting; this file is what the orchestrator re-reads to stay itself.

> Read this file FIRST when resuming any deep work on `graph-based-agent-system`.

---

## 0. Operating model (how this work is run)

- **Hermes = orchestrator.** Holds the argument, decides what is worth measuring,
  writes the decisions. Does NOT do bulk execution by hand.
- **Agents = executors.** Benchmarks, audits, LOC accounting, literature scans.
  Each returns a bounded, verifiable artifact.
- **Fares = architect + source of direction.** Brings the ideas/thoughts (خواطر)
  that open new axes. He reviews outcomes; he is not asked to micro-approve steps.
- **Verification rule:** an agent's summary is a SELF-REPORT, not evidence.
  Every claim that matters gets re-checked by the orchestrator against a real
  artifact on disk (file, JSONL row, docker grade) before it enters a decision.

---

## 1. The founding observation (2026-08-08)

A thought Fares brought in, paraphrased from a post he read. Two arguments in it:

**Surface argument:** a model is a bad teammate — over-engineers, speaks jargon
without context, makes confident mistakes, takes no feedback, wants a big charter
and to go dark.

**The load-bearing argument (final line — `don't let a bad model RL you`):**
a weak model does not merely fail. It **reshapes the system around itself**. Each
failure becomes a training signal for the *architecture*, not for the model. The
human ends up optimized by the model instead of the reverse.

This is not a metaphor. It describes a real optimization loop, and this repository
is an instance of it.

---

## 2. The mirror — what the repo's own numbers say

Source: `docs/AGENT-LOOP-EXPERIMENT.md` (§6–§9), the repo's own honest record.

| Arm | Dimension added | Applies /8 | **Resolved** |
|---|---|---|---|
| single-shot | — | ? | 4/8 (claimed) |
| alphacode N=3 | sampling | 6/8 | **1/8** |
| loop | self-repair + test feedback | 3/8 | **0/3** |
| graph (simple) | specialized agents | 4/8 | **1/5** |
| graphfull | +Reflexion +Debugger +Surgical | 5/8 | **0/6** |
| graphfull repaired | 3 dead dimensions fixed | **7/8** | **1/8** |

**Applicability rose 3→4→5→7. Resolve rate never left 1/8.**

Mass built alongside it (measured 2026-08-08):

| Quantity | Value |
|---|---|
| agent files | 37 |
| Laws | 20 |
| CONSTITUTION + LAWS | 1,473 lines |
| docs | 68 files / 11,863 lines |
| Python LOC (agents+kernel+benchmarks) | 14,694 |

Governance+docs to code ≈ **1:1**.

§8 records the sharpest fact: instance **1142**, resolved by the *simple* graph,
**failed** under `graphfull`. The repo named the cause itself — *"too many cooks"
context dilution*. The system measured that addition hurt, and the response was
to add more.

---

## 3. The rule that must become falsifiable

Fares's standing heuristic:

> "a metric drop = DESIGN bug, not 'the model is weak'"

**When it was right — §9.** It rejected "model is weak" and found 3 genuinely DEAD
dimensions: Debugger never ran (no `fail_log` captured), SurgicalRefiner was never
invoked (its text was only pasted into a prompt), and all dimensions were crammed
into one prompt. Fixing them lifted applicability 5/8 → 7/8. A real catch.

**Where it becomes a trap.** Applied to the *residual* gap it is **unfalsifiable**:
if every flat metric is by definition a design bug, then no evidence in the world
can ever say "enough architecture." The rule becomes an engine for unbounded growth.

The mechanism inverts the founding observation exactly:

| In the post | In this repo |
|---|---|
| model demands you reshape the company around it | architecture reshaped around a weak generator |
| takes no feedback | architecture never accepts "you are not the bottleneck" |
| always the smartest in the room | "decomposition is always the answer" — an axiom, not a hypothesis |

**This is NOT a rejection of the graph.** The graph is the right *shape*. What is
under challenge is the **growth rule** that adds a dimension whenever the number
refuses to move.

**Amendment (adopted):** any new dimension/agent/control must declare, IN ADVANCE,
the measurement that would falsify it. No falsifier ⇒ not built.

---

## 4. The experiment that was never run

All five arms ran on `step-3.7-flash`. **The same `--mode graphfull` has never been
run with a strong generator** — although `AGENT-LOOP-EXPERIMENT.md` §8 states this
as the explicit design goal:

> *"a stronger coding model dropped into the SAME `--mode graphfull` (no architecture change)"*

Written, never executed. It is the cheapest, highest-information experiment available,
and it discriminates three very different worlds:

| Outcome | Meaning | Consequence |
|---|---|---|
| resolve rate **rises**, same architecture | architecture was never the bottleneck | enforce **P7**: most of the 37 agents must go |
| stays **1/8** | neither model nor graph — the **harness/grader** is the gate | measure the apparatus first |
| rises **partially** | shared ceiling | split the contribution by measurement |

Consistent with the standing discipline: **measure the apparatus before the system.**
Precedent: 4 parser bugs once misclassified sound cases as infra failures, all biased
to flatter (56 → 74 usable once fixed).

### 4a. Feasibility of the decisive run (established 2026-08-08)

Mechanically it is **already possible with zero architecture change**, exactly as §8 claims:

- `benchmarks/swebench_harness.py:1350` — `--mode` accepts `graphfull` today.
- `llm/llm_integration.py:249` — the generator is `STEPFUN_MODEL` (default
  `step-3.7-flash`, `llm_integration.py:34`); it is an env var, not a hardcoded constant.
- `llm/llm_integration.py:248` — `STEPFUN_BASE_URL` is ALSO env-overridable, so an
  OpenAI-compatible endpoint can be pointed at without touching code.
- Strong models are already reachable in the operator's Hermes config via
  agentrouter (`claude-opus-5`, `gpt-5.6-sol`, 3 rotating keys, 600s timeouts).

**But there is a CONSTITUTIONAL blocker, not a technical one.** CONSTITUTION Article III
§2 "Stepfun-Only Provider Policy" (lines 204–217) states: the system MUST route all LLM
calls through Stepfun, and *"Adding alternate provider routing or silent dry-run fallbacks
MUST be rejected."*

So the single most informative experiment in the project is forbidden by its own
constitution. This is itself a finding, and it is the same pathology as §3: a control
that was written to prevent silent fallbacks now blocks a legitimate measurement.

Note the enforcement asymmetry: the policy is asserted in prose but is NOT enforced in
code — `grep` finds no provider assertion, only empty-value checks
(`llm_integration.py:252,254`). A run could therefore be done by env var **without any
code edit**, which would be a silent breach. That must NOT be done quietly.

**Resolution path (must be explicit, not sneaked):** treat it as a constitutional
amendment — a bounded, declared exemption for *measurement* runs, written into
CONSTITUTION.md, with the generator identity recorded in the result artifact. The
experiment is only meaningful if it is honest about what generated the patches.
Requires Fares's approval as architect: it changes a MUST clause.

---

## 5. The new research axis this opens

The post judges an agent by **teammate** criteria, not benchmark criteria. Turned
into measurable properties:

| Bad-teammate trait | Measurable agent property |
|---|---|
| takes no feedback | **Correctability** — given a correct signal, does the output change? |
| goes dark, no communication | **Legibility** — does it emit usable signal mid-task? |
| demands a big charter | **Scope discipline** — smallest step, or broad mandate? |
| no one tells him how to do his job | **Interface for correction** — does an intervention point exist at all? |

Nobody publishes these. SWE-bench measures resolve rate only.

**Correctability was already measured here, by accident: the `loop` arm.** Failing
test names were fed back, 4 full rounds, and the model returned the same partial
patch. `step-3.7-flash` correctability on that slice ≈ **0**. That is a property of
the model, not a harness defect.

Note: the 976-loop engine (stopped 2026-08-08) was a literal instance of the bad
teammate — 2,649 tasks, 375 blocked, 13 days of unobserved work. Its shutdown and
the kanban wipe were the first application of this principle.

---

## 6. Standing constraints (do not violate)

- **Provider:** deep philosophical synthesis → `claude-opus-5` via agentrouter.
  Prompts in ENGLISH (Arabic is rejected, HTTP 400). Deliver to Fares in Arabic.
- **Cost:** a prior session burned ~$90 on 500/504 errors. Show prompts before
  large runs. No surprise expensive runs.
- **Gates:** `make test` + `make compile` + `make audit-strict`. `pytest -q` ≈ 22s.
  `--cov` exceeds the 600s cap — do not run it inline.
- **Repo:** English artifacts + verbatim Karpathy quotes. Chat with Fares: Egyptian Arabic.
- **Concurrency:** check `git status --short` + mtimes for a sibling session before editing.
- **Never** fabricate a result. A blocked path reported honestly beats an invented number.

---

## 7. Decision log (append-only)

| Date | Decision | Basis |
|---|---|---|
| 2026-08-08 | Stopped the 976-loop engine; disabled `fares-patrol.service`; wiped kanban (2,649 tasks, 31.9MB→0.12MB) | Loop produced volume, not results; blind unobserved work |
| 2026-08-08 | Growth rule amended: every new dimension must declare its falsifier in advance | §8 regression + unfalsifiability of "metric drop = design bug" |
| 2026-08-08 | Strong-generator run on unchanged `graphfull` is the next experiment, before any new architecture | It discriminates 3 worlds; never run despite being the stated design goal |

---

## 8. Resume protocol

On a fresh/compacted session:
1. Read this file.
2. `git -C ~/Projects/graph-based-agent-system status --short` and check for a sibling.
3. Read the last rows of `docs/reconciliation/distillation_ledger.jsonl`.
4. Continue from §7's last row. Do not restart the argument from scratch.
