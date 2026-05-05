"""Multi-axis classification audit — CLI generator for curation_loop.csv.

Programmatic equivalent of the dashboard's Methods → "Download
curation CSV" button. Emits the same CURATION_LOOP_V1 format so the
output is interchangeable with the UI export — useful for CI
pipelines or when iterating on the classifier without spinning up
Streamlit.

Run from repo root:
    python3 scripts/audit_classification.py [snapshot_date]

Output:
    audit_output/curation_loop_<snapshot>.csv

The companion prompt `docs/internal/CLASSIFICATION_AUDIT_PROMPT.md`
walks Q1-Q7 against this CSV and patches config.py / pipeline.py /
llm_overrides.json with a strict no-downgrade acceptance gate.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd


_SENTINEL_DISEASE = {"Unclassified", "Autoimmune_other", "Other_or_unknown"}
_SENTINEL_TARGET  = {"CAR-T_unspecified", "Other_or_unknown",
                     "Unclassified", "Unknown"}
_SENTINEL_PRODUCT = {"Unclear"}

# CURATION_LOOP_V1 header — kept identical to the dashboard's
# `app.py:export_curation_loop` block so a CSV from this script is a
# drop-in replacement for the Methods-tab download.
_HEADER_LINES = [
    "# CURATION_LOOP_V1",
    "# INSTRUCTION: You are Claude Code assisting with a CAR-T rheumatology trial pipeline.",
    "# For each row below, read BriefTitle / Conditions / Interventions / BriefSummary.",
    "# Propose the correct DiseaseEntity, TargetCategory, and ProductType.",
    "# Then automatically patch config.py and/or pipeline.py to capture these cases.",
    "# Allowed DiseaseEntity values: SLE, SSc, Sjogren, CTD_other, IIM, AAV, RA, IgG4-RD,",
    "#   Behcet, cGVHD, Basket/Multidisease, Other immune-mediated, Autoimmune_other,",
    "#   Unclassified, Exclude",
    "# Allowed TargetCategory values: CD19, BCMA, CD20, CD70, CD6, CD7, BAFF, BAFF-R,",
    "#   CD19/BCMA dual, CD19/CD20 dual, CD19/BAFF dual, BCMA/CD70 dual,",
    "#   CAR-NK, CAAR-T, CAR-Treg, CAR-T_unspecified, Other_or_unknown",
    "# Allowed ProductType values: Autologous, Allogeneic/Off-the-shelf, In vivo, Unclear",
    "# UnclearFields column shows which field(s) triggered inclusion (Disease|Target|Product).",
    "# Walkthrough: docs/internal/CLASSIFICATION_AUDIT_PROMPT.md (Q1-Q7 decision tree).",
    "#",
]


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


def _unclear_fields(row: pd.Series) -> str:
    flags: list[str] = []
    if str(row.get("DiseaseEntity") or "") in _SENTINEL_DISEASE:
        flags.append("Disease")
    if str(row.get("TargetCategory") or "") in _SENTINEL_TARGET:
        flags.append("Target")
    if str(row.get("ProductType") or "") in _SENTINEL_PRODUCT:
        flags.append("Product")
    return "|".join(flags)


def main() -> None:
    snapshot = _resolve_snapshot(sys.argv[1] if len(sys.argv) > 1 else None)
    trials_path = REPO_ROOT / "snapshots" / snapshot / "trials.csv"
    out_dir = REPO_ROOT / "audit_output"
    out_dir.mkdir(exist_ok=True)

    df = pd.read_csv(trials_path)
    print(f"Loaded {len(df)} trials from snapshots/{snapshot}/trials.csv")

    df["UnclearFields"] = df.apply(_unclear_fields, axis=1)
    audit = df[df["UnclearFields"] != ""].copy()

    export_cols = [
        "NCTId", "BriefTitle", "Conditions", "Interventions",
        "DiseaseEntity", "TargetCategory", "ProductType",
        "UnclearFields", "BriefSummary",
    ]
    audit_export = audit[[c for c in export_cols if c in audit.columns]].copy()
    if "BriefSummary" in audit_export.columns:
        audit_export["BriefSummary"] = (
            audit_export["BriefSummary"].astype(str).str[:300]
        )

    # Write CURATION_LOOP_V1 — header + CSV body
    buf = io.StringIO()
    for line in _HEADER_LINES:
        buf.write(line + "\n")
    audit_export.to_csv(buf, index=False)

    out_path = out_dir / f"curation_loop_{snapshot}.csv"
    out_path.write_text(buf.getvalue())

    print(f"  → {out_path}  ({len(audit_export)} rows)")
    print()
    print("Per-axis flag counts:")
    for axis in ("Disease", "Target", "Product"):
        n = audit_export["UnclearFields"].str.contains(axis, na=False).sum()
        print(f"  {axis:8s} {n:4d}")
    print()
    print("Next: open docs/internal/CLASSIFICATION_AUDIT_PROMPT.md")
    print("and walk Q1-Q7 for each row. Strict no-downgrade gate at Step 3.")


if __name__ == "__main__":
    main()
