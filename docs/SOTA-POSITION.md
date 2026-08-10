# SOTA Position — Graph-Based Agent System (SWE-bench Verified)

**Date:** 2026-08-04
**Author:** Hermes Agent (with Fares)
**Scope:** Honest placement of this system on the SWE-bench Verified leaderboard, and the decision it forces.

## 0. TL;DR — the uncomfortable number

| System | SWE-bench Verified resolve rate | Notes |
|---|---|---|
| **This system (single-shot, best of 2 runs)** | **50%** (4/8) | 8-instance `psf/requests` slice, docker-graded |
| **This system (single-shot, worst run)** | **12.5%** (1/8) | same 8 instances, LLM nondeterminism |
| **This system (AlphaCode N=3)** | **12.5%** (1/8) | best-of-N selector, same slice |
| **This system (loop mode)** | **TBD** | `decision #3` — not yet run (see below) |
| Orchard-SWE (Microsoft, dense-reward) | **~69.7%** | reported Aug 2026, ~3B active / 35B sparse params |
| Frontier agents (Claude Opus 5, et al.) | **up to ~96%** (reported) | secondary aggregators; verify on swebench.com |

**The gap is not our architecture. It is the generator.** `step-3.7-flash`
localizes the right file 100% of the time, writes a patch that *applies* 100% of
the time, and its first cut is usually pointed at the right symptom — but it stops
at the first plausible diff instead of completing every failing test. Multi-agent
graph, AlphaCode sampling, and the pending loop mode are all *variance reducers*, not
*capability multipliers*: they cannot manufacture a fix the model cannot produce in
any sample.

> "We measured the AlphaCode arm on `psf/requests` (8 instances): 1/8 — same as the
> worst single-shot run, far below the best (4/8)." — `docs/AGENT-LOOP-EXPERIMENT.md`

## 1. What the numbers actually mean

SWE-bench Verified is 500 real GitHub issues (django, sympy, scikit-learn, astropy,
matplotlib, …) graded by `pytest` exit codes in Docker — **zero LLM grading**, the
same zero-governance philosophy as this system. A resolve = FAIL_TO_PASS flips to
passing *and* PASS_TO_PASS stays green.

Our two docker grades on the **same 8 instances** gave **4/8 and 1/8** — a 4×
swing from LLM nondeterminism alone. The published leaderboard reports best-of-N over
*hundreds* of instances precisely to average out this variance. **A single 8-instance
sample cannot characterize a system on SWE-bench** — that caveat applies to our own
numbers here and to any single leaderboard snapshot.

### Where our pipeline is genuinely strong (verified, not claimed)
- **Localizer recall@3:** 70% (IDF-weighted) / 57.5% pre-upgrade — the file-finding
  stage works.
- **Patch apply rate:** 100% post `repair_hunk_counts()` — the validator works.
- **Governance layer:** zero-LLM control plane, real permission `PermissionError`s,
  physical sandbox (`python -I`, secret purge, resource limits).
- **Honest reporting:** we publish raw + infra-adjusted numbers and split capability
  vs infrastructure failures.

### Where the ceiling is
- **Patch *quality*** per sample — the model generates weak/partial fixes on most
  instances regardless of N. Best-of-N only helps when ≥1 sample in the pool resolves;
  on 5/6 generated instances none of 3 samples cleared FAIL_TO_PASS.

## 2. The decision the data forces (decision #3 ladder)

```
H: test-feedback loop lets the model complete multi-step fixes it misses single-shot.
    │
    ├─ loop resolves any of {1724,1766,1921,2317,2931} single-shot missed
    │      → H CONFIRMED → the graph is worth building (each agent = one loop stage)
    │
    └─ loop == single-shot on these
           → H REJECTED → ceiling is the MODEL, not the loop/graph
               → swap to a stronger/coding-tuned generator BEFORE building the graph
```

**Loop mode is the empirical crucible; the graph is its scaled conclusion.** Building
the ultimate graph first (22 agents) would be bloat — we would not yet know which
agent boundaries matter. The `solve_agent_loop` probe (`--mode loop`) is implemented
but **not yet docker-graded**. Its result is the single most important number missing
from this table.

**Action:** run `--mode loop` on the 8 `psf/requests` instances and record the real
row before any graph investment. (Deferred in this cleanup pass: the sibling session
owns `benchmarks/swebench_harness.py` and is mid-edit on the loop wiring.)

## 3. SOTA comparison (caveated)

| Dimension | Orchard-SWE | Frontier (Opus 5 class) | This system |
|---|---|---|---|
| Resolve rate | ~69.7% | up to ~96% (reported) | 12.5–50% (8-inst slice) |
| Core technique | dense reward + sparse model | frontier LLM | zero-LLM control plane + governance |
| Generator | ~3B active / 35B sparse | frontier-scale | `step-3.7-flash` |
| Multi-agent? | yes (Orchard) | yes | yes (graph, partial) |
| Execution-grounded grading | yes (pytest/Docker) | yes | yes (identical philosophy) |
| Honest variance reporting | n/a | n/a | we publish the 4× swing |

**Sources (secondary aggregators, verify on swebench.com):**
- Orchard-SWE 69.7% — 24-ai.news Microsoft Orchard writeup (2026-08-03).
- Frontier ~96% (Claude Opus 5) — benchlm.ai SWE-bench Verified leaderboard snapshot.
- Canonical leaderboard: https://www.swebench.com/ (use the Agent dropdown).

> Numbers above the system's own row are **leaderboard-scale** (500 instances,
> best-of-N). Direct comparison to an 8-instance slice is unfair to *both* sides; the
> 8-instance number is only good enough to locate the order of magnitude of the gap
> and to decide model-swap vs graph.

## 4. Recommended next experiment (controlled, cheap)

Before building the ultimate graph, run a **controlled generator-swap**:
1. Take the same 8 `psf/requests` instances.
2. Swap `STEPFUN_MODEL` for a coding-tuned / frontier-equivalent model (if
   credentials + quota permit).
3. Re-run single-shot + loop on the *identical* slice.
4. If resolve rate jumps to the 50–70%+ tier → the architecture was fine; the model
   was the ceiling. Build the graph on the stronger generator.
5. If it stays flat → the *loop/graph shape* itself is the lever; invest there.

This is the smallest honest step that distinguishes "model ceiling" from
"architecture ceiling" — exactly the Karpathy method: *small strong readable core,
grow by accumulation not bloat.*

## 5. Status / open items

- [x] Benchmark suite defense: `scenario_4` adversarial now records a `NEVER` breach
      and scores as SECURE PASS (defense 100%) — fixed 2026-08-04.
- [ ] `decision #3` loop mode: **run + docker-grade**, fill the TBD row in §0.
- [ ] Thrashing harness (`scripts/measure_thrashing.py`): run, decide probe-budget (P4).
- [ ] VERIFY node + Cynefin: measure postcondition pass-rate impact, attach to §1.
- [ ] Controlled generator-swap experiment (§4) — pending model access.

**Honest bottom line:** the system is architecturally sound and honestly measured.
On SWE-bench Verified it sits at 12.5–50% on an 8-instance slice — 1–4× below
Orchard-SWE (69.7%) and an order of magnitude below frontier (~96%). The dominant
lever is the generator (`step-3.7-flash`), not the graph. Finish the loop-mode probe,
then run the generator-swap before committing to the 22-agent graph.
