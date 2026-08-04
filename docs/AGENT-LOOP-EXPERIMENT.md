# Experiment: Agent-Level Feedback Loop on SWE-bench (the step before the graph)

**Date:** 2026-08-04
**Author:** Fares (with Hermes Agent)
**Context:** graph-based-agent-system SWE-bench Verified harness

---

## 0. The observation that started this

We measured the AlphaCode arm (best-of-N) on `psf/requests` (8 instances, Docker-graded):
**1/8 resolved (12.5%)** — same as the *worst* single-shot run (1/8), far below the *best*
single-shot run (4/8). We then opened the 5 unresolved patches and diagnosed them by hand.

### Hand diagnosis of the 5 unresolved instances

| Instance | Localizer | Patch applies? | What the model actually produced |
|---|---|---|---|
| 1724 | ✅ models.py | ✅ | Touched `self.method` but the unicode→native fix was incomplete |
| 1766 | ✅ auth.py | ✅ | Fixed `qop=auth`→`qop="auth"`, but other digest-auth paths still need quoting |
| 1921 | ✅ sessions.py | ✅ | **No-op**: identical line + doc-comment only |
| 2317 | ✅ sessions.py | ✅ | Fixed `builtin_str(method)`→`to_native_string(method)` (correct!) but other call sites need it too |
| 2931 | ✅ models.py | ✅ | Split `(str,bytes)` branch (correct direction!) but the fix is needed in another place too |

### The key finding

The model is **not incompetent**. It localizes the right file 100% of the time, writes a
patch that *applies*, and its first cut is usually pointed at the right symptom. What it
fails at is the **second/third step of a multi-step fix**: it stops at the first plausible
diff instead of completing every failing test.

This is exactly the failure mode a single agent hits when a task is "too big for one
agent." The system's whole thesis is: when one agent can't finish, decompose the task
into a graph of specialized agents with feedback edges — not one agent doing everything.

---

## 1. Hypothesis (to be tested empirically)

> **H:** The model can *reason about* the fix but cannot *execute* a multi-step fix alone.
> A tight test-feedback loop (run FAIL_TO_PASS → return failing test names → ask for a
> corrected diff) lets it complete fixes that single-shot generation misses.

If H holds → the ceiling is loop/graph depth, and the next lever is the multi-agent graph.
If H fails → the ceiling is raw model capability, and no loop/graph will help without a
stronger model.

---

## 2. The probe: `solve_agent_loop` (agent-level feedback loop)

Implemented in `benchmarks/swebench_harness.py` as a new `--mode loop` arm. It is the
**smallest possible step** toward the graph:

1. Generate patch via the governance path (same as `solve_agent`).
2. Fix apply failures (mechanical, bounded) — same as `solve_agent`.
3. **NEW:** run FAIL_TO_PASS locally (`run_tests_in_worktree`).
4. If not all green, return the *failing test names* to the model and ask for a COMPLETE
   corrected diff (not just the first symptom). Loop up to `max_refinements` (default 4).
5. Keep the best patch that applies; the loop bounds total rounds so it cannot spin.

Why this is the right *first* probe (not jumping straight to the graph):
- It isolates the single variable we care about: **does test-feedback help?**
- It reuses the existing local test executor (no new infra).
- It is cheap to run and measure.
- If it works, we *know* the graph is worth building (and we know what each agent's job
  is: the loop's "generate → test → diagnose → correct" is literally the graph's shape).

---

## 3. How to read the result

After Docker-grading the `--mode loop` predictions, compare:

| Arm | 1142 | 1724 | 1766 | 1921 | 2317 | 2931 | 5414 | 6028 | Resolved |
|---|---|---|---|---|---|---|---|---|---|
| single-shot (best) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ? | ? | 4/8 |
| alphacode (N=3) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✗ | ✗ | 1/8 |
| **loop (this exp)** | ? | ? | ? | ? | ? | ? | ? | ? | **TBD** |

If `loop` resolves any of {1724, 1766, 1921, 2317, 2931} that single-shot/alphacode missed
→ H confirmed → build the graph next.
If `loop` == single-shot on these → H rejected → the model needs to be swapped, not looped.

---

## 4. Philosophical note (why this matters beyond the number)

Karpathy's method: *small strong readable core, grow by accumulation not bloat.* The
feedback loop is the smallest accumulation that could break the ceiling — it does not
add agents, it adds *a second pass with signal*. If even that fails, we have learned
something honest about the model, not about our harness.

The graph (Diagnoser → Generator → Analyst → Refiner, wired by feedback edges) is the
natural generalization *only if* the loop shows signal. Building the graph first would
have been bloat — we would not have known which agent boundaries matter. The loop is the
empirical crucible; the graph is its scaled conclusion.

---

## 5. Status

- [x] `solve_agent_loop` implemented (`--mode loop`), wired into `process_instance` + CLI
- [x] `make test` green (281 passed)
- [ ] Run `--mode loop` on 8 requests instances (running)
- [ ] Docker-grade the loop predictions
- [ ] Record the table above with real numbers
- [ ] Decision: graph vs model-swap based on H's outcome
