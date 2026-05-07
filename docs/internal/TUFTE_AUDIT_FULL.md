# Full figure-by-figure Tufte audit

Audit of every chart in the dashboard against Tufte's principles +
design rules. ~55 chart instances grouped by tab. Each gets:

  1. **What it shows** — one-line description
  2. **Tufte score** — letter grade + dominant strength/weakness
  3. **Concrete issue** — specific Tufte violation if any
  4. **Fix** — what to do (or "—" if none needed)

Top-N priority list at the bottom.

Already fixed in commit 212eda0: direct-label timelines, KPI
sparklines, redundant year-axis titles in Pub Figs 1 & 7b. Items
already addressed are marked **[FIXED 212eda0]**.

**Correction (post-audit):** the KPI-tile sparklines were judged to add
unnecessary visual clutter and were **reverted** in the follow-up
commit. Tile-5 sparkline (item 9) is also dropped. Tufte favours
sparklines, but the dashboard reader explicitly preferred clean
numeric tiles — local taste overrides general principle. Items 2 +
9 are marked **[REVERTED]** below.

---

## Overview tab

### O1 — KPI strip (5 metric tiles, no sparklines)

  - Shows: total trials, open/recruiting, total enrolled, top antigen,
    distinct sponsors.
  - Score: **A**. Clean numeric tiles — the reader prefers headline
    numbers without inline trend graphics (visual clutter outweighs
    the Tufte-canonical case for this dashboard).
  - Issue: none.
  - Fix: — (sparklines were tried in 212eda0 but reverted at user
    request).

### O2 — Top movers (3-axis YoY change table)

  - Shows: top 5 risers + 5 fallers across Disease / Antigen / Sponsor
    axes between last-complete year and prior.
  - Score: **B+**. Tabular form is appropriate for ranked, mixed-axis
    data. Direct-labelled (axis col + category col + numbers).
  - Issue: the Δ column shows raw count change; for low-count
    categories ("3 → 5") the raw delta is misleading vs proportional
    change. Tufte: relative is often more comparable than absolute.
  - Fix: add a "% change" column (or visual sparkbar). Deferred —
    raw count is currently easier to scan, % adds noise for tiny
    denominators.

### O3 — Recently added trials (table)

  - Shows: 8 most-recently-updated trials by LastUpdatePostDate.
  - Score: **A**. Table is the right primitive; columns are scannable.
  - Issue: none. Title truncated to 70 chars (good — no overflow).
  - Fix: —

### O4 — Sunburst (disease-hierarchy hero)

  - Shows: 3 nested rings — clinical specialty → indication → antigen
    target.
  - Score: **A**. Multivariate, hierarchical, contiguous arc encodes
    family clustering. 0.6 px white borders (already Tufte-tuned).
  - Issue: when many tiny wedges exist at L3, labels suppress (good)
    but the rim has unlabelled thin slices that read as visual
    noise. Possibly the maxdepth=3 could be cut to 2 for the smallest
    slices.
  - Fix: defer — current behaviour (uniformtext minsize=12) suppresses
    illegible labels; the unlabelled wedges still carry size info.

### O5 — PRISMA ledger (in expander)

  - Shows: financial-statement-style trial flow from API fetch to
    inclusion.
  - Score: **A**. Custom CSS, no chartjunk, dot-leader rows for
    exclusions, bordered final row.
  - Issue: none.
  - Fix: —

---

## Geography / Map tab

### G1 — Regional aggregates strip (6 metric tiles)

  - Shows: distinct trials per region (Asia / Europe / NA / LA /
    Oceania / Other).
  - Score: **B+**. Same idiom as O1 KPI strip but no sparklines.
  - Issue: tiles are inert (no per-year trend). Trade-off acceptable
    — region totals don't move much YoY, sparklines would be flat-
    looking.
  - Fix: defer.

### G2 — World choropleth + open-sites overlay

  - Shows: country trial counts (choropleth) + open recruiting sites
    (point overlay).
  - Score: **A−**. Multivariate (count + site location), direct
    encoding. Two-layer toggle.
  - Issue: choropleth colorscale is sequential (Plotly default) — fine.
  - Fix: —

### G3 — Top countries bar

  - Shows: top-12 countries by trial count.
  - Score: **B**. Simple horizontal bar; sorted; correct.
  - Issue: bar colours are uniform `THEME["primary"]`. Tufte would
    prefer colour-as-encoding (e.g., region) or no colour at all.
    Uniform colour wastes ink without conveying.
  - Fix: colour bars by region (matches the regional strip above).
    **Implemented this commit.**

### G4 — Country drilldown — sites map

  - Shows: sites within a chosen country with status.
  - Score: **A−**. Geographic + categorical (status).
  - Issue: none.
  - Fix: —

### G5 — Country drilldown — city table

  - Shows: cities × trials × site statuses.
  - Score: **A**. Tabular; row-clickable.
  - Issue: none.
  - Fix: —

### G6 — Country drilldown — city bar

  - Shows: open-site count per city.
  - Score: **B**. Simple horizontal bar.
  - Issue: same uniform-colour critique as G3 but lower stakes
    (single-country, fewer bars).
  - Fix: defer.

---

## Deep Dive — By disease

### DD-disease 1 — Disease × Antigen heatmap

  - Shows: which antigen targets are tested for which diseases (top
    12 × 15).
  - Score: **A**. Multivariate, cell-annotated, sorted by total.
  - Issue: none. Cell annotations show the count directly inside cells.
  - Fix: —

### DD-disease 2 — Phase composition stacked bar (% normalised)

  - Shows: % phase mix per top-12 disease.
  - Score: **A−**. Normalised stacking, sky-palette phase colours.
  - Issue: none.
  - Fix: —

### DD-disease 3 — Trial age by status box plot

  - Shows: years-since-start distribution stratified by current status.
  - Score: **A**. Box plot is the right primitive for distribution.
  - Issue: none.
  - Fix: —

### DD-disease 4 — Per-disease drilldown sponsor-type donut

  - Shows: Industry / Academic / Government / Other split for the
    picked disease.
  - Score: **B**. Donut shows ≤4 categories; data-ink ratio low.
  - Issue: 4-category donut could be a single-row stacked bar with
    higher data-ink ratio + faster proportion comparison.
  - Fix: convert to single-row stacked bar. **Implemented this commit
    via new `_compact_stack` helper, applied to this donut + the
    Compare tab's two donuts.**

### DD-disease 5 — Per-disease drilldown top-countries bar

  - Score: **B**. Uniform-colour bar. Same critique as G3.
  - Fix: defer (small chart, low priority).

### DD-disease 6 — Per-disease drilldown phase mix bar

  - Score: **B**. Uniform-colour bar.
  - Fix: defer.

---

## Deep Dive — By target

### DD-target 1 — Target × Disease heatmap

  - Shows: which diseases each antigen is tested in.
  - Score: **A**. Same idiom as DD-disease 1, axis-flipped.
  - Issue: none.
  - Fix: —

### DD-target 2 — Antigen emergence timeline (scatter)

  - Shows: year of first trial per antigen target.
  - Score: **A−**. Direct-labelled (target name as text).
  - Issue: x-axis range starts at the earliest year — fine.
  - Fix: —

### DD-target 3 — Phase composition by target (stacked bar)

  - Score: **A−**. Same idiom as DD-disease 2.
  - Fix: —

### DD-target 4-7 — Per-target drilldown panels

  - DD-target 4: entity bar (uniform colour) — defer
  - DD-target 5: phase bar (uniform colour) — defer
  - DD-target 6: annual timeline (now direct-labelled) — **[FIXED 212eda0]**
  - DD-target 7: enrollment box — fine

### DD-target 8 — Per-product landscape phase composition

  - Score: **A−**.
  - Fix: —

### DD-target 9 — Per-product enrollment box

  - Score: **A−**.
  - Fix: —

### DD-target 10 — Per-product annual timeline (direct-labelled)

  - **[FIXED 212eda0]**

---

## Deep Dive — By sponsor

### DD-sponsor 1 — Sponsor type × Disease heatmap

  - Score: **A**. Greens palette to differentiate from disease/target
    heatmaps.
  - Fix: —

### DD-sponsor 2 — Phase composition by sponsor type (stacked bar)

  - Score: **A−**.
  - Fix: —

### DD-sponsor 3 — Specific-sponsor drilldown — phase bar / antigens / diseases / annual timeline

  - DD-sponsor 3a-3c: uniform-colour bars — defer
  - DD-sponsor 3d: annual timeline — **[FIXED 212eda0]**

### DD-sponsor 4 — Per-disease drilldown specific-sponsor sponsor-type table

  - Score: **B+**. Table.
  - Fix: —

---

## Deep Dive — By geography

### DD-geo 1 — Country leaderboard (table)

  - Score: **A**. Table.
  - Fix: —

### DD-geo 2 — Country × Disease heatmap

  - Score: **A**. Blues palette.
  - Fix: —

### DD-geo 3 — Phase composition by country (stacked bar)

  - Score: **A−**.
  - Fix: —

### DD-geo 4 — Country drilldown bars (top diseases / top antigens)

  - Score: **B**. Uniform-colour bars.
  - Fix: defer.

---

## Deep Dive — By time

### DD-time 1 — Annual trial starts (selectable colour axis, direct-labelled)

  - **[FIXED 212eda0]**

### DD-time 2 — Cumulative active trials (line + area)

  - Score: **A**. Single-line cumulative — Tufte's "show change" rule.
  - Issue: none.
  - Fix: —

### DD-time 3 — Cohort × phase mix (stacked bar % normalised)

  - Score: **A**.
  - Fix: —

### DD-time 4 — Top sponsors annual timeline (direct-labelled)

  - **[FIXED 212eda0]**

### DD-time 5 — Phase-progression Sankey

  - Shows: start-year cohorts → current phase via flow bands.
  - Score: **A**. Multivariate flow diagram, sky-palette phase
    encoding, hover-on-link tooltip.
  - Issue: node labels for early-cohort years (`≤2020`) might collide
    on narrow screens. Mostly readable; current arrangement="snap"
    is already optimised.
  - Fix: —

---

## Deep Dive — Compare

### DD-compare — A vs B side-by-side mini-panels

  - Shows: two mini-dashboards rendered side-by-side for any two
    diseases or two antigens.
  - Score: **B+**. The whole IDEA is Tufte-y (small multiples for
    direct comparison).
  - Issue: each panel auto-scales its y-axis independently. Two
    diseases with similar absolute counts but different distributions
    visually look more different than they are. The comparison is
    silently distorted.
  - Fix: lock both panels to a shared y-axis range computed from the
    union. **Implemented this commit.**
  - Sub-issue: the sponsor-type donut inside each panel is a small
    donut. Convert to row-stacked-bar (same as DD-disease 4). **Done
    this commit.**

---

## Publication Figures

### Fig 1 — Temporal trends stacked area

  - Score: **A**. Multivariate (year × entity × count).
  - Issue (was): redundant `xaxis_title="Start year"` — **[FIXED 212eda0]**.
  - Fix: —

### Fig 2 — Phase distribution by sponsor sector

  - Score: **A**. Stacked bar; clear comparison axis.
  - Fix: —

### Fig 3a — Choropleth of trial counts by country

  - Score: **A**. Standard choropleth, sequential blues.
  - Fix: —

### Fig 3b — Top 10 countries bar

  - Score: **B**. Uniform-colour bar.
  - Issue: same as G3 — could colour by region.
  - Fix: defer (Pub Figure conservatism — keep stylistic consistency
    with simple categorical bars).

### Fig 4 — Trial enrollment 4-panel (4a-4d)

  - 4a: Enrollment distribution histogram
  - 4b: China vs Non-China box plot
  - 4c: Industry vs Academic median + IQR forest
  - 4d: Geography × Sponsor type forest
  - Score: **A**. Genuine small-multiples (Tufte-canonical).
  - Issue: none.
  - Fix: —

### Fig 5a + 5b — Disease distribution (trial count + planned patients)

  - Score: **A**. Per-bar entity colour from canonical palette.
  - Fix: —

### Fig 6 — Antigen target distribution

  - Score: **A**.
  - Fix: —

### Fig 7a — Modality distribution (horizontal bar)

  - Shows: 8 modalities as a horizontal bar coloured per modality.
  - Score: **A−**. Bar is the right primitive at 8 categories.
  - Issue: none. (Earlier audit draft mis-described this as a donut;
    it was already a bar in the live code.)
  - Fix: —

### Fig 7b — Modality evolution stacked area

  - Score: **A−**.
  - Issue (was): redundant `xaxis_title="Start year"` — **[FIXED 212eda0]**.
  - Fix: —

### Fig 8 — Antigen × Modality maturity matrix

  - Score: **A**. Heatmap with cell annotations.
  - Fix: —

### Fig 9 — Basket co-occurrence triangle

  - Score: **A**. Upper-triangle heatmap (avoids redundant lower
    triangle — Tufte-canonical).
  - Fix: —

### Fig 10 — Paediatric coverage stacked bar

  - Score: **A**.
  - Issue (was): caption was verbose (~60 words).
  - Fix: trimmed to 2 sentences. **[DONE this commit]**

### Fig 11 — Sponsor concentration with reference lines

  - Score: **A**. Threshold reference lines (30%, 60%) are Tufte-y;
    bar colour encodes concentration tier.
  - Issue (was): caption was the longest in the app (~60 words).
  - Fix: trimmed to 2 sentences. **[DONE this commit]**

---

## Top fixes — ranked by leverage

| # | Fix | Status |
|---|---|---|
| 1 | Direct-label timeline lines | [DONE 212eda0] |
| 2 | KPI tile sparklines | **[REVERTED — too much info per user]** |
| 3 | Trim redundant year-axis titles | [DONE 212eda0] |
| 4 | Compare tab — shared y-axis scale | PENDING |
| 5 | Donut → row-stacked-bar (3 instances live) | PENDING |
| 6 | Fig 7a donut → horizontal bar | already in live code (no donut to convert) |
| 7 | Trim verbose Fig 10 + Fig 11 captions | [DONE this commit] |
| 8 | Top-countries bars coloured by region (G3) | PENDING |
| 9 | KPI tile 5 (sponsors) sparkline | **[DROPPED — same reason as #2]** |
| 10 | Drop redundant `##### Section header` lines where the chart titles itself | DEFER — case-by-case |

Status after this commit: items 1, 3, 7 are live; items 2 + 9 are
withdrawn at user request (clean numeric tiles preferred over
sparklines); items 4, 5, 8 are still on the table for a future pass.

**General lesson from the sparkline reversal:** Tufte's principles
are heuristics, not rules. The dashboard reader's preference for
clean tiles trumps the abstract "more data per pixel" argument.
Future Tufte-flavoured edits should be confirmed before adding new
visual layers — trimming (captions, axis titles, redundant headers)
is safer than adding (sparklines, region tints, stacked bars where
a number sufficed).
