"""Build a fresh snapshot from the live ClinicalTrials.gov API.

Used by the daily-snapshot GitHub Action and by anyone wanting to
rebuild the snapshot locally without going through the Streamlit UI.

Usage:
    python scripts/build_snapshot.py [--max-records N] [--out snapshots/]

The output is written to `snapshots/<YYYY-MM-DD>/` (where the date is
today UTC). Files: trials.csv, sites.csv, prisma.json, metadata.json.

Exit codes:
    0  — snapshot built and saved
    1  — API fetch failed (rate limit, network error, etc.)
    2  — classification produced an empty dataset (sanity check)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pipeline as p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-records", type=int, default=2000,
        help="Cap on trials to fetch (default: 2000; covers the full active "
             "autoimmune-CAR-T pipeline with margin).",
    )
    ap.add_argument(
        "--out", type=str, default="snapshots",
        help="Snapshot output directory (default: snapshots/).",
    )
    ap.add_argument(
        "--statuses", nargs="*",
        default=None,
        help="Override the status filter list (default: pipeline.py's defaults).",
    )
    args = ap.parse_args()

    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"fetching live ClinicalTrials.gov API…", flush=True)
    try:
        df, df_sites, prisma = p.build_all_from_api(
            max_records=args.max_records, statuses=args.statuses,
        )
    except Exception as e:
        print(f"ERROR: live fetch failed: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1

    if df.empty:
        print("ERROR: classifier produced an empty dataset; aborting save.",
              file=sys.stderr)
        return 2

    print(f"  → {len(df):,} trials, {len(df_sites):,} site records, "
          f"PRISMA n_included={prisma.get('n_included', '?')}", flush=True)

    snap_date = p.save_snapshot(
        df, df_sites, prisma,
        snapshot_dir=args.out,
        backfill_geo=False,   # CI run; geo backfill needs network calls
                              # per-batch and would slow CI substantially.
                              # Manual rebuilds (UI button) opt in via True.
    )
    print(f"  → saved to {args.out}/{snap_date}/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
