"""Audit helper for named-product classifier coverage.

Run from repo root:
    python3 scripts/audit_named_products.py [snapshot_date]

If `snapshot_date` is omitted, uses the most recent snapshot in
`snapshots/`. Emits two CSVs to `audit_output/`:

  named_product_audit_<date>.csv
      Every trial whose TargetSource is named_product /
      car_core_fallback / no_match. Columns: NCTId, BriefTitle,
      OfficialTitle, Interventions, Conditions, LeadSponsor,
      CurrentTarget, Source. This is the worklist for the manual
      audit walkthrough described in
      docs/internal/NAMED_PRODUCT_AUDIT_PROMPT.md.

  named_product_existing_<date>.csv
      The current NAMED_PRODUCT_TARGETS dict as a flat CSV
      (Key, TargetCategory, ProductName). Useful for spotting
      duplicates / conflicting entries before adding new ones.

The audit itself (Q1–Q4 in the prompt) is human / LLM driven —
this script just produces the worklist + reference data so the
audit doesn't start from scratch.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

import pipeline as p


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


def main() -> None:
    snapshot = _resolve_snapshot(sys.argv[1] if len(sys.argv) > 1 else None)
    trials_path = REPO_ROOT / "snapshots" / snapshot / "trials.csv"
    out_dir = REPO_ROOT / "audit_output"
    out_dir.mkdir(exist_ok=True)

    df = pd.read_csv(trials_path)
    print(f"Loaded {len(df)} trials from snapshots/{snapshot}/trials.csv")

    # ── Worklist: trials whose target was set by named_product /
    # car_core_fallback / no_match — i.e., the explicit-marker path
    # didn't fire.
    audit_rows = []
    for _, r in df.iterrows():
        target, source = p._assign_target(r.to_dict())
        if source in ("named_product", "car_core_fallback", "no_match"):
            audit_rows.append({
                "NCTId": r["NCTId"],
                "BriefTitle": (r.get("BriefTitle") or "")[:200],
                "OfficialTitle": (r.get("OfficialTitle") or "")[:300],
                "Interventions": r.get("Interventions") or "",
                "Conditions": (r.get("Conditions") or "")[:200],
                "LeadSponsor": r.get("LeadSponsor") or "",
                "CurrentTarget": target,
                "Source": source,
            })
    audit = pd.DataFrame(audit_rows)
    audit_path = out_dir / f"named_product_audit_{snapshot}.csv"
    audit.to_csv(audit_path, index=False)
    print(f"  → {audit_path}  ({len(audit)} rows)")
    print(f"     Source breakdown: "
          f"{audit['Source'].value_counts().to_dict()}")

    # ── Reference: existing NAMED_PRODUCT_TARGETS dict
    refs = []
    for k, v in sorted(p.NAMED_PRODUCT_TARGETS.items()):
        if isinstance(v, tuple) and len(v) == 2:
            refs.append({"Key": k, "TargetCategory": v[0], "ProductName": v[1]})
        else:
            refs.append({"Key": k, "TargetCategory": str(v), "ProductName": ""})
    ref_df = pd.DataFrame(refs)
    ref_path = out_dir / f"named_product_existing_{snapshot}.csv"
    ref_df.to_csv(ref_path, index=False)
    print(f"  → {ref_path}  ({len(ref_df)} entries)")

    print()
    print("Next steps: open docs/internal/NAMED_PRODUCT_AUDIT_PROMPT.md")
    print("and walk through Q1–Q4 for each row in the audit CSV.")


if __name__ == "__main__":
    main()
