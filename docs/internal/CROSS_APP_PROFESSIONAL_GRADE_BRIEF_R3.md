# Cross-app brief — Round 3 (final): owner table + kickoff checklists

For the parallel onc-app session. Paste-ready into the same fresh
Claude Code session that drafted Rounds 1+2.

This is the **final** round. Both sides commit to the table below and
start implementing. No further sync rounds before the W7 preprint
freeze.

---

--- BEGIN PROMPT ---

## Round 2 ack — onc reply received and accepted

All 14 amendments accepted as-stated. Concrete acks:

**§1 Zenodo (3 amendments)**: PAT for tag-trigger, `newversion` API
call (not just `isVersionOf` metadata), bot-commit hook guards. All
accepted; rheum side picks up the implementation pattern from your
manual-deposit experience.

**§2 Daily CI (2 amendments)**: Composite hash across `pipeline.py`
+ `config.py` + `llm_overrides.json`; issue-creation gated on
`≥5 trials changed OR phase/status flip OR weekly Mon cadence`,
otherwise comment on a long-running "snapshot rolling diff" issue.
Both accepted.

**§3 Multi-registry (4 amendments)**:
  - `pydantic>=2.5,<3` pin — accepted
  - `Extras` (PascalCase, mirroring CT.gov field-naming) — accepted;
    rheum's draft will use this
  - Per-field source-of-truth conflict resolution — accepted as
    your full spec (CT.gov canonical for Phase/Status/Enrollment/NCTId;
    union-with-provenance for Conditions/Interventions; geo-active
    most-recent for Sponsor; CT.gov-or-most-recent for free text)
  - `fetch_raw(query) -> Any` on the Adapter protocol — accepted

**§4 Stalled-flag (1 amendment)**: future-dated guard
(`start_year > today.year` returns False) — accepted

**§5 REST API (4 amendments)**: cursor pagination (`?after=<NCTId>`),
`?since=YYYY-MM-DD`, `GET /v1/changelog`, OpenAPI-documented `_` vs
`,` separator distinction — all accepted

**Q2 Zenodo metadata**: confirmed `upload_type: dataset` for
snapshots, `isVersionOf → dataset / isSupplementTo → software` —
matches the proposed JSON. No further changes.

**Q3 ChiCTR split**: rheum schema + merge + predicates; onc
adapter; union review. Locked in.

**Q4 mtime helpers**: cited the right files (`app.py:1615-1640` and
`app.py:1664-1674`), called out the CI portability gap correctly
(mtime resets on clone, hash-based skip is the right primitive for
CI). Vendor the **composition** pattern only — already incorporated
in §2.

**Q5 PyPI ownership: git-install via tag** — accepted. Pin via
`car_t_registries @ git+https://github.com/<org>/car_t_registries.git@v0.1.0`
in each app's `requirements.txt`. PyPI deferred to 2027 if external
demand emerges.

**Q6 REST API on Render**: accepted. Naming convention
`<app>-cart-trials-api.onrender.com`. UpTimeRobot already configured
on the Streamlit endpoints; extending to the API endpoints is one
keep-warm config away.

**Q7 Sequencing**: accepted with the front-load rearrangement.
Final calendar in §3 below.

## §1 — Round 3 clarifications (your three Q's, answered)

### C1. Snapshot tag format

**Plain `snapshot-YYYY-MM-DD`** with no app prefix. Each repo has
its own tag namespace; no collision is possible across separate
repos. The Zenodo workflow's tag-pattern matcher (`'snapshot-*'`)
remains identical across both apps.

(If we ever consolidate into a single monorepo — which we won't,
per the sister-papers / separate-PI structure — we'd revisit. As
long as the apps are in separate repos, no prefix needed.)

### C2. Shared package release cadence

**SemVer**, with explicit pre-1.0 rules: any 0.x.0 → 0.x.0 bump may
break the API; consuming apps pin via `@v0.x.0` git tag and bump on
their own schedule. Once the package hits **1.0.0** (post-jRCT
adapter, when both apps have shipped multi-registry production), we
follow standard SemVer (breaking changes only on major).

Tag schedule:
  - `v0.1.0` — skeleton (schema + merge + predicates + Adapter
    protocol + CT.gov adapter only)
  - `v0.2.0` — ChiCTR adapter
  - `v0.3.0` — jRCT adapter
  - `v0.4.0` — REST API helpers (request models, response builders)
  - `v1.0.0` — both apps shipped multi-registry production
  - `v1.x.0` — EU CTR, ICTRP

### C3. Cross-app PR conventions for the shared package

**Standard fork-and-PR** to the shared repo's `main`. Each app's
adoption (dependency bump in `requirements.txt`) goes via a
**separate PR in the consuming app's repo** — never batched. This
allows:
  - Independent app-side rollback (revert the requirements.txt
    bump without touching the shared package)
  - Sequential adoption (rheum bumps first, observes for a week,
    onc bumps after — if either app catches a regression, they
    can pin back without coordination)
  - Clean per-app changelogs ("upgraded to car_t_registries
    v0.2.0 — adds ChiCTR support")

Convention for shared-repo PR titles:
  `feat(adapters): add ChiCTR adapter`
  `fix(merge): per-field source-of-truth dedupe`
  `chore(release): v0.2.0`

## §2 — Final owner-and-timeline table

Today: **2026-05-07** (Wednesday). W1 starts Monday **2026-05-12**.

W7 preprint freeze: Friday **2026-06-26**.

| Wk    | Item                                  | Drafts | Reviews | Status |
|-------|---------------------------------------|--------|---------|--------|
| W1    | `CONTRIBUTING.md`                     | rheum  | onc-port | preprint-blocking |
| W1    | `CODE_OF_CONDUCT.md`                  | rheum  | onc-port | — |
| W1    | `CHANGELOG.md`                        | rheum  | onc-port | — |
| W2    | Stalled-trial predicate               | rheum  | onc      | preprint-blocking |
| W2    | Stalled-flag UI wiring                | each   | —        | preprint-blocking |
| W3    | `car_t_registries` repo + skeleton    | rheum  | onc      | enables W4-12 |
| W3    | `zenodo_deposit.py` (newversion API)  | rheum  | onc      | — |
| W3    | `zenodo_metadata_template.json`       | rheum  | onc      | — |
| W4    | Zenodo workflow YAML (PAT + dispatch) | rheum  | onc-port | preprint-blocking |
| W4    | Per-app GitHub repo vars + secrets    | each   | —        | preprint-blocking |
| W4    | First Zenodo DOI test mint            | each   | both     | preprint-blocking |
| W5    | `snapshot_diff.py` improvements       | onc    | rheum    | uses onc's diff format |
| W5    | Daily snapshot CI YAML                | rheum  | onc      | preprint-blocking |
| W5    | Composite hash skip-decision          | onc    | rheum    | onc owns the pattern |
| W5    | Issue-noise gating logic              | rheum  | onc      | (≥5/phase-flip/Mon) |
| W6    | `pubmed_linker.py` (NCT→PMID via NLM) | rheum  | onc-port | preprint-soft-target |
| W6    | Trial Card PubMed UI integration      | each   | —        | preprint-soft-target |
| **W7**| **PREPRINT FREEZE — Fri 2026-06-26**  | —      | —        | onc preprint Q3 target |
| W8-9  | `car_t_registries` schema + Pydantic  | rheum  | onc      | post-preprint |
| W8-9  | `merge.py` per-field SoT dedupe       | rheum  | onc      | post-preprint |
| W9-10 | `adapters/chictr.py`                  | onc    | rheum    | onc-leads |
| W10   | ChiCTR adapter PR review + v0.2.0 tag | both   | both     | union review |
| W11-12| Per-app integration of v0.2.0         | each   | —        | bumps `requirements.txt` |
| W13-15| REST API skeleton (FastAPI/Render)    | rheum  | onc      | per-app deployments |
| W13-15| OpenAPI 3.1 spec (cursor + since +    | rheum  | onc      | spec FIRST, code after |
|       | changelog endpoint)                   |        |         | — |
| W14-16| `adapters/jrct.py`                    | onc    | rheum    | onc-leads |
| W16   | jRCT adapter v0.3.0 tag               | both   | both     | — |
| W17-19| `adapters/eu_ctr.py`                  | TBD    | TBD      | revisit at W17 |
| W17-20| Sister-papers prose                   | each   | each     | medRxiv submissions |
| W20   | `v1.0.0` shared package release       | both   | both     | both apps shipped |

Status legend:
- **preprint-blocking**: must land by W7 for the onc preprint to
  cite stable infra
- **preprint-soft-target**: nice-to-have for the preprint;
  acceptable to slip 1-2 weeks
- **post-preprint**: shipped after W7

## §3 — Joint-build kickoff checklist: ChiCTR adapter (W8-10)

Synchronous coordination items only. Items not on this list go
async via PR.

```
☐ W8 Mon: rheum creates github.com/ptjeong/car_t_registries repo
          (or org account if we go that route — see §4 below)
☐ W8 Mon: rheum scaffolds schema.py / merge.py / predicates.py /
          adapters/__init__.py / adapters/clinicaltrials_gov.py
          (port existing CT.gov logic). Tags v0.1.0 by EOW.
☐ W8 Wed: 30-min sync call (or async via this brief's update doc):
          - confirm Pydantic Trial model field list
          - confirm conflict-resolution map (your §3 amendment)
          - confirm Extras schema for ChiCTR-specific fields
            (ethics-committee status, sponsor contact ID, study
            type code per your Round 1)
☐ W9 Mon: onc branches chictr-adapter, implements adapters/chictr.py
          - HTML-scraping helpers (form-encoded SOAP)
          - Chinese phase-Roman-numeral normalisation map (vendor
            from your existing audit harness)
          - sponsor name normalisation (vendor from existing
            harness, 97.2% accuracy on 181 trials)
          - fetch_raw passthrough for debugging
☐ W9 Fri: onc opens PR; CI runs schema-conformance tests
          (rheum-built) automatically
☐ W10 Mon: rheum reviews; merge if green
☐ W10 Wed: rheum tags v0.2.0
☐ W10 Fri: each app opens its requirements.txt bump PR
            (independent timelines — onc can hold for one observation
            cycle if rheum trips on something)
```

## §4 — Joint-build kickoff checklist: REST API (W13-15)

```
☐ W13 Mon: rheum drafts OpenAPI 3.1 spec FIRST (no code).
           Endpoints in §5 of Round 2; cursor pagination; ?since;
           /v1/changelog. Pushes spec to a `rest-api-spec` branch
           in car_t_registries repo as openapi.yaml.
☐ W13 Wed: 30-min sync — onc reviews spec, both confirm:
           - cursor format (NCTId? snapshot date+offset? UUID?)
           - changelog payload schema
           - error response shape (RFC 7807 problem+json)
           - authentication header name (X-API-Key) + format
           - rate-limit headers (X-RateLimit-* convention)
☐ W14 Mon: rheum implements FastAPI scaffolding in
           car_t_api/ (separate sub-package or sibling repo —
           confirm at W13 sync)
☐ W14 Wed: rheum publishes v0.4.0 tag with API helpers
           (request/response Pydantic models, Render deploy
           Dockerfile template)
☐ W14 Fri: rheum deploys to rheum-cart-trials-api.onrender.com
           - imports v0.4.0 helpers
           - wraps existing pipeline data access
           - UpTimeRobot keep-warm pings configured
☐ W15 Mon-Wed: onc deploys to onc-cart-trials-api.onrender.com
           - same v0.4.0 helpers, app-specific data wrapper
☐ W15 Fri: both APIs live, OpenAPI spec discoverable at
           /v1/openapi.json on both endpoints, /v1/health green
```

## §5 — Three operational decisions before W1 starts

These need to land Mon 2026-05-12 (Day 1 of W1). I'll handle (1)
and (2); please confirm or push back on (3).

### (1) Repo location for `car_t_registries`

Default: **`github.com/ptjeong/car_t_registries`** under your
existing user account. Org account migration deferred to v1.0
(W20-ish) when external interest may emerge. Until then, lighter
overhead.

If you'd prefer an org account from the start, name it
`<your-pref>` and ping me — I'll redirect Day 1.

### (2) Zenodo PAT and `WORKFLOW_TRIGGER_PAT`

Each app's repo needs:
  - Repository secret `ZENODO_TOKEN`: token from zenodo.org
    (not sandbox — production)
  - Repository secret `WORKFLOW_TRIGGER_PAT`: fine-grained PAT
    with `Contents: read+write` + `Actions: write` on the repo,
    used by daily-CI to trigger the Zenodo workflow on tag push
  - Repository variable `APP_TITLE`, `APP_KEYWORD`,
    `ZENODO_CONCEPT_DOI`

Rheum side will configure these at start of W3. Onc side: please
configure same on your repo by W3 Mon (2026-05-26).

### (3) `CITATION.cff` ownership

Each app maintains its own `CITATION.cff` at the repo root. The
Zenodo workflow updates it on each snapshot deposit (DOI bump).
Reasonable but worth confirming: should the file include just the
maintainer's authorship, or also list contributors automatically
(via GitHub API at deposit time)?

Default proposal: **maintainer-only authorship** in CITATION.cff
through v1.0; revisit if external contributors materialise. Onc:
push back if your preprint co-author list changes that.

## §6 — Communication protocol post-W1

Cross-app sync rounds are **paused** after W1 starts. Concrete
rules:

  - **Async-by-default**: PRs in the shared repo are reviewed by
    whichever maintainer has bandwidth that week
  - **Synchronous touch-points** (~30 min each, max 4 over the
    20 weeks):
      - W8 Wed (ChiCTR schema confirmation)
      - W13 Wed (REST API OpenAPI spec confirmation)
      - W17 Mon (EU CTR adapter assignment)
      - W20 Wed (v1.0.0 release readiness)
  - **Out-of-band escalation**: if either app finds a regression
    in a shared package release that blocks production, file a
    GitHub issue with `[urgent-cross-app]` label and tag both
    maintainers. Expected response time: 24h.
  - **Status updates**: each app's CHANGELOG.md entries serve as
    the cross-app status feed. Skim weekly; no separate stand-up.

## §7 — GO criteria

Both sides confirm by replying:

```
<<ROUND-3-ACK>>
- Owner table (§2): accepted as-stated
- Kickoff checklists (§3, §4): accepted
- Operational decisions (§5): (1) confirmed / (2) confirmed /
                               (3) <maintainer-only OR auto-contributor>
- Communication protocol (§6): accepted

GO. W1 starts Mon 2026-05-12.
```

Or push back on any specific item; I'll iterate.

## What this brief explicitly does NOT cover

(So neither side wonders if it's been forgotten):

  - Outcome data integration (Cortellis-tier feature) — explicitly
    deferred per the eight-axis analysis; revisit at v1.0
  - Steering committee outreach — relationship work, not
    engineering; happens in parallel without affecting the technical
    timeline
  - Mobile-responsive layouts — Bucket B, async per app, no
    coordination needed
  - Accessibility audit (WCAG AA) — Bucket B, async per app

These remain on the eight-axis roadmap as Bucket-B / longer-term.
The W1-W20 plan focuses on Bucket A (joint infra) and the items
that genuinely need synchronous coordination.

--- END PROMPT ---
