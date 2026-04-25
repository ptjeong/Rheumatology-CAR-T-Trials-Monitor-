"""Locked benchmark of pivotal/representative rheum CAR-T trials.

Re-runs the live pipeline classifier (plus app-level Modality derivation) on
each benchmark trial in the latest snapshot and compares per-axis labels
against curated ground truth in `tests/benchmark_set.csv`.

A regression in any axis below the F1 floor fails the test, surfacing the
disagreement so it can be triaged before the regression ships.

Run:    python -m pytest tests/test_benchmark.py -v
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import (  # noqa: E402
    _assign_product_type,
    _assign_target,
    _classify_disease,
    _classify_sponsor,
    list_snapshots,
    load_snapshot,
)

# Importing app.py triggers Streamlit "no ScriptRunContext" warnings under
# pytest. They're harmless — we only need _add_modality_vectorized.
warnings.filterwarnings("ignore")
import app  # noqa: E402  pylint: disable=wrong-import-position

BENCHMARK_PATH = Path(__file__).parent / "benchmark_set.csv"

# Per-axis F1 floors. Below this and the test fails — pick the regression up
# in CI before the snapshot ships. Values reflect what the current classifier
# achieves on the curated set; raise them as the classifier improves.
F1_FLOOR: dict[str, float] = {
    "DiseaseEntity": 0.85,
    "TargetCategory": 0.85,
    "ProductType": 0.85,
    "Modality": 0.85,
    "SponsorType": 0.90,
    "TrialDesign": 0.90,
}
CHECKED_AXES = list(F1_FLOOR.keys())


def _norm(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower()


def _load_benchmark() -> pd.DataFrame:
    df = pd.read_csv(BENCHMARK_PATH, comment="#")
    if df.empty:
        raise RuntimeError("benchmark_set.csv is empty")
    return df


def _load_latest_snapshot() -> pd.DataFrame:
    snapshots = list_snapshots()
    if not snapshots:
        pytest.skip("no snapshots available")
    df, _, _ = load_snapshot(snapshots[0])
    return df


def _live_pipeline_labels(row: dict) -> dict[str, str]:
    """Re-run the pipeline classifier on a raw snapshot row.

    We deliberately do *not* trust the snapshot's stored labels here — the
    point of the benchmark is to catch classifier regressions that haven't
    been re-snapshotted yet.
    """
    _entities, design, primary = _classify_disease(row)
    target, target_src = _assign_target(row)
    ptype, _ptype_src = _assign_product_type(row, target_source=target_src)
    sponsor = _classify_sponsor(row.get("LeadSponsor"), row.get("LeadSponsorClass"))
    return {
        "DiseaseEntity": primary,
        "TargetCategory": target,
        "ProductType": ptype,
        "SponsorType": sponsor,
        "TrialDesign": design,
    }


def _attach_modality(rows: list[dict]) -> list[dict]:
    """Compute Modality for benchmark rows using the app-level vectorized
    derivation (named-product platform overrides + γδ / NK text fallbacks).
    """
    frame = pd.DataFrame(rows)
    enriched = app._add_modality_vectorized(frame)
    out = []
    for orig, mod in zip(rows, enriched["Modality"].tolist()):
        merged = dict(orig)
        merged["Modality"] = mod
        out.append(merged)
    return out


def _per_axis_metrics(rows: list[dict]) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for axis in CHECKED_AXES:
        labels = sorted({_norm(r["expected"][axis]) for r in rows if _norm(r["expected"][axis]) is not None})
        per_label_f1 = []
        agreed = 0
        n = 0
        for r in rows:
            exp = _norm(r["expected"][axis])
            got = _norm(r["actual"][axis])
            if exp is None:
                continue
            n += 1
            if exp == got:
                agreed += 1
        for label in labels:
            tp = sum(1 for r in rows if _norm(r["expected"][axis]) == label and _norm(r["actual"][axis]) == label)
            fp = sum(1 for r in rows if _norm(r["expected"][axis]) != label and _norm(r["actual"][axis]) == label)
            fn = sum(1 for r in rows if _norm(r["expected"][axis]) == label and _norm(r["actual"][axis]) != label)
            if tp + fp == 0 or tp + fn == 0:
                f1 = 0.0
            else:
                precision = tp / (tp + fp)
                recall = tp / (tp + fn)
                f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
            per_label_f1.append(f1)
        macro_f1 = sum(per_label_f1) / len(per_label_f1) if per_label_f1 else 0.0
        metrics[axis] = {
            "n": n,
            "agreed": agreed,
            "accuracy": (agreed / n) if n else 0.0,
            "f1": macro_f1,
        }
    return metrics


def _print_metrics(metrics: dict[str, dict[str, float]]) -> None:
    print("\n=== Benchmark per-axis metrics ===")
    print(f"{'axis':<18} {'n':>3} {'agreed':>7} {'accuracy':>9} {'macroF1':>9} {'floor':>7}")
    for axis, m in metrics.items():
        print(
            f"{axis:<18} {int(m['n']):>3} {int(m['agreed']):>7} "
            f"{m['accuracy']:>9.3f} {m['f1']:>9.3f} {F1_FLOOR[axis]:>7.2f}"
        )


def _print_disagreements(rows: list[dict]) -> None:
    diffs = []
    for r in rows:
        for axis in CHECKED_AXES:
            exp = _norm(r["expected"][axis])
            got = _norm(r["actual"][axis])
            if exp is not None and exp != got:
                diffs.append((r["NCTId"], axis, r["expected"][axis], r["actual"][axis]))
    if not diffs:
        return
    print("\n=== Disagreements ===")
    for nct, axis, exp, got in diffs:
        print(f"  {nct} {axis}: expected={exp!r}  got={got!r}")


@pytest.fixture(scope="module")
def evaluation_rows() -> list[dict]:
    bench = _load_benchmark()
    snapshot = _load_latest_snapshot()
    snap_by_nct = {r["NCTId"]: r for _, r in snapshot.iterrows()}

    rows: list[dict] = []
    for _, b in bench.iterrows():
        nct = b["NCTId"]
        if nct not in snap_by_nct:
            continue
        snap_row = snap_by_nct[nct]
        actual = _live_pipeline_labels(snap_row.to_dict())
        # Modality lives in app.py — compute on a temp frame so the
        # named-product registry is honoured.
        rows.append({
            "NCTId": nct,
            "snap_row": snap_row.to_dict(),
            "actual": actual,
            "expected": {axis: b[axis] for axis in CHECKED_AXES},
        })

    # Attach modality in one vectorized pass, using snap_row + actual ProductType
    base_frames = []
    for r in rows:
        merged = dict(r["snap_row"])
        merged["TargetCategory"] = r["actual"]["TargetCategory"]
        merged["ProductType"] = r["actual"]["ProductType"]
        base_frames.append(merged)
    enriched = app._add_modality_vectorized(pd.DataFrame(base_frames))
    for r, mod in zip(rows, enriched["Modality"].tolist()):
        r["actual"]["Modality"] = mod

    return rows


def test_benchmark_coverage(evaluation_rows: list[dict]) -> None:
    """At least 50% of the benchmark must be present in the latest snapshot."""
    bench = _load_benchmark()
    found = len(evaluation_rows)
    total = len(bench)
    coverage = found / total if total else 0.0
    print(f"\nBenchmark coverage: {found}/{total} = {coverage:.1%}")
    assert coverage >= 0.5, (
        f"Only {found}/{total} benchmark trials present in the latest snapshot — "
        "benchmark may be stale, or recruitment status filters dropped them."
    )


def test_benchmark_per_axis_accuracy(evaluation_rows: list[dict]) -> None:
    """Each axis must clear its F1 floor on the benchmark set."""
    if len(evaluation_rows) < 5:
        pytest.skip(f"only {len(evaluation_rows)} benchmark trials in snapshot — too few to score")

    metrics = _per_axis_metrics(evaluation_rows)
    _print_metrics(metrics)
    _print_disagreements(evaluation_rows)

    failures = []
    for axis, m in metrics.items():
        if m["n"] < 5:
            continue
        if m["f1"] < F1_FLOOR[axis]:
            failures.append((axis, m["f1"], F1_FLOOR[axis]))
    assert not failures, "F1 below floor: " + ", ".join(
        f"{a}={f:.3f} (floor {fl:.2f})" for a, f, fl in failures
    )
