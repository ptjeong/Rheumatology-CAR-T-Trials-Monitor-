# Deep Dive — audience-driven restructure analysis

The Deep Dive section currently renders ~30 distinct charts across
6 sub-tabs (By disease / By target / By sponsor / By geography /
By time / Compare), counted in the canonical sense (a stacked-bar
plus its drilldown twin = 2 chart instances). With the sister
sections (Overview, Geography map, Publication figures) the
dashboard is at ~80 chart instances. That's too many — readers
bounce between panels that don't answer their question and the
ones that do don't surface.

This brief audits Deep Dive against two distinct audiences:

  - **Academic researchers**: rheumatologists, immunologists,
    methodologists, doctoral students. Their goal is to understand
    the field, find research gaps, plan studies / meta-analyses,
    and cite specific trials.
  - **Pharma industry**: BD/strategy, clinical operations, medical
    affairs, competitive intelligence. Their goal is to map
    competitors, find white-space, plan trial design, time market
    entry, and benchmark their pipeline.

Each panel in Deep Dive is scored against both audiences. Drop /
keep / promote recommendations follow.

---

## What each audience actually wants

### Academic researchers

  - **Disease-level landscape**: which indications are well-served,
    which are research deserts? (drives study selection, grant
    framing)
  - **Methodological frontier**: what modalities are being tried?
    What's the phase-mix balance — are studies converging on
    Phase II or stuck in Phase I? (drives meta-analyses, scoping
    reviews)
  - **Geographic / regulatory diversity**: international
    representation, paediatric coverage, vulnerable-population
    inclusion. (drives equity-of-access analyses)
  - **Per-trial detail**: drill to NCT record, get classification
    rationale, cite the trial. (drives citation, validation)
  - **Methods transparency**: PRISMA, classifier rationale, ontology,
    exclusion criteria. (drives reproducibility, peer review)

What they DON'T want:

  - Sponsor competitive narratives
  - Industry vs academic deal dynamics
  - Product-level race timelines
  - "Who will be first to market" framing
  - Per-named-product pipeline overlays
  - Top-10 sponsor activity unless they're a target of analysis

### Pharma industry

  - **Sponsor concentration**: who controls each indication? Where's
    the field consolidating vs fragmenting? (drives positioning)
  - **Per-product pipelines**: where is competitor X in development?
    What phases / geographies are they in? (drives competitive
    intelligence)
  - **Modality competition**: autologous vs allogeneic vs CAR-NK
    velocity — which platform is winning? (drives platform bet)
  - **Year-over-year activity by sponsor**: who's accelerating, who's
    stalling? (drives benchmark + threat assessment)
  - **Geographic strategy**: where are sites concentrated? What's
    growing? (drives site-selection + regulatory strategy)
  - **Recent activity**: what trials registered in the last 90 days?
    (drives near-term threat watch)

What they DON'T want:

  - PRISMA exclusion details
  - Rare-disease coverage analysis (unless their drug)
  - Paediatric blind spots (unless their drug)
  - Methodological rigour breakdowns
  - Validation kappa, inter-rater agreement
  - Long captions explaining classifier logic

---

## Panel-by-panel audit

Each panel gets a 0-3 score per audience (0 = no value, 1 = mild,
2 = useful, 3 = high-value/critical). Aggregate "min score" of 0
means the panel is dead weight for one audience; "combined" is
academic + pharma.

### By disease tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| Disease × Antigen heatmap | 3 | 3 | 6 | KEEP — both audiences read it the same way |
| Phase composition (top 12 diseases) | 3 | 2 | 5 | KEEP — academic-led but pharma still scans it |
| Trial age by status box plot | 2 | 1 | 3 | KEEP — research-flavoured but useful |
| Pick-disease drilldown: antigen targets table | 2 | 2 | 4 | KEEP |
| Pick-disease drilldown: product types table | 1 | 3 | 4 | KEEP — pharma high value |
| Pick-disease drilldown: sponsor-type donut | 1 | 2 | 3 | DROP — covered better in Sponsor tab |
| Pick-disease drilldown: top countries bar | 2 | 2 | 4 | KEEP |
| Pick-disease drilldown: phase mix bar | 2 | 2 | 4 | KEEP — but matches the top-12 chart; consider merge |

### By target tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| Target × Disease heatmap | 3 | 3 | 6 | KEEP |
| Antigen emergence scatter | 3 | 2 | 5 | KEEP — research-novel |
| Phase composition by target | 2 | 3 | 5 | KEEP |
| Pick-target drilldown: disease entity breakdown | 2 | 2 | 4 | KEEP |
| Pick-target drilldown: modality breakdown | 2 | 3 | 5 | KEEP — pharma high value |
| Pick-target drilldown: phase distribution | 2 | 2 | 4 | DROP — duplicates the above phase composition chart |
| Pick-target drilldown: disease family split | 2 | 2 | 4 | DROP — heatmap above already shows this |
| Pick-target drilldown: annual starts timeline | 2 | 2 | 4 | KEEP |
| Pick-target drilldown: enrollment-size by disease | 2 | 3 | 5 | KEEP |
| Per-product pipeline view (appended) | 1 | 3 | 4 | PROMOTE to own tab |
| Per-product phase composition | 1 | 3 | 4 | PROMOTE |
| Per-product enrollment-size distribution | 1 | 3 | 4 | PROMOTE |
| Per-product annual starts | 1 | 3 | 4 | PROMOTE |

### By sponsor tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| Sponsor type × Disease heatmap | 1 | 3 | 4 | KEEP |
| Phase composition by sponsor type | 1 | 3 | 4 | KEEP |
| Pick-sponsor: phase distribution | 0 | 3 | 3 | KEEP — pharma-critical |
| Pick-sponsor: antigen targets table | 0 | 3 | 3 | KEEP |
| Pick-sponsor: disease coverage | 0 | 3 | 3 | KEEP |
| Pick-sponsor: annual trial starts | 0 | 3 | 3 | KEEP |

The whole By-sponsor sub-tab is pharma-skewed. That's fine — but
acknowledge it in the tab framing (currently neutral).

### By geography tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| Country leaderboard table | 2 | 3 | 5 | KEEP |
| Country × Disease heatmap | 2 | 2 | 4 | KEEP |
| Phase composition by country | 2 | 2 | 4 | KEEP |
| Per-country drilldown bars | 2 | 2 | 4 | KEEP |

Geography is the most balanced tab — both audiences read it
similarly. Less to cut.

### By time tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| Annual trial starts (selectable axis) | 3 | 3 | 6 | KEEP |
| Cumulative active trials | 2 | 3 | 5 | KEEP |
| Cohort × phase mix (%) | 3 | 2 | 5 | KEEP |
| Top sponsors heatmap (just rebuilt) | 1 | 3 | 4 | KEEP |
| Phase-progression heatmap | 3 | 2 | 5 | KEEP — academic-flavoured, pharma reads it as "maturity per cohort" |

By time is dense but every panel earns its slot.

### Compare tab

| Panel | Acad | Pharma | Combined | Verdict |
|---|---|---|---|---|
| A vs B (3 mini-charts each side) | 2 | 2 | 4 | KEEP — symmetric value |

Compare is conceptually solid. The mini-chart count (3 per side)
is the right balance. Adding more panels would dilute the
"comparison" framing.

---

## Cross-cutting issues

### 1. Phase composition shows up 5 times

It appears in:
  - By disease (top 12)
  - By target (top 12)
  - By sponsor type
  - By country (geography drilldown)
  - By time cohort × phase

The reader sees similar stacked bars over and over. **Recommendation**:
keep all five — they each slice the data differently — but unify
the visual treatment (same palette, same legend position, same
height) so the repetition feels intentional rather than redundant.

### 2. Drilldown bars are visually weak

Most "pick X, see Y mini-charts" panels show uniform-color bars
(blue everywhere). That was flagged in TUFTE_AUDIT_FULL.md as
"defer — case-by-case judgement". For the audience-restructure
pass, the right call is:
  - **Drop the lowest-value drilldown bars entirely** (the duplicates
    listed above)
  - **Color the kept ones by family / region / phase** where the
    underlying axis is categorical and named — adds a second
    encoding dimension at no cost

### 3. Per-product pipeline is buried

It's appended to By target. Pharma-critical content shouldn't
require scrolling past disease drilldowns. **Recommendation**:
promote to its own top-level Deep Dive tab — "By product" —
between By target and By sponsor.

### 4. No "Recent activity" panel

Pharma intelligence audiences will look for "what trials were
registered in the last 30/60/90 days?" The Overview tab has
"Recently added trials" (top 8) but it's a one-time read, not a
deep-dive panel. **Recommendation**: add a "Recent activity"
panel to By time — a table of trials registered in the last 90
days, filterable, with classification rationale on row click.
Pharma high-value, academic mild.

### 5. No "Trial-quality" or "Methodological" lens

Academic-flavoured filters that would surface things like:
  - Trials with no reported enrollment count
  - Trials with no listed country
  - Trials with conflicting phase / status
  - Single-arm vs randomised (where the data is available)

These exist as classification rationale in the per-trial
drilldown, but aren't aggregated. **Recommendation**: defer.
Adding a quality lens means broadening data ingestion (CT.gov has
some but not all of this). Note in roadmap.

---

## Proposed restructure

**Minimum-disruption version** (small commits, deploy in stages):

1. Drop the four duplicate drilldown panels listed above (-4 charts)
2. Promote "By product" to its own top-level sub-tab (-0 charts,
   +1 tab; shift content)
3. Add a "Recent activity" panel to By time (+1 panel)
4. Add per-tab audience-orientation captions:
   - By disease: "Indication landscape — research gaps + competitive
     mapping"
   - By target: "Antigen-level competitive + emergence view"
   - By product: "Pipeline detail per named product — competitor
     intelligence"
   - By sponsor: "Sponsor-level activity, concentration, and
     individual portfolios"
   - By geography: "Site distribution, country mix, regional trends"
   - By time: "Temporal patterns: starts, cumulative, cohort
     maturity, recent activity"
   - Compare: "Side-by-side mini-dashboards for any two diseases or
     antigens"

**Bigger version** (separate PR):

5. Audience-tagged display toggle in sidebar:
   - "Researcher view" — hides per-product detail, per-sponsor
     drilldown, recent-activity panel
   - "Industry view" — hides methodological-rigour panels, trial-
     age boxplot
   - "Full" (default) — everything

6. Re-rank the sub-tab order so the highest-combined-score tab is
   first. Current: By disease → By target → By sponsor → By
   geography → By time → Compare. Recommended: By disease → By
   target → By time → By product → By sponsor → By geography →
   Compare. (Bumps "By time" up, "By product" out of appendix
   position.)

---

## Net change

Current Deep Dive: ~30 chart instances + 4 drilldown picker tables.
Recommended Deep Dive (minimum-disruption version):
  - −4 duplicate drilldown bars
  - +1 Recent activity panel
  - same total tab count (6), one promoted

Net: −3 chart instances, slightly higher per-panel value, clearer
audience targeting via captions, per-product pipeline no longer
buried.

If the bigger version lands: add audience toggle, re-rank tab
order. No additional charts to maintain — same data filtered
through display flags.

---

## Out of scope

  - Drop the entire By-time sub-tab and merge into By-disease /
    By-target time-slices (too disruptive for marginal gain)
  - Replace tabs with continuous scroll (Streamlit's tabs are the
    right primitive given session-state semantics)
  - Add outcome-data linkage (already on cross-app roadmap, W6-7)
  - Switch from Plotly to Vega-Lite for tighter Tufte compliance
    (cost > benefit; PNG/SVG export pipeline works)

---

## Decision required

Which version to implement?
  - **Stage 1** (minimum-disruption, ~150 LOC): drop 4 duplicates,
    promote By product, add Recent activity, add audience captions
  - **Stage 2** (audience toggle, ~80 LOC after Stage 1): sidebar
    radio + per-panel `if researcher_mode: continue` guards
  - **Stage 3** (re-rank sub-tabs): trivial — just a list re-order
    in the `st.tabs([...])` call (~5 LOC)

Stage 1 is the safest, ships meaningful value. Stage 2 doubles the
gain. Stage 3 is essentially free once 1+2 are in.
