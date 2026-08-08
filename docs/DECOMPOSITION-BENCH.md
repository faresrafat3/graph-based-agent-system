# Decomposition Benchmark — First Run

**Suite:** `benchmarks/decomposition_bench.py` · **Fixtures:** 6, dependency-tiered (1–4)
**Arms:** `flat` (one LLM call: "list the steps") vs `graph` (`decompose_requirements`)
**Grading:** programmatic set/index arithmetic. No LLM judges anything.

---

## Why this suite exists

SWE-bench emits one end-to-end number. When an arm loses there, the result cannot say
*which* capability failed — localization, decomposition, repair, or transport. This suite
isolates one: given a compound request, does the system break it into the right units in
an order that respects their dependencies?

That matters here because the local SWE-bench run found the arms **statistically
indistinguishable** (10/21 vs 11/21, McNemar p=1.0). A null result on a composite metric
is not evidence that decomposition is worthless — it is evidence that the metric cannot
see it. So decomposition gets measured directly.

---

## Result

| metric | flat | graph |
|---|---|---|
| coverage | 0.979 | **1.000** |
| order accuracy | **0.850** | 0.678 |
| separation | **0.722** | 0.611 |
| granularity | 0.293 | **0.641** |
| **composite** | 0.711 | **0.733** |

Per fixture (composite):

| tier | fixture | flat | graph | Δ |
|---|---|---|---|---|
| 1 | csv-etl | 0.750 | 0.667 | −0.083 |
| 1 | single-unit-control | 0.750 | 0.750 | 0.000 |
| 2 | auth-service | 0.625 | **0.833** | **+0.208** |
| 2 | flaky-test-triage | 0.713 | 0.637 | −0.076 |
| 3 | rate-limited-api | 0.592 | **0.783** | **+0.191** |
| 4 | migration-zero-downtime | **0.838** | 0.725 | −0.113 |

**Mean delta +0.021 — graph wins 2, loses 3, ties 1.** At n=6 fixtures this is a wash,
not a win. The interesting content is in the per-metric split, not the headline.

---

## What the split actually says

The two arms fail in **opposite** directions, which a composite average hides:

- **graph** has perfect coverage (1.000) and more than double the granularity
  (0.293 → 0.641). It finds every required unit and sizes them sensibly.
- **flat** is markedly better at ordering (0.850 vs 0.678) and separation (0.722 vs 0.611).
  It sequences fewer, coarser steps more reliably.

So the governed decomposer's weakness is **not** "it misses work" — it is **sequencing**.
That is a concrete, addressable defect in the graph's dependency edges, and it is exactly
the kind of finding a single resolve-rate number cannot produce.

`flat`'s granularity of 0.293 is the mirror image: it routinely dumps a compound task into
too few units. On `single-unit-control` (an atomic bug fix) both arms score 1.0, so
neither over-decomposes a task that needs no structure.

---

## A scorer bug this run exposed

The first pass scored `graph` at 0.492 order accuracy, with the tier-4 migration plan at
**0.2** — apparently catastrophic. Inspecting the plan showed it was *correct*:

```
 4. Create a backfill process that updates rows in small batches
 5. Update application to write to BOTH old and new columns
 7. Run the batch backfill to populate first_name/last_name
```

"Create the backfill process" (prepare) legitimately precedes dual-write; "run the
backfill" (execute) follows it. The scorer compared **first occurrence vs first
occurrence**, so it read a sound plan as an inversion.

Fixed to compare the prerequisite's first occurrence against the dependent's **last**
occurrence — the constraint being tested is "the prerequisite starts before the dependent
finishes", not "no keyword ever reappears". Rescoring lifted **both** arms
(flat 0.628 → 0.711, graph 0.686 → 0.733), confirming it was a measurement defect and not
a bias toward either side. Pinned by two tests, including one asserting a genuine
inversion still fails.

This is the fifth measurement bug found this session. Every one of them distorted results
before any conclusion was drawn from them — which is the argument for testing the
instrument before trusting its output.

---

## Limits

- **n=6 fixtures, 1 repeat.** No significance testing is possible or claimed. Treat the
  per-metric split as a hypothesis generator, not a verdict.
- Fixtures are hand-built by the same author as the system. Keyword-based concept matching
  tolerates paraphrase but cannot judge semantic correctness.
- `granularity` penalises deviation from a hand-set expected unit count — a judgement call,
  not ground truth.

## Reproducing

```bash
PYTHONPATH= ./.venv/bin/python benchmarks/decomposition_bench.py --arms flat,graph --repeats 1
PYTHONPATH= ./.venv/bin/python -m pytest tests/test_decomposition_bench.py -q   # 26 tests
```
