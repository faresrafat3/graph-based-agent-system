# META-LOOP — The Loop That Governs The Loops

> Version: v1 | Opened: 2026-08-08 | Owner: Hermes (autonomous mode ULTRA)
> Mandate: fully digest `PrimeIntellect-ai/prime-agent` (v0.7.x, 1134 files, ~370k LOC,
> TypeScript monorepo + `prime-agent-runtime` Python package) into
> `graph-based-agent-system` (177 Python files, LangGraph, Constitution + 20 Laws)
> **without forking a second authority and without leaving residue.**

Karpathy, verbatim (primary source, `karpathy-method-notes`):
> "one GPU, one file, one metric"

Here that becomes: **one loop, one artifact, one gate.**

---

## 0. Why a meta-loop at all

The previous digest attempt produced `docs/prime-agent-study.md`, `DECISIONS.md`,
`TODO.md` (12 epics) and 4 ADRs — then stalled. Measured state at the opening of this
meta-loop:

| Artifact | Claimed | Actually done |
|---|---|---|
| `TODO.md` epics E0–E12 | 12 epics, ~55 checkboxes | **4 checked** (E0.1, E0.2, M1 docs) |
| `docs/repository-inventory.md` | full inventory | 83 lines — covers <5% of 1134 files |
| `agents/prime_agent_adapter.py` | sidecar RPC node | 270 lines, **never executed against a real sidecar** |
| `system/continual_harness.py` | Continual Harness port | exists — fidelity vs `harness.py` unverified |

Root cause (honest): the work was **breadth-first documentation** with no closing gate.
Nothing forced a loop to finish before the next began. That is the residue the user
warned about — "أصغر حاجة هتبقي وحشة جدا في نهاية الطريق".

The meta-loop's single job: **make a loop uncloseable until its gate is green.**

---

## 1. Meta-loop invariants (non-negotiable)

| # | Invariant | Enforcement |
|---|---|---|
| I1 | **No loop closes without a passing gate.** | `scripts/meta_loop.py verify <loop>` returns rc≠0 → loop stays open |
| I2 | **Every claim carries evidence.** 🟢 verbatim (file:line) · 🟡 inference · ⚠️ unverified | grep for `⚠️` in digest docs; ⚠️ may not be built upon |
| I3 | **No fork of authority.** Ported layers EXTEND `CONSTITUTION.md`; never rewrite it. | `system/governance_checks.py` + test asserting CONSTITUTION.md sha stable |
| I4 | **No residue.** Every loop leaves the repo with `make test` green and no orphan files. | `make test` + orphan scan in the gate |
| I5 | **Port, don't reinvent.** Logic must trace to a prime-agent file:line. Names may differ. | Each ported module carries a `PORTED-FROM:` header |
| I6 | **MIT attribution preserved** on any transferred logic. | `NOTICE` file + per-module header |
| I7 | **Measure the apparatus before the system.** A harness fix ships only with its own test. | Rule from MEASUREMENT DISCIPLINE; benchmark arms compared vs STRONGEST baseline |
| I8 | **English in artifacts, Arabic only in chat.** | review before commit |

---

## 2. The loop-of-loops (control flow)

```
        ┌──────────────────────── META-LOOP ────────────────────────┐
        │                                                            │
        │   select_loop ──▶ plan_tasks ──▶ execute ──▶ GATE ──┐      │
        │        ▲                                     │      │      │
        │        │                              rc==0  │ rc≠0 │      │
        │        │                                     ▼      ▼      │
        │        └──── distill ◀── record_ledger ◀── close  reopen   │
        │                                              │             │
        └──────────────────────────────────────────────┼─────────────┘
                                                       ▼
                                          next loop (or DONE)
```

- `select_loop` — highest-priority open loop from §3.
- `plan_tasks` — expand into concrete tasks with per-task acceptance criteria.
- `execute` — do the work (read real files, write real code, run real tests).
- `GATE` — `scripts/meta_loop.py verify <loop>`; fail-closed.
- `record_ledger` — append to `docs/reconciliation/VERSION-LEDGER.md` + `system/distillation_ledger.jsonl`.
- `distill` — extract the reusable lesson; update skill/ADR if it generalizes.

**Escalation ladder inside `execute`** (self-escalating, no permission asked):
L1 observe → L2 auto-fix → L3 research (web/primary source) → L4 delegate to subagents.

---

## 3. The loops (goals, in dependency order)

### LOOP 1 — DIGEST  *(P0, gate: coverage ≥ 95% of files ≥100 LOC)*
**Goal:** every prime-agent file ≥100 LOC is read and summarized with its real
responsibility, its key mechanism, and a verdict (adopt / adapt / reject).
**Artifact:** `docs/digest/INVENTORY.md` (machine-generated skeleton, human/agent-filled)
+ `docs/digest/MECHANISMS.md` (the extracted mechanisms, with file:line).
**Gate:** `meta_loop.py verify L1` — asserts inventory row count ≥ 0.95 × (files ≥100 LOC)
and that every row has a non-empty `responsibility` and `verdict`.

### LOOP 2 — MAP  *(P0, gate: every mechanism mapped or explicitly rejected)*
**Goal:** a correspondence matrix: prime-agent mechanism ↔ our module ↔ gap ↔ action.
**Artifact:** `docs/digest/CORRESPONDENCE.md`.
**Gate:** every mechanism from `MECHANISMS.md` appears in the matrix with a
non-empty action; no `TBD`.

### LOOP 3 — PORT  *(P0, gate: tests RED→GREEN per port)*
**Goal:** transfer the adopted mechanisms as native Python inside the LangGraph graph.
Ordered by value: E2 harness fidelity → E4 trace tree → E3 A2A delivery modes →
E9 compaction/`transformContext` → E6 tool hooks → E7 unified provider + faux → E5 host bridge.
**Gate:** each ported module has a test that fails against the pre-port code and
passes after; `make test` green; `PORTED-FROM:` header present.

### LOOP 4 — SIDECAR  *(P1, gate: a real prime-agent process answers a real RPC frame)*
**Goal:** `agents/prime_agent_adapter.py` proven against the ACTUAL binary, not a fake
transport. Governed: sandbox cwd, NEVER-list enforced, process death → HUMAN_CHECKPOINT.
**Gate:** an integration test that spawns the real sidecar (skipped-with-reason if the
binary is absent, never silently passing).

### LOOP 5 — MEASURE  *(P1, gate: before/after on the SAME harness vs STRONGEST baseline)*
**Goal:** quantify what the digest bought us. Arms compared on identical apparatus.
**Gate:** a report separating INFRA failures from CAPABILITY failures (MEASUREMENT
DISCIPLINE rule); no arm compared against a weak baseline.

### LOOP 6 — GOVERN  *(P0, runs continuously alongside every loop)*
**Goal:** every change passes governance: Constitution untouched, ledger appended,
rollback possible.
**Gate:** `CONSTITUTION.md` sha unchanged since `v0`; version-ledger row exists per change.

---

## 4. Per-loop task template

Every task in every loop MUST carry:

```
TASK <loop>.<n> — <title>
  evidence:    <prime-agent file:line>  |  N/A (our-side work)
  acceptance:  <a single checkable statement>
  gate:        <the command that proves it>
  residue:     <what must be cleaned when done>
```

A task without an `acceptance` + `gate` is not a task; it is a wish.

---

## 5. Anti-residue policy (the user's hard requirement)

> "متعملش اي مخلفات او اضرار لان اصغر حاجه هتبقي وحشه جدا في نهايه الطريق"

Concretely enforced at every gate:
1. `make test` exit 0.
2. No new file outside a declared artifact path for that loop.
3. No `TODO`/`FIXME`/`XXX` introduced without a tracking row in `TODO.md`.
4. No temp/scratch files left in the repo (`/tmp` only; deleted explicitly).
5. `git status` clean of unintended files before the ledger row is written.
6. No dead code: anything added must be reachable from a test or an entrypoint.

---

## 6. Ledger & rollback

- `docs/reconciliation/VERSION-LEDGER.md` — one row per visible change: `| ver | date | file | change | verdict |`.
- `system/distillation_ledger.jsonl` — append-only; each distilled principle gets
  `ref/text/source/status/date`.
- Rollback unit = one ledger version. Any `vN` can be reverted without touching `vN-1`.

---

## 7. Definition of DONE for the whole mandate

All six loops closed with green gates, and:
- [ ] ≥95% of prime-agent files ≥100 LOC digested with a verdict.
- [ ] Every adopted mechanism ported with a RED→GREEN test.
- [ ] Sidecar proven against the real binary (or skipped with an explicit recorded reason).
- [ ] Before/after measurement on identical apparatus vs the strongest baseline.
- [ ] `CONSTITUTION.md` unchanged; all governance tests green.
- [ ] `make test` green; zero residue.
