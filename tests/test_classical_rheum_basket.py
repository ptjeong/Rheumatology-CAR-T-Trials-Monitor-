"""Regression tests for the classical-rheumatology basket detector.

The detector splits basket/multidisease trials into:
  - "Classical rheumatology basket" — constituents are ALL CTD/IA/Vasc,
    no non-rheum text signal. Surfaced as a rheum-blue wedge in the Fig 1
    sunburst, contiguous with the CTD → IA → Vasculitis arc.
  - "Basket/Multidisease" — everything else (mixed-class baskets).

Why these tests matter:
  - The basket family/colour change is user-visible across Fig 1 sunburst,
    Fig 5 trials-by-disease bar, Fig 9 caption, and the trial drilldown
    "Family:" line. A regression here would silently misclassify trials
    in or out of the rheum cluster on every chart.
  - The defensive text-scan guard is the second line of defence against
    the entity classifier missing a non-rheum constituent — these tests
    lock that contract in.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pipeline import (
    _CLASSICAL_RHEUM_ENTITIES,
    is_classical_rheum_basket,
)


class TestEntitySetCoverage:
    """Lock the canonical CTD / IA / Vasc set so a future entity-rename in
    pipeline.py doesn't silently drop a member from the rheum cluster."""

    def test_set_contains_all_three_subfamilies(self):
        # Connective tissue
        assert {"SLE", "SSc", "Sjogren", "IIM", "CTD_other", "IgG4-RD"} <= _CLASSICAL_RHEUM_ENTITIES
        # Inflammatory arthritis
        assert "RA" in _CLASSICAL_RHEUM_ENTITIES
        # Vasculitis
        assert {"AAV", "Behcet"} <= _CLASSICAL_RHEUM_ENTITIES

    def test_set_excludes_cgvhd(self):
        """cGVHD lives under 'Other autoimmune' — a basket spanning cGVHD
        and a rheum entity is mixed-class, NOT classical-rheum."""
        assert "cGVHD" not in _CLASSICAL_RHEUM_ENTITIES

    def test_set_excludes_neuro_and_glomerular(self):
        """Sanity: classifier-emitted non-rheum entities must not creep in."""
        for non_rheum in ("MS", "NMOSD", "CIDP", "T1D", "IgAN"):
            assert non_rheum not in _CLASSICAL_RHEUM_ENTITIES


class TestQualifies:
    """Trials that SHOULD be flagged as classical-rheum baskets."""

    def test_ctd_dual(self):
        # SLE + SSc — both connective tissue → qualifies
        assert is_classical_rheum_basket("SLE|SSc")

    def test_pan_rheum_triad(self):
        # SLE + RA + AAV — one from each subfamily → qualifies
        assert is_classical_rheum_basket("SLE|RA|AAV")

    def test_clean_text_no_disqualifier(self):
        # Title mentions "rheumatology" — neutral, allowed
        assert is_classical_rheum_basket(
            "SLE|RA",
            conditions="Systemic lupus erythematosus, Rheumatoid arthritis",
            brief_title="CD19 CAR-T in refractory rheumatologic disease",
        )

    def test_ctd_with_iia_and_vasc(self):
        # 3-disease basket spanning all three rheum subfamilies
        assert is_classical_rheum_basket("SLE|IIM|Behcet")


class TestDoesNotQualify:
    """Trials that should NOT be flagged."""

    def test_single_rheum_entity(self):
        # Only 1 rheum entity — not a basket spread, even if labelled as one
        assert not is_classical_rheum_basket("SLE")

    def test_empty_entities(self):
        assert not is_classical_rheum_basket("")
        assert not is_classical_rheum_basket(None)

    def test_only_sentinels(self):
        # Sentinel labels are stripped → effectively empty
        assert not is_classical_rheum_basket("Basket/Multidisease|Unclassified")

    def test_rheum_plus_neuro_entity(self):
        # SLE + MS — non-rheum constituent in the entities column
        assert not is_classical_rheum_basket("SLE|MS")

    def test_rheum_plus_cgvhd(self):
        # cGVHD is not classical-rheum even though it's in _SYSTEMIC_DISEASES
        assert not is_classical_rheum_basket("SLE|cGVHD")

    def test_rheum_plus_glomerular_entity(self):
        # SLE + IgAN — IgAN is glomerular, not rheum
        assert not is_classical_rheum_basket("SLE|IgAN")


class TestTextSignalGuard:
    """The defensive text-scan should disqualify even when the entity
    column lists only rheum entities — catches classifier misses."""

    def test_neuro_keyword_in_title_disqualifies(self):
        # Entities say SLE+RA but title reveals neuro → disqualify
        assert not is_classical_rheum_basket(
            "SLE|RA",
            brief_title="Phase 1 CAR-T in SLE, RA, and multiple sclerosis",
        )

    def test_glomerular_keyword_in_conditions_disqualifies(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            conditions="SLE; rheumatoid arthritis; iga nephropathy",
        )

    def test_gvhd_keyword_disqualifies(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            brief_title="CAR-T for autoimmune disease and graft-versus-host disease",
        )

    def test_cytopenia_keyword_disqualifies(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            conditions="SLE, RA, autoimmune hemolytic anemia",
        )

    def test_dermatologic_keyword_disqualifies(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            brief_title="CD19 CAR-T in SLE, RA, and pemphigus vulgaris",
        )

    def test_endocrine_keyword_disqualifies(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            conditions="SLE, RA, type 1 diabetes",
        )


class TestEdgeCases:
    """Whitespace, casing, and sentinel handling."""

    def test_whitespace_in_pipe_split(self):
        assert is_classical_rheum_basket(" SLE | RA ")

    def test_text_signals_case_insensitive(self):
        assert not is_classical_rheum_basket(
            "SLE|RA",
            brief_title="MULTIPLE SCLEROSIS in combination",
        )

    def test_ignores_sentinel_in_entities(self):
        # Sentinel "Basket/Multidisease" listed alongside real entities —
        # should be stripped, leaving SLE+RA which qualifies.
        assert is_classical_rheum_basket("SLE|RA|Basket/Multidisease")
