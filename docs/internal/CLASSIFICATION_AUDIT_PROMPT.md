# Curation-loop prompt — multi-axis classification audit

Self-contained brief for a fresh Claude Code session in the rheum repo.
Drives the canonical curation loop the dashboard already exports as
**`curation_loop.csv`** (CURATION_LOOP_V1 format, downloadable from
the Methods tab → "Download curation CSV"). Walks every trial flagged
unclear on Disease / Target / Product and proposes the cheapest
upgrade that won't downgrade any other trial.

Companion prompt: `NAMED_PRODUCT_AUDIT_PROMPT.md` (narrower —
TargetCategory via product-name lookup only). Use this prompt for the
full multi-axis audit; use the named-product prompt when only the
target axis is in scope.

---

--- BEGIN PROMPT ---

You are auditing the rheum-dashboard classifier. Input: a
`curation_loop.csv` file in CURATION_LOOP_V1 format (downloadable
from the Methods tab of the dashboard, or generated programmatically
via `python3 scripts/audit_classification.py`).

Each row is a trial flagged unclear on at least one of three axes:

  Disease entity ─── DiseaseEntity ∈ {Unclassified, Autoimmune_other,
                                       Other_or_unknown}
  Antigen target ─── TargetCategory ∈ {CAR-T_unspecified,
                                        Other_or_unknown}
  Product type ───── ProductType   ∈ {Unclear}

The `UnclearFields` column tags which axes triggered inclusion (one
or more of: `Disease`, `Target`, `Product`).

## Controlled vocabulary (locked — DO NOT propose values outside this list)

```
DiseaseEntity:
  SLE, SSc, Sjogren, CTD_other, IIM, AAV, RA, IgG4-RD, Behcet, cGVHD,
  Basket/Multidisease, Other immune-mediated, Autoimmune_other,
  Unclassified, Exclude

  (OIM cluster labels also valid as DiseaseEntities entries — emitted
  by the pipeline's pure-OIM basket detector for multi-OIM trials:
  MS, NMOSD, CIDP, MOGAD, AIE, Myasthenia, Stiff_person, Pemphigus,
  T1D, ITP, AIHA, IgAN, Membranous, FSGS)

TargetCategory:
  CD19, BCMA, CD20, CD70, CD6, CD7, BAFF, BAFF-R,
  CD19/BCMA dual, CD19/CD20 dual, CD19/BAFF dual, BCMA/CD70 dual,
  CAR-NK, CAAR-T, CAR-Treg, CAR-T_unspecified, Other_or_unknown

ProductType:
  Autologous, Allogeneic/Off-the-shelf, In vivo, Unclear
```

`Exclude` on DiseaseEntity is the canonical "this trial is off-scope"
outcome — equivalent to adding to `HARD_EXCLUDED_NCT_IDS` but cleaner
for single-trial exclusions.

## Step 1 — Read the worklist

Read `curation_loop.csv` (or whichever path the user supplies). Each
row has these columns:

  NCTId, BriefTitle, Conditions, Interventions, DiseaseEntity,
  TargetCategory, ProductType, UnclearFields, BriefSummary

## Step 2 — Walk each trial. Decide the cheapest correction tool.

For each row, ask the questions in order and stop at the first that
fits. The goal is to make the classifier learn the pattern, not to
hand-correct each trial individually.

### Q1. Is the trial off-scope for an autoimmune CAR-T review?

A small fraction is mis-included (e.g., oncology trials that mention
"autoimmune" once in eligibility text, or animal studies). Two paths:

(a) Single-trial exclusion via per-NCT override — fastest, no rule risk:
```json
// llm_overrides.json
"NCT0XXXXXXX": {
  "disease_entity": "Exclude",
  "confidence": "high",
  "rationale": "Oncology trial; the autoimmune mention is in
                exclusion criteria, not enrolment."
}
```

(b) Permanent exclusion via curated list — for trials that should
    never have entered the index:
```python
# config.py
HARD_EXCLUDED_NCT_IDS = {
    ...,
    "NCT0XXXXXXX",   # one-line reason
}
```

Use (a) when the trial is borderline / individual; use (b) when the
trial pre-dates the current ingestion rules and won't return.

### Q2. Does the trial title / interventions text name a known
       CAR-T product (sponsor code, drug name, or research code)?

Examples that have been seen on the worklist: "JCAR017", "ide-cel",
"GC012F", "LMY-920", "BRL-301", "KYV-101", "C-CAR168", "FT819",
"CC-97540", "axi-cel", "HN2301", "F01" (wait — F01 is too generic,
see the warning at the bottom).

Look up the product's binding target via:
  - sponsor's pipeline page (gold standard),
  - ClinicalTrials.gov detailed description,
  - recent publications,
  - drugbank / chembl.

If found AND the target is unambiguous, add to:

```python
# pipeline.py
NAMED_PRODUCT_TARGETS = {
    ...,
    "lmy-920":   ("BAFF-R",          "LMY-920"),
    "kyv-101":   ("CD19",            "KYV-101"),
    "gc012f":    ("CD19/BCMA dual",  "GC012F"),
}
```

ALWAYS run the false-positive sanity check before adding:

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
candidate is too generic — refuse the add (use Q6 LLM override
instead for the specific trial).

### Q3. Does the title / conditions text name a specific antigen
       outside the current classifier vocabulary?

Examples that have appeared on the worklist before: BAFF-R (now
covered), GPRC5D, FcRn, NKG2D-L, CD22 (rare in rheum). Add to:

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

Also add `"GPRC5D"` to:
  - `_FLAG_AXIS_OPTIONS["TargetCategory"]` in app.py (community-flag UI)
  - the controlled-vocab list in `app.py:export_curation_loop` (the
    CURATION_LOOP_V1 header)
  - the doc above (this prompt's controlled-vocabulary block)

### Q4. Does the trial enrol a specific rheum / OIM disease that
       isn't in the current `_DISEASE_TERMS` map?

Examples: psoriatic arthritis, ankylosing spondylitis, juvenile
idiopathic arthritis, autoimmune hepatitis. Add to:

```python
# pipeline.py — _DISEASE_TERMS
"PsA": ["psoriatic arthritis"],
"AS":  ["ankylosing spondylitis", "axial spondyloarthritis"],
```

For a new entity, ALSO update three companion data structures:
  - `_SYSTEMIC_DISEASES` set (counts toward basket-promotion threshold)
  - `app.py:_DISEASE_FAMILY_MAP` — the family rollup for sunburst / charts
  - `app.py:ENTITY_COLORS` — pick a shade in the appropriate family's
    palette band (sky-900→sky-600 for rheum entities; comment block
    on ENTITY_COLORS explains the schema)

Without these companions, the new entity will appear in
DiseaseEntity / DiseaseEntities but won't roll up to a family wedge
in the sunburst.

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

### Q6. Is the construct's identity ambiguous from the public record?

When the trial title says "CAR-T cells" without specifying the
antigen / donor source / product, and the sponsor doesn't publish a
construct page, the right tool is a per-trial LLM override:

```json
// llm_overrides.json
"NCT0XXXXXXX": {
  "target_category": "CD19",
  "product_type":    "Autologous",
  "confidence":      "medium",
  "rationale":       "Sponsor's IND filing (link) describes the
                      construct as autologous anti-CD19. Trial
                      record was ambiguous."
}
```

Per-NCT overrides bypass the rule-based classifier for that trial.
Use sparingly — they don't generalise. If you find yourself adding
the same override to 5+ trials, look for a rule-level fix (Q2-Q5).

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

# 1. Edit config.py / pipeline.py / llm_overrides.json per Q1-Q6 above.
#    Restart Python to reload the modules.

# 2. Re-classify the snapshot in place.
trials_path = 'snapshots/<latest_date>/trials.csv'
df = pd.read_csv(trials_path)
old_target  = df['TargetCategory'].copy()
old_design  = df['TrialDesign'].copy()
old_entity  = df['DiseaseEntity'].copy()
old_product = df['ProductType'].copy()

# Re-run the full classifier on every row.
new_ents, new_design, new_primary = [], [], []
for _, r in df.iterrows():
    e, d, pr = p._classify_disease(r.to_dict())
    new_ents.append('|'.join(e)); new_design.append(d); new_primary.append(pr)
df['DiseaseEntities'] = new_ents
df['TrialDesign']     = new_design
df['DiseaseEntity']   = new_primary
df['TargetCategory']  = df.apply(lambda r: p._assign_target(r.to_dict())[0], axis=1)
df['TargetSource']    = df.apply(lambda r: p._assign_target(r.to_dict())[1], axis=1)
df['ProductType']     = df.apply(lambda r: p._assign_product_type(r.to_dict())[0], axis=1)

# 3. STRICT acceptance gate — every flip must be an upgrade or a
#    legitimate cross-specific change. Disallowed transitions:
#       <specific> → CAR-T_unspecified / Other_or_unknown   (target)
#       SLE / SSc / RA / etc → Other immune-mediated / Unclassified  (entity)
#       Single → Basket  ONLY when ≥2 distinct entities truly named
#       Autologous / Allogeneic / In vivo → Unclear         (product)
#
#    Cross-specific (e.g., BAFF → BAFF-R) is allowed iff the rationale
#    is documented in the commit message.

DOWNGRADES = []
SENTINEL_TARGETS  = {'CAR-T_unspecified', 'Other_or_unknown'}
SENTINEL_ENTITIES = {'Other immune-mediated', 'Unclassified', 'Autoimmune_other'}
SENTINEL_PRODUCTS = {'Unclear'}

for i, r in df.iterrows():
    nct = r['NCTId']
    if (df.loc[i, 'TargetCategory'] in SENTINEL_TARGETS
            and old_target[i] not in SENTINEL_TARGETS | {''}):
        DOWNGRADES.append((nct, 'Target', old_target[i], df.loc[i, 'TargetCategory']))
    if (df.loc[i, 'DiseaseEntity'] in SENTINEL_ENTITIES
            and old_entity[i] not in SENTINEL_ENTITIES | {''}):
        DOWNGRADES.append((nct, 'Entity', old_entity[i], df.loc[i, 'DiseaseEntity']))
    if (df.loc[i, 'ProductType'] in SENTINEL_PRODUCTS
            and old_product[i] not in SENTINEL_PRODUCTS | {''}):
        DOWNGRADES.append((nct, 'Product', old_product[i], df.loc[i, 'ProductType']))

assert not DOWNGRADES, (
    f"REGRESSION — {len(DOWNGRADES)} trials downgraded to sentinel: "
    f"{DOWNGRADES[:10]}"
)

# 4. Show net upgrade count per axis.
def _upgrades(old_col, new_col, sentinels):
    return ((old_col.isin(sentinels)) & (~new_col.isin(sentinels))).sum()
print(f"Target upgrades:   {_upgrades(old_target,  df['TargetCategory'], SENTINEL_TARGETS)}")
print(f"Entity upgrades:   {_upgrades(old_entity,  df['DiseaseEntity'],  SENTINEL_ENTITIES)}")
print(f"Product upgrades:  {_upgrades(old_product, df['ProductType'],    SENTINEL_PRODUCTS)}")

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
proportionally. Headline tile counts shift accordingly. Re-download
`curation_loop.csv` from the Methods tab; row count should have
dropped by approximately the number of upgrades you applied.

## Step 5 — Commit (template)

```
fix(classifier): expand <vocabulary | rule | override> — N upgrades

Curation-loop walkthrough of the <date> snapshot (worklist: M trials
in CURATION_LOOP_V1 export). Identified N upgrades across:

  - Q2 (named product):   <list of new NAMED_PRODUCT_TARGETS adds>
  - Q3 (new antigen):     <list of new CAR_SPECIFIC_TARGET_TERMS adds>
  - Q4 (new entity):      <list of new _DISEASE_TERMS adds>
  - Q5 (OIM alias):       <list of new _OIM_CLUSTERS aliases>
  - Q6 (LLM override):    <list of new llm_overrides.json entries>
  - Q1 (exclude):         <list of NCTs marked Exclude>

Acceptance gate (Python regression test inline above):
  - 0 trials downgraded from a specific label to sentinel.
  - N trials moved from sentinel/generic to specific.

Snapshot rewritten in place; tests still passing (175/175).
```

## Notes / pitfalls (locked-in lessons)

- **Always run the Q2 false-positive sanity-check** before adding a
  product key. A 4-character code like "F01" or "C19" matches in
  unrelated contexts and silently miscategorises trials. The "f01"
  example: there's a real "F01" CAR-T but the bare token also
  matches the ICD-10 code F01.5 in some trial eligibility text.

- **Sponsor pages are the gold standard** for product-target lookup.
  Avoid Wikipedia / press release summaries — they often paraphrase
  the target imprecisely. Patent / IND filings are the second-best.

- **OIM cluster aliases are case-insensitive substrings.** Adding
  "ms " (with trailing space) catches "MS therapy" but not "rMS".
  Test with at least one positive and one negative match in the
  current snapshot before committing.

- **Don't add anything you can't verify from public sources.** The
  pipeline is the canonical source of truth — a wrong rule
  miscategorises every future trial of that construct silently.

- **Audit the audit:** after applying changes, randomly sample 5
  upgraded trials and verify the new label is correct. If 1/5 is
  wrong, undo the rule that caused it. Better to revert than to
  ship a wrong label.

- **The "Exclude" disease-entity value** is the canonical mechanism
  for single-trial off-scope marking. Use it via `llm_overrides.json`
  rather than `HARD_EXCLUDED_NCT_IDS` for nuanced cases (the override
  carries a rationale field that the dashboard surfaces).

--- END PROMPT ---
