# Figures audit — Tufte's principles

Edward Tufte's analytic-graphics framework reduces to six principles plus
several design heuristics. This review applies them to the dashboard's
~40 figures (Pub Figs 1–11, Deep Dive heatmaps / lines / boxes /
Sankey, Overview newsroom strip). The goal is to identify the highest-
leverage edits — not a rewrite.

---

## Tufte's six principles, scored

### 1. Show comparisons

> "Evidence is always relative to alternatives."

**Score: B+.** Strong: the Compare sub-tab, the cohort × phase Sankey,
the side-by-side small-multiples in Fig 4 (4a-4d), the Disease ×
Antigen heatmap. Weak: many Deep Dive bar charts show ONE slice
without an implicit comparator (e.g., "phase distribution of trials
targeting CD19" — but no neighbouring chart for "phase distribution
of trials targeting BCMA" to anchor the reader's frame).

**Highest-impact fix**: where two related charts already render in
adjacent columns, ensure they share an axis range (not auto-scale per
panel). A "phase distribution by target" pair where each chart
auto-scales its y-axis silently distorts comparison.

### 2. Show causality, mechanism, structure, explanation

> "The deep purpose of statistical analysis is to understand."

**Score: C+.** Most figures are descriptive. The closest things to
mechanism: PRISMA ledger (selection mechanism), basket-detection
sub-classification (disease-classifier mechanism explained in
captions), per-trial classification rationale (drilldown). The
sunburst encodes hierarchy structure but not causality. No figure
explains *why* the autoimmune-CAR-T pipeline shifted to BCMA in 2024
or *why* SLE dominates — the data shows the pattern; mechanism is
left to the reader.

**Highest-impact fix**: this is fundamentally a research-tool issue —
adding outcome data + publication linkage (already on the cross-app
roadmap, weeks W6-7) is the structural fix. No figure-level edit
substitutes.

### 3. Show multivariate data

> "Three or more variables should be shown when relevant."

**Score: A−.** Strong: sunburst (3 nested variables — family ×
indication × antigen target), heatmaps (2 axes + value-as-colour, with
size-as-volume on the country-emergence scatter), Sankey (year cohort
× current phase × trial count). Most line charts encode time × group
× count. Weak: some bar charts are 1-variable (just trial count per
disease) and could carry a colour-as-second-variable encoding.

**Highest-impact fix**: small. Most charts already exploit available
dimensions; the few 1-variable bars are simple-by-design (Top
countries, Top sponsors are intentionally rank-only).

### 4. Integrate text, graphics, and data

> "Words, numbers, and pictures together inform the reader."

**Score: B.** Strong: every Pub Fig has a header + caption + chart +
CSV-with-provenance. The captions explain method choices (e.g.,
Fig 11 explains the 30% / 60% concentration thresholds inline).
Deep Dive figures have shorter `**Title**` + optional caption + chart
+ no CSV — leaner but appropriate for the exploratory tab.

Weak: some captions are LONG (Fig 11's caption is ~60 words) — Tufte
prefers concision. And Deep Dive's `**Title**` markdown adds a heading
line above each chart that's often redundant with the chart's title
itself.

**Highest-impact fix**: in the Deep Dive layouts, replace the
`**Title**` markdown with `chart_title=` argument (or just drop it
when the chart is self-titled).

### 5. Establish documentation

> "Source, scale, methodology, the unit of analysis."

**Score: A.** Every figure has provenance via CSV `#` headers,
snapshot date in the About tab, classifier methods in the auto-
generated Methods text, ontology table, and per-trial drilldown
showing the rule that fired. This is well-handled — methods text
+ snapshot pinning + Zenodo DOI on the repo + CITATION block.

**Highest-impact fix**: nothing. This is the strongest axis.

### 6. Content first

> "Above all, show the data."

**Score: A−.** The sunburst-as-hero, the 11 figures, the deep-dive
sub-tabs all centre on substantive disease/target/phase data rather
than aesthetic decoration. Few decorative gradients, no 3D effects,
no chart-junk-style icons.

Weak: a few drop-into-a-section blocks have an `##### Heading` that
adds visual weight without adding content (e.g., "##### Pipeline
maturity & competitive intensity" before a single chart).

---

## Tufte's visual design rules (specific)

### Data-ink ratio: maximise

  - **Sunburst borders** were 1.2 → 0.6 (already done).
  - **Plot grids**: Plotly's `plotly_white` template renders grids in
    `#e5e7eb` — already light. ✓
  - **Donut charts**: 5 instances, hole=0.55 with outside labels.
    Outside labels are good (direct-labeling), but the inner hole is
    visual emptiness. Tufte would prefer a stacked-bar single-row
    showing the same proportions with much higher data-ink ratio.
  - **Box plots**: defaults are fine — box, whiskers, median, outlier
    dots. No need to add mean line or notches.

### Chartjunk: minimise

  - No 3D effects, gradients, decorative shadows.
  - One pattern flagged: **redundant axis titles**. Multiple charts
    have an x-axis title "Year" or "Trial start year" when the year
    tick labels make this self-evident. Already removed from
    `_deepdive_timeline` (commit f55d6f9). Other instances:
      Fig 1 stacked area (line 6757): "Start year" — redundant
      Fig 7b (line 7716): "Start year" — redundant
      `_deepdive_emergence` scatter: "Year of first trial" — keep
        (the chart title might say something else; standalone needs it)

### Direct labeling

  - **Strong**: heatmap cell annotations (Fig 8, Fig 9, Deep Dive
    heatmaps) — values printed inside cells. Tufte-y.
  - **Weak**: line charts use category-colour + legend below. Tufte
    prefers labelling the line directly at its rightmost point. The
    "Annual trial starts by sponsor" chart with 10 wrapped-line
    sponsor names in the legend is the worst offender.

  Direct-labeling lines IS achievable in Plotly via `mode='lines+text'`
  with text only on the last point. ~20 LOC change in
  `_deepdive_timeline`. Substantial Tufte gain.

### Small multiples

  - **Strong**: Fig 4 sub-panels, the 2-column Deep Dive layouts.
  - **Weak**: the Compare tab uses two separate panels rendered in
    columns. A genuine small-multiples implementation would render
    BOTH panels with the SAME y-axis scale, allowing direct visual
    comparison. Today each panel auto-scales independently — silently
    distorts the comparison.

### Sparklines

  - **Not used.** The Overview KPI strip has 5 metric tiles
    ("Trials", "Open / recruiting", "Total enrolled", "Top antigen",
    "Trials started in 2026"). Each shows a single number. Tufte's
    sparkline ("a small intense, simple, word-sized graphic") would
    make these tiles much richer: each big number could have a
    24-month trend line behind it.

  Tractable: ~50 LOC. Significant Tufte alignment.

### Range-frame plots

  - **Not used.** Tufte advocates removing the full axis spine and
    replacing it with a range-line that shows only the data's actual
    extent. Plotly doesn't make this trivial; cost > benefit here.

---

## Highest-leverage edits (in priority order)

### 1. Direct-label line charts (biggest Tufte win)

Replace `_deepdive_timeline`'s bottom legend with end-of-line labels.
For the "Top sponsors — annual trial starts" chart with 10 wrapped
institutional names, this turns a 3-row-tall legend into 10 small
labels at the right edge of each line — each line is anchored to its
identity directly. ~30 LOC in the helper.

### 2. Add sparklines to Overview KPI tiles

Each metric tile gets a 24-month inline trend line behind / below the
big number. Recently-added trial count, active recruiting count, and
total enrolled all have time series available. ~50 LOC.

### 3. Trim redundant axis titles

  - Pub Fig 1 (stacked area): drop xaxis_title="Start year" — year
    ticks are self-evident
  - Pub Fig 7b (modality): drop xaxis_title="Start year"
  - Both have legend below; without an axis title competing for the
    bottom space, more chart breathes.

### 4. Compare tab: shared y-axis scale

In the side-by-side comparator, lock the two panels to the same
y-axis range so the visual comparison is honest. Today panel A's
"Phase mix" auto-scales to its own peak — panel B's auto-scales
independently. Two diseases with similar trial counts but different
phase concentrations look more different than they are.

### 5. Drop redundant `##### Section header` lines

Where a section header sits immediately above a single chart whose
own title already says what the section is, the heading is
chartjunk. Audit and remove or merge.

### 6. Donut → row stacked bar (where the donut shows ≤4 categories)

5 donuts in the dashboard, all showing 3-4 categories (sponsor type,
modality, etc.). A horizontal single-row stacked bar at the same
visual weight carries identical information at higher data-ink ratio
and faster value comparison. Cost: ~40 LOC for a `_compact_stack()`
helper; gain: tighter visual rhythm across the Deep Dive panels.

---

## What I'm NOT proposing

  - Replacing Plotly with custom SVG (D3 / Vega-Lite would let us
    follow Tufte more strictly, but the cost is enormous and the
    PNG/SVG export pipeline already works)
  - Removing colour from charts to maximise data-ink (Tufte's late-
    career pivot toward grayscale only matters for print reproduction;
    the dashboard is screen-first)
  - Replacing tabbed UI with continuous scroll (Tufte's "show more"
    advocacy is real but Streamlit's tabs are the right primitive
    given session-state and rerun semantics)
  - Adding range-frame plots (cost > benefit in Plotly)

---

## Estimate

Edits 1-3 (direct-labelling, sparklines, axis-title trim) total
~120 LOC. Edits 4-6 (shared scale, header trim, donut→stack) add
another ~150 LOC. Total ~270 LOC for the full Tufte pass.

Implementing 1-3 first (the biggest wins) and deferring 4-6 to
follow-up commits is the pragmatic split.
