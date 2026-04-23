#!/usr/bin/env python3
"""
LLM validation loop for CAR-T trial classifications.

Fetches live trial data, identifies borderline classifications, and sends each
to Claude for a structured second opinion.  Outputs a human-readable change
summary and copy-pasteable config patches.

Usage:
    python validate.py                        # review borderline cases (default ≤30)
    python validate.py --nct NCT06123456      # review a single trial
    python validate.py --all --limit 100      # review up to 100 trials
    python validate.py --output results.json  # custom output path

Requires:
    ANTHROPIC_API_KEY environment variable
    pip install anthropic  (already in requirements.txt)
"""

import json
import os
import sys
import textwrap
import argparse

import anthropic
import pandas as pd

# Allow running from repo root without install
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import build_clean_dataframe  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

VALID_DISEASES = [
    "SLE", "SSc", "Sjogren", "CTD_other",
    "IIM", "AAV", "RA", "IgG4-RD", "Behcet",
    "T1D", "cGVHD", "HLH", "HS", "CPPD", "Neurologic_autoimmune",
    "Basket/Multidisease", "Autoimmune_other", "Other immune-mediated",
    "Unclassified", "Exclude",
]
VALID_TARGETS = [
    "CD19", "BCMA", "CD20", "CD70", "CD6", "CD7",
    "CD19/BCMA dual", "BCMA/CD70 dual", "CD19/CD20 dual", "CD19/BAFF dual",
    "CAR-NK", "CAAR-T", "CAR-Treg",
    "CAR-T_unspecified", "Other_or_unknown",
]
VALID_PRODUCT_TYPES = ["Autologous", "Allogeneic/Off-the-shelf", "In vivo", "Unclear"]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM = textwrap.dedent("""
    You are an expert in CAR-T and related cell therapy clinical trials for
    autoimmune and immune-mediated diseases.

    Your task: validate automated classifications for a clinical trial and
    return a corrected classification as a JSON object — no prose, no markdown
    fences, no extra keys.

    Schema (return exactly this):
    {{
        "nct_id":        "NCTXXXXXXXX",
        "disease_entity": "<see list>",
        "target_category": "<see list>",
        "product_type":  "<see list>",
        "exclude":       false,
        "exclude_reason": null,
        "confidence":    "high|medium|low",
        "notes":         "<one sentence rationale>"
    }}

    Valid disease_entity values:
      {diseases}

    Valid target_category values:
      {targets}

    Valid product_type values:
      {product_types}

    Key rules:
    - "Exclude" → remove entirely (oncology, non-CAR-T, purely observational)
    - "Basket/Multidisease" → ≥2 distinct systemic autoimmune diseases enrolled
    - "Autoimmune_other" → confirmed autoimmune but disease not in specific list
    - "Other immune-mediated" → non-rheumatologic immune disease (MS, MG, T1D …)
    - "Unclassified" → genuinely cannot determine from available text
    - "CAR-T_unspecified" → confirmed CAR-T but target antigen unclear
    - confidence "high" = certain from trial text; "low" = best guess only
""")

_USER = textwrap.dedent("""
    Classify this clinical trial.

    NCT ID:       {nct_id}
    Title:        {title}
    Conditions:   {conditions}
    Interventions:{interventions}

    Brief summary:
    {summary}

    Current automated classifications (may be incorrect):
      DiseaseEntity:  {disease}
      TargetCategory: {target}
      ProductType:    {product_type}

    Return corrected JSON only.
""")

# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def _make_system() -> str:
    return _SYSTEM.format(
        diseases=", ".join(VALID_DISEASES),
        targets=", ".join(VALID_TARGETS),
        product_types=", ".join(VALID_PRODUCT_TYPES),
    )


def validate_trial(client: anthropic.Anthropic, row: dict) -> dict | None:
    prompt = _USER.format(
        nct_id=row.get("NCTId", ""),
        title=row.get("BriefTitle", ""),
        conditions=(row.get("Conditions") or "")[:400],
        interventions=(row.get("Interventions") or "")[:400],
        summary=(row.get("BriefSummary") or "")[:900],
        disease=row.get("DiseaseEntity", ""),
        target=row.get("TargetCategory", ""),
        product_type=row.get("ProductType", ""),
    )
    try:
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=512,
            system=_make_system(),
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Strip accidental markdown fences
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parse error for {row.get('NCTId')}: {e}")
        return None
    except Exception as e:
        print(f"  ✗ API error for {row.get('NCTId')}: {e}")
        return None


# ---------------------------------------------------------------------------
# Patch generation helpers
# ---------------------------------------------------------------------------

def _config_patch_lines(results: list[dict]) -> list[str]:
    """Return copy-pasteable HARD_EXCLUDED_NCT_IDS additions."""
    lines = []
    for r in results:
        if r.get("exclude") and r.get("confidence") == "high":
            reason = (r.get("exclude_reason") or r.get("notes") or "").replace("\n", " ")
            lines.append(f'    "{r["nct_id"]}",  # {reason}')
    return lines


def _named_product_hints(results: list[dict], df: pd.DataFrame) -> list[str]:
    """Return hints for NAMED_PRODUCT_TARGETS based on high-confidence target corrections."""
    hints = []
    for r in results:
        if r.get("confidence") != "high":
            continue
        orig = next((row for _, row in df.iterrows() if row["NCTId"] == r["nct_id"]), None)
        if orig is None:
            continue
        orig_target = orig.get("TargetCategory", "")
        new_target = r.get("target_category", "")
        if orig_target in ("CAR-T_unspecified", "Other_or_unknown") and new_target not in (orig_target, ""):
            ivx = (orig.get("Interventions") or "").lower().split("|")
            for name in ivx:
                name = name.strip()
                if name and len(name) > 3:
                    hints.append(f'    # {r["nct_id"]}: add "{name}" → {new_target} in NAMED_PRODUCT_TARGETS')
    return hints


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM validation loop for CAR-T trial classifications"
    )
    parser.add_argument("--nct", help="Validate a specific NCT ID only")
    parser.add_argument("--all", action="store_true", help="Validate all trials (ignores --limit for filtering)")
    parser.add_argument("--limit", type=int, default=30, help="Max borderline trials to validate (default 30)")
    parser.add_argument("--output", default="llm_overrides.json", help="JSON output path (merged with existing)")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("Fetching trial data from ClinicalTrials.gov …")
    df = build_clean_dataframe(max_records=1000)
    print(f"  {len(df)} trials loaded\n")

    # ---- Select subset to validate ----------------------------------------
    if args.nct:
        subset = df[df["NCTId"] == args.nct]
        if subset.empty:
            print(f"Trial {args.nct} not found in current dataset.")
            sys.exit(1)
    elif args.all:
        subset = df.head(args.limit)
    else:
        borderline = (
            df["DiseaseEntity"].isin(["Unclassified", "Autoimmune_other"])
            | df["TargetCategory"].isin(["CAR-T_unspecified", "Other_or_unknown"])
            | df["ProductType"].eq("Unclear")
        )
        subset = df[borderline].head(args.limit)
        print(f"  {len(subset)} borderline trials selected for validation\n")

    # ---- Validate ---------------------------------------------------------
    results: list[dict] = []
    changes: list[dict] = []

    for i, (_, row) in enumerate(subset.iterrows(), 1):
        nct = row["NCTId"]
        title = (row.get("BriefTitle") or "")[:70]
        print(f"[{i:>3}/{len(subset)}] {nct}  {title}")

        result = validate_trial(client, row.to_dict())
        if result is None:
            continue

        # Attach originals for diff reporting
        result["_orig_disease"]  = row.get("DiseaseEntity")
        result["_orig_target"]   = row.get("TargetCategory")
        result["_orig_product"]  = row.get("ProductType")
        results.append(result)

        diffs = []
        if result.get("disease_entity")  != row.get("DiseaseEntity"):
            diffs.append(f"disease:  {row['DiseaseEntity']} → {result['disease_entity']}")
        if result.get("target_category") != row.get("TargetCategory"):
            diffs.append(f"target:   {row['TargetCategory']} → {result['target_category']}")
        if result.get("product_type")    != row.get("ProductType"):
            diffs.append(f"type:     {row['ProductType']} → {result['product_type']}")
        if result.get("exclude"):
            diffs.append(f"EXCLUDE   {result.get('exclude_reason') or ''}")

        conf = result.get("confidence", "?")
        if diffs:
            changes.append({"nct_id": nct, "title": title, "diffs": diffs,
                            "confidence": conf, "notes": result.get("notes", "")})
            for d in diffs:
                print(f"       ✎  {d}  [{conf}]")
        else:
            print(f"       ✓  confirmed  [{conf}]")

    # ---- Merge with existing overrides file (preserve prior validations) ----
    existing: dict[str, dict] = {}
    if os.path.exists(args.output):
        with open(args.output) as f:
            for e in json.load(f):
                existing[e["nct_id"]] = e
    n_before = len(existing)
    for r in results:
        existing[r["nct_id"]] = r
    with open(args.output, "w") as f:
        json.dump(list(existing.values()), f, indent=2)
    n_new = len(existing) - n_before
    print(f"\nOverrides → {args.output}  ({len(existing)} total, {n_new} new)")

    if not changes:
        print("\nAll classifications look correct — no changes suggested.")
        return

    # ---- Change summary --------------------------------------------------
    W = 70
    print(f"\n{'═' * W}")
    print(f"  SUGGESTED CHANGES  ({len(changes)} of {len(results)} trials reviewed)")
    print(f"{'═' * W}")
    for c in changes:
        print(f"\n  {c['nct_id']}  {c['title']}")
        for d in c["diffs"]:
            print(f"    • {d}")
        print(f"    Confidence: {c['confidence']}")
        if c["notes"]:
            print(f"    {c['notes']}")

    # ---- Hard-exclusion patch --------------------------------------------
    excl_lines = _config_patch_lines(results)
    if excl_lines:
        print(f"\n{'─' * W}")
        print("  ADD TO HARD_EXCLUDED_NCT_IDS in config.py:")
        print(f"{'─' * W}")
        for ln in excl_lines:
            print(ln)

    # ---- Named product hints --------------------------------------------
    prod_hints = _named_product_hints(results, df)
    if prod_hints:
        print(f"\n{'─' * W}")
        print("  NAMED PRODUCT HINTS (review and add to NAMED_PRODUCT_TARGETS in config.py):")
        print(f"{'─' * W}")
        for h in prod_hints:
            print(h)

    print(f"\n{'═' * W}\n")


if __name__ == "__main__":
    main()
