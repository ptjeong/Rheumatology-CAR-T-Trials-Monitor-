# Changelog

All notable changes to the Rheumatology CAR-T Trials Monitor are recorded
here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions reference the classification-layer semantics; they are independent
of minor UI / figure tweaks.

## [Unreleased]

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
