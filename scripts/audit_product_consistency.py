"""Audit: products with inconsistent TargetCategory across their trials.

Run from repo root:
    python3 scripts/audit_product_consistency.py [snapshot_date]

If `snapshot_date` is omitted, uses the most recent snapshot in
`snapshots/`. Emits one CSV to `audit_output/`:

  product_consistency_<date>.csv
      One row per (ProductName, TargetCategory) pair where the
      product has trials under MORE THAN ONE TargetCategory.
      Columns: ProductName, TargetCategory, Trials, ExampleNCTId,
      ExampleInterventions, ExampleTargetSource.

A well-formed snapshot should be empty — each named product (KYV-101,
CABA-201, …) maps to exactly one canonical antigen. Any non-empty
output flags one of:

  (a) A classifier bug — likely a text-pattern marker firing on
      comedication mentions (e.g. anti-CD20 mAB alongside a CD19
      CAR-T) and overriding the named-product mapping.
  (b) A genuinely new dual-target product whose NAMED_PRODUCT_TARGETS
      entry needs to be added or updated.
  (c) A mis-typed product alias matching unrelated trials (rare).

This audit is the consistency-check companion to the priority-order
reorder landed alongside it (named_product → explicit_marker → …).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "snapshots"
OUT_DIR = ROOT / "audit_output"


def _resolve_snapshot(arg: str | None) -> Path:
    if arg:
        path = SNAP_DIR / arg / "trials.csv"
        if not path.exists():
            sys.exit(f"snapshot not found: {path}")
        return path
    if not SNAP_DIR.exists():
        sys.exit(f"no snapshots/ directory at {SNAP_DIR}")
    dates = sorted(p.name for p in SNAP_DIR.iterdir() if (p / "trials.csv").exists())
    if not dates:
        sys.exit("no snapshots with trials.csv found")
    return SNAP_DIR / dates[-1] / "trials.csv"


def main(argv: list[str]) -> int:
    snap_csv = _resolve_snapshot(argv[1] if len(argv) > 1 else None)
    snap_date = snap_csv.parent.name
    df = pd.read_csv(snap_csv)
    if "ProductName" not in df.columns:
        sys.exit("no ProductName column — pipeline must populate it before audit")

    named = df.dropna(subset=["ProductName"]).copy()
    named["ProductName"] = named["ProductName"].astype(str).str.lower().str.strip()
    if named.empty:
        print(f"[{snap_date}] no named-product trials in snapshot — nothing to audit")
        return 0

    targets_per_product = (
        named.groupby("ProductName")["TargetCategory"].nunique()
    )
    inconsistent = targets_per_product[targets_per_product > 1].index.tolist()

    if not inconsistent:
        print(f"[{snap_date}] PASS — all {len(targets_per_product)} named "
              "products have a single TargetCategory across their trials.")
        return 0

    rows = []
    for prod in inconsistent:
        sub = named[named["ProductName"] == prod]
        for tc, g in sub.groupby("TargetCategory"):
            ex = g.iloc[0]
            rows.append({
                "ProductName": prod,
                "TargetCategory": tc,
                "Trials": len(g),
                "ExampleNCTId": ex.get("NCTId", ""),
                "ExampleInterventions": str(ex.get("Interventions", ""))[:300],
                "ExampleTargetSource": ex.get("TargetSource", ""),
            })

    out_df = pd.DataFrame(rows).sort_values(
        ["ProductName", "Trials"], ascending=[True, False],
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"product_consistency_{snap_date}.csv"
    out_df.to_csv(out_path, index=False)

    print(f"[{snap_date}] FAIL — {len(inconsistent)} product(s) have "
          "inconsistent TargetCategory:")
    for prod in inconsistent:
        cats = sorted(named.loc[named["ProductName"] == prod, "TargetCategory"].unique())
        print(f"  • {prod}: {' / '.join(cats)}")
    print(f"\nWrote {out_path.relative_to(ROOT)} ({len(rows)} rows)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
