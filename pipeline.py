import json
import os
import re
import requests
import pandas as pd
from datetime import datetime

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
)

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def _safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("sjögren", "sjogren")
    text = text.replace("r/r", "relapsed refractory")
    text = text.replace("b-cell", "b cell")
    text = text.replace("t-cell", "t cell")
    text = text.replace("nk-cell", "nk cell")
    text = re.sub(r"[^a-z0-9/+\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _row_text(row: dict) -> str:
    return _normalize_text(
        " | ".join(
            [
                _safe_text(row.get("Conditions")),
                _safe_text(row.get("BriefTitle")),
                _safe_text(row.get("BriefSummary")),
                _safe_text(row.get("Interventions")),
            ]
        )
    )


def _contains_any(text: str | None, terms: list[str]) -> bool:
    if not text:
        return False
    normalized = _normalize_text(text)
    return any(_term_in_text(normalized, term) for term in terms)


def _term_in_text(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False
    if len(normalized_term) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", normalized_text))
    return normalized_term in normalized_text


def _match_terms(text: str, term_map: dict[str, list[str]]) -> list[str]:
    matches = []
    for label, terms in term_map.items():
        if any(_term_in_text(text, term) for term in terms):
            matches.append(label)
    return matches


_DISEASE_TERMS = {
    "SLE": ["systemic lupus erythematosus", "lupus nephritis", "sle"],
    "SSc": ["systemic sclerosis", "systemic scleroderma", "scleroderma", "ssc"],
    "IIM": [
        "idiopathic inflammatory myopathies", "idiopathic inflammatory myopathy",
        "juvenile idiopathic inflammatory myopathy", "dermatomyositis", "polymyositis",
        "immune mediated necrotizing myopathy", "antisynthetase syndrome",
        "anti synthetase syndrome", "myositis", "iim",
    ],
    "Sjogren": ["sjogren syndrome", "sjogren s syndrome", "sjogren disease", "sjd"],
    "AAV": [
        "anca associated vasculitis", "gpa", "granulomatosis with polyangiitis",
        "granulomatous polyangiitis", "mpa", "microscopic polyangiitis",
    ],
    "RA": ["rheumatoid arthritis", "ra"],
    "IgG4-RD": ["igg4 related disease", "igg4 rd"],
    "Behcet": ["behcet disease", "behcet s disease"],
    "T1D": ["type 1 diabetes", "stage 3 type 1 diabetes", "t1d"],
    "cGVHD": ["chronic graft versus host disease", "chronic graft versus host", "cgvhd"],
    "Neurologic_autoimmune": [
        "neurological autoimmune diseases", "neurologic autoimmune diseases",
        "neurologic immune disorders", "neurological immune disorders",
    ],
}

_AUTOIMMUNE_OTHER_TERMS = [
    "hemophagocytic lymphohistiocytosis", "hlh",
    "hidradenitis suppurativa",
    "cppd", "calcium pyrophosphate deposition",
]

_BROAD_BASKET_TERMS = [
    "b cell mediated autoimmune disease", "b cell mediated autoimmune diseases",
    "b cell related autoimmune disease", "b cell related autoimmune diseases",
    "severe refractory systemic autoimmune rheumatic disease",
]

_BROAD_AUTOIMMUNE_PHRASES = [
    "autoimmune disease", "autoimmune diseases",
    "relapsed refractory autoimmune disease", "relapsed refractory autoimmune diseases",
    "systemic autoimmune disease", "systemic autoimmune diseases",
]


def _classify_disease(row: dict) -> tuple[list[str], str, str]:
    """Return (disease_entities, trial_design, primary_entity).

    disease_entities: every specific disease label matched (pipe-join for DiseaseEntities column)
    trial_design:     "Single disease" | "Basket/Multidisease"
    primary_entity:   single label for charts/display (DiseaseEntity column)
    """
    conditions_raw = _safe_text(row.get("Conditions"))
    full_text = _row_text(row)

    condition_chunks = [_normalize_text(c) for c in conditions_raw.split("|") if _normalize_text(c)]
    matched_conditions = sorted({m for chunk in condition_chunks for m in _match_terms(chunk, _DISEASE_TERMS)})
    matched_full = _match_terms(full_text, _DISEASE_TERMS)
    all_matched = sorted(set(matched_conditions + matched_full))

    if all_matched:
        trial_design = "Basket/Multidisease" if len(all_matched) >= 2 else "Single disease"
        primary = all_matched[0] if len(all_matched) == 1 else "Basket/Multidisease"
        return all_matched, trial_design, primary

    if _contains_any(full_text, _AUTOIMMUNE_OTHER_TERMS):
        return ["Autoimmune_other"], "Single disease", "Autoimmune_other"

    if _contains_any(full_text, OTHER_IMMUNE_MEDIATED_TERMS):
        return ["Other immune-mediated"], "Single disease", "Other immune-mediated"

    if any(term in full_text for term in _BROAD_BASKET_TERMS):
        return ["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease"

    if any(p in full_text for p in _BROAD_AUTOIMMUNE_PHRASES):
        return ["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease"

    for entity, syns in DISEASE_ENTITIES.items():
        specific_syns = [_normalize_text(s) for s in syns if len(str(s)) > 3]
        if any(s in full_text for s in specific_syns):
            return [entity], "Single disease", entity

    if _contains_any(full_text, GENERIC_AUTOIMMUNE_TERMS):
        return ["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease"

    return ["Unclassified"], "Single disease", "Unclassified"


def _assign_disease_entity(row: dict) -> str:
    return _classify_disease(row)[2]


def _is_hard_excluded(nct_id: str) -> bool:
    return nct_id.strip() in HARD_EXCLUDED_NCT_IDS


def _is_indication_excluded(row: dict) -> bool:
    text = _row_text(row)
    return _contains_any(text, EXCLUDED_INDICATION_TERMS)


def _exclude_by_indication(row: dict) -> bool:
    if _is_hard_excluded(_safe_text(row.get("NCTId"))):
        return True
    return _is_indication_excluded(row)


def _assign_target(row: dict) -> str:
    text = _row_text(row)

    has_car_nk = _contains_any(text, CAR_NK_TERMS) or ("car nk" in text)
    has_caar_t = _contains_any(text, CAAR_T_TERMS)
    has_car_treg = _contains_any(text, CAR_TREG_TERMS) or ("treg" in text and "car" in text)

    has_cd19 = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["CD19"]) or ("cd19" in text)
    has_bcma = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["BCMA"]) or ("bcma" in text) or ("b cell maturation antigen" in text)
    has_baff = "baff" in text
    has_cd20 = "cd20" in text
    has_cd6 = "cd6" in text
    has_cd7 = "cd7" in text

    if has_car_nk:
        if has_cd19 and has_bcma:
            return "CD19/BCMA dual"
        if has_cd19:
            return "CD19"
        return "CAR-NK"

    if has_caar_t:
        return "CAAR-T"
    if has_car_treg:
        if has_cd6:
            return "CD6"
        return "CAR-Treg"
    if has_cd19 and has_bcma:
        return "CD19/BCMA dual"
    if has_cd19 and has_baff:
        return "CD19/BAFF dual"
    if has_cd19:
        return "CD19"
    if has_bcma:
        return "BCMA"
    if has_cd20:
        return "CD20"
    if has_cd6:
        return "CD6"
    if has_cd7:
        return "CD7"
    if _contains_any(text, CAR_CORE_TERMS):
        return "CAR-T_unspecified"
    return "Other_or_unknown"


def _assign_product_type(row: dict) -> str:
    text = _row_text(row)

    if "autoleucel" in text or "autologous" in text:
        return "Autologous"

    strong_allo_terms = [
        "ucart",
        "ucar",
        "universal car t",
        "off the shelf",
        "allogeneic",
        "healthy donor",
        "donor derived",
        "donor sourced",
    ]
    if any(term in text for term in strong_allo_terms):
        return "Allogeneic/Off-the-shelf"

    if _contains_any(text, ALLOGENEIC_MARKERS):
        return "Allogeneic/Off-the-shelf"
    if _contains_any(text, AUTOL_MARKERS):
        return "Autologous"

    return "Unclear"


def fetch_raw_trials(max_records: int = 1000, statuses: list[str] | None = None) -> list[dict]:
    term_query = (
        "("
        ' "CAR T" OR "CAR-T" OR "chimeric antigen receptor" '
        ' OR "CAR-NK" OR "CAR NK" OR "CAAR-T" OR "CAR-Treg" '
        ") AND ("
        ' lupus OR nephritis OR "systemic lupus erythematosus" '
        ' OR "idiopathic inflammatory myopathy" OR myositis '
        ' OR "systemic sclerosis" OR scleroderma OR vasculitis '
        ' OR "rheumatoid arthritis" OR sjogren OR "sjogren syndrome" '
        ' OR "igg4 related disease" OR behcet OR "autoimmune disease" '
        ' OR "type 1 diabetes" OR "graft versus host disease" '
        ")"
    )

    params = {"query.term": term_query, "pageSize": 200, "countTotal": "true"}
    if statuses:
        params["filter.overallStatus"] = ",".join(statuses)

    studies = []
    while True:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            raise requests.HTTPError(f"ClinicalTrials.gov API error {resp.status_code}: {resp.text}")
        data = resp.json()
        studies.extend(data.get("studies", []))
        if len(studies) >= max_records:
            break
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
    return studies[:max_records]


def _flatten_study(study: dict) -> dict:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    cond = ps.get("conditionsModule", {})
    design = ps.get("designModule", {})
    desc = ps.get("descriptionModule", {})
    loc_mod = ps.get("contactsLocationsModule", {})
    arms_mod = ps.get("armsInterventionsModule", {})
    sponsor_mod = ps.get("sponsorCollaboratorsModule", {})

    phase_list = design.get("phases") or []
    phase = "|".join(str(p) for p in phase_list if p) if phase_list else (design.get("phase") or "Unknown")

    interventions = []
    for inter in (arms_mod.get("interventions") or []):
        label = inter.get("name") or inter.get("description")
        if label:
            interventions.append(label)

    countries = sorted({loc.get("country") for loc in (loc_mod.get("locations") or []) if loc.get("country")})

    return {
        "NCTId": ident.get("nctId"),
        "BriefTitle": ident.get("briefTitle"),
        "OverallStatus": status.get("overallStatus"),
        "Phase": phase,
        "Conditions": "|".join(cond.get("conditions") or []) or None,
        "Interventions": "|".join(sorted(set(interventions))) or None,
        "StartDate": (status.get("startDateStruct") or {}).get("date"),
        "LastUpdatePostDate": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
        "EnrollmentCount": (design.get("enrollmentInfo") or {}).get("count"),
        "Countries": "|".join(countries) or None,
        "BriefSummary": desc.get("briefSummary"),
        "LeadSponsor": (sponsor_mod.get("leadSponsor") or {}).get("name"),
    }


def _extract_sites(study: dict) -> list[dict]:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    loc_mod = ps.get("contactsLocationsModule", {})

    sites = []
    for loc in (loc_mod.get("locations") or []):
        sites.append(
            {
                "NCTId": ident.get("nctId"),
                "BriefTitle": ident.get("briefTitle"),
                "OverallStatus": status.get("overallStatus"),
                "Facility": loc.get("facility"),
                "City": loc.get("city"),
                "State": loc.get("state"),
                "Zip": loc.get("zip"),
                "Country": loc.get("country"),
                "SiteStatus": loc.get("status"),
            }
        )
    return sites


def _process_trials_from_studies(studies: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Classify studies and return (df, prisma_counts)."""
    df = pd.DataFrame([_flatten_study(s) for s in studies])

    n_fetched = len(df)
    df = df.dropna(subset=["NCTId"]).drop_duplicates(subset=["NCTId"])
    n_after_dedup = len(df)
    n_duplicates = n_fetched - n_after_dedup

    disease_results = df.apply(lambda r: _classify_disease(r.to_dict()), axis=1)
    df["DiseaseEntities"] = disease_results.apply(lambda x: "|".join(x[0]))
    df["TrialDesign"] = disease_results.apply(lambda x: x[1])
    df["DiseaseEntity"] = disease_results.apply(lambda x: x[2])

    hard_mask = df["NCTId"].apply(_is_hard_excluded)
    n_hard_excluded = int(hard_mask.sum())

    df_after_hard = df[~hard_mask].copy()
    indication_mask = df_after_hard.apply(lambda r: _is_indication_excluded(r.to_dict()), axis=1)
    n_indication_excluded = int(indication_mask.sum())

    df = df_after_hard[~indication_mask].copy()
    n_included = len(df)

    df["TargetCategory"] = df.apply(lambda r: _assign_target(r.to_dict()), axis=1)
    df["ProductType"] = df.apply(lambda r: _assign_product_type(r.to_dict()), axis=1)

    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
    df["StartYear"] = df["StartDate"].dt.year
    df["LastUpdatePostDate"] = pd.to_datetime(df["LastUpdatePostDate"], errors="coerce")
    df["SnapshotDate"] = datetime.utcnow().date().isoformat()

    prisma = {
        "n_fetched": n_fetched,
        "n_duplicates_removed": n_duplicates,
        "n_after_dedup": n_after_dedup,
        "n_hard_excluded": n_hard_excluded,
        "n_indication_excluded": n_indication_excluded,
        "n_total_excluded": n_hard_excluded + n_indication_excluded,
        "n_included": n_included,
    }

    return df.reset_index(drop=True), prisma


def _sites_from_studies(studies: list[dict]) -> pd.DataFrame:
    site_rows = []
    for s in studies:
        site_rows.extend(_extract_sites(s))
    df_sites = pd.DataFrame(site_rows)
    if df_sites.empty:
        return df_sites
    return df_sites.dropna(subset=["NCTId"]).drop_duplicates().reset_index(drop=True)


def build_all_from_api(
    max_records: int = 2000,
    statuses: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fetch from live API and return (df_trials, df_sites, prisma_counts)."""
    studies = fetch_raw_trials(max_records=max_records, statuses=statuses)
    df, prisma = _process_trials_from_studies(studies)
    df_sites = _sites_from_studies(studies)
    return df, df_sites, prisma


# ---------------------------------------------------------------------------
# Backward-compatible wrappers
# ---------------------------------------------------------------------------

def build_clean_dataframe(max_records: int = 1000, statuses: list[str] | None = None) -> pd.DataFrame:
    df, _ = _process_trials_from_studies(fetch_raw_trials(max_records=max_records, statuses=statuses))
    return df


def build_sites_dataframe(max_records: int = 1000, statuses: list[str] | None = None) -> pd.DataFrame:
    return _sites_from_studies(fetch_raw_trials(max_records=max_records, statuses=statuses))


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

def save_snapshot(
    df: pd.DataFrame,
    df_sites: pd.DataFrame,
    prisma: dict,
    snapshot_dir: str = "snapshots",
    statuses: list[str] | None = None,
) -> str:
    """Save a frozen dataset to snapshots/<date>/. Returns the snapshot date string."""
    snapshot_date = datetime.utcnow().date().isoformat()
    out_dir = os.path.join(snapshot_dir, snapshot_date)
    os.makedirs(out_dir, exist_ok=True)

    df.to_csv(os.path.join(out_dir, "trials.csv"), index=False)
    df_sites.to_csv(os.path.join(out_dir, "sites.csv"), index=False)

    with open(os.path.join(out_dir, "prisma.json"), "w") as f:
        json.dump(prisma, f, indent=2)

    metadata = {
        "snapshot_date": snapshot_date,
        "created_utc": datetime.utcnow().isoformat(),
        "statuses_filter": statuses or [],
        "n_trials": len(df),
        "n_sites": len(df_sites),
        "api_base_url": BASE_URL,
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return snapshot_date


def load_snapshot(
    snapshot_date: str,
    snapshot_dir: str = "snapshots",
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load a frozen snapshot. Returns (df_trials, df_sites, prisma_counts)."""
    out_dir = os.path.join(snapshot_dir, snapshot_date)

    df = pd.read_csv(os.path.join(out_dir, "trials.csv"))
    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
    df["LastUpdatePostDate"] = pd.to_datetime(df["LastUpdatePostDate"], errors="coerce")
    # Back-compat: snapshots created before DiseaseEntities/TrialDesign were added
    if "DiseaseEntities" not in df.columns:
        df["DiseaseEntities"] = df["DiseaseEntity"].fillna("Unclassified")
    if "TrialDesign" not in df.columns:
        df["TrialDesign"] = "Single disease"

    df_sites_path = os.path.join(out_dir, "sites.csv")
    if os.path.exists(df_sites_path):
        df_sites = pd.read_csv(df_sites_path)
    else:
        df_sites = pd.DataFrame()

    prisma_path = os.path.join(out_dir, "prisma.json")
    if os.path.exists(prisma_path):
        with open(prisma_path) as f:
            prisma = json.load(f)
    else:
        prisma = {}

    return df, df_sites, prisma


def list_snapshots(snapshot_dir: str = "snapshots") -> list[str]:
    """Return sorted list of available snapshot date strings (newest first)."""
    if not os.path.isdir(snapshot_dir):
        return []
    dates = [
        d for d in os.listdir(snapshot_dir)
        if os.path.isdir(os.path.join(snapshot_dir, d))
        and os.path.exists(os.path.join(snapshot_dir, d, "trials.csv"))
    ]
    return sorted(dates, reverse=True)
