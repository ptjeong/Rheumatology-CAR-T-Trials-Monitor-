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
    _NEURO_OIM_CLUSTER_ENTITIES,
    is_classical_rheum_basket,
    is_neuro_basket,
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


# ---------------------------------------------------------------------------
# Neuro-basket detector tests (round-9 user spec: neuro-only baskets roll
# into the Neurologic autoimmune family wedge rather than the slate
# generic-basket bucket).
# ---------------------------------------------------------------------------


class TestNeuroBasketEntitySet:
    """Lock the canonical neuro OIM-cluster set."""

    def test_set_contains_canonical_neuro_diseases(self):
        assert {"MS", "NMOSD", "CIDP", "MOGAD", "AIE",
                "Myasthenia", "Stiff_person"} == _NEURO_OIM_CLUSTER_ENTITIES

    def test_no_overlap_with_classical_rheum(self):
        """Neuro and rheum entity sets must be disjoint — same trial
        can't qualify as both."""
        assert _NEURO_OIM_CLUSTER_ENTITIES.isdisjoint(_CLASSICAL_RHEUM_ENTITIES)


class TestNeuroBasketQualifies:
    """Trials that SHOULD be flagged as neuro-only baskets."""

    def test_two_neuro_entities_in_pipe(self):
        # MS + NMOSD — both neuro, qualifies
        assert is_neuro_basket("MS|NMOSD")

    def test_three_neuro_entities(self):
        assert is_neuro_basket("MS|NMOSD|CIDP")

    def test_two_text_keyword_hits(self):
        # Entity column empty / sentinel-only; qualifies via text alone
        assert is_neuro_basket(
            "",
            conditions="multiple sclerosis; neuromyelitis optica",
            brief_title="CD19 CAR-T for refractory neuro autoimmune disease",
        )

    def test_text_with_clean_entities(self):
        # Matched OIM cluster + clean text
        assert is_neuro_basket(
            "MS|NMOSD",
            conditions="Multiple sclerosis (MS); NMOSD",
            brief_title="Phase 1 CAR-T in neuro autoimmune basket",
        )


class TestNeuroBasketDoesNotQualify:
    """Trials that should NOT be flagged as neuro baskets."""

    def test_single_neuro_entity(self):
        # Only 1 neuro entity → not a neuro spread
        assert not is_neuro_basket("MS")

    def test_empty(self):
        assert not is_neuro_basket("")
        assert not is_neuro_basket(None)

    def test_neuro_plus_rheum_entity(self):
        # MS + SLE — mixed-class, NOT neuro-only
        assert not is_neuro_basket("MS|SLE")

    def test_neuro_plus_glomerular_entity(self):
        # MS + IgAN — IgAN disqualifies
        assert not is_neuro_basket("MS|IgAN")

    def test_neuro_text_with_rheum_text_disqualifies(self):
        # Text mentions both MS and SLE → mixed
        assert not is_neuro_basket(
            "MS|NMOSD",
            conditions="Multiple sclerosis; NMOSD; systemic lupus erythematosus",
        )

    def test_neuro_text_with_glomerular_text_disqualifies(self):
        assert not is_neuro_basket(
            "MS|NMOSD",
            conditions="MS; NMOSD; iga nephropathy",
        )

    def test_neuro_text_with_gvhd_disqualifies(self):
        assert not is_neuro_basket(
            "",
            brief_title="CAR-T in multiple sclerosis, NMOSD, and graft-versus-host disease",
        )


class TestNeuroBasketEdgeCases:

    def test_one_text_hit_alone_does_not_qualify(self):
        # Single neuro keyword → only 1 distinct neuro signal → fails
        assert not is_neuro_basket(
            "",
            conditions="multiple sclerosis",
        )

    def test_classifier_emitted_neuro_entities_count(self):
        # Two distinct OIM cluster entities (no text) → qualifies
        assert is_neuro_basket("CIDP|MOGAD")
