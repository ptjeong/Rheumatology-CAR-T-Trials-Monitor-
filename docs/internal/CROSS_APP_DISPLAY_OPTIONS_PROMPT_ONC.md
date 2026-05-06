# Cross-app port — sidebar Display options (PNG/SVG export + high-contrast palette)

Paste the section between `--- BEGIN PROMPT ---` and `--- END PROMPT ---`
into a fresh Claude Code session in the **onc-car-t-trials-monitor** repo.
Self-contained, no other context needed.

Rheum-side commits (reference):
- `47bccae` — Phase-3 Deep Dive expansion (introduced the per-chart
  PNG/SVG buttons + high-contrast toggle on every chart)
- `df4d4fc` — Sidebar consolidation (moved both controls into
  `Display options` expander; removed the per-chart buttons that
  were "obnoxious" per user feedback)

---

--- BEGIN PROMPT ---

The rheum sister monitor moved its chart-export and palette toggles
out of per-chart buttons (which were visually noisy) and into a
single sidebar expander. Port the same UX to the onc dashboard.

## What you're adding

A sidebar expander **"Display options"** between the Data-source
section and the Filters header, with two controls:

1. **Chart export format** — radio with two options:
   - "PNG (slides, 5× resolution)"  ← default
   - "SVG (vector — journal / Illustrator)"

   Drives the Plotly modebar download icon's `toImageButtonOptions`.
   Mutates the module-level `PUB_EXPORT` dict in place after the
   sidebar block runs (Streamlit re-executes the script top-to-bottom
   each rerun, so the mutation applies before any chart renders).

2. **High-contrast palette** — `st.toggle`, default off.

   When on, mutates `ENTITY_COLORS` (and `_FAMILY_COLORS` if onc
   maintains one) in place to a Tableau-20-based variant where every
   disease entity gets a maximally distinct hue. When off, restore
   the default family-clustered palette.

## Implementation pattern (lift from rheum app.py)

### Step 1 — Define a high-contrast palette alongside the default

In whatever module-top section onc keeps `ENTITY_COLORS`, snapshot
the default and define a high-contrast variant. Tableau-20 hand-
assigned per entity:

```python
# After the existing ENTITY_COLORS block:
_ENTITY_COLORS_DEFAULT = dict(ENTITY_COLORS)
_FAMILY_COLORS_DEFAULT = dict(_FAMILY_COLORS)

_ENTITY_COLORS_HIGH_CONTRAST = {
    # Use Tableau-20 distinct hues. The exact mapping should match
    # onc's entity vocab — DLBCL gets blue, MM gets orange, etc.
    "DLBCL":             "#1f77b4",  # tableau blue
    "FL":                "#ff7f0e",  # tableau orange
    "MM":                "#2ca02c",  # tableau green
    "MCL":               "#d62728",  # tableau red
    "ALL":               "#9467bd",  # tableau purple
    "AML":               "#8c564b",  # tableau brown
    "CLL":               "#e377c2",  # tableau pink
    "GBM":               "#7f7f7f",  # tableau gray
    "HCC":               "#bcbd22",  # tableau olive
    # ... fill in for your full vocabulary
    # Sentinels:
    "Unclassified":      "#bbbbbb",
    "Other":             "#dddddd",
}

_FAMILY_COLORS_HIGH_CONTRAST = {
    "Heme-onc":          "#1f77b4",   # blue
    "Solid-onc":         "#d62728",   # red
    "Mixed":             "#7f7f7f",
    "Unclassified":      "#bbbbbb",
    # ... onc's actual family vocab
}
```

### Step 2 — Add the sidebar expander

Insert this block AFTER the data-source / snapshot-pinning sidebar
code and BEFORE the existing `st.sidebar.header("Filters")`:

```python
with st.sidebar.expander("Display options", expanded=False):
    _export_choice = st.radio(
        "Chart export format",
        options=[
            "PNG (slides, 5× resolution)",
            "SVG (vector — journal / Illustrator)",
        ],
        index=0,
        key="chart_export_fmt",
        help=(
            "PNG — best for presentations / slide decks. Renders at 5× "
            "the chart's natural size for crisp 4K-projection / "
            "300-DPI print quality.\n\nSVG — best for journal "
            "submission requiring vector graphics, or post-editing in "
            "Illustrator / Inkscape / Figma. Infinite resolution; "
            "every wedge / bar / label is an editable element."
        ),
    )
    _hc_toggle = st.toggle(
        "High-contrast palette",
        value=False,
        key="high_contrast",
        help=(
            "Switch every entity-coloured chart to a Tableau-20-based "
            "palette where every disease gets a maximally distinct "
            "colour. Trades family-cluster cohesion for differentiation "
            "between similarly-prevalent diseases."
        ),
    )

# Mutate PUB_EXPORT in place per the export choice.
if _export_choice.startswith("SVG"):
    PUB_EXPORT["toImageButtonOptions"]["format"] = "svg"
    PUB_EXPORT["toImageButtonOptions"]["scale"] = 1
else:
    PUB_EXPORT["toImageButtonOptions"]["format"] = "png"
    PUB_EXPORT["toImageButtonOptions"]["scale"] = 5

# Mutate the colour dicts in place per the toggle.
if _hc_toggle:
    ENTITY_COLORS.clear(); ENTITY_COLORS.update(_ENTITY_COLORS_HIGH_CONTRAST)
    _FAMILY_COLORS.clear(); _FAMILY_COLORS.update(_FAMILY_COLORS_HIGH_CONTRAST)
else:
    ENTITY_COLORS.clear(); ENTITY_COLORS.update(_ENTITY_COLORS_DEFAULT)
    _FAMILY_COLORS.clear(); _FAMILY_COLORS.update(_FAMILY_COLORS_DEFAULT)

st.sidebar.header("Filters")
```

### Step 3 — Make sure PUB_EXPORT is defined high enough

`PUB_EXPORT` must be defined BEFORE the sidebar block runs (the
mutation block above references it). If onc's `PUB_EXPORT` lives
further down (near the per-figure layout constants), move it up to
the module-top constant block alongside `ENTITY_COLORS`.

The default value:

```python
PUB_EXPORT = {
    "toImageButtonOptions": {
        "format": "png",
        "scale": 5,
    },
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d", "select2d", "autoScale2d", "hoverClosestCartesian",
        "hoverCompareCartesian", "toggleSpikelines",
    ],
}
```

### Step 4 — Add kaleido to requirements.txt (only if onc adds SVG)

```
kaleido>=0.2.1
```

This is only needed if you ALSO port rheum's `_chart()` helper that
renders SVG server-side via kaleido. The pure modebar download
(driven by `toImageButtonOptions.format`) doesn't need kaleido —
Plotly's browser-side `Plotly.downloadImage()` handles SVG natively.

## Verification

1. Sidebar expander shows up between Data source and Filters
2. Toggling export format changes the modebar's download icon
   tooltip text (Plotly shows "Download plot as a png" / "...svg")
3. Toggling high-contrast immediately re-renders every entity-
   coloured chart with the new palette on the next rerun
4. No per-chart buttons added — the modebar PNG/SVG download is the
   single export path

## Commit message suggestion

```
sidebar: add Display options expander (PNG/SVG export + high-contrast)

Ports the rheum sister monitor's UX (rheum commits 47bccae + df4d4fc).
Two controls in a single sidebar expander between Data source and
Filters:
  - Chart export format radio: PNG (5× scale) | SVG (vector)
    Mutates PUB_EXPORT.toImageButtonOptions in place.
  - High-contrast palette toggle: Tableau-20-based variant.
    Mutates ENTITY_COLORS / _FAMILY_COLORS in place.

Both global; no per-chart UI clutter. Same Streamlit re-execute-
top-to-bottom mutation pattern.
```

--- END PROMPT ---
