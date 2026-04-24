import os
import re
import subprocess
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from datetime import date, datetime, timezone

from pipeline import (
    build_all_from_api,
    load_snapshot,
    list_snapshots,
    save_snapshot,
    BASE_URL,
    _normalize_text,
)
from config import (
    DISEASE_ENTITIES,
    EXCLUDED_INDICATION_TERMS,
    OTHER_IMMUNE_MEDIATED_TERMS,
    HARD_EXCLUDED_NCT_IDS,
    CAR_CORE_TERMS,
    CAR_SPECIFIC_TARGET_TERMS,
    CAR_NK_TERMS,
    CAAR_T_TERMS,
    CAR_TREG_TERMS,
    ALLOGENEIC_MARKERS,
    AUTOL_MARKERS,
    GENERIC_AUTOIMMUNE_TERMS,
    NAMED_PRODUCT_TARGETS,
    NAMED_PRODUCT_TYPES,
    NAMED_PRODUCT_PLATFORMS,
)

st.set_page_config(
    page_title="CAR-T Rheumatology Trials Monitor",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATUS_OPTIONS = [
    "RECRUITING",
    "NOT_YET_RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "COMPLETED",
    "TERMINATED",
    "SUSPENDED",
    "WITHDRAWN",
    "UNKNOWN",
]

STATUS_DISPLAY = {
    "RECRUITING":              "Recruiting",
    "NOT_YET_RECRUITING":      "Not yet recruiting",
    "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
    "ENROLLING_BY_INVITATION": "By invitation",
    "COMPLETED":               "Completed",
    "TERMINATED":              "Terminated",
    "SUSPENDED":               "Suspended",
    "WITHDRAWN":               "Withdrawn",
    "UNKNOWN":                 "Unknown",
}

OPEN_SITE_STATUSES = {
    "RECRUITING",
    "NOT_YET_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "ACTIVE_NOT_RECRUITING",
}

PHASE_ORDER = [
    "EARLY_PHASE1",
    "PHASE1",
    "PHASE1|PHASE2",
    "PHASE2",
    "PHASE2|PHASE3",
    "PHASE3",
    "PHASE4",
    "Unknown",
]

PHASE_LABELS = {
    "EARLY_PHASE1": "Early Phase I",
    "PHASE1": "Phase I",
    "PHASE1|PHASE2": "Phase I/II",
    "PHASE2": "Phase II",
    "PHASE2|PHASE3": "Phase II/III",
    "PHASE3": "Phase III",
    "PHASE4": "Phase IV",
    "Unknown": "Unknown",
}

# ---------------------------------------------------------------------------
# Cell-therapy modality — module-level so sidebar filter and pub-figures
# tab both use the same constants and function.
# ---------------------------------------------------------------------------
_MODALITY_ORDER = [
    "Auto CAR-T", "Allo CAR-T", "CAR-T (unclear)",
    "CAR-γδ T", "CAR-NK", "CAR-Treg", "CAAR-T", "In vivo CAR",
]

_MODALITY_COLORS: dict[str, str] = {}   # filled after NEJM constants are defined


_PLATFORM_TO_MODALITY = {
    "CAR-NK":            "CAR-NK",
    "CAR-Treg":          "CAR-Treg",
    "CAAR-T":            "CAAR-T",
    "CAR-T_γδ":          "CAR-γδ T",
    "CAR-iNKT":          "CAR-γδ T",  # nearest bucket; no separate iNKT row yet
    "In-vivo_mRNA-LNP":  "In vivo CAR",
}


def _modality(row) -> str:
    """Resolve Modality from a named-product platform override first, then
    TargetCategory / ProductType, then text heuristics. Named-product platform
    is the most reliable signal because it comes from a curated registry with
    CTgov-evidence citations (see config.NAMED_PRODUCTS)."""
    t = str(row.get("TargetCategory", ""))
    p = str(row.get("ProductType", ""))
    _txt = " ".join([
        str(row.get("BriefTitle", "")),
        str(row.get("BriefSummary", "")),
        str(row.get("Interventions", "")),
    ]).lower()
    normalized = _normalize_text(_txt)

    # 1) Named-product platform override (highest-fidelity, evidence-backed).
    for platform, aliases in NAMED_PRODUCT_PLATFORMS.items():
        mapped = _PLATFORM_TO_MODALITY.get(platform)
        if mapped is None:
            continue  # CAR-T platform → fall through to type-based logic
        if any(_normalize_text(a) in normalized for a in aliases):
            return mapped

    # 2) Target-category heuristics for platforms encoded as pseudo-targets.
    if t == "CAR-NK":
        return "CAR-NK"
    if t == "CAAR-T":
        return "CAAR-T"
    if t in ("CAR-Treg", "CD6"):
        return "CAR-Treg"

    # 3) Text fallbacks for products not in the named registry.
    has_gd_t = (
        "γδ" in _txt or "gamma delta" in _txt or "gamma-delta" in _txt
        or "-gdt" in _txt or " gdt " in _txt
    )
    has_nk = (
        "car-nk" in _txt or "car nk" in _txt
        or "natural killer" in _txt
    )
    if has_nk:
        return "CAR-NK"
    if has_gd_t:
        return "CAR-γδ T"

    # 4) ProductType-based final bucket.
    if p == "In vivo":
        return "In vivo CAR"
    if p == "Autologous":
        return "Auto CAR-T"
    if p == "Allogeneic/Off-the-shelf":
        return "Allo CAR-T"
    return "CAR-T (unclear)"


_PLATFORM_LABELS = {"CAR-NK", "CAR-Treg", "CAAR-T", "CAR-γδ T"}

# ---------------------------------------------------------------------------
# Disease families — the rheum analogue of the oncology app's Heme-onc vs
# Solid-onc top-level grouping. This gives a stable "branch" dimension that
# collapses related indications (e.g., SLE + SSc + Sjögren → CTD) for use in
# stacked charts and the disease-hierarchy sunburst.
# ---------------------------------------------------------------------------
_DISEASE_FAMILY_MAP = {
    "SLE":                   "Connective tissue",
    "SSc":                   "Connective tissue",
    "Sjogren":               "Connective tissue",
    "IIM":                   "Connective tissue",
    "CTD_other":             "Connective tissue",
    "IgG4-RD":               "Connective tissue",
    "RA":                    "Inflammatory arthritis",
    "AAV":                   "Vasculitis",
    "Behcet":                "Vasculitis",
    # Non-rheum autoimmune / immune-mediated indications that still show up
    # in CAR-T trial records (pipeline emits "Other immune-mediated" as a
    # valid DiseaseEntity, cGVHD appears in some historical trials).
    "Other immune-mediated": "Other autoimmune",
    "cGVHD":                 "Other autoimmune",
}
_FAMILY_ORDER = [
    "Connective tissue",
    "Inflammatory arthritis",
    "Vasculitis",
    "Other autoimmune",
    "Basket/Multidisease",
    "Other / Unclassified",
]
# Professional, non-purple palette: navy for the dominant CTD family, other
# families in complementary muted hues. Shared by sunburst and Deep Dive charts.
_FAMILY_COLORS = {
    "Connective tissue":       "#0b3d91",   # navy
    "Inflammatory arthritis":  "#b45309",   # amber-700
    "Vasculitis":              "#0f766e",   # teal-700
    "Other autoimmune":        "#475569",   # slate-600
    "Basket/Multidisease":     "#64748b",   # slate-500
    "Other / Unclassified":    "#cbd5e1",   # slate-300 — visibly lightest
}


def _disease_family(entity: str, trial_design: str | None = None) -> str:
    """Map a disease entity to its family. Basket trials always resolve to
    'Basket/Multidisease' regardless of their primary-disease assignment —
    matches how the sunburst presents them as a distinct branch."""
    if trial_design == "Basket/Multidisease":
        return "Basket/Multidisease"
    if not entity or entity in ("Unclassified", ""):
        return "Other / Unclassified"
    return _DISEASE_FAMILY_MAP.get(str(entity), "Other / Unclassified")

THEME = {
    "bg":      "#ffffff",            # pure white canvas
    "surface": "#ffffff",            # surface = canvas (flat, no card contrast)
    "surf2":   "#f8fafc",            # slate-50 — subtle hover/strip
    "surf3":   "#e5e7eb",            # gray-200
    "text":    "#0b1220",            # near-black
    "muted":   "#475569",            # slate-600 — readable secondary
    "faint":   "#94a3b8",            # slate-400
    "border":  "#e5e7eb",            # gray-200 — single hairline color
    "primary": "#0b3d91",            # deep navy — clinical/scientific
    "teal":    "#0f766e",            # teal-700
    "amber":   "#92400e",            # amber-800
    "shadow":  "none",               # flat aesthetic — no shadows
    "grid":    "#f1f5f9",            # slate-100
}

# Shared UI tokens — single source of truth for spacing / sizing / fonts.
PANEL_HEIGHT = 440           # "Landscape at a glance" panels
TABLE_HEIGHT_DEFAULT = 360   # default st.dataframe height when not auto-sized
HAIRLINE = THEME["border"]   # alias for visual separators
FONT_FAMILY = "Inter, -apple-system, sans-serif"

# Canonical CT.gov country name → ISO-3 mapping.  Plotly's `locationmode="country names"`
# is deprecated, so choropleths are rendered with ISO-3 codes; unknown names are dropped
# with a warning rather than silently mis-plotted.
_COUNTRY_TO_ISO3 = {
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Belgium": "BEL",
    "Brazil": "BRA", "Bulgaria": "BGR", "Canada": "CAN", "Chile": "CHL",
    "China": "CHN", "Colombia": "COL", "Croatia": "HRV", "Czechia": "CZE",
    "Czech Republic": "CZE", "Denmark": "DNK", "Egypt": "EGY", "Estonia": "EST",
    "Finland": "FIN", "France": "FRA", "Georgia": "GEO", "Germany": "DEU",
    "Greece": "GRC", "Hong Kong": "HKG", "Hungary": "HUN", "Iceland": "ISL",
    "India": "IND", "Indonesia": "IDN", "Iran, Islamic Republic of": "IRN",
    "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA", "Japan": "JPN",
    "Jordan": "JOR", "Korea, Republic of": "KOR", "Latvia": "LVA",
    "Lebanon": "LBN", "Lithuania": "LTU", "Luxembourg": "LUX", "Malaysia": "MYS",
    "Mexico": "MEX", "Netherlands": "NLD", "New Zealand": "NZL",
    "Norway": "NOR", "Pakistan": "PAK", "Peru": "PER", "Philippines": "PHL",
    "Poland": "POL", "Portugal": "PRT", "Puerto Rico": "PRI", "Romania": "ROU",
    "Russian Federation": "RUS", "Saudi Arabia": "SAU", "Serbia": "SRB",
    "Singapore": "SGP", "Slovakia": "SVK", "Slovenia": "SVN",
    "South Africa": "ZAF", "Spain": "ESP", "Sweden": "SWE", "Switzerland": "CHE",
    "Taiwan": "TWN", "Thailand": "THA", "Tunisia": "TUN", "Turkey": "TUR",
    "Türkiye": "TUR", "Ukraine": "UKR", "United Arab Emirates": "ARE",
    "United Kingdom": "GBR", "United States": "USA", "Uruguay": "URY",
    "Viet Nam": "VNM", "Vietnam": "VNM",
}


def _attach_iso3(df_country: pd.DataFrame, country_col: str = "Country") -> pd.DataFrame:
    """Add an Iso3 column; drop rows with no mapping (rare, e.g. 'Unknown')."""
    out = df_country.copy()
    out["Iso3"] = out[country_col].map(_COUNTRY_TO_ISO3)
    return out.dropna(subset=["Iso3"])


px.defaults.template = "plotly_white"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Reset / base ─────────────────────────────────────────────────── */
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}

    .stApp {{
        background: {THEME["bg"]};
        color: {THEME["text"]};
    }}

    .block-container {{
        max-width: 1320px;
        padding-top: 1.2rem;
        padding-bottom: 2.4rem;
        line-height: 1.55;
    }}

    h1 {{
        color: {THEME["text"]};
        font-weight: 600;
        letter-spacing: -0.022em;
        line-height: 1.2;
    }}
    h2 {{
        color: {THEME["text"]};
        font-weight: 600;
        letter-spacing: -0.018em;
        line-height: 1.25;
    }}
    h3 {{
        color: {THEME["text"]};
        font-weight: 600;
        letter-spacing: -0.012em;
        line-height: 1.3;
    }}

    /* ── Scrollbar ────────────────────────────────────────────────────── */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: {THEME["surf3"]};
        border-radius: 3px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: {THEME["faint"]}; }}

    /* ── Hero ─────────────────────────────────────────────────────────── */
    .hero {{
        padding: 1.6rem 0 1.4rem;
        border-top: 3px solid {THEME["primary"]};
        border-bottom: 1px solid {THEME["border"]};
        background: transparent;
        margin-bottom: 1.4rem;
    }}

    .hero-eyebrow {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.66rem;
        font-weight: 600;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: {THEME["primary"]};
        margin-bottom: 0.55rem;
    }}

    .hero-eyebrow::before {{
        content: '';
        display: inline-block;
        width: 18px;
        height: 1px;
        background: {THEME["primary"]};
        flex-shrink: 0;
    }}

    .hero-title {{
        font-size: 1.7rem;
        font-weight: 600;
        letter-spacing: -0.022em;
        line-height: 1.2;
        color: {THEME["text"]};
        margin-bottom: 0.55rem;
    }}

    .hero-sub {{
        font-size: 0.86rem;
        line-height: 1.6;
        color: {THEME["muted"]};
        max-width: 820px;
        font-weight: 400;
    }}

    /* ── Cards (flat, line-delineated) ────────────────────────────────── */
    .section-card {{
        background: transparent;
        border: none;
        border-top: 1px solid {THEME["border"]};
        border-radius: 0;
        padding: 1.0rem 0 0.8rem;
        box-shadow: none;
        margin-bottom: 0.6rem;
    }}

    .section-card h3 {{
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: {THEME["muted"]};
        margin-top: 0;
        margin-bottom: 0.85rem;
        padding-bottom: 0;
        border-bottom: none;
    }}

    .metric-card {{
        background: transparent;
        border: none;
        border-top: 2px solid {THEME["primary"]};
        border-radius: 0;
        padding: 0.7rem 0.1rem 0.4rem;
        box-shadow: none;
        transition: none;
    }}

    .metric-card:hover {{
        box-shadow: none;
    }}

    .metric-label {{
        font-size: 0.66rem;
        font-weight: 600;
        color: {THEME["muted"]};
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }}

    .metric-value {{
        font-size: 1.65rem;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: {THEME["text"]};
        line-height: 1.05;
        font-variant-numeric: tabular-nums;
    }}

    .metric-foot {{
        margin-top: 0.35rem;
        font-size: 0.72rem;
        color: {THEME["faint"]};
        font-weight: 400;
        line-height: 1.4;
    }}

    .small-note {{
        color: {THEME["muted"]};
        font-size: 0.84rem;
        line-height: 1.6;
        margin-top: 0.3rem;
        margin-bottom: 0.55rem;
        letter-spacing: -0.01em;
    }}

    /* ── Sidebar ──────────────────────────────────────────────────────── */
    div[data-testid="stSidebar"] {{
        background: {THEME["surf2"]};
        border-right: 1px solid {THEME["border"]};
    }}

    /* Top accent strip */
    [data-testid="stSidebar"] > div:first-child {{
        border-top: 2px solid {THEME["primary"]};
    }}

    /* Section label — thread-thin, all-caps */
    div[data-testid="stSidebar"] h1,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3 {{
        font-size: 0.59rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
        color: {THEME["faint"]} !important;
        margin-top: 1.3rem !important;
        margin-bottom: 0.1rem !important;
        padding-top: 0.9rem !important;
        padding-bottom: 0.1rem !important;
        border-top: 1px solid {THEME["border"]} !important;
        border-bottom: none !important;
    }}

    /* Widget labels */
    div[data-testid="stSidebar"] label {{
        font-size: 0.73rem !important;
        font-weight: 500 !important;
        color: {THEME["muted"]} !important;
        letter-spacing: -0.01em !important;
    }}
    div[data-testid="stSidebar"] p {{
        color: {THEME["text"]};
        font-size: 0.75rem;
    }}

    /* Multiselect / select inputs — flat, square */
    div[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background: {THEME["surface"]} !important;
        border: 1px solid {THEME["border"]} !important;
        border-radius: 2px !important;
        min-height: 28px !important;
        font-size: 0.75rem !important;
    }}
    div[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {{
        border-color: {THEME["primary"]} !important;
        box-shadow: none !important;
    }}

    /* Radio options — hover highlight */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label {{
        border-radius: 0 !important;
        padding: 0.28rem 0.45rem !important;
        transition: background 0.1s !important;
        margin-bottom: 0.06rem !important;
    }}
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {{
        background: {THEME["surface"]} !important;
    }}

    /* ── Buttons (flat, square) ───────────────────────────────────────── */
    .stButton > button,
    .stDownloadButton > button {{
        background: {THEME["surface"]};
        color: {THEME["text"]};
        border: 1px solid {THEME["border"]};
        border-radius: 2px;
        padding: 0.42rem 0.95rem;
        font-size: 0.82rem;
        font-weight: 500;
        letter-spacing: -0.005em;
        box-shadow: none;
        transition: background 0.12s, border-color 0.12s;
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        background: {THEME["surf2"]};
        border-color: {THEME["primary"]};
        box-shadow: none;
        color: {THEME["primary"]};
    }}

    /* ── Tabs — underline style (NEJM/Nature-inspired) ────────────────── */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {THEME["border"]};
        border-radius: 0;
        padding: 0;
        gap: 0;
    }}

    div[data-testid="stTabs"] [data-baseweb="tab"] {{
        border-radius: 0;
        padding: 10px 18px;
        font-size: 0.84rem;
        font-weight: 500;
        letter-spacing: -0.005em;
        color: {THEME["muted"]};
        background: transparent;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        margin-bottom: -1px;
        transition: color 0.12s, border-color 0.12s;
    }}

    div[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
        background: transparent;
        color: {THEME["text"]};
    }}

    div[data-testid="stTabs"] button[aria-selected="true"] {{
        background: transparent !important;
        color: {THEME["primary"]} !important;
        font-weight: 600 !important;
        border-bottom: 2px solid {THEME["primary"]} !important;
        box-shadow: none;
    }}

    div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
    div[data-testid="stTabs"] [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* ── Data table ───────────────────────────────────────────────────── */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {THEME["border"]};
        border-radius: 2px;
        overflow: hidden;
        background: {THEME["surface"]};
    }}

    /* ── Form controls ────────────────────────────────────────────────── */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {{
        background-color: {THEME["surface"]};
        border-color: {THEME["border"]} !important;
        color: {THEME["text"]};
        border-radius: 2px;
    }}

    .stTextInput input,
    .stNumberInput input {{
        background: {THEME["surface"]};
        border-color: {THEME["border"]};
        border-radius: 2px;
        color: {THEME["text"]};
    }}

    /* ── Expander ─────────────────────────────────────────────────────── */
    div[data-testid="stExpander"] {{
        background: transparent;
        border: none;
        border-top: 1px solid {THEME["border"]};
        border-radius: 0;
        box-shadow: none;
    }}

    /* ── Multiselect tags — flat ──────────────────────────────────────── */
    div[data-baseweb="tag"] {{
        background-color: {THEME["surf2"]} !important;
        border: 1px solid {THEME["border"]} !important;
        border-radius: 2px !important;
    }}
    div[data-baseweb="tag"] span {{
        color: {THEME["text"]} !important;
        font-weight: 500;
    }}
    div[data-baseweb="tag"] [role="button"] {{
        color: {THEME["muted"]} !important;
        opacity: 0.8;
    }}

    /* ── Text visibility ──────────────────────────────────────────────── */
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] li,
    div[data-testid="stMarkdownContainer"] span {{
        color: {THEME["text"]};
    }}
    div[data-testid="stCaptionContainer"] p,
    .stCaption {{
        color: {THEME["muted"]} !important;
    }}
    div[data-testid="stAlert"] p {{
        color: {THEME["text"]};
    }}
    div[data-testid="stRadio"] label span,
    div[data-testid="stCheckbox"] label span {{
        color: {THEME["text"]} !important;
    }}
    div[data-testid="stSidebar"] span,
    div[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {{
        color: {THEME["text"]} !important;
    }}
    div[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: {THEME["muted"]} !important;
    }}

    /* ── Sidebar background ───────────────────────────────────────────── */
    [data-testid="stSidebarContent"] {{
        background-color: {THEME["surface"]} !important;
    }}

    /* ── Strip ALL auto-background containers ─────────────────────────── */
    div[data-testid="stVerticalBlock"],
    div[data-testid="stHorizontalBlock"],
    div[data-testid="stColumn"] > div,
    div[data-testid="block-container"] > div,
    div[data-testid="element-container"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        border-radius: 0 !important;
    }}

    /* ── st.metric() — clean, no white card ──────────────────────────── */
    div[data-testid="stMetric"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.4rem 0 !important;
        border-radius: 0 !important;
    }}
    div[data-testid="stMetricValue"] > div {{
        color: {THEME["text"]} !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        font-variant-numeric: tabular-nums;
    }}
    div[data-testid="stMetricLabel"] > div {{
        color: {THEME["muted"]} !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.10em !important;
        text-transform: uppercase !important;
    }}

    /* ── st.info / warning / success ─────────────────────────────────── */
    div[data-testid="stAlert"] {{
        background: rgba(29,78,216,0.04) !important;
        border: 1px solid rgba(29,78,216,0.14) !important;
        border-left: 3px solid {THEME["primary"]} !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }}
    div[data-testid="stAlert"] p {{
        color: {THEME["text"]} !important;
    }}

    /* ── Section spacing — replaces removed section-card divs ────────── */
    div[data-testid="stVerticalBlock"] h3 {{
        margin-top: 0.5rem !important;
        padding-top: 1.1rem !important;
        padding-bottom: 0.55rem !important;
        border-top: 1px solid {THEME["border"]} !important;
        letter-spacing: -0.03em !important;
    }}

    /* ── Journal-style figure header (publication tab) ────────────────── */
    .pub-fig-header {{
        margin-top: 1.6rem;
        padding-top: 1.1rem;
        padding-bottom: 0.55rem;
        border-top: 1px solid {THEME["border"]};
    }}
    .pub-fig-eyebrow {{
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: {THEME["primary"]};
        margin-bottom: 0.35rem;
    }}
    .pub-fig-title {{
        font-size: 1.05rem;
        font-weight: 600;
        letter-spacing: -0.012em;
        line-height: 1.3;
        color: {THEME["text"]};
        margin-bottom: 0.2rem;
    }}
    .pub-fig-sub {{
        font-size: 0.78rem;
        font-weight: 400;
        line-height: 1.5;
        color: {THEME["muted"]};
        margin-top: 0.15rem;
    }}
    .pub-fig-caption {{
        font-size: 0.72rem;
        font-style: italic;
        color: {THEME["faint"]};
        margin: 0.4rem 0 0.8rem 0;
        line-height: 1.45;
    }}
    /* Don't double-stroke the auto h3 border on figure headers */
    .pub-fig-header + div h3,
    .pub-fig-header ~ div[data-testid="stVerticalBlock"] h3 {{
        border-top: none !important;
        padding-top: 0 !important;
    }}

    /* ── Preserve explicit white surfaces ─────────────────────────────── */
    .metric-card {{
        background: {THEME["surface"]} !important;
    }}
    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrame"] > div {{
        background-color: {THEME["surface"]} !important;
    }}
    div[data-testid="stExpander"] {{
        background-color: {THEME["surface"]} !important;
        border: 1px solid {THEME["border"]} !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_live(max_records: int = 2000, statuses: tuple[str, ...] = ()) -> tuple:
    statuses_list = list(statuses) if statuses else None
    return build_all_from_api(max_records=max_records, statuses=statuses_list)


@st.cache_data(show_spinner=False)
def load_frozen(snapshot_date: str) -> tuple:
    return load_snapshot(snapshot_date)


def _add_modality_vectorized(frame: pd.DataFrame) -> pd.DataFrame:
    """Vectorized replacement for row-wise ``df.apply(_modality, axis=1)``.

    Produces identical output via boolean masks + np.select.
    Falls back to the row-wise implementation for any rows the vectorized
    logic leaves as ``None`` (should be zero in practice — belt-and-braces).
    """
    out = frame.copy()

    target = out.get("TargetCategory", pd.Series([""] * len(out))).fillna("").astype(str)
    ptype = out.get("ProductType", pd.Series([""] * len(out))).fillna("").astype(str)
    title = out.get("BriefTitle", pd.Series([""] * len(out))).fillna("").astype(str)
    summary = out.get("BriefSummary", pd.Series([""] * len(out))).fillna("").astype(str)
    interv = out.get("Interventions", pd.Series([""] * len(out))).fillna("").astype(str)
    txt = (title + " " + summary + " " + interv).str.lower()
    normalized = txt.apply(_normalize_text)

    # Named-product platform overrides (curated registry — highest fidelity)
    # Build an (index) → modality map for rows that hit a named-platform alias.
    platform_hit = pd.Series([None] * len(out), index=out.index, dtype="object")
    for platform, aliases in NAMED_PRODUCT_PLATFORMS.items():
        mapped = _PLATFORM_TO_MODALITY.get(platform)
        if mapped is None:
            continue
        alias_norms = [_normalize_text(a) for a in aliases]
        for alias in alias_norms:
            mask = normalized.str.contains(alias, regex=False, na=False) & platform_hit.isna()
            if mask.any():
                platform_hit.loc[mask] = mapped

    # Target-category pseudo-platform shortcuts
    tgt_nk = target.eq("CAR-NK")
    tgt_caar = target.eq("CAAR-T")
    tgt_treg = target.isin(["CAR-Treg", "CD6"])

    # Text fallbacks
    has_gd = (
        txt.str.contains("γδ", regex=False, na=False)
        | txt.str.contains("gamma delta", regex=False, na=False)
        | txt.str.contains("gamma-delta", regex=False, na=False)
        | txt.str.contains("-gdt", regex=False, na=False)
        | txt.str.contains(" gdt ", regex=False, na=False)
    )
    has_nk = (
        txt.str.contains("car-nk", regex=False, na=False)
        | txt.str.contains("car nk", regex=False, na=False)
        | txt.str.contains("natural killer", regex=False, na=False)
    )

    # ProductType final bucket
    is_invivo = ptype.eq("In vivo")
    is_auto = ptype.eq("Autologous")
    is_allo = ptype.eq("Allogeneic/Off-the-shelf")

    conditions = [
        platform_hit.notna(),
        tgt_nk,
        tgt_caar,
        tgt_treg,
        has_nk,
        has_gd,
        is_invivo,
        is_auto,
        is_allo,
    ]
    choices = [
        platform_hit.fillna("CAR-T (unclear)"),
        pd.Series("CAR-NK", index=out.index),
        pd.Series("CAAR-T", index=out.index),
        pd.Series("CAR-Treg", index=out.index),
        pd.Series("CAR-NK", index=out.index),
        pd.Series("CAR-γδ T", index=out.index),
        pd.Series("In vivo CAR", index=out.index),
        pd.Series("Auto CAR-T", index=out.index),
        pd.Series("Allo CAR-T", index=out.index),
    ]
    out["Modality"] = np.select(conditions, choices, default="CAR-T (unclear)")
    return out


@st.cache_data(show_spinner=False)
def _post_process_trials(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Cached post-processing applied after the source load.

    These are pure transformations (phase normalization + modality assignment)
    that only need to be recomputed when the raw dataframe changes — not on
    every widget-driven rerun.
    """
    if raw_df.empty:
        return raw_df
    out = add_phase_columns(raw_df)
    out = _add_modality_vectorized(out)
    # Bake NCTLink once here so downstream filtered slices inherit it for free
    # instead of rebuilding via a row-wise apply on every widget-driven rerun.
    _nct = out["NCTId"].astype("string")
    out["NCTLink"] = np.where(
        _nct.notna(),
        "https://clinicaltrials.gov/study/" + _nct.fillna(""),
        None,
    )
    return out


def metric_card(label: str, value, foot: str = ""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-foot">{foot}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _landscape_table_cols(dim_key: str, dim_label: str) -> dict:
    """Shared column_config for the three Deep Dive summary tables
    (by disease / product type / sponsor type)."""
    _enroll_help = (
        "Planned enrollment from CT.gov (self-reported target, not actual accrual)."
    )
    return {
        dim_key: st.column_config.TextColumn(dim_label),
        "Trials": st.column_config.NumberColumn("Trials", format="%d"),
        "Open": st.column_config.NumberColumn("Open / recruiting", format="%d"),
        "Sponsors": st.column_config.NumberColumn("Distinct sponsors", format="%d"),
        "TotalEnrolled": st.column_config.NumberColumn(
            "Total planned enrollment", format="%,d", help=_enroll_help,
        ),
        "MedianEnrollment": st.column_config.NumberColumn(
            "Median enrollment", format="%d", help=_enroll_help,
        ),
    }


def _trial_detail_cols(extra: dict | None = None) -> dict:
    """Shared column_config for drilldown 'Trials' detail tables."""
    cfg = {
        "NCTId":          st.column_config.TextColumn("NCT ID"),
        "NCTLink":        st.column_config.LinkColumn("Trial link", display_text="Open trial"),
        "BriefTitle":     st.column_config.TextColumn("Title", width="large"),
        "DiseaseEntity":  st.column_config.TextColumn("Disease"),
        "DiseaseEntities": st.column_config.TextColumn("Disease(s)", width="medium"),
        "TargetCategory": st.column_config.TextColumn("Target"),
        "ProductType":    st.column_config.TextColumn("Product"),
        "ProductName":    st.column_config.TextColumn("Named product", width="small"),
        "Phase":          st.column_config.TextColumn("Phase"),
        "OverallStatus":  st.column_config.TextColumn("Status"),
        "LeadSponsor":    st.column_config.TextColumn("Lead sponsor", width="medium"),
        "StartYear":      st.column_config.NumberColumn("Start year", format="%d"),
        "Countries":      st.column_config.TextColumn("Countries", width="medium"),
    }
    if extra:
        cfg.update(extra)
    return cfg


def _mini_count_cols(label: str) -> dict:
    """Shared column_config for the 2-col mini count tables
    ('Antigen targets', 'Product types', 'Named products', 'Top sponsors')."""
    return {
        label: st.column_config.TextColumn(label, width="medium"),
        "Trials": st.column_config.NumberColumn("Trials", format="%d", width="small"),
    }


def make_bar(df_plot, x, y, height=360, color="#1d4ed8"):
    fig = px.bar(
        df_plot, x=x, y=y, height=height,
        color_discrete_sequence=[color], template="plotly_white",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(family="Inter, sans-serif", size=12, color=THEME["text"]),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        bargap=0.35,
    )
    fig.update_traces(marker_line_width=0, opacity=0.90)
    fig.update_xaxes(showgrid=False, color=THEME["muted"], tickfont_size=11)
    fig.update_yaxes(
        gridcolor=THEME["grid"], gridwidth=1, color=THEME["muted"],
        tickfont_size=11, zeroline=False,
    )
    fig.update_layout(bargap=0.4)
    return fig


def uniq_join(series):
    vals = []
    for v in series.dropna():
        v = str(v).strip()
        if v and v not in vals:
            vals.append(v)
    return " | ".join(vals)


def split_pipe_values(series: pd.Series) -> list[str]:
    values = []
    for item in series.dropna():
        for part in str(item).split("|"):
            part = part.strip()
            if part:
                values.append(part)
    return values


def normalize_phase_value(x):
    if pd.isna(x):
        return "Unknown"
    s = str(x).strip()
    if not s:
        return "Unknown"

    s_upper = s.upper().replace(" ", "").replace("/", "|")
    mapping = {
        "EARLYPHASE1": "EARLY_PHASE1",
        "EARLYPHASEI": "EARLY_PHASE1",
        "PHASE1": "PHASE1",
        "PHASEI": "PHASE1",
        "PHASE1|PHASE2": "PHASE1|PHASE2",
        "PHASEI|PHASEII": "PHASE1|PHASE2",
        "PHASE12": "PHASE1|PHASE2",
        "PHASE1PHASE2": "PHASE1|PHASE2",
        "PHASE112": "PHASE1|PHASE2",
        "PHASE2": "PHASE2",
        "PHASEII": "PHASE2",
        "PHASE2|PHASE3": "PHASE2|PHASE3",
        "PHASEII|PHASEIII": "PHASE2|PHASE3",
        "PHASE23": "PHASE2|PHASE3",
        "PHASE2PHASE3": "PHASE2|PHASE3",
        "PHASE2123": "PHASE2|PHASE3",
        "PHASE3": "PHASE3",
        "PHASEIII": "PHASE3",
        "PHASE4": "PHASE4",
        "PHASEIV": "PHASE4",
        "N/A": "Unknown",
        "NA": "Unknown",
    }
    return mapping.get(s_upper, s_upper if s_upper in PHASE_ORDER else "Unknown")


def add_phase_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["Phase"] = out["Phase"].fillna("Unknown")
    out["PhaseNormalized"] = out["Phase"].apply(normalize_phase_value)
    out["PhaseOrdered"] = pd.Categorical(out["PhaseNormalized"], categories=PHASE_ORDER, ordered=True)
    out["PhaseLabel"] = out["PhaseNormalized"].map(PHASE_LABELS).fillna(out["Phase"])
    return out


st.markdown(
    """
    <div class="hero">
        <div class="hero-eyebrow">ClinicalTrials.gov &middot; Live pipeline</div>
        <div class="hero-title">CAR-T &amp; Cell Therapies<br>in Rheumatologic Diseases</div>
        <div class="hero-sub">
            Systematic landscape analysis of CAR-T, CAR-NK, CAAR-T, and CAR-Treg trials
            in systemic autoimmune diseases — with disease, target-antigen, and
            cell-therapy modality classification; global site-level geography; and
            publication-ready figures.
        </div>
        <div class="hero-sub" style="margin-top: 0.55rem;">
            Use the <strong>sidebar filters</strong> to narrow to a subgroup of interest — filter state propagates to every chart, table, map, and CSV export in the analysis tabs.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("Data source")

available_snapshots = list_snapshots()
prisma_counts: dict = {}

# Live-first. A snapshot is only used if the user has explicitly pinned one
# (reproducibility mode) or if the live fetch fails.
_pinned = st.session_state.get("pinned_snapshot")

if _pinned:
    if _pinned not in available_snapshots:
        st.sidebar.warning(f"Pinned snapshot {_pinned} is missing; reverting to live.")
        st.session_state["pinned_snapshot"] = None
        _pinned = None

if _pinned:
    with st.spinner(f"Loading pinned snapshot {_pinned}..."):
        df, df_sites, prisma_counts = load_frozen(_pinned)
    st.sidebar.info(f"**Pinned:** {_pinned} · {len(df)} trials")
    if st.sidebar.button("Unpin — switch back to live data", use_container_width=True):
        st.session_state["pinned_snapshot"] = None
        st.cache_data.clear()
        st.rerun()
else:
    try:
        with st.spinner("Fetching ClinicalTrials.gov (cached 24h)..."):
            df, df_sites, prisma_counts = load_live(statuses=None)
        st.sidebar.caption(f"Live pull · {len(df)} trials (cached 24h)")
    except Exception as api_err:
        st.sidebar.error(
            "ClinicalTrials.gov API is currently unreachable. "
            "Falling back to the most recent snapshot if available."
        )
        st.sidebar.caption(f"Error: {type(api_err).__name__}: {str(api_err)[:120]}")
        if available_snapshots:
            fallback = available_snapshots[0]
            with st.spinner(f"Loading snapshot {fallback}..."):
                df, df_sites, prisma_counts = load_frozen(fallback)
            st.sidebar.info(f"Loaded frozen snapshot **{fallback}** (fallback).")
        else:
            st.error(
                "Cannot load data: the ClinicalTrials.gov API is unreachable and no local "
                "snapshots exist. Please try again later or check the API status at "
                "https://clinicaltrials.gov/."
            )
            st.stop()

    if st.sidebar.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.sidebar.expander("Reproducibility — pin a frozen dataset", expanded=False):
        if available_snapshots:
            _pin_sel = st.selectbox(
                "Snapshot date",
                available_snapshots,
                key="pin_snapshot_selector",
            )
            if st.button("Pin this snapshot", use_container_width=True):
                st.session_state["pinned_snapshot"] = _pin_sel
                st.cache_data.clear()
                st.rerun()
        else:
            st.caption("No snapshots yet — save one below to pin it later.")
        if st.button("Save current as snapshot", use_container_width=True):
            snap_date = save_snapshot(df, df_sites, prisma_counts, statuses=None)
            st.success(f"Saved snapshot: {snap_date}")
            st.cache_data.clear()

# Phase normalization + modality assignment are pure transforms. Bundled and
# cached so they don't re-run on every widget-driven rerun.
df = _post_process_trials(df)

if df.empty:
    st.error("No studies were returned. Try broadening the status filters.")
    st.stop()
df["DiseaseFamily"] = df.apply(
    lambda r: _disease_family(r.get("DiseaseEntity"), r.get("TrialDesign")),
    axis=1,
)
# Safety-backfill columns that older cached snapshots may be missing.
# load_snapshot() handles this on disk, but an in-memory cached DataFrame from
# a prior deploy can still be served before a cache-clear.
if "SponsorType" not in df.columns and "LeadSponsor" in df.columns:
    try:
        from pipeline import _classify_sponsor as _cs_safety
        df["SponsorType"] = df.apply(
            lambda r: _cs_safety(r.get("LeadSponsor"), r.get("LeadSponsorClass")),
            axis=1,
        )
    except Exception:
        pass

st.sidebar.header("Filters")

_FILTER_KEYS = (
    "flt_disease", "flt_design", "flt_phase", "flt_target",
    "flt_status", "flt_product", "flt_modality", "flt_country",
    "flt_age", "flt_sponsor", "flt_confidence",
)
# Short URL parameter names (keep the URL readable).
_FILTER_QPARAM = {
    "flt_disease": "d", "flt_design": "dd", "flt_phase": "ph",
    "flt_target": "t", "flt_status": "s", "flt_product": "p",
    "flt_modality": "m", "flt_country": "c",
    "flt_age": "ag", "flt_sponsor": "sp", "flt_confidence": "cf",
}


def _seed_filter_from_query(state_key: str, options: list[str]) -> None:
    """If query string has a value for this filter and session_state doesn't,
    seed session_state. Unknown tokens are silently dropped."""
    if state_key in st.session_state:
        return
    qkey = _FILTER_QPARAM[state_key]
    raw = st.query_params.get(qkey)
    if raw is None:
        return
    if isinstance(raw, list):
        raw = ",".join(raw)
    items = [x.strip() for x in str(raw).split(",") if x.strip()]
    opt_set = set(options)
    valid = [x for x in items if x in opt_set]
    if valid:
        st.session_state[state_key] = valid


def _sync_filters_to_query(opt_map: dict[str, list[str]]) -> None:
    """Write current filter state to URL. Omit params that equal 'all selected'."""
    for state_key, options in opt_map.items():
        qkey = _FILTER_QPARAM[state_key]
        val = st.session_state.get(state_key)
        if val is None:
            st.query_params.pop(qkey, None)
            continue
        if set(val) == set(options):
            st.query_params.pop(qkey, None)
        else:
            st.query_params[qkey] = ",".join(val)


if st.sidebar.button("Reset filters", width='stretch'):
    for _k in _FILTER_KEYS:
        st.session_state.pop(_k, None)
    for _qk in _FILTER_QPARAM.values():
        st.query_params.pop(_qk, None)
    st.rerun()

# Disease entity (multi-select) — based on DiseaseEntities so basket trials appear under each disease
_all_disease_entities: set[str] = set()
for _val in df["DiseaseEntities"].dropna():
    for _e in str(_val).split("|"):
        _e = _e.strip()
        if _e:
            _all_disease_entities.add(_e)
disease_options = sorted(_all_disease_entities)
_seed_filter_from_query("flt_disease", disease_options)
disease_sel = st.sidebar.multiselect(
    "Disease entity",
    options=disease_options,
    default=disease_options,
    help="Basket/multi-disease trials appear under every disease they enrol.",
    key="flt_disease",
)

# Trial design (single disease vs basket)
design_options = sorted(df["TrialDesign"].dropna().unique().tolist())
_seed_filter_from_query("flt_design", design_options)
design_sel = st.sidebar.multiselect(
    "Trial design",
    options=design_options,
    default=design_options,
    help="Filter to single-disease trials only or include basket/multi-disease trials.",
    key="flt_design",
)

# Phase (multi-select, displayed as labels)
phase_options = [PHASE_LABELS[p] for p in PHASE_ORDER if p in set(df["PhaseNormalized"].astype(str))]
_seed_filter_from_query("flt_phase", phase_options)
phase_sel = st.sidebar.multiselect(
    "Phase",
    options=phase_options,
    default=phase_options,
    key="flt_phase",
)

# Target category (multi-select) — antigen targets only; platform labels live in modality filter
target_options = sorted(
    t for t in df["TargetCategory"].dropna().unique()
    if t not in _PLATFORM_LABELS
)
_seed_filter_from_query("flt_target", target_options)
target_sel = st.sidebar.multiselect(
    "Antigen target",
    options=target_options,
    default=target_options,
    key="flt_target",
)

# Overall status (multi-select)
status_options = sorted(df["OverallStatus"].dropna().unique().tolist())
_seed_filter_from_query("flt_status", status_options)
status_sel = st.sidebar.multiselect(
    "Overall status",
    options=status_options,
    default=status_options,
    key="flt_status",
)

# Product type (multi-select)
product_options = sorted(df["ProductType"].dropna().unique().tolist())
_seed_filter_from_query("flt_product", product_options)
product_sel = st.sidebar.multiselect(
    "Product type",
    options=product_options,
    default=product_options,
    key="flt_product",
)

# Cell therapy modality (multi-select)
modality_options = [m for m in _MODALITY_ORDER if m in set(df["Modality"])]
_seed_filter_from_query("flt_modality", modality_options)
modality_sel = st.sidebar.multiselect(
    "Cell therapy modality",
    options=modality_options,
    default=modality_options,
    key="flt_modality",
)

# Country (multi-select)
all_countries = set()
for cs in df["Countries"].dropna():
    for c in str(cs).split("|"):
        c = c.strip()
        if c:
            all_countries.add(c)
country_options = sorted(all_countries)
_seed_filter_from_query("flt_country", country_options)
country_sel = st.sidebar.multiselect(
    "Country",
    options=country_options,
    default=country_options,
    key="flt_country",
)

# Age group (Pediatric / Adult / Both / Unknown)
_AGE_ORDER = ["Adult", "Both", "Pediatric", "Unknown"]
if "AgeGroup" in df.columns:
    age_options = [a for a in _AGE_ORDER if a in set(df["AgeGroup"].dropna().astype(str))]
else:
    age_options = []
if age_options:
    _seed_filter_from_query("flt_age", age_options)
    age_sel = st.sidebar.multiselect(
        "Age group",
        options=age_options,
        default=age_options,
        key="flt_age",
    )
else:
    age_sel = []

# Sponsor type (Industry / Academic / Government / Other)
_SPONSOR_ORDER = ["Industry", "Academic", "Government", "Other"]
if "SponsorType" in df.columns:
    sponsor_options = [s for s in _SPONSOR_ORDER if s in set(df["SponsorType"].dropna().astype(str))]
else:
    sponsor_options = []
if sponsor_options:
    _seed_filter_from_query("flt_sponsor", sponsor_options)
    sponsor_sel = st.sidebar.multiselect(
        "Sponsor type",
        options=sponsor_options,
        default=sponsor_options,
        key="flt_sponsor",
    )
else:
    sponsor_sel = []

# Classification confidence (high / medium / low)
_CONFIDENCE_ORDER = ["high", "medium", "low"]
if "ClassificationConfidence" in df.columns:
    confidence_options = [
        c for c in _CONFIDENCE_ORDER
        if c in set(df["ClassificationConfidence"].dropna().astype(str))
    ]
else:
    confidence_options = []
if confidence_options:
    _seed_filter_from_query("flt_confidence", confidence_options)
    confidence_sel = st.sidebar.multiselect(
        "Classification confidence",
        options=confidence_options,
        default=confidence_options,
        help="high = explicit markers, medium = one fallback, low = Unclassified or unclear+default.",
        key="flt_confidence",
    )
else:
    confidence_sel = []

# Sync current filter state to URL so the view is shareable
_sync_opt_map = {
    "flt_disease": disease_options,
    "flt_design": design_options,
    "flt_phase": phase_options,
    "flt_target": target_options,
    "flt_status": status_options,
    "flt_product": product_options,
    "flt_modality": modality_options,
    "flt_country": country_options,
}
if age_options:
    _sync_opt_map["flt_age"] = age_options
if sponsor_options:
    _sync_opt_map["flt_sponsor"] = sponsor_options
if confidence_options:
    _sync_opt_map["flt_confidence"] = confidence_options
_sync_filters_to_query(_sync_opt_map)


# ---------------------------------------------------------------------------
# CSV provenance helper — adds a '#'-prefixed metadata header to exports.
# Readable via pandas: pd.read_csv(path, comment='#').
# ---------------------------------------------------------------------------
def _csv_with_provenance(
    df_export: pd.DataFrame,
    title: str,
    include_filters: bool = True,
) -> str:
    snap = (
        df["SnapshotDate"].iloc[0]
        if "SnapshotDate" in df.columns and not df.empty
        else date.today().isoformat()
    )
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = [
        f"# {title}",
        f"# Exported (UTC): {now_utc}",
    ]
    if st.session_state.get("pinned_snapshot"):
        lines.append(f"# Data source: ClinicalTrials.gov API v2 — pinned snapshot {snap}")
    else:
        lines.append(f"# Data source: ClinicalTrials.gov API v2 — live fetch (snapshot date {snap})")
    lines.append(f"# Source URL: {BASE_URL}")

    if include_filters:
        def _fmt(sel, opts) -> str:
            if not sel or set(sel) == set(opts):
                return "all"
            return "; ".join(str(s) for s in sel)
        lines += [
            f"# Filter — disease entity: {_fmt(disease_sel, disease_options)}",
            f"# Filter — trial design: {_fmt(design_sel, design_options)}",
            f"# Filter — phase: {_fmt(phase_sel, phase_options)}",
            f"# Filter — target category: {_fmt(target_sel, target_options)}",
            f"# Filter — overall status: {_fmt(status_sel, status_options)}",
            f"# Filter — product type: {_fmt(product_sel, product_options)}",
            f"# Filter — cell therapy modality: {_fmt(modality_sel, modality_options)}",
            f"# Filter — country: {_fmt(country_sel, country_options)}",
        ]
        if age_options:
            lines.append(f"# Filter — age group: {_fmt(age_sel, age_options)}")
        if sponsor_options:
            lines.append(f"# Filter — sponsor type: {_fmt(sponsor_sel, sponsor_options)}")
        if confidence_options:
            lines.append(f"# Filter — classification confidence: {_fmt(confidence_sel, confidence_options)}")

    lines += [
        f"# Rows: {len(df_export)}",
        "# Read with: pd.read_csv(path, comment='#')",
        "",
    ]
    return "\n".join(lines) + df_export.to_csv(index=False)


# Data quality / missing classifications
with st.sidebar.expander("Data quality / missing classifications", expanded=False):
    cols_to_check = ["DiseaseEntity", "Phase", "TargetCategory", "OverallStatus", "Countries"]
    rows = []
    ambiguous_tokens = ["other_or_unknown", "car_t_unspecified", "unclassified", "autoimmune_other"]

    for col in cols_to_check:
        s = df[col].astype("string")
        missing = int(df[col].isna().sum() + (s.str.strip() == "").sum())
        ambiguous = int(s.str.lower().fillna("").isin(ambiguous_tokens).sum())
        rows.append(
            {
                "Column": col,
                "Missing / empty": missing,
                "Ambiguous labels": ambiguous,
            }
        )

    quality_df = pd.DataFrame(rows)
    st.dataframe(quality_df, width='stretch', hide_index=True)
    n_llm = int(df["LLMOverride"].sum()) if "LLMOverride" in df.columns else 0
    if n_llm:
        st.caption(
            f"LLM-assisted: **{n_llm}** trial(s) reclassified via `llm_overrides.json`. "
            "Run `python validate.py` to expand coverage."
        )
    else:
        st.caption(
            "No LLM overrides active. Run `python validate.py` to classify ambiguous trials "
            "and write `llm_overrides.json`."
        )

# Apply filters
mask = pd.Series(True, index=df.index)

if disease_sel:
    _sel_set = set(disease_sel)
    mask &= df["DiseaseEntities"].fillna("").apply(
        lambda v: any(e.strip() in _sel_set for e in v.split("|"))
    )

if design_sel:
    mask &= df["TrialDesign"].isin(design_sel)

if phase_sel:
    selected_phase_norm = [k for k, v in PHASE_LABELS.items() if v in phase_sel]
    mask &= df["PhaseNormalized"].isin(selected_phase_norm)

if target_sel:
    # Platform-labeled trials (CAR-NK, CAR-Treg, etc.) are not antigen targets;
    # they always pass this filter and are separately controlled by the modality filter.
    mask &= df["TargetCategory"].isin(target_sel) | df["TargetCategory"].isin(_PLATFORM_LABELS)

if status_sel:
    mask &= df["OverallStatus"].isin(status_sel)

if product_sel:
    mask &= df["ProductType"].isin(product_sel)

if modality_sel:
    mask &= df["Modality"].isin(modality_sel)

if country_sel:
    country_pattern = "|".join([re.escape(c) for c in country_sel])
    mask &= df["Countries"].fillna("").str.contains(country_pattern, case=False, na=False, regex=True)

if age_sel and "AgeGroup" in df.columns:
    mask &= df["AgeGroup"].astype(str).isin(age_sel)

if sponsor_sel and "SponsorType" in df.columns:
    mask &= df["SponsorType"].astype(str).isin(sponsor_sel)

if confidence_sel and "ClassificationConfidence" in df.columns:
    mask &= df["ClassificationConfidence"].astype(str).isin(confidence_sel)

_df_filt = df[mask].copy()
df_filt = add_phase_columns(_df_filt)
df_filt["OverallStatus"] = df_filt["OverallStatus"].fillna("Unknown")
# NCTLink is baked in _post_process_trials; df_filt inherits the column.

# Open / recruiting sites across ALL countries, restricted to trials visible
# under the current filter.  Session-cached by NCT filter tuple: the slice
# rebuilds only when the filter actually changes, not on every pill click.
def _build_all_open_sites(sites: pd.DataFrame, nct_ids: pd.Series) -> pd.DataFrame:
    if sites.empty:
        return pd.DataFrame()
    key = hash(tuple(sorted(nct_ids.dropna().unique().tolist())))
    if st.session_state.get("_all_open_sites_key") == key:
        cached = st.session_state.get("_all_open_sites_df")
        if cached is not None:
            return cached
    _os = sites[sites["SiteStatus"].fillna("").str.upper().isin(OPEN_SITE_STATUSES)]
    _os = _os[_os["NCTId"].isin(nct_ids)].copy()
    _os["Country"] = _os["Country"].fillna("Unknown").astype(str).str.strip()
    _os = _os[_os["Country"] != ""]
    st.session_state["_all_open_sites_key"] = key
    st.session_state["_all_open_sites_df"] = _os
    return _os


all_open_sites = _build_all_open_sites(df_sites, df_filt["NCTId"])


def _country_study_view(country: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (open site rows for this country, per-trial study view)."""
    if all_open_sites.empty or not country:
        return pd.DataFrame(), pd.DataFrame()
    c_sites = all_open_sites[
        all_open_sites["Country"].str.lower() == country.lower()
    ].copy()
    if c_sites.empty:
        return c_sites, pd.DataFrame()
    c_trials = df_filt[df_filt["NCTId"].isin(c_sites["NCTId"])].copy()
    sv = (
        c_sites.groupby("NCTId", as_index=False)
        .agg(Cities=("City", uniq_join), SiteStatuses=("SiteStatus", uniq_join))
    )
    merge_cols = [c for c in [
        "NCTId", "BriefTitle", "DiseaseEntity", "TargetCategory", "ProductType",
        "Phase", "PhaseNormalized", "PhaseOrdered", "PhaseLabel",
        "OverallStatus", "LeadSponsor",
    ] if c in c_trials.columns]
    sv = sv.merge(
        c_trials[merge_cols].drop_duplicates(subset=["NCTId"]),
        on="NCTId", how="left",
    )
    sv["NCTLink"] = sv["NCTId"].apply(
        lambda x: f"https://clinicaltrials.gov/study/{x}" if pd.notna(x) else None
    )
    if "PhaseLabel" in sv.columns:
        sv["Phase"] = sv["PhaseLabel"].fillna(sv.get("Phase"))
    sort_cols = [c for c in ["PhaseOrdered", "DiseaseEntity", "NCTId"] if c in sv.columns]
    if sort_cols:
        sv = sv.sort_values(sort_cols, na_position="last")
    return c_sites, sv


def _countries_by_activity() -> list[str]:
    """Countries with at least one open / recruiting site, ranked by unique trials."""
    if all_open_sites.empty:
        return []
    order = (
        all_open_sites.groupby("Country")["NCTId"].nunique()
        .sort_values(ascending=False)
    )
    return order.index.tolist()


def _get_geo_sites() -> pd.DataFrame:
    """Open sites with usable lat/lon for the current NCT filter scope, deduped.

    Session-cached: the merge + drop-duplicates on ~10k rows only rebuilds when
    the set of NCT IDs actually changes, not on every widget rerun.
    """
    if all_open_sites.empty or "Latitude" not in all_open_sites.columns:
        return pd.DataFrame()
    nct_key = hash(tuple(sorted(all_open_sites["NCTId"].dropna().unique().tolist())))
    if st.session_state.get("_geo_sites_key") == nct_key:
        cached = st.session_state.get("_geo_sites_df")
        if cached is not None:
            return cached
    geo = all_open_sites.copy()
    geo["Latitude"] = pd.to_numeric(geo["Latitude"], errors="coerce")
    geo["Longitude"] = pd.to_numeric(geo["Longitude"], errors="coerce")
    geo = geo.dropna(subset=["Latitude", "Longitude"])
    geo = geo.drop_duplicates(
        subset=["NCTId", "Facility", "City", "Country", "Latitude", "Longitude"]
    )
    st.session_state["_geo_sites_key"] = nct_key
    st.session_state["_geo_sites_df"] = geo
    return geo


total_trials = len(df_filt)
recruiting_trials = int(df_filt["OverallStatus"].isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum())
_tc_for_top = df_filt.loc[~df_filt["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"].dropna()
top_target = _tc_for_top.value_counts().idxmax() if not _tc_for_top.empty else "—"
_enroll_known = pd.to_numeric(df_filt["EnrollmentCount"], errors="coerce").dropna()
total_enrolled = int(_enroll_known.sum()) if not _enroll_known.empty else 0
median_enrolled = int(_enroll_known.median()) if not _enroll_known.empty else 0

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    metric_card("Filtered trials", total_trials, "Trials matching current filters")
with m2:
    metric_card("Open / recruiting", recruiting_trials, "Recruiting or not yet recruiting")
with m3:
    metric_card("Total enrolled", f"{total_enrolled:,}", f"Across {len(_enroll_known)} trials with reported enrollment")
with m4:
    metric_card("Median enrollment", median_enrolled, "Patients per trial (reported trials only)")
with m5:
    metric_card("Top target", top_target, "Most common target category")

st.markdown(
    f"""
    <div class="small-note">
        {len(df)} total trials after processing. Current view shows {len(df_filt)} filtered trials.
    </div>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_geo, tab_data, tab_deepdive, tab_pub, tab_methods, tab_about = st.tabs(
    ["Overview", "Geography / Map", "Data", "Deep Dive", "Publication Figures", "Methods & Appendix", "About"]
)

with tab_overview:
    # -----------------------------------------------------------------
    # Hero — disease hierarchy sunburst (the signature visual).
    # Inner ring: disease family (the rheum analogue of Heme-onc / Solid-onc).
    # Middle ring: disease entity. Outer ring: antigen target.
    # Basket trials form their own branch to avoid double-counting.
    # -----------------------------------------------------------------
    if not df_filt.empty:
        st.subheader("Disease hierarchy at a glance")
        st.markdown(
            f'<p class="small-note" style="color:{THEME["muted"]}">Click a wedge to zoom in. '
            'Inner ring: disease family · middle ring: indication · outer ring: antigen target. '
            'Basket / multi-disease trials form their own branch.</p>',
            unsafe_allow_html=True,
        )

        _UNCLEAR_BUCKET_OV = "Undisclosed / unclear"

        def _ov_disease_l2(row) -> str:
            if row.get("TrialDesign") == "Basket/Multidisease":
                return "Basket/Multidisease"
            ent = row.get("DiseaseEntity") or "Unclassified"
            return str(ent)

        def _ov_target_l3(row) -> str:
            t = str(row.get("TargetCategory") or "Unknown")
            if t in ("CAR-T_unspecified", "Other_or_unknown", "Unknown"):
                return _UNCLEAR_BUCKET_OV
            return t

        _sb = df_filt.copy()
        _sb["_L1"] = _sb["DiseaseFamily"]
        _sb["_L2"] = _sb.apply(_ov_disease_l2, axis=1)
        _sb["_L3"] = _sb.apply(_ov_target_l3, axis=1)
        _sb_counts = _sb.groupby(["_L1", "_L2", "_L3"]).size().reset_index(name="Trials")

        # Simplify the outer ring: keep only the top-2 antigen targets per
        # disease; collapse the long tail into a single "Other targets" wedge.
        # Eliminates the sliver clutter when a disease has many tiny cohorts.
        _TOP_TARGETS_PER_DISEASE = 2
        _simplified = []
        for (_fam, _dis), _grp in _sb_counts.groupby(["_L1", "_L2"]):
            _grp = _grp.sort_values("Trials", ascending=False)
            _top = _grp.head(_TOP_TARGETS_PER_DISEASE)
            _tail = _grp.iloc[_TOP_TARGETS_PER_DISEASE:]
            _simplified.append(_top)
            if not _tail.empty:
                _simplified.append(pd.DataFrame([{
                    "_L1": _fam, "_L2": _dis, "_L3": "Other targets",
                    "Trials": int(_tail["Trials"].sum()),
                }]))
        _sb_counts = pd.concat(_simplified, ignore_index=True) if _simplified else _sb_counts

        _ids, _labels, _parents, _values, _colors = [], [], [], [], []
        for _fam, _fd in _sb_counts.groupby("_L1"):
            _fam_color = _FAMILY_COLORS.get(_fam, "#64748b")
            _ids.append(_fam); _labels.append(_fam); _parents.append("")
            _values.append(int(_fd["Trials"].sum()))
            _colors.append(_fam_color)
            for _dis, _dd in _fd.groupby("_L2"):
                _dis_id = f"{_fam}/{_dis}"
                _ids.append(_dis_id); _labels.append(_dis); _parents.append(_fam)
                _values.append(int(_dd["Trials"].sum()))
                _colors.append(_fam_color)
                for _, _row in _dd.iterrows():
                    _tg_id = f"{_fam}/{_dis}/{_row['_L3']}"
                    _ids.append(_tg_id); _labels.append(_row["_L3"]); _parents.append(_dis_id)
                    _values.append(int(_row["Trials"]))
                    _colors.append(_fam_color)

        _fig_sb = go.Figure(go.Sunburst(
            ids=_ids, labels=_labels, parents=_parents, values=_values,
            branchvalues="total",
            marker=dict(colors=_colors, line=dict(color="white", width=1.2)),
            hovertemplate="<b>%{label}</b><br>%{value} trials<br>%{percentRoot:.0%} of filtered total<extra></extra>",
            insidetextorientation="auto",
            maxdepth=3,
        ))
        _fig_sb.update_layout(
            height=560, margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family=FONT_FAMILY, size=12, color=THEME["text"]),
            uniformtext=dict(minsize=10, mode="hide"),
        )
        st.plotly_chart(_fig_sb, width='stretch')

        # Family headline row
        _fam_counts = _sb["_L1"].value_counts().rename_axis("Family").reset_index(name="Trials")
        _fam_counts = _fam_counts.set_index("Family").reindex(_FAMILY_ORDER).dropna().reset_index()
        _fam_counts["Trials"] = _fam_counts["Trials"].astype(int)
        if not _fam_counts.empty:
            _fc_cols = st.columns(min(len(_fam_counts), 5))
            _fc_total = int(_fam_counts["Trials"].sum())
            for _col, (_, _r) in zip(_fc_cols, _fam_counts.iterrows()):
                _pct = 100 * _r["Trials"] / _fc_total if _fc_total else 0
                _col.metric(_r["Family"], f"{int(_r['Trials'])} ({_pct:.0f}%)")

        st.markdown("---")

    # ── Snapshot diff vs previous snapshot ─────────────────────────────────
    try:
        from pipeline import list_snapshots as _list_snapshots, load_snapshot as _load_snap, snapshot_diff as _snap_diff
        _snap_dates = _list_snapshots()
    except Exception:
        _snap_dates = []

    _pinned_for_diff = st.session_state.get("pinned_snapshot")
    if len(_snap_dates) >= 2 and _pinned_for_diff:
        # Pinned snapshot is the current view; find the one that preceded it.
        try:
            idx = _snap_dates.index(_pinned_for_diff)
            prev_date = _snap_dates[idx + 1] if idx + 1 < len(_snap_dates) else None
        except (ValueError, NameError):
            prev_date = None

        if prev_date:
            with st.expander(f"Changes since previous snapshot ({prev_date} → {_pinned_for_diff})", expanded=False):
                try:
                    df_prev, _, _ = _load_snap(prev_date)
                    diff = _snap_diff(df, df_prev)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Trials added", diff["n_added"])
                    c2.metric("Trials removed", diff["n_removed"])
                    c3.metric("Status changes", len(diff["status_changed"]))
                    c4.metric(
                        "Classification changes",
                        len(diff["disease_changed"]) + len(diff["target_changed"]) + len(diff["product_changed"]),
                    )

                    _sections = [
                        ("Newly added trials", diff["added"]),
                        ("Removed trials (no longer in dataset)", diff["removed"]),
                        ("Status transitions", diff["status_changed"]),
                        ("Disease-entity reclassifications", diff["disease_changed"]),
                        ("Target reclassifications", diff["target_changed"]),
                        ("Product-type reclassifications", diff["product_changed"]),
                        ("Enrollment updates", diff["enrollment_changed"]),
                    ]
                    for label, d in _sections:
                        if isinstance(d, pd.DataFrame) and not d.empty:
                            st.markdown(f"**{label}** — {len(d)}")
                            st.dataframe(d, width='stretch', hide_index=True, height=min(220, 40 + 28 * len(d)))
                except Exception as e:
                    st.caption(f"Snapshot diff unavailable: {type(e).__name__}: {e}")

    # -----------------------------------------------------------------
    # Landscape at a glance — four panels, all coloured by disease family
    # so a reader can cross-reference the sunburst above at a glance.
    # -----------------------------------------------------------------
    if not df_filt.empty:
        st.subheader("Landscape at a glance")
        st.markdown(
            f'<p class="small-note" style="color:{THEME["muted"]}">All four panels share the disease-family colour key shown below.</p>',
            unsafe_allow_html=True,
        )

        _swatch_html = (
            '<div style="display:flex;flex-wrap:wrap;gap:14px 22px;align-items:center;'
            'padding:6px 0 14px 0;font-family:Inter,-apple-system,sans-serif;'
            'font-size:12px;color:#0b1220;">'
        )
        for _fam in _FAMILY_ORDER:
            _c = _FAMILY_COLORS.get(_fam, "#64748b")
            _swatch_html += (
                f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'background:{_c};border-radius:2px;"></span>{_fam}</span>'
            )
        _swatch_html += "</div>"
        st.markdown(_swatch_html, unsafe_allow_html=True)

        _PANEL_HEIGHT = PANEL_HEIGHT  # alias local var for block clarity

        _ov_a, _ov_b = st.columns(2)

        # Panel 1: Trials by disease (stacked by family) — basket trials collapsed to one row
        _ov_exp_rows = []
        for _, _r in df_filt.iterrows():
            _ents = [e.strip() for e in str(_r.get("DiseaseEntities", "")).split("|") if e.strip()]
            if not _ents:
                _ents = [str(_r.get("DiseaseEntity", "Unclassified"))]
            for _e in _ents:
                _rr = _r.to_dict(); _rr["_Disease"] = _e
                _ov_exp_rows.append(_rr)
        _dd_ov = pd.DataFrame(_ov_exp_rows) if _ov_exp_rows else pd.DataFrame()
        if not _dd_ov.empty:
            _dd_ov["_DisplayDisease"] = _dd_ov.apply(
                lambda r: "Basket/Multidisease" if r.get("TrialDesign") == "Basket/Multidisease" else r["_Disease"],
                axis=1,
            )
            _dd_ov["_Family"] = _dd_ov.apply(
                lambda r: _disease_family(r["_Disease"], r.get("TrialDesign")), axis=1
            )
            _dd_dedup = _dd_ov.drop_duplicates(subset=["NCTId"])
            _ent_counts = (
                _dd_dedup.groupby(["_DisplayDisease", "_Family"]).size()
                .reset_index(name="Trials").sort_values("Trials", ascending=True)
            )
            with _ov_a:
                st.markdown("**Trials by disease**")
                _fig_ov1 = px.bar(
                    _ent_counts, x="Trials", y="_DisplayDisease", color="_Family",
                    orientation="h",
                    color_discrete_map=_FAMILY_COLORS,
                    category_orders={"_Family": _FAMILY_ORDER},
                    labels={"_DisplayDisease": "Disease", "_Family": "Family"},
                    template="plotly_white",
                    height=_PANEL_HEIGHT,
                )
                _fig_ov1.update_traces(marker_line_width=0, opacity=1)
                _fig_ov1.update_layout(
                    margin=dict(l=140, r=24, t=12, b=56),
                    showlegend=False,
                    yaxis_title=None, xaxis_title="Number of trials",
                    font=dict(family=FONT_FAMILY, size=11, color=THEME["text"]),
                )
                st.plotly_chart(_fig_ov1, width='stretch')

        # Panel 2: Antigen target, colored stack by family
        _tg_ov = df_filt.copy()
        _tg_ov["_Target"] = _tg_ov.apply(_ov_target_l3, axis=1)
        _tg_ov = _tg_ov[~_tg_ov["TargetCategory"].isin(_PLATFORM_LABELS)]
        _tg_counts = (
            _tg_ov.groupby(["_Target", "DiseaseFamily"]).size().reset_index(name="Trials")
        )
        _tg_order_ov = (
            _tg_counts.groupby("_Target")["Trials"].sum().sort_values(ascending=True).index.tolist()
        )
        with _ov_b:
            st.markdown("**Trials by antigen target**")
            if _tg_counts.empty:
                st.info("No antigen-target data.")
            else:
                _fig_ov2 = px.bar(
                    _tg_counts, x="Trials", y="_Target", color="DiseaseFamily",
                    orientation="h",
                    color_discrete_map=_FAMILY_COLORS,
                    category_orders={"_Target": _tg_order_ov, "DiseaseFamily": _FAMILY_ORDER},
                    labels={"_Target": "Target", "DiseaseFamily": "Family"},
                    template="plotly_white",
                    height=_PANEL_HEIGHT,
                )
                _fig_ov2.update_traces(marker_line_width=0, opacity=1)
                _fig_ov2.update_layout(
                    barmode="stack",
                    margin=dict(l=140, r=24, t=12, b=56),
                    showlegend=False,
                    yaxis_title=None, xaxis_title="Number of trials",
                    font=dict(family=FONT_FAMILY, size=11, color=THEME["text"]),
                )
                st.plotly_chart(_fig_ov2, width='stretch')

        _ov_c, _ov_d = st.columns(2)

        # Panel 3: Phase, stacked by family
        _ph_ov = (
            df_filt.assign(PhaseLbl=df_filt["PhaseLabel"].fillna("Unknown"))
            .groupby(["PhaseLbl", "DiseaseFamily"]).size().reset_index(name="Trials")
        )
        _phase_display_order = [PHASE_LABELS[p] for p in PHASE_ORDER]
        with _ov_c:
            st.markdown("**Trials by phase**")
            _fig_ov3 = px.bar(
                _ph_ov, x="PhaseLbl", y="Trials", color="DiseaseFamily",
                color_discrete_map=_FAMILY_COLORS,
                category_orders={"PhaseLbl": _phase_display_order, "DiseaseFamily": _FAMILY_ORDER},
                template="plotly_white",
                labels={"PhaseLbl": "Phase", "DiseaseFamily": "Family"},
                height=_PANEL_HEIGHT,
            )
            _fig_ov3.update_traces(marker_line_width=0, opacity=1)
            _fig_ov3.update_layout(
                barmode="stack",
                margin=dict(l=64, r=24, t=12, b=56),
                showlegend=False,
                xaxis_title="Phase", yaxis_title="Number of trials",
                font=dict(family=FONT_FAMILY, size=11, color=THEME["text"]),
            )
            st.plotly_chart(_fig_ov3, width='stretch')

        # Panel 4: Trials by start year, stacked area by family
        _yr_ov = df_filt.dropna(subset=["StartYear"]).copy()
        with _ov_d:
            st.markdown("**Trials by start year**")
            if _yr_ov.empty:
                st.info("No start-year data.")
            else:
                _yr_ov["StartYear"] = _yr_ov["StartYear"].astype(int)
                _yr_counts = (
                    _yr_ov.groupby(["StartYear", "DiseaseFamily"]).size().reset_index(name="Trials")
                )
                _fig_ov4 = px.area(
                    _yr_counts, x="StartYear", y="Trials", color="DiseaseFamily",
                    color_discrete_map=_FAMILY_COLORS,
                    category_orders={"DiseaseFamily": _FAMILY_ORDER},
                    template="plotly_white",
                    labels={"StartYear": "Start year", "DiseaseFamily": "Family"},
                    height=_PANEL_HEIGHT,
                )
                _fig_ov4.update_traces(line=dict(width=0.5), opacity=0.95)
                _fig_ov4.update_layout(
                    margin=dict(l=64, r=24, t=12, b=56),
                    showlegend=False,
                    xaxis=dict(tickmode="linear", dtick=1, tickformat="d"),
                    xaxis_title="Start year", yaxis_title="Number of trials",
                    font=dict(family=FONT_FAMILY, size=11, color=THEME["text"]),
                )
                st.plotly_chart(_fig_ov4, width='stretch')

    # -----------------------------------------------------------------
    # PRISMA — now a collapsed expander at the bottom. Full narrative
    # and methodological detail live in the Methods & Appendix tab.
    # -----------------------------------------------------------------
    if prisma_counts:
        with st.expander("Study selection (PRISMA flow)", expanded=False):
            st.caption("Summary PRISMA-style flow of records from ClinicalTrials.gov API to the final analysis set. "
                       "Full methods in the **Methods & Appendix** tab.")
            prisma_rows = [
                {"Step": "Records identified via ClinicalTrials.gov API", "n": prisma_counts.get("n_fetched", "—"), "Note": ""},
                {"Step": "Duplicate records removed", "n": prisma_counts.get("n_duplicates_removed", "—"), "Note": "Same NCT ID"},
                {"Step": "Records screened", "n": prisma_counts.get("n_after_dedup", "—"), "Note": ""},
                {"Step": "Excluded: pre-specified NCT IDs", "n": prisma_counts.get("n_hard_excluded", "—"), "Note": "Manually curated exclusion list"},
                {"Step": "Excluded: LLM-curation flagged", "n": prisma_counts.get("n_llm_excluded", 0), "Note": "LLM validation (high/medium confidence, exclude=true)"},
                {"Step": "Excluded: oncology / haematologic malignancy indications", "n": prisma_counts.get("n_indication_excluded", "—"), "Note": "Keyword-based exclusion"},
                {"Step": "Studies included in analysis", "n": prisma_counts.get("n_included", "—"), "Note": "Final dataset"},
            ]
            prisma_df = pd.DataFrame(prisma_rows)
            st.dataframe(
                prisma_df,
                width='stretch',
                hide_index=True,
                column_config={
                    "Step": st.column_config.TextColumn("Step", width="large"),
                    "n": st.column_config.NumberColumn("n", width="small"),
                    "Note": st.column_config.TextColumn("Note", width="medium"),
                },
            )

with tab_geo:
    st.subheader("Global studies by country")

    countries_long = split_pipe_values(df_filt["Countries"])
    if countries_long:
        country_df = pd.DataFrame({"Country": countries_long})
        country_counts = (
            country_df["Country"]
            .value_counts()
            .rename_axis("Country")
            .reset_index(name="Count")
        )

        country_counts = _attach_iso3(country_counts)

        # Prep outside the fragment: geo_sites is session-cached upstream.
        # Fragment captures country_counts + geo_sites via closure; only the
        # map + caption rerun when layer pills toggle.
        geo_sites = _get_geo_sites()

        @st.fragment
        def _render_world_map(country_counts: pd.DataFrame, geo_sites: pd.DataFrame) -> None:
            _layers = st.pills(
                "Map layers",
                options=["Country counts", "Open sites"],
                default=["Country counts", "Open sites"],
                selection_mode="multi",
                label_visibility="collapsed",
                key="geo_layers_world",
            ) or []

            fig_world = go.Figure()
            if "Country counts" in _layers:
                fig_world.add_trace(
                    go.Choropleth(
                        locations=country_counts["Iso3"],
                        locationmode="ISO-3",
                        z=country_counts["Count"],
                        text=country_counts["Country"],
                        hovertemplate="<b>%{text}</b><br>%{z} trials<extra></extra>",
                        colorscale=[
                            [0.00, "#dbeafe"],
                            [0.30, "#93c5fd"],
                            [0.55, "#3b82f6"],
                            [0.75, "#1d4ed8"],
                            [1.00, "#1e3a8a"],
                        ],
                        colorbar=dict(title="No. of trials", thickness=12, len=0.6),
                        marker_line_color="rgba(255,255,255,0.6)",
                        marker_line_width=0.4,
                    )
                )
            if "Open sites" in _layers and not geo_sites.empty:
                _site_label = (
                    geo_sites["Facility"].fillna("").astype(str)
                    + " · " + geo_sites["City"].fillna("").astype(str)
                    + ", " + geo_sites["Country"].fillna("").astype(str)
                    + "<br>" + geo_sites["NCTId"].fillna("").astype(str)
                )
                fig_world.add_trace(
                    go.Scattergeo(
                        lon=geo_sites["Longitude"],
                        lat=geo_sites["Latitude"],
                        text=_site_label,
                        hovertemplate="%{text}<extra></extra>",
                        mode="markers",
                        marker=dict(
                            size=5.5,
                            color="#d97706",  # amber-600 — contrasts with blue choropleth
                            opacity=0.78,
                            line=dict(width=0.3, color="#ffffff"),
                        ),
                        name="Open site",
                        showlegend=False,
                    )
                )
            fig_world.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=THEME["text"]),
                height=480,
                geo=dict(
                    bgcolor="rgba(0,0,0,0)",
                    lakecolor="#ddeeff",
                    landcolor="#e9ecef",
                    showframe=False,
                    showcoastlines=False,
                    showcountries=True,
                    countrycolor="rgba(0,0,0,0.12)",
                    projection_type="natural earth",
                    scope="world",
                    lataxis=dict(range=[-58, 80]),
                    lonaxis=dict(range=[-175, 190]),
                ),
            )
            st.plotly_chart(fig_world, width='stretch')
            if "Open sites" in _layers and not geo_sites.empty:
                st.caption(
                    f"{len(geo_sites):,} open / recruiting site locations plotted. "
                    "Choropleth counts unique trials per country; dots mark individual sites."
                )

        _render_world_map(country_counts, geo_sites)

        c1, c2 = st.columns([1.15, 0.85])
        with c1:
            st.markdown("**Country counts**")
            st.dataframe(country_counts[["Country", "Count"]], width='stretch',
                         height=320, hide_index=True)
        with c2:
            st.markdown("**Top countries**")
            st.plotly_chart(
                make_bar(country_counts.head(12), "Country", "Count", height=320, color=THEME["primary"]),
                width='stretch',
            )
    else:
        st.info("No country information available for the current filter selection.")

    st.subheader("Sites by city")

    _countries_avail = _countries_by_activity()
    if not _countries_avail:
        st.info("No open or recruiting study sites in the current filter selection.")
    else:
        _default = "Germany" if "Germany" in _countries_avail else _countries_avail[0]
        _prev = st.session_state.get("sites_country", _default)
        _default_idx = _countries_avail.index(_prev) if _prev in _countries_avail else 0
        selected_country = st.selectbox(
            "Country",
            options=_countries_avail,
            index=_default_idx,
            key="sites_country",
            help="Pick any country with at least one open or recruiting site in the current filter.",
        )

        country_open_sites, country_study_view = _country_study_view(selected_country)

        if country_open_sites.empty:
            st.info(f"No open or recruiting sites found in {selected_country}.")
        else:
            country_city_counts = (
                country_open_sites["City"]
                .fillna("Unknown")
                .value_counts()
                .rename_axis("City")
                .reset_index(name="OpenSiteCount")
                .sort_values(["OpenSiteCount", "City"], ascending=[False, True], na_position="last")
                .reset_index(drop=True)
            )

            g1, g2, g3 = st.columns(3)
            with g1:
                metric_card(f"{selected_country} site rows", len(country_open_sites),
                            f"Recruiting / active {selected_country} site rows")
            with g2:
                metric_card("Cities", country_open_sites["City"].dropna().nunique(),
                            "Cities with open sites")
            with g3:
                metric_card(
                    "Unique trials",
                    country_study_view["NCTId"].nunique() if not country_study_view.empty else 0,
                    f"NCT IDs with at least one open {selected_country} site",
                )

            _country_geo = _get_geo_sites()
            if not _country_geo.empty:
                _country_geo = _country_geo[
                    _country_geo["Country"].str.lower() == selected_country.lower()
                ]

            _panel_h = min(360, max(220, len(country_city_counts) * 22 + 60))

            c1, c2 = st.columns([0.6, 0.4])
            with c1:
                st.markdown(f"**{selected_country} site map**")
                if _country_geo.empty:
                    st.caption("No geocoded sites for this country yet.")
                else:
                    # Aggregate to city level: one blob per city, positioned at
                    # the mean lat/lon of its facilities, sized by unique-trial
                    # count. sqrt scaling so hub cities don't drown the long tail.
                    _hub = (
                        _country_geo.assign(
                            CityKey=_country_geo["City"].fillna("Unknown").astype(str)
                        )
                        .groupby("CityKey", dropna=False)
                        .agg(
                            Latitude=("Latitude", "mean"),
                            Longitude=("Longitude", "mean"),
                            Trials=("NCTId", "nunique"),
                            Sites=("Facility", "nunique"),
                        )
                        .reset_index()
                        .rename(columns={"CityKey": "City"})
                    )
                    _hub["Size"] = 8 + 6 * np.sqrt(_hub["Trials"].clip(lower=1))
                    _lab = (
                        "<b>" + _hub["City"].astype(str) + "</b>"
                        + "<br>" + _hub["Trials"].astype(str) + " trial(s) · "
                        + _hub["Sites"].astype(str) + " site(s)"
                    )
                    fig_country_geo = go.Figure(
                        go.Scattergeo(
                            lon=_hub["Longitude"],
                            lat=_hub["Latitude"],
                            text=_lab,
                            hovertemplate="%{text}<extra></extra>",
                            mode="markers",
                            marker=dict(
                                size=_hub["Size"],
                                color="#d97706",  # amber-600 — contrasts with blue choropleth
                                opacity=0.72,
                                line=dict(width=0.5, color="#ffffff"),
                            ),
                        )
                    )
                    fig_country_geo.update_layout(
                        margin=dict(l=0, r=0, t=4, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=_panel_h,
                        geo=dict(
                            bgcolor="rgba(0,0,0,0)",
                            lakecolor="#ddeeff",
                            landcolor="#e9ecef",
                            showframe=False,
                            showcoastlines=False,
                            showcountries=True,
                            countrycolor="rgba(0,0,0,0.2)",
                            projection_type="natural earth",
                            fitbounds="locations",
                        ),
                    )
                    st.plotly_chart(fig_country_geo, width='stretch')
                    _max_trials = int(_hub["Trials"].max()) if not _hub.empty else 0
                    _top_city = (
                        _hub.sort_values("Trials", ascending=False).iloc[0]["City"]
                        if not _hub.empty else ""
                    )
                    if _max_trials > 1:
                        st.caption(
                            f"Dot size ∝ √(trials per city) · "
                            f"{_top_city} leads with {_max_trials} trials."
                        )
            with c2:
                st.markdown("**Open sites by city**")
                st.plotly_chart(
                    make_bar(country_city_counts, "City", "OpenSiteCount",
                             height=_panel_h,
                             color=THEME["primary"]),
                    width='stretch',
                )

            st.markdown(f"**{selected_country} city table**")
            city_event = st.dataframe(
                country_city_counts,
                width='stretch',
                height=min(300, max(180, len(country_city_counts) * 20 + 48)),
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"city_table_{selected_country}",
            )

            if city_event and city_event.selection.rows:
                selected_idx = city_event.selection.rows[0]
                selected_city = country_city_counts.iloc[selected_idx]["City"]

                st.markdown(f"### Trials with open {selected_country} sites in {selected_city}")

                city_nct_ids = (
                    country_open_sites.loc[
                        country_open_sites["City"].fillna("Unknown") == selected_city,
                        "NCTId",
                    ]
                    .dropna()
                    .unique()
                )

                city_trial_view = country_study_view[
                    country_study_view["NCTId"].isin(city_nct_ids)
                ].copy()

                if city_trial_view.empty:
                    st.info(f"No study rows found for {selected_city}.")
                else:
                    _cols = [c for c in [
                        "NCTId", "NCTLink", "BriefTitle", "DiseaseEntity",
                        "TargetCategory", "ProductType", "Phase", "OverallStatus",
                        "LeadSponsor", "Cities", "SiteStatuses",
                    ] if c in city_trial_view.columns]
                    st.dataframe(
                        city_trial_view[_cols],
                        width='stretch',
                        height=320,
                        hide_index=True,
                        column_config={
                            "NCTId": st.column_config.TextColumn("NCT ID"),
                            "NCTLink": st.column_config.LinkColumn("Trial link", display_text="Open trial"),
                            "BriefTitle": st.column_config.TextColumn("Title", width="large"),
                            "DiseaseEntity": st.column_config.TextColumn("Disease"),
                            "TargetCategory": st.column_config.TextColumn("Target"),
                            "ProductType": st.column_config.TextColumn("Product"),
                            "Phase": st.column_config.TextColumn("Phase"),
                            "OverallStatus": st.column_config.TextColumn("Status"),
                            "LeadSponsor": st.column_config.TextColumn("Lead sponsor", width="medium"),
                            "Cities": st.column_config.TextColumn(f"{selected_country} cities", width="large"),
                            "SiteStatuses": st.column_config.TextColumn("Site status", width="medium"),
                        },
                    )
            else:
                st.caption("Select a city row in the table to open the related trial list below.")

with tab_data:
    st.subheader("Trial table")

    # Search + country zoom side-by-side.  Country zoom filters the main
    # table to trials with at least one open/recruiting site in the chosen
    # country, and swaps the "Countries" column for that country's Cities
    # and SiteStatuses — eliminating the need for a second "Studies active
    # in …" table lower on the page.
    _ALL_COUNTRIES_LABEL = "All countries"
    _zoom_countries = _countries_by_activity()
    _country_options = [_ALL_COUNTRIES_LABEL] + _zoom_countries

    _prev_zoom = st.session_state.get("data_country_zoom", _ALL_COUNTRIES_LABEL)
    if _prev_zoom not in _country_options:
        _prev_zoom = _ALL_COUNTRIES_LABEL
    _zoom_idx = _country_options.index(_prev_zoom)

    _c_search, _c_country = st.columns([0.65, 0.35])
    with _c_search:
        search_q = st.text_input(
            "Search",
            value=st.session_state.get("data_search", ""),
            key="data_search",
            placeholder="NCT ID, title, sponsor, condition, intervention (e.g. lupus, KYV-101, Cabaletta)",
            help="Case-insensitive substring match across NCT ID / title / sponsor / conditions / interventions.",
        )
    with _c_country:
        _zoom_country = st.selectbox(
            "Zoom into country",
            options=_country_options,
            index=_zoom_idx,
            key="data_country_zoom",
            help="Filter the trial table to studies with an open or recruiting site in a specific country. "
                 "Shows that country's cities and site statuses inline.",
        )
    _zoom_active = _zoom_country != _ALL_COUNTRIES_LABEL

    show_cols = [
        "NCTId",
        "NCTLink",
        "BriefTitle",
        "DiseaseEntities",
        "TrialDesign",
        "TargetCategory",
        "ProductType",
        "ClassificationConfidence",
        "ProductName",
        "AgeGroup",
        "Phase",
        "OverallStatus",
        "StartYear",
        "Countries",
        "LeadSponsor",
        "SponsorType",
    ]
    if _zoom_active:
        # Swap the aggregate "Countries" column for per-country detail.
        _ci = show_cols.index("Countries")
        show_cols = show_cols[:_ci] + ["Cities", "SiteStatuses"] + show_cols[_ci + 1:]

    table_df = df_filt.sort_values(["PhaseOrdered", "DiseaseEntity", "NCTId"], ascending=[True, True, True]).copy()
    table_df["Phase"] = table_df["PhaseLabel"]
    table_df["OverallStatus"] = table_df["OverallStatus"].map(STATUS_DISPLAY).fillna(table_df["OverallStatus"])

    if _zoom_active:
        _country_sites, _country_sv = _country_study_view(_zoom_country)
        if _country_sv.empty:
            table_df = table_df.iloc[0:0]
        else:
            _nct_in_country = set(_country_sv["NCTId"])
            table_df = table_df[table_df["NCTId"].isin(_nct_in_country)].copy()
            _merge_bits = _country_sv[["NCTId", "Cities", "SiteStatuses"]].drop_duplicates("NCTId")
            table_df = table_df.merge(_merge_bits, on="NCTId", how="left")
        st.caption(
            f"Zoomed to **{_zoom_country}** · {len(table_df)} trial"
            f"{'s' if len(table_df) != 1 else ''} with open or recruiting sites there."
        )

    show_cols = [c for c in show_cols if c in table_df.columns or c in ("NCTLink",)]

    if search_q:
        q = search_q.lower().strip()
        search_cols = ["NCTId", "BriefTitle", "LeadSponsor", "Conditions", "Interventions"]
        mask = pd.Series(False, index=table_df.index)
        for c in search_cols:
            if c in table_df.columns:
                mask |= table_df[c].fillna("").astype(str).str.lower().str.contains(q, regex=False)
        table_df = table_df[mask]
        st.caption(f"Search '{search_q}' · {len(table_df)} of {len(df_filt)} filtered trials match")

    st.caption("Click any row to open the full trial record below.")
    _table_event = st.dataframe(
        table_df[show_cols],
        width='stretch',
        height=460,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="data_table_sel",
        column_config={
            "NCTId": st.column_config.TextColumn("NCT ID"),
            "NCTLink": st.column_config.LinkColumn("Trial link", display_text="Open trial"),
            "BriefTitle": st.column_config.TextColumn("Title", width="large"),
            "DiseaseEntities": st.column_config.TextColumn("Disease(s)", width="medium"),
            "TrialDesign": st.column_config.TextColumn("Trial design", width="small"),
            "TargetCategory": st.column_config.TextColumn("Target"),
            "ProductType": st.column_config.TextColumn("Product"),
            "ClassificationConfidence": st.column_config.TextColumn(
                "Confidence",
                help="high = explicit markers or LLM override. medium = one of {target unclear, default/weak product signal}. low = both unclear, or disease Unclassified.",
            ),
            "ProductName": st.column_config.TextColumn("Named product", width="small"),
            "AgeGroup": st.column_config.TextColumn("Age", width="small"),
            "Phase": st.column_config.TextColumn("Phase"),
            "OverallStatus": st.column_config.TextColumn("Status"),
            "StartYear": st.column_config.NumberColumn("Start year", format="%d"),
            "Countries": st.column_config.TextColumn("Countries", width="large"),
            "Cities": st.column_config.TextColumn(
                f"{_zoom_country} cities" if _zoom_active else "Cities", width="large",
            ),
            "SiteStatuses": st.column_config.TextColumn("Site status", width="medium"),
            "LeadSponsor": st.column_config.TextColumn("Lead sponsor", width="medium"),
            "SponsorType": st.column_config.TextColumn("Sponsor type", width="small"),
        },
    )

    # ── Trial detail drilldown (row-click driven) ──────────────────────────
    if not table_df.empty:
        _selected_rows = (
            _table_event.selection.rows
            if _table_event and hasattr(_table_event, "selection") else []
        )
        if _selected_rows:
            rec = table_df.iloc[_selected_rows[0]]
            sel_nct = rec["NCTId"]
            with st.expander(f"{sel_nct} — {rec.get('BriefTitle', '')}", expanded=True):
                _link = rec.get("NCTLink") or f"https://clinicaltrials.gov/study/{sel_nct}"
                st.markdown(f"**[Open on ClinicalTrials.gov]({_link})**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**Disease:** {rec.get('DiseaseEntities', '')}")
                    st.markdown(f"**Trial design:** {rec.get('TrialDesign', '')}")
                    st.markdown(f"**Phase:** {rec.get('Phase', '')}")
                    st.markdown(f"**Status:** {rec.get('OverallStatus', '')}")
                with c2:
                    st.markdown(f"**Target:** {rec.get('TargetCategory', '')} *(via {rec.get('TargetSource', '—')})*")
                    st.markdown(f"**Product:** {rec.get('ProductType', '')} *(via {rec.get('ProductTypeSource', '—')})*")
                    st.markdown(f"**Confidence:** {rec.get('ClassificationConfidence', '—')}")
                    if rec.get("ProductName"):
                        st.markdown(f"**Named product:** {rec.get('ProductName')}")
                    if bool(rec.get("LLMOverride", False)):
                        st.markdown("**LLM override applied**")
                with c3:
                    st.markdown(f"**Sponsor:** {rec.get('LeadSponsor', '')}")
                    st.markdown(f"**Sponsor type:** {rec.get('SponsorType', '')}")
                    _enr = rec.get("EnrollmentCount")
                    if pd.notna(_enr):
                        st.markdown(f"**Enrollment:** {int(_enr)}")
                    st.markdown(f"**Countries:** {rec.get('Countries', '') or '—'}")
                    st.markdown(f"**Age group:** {rec.get('AgeGroup', '—')}")
                if rec.get("PrimaryEndpoints"):
                    st.markdown("**Primary endpoints:**")
                    st.write(str(rec["PrimaryEndpoints"]).replace("|", "; "))

                if rec.get("Conditions"):
                    st.markdown("**Conditions:**")
                    st.write(str(rec["Conditions"]).replace("|", ", "))
                if rec.get("Interventions"):
                    st.markdown("**Interventions:**")
                    st.write(str(rec["Interventions"]).replace("|", ", "))
                if rec.get("BriefSummary"):
                    st.markdown("**Brief summary:**")
                    st.write(str(rec["BriefSummary"]))
        else:
            st.info("Select a row in the table above to see the full trial record and classification reasoning.")

    # Build a short tag that describes the current view state — used in
    # both the button label and the filename so downloads are self-
    # documenting when saved to disk.
    _view_bits = []
    if _zoom_active:
        _view_bits.append(_zoom_country.lower().replace(" ", "_"))
    if search_q:
        _view_bits.append("search_" + search_q.lower().strip().replace(" ", "_")[:32])
    _view_suffix = "_" + "_".join(_view_bits) if _view_bits else ""
    _view_label = (
        f"Download current view ({len(table_df)} trial"
        f"{'s' if len(table_df) != 1 else ''}) as CSV"
    )

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            label=_view_label,
            data=_csv_with_provenance(table_df[show_cols], "Current trial table view"),
            file_name=f"car_t_rheumatology_view{_view_suffix}.csv",
            mime="text/csv",
            help="Exports exactly the rows and columns visible in the table above "
                 "(after country zoom and search).",
            disabled=table_df.empty,
        )
    with d2:
        st.download_button(
            label="Download all filtered trials as CSV",
            data=_csv_with_provenance(df_filt, "Filtered trial list"),
            file_name="car_t_rheumatology_trials_filtered.csv",
            mime="text/csv",
        )
    with d3:
        if not df_sites.empty:
            st.download_button(
                label="Download site-level data as CSV",
                data=_csv_with_provenance(df_sites, "Site-level data"),
                file_name="car_t_rheumatology_sites.csv",
                mime="text/csv",
            )


# ---------------------------------------------------------------------------
# TAB: Publication Figures
# ---------------------------------------------------------------------------

# Unified visualization palette — coordinated, scientific-grade
NEJM = ["#1d4ed8", "#dc2626", "#d97706", "#059669", "#475569", "#0891b2", "#0d9488", "#64748b"]
NEJM_BLUE    = "#1d4ed8"   # blue-700 (primary)
NEJM_RED     = "#dc2626"   # red-600
NEJM_AMBER   = "#d97706"   # amber-600
NEJM_GREEN   = "#059669"   # emerald-600
NEJM_PURPLE  = "#475569"   # slate-600 — non-purple replacement (legacy name kept)

_MODALITY_COLORS.update({
    "Auto CAR-T":      NEJM_BLUE,
    "Allo CAR-T":      "#0891b2",   # cyan-600
    "CAR-T (unclear)": "#a1a1aa",   # zinc-400
    "CAR-γδ T":        "#0d9488",   # teal-600
    "CAR-NK":          NEJM_GREEN,
    "CAR-Treg":        NEJM_PURPLE,
    "CAAR-T":          NEJM_AMBER,
    "In vivo CAR":     NEJM_RED,
})

_AX_COLOR  = "#1a1a1a"   # axis lines + ticks — near-black, publication weight
_GRID_CLR  = "#c8c8c8"   # grid lines — visible but not competing with data
_TICK_SZ   = 11           # tick label font size
_TITLE_SZ  = 14           # figure title font size
_LAB_SZ    = 12           # axis label font size

PUB_FONT = dict(family="Arial, Helvetica, sans-serif", size=_TICK_SZ, color=_AX_COLOR)

# Base: only the keys shared by ALL publication figures (no axes, no margin)
PUB_BASE = dict(
    template="plotly_white",
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=PUB_FONT,
)

def _pub_title(text: str, pad_b: int = 10) -> dict:
    """Legacy in-chart title helper. Retained for back-compat; new figures
    should use _pub_header() above the chart instead."""
    return dict(text=text, x=0, pad=dict(b=pad_b),
                font=dict(size=_TITLE_SZ, color="#000000", family="Arial, Helvetica, sans-serif"))


def _pub_header(figure_num: str, title: str, subtitle: str | None = None) -> None:
    """Render a journal-style figure header (eyebrow + title + optional sub)
    above a publication chart. Replaces st.subheader + Plotly title."""
    sub_html = f'<div class="pub-fig-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="pub-fig-header">'
        f'<div class="pub-fig-eyebrow">Figure {figure_num}</div>'
        f'<div class="pub-fig-title">{title}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _pub_caption(n: int, extra: str | None = None) -> None:
    """Render a small muted caption beneath a publication figure, noting the
    number of filtered trials and pointing to the CSV provenance header."""
    extra_html = f" {extra}" if extra else ""
    st.markdown(
        f'<div class="pub-fig-caption">n = {n:,} trials in the filtered set. '
        f'Full filter state and data source recorded in the CSV export header.'
        f'{extra_html}</div>',
        unsafe_allow_html=True,
    )

_V_XAXIS = dict(
    showline=True, linewidth=1.5, linecolor=_AX_COLOR, mirror=False,
    showgrid=False, ticks="outside", ticklen=6, tickwidth=1.2,
    title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
)
_V_YAXIS = dict(
    showline=True, linewidth=1.5, linecolor=_AX_COLOR, mirror=False,
    showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
    ticks="outside", ticklen=6, tickwidth=1.2,
    title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
    zeroline=False,
)

# Full layout for standard vertical bar / line charts (titles rendered by _pub_header)
PUB_LAYOUT = dict(
    **PUB_BASE,
    margin=dict(l=72, r=36, t=24, b=72),
    xaxis=_V_XAXIS,
    yaxis=_V_YAXIS,
)

# Shared axis settings for horizontal bar charts
_H_XAXIS = dict(
    showline=True, linewidth=1.5, linecolor=_AX_COLOR,
    showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
    ticks="outside", ticklen=6, tickwidth=1.2,
    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
    title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
    zeroline=False,
)
_H_YAXIS = dict(
    showline=True, linewidth=1.5, linecolor=_AX_COLOR,
    showgrid=False,
    ticks="outside", ticklen=4, tickwidth=1.2,
    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
)
PUB_EXPORT = {"toImageButtonOptions": {"format": "png", "width": 1600, "height": 900, "scale": 2}}


def pub_bar(df_plot, x, y, color=NEJM_BLUE, title="", xlab="", ylab="Number of trials", height=420):
    """Title kept as a no-op kwarg for back-compat; the journal-style title
    is rendered above the chart via _pub_header()."""
    fig = px.bar(
        df_plot, x=x, y=y, height=height,
        color_discrete_sequence=[color], template="plotly_white",
        text=y,
    )
    fig.update_traces(
        marker_line_width=0, opacity=1, width=0.65,
        texttemplate="%{text}", textposition="outside",
        textfont=dict(size=10, color=_AX_COLOR),
        cliponaxis=False,
    )
    fig.update_layout(
        **PUB_LAYOUT,
        xaxis_title=xlab,
        yaxis_title=ylab,
        showlegend=False,
        uniformtext_minsize=9, uniformtext_mode="hide",
    )
    return fig


def _cagr(first_count: int, last_count: int, n_years: int) -> float | None:
    if n_years <= 0 or first_count <= 0:
        return None
    return (last_count / first_count) ** (1 / n_years) - 1


with tab_deepdive:
    st.markdown(
        f'<p class="small-note" style="color:{THEME["muted"]}">Segmented landscape views. '
        'Pick a dimension, then drill into a single disease or product to see who is running trials, '
        'where, and at what scale.</p>',
        unsafe_allow_html=True,
    )

    _dd_view = st.radio(
        "Dimension",
        options=["By disease", "By product type", "By sponsor type"],
        horizontal=True,
        key="deepdive_view",
        label_visibility="collapsed",
    )

    def _expand_disease_rows(df_in: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, r in df_in.iterrows():
            ents = [e.strip() for e in str(r.get("DiseaseEntities", "")).split("|") if e.strip()]
            if not ents:
                ents = [str(r.get("DiseaseEntity", "Unclassified"))]
            for e in ents:
                rr = r.to_dict()
                rr["_Disease"] = e
                rows.append(rr)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    if df_filt.empty:
        st.info("No trials match the current filters.")
    elif _dd_view == "By disease":
        dd_df = _expand_disease_rows(df_filt)
        if dd_df.empty:
            st.info("No disease data available.")
        else:
            agg = (
                dd_df.groupby("_Disease")
                .agg(
                    Trials=("NCTId", "nunique"),
                    Open=("OverallStatus", lambda s: int(s.isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum())),
                    Sponsors=("LeadSponsor", "nunique"),
                    TotalEnrolled=("EnrollmentCount", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                    MedianEnrollment=("EnrollmentCount", lambda s: pd.to_numeric(s, errors="coerce").median()),
                )
                .reset_index()
                .rename(columns={"_Disease": "Disease"})
                .sort_values("Trials", ascending=False)
            )
            agg["MedianEnrollment"] = agg["MedianEnrollment"].fillna(0).astype(int)
            st.subheader("Landscape by disease")
            st.caption(f"{len(agg)} diseases · sorted by trial count")
            st.dataframe(
                agg, width='stretch', hide_index=True,
                column_config=_landscape_table_cols("Disease", "Disease"),
            )

            disease_choices = agg["Disease"].tolist()
            pick = st.selectbox("Drill into disease", options=["—"] + disease_choices, key="dd_disease_pick")
            if pick and pick != "—":
                sub = dd_df[dd_df["_Disease"] == pick].drop_duplicates(subset=["NCTId"])
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Trials", len(sub))
                c2.metric("Open / recruiting",
                          int(sub["OverallStatus"].isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum()))
                _enr = pd.to_numeric(sub["EnrollmentCount"], errors="coerce")
                c3.metric("Total enrolled", f"{int(_enr.fillna(0).sum()):,}")
                c4.metric("Median enrollment", int(_enr.median()) if _enr.notna().any() else 0)

                _tgt = (
                    sub.loc[~sub["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"]
                    .fillna("Unknown").value_counts().rename_axis("Target").reset_index(name="Trials")
                )
                _prod = sub["ProductType"].fillna("Unclear").value_counts().rename_axis("Product").reset_index(name="Trials")
                cA, cB = st.columns(2)
                with cA:
                    st.markdown("**Antigen targets**")
                    st.dataframe(_tgt, width='stretch', hide_index=True,
                                 column_config=_mini_count_cols("Target"))
                with cB:
                    st.markdown("**Product types**")
                    st.dataframe(_prod, width='stretch', hide_index=True,
                                 column_config=_mini_count_cols("Product"))

                _dd_cols = ["NCTId", "NCTLink", "BriefTitle", "TargetCategory", "ProductType",
                            "Phase", "OverallStatus", "LeadSponsor", "StartYear", "Countries"]
                _dd_cols = [c for c in _dd_cols if c in sub.columns]
                detail = sub[_dd_cols].copy()
                if "PhaseLabel" in sub.columns and "Phase" in detail.columns:
                    detail["Phase"] = sub["PhaseLabel"].values
                if "OverallStatus" in detail.columns:
                    detail["OverallStatus"] = detail["OverallStatus"].map(STATUS_DISPLAY).fillna(detail["OverallStatus"])
                st.markdown("**Trials**")
                st.caption(f"{len(detail)} trial{'s' if len(detail) != 1 else ''}")
                st.dataframe(
                    detail, width='stretch', hide_index=True,
                    column_config=_trial_detail_cols(),
                )

    elif _dd_view == "By product type":
        agg = (
            df_filt.groupby("ProductType")
            .agg(
                Trials=("NCTId", "nunique"),
                Open=("OverallStatus", lambda s: int(s.isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum())),
                Sponsors=("LeadSponsor", "nunique"),
                TotalEnrolled=("EnrollmentCount", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                MedianEnrollment=("EnrollmentCount", lambda s: pd.to_numeric(s, errors="coerce").median()),
            )
            .reset_index()
            .sort_values("Trials", ascending=False)
        )
        agg["MedianEnrollment"] = agg["MedianEnrollment"].fillna(0).astype(int)
        st.subheader("Landscape by product type")
        st.caption(f"{len(agg)} product types · sorted by trial count")
        st.dataframe(
            agg, width='stretch', hide_index=True,
            column_config=_landscape_table_cols("ProductType", "Product type"),
        )

        prod_choices = agg["ProductType"].tolist()
        pick = st.selectbox("Drill into product type", options=["—"] + prod_choices, key="dd_product_pick")
        if pick and pick != "—":
            sub = df_filt[df_filt["ProductType"] == pick]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Trials", len(sub))
            c2.metric("Distinct named products",
                      int(sub["ProductName"].dropna().nunique()) if "ProductName" in sub.columns else 0)
            c3.metric("Distinct sponsors", int(sub["LeadSponsor"].dropna().nunique()))
            c4.metric("Countries",
                      len({c.strip() for v in sub["Countries"].dropna() for c in str(v).split("|") if c.strip()}))

            if "ProductName" in sub.columns:
                _np = sub["ProductName"].dropna().value_counts().rename_axis("Named product").reset_index(name="Trials")
                if not _np.empty:
                    st.markdown("**Named products**")
                    st.dataframe(_np, width='stretch', hide_index=True,
                                 column_config=_mini_count_cols("Named product"))

            _detail_cols = ["NCTId", "NCTLink", "BriefTitle", "DiseaseEntities", "DiseaseEntity",
                            "TargetCategory", "ProductName", "Phase", "OverallStatus",
                            "LeadSponsor", "StartYear"]
            _detail_cols = [c for c in _detail_cols if c in sub.columns]
            detail = sub[_detail_cols].copy()
            if "PhaseLabel" in sub.columns and "Phase" in detail.columns:
                detail["Phase"] = sub["PhaseLabel"].values
            if "OverallStatus" in detail.columns:
                detail["OverallStatus"] = detail["OverallStatus"].map(STATUS_DISPLAY).fillna(detail["OverallStatus"])
            st.markdown("**Trials**")
            st.caption(f"{len(detail)} trial{'s' if len(detail) != 1 else ''}")
            st.dataframe(
                detail, width='stretch', hide_index=True,
                column_config=_trial_detail_cols(),
            )

    else:  # By sponsor type
        # Defensive fallback: older cached state may lack SponsorType.
        # Recompute it on the fly rather than blocking the view.
        if "SponsorType" not in df_filt.columns and "LeadSponsor" in df_filt.columns:
            try:
                from pipeline import _classify_sponsor as _cs
                df_filt["SponsorType"] = df_filt.apply(
                    lambda r: _cs(r.get("LeadSponsor"), r.get("LeadSponsorClass")), axis=1
                )
            except Exception:
                pass
        if "SponsorType" not in df_filt.columns:
            st.info("Sponsor type not available in the current snapshot.")
        else:
            agg = (
                df_filt.groupby("SponsorType")
                .agg(
                    Trials=("NCTId", "nunique"),
                    Open=("OverallStatus", lambda s: int(s.isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum())),
                    Sponsors=("LeadSponsor", "nunique"),
                    TotalEnrolled=("EnrollmentCount", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                    MedianEnrollment=("EnrollmentCount", lambda s: pd.to_numeric(s, errors="coerce").median()),
                )
                .reset_index()
                .sort_values("Trials", ascending=False)
            )
            agg["MedianEnrollment"] = agg["MedianEnrollment"].fillna(0).astype(int)
            st.subheader("Landscape by sponsor type")
            st.caption(f"{len(agg)} sponsor categories · sorted by trial count")
            st.dataframe(
                agg, width='stretch', hide_index=True,
                column_config=_landscape_table_cols("SponsorType", "Sponsor type"),
            )

            sp_choices = agg["SponsorType"].tolist()
            pick = st.selectbox("Drill into sponsor type", options=["—"] + sp_choices, key="dd_sponsor_pick")
            if pick and pick != "—":
                sub = df_filt[df_filt["SponsorType"] == pick]
                _top_sponsors = (
                    sub["LeadSponsor"].dropna().value_counts().head(10)
                    .rename_axis("Lead sponsor").reset_index(name="Trials")
                )
                st.markdown("**Top sponsors**")
                st.dataframe(_top_sponsors, width='stretch', hide_index=True,
                             column_config=_mini_count_cols("Lead sponsor"))
                _prod = sub["ProductType"].fillna("Unclear").value_counts().rename_axis("Product").reset_index(name="Trials")
                _tgt = (
                    sub.loc[~sub["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"]
                    .fillna("Unknown").value_counts().rename_axis("Target").reset_index(name="Trials")
                )
                cA, cB = st.columns(2)
                with cA:
                    st.markdown("**Antigen targets**")
                    st.dataframe(_tgt, width='stretch', hide_index=True,
                                 column_config=_mini_count_cols("Target"))
                with cB:
                    st.markdown("**Product types**")
                    st.dataframe(_prod, width='stretch', hide_index=True,
                                 column_config=_mini_count_cols("Product"))


with tab_pub:
    st.markdown(
        f'<p class="small-note" style="color:{THEME["muted"]}">Publication-ready figures with white backgrounds. '
        "Use the camera icon (▷ toolbar) on each chart to download a high-resolution PNG. "
        "Each section also provides the underlying data as CSV.</p>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Fig 1 — Temporal trends
    # ------------------------------------------------------------------
    years_raw = pd.to_numeric(df_filt["StartYear"], errors="coerce").dropna().astype(int)
    _FIG1_LEADING_MIN = 3
    if len(years_raw):
        _yearly_raw = years_raw.value_counts().sort_index()
        _above_raw = _yearly_raw[_yearly_raw >= _FIG1_LEADING_MIN]
        _yr_display_min = int(_above_raw.index.min()) if not _above_raw.empty else int(_yearly_raw.index.min())
        _yr_display_max = int(_yearly_raw.index.max())
    else:
        _yr_display_min = _yr_display_max = None
    _pub_header(
        "1",
        "Temporal trends by disease entity",
        (
            f"Annual trial starts by disease entity, {_yr_display_min}–{_yr_display_max}."
            if _yr_display_min is not None
            else "Annual trial starts by disease entity."
        ),
    )

    # ── Stacking groups: top-N disease entities + 'Other' ──────────────────
    _ENTITY_COLORS = {
        "SLE":                   NEJM_BLUE,
        "SSc":                   NEJM_AMBER,
        "IIM":                   NEJM_GREEN,
        "AAV":                   NEJM_PURPLE,
        "Sjogren":               "#0891b2",   # cyan-600
        "RA":                    NEJM_RED,
        "CTD_other":             "#0d9488",   # teal-600
        "IgG4-RD":               "#ea580c",   # orange-600
        "Behcet":                "#7c2d12",   # amber-900 — non-purple replacement
        "cGVHD":                 "#db2777",   # pink-600
        "Basket/Multidisease":   "#475569",   # slate-600
        "Other immune-mediated": "#94a3b8",   # slate-400
        "Unclassified":          "#cbd5e1",   # slate-300
        "Other":                 "#e2e8f0",   # slate-200
    }

    _entity_series = df_filt["DiseaseEntity"].fillna("Unclassified").astype(str)
    _top_entities = _entity_series.value_counts().head(7).index.tolist()

    def _display_group(e: str) -> str:
        return e if e in _top_entities else "Other"

    fig1_long = (
        df_filt.assign(
            StartYear=pd.to_numeric(df_filt["StartYear"], errors="coerce"),
            Group=_entity_series.map(_display_group),
        )
        .dropna(subset=["StartYear"])
        .astype({"StartYear": int})
        .groupby(["StartYear", "Group"], as_index=False)
        .size()
        .rename(columns={"size": "Trials"})
    )
    fig1_data = fig1_long.pivot(index="StartYear", columns="Group", values="Trials").fillna(0).astype(int).reset_index()

    if not fig1_long.empty:
        # Stacking order: largest totals at the bottom, 'Other' / 'Unclassified' on top
        group_totals = fig1_long.groupby("Group")["Trials"].sum().sort_values(ascending=False)
        sink_labels = [g for g in ["Other", "Unclassified"] if g in group_totals.index]
        main_order = [g for g in group_totals.index if g not in sink_labels]
        stack_order = main_order + sink_labels

        # Build explicit stacked-area traces.  px.area in plotly 6.x does not
        # auto-stack, so overlapping fills hide everything behind the topmost
        # (often near-white "Other") trace.  Using go.Scatter with an explicit
        # stackgroup guarantees a proper stacked-area rendering.
        # Trim leading years whose total count is below a noise threshold —
        # a single pilot trial in 2019 would otherwise anchor the axis to a
        # flat sliver and push meaningful activity to the right of the chart.
        _axis_start = _yr_display_min if _yr_display_min is not None else int(fig1_long["StartYear"].min())
        _axis_end = _yr_display_max if _yr_display_max is not None else int(fig1_long["StartYear"].max())
        _years_axis = list(range(_axis_start, _axis_end + 1))
        _pivot = (
            fig1_long.pivot(index="StartYear", columns="Group", values="Trials")
            .reindex(_years_axis)
            .fillna(0)
            .astype(int)
        )
        fig1 = go.Figure()
        # Stack from bottom → top (largest groups first, sinks last)
        for _grp in stack_order:
            if _grp not in _pivot.columns:
                continue
            _color = _ENTITY_COLORS.get(_grp, "#94a3b8")
            fig1.add_trace(go.Scatter(
                x=_pivot.index.tolist(),
                y=_pivot[_grp].tolist(),
                name=_grp,
                mode="lines",
                stackgroup="one",
                line=dict(width=0.5, color="white"),
                fillcolor=_color,
                hovertemplate="%{x}: %{y} trials<extra>" + _grp + "</extra>",
            ))
        _fig1_layout = {**PUB_LAYOUT}
        _fig1_layout["margin"] = dict(l=72, r=36, t=24, b=130)
        fig1.update_layout(
            **_fig1_layout,
            xaxis_title="Start year",
            yaxis_title="Number of trials",
            legend=dict(
                orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5,
                bgcolor="rgba(0,0,0,0)", borderwidth=0, title_text="",
                font=dict(size=11),
            ),
        )
        fig1.update_xaxes(title_standoff=12)
        fig1.update_xaxes(tickmode="linear", dtick=1, tickformat="d", showgrid=False)
        fig1.update_yaxes(rangemode="tozero")

        # Partial-year marker
        _current_year = pd.Timestamp.now().year
        if int(fig1_long["StartYear"].max()) >= _current_year:
            fig1.add_vrect(
                x0=_current_year - 0.5, x1=_current_year + 0.5,
                fillcolor="rgba(0,0,0,0.04)", line_width=0,
            )
            fig1.add_annotation(
                x=_current_year, y=1, yref="paper",
                text=f"{_current_year} (partial year)",
                showarrow=False,
                font=dict(size=10, color=THEME["muted"]),
                yanchor="bottom", xanchor="center",
            )
        st.plotly_chart(fig1, width='stretch', config=PUB_EXPORT)

        # Key statistics — use yearly totals, restricted to the displayed year
        # window so the CAGR baseline matches what the reader actually sees.
        totals_by_year = (
            fig1_long[fig1_long["StartYear"] >= _axis_start]
            .groupby("StartYear")["Trials"].sum().reset_index()
        )
        total_t = len(df_filt)
        peak_year = int(totals_by_year.loc[totals_by_year["Trials"].idxmax(), "StartYear"])
        peak_n = int(totals_by_year["Trials"].max())
        first_row = totals_by_year.iloc[0]
        last_row = totals_by_year.iloc[-1]
        cagr = _cagr(
            int(first_row["Trials"]), int(last_row["Trials"]),
            int(last_row["StartYear"] - first_row["StartYear"]),
        )
        cagr_str = f"{cagr * 100:.1f}%" if cagr is not None else "N/A"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total included trials", total_t)
        c2.metric("Year range", f"{int(first_row['StartYear'])}–{int(last_row['StartYear'])}")
        c3.metric("Peak year", f"{peak_year} (n={peak_n})")
        c4.metric("CAGR (first → last year)", cagr_str)

        _pub_caption(len(df_filt))
        st.download_button("Fig 1 data (CSV)",
                           _csv_with_provenance(fig1_data, "Fig 1 — Temporal trends by disease entity"),
                           "fig1_temporal_trends.csv", "text/csv")
    else:
        st.info("No start year data available.")

    # ------------------------------------------------------------------
    # Fig 2 — Phase distribution
    # ------------------------------------------------------------------
    _pub_header("2", "Distribution of clinical trial phases",
                "Horizontal bars by phase, split by sponsor sector (Academic vs Industry).")

    phase_counts = (
        df_filt.groupby("PhaseOrdered", observed=False).size().reset_index(name="Trials")
    )
    phase_counts["Phase"] = phase_counts["PhaseOrdered"].astype(str).map(PHASE_LABELS)
    phase_counts = phase_counts[phase_counts["Trials"] > 0].copy()
    phase_counts["Phase"] = pd.Categorical(
        phase_counts["Phase"], categories=[PHASE_LABELS[p] for p in PHASE_ORDER], ordered=True
    )
    phase_counts = phase_counts.sort_values("Phase")

    if not phase_counts.empty:
        _phase_order = [PHASE_LABELS[p] for p in PHASE_ORDER
                        if PHASE_LABELS[p] in phase_counts["Phase"].astype(str).tolist()]

        _sp = df_filt.copy()
        _sp["Phase"] = _sp["PhaseOrdered"].astype(str).map(PHASE_LABELS)
        _sp["SponsorBucket"] = _sp["SponsorType"].where(
            _sp["SponsorType"].isin(["Academic", "Industry"]), "Other"
        )
        phase_by_sp = (
            _sp.groupby(["Phase", "SponsorBucket"], observed=False).size()
            .reset_index(name="Trials")
        )
        phase_by_sp = phase_by_sp[phase_by_sp["Trials"] > 0]

        _sp_colors = {"Academic": NEJM_BLUE, "Industry": NEJM_AMBER, "Other": "#94a3b8"}
        fig2 = go.Figure()
        for bucket in ["Academic", "Industry", "Other"]:
            sub = phase_by_sp[phase_by_sp["SponsorBucket"] == bucket]
            if sub.empty:
                continue
            fig2.add_trace(go.Bar(
                y=sub["Phase"],
                x=sub["Trials"],
                name=bucket,
                orientation="h",
                marker_color=_sp_colors[bucket],
                hovertemplate=f"<b>{bucket}</b> · %{{y}}<br>%{{x}} trials<extra></extra>",
            ))
        fig2.update_layout(
            barmode="stack",
            template="plotly_white",
            height=max(320, 52 * len(_phase_order) + 80),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Trials",
            yaxis=dict(
                categoryorder="array",
                categoryarray=list(reversed(_phase_order)),  # earliest phase at top
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, width='stretch', config=PUB_EXPORT)

        total_ph = phase_counts["Trials"].sum()
        early = phase_counts.loc[phase_counts["Phase"].isin(["Early Phase I", "Phase I"]), "Trials"].sum()
        late = phase_counts.loc[phase_counts["Phase"].isin(["Phase II", "Phase II/III", "Phase III"]), "Trials"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Early-phase (I / Early I)", f"{early} ({100*early/total_ph:.0f}%)")
        c2.metric("Late-phase (II+)", f"{late} ({100*late/total_ph:.0f}%)")
        c3.metric("Phase I/II (hybrid)", str(int(phase_counts.loc[phase_counts["Phase"] == "Phase I/II", "Trials"].sum())))

        fig2_csv = (
            phase_by_sp.pivot(index="Phase", columns="SponsorBucket", values="Trials")
            .fillna(0).astype(int).reset_index()
        )
        fig2_csv["Total"] = fig2_csv.drop(columns=["Phase"]).sum(axis=1)
        _pub_caption(len(df_filt))
        st.download_button("Fig 2 data (CSV)",
                           _csv_with_provenance(fig2_csv, "Fig 2 — Phase distribution by sponsor sector"),
                           "fig2_phase_by_sponsor.csv", "text/csv")
    else:
        st.info("No phase data available.")

    # ------------------------------------------------------------------
    # Fig 3 — Geographic distribution
    # ------------------------------------------------------------------
    _pub_header("3", "Global distribution of trial sites",
                "Choropleth of trial counts by country, with leading countries shown below.")

    geo_vals = split_pipe_values(df_filt["Countries"])
    if geo_vals:
        geo_counts = (
            pd.DataFrame({"Country": geo_vals})["Country"]
            .value_counts().rename_axis("Country").reset_index(name="Trials")
        )

        geo_counts = _attach_iso3(geo_counts)
        fig3_map = px.choropleth(
            geo_counts, locations="Iso3", locationmode="ISO-3",
            hover_name="Country",
            color="Trials",
            color_continuous_scale=[[0, "#dce9f5"], [0.3, "#5aafd6"], [0.65, "#1c6faf"], [1, "#08306b"]],
            projection="natural earth", template="plotly_white",
        )
        fig3_map.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=PUB_FONT,
            margin=dict(l=0, r=0, t=10, b=0),
            geo=dict(
                bgcolor="white", lakecolor="#ddeeff", landcolor="#eeeeee",
                showframe=False,
                showcoastlines=True, coastlinecolor="#999999", coastlinewidth=0.6,
                showcountries=True, countrycolor="#cccccc", countrywidth=0.4,
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Trials", font=dict(size=11, color=_AX_COLOR)),
                tickfont=dict(size=10, color=_AX_COLOR),
                thickness=14, len=0.55, outlinewidth=0.5, outlinecolor="#aaaaaa",
            ),
        )
        st.plotly_chart(fig3_map, width='stretch', config=PUB_EXPORT)

        top10 = geo_counts.head(10).sort_values("Trials", ascending=True)
        fig3_bar = px.bar(
            top10, x="Trials", y="Country", orientation="h", height=380,
            color_discrete_sequence=[NEJM_BLUE], template="plotly_white",
            text="Trials",
        )
        fig3_bar.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig3_bar.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials", yaxis_title=None, showlegend=False,
            margin=dict(l=100, r=56, t=24, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">3b — Top 10 countries by number of trials</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig3_bar, width='stretch', config=PUB_EXPORT)

        total_geo = geo_counts["Trials"].sum()
        top3_geo = geo_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3_geo.iterrows()):
            col.metric(row["Country"], f"{row['Trials']} ({100*row['Trials']/total_geo:.0f}%)")

        fig3_csv = geo_counts[["Country", "Trials"]].copy()
        fig3_csv["% of total"] = (fig3_csv["Trials"] / total_geo * 100).round(1)
        _pub_caption(
            len(df_filt),
            extra="Multi-country trials are counted once per country."
        )
        st.download_button("Fig 3 data (CSV)",
                           _csv_with_provenance(fig3_csv, "Fig 3 — Geographic distribution"),
                           "fig3_geographic_distribution.csv", "text/csv")
    else:
        st.info("No country data available.")

    # ------------------------------------------------------------------
    # Fig 4 — Trial enrollment
    # ------------------------------------------------------------------
    _pub_header("4", "Trial enrollment landscape",
                "Distribution and median planned enrollment, with subgroup comparisons by phase, geography, and sponsor type.")

    df_enroll = df_filt.copy()
    df_enroll["EnrollmentCount"] = pd.to_numeric(df_enroll["EnrollmentCount"], errors="coerce")
    df_enroll_known = df_enroll.dropna(subset=["EnrollmentCount"]).copy()
    df_enroll_known["EnrollmentCount"] = df_enroll_known["EnrollmentCount"].astype(int)

    if len(df_enroll_known) >= 3:
        pct_known = 100 * len(df_enroll_known) / len(df_enroll)
        total_pts = int(df_enroll_known["EnrollmentCount"].sum())
        med_pts   = int(df_enroll_known["EnrollmentCount"].median())
        p25 = int(df_enroll_known["EnrollmentCount"].quantile(0.25))
        p75 = int(df_enroll_known["EnrollmentCount"].quantile(0.75))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Trials with reported enrollment", f"{len(df_enroll_known)} ({pct_known:.0f}%)")
        c2.metric("Total enrolled patients", f"{total_pts:,}")
        c3.metric("Median enrollment", med_pts)
        c4.metric("IQR", f"{p25}–{p75}")

        # 4a — Enrollment distribution histogram
        # A handful of very-large industry registries (n>1000) would otherwise
        # compress the distribution of the typical early-phase rheum CAR-T trial.
        _ENROLL_CAP = 1000
        _over_cap = df_enroll_known[df_enroll_known["EnrollmentCount"] > _ENROLL_CAP]
        df_enroll_plot = df_enroll_known[df_enroll_known["EnrollmentCount"] <= _ENROLL_CAP]
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">4a — Distribution of planned enrollment</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig4a = px.histogram(
            df_enroll_plot, x="EnrollmentCount", nbins=40, height=400,
            color_discrete_sequence=[NEJM_AMBER], template="plotly_white",
            labels={"EnrollmentCount": "Planned enrollment (patients)"},
        )
        fig4a.update_traces(marker_line_color="white", marker_line_width=0.4, opacity=0.9)
        _vline_med = dict(
            type="line", x0=med_pts, x1=med_pts, y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=NEJM_RED, width=1.5, dash="dash"),
        )
        fig4a.update_layout(
            **PUB_LAYOUT,
            xaxis_title="Planned enrollment (patients)",
            yaxis_title="Number of trials",
            shapes=[_vline_med],
            annotations=[dict(
                x=med_pts, y=0.97, xref="x", yref="paper",
                text=f" Median = {med_pts}", showarrow=False,
                font=dict(size=10, color=NEJM_RED), xanchor="left",
            )],
        )
        st.plotly_chart(fig4a, width='stretch', config=PUB_EXPORT)
        if len(_over_cap) > 0:
            st.markdown(
                f'<div class="pub-fig-caption" style="margin-top: 0.1rem;">'
                f'{len(_over_cap)} trial(s) with planned enrollment &gt; {_ENROLL_CAP:,} '
                f'excluded from this panel for readability; '
                f'included in all summary statistics above.'
                f'</div>',
                unsafe_allow_html=True,
            )

        # 4b — Median enrollment by phase
        _phase_enroll = (
            df_enroll_known.groupby("PhaseNormalized", observed=False)["EnrollmentCount"]
            .agg(Median="median", Q1=lambda x: x.quantile(0.25), Q3=lambda x: x.quantile(0.75), N="count")
            .reset_index()
            .rename(columns={"PhaseNormalized": "Phase"})
        )
        _phase_order_map = {v: k for k, v in PHASE_LABELS.items()}
        _phase_enroll = _phase_enroll[_phase_enroll["N"] > 0].copy()
        _phase_enroll["PhaseOrdered"] = _phase_enroll["Phase"].map(_phase_order_map)
        _phase_enroll = _phase_enroll.sort_values("PhaseOrdered", na_position="last")
        _phase_enroll["Median"] = _phase_enroll["Median"].astype(int)
        _phase_enroll["label"] = _phase_enroll.apply(
            lambda r: f"{r['Median']} (n={r['N']})", axis=1
        )

        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">4b — Median enrollment by trial phase</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig4b = px.bar(
            _phase_enroll, x="Phase", y="Median", height=380,
            color_discrete_sequence=[NEJM_AMBER], template="plotly_white",
            text="label",
            error_y=_phase_enroll["Q3"] - _phase_enroll["Median"],
            error_y_minus=_phase_enroll["Median"] - _phase_enroll["Q1"],
        )
        fig4b.update_traces(
            marker_line_width=0, opacity=1, width=0.6,
            textposition="outside", textfont=dict(size=10, color=_AX_COLOR),
            cliponaxis=False,
            error_y=dict(color=_AX_COLOR, thickness=1.1, width=6),
        )
        fig4b.update_layout(
            **PUB_LAYOUT,
            xaxis_title="Phase",
            yaxis_title="Median planned enrollment (patients)",
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig4b, width='stretch', config=PUB_EXPORT)
        st.markdown(
            '<div class="pub-fig-caption" style="margin-top: 0.1rem;">'
            'Whiskers = IQR (Q1–Q3).'
            '</div>',
            unsafe_allow_html=True,
        )

        # (Former 4c — disease-level enrollment — has been merged into Fig 5.)

        # 4c — China vs Non-China  ·  Academic vs Industry  (was 4d)
        def _geo_group(countries_str) -> str:
            if not countries_str or pd.isna(countries_str):
                return "Unknown"
            return "China" if "China" in str(countries_str).split("|") else "Non-China"

        _ACAD_TOKENS = [
            "hospital", "university", "universit",   # covers most international variants
            "medical center", "medical centre", "medical college", "medical school",
            "children's", "childrens", "school of medicine",
            "general hospital", "affiliated hospital",
            "national institute", "research center", "research centre",
            "pla ", "armed forces", "faculty of", "nhs", "inserm",
        ]
        _INDUS_TOKENS = [
            "therapeutics", "pharma", "pharmaceutical",
            "biotechnology", "biotech", "bioscience", "biotherapy",
            "biopharmaceutical", "biopharma", "biologics",
            " inc", " ltd", " co.,", " llc", " corp", " gmbh",
        ]

        def _sponsor_type(sponsor) -> str:
            if not sponsor or pd.isna(sponsor):
                return "Unknown"
            s = str(sponsor).lower()
            if any(t in s for t in _ACAD_TOKENS):
                return "Academic"
            if any(t in s for t in _INDUS_TOKENS):
                return "Industry"
            # short strings without corporate suffixes are usually PI names
            if len(s.split()) <= 4 and "." not in s:
                return "Academic"
            return "Industry"

        # Vectorized GeoGroup; SponsorType already baked in pipeline post-process.
        _ctr = df_enroll_known["Countries"].fillna("")
        _has_china = _ctr.str.contains(r"(?:^|\|)China(?:$|\|)", regex=True, na=False)
        df_enroll_known["GeoGroup"] = np.where(
            _ctr == "", "Unknown",
            np.where(_has_china, "China", "Non-China"),
        )

        def _comparison_stats(df_sub, group_col: str) -> pd.DataFrame:
            return (
                df_sub[df_sub[group_col] != "Unknown"]
                .groupby(group_col)["EnrollmentCount"]
                .agg(
                    Median="median",
                    Q1=lambda x: int(x.quantile(0.25)),
                    Q3=lambda x: int(x.quantile(0.75)),
                    N="count",
                )
                .reset_index()
                .rename(columns={group_col: "Group"})
                .assign(Median=lambda d: d["Median"].astype(int))
                .assign(Label=lambda d: d.apply(lambda r: f"Median {r['Median']}  (n={r['N']})", axis=1))
            )

        geo_stats  = _comparison_stats(df_enroll_known, "GeoGroup")
        spon_stats = _comparison_stats(df_enroll_known, "SponsorType")
        cross_stats_raw = (
            df_enroll_known[
                (df_enroll_known["GeoGroup"] != "Unknown") &
                (df_enroll_known["SponsorType"] != "Unknown")
            ]
            .groupby(["GeoGroup", "SponsorType"])["EnrollmentCount"]
            .agg(Median="median",
                 Q1=lambda x: int(x.quantile(0.25)),
                 Q3=lambda x: int(x.quantile(0.75)),
                 N="count")
            .reset_index()
            .assign(Median=lambda d: d["Median"].astype(int))
        )

        # ── Forest plot: one panel replacing the three previous comparison charts.
        #    Rows are grouped vertically by category; dot = median, whisker = IQR.
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">4c — Enrollment by subgroup</strong> '
            '<span style="color: #94a3b8;">— median (dot) and IQR (whisker)</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        forest_rows = []
        # Overall row
        _all = df_enroll_known["EnrollmentCount"]
        forest_rows.append({
            "Category": "Overall", "Group": "All trials",
            "Median": int(_all.median()),
            "Q1": int(_all.quantile(0.25)), "Q3": int(_all.quantile(0.75)),
            "N": int(len(_all)),
        })
        # Geography subgroup
        for _, r in geo_stats.iterrows():
            forest_rows.append({
                "Category": "Geography", "Group": r["Group"],
                "Median": int(r["Median"]), "Q1": int(r["Q1"]), "Q3": int(r["Q3"]), "N": int(r["N"]),
            })
        # Sponsor subgroup
        for _, r in spon_stats.iterrows():
            forest_rows.append({
                "Category": "Sponsor", "Group": r["Group"],
                "Median": int(r["Median"]), "Q1": int(r["Q1"]), "Q3": int(r["Q3"]), "N": int(r["N"]),
            })
        # Cross-stratified subgroup
        for _, r in cross_stats_raw.iterrows():
            forest_rows.append({
                "Category": "Geography × Sponsor",
                "Group": f"{r['GeoGroup']} · {r['SponsorType']}",
                "Median": int(r["Median"]), "Q1": int(r["Q1"]), "Q3": int(r["Q3"]), "N": int(r["N"]),
            })
        forest_df = pd.DataFrame(forest_rows)
        forest_df["Label"] = forest_df.apply(
            lambda r: f"{r['Category']}: {r['Group']}", axis=1
        )
        forest_df["NLabel"] = forest_df["N"].apply(lambda n: f"  Median {forest_df.loc[forest_df['N']==n, 'Median'].iloc[0]}  ·  n={n}")
        # Reverse so Overall sits at the top of the chart (Plotly y axis flips)
        forest_df = forest_df.iloc[::-1].reset_index(drop=True)

        # Color per category
        _CAT_COLORS = {
            "Overall":             "#0b1220",
            "Geography":           NEJM_BLUE,
            "Sponsor":             NEJM_GREEN,
            "Geography × Sponsor": NEJM_AMBER,
        }
        forest_df["Color"] = forest_df["Category"].map(_CAT_COLORS)

        fig4d = px.scatter(
            forest_df, x="Median", y="Label",
            color="Category", color_discrete_map=_CAT_COLORS,
            error_x=forest_df["Q3"] - forest_df["Median"],
            error_x_minus=forest_df["Median"] - forest_df["Q1"],
            height=max(360, 28 * len(forest_df) + 110),
            template="plotly_white",
        )
        fig4d.update_traces(
            marker=dict(size=11, line=dict(color="white", width=1.2)),
            error_x=dict(color=_AX_COLOR, thickness=1.2, width=6),
        )
        # Sample-size annotations to the right of each whisker
        for _, r in forest_df.iterrows():
            fig4d.add_annotation(
                x=r["Q3"], y=r["Label"], xref="x", yref="y",
                text=f"  Median {r['Median']}  ·  n={r['N']}",
                showarrow=False,
                font=dict(size=10, color=THEME["muted"]),
                xanchor="left",
            )
        _overall_median = int(df_enroll_known["EnrollmentCount"].median())
        fig4d.add_vline(
            x=_overall_median, line_dash="dash",
            line_color=NEJM_RED, line_width=1.3,
            annotation_text=f" Overall median = {_overall_median}",
            annotation_position="top right",
            annotation_font=dict(size=10, color=NEJM_RED),
        )
        fig4d.update_layout(
            **PUB_BASE,
            margin=dict(l=220, r=120, t=24, b=64),
            xaxis=dict(
                title="Median planned enrollment (patients)",
                showline=True, linewidth=1.5, linecolor=_AX_COLOR,
                showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
                ticks="outside", ticklen=6, tickwidth=1.2,
                tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
                title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
                zeroline=False, rangemode="tozero",
            ),
            yaxis=dict(
                title=None, showline=False, showgrid=False,
                ticks="", tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
            ),
            showlegend=False,
        )
        st.plotly_chart(fig4d, width='stretch', config=PUB_EXPORT)
        st.markdown(
            '<div class="pub-fig-caption" style="margin-top: 0.1rem;">'
            f'Whiskers = IQR (Q1–Q3). Dashed line marks the overall median ({_overall_median} patients).'
            '</div>',
            unsafe_allow_html=True,
        )

        # Tabular summary (inputs to forest plot, in display order)
        _cmp_summary = forest_df[["Category", "Group", "N", "Median", "Q1", "Q3"]].iloc[::-1].reset_index(drop=True)
        _cmp_summary = _cmp_summary.rename(columns={"N": "N (trials)", "Median": "Median enrollment", "Q1": "IQR Q1", "Q3": "IQR Q3"})

        fig4_csv = df_enroll_known[["NCTId", "BriefTitle", "DiseaseEntity", "TargetCategory",
                                     "ProductType", "Phase", "EnrollmentCount",
                                     "GeoGroup", "SponsorType"]].copy()
        fig4_csv = fig4_csv.sort_values("EnrollmentCount", ascending=False)
        _pub_caption(
            len(df_filt),
            extra=f"Enrollment panels restricted to {len(df_enroll_known):,} trials with a numeric enrollment target."
        )
        st.download_button("Fig 4 data (CSV)",
                           _csv_with_provenance(fig4_csv, "Fig 4 — Enrollment characteristics"),
                           "fig4_enrollment.csv", "text/csv")
        with st.expander("Comparison summary table"):
            st.dataframe(_cmp_summary, width='stretch', hide_index=True)
    else:
        st.info("Insufficient enrollment data available.")
    # ------------------------------------------------------------------
    # Fig 5 — Disease distribution
    # ------------------------------------------------------------------
    _pub_header("5", "Disease entity distribution",
                "Two panels: number of trials per disease (left) and total planned patients per disease (right). Basket and multi-disease trials are attributed to each enrolled disease.")

    _dis_vals = split_pipe_values(df_filt["DiseaseEntities"])
    disease_counts = (
        pd.DataFrame({"Disease": _dis_vals})["Disease"]
        .value_counts().rename_axis("Disease").reset_index(name="Trials")
    ) if _dis_vals else pd.DataFrame(columns=["Disease", "Trials"])

    # Disease × total enrollment (reported-enrollment subset)
    _dis_enroll_rows = []
    for _, row in df_enroll_known.iterrows():
        entities = [e.strip() for e in str(row.get("DiseaseEntities", "")).split("|") if e.strip()]
        if not entities:
            entities = [str(row.get("DiseaseEntity", "Unclassified"))]
        for ent in entities:
            _dis_enroll_rows.append({"Disease": ent, "Enrollment": row["EnrollmentCount"]})
    dis_enroll_agg = (
        pd.DataFrame(_dis_enroll_rows)
        .groupby("Disease")["Enrollment"]
        .sum()
        .reset_index(name="TotalEnrolled")
    ) if _dis_enroll_rows else pd.DataFrame(columns=["Disease", "TotalEnrolled"])

    if not disease_counts.empty:
        # Shared disease ordering: ascending by trial count so largest sits at top.
        disease_sorted = disease_counts.sort_values("Trials", ascending=True).copy()
        disease_sorted = disease_sorted.merge(dis_enroll_agg, on="Disease", how="left")
        disease_sorted["TotalEnrolled"] = disease_sorted["TotalEnrolled"].fillna(0).astype(int)
        _disease_order = disease_sorted["Disease"].tolist()

        _row_h = max(380, len(disease_sorted) * 36 + 120)
        fig5 = make_subplots(
            rows=1, cols=2,
            shared_yaxes=True,
            horizontal_spacing=0.08,
            subplot_titles=("5a — Trials per disease", "5b — Total planned patients per disease"),
        )
        fig5.add_trace(
            go.Bar(
                x=disease_sorted["Trials"], y=disease_sorted["Disease"],
                orientation="h", marker_color=NEJM_AMBER,
                text=disease_sorted["Trials"], textposition="outside",
                textfont=dict(size=10, color=_AX_COLOR),
                hovertemplate="<b>%{y}</b><br>%{x} trials<extra></extra>",
                cliponaxis=False,
            ),
            row=1, col=1,
        )
        fig5.add_trace(
            go.Bar(
                x=disease_sorted["TotalEnrolled"], y=disease_sorted["Disease"],
                orientation="h", marker_color=NEJM_BLUE,
                text=disease_sorted["TotalEnrolled"].apply(lambda v: f"{v:,}" if v else ""),
                textposition="outside",
                textfont=dict(size=10, color=_AX_COLOR),
                hovertemplate="<b>%{y}</b><br>%{x:,} planned patients<extra></extra>",
                cliponaxis=False,
            ),
            row=1, col=2,
        )
        fig5.update_layout(
            **PUB_BASE,
            showlegend=False,
            height=_row_h,
            margin=dict(l=170, r=64, t=48, b=56),
            uniformtext_minsize=9, uniformtext_mode="hide",
            bargap=0.35,
        )
        fig5.update_yaxes(
            categoryorder="array",
            categoryarray=_disease_order,
            showline=False, showgrid=False, ticks="",
            tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
        )
        fig5.update_xaxes(
            showline=True, linewidth=1.5, linecolor=_AX_COLOR,
            showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
            ticks="outside", ticklen=6, tickwidth=1.2,
            tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
            title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
            zeroline=False, rangemode="tozero",
        )
        fig5.update_xaxes(title_text="Number of trials", row=1, col=1)
        fig5.update_xaxes(title_text="Total planned patients (reported trials)", row=1, col=2)
        st.plotly_chart(fig5, width='stretch', config=PUB_EXPORT)

        total_dis = disease_counts["Trials"].sum()
        top3 = disease_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
            col.metric(row["Disease"], f"{row['Trials']} ({100*row['Trials']/total_dis:.0f}%)")

        fig5_csv = (
            disease_counts.merge(dis_enroll_agg, on="Disease", how="left")
            .fillna({"TotalEnrolled": 0})
        )
        fig5_csv["TotalEnrolled"] = fig5_csv["TotalEnrolled"].astype(int)
        fig5_csv["% of total (trials)"] = (fig5_csv["Trials"] / total_dis * 100).round(1)
        _pub_caption(
            len(df_filt),
            extra=(
                "5a counts trials with at least one match for the disease (basket trials counted per disease). "
                "5b restricted to trials with a numeric enrollment target."
            ),
        )
        st.download_button("Fig 5 data (CSV)",
                           _csv_with_provenance(fig5_csv, "Fig 5 — Disease distribution (trials + planned patients)"),
                           "fig5_disease_distribution.csv", "text/csv")
    else:
        st.info("No disease data available.")

    # ------------------------------------------------------------------
    # Fig 6 — Antigen target distribution (CAR-T_unspecified + Other_or_unknown
    # are merged into "Undisclosed / unclear" for the chart; the distinction is
    # preserved in the CSV export for downstream use.)
    # ------------------------------------------------------------------
    _pub_header("6", "Antigen target distribution",
                "Trials by primary CAR antigen target. Cell-therapy platforms (CAR-NK, CAR-Treg, CAAR-T, CAR-γδ T) are shown in Figure 7.")

    # CAR-NK / CAR-Treg / CAAR-T / CAR-γδ T are cell therapy platforms, not antigen targets —
    # they belong in the modality figure (Fig 7). Exclude them here.
    _raw_target_series = (
        df_filt.loc[~df_filt["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"].fillna("Unknown")
    )
    # Raw counts preserve the CAR-T_unspecified / Other_or_unknown distinction (for CSV export).
    _raw_target_counts = (
        _raw_target_series.value_counts().rename_axis("Target").reset_index(name="Trials")
    )
    _UNCLEAR_BUCKET = "Undisclosed / unclear"
    _display_target_series = _raw_target_series.replace({
        "CAR-T_unspecified": _UNCLEAR_BUCKET,
        "Other_or_unknown":  _UNCLEAR_BUCKET,
        "Unknown":           _UNCLEAR_BUCKET,
    })
    target_counts = (
        _display_target_series.value_counts().rename_axis("Target").reset_index(name="Trials")
    )

    def _target_class(target: str) -> str:
        """Group antigen targets by mechanistic class for coloring."""
        if not target or not isinstance(target, str):
            return "Undisclosed / unclear"
        t = target.lower()
        if t.startswith("other (") or "unclear" in t or "undisclosed" in t:
            return "Undisclosed / unclear"
        if "dual" in t or "/" in t or "tri" in t:
            return "Dual / multi-target"
        if any(m in t for m in ["cd19", "cd20", "cd22", "cd79"]):
            return "B-cell surface"
        if "bcma" in t or "gprc5d" in t:
            return "Plasma-cell"
        return "Other / novel"

    if not target_counts.empty:
        # Keep top 15 targets; collapse the long tail into a single "Other" bucket
        # so the chart stays readable even as the landscape grows.
        _TOP_N = 15
        if len(target_counts) > _TOP_N:
            _top = target_counts.nlargest(_TOP_N, "Trials")
            _tail = target_counts.loc[~target_counts["Target"].isin(_top["Target"])]
            _tail_row = pd.DataFrame([{
                "Target": f"Other ({len(_tail)} antigens)",
                "Trials": int(_tail["Trials"].sum()),
            }])
            target_display = pd.concat([_top, _tail_row], ignore_index=True)
        else:
            target_display = target_counts.copy()
        target_display["Class"] = target_display["Target"].apply(_target_class)
        target_sorted = target_display.sort_values("Trials", ascending=True)

        _CLASS_COLORS = {
            "B-cell surface":      NEJM_BLUE,
            "Plasma-cell":         NEJM_AMBER,
            "Dual / multi-target": NEJM_GREEN,
            "Other / novel":       "#7c3aed",
            "Undisclosed / unclear": "#94a3b8",
        }
        _class_order = [c for c in
                        ["B-cell surface", "Plasma-cell", "Dual / multi-target",
                         "Other / novel", "Undisclosed / unclear"]
                        if c in target_sorted["Class"].unique()]

        fig6 = px.bar(
            target_sorted, x="Trials", y="Target", orientation="h",
            color="Class",
            color_discrete_map=_CLASS_COLORS,
            category_orders={"Class": _class_order},
            height=max(340, len(target_sorted) * 36 + 120),
            template="plotly_white",
            text="Trials",
        )
        fig6.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig6.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials",
            yaxis_title=None,
            margin=dict(l=160, r=56, t=48, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                title_text="",
            ),
        )
        st.plotly_chart(fig6, width='stretch', config=PUB_EXPORT)

        total_tg = target_counts["Trials"].sum()
        cd19_n = int(target_counts.loc[target_counts["Target"] == "CD19", "Trials"].sum())
        bcma_n = int(target_counts.loc[target_counts["Target"] == "BCMA", "Trials"].sum())
        dual_n = int(target_counts.loc[target_counts["Target"].str.contains("dual", case=False, na=False), "Trials"].sum())
        unspec_n = int(target_counts.loc[target_counts["Target"] == _UNCLEAR_BUCKET, "Trials"].sum())

        _tc_sorted = target_counts.sort_values("Trials", ascending=False).reset_index(drop=True)
        top_row = _tc_sorted.iloc[0]
        top_name = str(top_row["Target"])
        top_n = int(top_row["Trials"])

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Top antigen", f"{top_name} ({100*top_n/total_tg:.0f}%)")
        c2.metric("CD19-targeted", f"{cd19_n} ({100*cd19_n/total_tg:.0f}%)")
        c3.metric("BCMA-targeted", f"{bcma_n} ({100*bcma_n/total_tg:.0f}%)")
        c4.metric("Dual-target", f"{dual_n} ({100*dual_n/total_tg:.0f}%)")
        c5.metric("Undisclosed / unclear", f"{unspec_n} ({100*unspec_n/total_tg:.0f}%)")

        # Export the raw (unmerged) counts so CAR-T_unspecified vs Other_or_unknown survives.
        fig6_csv = _raw_target_counts.copy()
        fig6_csv["% of total"] = (fig6_csv["Trials"] / fig6_csv["Trials"].sum() * 100).round(1)
        _pub_caption(
            len(df_filt),
            extra="CAR-T_unspecified and Other_or_unknown are shown as a single bar here; both categories are preserved separately in the CSV export."
        )
        st.download_button("Fig 6 data (CSV)",
                           _csv_with_provenance(fig6_csv, "Fig 6 — Antigen target distribution"),
                           "fig6_target_landscape.csv", "text/csv")
    else:
        st.info("No target data available.")

    # ------------------------------------------------------------------
    # Fig 7 — Cell-therapy modality: overall distribution and evolution
    # ------------------------------------------------------------------
    _pub_header("7", "Cell-therapy modality — distribution and evolution",
                "Trials grouped by cell-therapy platform (CAR-T autologous / allogeneic, CAR-NK, CAR-Treg, in vivo CAR, other); cumulative and over time.")

    df_innov = df_filt[df_filt["StartYear"].notna()].copy()
    df_innov["StartYear"] = df_innov["StartYear"].astype(int)

    if not df_innov.empty:
        # 7a: Therapy modality — cumulative horizontal bar
        # Modality is baked in _post_process_trials; no recompute needed per rerun.
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 0.4rem;">'
            '<strong style="color: #0b1220;">7a — Cell-therapy modality distribution</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        modality_counts = (
            df_innov["Modality"].value_counts()
            .rename_axis("Modality").reset_index(name="Trials")
            .sort_values("Trials", ascending=True)
        )
        # Colour each bar by its modality
        modality_counts["Color"] = modality_counts["Modality"].map(_MODALITY_COLORS)
        fig7a = px.bar(
            modality_counts, x="Trials", y="Modality", orientation="h",
            height=max(300, len(modality_counts) * 52 + 100),
            color="Modality", color_discrete_map=_MODALITY_COLORS,
            template="plotly_white", text="Trials",
        )
        fig7a.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig7a.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials", yaxis_title=None, showlegend=False,
            margin=dict(l=110, r=56, t=24, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig7a, width='stretch', config=PUB_EXPORT)

        # 7b: Modality over time (stacked bar shows composition and inflection points)
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">7b — Modality mix by start year</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        # Prep outside the fragment: groupby runs once per filter change, not per
        # pill click. Rheum CAR-T activity before ~2019 is one or two trials per
        # year at most — restricting to ≥2019 avoids noisy early bars dominating
        # the "% of year" view.
        _mod_year_raw = (
            df_innov[df_innov["StartYear"] >= 2019]
            .groupby(["StartYear", "Modality"]).size()
            .reset_index(name="Trials")
        )
        _present_mods = [m for m in _MODALITY_ORDER if m in _mod_year_raw["Modality"].unique()]
        _mod_year_base = _mod_year_raw[_mod_year_raw["Modality"].isin(_present_mods)].copy()

        @st.fragment
        def _render_fig7b(mod_year_base: pd.DataFrame) -> None:
            _mode = st.pills(
                "Scale",
                options=["Absolute", "% of year"],
                default="Absolute",
                selection_mode="single",
                label_visibility="collapsed",
                key="fig7b_mode",
            ) or "Absolute"

            mod_year_plot = mod_year_base.copy()
            if _mode == "% of year":
                _year_tot = mod_year_plot.groupby("StartYear")["Trials"].transform("sum")
                mod_year_plot["Share"] = (mod_year_plot["Trials"] / _year_tot * 100).fillna(0)
                _y_col, _y_title, _y_tick = "Share", "Share of trials (%)", "%"
            else:
                _y_col, _y_title, _y_tick = "Trials", "Number of trials", ""

            fig7b = px.bar(
                mod_year_plot,
                x="StartYear", y=_y_col, color="Modality",
                barmode="stack", height=400, template="plotly_white",
                color_discrete_map=_MODALITY_COLORS,
                category_orders={"Modality": _MODALITY_ORDER},
                labels={"StartYear": "Start year", _y_col: _y_title},
            )
            fig7b.update_traces(marker_line_width=0, opacity=1)
            fig7b.update_layout(
                **PUB_BASE,
                margin=dict(l=64, r=36, t=24, b=130),
                xaxis=dict(
                    tickmode="linear", dtick=1, tickformat="d", showgrid=False,
                    showline=True, linewidth=1.5, linecolor=_AX_COLOR,
                    ticks="outside", ticklen=6, tickwidth=1.2,
                    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
                ),
                yaxis=dict(
                    showline=True, linewidth=1.5, linecolor=_AX_COLOR,
                    showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
                    ticks="outside", ticklen=6, tickwidth=1.2,
                    tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
                    zeroline=False,
                    ticksuffix=_y_tick,
                    range=[0, 100] if _mode == "% of year" else None,
                ),
                legend=dict(
                    orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5,
                    font=dict(size=11, color=_AX_COLOR), bgcolor="rgba(0,0,0,0)",
                    borderwidth=0,
                ),
                xaxis_title="Start year",
                yaxis_title=_y_title,
            )
            st.plotly_chart(fig7b, width='stretch', config=PUB_EXPORT)
            st.caption("Restricted to trials with start year ≥ 2019.")

        _render_fig7b(_mod_year_base)

        # Summary stats
        total_prod = len(df_innov)
        auto_n  = int((df_innov["ProductType"] == "Autologous").sum())
        allo_n  = int((df_innov["ProductType"] == "Allogeneic/Off-the-shelf").sum())
        invivo_n = int((df_innov["Modality"] == "In vivo CAR").sum())
        carnk_n = int((df_innov["Modality"] == "CAR-NK").sum())
        treg_n  = int((df_innov["Modality"] == "CAR-Treg").sum())
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Autologous",              f"{auto_n} ({100*auto_n/total_prod:.0f}%)")
        c2.metric("Allogeneic/Off-the-shelf",f"{allo_n} ({100*allo_n/total_prod:.0f}%)")
        c3.metric("CAR-NK",                  f"{carnk_n} ({100*carnk_n/total_prod:.0f}%)")
        c4.metric("CAR-Treg",                f"{treg_n} ({100*treg_n/total_prod:.0f}%)")
        c5.metric("In vivo CAR",             f"{invivo_n} ({100*invivo_n/total_prod:.0f}%)")

        fig7_csv = df_innov.groupby(["StartYear", "Modality"]).size().reset_index(name="Trials")
        _pub_caption(
            len(df_filt),
            extra="Panel counts restricted to trials with a known start year."
        )
        st.download_button("Fig 7 data (CSV)",
                           _csv_with_provenance(fig7_csv, "Fig 7 — Cell-therapy modality distribution and evolution"),
                           "fig7_modality.csv", "text/csv")
    else:
        st.info("No start year data available for innovation analysis.")


# ---------------------------------------------------------------------------
# TAB: Methods & Appendix
# ---------------------------------------------------------------------------


def _build_methods_text(prisma: dict, snapshot_date: str, n_included: int) -> str:
    query_terms_car = '"CAR T", "CAR-T", "chimeric antigen receptor", "CAR-NK", "CAR NK", "CAAR-T", "CAR-Treg"'
    query_terms_disease = (
        'lupus, nephritis, "systemic lupus erythematosus", "idiopathic inflammatory myopathy", '
        'myositis, "systemic sclerosis", scleroderma, vasculitis, "rheumatoid arthritis", sjogren, '
        '"sjogren syndrome", "igg4 related disease", behcet, "autoimmune disease", '
        '"type 1 diabetes", "graft versus host disease"'
    )
    disease_list = ", ".join(sorted(DISEASE_ENTITIES.keys()))
    n_hard = len(HARD_EXCLUDED_NCT_IDS)
    n_indication = len(EXCLUDED_INDICATION_TERMS)
    n_fetched = prisma.get("n_fetched", "N/A")
    n_dedup = prisma.get("n_after_dedup", "N/A")
    n_hard_excl = prisma.get("n_hard_excluded", "N/A")
    n_indic_excl = prisma.get("n_indication_excluded", "N/A")

    text = f"""\
METHODS
=======

Data Source and Search Strategy
--------------------------------
Clinical trial data were retrieved from the ClinicalTrials.gov public registry using the
API (v2; {BASE_URL}; accessed {snapshot_date}). A structured keyword query was applied
combining CAR-based cell therapy terms ({query_terms_car}) with autoimmune and
inflammatory disease terms ({query_terms_disease}). No restriction was placed on
study phase, recruitment status, or geographic location at the query stage. A maximum
of 2,000 records were retrieved per query execution.

Inclusion Criteria
------------------
Studies were included if they: (1) described a CAR-based cellular therapy (CAR-T
[autologous or allogeneic], CAR-NK, CAAR-T, CAR-Treg, or in vivo CAR); and
(2) targeted a systemic autoimmune or rheumatic disease. No restriction was applied
to study phase, sponsor type, or country.

Exclusion Criteria
------------------
Studies were excluded if they met any of the following criteria:
    (1) The NCT identifier appeared on a manually curated exclusion list ({n_hard}
        pre-specified identifiers) compiled upon initial review to remove studies
        retrieved by the search query but clearly outside scope (e.g., studies
        confirmed as non-CAR-T interventions on manual inspection).
    (2) Text fields (conditions, title, brief summary, interventions) contained
        one or more of {n_indication} predefined oncology or haematologic
        malignancy keywords (e.g., multiple myeloma, leukemia, lymphoma, solid
        tumour, AL amyloidosis, stem cell transplantation).
Non-oncology immune-mediated diseases outside classical rheumatology (e.g.,
multiple sclerosis, myasthenia gravis, NMOSD, pemphigus vulgaris, anti-GBM
disease, antiphospholipid syndrome, AIHA, immune thrombocytopenia, aplastic
anaemia, type 1 diabetes, Graves disease, membranous nephropathy) were retained
and classified as "Other immune-mediated" to enable landscape analysis of CAR-T
use beyond rheumatology while preserving the ability to filter by disease category.
Exclusion was applied after deduplication and before downstream classification.

Study Selection (PRISMA)
------------------------
    Records identified via database search  : {n_fetched}
    Duplicate records removed               : {prisma.get("n_duplicates_removed", "N/A")}
    Records screened                        : {n_dedup}
    Excluded — pre-specified NCT IDs        : {n_hard_excl}
    Excluded — indication keywords          : {n_indic_excl}
    Studies included in final analysis      : {n_included}

Classification
--------------
Disease entity. Each study was assigned to one of {len(DISEASE_ENTITIES)} specific
disease categories ({disease_list}), a "Basket/Multidisease" category (for trials
enrolling ≥2 distinct systemic autoimmune diseases), or "Unclassified" (for studies
describing generic autoimmune conditions without a mappable specific entity).
Connective tissue diseases are reported at the entity level: systemic sclerosis (SSc),
Sjögren syndrome, and undifferentiated/mixed CTD (CTD_other) are each distinct
categories. Assignment used hierarchical rule-based matching of normalised text drawn
from the conditions, title, brief summary, and interventions fields. Condition-field
matches took precedence over full-text matches; multi-disease trials were identified
when ≥2 systemic entities were detected within the conditions field. Generic
autoimmune phrases (e.g., "autoimmune diseases", "B-cell mediated autoimmune
disorders", "paediatric B-cell related autoimmune diseases") — which typically
reflect basket-eligible trial designs — were mapped to "Basket/Multidisease"
rather than a specific entity.

Target category. The primary antigen target was assigned from trial text using a
priority-ordered ruleset. Cell-therapy platform types were identified first:
CAR-NK constructs (terms: {", ".join(CAR_NK_TERMS)}), CAAR-T
({", ".join(CAAR_T_TERMS)}), and CAR-Treg ({", ".join(CAR_TREG_TERMS)}).
Specific antigen targets were then evaluated in order of specificity: dual
BCMA/CD70, dual CD19/BCMA, dual CD19/CD20, dual CD19/BAFF (detected by
co-presence of CD19 and BAFF terms), then single-target CD19, BCMA, CD20,
CD70, BAFF, CD6, and CD7. Studies containing CAR-related terms but no
identifiable antigen were labelled "CAR-T_unspecified". A named-product lookup
table (NAMED_PRODUCT_TARGETS in config.py) was applied as a fallback for
well-known products that omit antigen names from accessible study text fields.
Platform labels (CAR-NK, CAR-Treg, CAAR-T) are excluded from antigen-target
frequency analyses, as these denote cell-therapy modalities rather than
antigens. For the antigen-target landscape chart (Figure 6), the residual
"CAR-T_unspecified" and "Other_or_unknown" categories are collapsed into a
single "Undisclosed / unclear" bar; the two categories are preserved
separately in the accompanying CSV export.

Product type. Studies were classified as "Autologous", "Allogeneic/Off-the-shelf",
"In vivo", or "Unclear" based on presence of corresponding keywords in normalised
text. Autologous markers included: autologous, autoleucel, patient-derived.
Allogeneic markers included: allogeneic, off-the-shelf, universal CAR-T, UCART,
healthy donor, donor-derived, umbilical cord blood, cord blood. In vivo markers
included: in vivo CAR, circular RNA, lentiviral nanoparticle, mRNA-LNP. A named
product lookup table (NAMED_PRODUCT_TYPES in config.py) was applied as a fallback
when these generic markers were absent. Both lookup tables are updated iteratively
via an LLM-assisted curation loop (validate.py) that submits borderline
classifications to an independent language-model reviewer and writes structured
corrections to llm_overrides.json, which is picked up automatically by the
pipeline at load time.

Cell therapy modality. Each trial was assigned to one of eight mechanistically
distinct modality categories based on target category and product type:
  • Auto CAR-T — conventional autologous alpha-beta CAR-T cells
  • Allo CAR-T — allogeneic/off-the-shelf CAR-T (including iPSC-derived)
  • CAR-T (unclear) — CAR-T with product source not determinable from public text
  • CAR-γδ T — gamma-delta T-cell CAR constructs
  • CAR-NK — CAR-modified natural killer cells (autologous or allogeneic)
  • CAR-Treg — regulatory T-cell CAR constructs
  • CAAR-T — chimeric autoantibody receptor T cells
  • In vivo CAR — mRNA-LNP or other non-cellular in vivo CAR delivery systems

Enrollment Analysis
-------------------
Planned enrollment counts were extracted from the EnrollmentCount field (type=
"Anticipated" or "Actual") and coerced to numeric; non-numeric or missing values
were excluded from enrollment analyses (Figure 4). Geographic classification:
trials recruiting exclusively in China were labelled "China"; all others
"Non-China" (based on the Countries field). Sponsor classification used a
two-stage rule: (i) the primary signal was the ClinicalTrials.gov
`leadSponsor.class` field, mapping INDUSTRY→Industry, NIH / FED→Government,
NETWORK→Academic, and INDIV→Academic (investigator-initiated trials run
through academic centres); (ii) when the CT.gov class was OTHER, UNKNOWN, or
when OTHER_GOV was used for a non-government academic medical centre (as is
common for Chinese provincial hospitals and European public hospitals), a
name-based heuristic was applied — academic keywords (university, hospital,
institute, medical centre, Mayo/Cleveland Clinic, etc.), industry keywords
(Inc, Ltd, GmbH, Pharma, Therapeutics, Biotech, Bio), and government
keywords (NIH, VA, DoD, Ministry of Health) were evaluated in priority order.
Short alphabetic multi-token strings without organisational keywords —
including those with medical-degree markers (M.D., Ph.D.) — were recognised
as individual principal investigators and classified as Academic.
Cross-tabulation of geography × sponsor type (Fig 4c) shows median planned
enrollment and IQR (error bars) for each of the four strata.

Data Processing
---------------
All processing was performed in Python (pandas {pd.__version__}) using a custom
ETL pipeline. Text normalisation included lowercasing, Unicode normalisation
(e.g., "sjögren" → "sjogren"), and removal of non-alphanumeric characters. Term
matching used whole-word boundary matching for short terms (≤3 characters) and
substring matching for longer terms. Classification rules and term dictionaries
are versioned in the accompanying config.py file and updated via structured
curation loops applied to random samples of pipeline output; the curation-loop
export, stratified validation sample, and inter-rater agreement (Cohen's κ)
tooling are available at the bottom of this Methods & Appendix tab.

Dataset Snapshot
----------------
The frozen dataset used for all analyses was generated on {snapshot_date}. CSV
exports of the trial-level dataset (trials.csv) and site-level dataset (sites.csv)
are available via the Data tab. All analyses are reproducible from the frozen
snapshot using the published code and configuration files.
"""
    return text


def _build_ontology_df() -> pd.DataFrame:
    rows = []
    for entity, terms in DISEASE_ENTITIES.items():
        rows.append({
            "Category": "Disease entity",
            "Label": entity,
            "Matching terms (sample)": "; ".join(str(t) for t in terms[:6]) + ("…" if len(terms) > 6 else ""),
            "N terms": len(terms),
        })
    rows.append({
        "Category": "Disease entity",
        "Label": "Basket/Multidisease",
        "Matching terms (sample)": "≥2 distinct systemic autoimmune diseases matched in conditions field",
        "N terms": 0,
    })
    rows.append({
        "Category": "Generic autoimmune (→ Basket)",
        "Label": "Generic autoimmune phrases",
        "Matching terms (sample)": "; ".join(GENERIC_AUTOIMMUNE_TERMS[:5]) + "…",
        "N terms": len(GENERIC_AUTOIMMUNE_TERMS),
    })
    rows.append({
        "Category": "Other immune-mediated",
        "Label": "Other immune-mediated",
        "Matching terms (sample)": "; ".join(OTHER_IMMUNE_MEDIATED_TERMS[:6]) + "…",
        "N terms": len(OTHER_IMMUNE_MEDIATED_TERMS),
    })

    rows.append({
        "Category": "CAR core terms",
        "Label": "CAR-based intervention gate",
        "Matching terms (sample)": "; ".join(CAR_CORE_TERMS),
        "N terms": len(CAR_CORE_TERMS),
    })
    for target, terms in CAR_SPECIFIC_TARGET_TERMS.items():
        rows.append({
            "Category": "Target (antigen)",
            "Label": target,
            "Matching terms (sample)": "; ".join(terms),
            "N terms": len(terms),
        })
    for label, terms in [("CAR-NK", CAR_NK_TERMS), ("CAAR-T", CAAR_T_TERMS), ("CAR-Treg", CAR_TREG_TERMS)]:
        rows.append({
            "Category": "Target (modality)",
            "Label": label,
            "Matching terms (sample)": "; ".join(terms),
            "N terms": len(terms),
        })
    for target, products in NAMED_PRODUCT_TARGETS.items():
        rows.append({
            "Category": "Named-product target fallback",
            "Label": target,
            "Matching terms (sample)": "; ".join(products[:6]) + ("…" if len(products) > 6 else ""),
            "N terms": len(products),
        })

    rows.append({
        "Category": "Product type",
        "Label": "Autologous",
        "Matching terms (sample)": "; ".join(AUTOL_MARKERS[:5]),
        "N terms": len(AUTOL_MARKERS),
    })
    rows.append({
        "Category": "Product type",
        "Label": "Allogeneic/Off-the-shelf",
        "Matching terms (sample)": "; ".join(ALLOGENEIC_MARKERS[:5]),
        "N terms": len(ALLOGENEIC_MARKERS),
    })
    for ptype, products in NAMED_PRODUCT_TYPES.items():
        rows.append({
            "Category": "Named-product type fallback",
            "Label": ptype,
            "Matching terms (sample)": "; ".join(products[:6]) + ("…" if len(products) > 6 else ""),
            "N terms": len(products),
        })

    for term in EXCLUDED_INDICATION_TERMS[:10]:
        rows.append({
            "Category": "Oncology exclusion keyword",
            "Label": term,
            "Matching terms (sample)": term,
            "N terms": 1,
        })
    rows.append({
        "Category": "Oncology exclusion keyword",
        "Label": f"… and {len(EXCLUDED_INDICATION_TERMS) - 10} more",
        "Matching terms (sample)": "",
        "N terms": len(EXCLUDED_INDICATION_TERMS) - 10,
    })
    return pd.DataFrame(rows)


with tab_methods:
    snap_date = df["SnapshotDate"].iloc[0] if "SnapshotDate" in df.columns and not df.empty else date.today().isoformat()
    n_inc = len(df_filt)

    methods_text = _build_methods_text(prisma_counts, snap_date, n_inc)

    st.subheader("Methods section (auto-generated)")
    st.markdown(
        '<p class="small-note">Generated from config.py, pipeline.py, and the current dataset. '
        "Copy or download for use in your manuscript. Edit the journal-specific wording as needed.</p>",
        unsafe_allow_html=True,
    )
    st.text_area("Methods text", value=methods_text, height=520, label_visibility="collapsed")
    st.download_button(
        "Download methods (.txt)",
        data=methods_text,
        file_name=f"car_t_autoimmune_methods_{snap_date}.txt",
        mime="text/plain",
    )

    st.subheader("Appendix — Classification ontology")
    st.markdown(
        '<p class="small-note">Complete term dictionary used for rule-based classification. '
        "Suitable for supplementary Table S1.</p>",
        unsafe_allow_html=True,
    )
    ontology_df = _build_ontology_df()
    st.dataframe(ontology_df, width='stretch', hide_index=True,
                 column_config={
                     "Category": st.column_config.TextColumn("Category", width="medium"),
                     "Label": st.column_config.TextColumn("Label", width="medium"),
                     "Matching terms (sample)": st.column_config.TextColumn("Matching terms (sample)", width="large"),
                     "N terms": st.column_config.NumberColumn("N terms", width="small"),
                 })
    st.download_button(
        "Download ontology table (CSV)",
        data=_csv_with_provenance(
            ontology_df,
            "Classification ontology — supplementary Table S1",
            include_filters=False,
        ),
        file_name=f"car_t_classification_ontology_{snap_date}.csv",
        mime="text/csv",
    )

    st.subheader("Appendix — Hard-excluded NCT IDs")
    st.markdown(
        '<p class="small-note">Manually curated list of NCT IDs excluded regardless of keyword matching '
        "(supplementary Table S2).</p>",
        unsafe_allow_html=True,
    )
    excl_df = pd.DataFrame(sorted(HARD_EXCLUDED_NCT_IDS), columns=["NCTId"])
    excl_df["ClinicalTrials.gov link"] = excl_df["NCTId"].apply(
        lambda x: f"https://clinicaltrials.gov/study/{x}"
    )
    st.dataframe(excl_df, width='stretch', hide_index=True,
                 column_config={
                     "NCTId": st.column_config.TextColumn("NCT ID"),
                     "ClinicalTrials.gov link": st.column_config.LinkColumn("Link", display_text="Open"),
                 })
    st.download_button(
        "Download excluded NCT IDs (CSV)",
        data=_csv_with_provenance(
            excl_df[["NCTId"]],
            "Hard-excluded NCT IDs — supplementary Table S2",
            include_filters=False,
        ),
        file_name=f"car_t_excluded_nct_ids_{snap_date}.csv",
        mime="text/csv",
    )

    # ── Curation loop ──────────────────────────────────────────────────────────
    st.subheader("Curation loop — unclear / unclassified trials")
    st.markdown(
        '<p class="small-note">Download the structured CSV, paste it into Claude Code, '
        "and the assistant will propose and apply patches to config.py / pipeline.py automatically.</p>",
        unsafe_allow_html=True,
    )

    unclear_disease_mask = df_filt["DiseaseEntity"].astype(str).str.lower().isin(
        ["unclassified", "autoimmune_other", "other_or_unknown"]
    )
    unclear_target_mask = df_filt["TargetCategory"].astype(str).str.lower().isin(
        ["other_or_unknown", "car-t_unspecified", "unclassified", "unknown"]
    )
    unclear_product_mask = df_filt["ProductType"].astype(str).str.lower() == "unclear"

    df_unclear = df_filt[unclear_disease_mask | unclear_target_mask | unclear_product_mask].copy()

    if not df_unclear.empty:
        def _unclear_fields(row):
            flags = []
            if str(row.get("DiseaseEntity", "")).lower() in {"unclassified", "autoimmune_other", "other_or_unknown"}:
                flags.append("Disease")
            if str(row.get("TargetCategory", "")).lower() in {"other_or_unknown", "car-t_unspecified", "unclassified", "unknown"}:
                flags.append("Target")
            if str(row.get("ProductType", "")).lower() == "unclear":
                flags.append("Product")
            return "|".join(flags)

        df_unclear["UnclearFields"] = df_unclear.apply(_unclear_fields, axis=1)

        export_cols = [
            "NCTId", "BriefTitle", "Conditions", "Interventions",
            "DiseaseEntity", "TargetCategory", "ProductType", "UnclearFields",
            "BriefSummary",
        ]
        df_export = df_unclear[[c for c in export_cols if c in df_unclear.columns]].copy()
        # Truncate BriefSummary to 300 chars to keep CSV readable
        if "BriefSummary" in df_export.columns:
            df_export["BriefSummary"] = df_export["BriefSummary"].astype(str).str[:300]

        import io as _io
        header_lines = [
            "# CURATION_LOOP_V1",
            "# INSTRUCTION: You are Claude Code assisting with a CAR-T rheumatology trial pipeline.",
            "# For each row below, read BriefTitle / Conditions / Interventions / BriefSummary.",
            "# Propose the correct DiseaseEntity, TargetCategory, and ProductType.",
            "# Then automatically patch config.py and/or pipeline.py to capture these cases.",
            "# Allowed DiseaseEntity values: SLE, SSc, Sjogren, CTD_other, IIM, AAV, RA, IgG4-RD,",
            "#   Behcet, cGVHD, Basket/Multidisease, Other immune-mediated, Autoimmune_other,",
            "#   Unclassified, Exclude",
            "# Allowed TargetCategory values: CD19, BCMA, CD20, CD70, CD6, CD7, BAFF,",
            "#   CD19/BCMA dual, CD19/CD20 dual, CD19/BAFF dual, BCMA/CD70 dual,",
            "#   CAR-NK, CAAR-T, CAR-Treg, CAR-T_unspecified, Other_or_unknown",
            "# Allowed ProductType values: Autologous, Allogeneic/Off-the-shelf, In vivo, Unclear",
            "# UnclearFields column shows which field(s) triggered inclusion (Disease|Target|Product).",
            "#",
        ]
        buf = _io.StringIO()
        for line in header_lines:
            buf.write(line + "\n")
        df_export.to_csv(buf, index=False)
        curation_csv = buf.getvalue()

        st.dataframe(
            df_export[["NCTId", "BriefTitle", "DiseaseEntity", "TargetCategory", "ProductType", "UnclearFields"]],
            width='stretch',
            height=280,
        )
        st.caption(f"{len(df_export)} trial(s) flagged for curation")

        st.download_button(
            label=f"Download curation CSV ({len(df_export)} trials)",
            data=curation_csv,
            file_name="curation_loop.csv",
            mime="text/csv",
        )
    else:
        st.success("No unclear / unclassified trials in the current filter.")


    st.subheader("Validation sample export")
    st.markdown(
        '<p class="small-note">Stratified random sample for manual classification review. '
        "Each row includes auto-assigned labels and blank reviewer columns. "
        "Two reviewers complete independently, then compute inter-rater agreement (Cohen's κ).</p>",
        unsafe_allow_html=True,
    )

    val_n = st.slider("Target sample size", min_value=25, max_value=200, value=100, step=25)
    val_seed = st.number_input("Random seed (for reproducibility)", min_value=0, max_value=9999, value=42, step=1)

    def build_validation_sample(source_df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
        review_cols = [
            "NCTId", "BriefTitle", "Conditions", "BriefSummary",
            "DiseaseEntity", "TargetCategory", "ProductType",
            "Phase", "OverallStatus", "LeadSponsor", "Countries",
        ]
        available = [c for c in review_cols if c in source_df.columns]
        base = source_df[available].copy()

        # Stratify proportionally by DiseaseEntity; ensure each stratum has ≥1 row
        strata = base["DiseaseEntity"].fillna("Unclassified")
        counts = strata.value_counts()
        total = len(base)
        per_stratum = (counts / total * n).clip(lower=1).round().astype(int)
        # Adjust so sum == n
        diff = n - per_stratum.sum()
        if diff != 0:
            largest = per_stratum.idxmax()
            per_stratum[largest] = max(1, per_stratum[largest] + diff)

        frames = []
        import numpy as _np
        rng = _np.random.default_rng(seed)  # noqa: F841 — kept for future use
        for entity, k in per_stratum.items():
            rows = base[strata == entity]
            k = min(k, len(rows))
            frames.append(rows.sample(n=k, random_state=int(seed), replace=False))

        sample = pd.concat(frames, ignore_index=True).sample(frac=1, random_state=int(seed)).reset_index(drop=True)
        sample.insert(0, "SampleID", range(1, len(sample) + 1))

        # Blank reviewer columns
        for col in ["Reviewer1_Disease", "Reviewer1_Target", "Reviewer1_Product",
                    "Reviewer2_Disease", "Reviewer2_Target", "Reviewer2_Product", "Notes"]:
            sample[col] = ""

        return sample

    if not df_filt.empty:
        sample_df = build_validation_sample(df_filt, val_n, int(val_seed))
        st.caption(
            f"Sample: {len(sample_df)} trials from {df_filt['DiseaseEntity'].nunique()} disease strata "
            f"(seed={int(val_seed)})"
        )
        st.dataframe(
            sample_df[["SampleID", "NCTId", "DiseaseEntity", "TargetCategory", "ProductType", "BriefTitle"]],
            width='stretch',
            height=260,
            hide_index=True,
        )
        st.download_button(
            label="Download validation sample CSV",
            data=sample_df.to_csv(index=False),
            file_name=f"car_t_validation_sample_n{len(sample_df)}_seed{int(val_seed)}.csv",
            mime="text/csv",
        )
    else:
        st.info("No trials in the current filter selection.")

    st.subheader("Inter-rater agreement (Cohen's κ)")
    st.markdown(
        '<p class="small-note">Upload the completed validation CSV (both reviewers filled in) '
        "to compute Cohen's κ for Disease, Target, and Product classification.</p>",
        unsafe_allow_html=True,
    )

    def _cohen_kappa(y1: list, y2: list) -> float:
        from collections import Counter
        n = len(y1)
        if n == 0:
            return float("nan")
        p_o = sum(a == b for a, b in zip(y1, y2)) / n
        c1, c2 = Counter(y1), Counter(y2)
        all_labels = set(c1) | set(c2)
        p_e = sum((c1[k] / n) * (c2[k] / n) for k in all_labels)
        if p_e >= 1.0:
            return 1.0
        return (p_o - p_e) / (1 - p_e)

    def _kappa_label(k: float) -> str:
        if k != k:  # nan
            return "—"
        if k < 0.00:
            return "Poor (< 0)"
        if k < 0.20:
            return "Slight (< 0.20)"
        if k < 0.40:
            return "Fair (0.20–0.40)"
        if k < 0.60:
            return "Moderate (0.40–0.60)"
        if k < 0.80:
            return "Substantial (0.60–0.80)"
        return "Almost perfect (≥ 0.80)"

    uploaded = st.file_uploader(
        "Completed validation CSV",
        type="csv",
        help="Upload the filled-in validation sample with Reviewer1_* and Reviewer2_* columns.",
    )

    if uploaded is not None:
        try:
            rev_df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            rev_df = None

        if rev_df is not None:
            required = {
                "Reviewer1_Disease", "Reviewer2_Disease",
                "Reviewer1_Target", "Reviewer2_Target",
                "Reviewer1_Product", "Reviewer2_Product",
            }
            missing_cols = required - set(rev_df.columns)
            if missing_cols:
                st.error(f"Missing columns: {', '.join(sorted(missing_cols))}")
            else:
                pairs = [
                    ("Disease classification", "Reviewer1_Disease", "Reviewer2_Disease"),
                    ("Target classification", "Reviewer1_Target", "Reviewer2_Target"),
                    ("Product type classification", "Reviewer1_Product", "Reviewer2_Product"),
                ]
                kappa_rows = []
                for label, col1, col2 in pairs:
                    sub = rev_df[[col1, col2]].dropna()
                    sub = sub[(sub[col1].str.strip() != "") & (sub[col2].str.strip() != "")]
                    n_rated = len(sub)
                    n_agreed = int((sub[col1].str.strip() == sub[col2].str.strip()).sum())
                    k = _cohen_kappa(sub[col1].str.strip().tolist(), sub[col2].str.strip().tolist())
                    kappa_rows.append({
                        "Classification task": label,
                        "n rated": n_rated,
                        "n agreed": n_agreed,
                        "% agreement": f"{100 * n_agreed / n_rated:.1f}%" if n_rated else "—",
                        "κ": round(k, 3) if k == k else "—",
                        "Interpretation": _kappa_label(k),
                    })

                kappa_summary = pd.DataFrame(kappa_rows)
                st.dataframe(kappa_summary, width='stretch', hide_index=True)

                # Disagreement table for adjudication
                disagree_masks = []
                for _, col1, col2 in pairs:
                    sub = rev_df[[col1, col2]].copy()
                    sub[col1] = sub[col1].fillna("").str.strip()
                    sub[col2] = sub[col2].fillna("").str.strip()
                    both_filled = (sub[col1] != "") & (sub[col2] != "")
                    disagree_masks.append(both_filled & (sub[col1] != sub[col2]))

                disagree_mask = disagree_masks[0] | disagree_masks[1] | disagree_masks[2]
                df_disagree = rev_df[disagree_mask].copy()

                if df_disagree.empty:
                    st.success("No disagreements — perfect agreement on all rated rows.")
                else:
                    with st.expander(f"Disagreement rows ({len(df_disagree)}) — for adjudication"):
                        show_dis_cols = [c for c in [
                            "SampleID", "NCTId", "BriefTitle",
                            "DiseaseEntity", "Reviewer1_Disease", "Reviewer2_Disease",
                            "TargetCategory", "Reviewer1_Target", "Reviewer2_Target",
                            "ProductType", "Reviewer1_Product", "Reviewer2_Product",
                            "Notes",
                        ] if c in df_disagree.columns]
                        st.dataframe(df_disagree[show_dis_cols], width='stretch', hide_index=True)
                        st.download_button(
                            label="Download disagreement rows CSV",
                            data=df_disagree[show_dis_cols].to_csv(index=False),
                            file_name="car_t_validation_disagreements.csv",
                            mime="text/csv",
                        )


# ---------------------------------------------------------------------------
# About / Impressum
# ---------------------------------------------------------------------------

def _git_version() -> tuple[str, str]:
    """Return (short_sha, commit_date) for the running checkout, or a fallback."""
    repo_root = os.path.dirname(os.path.abspath(__file__))
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root, stderr=subprocess.DEVNULL,
        ).decode().strip()
        commit_date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cs"],
            cwd=repo_root, stderr=subprocess.DEVNULL,
        ).decode().strip()
        return sha or "dev", commit_date or date.today().isoformat()
    except Exception:
        return "dev", date.today().isoformat()


with tab_about:
    sha, commit_date = _git_version()
    snap_date = (
        df["SnapshotDate"].iloc[0]
        if "SnapshotDate" in df.columns and not df.empty
        else date.today().isoformat()
    )

    st.subheader("About this dashboard")
    st.markdown(
        f"""
**CAR-T Rheumatology Trials Monitor** is an interactive dashboard that tracks
CAR-T and related cell-therapy clinical trials for rheumatologic and
immune-mediated diseases, sourced from the public ClinicalTrials.gov registry.
It is designed as a research and educational resource — not a medical,
regulatory, or decision-support tool.

- **Data source**: ClinicalTrials.gov API v2 ([{BASE_URL}]({BASE_URL}))
- **Current data snapshot**: {snap_date}
- **Software version**: `{sha}` &nbsp;·&nbsp; built {commit_date}
- **Code license**: MIT (see `LICENSE` in the repository)
        """
    )

    st.markdown("---")
    st.subheader("Contact")
    st.markdown(
        f"""
<div style="
    border: 1px solid {THEME['border']};
    border-left: 3px solid {THEME['primary']};
    border-radius: 8px;
    padding: 1.1rem 1.3rem;
    background: {THEME['surface']};
    max-width: 520px;
">
    <div style="
        font-size: 1.02rem;
        font-weight: 600;
        color: {THEME['text']};
        letter-spacing: -0.01em;
        margin-bottom: 0.35rem;
    ">Peter Jeong</div>
    <div style="
        font-size: 0.88rem;
        color: {THEME['text']};
        line-height: 1.45;
    ">Universitätsklinikum Köln</div>
    <div style="
        font-size: 0.82rem;
        color: {THEME['muted']};
        line-height: 1.5;
        margin-bottom: 0.6rem;
    ">Klinik I für Innere Medizin<br>Hämatologie und Onkologie<br>Klinische Immunologie und Rheumatologie</div>
    <div style="
        font-size: 0.80rem;
        color: {THEME['muted']};
        line-height: 1.55;
        padding-top: 0.55rem;
        border-top: 1px dashed {THEME['border']};
        margin-bottom: 0.7rem;
    ">Kerpener Straße 62<br>50937 Köln, Germany</div>
    <a href="mailto:peter.jeong@uk-koeln.de" style="
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.84rem;
        font-weight: 500;
        color: {THEME['primary']};
        text-decoration: none;
        padding: 0.35rem 0.7rem;
        border: 1px solid {THEME['border']};
        border-radius: 6px;
        background: {THEME['surf2']};
        transition: background 0.12s, border-color 0.12s;
    " onmouseover="this.style.background='{THEME['surf3']}';this.style.borderColor='{THEME['primary']}'"
       onmouseout="this.style.background='{THEME['surf2']}';this.style.borderColor='{THEME['border']}'">
        ✉ peter.jeong@uk-koeln.de
    </a>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.subheader("Suggested citation")
    citation = (
        f"Jeong P. CAR-T Rheumatology Trials Monitor "
        f"(version {sha}) [Internet]. "
        f"Klinik I für Innere Medizin, Hämatologie und Onkologie, "
        f"Klinische Immunologie und Rheumatologie, "
        f"Universitätsklinikum Köln; {date.today().year} "
        f"[cited {date.today().isoformat()}]. "
        f"DOI: 10.5281/zenodo.19713049. "
        f"Available from: https://rheum-car-t-trial-monitor.streamlit.app"
    )
    st.code(citation, language="text")
    st.caption(
        "Vancouver-style citation. "
        "DOI: [10.5281/zenodo.19713049](https://doi.org/10.5281/zenodo.19713049)"
    )

    st.markdown("---")
    st.subheader("Scientific disclaimer")
    st.markdown(
        """
Trial classifications (disease entity, antigen target, cell-therapy modality,
product type, geography) are produced by an automated pipeline combining
keyword matching, curated lookup tables, and — for flagged ambiguous cases —
large-language-model-assisted review. Despite careful curation, errors,
omissions, and misclassifications are possible.

For any definitive scientific, clinical, or regulatory purpose, consult the
original trial records on ClinicalTrials.gov. This dashboard does not provide
medical advice and must not be used to guide individual patient care.
        """
    )

    with st.expander("Impressum · Datenschutz · Haftungsausschluss", expanded=False):
        st.markdown(
            f"""
#### Angaben gemäß § 5 TMG

**Verantwortlich für den Inhalt im Sinne des § 18 Abs. 2 MStV**

Anbieter dieser Webanwendung: https://rheum-car-t-trial-monitor.streamlit.app

Peter Jeong
Universitätsklinikum Köln
Klinik I für Innere Medizin
Hämatologie und Onkologie
Klinische Immunologie und Rheumatologie
Kerpener Straße 62
50937 Köln
Germany

E-Mail: peter.jeong@uk-koeln.de

---

#### Haftung für Inhalte

Die Inhalte dieses Dashboards wurden mit größtmöglicher Sorgfalt erstellt. Für
die Richtigkeit, Vollständigkeit und Aktualität der Inhalte kann jedoch keine
Gewähr übernommen werden. Als Diensteanbieter bin ich gemäß § 7 Abs. 1 TMG für
eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich.
Nach §§ 8 bis 10 TMG bin ich als Diensteanbieter jedoch nicht verpflichtet,
übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach
Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen.

Die hier bereitgestellten Klassifikationen, Grafiken und aggregierten
Statistiken dienen ausschließlich wissenschaftlichen und edukativen Zwecken.
Sie stellen **keine medizinische Beratung** dar und sind nicht zur
Unterstützung individueller klinischer Entscheidungen geeignet.

#### Haftung für Links

Dieses Dashboard enthält Links zu externen Webseiten Dritter
(insbesondere ClinicalTrials.gov), auf deren Inhalte ich keinen Einfluss habe.
Deshalb kann ich für diese fremden Inhalte auch keine Gewähr übernehmen. Für
die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder
Betreiber der Seiten verantwortlich.

#### Urheberrecht

Der Quellcode dieser Anwendung steht unter der MIT-Lizenz. Die zugrunde
liegenden Studiendaten stammen aus dem öffentlichen Register
ClinicalTrials.gov (U.S. National Library of Medicine) und unterliegen deren
Nutzungsbedingungen.

---

#### Datenschutz (kurz)

Diese Anwendung erhebt selbst **keine personenbezogenen Daten** von Nutzerinnen
und Nutzern. Es werden keine Tracking-Cookies, keine Analytics-Dienste und keine
Drittanbieter-Einbettungen mit Tracking-Funktion verwendet.

**Hosting-Anbieter:** Die Anwendung wird auf **Streamlit Community Cloud**
betrieben, einem Dienst der Snowflake Inc., 106 East Babcock Street, Suite 3A,
Bozeman, MT 59715, USA. Beim Aufruf der Anwendung werden technisch
notwendige Verbindungsdaten (IP-Adresse, Zeitstempel, User-Agent)
vorübergehend durch den Hosting-Anbieter verarbeitet. Ein Datentransfer in die
USA findet statt; dieser stützt sich auf das EU-US Data Privacy Framework
sowie — ergänzend — auf Standardvertragsklauseln. Details in der
Datenschutzerklärung von Streamlit / Snowflake:

- [streamlit.io/privacy-policy](https://streamlit.io/privacy-policy)
- [snowflake.com/privacy-notice](https://www.snowflake.com/privacy-notice/)

**Datenquelle:** Die Anwendung ruft Studiendaten über die öffentliche API von
ClinicalTrials.gov ab ([{BASE_URL}]({BASE_URL})). Die Nutzung dieser
API-Schnittstelle unterliegt den Bedingungen der U.S. National Library of
Medicine. Hierbei werden keine nutzerbezogenen Daten übermittelt.

**Rechte der Nutzerinnen und Nutzer:** Sofern im Einzelfall doch
personenbezogene Daten verarbeitet werden sollten, bestehen die Rechte auf
Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16 DSGVO), Löschung
(Art. 17 DSGVO), Einschränkung der Verarbeitung (Art. 18 DSGVO), Widerspruch
(Art. 21 DSGVO) sowie das Recht auf Beschwerde bei einer Aufsichtsbehörde
(Art. 77 DSGVO). Zuständige Aufsichtsbehörde: Landesbeauftragte für
Datenschutz und Informationsfreiheit Nordrhein-Westfalen
([ldi.nrw.de](https://www.ldi.nrw.de)).

---

#### Versionierung

- **Software-Version (git commit):** `{sha}`
- **Build-Datum:** {commit_date}
- **Datensatz-Snapshot:** {snap_date}
- **Datenquelle:** ClinicalTrials.gov API v2

Stand: {date.today().isoformat()}
            """
        )
