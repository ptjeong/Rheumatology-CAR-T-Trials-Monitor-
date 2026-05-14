# Daily-snapshot CI — port brief for the onc app

The rheum monitor has been running a daily-snapshot GitHub Action since
2026-05-08 (commit `9f49bbb`). Six daily runs so far, zero failures,
~3 min wall-clock per run. It builds a fresh snapshot from the live
CT.gov API, classifies, hashes, commits only when something changed,
and tags the commit for downstream Zenodo / citation workflows.

This brief ports that mechanism to the onc CAR-T dashboard. Self-
contained — paste into a fresh Claude Code session in the onc repo.

---

## Why port this

Today the onc dashboard's snapshot is built manually via the Streamlit
UI's "Save current as snapshot" button. That means:

- The dataset shown to readers is as stale as the last manual save.
  Even with the keep-awake CI rebuilding the container every 6h, the
  classifier still reads the most recent committed snapshot.
- Reproducibility tooling (Zenodo DOI minting, citation pin) consumes
  snapshot tags that don't exist until someone clicks the button.
- The maintainer has to remember to save before disappearing for a
  conference / vacation / breaking-change refactor.

Daily auto-snapshot removes the maintainer from the freshness loop.
Rheum has been running it for a week; the diff-vs-previous comment
on the rolling GitHub issue is also a useful "what changed today"
signal for collaborators.

---

## Architecture (what rheum does — verbatim port target)

Three pieces:

### 1. `scripts/build_snapshot.py` (~80 LOC)

A standalone CLI that calls `pipeline.build_all_from_api(...)` and
writes `snapshots/<YYYY-MM-DD>/{trials.csv, sites.csv, prisma.json,
metadata.json}`. Exit codes: 0 success, 1 API failure, 2 empty
classifier output. Skips the geo backfill (network-heavy, slow in CI;
the UI button opts in via `backfill_geo=True`).

### 2. `scripts/snapshot_diff.py` (~220 LOC)

Compares today's snapshot directory against the previous one, emits a
markdown summary: added trials, removed trials, status changes,
classification changes (DiseaseEntity / TargetCategory / ProductType /
EnrollmentCount delta). Output goes into a rolling GitHub Issue
comment so collaborators see the day-over-day delta without checking
the repo.

### 3. `.github/workflows/daily-snapshot.yml` (~150 LOC)

Runs at 03:00 UTC daily (cron `0 3 * * *`). Key design points:

- **Composite skip-decision hash.** Hashes (a) today's `trials.csv`
  contents and (b) git-tracked SHAs of `pipeline.py` + `config.py` +
  `llm_overrides.json`. When BOTH hashes match the previous run, the
  classifier didn't change and the data didn't change — the run is a
  no-op (snapshot directory is deleted to avoid duplicate date-stamped
  directories).
- **Force-rebuild input** for `workflow_dispatch`. Sometimes you want
  to commit an "identical" snapshot to test downstream tooling — the
  `force: true` workflow input bypasses the skip.
- **Tag push for citation.** Every committed snapshot gets a
  `snapshot-YYYY-MM-DD` tag pushed; downstream Zenodo workflows (when
  they ship) listen on this tag.
- **Rolling-diff issue comment.** Uses
  `peter-evans/create-or-update-comment@v4` to append today's diff
  to a single tracking issue (configurable via
  `vars.ROLLING_DIFF_ISSUE`, falls back to issue #1).

---

## --- BEGIN PROMPT ---

This brief ports the rheum monitor's daily-snapshot CI to onc.
Rheum has been running it since 2026-05-08 with zero failures across
6 days. The mechanism is three files; copy them verbatim from the
rheum repo at:

    https://github.com/ptjeong/Rheumatology-CAR-T-Trials-Monitor-/

Specifically:
  - `scripts/build_snapshot.py`
  - `scripts/snapshot_diff.py`
  - `.github/workflows/daily-snapshot.yml`

### Adaptation required (onc-specific)

The three files reference rheum pipeline functions and CT.gov query
parameters. Each needs a one-line adjustment for onc:

1. **`scripts/build_snapshot.py`** — replace the `--max-records`
   default. Rheum is 2000 (covers full autoimmune-CAR-T pipeline with
   margin); onc's CAR-T-in-oncology pipeline is much larger, ~10000
   should be safe. Audit `pipeline.build_all_from_api`'s expected
   parameter list — if onc's pipeline takes additional kwargs (e.g.
   `disease_category` filter), thread them through.

2. **`scripts/snapshot_diff.py`** — verify the tracked columns list
   matches onc's classifier outputs. Rheum's tracked = `["NCTId",
   "BriefTitle", "OverallStatus", "Phase", "DiseaseEntity",
   "TargetCategory", "ProductType", "EnrollmentCount", "LeadSponsor"]`.
   Onc has `Branch` and `DiseaseCategory` columns as well — add them
   to the tracked list so cross-branch reclassifications surface in
   the diff comment.

3. **`.github/workflows/daily-snapshot.yml`** — adjust three items:
   - **Composite hash files**: rheum hashes `pipeline.py + config.py +
     llm_overrides.json`. Onc has the same trio; verify the filenames
     match (look in `app.py`'s import block to confirm). If onc
     additionally has e.g. `disease_buckets.py`, add it to the hash.
   - **Timeout**: rheum's `timeout-minutes: 15` covers a ~3 min fetch.
     Onc's ~10k records will take ~8-12 min — bump to `timeout-minutes:
     25` for safety margin.
   - **Cron schedule**: rheum runs at `0 3 * * *` (03:00 UTC). Onc
     can run at `0 4 * * *` to stagger and reduce GH cron-storm risk;
     they don't interfere with each other otherwise.

### Verification steps

After committing the three files (one PR):

1. **Manual dry-run via `workflow_dispatch`**. Actions tab → "Daily
   snapshot rebuild" → "Run workflow" → tick `force: true`. Should
   complete in ~10-15 min with a green check.
2. **Check the commit history.** Should show
   `Daily snapshot YYYY-MM-DD (auto)` from `github-actions[bot]`.
3. **Check the tag list.** `git fetch --tags && git tag -l 'snapshot-*'`
   should show today's tag.
4. **Check the rolling-diff issue.** If there's a prior snapshot to
   diff against, an issue comment should appear (or the workflow
   should log "First snapshot — no previous to diff against").
5. **Wait 24h** and verify the cron-triggered run fires. If it
   doesn't, GitHub's scheduled-runs queue is congested — check Actions
   tab's "Workflows" → look for queued/skipped runs.

### Edge cases handled by the rheum impl

- **Identical data day-over-day**: skip the commit (composite hash
  match). The empty snapshot directory is removed so the repo doesn't
  accumulate stub `YYYY-MM-DD/` dirs.
- **API rate-limit / network failure**: exits with code 1, the
  workflow logs the error to the run summary, no commit, no tag.
  Next day's run retries cleanly.
- **Classifier output empty** (config file corrupted, pipeline bug):
  exits with code 2 to distinguish from API failure.
- **Concurrent manual rebuild**: rheum uses
  `concurrency: { group: daily-snapshot, cancel-in-progress: false }`
  to serialise. Add to onc workflow yaml.

### What this is NOT

- It's not a backfill: only emits ONE new snapshot per day. Historical
  rebuilds require manual invocation per date.
- It's not a deploy trigger: Streamlit Cloud's webhook fires on the
  push to main (so the dashboard does refresh), but the keep-awake CI
  (see `KEEP_AWAKE_PORT_BRIEF_RHEUM.md` if the inverse port hasn't
  shipped) handles container-warming separately. The two are
  complementary, not redundant.
- It's not a citation pipeline: tags get pushed, but the Zenodo
  workflow that consumes them is separate (and not yet built on
  either side as of 2026-05-14).

### Estimated effort

~30 min if rheum's three files port cleanly. Add ~30-60 min if onc's
`pipeline.py` exposes `build_all_from_api` with a different signature
or returns different columns. Total: 1-1.5 hours including
verification.

### Files to commit (verbatim from rheum)

| File | LOC | Adapt? |
|---|---|---|
| `scripts/build_snapshot.py` | ~80 | One-line: `--max-records` default |
| `scripts/snapshot_diff.py` | ~220 | Maybe: add Branch / DiseaseCategory to tracked cols |
| `.github/workflows/daily-snapshot.yml` | ~150 | Three lines: hash files, timeout, cron offset |

### Decision required

Ship the port? Recommended yes — eliminates the manual snapshot step,
gives day-over-day diffs for free, sets up the citation pipeline.
Single PR. Reversible if anything breaks (delete the workflow file,
stop the cron).

## --- END PROMPT ---

---

## After landing

If both apps run the daily-snapshot CI:
- 2 commits per day per app (when data changes); ~60 commits/month
  combined. Within free-tier GitHub Actions budget by orders of
  magnitude.
- Cross-app diffs become possible: a script comparing the union of
  rheum + onc snapshots over time gives a "field-wide CAR-T cell-
  therapy pipeline activity" rolling dataset. Useful for a future
  meta-analysis or platform-wide news brief.

## Related briefs

- `KEEP_AWAKE_PORT_BRIEF_RHEUM.md` (lives in onc) — the reverse-
  direction port for Streamlit Cloud container warming.
- `CROSS_APP_PROFESSIONAL_GRADE_BRIEF_R3.md` — the broader 3-round
  cross-app coordination spec; the daily-snapshot CI is part of
  Round 3 W3-W4 deliverables.
