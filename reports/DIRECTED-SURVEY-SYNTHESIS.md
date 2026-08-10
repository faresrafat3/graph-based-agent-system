# Directed Survey — Synthesis & Live Loop

> Autonomous directed survey over `graph-based-agent-system` (start commit `c0e7f5a`).
> Mode: **propose-only** under Constitution Ruling C1 (default-deny). No source mutated.
> Frequency: cron `directed-survey-loop` every 30 min, change-detection gated (LIVE>cron).
> Governing standards applied: CONSTITUTION Rulings C1 / C2 / F2, Laws 3 & 7, P1/P2/P7.

---

## What the apparatus actually measures (the core finding)

The system's own governance check (`check_entrypoints_reachable`) reports **INERT = 0** and stays GREEN.
Our two-pass directed survey (name-graph ∪ strict `ast.Call`) shows that green is **partly false**:

| Dimension | System says | Survey says | Verdict |
|---|---|---|---|
| Registry size | 28 | 28 | ✅ |
| Reachable (name-graph) | 18 | 18 | upper bound |
| **Reachable (real call-site)** | not measured | **18** | the honest number |
| INERT (system) | **0** | — | **false green** |
| Honest inert (never called, not external) | — | **1** (`run_karpathy_pipeline` self-ref) | real gap |
| External-declared but never called | — | **9** (incl. all 3 memory agents) | the Fares 9/28, confirmed |
| **Reachable AND external (contradiction)** | — | **7** | classification bug |
| Genuinely live (pipeline/orchestrator) | — | **13** | ✅ |
| Live-only-via-beta (competitive subtree) | — | **5** | namespace candidate |

**Governance Score (F2): `0.5`** — judges rule-adherence, not task success.

### The two real defects
1. **Contradiction (classification bug).** 7 agents are in BOTH `reachable` and `EXTERNAL_ALLOWED`.
   Math impossibility: 18 + 17 = 35 > 28. The system cannot tell whether they are on the live path.
   (e.g. `AuthSquadAgent`, `Integration Agent`, `Progress Monitor`, `Reflexion Agent`, `Sampling Agent`,
   `Debugger Agent`, `Competitive Slice Graph`.)
2. **Silent dead weight / inert declaration.** 9 agents are registered, declared external, and **never called**
   on any path — including all 3 memory agents. Listing them validates the registry loads, but the system
   does not *use* them. This is exactly the "sloppy" pattern Fares rejects (a plugin that merely proves it loads).

---

## The falsifiers (declared up front, per Fares rule)

- `name_graph_reachable >= call_site_reachable` always; divergence ⇒ measurement mis-calibrated.
- `call_site_reachable > 0`; if 0 the live head is dead (critical).
- `len(reachable & EXTERNAL_ALLOWED) == 0`; non-zero ⇒ contradiction bug (this run: 7 ⇒ FAILS).
- `governance_score` reported separately from `success_rate` (F2), never conflated.

---

## GOALS (self-escalated, propose-only)

- **G1 (P0) — Fix the contradiction.** Enforce EXACTLY-ONE-SET (reachable XOR external); tighten
  `_transitive_reachable` to require a real `ast.Call` edge; stop force-seeding subtrees. → `PROPOSAL-fix-contradiction.md` (delegated, pending).
- **G2 (P1) — Resolve the 9 never-called agents.** For each: CONNECT (preferred for memory + escalation) into
  the live path, DELETE (P7) if no failure mode justifies it, or KEEP-EXTERNAL only if a real call path exists.
  → `PROPOSAL-connect-memory-escalation.md` (delegated, pending).
- **G3 (P1) — Namespace the beta arm.** Move the 5 competitive-slice-only agents out of the production registry
  into an experiments namespace so the green check reflects the production graph. → `PROPOSAL-beta-agents.md` (delegated, pending).
- **G4 (P1) — Honest pruning.** Wire `self_pruning.py` to the STRICT call-site reachable set so P7 prunes real
  silent controls instead of trusting a false-positive green.
- **G5 (monitor) — Keep the loop alive.** `directed-survey-loop` cron runs every 30 min; alerts on structural change only.

---

## LOOP STATUS

- ✅ Survey engine built: `scripts/directed_survey_inert.py` (deterministic, zero-LLM, zero-keys).
- ✅ LATEST artifacts: `reports/directed-survey-inert.LATEST.{json,md}` + timestamped history.
- ✅ Cron monitor: `directed-survey-loop` (every 30 min, change-gated, deliver=origin).
- 🔄 3 depth delegations running in background → proposal reports land in `reports/PROPOSAL-*.md`.
- ⏸️ Apply step is **opt-in only** (C1). When the proposals land, the human co-governor decides CONNECT/DELETE/MOVE.

---

*Next auto-cycle: the cron loop re-runs in 30 min and alerts only if the live graph structure changed.*
