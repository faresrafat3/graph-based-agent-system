# Local SWE-bench Arms — Interim Measurement

**Status:** partial run (paired subset), zero-Docker local judgement
**Harness:** `benchmarks/run_local_arms.py` · **Verified set:** `swebench_local_verified.json` (74 instances)
**Arms:** `baseline` (retrieval + one LLM call) vs `agent` (curate → validate → refine)

## Headline: the arms are indistinguishable on capability

| set | baseline | agent |
|---|---|---|
| capability-clean paired instances | **14/29** | **15/29** |
| discordant pairs | 1 | 2 |
| **McNemar exact p** | \- | **1.0000** |
| LLM calls | 21 | 28 (**1.33×**) |

**Three discordant pairs out of 29 is a tie.** The governance arm spends ~33% more tokens
and lands one extra instance — well inside noise.

## Why: the governance loop barely engages

| refinements | instances |
|---|---|
| 0 | **24 / 29 (83%)** |
| 1 | 1 |
| 2 | 4 |

**The refine loop fires on 5 of 29 instances.** On the other 83% the first patch applies
cleanly, so `solve_agent` degenerates into `solve_baseline` plus a context-curation step.
The null result is therefore **not** evidence that governance fails — it is evidence that
governance is *mostly not invoked* under this workload. A layer that runs on 17% of cases
cannot move an aggregate by much, whatever its quality.

This reframes the finding: the measurement is not "governance doesn't help", it is
"validate → refine only triggers on malformed patches, and malformed patches are the
smaller failure class."

## Where the losses actually are

| outcome | agent | meaning |
|---|---|---|
| resolved | 15/29 (52%) | — |
| **not_resolved** | **10/29 (34%)** | patch applied, fix was wrong → **reasoning gap** |
| no_apply | 4/29 (14%) | patch malformed → **formatting gap** |

Ceilings:
- fix every malformed patch → **66%**
- fix every wrong fix → **86%**

The governance layer targets the 14% (patch validity). The 34% — patches that apply
perfectly and still fail the gold test — is **more than twice as large** and is untouched
by validate/refine, because `validate_patch` asks git whether the patch is well-formed,
never whether the change is correct. That is the honest next lever.

## The trap this run walked into, and how it was caught

The naive read of the raw numbers is "agent 9, baseline 7 — governance wins." That
headline is **an artefact of infrastructure failure, not architecture**:

```
infra → resolved      2   (baseline's LLM call timed out; agent's didn't)
no_apply → infra      2   (agent's call timed out)
not_resolved → infra  1
```

All five contaminated pairs are the same root cause — `StepfunAPIError: The read
operation timed out` — a transport failure from one provider. Counting a network timeout
as a capability loss for the arm that hit it would have manufactured a 2-instance
"advantage" out of pure luck.

This is the same failure mode the triage tool had four times over: **a measurement error
that flatters the system**. The fix is the same discipline — classify infra separately,
exclude it from capability claims, and report both denominators.

## What this does and does not license

**Supported by the data:**
- On 15 capability-clean paired instances, `baseline` and `agent` resolve identically.
- The governance layer costs 1.47× the LLM calls on this set.
- 3 instances defeated both arms at the patch-application stage (`no_apply`), and
  4 produced applying-but-wrong patches (`not_resolved`) — these are the honest
  improvement targets.

**NOT supported:**
- Any claim that governance improves or harms resolve rate. n=15 with zero discordant
  pairs cannot distinguish the arms; it can only say the effect is not large.
- Any extrapolation to the full 74-instance set, or to non-django repositories.
- Any comparison to published SWE-bench numbers: this uses local `runtests.py` judgement
  on a filtered subset, not the official Docker harness on SWE-bench Verified.

## Method notes

- **Paired design.** Both arms see the same instance, the same worktree, and the same
  localizer output. Only the arm differs.
- **Patch application uses the grader's tolerance ladder** (plain → `--recount` →
  `--ignore-whitespace` → `-C1` → `--unidiff-zero`). An earlier version judged with a
  plain `git apply` and scored `no_apply` on patches the official grader accepts —
  charging the model for the harness's strictness. Caught on django-14725.
- **Outcome taxonomy:** `resolved` · `not_resolved` · `no_apply` · `infra` · `error`.
  Only the first three are capability signals.
- **Cost telemetry is measured, not estimated:** `llm_calls` is returned by each arm.

## Reproducing

```bash
PYTHONPATH= ./.venv/bin/python benchmarks/run_local_arms.py \
    --arms baseline,agent --workers 8 --out benchmarks/results/local_arms.jsonl
```

Resumable: re-running skips `(instance, arm)` units already in the JSONL.
