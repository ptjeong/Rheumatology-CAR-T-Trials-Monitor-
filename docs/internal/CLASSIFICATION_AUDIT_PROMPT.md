# Classification audit — systematic improvement across all axes

Self-contained brief for a fresh Claude Code session in the rheum repo.
Goal: walk through every trial whose classification is non-confident
(low-confidence OR sentinel-labelled on any axis) and propose
improvements via the right tool — config term lists, pipeline-logic
updates, or per-NCT LLM overrides — with a strict acceptance gate
that **only allows upgrades, never downgrades**.

Companion prompt: `NAMED_PRODUCT_AUDIT_PROMPT.md` (narrower —
TargetCategory via product-name lookup only). Use this prompt for
the full multi-axis audit.

---

--- BEGIN PROMPT ---

You are auditing the rheum-dashboard classifier. The pipeline emits
six classification fields per trial; each can be confident, generic,
or sentinel:

  Field                Confident                Generic / Sentinel
  ─────────────────────────────────────────────────────────────────
  DiseaseEntities      SLE / SSc / Sjogren /    "Other immune-mediated"
                       IIM / RA / AAV / Behcet/  "Unclassified"
                       IgG4-RD / cGVHD /         "Basket/Multidisease"
                       (OIM clusters: MS,
                       NMOSD, CIDP, MOGAD, AIE,
                       Myasthenia, Stiff_person)
  TrialDesign          "Single disease" /
                       "Basket/Multidisease"     —
  TargetCategory       CD19 / BCMA / CD20 /      "CAR-T_unspecified"
                       CD7 / CD70 / CD6 /        "Other_or_unknown"
                       BAFF-R / CAR-Treg /
                       CAAR-T / X/Y dual
  ProductType          Autologous / Allogeneic / "Unclear"
                       In vivo
  ProductName          (free text)               (NaN — most trials)
  SponsorType          Industry / Academic /     "Other"
                       Government

The audit identifies trials where a confident classification is
plausible but the pipeline emitted a sentinel/generic label, then
proposes the cheapest upgrade that won't downgrade any other trial.

## Step 1 — Generate the audit worklist

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, '.')
import pandas as pd
import pipeline as p

# Use the most recent snapshot (or whichever CSV the user supplies).
df = pd.read_csv('snapshots/<latest_date>/trials.csv')

# Audit-relevant: any trial with a sentinel label on any axis OR
# low/medium confidence overall.
mask_disease = df['DiseaseEntities'].fillna('').str.contains(
    'Other immune-mediated|Unclassified', regex=True)
mask_target  = df['TargetCategory'].isin(['CAR-T_unspecified', 'Other_or_unknown'])
mask_product = df['ProductType'] == 'Unclear'
mask_conf    = df['ClassificationConfidence'].isin(['low', 'medium'])

audit = df[mask_disease | mask_target | mask_product | mask_conf].copy()
audit = audit[[
    'NCTId', 'BriefTitle', 'DiseaseEntities', 'TrialDesign',
    'TargetCategory', 'ProductType', 'ProductName',
    'ClassificationConfidence', 'LeadSponsor',
]]
audit.to_csv('audit_output/classification_audit.csv', index=False)
print(f'{len(audit)} trials in worklist (of {len(df)} total)')
print('Source-axis breakdown:')
print(f'  sentinel disease entity:   {mask_disease.sum()}')
print(f'  sentinel target:           {mask_target.sum()}')
print(f'  sentinel product type:     {mask_product.sum()}')
print(f'  low/medium confidence:     {mask_conf.sum()}')
PY
```

On the 2026-05-05 snapshot this yields ~75 audit-relevant trials
(some trials have multiple sentinel axes; counted once).

## Step 2 — Walk each trial, decide the right correction tool

For each row, ask the questions IN ORDER. Stop at the first that fits.

### Q1. Is the trial irrelevant to autoimmune CAR-T?

A small fraction of the audit list is mis-included (e.g., oncology
trials that mention "autoimmune" once in eligibility text). If the
trial is genuinely off-scope, add to:

```python
# config.py
HARD_EXCLUDED_NCT_IDS = {
    ...,
    "NCT0XXXXXXX",   # one-line reason
}
```

OR add to `llm_overrides.json` with `exclude: true` and a confidence
+ rationale field. The pipeline reloads on the next snapshot rebuild.

### Q2. Does the trial title / interventions text name a known
       CAR-T product (sponsor code, drug name, or research code)?

Examples: "JCAR017", "ide-cel", "GC012F", "LMY-920", "BRL-301",
"KYV-101", "C-CAR168", "FT819", "CC-97540", "axi-cel".

Look up the product's binding target in:
  - the sponsor's pipeline page,
  - ClinicalTrials.gov detailed description,
  - recent publications,
  - drugbank / chembl.

If found AND the target is unambiguous, add to:

```python
# pipeline.py
NAMED_PRODUCT_TARGETS = {
    ...,
    "lmy-920":   ("BAFF-R", "LMY-920"),    # lowercase key, (target, display_name)
    "kyv-101":   ("CD19",   "KYV-101"),
}
```

Run the Q4 sanity-check before committing:

```python
candidate = "your-new-product-id"
hits = df[df.apply(
    lambda r: candidate.lower() in (
        str(r.get('BriefTitle') or '') + ' ' +
        str(r.get('OfficialTitle') or '') + ' ' +
        str(r.get('Interventions') or '')
    ).lower(),
    axis=1
)]
print(hits[['NCTId', 'BriefTitle', 'TargetCategory']])
```

If the candidate string also appears in trials currently classified
with a DIFFERENT confident target via `explicit_marker` source, the
candidate is too generic — refuse the add.

### Q3. Does the title / conditions text name a specific antigen
       outside the current classifier vocabulary?

Examples that have appeared on the worklist before: BAFF-R (now
covered), GPRC5D, FcRn, CD22 (rheum-rare), NKG2D-L. Add to:

```python
# config.py — CAR_SPECIFIC_TARGET_TERMS
"GPRC5D": ["gprc5d", "anti-gprc5d", "gprc5d targeted"],
```

```python
# pipeline.py — _assign_target()
has_gprc5d = _contains_any(text, CAR_SPECIFIC_TARGET_TERMS["GPRC5D"])
...
if has_gprc5d:
    return "GPRC5D", "explicit_marker"
```

Place the new branch in priority order — combinations BEFORE singles
(e.g., a CD19/GPRC5D dual catch must come before CD19 and GPRC5D).

### Q4. Does the trial enrol a specific rheum / OIM disease that
       isn't in the current `_DISEASE_TERMS` map?

Examples: psoriatic arthritis, ankylosing spondylitis, juvenile
idiopathic arthritis, autoimmune hepatitis. Add to:

```python
# pipeline.py — _DISEASE_TERMS
"PsA": ["psoriatic arthritis"],
"AS":  ["ankylosing spondylitis", "axial spondyloarthritis"],
```

For a new entity, also add it to the appropriate family in
`app.py:_DISEASE_FAMILY_MAP` so the sunburst / family rollups
find it:

```python
"PsA": "Inflammatory arthritis",
"AS":  "Inflammatory arthritis",
```

Add to `ENTITY_COLORS` so the new entity gets a deterministic
colour across all charts (pick a shade in the appropriate family's
palette band — see app.py:ENTITY_COLORS comment block).

### Q5. Does the trial enrol multiple OIM diseases without a strict
       rheum match (e.g., MS + NMOSD + CIDP)?

This case is now handled by the pure-OIM basket-detection pass in
`_classify_disease` (commit 670de88). If you find a multi-OIM trial
still mis-classified as Single + "Other immune-mediated", it means
the OIM cluster terms in `_OIM_CLUSTERS` don't match the trial's
spelling. Add the missing alias:

```python
# pipeline.py — _OIM_CLUSTERS
"MS": ["multiple sclerosis", "rrms", "ppms", "spms",
       "your-new-alias"],   # ← here
```

### Q6. Is the product type ambiguous from the public record?

Autologous vs Allogeneic vs In vivo is usually findable in the
sponsor's intervention description. If genuinely ambiguous (e.g.,
the trial description says "CAR-T cells" without specifying donor),
add an LLM override:

```json
// llm_overrides.json
"NCT0XXXXXXX": {
  "product_type": "Autologous",
  "confidence": "medium",
  "rationale": "Sponsor's pipeline page (link) describes the
                construct as autologous; trial record was ambiguous."
}
```

### Q7. None of the above — leave as-is

If you can't confidently determine the right label from public
sources, DO NOT guess. Leave the trial in the sentinel/generic
bucket. Better to have an honest "unclassified" than a confidently-
wrong label that miscategorises every future trial of the same
construct.

## Step 3 — Apply changes, regenerate snapshot, run the gate

```python
import pandas as pd
import pipeline as p

# 1. Edit config.py / pipeline.py / llm_overrides.json per Q2-Q6 above.
#    Restart Python to reload the modules.

# 2. Re-classify the snapshot in place.
trials_path = 'snapshots/<latest_date>/trials.csv'
df = pd.read_csv(trials_path)
old_target  = df['TargetCategory'].copy()
old_design  = df['TrialDesign'].copy()
old_entity  = df['DiseaseEntity'].copy()
old_entities = df['DiseaseEntities'].copy()

# Re-run the full classifier on every row.
new_ents, new_design, new_primary = [], [], []
for _, r in df.iterrows():
    e, d, p_ = p._classify_disease(r.to_dict())
    new_ents.append('|'.join(e)); new_design.append(d); new_primary.append(p_)
df['DiseaseEntities'] = new_ents
df['TrialDesign']     = new_design
df['DiseaseEntity']   = new_primary
df['TargetCategory']  = df.apply(lambda r: p._assign_target(r.to_dict())[0], axis=1)
df['TargetSource']    = df.apply(lambda r: p._assign_target(r.to_dict())[1], axis=1)
df['ProductType']     = df.apply(lambda r: p._assign_product_type(r.to_dict())[0], axis=1)

# 3. STRICT acceptance gate — every flip must be an upgrade or a
#    legitimate cross-specific change. Disallowed transitions:
#       <specific> → CAR-T_unspecified / Other_or_unknown   (target)
#       SLE / SSc / RA / AAV / etc → Other immune-mediated  (entity)
#       Single → Basket  ONLY if conditions list ≥2 distinct entities
#                        (defensive — don't over-promote)
#       Autologous / Allogeneic / In vivo → Unclear         (product)
#
#    Cross-specific (e.g., BAFF → BAFF-R) is allowed iff the rationale
#    is documented in the commit message.

DOWNGRADES = []
for i, r in df.iterrows():
    # Target
    if (df.loc[i, 'TargetCategory'] in ('CAR-T_unspecified', 'Other_or_unknown')
            and old_target[i] not in ('CAR-T_unspecified', 'Other_or_unknown', '')):
        DOWNGRADES.append((r['NCTId'], 'Target', old_target[i], df.loc[i, 'TargetCategory']))
    # Disease entity
    if (df.loc[i, 'DiseaseEntity'] == 'Other immune-mediated'
            and old_entity[i] not in ('Other immune-mediated', 'Unclassified', '')):
        DOWNGRADES.append((r['NCTId'], 'Entity', old_entity[i], df.loc[i, 'DiseaseEntity']))
    # Product type
    if (df.loc[i, 'ProductType'] == 'Unclear'
            and r.get('ProductType') not in ('Unclear', '')):
        DOWNGRADES.append((r['NCTId'], 'ProductType', r.get('ProductType'), df.loc[i, 'ProductType']))

assert not DOWNGRADES, (
    f"REGRESSION — {len(DOWNGRADES)} trials downgraded to "
    f"sentinel: {DOWNGRADES[:10]}"
)

# 4. Show net upgrade count per axis.
print(f"Target upgrades:   {sum((old_target.isin(['CAR-T_unspecified','Other_or_unknown'])) & (~df['TargetCategory'].isin(['CAR-T_unspecified','Other_or_unknown'])))}")
print(f"Entity upgrades:   {sum((old_entity == 'Other immune-mediated') & (df['DiseaseEntity'] != 'Other immune-mediated'))}")

# 5. Write back, sort by NCT for byte-deterministic CSV.
df.sort_values('NCTId', kind='stable').to_csv(trials_path, index=False)
```

## Step 4 — Run tests + verify dashboard

```bash
python3 -m pytest tests/ -q
# 175+ tests must still pass; benchmark + classification_rationale
# tests cover the classifier behaviour locked in by previous audits.
```

Open the dashboard, eyeball the sunburst — the "Other immune-
mediated" wedge should shrink, the specific-disease wedges grow
proportionally. Headline tile counts shift accordingly.

## Step 5 — Commit

Standard commit-message template:

```
fix(classifier): expand <vocabulary | rule | override> — N upgrades

Audit-driven walkthrough of the <date> snapshot (worklist: M trials
with sentinel labels on any classification axis). Identified N
upgrades across:

  - Q2 (named product):   <list of new NAMED_PRODUCT_TARGETS adds>
  - Q3 (new antigen):     <list of new CAR_SPECIFIC_TARGET_TERMS adds>
  - Q4 (new entity):      <list of new _DISEASE_TERMS adds>
  - Q5 (OIM alias):       <list of new _OIM_CLUSTERS aliases>
  - Q6 (LLM override):    <list of new llm_overrides.json entries>

Acceptance gate (Python regression test inline above):
  - 0 trials downgraded from a specific label to sentinel.
  - N trials moved from sentinel/generic to specific.

Snapshot rewritten in place; tests still passing (175/175).
```

## Notes / pitfalls

- **Always run the Q4 sanity-check** before adding a product key.
  A 4-character code like "F01" or "C19" matches in unrelated
  contexts and silently miscategorises trials.
- **Sponsor pages are the gold standard** for product-target lookup.
  Avoid Wikipedia / press release summaries — they often paraphrase
  the target imprecisely.
- **OIM cluster aliases are case-insensitive substrings.** Adding
  "ms " (with trailing space) catches "MS therapy" but not "rMS".
  Test with at least one positive and one negative match.
- **Don't add anything you can't verify from public sources.** The
  pipeline is the canonical source of truth — a wrong rule
  miscategorises every future trial of that construct silently.
- **Audit the audit:** after applying changes, randomly sample 5
  upgraded trials and verify the new label is correct. If 1/5 is
  wrong, undo the rule that caused it.

--- END PROMPT ---
