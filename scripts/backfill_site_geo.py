"""Patch sites.csv in a snapshot with geoPoint.lat / lon for any rows
that lack them.

The core implementation now lives in `pipeline.backfill_site_geo` so the
runtime save-snapshot path (when called with `backfill_geo=True`) and
this retroactive CLI share one source of truth. Safe to re-run; existing
Latitude / Longitude values are preserved.

Usage:
    python scripts/backfill_site_geo.py snapshots/2026-04-25
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import backfill_site_geo  # noqa: E402


def _backfill(snapshot_dir: str) -> None:
    sites_path = os.path.join(snapshot_dir, "sites.csv")
    if not os.path.exists(sites_path):
        print(f"No sites.csv at {sites_path}", file=sys.stderr)
        sys.exit(1)

    before = pd.read_csv(sites_path)
    if before.empty:
        print("sites.csv is empty — nothing to backfill.")
        return

    for col in ("Latitude", "Longitude"):
        if col not in before.columns:
            before[col] = pd.NA

    needs = (before["Latitude"].isna() | before["Longitude"].isna()).sum()
    if needs == 0:
        print("All rows already have coordinates — nothing to do.")
        return

    print(f"Backfilling geo for {needs:,} rows...")
    after = backfill_site_geo(before)

    patched = (
        ((before["Latitude"].isna() | before["Longitude"].isna()))
        & after["Latitude"].notna() & after["Longitude"].notna()
    ).sum()
    after.to_csv(sites_path, index=False)
    print(f"Patched {patched:,} / {needs:,} rows. Wrote {sites_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", help="e.g. snapshots/2026-04-25")
    args = parser.parse_args()
    _backfill(args.snapshot_dir)


if __name__ == "__main__":
    main()
