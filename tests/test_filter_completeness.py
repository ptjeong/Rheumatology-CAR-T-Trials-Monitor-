"""Regression test for the silent NaN-exclusion bug in sidebar filters.

Adapted from the onc app's tests/test_filter_completeness.py for the
rheum 5-axis filter set (no Branch / DiseaseCategory; add TrialDesign
/ Phase / Modality).

Bug discovered 2026-04-26 in onc (commit 085629a) and identified as
present in rheum on the 2026-04-25 snapshot:
  - 28 trials had `Countries = NaN` (CT.gov did not populate the
    locations module).
  - 27 trials had `Phase = NaN` (CT.gov Phase field empty).
  - The country / phase filters used `df[col].fillna("").str.contains(...)`
    or `df[col].isin(...)`, both of which return False for NaN.
  - Even with ALL options selected (the default), those trials were
    silently excluded from every chart, table, and CSV export.
  - User-facing impact: "Filtered trials" badge < PRISMA n_included
    by the count of NaN-bearing trials.

Fix (commit ahead of these tests): every sidebar filter now applies
the rule "narrow ONLY when the user has selected a SUBSET of the
available options". When the user has every option selected (the
default), the filter is skipped entirely so trials with NaN values
in that column are preserved.

These tests assert:
  1. With NaN-Countries trial → preserved when all countries selected
  2. Country subset filter still narrows correctly
  3. Same defensive pattern on a categorical .isin path (TrialDesign)
  4. TrialDesign subset filter still narrows
  5. Live-snapshot NaN inventory: surfaces any future column gaining
     unexpected NaNs while NOT being on the NaN-safe whitelist
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pytest

from pipeline import load_snapshot, list_snapshots


# ---------------------------------------------------------------------------
# Direct unit test of the filter-pattern (no Streamlit needed)
# ---------------------------------------------------------------------------

def _apply_filters_minimal(
    df: pd.DataFrame,
    *,
    design_sel: list, design_options: list,
    country_sel: list, country_options: list,
) -> pd.DataFrame:
    """Replicates the production filter contract for two columns —
    enough to assert the NaN-preservation invariant.

    Real production code lives in `app.py` (the "Apply filters" block,
    ~line 2540+); this helper mirrors the same `if sel and len(sel) <
    len(options)` pattern but is testable without a Streamlit context.
    """
    import re as _re
    mask = pd.Series(True, index=df.index)

    if design_sel and len(design_sel) < len(design_options):
        mask &= df["TrialDesign"].isin(design_sel)

    if country_sel and len(country_sel) < len(country_options):
        country_pattern = "|".join([_re.escape(c) for c in country_sel])
        mask &= df["Countries"].fillna("").str.contains(
            country_pattern, case=False, na=False, regex=True,
        )
    return df[mask].copy()


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """3 trials: one with Countries=NaN (the regression case),
    two with normal country strings."""
    return pd.DataFrame([
        {"NCTId": "NCT0001", "TrialDesign": "Single disease",
         "Countries": "United States"},
        {"NCTId": "NCT0002", "TrialDesign": "Basket/Multidisease",
         "Countries": "China"},
        {"NCTId": "NCT0003", "TrialDesign": "Single disease",
         "Countries": pd.NA},
    ])


# ---- Regression: NaN-Countries trial preserved with all-selected ----

def test_country_nan_trial_preserved_when_all_countries_selected(synthetic_df):
    """The 28-trial regression. With ALL countries selected (the
    default state), a trial with NaN Countries must NOT be filtered
    out."""
    country_options = ["United States", "China"]
    country_sel = country_options.copy()  # user has all selected
    out = _apply_filters_minimal(
        synthetic_df,
        design_sel=["Single disease", "Basket/Multidisease"],
        design_options=["Single disease", "Basket/Multidisease"],
        country_sel=country_sel,
        country_options=country_options,
    )
    assert "NCT0003" in set(out["NCTId"]), (
        "NaN-Countries trial NCT0003 was silently excluded — the "
        "regression has returned. Check that the country filter "
        "skips when len(country_sel) == len(country_options)."
    )
    assert len(out) == 3


def test_country_subset_filter_does_narrow(synthetic_df):
    """When the user actually narrows to a subset, the filter MUST
    narrow — not just skip on every input."""
    country_options = ["United States", "China"]
    country_sel = ["China"]  # user picked just one
    out = _apply_filters_minimal(
        synthetic_df,
        design_sel=["Single disease", "Basket/Multidisease"],
        design_options=["Single disease", "Basket/Multidisease"],
        country_sel=country_sel,
        country_options=country_options,
    )
    assert set(out["NCTId"]) == {"NCT0002"}, (
        "Country filter must still narrow when the user picks a SUBSET. "
        "Got: " + str(set(out["NCTId"]))
    )


# ---- Same defensive pattern on TrialDesign (.isin path) ----

def test_design_filter_skipped_when_all_selected(synthetic_df):
    """All-designs selected → no narrowing, no would-be NaN exclusion."""
    design_options = ["Single disease", "Basket/Multidisease"]
    out = _apply_filters_minimal(
        synthetic_df,
        design_sel=design_options,
        design_options=design_options,
        country_sel=["United States", "China"],
        country_options=["United States", "China"],
    )
    assert len(out) == 3


def test_design_filter_narrows_on_subset(synthetic_df):
    """Picking just one design must narrow."""
    design_options = ["Single disease", "Basket/Multidisease"]
    out = _apply_filters_minimal(
        synthetic_df,
        design_sel=["Single disease"],
        design_options=design_options,
        country_sel=["United States", "China"],
        country_options=["United States", "China"],
    )
    assert set(out["NCTId"]) == {"NCT0001", "NCT0003"}


# ---- Live-snapshot NaN inventory ----

def test_live_snapshot_nan_inventory():
    """Tracks the per-column NaN counts on the live snapshot. If a
    column gains unexpected NaNs in a future snapshot AND the column
    is also a sidebar filter, this test surfaces it before users
    notice silent dataset shrinkage.

    Whitelist (rheum, 2026-04-25 snapshot):
      - `Countries` may have NaN (CT.gov locations module sometimes empty)
      - `Phase` may have NaN (CT.gov Phase field sometimes empty)
      - `ProductName` may have NaN (most trials have no recognised
        named product alias — that's expected, not a bug)

    Other filterable columns must stay NaN-free.
    """
    snaps = list_snapshots()
    if not snaps:
        pytest.skip("no snapshots available")
    df, _, _ = load_snapshot(snaps[0])

    nan_safe_cols = {"Countries", "Phase", "ProductName"}
    filterable_cols = [
        "DiseaseEntity", "DiseaseEntities", "TrialDesign",
        "TargetCategory", "OverallStatus", "ProductType",
        "AgeGroup", "SponsorType", "ClassificationConfidence",
    ]
    bad = []
    for col in filterable_cols:
        if col not in df.columns:
            continue
        n_nan = int(df[col].isna().sum())
        if n_nan > 0 and col not in nan_safe_cols:
            bad.append((col, n_nan))
    assert not bad, (
        "Filterable columns gained NaN values; the sidebar filter "
        "may silently exclude these trials. Either fix the pipeline "
        "to populate the column for every row, or add the column to "
        "`nan_safe_cols` and verify its filter uses the defensive "
        f"`if sel and len(sel) < len(options)` pattern. Bad: {bad}"
    )
