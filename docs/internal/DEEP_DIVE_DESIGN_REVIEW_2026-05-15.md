# Deep Dive UI review — 2026-05-15

Scope: the 6 Deep Dive sub-tabs (By disease · By antigen · By product · By
sponsor · By time · Compare) — both landscape and focused views. Read-only
walk of `app.py:5651-8123`. Findings tier-ranked by severity. The May 2026
restructure has already paid down most foundational UX debt (TOC, click-to-
focus, sticky picker, click-to-focus tables) — the remaining work is
mostly trimming dead weight and tightening cross-tab consistency.

---

## Tier 1 — drop or rework (panel doesn't earn its space)

### T1.1 By product — "Product landscape — phase mix" panel
**`app.py:6835-6932`**
A single 100% horizontal-stacked-bar with trial-count labels for the top
10 products. The user already deleted today's enrollment box-plot from
the same panel; what's left repeats data the product portfolio table
directly above already carries (FurthestPhase column + Trials column =
the same answer). Reader-value: zero new pattern, ~420 px of vertical
space. **Severity**: Eyesore. **Direction**: drop the chart entirely; the
table is the hero. Keep "Annual trial starts by product" timeline below
— that one DOES add a pattern (year trajectory) the table can't show.
**Rule violated**: pharma reads chart-then-table; here the chart is
strictly downstream of the table.

### T1.2 By time — "Top sponsors heatmap" with sub-3 median cell counts
**`app.py:7609-7674`**
A 10-row × 5-7 column heatmap of sponsor activity by year. Each cell
shows count (most are 0, 1, or 2). Same failure mode as the box-plot
the user has dropped multiple times: median N ≤ 3 means the gradient
can't carry information, the eye reads it as a sea of low-saturation
cells with a few highlights. **Severity**: Eyesore. **Direction**:
replace with a top-sponsors-by-recent-activity sparkbar list (sponsor +
last-year count + 5-year sparkline as text glyph), or drop in favour of
the existing "Year-over-year movers" table directly above which already
surfaces sponsor risers/fallers. **Rule violated**: chart type vs data
shape; the user's standing dictum on sub-3 medians.

### T1.3 By antigen focused — third "help" tooltip wedged into Distinct sponsors
**`app.py:6510`**
`st.metric("Distinct sponsors", ..., help=f"across {len(_countries)}
countries")` — the country count is buried inside a tooltip on a tile
whose label is "sponsors". Two unrelated numbers welded together.
**Severity**: Polish. **Direction**: either show countries as the 4th
metric tile (replacing or augmenting "Distinct products" — both are
pharma-relevant), or drop the countries-in-tooltip altogether.
**Rule violated**: one tile, one number.

### T1.4 By disease landscape — "Open-trial age" panel uses a glyph emoji
**`app.py:5886`**
"✓ All open trials are <3 y old — landscape is fresh." Single ✓
character is the only emoji in any Deep Dive panel. Violates the
established enterprise-flat aesthetic (no emojis in any committed
flat-mode artifact since `5adf7e2`). **Severity**: Eyesore. **Direction**:
drop the glyph; the sentence stands without it.
**Rule violated**: enterprise-flat styling preference (memory file).

### T1.5 By sponsor-type drilldown — mini count tables instead of sparkbars
**`app.py:7387-7400`**
"Antigen targets" + "Product types" rendered as 2-column dataframes
with `_mini_count_cols(...)`. Every OTHER drilldown in Deep Dive uses
`_topn_sparkbar_html(...)` for the same shape of data (disease focused
view `app.py:6014-6032`, antigen focused view `app.py:6628-6672`,
sponsor focused view `app.py:7228-7259`). **Severity**: Eyesore.
**Direction**: swap to `_topn_sparkbar_html` for visual parity. The
table version was the original design that the rest of Deep Dive moved
past.
**Rule violated**: consistency (D in axis list).

### T1.6 By sponsor type drilldown — no charts, only tables
**`app.py:7368-7444`** (the `else:` branch when `pick != "—"`)
Industry/Academic/Gov/Other drilldown shows top sponsors then mini
tables then trial table. Only Deep Dive focused view with zero
visual gestalt before the trial table. **Severity**: Polish.
**Direction**: add a phase-mix horizontal-stacked bar at the top,
matching other focused views' "Charts" row.
**Rule violated**: logical flow (E).

---

## Tier 2 — adjust the chart type to fit the data

### T2.1 By disease focused — Phase mix uses vertical `make_bar`, not the shared phase stack
**`app.py:5962`** (and antigen focused at `app.py:6555`, sponsor focused at
`app.py:7154`)
The three focused views render the "phase mix" panel as a vertical
`make_bar(...)` (one bar per phase, 240 px). The landscape views use
the shared `_deepdive_phase_stack(...)` horizontal-stacked treatment
which encodes both volume and proportion. Two visual languages for the
same conceptual question.
**Severity**: Eyesore. **Direction**: standardise on
`_deepdive_phase_stack` OR define a "single-row phase stack" helper
that produces a 1-row horizontal stacked bar suitable for a focused
view. Right now reader has to re-learn what "phase mix" looks like
between landscape and focused.
**Rule violated**: consistency (D); chart-to-data alignment (C).

### T2.2 By antigen landscape — phase mix in column 2 uses 100% stacked, but only chart of its kind
**`app.py:6258-6386`**
The aligned subplot (emergence lollipop + phase stack) is a beautifully
executed shared-y-axis figure, but its 100%-normalisation hides the
trial-count gradient that the rest of Deep Dive's phase-stacks show
on absolute counts. A reader scanning across tabs sees absolute counts
in disease/sponsor landscapes and percentages here. **Severity**:
Polish. **Direction**: keep the alignment trick (it's the best chart
on the dashboard) but switch to absolute counts OR add a tiny
"(N=…)" trial-count annotation to the right edge of each row — same
visual pattern as the By product landscape's trial-count labels.
**Rule violated**: consistency (D).

### T2.3 By antigen focused — "Annual trial starts" by `_Disease` group
**`app.py:6562-6567`**
The third chart in the focused view's chart row is a `_deepdive_timeline`
keyed on `_Disease`. When the user picks a niche antigen with 2-3
trials, this becomes 2-3 line segments across maybe 2 years — a
degenerate timeline that doesn't communicate anything. **Severity**:
Eyesore. **Direction**: gate this chart behind `N >= 5 trials` AND
`distinct years >= 3`; below that, replace with a one-line caption
("First trial: 2023. Most recent: 2025."). Same compute, way better
density.
**Rule violated**: B (density vs noise) + F (sparse states).

### T2.4 By product landscape — annual starts top-6 timeline
**`app.py:6933-6939`**
Most named products have 1-3 trials. Top-6 by trial count = the long-
tail starts at ~3 trials. A 6-line timeline where most lines are 1-2
trials in 1-2 years is the same problem as T2.3. **Severity**:
Eyesore. **Direction**: drop entirely, or only render when the dataset
has ≥3 products each with ≥5 trials in ≥3 distinct years. The product
table above already shows year range.
**Rule violated**: chart-to-data (C); user's stand on sub-3 medians.

### T2.5 Compare "Phase mix" — grouped vertical bars on low-N pairs
**`app.py:7910-7958`**
Grouped vertical bars work at N≥5 each side; when user picks a 1-
trial sponsor it becomes 1 bar vs 6 bars — visually broken.
**Severity**: Latent. **Direction**: gate on `min(N_a, N_b) ≥ 3`;
below that show two text rows of phase counts.
**Rule violated**: F.

---

## Tier 3 — cross-tab consistency fixes (small, mechanical)

### T3.1 In-tab TOC present in 3 of 6 focused views
**`app.py:5939, 6516, 7130`** present;
**`app.py:6731+ (By product) and 7368+ (By sponsor type drilldown)`**
absent.
By disease, By antigen, By sponsor-specific have `_render_section_toc`.
By product (which IS a focused view inherently) and By sponsor-type
drilldown don't. Once a pattern lands across half the surface, missing
instances feel like bugs. **Severity**: Polish. **Direction**: add TOC
to both. By product's anchors: Pivot / Landscape / Timeline / Trials.
**Rule violated**: D (cross-tab consistency).

### T3.2 Null-bucket labels inconsistent
**`app.py:5969`** ("Other") vs **`6533`** ("Unknown") vs **`6011`**
("Unclear") vs **`6646`** ("Unknown") vs **`6584`** ("(unnamed)") vs
**`6011`** product type "Unclear" vs sponsor donut "Other".
Six different labels for "the data is missing for this row" across
five panels. Reader can't tell if "Unknown" and "Unclear" mean
different things or not. **Severity**: Polish. **Direction**: pick
two — one for categorical (e.g., "Unspecified") and one for naming
fields (e.g., "(unnamed)") — and apply uniformly via a small constant.
**Rule violated**: D.

### T3.3 Focus picker label conventions vary
By disease: `"Focus on a disease"` + `"—"` (`app.py:5758, 5760`).
By antigen: `"Focus on an antigen target — N available"` +
`"(any — show landscape)"` (`app.py:6108, 6109`).
By sponsor type: `"Focus on a sponsor type"` + `"—"` (`app.py:7080`).
By sponsor specific: `"Focus on a specific sponsor"` + `"—"`
(`app.py:7087`).
The "(any — show landscape)" verbose option in By antigen is the
odd one out. **Severity**: Polish. **Direction**: standardise on
`"—"` as the "no focus" sentinel everywhere; the help text already
explains the landscape behaviour.
**Rule violated**: D.

### T3.4 Heatmap colourscale varies per tab
By disease landscape: default Blues (`app.py:5818`).
By antigen landscape: `colorscale="Purples"` (`app.py:6169`).
By sponsor landscape: `colorscale="Greens"` (`app.py:7351`).
By time phase-progression: `colorscale="Blues"` (`app.py:7724`).
Three different palettes for the same chart type within Deep Dive.
**Severity**: Polish. **Direction**: pick one (Blues fits the navy
primary in `THEME`); the per-tab variation reads as decorative, not
data-encoding.
**Rule violated**: DESIGN_SYSTEM.md (THEME colour discipline).

### T3.5 Empty-state vs info-message inconsistency
**`app.py:5727+5731` (disease), `6476` (antigen focused), `6746`
(product)**. Two patterns: rich `_empty_state_panel` for sidebar-
filter empty + bare `st.info(...)` for focus-pick empty.
**Severity**: Polish. **Direction**: route every empty branch
through `_empty_state_panel` with a caller_id; the relax-filter
hint is the value-add. **Rule violated**: D + audience brief E1.

### T3.6 Trial table column order varies across focused views
**Disease `app.py:6034-6037`, Antigen `6694-6699`, Sponsor `7284-7289`,
Product `6966-6971`.** Same NCT scanned across tabs has different
column neighbours each time. **Severity**: Polish. **Direction**:
define one canonical `_DEEP_DIVE_TRIAL_COLS` constant.
**Rule violated**: D.

### T3.7 Compare tab — no `_section_question` orientation caption
Every other Deep Dive sub-tab calls `_section_question(...)` after
`st.subheader(...)`. Compare does too (`app.py:7762-7766`) — but the
text is the longest of any tab (3 lines wrapped). Other tabs hit one
line. **Severity**: Polish. **Direction**: tighten to one sentence:
"Pick any two diseases, antigens, modalities, sponsors, or products
— matched side-by-side."
**Rule violated**: terse-caption preference (user).

---

## Tier 4 — flow / hierarchy / empty-state issues

### T4.1 By antigen focused — inconsistent help-text on metric strip
**`app.py:6504-6513`** Only `Trials` and `Distinct sponsors` carry
`help=...`; `Open / recruiting` and `Distinct products` don't.
**Severity**: Polish. **Direction**: equalise — either all tiles
carry help or none do. **Rule violated**: B (density).

### T4.2 By time — no focused-view at all
By time is the only sub-tab with no landscape→pick→focused flow.
**Severity**: Latent. **Direction**: add cohort-year drilldown
(click a year column on the phase-progression heatmap → cohort
focused view). The "what trials started in 2024 and where are they
now" question the heatmap teases is currently un-answerable
in-tab.

### T4.3 By time — phase-progression heatmap caption is too long
**`app.py:7683-7690`** 60-word how-to-read paragraph. User prefers
title + chart shape to carry meaning. **Severity**: Polish.
**Direction**: cut to 1 sentence; methodology lives in Methods.
**Rule violated**: terse-caption preference.

### T4.4 Compare — gap-of-magnitude warning missing on lopsided pairs
**`app.py:7770-7822`** Picking a 50-trial sponsor against a 2-trial
sponsor produces a paired view where one side's bars are 25× the
other — accurate but the user can mistake it for "look how much
bigger A is" when really their slice is sub-significant.
**Severity**: Latent. **Direction**: when `max/min > 10`, render a
one-line caption above the panels noting the gap.
**Rule violated**: F.

### T4.5 By disease focused — no product portfolio table
By antigen + By sponsor focused both carry a Product Portfolio table
(`app.py:6575-6624, 7174-7226`). By disease focused has sparkbars
only. Pharma asking "what products are in IIM trials?" gets no
direct answer. **Severity**: Polish. **Direction**: add a Product
Portfolio table to the disease focused view, same shape as the
existing two. **Rule violated**: pharma-centred framing.

### T4.6 Focused view on a 1-trial slice reads as ceremony
For antigen/sponsor/product focused views, an N=1 pick still
renders the 3-chart row, 4-metric strip, portfolio table, trial
table — all degenerate. **Severity**: Polish. **Direction**: at
`N == 1` collapse to a single info line and jump to the trial
drilldown.
**Rule violated**: F.

### T4.7 By product landscape — two-step affordance phrasing
**`app.py:6796`** "click any row to see that product's trial list,
then click a trial for full details" — only Deep Dive table that
documents a two-step click. **Severity**: Polish. **Direction**:
tighten to "click any row for trials", or route the first click
direct to the trial table.
**Rule violated**: D.

---

## Recurring patterns worth flagging

Four panel motifs repeat across all 6 sub-tabs: **phase mix**,
**sponsor split**, **top-N breakdown** (countries/antigens/diseases),
and **trial table → drilldown**. Each is rendered slightly
differently per tab — `make_bar` here, `_deepdive_phase_stack`
there, donut elsewhere, sparkbar elsewhere again. Four reusable
panel helpers would collapse ~600 LOC of near-duplicate code into
one source of truth AND auto-resolve T1.5, T2.1, T3.4, T3.5, T3.6.
Not prescribing the refactor — just flagging that duplication is
the dominant code-shape across Deep Dive.

---

End of review.
