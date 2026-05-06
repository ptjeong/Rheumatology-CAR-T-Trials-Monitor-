# CAR-T Rheumatology Trials Monitor

**Live app: [rheum-car-t-trial-monitor.streamlit.app](https://rheum-car-t-trial-monitor.streamlit.app)**  
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19713049.svg)](https://doi.org/10.5281/zenodo.19713049)

An interactive dashboard that tracks CAR-T and related cell-therapy clinical
trials for rheumatologic and immune-mediated diseases, sourced from the public
ClinicalTrials.gov registry.

The app provides a filtered trial list, classification across six axes
(disease entity, trial design, antigen target, cell-therapy modality, product
type, sponsor type), geographic mapping (global + Germany-specific),
publication-ready figures with provenance-tagged CSV exports, an auto-
generated methods section, and an inter-rater κ validation study.

Designed as a research and educational resource — **not** a medical,
regulatory, or decision-support tool.

---

## Tab structure

The app has 7 top-level tabs:

| Tab | What it does |
|---|---|
| **Overview** | KPI strip (total trials, open, enrolled, top antigen) · top movers (YoY change) · recently-added trials · disease-hierarchy sunburst (3-ring: clinical specialty → indication → antigen target) · PRISMA flow expander |
| **Geography / Map** | World choropleth of trial counts · open-sites layer · regional aggregates (Asia / Europe / Americas / Oceania) · country leaderboard · country-emergence scatter (year of first trial per country) · multi-country trials list · Germany-specific city + site drilldown |
| **Data** | Full filterable trial table with row-click drilldown to a per-trial classification rationale + suggest-correction form |
| **Deep Dive** | 5 axis-pages (see below) |
| **Publication Figures** | 11 publication-ready figures (Fig 1-11) with provenance-tagged CSV exports |
| **Methods & Appendix** | PRISMA ledger · auto-generated methods text · ontology table · sub-family routing audit · curation-loop CSV download · validation-sample export |
| **About** | Dashboard description · contact · auto-populated citation block |

### Deep Dive sub-tabs

| Sub-tab | Contents |
|---|---|
| **By disease** | Disease landscape figures (Disease × Antigen heatmap, phase composition, trial-age vs status, top-3 sponsor share, age-group coverage with paediatric-gap callouts) · per-disease drilldown · side-by-side disease/target comparator |
| **By target** | Antigen landscape (Target × Disease heatmap, emergence timeline, phase composition) · per-target drilldown (timeline + enrollment box) · per-named-product pipeline view |
| **By sponsor** | Sponsor-type aggregate (Industry / Academic / Government / Other) · sponsor type × disease heatmap · phase composition by sponsor type · drill into a specific sponsor (full portfolio: phases, diseases, targets, timeline) |
| **By geography** | Country leaderboard · country × disease heatmap · phase composition by country · drill into a specific country (top diseases + top antigens) |
| **By time** | Annual trial starts (selectable colour axis: disease / target / family / sponsor type) · cumulative active trials · cohort × phase % · top-10 sponsor activity timeline · phase-progression Sankey |

### Sidebar display options

- **Chart export format** — every chart's modebar download button emits PNG
  (slides, 5× resolution) or SVG (vector for journal submission / Illustrator
  post-editing). Toggle in the sidebar's `Display options` expander.
- **High-contrast palette** — switches every entity-coloured chart from the
  default family-clustered palette (rheum-blue, neuro-violet, other-stone) to
  a Tableau-20-based palette where every disease gets a maximally distinct
  colour. Useful for dense charts where shade-similarity makes specific
  entities hard to distinguish.

---

## Features

- **Live pull** from ClinicalTrials.gov API v2 or reproducible **frozen snapshots**
- **Multi-axis classification pipeline**:
  - **Disease entity** — 10 strict-vocab labels (SLE, SSc, Sjogren, CTD_other,
    IIM, AAV, RA, IgG4-RD, Behcet, cGVHD) plus generic `Basket/Multidisease`
    and `Other immune-mediated`. Multi-disease basket trials get a per-cluster
    routing: rheum-only → "Rheumatology basket" wedge in the rheum-blue
    cluster; neuro-only → rolled into the Neurologic autoimmune family wedge;
    mixed-family → slate "Multidisease basket" wedge
  - **OIM-cluster sub-classification** — for trials whose strict vocab is
    "Other immune-mediated", a second-pass classifier assigns one of 7 neuro
    clusters (MS, NMOSD, CIDP, MOGAD, AIE, Myasthenia, Stiff-person) or
    sub-family (Cytopenias, Glomerular, Endocrine, Dermatologic, GVHD).
    Pure-OIM multi-disease trials are promoted to baskets even when no strict
    rheum entity matches.
  - **15 antigen-target categories** — CD19, BCMA, CD20, CD70, CD6, CD7, BAFF,
    BAFF-R, dual / combinatorial variants (CD19/BCMA, CD19/CD20, CD19/BAFF,
    BCMA/CD70), platform labels (CAR-NK, CAAR-T, CAR-Treg), plus `CAR-T_unspecified`
    fallback. Includes a ligand-CAR convention: BAFF-CAR designs route to
    `BAFF-R` (the receptor on the target cell) rather than `BAFF` (the ligand).
  - **8 cell-therapy modalities** — Auto / Allo CAR-T, CAR-T (unclear), CAR-γδ
    T, CAR-NK, CAR-Treg, CAAR-T, In vivo CAR
  - **Sponsor classification** — Industry / Academic / Government / Other,
    via `leadSponsor.class` + name-based heuristics
  - **Trial design** — Single disease vs Basket/Multidisease (≥2 distinct
    entities or generic broad-basket phrasing)
- **Three-layer validation loop**:
  - Locked benchmark of 21 hand-curated trials with per-axis F1 floors
    (`tests/test_benchmark.py`)
  - Independent-LLM cross-validation with per-provider Cohen's κ across
    Gemini / OpenAI / Groq / Anthropic (`scripts/validate_independent_llm.py`)
  - Snapshot-to-snapshot reclassification diff (`scripts/snapshot_diff.py`)
  - **Inter-rater κ validation study** — standalone Streamlit app at
    `validation_study/app.py` where two raters independently classify a locked
    100-trial sample on 6 axes (Disease family, Disease entity, Trial design,
    Target category, Product type, Sponsor type); Cohen's κ between raters is
    the primary outcome
- **LLM-assisted classification** via `validate.py` — Claude-powered
  second-opinion tool that writes persistent per-trial overrides to
  `llm_overrides.json`, picked up automatically by the pipeline
- **Curation-loop infrastructure** — the dashboard exports a structured
  `curation_loop.csv` (CURATION_LOOP_V1 format) listing every trial flagged
  unclear on disease / target / product, with controlled-vocab header so
  human / LLM reviewers can propose patches to `config.py` / `pipeline.py`
  / `llm_overrides.json`. Companion CLI: `scripts/audit_classification.py`.
  Walkthrough prompts: `docs/internal/CLASSIFICATION_AUDIT_PROMPT.md` (broad)
  and `docs/internal/NAMED_PRODUCT_AUDIT_PROMPT.md` (target-only)
- **11 publication figures** (Fig 1-11) with CSV exports that include snapshot
  date, filter state, and source URL as `#`-prefixed provenance headers:
  - Fig 1 — Temporal trends by disease entity
  - Fig 2 — Phase distribution by sponsor sector
  - Fig 3 — Geographic distribution
  - Fig 4 — Trial enrollment characteristics (4a-4d sub-panels)
  - Fig 5 — Disease distribution (trials + planned patients)
  - Fig 6 — Antigen target distribution
  - Fig 7 — Cell-therapy modality distribution and evolution
  - Fig 8 — Antigen × Modality maturity matrix
  - Fig 9 — Basket-disease co-occurrence triangle
  - Fig 10 — Paediatric coverage gap by disease entity
  - Fig 11 — Sponsor concentration (top-3 lead-sponsor share)
- **PRISMA-style flow** as a financial-statement-style ledger documenting
  study selection (5-stage: identified → after dedup → after hard-excl →
  after LLM-curation → after indication-filter → included)
- **Auto-generated methods section** with live counts, version pins, and
  cross-references to specific figures
- **Data-quality panel** surfacing missing / ambiguous classifications
- **Community-flag system** — GitHub Issues + auto-label workflow + 🚩 prefix
  on community-flagged trials + per-trial suggest-correction form
- **Germany-specific view** (site-level map, city breakdown, enrolling centers)
- Full **Impressum, Datenschutz, and citation block** for academic use

---

## Quick start

### Local

```bash
git clone https://github.com/<your-user>/Rheumatology-CAR-T-Trials-Monitor-.git
cd Rheumatology-CAR-T-Trials-Monitor-
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Streamlit Community Cloud

1. Fork or push this repository to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app from
   the repo, with `app.py` as the entry point.
3. (Optional) Add `ANTHROPIC_API_KEY` under **Secrets** if you want to run the
   LLM validation tool from the deployed instance. For most workflows, running
   `validate.py` locally is preferable.
4. Optional: add `VALIDATION_TOKENS` (JSON map of token → rater identity) to
   enable the inter-rater κ validation study at `validation_study/app.py`.

---

## Data source

All trial data comes from [ClinicalTrials.gov API v2](https://clinicaltrials.gov/api/v2/studies).
The query targets autoimmune and immune-mediated indications and excludes
oncology / haematologic malignancy trials via a curated keyword list plus a
hard-exclusion NCT ID list (see `config.py`).

---

## Classification strategy

Trials are classified in layers, from most durable to most specific:

1. **`config.py` keyword tables** — `DISEASE_ENTITIES`,
   `OTHER_IMMUNE_MEDIATED_TERMS`, `CAR_SPECIFIC_TARGET_TERMS`,
   `ALLOGENEIC_MARKERS`, `AUTOL_MARKERS`. Shared, deterministic.
2. **OIM-cluster terms** — `_OIM_CLUSTERS` in `pipeline.py` provides
   second-pass disease-cluster detection for non-rheum autoimmune diseases
   (MS, NMOSD, CIDP, MOGAD, AIE, Myasthenia, Stiff-person, Pemphigus,
   T1D, ITP, AIHA, IgAN, Membranous, FSGS). Used for basket detection
   (≥2 distinct OIM clusters → Basket/Multidisease) and L2 sub-family
   labelling in the sunburst.
3. **Named-product lookup tables** — `NAMED_PRODUCT_TARGETS` and
   `NAMED_PRODUCT_TYPES` resolve specific products (e.g. `kn5601`,
   `ytb323`, `rapcabtagene autoleucel`) when the abstract text alone is
   insufficient.
4. **LLM overrides** — per-trial JSON entries in `llm_overrides.json` produced
   by `python validate.py`. Applied in `pipeline._classify_disease()` before
   keyword matching; trials are flagged with `LLMOverride = True` in the
   dataframe and surfaced in the Data Quality panel.
5. **Hard-exclusion list** — `HARD_EXCLUDED_NCT_IDS` in `config.py` for trials
   that should never appear.

### Basket sub-classification

Basket / multi-disease trials are routed to one of three families based on
their constituent entities:

- **Rheumatology basket** — all constituents are classical rheum (CTD / IA /
  Vasculitis), no non-rheum text signals. Renders in the rheum-blue cluster.
- **Neurology basket** — exclusively neuro OIM clusters (MS / NMOSD / CIDP /
  MOGAD / AIE / Myasthenia / Stiff-person), no other-family entities. Rolls
  into the Neurologic autoimmune family wedge.
- **Multidisease basket** — true mixed-family baskets (≥2 distinct families).
  Slate-grey wedge in the sunburst.

The detectors live in `pipeline.py:is_classical_rheum_basket` and
`pipeline.py:is_neuro_basket`; tested in
`tests/test_classical_rheum_basket.py` (37 tests covering qualifying
baskets, disqualifiers, and text-signal guards).

### Running the LLM validator

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Validate up to 30 borderline trials (default)
python validate.py

# Validate a specific trial
python validate.py --nct NCT06123456

# Expand the batch
python validate.py --limit 100
```

Results merge into `llm_overrides.json` — previously validated trials are
preserved across runs. The next app load picks up the overrides automatically.

### Audit workflow (curation loop)

For systematic improvement of borderline classifications:

```bash
# Generate a CURATION_LOOP_V1 worklist from the latest snapshot
python3 scripts/audit_classification.py

# → audit_output/curation_loop_<date>.csv  (one row per trial flagged
#   unclear on Disease / Target / Product, with controlled-vocab header)
```

Then open `docs/internal/CLASSIFICATION_AUDIT_PROMPT.md` in a fresh
Claude session and walk Q1-Q7 per trial. The prompt enforces a strict
no-downgrade acceptance gate: every flip must be from sentinel/generic
to specific, never the reverse.

---

## Snapshots

The app can save reproducible snapshots of a live pull:

1. Use the sidebar **Save snapshot** button in live mode.
2. The snapshot (trials.csv, sites.csv, prisma.json, metadata.json) is
   written to `snapshots/<YYYY-MM-DD>/`.
3. Switch the sidebar source toggle to **Frozen snapshot** to reload any
   previous snapshot. Useful for locking figure data for a publication
   submission.

Publication CSVs include a `#`-prefixed header block with snapshot date,
filter state, row count, and API source — readable via
`pd.read_csv(path, comment="#")`.

---

## Repository layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit UI, filters, tabs, figures, exports |
| `pipeline.py` | API fetch, classification, basket detection, PRISMA, snapshot I/O |
| `config.py` | Disease / target / product / exclusion keyword tables |
| `validate.py` | Standalone Claude-powered validation tool |
| `llm_overrides.json` | Generated per-trial classification overrides |
| `snapshots/<date>/` | Reproducible frozen datasets |
| `tests/` | Pytest suite (175+ tests covering classifier, pipeline I/O, basket detection, validation κ, flag consensus, moderator helpers) |
| `validation_study/app.py` | Standalone inter-rater κ validation Streamlit app |
| `scripts/` | Audit, snapshot diff, and curation-loop helpers |
| `docs/internal/` | Self-contained prompts for cross-app sync, audit walkthroughs, and curation loops |
| `requirements.txt` | Pinned Python dependencies |
| `LICENSE` | MIT |

---

## Citation

If you use this dashboard in scientific work, please cite:

> Jeong P. CAR-T Rheumatology Trials Monitor (version `<sha>`) [Internet].
> Klinik I für Innere Medizin, Klinische Immunologie und Rheumatologie,
> Universitätsklinikum Köln; `<year>` [cited `<YYYY-MM-DD>`].
> Data snapshot: `<date>`. Source: ClinicalTrials.gov API v2.
> DOI: 10.5281/zenodo.19713049.

The live app surfaces an auto-populated citation block under the **About** tab.

---

## License

[MIT](./LICENSE). Copyright (c) 2026 Peter Jeong, Universitätsklinikum Köln.

---

## Contact

**Peter Jeong**
Universitätsklinikum Köln
Klinik I für Innere Medizin — Klinische Immunologie und Rheumatologie
✉️ [peter.jeong@uk-koeln.de](mailto:peter.jeong@uk-koeln.de)
