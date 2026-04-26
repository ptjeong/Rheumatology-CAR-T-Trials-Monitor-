"""Generate the locked random sample for the inter-rater κ validation study.

This is a ONE-SHOT script. The output (`validation_study/sample_<v>.json`) is
committed to the repository before any rater starts work, with a sha256
hash recorded in the commit message — the pre-registration anchor for
the validation study.

Re-running this script with the same seed + snapshot produces the
identical sample (deterministic). If a future revision of the study
needs a different sample, increment the `--version` arg → output goes to
`sample_v2.json` etc., never overwriting v1.

Stratification (locked design for rheum v1):
    Stratified by DiseaseEntity. Rheum is single-branch, so the
    Heme/Solid split that the onc study uses doesn't apply; instead we
    enforce a floor of ≥3 trials per DiseaseEntity that has ≥5 trials in
    the source snapshot. Trials with insufficient text (no
    BriefSummary, no Conditions, no Interventions ≥50 chars) are
    filtered out before sampling.

Sample size (N=100) justification: rheum's snapshot is ~284 trials; an
N=100 stratified sample is ~35% coverage and powers detection of κ ≥ 0.4
vs null κ=0.0 at α=0.05, β=0.2 even for the wider axes (e.g. 13-label
DiseaseEntity), with ~10% margin for items raters mark "Unsure" or skip.

Usage:
    python scripts/generate_validation_sample.py \\
        --snapshot 2026-04-25 --n 100 --seed 20260426 --version v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Make the repo importable regardless of where this script is invoked
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from pipeline import load_snapshot  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "validation_study"


def _stratified_sample(
    df: pd.DataFrame,
    n_total: int,
    seed: int,
) -> pd.DataFrame:
    """Stratified sample: floor per major DiseaseEntity + uniform top-up.

    Algorithm (rheum v1):
      1. Filter out trials with insufficient text (no rater can score them).
      2. Identify "major" DiseaseEntities (≥5 trials in source).
      3. For each major entity, take min(3, len(pool)) trials (floor).
      4. Top up to n_total with random draws from the remaining pool.
      5. Shuffle final order so raters don't see all SLE then all SSc.
    """
    rng = random.Random(seed)

    # ---- 1. Minimum-evidence filter ----
    def _has_evidence(row) -> bool:
        bits = [str(row.get(c, "") or "") for c in
                ["BriefSummary", "Conditions", "Interventions"]]
        return any(len(b.strip()) >= 50 for b in bits)
    df = df[df.apply(_has_evidence, axis=1)].copy()

    # ---- 2. Major entities ----
    entity_counts = df["DiseaseEntity"].value_counts()
    major_entities = entity_counts[entity_counts >= 5].index.tolist()

    selected: set[str] = set()

    # ---- 3. Floor per major entity ----
    for ent in major_entities:
        ent_pool = df[df["DiseaseEntity"] == ent]["NCTId"].tolist()
        k = min(3, len(ent_pool))
        picks = rng.sample(ent_pool, k)
        selected.update(picks)

    # ---- 4. Top up to n_total ----
    remaining_pool = [n for n in df["NCTId"].tolist() if n not in selected]
    slots_left = n_total - len(selected)
    if slots_left > 0:
        top_up = rng.sample(remaining_pool, min(slots_left, len(remaining_pool)))
        selected.update(top_up)
    elif len(selected) > n_total:
        # If the floor exceeds the requested N, take the requested N
        selected = set(rng.sample(list(selected), n_total))

    selected_list = list(selected)
    rng.shuffle(selected_list)
    return df[df["NCTId"].isin(selected_list)].copy().set_index("NCTId").loc[selected_list].reset_index()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--snapshot", required=True,
                   help="Snapshot date (e.g. 2026-04-24).")
    p.add_argument("--n", type=int, default=100,
                   help="Total sample size. Default 100 (rheum has ~284 trials; "
                        "100 is ~35%% coverage and powers κ ≥ 0.4 detection).")
    p.add_argument("--seed", type=int, default=20260426,
                   help="Random seed for reproducibility. Default 20260426.")
    p.add_argument("--version", default="v1",
                   help="Output suffix: validation_study/sample_<version>.json")
    args = p.parse_args()

    print(f"Loading snapshot {args.snapshot} …")
    df, _df_sites, _meta = load_snapshot(args.snapshot)
    print(f"  {len(df):,} trials in snapshot.")

    print(f"Sampling N={args.n} stratified (seed={args.seed}) …")
    sample_df = _stratified_sample(df, args.n, args.seed)
    print(f"  drew {len(sample_df)} trials.")

    # Build the manifest with the minimum trial info raters need
    # — no pipeline labels (those are deliberately hidden during rating)
    fields_for_raters = [
        "NCTId", "BriefTitle", "BriefSummary",
        "Conditions", "Interventions",
        "Phase", "OverallStatus", "LeadSponsor",
        "EnrollmentCount", "StartDate", "TrialDesign",
    ]
    manifest_trials = []
    for _, row in sample_df.iterrows():
        rec = {}
        for f in fields_for_raters:
            v = row.get(f)
            if pd.isna(v):
                rec[f] = None
            elif isinstance(v, (pd.Timestamp,)):
                rec[f] = v.isoformat()
            else:
                rec[f] = str(v) if not isinstance(v, (int, float, bool)) else v
        # Pipeline labels — kept in the manifest under a `_pipeline` key
        # so the analysis script can compute κ vs pipeline as a secondary
        # statistic. The rater UI MUST NOT display these.
        rec["_pipeline"] = {
            ax: (None if pd.isna(row.get(ax)) else str(row.get(ax)))
            for ax in ["DiseaseEntity", "TargetCategory", "ProductType",
                       "TrialDesign", "SponsorType"]
        }
        manifest_trials.append(rec)

    # Stratification summary (audit trail)
    strat_summary = (
        sample_df.groupby(["DiseaseEntity"])
        .size().reset_index(name="n").to_dict("records")
    )

    # Provenance: pin the exact pipeline state at sample-generation time
    # so the analysis can claim "we compared against pipeline @ <sha>"
    # in the manuscript's methods section. Without this, a pipeline
    # change mid-study could silently shift the secondary-outcome
    # (rater-vs-pipeline) numbers and require re-running everything.
    import subprocess as _sp
    try:
        pipeline_sha = _sp.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT), text=True, stderr=_sp.DEVNULL,
        ).strip()
    except Exception:
        pipeline_sha = "unknown"
    try:
        pipeline_dirty = bool(_sp.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT), text=True, stderr=_sp.DEVNULL,
        ).strip())
    except Exception:
        pipeline_dirty = False

    # Autocomplete vocabularies — surface the canonical entity + target
    # lists in the manifest so the rater UI can offer them as quick-pick
    # suggestions. Cuts typing time and standardizes spelling so κ doesn't
    # get artificially deflated by "Lupus" vs "SLE".
    try:
        from config import DISEASE_ENTITIES
        autocomplete_vocab = {
            "DiseaseEntity": (
                sorted(DISEASE_ENTITIES.keys())
                + ["Other immune-mediated", "Basket/Multidisease", "Unclassified"]
            ),
            # TargetCategory closed vocab matches scripts/validate_independent_llm.py
            # (Phase 1 enum-lock).
            "TargetCategory": [
                "CD19", "CD20", "CD7", "CD70", "BCMA", "BAFF", "CD6",
                "CD19/BCMA dual", "CD19/CD20 dual", "CD19/BAFF dual",
                "BCMA/CD70 dual",
                "CAR-Treg", "CAAR-T",
                "CAR-T_unspecified", "Other_or_unknown",
            ],
            "ProductType": ["Autologous", "Allogeneic/Off-the-shelf",
                            "In vivo", "Unclear"],
            "TrialDesign": ["Single disease", "Basket/Multidisease"],
            "SponsorType": ["Industry", "Academic", "Government", "Other"],
        }
    except Exception:
        autocomplete_vocab = {"DiseaseEntity": [], "TargetCategory": []}

    manifest = {
        "version": args.version,
        "n": len(manifest_trials),
        "n_requested": args.n,
        "snapshot_date": args.snapshot,
        "seed": args.seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_sha": pipeline_sha,
        "pipeline_dirty_worktree": pipeline_dirty,
        "stratification": "Stratified by DiseaseEntity. ≥3 trials per "
                          "DiseaseEntity that has ≥5 in the source snapshot. "
                          "Trials with insufficient text (no Title/Summary/"
                          "Conditions/Interventions ≥50 chars) excluded.",
        "stratification_breakdown": strat_summary,
        "axes_to_rate": [
            "DiseaseEntity", "TargetCategory", "ProductType",
            "TrialDesign", "SponsorType",
        ],
        "autocomplete_vocab": autocomplete_vocab,
        "trials": manifest_trials,
    }

    # Compute hash of the canonical (sorted-keys) JSON for pre-registration
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest["sha256"] = sha

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"sample_{args.version}.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print()
    print(f"✓ Wrote {out_path}")
    print(f"  N = {manifest['n']}")
    print(f"  sha256 = {sha}")
    print()
    print("Stratification breakdown:")
    for row in strat_summary:
        print(f"  {row['DiseaseEntity']:30s}  N={row['n']}")
    print()
    print("→ Commit this file with the sha256 in the commit message; "
          "this is the pre-registration anchor for the κ study.")
    print(f"→ Then deploy validation_study/app.py and share the rater "
          f"URLs with PJ + the clinical collaborator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
