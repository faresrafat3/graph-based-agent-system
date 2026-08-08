# Structural Verdict: what is real, what is scaffolding

**Date:** 2026-08-08
**Method:** AST import analysis + runtime counters + direct reading. No inference from names.
**Question asked by the architect:** rebuild from scratch, or continue?

---

## 0. The measured shape of the repo

| Quantity | Value |
|---|---|
| Python files (excl. venv) | 190 |
| Python LOC | 33,472 |
| Markdown files / lines | 88 / 16,239 |
| `agents/` files | 37 |
| Tests | 1184 passing |

Docs-to-code ≈ **1 : 2**. That alone is not damning. What follows is.

---

## 1. Only 7 of 37 "agents" ever talk to a model

Files under `agents/` that reference `call_llm` / `call_stepfun_native`:

`code_executor`, `debugger_agent`, `domain_squads`, `reflexion_agent`, `sampling_agent`,
`semantic_memory_agent`, `task_decomposer`.

The other **30 files (6,814 LOC)** contain no model call.

**This is not automatically wrong.** Reading them shows real, competent, deliberately
deterministic code — e.g. `quality_reviewer.py` is an honest rule-based approval gate that
documents itself as "without LLM calls". A deterministic validator is a legitimate component.

The problem is the naming: calling 30 deterministic modules "agents" inflates the apparent
system. The registry advertises 28 agents; the population that can actually reason is 7.

**A hypothesis I tested and disproved:** that these were template-generated (many share a
`2 classes / 7 functions` shape). AST comparison found **no two files with an identical
function-name set**. They were written individually, not stamped out. Recorded because it
would have been an easy and wrong thing to assert.

---

## 2. The load-bearing finding: the kernel and the router are not connected

Real AST import analysis (not name matching):

| Module | Production importers | Test importers |
|---|---|---|
| `kernel/slice_router.py` | **0** | **0** |
| `kernel/dispatch_kernel.py` | **0** | 1 |
| `system/agent_registry.py` | 4 | 2 |
| `agents/karpathy_pipeline.py` | 4 | 1 |

`slice_router.py` — the file that decides which agents form a slice — **is imported by
nothing at all, not even a test.** `dispatch_kernel.py` — the dispatch kernel — is imported
only by its own test.

What `slice_router` contains is a dictionary of **name strings**:

```python
"default": {
    "description": "Default Ultimate Graph - full 22 agents",
    "agents": ["context_curator", "task_decomposer", "deterministic_validator", ...],
    "topology": "Ultimate: all layers, memory system included",
    "n_agents": 18,
}
```

Note also `"full 22 agents"` beside `"n_agents": 18` in the same literal — the description
and the count disagree, and nothing consumes either, so nothing ever caught it.

`system/agent_registry.py` is the same pattern: agents stored as `"module"` / `"entrypoint"`
strings, resolved only by `governance_checks.py` via `importlib` to confirm the symbols
*exist*. Existence checking, not execution.

**So the "graph" is a description of a graph, not a graph.**

---

## 3. Ten modules are tested but never imported by production

| Module | Imported by production? | Imported by tests? |
|---|---|---|
| `working_memory_agent` | NO | yes |
| `episodic_memory_agent` | NO | yes |
| `semantic_memory_agent` | NO | yes |
| `competitive_context_manager` | NO | yes |
| `competitive_slice` | NO | yes |
| `cynefin_classifier` | NO | yes |
| `decision_conflict_agent` | NO | yes |
| `human_escalation` | NO | yes |
| `intelligence_forge_demo` | NO | yes |
| `prime_agent_adapter` | NO | yes |

All three memory agents are here. **The tier whose entire purpose is carrying knowledge
forward is imported by nobody.**

This is why 1184 green tests were not evidence of health: a large share of them exercise code
that no execution path reaches. The suite measures that the parts *work*, never that they are
*plugged in*.

Summary of `agents/` (36 modules, excluding `__init__`):

| Category | Count |
|---|---|
| genuinely imported outside `agents/` | 14 |
| imported only by sibling agents | 12 |
| never imported by production (tests only) | 10 |

---

## 4. Verdict on "rebuild or continue"

**Neither extreme is supported by the evidence.**

Against a full rebuild — these are real and worth keeping:

- `llm/llm_integration.py` — now correct after D1/D2/D3, with a measured token budget, a real
  key pool, rate limiting, and fail-loud behavior.
- `benchmarks/swebench_harness.py` — a working SWE-bench harness with Docker grading; the
  grading defect is fixed.
- The deterministic components (`quality_reviewer`, `deterministic_validator`,
  `test_runner_agent`) are competent code.
- 1184 tests are a real safety net for whatever is kept.

Against continuing as-is — the core is not a system:

- The router and kernel are not wired to anything.
- Composition exists as string lists, so the "graph" was never executed as a graph.
- 10 modules are alive only in tests.
- Governance validates *existence*, which is why every accounting surface reported health
  while nothing flowed.

The honest description: **a large, well-tested parts bin with a missing assembly.** The
correct move is neither to discard the parts nor to defend the assembly — it is to build a
small real execution core and connect the parts to it one at a time, each connection
justified by a measurement.

---

## 5. Why this happened (relevant to preventing a repeat)

Every defect found today shared one shape: **an accounting surface that reports success
without execution.**

| Surface | What it certified | What it did not check |
|---|---|---|
| `agent_registry` | the module and symbol exist | that anything calls them |
| `governance_checks` | 28 items conform | that they run |
| test suite | components work in isolation | that they are reachable |
| `slice_router` | a topology is described | that the topology executes |
| harness grading (D1) | commands were "run" | that they were real commands |
| LLM client (D3) | a response was returned | that it contained an answer |

The system was optimised against its accounting layer rather than against execution. That is
the mechanism behind "we are not capturing the good reasoning": in D3 the reasoning was
literally produced and then read from the wrong field.

**Design rule for whatever comes next:** no component counts as present until an execution
trace shows it ran and changed an output. Registration, conformance, and green tests are
necessary but never sufficient.

---

## 6. What this does NOT claim

- Not a quality judgment on individual modules; several are well written.
- Static imports can miss dynamic dispatch. Confirmed here by runtime counters, which agreed:
  6/28 entrypoints fired on a default run, 14/28 with all optional flags.
- Does not prove that a rebuilt core would score better. That requires the re-run of the arms
  on the now-repaired harness, which has not been done yet.
