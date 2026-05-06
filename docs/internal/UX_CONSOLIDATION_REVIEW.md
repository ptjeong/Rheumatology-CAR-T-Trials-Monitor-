# UX consolidation review — rheum dashboard
*Date 2026-05-06 · author: Claude · responding to user "I feel that
it has become overly complicated in some ways"*

After the Phase 0–6 expansion the dashboard has 7 top-level tabs and
~50+ figures. The expansion delivered analytical depth but the user
correctly flags that depth ≠ usability. This doc is a redundancy +
ease-of-use audit with concrete consolidation proposals, ordered
high-impact first.

## TL;DR — the 5 biggest wins (do these first)

1. **Drop the "Compare" sub-tab** — embed the A/B picker INSIDE the
   By-disease and By-target tabs as an optional "+ vs B" toggle
   (saves 1 sub-tab, removes the conceptual duplication of the
   comparator-as-a-thing).

2. **Merge "By sponsor type" + "By sponsor"** into a single
   **Sponsor** tab with a "View by:" radio at top (`All sponsors` |
   `Industry` | `Academic` | `Government` | `Specific sponsor: <pick>`).
   Saves 1 sub-tab; one mental model for sponsor analysis.

3. **Drop the Overview "Landscape at a glance" 4-panel section** —
   it duplicates what the sunburst + Pub Figs already show. The
   sunburst answers "what's in the dataset?"; Pub Fig 5 answers
   "trials per disease". The 4-panel grid in the middle is an
   unloved third version. Replace with a single "Family headline"
   tile row (already exists) + the new newsroom strip.

4. **Drop the "By product" sub-tab** — make Product a filter inside
   the **Target** tab (since every named product has a single
   target by construction). The product table becomes a sub-view of
   target. Saves 1 sub-tab; removes the inconsistency that products
   live alongside targets/sponsors as a peer when they're really a
   sub-classification of target.

5. **Pin a consistent layout pattern** across the remaining sub-tabs:
   `top: aggregate landscape (≤3 figures)` →
   `middle: drill-into-one (1 dropdown)` →
   `bottom: trial list with row-click drilldown`.
   Audit each sub-tab against this template; cut figures that don't
   fit one of the three slots.

After these 5 changes Deep Dive shrinks from 8 → 5 sub-tabs:
**Disease · Target · Sponsor · Geography · Time**.

## Detailed redundancy audit

### Overview tab

Currently:
1. Newsroom strip (NEW Phase 4 — KPI tiles + Top movers + Recently added)
2. Sunburst hero + headline tiles
3. "Landscape at a glance" 4-panel (Trials by disease / by target /
   by phase / by year)
4. Snapshot diff (collapsed)
5. PRISMA expander (collapsed)

**Issues:**
- Sections 1 and 3 are both "summary panels" — competing for the
  same role.
- Panel 1 of section 3 ("Trials by disease") duplicates Pub Fig 5 +
  Deep Dive By disease "trials per disease" bar.
- Panel 3 ("Phase distribution") duplicates Pub Fig 2 + Deep Dive
  By disease phase composition.

**Proposal:**
- Sunburst hero + headline tiles FIRST (already correct after the
  recent reorder)
- Newsroom strip (KPIs + recently updated; drop top movers because
  YoY is unreliable mid-year)
- Snapshot diff
- PRISMA expander
- DROP "Landscape at a glance" entirely

The user previously said the sunburst should be the visual anchor;
let it be.

### Geography / Map tab

Currently:
1. Regional aggregates strip (NEW Phase 5)
2. World choropleth + open-sites
3. Country leaderboard
4. Country drilldown
5. Country emergence scatter (NEW Phase 5)
6. Multi-country trials table (NEW Phase 5)

**Issues:**
- Section 1 (regional aggregates) tells me totals; section 3
  (country leaderboard) tells me country totals. Mostly fine but
  the region/country relationship is not made explicit.
- Section 5 + 6 are bottom-of-page; users may not scroll there.

**Proposal:**
- Keep regional + map up top
- Move emergence scatter into a collapsible "Trends" expander
- Move multi-country table into the country drilldown's right column

### Deep Dive

8 sub-tabs is the most acute problem. Proposed final structure:

| Tab | Holds | Was |
|---|---|---|
| **Disease** | Landscape (4 figs) → drilldown (3 figs) + trial list. Optional "+ vs other disease" picker for comparator | By disease + Compare (disease arm) |
| **Target** | Landscape (3 figs) → drilldown (4 figs incl. enrollment box) + per-product table inline + trial list. "+ vs other target" picker | By target + By product + Compare (target arm) |
| **Sponsor** | Top-level "View by:" radio: All / Industry / Academic / Govt / Pick a specific sponsor → adaptive landscape + drilldown | By sponsor type + By sponsor |
| **Geography** | (unchanged) | By geography |
| **Time** | (unchanged) | By time |

5 sub-tabs instead of 8. Same data, less fragmented.

### Publication Figures tab

11 figures. Mostly fine — these are the "cite this in the paper"
figures and shouldn't be cut.

**Minor issue:** Fig 3 / 4 already use the side-by-side split-panel
layout (3a + 3b, 4a + 4b). Other figures could benefit (Fig 1
temporal could pair with a small phase-mix sidebar). Not urgent.

### Methods & Appendix

Already comprehensive; no consolidation needed.

## What's NOT redundant (preserve)

- **Sunburst** is the signature visual — keep prominent
- **Pub Figs** are publication-ready and orthogonal to Deep Dive
- **Disease entity drilldown table → trial detail** is the core
  navigation pattern; keep consistent
- **Snapshot diff + PRISMA + Methods** are evidence/audit

## Implementation plan (if you want to execute)

**Phase 7a — Quick wins (low risk):**
- Remove 4-panel "Landscape at a glance" from Overview
- Remove Top movers from Newsroom strip (YoY unreliable)
- Drop "Compare" sub-tab; add a "+ vs B" picker inside Disease/Target

**Phase 7b — Sub-tab consolidation (medium risk):**
- Merge By sponsor type + By sponsor → unified Sponsor tab
- Merge By product → embed as a section inside Target tab

**Phase 7c — Layout polish (low risk):**
- Audit each remaining sub-tab against the 3-slot template
- Move long-tail figures into expanders so the default view is the
  top-3 most-used charts

## What to ask the user before executing

1. The 4-panel "Landscape at a glance" was added before the recent
   expansion. Is anyone using it? If yes, which panel? Cut the rest.
2. The "Compare" tab is brand-new (Phase 3). Cutting it removes
   recently-added work. Confirm before I delete.
3. Sponsor consolidation merges two recently-added tabs. Confirm.

If the user just says "go", execute Phase 7a + 7b in one commit.
