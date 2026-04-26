# Per-trial drilldown UI — canonical spec v1.3

Status: **active** as of 2026-04-26.
Applies to: `onc-car-t-trials-monitor` AND `rheum-car-t-trials-monitor`.
Both apps declare conformance to this spec via `_render_trial_drilldown`.

## Visual discipline (v1.3)

Two surfaces, two distinct aesthetic budgets:

**Main public dashboards** — strict NEJM-clean.
The only emoji permitted is the canonical **🚩** community-flag indicator,
and only where it conveys that semantic. All other emoji are stripped:
text labels + unicode arrows (`↗ ↻ ↺ →`). No traffic-light color
emoji (🟢/🟡/🔴) for confidence — use the text vocabulary
`{"high": "High", "medium": "Moderate", "low": "Limited"}` plus the
percentage as the only quantitative indicator.

**Validation app** (rater experience) — sophisticated gamification.
No emoji either, but indie-game polish through CSS heatmaps
(GitHub-contributions style), Linear-style stat tiles, and milestone
messages with methodology context. Reward = useful knowledge, not
cartoon confetti.

## Schema (v1.3)

`compute_confidence_factors` returns the canonical nested shape:

```python
{
  "score":   <composite 0..1>,
  "level":   <"high" | "medium" | "low">,
  "factors": {
      <axis>: {"score": float, "driver": str},
      ...
  },
  "drivers": [(axis, driver), ...]   # 2-tuples, ascending by score, top 3
}
```

The flat factor shape (`{axis: float}` + parallel
`(axis, score, reason)` drivers list) used in v1.0–v1.2 has been
replaced. UI consumers should tolerate the legacy shape during
rollover but write the canonical shape.

This spec is the **single source of truth** for the per-trial detail
card visible whenever a user clicks a trial row in either dashboard.
The two apps had drifted independently; this v1.0 merges the best
elements of each. Future revisions go through this doc, not via
unilateral edits to either `app.py`.

## Why a shared spec

The drilldown is the user's primary interaction surface — they spend
more time looking at one trial card than at any other element.
Diverging UX across the two apps means:

- Cross-citation in the methods paper is awkward (different screenshots)
- Users who use both apps relearn the same affordance twice
- Bug fixes don't propagate
- The methodology paper has to enumerate per-app differences

Best practice for cross-app UI alignment: write the spec, version it,
both apps declare which version they implement. Spec edits get a
bump (v1.1, v2.0); each app's CHANGELOG records the version it
currently conforms to.

## Anatomy

```
┌─ st.expander(f"**{NCT_ID}** — {BriefTitle}", expanded=True) ───────────┐
│                                                                          │
│  [1. Flag banner] _render_flag_banner(record)                           │
│      Invisible when no flags. Otherwise st.error (consensus) or         │
│      st.warning (open) + inline proposed-corrections table.             │
│                                                                          │
│  [2. External link row]                                                 │
│      📎 Open on ClinicalTrials.gov ↗                                    │
│      (placed BEFORE metadata so the rater can verify against the live   │
│      record without scrolling)                                          │
│                                                                          │
│  [3. Three-column metadata grid]                                        │
│      ┌─────────────────┬─────────────────┬─────────────────┐            │
│      │ DISEASE         │ PRODUCT         │ SPONSOR         │            │
│      ├─────────────────┼─────────────────┼─────────────────┤            │
│      │ Branch / Family │ Target          │ LeadSponsor     │            │
│      │ Category        │   *(via Source)*│ SponsorType     │            │
│      │ Entity          │ ProductType     │ Enrollment      │            │
│      │ All entities    │   *(via Source)*│ Countries       │            │
│      │ TrialDesign     │ Modality†       │ Age group       │            │
│      │ Phase / Status  │ Named product‡  │                 │            │
│      │ Start year      │ LLM override‡   │                 │            │
│      └─────────────────┴─────────────────┴─────────────────┘            │
│      †: onc only.   ‡: only render when present.                        │
│      *(via Source)*: italicised inline source tag for instant audit.    │
│                                                                          │
│  [4. Free-text payload]                                                 │
│      Render only fields that are non-empty:                             │
│      - **Primary endpoints**: <semicolon-joined>                        │
│      - **Conditions**: <comma-joined; replace pipe with comma>          │
│      - **Interventions**: <comma-joined; replace pipe with comma>       │
│      - **Brief summary**:                                               │
│        > <BriefSummary in markdown block-quote>                         │
│                                                                          │
│  [5. expander: "How was this classified?"]                              │
│      _render_classification_rationale(record, key_suffix)               │
│      Three sub-sections:                                                │
│        a) Composite confidence header                                   │
│           "Composite confidence: 🟡 medium (72%)"                        │
│        b) Row of st.metric tiles, one per axis                          │
│           Each tile: axis name, score %, driver as tooltip              │
│        c) "What's holding the score down" caption                       │
│           Bulleted list of (axis, driver) for worst-scoring axes        │
│        d) Tabular rationale: dataframe with column_config               │
│           Columns: Axis | Label | Source | Matched terms | Explanation  │
│        e) (st.info) LLM-override note when applicable                   │
│                                                                          │
│  [6. expander: "Suggest a classification correction"]                   │
│      _render_suggest_correction(record, key_suffix)                     │
│      Multiselect axes → per-axis correction (selectbox or text)         │
│      → notes textarea → "Open as GitHub issue ↗" link button.           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Implementation contract

Both apps MUST expose:

```python
def _render_trial_drilldown(record, *, key_suffix: str = "") -> None:
    """Render the per-trial detail card. Conforms to UI_DRILLDOWN_SPEC v1.0."""
    ...
```

`record` is a `pd.Series` or dict; `key_suffix` disambiguates session-state
widget keys when the same trial may be drilled into from multiple
contexts in one render (e.g. Geography city table + Data tab).

The helper MUST:
- Be the SOLE drilldown render path used by every trial-table call site
  in the app (no inline drilldown blocks)
- Wrap the entire card in `st.expander(..., expanded=True)`
- Tolerate missing optional fields by rendering "—"
- Survive a missing `_render_flag_banner` / `_render_classification_rationale`
  / `_render_suggest_correction` (wrap each in `try/except` so a
  subsystem failure degrades to a silent skip, not a crashed card)

## App-specific axis differences (intentional)

Onc and rheum have different classification axes by design. This is
NOT a spec divergence:

| Axis | Onc | Rheum |
|---|---|---|
| Top-level grouping | Branch (Heme-onc / Solid-onc / Mixed / Unknown) | DiseaseFamily (single — autoimmune rheumatologic) |
| Mid-level grouping | DiseaseCategory (~30 categories) | (none — flatter taxonomy) |
| Leaf | DiseaseEntity (~70 entities) | DiseaseEntity (~13 entities) |
| Modality column | Yes — Auto / Allo / In-vivo / CAR-NK / etc. | No — handled via TargetCategory `CAR-NK: X` etc. |

The 3-column metadata grid renders only the axes the app's pipeline
populates. Empty axes ("Modality" in rheum) are not rendered.

## Source-tag display

Both apps annotate the Target and ProductType labels with their source
tag inline:

```
Target: CD19 *(via antigen_match)*
ProductType: Allogeneic/Off-the-shelf *(via explicit_allogeneic_marker)*
```

This is the single most-discoverable audit affordance — the rater sees
WHERE the label came from without expanding anything. Source tags
are surfaced from the pipeline's existing source-tag columns
(`TargetSource`, `ProductTypeSource`).

The full per-axis explanation lives in the "How was this classified?"
expander; the inline tag is the at-a-glance hint.

## Confidence model

Both apps surface the multi-factor confidence model
(`compute_confidence_factors(row)`) inside the rationale expander:

```python
{
  "score": 0.72,
  "level": "medium",
  "factors": {
    "Branch":          {"score": 1.00, "driver": "Clean single-branch"},
    "DiseaseCategory": {"score": 1.00, "driver": "Specific category match"},
    "DiseaseEntity":   {"score": 0.55, "driver": "Basket-level fallback"},
    "TargetCategory":  {"score": 1.00, "driver": "Antigen identified: CD19"},
    "ProductType":     {"score": 0.50, "driver": "Defaulted to autologous"},
  },
  "drivers": [(axis, driver), ...]
}
```

The legacy 3-bucket `ClassificationConfidence` (high/medium/low) is
preserved bit-for-bit in both apps for snapshot back-compat. The
multi-factor model lives alongside it as a per-axis read-only enrichment.

## Versioning

Current version: **v1.3** (2026-04-26).

| Version | Change |
|---|---|
| v1.0 | Initial spec — 6-section anatomy; flat factor schema. |
| v1.1 | Schema flip: factors → nested `{axis: {score, driver}}`; drivers → 2-tuples. |
| v1.2 | Metadata grid column headers ("Disease" / "Product" / "Sponsor"). |
| v1.3 | Visual discipline — strict NEJM-clean main dashboards (emoji only for 🚩); sophisticated-but-emoji-free validation app. Text confidence vocabulary replaces traffic-light emoji. Refresh actions use text + unicode arrows. |

When this spec changes:
1. Bump version in this file's header
2. Both apps' `_render_trial_drilldown` docstrings reference the new version
3. Both apps' CHANGELOG records the conformance update
4. Cross-app sync brief notes the version delta

For backward-incompatible changes (e.g. column count change), bump
the major version (v2.0). For additive changes (e.g. a new optional
field in the metadata grid), bump the minor (v1.1).

## Reference implementations

- `onc-car-t-trials-monitor` `app.py:_render_trial_drilldown` @ v1.3 conforming
  (commit `2e221e5`).
- `rheum-car-t-trials-monitor` `app.py:_render_trial_drilldown` @ v1.3 conforming.
  Rationale dataframe powered by `pipeline.compute_classification_rationale`;
  per-axis tiles powered by `pipeline.compute_confidence_factors` (nested
  schema). Visual discipline pass landed alongside the schema flip.
