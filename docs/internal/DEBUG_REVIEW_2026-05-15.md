# Debug review — 2026-05-15

Debug-focused 4th-pass review of `app.py` (~10.9 K LOC) over the ~25 commits
since `REVIEW_2026-05-15.md`. Read-only, no code changes. All line numbers
relative to current branch tip.

---

## Critical (something is wrong with shipped behaviour)

### C1 — `_add_modality_vectorized` runs BEFORE the in-memory reclassifier
**file**: `app.py:2388-2422`
**path**: `_post_process_trials()` calls `_add_modality_vectorized(out)` at
L2389; the antigen + product-type reclassifier loop runs at L2407–2422,
*after* the Modality column has already been assigned. Modality is computed
from the **saved** `TargetCategory` / `ProductType`, then the classifier
overwrites those two columns — leaving `Modality` stale w.r.t. the new
target/product.
**what triggers**: the snapshot 2026-05-15 has 14 target flips + 4
product-type flips on load (verified by running both classifiers against
the snapshot CSV). Concretely:
  - `NCT04422912` (DSG3-CAART / CABA-201): saved TC `CAAR-T` → reclassified
    to `CD19`. `Modality` was assigned `CAAR-T` (via `tgt_caar`), so the
    row now has TargetCategory=CD19 but Modality=CAAR-T.
  - `NCT06421701 / 06464679 / 06518668 / 06614270`: saved PT `Autologous`
    → `Allogeneic/Off-the-shelf`. Modality was assigned "Auto CAR-T" via
    `is_auto`, but ProductType is now "Allogeneic/Off-the-shelf".
**fix sketch**: move `_add_modality_vectorized` call to AFTER the
classifier loop (or restructure the loop to write to a copy and reorder).
**confidence**: Verified (reproduced via standalone script against the
pinned snapshot CSV).

### C2 — `snapshot_diff` compares reclassified `df` against raw `df_prev`
**file**: `app.py:4715-4727` + `pipeline.py:1883-1885`
**path**: Overview → "Changes since previous snapshot" panel. `df` is
post-processed (reclassified). `df_prev` comes from `_load_snap(prev_date)`
which returns the RAW saved CSV — no `_post_process_trials` applied. The
diff at L4726 reports `disease_changed + target_changed + product_changed`.
**what triggers**: every load shows ~14 phantom `target_changed` and ~4
phantom `product_changed` entries that aren't real overnight changes —
they're the static in-memory reclassification deltas that appear in the
diff vs *any* previous snapshot. The "Classification changes" KPI tile is
inflated; the listed reclassifications include rows that have been "drift"
since whatever date the in-code classifier last got a marker update.
**fix sketch**: post-process `df_prev` through `_post_process_trials` (or
call `_reclassify_target` / `_reclassify_product_type` per row) before
diffing, so both sides reflect the current classifier.
**confidence**: Verified.

### C3 — Antigen-focus "Open / recruiting" metric uses 2-status set, not OPEN_STATUSES
**file**: `app.py:6439-6440` + `6461`
**path**: Deep Dive → "By antigen" → pick a target → metric strip "Open /
recruiting". Computed as `OverallStatus.isin(["RECRUITING",
"NOT_YET_RECRUITING"])`. The canonical OPEN_STATUSES (L1664) also includes
`ENROLLING_BY_INVITATION`, and the in-tab product portfolio below at L6559
uses OPEN_STATUSES properly.
**what triggers**: any antigen with a by-invitation trial shows a lower
"Open" number in the headline metric than in the product table directly
beneath it, and lower than the same antigen's count in any other tab. This
is exactly the inconsistency the OPEN_STATUSES comment at L1655-1666
explicitly warns about ("232 vs 239 — because one used …").
**fix sketch**: replace the inline 2-status list with `OPEN_STATUSES`.
**confidence**: Verified (single-line grep, only call site that hard-codes
the 2-status list outside of the explicit "ACTIVE_NOT_RECRUITING" branch
in the recently-updated filter).

---

## High (likely wrong under realistic user flow)

### H1 — Audit script reports stale "PASS / FAIL" — disconnected from runtime
**file**: `scripts/audit_product_consistency.py:59`
**path**: The audit reads the saved CSV at `snapshots/<date>/trials.csv`
and computes `targets_per_product`. It does NOT apply the in-app
reclassification step. Today's snapshot (2026-05-15) reports 4 inconsistent
products via the audit (`caba-201`, `ct1192`, `hn2301`, `kyv-101`) but
the in-memory reclassifier produces a DIFFERENT set of inconsistencies
post-load (e.g. `NCT07339332` saved CD19 → reclassified CD19/CD20 dual).
**what triggers**: a clean audit run can be green while the rendered app
still has product inconsistencies (or vice versa). Specifically:
NCT04422912 (CABA-201/DSG3-CAART) is saved as CAAR-T but reclassified to
CD19 — losing the CAAR-T marker. The named_product priority reorder
(commit 3b166ca) is overruling the explicit DSG3-CAART marker for a
genuine dual-construct trial.
**fix sketch**: have the audit script call `_assign_target` /
`_assign_product_type` on each row before grouping, so the audit reflects
what users actually see. Separately, consider whether the named_product
priority should yield to explicit_marker when the intervention text
mentions a different antigen alongside the named product.
**confidence**: Verified.

### H2 — `_deepdive_timeline` hard-requires `StartYearNumeric` on every input frame
**file**: `app.py:2787`
**path**: `_deepdive_timeline()` does `df["StartYear"] =
df["StartYearNumeric"]` unconditionally after only checking that
`StartYear` is present (L2784). If a caller passes a frame WITHOUT
`StartYearNumeric` (e.g. a downstream test, a future caller that builds
its own DF from `pd.DataFrame(...)`, or a code path that drops the baked
column), this raises `KeyError`.
**what triggers**: today, every caller derives the frame from `df_filt`
which inherits the baked column from `_post_process_trials`. But the
contract isn't enforced — `_focus_with_disease` (an `_expand_disease_rows`
output) is passed in, and if the apply path ever drops the column the
chart will crash silently into the chart cell. The L2784 check is
misleading because it tests `StartYear`, not `StartYearNumeric`.
**fix sketch**: fall back to `pd.to_numeric(df["StartYear"],
errors="coerce")` when `StartYearNumeric` is missing, or update the guard
at L2784 to also check for `StartYearNumeric`.
**confidence**: Likely (no observed crash; defensive concern flagged by
the numeric-bake refactor).

### H3 — Compare tab sponsor / product picker labels carry trial counts that desync from URL state
**file**: `app.py:7050-7082` + `3414-3416` (`_seed_pick_from_query`)
**path**: For sponsor / product compare axes, options are labelled
`"AcmeBio  (5 trials)"`. `_sync_pick_to_query` writes the full label to
the URL (`?fsp=AcmeBio%20%20%285%20trials%29`). On a return visit after a
snapshot update, "AcmeBio" may now have 7 trials → the URL value no longer
matches any option → `_seed_pick_from_query` silently drops the seed and
the focused view falls back to "no specific sponsor". Same shape applies
to the dd_compare_a / dd_compare_b selectboxes (no URL but a stale value
in session_state across reruns after sidebar filters narrow).
**what triggers**: shared URL stops opening the intended sponsor view
once trial counts change.
**fix sketch**: store/restore the bare sponsor name in the URL; expand
the label only for display in the option list (the inverse of the existing
`_resolve` helper, but applied to the seed side).
**confidence**: Likely.

### H4 — DiseaseFamily speed-win guard is a no-op for current snapshots
**file**: `app.py:3226-3241`
**path**: `if "DiseaseFamily" not in df.columns:` was added to skip
recomputation when the snapshot already carries the column. But the
pipeline (`pipeline.py`) does not write a DiseaseFamily column to
snapshots — verified by inspecting the CSV header (`DiseaseEntities`,
`DiseaseEntity` are present; `DiseaseFamily` is not). So the guard never
prevents recomputation in production.
**what triggers**: no user-visible bug; speed claim in the commit message
("~50-100 ms per warm rerun" saved) doesn't apply. Worth flagging
because the *intent* was to skip the apply.
**fix sketch**: have `build_snapshot.py` write `DiseaseFamily`, OR remove
the guard with a comment explaining why we always rebuild.
**confidence**: Verified.

---

## Medium (edge-case bugs, probably never hit)

### M1 — `dd_disease_pick` cleared via dropdown to "—" while widget still has a row selected — landscape re-fires only if user clicks a DIFFERENT row
**file**: `app.py:5760-5772` (and mirrors at 6393-6405, 7307-7319)
**path**: User clicks row X → `pick=X`, `last_acted=X`. User changes
dropdown to "—" (landscape). Landscape re-renders, dataframe widget's
preserved selection is row X. `_picked_d=X`, `last_acted==X` → guard
blocks re-fire (correct — that's the intended behaviour). But session
state `dd_disease_last_acted` still equals X. Now user clicks row X AGAIN
to focus it again — the guard at L5769 (`last_acted != _picked_d`) is
TRUE only if X differs from last_acted; X == X so it blocks. User has to
click a different row first, then back to X. This is the documented
trade-off the comment at L5754-5759 describes, but the comment claims
clicking the same row "re-fires correctly" — actually it doesn't, unless
the user first clears the selection by clicking somewhere else.
**what triggers**: niche but real — a user re-focusing the same disease
after browsing the landscape briefly will silently fail to re-fire.
**fix sketch**: clear `dd_disease_last_acted` when `pick` transitions from
non-"—" back to "—" (do this in a separate detection block before the
selectbox renders).
**confidence**: Likely (theoretical; not behaviourally observed in this
review).

### M2 — Compare tab dropdown value stale-state after sidebar narrowing
**file**: `app.py:7800-7811`
**path**: User picks Sponsor A and Sponsor B in Compare. Then user
narrows sidebar so Sponsor A no longer has any trials in `df_filt`.
`_opts_display` rebuilds, Sponsor A is gone. `key="dd_compare_a"` carries
the stale label. Streamlit selectbox behaviour with a persisted key whose
value isn't in `options` varies by version — newest behaviour resets to
the first option silently; older versions raise StreamlitAPIException.
**what triggers**: silent picker-switch on filter narrow (with no warning
to the user that their compare was redirected) OR a hard exception
banner.
**fix sketch**: before rendering, check
`st.session_state.get("dd_compare_a") in _opts_display` and pop if not.
**confidence**: Likely.

### M3 — Recently updated panel uses UTC-now for tz-naive comparison
**file**: `app.py:4632-4635`
**path**: `_cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=N)`
then `.tz_localize(None)` to compare against tz-naive
`LastUpdatePostDate`. CT.gov dates are calendar-day, but "now in UTC
local-naive" can be up to a calendar day ahead/behind the user's local
calendar day.
**what triggers**: edge of the timeframe filter (a date posted yesterday
in the user's locale may or may not appear in "Past week" depending on
UTC vs local). Cosmetic.
**fix sketch**: `pd.Timestamp.now()` (locale-naive) without the tz
roundtrip; or always work in calendar-day buckets.
**confidence**: Verified (logic-walk; effect is small).

### M4 — DiseaseFamily NOT re-derived when in-memory reclassifier changes TargetCategory
**file**: `app.py:2407-2422` + `app.py:3226-3241`
**path**: The reclassifier runs inside `_post_process_trials` (cached).
DiseaseFamily is computed AFTER `_post_process_trials` returns. The
14-row target flips don't change DiseaseEntity, so DiseaseFamily is
generally stable. But `_disease_family()` does consult BriefTitle /
Conditions, not TargetCategory, so this is mostly safe — flagging for
the record because the commit description ("re-classification on
snapshot load") implies full reclassification of every derived column,
which it isn't.
**what triggers**: nothing observed.
**confidence**: Speculative.

---

## Low / informational

### L1 — `_post_process_trials` cache key is the raw_df
The `@st.cache_data` decorator on `_post_process_trials` keys off `raw_df`
identity. The cache is cleared on snapshot pin / sidebar Reset. No bug.

### L2 — `EnrollmentCount` re-coerced in some sites even after baking
The bake at L2428-2430 produces `EnrollmentCountNumeric`. Some call sites
(e.g. L5713-5714 inside the `agg(...)` lambdas, L5898 indirect) still go
through `pd.to_numeric(...)` again or use the alias. Functionally
equivalent — performance only.

### L3 — Test gaps (not bugs, just coverage)
The smoke test in `tests/test_app_smoke.py` covers cold boot + tab labels
+ KPI strip + sidebar reset button. Five worthwhile additions that would
catch the bugs above:
  1. After cold-boot, assert "Open / recruiting" KPI value equals
     `df_filt.OverallStatus.isin(OPEN_STATUSES).sum()` — catches C3 if
     the antigen-tab metric ever percolates to the headline.
  2. Assert no `target_changed` rows in the snapshot-diff panel when
     comparing today's snapshot to itself — catches C2 by making the
     phantom diffs measurable.
  3. Switch to Deep Dive → "By antigen" sub-tab via
     `at.pills(key="dd_active_view").set_value("By antigen").run()` and
     assert no exception + the antigen landscape table renders.
  4. Apply a sidebar filter that empties `df_filt` (e.g. pick a phase
     never used) and assert no exception across every sub-tab.
  5. Set `dd_compare_a` / `dd_compare_b` to two valid sponsors and
     assert paired-row layout renders + cross-mix breakdowns appear —
     catches H3/M2 regressions in the recent compare-axis refactor.

### L4 — "Looks like a bug but isn't"
  - **`Modality` falls back to `"CAR-T (unclear)"` via `default=` at
    L2374**: belt-and-braces; the comment says "should be zero in
    practice". Fine.
  - **`_seed_pick_from_query` silently drops out-of-range URLs**: this
    is documented in the docstring as intentional; not a bug.
  - **Empty-state for Compare with `_pick_a == _pick_b`**: guarded at
    L7813-7814 with a warning. Correct.
  - **Recently updated panel `_ra_full.empty` guard**: correctly checks
    before drilldown render (L4689). Correct.
  - **`_fold_unclear_target` collapsing platform labels into "Unclear"
    for the L3 sunburst**: deliberate (comment at L4362-4380).

---

## Summary scorecard

| ID  | Area              | Severity | Verified? |
|-----|-------------------|----------|-----------|
| C1  | Modality stale    | Critical | Yes       |
| C2  | Snapshot diff     | Critical | Yes       |
| C3  | "Open" metric     | Critical | Yes       |
| H1  | Audit drift       | High     | Yes       |
| H2  | Timeline guard    | High     | Likely    |
| H3  | Compare URL state | High     | Likely    |
| H4  | DiseaseFamily NO-op guard | High | Yes |
| M1  | last_acted same-row | Medium | Likely   |
| M2  | Compare stale picker | Medium | Likely  |
| M3  | UTC-now tz quirk  | Medium   | Yes       |
| M4  | DiseaseFamily reclass | Medium | Spec.   |

The three Critical findings (C1/C2/C3) share a common root cause: the
"re-run classifier on snapshot load" commit (ce650bd) was added without
updating its three downstream dependents — the modality assignment that
runs before it, the snapshot-diff that compares against unprocessed
data, and the `audit_product_consistency.py` script that reads disk.
Fixing C1 is a one-line reorder. C2 needs `_load_snap` results post-
processed. C3 is a one-line constant swap.
