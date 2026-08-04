# Agent Git Policy — Hermes Patrol & Autonomous Agents

This repo is co-owned by humans **and** an autonomous Hermes patrol/agent
(`faresrafat3` GitHub account, token-scoped). To keep `main` always-green
while letting the agent ship work without deadlock, the patrol follows one
hard rule:

> **The patrol NEVER pushes directly to `main`. It opens a branch + PR, waits
> for the `test` CI context to go green, then merges its own PR with
> `--admin --squash`.**

`enforce_admins` is **false** on the `main` protection rule, so a token carrying
the owner/admin scope may `gh pr merge --admin` to bypass the "no review" gate
without bypassing the required green `test` check. Direct `git push origin main`
is still blocked by branch protection for everyone, including the agent — this
is intentional.

## Why this shape

- **Multiple contributors (human + agent).** Concurrent direct pushes to
  `main` clobber each other. A PR is the single merge point.
- **CI is the gate, not a human.** Branch protection requires the `test`
  status check (pytest + coverage ≥ 80%). The agent waits for it before merge,
  exactly like a human would.
- **No review deadlock.** The repo has one primary human owner + an agent, so
  "required approving reviews" is deliberately **not** enforced (it would
  deadlock both). Reviews are a recommendation in CONTRIBUTING.md, not a hard
  gate.
- **Admins can break the glass.** `enforce_admins: false` lets the owner
  (`--admin`) unblock a stuck `main` in a true emergency.

## Patrol workflow (exact commands)

```bash
# 1. Always branch off fresh main
git switch main && git pull --ff-only
git switch -c chore/agent-<slug>

# 2. Make focused, Conventional-Commits messages
git commit -m "chore: <imperative subject>"

# 3. Push + open PR
git push -u origin chore/agent-<slug>
gh pr create --base main --fill --title "chore: <slug>"

# 4. Wait for the `test` check, then merge as admin (squash)
gh pr merge --admin --squash --delete-branch
```

The commit-message linter (`scripts/check_commit_msg.py`) runs in CI on every
PR and lints **only the PR author's own non-merge commits**, so the agent's
commits are checked independently of any human commits on the same base.

## What the agent may NOT do

- Push directly to `main` (blocked by protection; also a policy breach).
- Force-push or delete `main` (blocked by protection).
- Merge a PR whose `test` check is red.
- Commit `.env`, secrets, `gbas-agent.gbas_agent_v5.json`, or `__pycache__/`.
- Bypass `LAWS.md` / `CONSTITUTION.md` — governance audit (`make audit`) is part
  of CI and a red audit blocks merge.

## Emergency human override

The repo owner may, in a true emergency, push/force-push to `main` using the
admin scope (`enforce_admins: false`). This is for unblocking CI or reverting a
bad merge only — never routine work.
