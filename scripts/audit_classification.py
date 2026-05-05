"""Multi-axis classification audit worklist generator.

Companion to `scripts/audit_named_products.py` (which is target-only).
This script generates the broader worklist used by
`docs/internal/CLASSIFICATION_AUDIT_PROMPT.md`: every trial with a
sentinel/generic label on ANY classification axis or low/medium overall
classification confidence.

Run from repo root:
    python3 scripts/audit_classification.py [snapshot_date]

Emits a single CSV `audit_output/classification_audit_<date>.csv`
with the columns the audit walkthrough needs:

  NCTId, BriefTitle, OfficialTitle, Interventions, Conditions,
  LeadSponsor, DiseaseEntities, TrialDesign, TargetCategory,
  ProductType, ProductName, ClassificationConfidence,
  + AxisFlags (which axes triggered inclusion in the audit)

`AxisFlags` is a pipe-joined list of {entity, target, product, conf}
tags so the auditor can sort the worklist by which axis needs
attention.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd


_SENTINEL_TARGETS = {"CAR-T_unspecified", "Other_or_unknown"}
_SENTINEL_ENTITIES = {"Other immune-mediated", "Unclassified"}
_SENTINEL_PRODUCT_TYPES = {"Unclear"}
_NON_HIGH_CONFIDENCE = {"low", "medium"}


def _resolve_snapshot(arg: str | None) -> str:
    snapshots_dir = REPO_ROOT / "snapshots"
    if arg:
        if not (snapshots_dir / arg / "trials.csv").exists():
            raise SystemExit(f"snapshot {arg} not found under {snapshots_dir}")
        return arg
    candidates = sorted(
        d.name for d in snapshots_dir.iterdir()
        if d.is_dir() and (d / "trials.csv").exists()
    )
    if not candidates:
        raise SystemExit(f"No snapshots found in {snapshots_dir}")
    return candidates[-1]


def _flags_for_row(row: pd.Series) -> list[str]:
    flags: list[str] = []
    entities = str(row.get("DiseaseEntities") or "").split("|")
    if any(e.strip() in _SENTINEL_ENTITIES for e in entities):
        flags.append("entity")
    if str(row.get("TargetCategory") or "") in _SENTINEL_TARGETS:
        flags.append("target")
    if str(row.get("ProductType") or "") in _SENTINEL_PRODUCT_TYPES:
        flags.append("product")
    if str(row.get("ClassificationConfidence") or "") in _NON_HIGH_CONFIDENCE:
        flags.append("conf")
    return flags


def main() -> None:
    snapshot = _resolve_snapshot(sys.argv[1] if len(sys.argv) > 1 else None)
    trials_path = REPO_ROOT / "snapshots" / snapshot / "trials.csv"
    out_dir = REPO_ROOT / "audit_output"
    out_dir.mkdir(exist_ok=True)

    df = pd.read_csv(trials_path)
    print(f"Loaded {len(df)} trials from snapshots/{snapshot}/trials.csv")

    rows = []
    for _, r in df.iterrows():
        flags = _flags_for_row(r)
        if not flags:
            continue
        rows.append({
            "NCTId":            r.get("NCTId", ""),
            "AxisFlags":        "|".join(flags),
            "BriefTitle":       (r.get("BriefTitle") or "")[:200],
            "OfficialTitle":    (r.get("OfficialTitle") or "")[:300],
            "Interventions":    (r.get("Interventions") or "")[:300],
            "Conditions":       (r.get("Conditions") or "")[:300],
            "LeadSponsor":      r.get("LeadSponsor") or "",
            "DiseaseEntities":  r.get("DiseaseEntities") or "",
            "TrialDesign":      r.get("TrialDesign") or "",
            "TargetCategory":   r.get("TargetCategory") or "",
            "ProductType":      r.get("ProductType") or "",
            "ProductName":      r.get("ProductName") or "",
            "ClassificationConfidence": r.get("ClassificationConfidence") or "",
        })

    audit = pd.DataFrame(rows)
    audit_path = out_dir / f"classification_audit_{snapshot}.csv"
    audit.to_csv(audit_path, index=False)

    print(f"  → {audit_path}  ({len(audit)} rows)")
    print()
    print("Per-axis flag counts:")
    for axis in ("entity", "target", "product", "conf"):
        n = audit["AxisFlags"].str.contains(axis, na=False).sum()
        print(f"  {axis:8s} {n:4d}")
    print()
    print("Next: open docs/internal/CLASSIFICATION_AUDIT_PROMPT.md")
    print("and walk Q1-Q7 for each row.")


if __name__ == "__main__":
    main()
