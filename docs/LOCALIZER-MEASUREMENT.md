# Localizer Measurement — n=336, Zero LLM

**Date:** 2026-08-07
**Instrument:** `benchmarks/localizer_recall.py` (this run: `benchmarks/results/localizer_recall.json`)
**Scope:** 336 SWE-bench Verified instances across the 4 locally-cloned repos
**Infrastructure failures:** 0

---

## Why this measurement exists

`docs/SWEBENCH-REPORT.md` names localization as the ceiling on resolve rate: at ~70%
recall@3, roughly 30% of instances point the generator at the wrong file, and no amount
of patch quality recovers from that. But that figure came from a **40-instance** sample
(95% CI ≈ ±14pp) and was only ever produced as a by-product of full generation runs —
expensive, LLM-bound, network-bound.

`localize()` is pure lexical scoring with **no model call**, so its accuracy can be
measured directly and offline. This run does exactly that: 336 instances, 8× the prior
sample, at zero token cost.

---

## Headline

| Metric | k=1 | k=3 | k=5 | k=10 |
|---|---|---|---|---|
| **hit@k** (≥1 gold file found) | 46.73% | **69.64%** | 77.68% | 83.63% |
| 95% CI | 41.5–52.1 | **64.5–74.3** | 72.9–81.8 | 79.3–87.2 |
| **recall@k** (fraction of gold set) | 42.31% | 65.35% | 73.16% | 80.23% |
| **precision@k** | 46.73% | 24.11% | 16.37% | 9.20% |

**MRR: 0.593**

**The documented 70% recall@3 is confirmed** — 69.64% at n=336, and the old 40-instance
estimate sat inside the new CI. The number was right. What it was hiding is below.

---

## Finding 1 — "recall" and "hit" were conflated, and they are not the same

Prior reports quoted a single "recall@3 = 70%". Two different quantities were being
collapsed:

- **hit@3 = 69.64%** — at least one gold file appears in the top 3
- **recall@3 = 65.35%** — the *fraction of the gold set* found

They coincide on single-file fixes and diverge on multi-file ones:

| gold files | n | recall@3 | hit@3 |
|---|---|---|---|
| single | 293 | 68.94% | 68.94% |
| **multi** | **43** | **40.89%** | **74.42%** |

On multi-file instances the localizer usually finds *a* gold file (74%) but only ~41% of
the gold set. Since a patch must edit every gold file to resolve, hit@3 **overstates**
readiness on precisely the 12.8% of instances that are hardest. Both numbers are now
reported separately.

---

## Finding 2 — the 30% failure is two different problems, not one

This is the actionable result. Of the 102 instances that miss at k=3:

| failure mode | n | % of misses | what it means |
|---|---|---|---|
| **ranking** — gold is in top-10, ranked 4–10 | **47** | 46% | retrieval already found it; the scorer ordered it wrong |
| **retrieval** — gold absent from top-10 | **55** | 54% | the lexical scorer never surfaced it at all |

These need opposite fixes. Treating the 30% as one undifferentiated ceiling is why
"improve the localizer" never had a concrete next step.

### Oracle ceiling: what perfect re-ranking alone would buy

Holding retrieval fixed and assuming ideal ordering *within the candidates already
returned*:

```
current hit@3                    69.64%
oracle re-rank of top-5  -> hit@3 77.68%   (+8.0pp)
oracle re-rank of top-10 -> hit@3 83.63%   (+14.0pp)
```

**+14pp is available without improving retrieval at all.** That is a hard upper bound
on the re-ranking lever, measured rather than guessed.

The re-rankable cases are spread evenly across repos, so this is a property of the
scorer, not of one codebase:

| repo | re-rankable | of n | rate |
|---|---|---|---|
| django/django | 32 | 231 | 13.9% |
| sympy/sympy | 12 | 75 | 16.0% |
| psf/requests | 1 | 8 | 12.5% |
| astropy/astropy | 2 | 22 | 9.1% |

---

## Finding 3 — raising `top_k` is not the cheap alternative

The obvious shortcut is to pass more files to the generator. The precision column prices
that:

| k | precision | context cost per gold file found |
|---|---|---|
| 3 | 24.11% | ~4× |
| 5 | 16.37% | ~6× |
| 10 | 9.20% | ~11× |

Going 3→10 buys the same +14pp as perfect re-ranking, but at **11× the context per gold
file** — more distractor code in the prompt on every instance, including the 70% that
were already correct. Re-ranking gets the same ceiling without the dilution.

---

## Per-repo and per-difficulty

| repo | n | hit@3 | MRR |
|---|---|---|---|
| psf/requests | 8 | 87.50% | 0.688 |
| astropy/astropy | 22 | 81.82% | 0.695 |
| django/django | 231 | 69.70% | 0.593 |
| sympy/sympy | 75 | 64.00% | 0.555 |

> The 8-instance `psf/requests` slice used for every SWE-bench arm comparison scores
> **87.5%** — the *easiest* repo in the set, 18pp above django which dominates the real
> benchmark. Another way the n=8 slice was not representative.

| difficulty | n | hit@3 |
|---|---|---|
| <15 min fix | 127 | 76.38% |
| 15 min – 1 hour | 177 | 64.97% |
| 1–4 hours | 31 | 67.74% |

Localization degrades on longer fixes, which is also where resolve rate is worst — the
two ceilings compound.

---

## What this does and does not establish

**Established:**
- 69.64% hit@3 at n=336, CI ±5pp — a usable number, unlike the ±14pp it replaces.
- The failure splits ~46/54 between ranking and retrieval.
- A re-ranker's ceiling is **+14pp**, measured.
- The `psf/requests` slice is unrepresentatively easy.

**Not established:**
- That a re-ranker would *reach* the oracle ceiling. The oracle assumes perfect ordering;
  a real re-ranker captures some fraction of it.
- Any causal link to resolve rate. Better localization is necessary, not sufficient —
  the generator still has to write a correct patch.
- Anything about the 164 instances in repos not cloned locally (sphinx, matplotlib,
  scikit-learn, xarray, pytest, pylint, seaborn, flask).

---

## Reproduce

```bash
export PYTHONPATH=
.venv/bin/python benchmarks/localizer_recall.py                       # all local instances
.venv/bin/python benchmarks/localizer_recall.py --repo django/django  # one repo
.venv/bin/python -m pytest tests/test_localizer_recall.py -q          # 11 tests on the instrument
```

Runtime ≈ 9 minutes for 336 instances. No API keys, no network, no tokens.
