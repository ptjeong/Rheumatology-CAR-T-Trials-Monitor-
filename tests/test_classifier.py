"""Classifier regression tests.

Run with:  python -m pytest tests/ -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import (
    _assign_product_type,
    _assign_target,
    _classify_disease,
    _classify_sponsor,
    _compute_confidence,
    _derive_age_group,
    _derive_product_name,
    _is_hard_excluded,
    _normalize_text,
    _term_in_text,
)


# ---------------------------------------------------------------------------
# Text-matching primitives
# ---------------------------------------------------------------------------

class TestWordBoundary:
    def test_short_term_is_word_bounded(self):
        assert _term_in_text("patient with cd19 car-t", "cd19")
        assert not _term_in_text("receptor cd190 variant", "cd19")

    def test_long_term_is_also_word_bounded(self):
        # This is the key fix — previously long terms used substring match,
        # which let "egfr" match inside "egfrviii".
        assert _term_in_text("anti egfr car-t", "egfr")
        assert not _term_in_text("anti egfrviii variant", "egfr")

    def test_ra_does_not_match_inside_words(self):
        assert _term_in_text("rheumatoid arthritis ra", "ra")
        assert not _term_in_text("brain tumour", "ra")

    def test_hyphenated_tokens_match(self):
        # _term_in_text expects already-normalized text. After uniform hyphen
        # collapse, both sides become "caba 201" / "car t" / etc., so search
        # should match symmetrically regardless of hyphen presence in input.
        norm = _normalize_text("CABA-201 autologous CAR-T")
        assert _term_in_text(norm, "caba-201")
        assert _term_in_text(norm, "caba 201")
        assert _term_in_text(norm, "car-t")
        # Negative: a substring that crosses a (former) hyphen boundary
        # should NOT match — collapsing makes "201autologous" impossible.
        assert not _term_in_text(norm, "201autologous")

    def test_normalize_collapses_hyphens_uniformly(self):
        """Phase 2 alignment with onc: hyphens become spaces in every token,
        so 'anti-CD19' / 'BCMA-CD19' / 'non-rheumatic' all normalise to a
        clean space-separated form."""
        assert _normalize_text("anti-CD19") == "anti cd19"
        assert _normalize_text("BCMA-CD19 dual") == "bcma cd19 dual"
        assert _normalize_text("non-rheumatic") == "non rheumatic"
        # Period preserved (e.g. for "claudin 18.2"-style version tokens)
        assert _normalize_text("claudin 18.2") == "claudin 18.2"

    def test_normalize_strips_accents_and_punctuation(self):
        assert "sjogren" in _normalize_text("Sjögren's syndrome")
        assert "relapsed refractory" in _normalize_text("R/R lupus")


# ---------------------------------------------------------------------------
# Target assignment
# ---------------------------------------------------------------------------

class TestTargetAssignment:
    def _row(self, **kw):
        base = {
            "NCTId": "NCT99999999",
            "BriefTitle": "", "BriefSummary": "",
            "Conditions": "", "Interventions": "",
        }
        base.update(kw)
        return base

    def test_explicit_cd19(self):
        target, source = _assign_target(self._row(
            BriefTitle="Anti-CD19 CAR-T for lupus",
            BriefSummary="autologous anti-CD19 CAR",
        ))
        assert target == "CD19"
        assert source == "explicit_marker"

    def test_cd19_bcma_dual(self):
        target, source = _assign_target(self._row(
            BriefSummary="anti-CD19/BCMA bispecific CAR-T",
        ))
        assert target == "CD19/BCMA dual"
        assert source == "explicit_marker"

    def test_named_product_fallback(self):
        # KYV-101 → CD19 via NAMED_PRODUCTS lookup when text lacks the antigen
        target, source = _assign_target(self._row(
            BriefTitle="KYV-101 for SSc",
            BriefSummary="Open-label study of KYV-101.",
        ))
        assert target == "CD19"
        assert source == "named_product"

    def test_car_core_fallback(self):
        target, source = _assign_target(self._row(
            BriefTitle="CAR-T cells for SLE",
            BriefSummary="chimeric antigen receptor",
        ))
        assert target == "CAR-T_unspecified"
        assert source == "car_core_fallback"

    def test_unknown_when_no_car_signal(self):
        target, source = _assign_target(self._row(
            BriefTitle="Observational study of SLE outcomes",
        ))
        assert target == "Other_or_unknown"
        assert source == "unknown"


# ---------------------------------------------------------------------------
# Product-type assignment — the newly expanded tag vocabulary
# ---------------------------------------------------------------------------

class TestProductTypeAssignment:
    def _row(self, **kw):
        base = {"NCTId": "NCT99999998",
                "BriefTitle": "", "BriefSummary": "",
                "Conditions": "", "Interventions": ""}
        base.update(kw)
        return base

    def test_explicit_autologous_via_autoleucel(self):
        pt, src = _assign_product_type(self._row(
            BriefSummary="rapcabtagene autoleucel for SLE",
        ))
        assert pt == "Autologous"
        assert src == "explicit_autologous"

    def test_explicit_allogeneic_via_ucart(self):
        pt, src = _assign_product_type(self._row(
            BriefSummary="UCART19 allogeneic platform",
        ))
        assert pt == "Allogeneic/Off-the-shelf"
        assert src == "explicit_allogeneic"

    def test_in_vivo_title_is_distinct_source(self):
        pt, src = _assign_product_type(self._row(
            BriefTitle="In vivo CAR-T for autoimmune disease",
        ))
        assert pt == "In vivo"
        assert src == "explicit_in_vivo_title"

    def test_in_vivo_text_fallback(self):
        pt, src = _assign_product_type(self._row(
            BriefSummary="lentiviral nanoparticle for in vivo programming",
        ))
        assert pt == "In vivo"
        assert src == "explicit_in_vivo_text"

    def test_default_autologous_when_target_known(self):
        # CAR-T confirmed via explicit antigen; no allo/in-vivo signal → default Autologous
        pt, src = _assign_product_type(
            self._row(BriefSummary="anti-CD19 CAR-T for SLE"),
            target_source="explicit_marker",
        )
        assert pt == "Autologous"
        assert src == "default_autologous_no_allo_markers"

    def test_no_signal_when_target_unknown(self):
        pt, src = _assign_product_type(
            self._row(BriefSummary="observational cohort"),
            target_source="unknown",
        )
        assert pt == "Unclear"
        assert src == "no_signal"

    def test_named_product_type_fallback(self):
        # UCART is in NAMED_PRODUCT_TYPES Allogeneic bucket (if configured)
        pt, src = _assign_product_type(self._row(
            BriefTitle="PRG-1801 for AAV",
            BriefSummary="PRG-1801 study",
        ))
        # Resolves via named-product or explicit; source should not be no_signal
        assert src != "no_signal"


# ---------------------------------------------------------------------------
# Confidence logic — exact spec
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_llm_override_always_high(self):
        assert _compute_confidence(
            "Other_or_unknown", "unknown", "Unclear", "no_signal",
            "Unclassified", llm_override=True,
        ) == "high"

    def test_unclassified_disease_is_low(self):
        assert _compute_confidence(
            "CD19", "explicit_marker", "Autologous", "explicit_autologous",
            "Unclassified",
        ) == "low"

    def test_unclear_target_and_default_product_is_low(self):
        assert _compute_confidence(
            "CAR-T_unspecified", "car_core_fallback",
            "Autologous", "default_autologous_no_allo_markers",
            "SLE",
        ) == "low"

    def test_unclear_target_only_is_medium(self):
        assert _compute_confidence(
            "Other_or_unknown", "unknown",
            "Autologous", "explicit_autologous", "SLE",
        ) == "medium"

    def test_default_product_only_is_medium(self):
        assert _compute_confidence(
            "CD19", "explicit_marker",
            "Autologous", "default_autologous_no_allo_markers", "SLE",
        ) == "medium"

    def test_all_explicit_is_high(self):
        assert _compute_confidence(
            "CD19", "explicit_marker",
            "Autologous", "explicit_autologous", "SLE",
        ) == "high"


# ---------------------------------------------------------------------------
# Sponsor classification
# ---------------------------------------------------------------------------

class TestSponsorClassification:
    def test_industry_via_ctgov_class(self):
        assert _classify_sponsor("Bristol-Myers Squibb", "INDUSTRY") == "Industry"

    def test_government_via_ctgov_class(self):
        assert _classify_sponsor("NCI", "NIH") == "Government"
        # OTHER_GOV is intentionally NOT pre-mapped to Government (Phase 2
        # alignment with onc; see _CTGOV_CLASS_MAP). Sponsors whose name
        # carries an explicit gov-agency signal still resolve to Government
        # via the name heuristic.
        assert _classify_sponsor("Department of Veterans Affairs", "OTHER_GOV") == "Government"

    def test_other_gov_with_industry_name_resolves_to_industry(self):
        """OTHER_GOV with industry-name signals correctly resolves through
        the heuristic to Industry. Old behaviour pre-mapped OTHER_GOV →
        Government, masking these.
        """
        assert _classify_sponsor("Acme Therapeutics, Inc.", "OTHER_GOV") == "Industry"

    def test_other_gov_with_blank_name_is_other(self):
        """OTHER_GOV with no name signal falls through to 'Other' rather
        than silently 'Government'."""
        assert _classify_sponsor("", "OTHER_GOV") == "Other"

    def test_academic_keyword_fallback(self):
        assert _classify_sponsor("Universitätsklinikum Köln", None) == "Academic"
        assert _classify_sponsor("Stanford Medical Center", None) == "Academic"

    def test_industry_keyword_fallback(self):
        assert _classify_sponsor("Kyverna Therapeutics", None) == "Industry"

    def test_none_is_other(self):
        assert _classify_sponsor(None, None) == "Other"

    def test_other_gov_academic_hospital_is_academic(self):
        assert _classify_sponsor("Anhui Provincial Hospital", "OTHER_GOV") == "Academic"

    def test_other_gov_strong_gov_name_still_government(self):
        assert _classify_sponsor("Veterans Affairs Medical Center", "OTHER_GOV") == "Government"

    def test_peoples_hospital_is_academic(self):
        assert _classify_sponsor("Peking Union Medical College Hospital", None) == "Academic"

    def test_indiv_pi_is_academic(self):
        # CT.gov class INDIV = investigator-initiated; treated as Academic
        assert _classify_sponsor("Marcela V. Maus, M.D.,Ph.D.", "INDIV") == "Academic"
        assert _classify_sponsor("David Porter", "INDIV") == "Academic"

    def test_other_class_with_degree_markers_is_academic(self):
        # CT.gov frequently tags PIs as class OTHER (not INDIV).
        assert _classify_sponsor("Marcela V. Maus, M.D.,Ph.D.", "OTHER") == "Academic"
        assert _classify_sponsor("Ting Chang, MD", "OTHER") == "Academic"

    def test_other_class_plain_person_name_is_academic(self):
        # Plain multi-word alphabetic names with no org keywords are PIs.
        assert _classify_sponsor("Bruce Cree", "OTHER") == "Academic"
        assert _classify_sponsor("Polina Stepensky", "OTHER") == "Academic"
        assert _classify_sponsor("YANRU WANG", "OTHER") == "Academic"
        assert _classify_sponsor("Daishi Tian", "OTHER") == "Academic"

    def test_gustave_roussy_is_academic(self):
        # Major cancer research hospital in France.
        assert _classify_sponsor("Gustave Roussy, Cancer Campus, Grand Paris", "OTHER") == "Academic"

    def test_calibr_scripps_is_academic(self):
        assert _classify_sponsor("Calibr, a division of Scripps Research", "OTHER") == "Academic"

    def test_company_with_industry_keywords_stays_industry(self):
        # Regression: two-word company names with industry hint → Industry, not PI.
        assert _classify_sponsor("Quell Therapeutics", None) == "Industry"
        assert _classify_sponsor("Cabaletta Bio", None) == "Industry"


# ---------------------------------------------------------------------------
# AgeGroup derivation
# ---------------------------------------------------------------------------

class TestAgeGroup:
    def test_adult_only_from_std_ages(self):
        assert _derive_age_group("ADULT|OLDER_ADULT") == "Adult"

    def test_pediatric_only_from_std_ages(self):
        assert _derive_age_group("CHILD") == "Pediatric"

    def test_both_when_child_and_adult(self):
        assert _derive_age_group("CHILD|ADULT") == "Both"

    def test_fallback_to_min_max_when_std_ages_missing(self):
        assert _derive_age_group(None, "18 Years", "65 Years") == "Adult"
        assert _derive_age_group(None, "6 Months", "17 Years") == "Pediatric"
        assert _derive_age_group(None, "2 Years", "75 Years") == "Both"

    def test_unknown_when_no_data(self):
        assert _derive_age_group(None, None, None) == "Unknown"


# ---------------------------------------------------------------------------
# ProductName derivation (longest-alias wins)
# ---------------------------------------------------------------------------

class TestProductName:
    def test_named_product_resolves(self):
        # KYV-101 is in NAMED_PRODUCTS
        assert _derive_product_name("kyv-101 autologous car-t") is not None

    def test_none_when_no_alias_in_text(self):
        assert _derive_product_name("generic car-t study") is None


# ---------------------------------------------------------------------------
# Disease classification
# ---------------------------------------------------------------------------

class TestDiseaseClassification:
    def _row(self, conditions="", title="", summary=""):
        return {
            "NCTId": "NCT",
            "BriefTitle": title, "BriefSummary": summary,
            "Conditions": conditions, "Interventions": "",
        }

    def test_sle_single_disease(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="Systemic Lupus Erythematosus",
        ))
        assert entities == ["SLE"]
        assert design == "Single disease"
        assert primary == "SLE"

    def test_basket_when_multiple_systemic(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="Systemic Lupus Erythematosus|Systemic Sclerosis|Myositis",
        ))
        assert design == "Basket/Multidisease"
        assert primary == "Basket/Multidisease"
        assert set(entities) >= {"SLE", "SSc", "IIM"}

    def test_unclassified_when_no_match(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="Unusual rare syndrome X",
        ))
        assert primary == "Unclassified"

    def test_ctd_other_pair_with_sle_is_basket(self):
        """CTD_other paired with another systemic disease (SLE/SSc/IIM/AAV)
        is a real multi-disease cohort, not a single-disease trial. Regression
        for the bug surfaced in REVIEW.md (pipeline.py:164 — CTD_other was
        missing from _SYSTEMIC_DISEASES). Live evidence: NCT07490041.
        """
        entities, design, primary = _classify_disease(self._row(
            conditions=(
                "Connective Tissue Disease | Systemic Lupus Erythematosus | "
                "Connective Tissue Disease-associated Interstitial Lung Disease"
            ),
        ))
        assert "CTD_other" in entities
        assert "SLE" in entities
        assert design == "Basket/Multidisease"
        assert primary == "Basket/Multidisease"

    def test_ctd_other_alone_stays_single_disease(self):
        """CTD_other on its own (no other systemic disease) must remain
        Single-disease. The basket promotion only fires when ≥2 systemic
        diseases match.
        """
        entities, design, primary = _classify_disease(self._row(
            conditions="Mixed Connective Tissue Disease",
        ))
        assert entities == ["CTD_other"]
        assert design == "Single disease"
        assert primary == "CTD_other"

    def test_other_immune_mediated_fallback(self):
        """Trials whose only signal is in OTHER_IMMUNE_MEDIATED_TERMS land in
        the 'Other immune-mediated' bucket. Coverage gap flagged in REVIEW.md.
        """
        entities, design, primary = _classify_disease(self._row(
            conditions="Myasthenia Gravis",
        ))
        assert primary == "Other immune-mediated"
        assert design == "Single disease"

    def test_broad_basket_phrase_promotes(self):
        """Generic 'B-cell mediated autoimmune disease' phrasing without any
        specific disease match still promotes to Basket/Multidisease.
        """
        entities, design, primary = _classify_disease(self._row(
            conditions="Refractory B-cell mediated autoimmune disease",
        ))
        assert design == "Basket/Multidisease"
        assert primary == "Basket/Multidisease"

    def test_behcet_single_disease(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="Behcet's Disease",
        ))
        assert entities == ["Behcet"]
        assert primary == "Behcet"

    def test_cgvhd_single_disease(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="Chronic Graft Versus Host Disease",
        ))
        assert entities == ["cGVHD"]
        assert primary == "cGVHD"

    def test_iggm4_single_disease(self):
        entities, design, primary = _classify_disease(self._row(
            conditions="IgG4 Related Disease",
        ))
        assert entities == ["IgG4-RD"]
        assert primary == "IgG4-RD"
