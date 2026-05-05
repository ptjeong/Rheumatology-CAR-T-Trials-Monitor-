# Named-product audit — systematic identification of CAR-T constructs

Self-contained brief for a fresh Claude Code session in the rheum repo.
Goal: walk through every trial in the live snapshot, identify any
known named CAR-T product (by code, name, or sponsor identifier), and
propose additions / corrections to `pipeline.py:NAMED_PRODUCT_TARGETS`.
The audit must **improve and not worsen classification** — the
acceptance gate at the bottom guards against regressions.

---

--- BEGIN PROMPT ---

You are auditing the named-product classifier in
`pipeline.py:NAMED_PRODUCT_TARGETS`. This dict maps construct names
(e.g. "ide-cel", "JCAR017") and code identifiers (e.g. "LMY-920",
"GC012F") to a (TargetCategory, ProductName) tuple — used as a
fallback by `_assign_target` when the trial's title / brief summary
omits the antigen but does name a known product.

## Step 1 — Read the current map

```python
import pipeline as p
print(len(p.NAMED_PRODUCT_TARGETS), "products currently mapped")
for k, v in sorted(p.NAMED_PRODUCT_TARGETS.items()):
    print(f"  {k:30s}  →  {v}")
```

Memorise the format (key = lowercased construct identifier; value =
`(target_category, product_name)`). The product_name is the canonical
display label; the target_category must be one of the strings in
`_FLAG_AXIS_OPTIONS["TargetCategory"]` (CD19, BCMA, CD19/BCMA dual,
BAFF-R, CAR-Treg, CAAR-T, etc.).

## Step 2 — Load the snapshot and isolate trials NOT classified by
explicit-marker matching

The classifier returns a tuple `(target, source)` where source ∈
`{explicit_marker, named_product, car_core_fallback, no_match}`.
`named_product` and `car_core_fallback` are the two paths where a
better named-product map would help — `explicit_marker` trials
already have a confident label from their own text.

```python
import pandas as pd
import pipeline as p
df = pd.read_csv("snapshots/<latest_date>/trials.csv")
audit_rows = []
for _, r in df.iterrows():
    target, source = p._assign_target(r.to_dict())
    if source in ("named_product", "car_core_fallback", "no_match"):
        audit_rows.append({
            "NCTId": r["NCTId"],
            "BriefTitle": (r.get("BriefTitle") or "")[:140],
            "OfficialTitle": (r.get("OfficialTitle") or "")[:200],
            "Interventions": r.get("Interventions") or "",
            "Conditions": (r.get("Conditions") or "")[:120],
            "LeadSponsor": r.get("LeadSponsor") or "",
            "CurrentTarget": target,
            "Source": source,
        })
audit = pd.DataFrame(audit_rows)
print(f"{len(audit)} trials currently classified via "
      f"named_product / car_core_fallback / no_match — these are the "
      f"audit-relevant rows.")
```

## Step 3 — Walk through each row and answer three questions

For each row, ask:

  Q1. Does the title / interventions text name a CAR-T product
      (e.g. "JCAR017", "ide-cel", "GC012F", "LMY-920", "axi-cel")
      or sponsor-coded identifier (e.g. "BRL-301", "CC-97540",
      "FT819", "C-CAR168", "KYV-101")?

  Q2. Is that product / identifier already in `NAMED_PRODUCT_TARGETS`
      (case-insensitive, hyphen-stripped)?

  Q3. If yes-to-Q1-no-to-Q2: what TargetCategory does the construct
      target? Sources to consult, in order:
        a. Sponsor's pipeline page (companies usually publish the
           target receptor on the construct's product page).
        b. ClinicalTrials.gov detailed description (sometimes spells
           out the target even if BriefTitle doesn't).
        c. Recent publications mentioning the construct.
        d. Sponsor press releases.
      If you can't confidently determine the target from public
      sources, DO NOT add the product — leave it for human review.

  Q4. (Sanity) Could adding this product-target mapping cause a
      false-positive elsewhere in the dataset? Run:

      ```python
      candidate = "your-new-product-id-here"
      hits = df[df.apply(
          lambda r: candidate.lower() in (
              str(r.get("BriefTitle") or "") + " " +
              str(r.get("OfficialTitle") or "") + " " +
              str(r.get("Interventions") or "")
          ).lower(),
          axis=1
      )]
      print(hits[["NCTId", "BriefTitle", "TargetCategory"]])
      ```

      If the candidate string appears in trials currently classified
      with a DIFFERENT confident target (`explicit_marker` source),
      that's a red flag — either the candidate is too short / too
      generic, or you've found a misclassification. Investigate
      before adding.

## Step 4 — Compose proposed adds in a single Python block

```python
PROPOSED_ADDS = {
    # key (lowercase) : (TargetCategory, ProductName)
    "lmy-920":  ("BAFF-R",  "LMY-920"),
    "kyv-101":  ("CD19",    "KYV-101"),
    "gc012f":   ("CD19/BCMA dual", "GC012F"),
    # ... etc, one per audited trial
}
```

For each proposed add, attach a one-line justification: which trial
NCTId surfaced it, what source you used to determine the target.

## Step 5 — Apply, regenerate snapshot, run the regression gate

```python
# 1. Apply adds to NAMED_PRODUCT_TARGETS in pipeline.py (manual edit)

# 2. Re-classify the snapshot in place — same pattern used for the
#    BAFF-R fix in commit cb7e8f2.
import pandas as pd
import pipeline as p
trials_path = "snapshots/<latest_date>/trials.csv"
df = pd.read_csv(trials_path)
new_target = df.apply(lambda r: p._assign_target(r.to_dict())[0], axis=1)
new_source = df.apply(lambda r: p._assign_target(r.to_dict())[1], axis=1)
flips = df["TargetCategory"] != new_target
print(f"Total trials flipping: {flips.sum()}")
print(df[flips][["NCTId", "BriefTitle", "TargetCategory"]].assign(NewLabel=new_target[flips]))

# 3. Acceptance gate — STRICT: every flip must move from a less-
#    confident label to a more-confident one. Disallowed transitions:
#       CD19 → CAR-T_unspecified
#       CD19 → Other_or_unknown
#       BCMA → CAR-T_unspecified
#       any specific target → CAR-T_unspecified / Other_or_unknown
#    Allowed transitions:
#       CAR-T_unspecified → <any specific target>
#       Other_or_unknown   → <any specific target>
#       <specific> → <different specific> ONLY if you can cite the
#                     construct's true target receptor from a
#                     verifiable source (sponsor page, paper,
#                     drugbank), AND it's documented in the commit
#                     message.
DOWNGRADES = []
for _, row in df[flips].iterrows():
    old, new = row["TargetCategory"], new_target[row.name]
    if new in ("CAR-T_unspecified", "Other_or_unknown") and \
       old not in ("CAR-T_unspecified", "Other_or_unknown", ""):
        DOWNGRADES.append((row["NCTId"], old, new))
assert not DOWNGRADES, (
    f"REGRESSION — {len(DOWNGRADES)} trials downgraded to "
    f"unspecified/unknown: {DOWNGRADES[:5]}"
)
print("Acceptance gate passed — no regressions.")

# 4. Write back
df["TargetCategory"] = new_target
df["TargetSource"] = new_source
df.sort_values("NCTId", kind="stable").to_csv(trials_path, index=False)

# 5. Run the test suite
# bash$ python3 -m pytest tests/ -q
```

## Step 6 — Commit

```
fix(target-classifier): expand NAMED_PRODUCT_TARGETS — N new constructs

Audit-driven: walked through every trial with target source =
named_product / car_core_fallback / no_match. Identified N new
named CAR-T products / sponsor codes that the classifier was
missing.

Adds (per proposed-products dict at scripts/audit_named_products.py):

  - LMY-920   → BAFF-R   (already covered by BAFF-R branch but
                          double-listed here for explicit-product
                          fallback)
  - KYV-101   → CD19     (Kyverna's anti-CD19 CAR-T; ref: KYV-101 page)
  - ...

Acceptance gate (Python regression test inline in commit):
  - No trial downgraded from a specific target to CAR-T_unspecified
    or Other_or_unknown. Total flips = N (all upgrades).

Tests still passing (175/175).
```

## Notes / gotchas

- **Don't add bare-product-name keys that could false-match in
  unrelated trials.** Use the FULL identifier (e.g. "lmy-920", not
  just "920"). Run the Step-3 Q4 sanity check.
- **Sponsor identifiers are usually safe** (e.g., "BRL-301", "CC-
  97540") because they're alphanumeric tokens that don't appear in
  natural language.
- **Construct codes containing common words** are dangerous —
  "f01" might match "F01 in the Treatment of..." but also
  "F01.5" in an ICD-10 code. Test with the Q4 query.
- **Don't add anything you can't verify.** A wrong product →
  target mapping silently miscategorises every future trial of
  that construct. Better to leave a trial in `CAR-T_unspecified`
  than to put it under the wrong target.

--- END PROMPT ---
