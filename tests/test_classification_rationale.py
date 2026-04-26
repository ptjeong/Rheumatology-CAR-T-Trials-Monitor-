"""Tests for `pipeline.compute_classification_rationale` (rheum).

The dashboard's "How was this classified?" expander depends on this
helper returning a stable shape with sensible content. A regression
here would silently degrade the per-trial audit experience without
any failing user-facing path — hence dedicated tests.

Adapted from the onc app's tests/test_classification_rationale.py for
the rheum 5-axis schema (no Branch / DiseaseCategory; adds TrialDesign).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest

from pipeline import compute_classification_rationale


# Rheum's 5 axes (no Branch / DiseaseCategory)
_AXES = {"DiseaseEntity", "TrialDesign", "TargetCategory",
         "ProductType", "SponsorType"}


@pytest.fixture
def sle_row() -> dict:
    return {
        "NCTId": "NCT_TEST_SLE",
        "BriefTitle": "Anti-CD19 CAR-T in refractory systemic lupus erythematosus",
        "BriefSummary": "Phase 1 trial of autologous anti-CD19 CAR-T in SLE",
        "Conditions": "Systemic Lupus Erythematosus",
        "Interventions": "anti-CD19 CAR-T",
        "LeadSponsor": "Universitätsklinikum Köln",
        "LeadSponsorClass": "OTHER",
    }


@pytest.fixture
def basket_row() -> dict:
    return {
        "NCTId": "NCT_TEST_BASKET",
        "BriefTitle": "CAR-T cells in B-cell-mediated autoimmune diseases",
        "BriefSummary": "Phase 1 of allogeneic CD19/BCMA dual CAR-T in SLE, "
                        "systemic sclerosis, and idiopathic inflammatory myopathies",
        "Conditions": "Systemic Lupus Erythematosus | Systemic Sclerosis | Myositis",
        "Interventions": "CD19/BCMA dual CAR-T",
        "LeadSponsor": "Acme Biopharma Inc",
        "LeadSponsorClass": "INDUSTRY",
    }


def test_returns_all_five_axes(sle_row):
    out = compute_classification_rationale(sle_row)
    assert set(out.keys()) == _AXES


def test_each_axis_has_required_keys(sle_row):
    out = compute_classification_rationale(sle_row)
    for axis, info in out.items():
        assert "label" in info, f"{axis} missing 'label'"
        assert "source" in info, f"{axis} missing 'source'"
        assert "matched_terms" in info, f"{axis} missing 'matched_terms'"
        assert "explanation" in info, f"{axis} missing 'explanation'"
        assert isinstance(info["matched_terms"], list), (
            f"{axis} matched_terms must be a list"
        )


def test_sle_classified_correctly(sle_row):
    out = compute_classification_rationale(sle_row)
    assert out["DiseaseEntity"]["label"] == "SLE"
    assert out["TrialDesign"]["label"] == "Single disease"
    assert out["TargetCategory"]["label"] == "CD19"
    # Rheum's strict map should match systemic lupus erythematosus / lupus nephritis / sle
    assert any("lupus" in t.lower() or t.lower() == "sle"
               for t in out["DiseaseEntity"]["matched_terms"])
    assert out["SponsorType"]["label"] == "Academic"


def test_basket_promotes_correctly(basket_row):
    out = compute_classification_rationale(basket_row)
    assert out["DiseaseEntity"]["label"] == "Basket/Multidisease"
    assert out["TrialDesign"]["label"] == "Basket/Multidisease"
    assert "Multi-systemic match" in out["DiseaseEntity"]["explanation"]


def test_sponsor_industry(basket_row):
    out = compute_classification_rationale(basket_row)
    assert out["SponsorType"]["label"] == "Industry"


def test_pure_function_no_side_effects(sle_row):
    """Calling rationale must not mutate the input row."""
    snapshot = dict(sle_row)
    _ = compute_classification_rationale(sle_row)
    assert sle_row == snapshot


def test_idempotent(sle_row):
    """Same input → same output, every time."""
    a = compute_classification_rationale(sle_row)
    b = compute_classification_rationale(sle_row)
    assert a == b


def test_handles_empty_row():
    """Defensive: a near-empty row should still return all 5 axes
    rather than raising — drilldown UI must not crash on edge data."""
    out = compute_classification_rationale({"NCTId": "NCT_TEST_EMPTY"})
    assert set(out.keys()) == _AXES


def test_source_tag_is_one_of_known_values(sle_row, basket_row):
    """Source tags must come from a known vocabulary (not ad-hoc)."""
    known_prefixes = {
        "llm_override", "rule_based", "named_product", "explicit_marker",
        "car_core_fallback", "unknown", "legacy_snapshot",
        "explicit_autologous", "explicit_allogeneic",
        "explicit_in_vivo_title", "explicit_in_vivo_text",
        "weak_allogeneic_marker", "weak_autologous_marker",
        "default_autologous_no_allo_markers", "no_signal",
        "lead_sponsor_class + name_pattern",
        "derived_from_disease_entity",
    }
    for row in (sle_row, basket_row):
        out = compute_classification_rationale(row)
        unknown = [
            (axis, info["source"]) for axis, info in out.items()
            if info["source"] not in known_prefixes
        ]
        assert not unknown, f"Unknown source tags surfaced: {unknown}"
