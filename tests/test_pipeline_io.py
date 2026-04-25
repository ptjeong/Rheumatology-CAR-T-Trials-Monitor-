"""Pipeline I/O determinism tests.

Run with:  python -m pytest tests/test_pipeline_io.py -v

Verifies that save_snapshot produces byte-identical CSV / JSON outputs
across runs that differ only in input row order. Reviewers replicating
the dashboard should be able to checksum a snapshot rebuild and match
the published artifact bit-for-bit (except for the per-run wall-clock
in runinfo.json, which is deliberately segregated).
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import save_snapshot, load_snapshot, list_snapshots  # noqa: E402


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _save_and_hash(df, sites, prisma, outdir: str) -> dict[str, str]:
    save_snapshot(df, sites, prisma, snapshot_dir=outdir)
    date = sorted(os.listdir(outdir))[0]
    run_dir = os.path.join(outdir, date)
    return {f: _sha(os.path.join(run_dir, f)) for f in sorted(os.listdir(run_dir))}


@pytest.fixture(scope="module")
def latest_snapshot():
    snaps = list_snapshots()
    if not snaps:
        pytest.skip("no snapshots available to use as input")
    return load_snapshot(snaps[0])


def test_save_is_deterministic_under_row_shuffle(latest_snapshot):
    """Sorting + sort_keys=True on JSON means trials.csv / sites.csv /
    prisma.json / metadata.json are byte-identical regardless of input
    row order. runinfo.json is the only file that carries the wall-clock
    and is therefore exempt from the byte-identity contract.
    """
    df, sites, prisma = latest_snapshot
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        h1 = _save_and_hash(df.copy(), sites.copy(), dict(prisma), t1)
        h2 = _save_and_hash(
            df.sample(frac=1, random_state=99).copy(),
            sites.sample(frac=1, random_state=99).copy(),
            dict(prisma),
            t2,
        )

    deterministic = ["trials.csv", "sites.csv", "prisma.json", "metadata.json"]
    mismatches = [f for f in deterministic if h1.get(f) != h2.get(f)]
    assert not mismatches, (
        f"save_snapshot is not byte-deterministic for: {mismatches}\n"
        f"first run: {h1}\nshuffled:  {h2}"
    )
    # runinfo.json SHOULD differ — that's the point of segregating it.
    assert h1.get("runinfo.json") != h2.get("runinfo.json"), (
        "runinfo.json was identical across runs — the wall-clock is supposed "
        "to be captured here, so this is a regression."
    )
