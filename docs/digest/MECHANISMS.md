# MECHANISMS — transferable mechanisms extracted from prime-agent

> Source: `PrimeIntellect-ai/prime-agent` v0.7.x (MIT, Mario Zechner 2025 + Prime Intellect 2026),
> read from a real clone. Every `source:` below is a file:line that was actually read.
>
> Provenance marks: 🟢 verbatim from the source · 🟡 our inference · ⚠️ unverified.
> Per META-LOOP invariant I2, nothing marked ⚠️ may be built upon.
>
> Scope note (honest): this file covers the mechanisms we could verify directly.
> Delegated extraction of `packages/ai/src/providers/*` failed repeatedly on provider-side
> content filters (see the DELEGATION FAILURE note at the end), so provider-layer
> mechanisms are deliberately absent rather than guessed.

---

### M1 — Branch-version invalidation for background work
- **source**: `packages/coding-agent/src/core/agent-session.ts:2556`, `:2569`
- **what**: A plan computed in the background re-checks `branchVersion !== this._autoRefineBranchVersion`
  both after review and after planning. If the version moved, the result is downgraded to
  `invalidated` instead of returning a plan.
- **why it is strong**: A plan computed against one history must never apply to a mutated one.
  Naive async self-improvement silently applies stale conclusions to state that moved underneath it.
- **transfer note**: **LANDED** — `system/self_improvement.measurement_version()` +
  `is_proposal_stale()`; proposals are stamped in `agents/systems_layer.propose_node`.
  Our evidence is a value object, not an append-only history, so the honest analogue is a
  content hash of the signal fields rather than a monotonic counter. Fails safe: an unstamped
  proposal reads as STALE, never fresh.

### M2 — Serialized plan result as a discriminated union
- **source**: `agent-session.ts:519`, `:2543`
- **what**: `SerializedBackgroundPlanResult` is a four-way union — `plan` (carrying the exact
  `RefinementPlan`, its options, its `AbortController`, and `branchVersion`), `skip`,
  `invalidated`, `failure` (with an `explicit` flag so only user-initiated failures re-queue).
- **why it is strong**: Persisting the executable plan itself means the apply phase never
  re-plans. The union makes every terminal state explicit instead of overloading `None`
  to mean three different outcomes.
- **transfer note**: Our `control_proposals` are bare dicts with no terminal-state vocabulary.
  Adopting `skip`/`invalidated`/`failure` as first-class outcomes would let a human reading
  the board tell "nothing to do" from "was valid, no longer" from "broke".

### M3 — Tool-result-safe cut point with explicit split-turn handling
- **source**: `packages/coding-agent/src/core/compaction/compaction.ts:310-347`
  (`findValidCutPoints`), `:354-369` (`findTurnStartIndex`), `:402-458` (`findCutPoint`)
- **what**: `findValidCutPoints` collects indices of `user`/`assistant`/`bashExecution`/
  `custom`/`branchSummary`/`compactionSummary` messages and **explicitly excludes
  `toolResult`** (:326-327) — 🟢 "Never cut at tool results (they must follow their tool call)."
  `findCutPoint` walks backwards accumulating `estimateTokens` until `keepRecentTokens` is
  exceeded, then snaps to the closest valid cut point **at or after** that entry (:422-429).
  It then rewinds over non-message entries (settings/model changes) so they travel with the
  kept block, stopping at any message or compaction (:433-446). Finally, if the cut landed on
  a non-user message it sets `isSplitTurn` and records `turnStartIndex` (:448-457).
- **why it is strong**: Two distinct correctness properties. (1) Cutting at a `toolResult`
  orphans it from its tool call and most providers hard-error on that history. (2) Cutting at
  an *assistant* message is allowed precisely because its tool results follow and are kept —
  so the naive "only cut at user messages" rule is too strict and wastes budget.
- **transfer note**: **CORRECTED.** An earlier draft of this entry described the mechanism as
  "rewind the cut to the nearest turn start". That is wrong: it does NOT rewind the cut. It
  keeps the cut and *flags* the split, so `prepareCompaction` (:636-690) can summarise the
  split turn's prefix separately (`turnPrefixMessages`) from the older history
  (`messagesToSummarize`). Landed as `system/compaction_cut.py`.

### M4 — Compaction as a pure predicate
- **source**: `compaction.ts:229`
- **what**: `shouldCompact` returns true only when enabled and
  `contextTokens > contextWindow - reserveTokens`; a non-positive window disables it outright.
- **why it is strong**: The trigger decision is pure and testable without a model call.
- **transfer note**: Keep the trigger out of the node body so it can be tested in isolation —
  the same shape as our existing gate predicates.

### M5 — `CompactionReason` taxonomy
- **source**: `agent-session.ts:312`
- **what**: Four reasons — `manual`, `threshold`, `overflow`, `requested` — flow through the
  `compaction_start`/`compaction_end` events and select different downstream behaviour.
- **why it is strong**: Records *why* context was reduced, not just that it was. Recovery
  policy, retry, and telemetry all branch on this; a bare `compact()` loses it permanently.
- **transfer note**: Directly relevant to measurement discipline — a run compacted under
  `overflow` is not comparable to one compacted under `threshold`.

### M6 — Bounded overflow recovery (idle → attempted → reported)
- **source**: `agent-session.ts:7980`, `:8001`
- **what**: On a provider context-overflow error, `_overflowRecovery` walks a three-state
  machine: first hit strips the error from live state and compacts with `willRetry=true`;
  a second hit reports terminal failure instead of looping.
- **why it is strong**: "Compact and retry on overflow" is an infinite loop when compaction
  cannot free enough tokens. The bounded state machine is the fix.
- **transfer note**: Our sidecar retry counting (`SidecarResult.retries`) observes retries;
  it does not yet bound them. This is the shape to adopt when we do.

### M7 — Typed benign-failure signalling
- **source**: `agent-session.ts:400`, `:7105`; catch sites `:5837`, `:7051`, `:8191`
- **what**: `CompactionSkippedError` is a dedicated `Error` subclass thrown when there is
  genuinely nothing to compact; catch sites downgrade it to `errorSeverity: "warning"`.
- **why it is strong**: Distinguishes "no-op" from "broke" by exception *type* rather than
  string matching, so a harmless skip does not surface as a failure.
- **transfer note**: We use `HarnessError` for genuine faults. A separate benign class would
  stop no-op refinements from polluting the failure signal our measurements read.

### M8 — Snapshot-per-change child tracking
- **source**: `agent-session.ts:286`, `:279`, `:281`
- **what**: `RlmChildAgentSnapshot` is an immutable flat value object (id, `parentId`, model,
  label, status, `durationMs`, `toolUseCount`, `tokenCount`, `recap`, `answerPreview`, `error`)
  re-emitted whole on every change. Status (`queued/running/done/error/cancelled`) and
  `activity` (`waiting/writing/executing` + `toolName`) are two orthogonal axes, not one enum.
- **why it is strong**: Whole snapshots make late-attaching observers correct with zero replay
  logic; `parentId` on a flat record reconstructs an N-deep tree client-side. Collapsing
  lifecycle and activity into a single status field is the usual mistake.
- **transfer note**: Maps onto our per-agent observability. Two axes: one drives orchestration
  decisions, the other drives display.

### M9 — Transparent nested event forwarding
- **source**: `agent-session.ts:9744`
- **what**: The parent subscribes to each child; a nested `rlm_child_update` is re-emitted
  *verbatim*, while `agent_start`/`agent_end`/`message_end` fold into the parent's own snapshot.
- **why it is strong**: Grandchildren surface at the root without per-level rewrapping, so
  arbitrarily deep orchestration renders off one flat stream.
- **transfer note**: Directly portable to nested LangGraph subgraph event propagation.

### M10 — Registration-time race guard for spawned children
- **source**: `agent-session.ts:9425`
- **what**: Before registering a child, it re-checks deleting/deleted sets, the runtime host's
  veto, and `_disposed`/`_disposing`; a runtime that finished starting after a delete is
  disposed rather than registered.
- **why it is strong**: Async spawn always races cancellation. A pre-spawn check is not enough —
  the check must happen at registration time or a cancelled child leaks a live runtime.
- **transfer note**: Applies to our sidecar spawn path, where the process can outlive the
  graph node that requested it.

### M11 — Injectable self-critique seam
- **source**: `agent-session.ts:538`, `:7545`, `:506`
- **what**: `AutoRefineReviewer` is a pluggable `(request, signal) => Promise<AutoRefineReview>`;
  the default falls back to a model call. `AutoRefineReviewRequest` is deliberately tiny —
  `reason` plus `turnsSinceLastReview` — so the reviewer pulls what it needs itself.
- **why it is strong**: Tests pass a deterministic stub; another process can own review; the
  default still works. A hardcoded LLM call in the loop is untestable.
- **transfer note**: Our `distill_opus5` is closer to a hardcoded call than a seam. Making it
  an interface would let the loop be tested without a live provider — which is exactly what
  bit us when delegation failed on provider errors.

### M12 — Two-tier merged memory
- **source**: `agent-session.ts:7567`
- **what**: Review input is global harness state overlaid with session-local state
  (`mergeHarnessStates`), plus global + session refinement history.
- **why it is strong**: A single flat memory store cannot express "learned globally,
  overridden here".
- **transfer note**: Our `ContinualHarness` has a `scope` field (`local`/`global`) but a single
  backing store — the label exists, the two-tier merge does not. A real gap, deliberately
  recorded rather than papered over.

### M13 — Session JSONL tree v3 (id/parentId)
- **source**: `packages/coding-agent/docs/session-format.md:3`, `:178`, `:190`, `:330`
- **what**: 🟢 "Session entries form a tree structure via `id`/`parentId` fields, enabling
  in-place branching without creating new files." First entry has `parentId: null`; entry types
  include `message`, `compaction`, `branch_summary`, `custom`, `custom_message`, `label`,
  `model_change`, `session_info`.
- **why it is strong**: Branching without file duplication, and every durable reference is an
  **id, not an index** — indices break under any history rewrite.
- **transfer note**: Our `distillation_ledger.jsonl` is a flat append-only log with no parent
  links, so it cannot express a branch or a replay. This is the schema to adopt (TODO.md E4).

### M14 — `buildSessionContext()` leaf-to-root walk
- **source**: `session-format.md:343-353`
- **what**: Walks from the current leaf to the root; on hitting a `CompactionEntry` it emits
  the summary first, then messages from `firstKeptEntryId` to the compaction, then messages
  after it. 🟢 "Bookkeeping entries such as child usage attribution, session lifecycle, agent
  status, and git state are ignored when building model context."
- **why it is strong**: The bookkeeping/context split is what keeps operational metadata out
  of the model's window while remaining fully auditable on disk.
- **transfer note**: Gives us a principled answer to "what belongs in context vs what is only
  for the audit trail" — a question our ledger currently does not ask.

### M15 — Compaction summary chaining by stable id
- **source**: `compaction.ts:644-673`; `session-format.md:238`
- **what**: Kept: everything from `firstKeptEntryId` forward, plus the prior compaction's
  `summary` carried as `previousSummary`. Dropped entries are replaced by a generated summary.
  The compaction entry records `firstKeptEntryId` and `tokensBefore`.
- **why it is strong**: The summary-of-summaries chain makes long sessions survivable, and
  storing a stable entry id (not an index) survives history rewrites.
- **transfer note**: `tokensBefore` on the entry is what makes compaction cost measurable
  after the fact — worth copying for our own budgeting.

### M16 — Agent-to-agent delivery modes
- **source**: `docs/long-running-agents.md:106-110`, `:150`
- **what**: 🟢 "`auto`: steer a busy target and deliver immediately to an idle target;
  `steer`: intentionally inject the message into active work" and `follow_up` waits for the
  current turn. A receipt is `delivered` when it reached an idle target's context or `queued`
  when accepted for later delivery.
- **why it is strong**: Encodes *when* a message reaches a busy peer. A single `send()` either
  interrupts everything or is silently queued; both are wrong some of the time.
- **transfer note**: Maps onto `agents/topology_assembler.py` edges (TODO.md E3). The receipt
  distinction (`delivered` vs `queued`) is what makes delivery observable rather than assumed.

### M17 — Due-tick claim before delivery
- **source**: `long-running-agents.md:170`
- **what**: 🟢 "Due ticks are claimed before delivery so a crash does not replay an uncertain
  prompt, and missed ticks are coalesced rather than accumulated into an unbounded backlog."
- **why it is strong**: Two distinct failure modes solved at once — crash-replay duplication,
  and backlog explosion after downtime.
- **transfer note**: Any scheduled/recurring node we add must claim-then-deliver, and coalesce
  missed ticks. Directly applicable to our cron-driven measurement cycles.

### M18 — Strict JSONL framing with an explicit anti-pattern
- **source**: `docs/rpc.md:29-37`
- **what**: 🟢 "RPC mode uses strict JSONL semantics with LF (`\n`) as the only record
  delimiter... Do not use generic line readers that treat Unicode separators as newlines."
  Explicitly: 🟢 "Node `readline` is not protocol-compliant for RPC mode because it also splits
  on `U+2028` and `U+2029`, which are valid inside JSON strings."
- **why it is strong**: Names the exact library that silently corrupts the protocol. A spec
  that documents its own footgun prevents a whole class of intermittent parse failures.
- **transfer note**: **VERIFIED** — Python file iteration splits on `\n` only, so our
  transport is compliant; `tests/test_prime_agent_adapter_protocol.py` pins this with a
  payload containing U+2028/U+2029.

### M19 — Command responses are separate from events
- **source**: `rpc.md:19-25`, `:1225-1247`
- **what**: Commands get `{"type":"response","command":...,"success":bool,"error":...}`;
  agent activity streams as separate typed events. Parse errors also return a `response`.
- **why it is strong**: A rejected command is answered immediately on a distinct channel, so a
  client never waits on an event stream for a command that was refused.
- **transfer note**: **LANDED** — our adapter previously ignored `response` frames entirely
  and would block forever on a rejected prompt. Now handled as `HUMAN_CHECKPOINT`.

### M20 — Health events are first-class protocol members
- **source**: `rpc.md:789-808`, `:988-1018`, `:1020-1031`
- **what**: The event list includes `auto_retry_start`/`auto_retry_end` (after a transient
  error), `compaction_start`/`compaction_end`, and `extension_error` alongside normal
  lifecycle events.
- **why it is strong**: Retries and compactions are INFRA facts. A protocol that hides them
  makes every consumer conflate "worked cleanly" with "worked after three retries" —
  which corrupts any capability measurement built on those runs.
- **transfer note**: **LANDED** — `SidecarResult.errors/retries/compactions`, surfaced into
  graph state as `prime_agent_health` so a measurement node can separate infra from capability.

### M21 — Ordered async teardown
- **source**: `agent-session.ts:3770`, `:3925`
- **what**: `disposeAsync()` awaits child `disposeAsync` (flushing kernel snapshots), then runs
  every child unsubscribe, then disposes child sessions, then the sync teardown. Concurrent
  callers await one shared in-flight promise.
- **why it is strong**: Sync-only cleanup races process exit and loses persisted state; a
  non-idempotent dispose double-frees under concurrent shutdown.
- **transfer note**: Our sidecar `close()` terminates and waits, but the graph has no ordered
  teardown for nested work. Relevant when the sidecar spawns children of its own.

### M22 — Closure-returning subscribe
- **source**: `agent-session.ts:3729`, `:1487`
- **what**: `subscribe()` pushes the listener and returns a closure that splices out *that
  identity*. `_emit` wraps each listener call in its own `try/catch` so one throwing observer
  cannot starve the rest.
- **why it is strong**: Callers cannot accidentally unsubscribe a peer's handler, and a bad
  observer cannot kill the run.
- **transfer note**: 🟡 Note the tradeoff: this code *silently* discards listener exceptions.
  We should isolate per-listener but LOG the swallow — silent catch violates our Law 3.

### M23 — Pause upstream without disturbing observers
- **source**: `agent-session.ts:1353`, `:3746`, `:3757`
- **what**: One upstream subscription handle is held in `_unsubscribeAgent`; internal ops drop
  and re-add it while *user* listeners stay registered.
- **why it is strong**: Lets the session pause event ingestion, mutate state, and resume
  without tearing down the client-facing stream.
- **transfer note**: 🟡 The enabling pattern for safe mid-run graph mutation. Nothing in
  LangGraph provides this directly.

### M24 — Single-claimant plan consumption
- **source**: `agent-session.ts:2420`, `:2458`, `:7583`
- **what**: `_consumeSerializedBackgroundPlan` installs a claim promise; a concurrent caller
  awaits the holder's *entire* processing callback rather than resuming when planning merely
  settles. The claim clears in `finally` only if still self. Slow planning runs off the
  critical path; only the fast apply phase blocks.
- **why it is strong**: Prevents double-apply when two turn boundaries hit simultaneously.
  The subtlety worth copying: wait on full processing, not on the underlying future.
- **transfer note**: Split slow inference from fast mutation so self-improvement costs no turn
  latency while staying atomic where it must be.

### M25 — Failure classification by cause, text before status
- **source**: `packages/ai/src/utils/stream-failure.ts:66-88`
- **what**: `classifyStreamFailure(providerErrorType, status)` returns one of nine
  `StreamFailureKind` values. Branch ORDER is load-bearing: `refusal` (:68), then a
  `/sensitive|safety|prohibited_content|blocklist|spii|recitation|content.?filter|guardrail|flagged/`
  test (:69) — **before** any status check — then `overloaded`/529, `rate_limit`/429, `auth`,
  `invalid_request`/400/404, `malformed_response`, and only last `server_error`/>=500 (:79-86).
- **why it is strong**: A safety refusal often arrives wearing a 5xx status. Checking status
  first classifies it as a transient server error, so the caller retries a request that can
  never succeed. Text-before-status is what separates "will never work" from "try again".
- **transfer note**: **CORRECTED OUR OWN RECORD.** Our five failed digest delegations returned
  `HTTP 500: sensitive words detected` / `HTTP 400 content-blocked`, and we logged them as
  transient infra. Under this taxonomy they are `safety` and `invalid_request` — **non-retryable**.
  Landed as `system/failure_taxonomy.py`.

### M26 — Provider-agnostic overflow detection with a negative-pattern guard
- **source**: `packages/ai/src/utils/overflow.ts:31-52` (OVERFLOW_PATTERNS),
  `:65-69` (NON_OVERFLOW_PATTERNS), `:117-149` (`isContextOverflow`)
- **what**: 21 regexes for real overflow strings across 16 providers, plus a
  NON_OVERFLOW list (`/^(Throttling error|Service unavailable):/i`, `/rate limit/i`,
  `/too many requests/i`) subtracted FIRST. Then three positive cases: error-pattern match;
  silent overflow (`stopReason==="stop"` but `input+cacheRead > contextWindow`); and
  length-stop overflow (`stopReason==="length"`, `output===0`, `input >= contextWindow*0.99`).
- **why it is strong**: 🟢 Their comment names the exact trap — Bedrock throttling reads
  `"ThrottlingException: Too many tokens"` which matches the `/too many tokens/i` overflow
  pattern. Without the negative guard, a rate-limit gets "fixed" by compacting context.
  Cases 2 and 3 catch providers that never error at all.
- **transfer note**: The three-case shape is the real lesson: an overflow is not always an
  error. Any budget logic reading only exceptions misses silent truncation entirely.

### M27 — Registry-based provider dispatch with an api-mismatch assertion
- **source**: `packages/ai/src/api-registry.ts:41-63`, `:66-77`; `packages/ai/src/stream.ts:17-31`
- **what**: `registerApiProvider` stores providers in a `Map` keyed by `api`, wrapping each in
  `wrapStream`/`wrapStreamSimple` which throw `Mismatched api: ${model.api} expected ${api}`
  when a model is routed to the wrong provider. `stream()` is a 31-line dispatcher.
  `sourceId` enables `unregisterApiProviders(sourceId)` for clean plugin teardown.
- **why it is strong**: The wrapper turns a silent mis-route into an immediate loud error, and
  `sourceId` scoping means an extension can be unloaded without corrupting the registry.
- **transfer note**: Matches our model-routing needs; the mismatch assertion is the part to
  copy, since a mis-routed model otherwise fails deep inside a provider with a confusing error.

### M28 — Unpaired-surrogate sanitisation
- **source**: `packages/ai/src/utils/sanitize-unicode.ts:21-25`
- **what**: Strips lone high/low surrogates via
  `/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g`,
  deliberately preserving correctly paired ones (emoji survive).
- **why it is strong**: 🟢 "Unpaired surrogates ... cause JSON serialization errors in many API
  providers." Truncating text at a character boundary can split a surrogate pair and poison the
  next request — a bug that looks random and is very hard to trace.
- **transfer note**: Any Python truncation of tool output must not split a surrogate pair.
  Relevant wherever we slice model-bound strings by length.

### M29 — Structured diagnostics persisted next to the message
- **source**: `stream-failure.ts:196-227` (`recordStreamFailure`), `:31-39` (`StreamFailureError`)
- **what**: On a terminal failure it appends a `provider_stream_failure` diagnostic
  (timestamp, extracted error, full `info`) onto the message so it persists to session JSONL,
  and emits one structured log line with `kind`/`providerErrorType`/`status`/`requestId`.
  `truncateRawPayload` caps the raw body at 2000 chars. No-ops for user aborts.
- **why it is strong**: The user-facing message stays short while the forensic detail survives
  on disk, keyed by `requestId`. Post-mortems otherwise depend on logs that were never kept.
- **transfer note**: Our ledger should carry the provider `requestId` for every failed agent
  call — without it, a failure cannot be traced back to the provider's own record.

---

## Rejected on purpose

| mechanism | why rejected |
|---|---|
| IPython-as-universal-tool (RLM) | Weak at enforcing permission boundaries; our READ/WRITE/NEVER/HUMAN_CHECKPOINT is architectural, not prompt-level. 🟢 Their own docs state the kernel is **not** a sandbox. |
| pi-mono / TUI stack | Product-shape specific; we are Python and have no terminal UI. |
| Kernel-as-sandbox assumption | Explicitly disclaimed by the source; untrusted code needs real isolation. |

## DELEGATION FAILURE — recorded, and it taught us something

Five delegated digest tasks died on provider-side errors, never on the work itself:
`HTTP 400 content-blocked`, `HTTP 500 sensitive words detected` (three times, all targeting
`packages/ai/src/providers/*`), `HTTP 504 Gateway Time-out`.

We first recorded these as transient INFRA failures. **That classification was wrong**, and
M25 — extracted from this very area — is what proved it: upstream checks error TEXT before
status precisely because refusals arrive wearing 5xx. Under that taxonomy, four of the five
were `safety`/`invalid_request` — **non-retryable**. Only the 504 was genuinely transient.
The decision to stop retrying was right; the reason recorded for it was not. Corrected in
`docs/reconciliation/distillation_ledger.jsonl`.

The area was then digested directly with targeted greps rather than delegation, which is why
M25–M29 exist. Nothing here was inferred from a filename.

The inventory is now complete: 302/302 rows carry a description and a verdict, and the L1
gate reports PASS at 100%. Distribution: 75 adopt, 104 adapt, 109 reject, 14 n/a.

Grounding audit of that 100% (because a gate turning green is when to distrust it):
every one of the 302 rows resolves to a real file on disk with an exact line-count match,
zero rows kept an `Exports:` placeholder, and the 7 rows still marked UNREAD are all
`n/a` CHANGELOGs and package READMEs that state their own reason. No `adopt`/`adapt`
verdict rests on an unread file.

## M30 — Lease as compare-and-swap, not as a flag

`packages/coding-agent/src/core/session-lease.ts`

Single-writer admission is won by `mkdirSync` of a candidate directory then `renameSync`
onto the real lease path (`:258-263`) — an atomic compare-and-swap, so two racing openers
cannot both believe they hold it. Reclamation is the same primitive in reverse: a stale
lease is `renameSync`d aside to `${directory}.stale-${pid}-${uuid}` and only then removed
(`:219-228`), so a crash mid-reclaim leaves an orphan directory rather than a half-deleted
lease. Cleanup is explicitly best-effort with the next process reclaiming (`:58`).

Why it transfers: this is filesystem semantics, not TypeScript. Our shared result files
already use lock + atomic write; this extends the same discipline to *ownership* rather
than just content.

## M31 — Exactly-once commands via a three-state journal

`packages/coding-agent/src/modes/daemon/command-recovery-journal.ts`

`begin()` returns one of three states — `new`, `pending`, or `complete` carrying the
stored `response` (`:37-40`, `:73-88`). A replayed command therefore *replays its recorded
response* instead of re-executing, and recording a result before receipt is a hard error
rather than a silent insert (`:95`).

Why it matters here: the same shape as the silent-collision bug this cycle found in our own
`continual_harness.py`, where a duplicate id became a silent update. This mechanism is the
general fix — make the duplicate case an explicit, named state instead of an overwrite.
