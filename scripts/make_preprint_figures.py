"""Static publication figures for the CAR-T Rheumatology preprint.

Reads `snapshots/2026-04-25/{trials.csv,prisma.json}` and writes seven
PDF + PNG figures to `figures/preprint/`. Run from the repo root:

    python3 scripts/make_preprint_figures.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "snapshots" / "2026-04-25"
OUT = ROOT / "figures" / "preprint"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Theme — flat NEJM-style, navy + slate, hairline borders, no shadows
# ---------------------------------------------------------------------------
THEME = {
    "bg": "#ffffff",
    "text": "#0b1220",
    "muted": "#475569",
    "faint": "#94a3b8",
    "grid": "#e5e7eb",
    "border": "#cbd5e1",
}
FAMILY_COLORS = {
    "Connective tissue":       "#0b3d91",
    "Inflammatory arthritis":  "#2e6dbf",
    "Vasculitis":              "#5fa3d9",
    "Neurologic autoimmune":   "#7c3aed",
    "Other autoimmune":        "#475569",
    "Basket/Multidisease":     "#94a3b8",
    "Other / Unclassified":    "#cbd5e1",
}
FAMILY_ORDER = list(FAMILY_COLORS.keys())
TARGET_CLASS_COLORS = {
    "B-cell":      "#0b3d91",
    "Plasma-cell": "#92400e",
    "Dual":        "#0f766e",
    "Other":       "#475569",
    "Undisclosed": "#94a3b8",
}
MODALITY_COLORS = {
    "Autologous":              "#0b3d91",
    "Allogeneic/Off-the-shelf":"#0f766e",
    "In vivo":                 "#92400e",
    "Unclear":                 "#94a3b8",
}
SPONSOR_COLORS = {
    "Academic": "#0b3d91",
    "Industry": "#92400e",
    "Government": "#0f766e",
    "Other": "#94a3b8",
}
FONT = dict(family="Helvetica, Arial, sans-serif", size=12, color=THEME["text"])

# ---------------------------------------------------------------------------
# Family + L2 classification (mirrors app.py)
# ---------------------------------------------------------------------------
DFM = {
    "SLE":"Connective tissue","SSc":"Connective tissue","Sjogren":"Connective tissue",
    "IIM":"Connective tissue","CTD_other":"Connective tissue","IgG4-RD":"Connective tissue",
    "RA":"Inflammatory arthritis","AAV":"Vasculitis","Behcet":"Vasculitis",
    "Other immune-mediated":"Other autoimmune","cGVHD":"Other autoimmune",
}
SUBFAM = [
    ("Autoimmune cytopenias", r"hemolytic anemia|\baiha\b|\bwaiha\b|immune thrombocytopen|\bitp\b|evans syndrome|aplastic anemia|alloimmune thrombocyt|immune cytopen|red cell aplasia|platelet transfusion refractor|autoimmune neutropen"),
    ("Glomerular / renal", r"iga nephropathy|\bigan\b|membranous nephropathy|nephrotic syndrome|glomeruloneph|focal segmental"),
    ("Endocrine autoimmune", r"type 1 diabetes|\bt1dm\b|graves|hashimoto"),
    ("Dermatologic autoimmune", r"pemphigus|pemphigoid|hidradenitis|bullous"),
    ("Neurologic autoimmune", r"multiple sclerosis|myasthenia|neuromyelitis|\bnmosd?\b|autoimmune encephalitis|stiff[-\s]person|demyelinating|\bcidp\b|\bmog\b|\bmusk\b|nervous system|neurolog"),
    ("GVHD", r"graft[-\s]?versus[-\s]?host|graft[-\s]vs[-\s]?host|\bgvhd\b"),
]
SUBFAM_RX = [(l, re.compile(p, re.I)) for l, p in SUBFAM]
NEURO = [
    ("MS", r"multiple sclerosis|\brrms\b|\bppms\b|\bspms\b"),
    ("Myasthenia", r"myasthenia gravis|\bmgfa\b|\bmusk\b"),
    ("NMOSD", r"neuromyelitis|\bnmosd?\b"),
    ("AIE", r"autoimmune encephalitis|anti[-\s]?nmda|lgi1|\bcaspr2\b"),
    ("CIDP", r"\bcidp\b|chronic inflammatory demyelinating"),
    ("MOGAD", r"\bmogad?\b|mog antibody|mog[-\s]?associated"),
    ("Stiff-person", r"stiff[-\s]person"),
]
NEURO_RX = [(l, re.compile(p, re.I)) for l, p in NEURO]
OTHER_AI = ("Other immune-mediated", "cGVHD")


def _sub(text: str) -> str:
    if not text:
        return "Other autoimmune"
    hits = [l for l, rx in SUBFAM_RX if rx.search(text)]
    return hits[0] if len(hits) == 1 else "Other autoimmune"


def _neuro(text: str) -> str:
    if not text:
        return "Neurology_other"
    hits = [l for l, rx in NEURO_RX if rx.search(text)]
    return hits[0] if len(hits) == 1 else "Neurology_other"


def _family(row: pd.Series) -> str:
    if row.get("TrialDesign") == "Basket/Multidisease":
        return "Basket/Multidisease"
    e = row.get("DiseaseEntity")
    if not e or e in ("Unclassified", ""):
        return "Other / Unclassified"
    if e in OTHER_AI:
        t = f"{row.get('Conditions') or ''} {row.get('BriefTitle') or ''}"
        if _sub(t) == "Neurologic autoimmune":
            return "Neurologic autoimmune"
    return DFM.get(str(e), "Other / Unclassified")


def _l2(row: pd.Series) -> str:
    fam = row["Family"]
    if fam == "Neurologic autoimmune":
        t = f"{row.get('Conditions') or ''} {row.get('BriefTitle') or ''}"
        return _neuro(t)
    if fam == "Other autoimmune":
        t = f"{row.get('Conditions') or ''} {row.get('BriefTitle') or ''}"
        return _sub(t)
    return str(row.get("DiseaseEntity") or "Unclassified")


# Antigen target classes (B-cell / plasma / dual / other / undisclosed)
def _target_class(t: str) -> str:
    if not t or t == "Other_or_unknown":
        return "Other"
    if t == "CAR-T_unspecified":
        return "Undisclosed"
    if "dual" in t.lower():
        return "Dual"
    if t in ("CD19", "CD20", "CD22", "BAFF", "CD7", "CD6"):
        return "B-cell"
    if t in ("BCMA", "CD70"):
        return "Plasma-cell"
    return "Other"


# Country → region
REGIONS = {
    "China": "East Asia", "Japan": "East Asia", "Korea, Republic of": "East Asia",
    "South Korea": "East Asia", "Taiwan": "East Asia", "Hong Kong": "East Asia",
    "Singapore": "East Asia",
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "Germany": "Europe", "France": "Europe", "United Kingdom": "Europe", "Spain": "Europe",
    "Italy": "Europe", "Netherlands": "Europe", "Belgium": "Europe", "Austria": "Europe",
    "Switzerland": "Europe", "Sweden": "Europe", "Denmark": "Europe", "Norway": "Europe",
    "Finland": "Europe", "Ireland": "Europe", "Poland": "Europe", "Czechia": "Europe",
    "Czech Republic": "Europe", "Greece": "Europe", "Portugal": "Europe", "Hungary": "Europe",
    "Romania": "Europe", "Bulgaria": "Europe", "Croatia": "Europe", "Slovakia": "Europe",
    "Slovenia": "Europe", "Estonia": "Europe", "Latvia": "Europe", "Lithuania": "Europe",
    "Russia": "Europe", "Ukraine": "Europe", "Turkey": "Europe", "Israel": "Europe",
    "Australia": "Oceania", "New Zealand": "Oceania",
}
REGION_COLORS = {
    "East Asia": "#0b3d91",
    "Europe": "#2e6dbf",
    "North America": "#5fa3d9",
    "Oceania": "#0f766e",
    "Rest of World": "#94a3b8",
}

# Country name → ISO-3 (subset for choropleth)
ISO3 = {
    "China": "CHN", "United States": "USA", "Germany": "DEU", "France": "FRA",
    "Spain": "ESP", "United Kingdom": "GBR", "Australia": "AUS", "Canada": "CAN",
    "Italy": "ITA", "Switzerland": "CHE", "Israel": "ISR", "Japan": "JPN",
    "Brazil": "BRA", "Belgium": "BEL", "Singapore": "SGP", "Netherlands": "NLD",
    "Austria": "AUT", "Sweden": "SWE", "Denmark": "DNK", "Norway": "NOR",
    "Finland": "FIN", "Ireland": "IRL", "Poland": "POL", "Czechia": "CZE",
    "Czech Republic": "CZE", "Greece": "GRC", "Portugal": "PRT", "Hungary": "HUN",
    "Romania": "ROU", "Bulgaria": "BGR", "Korea, Republic of": "KOR",
    "South Korea": "KOR", "Taiwan": "TWN", "Hong Kong": "HKG", "Mexico": "MEX",
    "New Zealand": "NZL", "Russia": "RUS", "Ukraine": "UKR", "Turkey": "TUR",
    "Argentina": "ARG", "Chile": "CHL", "Colombia": "COL", "India": "IND",
    "Thailand": "THA", "Malaysia": "MYS", "Vietnam": "VNM", "Philippines": "PHL",
    "South Africa": "ZAF", "Egypt": "EGY",
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_trials() -> pd.DataFrame:
    df = pd.read_csv(SNAP / "trials.csv")
    df["Family"] = df.apply(_family, axis=1)
    df["L2"] = df.apply(_l2, axis=1)
    df["TargetClass"] = df["TargetCategory"].fillna("Other_or_unknown").apply(_target_class)
    return df


def load_prisma() -> dict:
    return json.loads((SNAP / "prisma.json").read_text())


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------
def _layout(fig: go.Figure, title: str | None = None, height: int = 520, width: int = 900):
    fig.update_layout(
        title=dict(text=title or "", x=0.0, xanchor="left", font=dict(size=14)) if title else None,
        font=FONT,
        paper_bgcolor=THEME["bg"],
        plot_bgcolor=THEME["bg"],
        margin=dict(l=80, r=40, t=60 if title else 30, b=60),
        height=height,
        width=width,
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=THEME["border"], borderwidth=0),
    )
    fig.update_xaxes(showgrid=True, gridcolor=THEME["grid"], gridwidth=1,
                     zeroline=False, linecolor=THEME["border"], linewidth=1, ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]))
    fig.update_yaxes(showgrid=True, gridcolor=THEME["grid"], gridwidth=1,
                     zeroline=False, linecolor=THEME["border"], linewidth=1, ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]))


def _save(fig: go.Figure, name: str, scale: float = 2.0):
    pdf = OUT / f"{name}.pdf"
    png = OUT / f"{name}.png"
    fig.write_image(str(pdf), format="pdf")
    fig.write_image(str(png), format="png", scale=scale)
    print(f"  -> {pdf.relative_to(ROOT)}")
    print(f"  -> {png.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def fig1_prisma_growth(df: pd.DataFrame, prisma: dict):
    """Two-panel: PRISMA flow (left) + cumulative-trials curve (right)."""
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.40, 0.60],
        subplot_titles=("(A) Study selection", "(B) Cumulative trials by start year"),
        horizontal_spacing=0.22,
    )

    # --- Left panel: PRISMA flow as labelled boxes via shapes/annotations ---
    boxes = [
        ("Records identified from<br>ClinicalTrials.gov v2 API",
         f"n = {prisma['n_fetched']:,}", 0.86),
        ("After de-duplication",
         f"n = {prisma['n_after_dedup']:,}", 0.66),
        (f"Excluded:<br>• Hard-excluded NCT IDs (n={prisma['n_hard_excluded']})<br>"
         f"• Indication keyword filters (n={prisma['n_indication_excluded']})<br>"
         f"• LLM-derived exclusions (n={prisma['n_llm_excluded']})",
         f"n = {prisma['n_total_excluded']:,}", 0.40),
        ("Trials included in analysis",
         f"n = {prisma['n_included']:,}", 0.14),
    ]
    box_x_lo, box_x_hi = 0.02, 0.36  # left subplot, width 0.34 fits long labels; center ~0.19
    for i, (label, n, y) in enumerate(boxes):
        fillcolor = "#0b3d91" if i == len(boxes) - 1 else "#f8fafc"
        fontcolor = "#ffffff" if i == len(boxes) - 1 else THEME["text"]
        fig.add_shape(
            type="rect", xref="paper", yref="paper",
            x0=box_x_lo, x1=box_x_hi, y0=y - 0.08, y1=y + 0.08,
            line=dict(color=THEME["border"], width=1),
            fillcolor=fillcolor,
        )
        fig.add_annotation(
            xref="paper", yref="paper", x=(box_x_lo + box_x_hi) / 2, y=y,
            text=f"<b>{label}</b><br><span style='font-size:11px'>{n}</span>",
            showarrow=False, font=dict(size=11, color=fontcolor), align="center",
        )
    # Connecting lines (drawn as shapes — no arrowheads; readers infer top→bottom flow)
    arrow_x = (box_x_lo + box_x_hi) / 2
    for i in range(len(boxes) - 1):
        y_top = boxes[i][2] - 0.08
        y_bot = boxes[i + 1][2] + 0.08
        fig.add_shape(
            type="line", xref="paper", yref="paper",
            x0=arrow_x, x1=arrow_x, y0=y_top, y1=y_bot,
            line=dict(color=THEME["muted"], width=1.2),
        )
        # Small triangle arrowhead at bottom of segment
        head_w = 0.006
        head_h = 0.012
        fig.add_shape(
            type="path", xref="paper", yref="paper",
            path=(f"M {arrow_x - head_w} {y_bot + head_h} "
                  f"L {arrow_x + head_w} {y_bot + head_h} "
                  f"L {arrow_x} {y_bot} Z"),
            line=dict(color=THEME["muted"], width=0),
            fillcolor=THEME["muted"],
        )

    # --- Right panel: cumulative trials by family, stacked area on year ---
    sub = df[df["StartYear"].notna()].copy()
    sub["StartYear"] = sub["StartYear"].astype(int)
    yearly = sub.groupby(["StartYear", "Family"]).size().unstack(fill_value=0)
    # ensure all years present 2019..max
    full_years = list(range(int(yearly.index.min()), int(yearly.index.max()) + 1))
    yearly = yearly.reindex(full_years, fill_value=0)
    cum = yearly[FAMILY_ORDER if all(f in yearly.columns for f in FAMILY_ORDER) else yearly.columns].cumsum()

    for fam in FAMILY_ORDER:
        if fam not in cum.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=cum.index, y=cum[fam], name=fam,
                mode="lines", stackgroup="cum",
                line=dict(width=0.6, color=FAMILY_COLORS[fam]),
                fillcolor=FAMILY_COLORS[fam],
                hovertemplate=f"%{{x}} · {fam}: %{{y}}<extra></extra>",
            ),
            row=1, col=2,
        )

    fig.update_xaxes(title_text="Trial start year", row=1, col=2,
                     showgrid=True, gridcolor=THEME["grid"],
                     zeroline=False, linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]),
                     dtick=1, title_standoff=8)
    fig.update_yaxes(title_text="Cumulative trials", row=1, col=2,
                     showgrid=True, gridcolor=THEME["grid"],
                     zeroline=False, linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]),
                     title_standoff=4)
    # left subplot axes off
    fig.update_xaxes(visible=False, row=1, col=1)
    fig.update_yaxes(visible=False, row=1, col=1)

    fig.update_layout(
        font=FONT, paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["bg"],
        margin=dict(l=40, r=40, t=60, b=70), height=560, width=1100,
        legend=dict(orientation="h", yanchor="top", y=-0.10, xanchor="center", x=0.78,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        showlegend=True,
    )
    for ann in fig["layout"]["annotations"][:2]:
        ann.update(font=dict(size=12, color=THEME["text"]), x=ann["x"], xanchor="left")
    _save(fig, "fig1_prisma_growth")


def fig2_disease_hierarchy(df: pd.DataFrame):
    """Hierarchical horizontal stacked bar: family rows; L2 entities as stacked segments."""
    grouped = df.groupby(["Family", "L2"]).size().reset_index(name="n")
    grouped = grouped[grouped["Family"].isin(FAMILY_ORDER)]

    family_totals = grouped.groupby("Family")["n"].sum().reindex(FAMILY_ORDER).fillna(0).astype(int)
    family_order = [f for f in FAMILY_ORDER if family_totals[f] > 0]

    fig = go.Figure()
    # For each family build segments by L2 in descending L2 size
    for fam in family_order:
        sub = grouped[grouped["Family"] == fam].sort_values("n", ascending=False)
        x_offset = 0
        # alternating shade within family (using family base color, varying alpha)
        for j, (_, r) in enumerate(sub.iterrows()):
            base = FAMILY_COLORS[fam]
            alpha = 1.0 - 0.12 * j  # darker for largest segment
            alpha = max(alpha, 0.45)
            seg_color = _hex_with_alpha(base, alpha)
            label = r["L2"]
            n = int(r["n"])
            fig.add_trace(go.Bar(
                y=[fam], x=[n], orientation="h",
                marker=dict(color=seg_color, line=dict(color="#ffffff", width=1)),
                name=label, hovertemplate=f"{fam} · {label}: {n}<extra></extra>",
                text=[f"{label}: {n}"] if n >= 6 else [""],
                textposition="inside", insidetextanchor="middle",
                textfont=dict(size=10, color="#ffffff"),
                showlegend=False,
            ))
            x_offset += n
        # total annotation at end
        fig.add_annotation(
            x=family_totals[fam], y=fam,
            text=f" {family_totals[fam]}",
            showarrow=False, font=dict(size=11, color=THEME["text"]),
            xanchor="left", yanchor="middle",
        )

    fig.update_layout(
        barmode="stack",
        font=FONT, paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["bg"],
        margin=dict(l=180, r=80, t=40, b=60), height=460, width=900,
        showlegend=False,
        yaxis=dict(categoryorder="array", categoryarray=family_order[::-1],
                   title="", showgrid=False, linecolor=THEME["border"],
                   tickfont=dict(size=12, color=THEME["text"])),
        xaxis=dict(title="Number of trials",
                   showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                   linecolor=THEME["border"], ticks="outside",
                   tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"])),
    )
    _save(fig, "fig2_disease_hierarchy")


def _hex_with_alpha(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb to rgba(r,g,b,alpha)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.3f})"


def fig3_temporal_by_family(df: pd.DataFrame):
    """Stacked area: trials initiated per year, by L1 family, 2019–2026."""
    sub = df[df["StartYear"].notna()].copy()
    sub["StartYear"] = sub["StartYear"].astype(int)
    yearly = sub.groupby(["StartYear", "Family"]).size().unstack(fill_value=0)
    yrs = list(range(int(yearly.index.min()), int(yearly.index.max()) + 1))
    yearly = yearly.reindex(yrs, fill_value=0)

    fig = go.Figure()
    for fam in FAMILY_ORDER:
        if fam not in yearly.columns:
            continue
        fig.add_trace(go.Scatter(
            x=yearly.index, y=yearly[fam], name=fam,
            mode="lines", stackgroup="one",
            line=dict(width=0.6, color=FAMILY_COLORS[fam]),
            fillcolor=FAMILY_COLORS[fam],
            hovertemplate=f"%{{x}} · {fam}: %{{y}}<extra></extra>",
        ))
    _layout(fig, height=460, width=900)
    fig.update_xaxes(title_text="Trial start year", dtick=1)
    fig.update_yaxes(title_text="Trials initiated")
    fig.update_layout(legend=dict(orientation="v", x=1.02, y=1, font=dict(size=10)),
                      margin=dict(l=70, r=200, t=30, b=60))
    _save(fig, "fig3_temporal_by_family")


def fig4_target_landscape(df: pd.DataFrame):
    """Horizontal bar: top-15 antigen targets, color = target class."""
    counts = df["TargetCategory"].fillna("Other_or_unknown").value_counts()
    top = counts.head(15)
    classes = top.index.map(_target_class).tolist()
    colors = [TARGET_CLASS_COLORS[c] for c in classes]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=top.index[::-1], x=top.values[::-1],
        orientation="h",
        marker=dict(color=colors[::-1], line=dict(color="#ffffff", width=0.5)),
        text=[str(v) for v in top.values[::-1]],
        textposition="outside", textfont=dict(size=11, color=THEME["text"]),
        hovertemplate="%{y}: %{x}<extra></extra>",
        showlegend=False,
    ))
    # Manual class legend via dummy traces
    for cls, col in TARGET_CLASS_COLORS.items():
        fig.add_trace(go.Bar(
            y=[None], x=[None], name=cls,
            marker=dict(color=col), showlegend=True,
        ))

    _layout(fig, height=520, width=850)
    fig.update_xaxes(title_text="Number of trials")
    fig.update_yaxes(title_text="", tickfont=dict(size=11, color=THEME["text"]))
    fig.update_layout(margin=dict(l=180, r=60, t=30, b=60),
                      legend=dict(orientation="v", x=0.78, y=0.18,
                                  bordercolor=THEME["border"], borderwidth=1,
                                  bgcolor="#ffffff"))
    _save(fig, "fig4_target_landscape")


def fig5_modality(df: pd.DataFrame):
    """Two-panel: (A) overall modality donut; (B) modality % by start year ≥2019."""
    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.40, 0.60],
        specs=[[{"type": "domain"}, {"type": "xy"}]],
        subplot_titles=("(A) Overall modality mix", "(B) Trials initiated per year, by modality"),
        horizontal_spacing=0.12,
    )

    overall = df["ProductType"].value_counts()
    order = ["Autologous", "Allogeneic/Off-the-shelf", "In vivo", "Unclear"]
    vals = [int(overall.get(k, 0)) for k in order]
    short_labels = ["Autologous", "Allo", "In vivo", "Unclear"]
    fig.add_trace(go.Pie(
        labels=short_labels, values=vals,
        marker=dict(colors=[MODALITY_COLORS[k] for k in order],
                    line=dict(color="#ffffff", width=1)),
        hole=0.55,
        text=[f"{lbl}<br>{v} ({v/sum(vals):.1%})" if v/sum(vals) >= 0.05 else ""
              for lbl, v in zip(short_labels, vals)],
        textinfo="text", textposition="inside", insidetextorientation="horizontal",
        textfont=dict(size=11, color="#ffffff"),
        sort=False, direction="clockwise",
        domain=dict(x=[0.02, 0.38], y=[0.04, 0.80]),
        showlegend=False,
    ), row=1, col=1)
    # Annotate "n=" total in donut center
    fig.add_annotation(
        xref="paper", yref="paper", x=0.20, y=0.42,
        text=f"<b>n = {sum(vals)}</b>", showarrow=False,
        font=dict(size=12, color=THEME["text"]),
    )

    sub = df[df["StartYear"].notna() & (df["StartYear"] >= 2019)].copy()
    sub["StartYear"] = sub["StartYear"].astype(int)
    piv = sub.groupby(["StartYear", "ProductType"]).size().unstack(fill_value=0)
    piv = piv.reindex(columns=[c for c in order if c in piv.columns], fill_value=0)
    piv_n = piv.copy()
    piv = piv.div(piv.sum(axis=1), axis=0) * 100

    for col in [c for c in order if c in piv.columns]:
        fig.add_trace(go.Bar(
            x=piv.index, y=piv[col], name=col,
            marker=dict(color=MODALITY_COLORS[col]),
            customdata=piv_n[col].values,
            hovertemplate="%{x} · " + col + ": %{y:.1f}% (n=%{customdata})<extra></extra>",
            showlegend=True,
        ), row=1, col=2)

    fig.update_layout(barmode="stack", font=FONT,
                      paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["bg"],
                      margin=dict(l=40, r=40, t=60, b=80), height=480, width=1100,
                      legend=dict(orientation="h", x=0.50, y=-0.12, xanchor="center",
                                  font=dict(size=10)))
    fig.update_xaxes(title_text="Start year", row=1, col=2, dtick=1,
                     showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                     linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]))
    fig.update_yaxes(title_text="% of trials initiated that year", row=1, col=2,
                     range=[0, 100],
                     showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                     linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=11, color=THEME["muted"]))
    _save(fig, "fig5_modality")


def fig6_geography(df: pd.DataFrame):
    """Three-panel: (A) world choropleth, (B) top-10 country bar,
    (C) regional share over time."""
    fig = make_subplots(
        rows=2, cols=2, column_widths=[0.60, 0.40], row_heights=[0.50, 0.50],
        specs=[[{"type": "geo", "rowspan": 2}, {"type": "xy"}],
               [None, {"type": "xy"}]],
        subplot_titles=("(A) Trials per country (log scale)",
                        "(B) Top 10 countries",
                        "(C) Regional share of trials by start year"),
        horizontal_spacing=0.08, vertical_spacing=0.22,
    )

    countries = df["Countries"].dropna().str.split("|").explode().str.strip()
    countries = countries[countries != ""]
    cc = countries.value_counts()
    iso_df = pd.DataFrame({"country": cc.index, "n": cc.values})
    iso_df["iso3"] = iso_df["country"].map(ISO3)
    iso_df = iso_df.dropna(subset=["iso3"])
    import math
    iso_df["log_n"] = iso_df["n"].apply(lambda v: math.log10(max(v, 1)))

    fig.add_trace(go.Choropleth(
        locations=iso_df["iso3"], z=iso_df["log_n"],
        text=[f"{c}: {n}" for c, n in zip(iso_df["country"], iso_df["n"])],
        hovertemplate="%{text}<extra></extra>",
        colorscale=[[0.0, "#dbeafe"], [0.4, "#5fa3d9"], [0.7, "#2e6dbf"], [1.0, "#0b3d91"]],
        marker_line_color=THEME["border"], marker_line_width=0.5,
        colorbar=dict(
            title=dict(text="Trials", font=dict(size=9)),
            tickvals=[0, 1, 2, math.log10(iso_df["n"].max())],
            ticktext=["1", "10", "100", str(int(iso_df["n"].max()))],
            len=0.36, thickness=8, x=0.02, y=0.30, yanchor="middle",
            tickfont=dict(size=8, color=THEME["muted"])),
    ), row=1, col=1)
    fig.update_geos(showcountries=True, countrycolor=THEME["border"],
                    showcoastlines=False, showland=True, landcolor="#f8fafc",
                    showocean=False, projection_type="natural earth", row=1, col=1)

    # (B) top-10 country bar
    top = cc.head(10)
    fig.add_trace(go.Bar(
        y=top.index[::-1], x=top.values[::-1], orientation="h",
        marker=dict(color="#0b3d91"),
        text=[str(v) for v in top.values[::-1]], textposition="outside",
        textfont=dict(size=10, color=THEME["text"]),
        hovertemplate="%{y}: %{x}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)

    # (C) regional share by year
    sub = df[df["StartYear"].notna()].copy()
    sub["StartYear"] = sub["StartYear"].astype(int)
    rows = []
    for _, r in sub.iterrows():
        if not isinstance(r["Countries"], str) or not r["Countries"]:
            continue
        for c in r["Countries"].split("|"):
            c = c.strip()
            if not c:
                continue
            rows.append({"StartYear": r["StartYear"],
                         "Region": REGIONS.get(c, "Rest of World")})
    rdf = pd.DataFrame(rows)
    if not rdf.empty:
        piv = rdf.groupby(["StartYear", "Region"]).size().unstack(fill_value=0)
        piv = piv.div(piv.sum(axis=1), axis=0) * 100
        for region in ["East Asia", "Europe", "North America", "Oceania", "Rest of World"]:
            if region not in piv.columns:
                continue
            fig.add_trace(go.Bar(
                x=piv.index, y=piv[region], name=region,
                marker=dict(color=REGION_COLORS[region]),
                hovertemplate="%{x} · " + region + ": %{y:.1f}%<extra></extra>",
            ), row=2, col=2)

    fig.update_layout(barmode="stack", font=FONT,
                      paper_bgcolor=THEME["bg"], plot_bgcolor=THEME["bg"],
                      margin=dict(l=60, r=40, t=60, b=110), height=760, width=1200,
                      legend=dict(orientation="h", x=0.78, y=-0.10, xanchor="center",
                                  font=dict(size=9)))
    fig.update_xaxes(title_text="Trials", row=1, col=2,
                     showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                     linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=10, color=THEME["muted"]),
                     title_standoff=8)
    fig.update_yaxes(title_text="", row=1, col=2,
                     tickfont=dict(size=10, color=THEME["text"]))
    fig.update_xaxes(title_text="Start year", row=2, col=2, dtick=1,
                     showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                     linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=10, color=THEME["muted"]),
                     title_standoff=8)
    fig.update_yaxes(title_text="% of trial-country pairs", row=2, col=2, range=[0, 100],
                     showgrid=True, gridcolor=THEME["grid"], zeroline=False,
                     linecolor=THEME["border"], ticks="outside",
                     tickcolor=THEME["border"], tickfont=dict(size=10, color=THEME["muted"]),
                     title_standoff=4, title_font=dict(size=10))
    _save(fig, "fig6_geography")


def fig7_phase_sponsor(df: pd.DataFrame):
    """Stacked horizontal bar: trial counts by phase, stacked by sponsor sector."""
    phase_order = [
        "EARLY_PHASE1", "PHASE1", "PHASE1|PHASE2",
        "PHASE2", "PHASE2|PHASE3", "PHASE3", "Unknown",
    ]
    phase_label = {
        "EARLY_PHASE1": "Early Phase 1",
        "PHASE1": "Phase 1",
        "PHASE1|PHASE2": "Phase 1/2",
        "PHASE2": "Phase 2",
        "PHASE2|PHASE3": "Phase 2/3",
        "PHASE3": "Phase 3",
        "Unknown": "Unknown",
    }
    sponsor_order = ["Academic", "Industry", "Government", "Other"]

    sub = df.copy()
    sub["Phase"] = sub["Phase"].fillna("Unknown")
    sub.loc[~sub["Phase"].isin(phase_order), "Phase"] = "Unknown"
    sub["SponsorType"] = sub["SponsorType"].fillna("Other")
    sub.loc[~sub["SponsorType"].isin(sponsor_order), "SponsorType"] = "Other"

    piv = sub.groupby(["Phase", "SponsorType"]).size().unstack(fill_value=0)
    piv = piv.reindex(index=phase_order, columns=sponsor_order, fill_value=0)
    piv = piv[piv.sum(axis=1) > 0]  # drop empty phases

    fig = go.Figure()
    for s in sponsor_order:
        if s not in piv.columns:
            continue
        fig.add_trace(go.Bar(
            y=[phase_label[p] for p in piv.index],
            x=piv[s], orientation="h", name=s,
            marker=dict(color=SPONSOR_COLORS[s], line=dict(color="#ffffff", width=0.5)),
            text=[str(v) if v > 0 else "" for v in piv[s]],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#ffffff"),
            hovertemplate=f"%{{y}} · {s}: %{{x}}<extra></extra>",
        ))

    _layout(fig, height=460, width=900)
    fig.update_layout(barmode="stack",
                      legend=dict(orientation="h", x=0.5, y=-0.28, xanchor="center",
                                  font=dict(size=10)),
                      margin=dict(l=120, r=60, t=30, b=120))
    fig.update_xaxes(title_text="Number of trials", title_standoff=12)
    fig.update_yaxes(title_text="", autorange="reversed")
    _save(fig, "fig7_phase_sponsor")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    df = load_trials()
    prisma = load_prisma()
    print(f"Loaded {len(df)} trials, {sum(prisma.values()) - prisma['n_included'] - prisma['n_total_excluded'] + prisma['n_fetched']} fetched.")
    print()
    print("Fig 1: PRISMA + cumulative growth")
    fig1_prisma_growth(df, prisma)
    print("Fig 2: Disease hierarchy")
    fig2_disease_hierarchy(df)
    print("Fig 3: Temporal trends by family")
    fig3_temporal_by_family(df)
    print("Fig 4: Antigen target landscape")
    fig4_target_landscape(df)
    print("Fig 5: Modality mix")
    fig5_modality(df)
    print("Fig 6: Geography")
    fig6_geography(df)
    print("Fig 7: Phase × sponsor")
    fig7_phase_sponsor(df)
    print()
    print(f"All figures written to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
