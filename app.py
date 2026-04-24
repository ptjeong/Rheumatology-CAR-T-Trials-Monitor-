import os
import re
import subprocess
import streamlit as st
import pandas as pd
import plotly.express as px

from datetime import date, datetime, timezone

from pipeline import (
    build_all_from_api,
    load_snapshot,
    list_snapshots,
    save_snapshot,
    BASE_URL,
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


def _modality(row) -> str:
    t = str(row.get("TargetCategory", ""))
    p = str(row.get("ProductType", ""))
    # γδ T detection from title / summary text
    _txt = " ".join([
        str(row.get("BriefTitle", "")),
        str(row.get("BriefSummary", "")),
        str(row.get("Interventions", "")),
    ]).lower()
    has_gd_t = (
        "γδ" in _txt or "gamma delta" in _txt or "gamma-delta" in _txt
        or "-gdt" in _txt or " gdt " in _txt
    )
    has_nk = "car-nk" in _txt or "car nk" in _txt or "lucar-dks1" in _txt
    if t == "CAR-NK" or has_nk:
        return "CAR-NK"
    if t == "CAAR-T":
        return "CAAR-T"
    if t in ("CAR-Treg", "CD6"):
        return "CAR-Treg"
    if has_gd_t:
        return "CAR-γδ T"
    if p == "In vivo":
        return "In vivo CAR"
    if p == "Autologous":
        return "Auto CAR-T"
    if p == "Allogeneic/Off-the-shelf":
        return "Allo CAR-T"
    return "CAR-T (unclear)"


_PLATFORM_LABELS = {"CAR-NK", "CAR-Treg", "CAAR-T", "CAR-γδ T"}

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


@st.cache_data(ttl=60 * 60)
def load_live(max_records: int = 2000, statuses: tuple[str, ...] = ()) -> tuple:
    statuses_list = list(statuses) if statuses else None
    return build_all_from_api(max_records=max_records, statuses=statuses_list)


@st.cache_data
def load_frozen(snapshot_date: str) -> tuple:
    return load_snapshot(snapshot_date)


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
            Systematic landscape analysis of CAR-T, CAR-NK, CAAR-T, and CAR-Treg trials in
            systemic autoimmune diseases — disease mapping, target classification,
            product-type annotation, and Germany-specific site tracking.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("Data source")

available_snapshots = list_snapshots()
data_source = st.sidebar.radio(
    "Source",
    ["Live (ClinicalTrials.gov API)", "Frozen snapshot"],
    index=0 if not available_snapshots else 0,
)

prisma_counts: dict = {}

if data_source == "Frozen snapshot":
    if not available_snapshots:
        st.sidebar.warning("No snapshots found. Pull live data and save a snapshot first.")
        st.stop()
    selected_snapshot = st.sidebar.selectbox("Snapshot date", available_snapshots)
    with st.spinner(f"Loading frozen snapshot {selected_snapshot}..."):
        df, df_sites, prisma_counts = load_frozen(selected_snapshot)
    st.sidebar.caption(f"Loaded: {selected_snapshot} ({len(df)} trials)")
else:
    st.sidebar.header("Data pull")
    selected_statuses = st.sidebar.multiselect(
        "Statuses to pull",
        STATUS_OPTIONS,
        default=["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"],
    )
    try:
        with st.spinner("Fetching and processing ClinicalTrials.gov data..."):
            df, df_sites, prisma_counts = load_live(statuses=tuple(selected_statuses))
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
            st.sidebar.info(
                f"Loaded frozen snapshot **{fallback}** (fallback). "
                "Switch the source toggle above to 'Frozen snapshot' for intentional offline use."
            )
        else:
            st.error(
                "Cannot load data: the ClinicalTrials.gov API is unreachable and no local "
                "snapshots exist. Please try again later or check the API status at "
                "https://clinicaltrials.gov/."
            )
            st.stop()

    if st.sidebar.button("Save snapshot"):
        statuses_list = selected_statuses if selected_statuses else None
        snap_date = save_snapshot(df, df_sites, prisma_counts, statuses=statuses_list)
        st.sidebar.success(f"Saved snapshot: {snap_date}")
        st.cache_data.clear()

df = add_phase_columns(df)

if df.empty:
    st.error("No studies were returned. Try broadening the status filters.")
    st.stop()

# Compute modality column on full df before any filtering
df["Modality"] = df.apply(_modality, axis=1)

st.sidebar.header("Filters")

# Disease entity (multi-select) — based on DiseaseEntities so basket trials appear under each disease
_all_disease_entities: set[str] = set()
for _val in df["DiseaseEntities"].dropna():
    for _e in str(_val).split("|"):
        _e = _e.strip()
        if _e:
            _all_disease_entities.add(_e)
disease_options = sorted(_all_disease_entities)
disease_sel = st.sidebar.multiselect(
    "Disease entity",
    options=disease_options,
    default=disease_options,
    help="Basket/multi-disease trials appear under every disease they enrol.",
)

# Trial design (single disease vs basket)
design_options = sorted(df["TrialDesign"].dropna().unique().tolist())
design_sel = st.sidebar.multiselect(
    "Trial design",
    options=design_options,
    default=design_options,
    help="Filter to single-disease trials only or include basket/multi-disease trials.",
)

# Phase (multi-select, displayed as labels)
phase_options = [PHASE_LABELS[p] for p in PHASE_ORDER if p in set(df["PhaseNormalized"].astype(str))]
phase_sel = st.sidebar.multiselect(
    "Phase",
    options=phase_options,
    default=phase_options,
)

# Target category (multi-select) — antigen targets only; platform labels live in modality filter
target_options = sorted(
    t for t in df["TargetCategory"].dropna().unique()
    if t not in _PLATFORM_LABELS
)
target_sel = st.sidebar.multiselect(
    "Antigen target",
    options=target_options,
    default=target_options,
)

# Overall status (multi-select)
status_options = sorted(df["OverallStatus"].dropna().unique().tolist())
status_sel = st.sidebar.multiselect(
    "Overall status",
    options=status_options,
    default=status_options,
)

# Product type (multi-select)
product_options = sorted(df["ProductType"].dropna().unique().tolist())
product_sel = st.sidebar.multiselect(
    "Product type",
    options=product_options,
    default=product_options,
)

# Cell therapy modality (multi-select)
modality_options = [m for m in _MODALITY_ORDER if m in set(df["Modality"])]
modality_sel = st.sidebar.multiselect(
    "Cell therapy modality",
    options=modality_options,
    default=modality_options,
)

# Country (multi-select)
all_countries = set()
for cs in df["Countries"].dropna():
    for c in str(cs).split("|"):
        c = c.strip()
        if c:
            all_countries.add(c)
country_options = sorted(all_countries)
country_sel = st.sidebar.multiselect(
    "Country",
    options=country_options,
    default=country_options,
)


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
    if data_source == "Frozen snapshot":
        lines.append(f"# Data source: ClinicalTrials.gov API v2 — frozen snapshot {snap}")
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
    st.dataframe(quality_df, use_container_width=True, hide_index=True)
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

_df_filt = df[mask].copy()
df_filt = add_phase_columns(_df_filt)
df_filt["OverallStatus"] = df_filt["OverallStatus"].fillna("Unknown")
df_filt["NCTLink"] = df_filt["NCTId"].apply(
    lambda x: f"https://clinicaltrials.gov/study/{x}" if pd.notna(x) else None
)

germany_sites_all = pd.DataFrame()
germany_open_sites = pd.DataFrame()
germany_study_view = pd.DataFrame()

if not df_sites.empty:
    germany_sites_all = df_sites[df_sites["Country"].fillna("").str.lower() == "germany"].copy()
    germany_open_sites = germany_sites_all[
        germany_sites_all["SiteStatus"].fillna("").str.upper().isin(OPEN_SITE_STATUSES)
    ].copy()
    germany_open_sites = germany_open_sites[germany_open_sites["NCTId"].isin(df_filt["NCTId"])].copy()

    if not germany_open_sites.empty:
        germany_trials = df_filt[df_filt["NCTId"].isin(germany_open_sites["NCTId"])].copy()

        germany_study_view = (
            germany_open_sites.groupby("NCTId", as_index=False)
            .agg(
                GermanCities=("City", uniq_join),
                GermanSiteStatuses=("SiteStatus", uniq_join),
            )
        )

        germany_study_view = germany_study_view.merge(
            germany_trials[
                [
                    "NCTId",
                    "BriefTitle",
                    "DiseaseEntity",
                    "TargetCategory",
                    "ProductType",
                    "Phase",
                    "PhaseNormalized",
                    "PhaseOrdered",
                    "PhaseLabel",
                    "OverallStatus",
                    "LeadSponsor",
                ]
            ].drop_duplicates(subset=["NCTId"]),
            on="NCTId",
            how="left",
        )

        germany_study_view["NCTLink"] = germany_study_view["NCTId"].apply(
            lambda x: f"https://clinicaltrials.gov/study/{x}" if pd.notna(x) else None
        )
        germany_study_view["Phase"] = germany_study_view["PhaseLabel"].fillna(germany_study_view["Phase"])

        germany_study_view = germany_study_view[
            [
                "NCTId",
                "NCTLink",
                "BriefTitle",
                "DiseaseEntity",
                "TargetCategory",
                "ProductType",
                "Phase",
                "PhaseNormalized",
                "PhaseOrdered",
                "OverallStatus",
                "LeadSponsor",
                "GermanCities",
                "GermanSiteStatuses",
            ]
        ].sort_values(["PhaseOrdered", "DiseaseEntity", "NCTId"], na_position="last")

total_trials = len(df_filt)
recruiting_trials = int(df_filt["OverallStatus"].isin(["RECRUITING", "NOT_YET_RECRUITING"]).sum())
german_trials_count = germany_study_view["NCTId"].nunique() if not germany_study_view.empty else 0
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

tab_overview, tab_geo, tab_data, tab_pub, tab_methods, tab_about = st.tabs(
    ["Overview", "Geography / Map", "Data", "Publication Figures", "Methods & Appendix", "About"]
)

with tab_overview:
    if prisma_counts:
        st.subheader("Study selection (PRISMA flow)")
        prisma_rows = [
            {"Step": "Records identified via ClinicalTrials.gov API", "n": prisma_counts.get("n_fetched", "—"), "Note": ""},
            {"Step": "Duplicate records removed", "n": prisma_counts.get("n_duplicates_removed", "—"), "Note": "Same NCT ID"},
            {"Step": "Records screened", "n": prisma_counts.get("n_after_dedup", "—"), "Note": ""},
            {"Step": "Excluded: pre-specified NCT IDs", "n": prisma_counts.get("n_hard_excluded", "—"), "Note": "Manually curated exclusion list"},
            {"Step": "Excluded: oncology / haematologic malignancy indications", "n": prisma_counts.get("n_indication_excluded", "—"), "Note": "Keyword-based exclusion"},
            {"Step": "Studies included in analysis", "n": prisma_counts.get("n_included", "—"), "Note": "Final dataset"},
        ]
        prisma_df = pd.DataFrame(prisma_rows)
        st.dataframe(
            prisma_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Step": st.column_config.TextColumn("Step", width="large"),
                "n": st.column_config.NumberColumn("n", width="small"),
                "Note": st.column_config.TextColumn("Note", width="medium"),
            },
        )

    # Row 1
    ov_r1c1, ov_r1c2 = st.columns(2)

    with ov_r1c1:
        st.subheader("Trials by disease entity")
        st.caption("Basket/multi-disease trials are counted once per disease they enrol.")
        _disease_vals = split_pipe_values(df_filt["DiseaseEntities"])
        counts_disease = (
            pd.DataFrame({"DiseaseEntity": _disease_vals})["DiseaseEntity"]
            .value_counts()
            .rename_axis("DiseaseEntity")
            .reset_index(name="Count")
        ) if _disease_vals else pd.DataFrame(columns=["DiseaseEntity", "Count"])
        if not counts_disease.empty:
            st.plotly_chart(make_bar(counts_disease, "DiseaseEntity", "Count", color=THEME["primary"], height=380), use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")

    with ov_r1c2:
        st.subheader("Trials by antigen target")
        counts_target = (
            df_filt.loc[~df_filt["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("TargetCategory")
            .reset_index(name="Count")
        )
        if not counts_target.empty:
            st.plotly_chart(make_bar(counts_target, "TargetCategory", "Count", color=THEME["primary"], height=380), use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")

    # Row 2
    ov_r2c1, ov_r2c2 = st.columns(2)

    with ov_r2c1:
        st.subheader("Trials by phase")
        counts_phase = (
            df_filt.groupby("PhaseOrdered", observed=False)
            .size()
            .reset_index(name="Count")
        )
        counts_phase["PhaseNormalized"] = counts_phase["PhaseOrdered"].astype(str)
        counts_phase["Phase"] = counts_phase["PhaseNormalized"].map(PHASE_LABELS)
        counts_phase = counts_phase[counts_phase["Count"] > 0].copy()
        counts_phase["Phase"] = pd.Categorical(
            counts_phase["Phase"],
            categories=[PHASE_LABELS[p] for p in PHASE_ORDER],
            ordered=True,
        )
        counts_phase = counts_phase.sort_values("Phase")
        if not counts_phase.empty:
            fig_phase = make_bar(counts_phase, "Phase", "Count", color=THEME["primary"], height=320)
            fig_phase.update_xaxes(categoryorder="array", categoryarray=[PHASE_LABELS[p] for p in PHASE_ORDER])
            st.plotly_chart(fig_phase, use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")

    with ov_r2c2:
        st.subheader("Trials by start year")
        start_years = pd.to_numeric(df_filt["StartYear"], errors="coerce").dropna().astype(int)
        counts_year = (
            start_years
            .value_counts()
            .sort_index()
            .rename_axis("StartYear")
            .reset_index(name="Count")
        )
        if not counts_year.empty:
            fig_year = px.line(
                counts_year,
                x="StartYear",
                y="Count",
                markers=True,
                height=320,
                template="plotly_white",
            )
            fig_year.update_traces(line_color=THEME["primary"], marker_color=THEME["primary"], line_width=2.5)
            fig_year.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(color=THEME["text"]),
                xaxis_title=None,
                yaxis_title=None,
            )
            fig_year.update_xaxes(
                color=THEME["muted"],
                tickmode="linear",
                dtick=1,
                tickformat="d",
            )
            fig_year.update_yaxes(gridcolor=THEME["grid"], color=THEME["muted"])
            st.plotly_chart(fig_year, use_container_width=True)
        else:
            st.info("No trials with a valid start year for the current filter selection.")

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

        fig_world = px.choropleth(
            country_counts,
            locations="Country",
            locationmode="country names",
            color="Count",
            color_continuous_scale=[
                [0.00, "#dbeafe"],
                [0.30, "#93c5fd"],
                [0.55, "#3b82f6"],
                [0.75, "#1d4ed8"],
                [1.00, "#1e3a8a"],
            ],
            projection="natural earth",
            template="plotly_white",
        )
        fig_world.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=THEME["text"]),
            geo=dict(
                bgcolor="rgba(0,0,0,0)",
                lakecolor="#ddeeff",
                landcolor="#e9ecef",
                showframe=False,
                showcoastlines=False,
                showcountries=True,
                countrycolor="rgba(0,0,0,0.12)",
            ),
            coloraxis_colorbar_title="No. of trials",
        )
        st.plotly_chart(fig_world, use_container_width=True)

        c1, c2 = st.columns([1.15, 0.85])
        with c1:
            st.markdown("**Country counts**")
            st.dataframe(country_counts, use_container_width=True, height=320, hide_index=True)
        with c2:
            st.markdown("**Top countries**")
            st.plotly_chart(
                make_bar(country_counts.head(12), "Country", "Count", height=320, color=THEME["primary"]),
                use_container_width=True,
            )
    else:
        st.info("No country information available for the current filter selection.")

    st.subheader("Germany by city")

    if germany_open_sites.empty:
        st.info("No open or recruiting German study sites found in the current result set.")
    else:
        germany_city_counts = (
            germany_open_sites["City"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("City")
            .reset_index(name="OpenSiteCount")
            .sort_values(["OpenSiteCount", "City"], ascending=[False, True], na_position="last")
            .reset_index(drop=True)
        )

        g1, g2, g3 = st.columns(3)
        with g1:
            metric_card("German site rows", len(germany_open_sites), "Recruiting / active German site rows")
        with g2:
            metric_card("German cities", germany_open_sites["City"].dropna().nunique(), "Cities with open sites")
        with g3:
            metric_card(
                "German unique trials",
                germany_study_view["NCTId"].nunique() if not germany_study_view.empty else 0,
                "Unique NCT IDs with at least one open German site",
            )

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("**Open sites by city**")
            st.plotly_chart(
                make_bar(germany_city_counts, "City", "OpenSiteCount",
                         height=min(300, max(180, len(germany_city_counts) * 20 + 48)), color=THEME["primary"]),
                use_container_width=True,
            )
        with c2:
            st.markdown("**Germany city table**")
            city_event = st.dataframe(
                germany_city_counts,
                use_container_width=True,
                height=min(300, max(180, len(germany_city_counts) * 20 + 48)),
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="germany_city_table",
            )

        if city_event and city_event.selection.rows:
            selected_idx = city_event.selection.rows[0]
            selected_city = germany_city_counts.iloc[selected_idx]["City"]

            st.markdown(f"### Trials with open German sites in {selected_city}")

            city_nct_ids = (
                germany_open_sites.loc[
                    germany_open_sites["City"].fillna("Unknown") == selected_city,
                    "NCTId",
                ]
                .dropna()
                .unique()
            )

            city_trial_view = germany_study_view[
                germany_study_view["NCTId"].isin(city_nct_ids)
            ].copy()

            city_trial_view = city_trial_view.sort_values(
                ["PhaseOrdered", "DiseaseEntity", "NCTId"],
                ascending=[True, True, True],
                na_position="last",
            )

            if city_trial_view.empty:
                st.info(f"No study rows found for {selected_city}.")
            else:
                st.dataframe(
                    city_trial_view[
                        [
                            "NCTId",
                            "NCTLink",
                            "BriefTitle",
                            "DiseaseEntity",
                            "TargetCategory",
                            "ProductType",
                            "Phase",
                            "OverallStatus",
                            "LeadSponsor",
                            "GermanCities",
                            "GermanSiteStatuses",
                        ]
                    ],
                    use_container_width=True,
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
                        "GermanCities": st.column_config.TextColumn("German cities", width="large"),
                        "GermanSiteStatuses": st.column_config.TextColumn("German site status", width="medium"),
                    },
                )
        else:
            st.caption("Select a city row in the table to open the related trial list below.")

with tab_data:
    st.subheader("Trial table")

    show_cols = [
        "NCTId",
        "NCTLink",
        "BriefTitle",
        "DiseaseEntities",
        "TrialDesign",
        "TargetCategory",
        "ProductType",
        "Phase",
        "OverallStatus",
        "StartYear",
        "Countries",
        "LeadSponsor",
    ]

    table_df = df_filt.sort_values(["PhaseOrdered", "DiseaseEntity", "NCTId"], ascending=[True, True, True]).copy()
    table_df["Phase"] = table_df["PhaseLabel"]
    table_df["OverallStatus"] = table_df["OverallStatus"].map(STATUS_DISPLAY).fillna(table_df["OverallStatus"])

    st.dataframe(
        table_df[show_cols],
        use_container_width=True,
        height=460,
        hide_index=True,
        column_config={
            "NCTId": st.column_config.TextColumn("NCT ID"),
            "NCTLink": st.column_config.LinkColumn("Trial link", display_text="Open trial"),
            "BriefTitle": st.column_config.TextColumn("Title", width="large"),
            "DiseaseEntities": st.column_config.TextColumn("Disease(s)", width="medium"),
            "TrialDesign": st.column_config.TextColumn("Trial design", width="small"),
            "TargetCategory": st.column_config.TextColumn("Target"),
            "ProductType": st.column_config.TextColumn("Product"),
            "Phase": st.column_config.TextColumn("Phase"),
            "OverallStatus": st.column_config.TextColumn("Status"),
            "StartYear": st.column_config.NumberColumn("Start year", format="%d"),
            "Countries": st.column_config.TextColumn("Countries", width="large"),
            "LeadSponsor": st.column_config.TextColumn("Lead sponsor", width="medium"),
        },
    )

    st.subheader("Studies active in Germany")

    if germany_study_view.empty:
        st.info("No open or recruiting German study sites found in the current result set.")
    else:
        germany_export_view = germany_study_view.copy()
        germany_export_view["OverallStatus"] = germany_export_view["OverallStatus"].map(STATUS_DISPLAY).fillna(germany_export_view["OverallStatus"])
        germany_export_view = germany_export_view.sort_values(["PhaseOrdered", "DiseaseEntity", "NCTId"], na_position="last")
        st.dataframe(
            germany_export_view[
                [
                    "NCTId",
                    "NCTLink",
                    "BriefTitle",
                    "DiseaseEntity",
                    "TargetCategory",
                    "ProductType",
                    "Phase",
                    "OverallStatus",
                    "LeadSponsor",
                    "GermanCities",
                    "GermanSiteStatuses",
                ]
            ],
            use_container_width=True,
            height=380,
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
                "GermanCities": st.column_config.TextColumn("German cities", width="large"),
                "GermanSiteStatuses": st.column_config.TextColumn("German site status", width="medium"),
            },
        )

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            label="Download filtered trial data as CSV",
            data=_csv_with_provenance(df_filt, "Filtered trial list"),
            file_name="car_t_rheumatology_trials_filtered.csv",
            mime="text/csv",
        )
    with d2:
        if not df_sites.empty:
            st.download_button(
                label="Download site-level data as CSV",
                data=_csv_with_provenance(df_sites, "Site-level data"),
                file_name="car_t_rheumatology_sites.csv",
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
            "# Allowed DiseaseEntity values: SLE, SSc, Sjogren, CTD_other, IIM, AAV, RA, IgG4-RD, Behcet,",
            "#   Other immune-mediated, Unclassified",
            "# Allowed TargetCategory values: CD19, BCMA, CD19/BCMA dual, CD19/BAFF dual,",
            "#   CD20, CD6, CD7, CAR-NK, CAAR-T, CAR-Treg, CAR-T_unspecified, Other_or_unknown",
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
            use_container_width=True,
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
            use_container_width=True,
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
                st.dataframe(kappa_summary, use_container_width=True, hide_index=True)

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
                        st.dataframe(df_disagree[show_dis_cols], use_container_width=True, hide_index=True)
                        st.download_button(
                            label="Download disagreement rows CSV",
                            data=df_disagree[show_dis_cols].to_csv(index=False),
                            file_name="car_t_validation_disagreements.csv",
                            mime="text/csv",
                        )

# ---------------------------------------------------------------------------
# TAB: Publication Figures
# ---------------------------------------------------------------------------

# Unified visualization palette — coordinated, scientific-grade
NEJM = ["#1d4ed8", "#dc2626", "#d97706", "#059669", "#4f46e5", "#0891b2", "#0d9488", "#64748b"]
NEJM_BLUE    = "#1d4ed8"   # blue-700 (primary)
NEJM_RED     = "#dc2626"   # red-600
NEJM_AMBER   = "#d97706"   # amber-600
NEJM_GREEN   = "#059669"   # emerald-600
NEJM_PURPLE  = "#4f46e5"   # indigo-600

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


with tab_pub:
    st.markdown(
        '<p class="small-note" style="color:#555">Publication-ready figures with white backgrounds. '
        "Use the camera icon (▷ toolbar) on each chart to download a high-resolution PNG. "
        "Each section also provides the underlying data as CSV.</p>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Fig 1 — Temporal trends
    # ------------------------------------------------------------------
    years_raw = pd.to_numeric(df_filt["StartYear"], errors="coerce").dropna().astype(int)
    _yr_min = int(years_raw.min()) if len(years_raw) else None
    _yr_max = int(years_raw.max()) if len(years_raw) else None
    _fig1_sub = (
        f"CAR-T and related cell therapies in autoimmune disease, {_yr_min}–{_yr_max}."
        if _yr_min is not None
        else "CAR-T and related cell therapies in autoimmune disease."
    )
    _pub_header("1", "Trials by start year", _fig1_sub)
    fig1_data = (
        years_raw.value_counts().sort_index()
        .rename_axis("StartYear").reset_index(name="Trials")
    )

    if not fig1_data.empty:
        fig1 = px.line(
            fig1_data, x="StartYear", y="Trials", markers=True, height=420, template="plotly_white",
        )
        fig1.update_traces(
            line_color=NEJM_BLUE, line_width=2.5,
            marker=dict(color=NEJM_BLUE, size=8, line=dict(color="white", width=1.5)),
        )
        fig1.update_layout(
            **PUB_LAYOUT,
            xaxis_title="Start year",
            yaxis_title="Number of trials",
        )
        fig1.update_xaxes(tickmode="linear", dtick=1, tickformat="d", showgrid=False)
        fig1.update_yaxes(rangemode="tozero")
        # Mark the current (incomplete) year so readers don't misread a dip as a trend
        _current_year = pd.Timestamp.now().year
        if int(fig1_data["StartYear"].max()) >= _current_year:
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
        st.plotly_chart(fig1, use_container_width=True, config=PUB_EXPORT)

        # Key statistics
        total_t = len(df_filt)
        peak_year = int(fig1_data.loc[fig1_data["Trials"].idxmax(), "StartYear"])
        peak_n = int(fig1_data["Trials"].max())
        first_row = fig1_data.iloc[0]
        last_row = fig1_data.iloc[-1]
        cagr = _cagr(int(first_row["Trials"]), int(last_row["Trials"]), int(last_row["StartYear"] - first_row["StartYear"]))
        cagr_str = f"{cagr * 100:.1f}%" if cagr is not None else "N/A"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total included trials", total_t)
        c2.metric("Year range", f"{int(first_row['StartYear'])}–{int(last_row['StartYear'])}")
        c3.metric("Peak year", f"{peak_year} (n={peak_n})")
        c4.metric("CAGR (first → last year)", cagr_str)

        _pub_caption(len(df_filt))
        st.download_button("Fig 1 data (CSV)",
                           _csv_with_provenance(fig1_data, "Fig 1 — Temporal trends"),
                           "fig1_temporal_trends.csv", "text/csv")
    else:
        st.info("No start year data available.")

    # ------------------------------------------------------------------
    # Fig 2 — Phase distribution
    # ------------------------------------------------------------------
    _pub_header("2", "Distribution of clinical trial phases",
                "Number of trials at each clinical development stage.")

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
        fig2 = pub_bar(phase_counts, "Phase", "Trials", color=NEJM_BLUE,
                       title="Distribution of Clinical Trial Phases", xlab="Phase")
        fig2.update_xaxes(categoryorder="array", categoryarray=[PHASE_LABELS[p] for p in PHASE_ORDER])
        st.plotly_chart(fig2, use_container_width=True, config=PUB_EXPORT)

        total_ph = phase_counts["Trials"].sum()
        early = phase_counts.loc[phase_counts["Phase"].isin(["Early Phase I", "Phase I"]), "Trials"].sum()
        late = phase_counts.loc[phase_counts["Phase"].isin(["Phase II", "Phase II/III", "Phase III"]), "Trials"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Early-phase (I / Early I)", f"{early} ({100*early/total_ph:.0f}%)")
        c2.metric("Late-phase (II+)", f"{late} ({100*late/total_ph:.0f}%)")
        c3.metric("Phase I/II (hybrid)", str(int(phase_counts.loc[phase_counts["Phase"] == "Phase I/II", "Trials"].sum())))

        fig2_csv = phase_counts[["Phase", "Trials"]].copy()
        fig2_csv["% of total"] = (fig2_csv["Trials"] / total_ph * 100).round(1)
        _pub_caption(len(df_filt))
        st.download_button("Fig 2 data (CSV)",
                           _csv_with_provenance(fig2_csv, "Fig 2 — Phase distribution"),
                           "fig2_phase_distribution.csv", "text/csv")
    else:
        st.info("No phase data available.")

    # ------------------------------------------------------------------
    # Fig 3 — Target landscape
    # ------------------------------------------------------------------
    _pub_header("3", "Antigen target distribution",
                "Trials by primary CAR antigen target. Cell-therapy platforms (CAR-NK, CAR-Treg, CAAR-T, CAR-γδ T) are shown in Figure 6.")

    # CAR-NK / CAR-Treg / CAAR-T / CAR-γδ T are cell therapy platforms, not antigen targets —
    # they belong in the modality figure (Fig 6). Exclude them here.
    target_counts = (
        df_filt.loc[~df_filt["TargetCategory"].isin(_PLATFORM_LABELS), "TargetCategory"]
        .fillna("Unknown").value_counts()
        .rename_axis("Target").reset_index(name="Trials")
    )

    if not target_counts.empty:
        target_sorted = target_counts.sort_values("Trials", ascending=True)
        fig3 = px.bar(
            target_sorted, x="Trials", y="Target", orientation="h", height=max(340, len(target_sorted) * 36 + 100),
            color_discrete_sequence=[NEJM_BLUE], template="plotly_white",
            text="Trials",
        )
        fig3.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig3.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials",
            yaxis_title=None,
            showlegend=False,
            margin=dict(l=160, r=56, t=24, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig3, use_container_width=True, config=PUB_EXPORT)

        total_tg = target_counts["Trials"].sum()
        cd19_n = int(target_counts.loc[target_counts["Target"] == "CD19", "Trials"].sum())
        bcma_n = int(target_counts.loc[target_counts["Target"] == "BCMA", "Trials"].sum())
        dual_n = int(target_counts.loc[target_counts["Target"].str.contains("dual", case=False, na=False), "Trials"].sum())
        unspec_n = int(target_counts.loc[target_counts["Target"] == "CAR-T_unspecified", "Trials"].sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CD19-targeted", f"{cd19_n} ({100*cd19_n/total_tg:.0f}%)")
        c2.metric("BCMA-targeted", f"{bcma_n} ({100*bcma_n/total_tg:.0f}%)")
        c3.metric("Dual-target", f"{dual_n} ({100*dual_n/total_tg:.0f}%)")
        c4.metric("Target unspecified", f"{unspec_n} ({100*unspec_n/total_tg:.0f}%)")

        fig3_csv = target_counts.copy()
        fig3_csv["% of total"] = (fig3_csv["Trials"] / total_tg * 100).round(1)
        _pub_caption(len(df_filt))
        st.download_button("Fig 3 data (CSV)",
                           _csv_with_provenance(fig3_csv, "Fig 3 — Target landscape"),
                           "fig3_target_landscape.csv", "text/csv")
    else:
        st.info("No target data available.")

    # ------------------------------------------------------------------
    # Fig 4 — Disease distribution
    # ------------------------------------------------------------------
    _pub_header("4", "Disease entity distribution",
                "Trials per disease. Basket and multi-disease trials are counted once per enrolled disease.")

    _dis_vals = split_pipe_values(df_filt["DiseaseEntities"])
    disease_counts = (
        pd.DataFrame({"Disease": _dis_vals})["Disease"]
        .value_counts().rename_axis("Disease").reset_index(name="Trials")
    ) if _dis_vals else pd.DataFrame(columns=["Disease", "Trials"])

    if not disease_counts.empty:
        disease_sorted = disease_counts.sort_values("Trials", ascending=True)
        fig4 = px.bar(
            disease_sorted, x="Trials", y="Disease", orientation="h", height=max(380, len(disease_sorted) * 36 + 100),
            color_discrete_sequence=[NEJM_AMBER], template="plotly_white",
            text="Trials",
        )
        fig4.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig4.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials",
            yaxis_title=None,
            showlegend=False,
            margin=dict(l=160, r=56, t=24, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig4, use_container_width=True, config=PUB_EXPORT)

        total_dis = disease_counts["Trials"].sum()
        top3 = disease_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
            col.metric(row["Disease"], f"{row['Trials']} ({100*row['Trials']/total_dis:.0f}%)")

        fig4_csv = disease_counts.copy()
        fig4_csv["% of total"] = (fig4_csv["Trials"] / total_dis * 100).round(1)
        _pub_caption(
            len(df_filt),
            extra="Disease totals may exceed trial count because basket trials are attributed to multiple diseases."
        )
        st.download_button("Fig 4 data (CSV)",
                           _csv_with_provenance(fig4_csv, "Fig 4 — Disease distribution"),
                           "fig4_disease_distribution.csv", "text/csv")
    else:
        st.info("No disease data available.")

    # ------------------------------------------------------------------
    # Fig 5 — Geographic distribution
    # ------------------------------------------------------------------
    _pub_header("5", "Global distribution of trial sites",
                "Choropleth of trial counts by country, with leading countries shown below.")

    geo_vals = split_pipe_values(df_filt["Countries"])
    if geo_vals:
        geo_counts = (
            pd.DataFrame({"Country": geo_vals})["Country"]
            .value_counts().rename_axis("Country").reset_index(name="Trials")
        )

        fig5_map = px.choropleth(
            geo_counts, locations="Country", locationmode="country names",
            color="Trials",
            color_continuous_scale=[[0, "#dce9f5"], [0.3, "#5aafd6"], [0.65, "#1c6faf"], [1, "#08306b"]],
            projection="natural earth", template="plotly_white",
        )
        fig5_map.update_layout(
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
        st.plotly_chart(fig5_map, use_container_width=True, config=PUB_EXPORT)

        top10 = geo_counts.head(10).sort_values("Trials", ascending=True)
        fig5_bar = px.bar(
            top10, x="Trials", y="Country", orientation="h", height=380,
            color_discrete_sequence=[NEJM_BLUE], template="plotly_white",
            text="Trials",
        )
        fig5_bar.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig5_bar.update_layout(
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
            '<strong style="color: #0b1220;">5b — Top 10 countries by number of trials</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig5_bar, use_container_width=True, config=PUB_EXPORT)

        total_geo = geo_counts["Trials"].sum()
        top3_geo = geo_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3_geo.iterrows()):
            col.metric(row["Country"], f"{row['Trials']} ({100*row['Trials']/total_geo:.0f}%)")

        fig5_csv = geo_counts.copy()
        fig5_csv["% of total"] = (fig5_csv["Trials"] / total_geo * 100).round(1)
        _pub_caption(
            len(df_filt),
            extra="Multi-country trials are counted once per country."
        )
        st.download_button("Fig 5 data (CSV)",
                           _csv_with_provenance(fig5_csv, "Fig 5 — Geographic distribution"),
                           "fig5_geographic_distribution.csv", "text/csv")
    else:
        st.info("No country data available.")

    # ------------------------------------------------------------------
    # Fig 6 — Innovation signals (product type + modality over time)
    # ------------------------------------------------------------------
    _pub_header("6", "Innovation signals — product type and cell-therapy modality",
                "Trial composition over time, by manufacturing approach (autologous / allogeneic / in vivo) and by cell-therapy platform.")

    # 6a: Autologous vs allogeneic by start year
    df_innov = df_filt[df_filt["StartYear"].notna()].copy()
    df_innov["StartYear"] = df_innov["StartYear"].astype(int)

    if not df_innov.empty:
        product_year = (
            df_innov.groupby(["StartYear", "ProductType"]).size()
            .reset_index(name="Trials")
        )
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 0.4rem;">'
            '<strong style="color: #0b1220;">6a — Product type by start year</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig6a = px.bar(
            product_year, x="StartYear", y="Trials", color="ProductType",
            barmode="stack", height=420, template="plotly_white",
            color_discrete_map={
                "Autologous":              NEJM_BLUE,
                "Allogeneic/Off-the-shelf": NEJM_RED,
                "In vivo":                 NEJM_GREEN,
                "Unclear":                 "#888888",
            },
            category_orders={"ProductType": ["Autologous", "Allogeneic/Off-the-shelf", "In vivo", "Unclear"]},
            labels={"StartYear": "Start year", "Trials": "Number of trials", "ProductType": "Product type"},
        )
        fig6a.update_traces(marker_line_width=0, opacity=1)
        fig6a.update_layout(
            **PUB_BASE,
            margin=dict(l=64, r=36, t=24, b=110),
            xaxis=dict(
                tickmode="linear", dtick=1, tickformat="d", showgrid=False,
                showline=True, linewidth=1.5, linecolor=_AX_COLOR,
                ticks="outside", ticklen=6, tickwidth=1.2,
                tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
                title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
            ),
            yaxis=dict(
                showline=True, linewidth=1.5, linecolor=_AX_COLOR,
                showgrid=True, gridcolor=_GRID_CLR, gridwidth=0.7,
                ticks="outside", ticklen=6, tickwidth=1.2,
                tickfont=dict(size=_TICK_SZ, color=_AX_COLOR),
                title_font=dict(size=_LAB_SZ, color=_AX_COLOR),
                zeroline=False,
            ),
            legend=dict(
                orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5,
                font=dict(size=11, color=_AX_COLOR), bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
            ),
        )
        st.plotly_chart(fig6a, use_container_width=True, config=PUB_EXPORT)

        # 6b: Therapy modality — eight categories (CAR-T split by autologous/allogeneic + γδ T)
        # _MODALITY_ORDER, _MODALITY_COLORS, _modality() are module-level; Modality column pre-computed
        df_innov["Modality"] = df_innov.apply(_modality, axis=1)
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">6b — Cell-therapy modality distribution</strong>'
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
        fig6b = px.bar(
            modality_counts, x="Trials", y="Modality", orientation="h",
            height=max(300, len(modality_counts) * 52 + 100),
            color="Modality", color_discrete_map=_MODALITY_COLORS,
            template="plotly_white", text="Trials",
        )
        fig6b.update_traces(
            marker_line_width=0, opacity=1,
            texttemplate="%{text}", textposition="outside",
            textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
        )
        fig6b.update_layout(
            **PUB_BASE,
            xaxis_title="Number of trials", yaxis_title=None, showlegend=False,
            margin=dict(l=110, r=56, t=24, b=56),
            yaxis=_H_YAXIS,
            xaxis=_H_XAXIS,
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig6b, use_container_width=True, config=PUB_EXPORT)

        # 6c: Modality over time (stacked area gives better temporal story)
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">6c — Modality mix by start year</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        mod_year = (
            df_innov.groupby(["StartYear", "Modality"]).size()
            .reset_index(name="Trials")
        )
        # keep only modalities that actually appear
        present_mods = [m for m in _MODALITY_ORDER if m in mod_year["Modality"].unique()]
        fig6c = px.bar(
            mod_year[mod_year["Modality"].isin(present_mods)],
            x="StartYear", y="Trials", color="Modality",
            barmode="stack", height=400, template="plotly_white",
            color_discrete_map=_MODALITY_COLORS,
            category_orders={"Modality": _MODALITY_ORDER},
            labels={"StartYear": "Start year", "Trials": "Number of trials"},
        )
        fig6c.update_traces(marker_line_width=0, opacity=1)
        fig6c.update_layout(
            **PUB_BASE,
            margin=dict(l=64, r=36, t=24, b=110),
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
            ),
            legend=dict(
                orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5,
                font=dict(size=11, color=_AX_COLOR), bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
            ),
            xaxis_title="Start year",
            yaxis_title="Number of trials",
        )
        st.plotly_chart(fig6c, use_container_width=True, config=PUB_EXPORT)

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

        fig6_csv = pd.merge(
            product_year.rename(columns={"ProductType": "Category", "Trials": "n_product"}),
            df_innov.groupby(["StartYear", "Modality"]).size().reset_index(name="n_modality"),
            left_on="StartYear", right_on="StartYear", how="outer",
        )
        _pub_caption(
            len(df_filt),
            extra="Panel counts restricted to trials with a known start year."
        )
        st.download_button("Fig 6 data (CSV)",
                           _csv_with_provenance(fig6_csv, "Fig 6 — Innovation signals / cell therapy modality"),
                           "fig6_innovation_signals.csv", "text/csv")
    else:
        st.info("No start year data available for innovation analysis.")

    # ------------------------------------------------------------------
    # Fig 7 — Trial enrollment
    # ------------------------------------------------------------------
    _pub_header("7", "Trial enrollment landscape",
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

        # 7a — Enrollment distribution histogram
        st.markdown(
            '<div class="pub-fig-sub" style="margin-top: 1rem; '
            'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
            '<strong style="color: #0b1220;">7a — Distribution of planned enrollment</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig7a = px.histogram(
            df_enroll_known, x="EnrollmentCount", nbins=40, height=400,
            color_discrete_sequence=[NEJM_BLUE], template="plotly_white",
            labels={"EnrollmentCount": "Planned enrollment (patients)"},
        )
        fig7a.update_traces(marker_line_color="white", marker_line_width=0.4, opacity=0.9)
        _vline_med = dict(
            type="line", x0=med_pts, x1=med_pts, y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=NEJM_RED, width=1.5, dash="dash"),
        )
        fig7a.update_layout(
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
        st.plotly_chart(fig7a, use_container_width=True, config=PUB_EXPORT)

        # 7b — Median enrollment by phase
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
            '<strong style="color: #0b1220;">7b — Median enrollment by trial phase</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig7b = px.bar(
            _phase_enroll, x="Phase", y="Median", height=380,
            color_discrete_sequence=[NEJM_GREEN], template="plotly_white",
            text="label",
        )
        fig7b.update_traces(
            marker_line_width=0, opacity=1, width=0.6,
            textposition="outside", textfont=dict(size=10, color=_AX_COLOR),
            cliponaxis=False,
        )
        fig7b.update_layout(
            **PUB_LAYOUT,
            xaxis_title="Phase",
            yaxis_title="Median planned enrollment (patients)",
            uniformtext_minsize=9, uniformtext_mode="hide",
        )
        st.plotly_chart(fig7b, use_container_width=True, config=PUB_EXPORT)

        # 7c — Total enrolled patients by disease (enrollment-weighted landscape)
        _dis_enroll_rows = []
        for _, row in df_enroll_known.iterrows():
            entities = [e.strip() for e in str(row.get("DiseaseEntities", "")).split("|") if e.strip()]
            if not entities:
                entities = [str(row.get("DiseaseEntity", "Unclassified"))]
            for ent in entities:
                _dis_enroll_rows.append({"Disease": ent, "Enrollment": row["EnrollmentCount"]})
        if _dis_enroll_rows:
            _dis_enroll_df = pd.DataFrame(_dis_enroll_rows)
            _dis_enroll_agg = (
                _dis_enroll_df.groupby("Disease")["Enrollment"]
                .agg(TotalEnrolled="sum", Trials="count")
                .reset_index()
                .sort_values("TotalEnrolled", ascending=True)
            )
            _dis_enroll_agg["TotalEnrolled"] = _dis_enroll_agg["TotalEnrolled"].astype(int)

            st.markdown(
                '<div class="pub-fig-sub" style="margin-top: 1rem; '
                'border-top: 1px solid #e5e7eb; padding-top: 0.8rem;">'
                '<strong style="color: #0b1220;">7c — Total planned enrollment by disease</strong> '
                '<span style="color: #94a3b8;">— enrollment-weighted disease landscape</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            fig7c = px.bar(
                _dis_enroll_agg, x="TotalEnrolled", y="Disease", orientation="h",
                height=max(380, len(_dis_enroll_agg) * 34 + 100),
                color_discrete_sequence=[NEJM_AMBER], template="plotly_white",
                text="TotalEnrolled",
            )
            fig7c.update_traces(
                marker_line_width=0, opacity=1,
                texttemplate="%{text:,}", textposition="outside",
                textfont=dict(size=10, color=_AX_COLOR), cliponaxis=False,
            )
            fig7c.update_layout(
                **PUB_BASE,
                xaxis_title="Total planned patients (reported trials)",
                yaxis_title=None, showlegend=False,
                margin=dict(l=155, r=72, t=24, b=56),
                yaxis=_H_YAXIS,
                xaxis=_H_XAXIS,
                uniformtext_minsize=9, uniformtext_mode="hide",
            )
            st.plotly_chart(fig7c, use_container_width=True, config=PUB_EXPORT)
            st.markdown(
                '<div class="pub-fig-caption" style="margin-top: 0.1rem;">'
                'Basket trials counted once per enrolled disease · '
                'Trials without reported enrollment excluded.'
                '</div>',
                unsafe_allow_html=True,
            )

        # 7d / 7e — China vs Non-China  ·  Academic vs Industry
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

        df_enroll_known["GeoGroup"]    = df_enroll_known["Countries"].apply(_geo_group)
        df_enroll_known["SponsorType"] = df_enroll_known["LeadSponsor"].apply(_sponsor_type)

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
            '<strong style="color: #0b1220;">7d — Enrollment by subgroup</strong> '
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

        fig7d = px.scatter(
            forest_df, x="Median", y="Label",
            color="Category", color_discrete_map=_CAT_COLORS,
            error_x=forest_df["Q3"] - forest_df["Median"],
            error_x_minus=forest_df["Median"] - forest_df["Q1"],
            height=max(360, 28 * len(forest_df) + 110),
            template="plotly_white",
        )
        fig7d.update_traces(
            marker=dict(size=11, line=dict(color="white", width=1.2)),
            error_x=dict(color=_AX_COLOR, thickness=1.2, width=6),
        )
        # Sample-size annotations to the right of each whisker
        for _, r in forest_df.iterrows():
            fig7d.add_annotation(
                x=r["Q3"], y=r["Label"], xref="x", yref="y",
                text=f"  Median {r['Median']}  ·  n={r['N']}",
                showarrow=False,
                font=dict(size=10, color=THEME["muted"]),
                xanchor="left",
            )
        fig7d.update_layout(
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
        st.plotly_chart(fig7d, use_container_width=True, config=PUB_EXPORT)
        st.markdown(
            '<div class="pub-fig-caption" style="margin-top: 0.1rem;">'
            'Whiskers = IQR (Q1–Q3).'
            '</div>',
            unsafe_allow_html=True,
        )

        # Tabular summary (inputs to forest plot, in display order)
        _cmp_summary = forest_df[["Category", "Group", "N", "Median", "Q1", "Q3"]].iloc[::-1].reset_index(drop=True)
        _cmp_summary = _cmp_summary.rename(columns={"N": "N (trials)", "Median": "Median enrollment", "Q1": "IQR Q1", "Q3": "IQR Q3"})

        fig7_csv = df_enroll_known[["NCTId", "BriefTitle", "DiseaseEntity", "TargetCategory",
                                     "ProductType", "Phase", "EnrollmentCount",
                                     "GeoGroup", "SponsorType"]].copy()
        fig7_csv = fig7_csv.sort_values("EnrollmentCount", ascending=False)
        _pub_caption(
            len(df_filt),
            extra=f"Enrollment panels restricted to {len(df_enroll_known):,} trials with a numeric enrollment target."
        )
        st.download_button("Fig 7 data (CSV)",
                           _csv_with_provenance(fig7_csv, "Fig 7 — Enrollment characteristics"),
                           "fig7_enrollment.csv", "text/csv")
        with st.expander("Comparison summary table"):
            st.dataframe(_cmp_summary, use_container_width=True, hide_index=True)
    else:
        st.info("Insufficient enrollment data available.")

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
disorders", "paediatric B-cell related autoimmune diseases") were mapped to
"Unclassified" rather than a specific entity.

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
antigens.

Product type. Studies were classified as "Autologous", "Allogeneic/Off-the-shelf",
"In vivo", or "Unclear" based on presence of corresponding keywords in normalised
text. Autologous markers included: autologous, autoleucel, patient-derived.
Allogeneic markers included: allogeneic, off-the-shelf, universal CAR-T, UCART,
healthy donor, donor-derived, umbilical cord blood, cord blood. In vivo markers
included: in vivo CAR, circular RNA, lentiviral nanoparticle, mRNA-LNP. A named
product lookup table (NAMED_PRODUCT_TYPES in config.py) was applied as a fallback
when these generic markers were absent. Both lookup tables are updated iteratively
via a structured curation loop applied to pipeline output.

Cell therapy modality. Each trial was assigned to one of seven mechanistically
distinct modality categories based on target category and product type:
  • Auto CAR-T — conventional autologous alpha-beta CAR-T cells
  • Allo CAR-T — allogeneic/off-the-shelf CAR-T (including iPSC-derived)
  • CAR-T (unclear) — CAR-T with product source not determinable from public text
  • CAR-NK — CAR-modified natural killer cells (autologous or allogeneic)
  • CAR-Treg — regulatory T-cell CAR constructs
  • CAAR-T — chimeric autoantibody receptor T cells
  • In vivo CAR — mRNA-LNP or other non-cellular in vivo CAR delivery systems

Enrollment Analysis
-------------------
Planned enrollment counts were extracted from the EnrollmentCount field (type=
"Anticipated" or "Actual") and coerced to numeric; non-numeric or missing values
were excluded from enrollment analyses (Figure 7). Geographic classification:
trials recruiting exclusively in China were labelled "China"; all others
"Non-China" (based on the Countries field). Sponsor classification: lead sponsors
were labelled "Academic" if their name contained tokens indicating a hospital,
university, research institute, or affiliated medical centre; "Industry" if
containing therapeutics, pharma, biotech, or corporate-suffix tokens (Inc, Ltd,
GmbH, LLC, Corp). Short strings (≤4 words) without corporate suffixes were treated
as PI names and classified as "Academic". Cross-tabulation of geography × sponsor
type (Fig 7f) shows median planned enrollment and IQR (error bars) for each of
the four strata.

Data Processing
---------------
All processing was performed in Python (pandas {pd.__version__}) using a custom
ETL pipeline. Text normalisation included lowercasing, Unicode normalisation
(e.g., "sjögren" → "sjogren"), and removal of non-alphanumeric characters. Term
matching used whole-word boundary matching for short terms (≤3 characters) and
substring matching for longer terms. Classification rules and term dictionaries
are versioned in the accompanying config.py file and updated via structured
curation loops applied to random samples of pipeline output.

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
    rows.append({
        "Category": "Other immune-mediated",
        "Label": "Other immune-mediated",
        "Matching terms (sample)": "; ".join(OTHER_IMMUNE_MEDIATED_TERMS[:6]) + "…",
        "N terms": len(OTHER_IMMUNE_MEDIATED_TERMS),
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
    st.dataframe(ontology_df, use_container_width=True, hide_index=True,
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
    st.dataframe(excl_df, use_container_width=True, hide_index=True,
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
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
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
    ">Klinik I für Innere Medizin<br>Klinische Immunologie und Rheumatologie</div>
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
        f"Klinik I für Innere Medizin, Klinische Immunologie und Rheumatologie, "
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
Klinik I für Innere Medizin — Klinische Immunologie und Rheumatologie
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
