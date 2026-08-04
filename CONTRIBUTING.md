# Contributing — Graph-Based Agent System

This repo is worked on by more than one person (including an autonomous
patrol that pushes to `main`). To avoid `main` getting clobbered by
conflicting direct pushes, **all human changes go through a branch + pull
request**, and `main` is branch-protected on GitHub (no direct push for
non-admins, require a passing CI run).

## 1. Branch model

| Branch | Purpose | Push directly? |
|--------|---------|----------------|
| `main` | Always-green, deployable. Protected. | **No** for collaborators; the repo owner / patrol may direct-push in emergencies |
| `feat/<short-slug>` | New feature / agent / benchmark arm | Yes |
| `fix/<short-slug>` | Bug fix | Yes |
| `docs/<short-slug>` | Docs / report only | Yes |
| `chore/<short-slug>` | Build, CI, gitignore, dependency | Yes |

Rule of thumb: one logical change per branch. Branch off the latest `main`
(`git switch main && git pull --ff-only && git switch -c feat/...`).

Arena branches (`arena/*`) are auto-created by the harness and merged via PR —
treat them like any other feature branch; don't push to them by hand.

## 2. Commit message convention

We follow [Conventional Commits](https://www.conventionalcommits.org/).
CI runs `scripts/check_commit_msg.py` on every PR. It lints only the PR
author's own non-merge commits in the branch range — commits made by other
collaborators or the autonomous patrol are skipped, so they can't block your
PR.

```
<type>: <subject>            # subject: imperative, lowercase, no trailing period, <= 72 chars

<body, optional>            # why, not what. Wrap at 72 cols.
```

**Allowed `type` values:** `feat`, `fix`, `docs`, `chore`, `refactor`,
`test`, `perf`, `ci`, `build`, `revert`.

Examples:
- `feat: add AlphaCode benchmark arm to HumanEval harness`
- `fix: unbreak Stepfun policy audit (drop dead allow-mock kwarg)`
- `docs: correct SWE-bench localizer recall to 70%@3`

Bad (will fail CI):
- `Update stuff` (no type, non-imperative)
- `Feat: Added memory agents` (capitalized type, past tense, capitalized subject)
- `WIP` (no substance)

A commit that only touches `docs/` or `*.md` reports must still use `docs:`.
Squash noisy "fixup" commits before opening the PR (`git rebase -i main`).

## 3. Pull request workflow

1. Branch from current `main`, make focused commits.
2. Ensure local tests pass: `make test` (or `pytest -q`).
3. Push the branch: `git push -u origin feat/<slug>`.
4. Open a PR against `main`. Fill the PR template.
5. CI (`test`) must be green. **A PR is mandatory** — direct push to `main`
   is blocked by branch protection. For human teams of 2+, get at least 1
   review approval before merge (the autonomous patrol merges its own PRs once
   CI is green). Branch protection enforces the PR + green CI gate, not the
   review count, so a solo author is never deadlocked.
6. Merge with **Squash and merge** for single-feature branches, or
   **Rebase and merge** when you want to preserve a meaningful commit chain.
   Avoid "Create a merge commit" for routine work — it pollutes history.
7. Delete the branch after merge (GitHub offers the button; remote stale
   branches are periodically pruned).

## 4. What belongs in the repo (and what does not)

**Commit:**
- Source: `agents/`, `kernel/`, `llm/`, `benchmarks/`, `system/`, `tools/`, `scripts/`
- Docs: `docs/*.md`, `README.md`, `LAWS.md`, `CONSTITUTION.md`
- Config: `Makefile`, `requirements.txt`, `.github/`, `pyproject.toml`
- Small benchmark **evidence** JSONs in `benchmarks/results/` (keep them —
  they back the reports).

**Do NOT commit (already gitignored or should be):**
- `.env` / any secret or API key file — use `.env.example` as the template.
- Large raw datasets (`benchmarks/data/`), SWE-bench repo clones, Docker logs.
- Throwaway smoke/proto artifacts: `benchmarks/results/*smoke*`,
  `*repro*`, `*_preds.jsonl`, `*requests*.json` (regenerate, don't vendor).
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.venv/`.

If you must ship a large artifact, store it in release assets or object
storage, not git history.

## 5. Governance

All code MUST respect `LAWS.md` and `CONSTITUTION.md`. The governance check
(`system/governance_checks.py`, run via `make audit`) validates this and is
part of CI. A PR that breachs a Law is not mergeable.

## 6. Emergency direct push

`main` protection does **not** enforce on admins, so the repo owner can
force-push / direct-push in a true emergency. Use it only to unblock CI
or revert a bad merge — never for routine work.
