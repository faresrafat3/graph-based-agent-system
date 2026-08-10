# APPARATUS AUDIT — Are the 5 Arms Measuring the Same Thing?

**Scope:** forensic audit of the measurement apparatus behind the 5 experimental arms
reported in `docs/AGENT-LOOP-EXPERIMENT.md` (SWE-bench Verified, `psf/requests`, 8 instances).
**Method:** read-only inspection of harness code + reconstruction of every number from the
primary grader artifacts under `logs/run_evaluation/*/*/*/report.json`. No benchmark was
re-run; no repo file was modified except this report.

**VERDICT: NO.** The arm-to-arm comparisons are **not apples-to-apples**. The published
progression `applies 3 → 4 → 5 → 7` and `resolve stuck at 1/8` are both artifacts of the
measurement apparatus, not properties of the arms.

## 0. The one-paragraph answer

Every published "X/8" is a different fraction with a different denominator, and three
separate defects each independently break comparability:

1. Instances are dropped from the denominator by an over-broad `infrastructure` class that
   also captures a **harness bug in the local test runner** (§1), not just transport loss.
2. `applies` is measured by a **local check that is more permissive than the official
   grader**; three patches counted as "applies" were rejected outright by the real grader (§3).
3. There is **no seed anywhere** and the same arm re-run produces wildly different numbers —
   the loop arm produced 0/8, 0/8, and 3/8 applies across three identical runs (§4).

The `4/8 single-shot` baseline is real and traceable (§5) — but it is **not comparable** to
the other arms, because it is the *best of two* runs of an arm whose *other* run of the same
8 instances graded `1/8`. Every "improvement" in the document is measured against a
cherry-picked high-water mark.

## 1. Severity-ranked findings

| # | Sev | Finding | Evidence (file:line) |
|---|-----|---------|----------------------|
| F1 | **CRITICAL** | `FAIL_TO_PASS` is a **JSON string**, never parsed. Code guards only for a nested *list*, so a string falls through and is **iterated character by character**. Every character becomes a "test command". | `benchmarks/swebench_harness.py:1050-1057`; guard `:1052`; same defect at `:562-564`, `:650-652`, `:749-751`, `:899-901` |
| F2 | **CRITICAL** | Consequence of F1: for instances whose FTP string contains `/`, the harness executes literally `python -m pytest / -x -q` — pytest collects the entire filesystem and hits the 120 s timeout. That `TimeoutExpired` is then classified **`infrastructure`** and the instance silently leaves the denominator. | command built at `:1035`; timeout at `:1037`; classified at `:1206-1208` |
| F3 | **CRITICAL** | `failure_class="infrastructure"` is assigned by a **blanket `except Exception`** around the whole solve+validate path. It cannot distinguish LLM transport loss from a harness bug, a malformed patch, or a local-runner timeout. Anything that raises leaves the denominator. | `:1199-1211` |
| F4 | **CRITICAL** | `applied` counts over **all** results while `local_resolved` counts only rows carrying `best_local_resolved` — a key **only ever set for the `alphacode` mode**. For every other arm `local_resolved` is structurally 0. | `:1231` vs `:1242`; `:1295` vs `:1311`; key set only at `:1179-1182` |
| F5 | **CRITICAL** | Local `patch_applies` is more permissive than the official grader: `validate_patch` retries with escalating tolerance (`--recount`, `--ignore-whitespace`, `-C1`, `--unidiff-zero -C0`). The grader uses plain `patch`. **3 patches marked `applies=True` were rejected by the real grader.** | `:392-409`; disagreements listed in §3 |
| F6 | **HIGH** | The graph/graphfull feedback loop's exit condition `res["ftp_pass"] == res["ftp_total"]` can **never be satisfied** when F1 is active: `ftp_total` is a character count (62–568), so the loop always burns all `max_rounds`. The reported "full 3-round cycle executed" is a symptom of this defect, not evidence the dimensions worked. | `:889`; `ftp_total` produced at `:1057` from `:1026-1048` |
| F7 | **HIGH** | Grading exceptions are recorded as `resolved: False` and still counted in `total`. A Docker apply-failure or a 600 s test timeout is therefore reported as a **model failure**. 8 of the graded verdicts across the arms have **no grader report at all** yet appear as "not resolved". | `benchmarks/grade_alphacode.py:67-72`, denominator at `:74` |
| F8 | **HIGH** | No seed is passed anywhere. `temperature=0.0` is fixed but that is not determinism for this provider — empirically the same arm re-run gives different results (§4). | `llm/llm_integration.py:288,334` (and `:414,430`); no `seed` token exists in the file |
| F9 | **HIGH** | `graphfull`'s three "dimensions" are each wrapped in `except Exception` that resets the dimension text to `""`. A dimension that crashes every time is indistinguishable from one that ran and had nothing to add — and the run is still reported as a success. | `:918-919`, `:932-933`, `:943-944` |
| F10 | **MEDIUM** | The specialized-agent engines are imported under `except Exception: pass`. If an import fails, the dimension is silently `None` and the arm degrades to a plain refiner while still being labelled `graphfull`. | `:833-847` |
| F11 | **MEDIUM** | `solve_agent_graph_full` returns a hardcoded `"patch_applies": True` on the success path. It is *currently* sound (the patch is only replaced when `new_val["success"]` at `:964-966`), but it records a literal instead of a measurement — any future edit to the loop makes the field silently lie. | `:972` vs the guarded assignment `:964-966` |
| F12 | **MEDIUM** | Worktree cleanup is wrapped in `except Exception: pass` twice. A failed cleanup leaves a dirty tree that the next instance inherits. | `:130`, `:136` |
| F13 | **MEDIUM** | The arms are not configuration-matched: `solve_agent` allows `max_refinements=2`, `solve_agent_loop` allows `4`, `solve_agent_graph_full` allows `max_rounds=3` plus 2 apply-refinements. Arms differ in **compute budget** as well as architecture, so any delta is confounded. | `:443`, `:494`, `:819`, `:864` |
| F14 | **MEDIUM** | `skip_ptp=True` is the default in the local ranker, so `ptp_total=0` and the `local_resolved` condition `ptp_pass == ptp_total` is **trivially true** (0 == 0). Local "resolved" ignores regressions entirely — while the real grader shows PASS_TO_PASS failures up to 133. | `:1058`, condition at `:1099`, defaults at `:494`, `:819` |
| F15 | **LOW** | `patch_apply_rate_percent` is emitted as a headline percentage over a denominator that already excludes infrastructure rows, inviting exactly the misreading the adjacent `note` warns against. | `:1240-1246`, `:1304` |

## 2. The normalized comparison table

Reconstructed from the official grader's own `report.json` files, **all over the same
denominator of 8**. `attempted` = 8 for every arm by construction.

| Arm | Run id | Attempted | Non-empty patch | Harness says applies | Sent to grader | Grader accepted patch | **Graded** | **RESOLVED** |
|---|---|---|---|---|---|---|---|---|
| single-shot (agent) | `gbas_smoke` | 8 | 7 | 7 | 8 | 7 | 7 | **4** |
| single-shot (rerun) | `gbas_agent_requests` | 8 | 7 | 7 | 8 | 8 | 8 | **1** |
| alphacode N=3 | `gbas_alphacode_full` | 8 | 6 | 6 | 6 | 6 | 6 | **1** |
| loop (RUN 5) | `gbas_loop_r5` | 8 | 3 | 3 | 3 | 2 | 2 | **0** |
| graph (simple) | `gbas_graph` | 8 | 5 | 4 | 5 | 4 | 4 | **1** |
| graphfull v1 | `gbas_graphfull` | 8 | 6 | 5 | 6 | **2** | 2 | **0** |
| graphfull repaired | `gbas_gfr2` | 8 | 8 | 7 | 8 | 7 | 7 | **1** |

### Resolve rate over the honest denominator of 8

| Arm | Published | True (of 8) | Ungraded instances and why |
|---|---|---|---|
| single-shot | `4/8 (claimed)` | **4/8** | 6028 — grader apply-failure |
| alphacode | `1/8` | **1/8** | 5414, 6028 — never generated (both `infrastructure`) |
| loop | `0/3 graded` | **0/8** | 6 ungraded: 5 never generated, 2317 grader timeout |
| graph simple | `1/5 graded` | **1/8** | 4 ungraded: 3 never generated, 2317 grader timeout |
| graphfull v1 | `0/6 graded` | **0/8** | 6 ungraded: 2 never generated, **3 grader apply-failures**, 2317 timeout |
| graphfull repaired | `1/8` | **1/8** | 6028 — grader apply-failure |

### Which published figures are not comparable

- **`0/3`, `1/5`, `0/6` are not rates.** They are counts over the subset that survived to a
  grader verdict. Only `4/8`, `1/8`, `1/8` share the denominator 8 — and only by coincidence.
- **`applies 3 → 4 → 5 → 7` is not a capability progression.** It tracks how many instances
  avoided the infrastructure class on that particular day. `loop` scored 3 because 5 of its 8
  runs lost the network; the same arm scored **0 applies twice** in RUN 3 and RUN 4.
- **`graphfull v1 = 5/8 applies` is wrong by the grader's own measure.** Of those 5, three
  (1142, 1766, 6028) were rejected at apply time by the official grader. The real
  grader-accepted count is **2/8**, not 5/8.
- **The §8 → §9 "regression then repair" narrative does not survive.** The claim is that 1142
  resolved under `graph`, failed under `graphfull` v1, and was restored by the dimension
  repair. The primary artifact shows 1142 under `graphfull` v1 never reached a test at all —
  it failed the grader's *patch apply* step (`Hunk #1 FAILED at 1`,
  `logs/run_evaluation/gbas_graphfull/gbas-graphfull/psf__requests-1142/run_instance.log`).
  It was a malformed diff, not "context dilution across dimensions." The stated root cause
  of the repair is not supported by the evidence.

## 3. `applies` vs `resolved` — where each is decided

**`applies`** — local, in `validate_patch` (`:341-417`). Structural checks first
(`:371-380`), then `git apply --check` with **five escalating tolerance levels**
(`:392-409`). Returns `success` on the first level that passes.

**`resolved`** — two different mechanisms, and they disagree:

- *Local* (`run_tests_in_worktree`, `:977-1069`): applies the patch, runs FTP commands
  (`:1057`) and optionally PTP (`:1058`), computes `score = ftp_pass - (ptp_total - ptp_pass)`
  (`:1062`). `local_resolved` requires `applied and ftp_pass == ftp_total and ptp_pass == ptp_total`
  (`:1099`). **This signal is inert** — F1 makes `ftp_total` a character count, and F14 makes
  the PTP clause trivially true.
- *Authoritative* (`grade_alphacode.py:53-63`): the real SWE-bench `run_instance` in Docker,
  which applies the patch with plain `patch` and requires all FAIL_TO_PASS to flip and all
  PASS_TO_PASS to stay green.

**The gap between them (F5), from primary logs:**

| Run | Instance | Harness `patch_applies` | Official grader |
|---|---|---|---|
| `gbas_graphfull` | 1142 | `True` | `Patch Apply Failed: Hunk #1 FAILED at 1` |
| `gbas_graphfull` | 1766 | `True` | `Patch Apply Failed: Hunk #2 FAILED at 177` |
| `gbas_gfr2` | 6028 | `True` | `Patch Apply Failed: Hunk #1 FAILED at 200` |

Escalating tolerance (`--recount`, `-C1`, `--unidiff-zero`) accepts diffs whose hunk
counts and context lines have drifted. The grader does not. So `applies` — the one metric
that "rose monotonically" and carries the document's entire positive claim — is measured
by a **more forgiving instrument than the one used to measure `resolved`**. The two headline
numbers are not on the same scale.

A separate consequence: `run_tests_in_worktree` uses `git apply --check`/`git apply` with
**no** tolerance flags (`:1005-1018`), while `patch_applies` came from the 5-level path.
So a patch can be `applies=True` yet fail to apply inside the local grader, returning
`applied: False, score: -1` (`:1011-1014`) — scored as a capability failure.

## 4. Determinism — the arm differences are inside the noise

**No seed is passed anywhere.** `llm/llm_integration.py` fixes `temperature=0.0`
(`:288`, `:334`, and `:414`, `:430`) but the request body contains no `seed` field, and the
string `seed` does not occur in the module. Temperature 0 is not a determinism guarantee for
a hosted model behind a load-balanced pool — and the artifacts prove it empirically.

**Same arm, same config, same 8 instances, three runs:**

| Artifact | Applies | Infrastructure | Which instances applied |
|---|---|---|---|
| `swebench_loop_r3.json` | **0/8** | 8 | — |
| `swebench_loop_r4.json` | **0/8** | 7 | — |
| `swebench_loop_r5.json` | **3/8** | 5 | 1724, 1921, 2317 |

`graphfull` likewise: `swebench_graphfull_requests.json` = 5/8 applies with 2 infra;
`swebench_graphfull_r2.json` = 7/8 applies with 0 infra. And the single-shot arm graded
**4/8 and 1/8 on the identical 8 instances** (`gbas_smoke` vs `gbas_agent_requests`).

Instance 1142 alone was graded four times with four verdicts across arms —
`True, True, False, True`.

**Explicit statement:** run-to-run variance of the *same* arm (0 → 3 applies; 4 → 1 resolved)
is **larger than every between-arm difference reported in the document**. With n=8, no seed,
a single run per arm, and no confidence intervals, **none of the arm-to-arm deltas are
distinguishable from noise.** The repo already owns the correct tool for this —
`benchmarks/run_local_arms.py:269-308` implements paired McNemar — but it was **not used
for any of the five arms** in `AGENT-LOOP-EXPERIMENT.md`.

## 5. Provenance of the `4/8 single-shot (claimed)` baseline

**It is real, and it came from this grader.** Traced to run id `gbas_smoke`
(`docs/SWEBENCH-REPORT.md:14`), and the primary artifacts survive at
`logs/run_evaluation/gbas_smoke/gbas-agent/*/report.json`. Reconstructed directly:

| Instance | Resolved | FAIL_TO_PASS | PASS_TO_PASS failures |
|---|---|---|---|
| 1142 | **yes** | 1p / 0f | 0 |
| 1724 | **yes** | 6p / 0f | 0 |
| 1766 | **yes** | 6p / 0f | 0 |
| 2317 | **yes** | 8p / 0f | 0 |
| 1921 | no | 5p / 1f | 7 |
| 2931 | no | 1p / 0f | 1 |
| 5414 | no | 0p / 1f | 0 |
| 6028 | — | no report — grader apply-failure | — |

So `4/8` is genuine and Docker-graded, and the `?` marks in the document's scoreboard are
unnecessary — the per-instance detail exists on disk.

**But it is not a comparable baseline**, for three reasons:

1. **It is the maximum of two runs.** The same arm on the same 8 instances graded **1/8**
   under `gbas_agent_requests`. `docs/SOTA-POSITION.md:13-14` states this openly
   ("best of 2 runs" / "worst run"), yet `AGENT-LOOP-EXPERIMENT.md:161,220,294` carries only
   the 4/8 into every scoreboard. Comparing single-run arms against a best-of-2 maximum
   biases every subsequent arm downward.
2. **It is a different arm.** `gbas_smoke` ran `--mode agent` (`solve_agent`, `:443`,
   `max_refinements=2`), not a bare single LLM call. The row labelled "single-shot" is the
   governance arm; the true single-shot control is `solve_baseline` (`:425-440`), which was
   **never graded on this slice at all**. There is no measured no-governance control.
3. **`gbas_smoke` looks like a genuinely different generation.** Its FTP counts (6p/0f on
   1724, 8p/0f on 2317) are far above every later run of the same instances (0p/6f, 0p/8f).
   That is the variance of F8, not a stable baseline.

**Consequence:** the document's framing — "applicability rose but resolve never moved off
1/8" — measures every arm against a high-water mark that the same arm could not reproduce on
its second attempt. On the *reproducible* single-shot number (1/8), **no arm improved on the
baseline and none regressed**: every arm scored 0/8 or 1/8. The entire reported arc is one
resolved instance (1142) appearing or not appearing.

## 6. Quietly swallowed errors

| Location | Construct | What it can hide |
|---|---|---|
| `swebench_harness.py:1199-1211` | `except Exception` → `failure_class="infrastructure"`, `patch_applies=False` | **Any** failure — malformed patch, empty output, local-runner timeout, harness bug — becomes "not the model's fault" and leaves the denominator (F2, F3) |
| `swebench_harness.py:918-919` | `except Exception` → `reflection_txt = ""` | Reflexion dimension crashing looks identical to it having nothing to say |
| `swebench_harness.py:932-933` | `except Exception` → `debugger_txt = ""` | Same for Debugger; `debugger_used` stays `False` and is reported as a finding rather than a fault |
| `swebench_harness.py:943-944` | `except Exception` → `surgical_txt = ""` | Same for SurgicalRefiner |
| `swebench_harness.py:833-847` | 3× `except Exception: pass` on import | Missing engine silently degrades `graphfull` to a plain refiner under the same arm label |
| `swebench_harness.py:130`, `:136` | `except Exception: pass` on worktree removal | Dirty tree inherited by the next instance; cross-contamination between runs |
| `swebench_harness.py:414-415` | `except subprocess.TimeoutExpired` → `success: False` | A 120 s `git apply --check` timeout is reported as a patch defect |
| `swebench_harness.py:1009-1014`, `:1019-1024` | early return `score: -1, applied: False` | Local apply failure (stricter than `validate_patch`) scored as capability failure (F5) |
| `swebench_harness.py:1040-1041` | `if p.returncode == 0: passed += 1` | pytest **collection errors, usage errors and timeouts all return non-zero** — indistinguishable from a genuinely failing test |
| `swebench_harness.py:972` | literal `"patch_applies": True` | Records an assumption rather than a measurement (F11) |
| `grade_alphacode.py:67-72` | `except Exception` → `resolved: False`, still counted in `total` | Docker apply-failure / 600 s timeout reported as a model failure (F7) |
| `run_local_arms.py:77-84` | `INFRA_MARKERS` substring match incl. `"Connection"`, `"Timeout"`, `"failed after"` | Substring matching on error text — a model-produced string containing these words reclassifies a real failure as infra |
| `run_local_arms.py:232-236` | `except Exception` → `outcome: "error"` | Worker crash becomes a scored outcome |
| `llm/llm_integration.py:267`, `:278` | `except Exception` → `logger.debug` | Error-body and `Retry-After` parse failures visible only at debug level |

## 7. What would have to be true for the comparison to be valid

1. Parse `FAIL_TO_PASS` / `PASS_TO_PASS` with `json.loads` when they are strings
   (`swebench_harness.py:1050-1055` and the four duplicate sites). Until then every local
   test signal, the loop exit condition, and `local_resolved` are inert.
2. Split `failure_class` into `transport`, `harness`, and `model` so that a local-runner
   timeout caused by defect F1 stops being scored as infrastructure (`:1199-1211`).
3. Measure `applies` with the **grader's** tolerance, or report both numbers
   (`:392-409` vs the Docker `patch` step).
4. Grade **all 8** predictions for every arm, and report `resolved/8` with ungraded
   instances named — never `0/3` or `1/5`.
5. Separate grading infrastructure failures from model failures in
   `grade_alphacode.py:67-72`.
6. Pass a seed, or run each arm ≥5 times and report the interval. With n=8 the 95% CI on
   1/8 spans roughly 0–50%; the arms are indistinguishable.
7. Compare against the **reproducible** single-shot number (1/8), or re-run the baseline the
   same number of times as the treatment arms.
8. Use the paired McNemar machinery already present at `run_local_arms.py:269-308`.

## 8. Verdict

> **Are the arm-to-arm comparisons apples-to-apples? NO.**

- The denominators are not shared: `4/8`, `1/8`, `0/3`, `1/5`, `0/6`, `1/8` are six
  different fractions over four different denominators.
- `applies` and `resolved` are measured by instruments of different strictness, and the
  more permissive one produced the only rising trend in the document.
- A harness defect (F1/F2) systematically removes specific instances from specific arms.
- No seed exists, and the same arm re-run varies by more than any reported between-arm delta.
- The `4/8` baseline is real and Docker-graded, but it is the best of two runs of a
  *different* arm than its label suggests, and the same arm's other run graded `1/8`.

**The one defensible statement the evidence supports:** across all five arms and all runs,
exactly one instance (`psf__requests-1142`) was ever resolved reliably, and every arm landed
at 0/8 or 1/8 on the reproducible measurement. The reported applicability progression is not
established, and the "resolve ceiling" it is contrasted against was never a stable number.

---

*Read-only audit. No repo file was modified other than this report. No benchmark or test
suite was executed; every figure above is reconstructed from committed artifacts under
`benchmarks/results/` and `logs/run_evaluation/`.*
