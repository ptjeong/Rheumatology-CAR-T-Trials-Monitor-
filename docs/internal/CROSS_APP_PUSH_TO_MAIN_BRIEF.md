# Cross-app brief — pushing directly to main

For the parallel onc-app session. Paste-ready into a fresh Claude Code
session if you want to mirror the rheum app's fast-iteration workflow.

Self-contained; references rheum repo conventions but the technique
is repo-agnostic.

---

--- BEGIN PROMPT ---

In the rheum app I've been pushing every commit to BOTH the working
branch and `main` in a single command. Worth knowing because:

  - Streamlit Cloud auto-rebuilds on `main` push (1-2 min lag), so
    the deployed app reflects every commit without merge-PR overhead
  - The user gets to see changes in the live deploy at the URL they
    share with collaborators, not just on localhost
  - Fast iteration cycle: edit → commit → push (both refs) → user
    refreshes deployed app within ~2 min

This is appropriate ONLY when the deploy is **not yet public** — i.e.,
no external users hitting the URL, no patient-facing claim, no
pre-registered analysis pipeline locked to a specific commit. The
rheum dashboard is currently in pre-launch iteration with the
maintainer as the sole user; that's the regime where direct-to-main
makes sense.

## The command

```bash
git push origin <branch_name> <branch_name>:main 2>&1 | tail -5
```

Single invocation pushes:
  - `<branch_name>` → `origin/<branch_name>` (the working branch)
  - `<branch_name>:main` → `origin/main` (the deploy ref)

Both refs land at the same commit SHA, so the branch and main stay
in lockstep.

## When the system blocks direct-main pushes

In this rheum session the runtime briefly denied the push with:

  > Permission for this action has been denied. Reason: User asked
  > to push to main, but the repo's default branch is main and
  > pushing directly to it bypasses PR review (Git Push to Default
  > Branch).

The block is a safety net — it fires when the user hasn't explicitly
authorised direct-main pushes. The path through:

  1. The user grants permission interactively, OR
  2. The user types something equivalent to "push to main" /
     "push directly" / "deploy this" — Claude can then proceed
     under their explicit instruction

In the rheum session the user said "can you push also directly to
main? the website isnt public yet, so we can still tinker", which is
the explicit authorisation pattern. Subsequent pushes then went
through without re-asking.

## The merge-fast-forward gotcha

First time you do this, `main` is likely AHEAD of your branch
(previous PR merges have landed there). A direct push will be
rejected with:

  ! [rejected]  branch -> main (fetch first)

Fix in one merge:

```bash
git fetch origin
git merge origin/main --no-edit   # creates a merge commit on your branch
git push origin <branch> <branch>:main
```

After the first merge, the branch tracks main; subsequent commits
push cleanly because branch is always >= main.

## When to NOT use this

  - Repo has a deployed app with non-trivial external usage (real
    users, citations, pre-prints linking to specific URLs)
  - PRs are part of the review/governance process (peer review,
    validation studies)
  - main is protected or has required CI checks that haven't run yet
  - The change touches data classification rules that are
    "locked in" by a published methods document

For those cases, stick to the standard PR flow.

## Verification after push

```bash
git log --oneline -1                    # local HEAD
git ls-remote origin main <branch>      # both refs at same SHA?
git status -sb                          # no `[ahead N]` marker
```

If `git ls-remote` shows both refs at the same SHA and status has no
ahead-marker, the push landed cleanly.

## Streamlit Cloud rebuild signal

After pushing to main, the deployed app rebuilds automatically. Lag
is typically 60-120 seconds. If the user reports they don't see the
change after that interval:

  1. Check `requirements.txt` — newly-added imports (kaleido for SVG
     export was a real gotcha) need to be listed there or the
     rebuilt container ImportError-fails silently with the runtime
     gracefully degrading the affected feature.
  2. Suggest the user click the three-dot menu on the deployed app →
     "Manage app" → "Reboot app" to force a fresh container.
  3. Hard-refresh the browser tab (Cmd+Shift+R) — Streamlit Cloud
     sometimes serves a cached HTML shell.

## Commit message convention (cross-app aligned)

For changes that affect both apps, prefix the commit with `cross-app:`
or `round-N:` so the parallel session can grep for sync-relevant
commits. The rheum side has used this convention since round 1.

--- END PROMPT ---
