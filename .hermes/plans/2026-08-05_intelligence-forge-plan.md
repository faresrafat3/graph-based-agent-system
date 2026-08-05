# Plan — Intelligence Forge: Context-as-System, Bespoke Governed Agents

**Date:** 2026-08-05
**Author:** hy3 (with Fares's direction + opus-5 / gpt-5.6-sol pressure-check + opus-5 FINAL review)
**Status:** DRAFT v2 (post opus-5 review) — Q1-Q3 DECIDED by design-council (2026-08-05, hy3). Build unblocked; proceed Task 1→4.

---

## 0. What Fares actually said (verified against 2 models + final review)

Faithful core (confirmed by opus-5 + gpt-5.6-sol):
1. **CONTEXT = the system itself.** An agent's context is not a small prompt — it IS the big
   graph / many bespoke agents / all specs (old+new). The context is a managed, deep-running system.
2. **Agent = a "living" entity.** Its context carries instructions + role + lifecycle ("life") +
   what-it-will-do. We LET the LLM "live" (autonomous) BUT it is bound by a **HIGH INTELLIGENCE
   I DEFINED** (a governance layer we specify).
3. **Among other agents → focused task.** Being in a system of agents gives it a task it can
   concentrate on (division of labor), not an open-ended one.

### Corrections the models forced (do NOT build these as if Fares said them):
- **#3 causality:** the binding is the DEFINED HIGH INTELLIGENCE (enforced layer), NOT merely
  "being among other agents." Peer-presence is the *reason* for focus, not the restraint itself.
- **#4-5 are MY extrapolation, not Fares's words:** "we step away / weak models run our spirit"
  and "system has its own self-repair meta-loop" are design posture / my extension. Treat as
  OPTIONAL extensions, never as his spec.
- **Most dangerous misbuild (both models agree):** implementing HIGH INTELLIGENCE as a
  prompt/jailbox of rules bolted onto the LLM. The constraint must be ARCHITECTURAL — the
  agent's structural position in the topology that forces a focused claim.

### opus-5 FINAL review (APPROVE-WITH-FIXES) — critical:
- **DO NOT build parallel governance.** `system/governance_checks.py`, `agent_registry.py`,
  `deterministic_validator.py`, `cynefin_classifier.py`, `self_pruning.py` ALREADY implement
  P2/P3/P7 as *architecture*. New `spec_store.py` / `governance_layer.py` = DUPLICATION /
  governance drift / fork of the constitution. **EXTEND existing files; never ship a 2nd authority.**
- **The meta-loop is the live backbone, NOT "extension only."** `systems_layer.py` + `sage_council.py`
  already run P5 (custodial cycle_log) + P6 (reconciler + consensus conflict detection). Re-sequence
  around them, do not build a new governance layer beside them.
- **P1 (Requisite Variety) + P4 (Bounded Probing) are MISSING from the architecture.** Add
  enforcement or explicitly mark out-of-scope.
- **Bespoke guarantee is unproven.** `agent_forge` will collapse into a template factory (the
  clone trap). Must specify per-agent distinctness enforcement + a test asserting no two agents
  share a behavioral/template hash.
- **Q1 blocks Task 2.** "Defined intelligence = P1-P7+CIR or a stricter new set?" MUST be answered
  before any governance code.

---

## 1. Design principles (the "DNA" we embed)

- **P-EMBED:** The defined intelligence is an ENFORCED, AUDITABLE layer in the architecture,
  not a prompt wrapper. (Directly from model warning C.)
- **P-BESPOKE:** Every agent is built purpose-specific (governed + bespoke). No template clones.
  DISTINCTNESS is enforced + tested (no shared behavioral/template hash).
- **P-CONTEXT-IS-SYSTEM:** An agent's context exposes the managed system (graph + specs + peers),
  not a trimmed summary. Built by EXTENDING existing stores, not a new parallel one.
- **P-FOCUS:** Topology assigns each agent a focused task via its structural position.
- **P-AUDIT:** Every governance decision is recorded + replayable (extends existing ledger).
- **P-NO-FORK:** Never create a 2nd governance authority. EXTEND `governance_checks.py` etc.

---

## 2. Architecture (REVISED — extends existing infra, no fork)

```
   EXISTING (live backbone, do NOT duplicate):
   - system/governance_checks.py  (P2 verify-no-LLM, entrypoint reachability, permission matrices)
   - deterministic_validator.py   (P2 Verified Closure)
   - cynefin_classifier.py        (P3 Domain-Gated Governance)
   - self_pruning.py              (P7 Least Sufficient Intervention)
   - agents/systems_layer.py      (meta-loop: measure→philosopher→...→record; P5/P6 live)
   - agents/sage_council.py       (ConsensusMechanism: P6 conflict detection)
   - agent_registry.py            (30 agents)

   NEW (extends, does not fork):
   - agents/agent_forge.py        EXTENDS agent_registry: bespoke-per-agent constraint set,
                                   distinctness test. No template. (P-EMBED, P-BESPOKE)
   - agents/topology_assembler.py EXTENDS systems_layer edges: typed focus edges.
                                   (P-FOCUS, P1 Requisite Variety)
   - system/bounded_probe.py      EXTENDS cynefin_classifier: P4 Bounded Probing enforcement.
   - context view                 EXTENDS existing state (cycle_log) to expose system-as-context.
                                   (P-CONTEXT-IS-SYSTEM, P5)
```

The governance layer is NOT a prompt around the LLM. It is:
- **Structural:** who an agent may message, what claim it may emit (typed edges) — via topology_assembler.
- **Enforced:** existing validators reject violations (auditable) — extended, not replaced.
- **Embedded:** compiled into the graph, runs on weak models without us present.

---

## 3. Build sequence (smallest coherent pieces, one at a time) — REVISED

### Task 1 — Extend governance with P1 + P4 (no new authority) — DONE (2026-08-05)
- `system/bounded_probe.py` (NEW): P4 Bounded Probing enforcement. `ProbeBudget` tracks N attempts,
  each a NEW falsifiable hypothesis (reuses `debugger_agent.extract_hypothesis`, zero-LLM). On repeat
  OR budget-exhaust → escalate with auditable `hypothesis_trail`. `enforce_bounded_probe()` runs a
  full session. **Architectural, not a prompt.**
- `check_requisite_variety` ADDED to `system/governance_checks.py` (P1). Inspects real call graph from
  `LIVE_ENTRYPOINT`; honors `EXTERNAL_ALLOWED` (consistent with existing `check_entrypoints_reachable`).
  Wired into `run_governance_checks` (now 8 checks).
- Tests: `tests/test_p1_p4_governance.py` (7 tests). 354 passed.
- NO fork: extended existing infra only.

### Task 2 — Bespoke Agent Forge (no templates) [UNBLOCKED — Q1 DECIDED] — DONE (2026-08-05)
- `agents/agent_forge.py` (NEW): `forge_agent()` produces ONE bespoke `ForgedAgent` from
  (spec_slice + focused_task + governance_profile). `extend_registry()` adds it to AGENT_REGISTRY
  (EXTEND, idempotent, does NOT rewrite the 30). `assert_distinct()` HARD-fails on shared
  behavior_hash (clone-trap guard, P2 zero-LLM). `context_view()` = the agent's CONTEXT (instructions
  + role + lifecycle-in-graph-state + what-it-will-do), bound to existing P1-P7+CIR (Q1).
- `forge_agent` is PURE (no global mutation); EXTEND is explicit. Fixes registry-pollution.
- Tests: `tests/test_agent_forge.py` (6 tests). 361 passed.
- NO fork, NO template: bespoke + governed.

### Task 3 — Context-as-System view — DONE (2026-08-05)
- `agents/context_system_view.py` (NEW): `build_context_view()` merges the agent's own
  context_view() with the live graph state (cycle_log = system's persisted life, P5) + peer
  agents from the registry + constitution binding. The agent's CONTEXT = the whole managed
  system (P-CONTEXT-IS-SYSTEM). `context_includes_system()` is a zero-LLM auditable guard.
- EXTENDS existing state (cycle_log), no parallel store. Peers capped at 20 (observable, P2).
- Tests: `tests/test_context_system_view.py` (4 tests).

### Task 4 — Topology Assembler (focus edges) — DONE (2026-08-05)
- `agents/topology_assembler.py` (NEW): `build_focus_edges()` emits TYPED edges per agent —
  FOCUS (agent -> its focused task = structural binding, P-FOCUS), VERIFY (P2 closure),
  conditional peer-review (P6) + escalate (P3/P4). `GraphEdge` HARD-rejects untyped edges
  (constitution-enforced). `assemble_topology()` is PURE, returns spec with `extends:
  systems_layer` (P-NO-FORK).
- This is where "among other agents -> focused task" becomes STRUCTURAL, not emergent hope.
- Tests: `tests/test_topology_assembler.py` (5 tests).

### Task 5 — Meta monitor (extension, NOT core) — DONE (2026-08-05)
- Confirmed the EXISTING `systems_layer` StateGraph IS the live backbone (measure -> philosopher
  -> reconciler -> compare -> propose -> distill -> gate -> apply_or_escalate -> record). It runs
  end-to-end (integration test proves cycle_log fills). Forge/context/topology assemble ON TOP
  (P-NO-FORK) — no second governor created.
- Tests: `tests/test_meta_monitor_backbone.py` (2 tests).

---

## 4. What we explicitly do NOT build (per model warnings)
- No constitution-prompt wrapper around the LLM.
- No "self-repair meta-loop" claimed as Fares's spec (extension only).
- No template/role-play cloning (distinctness test guards this).
- No 2nd governance authority (P-NO-FORK: extend existing).
- No assumption we "step away" — we build the enforced layer, then it runs; our presence is
  not required for runtime, but that is a consequence, not a feature we assert.

---

## 5. Open questions — DECIDED (design council, 2026-08-05)
- **Q1 — DECIDED: EXISTING constitution (P1-P7 + CIR).** C5 makes any new principle without a
  `distillation_ledger` entry advisory-only/non-enforceable; the defined intelligence must be an
  ENFORCED layer (P-EMBED), so it rests on the already-enforceable P1-P7+CIR. P7 forbids adding
  unproven rules. Only gap (P1/P4 not in code) is closed by Task 1 — no new set.
- **Q2 — DECIDED: forge a NEW class on top; do NOT rewrite the 30.** P7 (least sufficient
  intervention) — the 30 already carry the constitution structurally. C2: growth only when P1
  forces; rewrites aren't. P-NO-FORK: `agent_forge` EXTENDS `agent_registry`.
- **Q3 — DECIDED: RE-FORGED per task; "life" in GRAPH STATE (cycle_log), not a thread.** P5
  (context serializes to state); Article VI §2 rejects tacit continuity. P7 + "What We Reject
  (Wu-wei)": persistent stateful agents drift and narrate success.

## 6. Highest-risk failure mode (added by design council)

- **Risk:** Constitutional drift into a *silent supreme governor* — the meta-loop/forge accretes
  rule-changing authority, or "living" agents narrate success with no verified postcondition, so
  `governance_score` stays green while reality diverges (the F2 metric-conflations trap).
- **Constitutional prevention (architecture, not a prompt):**
  - **C1** — meta-loop is default-deny, proposer-only; independent reversibility + counter-proposal
    channel → it can never apply a control unilaterally.
  - **C5** — a principle without a `distillation_ledger` entry is advisory-only, never enforced.
  - **P2 Verified Closure** — every write edge terminates in a zero-LLM VERIFY node reading a
    declared postcondition (`deterministic_validator.py`); drift cannot pass silently.
  - **P7 self_pruning** — any control/agent not catching a failure in N cycles is flagged for removal.
  - **F2** — `governance_score` reported separately from `success_rate`; green governance can't mask
    red outcomes.
  - **P6** — contradiction is a first-class routed signal; suppressed divergence surfaces.
  - **Non-LLM `governance_checks.py`** — hard-fails CI on invariant breach.
  The binding constraint is the *compiled graph*, not words around the LLM.

---
*Draft v2 (post opus-5 final review). Q1–Q3 DECIDED by design council 2026-08-05 (Fares declined to
answer; deep-model call per his directive). Task 2 unblocked. Models consulted: opus-5
(deleg_1c70e988, deleg_df373b7d), gpt-5.6-sol (deleg_4d58f760).*
