<!-- version: v8 | 2026-08-05 | verdict: pending-review -->
# Methodology Reconciliation — توحيد المنهجيات الخمسة

**Author:** the (hy3 + opus-5) system, per Fares's direction
**Date:** 2026-08-05
**Supersedes:** implicit/ad-hoc reconciliation in CONSTITUTION + ULTIMATE-GRAPH-PLAN
**Companion:** docs/reconciliation/VERSION-LEDGER.md
**Live review:** opus-5 pressure-reviewed the P4 proposal (see §LIVE below)

## 0. Why this document exists

The system is governed by **five distinct methodologies** that were added at different
times by different reasoning. They do not fully agree. Running them side-by-side without
reconciliation produces silent contradictions (a control that is simultaneously "required"
and "forbidden", or a router that claims to obey P3 while violating it). This document is
the **single reconciled source of truth** — every contradiction gets one explicit ruling.

The five methodologies:
1. **Karpathy Agentic Engineering** (4 principles: think-before-acting, simplicity, surgical, goal-driven) → Law 7 (Simplicity) etc.
2. **opus-5 philosophical audit** → CONSTITUTION Article VI, P1–P7 (Requisite Variety, Verified Closure, Domain-Gated, Bounded Probing, Custodial Context, Productive Contradiction, Least Sufficient Intervention).
3. **Cynefin sense-making** (Clear / Complicated / Complex / Chaotic) → referenced by P3.
4. **Reflexive loops** (AlphaCode sampling + Reflexion verbal-RL + debugger repair) → ULTIMATE-GRAPH-PLAN.
5. **Distributed governance** (no supreme decision agent) → GOVERNANCE-SYSTEM.md.

## 1. The contradictions (C1–C5) and their rulings

### C1 — "No supreme governor" vs the meta-loop that edits controls
- **Tension:** GOVERNANCE-SYSTEM says *no single agent owns the big decision*; the
  META-SYSTEM (`system/self_improvement.py`) proposes AND would apply control changes.
- **Ruling:** The meta-loop is a **proposer only**. Application of any control change
  requires either (a) a reversible config/flag flip, or (b) an explicit human checkpoint.
  This preserves "no supreme governor" — the loop has no unilateral authority. The
  `gate()` function already enforces observability + reversibility; we now *also* require
  that `apply` is never automatic for non-flag changes.
- **Resolves:** Article VI gains a sub-clause: *"The meta-loop proposes; it does not
  apply. Application is gated by P7 + human checkpoint."*

### C2 — Law 7 (Simplicity / small core) vs ULTIMATE-GRAPH-PLAN (22 agents)
- **Tension:** Law 7 demands the simplest thing; the plan grows the graph to 22 agents.
- **Ruling:** Growth is permitted **only when P1 (Requisite Variety) forces it** — i.e.
  a routing point has more failure modes than outcomes, so a new specialized agent is the
  minimal response. Every added agent must later pass P7 (demonstrably catches a failure)
  or be pruned. "Small core" means *no agent that does not earn its place*, not *few agents
  at all costs*.
- **Resolves:** Law 7 annotated: *"Small = no redundant agent; growth is justified only
  by P1 + later confirmed by P7."*

### C3 — Law 11 (no LLM in evaluate) vs Reflexion/Debugger LLM reflections
- **Tension:** ReflexionAgent and DebuggerAgent generate LLM text that feeds the propose
  step; Law 11 forbids LLM in `evaluate()`.
- **Ruling:** Sharp boundary. The **verdict** (pass/fail, breaches) is ALWAYS zero-LLM
  (Law 11 holds). The **reflection** (a natural-language hypothesis) is LLM-generated but
  is classified as *input to propose*, NOT as evaluation. We tag it `llm_reflection_input`
  so audits can distinguish "LLM-as-input" from "LLM-as-judge". Law 11 is narrowed to
  *"no LLM in the accept/reject verdict"*.
- **Resolves:** Law 11 annotation added.

### C4 — P3 (Cynefin domain-gated) vs keyword `detect_task_type`
- **Tension:** P3 says control intensity follows Cynefin domain + reversibility; the live
  router picks slice by substring ("humaneval", "e-commerce").
- **Ruling:** The keyword router is a **legacy shortcut**, not P3. Replace it with a
  `CynefinClassifier` node that infers {Clear, Complicated, Complex, Chaotic} from the
  task's reversibility + ambiguity, and binds control intensity to that (Clear→VERIFY
  only; Complex→probe budget; Chaotic→human). The keyword router may remain as a cheap
  pre-filter but its output is overridden by the classifier. (See Task C / v3.)
- **Resolves:** P3 becomes enforceable; the router stops lying about obedience.

### C5 — Claimed "opus-5 distillation" without a provenance channel
- **Tension:** P1–P7 are attributed to opus-5 but there is no ledger proving they were
  actually distilled (frozen principle) vs just written by a human.
- **Ruling:** Every principle carries a **distillation ledger entry**: source (opus-5
  audit), date, the frozen principle text, and status (proposed → distilled → enforced).
  A principle without a ledger entry is *advisory only*, never enforced. (See Task D / v4.)
- **Resolves:** Provenance becomes auditable; "distilled" means *ledger-recorded*.

## 2. The fallacies (F1–F3) and corrections

### F1 — "27 agents = comprehensive coverage"
- **Correction:** 9 of 27 are not reachable from the live path (audit finding). Agent
  **count is a vanity metric**. Strength = reachable ∩ observed-effect. The P7 pruning
  report (`system/self_pruning.py`) is the real coverage measure.
- **Action:** Stop citing "27 agents" as a strength; cite "18 reachable, N with observed
  effect".

### F2 — "Loops/reflexion improve results"
- **Correction:** On `step-3.7-flash`, loop/alphacode did NOT lift resolve rate (1/8 = 1/8
  on the same slice). The loops improve **reliability + governance**, not raw capability.
  The capability ceiling is the **generator**, not the graph.
- **Action:** Split metrics — `governance_score` (does the system obey its own rules?) from
  `success_rate` (does it solve the task?). Report both. Never claim a loop "improved
  results" when only governance improved. (See Task F / v6.)

### F3 — "The script = the system improves itself"
- **Correction:** `system/self_improvement.py` is an **observer script**, not a
  self-improving graph. True self-improvement requires the meta-loop as **nodes inside the
  LangGraph StateGraph**, reading/writing graph state, not a cron job outside it.
- **Action:** Embed the loop as `agents/systems_layer.py` (Task B / v2). The cron stays as
  a measurement runner, not the improver.

## 3. The reconciled authority model

```
                    ┌──────────────────────────────────────────┐
                    │  SYSTEMS LAYER (in-graph, proposed)        │
                    │  measure → compare → propose → distill →   │
                    │  gate → apply_or_escalate                  │
                    │  (proposes ONLY; never auto-applies)       │
                    └───────────────────┬──────────────────────┘
                                        │ writes control_proposals
                                        ▼
   HUMAN CHECKPOINT ◀─────────── (non-flag changes) ────────────▶ DOMAIN LAYER (27 agents)
                                        │
                    (reversible flag changes applied, logged)
```

- **No supreme governor:** the systems layer proposes; humans (or flagged config) apply.
- **Provenance:** every principle in the systems layer traces to the distillation ledger.
- **Observation:** every control survives only if P7-observed to catch a failure.

## 4. Open questions carried forward
- Should the systems layer itself be subject to P7 (can it prune its own nodes)? → yes,
  but only after v2 lands and we observe it.
- Does swapping the generator (SOTA-POSITION.md §4) shrink the needed agent set? → predicted
  yes; P7 will remove now-redundant agents.
- Is the measurer allowed to be measured? → No (Ashby): the observer must sit outside what
  it observes. The cron runner stays external; the in-graph layer observes the domain layer
  only.

## 5. LIVE opus-5 review (2026-08-05, deleg_ebfc3e6d) — P4 probe_budget

The meta-loop emitted a control proposal (`probe_budget`, ref P4) after observing
`thrash_count` 0→3. opus-5 was consulted LIVE (agentrouter-org/claude-opus-5) and returned
a pressure-review that hardened the proposal. Recorded verbatim in
`system/distillation_ledger.jsonl` (type=opus5_review, ruling_id=P4).

**opus-5 verdict (condensed):**
- A budget *bounds* thrashing, it does **not reduce** it. Novelty is the real control; N is
  only a stop-loss. → do not ship probe_budget as the fix.
- The trigger signal is weak: `thrash_count` uses Jaccard≥0.6 on reflection *text* (word
  reuse), not hypothesis identity. step-3.7-flash rephrases one theory (false negative) or
  reuses a traceback while genuinely narrowing (false positive). **Harden the signal before
  enforcing control on it (P7).**
- Capability risk is real on a weak model: a hard cap amputates the round-4 fix. Count a
  probe as spent only when there is *no measurable progress* (failing-test count not
  decreasing); progress refunds the probe.
- Make "NEW hypothesis" enforceable: carry a rejected-hypothesis list in graph state and
  inject it as a negative constraint into the next debugger prompt (P5).
- Escalate with artifacts (hypothesis trail, diffs, failing tests) — or you convert agent
  thrash into human thrash.
- **Falsify first:** replay logged runs; adopt only if capping at N loses zero successes
  found at attempt >N. Scope to Complex per P3.

**Code finding opus-5 surfaced:** `scripts/run_improvement_cycle.py` hardcoded
`thrash_count: 0` in the measure path, so the 0→3 rise could not be observed from the cycle
script. **Fixed in v8** — `measure_benchmark()` now reads the live harness output
(`scripts/measure_thrashing.main()` returns (dbg_max, ref_max)); falls back to 0 only on
harness error. Covered by `tests/test_thrash_measure.py`.

**Resolution:** P4 stays a *proposed, scoped-to-Complex, signal-hardened* control. The
meta-loop will not auto-apply it (C1-rev1 default-deny); application requires an independent
opt-in + a hardened thrash signal. This is the distillation loop working as designed:
proposal → opus-5 review → hardened ruling → recorded provenance.
