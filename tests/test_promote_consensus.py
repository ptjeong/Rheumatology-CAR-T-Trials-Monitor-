"""Tests for scripts/promote_consensus_flags.py — patch construction.

Covers the part of the promotion script that we can test without making
real GitHub API calls: the YAML-block parser shared with the consensus
detector, and the llm_overrides.json patch builder. The HTTP layer is
covered by manually running --close-issues against a real test issue
when the script is first deployed.

Adapted from the onc app's tests/test_promote_consensus.py for the
rheum override schema (no Branch / DiseaseCategory; TrialDesign
unsupported because it derives from disease_entity).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "promote_consensus_flags",
    Path(__file__).resolve().parent.parent / "scripts" / "promote_consensus_flags.py",
)
promote_consensus_flags = importlib.util.module_from_spec(_SPEC)
sys.modules["promote_consensus_flags"] = promote_consensus_flags
_SPEC.loader.exec_module(promote_consensus_flags)


def test_axis_field_map_covers_all_supported_axes():
    """The Moderation tab and the override file must agree on field names."""
    assert promote_consensus_flags.AXIS_TO_OVERRIDE_FIELD["DiseaseEntity"] == "disease_entity"
    assert promote_consensus_flags.AXIS_TO_OVERRIDE_FIELD["TargetCategory"] == "target_category"
    assert promote_consensus_flags.AXIS_TO_OVERRIDE_FIELD["ProductType"] == "product_type"


def test_axis_field_map_does_not_include_branch_for_rheum():
    """Rheum is single-branch — Branch / DiseaseCategory must NOT be in
    the override map. If a contributor adds them by mistake (porting from
    onc), this test catches it before the override file gets corrupted."""
    assert "Branch" not in promote_consensus_flags.AXIS_TO_OVERRIDE_FIELD
    assert "DiseaseCategory" not in promote_consensus_flags.AXIS_TO_OVERRIDE_FIELD


def test_unsupported_axes_include_sponsor_and_trial_design():
    """SponsorType (derived from sponsor name) and TrialDesign (derived
    from whether disease_entity == Basket/Multidisease) cannot be
    promoted through the override file — they must surface as 'skipped'
    in the dry-run report."""
    assert "SponsorType" in promote_consensus_flags.UNSUPPORTED_AXES
    assert "TrialDesign" in promote_consensus_flags.UNSUPPORTED_AXES


def test_build_patch_creates_new_entry_when_no_existing():
    proposals = {
        ("DiseaseEntity", "SLE"): {"a", "b", "c"},
        ("TargetCategory", "CD19"): {"a", "b", "c"},
    }
    entry = promote_consensus_flags._build_patch(
        nct="NCT12345678",
        proposals=proposals,
        issue_url="https://github.com/foo/bar/issues/1",
        existing=None,
    )
    assert entry["nct_id"] == "NCT12345678"
    assert entry["disease_entity"] == "SLE"
    assert entry["target_category"] == "CD19"
    assert entry["confidence"] == "high"
    assert entry["exclude"] is False
    assert "community-flag" in entry["notes"]
    assert "https://github.com/foo/bar/issues/1" in entry["notes"]
    # Rheum schema: NO branch / disease_category fields
    assert "branch" not in entry
    assert "disease_category" not in entry


def test_build_patch_updates_existing_entry_in_place():
    """Existing entries must keep unrelated fields and update only flagged axes."""
    existing = {
        "nct_id": "NCT99999999",
        "disease_entity": "SLE",   # unchanged
        "target_category": "CD19",  # WRONG, will be corrected
        "product_type": "Autologous",
        "exclude": False,
        "exclude_reason": None,
        "confidence": "medium",  # will be bumped to high
        "notes": "Original Claude curation 2025",
    }
    proposals = {
        ("TargetCategory", "BCMA"): {"a", "b", "c"},  # the only correction
    }
    entry = promote_consensus_flags._build_patch(
        nct="NCT99999999",
        proposals=proposals,
        issue_url="https://github.com/foo/bar/issues/2",
        existing=existing,
    )
    assert entry["target_category"] == "BCMA"
    # Untouched fields preserved
    assert entry["disease_entity"] == "SLE"
    assert entry["product_type"] == "Autologous"
    # Confidence bumped to high
    assert entry["confidence"] == "high"
    # Notes append (don't overwrite)
    assert "Original Claude curation 2025" in entry["notes"]
    assert "community-flag" in entry["notes"]
    assert "BCMA" in entry["notes"]


def test_build_patch_returns_none_for_unsupported_axes_only():
    """SponsorType / TrialDesign corrections aren't applied through
    llm_overrides.json. Patch builder must return None so the script
    reports `skipped` rather than silently inserting an empty entry."""
    proposals = {
        ("SponsorType", "Industry"): {"a", "b", "c"},
        ("TrialDesign", "Basket/Multidisease"): {"a", "b", "c"},
    }
    entry = promote_consensus_flags._build_patch(
        nct="NCT12345678",
        proposals=proposals,
        issue_url="https://github.com/foo/bar/issues/3",
        existing=None,
    )
    assert entry is None


def test_nct_extraction_from_issue_title():
    issue = {
        "title": "[Flag] NCT01234567 — TargetCategory should be CD19",
        "body": "details here",
    }
    assert promote_consensus_flags._nct_from_issue(issue) == "NCT01234567"


def test_nct_extraction_falls_back_to_body():
    issue = {
        "title": "[Flag] classification correction",
        "body": "Trial NCT09876543 needs a new disease_entity label.",
    }
    assert promote_consensus_flags._nct_from_issue(issue) == "NCT09876543"


def test_nct_extraction_returns_none_when_absent():
    issue = {"title": "no NCT here", "body": "neither here"}
    assert promote_consensus_flags._nct_from_issue(issue) is None


def test_parse_flag_block_handles_real_template():
    """The exact YAML payload the dashboard's link-out builder generates
    must round-trip through the parser cleanly."""
    text = """
some markdown

<!-- BEGIN_FLAG_DATA
nct_id: NCT07490041
flagged_axes:
  - axis: DiseaseEntity
    pipeline_label: "CTD_other"
    proposed_correction: "Basket/Multidisease"
  - axis: TargetCategory
    pipeline_label: "CD19/BCMA dual"
    proposed_correction: "CD19/BCMA dual"
END_FLAG_DATA -->

more markdown
"""
    blocks = promote_consensus_flags._parse_flag_blocks(text)
    assert len(blocks) == 1
    assert blocks[0]["nct_id"] == "NCT07490041"
    axes = blocks[0]["flagged_axes"]
    assert {a["axis"] for a in axes} == {"DiseaseEntity", "TargetCategory"}
