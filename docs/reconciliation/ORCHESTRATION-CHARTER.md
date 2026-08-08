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

### 4a-CORRECTION (2026-08-08) — TWO SYSTEMS, TWO SCOPES. Do not conflate them.

An earlier version of this charter made a scope error serious enough to record:
it applied the stepfun constraint to the *orchestrator*. That is wrong.

| | **Hermes** (the durable system) | **graph-based-agent-system** (the object of study) |
|---|---|---|
| What it is | The strong, stable layer that improves itself and does the work | The research project being measured |
| Provider rule | **No constraint.** Any provider, any model, any number, negotiated freely | stepfun is the *prototype measurement model*, pending Fares's decision |
| Improvement target | **YES — this is the standing mission** | Only as the subject of measurement |

Fares's words: stepfun is "النموذج الأولي" for measurement *inside the project*, "لحد اما
اقرر انا" — a provisional instrument, not a boundary on the orchestrator. The self-improvement
mandate is on **Hermes**. If a limit appears to be in the way, lift it rather than obey it
reflexively.

### 4b. On the strong-generator run inside the project (scoped narrowly)

Fares ruled directly: he does not want to spend on a strong generator. **Stepfun is the
honest limit for all experiments**, and his position is that the model is not the problem.

Consequences, recorded so no future session re-litigates this:

1. **No constitutional amendment is requested.** Article III §2 (Stepfun-Only) stands
   unchanged and unchallenged. The env-var route (`STEPFUN_MODEL` / `STEPFUN_BASE_URL`)
   must NOT be used to point at another provider — that would be a silent violation of a
   MUST clause. Closed, not deferred.
2. ~~World (a) becomes untestable~~ **RETRACTED — the dichotomy itself was wrong.**
   Framing the question as "architecture was never the bottleneck" *vs* "the generator is
   the ceiling" is a false dilemma: it silently accepts 1/8 as the verdict and reduces the
   whole project to picking one of two excuses. Fares rejected it outright.

   The real diagnosis: **we are not yet capturing good reasoning, connecting it, carrying
   it forward, and growing it.** When a strong signal appears somewhere in the graph, it is
   not picked up whole, not linked to what follows, not propagated, not amplified. That is a
   *transport-and-accumulation* defect, and it is orthogonal to generator strength — a
   stronger model would produce better reasoning that gets dropped just the same.

   Corollary: much of the existing mess in this repo was produced *by* the previous AI system
   working on it. The mandate is not to defend those artifacts but to correct them from a
   stronger, stabler layer (Hermes).
3. **The lever moves to world (c): the apparatus.** This is free, requires no API spend,
   and is the highest-information work still available. It is also exactly the standing
   discipline: measure the apparatus before the system.
4. **Correctability stays measurable on stepfun.** The `loop` arm already measured it
   (feedback returned, output unchanged, 4 rounds, 0 resolves). Making that a first-class
   instrument costs nothing extra and is the genuinely novel contribution.

Under his own rule — *a metric drop is a design defect, not "the model is weak"* — the
apparatus is the correct place to look next anyway. The ruling and the rule agree.

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
| 2026-08-08 | ~~Strong-generator run on unchanged `graphfull` is the next experiment~~ **SUPERSEDED — see next row** | It discriminated 3 worlds; never run despite being the stated design goal |
| 2026-08-08 | **Architect's ruling: no strong-generator spend. Stepfun is the limit for all experiments.** Article III §2 stands; env-var provider switching is forbidden, not deferred | Fares's direct decision; his position is that the model is not the problem |
| 2026-08-08 | Primary lever is now the **apparatus audit** (free), plus **correctability** as a first-class instrument on stepfun | World (a) is untestable without spend; world (c) is untested and free. Matches "measure the apparatus before the system" |
| 2026-08-08 | Declared evidence limit: this project cannot empirically separate "architecture was never the bottleneck" from "generator is the ceiling". Must be stated in writeups, not hidden | Direct consequence of the no-spend ruling |
| 2026-08-08 | **RETRACTED the above dichotomy.** Real diagnosis (Fares): good reasoning IS produced, then not captured / linked / carried / grown. Transport-and-accumulation defect, orthogonal to generator strength | Architect rejected the framing as accepting a bad number as the verdict |
| 2026-08-08 | **VERIFIED: 11 of 28 registered agents (39%) never execute on the main pipeline** — 8 directly inert, 3 via dead chains. Includes ALL 3 memory agents. Registry stores metadata strings; `governance_checks.py:88,143` importlib only confirms symbols exist | AST + chain analysis + runtime counters (`wrapped_count=28`, `failed_to_wrap={}`); repro script in `INERT-REGISTRY-FINDING.md` §4, executed |
| 2026-08-08 | Runtime counters: **28/28 fire under tests, 3/28 on a real run.** The real run is NOT evidence — it died on its first LLM call (3 Stepfun timeouts). Infra failure, not capability failure; must not be counted as one | `/tmp/real_run.log` is 5 lines; `INERT-REGISTRY-FINDING.md` §3c |
| 2026-08-08 | `reflexion_agent` removed from the inert set — reachable via an ALIASED import (`swebench_harness.py:834`, `as _gr`) that name-based AST matching cannot see. My count corrected 12 → 11 | Third defect found in my own instruments; caught by an independent instrument, never by re-reading my own output |
| 2026-08-08 | **ALL ARM COMPARISONS VOID.** Two verified defects manufactured the numbers: (D1) `FAIL_TO_PASS` is a JSON *string*, guard at `swebench_harness.py:1050` only checks for a nested list → grading command built CHARACTER BY CHARACTER; (D2) request body omits `max_tokens` (`llm_integration.py:331`) against a 30s timeout (`:289`) → unbounded generation killed mid-flight, stamped `infrastructure` | 8/8 `psf/requests` instances verified `type=str` on the live dataset; D2 reproduced: unbounded=135.5s/16,122 tok vs 30s limit; `MEASUREMENT-INVALIDATION.md` |
| 2026-08-08 | Stepfun EXONERATED by measurement — not the cause of the infra-fails. 200 OK; 800 tok in ~9s; 8/8 parallel requests succeeded; 1 working key | The defect is ours: the client requests unbounded output then refuses to wait. Blaming the provider would have been the comfortable wrong answer |
| 2026-08-08 | D2 is biased toward the HARDEST cases: short prompts finish <30s, complex reasoning generates more tokens and dies. The instrument deletes exactly the cases carrying the signal | Same pattern as the 4 earlier parser bugs — every defect so far has flattered the system |
| 2026-08-08 | Inert count corrected AGAIN: 28/28 fire under tests, **6/28 on the default CLI path, 14/28 with all optional flags**. Most "inert" agents are FLAG-GATED, not disconnected — a different diagnosis with a different remedy (enable/route, not connect) | Runtime counters; `domain_context_managers` is genuinely live under domain flags — calling it inert was wrong |
| 2026-08-08 | Survives all corrections: the **3 memory agents** (`semantic`, `working`, `episodic`) fired in NO real run, at any flag setting. Only non-test referrers are registry metadata + an importlib existence check | This is the capture-and-carry defect, located by two independent instruments |
| 2026-08-08 | Remedy for inert ≠ remedy for unreachable: **inert ⇒ CONNECT**, unreachable ⇒ delete. A subagent's "10 removal candidates" list was NOT actioned — it would have deleted the memory tier | Independent re-measurement contradicted the subagent report |
| 2026-08-08 | My own first pass (grep) was defective in both directions; corrected by AST + runtime counters. Recorded in `INERT-REGISTRY-FINDING.md` §3b | Two independent instruments disagreeing is what caught it |

---

## 8. Resume protocol

On a fresh/compacted session:
1. Read this file.
2. `git -C ~/Projects/graph-based-agent-system status --short` and check for a sibling.
3. Read the last rows of `docs/reconciliation/distillation_ledger.jsonl`.
4. Continue from §7's last row. Do not restart the argument from scratch.
