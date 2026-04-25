---
title: "Supplementary material — CAR-T cell therapy across rheumatic and immune-mediated disease: a global registry-derived landscape"
companion: "manuscript.md"
snapshot_date: "2026-04-25"
code_commit: "540b9c1"
---

This supplement accompanies the main manuscript and provides the search
expression, classification ontology, validation results, reporting checklist,
and full data manifest. All file references are relative to the project
repository at commit `540b9c1`.

---

# S1 · Data source, search expression, and exclusion lists

## S1.1 ClinicalTrials.gov API v2 query

Trials were retrieved via the public ClinicalTrials.gov API v2 endpoint:

```
GET https://clinicaltrials.gov/api/v2/studies
```

with paginated requests (page size 200) cycled with `nextPageToken` until
exhaustion. Snapshot timestamp: 2026-04-25 (UTC). Implementation:
[`pipeline.py:631–663`](../pipeline.py#L631).

The combined search expression and named-product alias index live in
[`config.py`](../config.py) under the constants `DISEASE_ENTITIES`,
`OTHER_IMMUNE_MEDIATED_TERMS`, `CAR_SPECIFIC_TARGET_TERMS`,
`ALLOGENEIC_MARKERS`, `AUTOL_MARKERS`, `NAMED_PRODUCTS`,
`NAMED_PRODUCT_TARGETS`, `NAMED_PRODUCT_TYPES`, and
`HARD_EXCLUDED_NCT_IDS`. The full constant tables are reproduced verbatim
from the locked code at commit `540b9c1` for archival purposes; readers may
also consult the file directly.

## S1.2 Hard-excluded NCT IDs

Twenty-nine NCT identifiers were on the curated hard-exclusion list at
snapshot date. The full list is in `config.HARD_EXCLUDED_NCT_IDS`. Each
exclusion has a one-line rationale (false-positive autoimmune match, CAR-T
for transplant desensitization, observational-only, sarcoma context, etc.)
maintained in the source.

## S1.3 Indication-keyword exclusions

Approximately 15 stems removed records whose primary indication was malignancy
(lymphoma, leukaemia, myeloma, B-cell malignancy, solid tumour, etc.). Full
list: `config.EXCLUDED_INDICATION_TERMS`. At 2026-04-25 snapshot, 43 records
were removed by this layer.

## S1.4 LLM-derived exclusions

Per-NCT overrides produced by `validate.py` (Claude `claude-opus-4-7`,
constrained JSON schema) marked `exclude=true` with `confidence ∈ {high,
medium}` and `disease_entity != Exclude` are filtered out at the pipeline
classification step. At 2026-04-25 snapshot, 0 records were removed by this
layer; the LLM second-opinion is more often used to *re-classify* than to
*exclude*.

---

# S2 · Classification ontology

## S2.1 Disease-entity to L1-family mapping (locked at commit `540b9c1`)

| Disease entity (pipeline.py output) | L1 family |
|---|---|
| SLE | Connective tissue |
| SSc | Connective tissue |
| Sjogren | Connective tissue |
| IIM | Connective tissue |
| CTD_other | Connective tissue |
| IgG4-RD | Connective tissue |
| RA | Inflammatory arthritis |
| AAV | Vasculitis |
| Behcet | Vasculitis |
| Other immune-mediated (text-matched neurologic) | Neurologic autoimmune |
| Other immune-mediated (other) | Other autoimmune |
| cGVHD (text-matched neurologic) | Neurologic autoimmune |
| cGVHD (other) | Other autoimmune |
| (any, with `TrialDesign == "Basket/Multidisease"`) | Basket/Multidisease |
| Unclassified, "" | Other / Unclassified |

Source: [`app.py:183–207`](../app.py#L183), `_DISEASE_FAMILY_MAP` and
`_FAMILY_ORDER`.

## S2.2 L2 sub-family classifier (Other autoimmune)

Five system-level sub-families are matched on conditions/title text inside
the Other autoimmune family:

| Sub-family | Pattern (truncated; full regex in source) |
|---|---|
| Autoimmune cytopenias | hemolytic anemia, AIHA, ITP, Evans, aplastic anemia, … |
| Glomerular / renal | IgA nephropathy, membranous nephropathy, FSGS, … |
| Endocrine autoimmune | Type 1 diabetes, Graves, Hashimoto |
| Dermatologic autoimmune | pemphigus, pemphigoid, hidradenitis, bullous |
| GVHD | graft-versus-host, GVHD |

Multi-match → Other autoimmune (defensive). Source:
[`app.py:246–315`](../app.py#L246).

## S2.3 L2 disease classifier (Neurologic autoimmune)

Seven specific diseases plus a `Neurology_other` fallback:

| Disease label | Pattern |
|---|---|
| MS | multiple sclerosis, RRMS, PPMS, SPMS |
| Myasthenia | myasthenia gravis, MGFA, MuSK |
| NMOSD | neuromyelitis, NMOSD |
| AIE | autoimmune encephalitis, anti-NMDA, LGI1, CASPR2 |
| CIDP | CIDP, chronic inflammatory demyelinating |
| MOGAD | MOGAD, MOG antibody, MOG-associated |
| Stiff-person | stiff-person, stiff person |
| Neurology_other | (multi-match or non-match within the neuro umbrella) |

Source: [`app.py:289–328`](../app.py#L289).

## S2.4 Antigen-target categories

Twelve canonical categories plus two CAR-modality-specific labels emitted by
`_assign_target` at [`pipeline.py:250–318`](../pipeline.py#L250): CD19, BCMA,
CD20, CD70, CD6, CD7, BAFF, CD19/BCMA dual, CD19/CD20 dual, CD19/BAFF dual,
BCMA/CD70 dual, CAR-NK, CAAR-T, CAR-Treg, CAR-T_unspecified, Other_or_unknown.

Target classes used in Figure 4:

- **B-cell-directed:** CD19, CD20, CD22, BAFF, CD7, CD6
- **Plasma-cell-directed:** BCMA, CD70
- **Dual:** any combination including ≥2 of the above
- **Other:** non-canonical or unknown
- **Undisclosed:** `CAR-T_unspecified` (CAR confirmed; target not reported)

## S2.5 Cell-therapy modality (`ProductType`)

Four canonical labels emitted by `_assign_product_type` at
[`pipeline.py:321–389`](../pipeline.py#L321):

- **Autologous** — patient-derived; default when CAR confirmed and no
  allogeneic / in-vivo signal.
- **Allogeneic/Off-the-shelf** — donor-derived or universal CAR; matched on
  `ALLOGENEIC_MARKERS`.
- **In vivo** — lipid-nanoparticle-delivered CAR mRNA or analogous in-vivo
  reprogramming.
- **Unclear** — autoimmune indication confirmed but modality cannot be
  resolved from registry text.

---

# S3 · Validation

## S3.1 Inter-rater agreement (κ) — *to be completed*

A stratified random sample of n=100 trials was drawn proportional to L1
family from `snapshots/2026-04-25/trials.csv`. The sample is reproduced as
`tables/validation_sample.csv`.

Two independent classifications per trial:

1. Pipeline output (frozen at commit `540b9c1`).
2. Single human rater (P.J., blinded to pipeline output).
3. LLM second opinion (`claude-opus-4-7`, structured JSON).

Cohen's κ for each axis:

| Axis | κ (rater vs pipeline) | κ (rater vs LLM) | κ (pipeline vs LLM) |
|---|---|---|---|
| Disease entity | *tbd* | *tbd* | *tbd* |
| L1 family | *tbd* | *tbd* | *tbd* |
| Target category | *tbd* | *tbd* | *tbd* |
| Modality (ProductType) | *tbd* | *tbd* | *tbd* |

Confusion matrices and full per-trial reconciliation in
`tables/validation_confusion.csv` (to be generated).

## S3.2 Curation loop

Borderline trials (any of `DiseaseEntity == "Unclassified"`,
`TargetCategory == "CAR-T_unspecified"`, `ProductType == "Unclear"`,
`ClassificationConfidence == "low"`) are exported to `curation_loop.csv` for
human-in-the-loop refinement. At 2026-04-25 snapshot, the curation queue
contained *(N=tbd)* trials; these were reviewed by the LLM second-opinion
and the resulting overrides are recorded in `llm_overrides.json` shipped
with the repository.

---

# S4 · STROBE-adapted reporting checklist (registry analysis)

The STROBE checklist is intended for cohort, case-control, and cross-sectional
studies of individual patients; it is adapted here for routinely-collected
registry data.

| Item | Description | Section in main text |
|---|---|---|
| Title and abstract | Indicate study design and methods in title/abstract | Title; Abstract |
| Background/rationale | Explain scientific background and rationale | §1 Introduction |
| Objectives | State specific objectives, including any prespecified hypotheses | §1 final paragraph |
| Study design | Present key elements of study design early in the paper | §2 Methods (Abstract) |
| Setting | Describe the setting, locations, dates including periods | §2.1, §2.2 |
| Participants (records) | Eligibility criteria and sources/methods of selection | §2.2 |
| Variables | Clearly define all outcomes, exposures, predictors, classifiers | §2.3, §2.4 |
| Data sources / measurement | Detail sources of data and methods of assessment | §2.1, §2.3 |
| Bias | Describe efforts to address potential sources of bias | §4.5 Limitations |
| Study size | Explain how the analytic cohort size was arrived at | §3.1, §2.5 PRISMA |
| Quantitative variables | Explain how quantitative variables were handled | §2.7 |
| Statistical methods | Describe statistical methods, including those used to control for confounding | §2.7 (descriptive only) |
| Missing data | Describe handling of missing data | §3.5 (28 trials missing country); §2.7 |
| Sensitivity analyses | Describe any sensitivity analyses | §S3 (validation κ); main text §4.5 |
| Descriptive data | Give characteristics of study cohort | §3.1, Table 1 |
| Outcome data | Report numbers of outcome events or summary measures | §3.2–§3.6 |
| Main results | Give unadjusted estimates and, if applicable, confounder-adjusted | §3.2–§3.6 (descriptive) |
| Other analyses | Report other analyses done — eg, subgroups, interactions, sensitivity | §3.2–§3.6 |
| Key results | Summarize key results with reference to study objectives | §4 first paragraph |
| Limitations | Discuss limitations, taking into account sources of potential bias or imprecision | §4.5 |
| Interpretation | Give a cautious overall interpretation considering objectives and limitations | §4.1–§4.6 |
| Generalisability | Discuss the generalisability (external validity) of the study results | §4.4, §4.5 |
| Funding | Give the source of funding and the role of the funders | §7 |

PRISMA 2020 was not followed because this is a registry-analysis snapshot,
not a systematic review of evidence; the PRISMA-style flow in Figure 1A is
descriptive of the trial-selection procedure only and does not imply
adherence to the PRISMA reporting guideline.

---

# S5 · Data manifest

| File | Rows | Columns | Description |
|---|---|---|---|
| `snapshots/2026-04-25/trials.csv` | 284 | 31 | Per-trial classification (NCT ID, title, conditions, classification axes, geography, sponsor, phase, status, start year). Provenance header included. |
| `snapshots/2026-04-25/sites.csv` | 1530 | 8 | Per-facility geocoded site information. |
| `snapshots/2026-04-25/prisma.json` | — | — | Trial-selection ledger (n_fetched, n_after_dedup, n_hard_excluded, n_indication_excluded, n_llm_excluded, n_total_excluded, n_included). |
| `snapshots/2026-04-25/metadata.json` | — | — | Snapshot date, UTC timestamp, statuses filter, counts, API base URL. |
| `figures/preprint/fig{1..7}.{pdf,png}` | — | — | Static figures generated by `scripts/make_preprint_figures.py`. |
| `tables/table1_family_counts.csv` | *to be generated* | | L1 family with L2 detail and recruiting status. |
| `tables/table2_sponsors_products.csv` | *to be generated* | | Top 10 sponsors and top 15 named products. |
| `tables/validation_sample.csv` | 100 | — | Stratified random validation sample (to be generated; see §S3). |

---

# S6 · Code availability

Source code: `https://github.com/ptjeong/Rheumatology-CAR-T-Trials-Monitor-`,
locked at commit `540b9c1`. Live monitor:
`https://rheum-car-t-trial-monitor.streamlit.app`. Archived at Zenodo DOI
[10.5281/zenodo.19713049](https://doi.org/10.5281/zenodo.19713049).

To reproduce the figures from a fresh checkout:

```bash
git clone https://github.com/ptjeong/Rheumatology-CAR-T-Trials-Monitor-.git
cd Rheumatology-CAR-T-Trials-Monitor-
git checkout 540b9c1
python3 -m pip install -r requirements.txt plotly kaleido
python3 scripts/make_preprint_figures.py
# → figures/preprint/fig{1..7}.{pdf,png}
```

---

*Supplement v1.0 — locked at commit `540b9c1` + snapshot 2026-04-25.
Validation κ to be completed; tables 1, 2, and validation sample to be generated.*
