# Cross-app brief — Round 2: Bucket A architectures + sequencing

For the parallel onc-app session. Paste-ready into the same fresh
Claude Code session that drafted the Round 1 reply. **Stop after
Round 2's reply** and ping back — Round 3 closes with explicit
owner-and-timeline assignments.

Onc Round 1 reply received and acknowledged below. Concrete
architectures for the four co-developed Bucket A items follow.

---

--- BEGIN PROMPT ---

## Round 1 ack — onc reply received

Quick acknowledgements before architectures:

- **Q1 priorities** noted: κ lock-in is your #1; rheum's #1 is the
  same in spirit (locked benchmark + κ study). Glad these align.
- **Q2 dispositions** all accepted as proposed. Co-develop slots:
  Zenodo DOI, daily CI, multi-registry, stalled-flag, REST API.
  Rheum-ships-first slots: NCT→PubMed, governance files. Onc-leads-
  jRCT after the joint ChiCTR adapter — accepted.
- **Q3 alignment** — agreed on all four:
    snake_case query params + `?snapshot=YYYY-MM-DD` reserved
    rapidfuzz for fuzzy search
    `## Limitations` H2 + matching sub-bullet structure
    python:3.12-slim Docker base + pip-compile + expose 8501
- **Q4 sister-papers** accepted. The argument about authorship and
  reviewer-pool divergence is decisive.
- **Q5 ChiCTR-first** — convergent ordering. Lead-jRCT-by-onc accepted.
- **Q6 overlap** — biostat/methods, regulatory, open-science slots are
  realistic. Names offline as you said.
- **Q7 deadline implications** drive the sequencing proposal in §6 below.
- **Schema clarification (your last paragraph)** answered concretely
  in §3.

## §1 — Zenodo DOI workflow

Trigger: GitHub Action on push of any tag matching `snapshot-YYYY-MM-DD`.
Each app maintains its own concept DOI; per-snapshot DOIs are versions
of the concept DOI. Onc's existing `10.5281/zenodo.19738097` becomes
the concept DOI for onc; rheum already has `10.5281/zenodo.19713049`
for the repo (concept) and minted versions go under it.

```yaml
# .github/workflows/zenodo-snapshot-doi.yml — IDENTICAL ACROSS BOTH APPS
name: Mint Zenodo DOI on snapshot tag
on:
  push:
    tags:
      - 'snapshot-*'        # e.g. snapshot-2026-05-07
jobs:
  zenodo-deposit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }      # need full history for SHA in metadata
      - name: Build snapshot bundle
        run: |
          ./scripts/zenodo_build_bundle.sh \
            --snapshot "${GITHUB_REF_NAME#snapshot-}" \
            --commit "${GITHUB_SHA}" \
            --out dist/
      - name: Mint DOI via Zenodo API
        env:
          ZENODO_TOKEN: ${{ secrets.ZENODO_TOKEN }}
          ZENODO_CONCEPT_DOI: ${{ vars.ZENODO_CONCEPT_DOI }}  # per-app value
        run: |
          python scripts/zenodo_deposit.py \
            --bundle dist/*.zip \
            --metadata zenodo_metadata_template.json \
            --concept-doi "$ZENODO_CONCEPT_DOI" \
            --token "$ZENODO_TOKEN" \
            --out-meta dist/zenodo_response.json
      - name: Update README + CITATION.cff with new DOI
        run: python scripts/update_doi_refs.py dist/zenodo_response.json
      - name: Commit + push DOI bumps
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "actions@github.com"
          git add README.md CITATION.cff snapshots/
          git diff --quiet && exit 0 || git commit -m "Auto-update DOI refs to ${GITHUB_REF_NAME}"
          git push
```

Metadata template (per-app values via `${VAR}` placeholders, resolved
in `zenodo_deposit.py`):

```json
{
  "metadata": {
    "title":        "${APP_TITLE} — snapshot ${SNAPSHOT_DATE}",
    "upload_type":  "dataset",
    "publication_date": "${SNAPSHOT_DATE}",
    "creators": [
      {"name": "Jeong, Peter", "affiliation": "Universitätsklinikum Köln"}
    ],
    "description": "Frozen snapshot ${SNAPSHOT_DATE} of the ${APP_TITLE} dashboard. Includes trials.csv, sites.csv, prisma.json, and metadata.json. Generated from ClinicalTrials.gov API v2 + closed-vocab classifier (commit ${COMMIT_SHA}).",
    "keywords":    ["CAR-T", "clinical-trials", "${APP_KEYWORD}", "registry"],
    "license":     "MIT",
    "version":     "${SNAPSHOT_DATE}",
    "related_identifiers": [
      {"identifier": "${ZENODO_CONCEPT_DOI}", "relation": "isVersionOf",     "resource_type": "dataset"},
      {"identifier": "https://github.com/${GITHUB_REPOSITORY}/tree/${COMMIT_SHA}", "relation": "isSupplementTo", "resource_type": "software"}
    ]
  }
}
```

Per-app `vars` in GitHub repo settings:
- `APP_TITLE` (e.g., "CAR-T Rheumatology Trials Monitor")
- `APP_KEYWORD` ("rheumatology" / "oncology")
- `ZENODO_CONCEPT_DOI` (`10.5281/zenodo.19713049` / `10.5281/zenodo.19738097`)

**Onc's "hard-won schema lessons" from the manual deposit** — please
flag in your Round 2 reply if any field above conflicts with what
worked. Specifically: was `upload_type: dataset` the right choice
or did Zenodo prefer `software` for our type of artifact? Did
`related_identifiers.resource_type: dataset` cause any validation
warnings?

## §2 — Daily snapshot CI

Trigger: 03:00 UTC daily cron + `workflow_dispatch` for manual runs.
Diff-detection uses onc's `_snapshot_mtime()` / `_classifier_mtime()`
pattern — the Action skips the commit if the data hash and classifier
hash both match the previous snapshot (no spurious snapshots when
nothing changed).

```yaml
# .github/workflows/daily-snapshot.yml — TEMPLATE, per-app diff in fetch step
name: Daily snapshot rebuild
on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:
jobs:
  snapshot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - name: Fetch + classify
        run: python scripts/build_snapshot.py --out snapshots/
      - name: Hash the new snapshot
        id: hash
        run: |
          DATA_HASH=$(./scripts/hash_snapshot.py snapshots/$(ls snapshots/ | tail -1))
          CLASSIFIER_HASH=$(git rev-parse HEAD:pipeline.py)
          PREV_DATA_HASH=$(cat snapshots/.last_data_hash 2>/dev/null || echo "")
          PREV_CLF_HASH=$(cat snapshots/.last_classifier_hash 2>/dev/null || echo "")
          if [ "$DATA_HASH" = "$PREV_DATA_HASH" ] && [ "$CLASSIFIER_HASH" = "$PREV_CLF_HASH" ]; then
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
            echo "$DATA_HASH"       > snapshots/.last_data_hash
            echo "$CLASSIFIER_HASH" > snapshots/.last_classifier_hash
          fi
      - name: Diff vs previous snapshot
        if: steps.hash.outputs.skip == 'false'
        id: diff
        run: |
          python scripts/snapshot_diff.py \
            --previous --current --markdown > diff.md
      - name: Open summary issue
        if: steps.hash.outputs.skip == 'false'
        uses: peter-evans/create-issue-from-file@v5
        with:
          title:        "Snapshot ${{ env.SNAP_DATE }} — N trial(s) changed"
          content-filepath: diff.md
          labels:       "snapshot,daily-rebuild"
      - name: Commit + push
        if: steps.hash.outputs.skip == 'false'
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "actions@github.com"
          git add snapshots/
          git commit -m "Daily snapshot $(date +%Y-%m-%d)"
          git push
      - name: Tag for Zenodo workflow
        if: steps.hash.outputs.skip == 'false'
        run: |
          git tag "snapshot-$(date +%Y-%m-%d)"
          git push --tags    # triggers the Zenodo workflow above
```

Onc's `_snapshot_mtime()` lives in `pipeline.py` (per your reply); rheum
side uses `list_snapshots()` + a per-snapshot `metadata.json`. The hash-
based skip-decision avoids any cross-app dependency on those internal
helpers — both apps just write `.last_data_hash` files alongside the
snapshot.

## §3 — Multi-registry adapter API (your clarification answered)

**Decision: CT.gov v2 field names as the core schema, `_extras: dict`
for registry-specific fields.** Your concern about onc-side porting
work is the deciding factor — both apps already transform CT.gov v2
fields end-to-end; reusing the names means zero pipeline churn for the
common case, and `_extras` carries the registry-native oddities until
both apps need them promoted to first-class fields.

Package layout:

```
car_t_registries/                    ← new shared package on PyPI
    __init__.py
    schema.py                        — Trial Pydantic model
    merge.py                         — dedupe + cross-registry join
    adapters/
        __init__.py
        clinicaltrials_gov.py        — already-existing logic, repackaged
        chictr.py                    — NEW (joint, ChiCTR-first)
        jrct.py                      — NEW (onc leads, post-preprint)
        eu_ctr.py                    — NEW (Q1 2027)
        ictrp.py                     — NEW (deferred)
    classifiers/
        # NOT IN THE SHARED PACKAGE — disease/target classification stays
        # per-app since the closed vocabularies differ.
```

```python
# car_t_registries/schema.py
from datetime import date
from typing  import Optional
from pydantic import BaseModel, Field

class Trial(BaseModel):
    """Cross-registry trial record. Field names mirror CT.gov v2 so
    existing pipeline transforms keep working unchanged. Registry-
    native fields that don't fit live in `_extras`."""
    # ── CT.gov v2 core (mirrored exactly) ─────────────────────────
    NCTId:                Optional[str] = None      # CT.gov ID (None for non-CT.gov-registered)
    BriefTitle:           str
    OfficialTitle:        Optional[str] = None
    Conditions:           list[str]            = Field(default_factory=list)
    Interventions:        list[str]            = Field(default_factory=list)
    Phase:                Optional[str] = None
    OverallStatus:        str
    StartDate:            Optional[date] = None
    EnrollmentCount:      Optional[int] = None
    Countries:            list[str]            = Field(default_factory=list)
    LeadSponsor:          str
    LeadSponsorClass:     Optional[str] = None
    PrimaryEndpoints:     list[str]            = Field(default_factory=list)
    BriefSummary:         str

    # ── Cross-registry provenance ─────────────────────────────────
    SourceRegistry:       str           # "CT.gov" | "ChiCTR" | "jRCT" | "EU_CTR" | "ICTRP"
    SourceTrialId:        str           # registry-native ID
    SourceUrl:            str           # canonical URL on that registry
    FetchedAt:            date          # when this record was pulled

    # ── Registry-specific extras (free-form dict) ─────────────────
    Extras:               dict          = Field(default_factory=dict)

class Adapter:
    """All adapters expose `fetch(query: dict) -> list[Trial]`."""
    def fetch(self, query: dict) -> list[Trial]: ...
```

ChiCTR adapter (joint build) notes:
- chictr.org.cn endpoint is form-encoded, not REST. Returns HTML
  tables in some cases — adapter must scrape robustly.
- Trial IDs: `ChiCTR-NNN-XXNNNNNN` format. Adapter sets
  `NCTId=None`, `SourceTrialId=ChiCTR-...`.
- Chinese conditions/interventions: adapter passes the original
  Chinese text through; per-app classifiers do the disease/target
  classification (which already needs Chinese-aware terms in
  `_DISEASE_TERMS` etc.). Shared package does NOT classify.
- ChiCTR-specific fields that don't fit CT.gov: ethics committee
  approval status, sponsor contact ID, study type code. All into
  `Extras`.

`merge.py` cross-registry dedupe:
- Primary key: NCTId when present (canonical CT.gov ID).
- Fallback: `(SourceRegistry, SourceTrialId)` — multi-registered
  trials (e.g., ChiCTR + CT.gov) collapse on NCTId, with ChiCTR
  data folded into `Extras["ChiCTR"]`.
- When fields conflict (different phase, different sponsor), prefer
  the most-recent `FetchedAt`.

## §4 — Stalled-trial flag

```python
# car_t_registries/predicates.py — shared one-liner helper
from datetime import date

def is_stalled_recruiting(
    overall_status: str,
    start_year:     int | None,
    *,
    today:           date | None = None,
    threshold_years: int          = 3,
) -> bool:
    """A trial is "stalled" iff its OverallStatus is RECRUITING or
    NOT_YET_RECRUITING AND its StartYear is at least `threshold_years`
    years before today. Default threshold = 3 years (consistent with
    FDA / EMA reporting cadence)."""
    if overall_status not in {"RECRUITING", "NOT_YET_RECRUITING"}:
        return False
    if start_year is None:
        return False
    return ((today or date.today()).year - int(start_year)) >= threshold_years
```

Each app:
- Adds `IsStalled` boolean column to the dataframe via the predicate
- Sidebar filter "Stalled trials" toggle (Yes / No / Either)
- Trial-card amber tag when stalled
- Per-disease % stalled metric in the Deep Dive "By disease" landscape

Trail-recency logic in onc's `pipeline.py` you mentioned — please
quote the exact function or commit so I can vendor the cleaner of
the two implementations into `car_t_registries.predicates`.

## §5 — REST API endpoint shape

```
GET  /v1/trials                               — list (filter via query params)
GET  /v1/trials/{nct_or_source_id}           — single trial
GET  /v1/snapshots                            — list available snapshots
GET  /v1/snapshots/{date}                     — snapshot manifest + DOI
GET  /v1/snapshots/{date}/trials              — full snapshot CSV-equivalent JSON
GET  /v1/health                               — uptime check + version
```

Filter conventions (matches Bucket B query-param naming):
```
?disease=SLE,SSc          ── comma-separated multi-select
?phase=2,2_3              ── PHASE2 + PHASE2|PHASE3
?country=China,US
?stalled=true             ── boolean
?snapshot=2026-05-07      ── pin to snapshot
?registry=CT.gov,ChiCTR   ── filter by source registry (post-multi-registry)
?limit=50&offset=100      ── pagination
?fields=NCTId,BriefTitle,Phase  ── projection (default: all)
```

Authentication: optional `X-API-Key` header for elevated rate limits
(100 req/h anonymous, 1000 req/h with key). Keys minted via a simple
admin command; per-app key namespaces.

Deployment per-app (FastAPI sidecar to Streamlit). Both apps publish
OpenAPI 3.1 specs at `/v1/openapi.json` for tooling.

## §6 — Sequencing (respects onc preprint Q3 2026 deadline)

Onc preprint deadline implies Bucket A items #1 + #5 must land by
~end of Q2 2026 (~7 weeks from today, 2026-05-07). Multi-registry +
NCT→PubMed are post-preprint Q3-Q4. Concrete sequence:

| Week | Joint deliverables | Owner | Notes |
|---|---|---|---|
| **W1-2** | Zenodo DOI workflow | rheum builds, onc reviews | both apps mint DOIs by W2 |
| **W1**   | CONTRIBUTING / COC / CHANGELOG | rheum builds, onc ports | trivial |
| **W2**   | Stalled-trial flag | rheum builds the predicate, both apps wire UI | half-day each |
| **W3-4** | Daily snapshot CI | rheum builds template, onc adapts to its `_snapshot_mtime` flow | tag-on-change → triggers Zenodo |
| **W5-6** | NCT → PubMed linkage | rheum builds, onc ports | both apps surface PubMed links in Trial Cards by W6 |
| **W7** (preprint freeze) | All preprint-blocking items shipped | — | onc preprint can cite stable Zenodo DOIs + reproducible CI |
| **W8-12** | Multi-registry shared package | joint build, ChiCTR adapter first | rheum + onc both consume |
| **W13-16** | jRCT adapter | onc leads | post-preprint |
| **W13-15** | REST API skeleton | rheum builds, onc ports | both apps deploy by W16 |
| **W17-20** | EU CTR adapter, sister-papers refinement | both | Q4 2026 |

## Round 2 questions — please reply

When you reply, please address each:

### Q1. Architecture acceptance per §1-§5

For each of the five architectures (Zenodo workflow, daily CI, multi-
registry, stalled-flag, REST API) — do you accept as proposed, accept
with amendments (specify), or reject?

### Q2. Zenodo metadata schema

Two specific fields to confirm based on your manual-deposit experience:
- `upload_type`: `dataset` (proposed) vs `software` vs `other`?
- `related_identifiers[].resource_type`: `dataset` vs `software`?

### Q3. ChiCTR adapter — who codes it?

Both apps need ChiCTR. Two options:
  (a) rheum drafts the adapter + schema, onc reviews at W8 then
      contributes Chinese-text-handling improvements;
  (b) onc drafts (you mentioned a stronger Chinese named-product
      audit harness — that domain knowledge transfers), rheum
      reviews;
  (c) split: rheum drafts the schema + Pydantic model + dedupe;
      onc drafts the chictr adapter; both review the union.

Pick one.

### Q4. Onc's `_snapshot_mtime()` / `_classifier_mtime()` — quote

Please cite the exact onc commit + line range so I can vendor the
cleaner of the two patterns. Diff-detection is the load-bearing
piece of the daily CI; getting this right matters.

### Q5. PyPI package ownership

The shared `car_t_registries` package — who hosts on PyPI? Options:
  (a) rheum maintainer publishes under their name
  (b) onc maintainer publishes
  (c) jointly (organisation account)
  (d) GitHub package registry (no PyPI; both apps install from git)

Maintenance overhead is the deciding factor. (d) is lowest-overhead;
(c) is most professional but requires an org account.

### Q6. REST API — sidecar or subpath?

Two deployment patterns:
  (a) FastAPI sidecar at `api.<app>.streamlit.app` (separate domain)
  (b) Same Streamlit app serves both (`/api/v1/*` mounted via WSGI
      bridge — fragile with Streamlit but possible)
  (c) FastAPI on a separate Render / Fly.io app

Pick one. Onc's "deployment is per-app" stance from Round 1 makes
me think (a) or (c) — confirm.

### Q7. Sequencing — fits the preprint deadline?

§6's sequence has all preprint-blocking items shipping by W7 (mid-
June 2026). If onc's bandwidth is more constrained (you mentioned
Stage-3 / Deep Dive consolidation in flight), what's the realistic
cadence?

## Stop here — DO NOT implement

Stop after drafting the Round 2 reply. Round 3 closes with the
explicit owner-and-timeline table both sides commit to.

If anything in §1-§6 is ambiguous, ask in your reply rather than
guessing.

## Preview — Round 3

Round 3 deliverable from rheum side will be a single table:

| Item | Owner (drafts) | Reviewer | Target week | Status |
|---|---|---|---|---|

Plus a "joint-build kickoff checklist" for ChiCTR adapter + REST API
shape (the two items that need synchronous coordination, not just
async PRs).

--- END PROMPT ---
