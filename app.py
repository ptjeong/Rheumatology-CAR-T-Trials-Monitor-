import re
import streamlit as st
import pandas as pd
import plotly.express as px

from datetime import date

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

THEME = {
    "bg": "#0b0f14",
    "panel": "#11161d",
    "panel_2": "#151c24",
    "panel_3": "#1a232d",
    "text": "#ecf1f7",
    "muted": "#9aa6b2",
    "faint": "#6f7b87",
    "border": "rgba(255,255,255,0.08)",
    "primary": "#21b3a3",
    "primary_2": "#123b39",
    "accent": "#d38a5a",
    "grid": "rgba(255,255,255,0.08)",
    "shadow": "0 12px 32px rgba(0,0,0,0.28)",
}

px.defaults.template = "plotly_dark"

st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{
        color: {THEME["text"]};
    }}

    .stApp {{
        background:
            radial-gradient(circle at top left, rgba(33,179,163,0.08), transparent 30%),
            radial-gradient(circle at top right, rgba(211,138,90,0.06), transparent 28%),
            linear-gradient(180deg, #0b0f14 0%, #0d1218 100%);
        color: {THEME["text"]};
    }}

    .block-container {{
        max-width: 1450px;
        padding-top: 1.6rem;
        padding-bottom: 2.2rem;
    }}

    h1, h2, h3 {{
        color: {THEME["text"]};
        letter-spacing: -0.02em;
    }}

    .hero {{
        position: relative;
        overflow: hidden;
        padding: 1.8rem 2rem;
        border: 1px solid {THEME["border"]};
        border-radius: 24px;
        background: linear-gradient(180deg, rgba(21,28,36,0.96) 0%, rgba(17,22,29,0.96) 100%);
        box-shadow: {THEME["shadow"]};
        margin-bottom: 1.2rem;
    }}

    .hero:before {{
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(120deg, rgba(33,179,163,0.08), transparent 35%, rgba(211,138,90,0.06) 100%);
        pointer-events: none;
    }}

    .hero-title {{
        position: relative;
        z-index: 1;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
        color: {THEME["text"]};
    }}

    .hero-sub {{
        position: relative;
        z-index: 1;
        font-size: 1rem;
        line-height: 1.65;
        color: {THEME["muted"]};
        max-width: 900px;
    }}

    .section-card {{
        background: linear-gradient(180deg, rgba(21,28,36,0.95) 0%, rgba(17,22,29,0.96) 100%);
        border: 1px solid {THEME["border"]};
        border-radius: 20px;
        padding: 1.1rem 1.1rem 0.9rem 1.1rem;
        box-shadow: {THEME["shadow"]};
        margin-bottom: 1rem;
    }}

    .metric-card {{
        background: linear-gradient(180deg, rgba(21,28,36,0.96) 0%, rgba(17,22,29,0.96) 100%);
        border: 1px solid {THEME["border"]};
        border-radius: 18px;
        padding: 1rem 1rem 0.85rem 1rem;
        box-shadow: {THEME["shadow"]};
    }}

    .metric-label {{
        font-size: 0.82rem;
        color: {THEME["muted"]};
        margin-bottom: 0.45rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    .metric-value {{
        font-size: 1.95rem;
        font-weight: 700;
        color: {THEME["text"]};
        line-height: 1.05;
    }}

    .metric-foot {{
        margin-top: 0.4rem;
        font-size: 0.82rem;
        color: {THEME["faint"]};
    }}

    .small-note {{
        color: {THEME["muted"]};
        font-size: 0.92rem;
        margin-top: 0.35rem;
        margin-bottom: 0.5rem;
    }}

    div[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0f141b 0%, #10161e 100%);
        border-right: 1px solid {THEME["border"]};
    }}

    div[data-testid="stSidebar"] h1,
    div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3,
    div[data-testid="stSidebar"] label,
    div[data-testid="stSidebar"] p,
    div[data-testid="stSidebar"] span {{
        color: {THEME["text"]};
    }}

    .stButton > button,
    .stDownloadButton > button {{
        background: linear-gradient(180deg, #1ab09f 0%, #149282 100%);
        color: white;
        border: 0;
        border-radius: 999px;
        padding: 0.62rem 1rem;
        font-weight: 600;
        box-shadow: 0 8px 20px rgba(33,179,163,0.18);
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        background: linear-gradient(180deg, #1fc0ae 0%, #169b8a 100%);
        color: white;
    }}

    div[data-testid="stTabs"] button {{
        color: {THEME["muted"]};
    }}

    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: {THEME["text"]};
    }}

    div[data-testid="stDataFrame"] {{
        border: 1px solid {THEME["border"]};
        border-radius: 16px;
        overflow: hidden;
        background: {THEME["panel"]};
    }}

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {{
        background-color: {THEME["panel_3"]};
        border-color: {THEME["border"]};
        color: {THEME["text"]};
    }}

    .stTextInput input, .stSelectbox div, .stMultiSelect div {{
        color: {THEME["text"]};
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


def make_bar(df_plot, x, y, height=360, color="#21b3a3"):
    fig = px.bar(
        df_plot,
        x=x,
        y=y,
        height=height,
        color_discrete_sequence=[color],
        template="plotly_dark",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(color=THEME["text"]),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
    )
    fig.update_xaxes(showgrid=False, color=THEME["muted"])
    fig.update_yaxes(gridcolor=THEME["grid"], color=THEME["muted"])
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
        <div class="hero-title">CAR-T and Related Cell Therapies in Rheumatologic Systemic Diseases</div>
        <div class="hero-sub">
            A monitoring dashboard for ClinicalTrials.gov studies with disease mapping,
            target classification, clickable NCT links, and a dedicated geography view for global
            and Germany-specific activity.
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
    with st.spinner("Fetching and processing ClinicalTrials.gov data..."):
        df, df_sites, prisma_counts = load_live(statuses=tuple(selected_statuses))

    if st.sidebar.button("Save snapshot"):
        statuses_list = selected_statuses if selected_statuses else None
        snap_date = save_snapshot(df, df_sites, prisma_counts, statuses=statuses_list)
        st.sidebar.success(f"Saved snapshot: {snap_date}")
        st.cache_data.clear()

df = add_phase_columns(df)

if df.empty:
    st.error("No studies were returned. Try broadening the status filters.")
    st.stop()

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

# Target category (multi-select)
target_options = sorted(df["TargetCategory"].dropna().unique().tolist())
target_sel = st.sidebar.multiselect(
    "Target category",
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
    st.caption(
        "Ambiguous labels counted: other_or_unknown, CAR_T_unspecified, unclassified, autoimmune_other (if present)."
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
    mask &= df["TargetCategory"].isin(target_sel)

if status_sel:
    mask &= df["OverallStatus"].isin(status_sel)

if product_sel:
    mask &= df["ProductType"].isin(product_sel)

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
top_target = df_filt["TargetCategory"].value_counts().idxmax() if not df_filt["TargetCategory"].dropna().empty else "—"

m1, m2, m3, m4 = st.columns(4)
with m1:
    metric_card("Filtered trials", total_trials, "Trials matching current filters")
with m2:
    metric_card("Open / recruiting", recruiting_trials, "Recruiting or not yet recruiting")
with m3:
    metric_card("German-linked trials", german_trials_count, "Unique filtered studies with at least one open German site")
with m4:
    metric_card("Top target", top_target, "Most common target category")

st.markdown(
    f"""
    <div class="small-note">
        {len(df)} total trials after processing. Current view shows {len(df_filt)} filtered trials.
    </div>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_geo, tab_data, tab_pub, tab_methods = st.tabs(
    ["Overview", "Geography / Map", "Data", "Publication Figures", "Methods & Appendix"]
)

with tab_overview:
    if prisma_counts:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1.05, 1])

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
            st.plotly_chart(make_bar(counts_disease, "DiseaseEntity", "Count", color="#21b3a3"), use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
            fig_phase = make_bar(counts_phase, "Phase", "Count", color="#d38a5a")
            fig_phase.update_xaxes(categoryorder="array", categoryarray=[PHASE_LABELS[p] for p in PHASE_ORDER])
            st.plotly_chart(fig_phase, use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Trials by target category")
        counts_target = (
            df_filt["TargetCategory"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("TargetCategory")
            .reset_index(name="Count")
        )
        if not counts_target.empty:
            st.plotly_chart(make_bar(counts_target, "TargetCategory", "Count", color="#6fb7ff"), use_container_width=True)
        else:
            st.info("No trials for the current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
                height=360,
                template="plotly_dark",
            )
            fig_year.update_traces(line_color="#21b3a3", marker_color="#d38a5a", line_width=3)
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
        st.markdown("</div>", unsafe_allow_html=True)

with tab_geo:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
                [0.00, "#1d4e89"],
                [0.20, "#4f86c6"],
                [0.40, "#a8c6ea"],
                [0.58, "#f3d37a"],
                [0.78, "#e67e22"],
                [1.00, "#b22222"],
            ],
            projection="natural earth",
            template="plotly_dark",
        )
        fig_world.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=THEME["text"]),
            geo=dict(
                bgcolor="rgba(0,0,0,0)",
                lakecolor="rgba(0,0,0,0)",
                landcolor="#17202a",
                showframe=False,
                showcoastlines=False,
                showcountries=True,
                countrycolor="rgba(255,255,255,0.12)",
            ),
            coloraxis_colorbar_title="Trials",
        )
        st.plotly_chart(fig_world, use_container_width=True)

        c1, c2 = st.columns([1.15, 0.85])
        with c1:
            st.markdown("**Country counts**")
            st.dataframe(country_counts, use_container_width=True, height=320, hide_index=True)
        with c2:
            st.markdown("**Top countries**")
            st.plotly_chart(
                make_bar(country_counts.head(12), "Country", "Count", height=320, color="#21b3a3"),
                use_container_width=True,
            )
    else:
        st.info("No country information available for the current filter selection.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
                make_bar(germany_city_counts, "City", "OpenSiteCount", height=380, color="#d38a5a"),
                use_container_width=True,
            )
        with c2:
            st.markdown("**Germany city table**")
            city_event = st.dataframe(
                germany_city_counts,
                use_container_width=True,
                height=380,
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
    st.markdown("</div>", unsafe_allow_html=True)

with tab_data:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Studies active in Germany")

    if germany_study_view.empty:
        st.info("No open or recruiting German study sites found in the current result set.")
    else:
        germany_export_view = germany_study_view.copy()
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
    st.markdown("</div>", unsafe_allow_html=True)

    # Identify trials with unclassified / other buckets for disease or target
    unclassified_mask = (
        df_filt["DiseaseEntity"].astype(str).str.lower().isin(["autoimmune_other", "unclassified", "other_or_unknown"])
        | df_filt["TargetCategory"].astype(str).str.lower().isin(["other_or_unknown", "unclassified", "unknown"])
    )
    df_unclassified = df_filt[unclassified_mask].copy()

    # Prepare a plain-text prompt/command to help generate a supplementary curation checklist
    unclassified_text = ""\

    if not df_unclassified.empty:
        lines = []
        lines.append(
            "INSTRUCTION / COMMAND: Based on the following clinical trials, generate a supplementary curation "
            "checklist to improve DiseaseEntity and TargetCategory classification. For each trial, "
            "propose refined labels and a short justification that can be integrated back into the ETL pipeline."
        )
        lines.append(
            "Output format suggestion (CSV columns): "
            "NCTId, ExistingDiseaseEntity, ExistingTargetCategory, "
            "ProposedDiseaseEntity, ProposedTargetCategory, Rationale"
        )
        lines.append(
            "Focus especially on replacing autoimmune_other / other_or_unknown / unclassified "
            "with more specific entities or targets where justified."
        )
        lines.append("")
        lines.append("Trial rows (NCTId | DiseaseEntity | TargetCategory | BriefTitle):")
        for _, row in df_unclassified.iterrows():
            lines.append(
                f"- {row.get('NCTId', '')} | "
                f"{row.get('DiseaseEntity', '')} | "
                f"{row.get('TargetCategory', '')} | "
                f"{row.get('BriefTitle', '')}"
            )
        unclassified_text = "\n".join(lines)

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            label="Download filtered trial data as CSV",
            data=df_filt.to_csv(index=False),
            file_name="car_t_rheumatology_trials_filtered.csv",
            mime="text/csv",
        )
    with d2:
        if not df_sites.empty:
            st.download_button(
                label="Download site-level data as CSV",
                data=df_sites.to_csv(index=False),
                file_name="car_t_rheumatology_sites.csv",
                mime="text/csv",
            )
    with d3:
        st.download_button(
            label="Unclassified trials prompt (.txt)",
            data=unclassified_text if unclassified_text else "No unclassified trials in current filter.",
            file_name="unclassified_trials_prompt.txt",
            mime="text/plain",
            disabled=df_unclassified.empty,
        )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB: Publication Figures
# ---------------------------------------------------------------------------

PUB_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Arial, sans-serif", size=13, color="#1a1a1a"),
    margin=dict(l=70, r=30, t=50, b=70),
)
PUB_EXPORT = {"toImageButtonOptions": {"format": "png", "width": 1400, "height": 800, "scale": 2}}


def pub_bar(df_plot, x, y, color="#2a6099", title="", xlab="", ylab="Count", height=420):
    fig = px.bar(df_plot, x=x, y=y, height=height, color_discrete_sequence=[color], template="plotly_white")
    fig.update_layout(**PUB_LAYOUT, title=dict(text=title, font_size=15, x=0), xaxis_title=xlab, yaxis_title=ylab, showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e5e5e5")
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 1 — Temporal trends")

    years_raw = pd.to_numeric(df_filt["StartYear"], errors="coerce").dropna().astype(int)
    fig1_data = (
        years_raw.value_counts().sort_index()
        .rename_axis("StartYear").reset_index(name="Trials")
    )

    if not fig1_data.empty:
        fig1 = px.line(
            fig1_data, x="StartYear", y="Trials", markers=True, height=420, template="plotly_white",
        )
        fig1.update_traces(line_color="#2a6099", marker_color="#d95f02", line_width=2.5, marker_size=8)
        fig1.update_layout(
            **PUB_LAYOUT,
            title=dict(text="CAR-T and Related Cell Therapies in Autoimmune Diseases: Trials by Start Year", font_size=14, x=0),
            xaxis_title="Start year", yaxis_title="Number of trials",
        )
        fig1.update_xaxes(tickmode="linear", dtick=1, tickformat="d", showgrid=False)
        fig1.update_yaxes(gridcolor="#e5e5e5")
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

        st.download_button("Fig 1 data (CSV)", fig1_data.to_csv(index=False),
                           "fig1_temporal_trends.csv", "text/csv")
    else:
        st.info("No start year data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Fig 2 — Phase distribution
    # ------------------------------------------------------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 2 — Phase distribution")

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
        fig2 = pub_bar(phase_counts, "Phase", "Trials", color="#2a6099",
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
        st.download_button("Fig 2 data (CSV)", fig2_csv.to_csv(index=False),
                           "fig2_phase_distribution.csv", "text/csv")
    else:
        st.info("No phase data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Fig 3 — Target landscape
    # ------------------------------------------------------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 3 — Target landscape")

    target_counts = (
        df_filt["TargetCategory"].fillna("Unknown").value_counts()
        .rename_axis("Target").reset_index(name="Trials")
    )

    if not target_counts.empty:
        fig3 = pub_bar(target_counts, "Target", "Trials", color="#7b2d8b",
                       title="CAR-T Target Categories in Autoimmune Disease Trials", xlab="Target category")
        st.plotly_chart(fig3, use_container_width=True, config=PUB_EXPORT)

        total_tg = target_counts["Trials"].sum()
        cd19_n = int(target_counts.loc[target_counts["Target"] == "CD19", "Trials"].sum())
        bcma_n = int(target_counts.loc[target_counts["Target"] == "BCMA", "Trials"].sum())
        dual_n = int(target_counts.loc[target_counts["Target"].str.contains("dual", case=False, na=False), "Trials"].sum())
        car_nk_n = int(target_counts.loc[target_counts["Target"] == "CAR-NK", "Trials"].sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CD19-targeted", f"{cd19_n} ({100*cd19_n/total_tg:.0f}%)")
        c2.metric("BCMA-targeted", f"{bcma_n} ({100*bcma_n/total_tg:.0f}%)")
        c3.metric("Dual-target", f"{dual_n} ({100*dual_n/total_tg:.0f}%)")
        c4.metric("CAR-NK", f"{car_nk_n} ({100*car_nk_n/total_tg:.0f}%)")

        fig3_csv = target_counts.copy()
        fig3_csv["% of total"] = (fig3_csv["Trials"] / total_tg * 100).round(1)
        st.download_button("Fig 3 data (CSV)", fig3_csv.to_csv(index=False),
                           "fig3_target_landscape.csv", "text/csv")
    else:
        st.info("No target data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Fig 4 — Disease distribution
    # ------------------------------------------------------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 4 — Disease distribution")

    _dis_vals = split_pipe_values(df_filt["DiseaseEntities"])
    disease_counts = (
        pd.DataFrame({"Disease": _dis_vals})["Disease"]
        .value_counts().rename_axis("Disease").reset_index(name="Trials")
    ) if _dis_vals else pd.DataFrame(columns=["Disease", "Trials"])

    if not disease_counts.empty:
        fig4 = pub_bar(disease_counts, "Disease", "Trials", color="#d95f02",
                       title="Disease Entity Distribution in CAR-T Autoimmune Trials\n(basket trials counted per disease enrolled)",
                       xlab="Disease entity")
        st.plotly_chart(fig4, use_container_width=True, config=PUB_EXPORT)

        total_dis = disease_counts["Trials"].sum()
        top3 = disease_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3.iterrows()):
            col.metric(row["Disease"], f"{row['Trials']} ({100*row['Trials']/total_dis:.0f}%)")

        fig4_csv = disease_counts.copy()
        fig4_csv["% of total"] = (fig4_csv["Trials"] / total_dis * 100).round(1)
        st.download_button("Fig 4 data (CSV)", fig4_csv.to_csv(index=False),
                           "fig4_disease_distribution.csv", "text/csv")
    else:
        st.info("No disease data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Fig 5 — Geographic distribution
    # ------------------------------------------------------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 5 — Geographic distribution")

    geo_vals = split_pipe_values(df_filt["Countries"])
    if geo_vals:
        geo_counts = (
            pd.DataFrame({"Country": geo_vals})["Country"]
            .value_counts().rename_axis("Country").reset_index(name="Trials")
        )

        fig5_map = px.choropleth(
            geo_counts, locations="Country", locationmode="country names",
            color="Trials",
            color_continuous_scale=[[0, "#deebf7"], [0.4, "#9ecae1"], [0.7, "#3182bd"], [1, "#08306b"]],
            projection="natural earth", template="plotly_white",
        )
        fig5_map.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="Arial, sans-serif", size=12, color="#1a1a1a"),
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(text="Global Distribution of Trial Sites", font_size=14, x=0),
            geo=dict(
                bgcolor="white", lakecolor="#d0e8f5", landcolor="#f0f0f0",
                showframe=True, framecolor="#cccccc",
                showcoastlines=True, coastlinecolor="#cccccc",
                showcountries=True, countrycolor="#dddddd",
            ),
            coloraxis_colorbar_title="Trials",
        )
        st.plotly_chart(fig5_map, use_container_width=True, config=PUB_EXPORT)

        top10 = geo_counts.head(10)
        fig5_bar = pub_bar(top10, "Country", "Trials", color="#2a6099",
                           title="Top 10 Countries by Trial Count", xlab="Country", height=380)
        st.plotly_chart(fig5_bar, use_container_width=True, config=PUB_EXPORT)

        total_geo = geo_counts["Trials"].sum()
        top3_geo = geo_counts.head(3)
        c1, c2, c3 = st.columns(3)
        for col, (_, row) in zip([c1, c2, c3], top3_geo.iterrows()):
            col.metric(row["Country"], f"{row['Trials']} ({100*row['Trials']/total_geo:.0f}%)")

        fig5_csv = geo_counts.copy()
        fig5_csv["% of total"] = (fig5_csv["Trials"] / total_geo * 100).round(1)
        st.download_button("Fig 5 data (CSV)", fig5_csv.to_csv(index=False),
                           "fig5_geographic_distribution.csv", "text/csv")
    else:
        st.info("No country data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Fig 6 — Innovation signals (product type + modality over time)
    # ------------------------------------------------------------------
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Figure 6 — Innovation signals")

    # 6a: Autologous vs allogeneic by start year
    df_innov = df_filt[df_filt["StartYear"].notna()].copy()
    df_innov["StartYear"] = df_innov["StartYear"].astype(int)

    if not df_innov.empty:
        product_year = (
            df_innov.groupby(["StartYear", "ProductType"]).size()
            .reset_index(name="Trials")
        )
        fig6a = px.bar(
            product_year, x="StartYear", y="Trials", color="ProductType",
            barmode="stack", height=420, template="plotly_white",
            color_discrete_map={
                "Autologous": "#2a6099",
                "Allogeneic/Off-the-shelf": "#d95f02",
                "Unclear": "#999999",
            },
            labels={"StartYear": "Start year", "Trials": "Number of trials", "ProductType": "Product type"},
        )
        fig6a.update_layout(
            **PUB_LAYOUT,
            title=dict(text="Autologous vs. Allogeneic CAR Cell Therapies by Start Year", font_size=14, x=0),
            xaxis=dict(tickmode="linear", dtick=1, tickformat="d"),
        )
        fig6a.update_xaxes(showgrid=False)
        fig6a.update_yaxes(gridcolor="#e5e5e5")
        st.plotly_chart(fig6a, use_container_width=True, config=PUB_EXPORT)

        # 6b: Therapy modality (derive from TargetCategory)
        def _modality(target: str) -> str:
            t = str(target)
            if t == "CAR-NK":
                return "CAR-NK"
            if t == "CAAR-T":
                return "CAAR-T"
            if t in ("CAR-Treg", "CD6"):
                return "CAR-Treg"
            return "CAR-T"

        df_innov["Modality"] = df_innov["TargetCategory"].apply(_modality)
        modality_counts = (
            df_innov["Modality"].value_counts()
            .rename_axis("Modality").reset_index(name="Trials")
        )
        fig6b = pub_bar(
            modality_counts, "Modality", "Trials", color="#2a6099",
            title="Cell Therapy Modality Distribution", xlab="Modality", height=380,
        )
        st.plotly_chart(fig6b, use_container_width=True, config=PUB_EXPORT)

        # Summary stats
        total_prod = len(df_innov)
        auto_n = int((df_innov["ProductType"] == "Autologous").sum())
        allo_n = int((df_innov["ProductType"] == "Allogeneic/Off-the-shelf").sum())
        carnk_n = int((df_innov["Modality"] == "CAR-NK").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Autologous", f"{auto_n} ({100*auto_n/total_prod:.0f}%)")
        c2.metric("Allogeneic/Off-the-shelf", f"{allo_n} ({100*allo_n/total_prod:.0f}%)")
        c3.metric("CAR-NK modality", f"{carnk_n} ({100*carnk_n/total_prod:.0f}%)")

        fig6_csv = pd.merge(
            product_year.rename(columns={"ProductType": "Category", "Trials": "n_product"}),
            df_innov.groupby(["StartYear", "Modality"]).size().reset_index(name="n_modality"),
            left_on="StartYear", right_on="StartYear", how="outer",
        )
        st.download_button("Fig 6 data (CSV)", product_year.to_csv(index=False),
                           "fig6_innovation_signals.csv", "text/csv")
    else:
        st.info("No start year data available for innovation analysis.")
    st.markdown("</div>", unsafe_allow_html=True)

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
Studies were included if they: (1) described a CAR-based cellular therapy (CAR-T,
CAR-NK, CAAR-T, or CAR-Treg); and (2) targeted a systemic autoimmune or rheumatic
disease. No restriction was applied to study phase, sponsor type, or country.

Exclusion Criteria
------------------
Studies were excluded if they met any of the following criteria:
    (1) The NCT identifier appeared on a manually curated exclusion list ({n_hard}
        pre-specified identifiers) compiled upon initial review to remove studies
        that were retrieved by the search query but were clearly outside scope.
    (2) Text fields (conditions, title, brief summary, interventions) contained
        one or more of {n_indication} predefined oncology or haematologic
        malignancy keywords (e.g., multiple myeloma, leukemia, lymphoma, solid
        tumour, AL amyloidosis, stem cell transplantation).
Non-oncology immune-mediated diseases outside classical rheumatology (e.g.,
multiple sclerosis, myasthenia gravis, NMOSD, pemphigus vulgaris, anti-GBM
disease, antiphospholipid syndrome, AIHA, immune thrombocytopenia, Graves
disease, membranous nephropathy) were retained and classified as
"Other immune-mediated" to enable landscape analysis of CAR-T use beyond
rheumatology while preserving the ability to filter by disease category.
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
enrolling ≥2 distinct systemic autoimmune diseases), or "Autoimmune_other" (for
studies describing autoimmune conditions not matching a specific entity). Assignment
used hierarchical rule-based matching of normalised text drawn from the conditions,
title, brief summary, and interventions fields. Condition-field matches took precedence
over full-text matches; multi-disease trials were identified when ≥2 systemic entities
were detected within the conditions field.

Target category. The primary cell therapy target was assigned from intervention text
using a priority-ordered ruleset: CAR-NK constructs were identified first (terms:
{", ".join(CAR_NK_TERMS)}), followed by CAAR-T ({", ".join(CAAR_T_TERMS)}),
CAR-Treg ({", ".join(CAR_TREG_TERMS)}), then specific antigen targets (CD19, BCMA,
dual CD19/BCMA, CD19/BAFF, CD20, CD6, CD7). Studies containing CAR-related terms
but no identifiable specific target were labelled "CAR-T_unspecified".

Product type. Studies were classified as "Autologous", "Allogeneic/Off-the-shelf",
or "Unclear" based on presence of corresponding keywords in normalised text (e.g.,
autologous, autoleucel; allogeneic, off-the-shelf, ucart, universal CAR-T).

Data Processing
---------------
All processing was performed in Python (pandas {pd.__version__}) using a custom
ETL pipeline. Text normalisation included lowercasing, Unicode normalisation
(e.g., "sjögren" → "sjogren"), and removal of non-alphanumeric characters. Term
matching used whole-word boundary matching for short terms (≤3 characters) and
substring matching for longer terms. Classification rules and term dictionaries are
versioned in the accompanying config.py file.

Dataset Snapshot
----------------
The frozen dataset used for all analyses was generated on {snapshot_date}. CSV files
containing the trial-level dataset (trials.csv) and site-level dataset (sites.csv)
are provided as supplementary data. All analyses are reproducible from the frozen
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

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
        data=ontology_df.to_csv(index=False),
        file_name=f"car_t_classification_ontology_{snap_date}.csv",
        mime="text/csv",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
        data=excl_df[["NCTId"]].to_csv(index=False),
        file_name=f"car_t_excluded_nct_ids_{snap_date}.csv",
        mime="text/csv",
    )
    st.markdown("</div>", unsafe_allow_html=True)
