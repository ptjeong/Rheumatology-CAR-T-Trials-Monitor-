# Design system — rheum monitor

This dashboard follows a **flat, line-delineated, NEJM-style** aesthetic:
hairline dividers instead of cards, navy primary, no shadows, no
gradients. The visual discipline is held together by a small set of
design tokens defined in CSS custom properties (`:root` block at the
top of `app.py`'s inline style block) plus a handful of Python
constants.

This brief documents the system so contributors don't re-invent it.

---

## Typography scale

Seven roles, each with its own CSS variable. Use the variable, never
inline a `rem` value.

| Variable | Value | px (16px root) | Role |
|---|---|---|---|
| `--fs-micro` | 0.625rem | 10 | Uppercase eyebrows, sidebar nav headings, very-small KPI labels |
| `--fs-xs`    | 0.75rem  | 12 | Captions, footnotes, multiselect text, button text in sidebar |
| `--fs-sm`    | 0.8125rem| 13 | Secondary body, button labels, sub-section H3 |
| `--fs-base`  | 0.875rem | 14 | Primary body, tab labels, small-note, top-level captions |
| `--fs-md`    | 1.0625rem| 17 | Figure titles (pub-fig-title), expander headings, contact name |
| `--fs-lg`    | 1.5rem   | 24 | Metric values (headline numbers) |
| `--fs-xl`    | 1.75rem  | 28 | Hero title (top-of-page eyebrow + title) |

**Scale ratio:** ~1.16× between adjacent steps (modular). Visual
hierarchy is unambiguous: each step is large enough to read as a
distinct role, small enough that adjacent roles still feel related.

**Before this scale (commit `4bde241` and earlier):** 14+ distinct rem
values (0.59, 0.66, 0.7, 0.72, 0.73, 0.75, 0.78, 0.82, 0.84, 0.86,
1.05, 1.4, 1.65, 1.7) were scattered across the CSS, used
inconsistently. The differences were often <1 px — visually
indistinguishable, but creating constant micro-inconsistency. The
seven-step scale consolidates them with at most ±1 px drift from
the previous values.

## Line height

| Variable | Value | Use |
|---|---|---|
| `--lh-tight`   | 1.15 | Headings (`h1`-`h3`, hero title) |
| `--lh-snug`    | 1.35 | Sub-headings, figure titles |
| `--lh-normal`  | 1.5  | Body text |
| `--lh-relaxed` | 1.65 | Long captions, sub captions, methods text |

## Font weight

| Variable | Value | Use |
|---|---|---|
| `--fw-regular`  | 400 | Default body |
| `--fw-medium`   | 500 | Tab labels, button text, sidebar widget labels |
| `--fw-semibold` | 600 | Headings, metric values, eyebrows |
| `--fw-bold`     | 700 | Sidebar nav headings (paired with letter-spacing) |

## Letter spacing (tracking)

| Variable | Value | Use |
|---|---|---|
| `--tracking-tight`   | -0.022em | Hero title, large display |
| `--tracking-snug`    | -0.012em | h3, figure titles |
| `--tracking-normal`  | -0.005em | Body, buttons, tabs |
| `--tracking-wide`    | 0.12em   | Metric labels (uppercase) |
| `--tracking-widest`  | 0.16em   | Eyebrows (uppercase) |

---

## Font families

| Where | Family | Why |
|---|---|---|
| App UI body | `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | Modern, readable, free, hosted via Google Fonts. Use `FONT_FAMILY` constant in Python. |
| Publication figures | `Arial, Helvetica, sans-serif` | Renders identically across viewers (no remote font dependency in exported PNG/SVG). Defined in `PUB_FONT` constant. |
| Icons | `Material Symbols Outlined, Material Icons` | Streamlit's internal icon font — must NOT be overridden. Preserved via narrow CSS scoping. |

**Rule:** never hardcode a font-family string. Reference `FONT_FAMILY`
in Python or rely on the CSS body default for app UI; use `PUB_FONT`
for publication figures.

---

## Colors

Defined in the `THEME` dict in `app.py`. Single source of truth.

```python
THEME = {
    "bg":      "#ffffff",   # pure white canvas
    "surface": "#ffffff",   # = canvas (flat, no card contrast)
    "surf2":   "#f8fafc",   # slate-50 — subtle hover/strip
    "surf3":   "#e5e7eb",   # gray-200
    "text":    "#0b1220",   # near-black body
    "muted":   "#475569",   # slate-600 — readable secondary
    "faint":   "#94a3b8",   # slate-400 — micro / disabled
    "border":  "#e5e7eb",   # gray-200 — single hairline color
    "primary": "#0b3d91",   # deep navy — clinical/scientific
    "teal":    "#0f766e",   # teal-700 — secondary accent
    "amber":   "#92400e",   # amber-800 — rare accent
    "shadow":  "none",      # flat aesthetic — no shadows
    "grid":    "#f1f5f9",   # slate-100 — chart gridlines
}
```

**Publication figures** have their own axis-color constant
(`_AX_COLOR = "#1a1a1a"`) which is slightly darker than `THEME["text"]`
to optimise for print rendering. Don't unify these — they serve
different display media.

**Disease/target entity colors** live in `ENTITY_COLORS` (defined near
the top of `app.py`) with a high-contrast Tableau-20 variant
toggleable from the sidebar. The variant override mutates
`ENTITY_COLORS` in-place; never hardcode a specific entity color in
a chart definition.

---

## Spacing

Defined inline; no token system yet (low-priority future work).
General rules:

- Section dividers: 1px border-top in `THEME["border"]`, padding-top
  ~1.1rem
- Inter-section spacing: 0.6-1.0rem
- Inter-element spacing within a section: 0.25-0.55rem
- Tab padding: `10px 18px`
- Button padding: `0.42rem 0.95rem`

---

## Containers and surfaces

The dashboard is **flat by design** — almost no card-style elements.
Per `MEMORY.md`: NEJM-style aesthetic confirmed preferred over
card-heavy SaaS look.

Container rules:
- No box-shadows anywhere (`THEME["shadow"] = "none"`)
- No border-radius beyond 2px (squared corners signal seriousness)
- Sections separated by 1px hairlines (`border-top: 1px solid var(--border)`)
- The two exceptions: `st.expander` (8px radius) and the contact card
  on the About page (border-left accent). Both intentional.

If a future contributor adds a `box-shadow: 0 2px 8px rgba(...)` or
a `border-radius: 12px`, it's a violation — push back.

---

## Tables

`st.dataframe` is styled via the global CSS rules. Common patterns:

- **Title columns**: use `width="large"` and provide a `help=` tooltip
  noting the hover-recovery affordance. **Never pre-truncate strings
  with `.str[:N]`** — that destroys Streamlit's native hover-to-see-
  full-cell behaviour. Confirmed offender (now fixed): the "Recently
  updated trials" panel used `BriefTitle.str[:60]` which left readers
  staring at "A Study of Healthy Donor CD19-Targeted Allogeneic CA…"
  with no path to recover the rest.
- **Reference column configs**: use `_trial_detail_cols()` for any
  trial-detail table; it sets sensible widths + help text for every
  standard CT.gov column.
- **Numeric columns**: use `st.column_config.NumberColumn(format="%d")`
  for integers (no thousands separator in tables — separator on KPI
  tiles only).

---

## Charts (Plotly)

Two parallel sets of layout constants:

**Publication figures** (`PUB_LAYOUT`, `_V_XAXIS`, `_H_YAXIS`, etc.)
- Font: Arial 11 (tick), 12 (label), 14 (title) — `_TICK_SZ`, `_LAB_SZ`,
  `_TITLE_SZ`
- Axes: black 1.5px lines, outside ticks, grid in `_GRID_CLR`
- Right margin: 36px (no end-of-line labels)
- Titles rendered via `_pub_header()`, not Plotly's in-chart title

**Deep Dive figures** (`_deepdive_*` helpers)
- Font: `FONT_FAMILY` (Inter) at sizes 10-11
- Axes: lighter, fewer ticks
- Right margin: 180px when direct-labelled (timeline charts)

**Don't mix:** never use Arial in a Deep Dive chart, never use Inter in
a publication chart export. The two contexts serve different downstream
uses (screen browse vs PNG/SVG into a manuscript).

---

## When to break the system

The token system is a starting point, not a cage. Acceptable reasons
to deviate:

- **A new role emerges** that doesn't fit any of the 7 type sizes —
  add an 8th variable rather than reusing an inappropriate one. But
  audit first: usually the role IS one of the 7, just framed
  differently.
- **A one-off accent** (e.g., the "🎯 Focus" amber chip strip) needs
  a colour that's not in `THEME`. Define the colour inline with a
  comment explaining why (e.g., "amber matches the focus-bar accent
  to signal interactive state").
- **A specific Streamlit component overrides** the cascade in a way
  the system can't reach. Use `!important` sparingly; document why in
  a comment.

What's NOT acceptable:
- Inventing a new font-size value because "this one needs to be just
  a bit smaller"
- Adding a `border-radius: 8px` to a div that should be flat
- Hardcoding a hex colour that approximates one already in `THEME`
- Pre-truncating strings shown in tables

---

## Cross-app consistency

The onc CAR-T monitor (sister app) uses a similar but not identical
system. Don't ports tokens directly across — each app's CSS is its
own — but the design language is shared. Both apps:
- Use Inter for UI body
- Use Arial for publication figures
- Use navy primary, slate-grey secondary
- Flat surfaces, no shadows
- Hairline section dividers

When a new pattern lands in one app, consider porting it to the
other; that's tracked in the cross-app coordination briefs
(`CROSS_APP_PROFESSIONAL_GRADE_BRIEF_R{1,2,3}.md`).

---

## Audit checklist (for future design passes)

When reviewing a new section / feature:

- [ ] All `font-size` values use `var(--fs-*)`, no inline `rem` literals
- [ ] All `font-family` strings use `FONT_FAMILY` (Python) or rely on
      the CSS body default (no hardcoded "Inter, ..." strings)
- [ ] All colours come from `THEME` or `ENTITY_COLORS` (no hardcoded
      hex except for documented one-offs)
- [ ] No box-shadows, no border-radius > 2px (except expander + the
      one accent card)
- [ ] Tables use `_trial_detail_cols()` or equivalent shared column
      config
- [ ] No string-level pre-truncation (`.str[:N]`) on display columns
- [ ] Hairline dividers (1px, `THEME["border"]`) between sections,
      not card-style containers
- [ ] Tab structure uses `st.tabs` (consistent), not `st.radio` or
      `st.selectbox` masquerading as navigation
