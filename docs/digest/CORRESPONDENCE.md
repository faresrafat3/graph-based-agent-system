# CORRESPONDENCE — prime-agent mechanism ↔ our system ↔ gap ↔ action

> Gate: `scripts/meta_loop.py verify L2`. Every mechanism in `MECHANISMS.md` must appear
> here with a real action — placeholder markers are rejected by the gate as a substring match,
> so this file must not contain one anywhere, including in its own prose.
>
> Status vocabulary:
> - **LANDED** — ported, with a RED→GREEN test naming the upstream source.
> - **GAP** — real absence in our system, understood and specified.
> - **PARTIAL** — something exists but does not carry the mechanism's load-bearing property.
> - **N/A** — deliberately not adopted; the reason is recorded, not implied.

| id | mechanism | our counterpart | gap | status | action |
|---|---|---|---|---|---|
| M1 | Branch-version invalidation | `system/self_improvement.measurement_version` / `is_proposal_stale`; stamped in `agents/systems_layer.propose_node` | none | **LANDED** | Done — `tests/test_proposal_staleness.py` (6 tests, RED→GREEN). Fails safe: unstamped reads STALE. |
| M2 | Plan result as discriminated union | `control_proposals` (bare dicts) | no terminal-state vocabulary; `skip` / `invalidated` / `failure` are indistinguishable | **GAP** | Add a `status` field to proposals with those four values so a human reading the board can tell "nothing to do" from "was valid, no longer". |
| M3 | Turn-boundary-aware compaction cut | none — we have no compactor | we would hit the classic orphaned-tool-result bug on first implementation | **GAP** | Port `findTurnStartIndex` semantics BEFORE writing any compactor. Pure function, directly unit-testable. |
| M4 | Compaction as a pure predicate | `system/refine_gate.py` (similar shape, different subject) | none structurally | **N/A (pattern already held)** | Keep any future `should_compact` pure and outside the node body, matching our existing gate style. |
| M5 | `CompactionReason` taxonomy | none | a future compactor would lose *why* context shrank | **GAP** | Adopt the four-value reason enum when M3 lands; record it on the measurement so runs compacted under `overflow` are not compared to clean ones. |
| M6 | Bounded overflow recovery | `SidecarResult.retries` counts retries | counts but does not BOUND; no state machine | **PARTIAL** | Add an `idle → attempted → reported` bound so a retry loop terminates instead of spinning. |
| M7 | Typed benign-failure signalling | `HarnessError` (genuine faults only) | no benign class; a no-op refinement looks like a failure | **GAP** | Add a `HarnessSkipped` subclass so no-op refinements stop polluting the failure signal our measurements read. |
| M8 | Snapshot-per-change child tracking | per-agent state in graph state | single status axis; no immutable whole-snapshot emission | **PARTIAL** | Split lifecycle status from activity; emit whole snapshots so late observers need no replay logic. |
| M9 | Transparent nested event forwarding | LangGraph subgraph events | nested child events are not re-emitted verbatim at the root | **GAP** | Forward nested updates unchanged; fold only lifecycle events into the parent snapshot. |
| M10 | Registration-time race guard | `prime_agent_node` spawn path | cancellation between spawn and register would leak a live process | **GAP** | Re-check disposal/cancel state at REGISTRATION time, not only before spawn. |
| M11 | Injectable self-critique seam | `system/opus5_consult.distill_opus5` | closer to a hardcoded call than an interface | **PARTIAL** | Make it a `(request, signal) -> Review` protocol with a model-backed default. This is exactly what would have kept the loop testable when delegation died on provider errors. |
| M12 | Two-tier merged memory | `ContinualHarness` has a `scope` field | the label exists; the two-tier merge does not — single backing store | **GAP** | Implement `merge_harness_states(global, local)` so "learned globally, overridden here" is expressible. |
| M13 | Session JSONL tree v3 (id/parentId) | `system/distillation_ledger.jsonl` | flat append-only log; no parent links, so no branching and no replay | **GAP** | Adopt `id`/`parentId` + entry kinds (TODO.md E4). Ids, never indices — indices break under history rewrite. |
| M14 | Leaf-to-root context walk | none | no principled split between "context" and "audit-only" entries | **GAP** | Implement the walk with a bookkeeping-entry exclusion list, so operational metadata stays out of model context while remaining auditable. |
| M15 | Compaction summary chaining by stable id | none | long-run survivability and post-hoc cost measurement both absent | **GAP** | Carry `previousSummary` + `firstKeptEntryId` + `tokensBefore` when M3/M13 land. |
| M16 | A2A delivery modes (auto/steer/follow_up) | `agents/topology_assembler.py` typed edges | edges are typed by ROLE but carry no delivery timing; no receipt | **GAP** | Add `delivery_mode` to edges plus a `delivered`/`queued` receipt (TODO.md E3), making delivery observable rather than assumed. |
| M17 | Due-tick claim before delivery | cron-driven measurement cycles | a crash mid-cycle can replay an uncertain prompt; missed ticks could pile up | **GAP** | Claim-then-deliver, and coalesce missed ticks instead of accumulating a backlog. |
| M18 | Strict JSONL framing (LF only) | `RpcFrame.from_line` + Python file iteration | none — Python splits on `\n` only, unlike Node `readline` | **LANDED** | Verified and pinned: a payload containing U+2028/U+2029 survives round-trip (`tests/test_prime_agent_adapter_protocol.py`). |
| M19 | Command responses distinct from events | `PrimeAgentAdapter.run` | was: `response` frames ignored entirely → a rejected prompt blocked forever | **LANDED** | Fixed — `success:false` now returns `HUMAN_CHECKPOINT` with the command and error attached. |
| M20 | Health events as protocol members | `SidecarResult.errors/retries/compactions` → `prime_agent_health` | was: 3 of 16 events handled; retries/compactions/errors invisible | **LANDED** | Fixed — infra facts now travel with the result so measurement can separate infra from capability failure. |
| M21 | Ordered async teardown | `PrimeAgentAdapter.close()` | terminates and waits, but no ordered teardown for nested work | **PARTIAL** | Add ordered teardown once the sidecar can spawn children of its own. |
| M22 | Closure-returning subscribe | none (no observer registry) | — | **N/A (with a correction)** | If we build an observer registry, adopt the closure-return shape BUT log swallowed listener exceptions — the upstream discards them silently, which would violate our Law 3. |
| M23 | Pause upstream without disturbing observers | none | no safe mid-run graph mutation path | **GAP** | Hold the upstream subscription in one handle so ingestion can pause/resume without tearing down client-facing streams. |
| M24 | Single-claimant plan consumption | `propose → gate → apply` (human-applied, Ruling C1) | no claim; two simultaneous cycles could double-apply | **GAP** | Install a claim promise; a concurrent caller awaits the holder's FULL processing, not merely the underlying future. |

## Rejected mechanisms (recorded so the decision is auditable)

| mechanism | decision | reason |
|---|---|---|
| IPython-as-universal-tool (RLM) | **reject** | Weak at enforcing permission boundaries. Our READ/WRITE/NEVER/HUMAN_CHECKPOINT is architectural, not prompt-level. Their own docs state the kernel is not a sandbox. |
| pi-mono / TUI stack | **reject** | Product-shape specific; we are Python with no terminal UI. |
| Kernel-as-sandbox assumption | **reject** | Explicitly disclaimed upstream; untrusted code requires real isolation. |

## Honest coverage statement

24 mechanisms mapped: **4 LANDED**, **4 PARTIAL**, **13 GAP**, **3 N/A**.

This matrix covers the mechanisms we could verify directly (53 line-citations checked against
the real clone; every cited line exists and was spot-checked for accuracy). It does NOT cover
`packages/ai/src/providers/*` — delegated extraction of that area failed four times on
provider-side content filters, and inventing mechanisms from filenames would defeat the
purpose of this document. That area remains undigested and is recorded as such.
