# ADR — Intelligence Forge: Context-as-System, Bespoke Governed Agents

**Status:** ACCEPTED (2026-08-05, reviewed by opus-5 + gpt-5.6-sol)
**Author:** hy3 (with Fares's direction)
**Supersedes:** none (extends existing governance — no fork)

## Context

Fares's vision: the **context IS the managed system** — a big graph of many *bespoke* governed
agents, each "living" under a HIGH INTELLIGENCE that is *defined* (the constitution P1-P7 + CIR)
and *embedded as architecture*, not as a prompt around an LLM. We step away; weaker models run
with our "spirit". The earlier design risk (flagged by opus-5 + gpt-5.6-sol) was that this could
collapse into (a) a forked parallel authority, (b) a prompt-wrapper clone of the LLM, or
(c) demo-shaped completeness where the new pieces are never reached by the live path.

## Decision

Build the **Intelligence Forge** as an *extension* of the existing governance, not a second
authority:

| Piece | File | Role | Constitution binding |
|-------|------|------|----------------------|
| P1 + P4 enforcement | `system/bounded_probe.py`, `governance_checks.check_requisite_variety` | extend existing infra | P1 Requisite Variety, P4 Bounded Probing |
| Bespoke forge | `agents/agent_forge.py` | forge 1 bespoke agent per input; clone-trap guard | no template (Fares: no role-play clones) |
| Context-as-System | `agents/context_system_view.py` | agent's CONTEXT = the managed system | P-CONTEXT-IS-SYSTEM, P5 (life in graph state) |
| Topology Assembler | `agents/topology_assembler.py` | typed FOCUS/VERIFY/peer/escalate edges | P-FOCUS, P-NO-FORK |
| Sage Council | `agents/sage_council.py` | local CIR consensus (no opus-5 at runtime) | P6, CIR |
| Meta-loop backbone | `agents/systems_layer.py` | StateGraph: measure→…→record (disk-persisted) | P2 verified closure, P7 least-sufficient |

**Q1/Q2/Q3 (decided by the architecture council, opus-5 + gpt-5.6-sol):**
- Q1: defined intelligence = the EXISTING constitution P1-P7 + CIR (no new stricter set; C5 forbids
  unenforceable new laws).
- Q2: forge a NEW class ON TOP of the existing 30 (extend `AGENT_REGISTRY`, do not rewrite).
- Q3: agents are RE-FORGED per task; "life" persists in GRAPH STATE (cycle_log), not a private thread.

## Strong-Model Review Findings (2026-08-05) & Resolutions

opus-5 + gpt-5.6-sol pressure-tested the full architecture and found 3 real weaknesses; all fixed:

1. **Forge amputated / governance blind spot** — forge/topology/context/probe were reachable only
   from a demo/test; the live `karpathy_pipeline` and `systems_layer` imported none of them, and
   none were in `AGENT_REGISTRY`, so governance could not see them. Worse (gpt-5.6-sol #1-b):
   forging + `extend_registry` bumped governance breaches **0 → 6** (missing module/entrypoint/
   lifecycle doc/test file) — the system could not self-extend without self-violating.
   *Fix:* `check_forge_wired` surfaces the wiring gap as a visible WARNING (tracked, not hidden);
   `extend_registry` is now **TRANSACTIONAL** — it scaffolds the required on-disk artifacts
   (module+entrypoint, test file, lifecycle doc) so the new entry is governable, then registers
   it, and **rolls back** (deletes scaffolds + entry) if the registry still has any breach. The
   forged entrypoint is declared in `EXTERNAL_ALLOWED` (intentionally external, re-forged-per-task
   per Q3) so the reachability gap stays visible (Law 3) while governance stays green.
2. **Consensus theater** — 14 sages emitted 1 distinct view body (only the name tag differed), so
   the fusion was an echo, not disagreement. *Fix:* `Sage.reason()` now emits a DISTINCT stance per
   principle slice, modulated by the signals (breaches→verify/prune, complexity→gate/variety,
   thrash→bound/surface). Conflict detection now matches the real stance vocabulary.
3. **Context-scaling break** — `peers[:20]` was an unnamed silent cap, `cycle_log` was unbounded,
   and `MemorySaver` lost all state on restart. *Fix:* named `MAX_PEERS`/`MAX_CYCLE_LOG` bounds
   (cycle_log truncated + flagged); a dependency-free `JsonlCheckpointSaver` makes the meta-loop
   state durable on disk (survives restart).

## Consequences

- The constraint is now **architectural** (who may message whom, what terminates in VERIFY, the
  clone-trap) — not a prompt wrapper around the LLM.
- No fork of the constitution; the existing governance (`governance_checks`, `deterministic_validator`,
  `cynefin_classifier`, `self_pruning`) remains THE authority.
- 210 bespoke agents forge clone-free (`scripts/forge_scale_demo.py`), proving scale without clones.
- Risk: the forge is not yet wired into the live `karpathy_pipeline` import graph; until then
  `check_forge_wired` reports a breach (intentional — surfaces the gap rather than hiding it).

## Verification

- `make test` → 374+ passed (forge/context/topology/sage/scale/disk all covered)
- `make audit` → clean (28 items)
- `make compile` → clean
- `python scripts/forge_scale_demo.py --count 210` → 210 distinct hashes, 0 clones, 735 edges
