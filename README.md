# CAR-T Rheumatology & Autoimmune Trials Monitor

**Live app: [rheum-car-t-trial-monitor.streamlit.app](https://rheum-car-t-trial-monitor.streamlit.app)**  
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19713049.svg)](https://doi.org/10.5281/zenodo.19713049)

An interactive dashboard that tracks CAR-T and related cell-therapy clinical
trials for rheumatologic and autoimmune diseases, sourced from the public
ClinicalTrials.gov registry.

The app provides a filtered trial list, classification across six axes
(disease entity, trial design, antigen target, cell-therapy modality, product
type, sponsor type), geographic mapping, 11 publication-ready figures with
provenance-tagged CSV exports, an auto-generated Methods section with
explicit limitations, six Deep Dive axis-pages (By disease · By antigen ·
By product · By sponsor · By time · Compare) supporting click-row drilldown
from landscape tables to focused views, and an inter-rater κ validation
study.

Designed as a research and educational resource — **not** a medical,
regulatory, or decision-support tool.

---

## Tab structure

The app has 7 top-level tabs:

| Tab | What it does |
|---|---|
| **Overview** | KPI strip (filtered trials · open / recruiting · planned enrollment · top target) · disease-hierarchy sunburst (3-ring: clinical specialty → indication → antigen target) · family headline tiles · **Recently updated trials** panel (timeframe pills incl. All-time; family + status filters; click-row drilldown) · snapshot-diff expander vs previous snapshot |
| **Geography / Map** | World choropleth of trial counts · open-sites layer · country leaderboard · country-emergence scatter (year of first trial per country) · multi-country trials list · per-country drilldown (top diseases + top antigens as sparkbars, site-level map, city breakdown) |
| **Data** | Full filterable trial table with row-click drilldown to a per-trial classification rationale + suggest-correction form |
| **Deep Dive** | 6 axis-pages (see below) — landscape view by default; click any landscape-table row to focus, or use the pickers |
| **Publication Figures** | 11 publication-ready figures (Fig 1-11) with provenance-tagged CSV exports |
| **Methods & Appendix** | PRISMA ledger · auto-generated methods text · ontology table · sub-family routing audit · curation-loop CSV download · validation-sample export · explicit limitations section |
| **About** | Dashboard description · contact · auto-populated citation block |

### Deep Dive sub-tabs

| Sub-tab | Contents |
|---|---|
| **By disease** | Disease landscape figures (Disease × Antigen heatmap, phase composition stacked bar, open-trial age watchlist — directly surfaces stalled-enrolment trials) · per-disease focused view: 3-chart row (phase mix, sponsor-type donut, top countries), sparkbar lists for antigen targets + product types, trial table with row-click drilldown |
| **By antigen** | Antigen landscape (Target × Disease heatmap, emergence timeline + phase composition with shared y-axis, top-antigens table with `# Products` column) · per-antigen focused view: 4-tile metric strip, 3-chart row (diseases, phases, annual trial starts), **Products targeting this antigen** portfolio table, sparkbar lists, top sponsors, trial drilldown |
| **By product** | Per-named-product pipeline view: each row a CAR-T product (KYV-101, CABA-201, …) with sponsor, modality, primary target, indications, furthest phase, trial count. Click a product row → that product's full trial list. Shared-axis phase × enrollment landscape chart |
| **By sponsor** | Sponsor-type landscape (Industry / Academic / Government / Other) with click-row drilldown · per-sponsor focused view: 4-tile metric strip (trials / distinct products / distinct diseases / open), **product portfolio table** (one row per product the sponsor runs, with modality / antigen / diseases / phases / years), aggregate sparkbar lists, trial table sorted by Product → Phase → StartYear |
| **By time** | Annual trial starts (selectable colour axis: disease / target / family / sponsor type) · cumulative active trials · cohort × phase % heatmap · year-over-year movers (risers / fallers) |
| **Compare** | Paired side-by-side comparator with shared scales — pick any two diseases, antigens, modalities, sponsors, or products. Shows compact paired metric strip, grouped phase-mix bars (shared y-axis), paired horizontal 100%-stacked sponsor-type bars, and paired sparkbar cross-axis lists (e.g. sponsor compare → disease coverage + antigen coverage) |

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
  - **Antigen-target categories** — CD19, CD20, CD22, BCMA, CD70, BAFF / BAFF-R,
    CD6, CD7, plus arbitrary-arity multi-target labels (`CD19/BCMA dual`,
    `CD19/CD22/BCMA triple`, `CD19/CD20/CD22 multi`, etc.) generated by a
    collect-then-format pattern that scales to any combination, and platform
    labels (CAR-NK, CAAR-T, CAR-Treg) plus `CAR-T_unspecified` / `Other_or_unknown`
    fallbacks. Ligand-CAR convention: BAFF-CAR designs route to `BAFF-R` (the
    receptor on the target cell) rather than `BAFF` (the ligand). Adding a new
    antigen is a one-line addition to `CAR_SPECIFIC_TARGET_TERMS`.
  - **8 cell-therapy modalities** — Auto / Allo CAR-T, CAR-T (unclear), CAR-γδ
    T, CAR-NK, CAR-Treg, CAAR-T, In vivo CAR
  - **Sponsor classification** — Industry / Academic / Government / Other,
    via `leadSponsor.class` + name-based heuristics
  - **Trial design** — Single disease vs Basket/Multidisease (≥2 distinct
    entities or generic broad-basket phrasing)
- **Multi-layer validation infrastructure**:
  - Locked benchmark of 21 hand-curated trials with per-axis F1 floors
    (`tests/test_benchmark.py`)
  - Classifier unit tests (187 tests; `tests/test_classifier.py` locks
    every rule including multi-target arity, CD22 detection, CAR-NK Allo
    default, named-product priority, BAFF-R supersedes BAFF, word-boundary
    detection for CD6/CD7)
  - **Product-consistency audit** (`scripts/audit_product_consistency.py`) —
    scans the current snapshot for named products with divergent
    TargetCategory across their trials, flagging classifier drift or
    new genuinely-dual-target products needing a `NAMED_PRODUCT_TARGETS`
    update
  - Independent-LLM cross-validation with per-provider Cohen's κ across
    Gemini / OpenAI / Groq / Anthropic (`scripts/validate_independent_llm.py`)
  - Snapshot-to-snapshot reclassification diff via the Overview tab's
    "Changes since previous snapshot" expander (both sides are
    post-processed so the diff reflects real day-over-day changes, not
    static in-memory reclassification deltas)
  - **Inter-rater κ validation study** — standalone Streamlit app at
    `validation_study/app.py` where two raters independently classify a locked
    100-trial sample on 6 axes (Disease family, Disease entity, Trial design,
    Target category, Product type, Sponsor type); Cohen's κ between raters is
    the primary outcome
  - **App smoke test** (`tests/test_app_smoke.py`) — boots the Streamlit
    script via `AppTest` against a pinned snapshot, asserts no exceptions,
    all tabs render, the KPI strip is present, and the sidebar reset
    button is wired
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

Antigen + product-type classification runs as a strict priority chain, applied
in this order at both snapshot-build time AND at every app load (so
code-level classifier fixes apply immediately without waiting for a nightly
rebuild — see "Re-classification on load" below):

1. **LLM overrides** — per-trial JSON entries in `llm_overrides.json` produced
   by `python validate.py` (Claude-powered) or curated by hand for ambiguous
   trials (e.g. dual-arm protocols testing two products of different
   mechanism). Trials are flagged with `LLMOverride = True`.
2. **Named-product lookup** — `NAMED_PRODUCT_TARGETS` /
   `NAMED_PRODUCT_TYPES` in `config.py` resolve known canonical CAR-T
   products (KYV-101, CABA-201, CT1192, YTB323, …) directly to their
   documented antigen / modality. This is the **primary** resolver, not a
   fallback — keyword matching is layered beneath it. The priority avoids
   comedication mentions (e.g. "Anti-CD20 mAB" administered alongside a
   KYV-101 CD19 CAR-T) being misread as a dual-target CAR-T construct.
3. **Explicit text-pattern detection** — `CAR_SPECIFIC_TARGET_TERMS` plus
   bare-token matches over a closed vocabulary (CD19, CD20, CD22, BCMA,
   CD70, BAFF-R / BAFF, CD6, CD7). All detected antigens are collected
   into a sorted list and emitted as a multi-target label
   (`"CD19"` / `"CD19/BCMA dual"` / `"CD19/CD22/BCMA triple"` / `"… multi"`)
   — this replaced an earlier hardcoded if-chain that handled only specific
   dual pairs and silently dropped third antigens. CAR-NK products default
   to Allogeneic when no explicit autologous marker is present (the
   field-standard default for NK-cell CAR products in autoimmune).
4. **CAR-core fallback** — `CAR-T_unspecified` when CAR-related terms are
   present but no antigen is identifiable.
5. **Hard-exclusion list** — `HARD_EXCLUDED_NCT_IDS` in `config.py` for trials
   that should never appear in the dataset (regardless of keyword matching).

### Disease classification

Trials are mapped to one of the 10 strict-vocab disease entities (SLE / SSc /
Sjogren / CTD_other / IIM / AAV / RA / IgG4-RD / Behcet / cGVHD), the generic
`Basket/Multidisease` category (for trials enrolling ≥2 distinct systemic
entities or registered with generic broad-basket phrasing), or
`Other immune-mediated` (rolled-up bucket for non-classical-rheum autoimmune).
An L2 sub-classifier (`_OIM_CLUSTERS` in `pipeline.py`) routes "Other
immune-mediated" trials into one of seven neurologic clusters (MS, NMOSD,
CIDP, MOGAD, AIE, Myasthenia, Stiff-person) or a non-neuro sub-family
(Cytopenias, Glomerular, Endocrine, Dermatologic, GVHD). Neurologic-cluster
matches are **promoted to their own L1 family** (Neurologic autoimmune),
shown as a distinct violet wedge in the sunburst alongside the classical
rheum cluster.

### Re-classification on load

The classifier (`_assign_target` + `_assign_product_type` in `pipeline.py`) is
executed at snapshot-build time AND again at every app load inside
`_post_process_trials`. The saved snapshot's `TargetCategory`, `TargetSource`,
`ProductType`, and `ProductTypeSource` columns are advisory — overwritten in
memory whenever the rule-based classifier output differs from the saved value.
This guarantees that code-level classifier improvements take effect
immediately, without waiting for the nightly snapshot rebuild. The canonical
source of truth for a trial's classification is the **code + raw data at view
time**, not the saved CSV. For frozen reproducibility, pin a snapshot AND
check out the code at that date (the classifier is deterministic for given
code + input).

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
| `tests/` | Pytest suite (187 tests covering classifier rules — including multi-target arity, CD22 detection, CAR-NK Allo default, named-product priority — pipeline I/O, basket detection, validation κ, flag consensus, moderator helpers, plus a `streamlit.testing.v1.AppTest` smoke test for cold-boot regression) |
| `validation_study/app.py` | Standalone inter-rater κ validation Streamlit app |
| `scripts/` | Audit, snapshot diff, and curation-loop helpers |
| `docs/internal/` | Self-contained prompts for cross-app sync, audit walkthroughs, and curation loops |
| `requirements.txt` | Pinned Python dependencies |
| `LICENSE` | MIT |

---

## Citation

If you use this dashboard in scientific work, please cite:

> Jeong P. CAR-T Rheumatology & Autoimmune Trials Monitor (version `<sha>`) [Internet].
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
