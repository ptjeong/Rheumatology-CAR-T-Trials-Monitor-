# Deep Dive — UX restructure analysis

> **Update (post-2026-05-15):** most of Stages 1 + 2 from this brief
> have shipped. The current Deep Dive sub-tab structure is: By
> disease, By antigen (formerly "By target"; now with a modality
> sub-filter), By product (its own sub-tab, was appended under By
> target), By sponsor (type + specific consolidated into one tab),
> By time (with year-end projection toggle), Compare. "By geography"
> was removed entirely — all geographic content lives in the top-
> level Geography / Map tab, which now uses the same picker-on-top /
> landscape-default UX as the Deep Dive sub-tabs. The references
> below to "By target" / "By geography" reflect the pre-restructure
> state; they're preserved for historical context.

The Deep Dive section is information-dense and powerful, but
**hard to navigate intuitively**. A first-time visitor doesn't
know which sub-tab answers their question. A returning visitor
loses their place when they scroll. Two visitors can't share a
specific view via link. This brief diagnoses those frictions and
proposes a UX-focused restructure.

The companion brief `DEEP_DIVE_AUDIENCE_ANALYSIS.md` covers WHAT
to show (panel-level keep/drop decisions for academic vs pharma
audiences). This brief covers HOW to show it (information
architecture, affordances, state, interaction patterns).

---

## Walking the current UX as a new user

A clinician opens the dashboard for the first time. She wants
"trials for refractory myositis, autologous CD19, in Europe,
recently registered". Here's her path:

  1. Lands on Overview tab. Sees the sunburst hero. Reads "OK,
     this dashboard has more than I expected." Clicks Deep Dive.
  2. Lands on Deep Dive → By disease (default sub-tab). Sees
     "Disease-entity focus" subheader. Scrolls. Sees Disease ×
     Antigen heatmap. "Where's myositis?" Tries to find IIM.
     Spots a cell. "Cool, 20 trials. How do I see them?"
  3. Scrolls past phase composition, trial-age boxplot, hits a
     **picker** halfway down: "Drill into a disease". Picks IIM.
     Sees 5 mini-charts. None of them filter by "autologous" or
     "Europe" — those are sidebar filters.
  4. Returns to sidebar. Sets status filter, year filter, modality
     filter, country filter. Every chart in Deep Dive updates,
     **including the ones above her IIM pick that she's not
     looking at anymore**. Scrolls back down.
  5. "Where's the CD19 detail? Let me check By target." Clicks the
     sub-tab. Lands at the top of the By target page. Sees Target
     × Disease heatmap. "I already saw IIM × CD19 in the heatmap
     on the previous tab — this is just transposed." Scrolls. Finds
     the target picker. Picks CD19. Sees 6 different mini-charts —
     not the same set as the disease drilldown.
  6. "OK I want autologous specifically. Where's modality?" Scrolls
     through By target's CD19 drilldown — finds a Modality
     breakdown bar. Clicks it. **Nothing happens** — it's not
     interactive.
  7. "Where do I see only autologous CD19 trials?" Goes back to
     the sidebar, sets the modality filter. Every chart updates
     again. Now she's looking at autologous CD19 in IIM in Europe
     in 2025. She wants to share this view with a colleague.
  8. Copies the URL. It's `app.streamlit.io/...` — no filter
     state encoded. Colleague gets a fresh dashboard.

Total friction points: ~8. Total navigation actions: ~15. Total
time to answer the question: 5+ minutes for an experienced user,
indefinite for a first-time one.

---

## What's broken — diagnostic findings

### 1. Tab labels say WHERE, not WHAT

Current: "By disease" / "By target" / "By sponsor" / "By geography"
/ "By time" / "Compare".

These name the **slicing axis**, not the **question answered**.
A user thinking "I want to see who's competing with me on CD19"
doesn't know to click By target → CD19 → modality / disease /
phase. The mental translation is "competition → axis → what
heuristic do I use?" — that's expert behaviour, not intuitive.

### 2. The same picker pattern is implemented 6 different ways

Every Deep Dive sub-tab has the pattern:
  - Landscape charts at top (showing all)
  - Picker (selectbox) midway
  - Drilldown charts below

But each tab implements this slightly differently — different
section headings, different picker labels, different drilldown
column counts (3 vs 4), different "no data" messages. The reader
re-learns the pattern in every tab.

### 3. The picker is buried mid-page

After 1-3 landscape charts plus the section divider, the picker
selectbox is several hundred pixels down. Users scroll, see
charts, scroll more, find picker, change selection, scroll BACK
to remember context. The picker should be at the TOP of the
drilldown section, anchored, sticky.

### 4. Cross-tab navigation is invisible

A user looking at the Disease × Antigen heatmap who wants to
follow up on "CD19 column" has no path. The chart is non-
interactive. The only way to follow that thread is:
  - Mentally remember "CD19"
  - Manually click By target sub-tab
  - Scroll to find the target picker
  - Find CD19 in the dropdown
  - Pick it

That's 4 manual steps for one conceptual "drill into this".

### 5. Filter state is opaque

The sidebar holds 5-8 filters (status, year, modality, sponsor
type, country, etc.). Once set, **there's no visible reminder of
what's active** except by re-opening the sidebar. Charts in Deep
Dive show filtered data without indicating what was filtered.

Two failure modes:
  - User forgets filters are on, misinterprets a sparse chart as
    "the field is small"
  - User wants to clear filters for a fresh look — has to remember
    each filter and reset it individually

### 6. Drilldown state doesn't persist across navigation

If a user picks IIM in By disease, then switches to By target,
their disease context is lost. The By target tab opens with the
default selection (alphabetically first target). They have no way
to say "show me By target FILTERED TO IIM".

This is the core information-architecture failure. The drilldown
state should be **one entity per axis** (one disease, one target,
one sponsor, one country, one product) and **every tab respects
all dimensions of the current selection**.

### 7. URL state is not persistent

You can't share a Deep Dive view. Filter state, picker state, tab
state — none of it round-trips through the URL. Two users can't
collaborate by sending links. Reproducibility is via snapshot
pin, which is the wrong tool for sharing a view.

### 8. Vertical scroll fatigue

Each Deep Dive sub-tab is 1500-3000 px tall. There's no in-tab
navigation. No mini-TOC. No "jump to section". Section dividers
are horizontal lines that don't help orientation.

### 9. Visual hierarchy within tabs is flat

Every panel is presented at the same visual weight. A high-value
heatmap looks the same as a low-value drilldown bar. The reader
has to figure out "what should I look at first?" — every time.

### 10. No empty / loading states

When a filter combination produces zero results, panels show "No
trials in the current filter selection." — accurate, but
unfriendly. The user doesn't know which filter to relax. Loading
states don't exist at all (Streamlit reruns are atomic; users see
the whole page disappear and reappear).

---

## Design principles for the restructure

### Principle 1: Intuition over expertise

A first-time visitor should be able to answer a clinical question
in 3 clicks without reading documentation. Defaults should be
sensible, labels should be question-shaped, and the next step
should always be visible.

### Principle 2: One picker, all tabs

The Deep Dive should have a **persistent focus state** — a single
"what am I looking at right now?" badge that's shared across
sub-tabs. Pick IIM once; every tab updates. Pick CD19; same. The
six sub-tabs become **lenses on the same focus**, not separate
mini-apps.

### Principle 3: Spatial consistency

Every sub-tab follows the same layout:
  1. Header: "Lens — what this tab shows you" (1 line)
  2. Active filters chip strip (clickable to deactivate)
  3. Focus card (when a focus is set)
  4. Landscape section (heatmap + 1-2 supporting)
  5. Drilldown section (full-width chart + supporting cards)

No surprises. Once the user learns one tab, they know all six.

### Principle 4: State is the URL

Everything that defines a view — filters, focus, sub-tab — round-
trips through `st.query_params`. Users can bookmark, share,
back-button. Two users can collaborate by sending links. The
dashboard becomes a tool, not an experience.

### Principle 5: Click-to-navigate

Tables and heatmaps should be interactive. Click a disease cell →
focus that disease. Click an antigen row → focus that target.
Click a sponsor name in a table → focus that sponsor. The
information architecture should match the data's natural graph
shape — every entity is clickable to drill into.

### Principle 6: Progressive disclosure

Every tab opens at "summary": 2-3 key panels visible immediately.
Additional panels live behind "Show more" / expander affordances.
Power users expand everything; casual users see a clean
overview.

### Principle 7: Visual hierarchy

Three weight tiers:
  - **Hero**: the one chart that answers the tab's question (full-
    width, large, top of fold)
  - **Supporting**: 2-4 charts that add context (medium, below
    fold, equal weight to each other)
  - **Detail**: drilldown / table / methodology (small, behind
    expanders, on-demand)

---

## Specific recommendations

### A. Information architecture

**A1. Rename sub-tabs to question-shaped labels**

  - "By disease" → "Disease landscape"
  - "By target" → "Antigen landscape"
  - "By sponsor" → "Sponsor activity"
  - "By geography" → "Geographic spread"
  - "By time" → "Temporal patterns"
  - "Compare" → "A vs B comparator"

Slight verbosity, immediate clarity. (Counter-proposal: keep "By
X" but add per-tab orientation captions — see B5.)

**A2. Persistent focus bar above all sub-tabs**

Render a single component at the top of Deep Dive (above the
`st.tabs(...)` call):

```
🎯 Focus: [Disease: SLE ▾] [Target: any ▾] [Sponsor: any ▾]
         [Country: any ▾] [Product: any ▾]
```

These are five selectboxes laid out as one row, each with an
"any" default. Picking values here updates session_state. Every
sub-tab below reads from that state.

The current per-tab pickers (`pick = st.selectbox(...)` in disease
/ target / sponsor / country / product tabs) get replaced by
**reading from this shared state**. The user picks once, sees the
focus reflected across every tab.

**A3. URL-state binding**

Use `st.query_params` to serialise the focus + filter state:
`?disease=SLE&target=CD19&modality=Allo&status=open&year_min=2024`

On page load, read query_params → seed session_state → render.
On any control change, write back to query_params. Streamlit's
modern API supports this round-trip.

**A4. Drop the appended "By product" / "specific sponsor" panels**

The current code appends two extra sections to By target and By
sponsor (`deep_sub_product = deep_sub_target`). This was a
pragmatic shortcut but it hides pharma-critical content. With the
shared-focus architecture (A2), per-product and per-sponsor
detail comes "free": pick a product or sponsor in the focus bar,
the rest of the tabs respect it. No appended sub-sections needed.

### B. Within-tab layout

**B1. Sticky picker bar inside each tab**

Even with the shared focus (A2), each tab may have its own axis-
specific control (e.g., the timeline color-axis radio in By time).
These should sit in a sticky container at the top of the tab so
they don't scroll out of view.

Streamlit doesn't have native sticky containers but a thin CSS
shim with `position: sticky; top: 0` on a wrapper div works.

**B2. Section cards instead of long scroll**

Wrap each panel in a styled container:

```
┌─────────────────────────────────────┐
│ Disease × Antigen heatmap         ⓘ │  ← title + info icon
├─────────────────────────────────────┤
│ [chart]                             │
├─────────────────────────────────────┤
│ ▾ Show data + methodology           │  ← collapsible footer
└─────────────────────────────────────┘
```

The collapsible footer hides the caption + CSV download by
default. Casual users see a clean chart; power users expand to
get the methodology.

This is implementable with a `_panel(title, chart, footer)`
helper. ~40 LOC, applied to every Deep Dive panel.

**B3. In-tab navigation TOC**

For tabs taller than 2 viewports, render a thin right-side TOC:

```
                    │ ↓ Heatmap
                    │   Phase composition
                    │   Box plot
                    │ ↓ Drilldown
                    │   Phase mix
                    │   Top countries
```

Each entry is a button that scrolls to the section. Streamlit
supports `st.markdown(f'<a href="#section-id">…</a>')` with
section anchors. ~30 LOC including section anchors.

**B4. Three-tier visual hierarchy per tab**

  - Hero panel (full-width, 480 px tall)
  - Supporting panels (2-3 in a row, 320 px tall each)
  - Detail / drilldown (behind a collapsible "Drill into one X" expander)

This forces ranking: every tab must identify ITS hero panel.
Disease tab's hero = Disease × Antigen heatmap. Target tab's hero
= Target × Disease heatmap. Sponsor tab's hero = Sponsor type ×
Disease heatmap. Etc.

**B5. Per-tab orientation caption (1 sentence)**

At the top of each tab, one bold sentence telling the reader what
question this tab answers:

  - Disease landscape: "**Which indications have the most activity,
    and which antigens are being tried in each?**"
  - Antigen landscape: "**Which antigens dominate, in which diseases,
    and how have they emerged over time?**"
  - Sponsor activity: "**Who's sponsoring trials, how concentrated is
    each indication, and what's any single sponsor's portfolio?**"
  - Geographic spread: "**Where are sites located, and how does
    activity vary by country / region?**"
  - Temporal patterns: "**How is the field growing, by what metric,
    and how do recent cohorts mature?**"
  - Comparator: "**Pick any two diseases or antigens — side-by-side
    mini-dashboards.**"

### C. Cross-linking and interactivity

**C1. Click-to-focus on tables**

Wherever a table shows entities (disease, target, sponsor,
country, product), make rows clickable to set focus:

```python
event = st.dataframe(df, on_select="rerun", selection_mode="single-row")
if event.selection.rows:
    selected_entity = df.iloc[event.selection.rows[0]][entity_col]
    st.session_state.focus_disease = selected_entity
    st.rerun()
```

After the click, the focus bar (A2) updates and every tab
reflects the new selection.

**C2. Heatmap cell-click cross-navigation**

Plotly supports `customdata` on traces. Streamlit's
`plotly_events` (or `streamlit-plotly-events` community
component) reads click events. Click a cell in the Disease × Antigen
heatmap → set BOTH focus_disease and focus_target → user is now
viewing the intersection across every tab.

This is the killer feature. Requires the streamlit-plotly-events
component. ~50 LOC integration + plumbing.

**C3. "Follow this" buttons next to entity mentions**

In drilldown tables that mention entities (e.g., a disease
drilldown shows "Top sponsors: Cabaletta Bio, BMS, Novartis"),
add a small button next to each:

```
Cabaletta Bio  [→ Focus on this sponsor]
```

Click → set focus_sponsor → every tab updates.

### D. State and persistence

**D1. URL-bound filter + focus state**

(See A3.) Treat `st.query_params` as the canonical store. Every
filter and focus is a URL key. Bookmarking saves the view.
Sharing a link reproduces it.

**D2. Active-filter chip strip**

Render at the top of Deep Dive (below the focus bar):

```
Filters: [Status: Open/Recruiting ✕] [Year: ≥2023 ✕] [Region: NA ✕]
[Clear all]
```

Each chip is clickable to deactivate. Makes the active filter
state always visible.

**D3. "Reset focus" button**

Single button that clears all focus selections (disease, target,
sponsor, country, product all → "any"). One-click escape hatch
from a drilled-in view.

### E. Empty / loading / error states

**E1. Friendly empty states**

When a filter combination produces zero results, show **what was
filtered** + **how to relax**:

```
No trials match: Status=Open, Year≥2025, Modality=Allo, Country=Brazil

Try relaxing:
  [✕] Country=Brazil (try removing — 23 trials match the other 3 filters)
  [✕] Year≥2025  (try removing — 8 trials match the other 3 filters)
```

The "8 trials match if you remove this" hint requires a small
compute (count(df_filt minus this filter)) per filter — cheap.

**E2. Skeleton placeholders for chart compute**

When a chart takes >250 ms to compute (heatmaps, Sankey), show a
fixed-height grey placeholder rectangle while the data is being
prepared. Streamlit's `st.empty()` + `st.spinner()` give us a
crude version; a CSS skeleton would be smoother but adds LOC.

---

## Proposed staged implementation

### Stage 1 — Foundations (~200 LOC, single PR)

  - **A2** Persistent focus bar above the sub-tabs (single source
    of truth for which disease / target / sponsor / country /
    product the user is exploring)
  - **A3** URL-state binding via `st.query_params` for filters +
    focus
  - **D2** Active-filter chip strip
  - **D3** "Reset focus" button
  - **B5** Per-tab orientation captions

After Stage 1, the cognitive model shifts: focus is one global
state, tabs are lenses. Users who learn the focus bar can drive
the dashboard from one row of controls.

### Stage 2 — Within-tab layout (~250 LOC)

  - **B1** Sticky picker bar (per-tab axis-specific controls)
  - **B2** Section-card wrapper with collapsible footer (`_panel()`
    helper applied across all Deep Dive panels)
  - **B4** Three-tier visual hierarchy (hero / supporting / detail)
  - **E1** Friendly empty states with "relax filter" hints

After Stage 2, every tab reads the same way, the most important
chart is unambiguously the hero, and the long-tail drilldowns
hide behind expanders.

### Stage 3 — Interactivity (~300 LOC)

  - **C1** Click-to-focus on tables (using `st.dataframe`'s
    `on_select="rerun"`)
  - **C2** Plotly cell-click cross-navigation (requires
    streamlit-plotly-events; verify component is maintained and
    compatible with our Plotly version)
  - **C3** "Follow this" buttons next to entity mentions in
    drilldown tables

After Stage 3, the dashboard reads like a graph: every entity is
a node, every chart is a navigable surface. The 5-minute "find
the IIM CD19 European cohort" task becomes 3 clicks.

### Stage 4 — Polish (~150 LOC)

  - **A1** Sub-tab label rename
  - **B3** In-tab TOC for tall tabs
  - **E2** Skeleton loading states
  - Drop appended sections (A4)

Stage 4 is cosmetic / nice-to-have. Skippable until users complain.

---

## Net change

  - Stage 1 alone: dashboard becomes shareable + filter-transparent.
    Maximum impact per LOC.
  - Stage 1+2: dashboard becomes consistent across tabs, reads at
    multiple zoom levels (hero / supporting / detail).
  - Stage 1+2+3: dashboard becomes navigable as a graph; cross-axis
    questions take 1-2 clicks instead of 5+.

Each stage is independently valuable and could ship without the
others. Stage 1 has the highest impact-per-LOC; Stage 3 has the
biggest UX-quality leap but the highest implementation cost
(community component dependency).

---

## Out of scope

  - Mobile-first redesign (Streamlit on small screens is a known
    pain; not addressing here)
  - Multi-page Streamlit app refactor (the tabs primitive is
    good enough; moving to `pages/` would lose the shared filter
    sidebar)
  - Full keyboard-shortcut navigation (Streamlit limits this; not
    worth the engineering)
  - Theme / dark-mode toggle (separate concern, NEJM-style aesthetic
    is the right default per existing preferences)

---

## Decision required

Which stage(s) to implement? Recommendations:

  - **Stage 1 only** (~200 LOC): biggest cognitive shift, no new
    dependencies. Safe ship.
  - **Stages 1 + 2** (~450 LOC): adds visual hierarchy + within-
    tab consistency. Recommended baseline.
  - **All four** (~900 LOC): full restructure, requires community
    component for click events. Recommended if Stage 1+2 prove
    valuable.

Stage 1 should ship first regardless. The shared-focus + URL-state
foundation enables everything else.
