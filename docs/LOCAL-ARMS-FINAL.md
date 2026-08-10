# Local SWE-bench Arms — Final Measurement

**Status:** COMPLETE — 148/148 units (74 instances × 2 arms), zero-Docker local judgement
**Harness:** `benchmarks/run_local_arms.py` · **Verified set:** `swebench_local_verified.json`
**Arms:** `baseline` (retrieval + one LLM call) vs `agent` (curate → validate → refine)
**Raw data:** `benchmarks/results/local_arms.jsonl`

## Result: the arms are statistically indistinguishable

| | baseline | agent |
|---|---|---|
| resolved (capability-clean, n=50) | **25/50 — 50.0%** | **26/50 — 52.0%** |
| 95% CI | [36.6, 63.4] | [38.5, 65.2] |
| discordant pairs | 4 | 5 |
| **McNemar exact p** | colspan | **1.0000** |
| LLM calls | 50 | 66 (**1.32×**) |

Nine discordant pairs split 5–4. That is a coin flip. **The governance layer costs 32%
more tokens and produces one additional resolved instance out of fifty.**

Outcome distribution is nearly identical:

| outcome | baseline | agent |
|---|---|---|
| resolved | 25 (50%) | 26 (52%) |
| not_resolved | 18 (36%) | 17 (34%) |
| no_apply | 7 (14%) | 7 (14%) |

## Why: the governance loop fires on 18% of instances

| refinements | instances |
|---|---|
| **0** | **41 / 50 (82%)** |
| 1 | 2 |
| 2 | 7 |

On 82% of instances the first patch applies cleanly, so `solve_agent` reduces to
`solve_baseline` plus context curation. **The refine loop never runs.**

This is the finding that matters, and it reframes the null result. The measurement does
*not* say "governance does not work". It says **governance is mostly not invoked** under
this workload. A layer active on 18% of cases cannot move an aggregate regardless of its
quality — the experiment as designed had almost no room to detect an effect.

## Where the losses actually are

| failure class | share | what it means | addressed by validate/refine? |
|---|---|---|---|
| **not_resolved** | **34%** | patch applies, fix is wrong | **no** |
| no_apply | 14% | patch malformed | yes |

Measured ceilings:
- repair every malformed patch → **66%**
- repair every wrong fix → **86%**

`validate_patch` asks git whether a patch is *well-formed*, never whether the change is
*correct*. The governance layer therefore targets the 14% and leaves the 34% — a class
**2.4× larger** — completely untouched. That asymmetry, not the refine loop's quality, is
the reason the arms tie.

## Infrastructure

| | |
|---|---|
| units lost to transport failure | 35/148 (**23.6%**) |
| instances excluded from pairing | 24/74 |
| cause | `StepfunAPIError: The read operation timed out` (100%) |
| baseline / agent split | 18.9% / 20.0% — **not** arm-correlated |
| wall-clock lost to failed retries | **47%** |

Infra failures are excluded from every capability claim above. Counting them would have
manufactured an "advantage" for whichever arm got luckier: at one interim point the raw
numbers read 9–7 for the agent, and **both** differing pairs were `infra → resolved`.
That headline would have been network luck reported as architecture.

## What this licenses

**Supported:**
- On 50 capability-clean paired django instances, `baseline` and `agent` resolve
  equivalently (50.0% vs 52.0%, p=1.0).
- The governance layer costs 1.32× the LLM calls.
- The refine loop engages on 18% of instances.
- The dominant failure class (34%) is semantic, not structural.

**Not supported:**
- That governance is worthless. It was barely exercised; this is a null result on a
  weakly-activated treatment, not evidence of no effect.
- Extrapolation beyond django, or to the official Docker-graded SWE-bench Verified.
- Any per-arm ranking: the CIs overlap almost completely.

## The actionable conclusion

Two levers, in order of measured size:

1. **Govern reasoning, not formatting.** The 34% not_resolved class is 2.4× the class the
   current validator can see. A check that runs the gold-adjacent tests and feeds failures
   back would address it; `validate_patch` structurally cannot.
2. **Widen activation.** A layer that fires on 18% of cases cannot pay for 32% more
   tokens. Either trigger it more broadly or accept it as a narrow patch-repair utility.

## Method

- **Paired design:** both arms see the same instance, worktree, and localizer output.
- **Apply ladder:** patches are applied with the grader's own escalating tolerance
  (plain → `--recount` → `--ignore-whitespace` → `-C1` → `--unidiff-zero`). An earlier
  version used a plain `git apply` and scored `no_apply` on patches the official grader
  accepts, charging the model for harness strictness. Caught on django-14725.
- **Outcome taxonomy:** `resolved` · `not_resolved` · `no_apply` · `infra` · `error`.
  Only the first three are capability signals.
- **Diagnostics before execution:** localizer output is recorded *before* the arm runs;
  16 infra records had previously lost it to the exception path.
- **Cost telemetry is measured**, returned per-arm, not estimated.

## Reproducing

```bash
PYTHONPATH= ./.venv/bin/python benchmarks/run_local_arms.py \
    --arms baseline,agent --workers 8 --out benchmarks/results/local_arms.jsonl
PYTHONPATH= ./.venv/bin/python -m pytest tests/test_run_local_arms.py -q   # 22 tests
```

Resumable: re-running skips `(instance, arm)` units already recorded.
