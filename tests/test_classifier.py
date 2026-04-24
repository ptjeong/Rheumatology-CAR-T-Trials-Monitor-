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
        assert _term_in_text("caba-201 autologous", "caba-201")

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
        assert _classify_sponsor("VA", "OTHER_GOV") == "Government"

    def test_academic_keyword_fallback(self):
        assert _classify_sponsor("Universitätsklinikum Köln", None) == "Academic"
        assert _classify_sponsor("Stanford Medical Center", None) == "Academic"

    def test_industry_keyword_fallback(self):
        assert _classify_sponsor("Kyverna Therapeutics", None) == "Industry"

    def test_none_is_other(self):
        assert _classify_sponsor(None, None) == "Other"


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
