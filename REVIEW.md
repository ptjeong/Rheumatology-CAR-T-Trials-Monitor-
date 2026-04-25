# Rheumatology CAR-T Trials Monitor — comprehensive review

Snapshot of state on 2026-04-25. 284 included trials, 1,530 sites, 39
countries. 49/49 unit tests green. 12/12 benchmark axes at 1.000 macro-F1
on the live snapshot. Three-layer validation infrastructure (locked
benchmark, independent-LLM cross-validation, snapshot-diff blast-radius
check) is coded but only the benchmark layer has actually run.

## 1. Executive summary

The classifier and UI are in shippable shape and the validation scaffolding
is genuinely good — better, on most axes, than a typical academic dashboard.
What is missing for a credible preprint is the *evidence* that the
validation works: independent-LLM κ has never been computed; the locked
benchmark is too narrow (12 trials, 9 entities, no negatives) to plausibly
backstop the broader vocabulary the pipeline emits; one real classifier
bug (CTD_other excluded from systemic-basket detection) is silently
mis-labelling multi-disease trials.

**Top three risks (publication horizon):**
1. CTD_other systemic-basket bug (`pipeline.py:164`) — multi-disease trials
   pairing CTD_other with SLE/SSc silently classify as single-disease.
2. No CI (`.github/workflows/` missing). A regression can ship — there is
   no automated gate between local pytest and `git push origin main`.
3. Independent-LLM κ has never been computed (`reports/` does not exist;
   `llm_overrides.json` is empty `[]`). The methods section of the preprint
   cannot cite cross-vendor agreement metrics that do not exist on disk.

**Top three wins to bank:**
1. Source-tagging on `_assign_target` and `_assign_product_type`
   (`pipeline.py:250–318`, `321–397`) feeds a transparent confidence rubric
   — this is more mature than the companion onc app.
2. Sub-family L2 + neuro L1 promotion + audit panel split
   (`app.py:225–351`, `4427–4481`) is genuinely novel; the onc app should
   borrow it.
3. Aesthetic discipline (`app.py:517–902`, all `box-shadow: none`;
   `.streamlit/config.toml`) holds — flat NEJM look is intact and the
   audit added two weeks ago did not regress it.

## 2. Per-dimension findings

### Classifier quality — *Concern*

- **CTD_other excluded from `_SYSTEMIC_DISEASES`** (`pipeline.py:164`).
  `_classify_disease` requires ≥2 entries in `_SYSTEMIC_DISEASES` to flip
  TrialDesign to Basket/Multidisease. CTD_other matches generic
  connective-tissue terms and overlaps SLE/SSc/IIM trials in the live
  snapshot (NCT07490041 matches `['CTD_other', 'SLE']` but lands in
  Single-disease/CTD_other because CTD_other is not counted as systemic).
  Two CTD_other trials in the snapshot — small blast radius today, but the
  rule is wrong.
- **`_compute_confidence` is partial signal** (`pipeline.py:399–424`).
  Confidence rewards (target × product-type) coherence but ignores
  named-product strength and basket-design robustness. 15 low-confidence
  trials (5.3%) skew toward basket trials with named products
  (NCT06822881 CT1190B is "low" despite a curated platform name).
  Verdict: usable as a coarse triage signal; not safe as an inclusion gate.
- **Validator closed-vocab does not constrain TargetCategory**
  (`scripts/validate_independent_llm.py:83–91`). DiseaseEntity and
  ProductType are enum-locked; TargetCategory is constrained only in the
  prompt prose. A reviewer that returns `cd19` (lower case) or
  `CD19/CD20-dual` (hyphen) registers as disagreement and inflates
  reported κ noise.
- **Coverage of `OTHER_IMMUNE_MEDIATED_TERMS` is reasonable** for current
  data (`config.py:109–159`). Verified: myasthenia gravis, MS, NMOSD,
  pemphigus, Graves, ITP, AIHA all match. AIHA has only the singular
  variant; "Cold Autoimmune Hemolytic Anemia" (NCT07091370) matches via
  the substring path but a curated synonym list would be cleaner.

**Recommendations:** add CTD_other to `_SYSTEMIC_DISEASES`; either replace
or rewrite `_compute_confidence` to a multi-factor score (currently used
in the audit panel but not gated on); enum-lock `TargetCategory` in the
validator's `ALLOWED_VALUES`.

### Scientific rigor & reproducibility — *Concern*

- **PRISMA accounting is internally consistent.**
  `snapshots/2026-04-25/prisma.json`: 362 fetched → 35 hard-excluded →
  43 indication-excluded → 284 included. Accounting reconciles.
- **Snapshot determinism is partial.** `save_snapshot` writes a
  `created_utc` timestamp into `metadata.json` (`pipeline.py:876`) so
  snapshots are not byte-identical across runs even when upstream data
  is identical. CSV row order is preserved from the API response and is
  not re-sorted, so order can drift if CT.gov pagination shifts.
- **LLM-override audit trail is empty.** `llm_overrides.json` is `[]`
  (2 bytes). The override path in `_classify_disease` (`pipeline.py:187–
  191`) is wired but unused. Either no curation has run on this branch,
  or the file was reset; either way the `LLMOverride` column is `False`
  for all 284 trials.
- **Benchmark coverage is too narrow.** 12 trials covering 9 entities,
  no `Behcet`, no `cGVHD`, no `CTD_other`, no `Unclassified` negative
  case (`tests/benchmark_set.csv`). All 11 testable trials are
  Autologous/Allogeneic/In-vivo — no `Unclear` ProductType. CD19
  dominates targets (9 of 12). A regression that downgraded a known
  CD20 trial to "CAR-T_unspecified" might pass.
- **Independent-LLM validation has never been run** on this snapshot
  (`reports/` does not exist; `scripts/validate_independent_llm.py:326`
  default `--out` writes there).

**Recommendations:** add a deterministic sort to `save_snapshot` (sort
by NCTId before write); strip the timestamp from `metadata.json` or move
it to a separate `.runinfo` file that is .gitignored; broaden the
benchmark to ~25 trials including all 9 disease entities + Behcet +
cGVHD + an Unclassified negative + at least one Unclear ProductType;
actually run the independent-LLM validator and commit the report so the
methods section can cite it.

### Data freshness & pipeline robustness — *OK*

- **Fetch path is single-shot, no retry** (`pipeline.py:631–663`). 30s
  timeout; HTTPError raised on non-200; mid-pagination 5xx loses earlier
  pages. CT.gov is reliable in practice but a transient 502 today wipes
  the run.
- **Geo backfill is manual, ~1.6% incomplete.**
  `scripts/backfill_site_geo.py` is run on demand, not chained to
  `save_snapshot`. 25 of 1,530 sites in the current snapshot lack
  Latitude/Longitude.
- **`build_all_from_api` does no incremental fetch.** Every refresh is a
  full re-fetch of all 362 raw studies. Acceptable at this scale; not at
  10× scale.

**Recommendations:** wrap the fetch loop in `tenacity` or a hand-rolled
exponential backoff with 3 retries on 5xx and ConnectionError; chain
`backfill_site_geo` into `save_snapshot` so a fresh snapshot is always
geo-complete; capture the raw API response page-by-page to a temp
directory before flattening, so a partial fetch can resume.

### UX & analytics — *OK*

- **Filters round-trip via URL.** `_seed_filter_from_query` /
  `_sync_filters_to_query` (`app.py:1309–1345`). Deep links work.
- **Hot-path row-wise apply on every filter change**
  (`app.py:1826–1827`). Sunburst L2/L3 derivation calls `df_filt.apply(
  ..., axis=1)` twice per filter widget event. At 284 trials this is
  ~2 ms; at 2,000 it is noticeable.
- **Mobile is not supported.** `st.set_page_config(layout="wide")`
  (`app.py:39`); fixed column ratios (`[0.65, 0.35]`, `[1.15, 0.85]`).
  No `use_container_width=True` on charts. Sidebar fights for space on
  narrow viewports.
- **Color-only encoding in stacked-area Fig 1** (`app.py:3149`). Thin
  slivers (1-trial entities) rely on legend + hover only; for CVD users
  emerald (#059669) / teal (#0d9488) / cyan (#0891b2) in
  `_MODALITY_COLORS` are close in hue.
- **No alt-text / aria-labels** on Plotly figures. Static SVG exports
  for the preprint will fail accessibility review.
- **Per-trial classification rationale is not exposed.** The Data tab
  trial detail panel shows conditions/interventions/summary
  (`app.py:2631–2639`) and an `LLMOverride` banner, but never says "we
  classified this as SLE because the title contained X". Auditability
  hole.
- **One emoji** (`app.py:41`, page icon `🧬`). Tolerable as a favicon.

**Recommendations:** vectorise sunburst L2/L3 derive with a single
boolean-mask pass (model on `_add_modality_vectorized`,
`app.py:921–998`); test the modality palette through a deutan/protan
simulator and adjust the cyan/teal/emerald axis; add a "How was this
classified?" disclosure in the trial detail panel surfacing
`TargetSource` / `ProductTypeSource` / matched terms.

### Code health — *OK*

- **app.py is 5,031 lines.** Not unreasonable for a single-file
  Streamlit dashboard, but the file mixes CSS, palettes, classifier
  helpers (`_modality`, `_disease_family`, `_subfamily`, etc.), filter
  wiring, and figure rendering. Extracting `app/style.py`,
  `app/taxonomy.py`, `app/figures.py` would not change behaviour and
  would make the next contributor's job tractable.
- **26 `.apply(...)` calls** across `app.py`. Three are in hot paths
  (`app.py:1613`, `1826`, `1827`); the rest are conditional (Deep
  Dive / Methods tab) and acceptable.
- **No mutating-cached-input bugs found.** Cache discipline is correct
  for `load_live`, `load_frozen`, `_post_process_trials`.
- **`pipeline.py` and `app.py` redundantly define disease taxonomy.**
  `_DISEASE_TERMS` lives inline at `pipeline.py:132–160`; `config.py`
  has `DISEASE_ENTITIES`. Both target the same vocabulary but the maps
  are not generated from a single source. Risk: the next entity edit
  touches one and not the other.

**Recommendations:** consolidate to a single source of truth in
`config.py`; introduce `DISEASE_TERMS` as the authoritative map and
generate any pipeline-side normalised view from it. Defer the app.py
extraction until after the preprint — disruptive at this stage.

### Performance — *OK at current scale*

- 49 unit tests run in ~3.5s. Fine.
- Cold app load on Streamlit Cloud is dominated by the CT.gov fetch
  (~10–15s for 362 studies). Frozen snapshots open in <1s.
- At 2× current trial count (~570 trials) the row-wise applies in
  `app.py:1613,1826,1827` would still complete in <50ms total.
  Performance is not a near-term concern.

**Recommendations:** none urgent. Revisit if we ship to a 10×-scale
domain (e.g., onc) or share a runtime with another app.

### Deployment & ops — *Concern*

- **No CI.** `.github/workflows/` does not exist. Regressions reach
  `main` without an automated test gate. (Onc has `test.yml`.)
- **`anthropic` pin is loose** (`requirements.txt`: `anthropic>=0.40.0`).
  Every other dep is pinned. Streamlit Cloud rebuilds will pick up new
  Anthropic SDK majors silently.
- **No retention policy for snapshots.** Only one snapshot exists
  (`snapshots/2026-04-25/`). Git is the storage layer; nothing prunes
  or rotates.
- **Secrets handling is minimal but correct.** `validate.py` reads
  `ANTHROPIC_API_KEY` (`validate.py:206`); nothing else uses secrets.
- **Devcontainer points at Python 3.11**
  (`.devcontainer/devcontainer.json:3`). Local development uses 3.13
  (verified: `pytest` runs on 3.13.13). Drift is fine for now but
  CI should pin both versions.

**Recommendations:** copy onc's `.github/workflows/test.yml` verbatim
(retest on 3.11 + 3.13); pin `anthropic==0.<x>.<y>`; document a
snapshot retention rule (e.g., keep N most recent + every-quarter
permanent) once snapshots are saved more than once a month.

### Documentation — *Concern (for preprint-readiness)*

- **README is partially stale.** Claims "9 systemic autoimmune
  diseases" and "8 cell-therapy modalities" (`README.md:23–25`). The 9
  is correct (`DISEASE_ENTITIES` keys + cGVHD = 10, not 9; SLE / SSc /
  Sjogren / CTD_other / IIM / AAV / RA / IgG4-RD / Behcet / cGVHD).
  The 8-modality claim matches `_MODALITY_ORDER` in `app.py` but is
  derived in `_add_modality_vectorized` not explicitly enumerated.
- **No `CHANGELOG.md`, `CITATION.cff`, or `SECURITY.md`** at repo root.
  Onc has all three.
- **No methods document.** `ONCOLOGY_APP_KICKOFF.md` exists at root but
  is the *onc* planning doc accidentally living in the rheum repo. No
  rheum-side equivalent.
- **`scripts/snapshot_diff.py` is on disk but uncommitted** (verified
  via `git status` earlier — created in this branch but not added).

**Recommendations:** update the README modality count to match
`_MODALITY_ORDER`; add `CITATION.cff` (Zenodo DOI is already in the
README badge); draft a `METHODS.md` that the preprint can pull from
verbatim; remove or relocate `ONCOLOGY_APP_KICKOFF.md` to avoid reader
confusion; commit `scripts/snapshot_diff.py`.

### Strategic coherence with onc app — *OK*

- **Where rheum is more mature than onc:** source-tagging on
  `_assign_target` (`pipeline.py:250–318`); sub-family classifier with
  L1 neuro promotion (`app.py:225–351`); audit panel split
  (`app.py:4427–4481`); locked benchmark includes Modality axis
  (`tests/test_benchmark.py:42–51`).
- **Where onc is more mature than rheum:** CI matrix
  (`.github/workflows/test.yml`); `_normalize_text` uniformly collapses
  hyphens and adds the `non hodgkin → nonhodgkin` trick (the rheum
  equivalent at `pipeline.py:72–81` keeps hyphens in some tokens);
  sponsor classification does not default OTHER_GOV → Government
  (rheum still does at `pipeline.py:494`); validate.py injects a
  closed-vocab system prompt; CHANGELOG/CITATION/SECURITY exist.
- **95%+ identical scripts** (`snapshot_diff.py`,
  `validate_independent_llm.py`) and identical-intent helpers
  (`_safe_text`, `_normalize_text`, `_term_in_text`, sponsor
  classification, age parsing, snapshot I/O) live in two repos. This
  is a real maintenance tax — every fix must be applied twice.

**Recommendations:** in Phase 3, extract a `cart-trials-core` package
(text utilities, sponsor classification, age parsing, snapshot I/O,
snapshot_diff, validate_independent_llm) and pin it from both apps.
Don't do this before the preprint — disruptive and unrelated to the
publication artifact.

## 3. Roadmap

### Phase 1 — Pre-preprint (1–2 weeks)

Only items that block publishability or credibility.

| Title | Effort | Impact | Rationale | Dependencies |
|---|---|---|---|---|
| Fix CTD_other systemic-basket bug | S | High | Real classifier bug. NCT07490041 is mis-classified today. One-line fix at `pipeline.py:164` + a regression test. | None |
| Add CI (copy onc `.github/workflows/test.yml`) | S | High | Without CI, fixes can be undone silently. 10-line workflow file. | None |
| Run independent-LLM validation, commit report | M | High | Methods section needs a κ to cite. Run with Gemini + one other (Groq or OpenAI) on n=100, commit `reports/independent_llm_validation_2026-04-25.md`. | API keys |
| Broaden benchmark to ~25 trials | M | High | Cover Behcet, cGVHD, CTD_other, Unclassified negative, at least one Unclear ProductType. F1 floors stay where they are; coverage breadth is the win. | None |
| Enum-lock `TargetCategory` in validator `ALLOWED_VALUES` | S | Medium | Prevents case/format false-positives inflating reported disagreement. | None |
| Update README modality count + remove `ONCOLOGY_APP_KICKOFF.md` from rheum repo | S | Medium | Reader confusion. README claim should match `_MODALITY_ORDER`. | None |
| Commit `scripts/snapshot_diff.py` | S | Low | Currently uncommitted but referenced in this review. | None |
| Add `CITATION.cff` | S | Medium | Zenodo DOI exists; CFF makes it machine-readable for citing systems. | None |
| Draft `METHODS.md` | M | High | Preprint pulls from this verbatim. PRISMA, classifier description, validation evidence, snapshot policy. | independent-LLM run |

### Phase 2 — Post-preprint hardening (1–2 months)

Scale, robustness, automation. Items not blocking publication but
making the next iteration faster.

| Title | Effort | Impact | Rationale | Dependencies |
|---|---|---|---|---|
| Deterministic snapshots (sort by NCTId; strip wall-clock from metadata) | S | Medium | Byte-identical snapshots given identical upstream data; reviewers can verify reproducibility. | None |
| Retry + resume on CT.gov fetch | M | Medium | A 5xx mid-pagination today wipes the run. Replace bare `requests.get` with retry + page-cache. | None |
| Chain `backfill_site_geo` into `save_snapshot` | S | Medium | 25 sites currently lack lat/lon. New snapshots should be geo-complete. | None |
| Vectorise sunburst L2/L3 derive | S | Low | `app.py:1826–1827` row-wise apply. Use `np.select` or a vectorised mask pass. Worth doing once the benchmark covers it. | None |
| Per-trial classification rationale UI | M | Medium | Surface `TargetSource` / `ProductTypeSource` / matched terms in the trial detail panel. Trust + auditability. | None |
| Expand unit test coverage on disease classification | M | High | 3 tests for 9 entities is too few. Add tests for every entity + the `_BROAD_BASKET_TERMS` and OIM fallback paths. | None |
| Pin `anthropic` exactly | S | Low | Match the rest of `requirements.txt`. | None |
| Add `CHANGELOG.md` and `SECURITY.md` | S | Low | Match onc; lowers cost for external contributors. | None |
| Tighten `_normalize_text` (uniform hyphen collapse) | S | Medium | Align with onc; closes a class of term-matching bugs. | New benchmark trials |
| Drop OTHER_GOV → Government default | S | Low | Match onc's stricter sponsor classification. Some Chinese provincial / Czech academic-hospital records get correctly re-routed to Academic. | New benchmark for sponsor-edge cases |
| Add `_normalize_disease_result` post-hook | S | Medium | Catch incoherent label combos at exit (e.g., "Single disease" + multiple matches). Onc has it. | None |
| Devcontainer pinned to 3.11+3.13 matrix | S | Low | Drift between dev (3.13) and devcontainer (3.11). | CI |

### Phase 3 — Strategic (3–6 months)

Architectural, cross-app convergence, new analytical capabilities.

| Title | Effort | Impact | Rationale | Dependencies |
|---|---|---|---|---|
| Extract `cart-trials-core` shared package | L | High | 7+ identical-intent helpers + 95%-identical scripts duplicated across rheum and onc. PyPI package, both apps pin it. Cuts maintenance tax in half. | Stable APIs in both |
| Single source of truth for disease taxonomy | M | Medium | `_DISEASE_TERMS` (`pipeline.py:132–160`) and `DISEASE_ENTITIES` (`config.py`) are parallel maps. Generate one from the other. | None |
| Extract `app/{style,taxonomy,figures}.py` from `app.py` | M | Medium | 5,031-line single-file is fine for one author; not for collaboration. Defer until contributor onboarding becomes friction. | None |
| Mobile / narrow-viewport pass | M | Low | If the preprint drives traffic from phones (likely on Twitter/X), the dashboard collapses. Either acknowledge as desktop-only or add responsive breakpoints. | Open question |
| Multi-factor confidence model | M | Medium | Replace `_compute_confidence`'s rule list with a transparent multi-factor score (named-product strength, basket coherence, OIM fallback depth). Surfaced in audit panel. | Phase 2 rationale UI |
| Cross-vendor κ as a CI gate | M | Medium | Once the validator has run a few times and a baseline κ is established, regress against it on pull requests. Single OPEN_ROUTER key + a 30-trial sample is ~30s in CI. | CI; budget |
| Auto-curated weekly snapshots | M | Medium | Cron on Streamlit Cloud or GitHub Actions; commits a snapshot every Monday; runs snapshot-diff on the prior week and posts the unexplained-list as an issue. | Phase 1 CI |
| `_assign_target` source-tag adoption in onc | S | Low | Cross-pollination. Trivial port of rheum's tuple return. | onc maintainer alignment |
| Sub-family + L1-promotion port to onc | M | Low | Cross-pollination. Onc could split "Heme-onc_other" by lineage. | onc maintainer alignment |
| Network-of-sites view (collaborator graph) | L | Medium | Sites table already has 1,530 rows × 39 countries; a sponsor↔site bipartite graph would be a real analytical addition rather than a re-cut of existing data. | None |
| Time-to-first-patient + status-transition tracking | L | High | We currently snapshot Status but never compare across snapshots. A second-axis "trial dynamics" view (recruiting → enrolling → completed) is unique. Requires multi-snapshot data. | Auto-curated weekly snapshots |

## 4. Out of scope / explicit non-recommendations

- **Do not refactor `app.py` into modules before the preprint.** It is
  long but coherent. Splitting it now invites merge conflicts with the
  preprint editor pass and adds zero to the publication artifact.
- **Do not migrate to a database.** The snapshot CSV+JSON approach is
  the *correct* design for a reproducibility-first dashboard; SQLite
  / Postgres would obscure provenance and break the single-tarball
  reviewability that PRISMA-style work needs. The right scaling axis
  is more snapshots, not relational storage.
- **Do not add user accounts or saved views.** This is a public
  read-only dashboard. Auth introduces secrets, ops, and data-policy
  surface that no academic project should carry without a clear funded
  reason.
- **Do not migrate to a heavier LLM provider for the curation loop.**
  Claude is fine for the curation tier; the *independent* validator is
  deliberately cross-vendor for that reason. Consolidating both onto
  one vendor defeats the validation design.
- **Do not pursue `gpt-4o`-as-judge over Claude as judge.** No evidence
  either is better for this domain; switching costs > gains until the
  independent-LLM run shows actual disagreement clusters.
- **Do not add a "real-time" mode** (websocket-driven CT.gov polling).
  Daily-cache + manual snapshot is the right cadence; "live" trial
  data is not actually live (CT.gov posts updates with multi-day lag).
  Implementing real-time would suggest a level of currency the data
  can't actually support.
- **Do not add a custom rheum-specific classification ontology beyond
  what `DISEASE_ENTITIES` covers.** The current 9-entity vocabulary
  matches the way rheumatologists carve the space; finer taxonomy
  (e.g., "Lupus nephritis class V" vs "Lupus nephritis class III/IV")
  is below the resolution of CT.gov free-text and would inflate
  Unclassified rates.

## 5. Open questions for me

1. **Preprint horizon.** What is the target submission date? "1–2
   weeks" in Phase 1 assumes ≤4 weeks to medRxiv. If it's tighter,
   independent-LLM run + benchmark broadening is the floor; everything
   else can ship as v1.1.
2. **κ acceptance threshold.** What κ does the methods section claim?
   Substantial (≥0.6) is honest; almost-perfect (≥0.8) is achievable
   on the structured axes (TargetCategory, ProductType) but probably
   not on DiseaseEntity given the basket-vs-OIM ambiguity. The number
   you cite shapes which Phase 1 fixes are mandatory.
3. **Mobile support — explicitly desktop-only or responsive?** This is
   a decision, not a discovery. If the preprint is going to be tweeted
   it matters; if the audience is a PI on a workstation it doesn't.
4. **Snapshot cadence post-preprint.** Weekly auto + manual on demand
   (Phase 3 item), or quarterly only? The choice drives the snapshot
   retention policy and the snapshot-diff cron design.
5. **Onc / rheum convergence direction.** Should the two apps converge
   on a shared core package (Phase 3 `cart-trials-core`), or diverge
   intentionally and accept the duplication tax? This is partly a
   maintainer-time question and partly a positioning question (one
   "platform" with two domain skins, vs. two independent dashboards).
6. **`ONCOLOGY_APP_KICKOFF.md` at the rheum repo root.** Was this
   intentional cross-pollination context, or accidental commit drift?
   I assume the latter and recommend removal in Phase 1.
7. **`HARD_EXCLUDED_NCT_IDS` (35 trials in current snapshot).** Are
   the exclusions documented anywhere with rationale? The preprint
   reviewers will ask. If not, Phase 1 should include a
   `docs/exclusions.md` table.

---

*Review compiled from: file inspection (file:line refs throughout),
runtime checks (`pytest tests/ -v`: 49 passed; snapshot self-diff: 0
changes; benchmark: 12/12 at 1.000 macro-F1; pandas inspection of
`snapshots/2026-04-25/trials.csv`), and a parallel cross-reference
against `https://github.com/ptjeong/ONC-CAR-T-Trials-Monitor` (main).
No code or commits were made.*
