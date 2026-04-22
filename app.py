import streamlit as st
import pandas as pd
import plotly.express as px

from pipeline import build_clean_dataframe, build_sites_dataframe

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
def load_trials(max_records: int = 2000, statuses: tuple[str, ...] = ()) -> pd.DataFrame:
    statuses_list = list(statuses) if statuses else None
    return build_clean_dataframe(max_records=max_records, statuses=statuses_list)

@st.cache_data(ttl=60 * 60)
def load_sites(max_records: int = 2000, statuses: tuple[str, ...] = ()) -> pd.DataFrame:
    statuses_list = list(statuses) if statuses else None
    return build_sites_dataframe(max_records=max_records, statuses=statuses_list)

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

st.sidebar.header("Data pull")
selected_statuses = st.sidebar.multiselect(
    "Statuses to pull",
    STATUS_OPTIONS,
    default=["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"],
)

with st.spinner("Fetching and processing ClinicalTrials.gov data..."):
    df = load_trials(statuses=tuple(selected_statuses))
    df_sites = load_sites(statuses=tuple(selected_statuses))

if df.empty:
    st.error("No studies were returned. Try broadening the status filters.")
    st.stop()

st.sidebar.header("Filters")

disease_options = ["All"] + sorted(df["DiseaseEntity"].dropna().unique().tolist())
disease_sel = st.sidebar.selectbox("Disease entity", disease_options, index=0)

phase_options = ["All"] + sorted(df["Phase"].fillna("Unknown").unique().tolist())
phase_sel = st.sidebar.selectbox("Phase", phase_options, index=0)

target_options = ["All"] + sorted(df["TargetCategory"].dropna().unique().tolist())
target_sel = st.sidebar.selectbox("Target category", target_options, index=0)

status_options = ["All"] + sorted(df["OverallStatus"].dropna().unique().tolist())
status_sel = st.sidebar.selectbox("Overall status", status_options, index=0)

all_countries = set()
for cs in df["Countries"].dropna():
    for c in str(cs).split("|"):
        c = c.strip()
        if c:
            all_countries.add(c)

country_options = ["All"] + sorted(all_countries)
country_sel = st.sidebar.selectbox("Country", country_options, index=0)

mask = pd.Series(True, index=df.index)

if disease_sel != "All":
    mask &= df["DiseaseEntity"] == disease_sel

if phase_sel != "All":
    mask &= df["Phase"].fillna("Unknown") == phase_sel

if target_sel != "All":
    mask &= df["TargetCategory"] == target_sel

if status_sel != "All":
    mask &= df["OverallStatus"] == status_sel

if country_sel != "All":
    mask &= df["Countries"].fillna("").str.contains(country_sel, case=False, na=False)

df_filt = df[mask].copy()
df_filt["Phase"] = df_filt["Phase"].fillna("Unknown")
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

        germany_study_view = germany_study_view[
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
        ].sort_values(["DiseaseEntity", "NCTId"], na_position="last")

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
    metric_card("Studies active in Germany", german_trials_count, "Grouped by NCTId")
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

tab_overview, tab_geo, tab_data = st.tabs(["Overview", "Geography / Map", "Data"])

with tab_overview:
    left, right = st.columns([1.05, 1])

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Trials by disease entity")
        counts_disease = (
            df_filt["DiseaseEntity"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("DiseaseEntity")
            .reset_index(name="Count")
        )
        if not counts_disease.empty:
            st.plotly_chart(make_bar(counts_disease, "DiseaseEntity", "Count", color="#21b3a3"), width="stretch")
        else:
            st.info("No trials for the current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Trials by phase")
        counts_phase = (
            df_filt["Phase"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("Phase")
            .reset_index(name="Count")
        )
        if not counts_phase.empty:
            st.plotly_chart(make_bar(counts_phase, "Phase", "Count", color="#d38a5a"), width="stretch")
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
            st.plotly_chart(make_bar(counts_target, "TargetCategory", "Count", color="#6fb7ff"), width="stretch")
        else:
            st.info("No trials for the current filter selection.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Trials by start year")
        counts_year = (
            df_filt.dropna(subset=["StartYear"])["StartYear"]
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
            fig_year.update_xaxes(color=THEME["muted"])
            fig_year.update_yaxes(gridcolor=THEME["grid"], color=THEME["muted"])
            st.plotly_chart(fig_year, width="stretch")
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
            color_continuous_scale="Tealgrn",
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
        st.plotly_chart(fig_world, width="stretch")

        c1, c2 = st.columns([1.15, 0.85])
        with c1:
            st.markdown("**Country counts**")
            st.dataframe(country_counts, width="stretch", height=320, hide_index=True)
        with c2:
            st.markdown("**Top countries**")
            st.plotly_chart(
                make_bar(country_counts.head(12), "Country", "Count", height=320, color="#21b3a3"),
                width="stretch",
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
        )

        g1, g2, g3 = st.columns(3)
        with g1:
            metric_card("Open German sites", len(germany_open_sites), "Recruiting / active site rows")
        with g2:
            metric_card("German cities", germany_open_sites["City"].dropna().nunique(), "Cities with open sites")
        with g3:
            metric_card("German studies", germany_study_view["NCTId"].nunique() if not germany_study_view.empty else 0, "Grouped by NCTId")

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("**Open sites by city**")
            st.plotly_chart(
                make_bar(germany_city_counts, "City", "OpenSiteCount", height=380, color="#d38a5a"),
                width="stretch",
            )
        with c2:
            st.markdown("**Germany city table**")
            st.dataframe(germany_city_counts, width="stretch", height=380, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tab_data:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Trial table")

    show_cols = [
        "NCTId",
        "NCTLink",
        "BriefTitle",
        "DiseaseEntity",
        "TargetCategory",
        "ProductType",
        "Phase",
        "OverallStatus",
        "StartYear",
        "Countries",
        "LeadSponsor",
    ]

    st.dataframe(
        df_filt[show_cols],
        width="stretch",
        height=460,
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
        st.dataframe(
            germany_study_view,
            width="stretch",
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

    d1, d2 = st.columns(2)
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