"""One-off backfill script: patches sites.csv in a snapshot with geoPoint.

Hits ClinicalTrials.gov v2 /studies endpoint with filter.ids=NCT1,NCT2,... in
batches of 100, extracts each location's geoPoint.lat/lon, and merges those
columns into the snapshot's sites.csv in place.

Usage:
    python scripts/backfill_site_geo.py snapshots/2026-04-24

Safe to re-run: existing Latitude / Longitude values are preserved; only
blanks are filled.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
import requests

CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"
BATCH_SIZE = 100
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_BATCHES = 0.25  # polite rate limit


def _fetch_geopoints(nct_ids: list[str]) -> dict[tuple[str, str, str, str], tuple[float, float]]:
    """Return {(NCTId, Facility, City, Country): (lat, lon)} for every site in a batch."""
    params = {
        "filter.ids": ",".join(nct_ids),
        "fields": "NCTId,ContactsLocationsModule",
        "pageSize": BATCH_SIZE,
        "format": "json",
    }
    resp = requests.get(CTGOV_API, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    out: dict[tuple[str, str, str, str], tuple[float, float]] = {}
    for study in data.get("studies", []):
        ps = study.get("protocolSection", {}) or {}
        ident = ps.get("identificationModule", {}) or {}
        nct = ident.get("nctId") or ""
        loc_mod = ps.get("contactsLocationsModule", {}) or {}
        for loc in (loc_mod.get("locations") or []):
            gp = loc.get("geoPoint") or {}
            lat, lon = gp.get("lat"), gp.get("lon")
            if lat is None or lon is None:
                continue
            key = (
                str(nct),
                str(loc.get("facility") or ""),
                str(loc.get("city") or ""),
                str(loc.get("country") or ""),
            )
            out[key] = (float(lat), float(lon))
    return out


def backfill(snapshot_dir: str) -> None:
    sites_path = os.path.join(snapshot_dir, "sites.csv")
    if not os.path.exists(sites_path):
        print(f"No sites.csv at {sites_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(sites_path)
    if df.empty:
        print("sites.csv is empty — nothing to backfill.")
        return

    for col in ("Latitude", "Longitude"):
        if col not in df.columns:
            df[col] = pd.NA

    # Only refetch rows that are missing coords
    needs_geo = df["Latitude"].isna() | df["Longitude"].isna()
    targets = df[needs_geo]
    if targets.empty:
        print("All rows already have coordinates — nothing to do.")
        return

    nct_ids = sorted(targets["NCTId"].dropna().unique().tolist())
    print(f"Backfilling geo for {len(targets):,} rows across {len(nct_ids):,} trials...")

    lookup: dict[tuple[str, str, str, str], tuple[float, float]] = {}
    for i in range(0, len(nct_ids), BATCH_SIZE):
        batch = nct_ids[i : i + BATCH_SIZE]
        try:
            got = _fetch_geopoints(batch)
        except requests.RequestException as e:
            print(f"  batch {i // BATCH_SIZE + 1} failed: {e}", file=sys.stderr)
            got = {}
        lookup.update(got)
        print(f"  batch {i // BATCH_SIZE + 1}/{(len(nct_ids) + BATCH_SIZE - 1) // BATCH_SIZE}: "
              f"+{len(got)} geopoints (cumulative {len(lookup):,})")
        time.sleep(SLEEP_BETWEEN_BATCHES)

    # Merge back row-by-row
    patched = 0
    for idx, row in df[needs_geo].iterrows():
        key = (
            str(row.get("NCTId") or ""),
            str(row.get("Facility") or ""),
            str(row.get("City") or ""),
            str(row.get("Country") or ""),
        )
        if key in lookup:
            lat, lon = lookup[key]
            df.at[idx, "Latitude"] = lat
            df.at[idx, "Longitude"] = lon
            patched += 1

    df.to_csv(sites_path, index=False)
    print(f"Patched {patched:,} / {len(targets):,} rows. Wrote {sites_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", help="e.g. snapshots/2026-04-24")
    args = parser.parse_args()
    backfill(args.snapshot_dir)


if __name__ == "__main__":
    main()
