# CAR-T Rheumatology Trials Monitor

An interactive dashboard that tracks CAR-T and related cell-therapy clinical
trials for rheumatologic and immune-mediated diseases, sourced from the public
ClinicalTrials.gov registry.

The app provides a filtered trial list, classification by disease entity,
antigen target, cell-therapy modality, and product type, geographic mapping
(global + Germany-specific), publication-ready figures with provenance-tagged
CSV exports, and an auto-generated methods section.

Designed as a research and educational resource — **not** a medical,
regulatory, or decision-support tool.

---

## Features

- **Live pull** from ClinicalTrials.gov API v2 or reproducible **frozen snapshots**
- **Classification pipeline** covering 9 systemic autoimmune diseases, 12+ antigen-target
  categories, and 8 cell-therapy modalities (Auto / Allo CAR-T, CAR-NK, CAR-γδ T,
  CAAR-T, CAR-Treg, in vivo CAR, plus an explicit "unclear" bucket)
- **LLM-assisted classification** via `validate.py` — a standalone Claude-powered
  second-opinion tool that writes persistent per-trial overrides to
  `llm_overrides.json`, picked up automatically by the pipeline
- **Publication figures** (7 figures with CSV exports that include snapshot date,
  filter state, and source URL as `#`-prefixed provenance headers)
- **PRISMA-style flow** documenting study selection
- **Auto-generated methods section** with live counts
- **Data-quality panel** surfacing missing / ambiguous classifications
- **Curation loop** CSV for human-in-the-loop refinement
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
2. **Named-product lookup tables** — `NAMED_PRODUCT_TARGETS` and
   `NAMED_PRODUCT_TYPES` resolve specific products (e.g. `kn5601`,
   `ytb323`, `rapcabtagene autoleucel`) when the abstract text alone is
   insufficient.
3. **LLM overrides** — per-trial JSON entries in `llm_overrides.json` produced
   by `python validate.py`. Applied in `pipeline._classify_disease()` before
   keyword matching; trials are flagged with `LLMOverride = True` in the
   dataframe and surfaced in the Data Quality panel.
4. **Hard-exclusion list** — `HARD_EXCLUDED_NCT_IDS` in `config.py` for trials
   that should never appear.

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

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI, filters, tabs, figures, exports |
| `pipeline.py` | API fetch, classification, PRISMA, snapshot I/O |
| `config.py` | Disease / target / product / exclusion keyword tables |
| `validate.py` | Standalone Claude-powered validation tool |
| `llm_overrides.json` | Generated per-trial classification overrides |
| `snapshots/<date>/` | Reproducible frozen datasets |
| `requirements.txt` | Pinned Python dependencies |
| `LICENSE` | MIT |

---

## Citation

If you use this dashboard in scientific work, please cite:

> Jeong P. CAR-T Rheumatology Trials Monitor (version `<sha>`) [Internet].
> Klinik I für Innere Medizin, Klinische Immunologie und Rheumatologie,
> Universitätsklinikum Köln; `<year>` [cited `<YYYY-MM-DD>`].
> Data snapshot: `<date>`. Source: ClinicalTrials.gov API v2.

The live app surfaces an auto-populated citation block under the **About** tab.
Tagging a GitHub release and linking the repository to
[Zenodo](https://zenodo.org/account/settings/github/) will produce a permanent
DOI for each release.

---

## License

[MIT](./LICENSE). Copyright (c) 2026 Peter Jeong, Universitätsklinikum Köln.

---

## Contact

**Peter Jeong**
Universitätsklinikum Köln
Klinik I für Innere Medizin — Klinische Immunologie und Rheumatologie
✉️ [peter.jeong@uk-koeln.de](mailto:peter.jeong@uk-koeln.de)
