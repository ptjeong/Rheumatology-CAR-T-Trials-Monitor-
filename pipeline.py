import requests
import pandas as pd
from datetime import datetime

from config import (
    DISEASE_ENTITIES,
    EXCLUDED_INDICATION_TERMS,
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


def _row_text(row: dict) -> str:
    return " | ".join(
        [
            _safe_text(row.get("Conditions")),
            _safe_text(row.get("BriefTitle")),
            _safe_text(row.get("BriefSummary")),
            _safe_text(row.get("Interventions")),
        ]
    ).lower()


def _contains_any(text: str | None, terms: list[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _assign_disease_entity(row: dict) -> str:
    conditions_text = _safe_text(row.get("Conditions")).lower()
    full_text = _row_text(row)

    basket_terms = {
        "SLE": [
            "systemic lupus erythematosus",
            "lupus nephritis",
            "lupus erythematosus, systemic",
        ],
        "SSc": [
            "systemic sclerosis",
            "systemic scleroderma",
            "diffuse cutaneous systemic sclerosis",
        ],
        "IIM": [
            "idiopathic inflammatory myopathies",
            "idiopathic inflammatory myopathy",
            "dermatomyositis",
            "polymyositis",
            "myositis",
            "immune-mediated necrotizing myopathy",
            "antisynthetase syndrome",
            "anti-synthetase syndrome",
            "inflammatory myopathy",
            "inflammatory myopathies",
        ],
        "Sjogren": [
            "sjogren syndrome",
            "sjogren's syndrome",
            "primary sjogren syndrome",
            "primary sjogren's syndrome",
            "primary sjögren syndrome",
        ],
        "AAV": [
            "anca-associated vasculitis",
            "anca associated vasculitis",
            "microscopic polyangiitis",
            "granulomatous polyangiitis",
        ],
        "RA": [
            "rheumatoid arthritis",
        ],
        "IgG4-RD": [
            "igg4 related disease",
            "igg4-related disease",
        ],
        "Behcet": [
            "behcet disease",
            "behcet's disease",
        ],
    }

    matched_entities = []
    for entity, terms in basket_terms.items():
        if any(term in conditions_text for term in terms):
            matched_entities.append(entity)

    if len(matched_entities) >= 2:
        return "Basket/Multidisease"
    if len(matched_entities) == 1:
        return matched_entities[0]

    broad_autoimmune_phrases = [
        "autoimmune disease",
        "autoimmune diseases",
        "relapsed/refractory autoimmune disease",
        "relapsed/refractory autoimmune diseases",
        "systemic autoimmune disease",
        "systemic autoimmune diseases",
    ]

    if any(p in full_text for p in broad_autoimmune_phrases):
        return "Autoimmune_other"

    for entity, syns in DISEASE_ENTITIES.items():
        specific_syns = [s.lower() for s in syns if len(s) > 5]
        if any(s in full_text for s in specific_syns):
            return entity

    if _contains_any(full_text, GENERIC_AUTOIMMUNE_TERMS):
        return "Autoimmune_other"

    return "Unclassified"


def _exclude_by_indication(row: dict) -> bool:
    text = _row_text(row)
    return _contains_any(text, EXCLUDED_INDICATION_TERMS)


def _assign_target(row: dict) -> str:
    text = _row_text(row)

    has_cd19 = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["CD19"]) or ("cd19" in text)
    has_bcma = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["BCMA"]) or ("bcma" in text)

    has_car_nk = _contains_any(text, CAR_NK_TERMS)
    has_caar_t = _contains_any(text, CAAR_T_TERMS)
    has_car_treg = _contains_any(text, CAR_TREG_TERMS)

    if has_car_nk:
        return "CAR-NK"
    if has_caar_t:
        return "CAAR-T"
    if has_car_treg:
        return "CAR-Treg"
    if has_cd19 and has_bcma:
        return "CD19/BCMA dual"
    if has_cd19:
        return "CD19"
    if has_bcma:
        return "BCMA"
    if _contains_any(text, CAR_CORE_TERMS):
        return "CAR-T_unspecified"
    return "Other_or_unknown"


def _assign_product_type(row: dict) -> str:
    text = _row_text(row)

    if "autoleucel" in text:
        return "Autologous"

    strong_allo_terms = [
        "ucart",
        "ucar",
        "universal car-t",
        "universal car t",
        "off-the-shelf",
        "off the shelf",
        "allogeneic",
        "allo1",
        "healthy donor",
        "donor-derived",
        "donor derived",
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
        " \"CAR T\" OR \"CAR-T\" OR \"chimeric antigen receptor\" "
        " OR \"CAR-NK\" OR \"CAR NK\" OR \"CAAR-T\" OR \"CAR-Treg\" "
        ") AND ("
        " lupus OR nephritis OR "
        " \"systemic lupus erythematosus\" OR \"idiopathic inflammatory myopathy\" "
        " OR myositis OR \"systemic sclerosis\" OR scleroderma OR vasculitis "
        " OR \"rheumatoid arthritis\" OR sjogren OR \"sjogren syndrome\" "
        " OR \"igg4 related disease\" OR behcet OR \"autoimmune disease\" "
        ")"
    )

    params = {
        "query.term": term_query,
        "pageSize": 200,
        "countTotal": "true",
    }

    if statuses:
        params["filter.overallStatus"] = ",".join(statuses)

    studies = []

    while True:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            raise requests.HTTPError(
                f"ClinicalTrials.gov API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        studies.extend(data.get("studies", []))

        if len(studies) >= max_records:
            break

        token = data.get("nextPageToken")
        if not token:
            break

        params["pageToken"] = token

    return studies


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

    nct_id = ident.get("nctId")
    title = ident.get("briefTitle")
    overall_status = status.get("overallStatus")
    start_date = (status.get("startDateStruct") or {}).get("date")
    last_update = (status.get("lastUpdatePostDateStruct") or {}).get("date")

    phase_list = design.get("phases") or []
    if isinstance(phase_list, list) and len(phase_list) > 0:
        phase = "|".join(str(p) for p in phase_list if p)
    else:
        possible_phase = design.get("phase")
        phase = possible_phase.strip() if isinstance(possible_phase, str) and possible_phase.strip() else "Unknown"

    conditions = cond.get("conditions") or []
    conditions_str = "|".join(conditions) if conditions else None

    brief_summary = desc.get("briefSummary")

    interventions = []
    for inter in (arms_mod.get("interventions") or []):
        label = inter.get("name") or inter.get("description")
        if label:
            interventions.append(label)
    interventions_str = "|".join(sorted(set(interventions))) if interventions else None

    countries = []
    for loc in (loc_mod.get("locations") or []):
        c = loc.get("country")
        if c:
            countries.append(c)
    countries_str = "|".join(sorted(set(countries))) if countries else None

    enrollment = (design.get("enrollmentInfo") or {}).get("count")
    lead_sponsor = (sponsor_mod.get("leadSponsor") or {}).get("name")

    return {
        "NCTId": nct_id,
        "BriefTitle": title,
        "OverallStatus": overall_status,
        "Phase": phase,
        "Conditions": conditions_str,
        "Interventions": interventions_str,
        "StartDate": start_date,
        "LastUpdatePostDate": last_update,
        "EnrollmentCount": enrollment,
        "Countries": countries_str,
        "BriefSummary": brief_summary,
        "LeadSponsor": lead_sponsor,
    }


def _extract_sites(study: dict) -> list[dict]:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    loc_mod = ps.get("contactsLocationsModule", {})

    nct_id = ident.get("nctId")
    title = ident.get("briefTitle")
    overall_status = status.get("overallStatus")

    sites = []
    for loc in (loc_mod.get("locations") or []):
        sites.append(
            {
                "NCTId": nct_id,
                "BriefTitle": title,
                "OverallStatus": overall_status,
                "Facility": loc.get("facility"),
                "City": loc.get("city"),
                "State": loc.get("state"),
                "Zip": loc.get("zip"),
                "Country": loc.get("country"),
                "SiteStatus": loc.get("status"),
            }
        )
    return sites


def build_clean_dataframe(max_records: int = 1000, statuses: list[str] | None = None) -> pd.DataFrame:
    studies = fetch_raw_trials(max_records=max_records, statuses=statuses)
    rows = [_flatten_study(s) for s in studies]
    df = pd.DataFrame(rows)

    df = df.dropna(subset=["NCTId"]).drop_duplicates(subset=["NCTId"])

    df["DiseaseEntity"] = df.apply(lambda r: _assign_disease_entity(r.to_dict()), axis=1)
    mask_excl = df.apply(lambda r: _exclude_by_indication(r.to_dict()), axis=1)
    df = df[~mask_excl]

    df["TargetCategory"] = df.apply(lambda r: _assign_target(r.to_dict()), axis=1)
    df["ProductType"] = df.apply(lambda r: _assign_product_type(r.to_dict()), axis=1)

    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
    df["StartYear"] = df["StartDate"].dt.year
    df["LastUpdatePostDate"] = pd.to_datetime(df["LastUpdatePostDate"], errors="coerce")

    df["SnapshotDate"] = datetime.utcnow().date().isoformat()

    return df.reset_index(drop=True)


def build_sites_dataframe(max_records: int = 1000, statuses: list[str] | None = None) -> pd.DataFrame:
    studies = fetch_raw_trials(max_records=max_records, statuses=statuses)

    site_rows = []
    for s in studies:
        site_rows.extend(_extract_sites(s))

    df_sites = pd.DataFrame(site_rows)

    if df_sites.empty:
        return df_sites

    df_sites = df_sites.dropna(subset=["NCTId"]).drop_duplicates()

    return df_sites.reset_index(drop=True)