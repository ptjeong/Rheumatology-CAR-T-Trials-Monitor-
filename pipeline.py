import json
import os
import re
import time
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
    NAMED_PRODUCT_TARGETS,
    NAMED_PRODUCT_TYPES,
)

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

# ---------------------------------------------------------------------------
# LLM override cache  (populated by:  python validate.py)
# ---------------------------------------------------------------------------

_OVERRIDES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_overrides.json")
_LLM_OVERRIDES: dict[str, dict] = {}
_LLM_EXCLUDED_NCT_IDS: set[str] = set()


def _load_overrides() -> None:
    global _LLM_OVERRIDES, _LLM_EXCLUDED_NCT_IDS
    if not os.path.exists(_OVERRIDES_PATH):
        _LLM_OVERRIDES = {}
        _LLM_EXCLUDED_NCT_IDS = set()
        return
    with open(_OVERRIDES_PATH) as f:
        entries = json.load(f)
    _LLM_OVERRIDES = {
        e["nct_id"]: e
        for e in entries
        if e.get("confidence") in ("high", "medium")
        and e.get("disease_entity") not in ("Exclude", None)
        and not e.get("exclude")
    }
    _LLM_EXCLUDED_NCT_IDS = {
        e["nct_id"] for e in entries
        if e.get("exclude") and e.get("confidence") in ("high", "medium")
    }


def reload_overrides() -> int:
    """Reload LLM overrides from disk. Returns number of active overrides."""
    _load_overrides()
    return len(_LLM_OVERRIDES)


_load_overrides()


def _safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _normalize_text(text: str) -> str:
    """Lowercase + collapse to a deterministic alphanumeric form.

    Aligned with the onc app's normalisation (Phase 2 of REVIEW.md):
      * Hyphens are uniformly collapsed to spaces. Previously only "b-cell",
        "t-cell" and "nk-cell" were rewritten; new hyphenated tokens
        (e.g. "anti-CD19", "BCMA-CD19", "CABA-201") were left half-handled,
        masking term-matching collisions.
      * The character class keeps "." so version-tagged tokens
        (e.g. "claudin 18.2") survive normalisation.
      * Tokens previously hand-rewritten (b-cell / t-cell / nk-cell) drop
        out — the unconditional hyphen collapse handles them generically.
    """
    text = (text or "").lower()
    text = text.replace("sjögren", "sjogren")
    text = text.replace("r/r", "relapsed refractory")
    text = re.sub(r"[^a-z0-9/+.\- ]+", " ", text)
    # Treat hyphens as word separators uniformly.
    text = text.replace("-", " ")
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
    # Word-boundary match for all lengths — prevents prefix collisions
    # (e.g. cd19 inside cd190, egfr inside egfrviii, ra inside brain).
    return bool(re.search(
        rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])",
        normalized_text,
    ))


def _match_terms(text: str, term_map: dict[str, list[str]]) -> list[str]:
    matches = []
    for label, terms in term_map.items():
        if any(_term_in_text(text, term) for term in terms):
            matches.append(label)
    return matches


def _lookup_named_product(text: str, product_dict: dict[str, list[str]]) -> str | None:
    """Return the first category whose any product name appears as a substring in text."""
    for category, names in product_dict.items():
        if any(_normalize_text(name) in text for name in names):
            return category
    return None


# PRIMARY high-precision disease vocabulary (word-boundary matched). Each
# entry is a hand-curated short list of canonical / unambiguous variants —
# deliberately leaner than config.DISEASE_ENTITIES (the LATE-fallback
# substring-match table) so short tokens don't false-positive on overlapping
# context. Keys MUST stay aligned with config.DISEASE_ENTITIES (asserted by
# tests/test_classifier.py::TestVocabularyParity). See config.py for the
# two-vocabulary design rationale.
_DISEASE_TERMS = {
    "SLE": ["systemic lupus erythematosus", "lupus nephritis", "sle"],
    "SSc": [
        "systemic sclerosis", "systemic scleroderma", "scleroderma", "ssc",
        "diffuse cutaneous systemic sclerosis",
    ],
    "Sjogren": [
        "sjogren syndrome", "sjogren s syndrome", "sjogren disease", "sjd",
        "primary sjogren",
    ],
    "CTD_other": [
        "connective tissue disease", "mixed connective tissue disease", "mctd",
        "undifferentiated connective tissue disease", "uctd",
    ],
    "IIM": [
        "idiopathic inflammatory myopathies", "idiopathic inflammatory myopathy",
        "juvenile idiopathic inflammatory myopathy", "dermatomyositis", "polymyositis",
        "immune mediated necrotizing myopathy", "antisynthetase syndrome",
        "anti synthetase syndrome", "myositis", "iim",
    ],
    "AAV": [
        "anca associated vasculitis", "gpa", "granulomatosis with polyangiitis",
        "granulomatous polyangiitis", "mpa", "microscopic polyangiitis",
    ],
    "RA": ["rheumatoid arthritis", "ra"],
    "IgG4-RD": ["igg4 related disease", "igg4 rd"],
    "Behcet": ["behcet disease", "behcet s disease"],
    "cGVHD": ["chronic graft versus host disease", "chronic graft versus host", "cgvhd"],
}

_SYSTEMIC_DISEASES = {
    # Diseases that count toward the >=2 threshold for Basket/Multidisease.
    # CTD_other (mixed/undifferentiated CTD) is included here because trials
    # that pair it with SLE / SSc / IIM are real multi-disease cohorts, not
    # single-disease trials with an incidental CTD label.
    "SLE", "SSc", "Sjogren", "CTD_other", "IIM", "AAV", "RA", "IgG4-RD", "Behcet", "cGVHD",
}

# OIM-disease clusters — used for the basket-detection broadening pass
# inside `_classify_disease`. Each cluster groups synonyms / variant
# spellings for ONE specific OIM disease so a condition-entry like
# "Myasthenia Gravis" and one like "MGFA Class IIIa" don't double-count
# as two distinct OIM diseases. The cluster set mirrors the L2 disease
# split inside app.py's `_NEURO_DISEASE_PATTERNS` and the system-level
# `_SUBFAMILY_PATTERNS`, but lives in pipeline.py so the basket-detection
# logic doesn't need to import from app.py.
_OIM_CLUSTERS: dict[str, list[str]] = {
    # Neurologic-autoimmune
    "MS":           ["multiple sclerosis", "rrms", "ppms", "spms"],
    "Myasthenia":   ["myasthenia gravis", "musk antibody", "musk myasthenia"],
    "NMOSD":        ["neuromyelitis optica", "nmosd", "nmo spectrum"],
    "CIDP":         ["chronic inflammatory demyelinating", "cidp"],
    "MOGAD":        ["mogad", "mog antibody", "mog associated"],
    "AIE":          ["autoimmune encephalitis", "anti nmda", "lgi1", "caspr2"],
    "Stiff_person": ["stiff person", "stiff man"],
    # Dermatologic
    "Pemphigus":    ["pemphigus", "pemphigoid"],
    # Endocrine
    "T1D":          ["type 1 diabetes", "t1dm"],
    "Graves":       ["graves disease", "graves"],
    "Hashimoto":    ["hashimoto"],
    # Cytopenias
    "ITP":          ["immune thrombocytopen", "itp"],
    "AIHA":         ["hemolytic anemia", "aiha", "waiha"],
    # Glomerular / renal (not bundled into SLE-Lupus-Nephritis path)
    "IgAN":         ["iga nephropathy", "igan"],
    "Membranous":   ["membranous nephropathy"],
    "FSGS":         ["focal segmental glomerul", "fsgs"],
    # NOTE: GVHD is intentionally NOT in this map — cGVHD already lives
    # in the strict _DISEASE_TERMS, so a GVHD cluster here would double-
    # count as both "cGVHD" (strict) and "OIM:GVHD" on the same disease,
    # falsely flipping single-disease cGVHD trials to Basket. Add only
    # OIM diseases that have NO strict-map entry.
}


_BROAD_BASKET_TERMS = [
    "b cell mediated autoimmune disease", "b cell mediated autoimmune diseases",
    "b cell related autoimmune disease", "b cell related autoimmune diseases",
    "severe refractory systemic autoimmune rheumatic disease",
]


# ── Classical-rheumatology basket detection ────────────────────────────────
# Used by app.py's `_disease_family()` to split basket trials into:
#   - "Classical rheumatology basket" (constituents are ALL CTD/IA/Vasc,
#     no non-rheum text signal) → rheum-blue wedge in the sunburst, sits
#     adjacent to the CTD/IA/Vasc arc so the reader sees these as part
#     of the rheum cluster rather than a separate slate basket bucket.
#   - "Basket/Multidisease" (everything else — mixed-class baskets with
#     ≥1 neuro/glomerular/GVHD/etc constituent).
# Lives in pipeline.py rather than app.py so `is_classical_rheum_basket`
# is importable in tests without spinning up Streamlit.
_CLASSICAL_RHEUM_ENTITIES = {
    # Connective tissue
    "SLE", "SSc", "Sjogren", "IIM", "CTD_other", "IgG4-RD",
    # Inflammatory arthritis
    "RA",
    # Vasculitis
    "AAV", "Behcet",
}
# cGVHD is intentionally EXCLUDED — it lives under "Other autoimmune"; a
# basket spanning cGVHD + a rheum entity is mixed-class, not classical-rheum.

# Text signals that disqualify a basket from being "classical-rheum-only"
# even if the DiseaseEntities column lists only CTD/IA/Vasc entities. Catches
# trials where the entity classifier missed a non-rheum constituent but the
# conditions/title text reveals it (defensive — keeps the
# "Classical rheumatology basket" wedge clean).
_NON_RHEUM_BASKET_TEXT_SIGNALS = (
    # Neurologic
    "multiple sclerosis", "myasthenia", "neuromyelitis", "nmosd",
    "demyelinating", "cidp", "encephalitis", "mogad", "stiff person",
    # Glomerular / renal
    "iga nephropathy", "igan ", "membranous nephropathy",
    "fsgs", "focal segmental glomer", "minimal change",
    # GVHD
    "graft-versus-host", "graft versus host", "gvhd",
    # Cytopenias
    "hemolytic anemia", "aiha", "immune thrombocytopen", " itp ",
    "evans syndrome", "aplastic anemia",
    # Dermatologic
    "pemphigus", "pemphigoid", "hidradenitis",
    # Endocrine
    "type 1 diabetes", "t1dm", "graves", "hashimoto",
)


# OIM-cluster labels that the pipeline emits as DiseaseEntities for
# neuro-autoimmune baskets (`_classify_disease` adds these for basket
# trials when the conditions/title text matches the cluster terms).
# Used by `is_neuro_basket` to detect baskets whose constituents are
# exclusively neuro — those land in the Neurologic autoimmune family
# rather than the generic Basket/Multidisease bucket.
_NEURO_OIM_CLUSTER_ENTITIES = {
    "MS", "NMOSD", "CIDP", "MOGAD", "AIE", "Myasthenia", "Stiff_person",
}

# Text signals for neuro autoimmune diseases — the same set used by
# `_NON_RHEUM_BASKET_TEXT_SIGNALS` above, exposed here for the
# neuro-basket detector.
_NEURO_BASKET_TEXT_SIGNALS = (
    "multiple sclerosis", "myasthenia", "neuromyelitis", "nmosd",
    "demyelinating", "cidp", "encephalitis", "mogad", "stiff person",
)

# Text signals from OTHER non-neuro families — if any of these appear
# in conditions/title, the basket is mixed-class and must NOT land in
# the neuro family. Mirrors `_NON_RHEUM_BASKET_TEXT_SIGNALS` minus the
# neuro keywords.
_NON_NEURO_BASKET_TEXT_SIGNALS = (
    # Rheum (CTD / IA / Vasculitis)
    "lupus", "systemic sclerosis", "sjogren", "rheumatoid arthritis",
    "inflammatory myopath", "vasculitis", "anca-associated",
    "igg4", "behcet", "mixed connective", "antiphospholipid",
    # Glomerular / renal
    "iga nephropathy", "igan ", "membranous nephropathy",
    "fsgs", "focal segmental glomer", "minimal change",
    # GVHD
    "graft-versus-host", "graft versus host", "gvhd",
    # Cytopenias
    "hemolytic anemia", "aiha", "immune thrombocytopen", " itp ",
    "evans syndrome", "aplastic anemia",
    # Dermatologic
    "pemphigus", "pemphigoid", "hidradenitis",
    # Endocrine
    "type 1 diabetes", "t1dm", "graves", "hashimoto",
)


def is_neuro_basket(
    entities_str: str | None,
    conditions: str | None = None,
    brief_title: str | None = None,
) -> bool:
    """Return True iff a basket trial enrols ≥2 distinct neuro autoimmune
    diseases AND no entities or text signals from any other family.

    Detection sources (either is sufficient):
      1. DiseaseEntities column lists ≥2 of {MS, NMOSD, CIDP, MOGAD, AIE,
         Myasthenia, Stiff_person} (the OIM-cluster labels emitted by
         `_classify_disease`).
      2. Conditions/title text matches ≥2 distinct neuro disease keywords.

    Disqualifiers (any is sufficient):
      - DiseaseEntities lists ANY non-neuro classifier-emitted entity
        (e.g., SLE, RA, cGVHD, IgAN — these mean the basket is mixed).
      - Conditions/title text matches ANY rheum / glomerular / GVHD /
        cytopenia / dermatologic / endocrine keyword.

    Used by app.py's `_disease_family()` to route neuro-only baskets to
    the Neurologic autoimmune family wedge (per round-9 user spec) so
    they cluster with single-disease neuro trials rather than sitting
    under the slate generic-basket bucket.
    """
    ents = {
        e.strip()
        for e in str(entities_str or "").split("|")
        if e.strip()
        and e.strip() not in (
            "Basket/Multidisease", "Unclassified", "Other immune-mediated",
        )
    }
    # Any non-neuro entity disqualifies (rheum / glomerular / etc.)
    non_neuro_ents = ents - _NEURO_OIM_CLUSTER_ENTITIES
    if non_neuro_ents:
        return False
    text = f"{conditions or ''} {brief_title or ''}".lower()
    # Any non-neuro text signal disqualifies — defensive against
    # classifier misses that left a non-neuro constituent un-flagged.
    if any(kw in text for kw in _NON_NEURO_BASKET_TEXT_SIGNALS):
        return False
    # Need ≥2 distinct neuro signals (entities OR text).
    n_neuro_ents = len(ents & _NEURO_OIM_CLUSTER_ENTITIES)
    if n_neuro_ents >= 2:
        return True
    n_neuro_text_hits = sum(1 for kw in _NEURO_BASKET_TEXT_SIGNALS if kw in text)
    return n_neuro_text_hits >= 2


def is_classical_rheum_basket(
    entities_str: str | None,
    conditions: str | None = None,
    brief_title: str | None = None,
) -> bool:
    """Return True iff a basket trial enrols ≥2 distinct classical-rheum
    entities (CTD / IA / Vasculitis) AND no entities outside that triad
    AND no conditions/title text signals a non-rheum constituent.

    The defensive text-scan catches the rare case where the entity
    classifier missed a non-rheum disease but the trial title clearly
    names it (e.g., a trial classified as SLE|RA in DiseaseEntities whose
    title also mentions "multiple sclerosis").

    Used by app.py's `_disease_family()` to route the trial to the
    rheum-blue "Classical rheumatology basket" wedge versus the generic
    slate "Basket/Multidisease" bucket.
    """
    ents = {
        e.strip()
        for e in str(entities_str or "").split("|")
        if e.strip()
        and e.strip() not in (
            "Basket/Multidisease", "Unclassified", "Other immune-mediated",
        )
    }
    if not ents:
        return False
    rheum_in = ents & _CLASSICAL_RHEUM_ENTITIES
    non_rheum = ents - _CLASSICAL_RHEUM_ENTITIES
    if len(rheum_in) < 2 or non_rheum:
        return False
    text = f"{conditions or ''} {brief_title or ''}".lower()
    if any(kw in text for kw in _NON_RHEUM_BASKET_TEXT_SIGNALS):
        return False
    return True

_BROAD_AUTOIMMUNE_PHRASES = [
    "autoimmune disease", "autoimmune diseases",
    "relapsed refractory autoimmune disease", "relapsed refractory autoimmune diseases",
    "systemic autoimmune disease", "systemic autoimmune diseases",
]


def _normalize_disease_result(
    entities: list[str], design: str, primary: str,
) -> tuple[list[str], str, str]:
    """Post-classification normalisation: enforce the invariant that
    primary == 'Basket/Multidisease' iff design == 'Basket/Multidisease',
    and that 'Unclassified' / 'Other immune-mediated' are never bundled
    with a specific entity in the entities list.

    Defensive guard for future contributors / LLM overrides that might
    set the three values inconsistently. The rule-based classifier is
    already internally consistent — this hook locks that property in.
    Aligned with the onc app's _normalize_disease_result.
    """
    # Coerce primary <-> design consistency on the basket axis.
    if primary == "Basket/Multidisease" and design != "Basket/Multidisease":
        design = "Basket/Multidisease"
    elif design == "Basket/Multidisease" and primary != "Basket/Multidisease":
        # Caller asserts a multi-disease cohort but pinned a single primary;
        # flip primary to the basket label so chart bins are consistent.
        primary = "Basket/Multidisease"

    # Sentinel labels (Unclassified / Other immune-mediated) must stand
    # alone — bundling them with a specific entity is logically incoherent.
    if "Unclassified" in entities and len(entities) > 1:
        entities = [e for e in entities if e != "Unclassified"]
    if "Other immune-mediated" in entities and len(entities) > 1:
        entities = [e for e in entities if e != "Other immune-mediated"]
    # Idempotent fallback: if entities ends up empty, mirror primary.
    if not entities:
        entities = [primary]
    return entities, design, primary


def _classify_disease(row: dict) -> tuple[list[str], str, str]:
    """Return (disease_entities, trial_design, primary_entity).

    disease_entities: every specific disease label matched (pipe-join for DiseaseEntities column)
    trial_design:     "Single disease" | "Basket/Multidisease"
    primary_entity:   single label for charts/display (DiseaseEntity column)

    Every return path runs through `_normalize_disease_result` so the three
    values are guaranteed mutually consistent.
    """
    nct = str(row.get("NCTId", "")).strip()
    if nct and nct in _LLM_OVERRIDES:
        ov = _LLM_OVERRIDES[nct]
        entity = ov.get("disease_entity", "Unclassified")
        design = "Basket/Multidisease" if entity == "Basket/Multidisease" else "Single disease"
        return _normalize_disease_result([entity], design, entity)

    conditions_raw = _safe_text(row.get("Conditions"))
    full_text = _row_text(row)

    condition_chunks = [_normalize_text(c) for c in conditions_raw.split("|") if _normalize_text(c)]
    matched_conditions = sorted({m for chunk in condition_chunks for m in _match_terms(chunk, _DISEASE_TERMS)})
    matched_full = _match_terms(full_text, _DISEASE_TERMS)
    all_matched = sorted(set(matched_conditions + matched_full))

    if all_matched:
        n_systemic = sum(1 for m in all_matched if m in _SYSTEMIC_DISEASES)
        if n_systemic >= 2:
            return _normalize_disease_result(all_matched, "Basket/Multidisease", "Basket/Multidisease")

        # Basket-detection broadening: a trial that strict-matches one
        # rheum systemic AND has pipe-separated condition entries naming
        # additional OIM-cluster diseases (MS / Myasthenia / NMOSD / CIDP
        # / pemphigus / membranous nephropathy / etc.) is also a multi-
        # disease cohort. Live evidence: NCT07022197 (BAFF-R CART for
        # refractory neuroimmune diseases) lists CIDP | NMOSD | MG | IIM
        # but only IIM is in _SYSTEMIC_DISEASES, so n_systemic=1 and the
        # trial wrongly stays Single.
        #
        # Algorithm: identify the DISEASE ENTITY each pipe-separated
        # condition entry maps to (strict entity for rheum systemics, an
        # OIM cluster label otherwise). Aliases of the same disease
        # ("SLE | Lupus Nephritis", "Dermatomyositis, Juvenile |
        # Dermatomyositis") collapse to a single entity. Promote to
        # Basket when >=2 DISTINCT entities are named.
        distinct_entities: set[str] = set(all_matched)
        for chunk in condition_chunks:
            if _match_terms(chunk, _DISEASE_TERMS):
                # Already counted via the strict map; skip
                continue
            for cluster_label, cluster_terms in _OIM_CLUSTERS.items():
                if any(_term_in_text(chunk, t) for t in cluster_terms):
                    distinct_entities.add(f"OIM:{cluster_label}")
                    break  # at most one OIM cluster per chunk
        if len(distinct_entities) >= 2:
            return _normalize_disease_result(
                all_matched, "Basket/Multidisease", "Basket/Multidisease",
            )

        return _normalize_disease_result(all_matched, "Single disease", all_matched[0])

    # Pure-OIM basket detection (no rheum anchor). The block above only runs
    # when at least one strict rheum disease matched, which means trials
    # spanning multiple neuro / glomerular / etc. autoimmune diseases (with
    # NO rheum constituent) silently fell through to the "Other immune-
    # mediated" Single-disease path below. Live evidence on the 2026-04-25
    # snapshot: 8 trials with conditions like "Multiple sclerosis | NMOSD |
    # Myasthenia | Encephalitis | Stiff Person Syndrome" were classified as
    # Single + Other-immune-mediated — they should be Basket trials, and
    # `is_neuro_basket()` + `_disease_family()` should then route them to
    # the Neurologic autoimmune family wedge.
    distinct_oim_clusters: set[str] = set()
    for chunk in condition_chunks:
        for cluster_label, cluster_terms in _OIM_CLUSTERS.items():
            if any(_term_in_text(chunk, t) for t in cluster_terms):
                distinct_oim_clusters.add(cluster_label)
                break  # at most one OIM cluster per chunk
    # Also scan the full title/conditions text for clusters that weren't
    # captured by a chunk-level match (some trials list diseases in the
    # brief title or as a single un-pipe-split condition string).
    for cluster_label, cluster_terms in _OIM_CLUSTERS.items():
        if cluster_label in distinct_oim_clusters:
            continue
        if any(_term_in_text(full_text, t) for t in cluster_terms):
            distinct_oim_clusters.add(cluster_label)
    if len(distinct_oim_clusters) >= 2:
        cluster_entities = sorted(distinct_oim_clusters)
        return _normalize_disease_result(
            cluster_entities, "Basket/Multidisease", "Basket/Multidisease",
        )

    if _contains_any(full_text, OTHER_IMMUNE_MEDIATED_TERMS):
        return _normalize_disease_result(["Other immune-mediated"], "Single disease", "Other immune-mediated")

    if any(term in full_text for term in _BROAD_BASKET_TERMS):
        return _normalize_disease_result(["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease")

    if any(p in full_text for p in _BROAD_AUTOIMMUNE_PHRASES):
        return _normalize_disease_result(["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease")

    for entity, syns in DISEASE_ENTITIES.items():
        specific_syns = [_normalize_text(s) for s in syns if len(str(s)) > 3]
        if any(s in full_text for s in specific_syns):
            return _normalize_disease_result([entity], "Single disease", entity)

    if _contains_any(full_text, GENERIC_AUTOIMMUNE_TERMS):
        return _normalize_disease_result(["Basket/Multidisease"], "Basket/Multidisease", "Basket/Multidisease")

    return _normalize_disease_result(["Unclassified"], "Single disease", "Unclassified")


def _assign_disease_entity(row: dict) -> str:
    return _classify_disease(row)[2]


def _is_hard_excluded(nct_id: str) -> bool:
    n = nct_id.strip()
    return n in HARD_EXCLUDED_NCT_IDS or n in _LLM_EXCLUDED_NCT_IDS


def _is_indication_excluded(row: dict) -> bool:
    text = _row_text(row)
    return _contains_any(text, EXCLUDED_INDICATION_TERMS)


def _exclude_by_indication(row: dict) -> bool:
    if _is_hard_excluded(_safe_text(row.get("NCTId"))):
        return True
    return _is_indication_excluded(row)


_TARGET_FALLBACK_LABELS = {"CAR-T_unspecified", "Other_or_unknown"}


def _assign_target(row: dict) -> tuple[str, str]:
    """Return (target_category, source).

    source ∈ {"llm_override", "explicit_marker", "named_product",
              "car_core_fallback", "unknown"}.
    """
    nct = _safe_text(row.get("NCTId")).strip()
    ov = _LLM_OVERRIDES.get(nct) if nct else None
    if ov and ov.get("target_category"):
        return ov["target_category"], "llm_override"

    text = _row_text(row)

    has_car_nk = _contains_any(text, CAR_NK_TERMS) or ("car nk" in text)
    has_caar_t = _contains_any(text, CAAR_T_TERMS)
    has_car_treg = _contains_any(text, CAR_TREG_TERMS) or ("treg" in text and "car" in text)

    has_cd19 = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["CD19"]) or ("cd19" in text)
    has_bcma = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["BCMA"]) or ("bcma" in text)
    has_baff = "baff" in text
    # "cd19/20" notation (e.g. "universal CD19/20 CAR-T") — slash is preserved by normalizer
    has_cd20 = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["CD20"]) or ("cd20" in text) or ("cd19/20" in text)
    has_cd70 = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["CD70"]) or ("cd70" in text)
    has_cd6 = "cd6" in text
    has_cd7 = "cd7" in text

    if has_car_nk:
        if has_cd19 and has_bcma:
            return "CD19/BCMA dual", "explicit_marker"
        if has_cd19:
            return "CD19", "explicit_marker"
        return "CAR-NK", "explicit_marker"

    if has_caar_t:
        return "CAAR-T", "explicit_marker"
    if has_car_treg:
        if has_cd6:
            return "CD6", "explicit_marker"
        return "CAR-Treg", "explicit_marker"
    if has_bcma and has_cd70:
        return "BCMA/CD70 dual", "explicit_marker"
    if has_cd19 and has_bcma:
        return "CD19/BCMA dual", "explicit_marker"
    if has_cd19 and has_cd20:
        return "CD19/CD20 dual", "explicit_marker"
    if has_cd19 and has_baff:
        return "CD19/BAFF dual", "explicit_marker"
    if has_cd19:
        return "CD19", "explicit_marker"
    if has_bcma:
        return "BCMA", "explicit_marker"
    if has_cd20:
        return "CD20", "explicit_marker"
    if has_cd70:
        return "CD70", "explicit_marker"
    if has_baff:
        return "BAFF", "explicit_marker"
    if has_cd6:
        return "CD6", "explicit_marker"
    if has_cd7:
        return "CD7", "explicit_marker"
    # Named product fallback: resolves target for well-known products that omit the
    # antigen name from accessible study text (title / brief summary / interventions).
    named_target = _lookup_named_product(text, NAMED_PRODUCT_TARGETS)
    if named_target:
        return named_target, "named_product"
    if _contains_any(text, CAR_CORE_TERMS):
        return "CAR-T_unspecified", "car_core_fallback"
    return "Other_or_unknown", "unknown"


def _assign_product_type(row: dict, target_source: str | None = None) -> tuple[str, str]:
    """Return (product_type, source).

    source ∈ {
        "llm_override",
        "explicit_in_vivo_title",      # "in vivo" appears in the BriefTitle
        "explicit_in_vivo_text",       # explicit in-vivo phrase in body text
        "explicit_autologous",         # "autoleucel" or "autologous" in text
        "explicit_allogeneic",         # UCART / "universal CAR" / "allogeneic" / donor
        "named_product",               # resolved via NAMED_PRODUCT_TYPES
        "weak_autologous_marker",      # low-specificity autologous hint (AUTOL_MARKERS)
        "weak_allogeneic_marker",      # low-specificity allogeneic hint (ALLOGENEIC_MARKERS)
        "default_autologous_no_allo_markers",
        "no_signal",
    }

    Default rule: when CAR-T is confirmed (target resolved via explicit marker,
    named product, or CAR-core fallback) and no product-type signal is found in
    text, default to Autologous — empirically ~85% accurate in rheum CAR-T
    (allo is almost always labelled; in-vivo always titled).
    """
    nct = _safe_text(row.get("NCTId")).strip()
    ov = _LLM_OVERRIDES.get(nct) if nct else None
    if ov and ov.get("product_type"):
        return ov["product_type"], "llm_override"

    text = _row_text(row)
    title = _normalize_text(_safe_text(row.get("BriefTitle")))

    if "in vivo" in title:
        return "In vivo", "explicit_in_vivo_title"
    in_vivo_terms = [
        "in vivo car", "in-vivo car",
        "in vivo programming", "in vivo generated", "in vivo transduction",
        "vivovec", "lentiviral nanoparticle",
        "circular rna",
    ]
    if any(term in text for term in in_vivo_terms):
        return "In vivo", "explicit_in_vivo_text"

    if "autoleucel" in text or "autologous" in text:
        return "Autologous", "explicit_autologous"

    strong_allo_terms = [
        "ucart", "ucar",
        "universal car t", "universal car-t",
        "universal cd19", "universal bcma",
        "universal cd70", "universal anti",
        "u car t", "u car-t",
        "off the shelf", "allogeneic",
        "healthy donor", "donor derived", "donor sourced",
    ]
    if any(term in text for term in strong_allo_terms):
        return "Allogeneic/Off-the-shelf", "explicit_allogeneic"

    named_type = _lookup_named_product(text, NAMED_PRODUCT_TYPES)
    if named_type:
        return named_type, "named_product"

    if _contains_any(text, ALLOGENEIC_MARKERS):
        return "Allogeneic/Off-the-shelf", "weak_allogeneic_marker"
    if _contains_any(text, AUTOL_MARKERS):
        return "Autologous", "weak_autologous_marker"

    # Default: CAR-T confirmed via any target channel and no allo/in-vivo signal
    if target_source in ("explicit_marker", "named_product", "car_core_fallback"):
        return "Autologous", "default_autologous_no_allo_markers"

    return "Unclear", "no_signal"


_WEAK_OR_DEFAULT_PRODUCT_SOURCES = {
    "default_autologous_no_allo_markers",
    "weak_autologous_marker",
    "weak_allogeneic_marker",
}

# Per-axis sub-scores in [0, 1]. Mapped from each *_source value so the
# confidence breakdown is transparent (every input traceable to a number).
# See compute_confidence_factors below for the composition rule.
_DISEASE_FACTOR = {
    "Unclassified":          0.0,
    "Basket/Multidisease":   0.6,
    "Other immune-mediated": 0.7,
    # Anything not in this map (a specific entity from the strict pass)
    # gets the default of 1.0 (highest signal).
}
_TARGET_FACTOR = {
    "explicit_marker":   1.0,
    "named_product":     0.9,
    "car_core_fallback": 0.4,
    "unknown":           0.0,
    "legacy_snapshot":   0.6,
}
_PRODUCT_FACTOR = {
    "explicit_autologous":               1.0,
    "explicit_allogeneic":               1.0,
    "explicit_in_vivo_title":            1.0,
    "explicit_in_vivo_text":             1.0,
    "named_product":                     0.9,
    "weak_allogeneic_marker":            0.55,
    "weak_autologous_marker":            0.55,
    "default_autologous_no_allo_markers": 0.5,
    "no_signal":                         0.0,
    "legacy_snapshot":                   0.6,
}
# Threshold cuts for the legacy 3-bucket categorical wrapper. Tuned so the
# new factor-based score reproduces the existing snapshot's high / medium /
# low distribution within +/- 5% (verified on snapshots/2026-04-25 — see
# tests/test_classifier.py::TestConfidence).
_CONFIDENCE_HIGH_CUT = 0.85
_CONFIDENCE_MEDIUM_CUT = 0.55


def compute_confidence_factors(
    target: str, target_source: str,
    product_type: str, product_source: str,
    disease_entity: str,
    llm_override: bool = False,
) -> dict:
    """Multi-factor confidence breakdown — UI_DRILLDOWN_SPEC v1.3 schema.

    Returns:
        {
          "score":   <composite 0..1>,        # unweighted mean of factor sub-scores
          "level":   <"high" | "medium" | "low">,
          "factors": {
              "disease": {"score": float, "driver": str},
              "target":  {"score": float, "driver": str},
              "product": {"score": float, "driver": str},
          },
          "drivers": [(axis, driver), ...]    # 2-tuples sorted ascending by score (worst first), top 3
        }

    Every factor is in [0, 1] and traceable to the source-tag inputs.
    Composite score is the unweighted mean of the three axis factors;
    LLM override pins the composite to 1.0. The legacy 3-bucket categorical
    (high/medium/low) is derived from the score with thresholds at 0.85
    and 0.55.

    `drivers` surfaces the worst-scoring axes for the trial-detail
    "What's holding the score down" caption.

    Schema flip from v1.0 (flat factors {axis: float} + parallel
    (axis, score, reason) drivers list) to v1.3 (nested
    {axis: {score, driver}} + 2-tuple (axis, driver) drivers list).
    Aligned with the canonical schema in onc app's
    compute_confidence_factors per cross-app round 6 brief.
    """
    if llm_override:
        factors = {
            "disease": {"score": 1.0, "driver": "Disease entity validated by LLM curator override."},
            "target":  {"score": 1.0, "driver": "Target validated by LLM curator override."},
            "product": {"score": 1.0, "driver": "Product type validated by LLM curator override."},
        }
        return {
            "score": 1.0,
            "level": "high",
            "factors": factors,
            "drivers": [("llm_override", "Per-trial LLM curator override is in force.")],
        }

    disease_factor = _DISEASE_FACTOR.get(str(disease_entity), 1.0)
    target_factor = _TARGET_FACTOR.get(str(target_source), 0.4)
    product_factor = _PRODUCT_FACTOR.get(str(product_source), 0.4)

    factors = {
        "disease": {"score": disease_factor,
                    "driver": f"DiseaseEntity = {disease_entity!r}"},
        "target":  {"score": target_factor,
                    "driver": f"TargetSource = {target_source!r}"},
        "product": {"score": product_factor,
                    "driver": f"ProductTypeSource = {product_source!r}"},
    }

    score = (disease_factor + target_factor + product_factor) / 3.0
    if score >= _CONFIDENCE_HIGH_CUT:
        level = "high"
    elif score >= _CONFIDENCE_MEDIUM_CUT:
        level = "medium"
    else:
        level = "low"

    # `drivers`: worst-scoring axes first (lower score = more interesting to surface)
    drivers = sorted(
        ((axis, info["driver"], info["score"]) for axis, info in factors.items()),
        key=lambda t: t[2],
    )[:3]
    drivers = [(axis, drv) for axis, drv, _ in drivers]

    return {"score": score, "level": level,
            "factors": factors, "drivers": drivers}


# Plain-language rationale snippets per source-tag value, surfaced in the
# "How was this classified?" expander (UI_DRILLDOWN_SPEC v1.0 §5d).
_TARGET_SOURCE_EXPLAINS = {
    "explicit_marker":   "Antigen named directly in trial text (e.g. 'CD19', 'BCMA' as a CAR target).",
    "named_product":     "Resolved via a named-product alias (e.g. 'KYV-101' → CD19).",
    "car_core_fallback": "Generic 'CAR-T' language with no specific antigen disclosed.",
    "unknown":           "No CAR-T construct or antigen signal found.",
    "llm_override":      "Per-trial LLM curator override is in force.",
    "legacy_snapshot":   "Inherited from an older snapshot (pre source-tag attribution).",
}
_PRODUCT_SOURCE_EXPLAINS = {
    "explicit_autologous":              "Trial text explicitly says autologous.",
    "explicit_allogeneic":              "Trial text explicitly says allogeneic / off-the-shelf / donor-derived.",
    "explicit_in_vivo_title":           "Title explicitly says 'in vivo' / 'in-vivo CAR-T'.",
    "explicit_in_vivo_text":            "Brief summary or interventions describe in-vivo CAR-T (e.g. mRNA-LNP).",
    "named_product":                    "Resolved via a named-product alias.",
    "weak_allogeneic_marker":           "Weak allogeneic marker without an explicit autologous statement.",
    "default_autologous_no_allo_markers": "Defaulted to autologous — a CAR-T target is present and no allogeneic markers were found.",
    "no_signal":                        "No product-type signal in the trial text.",
    "llm_override":                     "Per-trial LLM curator override is in force.",
    "legacy_snapshot":                  "Inherited from an older snapshot.",
}


def compute_classification_rationale(row: dict) -> dict:
    """Re-run the classifier instrumented to surface WHY each label was chosen.

    Returns a dict with one entry per rheum axis, each value a sub-dict:
        {
            "label":          <the label assigned>,
            "source":         <short source-tag, e.g. 'llm_override' / 'rule_based'>,
            "matched_terms":  <list of terms the row text matched>,
            "explanation":    <human-readable one-sentence rationale>,
        }

    Used by the dashboard's per-trial drilldown to render a tabular
    "How was this classified?" expander (UI_DRILLDOWN_SPEC v1.0 §5d).
    Read-only — never mutates the input row, never persists. Pure
    function: same row in → same rationale out.

    Rheum axes (5): DiseaseEntity, TargetCategory, ProductType,
    TrialDesign, SponsorType. (Onc has Branch + DiseaseCategory in
    addition; rheum is single-branch with a flatter taxonomy.)
    """
    text = _row_text(row)
    nct = _safe_text(row.get("NCTId")).strip()

    rationale: dict[str, dict] = {}
    is_llm_override = bool(nct and nct in _LLM_OVERRIDES)
    override_entry = _LLM_OVERRIDES.get(nct, {}) if is_llm_override else {}

    # ---- DiseaseEntity (also drives TrialDesign) ----
    entities, design, primary = _classify_disease(row)
    if is_llm_override and override_entry.get("disease_entity"):
        rationale["DiseaseEntity"] = {
            "label": override_entry["disease_entity"],
            "source": "llm_override",
            "matched_terms": [],
            "explanation": (
                f"Overridden by `llm_overrides.json` entry for {nct}. "
                f"Strict-vocabulary matching was bypassed."
            ),
        }
    else:
        # Surface every term in the strict map that hit the row text.
        ent_matches: list[str] = []
        for entity_key, terms in _DISEASE_TERMS.items():
            ent_matches.extend(t for t in terms if _term_in_text(text, t))
        n_systemic = sum(1 for m in entities if m in _SYSTEMIC_DISEASES)
        if n_systemic >= 2:
            explanation = (
                "Multi-systemic match (≥2 systemic diseases) — promoted to "
                "Basket/Multidisease per pipeline.py:_SYSTEMIC_DISEASES."
            )
        elif primary == "Other immune-mediated":
            explanation = (
                "No strict-vocabulary match; matched the OTHER_IMMUNE_MEDIATED_TERMS "
                "fallback (e.g. neurologic / dermatologic / endocrine autoimmune)."
            )
        elif primary == "Basket/Multidisease":
            explanation = (
                "No strict-vocabulary match; matched a generic basket phrase "
                "('B-cell mediated autoimmune disease', 'systemic autoimmune disease')."
            )
        elif primary == "Unclassified":
            explanation = "No vocabulary match — landed in 'Unclassified'. Curation candidate."
        else:
            explanation = (
                f"Strict-vocabulary match (high precision); single-disease "
                f"(systemic count = {n_systemic})."
            )
        rationale["DiseaseEntity"] = {
            "label": primary,
            "source": "rule_based",
            "matched_terms": ent_matches[:6],
            "explanation": explanation,
        }

    # ---- TrialDesign (derived from disease classification) ----
    rationale["TrialDesign"] = {
        "label": design,
        "source": "derived_from_disease_entity",
        "matched_terms": [],
        "explanation": (
            "Single disease = trial enrols ONE rheum indication; "
            "Basket/Multidisease = ≥2 systemic diseases or a generic "
            "B-cell-mediated cohort. Derived from DiseaseEntity classification."
        ),
    }

    # ---- TargetCategory ----
    target_label, target_source = _assign_target(row)
    rationale["TargetCategory"] = {
        "label": target_label,
        "source": target_source,
        "matched_terms": [target_label] if target_source == "explicit_marker" else [],
        "explanation": _TARGET_SOURCE_EXPLAINS.get(
            target_source, f"Source tag: {target_source}"
        ),
    }

    # ---- ProductType ----
    try:
        ptype, ptype_source = _assign_product_type(row, target_source=target_source)
    except Exception:
        ptype = _safe_text(row.get("ProductType", "Unclear"))
        ptype_source = _safe_text(row.get("ProductTypeSource", "unknown"))
    rationale["ProductType"] = {
        "label": ptype,
        "source": ptype_source,
        "matched_terms": [],
        "explanation": _PRODUCT_SOURCE_EXPLAINS.get(
            ptype_source, f"Source tag: {ptype_source}"
        ),
    }

    # ---- SponsorType ----
    sponsor_label = _classify_sponsor(
        row.get("LeadSponsor"), row.get("LeadSponsorClass"),
    )
    rationale["SponsorType"] = {
        "label": sponsor_label,
        "source": "lead_sponsor_class + name_pattern",
        "matched_terms": [],
        "explanation": (
            f"Classified from LeadSponsor name + LeadSponsorClass. "
            f"Class hint: {row.get('LeadSponsorClass') or '—'}."
        ),
    }

    return rationale


def _compute_confidence(
    target: str, target_source: str,
    product_type: str, product_source: str,
    disease_entity: str,
    llm_override: bool = False,
) -> str:
    """Return 'high' | 'medium' | 'low' (legacy 3-bucket categorical).

    Kept strictly back-compatible so the snapshot's
    ClassificationConfidence column reproduces bit-for-bit on a re-derive.
    The new transparent factor breakdown is in compute_confidence_factors
    and is wired into the trial-detail rationale UI; switching the
    categorical to the new model is a Phase 3 follow-up that requires a
    snapshot regeneration round.
    """
    if llm_override:
        return "high"
    if disease_entity == "Unclassified":
        return "low"
    unclear_target = target in _TARGET_FALLBACK_LABELS
    default_product = product_source in _WEAK_OR_DEFAULT_PRODUCT_SOURCES
    if unclear_target and default_product:
        return "low"
    if unclear_target or default_product:
        return "medium"
    return "high"


_ACADEMIC_HINTS = (
    "university", "universität", "universitat", "universite", "université",
    "hospital", "klinik", "klinikum", "hôpital", "ospedale",
    "institute", "institut", "instituto",
    "school of medicine", "college of medicine", "medical college", "medical center",
    "medical centre", "centre hospitalier", "center hospitalier",
    "academic", "faculty", "facultad",
    "nih", "national institutes of health", "national cancer institute",
    "mayo clinic", "cleveland clinic", "charite", "charité",
    "chinese academy", "chinese pla", "pla general hospital",
    "people's hospital", "peoples hospital",
    "gustave roussy", "scripps", "calibr", "cancer center", "cancer centre",
    "fred hutchinson", "memorial sloan", "dana-farber", "md anderson",
    "children's hospital", "childrens hospital",
    "foundation", "fondazione", "trust", "nhs",
)

_INDUSTRY_HINTS = (
    "inc", "inc.", "ltd", "ltd.", "limited", "llc", "corp", "corporation",
    "gmbh", "ag", "s.a.", "s.p.a", "s.a.s", "sas", "plc", "co., ltd",
    "pharma", "pharmaceutical", "pharmaceuticals",
    "biotech", "bioscience", "biosciences", "biologics", "therapeutics",
    "bio-tech", "biopharma", "oncology",
    "diagnostics", "genomics", "medicines", "biosimilar",
    " bio",  # trailing 'Bio' as company suffix: 'Cabaletta Bio', 'Bioray'
)


_PERSON_DEGREE_MARKERS = (
    "m.d.", " md,", " md ", ", md", " md.", "md,",
    "ph.d", "phd", " d.o.", ", do",
    "pharmd", " dsc", " msc", "professor ",
)


def _looks_like_personal_name(name: str) -> bool:
    """Detect whether a sponsor string refers to an individual investigator.

    CT.gov tags many investigator-initiated trials with lead sponsor class
    OTHER (not INDIV) when the sponsor is actually a named PI — e.g. 'Bruce
    Cree', 'Marcela V. Maus, M.D.,Ph.D.', 'Daishi Tian'. This heuristic
    routes them to Academic rather than the opaque Other bucket.
    """
    if not name:
        return False
    n = name.lower().strip()
    if any(m in n for m in _PERSON_DEGREE_MARKERS):
        return True
    # If any org keyword is present, it is not a personal name.
    if any(h in n for h in _ACADEMIC_HINTS):
        return False
    if any(h in n for h in _INDUSTRY_HINTS):
        return False
    if any(h in n for h in _GOV_HINTS):
        return False
    # Short, alphabetic 2–4-token strings look like personal names.
    tokens = [t.strip(",.'-") for t in name.split() if t.strip(",.'-")]
    if 2 <= len(tokens) <= 4 and all(t.replace("-", "").isalpha() for t in tokens):
        if all(len(t) <= 15 for t in tokens):
            return True
    return False


_CTGOV_CLASS_MAP = {
    "INDUSTRY": "Industry",
    "NIH": "Government",
    "FED": "Government",
    # OTHER_GOV is deliberately NOT mapped (Phase 2 alignment with the onc
    # app). CT.gov over-applies it to non-US public hospitals — Chinese
    # provincial hospitals, Czech public research institutes, Russian federal
    # institutes — that are functionally academic. Those cases are routed
    # through the name-based heuristic. Only sponsors whose names carry an
    # explicit gov-agency signal (NIH / VA / DoD / MoH) end up "Government".
    "NETWORK": "Academic",
    "INDIV": "Academic",  # investigator-initiated trials run through academic centers
    "OTHER": None,  # fall through to heuristic
    "UNKNOWN": None,
}

_GOV_HINTS = (
    "nih", "national institutes of health", "national cancer institute",
    "department of veterans affairs", "veterans affairs", "dod",
    "ministry of health", "public health",
)


def _classify_sponsor(lead_sponsor: str | None, lead_sponsor_class: str | None = None) -> str:
    """Return 'Industry' | 'Academic' | 'Government' | 'Other'.

    Primary signal: CT.gov `leadSponsor.class` (INDUSTRY/NIH/OTHER_GOV/…).
    Fallback: keyword heuristic against the sponsor name.
    """
    name = (lead_sponsor or "").lower().strip()
    if lead_sponsor_class:
        cls = str(lead_sponsor_class).upper().strip()
        mapped = _CTGOV_CLASS_MAP.get(cls)
        if mapped is not None:
            return mapped
        # OTHER_GOV / OTHER / UNKNOWN fall through to the name-based
        # heuristic below — see the _CTGOV_CLASS_MAP comment for why
        # OTHER_GOV is not pre-mapped to Government.
    if not name:
        return "Other"
    if any(h in name for h in _GOV_HINTS):
        return "Government"
    if any(h in name for h in _ACADEMIC_HINTS):
        return "Academic"
    if any(h in name for h in _INDUSTRY_HINTS):
        return "Industry"
    if _looks_like_personal_name(name):
        return "Academic"
    return "Other"


# ---------------------------------------------------------------------------
# AgeGroup / ProductName derivations
# ---------------------------------------------------------------------------

def _parse_age_years(age_str: str | None) -> float | None:
    """Parse CT.gov age strings like '18 Years', '6 Months' → years as float."""
    if not age_str:
        return None
    s = str(age_str).strip().lower()
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(year|month|week|day)s?\b", s)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "year":
        return val
    if unit == "month":
        return val / 12.0
    if unit == "week":
        return val / 52.0
    if unit == "day":
        return val / 365.0
    return None


def _derive_age_group(std_ages: str | None, min_age: str | None = None, max_age: str | None = None) -> str:
    """Return 'Pediatric' | 'Adult' | 'Both' | 'Unknown' from StdAges (primary)
    with MinAge/MaxAge fallback."""
    tags = set()
    if std_ages:
        tags = {t.strip().upper() for t in str(std_ages).split("|") if t.strip()}
    has_child = bool(tags & {"CHILD"})
    has_adult = bool(tags & {"ADULT", "OLDER_ADULT"})
    if has_child and has_adult:
        return "Both"
    if has_adult and not has_child:
        return "Adult"
    if has_child and not has_adult:
        return "Pediatric"

    # Fallback: parse min/max
    lo = _parse_age_years(min_age)
    hi = _parse_age_years(max_age)
    if lo is None and hi is None:
        return "Unknown"
    lo_v = lo if lo is not None else 0.0
    hi_v = hi if hi is not None else 200.0
    if hi_v < 18:
        return "Pediatric"
    if lo_v >= 18:
        return "Adult"
    return "Both"


_NAMED_PRODUCT_ALIASES: list[tuple[str, str]] = []


def _rebuild_named_product_alias_index() -> None:
    """Cache (alias_normalized, canonical_name) sorted by descending length.
    Longest match wins — prevents 'caba' matching inside 'caba-201'."""
    global _NAMED_PRODUCT_ALIASES
    pairs: list[tuple[str, str]] = []
    try:
        from config import NAMED_PRODUCTS  # type: ignore
        for canonical, entry in NAMED_PRODUCTS.items():
            for alias in entry.get("aliases", []):
                n = _normalize_text(alias)
                if n:
                    pairs.append((n, canonical))
    except Exception:
        pairs = []
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    _NAMED_PRODUCT_ALIASES = pairs


_rebuild_named_product_alias_index()


def _derive_product_name(text: str) -> str | None:
    """Return canonical NAMED_PRODUCTS key whose longest alias appears in text.
    Uses word-boundary matching to avoid partial-alias collisions.

    Normalises text internally so callers may pass raw or already-normalised
    input. _normalize_text is idempotent on already-normalised input.
    """
    if not text:
        return None
    normalized = _normalize_text(text)
    for alias, canonical in _NAMED_PRODUCT_ALIASES:
        if _term_in_text(normalized, alias):
            return canonical
    return None


_FETCH_MAX_ATTEMPTS = 4
_FETCH_BACKOFF_BASE = 1.5  # seconds — 1.5, 3.0, 6.0


def _request_with_retry(url: str, params: dict, timeout: int = 30) -> requests.Response:
    """GET with exponential backoff on transient failures.

    Retries on ConnectionError, Timeout, and 5xx responses. 4xx (client
    errors) and other unexpected exceptions raise immediately — those are
    not transient. Caller still receives a clear HTTPError if every retry
    fails so a partial fetch surfaces as a hard failure rather than silent
    data loss. (Phase 2 of REVIEW.md.)
    """
    last_exc: Exception | None = None
    for attempt in range(1, _FETCH_MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
        else:
            if resp.status_code < 500:
                # 2xx success or 4xx client error — return either way; the
                # caller checks status_code and raises on non-200.
                return resp
            last_exc = requests.HTTPError(
                f"ClinicalTrials.gov API error {resp.status_code}: {resp.text[:200]}"
            )
        if attempt < _FETCH_MAX_ATTEMPTS:
            time.sleep(_FETCH_BACKOFF_BASE ** attempt)
    # All retries exhausted.
    raise last_exc if last_exc else RuntimeError("fetch failed without an exception")


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

    studies: list[dict] = []
    page_no = 0
    while True:
        page_no += 1
        try:
            resp = _request_with_retry(BASE_URL, params)
        except Exception as e:
            # Surface the partial-fetch context — without this, a transient
            # CT.gov outage mid-pagination silently loses cumulative pages.
            raise requests.HTTPError(
                f"ClinicalTrials.gov fetch failed on page {page_no} after "
                f"{_FETCH_MAX_ATTEMPTS} attempts (cumulative studies so far: "
                f"{len(studies):,}): {e}"
            ) from e
        if resp.status_code != 200:
            raise requests.HTTPError(
                f"ClinicalTrials.gov API error {resp.status_code} on page "
                f"{page_no}: {resp.text[:200]}"
            )
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
    elig_mod = ps.get("eligibilityModule", {})
    outcomes_mod = ps.get("outcomesModule", {})

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
        "LeadSponsorClass": (sponsor_mod.get("leadSponsor") or {}).get("class"),
        "MinAge": elig_mod.get("minimumAge"),
        "MaxAge": elig_mod.get("maximumAge"),
        "StdAges": "|".join(elig_mod.get("stdAges") or []) or None,
        "PrimaryEndpoints": "|".join(
            o.get("measure", "") for o in (outcomes_mod.get("primaryOutcomes") or [])
            if o.get("measure")
        ) or None,
    }


def _extract_sites(study: dict) -> list[dict]:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    status = ps.get("statusModule", {})
    loc_mod = ps.get("contactsLocationsModule", {})

    sites = []
    for loc in (loc_mod.get("locations") or []):
        gp = loc.get("geoPoint") or {}
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
                "Latitude": gp.get("lat"),
                "Longitude": gp.get("lon"),
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
    df["LLMOverride"] = df["NCTId"].isin(_LLM_OVERRIDES)

    hard_manual_mask = df["NCTId"].apply(lambda n: n.strip() in HARD_EXCLUDED_NCT_IDS)
    hard_llm_mask = df["NCTId"].apply(lambda n: n.strip() in _LLM_EXCLUDED_NCT_IDS) & ~hard_manual_mask
    hard_mask = hard_manual_mask | hard_llm_mask
    n_hard_excluded = int(hard_manual_mask.sum())
    n_llm_excluded = int(hard_llm_mask.sum())

    df_after_hard = df[~hard_mask].copy()
    indication_mask = df_after_hard.apply(lambda r: _is_indication_excluded(r.to_dict()), axis=1)
    n_indication_excluded = int(indication_mask.sum())

    df = df_after_hard[~indication_mask].copy()
    n_included = len(df)

    target_results = df.apply(lambda r: _assign_target(r.to_dict()), axis=1)
    df["TargetCategory"] = target_results.apply(lambda x: x[0])
    df["TargetSource"] = target_results.apply(lambda x: x[1])

    type_results = df.apply(
        lambda r: _assign_product_type(r.to_dict(), r["TargetSource"]), axis=1
    )
    df["ProductType"] = type_results.apply(lambda x: x[0])
    df["ProductTypeSource"] = type_results.apply(lambda x: x[1])

    df["ClassificationConfidence"] = df.apply(
        lambda r: _compute_confidence(
            r["TargetCategory"], r["TargetSource"],
            r["ProductType"], r["ProductTypeSource"],
            r["DiseaseEntity"],
            llm_override=bool(r.get("LLMOverride", False)),
        ),
        axis=1,
    )
    df["SponsorType"] = df.apply(
        lambda r: _classify_sponsor(r.get("LeadSponsor"), r.get("LeadSponsorClass")),
        axis=1,
    )
    df["AgeGroup"] = df.apply(
        lambda r: _derive_age_group(r.get("StdAges"), r.get("MinAge"), r.get("MaxAge")),
        axis=1,
    )
    df["ProductName"] = df.apply(lambda r: _derive_product_name(_row_text(r.to_dict())), axis=1)

    df["StartDate"] = pd.to_datetime(df["StartDate"], errors="coerce")
    df["StartYear"] = df["StartDate"].dt.year
    df["LastUpdatePostDate"] = pd.to_datetime(df["LastUpdatePostDate"], errors="coerce")
    df["EnrollmentCount"] = pd.to_numeric(df["EnrollmentCount"], errors="coerce")
    df["SnapshotDate"] = datetime.utcnow().date().isoformat()

    prisma = {
        "n_fetched": n_fetched,
        "n_duplicates_removed": n_duplicates,
        "n_after_dedup": n_after_dedup,
        "n_hard_excluded": n_hard_excluded,
        "n_llm_excluded": n_llm_excluded,
        "n_indication_excluded": n_indication_excluded,
        "n_total_excluded": n_hard_excluded + n_llm_excluded + n_indication_excluded,
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

def backfill_site_geo(df_sites: pd.DataFrame, *, batch_size: int = 100,
                       sleep_between_batches: float = 0.25) -> pd.DataFrame:
    """Patch a sites DataFrame with geoPoint.lat / lon for every row that
    lacks them. Returns a new DataFrame; never mutates the input.

    Re-fetches CT.gov in batches of 100 NCT IDs, extracts geoPoint per
    location, and merges by (NCTId, Facility, City, Country). Existing
    Latitude / Longitude values are preserved — only blanks are filled.

    The standalone scripts/backfill_site_geo.py CLI also calls this so
    the runtime path and the retroactive-snapshot path share one
    implementation. (Phase 2 of REVIEW.md.)
    """
    out = df_sites.copy()
    for col in ("Latitude", "Longitude"):
        if col not in out.columns:
            out[col] = pd.NA
    if out.empty:
        return out

    needs_geo = out["Latitude"].isna() | out["Longitude"].isna()
    if not needs_geo.any():
        return out

    nct_ids = sorted(out.loc[needs_geo, "NCTId"].dropna().unique().tolist())
    if not nct_ids:
        return out

    lookup: dict[tuple[str, str, str, str], tuple[float, float]] = {}
    for i in range(0, len(nct_ids), batch_size):
        batch = nct_ids[i : i + batch_size]
        params = {
            "filter.ids": ",".join(batch),
            "fields": "NCTId,ContactsLocationsModule",
            "pageSize": batch_size,
            "format": "json",
        }
        try:
            resp = _request_with_retry(BASE_URL, params)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            # Backfill is best-effort; a transient failure on one batch
            # shouldn't fail the parent save_snapshot. Operator can re-run
            # scripts/backfill_site_geo.py against the saved snapshot.
            continue
        for study in data.get("studies", []):
            ps = study.get("protocolSection", {}) or {}
            ident = ps.get("identificationModule", {}) or {}
            nct = ident.get("nctId") or ""
            loc_mod = ps.get("contactsLocationsModule", {}) or {}
            for loc in (loc_mod.get("locations") or []):
                gp = loc.get("geoPoint") or {}
                lat, lon = gp.get("lat"), gp.get("lon")
                if lat is None or lon is None:
                    continue
                key = (
                    str(nct), str(loc.get("facility") or ""),
                    str(loc.get("city") or ""), str(loc.get("country") or ""),
                )
                lookup[key] = (float(lat), float(lon))
        time.sleep(sleep_between_batches)

    for idx in out.index[needs_geo]:
        row = out.loc[idx]
        key = (
            str(row.get("NCTId") or ""), str(row.get("Facility") or ""),
            str(row.get("City") or ""), str(row.get("Country") or ""),
        )
        hit = lookup.get(key)
        if hit:
            out.at[idx, "Latitude"], out.at[idx, "Longitude"] = hit
    return out


def save_snapshot(
    df: pd.DataFrame,
    df_sites: pd.DataFrame,
    prisma: dict,
    snapshot_dir: str = "snapshots",
    statuses: list[str] | None = None,
    backfill_geo: bool = False,
) -> str:
    """Save a frozen dataset to snapshots/<date>/. Returns the snapshot date string.

    Determinism contract (REVIEW.md Phase 2):
      * trials.csv and sites.csv are sorted by stable keys before write so
        two snapshots of identical upstream data are byte-identical (CT.gov
        pagination ordering does not leak into the snapshot).
      * metadata.json carries snapshot_date but NOT a wall-clock timestamp;
        the per-run wall clock lives in `runinfo.json` alongside it (kept
        out of any byte-identity comparison).

    backfill_geo: when True (default False — non-breaking for existing
    callers and tests), runs `backfill_site_geo` against df_sites before
    sorting + writing so the saved snapshot is geo-complete on day one.
    The app's "Save snapshot" button opts in; tests / dev callers stay
    network-free unless they pass True explicitly.
    """
    snapshot_date = datetime.utcnow().date().isoformat()
    out_dir = os.path.join(snapshot_dir, snapshot_date)
    os.makedirs(out_dir, exist_ok=True)

    if backfill_geo:
        df_sites = backfill_site_geo(df_sites)

    df_out = df.sort_values("NCTId", kind="stable").reset_index(drop=True) \
        if "NCTId" in df.columns else df
    df_out.to_csv(os.path.join(out_dir, "trials.csv"), index=False)

    if not df_sites.empty and {"NCTId", "Facility"}.issubset(df_sites.columns):
        # Sort on the full discriminating tuple so duplicate (NCTId, Facility,
        # City, Country) rows (multi-contact sites) are deterministically
        # ordered. State / Zip / SiteStatus / Lat / Lon serve as tiebreakers
        # so byte-identity holds across reshuffled inputs.
        sites_sort_keys = [c for c in (
            "NCTId", "Facility", "City", "Country", "State", "Zip",
            "SiteStatus", "Latitude", "Longitude",
        ) if c in df_sites.columns]
        sites_out = df_sites.sort_values(sites_sort_keys, kind="stable").reset_index(drop=True)
    else:
        sites_out = df_sites
    sites_out.to_csv(os.path.join(out_dir, "sites.csv"), index=False)

    with open(os.path.join(out_dir, "prisma.json"), "w") as f:
        json.dump(prisma, f, indent=2, sort_keys=True)

    metadata = {
        "snapshot_date": snapshot_date,
        "statuses_filter": sorted(statuses or []),
        "n_trials": len(df_out),
        "n_sites": len(sites_out),
        "api_base_url": BASE_URL,
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    # Per-run wall-clock info kept separate so it doesn't break byte-identity
    # comparisons of metadata.json. Reviewers can still see when the snapshot
    # was rebuilt without that info polluting the deterministic surface.
    runinfo = {
        "created_utc": datetime.utcnow().isoformat(),
    }
    with open(os.path.join(out_dir, "runinfo.json"), "w") as f:
        json.dump(runinfo, f, indent=2, sort_keys=True)

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
    # Back-compat: snapshots created before new columns were added
    if "DiseaseEntities" not in df.columns:
        df["DiseaseEntities"] = df["DiseaseEntity"].fillna("Unclassified")
    if "TrialDesign" not in df.columns:
        df["TrialDesign"] = "Single disease"
    if "LLMOverride" not in df.columns:
        df["LLMOverride"] = df["NCTId"].isin(_LLM_OVERRIDES)
    if "TargetSource" not in df.columns:
        df["TargetSource"] = "legacy_snapshot"
    if "ProductTypeSource" not in df.columns:
        df["ProductTypeSource"] = "legacy_snapshot"
    if "ClassificationConfidence" not in df.columns:
        # Back-compat: also map older "Confidence" column if present
        if "Confidence" in df.columns:
            df["ClassificationConfidence"] = df["Confidence"]
        else:
            df["ClassificationConfidence"] = df.apply(
                lambda r: _compute_confidence(
                    r.get("TargetCategory", ""), r.get("TargetSource", "legacy_snapshot"),
                    r.get("ProductType", ""), r.get("ProductTypeSource", "legacy_snapshot"),
                    r.get("DiseaseEntity", ""),
                    llm_override=bool(r.get("LLMOverride", False)),
                ),
                axis=1,
            )
    if "SponsorType" not in df.columns:
        df["SponsorType"] = df.apply(
            lambda r: _classify_sponsor(r.get("LeadSponsor"), r.get("LeadSponsorClass")),
            axis=1,
        )
    if "AgeGroup" not in df.columns:
        df["AgeGroup"] = df.apply(
            lambda r: _derive_age_group(r.get("StdAges"), r.get("MinAge"), r.get("MaxAge")),
            axis=1,
        )
    if "ProductName" not in df.columns:
        df["ProductName"] = df.apply(lambda r: _derive_product_name(_row_text(r.to_dict())), axis=1)

    df_sites_path = os.path.join(out_dir, "sites.csv")
    if os.path.exists(df_sites_path):
        df_sites = pd.read_csv(df_sites_path)
    else:
        df_sites = pd.DataFrame()
    # Back-compat: old snapshots predate site-level lat/lon columns.
    for _col in ("Latitude", "Longitude"):
        if not df_sites.empty and _col not in df_sites.columns:
            df_sites[_col] = pd.NA

    prisma_path = os.path.join(out_dir, "prisma.json")
    if os.path.exists(prisma_path):
        with open(prisma_path) as f:
            prisma = json.load(f)
    else:
        prisma = {}

    return df, df_sites, prisma


def snapshot_diff(df_new: pd.DataFrame, df_old: pd.DataFrame) -> dict:
    """Compute diff between two snapshot DataFrames.

    Returns dict with:
      added        — rows (records) present in new but not old
      removed      — rows present in old but not new
      status_changed — records where OverallStatus differs
      class_changed  — records where DiseaseEntity / TargetCategory / ProductType differ
      enrollment_changed — records where EnrollmentCount differs
    """
    tracked = ["NCTId", "BriefTitle", "OverallStatus", "Phase",
               "DiseaseEntity", "TargetCategory", "ProductType",
               "EnrollmentCount", "LeadSponsor"]
    cols_new = [c for c in tracked if c in df_new.columns]
    cols_old = [c for c in tracked if c in df_old.columns]

    new_idx = df_new.set_index("NCTId")[cols_new[1:]] if not df_new.empty else pd.DataFrame()
    old_idx = df_old.set_index("NCTId")[cols_old[1:]] if not df_old.empty else pd.DataFrame()

    new_ids = set(new_idx.index) if len(new_idx) else set()
    old_ids = set(old_idx.index) if len(old_idx) else set()

    added = new_idx.loc[sorted(new_ids - old_ids)].reset_index() if (new_ids - old_ids) else pd.DataFrame()
    removed = old_idx.loc[sorted(old_ids - new_ids)].reset_index() if (old_ids - new_ids) else pd.DataFrame()

    common = sorted(new_ids & old_ids)
    def _changes(col: str) -> pd.DataFrame:
        if col not in new_idx.columns or col not in old_idx.columns or not common:
            return pd.DataFrame()
        left = new_idx.loc[common, col]
        right = old_idx.loc[common, col]
        mask = (left.fillna("") != right.fillna("")) if left.dtype == object else (left.fillna(-1) != right.fillna(-1))
        if not mask.any():
            return pd.DataFrame()
        changed = pd.DataFrame({
            "NCTId": left.index[mask],
            f"{col} (old)": right[mask].values,
            f"{col} (new)": left[mask].values,
        })
        titles = new_idx.loc[changed["NCTId"], "BriefTitle"].values if "BriefTitle" in new_idx.columns else [""] * len(changed)
        changed.insert(1, "BriefTitle", titles)
        return changed

    return {
        "added": added,
        "removed": removed,
        "status_changed": _changes("OverallStatus"),
        "disease_changed": _changes("DiseaseEntity"),
        "target_changed": _changes("TargetCategory"),
        "product_changed": _changes("ProductType"),
        "enrollment_changed": _changes("EnrollmentCount"),
        "n_added": len(added),
        "n_removed": len(removed),
        "n_common": len(common),
    }


def export_curation_loop(df: pd.DataFrame, path: str = "curation_loop.csv") -> int:
    """Write low-confidence trials to CSV for LLM re-review. Returns row count."""
    if "Confidence" not in df.columns:
        return 0
    low = df[df["Confidence"] == "low"].copy()
    cols = [c for c in [
        "NCTId", "BriefTitle", "Conditions", "Interventions",
        "DiseaseEntity", "TargetCategory", "ProductType",
        "TargetSource", "ProductTypeSource", "Confidence",
        "LeadSponsor", "BriefSummary",
    ] if c in low.columns]
    low[cols].to_csv(path, index=False)
    return len(low)


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
