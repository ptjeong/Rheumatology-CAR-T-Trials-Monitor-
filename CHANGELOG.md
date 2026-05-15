# Changelog

All notable changes to the Rheumatology CAR-T Trials Monitor are recorded
here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions reference the classification-layer semantics; they are independent
of minor UI / figure tweaks.

## [Unreleased]

### Classifier — May 2026 wave

- **Multi-target arbitrary-arity labels**: the explicit-marker layer in
  `_assign_target` now collects all detected antigens and emits a label
  via `_format_target_label` (`"CD19"` → `"CD19/BCMA dual"` →
  `"CD19/CD22/BCMA triple"` → `"… multi"`). Replaced an earlier
  hardcoded if-chain that handled only specific dual pairs and silently
  dropped any 3rd antigen. Surfaced when NCT07174843 (BZE2204) was
  reported as "CD19/BCMA dual" despite explicitly being a
  CD19/CD22/BCMA triple-target CAR-T.
- **CD22 detection** added to `CAR_SPECIFIC_TARGET_TERMS`. Previously
  unsupported; CD22-bearing trials fell to `CAR-T_unspecified`.
- **Named-product first** priority — `_lookup_named_product` runs BEFORE
  explicit-marker text matching, so known canonical CAR-T products
  (KYV-101, CABA-201, CT1192, …) resolve to their documented antigen
  regardless of comedication mentions in the text. Fixed NCT06384976
  (KYSA-7: KYV-101 + anti-CD20 mAB) being mis-classified as
  CD19/CD20 dual.
- **CAR-NK platform → Allogeneic** default rule. CAR-NK products in
  autoimmune are predominantly allogeneic; the earlier default-to-
  Autologous rule mis-classified ~5 trials per snapshot. Triggered
  by a manual validation pass against a 200-trial sample.
- **Word-boundary regex on short tokens** (CD6, CD7) — `"cd7" in text`
  was matching the "cd7" inside "cd70", producing false-positive
  triple labels for CHT105 ("anti-CD19/70 CAR-T") and similar.
- **NAMED_PRODUCT_TARGETS corrections**: LCAR-AIO restored from
  "CD19/CD20 dual" (previously downgraded "as closest fit") to
  "CD19/CD20/CD22 triple" now that the classifier supports triples;
  LMY-920 corrected to BAFF-R per the ligand-CAR convention; GT719
  corrected to CD19 per its explicit "CD19-targeted iNKT Cell"
  interventions string.
- **Re-classification on snapshot load**: `_assign_target` and
  `_assign_product_type` are re-run inside `_post_process_trials` at
  every load. Saved snapshot columns become advisory; the canonical
  source of truth is code + raw data at view time.
- **Product-consistency audit script**
  (`scripts/audit_product_consistency.py`) flags named products with
  inconsistent TargetCategory across their trials — a drift sentinel
  paired with the reclassification refactor.

### UX — Deep Dive restructure

- **6 sub-tabs**: By disease · By antigen (was "By target") · By
  product (new) · By sponsor · By time · Compare (new). Each focused
  view follows a consistent shape: metric strip → charts row →
  product-portfolio table (where applicable) → sparkbar lists →
  trial table with row-click drilldown.
- **Click-to-focus on landscape tables**: clicking any row in the
  Disease / Antigen / Sponsor-type landscape tables sets the focus
  picker and jumps directly to the focused view.
- **Compact sparkbar lists** replaced narrow Plotly bar charts for
  small-N panels (country drilldown, focused-view antigen/product
  breakdowns, modality split). Constant per-row height regardless
  of category count.
- **Product portfolio table** centrepiece in both By sponsor and
  By antigen focused views: one row per `ProductName` showing
  sponsor / modality / antigen / diseases / phases active / trials
  / open / year range.
- **Compare tab**: paired-row layout with shared scales (grouped
  phase-mix bars, paired 100%-stacked sponsor-type bars, paired
  sparkbar cross-axis lists), replacing the prior two parallel
  panels with independent y-axes. Supports 5 axes: Disease entity ·
  Antigen target · Modality · Sponsor · Product.
- **In-tab TOC** on the three long focused views (Disease / Antigen /
  Sponsor) for scroll-relief.
- **Recently updated panel** absorbed the separate "Recently closed"
  panel; status filter expanded to "All closures", new "All time"
  timeframe pill. Row-click → trial drilldown matches the Data tab
  pattern.
- **Sidebar filter chip strip removed**. Both the focus-picker chip
  strip and the sidebar-filter chip strip are gone; the sidebar
  itself is the source of truth and the trial-count footer conveys
  narrowing.

### Methods + data integrity

- **Methods text** (`_build_methods_text`) updated to reflect current
  classifier (named-product first priority, CD22, multi-target arity,
  CAR-NK Allo default, re-classification on load). Added explicit
  **Limitations** section covering registry-source caveat, search
  recall/precision tradeoff, classification subjectivity,
  EnrollmentType reporting lag, declared-vs-actual geographic
  coverage, and snapshot-freshness caveat.
- **"Actual enrollment" KPI tile dropped**. Neither the status-based
  heuristic nor the strict `EnrollmentType=ACTUAL` flag produces a
  defensible number at this field maturity (heuristic overclaimed
  by ~5×, flag underclaimed by ~4×). "Planned enrollment" remains
  the headline.
- **Snapshot diff fix**: the Overview tab's "Changes since previous
  snapshot" panel now post-processes both sides before diffing.
  Previously surfaced ~14 phantom `target_changed` + ~4 phantom
  `product_changed` entries per load.
- Antigen-focus "Open / recruiting" metric now uses canonical
  `OPEN_STATUSES` (was hardcoded 2-status list missing
  `ENROLLING_BY_INVITATION`, disagreeing with every other tab).
- **Site title** updated to "CAR-T Rheumatology & Autoimmune Trials
  Monitor" (was "CAR-T Rheumatology Trials Monitor"). Reflects that
  the dataset has always included neurologic autoimmune trials
  (MS, NMOSD, MG) and other immune-mediated conditions.

### Speed wins

- **`_expand_disease_rows` vectorised** — was a per-row `iterrows()`
  loop called 6+ times per render. Replaced with column-wise split /
  explode; per-row Python helpers only run on the "Other immune-
  mediated" subset that needs subfamily reclassification. ~200-400 ms
  saved per warm rerun.
- **`EnrollmentCountNumeric` + `StartYearNumeric` baked** at
  `_post_process_trials` time; 16 render-time `pd.to_numeric(...,
  errors="coerce")` call sites swapped to read the baked columns
  directly. ~80 ms / rerun.
- `_post_process_trials` reorder so the in-memory classifier runs
  BEFORE `_add_modality_vectorized` — fixes a stale-Modality bug
  where 14 trials had their TargetCategory updated but Modality
  still reflected the pre-reclassification values.

### Testing

- 187 pytest cases (up from 175), incl. `tests/test_app_smoke.py`
  smoke test via `streamlit.testing.v1.AppTest`. Locks every
  classifier rule including multi-target arity, CD22 detection,
  CAR-NK Allo default, named-product priority, BAFF-R supersedes
  BAFF, word-boundary detection for CD6/CD7.

### Changed
- Snapshots are now byte-deterministic given identical upstream data.
  `trials.csv` and `sites.csv` are sorted on stable keys before write;
  `prisma.json` and `metadata.json` use `sort_keys=True`. Per-run
  wall-clock metadata moved out of `metadata.json` into a separate
  `runinfo.json` so it doesn't break byte-identity comparisons. Reviewers
  replicating the dashboard can now checksum a snapshot rebuild against
  the published artifact.
- `_normalize_text` now collapses every hyphen to a space (previously
  only `b-cell` / `t-cell` / `nk-cell` were rewritten). Closes a class
  of half-handled term-matching collisions on tokens like `anti-CD19`,
  `BCMA-CD19`, `CABA-201`. Also accepts `.` so version-tagged tokens
  (`claudin 18.2`) survive normalisation. Aligned with the onc app.
- Sponsor classification: `OTHER_GOV` is no longer pre-mapped to
  Government. CT.gov over-applies `OTHER_GOV` to non-US public hospitals
  that are functionally academic; those sponsors now route through the
  name-based heuristic (Anhui Provincial Hospital → Academic via
  "hospital"; Department of Veterans Affairs still → Government via the
  gov-name signal). Aligned with the onc app.
- Locked benchmark expanded from 12 to 21 trials. Adds first-time
  coverage of cGVHD (CD6 / CAR-Treg), CTD_other (single + basket),
  Unclear ProductType, BCMA-only target, Allo CAR-T modality, and
  academic-vs-industry balance for SSc / RA. 21/21 axes still at 1.000
  macro-F1 against the live snapshot.
- Validator (`scripts/validate_independent_llm.py`): TargetCategory
  enum-locked in `ALLOWED_VALUES` and injected into the prompt with
  spelling guidance, so cross-vendor reviewers (Gemini / OpenAI / Groq /
  Anthropic) format identically. Prevents formatting drift from
  inflating disagreement metrics.
- README: correct disease/target counts (10 entities, 15 targets);
  describe the three-layer validation loop; relocate the unrelated
  `ONCOLOGY_APP_KICKOFF.md` to `docs/onc-app-kickoff-archive.md`.
- Pin `anthropic<1.0.0` in `requirements.txt` to prevent silent
  major-version SDK drift on Streamlit Cloud rebuilds.

### Added
- **`_normalize_disease_result` post-hook** wraps every return path of
  `_classify_disease`. Enforces the (entities, design, primary)
  consistency invariants — primary == "Basket/Multidisease" iff design
  == "Basket/Multidisease"; sentinel labels ("Unclassified",
  "Other immune-mediated") never bundle with a specific entity.
  Defensive guard for future LLM-override edits.
- **GitHub Actions CI** (`.github/workflows/test.yml`) — Python 3.11 +
  3.12 matrix, py_compile + full pytest suite on every push and PR to
  main.
- **`CITATION.cff`** with the Zenodo concept DOI, mirroring the onc
  repo so GitHub's "Cite this repository" widget renders correctly and
  citing systems (Zotero, Mendeley, BibTeX exporters) can ingest the
  metadata directly.
- **`tests/test_pipeline_io.py`** — regression test for the
  byte-determinism contract: shuffles input rows, re-saves, and asserts
  SHA-256 byte-identity for `trials.csv` / `sites.csv` / `prisma.json` /
  `metadata.json` (and that `runinfo.json` does differ).

### Fixed
- **CTD_other systemic-basket bug** (`pipeline.py:_SYSTEMIC_DISEASES`).
  CTD_other was excluded from the systemic set, so multi-disease trials
  pairing CTD_other with SLE / SSc / IIM silently classified as
  Single-disease/CTD_other. Live evidence: NCT07490041 (matches
  `['CTD_other', 'SLE']`) was landing in Single-disease before the fix.

## [0.2.0] - 2026-04-25

### Added
- **Frozen snapshot 2026-04-25** for preprint readout (`snapshots/2026-04-25/`):
  284 included trials, 1,530 sites, 39 countries.
- **Three-layer validation infrastructure** ported from the onc app:
  - `tests/test_benchmark.py` + `tests/benchmark_set.csv` — per-axis F1
    floors (DiseaseEntity, TargetCategory, ProductType, Modality,
    SponsorType, TrialDesign).
  - `scripts/validate_independent_llm.py` — multi-provider κ
    cross-validation (Gemini / OpenAI / Groq / Anthropic) with
    stratified sampling and per-provider RPM pacing.
  - `scripts/snapshot_diff.py` — snapshot-to-snapshot reclassification
    diff with cause categorisation (expected LLM-override / hard-listed /
    unexplained) for blast-radius checking.
- **REVIEW.md** at repo root — comprehensive state review and 3-phase
  improvement roadmap.
- **Audit panel split** (`app.py`) — surfaces L1-promoted Neurologic
  autoimmune trials separately from Other-autoimmune sub-families with
  per-disease breakdown.
- **Neurologic autoimmune L1 family** with disease-level L2 (MS,
  Myasthenia gravis, NMOSD, AIE, CIDP, MOGAD, Stiff-person, neuro_other).

### Changed
- Sub-family L2 ring on the sunburst gets a distinct palette (slate +
  violet accent) inside Other autoimmune to separate Cytopenias /
  Glomerular / Endocrine / Dermatologic / GVHD.
- Disease-family palette unified on a navy / blue ramp so the rheum
  families read as a coherent set; neuro autoimmune gets a violet
  accent.

## [0.1.0] - 2026-04-23

Initial public release.

### Added
- Live pull from the ClinicalTrials.gov API v2 (PRISMA-style flow with
  hard-exclusion + indication-exclusion accounting).
- Reproducible **frozen snapshots** with `save_snapshot` / `load_snapshot`.
- **Disease-entity classifier** (`_classify_disease`) covering SLE, SSc,
  Sjogren, CTD_other, IIM, AAV, RA, IgG4-RD, Behcet plus generic
  Basket/Multidisease and Other immune-mediated buckets.
- **Antigen-target** + **product-type** classifiers with source-tag
  attribution for confidence calibration.
- **Modality derivation** in `app.py` (`_add_modality_vectorized`) over
  Auto / Allo CAR-T, CAR-NK, CAR-γδ T, CAAR-T, CAR-Treg, in-vivo CAR,
  plus an explicit "unclear" bucket.
- **LLM-assisted curation** via `validate.py` writing per-trial
  overrides into `llm_overrides.json`.
- **Streamlit dashboard** with 7 publication-ready figures, sunburst
  taxonomy view, choropleth + site-level world map, Germany-specific
  view, filter URL round-tripping, provenance-tagged CSV exports, and
  an auto-generated methods section.
