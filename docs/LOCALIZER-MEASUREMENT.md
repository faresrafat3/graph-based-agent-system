# Localizer Measurement Study

**Date:** 2026-08-07
**Question:** the SWE-bench arms were capped by file localization, not by patch quality.
Is that cap a *scoring* problem (fixable) or an *information* problem (not)?
**Instrument:** `benchmarks/localizer_recall.py` — paired arms over the same 336
SWE-bench Verified instances (4 repos), same worktree, same `top_k`. Zero LLM calls,
~9 min per full run, so every claim below is a re-runnable measurement, not an estimate.

## Result

| arm | hit@1 | hit@3 | hit@10 | MRR |
|---|---|---|---|---|
| flat (lexical, pre-existing) | 47.02% | 69.64% | 83.63% | 0.5926 |
| graph (staged, this study) | 47.02% | 69.35% | **88.39%** | 0.6049 |
| **ensemble (shipped)** | 46.73% | **73.51%** | **90.18%** | **0.6183** |

**Shipped change: hit@3 69.64% → 73.51% (+3.87pp), McNemar exact p=0.029 — significant.**
This is the project's first localization improvement with a p-value attached.

## How the diagnosis was reached

Failures were partitioned before anything was built:

| condition | hit@3 |
|---|---|
| gold filename appears in the problem text | **67.5%** |
| ranking failure (gold retrieved, ranked too low) | 40.4% |
| retrieval failure (gold never retrieved) | **14.5%** |

Problem-statement length had no effect (68.8% long vs 70.0% short). So the cap was not
missing information — it was a **lexical gap**: issues are written in behavioural language
(`aggregate`, `deletion`, `timeseries`) while the fix lives in `core.py` or `base.py`.
Of 102 sampled failures, **51 contained an exploitable symbol signal** — a ceiling of
~84.8% hit@3 reachable without any model call.

## What the two arms actually showed

The staged graph — `retrieve → rerank → verify`, each stage one responsibility, mirroring
the rest of the system rather than the previous single 60-line function — did **not** beat
the flat scorer at k=3 (69.35% vs 69.64%, p=1.0). Taking that at face value would have
been the wrong conclusion. The informative number was the disagreement:

```
both arms correct : 57.44%
discordant        : 81 / 336   (40 solved only by graph, 41 only by flat)
UNION ceiling     : 81.55%     (+11.9pp over either arm alone)
```

Two rankers scoring the same while disagreeing on a quarter of instances is the signature
of **complementary evidence**, not of one ranker being better. Lexical mass and symbol
definitions fail on *different* issues. So the lever was never "write a smarter single
scorer" — both attempts land at ~69.5%. It was to run distinct rankers and merge them.
Plain round-robin interleaving, no oracle, no extra cost beyond running both, captures
+3.87pp of that 11.9pp headroom.

## A prior that measurement removed

The graph's first version penalised generic filenames (`utils.py`, `base.py`) on the
assumption that they are rarely the fix site. That was an assumption, not a finding.
Measured: **11.2% of gold files have generic names** (`base.py` alone appears 20 times).
The penalty was demoting the correct answer in roughly one of every nine instances. It was
removed, which lifted graph hit@10 to 88.39% and MRR to 0.6049. `tests/test_localizer_graph.py`
now asserts the *absence* of that penalty, so it cannot be reintroduced silently.

## Standing headroom

- **union → 81.55%** — 8.0pp still unclaimed by the naive merge; needs a learned combiner
  (which would cost training data and the current zero-LLM auditability).
- **symbol-signal ceiling → ~84.8%** — reachable with better symbol extraction alone.
- **retrieval failures (14.5% hit@3)** — the hard residue; the gold file is never surfaced,
  so no reranker can recover it.

## Bearing on the architectural thesis

This is the cleanest evidence so far that decomposition extracts capability at fixed model
strength, because it is measured with **no model in the loop at all**. The single-scorer
rewrite tied; combining *differing* rankers moved the number with p=0.029. The gain came
from topology, not from a stronger component — the same claim the SWE-bench applicability
result makes, here at zero cost and with statistical power.

## Reproducing

```bash
.venv/bin/python benchmarks/localizer_recall.py --arms flat,graph      # the tie + disagreement
.venv/bin/python benchmarks/localizer_recall.py --arms flat,ensemble   # the shipped +3.87pp
```

Artifacts: `benchmarks/results/localizer_ab.json`, `localizer_ab_v2.json`,
`localizer_ensemble.json`. The ensemble is wired into `swebench_harness.process_instance`,
so all arms (agent / alphacode / loop) inherit it.
