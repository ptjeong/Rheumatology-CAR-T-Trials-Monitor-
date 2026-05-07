# What would elevate this app to professional grade

A reviewer with experience using BioMedTracker / Cortellis / ClinicalTrials.gov
or contributing to a EULAR/ACR registry would judge this dashboard along eight
axes. Below: where the app currently sits, the gap to professional grade, and
the highest-leverage moves to close it.

The TL;DR is at the bottom (a 12-item "do these next" list).

---

## Axis 1 — Data quality & trustworthiness

**Where we are now**
- Single source: ClinicalTrials.gov API v2
- Classifier: rule-based keyword tables + OIM-cluster broadening + named-
  product lookup + LLM overrides
- 21-trial locked benchmark with per-axis F1 floors
- Inter-rater κ validation study infrastructure (6 axes, 100-trial sample)
- Per-trial classification confidence + drilldown rationale

**What's missing**
1. **Multi-registry cross-referencing.** CT.gov is North-America-centric;
   ChiCTR (China), jRCT (Japan), EU CTR (Europe), WHO ICTRP (global) all carry
   trials that never appear in CT.gov. A SLE CAR-T trial that exists only on
   ChiCTR is invisible today. ASGCT Q1 2026 reported 100 active non-onc CD19
   programs; we currently see ~80% of that, with the gap concentrated in
   non-US trials.
2. **Trial-level audit log.** Every classification change should be timestamped
   with the rule that fired (and the input fields). Right now the snapshot
   shows the *current* label but not *why this label, when, and by what
   change*. Reviewers asking "why did NCT06xxxxx flip from CD19 to BAFF-R
   on 2026-04-27?" can't answer from the artifact.
3. **Discrepancy alerting.** When the same trial appears in multiple
   registries with conflicting fields (different phase, different enrollment,
   different sponsor), surface the conflict explicitly — don't silently
   prefer one source.
4. **Sensitivity analyses.** "What if we re-classify all `Unclear` product
   types as Autologous?" "What if we exclude all single-trial sponsors?" The
   downstream figures should be available with these toggles.

**Why this matters**
A reviewer for a Lancet methods paper will ask: how do you know your sample
is complete? Today the answer is "CT.gov plus our exclusion filter, which
captures most but not all." Professional grade is "we cross-reference 5
registries and resolve conflicts via [documented procedure]; missing-trial
rate is bounded at < N% per [method]."

---

## Axis 2 — Analytical depth

**Where we are now**
- 11 publication figures + ~30 Deep Dive figures
- Cross-tabs (Disease × Target, Disease × Sponsor type, Country × Disease)
- Cohort × phase mix
- Top-3 sponsor share (concentration proxy)
- Paediatric coverage gap with blind-spot callouts
- Phase-progression Sankey

**What's missing**
1. **Outcome data.** No primary-endpoint results, no safety signals (CRS,
   ICANS rates), no efficacy data (CR/ORR). The dashboard tracks the
   *pipeline* (what trials exist) but not the *evidence* (what they show).
   For a rheumatologist deciding whether CAR-T is an option for refractory
   SLE, "100 trials are running" is less useful than "of 12 completed trials,
   median CR rate is X%, CRS grade ≥3 in Y%".
2. **Publication linkage.** Every NCT should auto-link to its PubMed papers
   (where they exist). NCT-to-PMID linkage is queryable via NLM's services;
   it's a 1-day implementation but a substantial credibility lift.
3. **Recruiting velocity / time-to-event.** A "Recruiting" trial with a
   2021 start year is probably stalled. We have the start year and current
   status; we don't surface the implication.
4. **Predictive flags.** "Trials likely to complete in 2027" is a
   straightforward classifier (start year + phase + status + enrollment
   target). Adds genuine intelligence, not just description.
5. **Sponsor pipeline depth.** "Sponsor X has 8 trials across 4 diseases"
   is currently visible. "Sponsor X spends 60% of their pipeline on CD19"
   is the next-level insight.
6. **Statistical rigour in comparisons.** The side-by-side comparator
   shows numbers but no test (Fisher's exact for phase-mix difference,
   Wilcoxon for enrollment-distribution difference, etc.). Adding a test
   strip below each comparator pair would professionalise the section.

**Why this matters**
Descriptive figures are necessary but not sufficient. A pharma competitive-
intelligence team will ask: "what are the likely top-5 first-in-disease
approvals in 2027?". The dashboard should be able to answer.

---

## Axis 3 — Reproducibility & transparency

**Where we are now**
- Snapshot system with date-stamped CSVs
- PRISMA flow + auto-generated methods text
- 175-test pytest suite
- Public source code on GitHub
- Validation κ study (when complete)
- Zenodo DOI on the repo

**What's missing**
1. **Per-snapshot DOI.** Each snapshot should have its own Zenodo DOI so a
   paper citing "snapshot 2026-04-25" lands at an immutable archived
   artifact. Zenodo's GitHub integration plus a release-on-snapshot workflow
   gets this in ~2 hours.
2. **Reproducibility container.** A `Dockerfile` that pins the Streamlit
   version + dependencies + snapshot, runnable in one command. Reviewers
   downloading the container today get a working dashboard instance for the
   exact paper version.
3. **Test coverage report.** 175 tests is great but coverage is unknown.
   Adding coverage.py + a CI badge would publicly attest to quality.
4. **CI on every snapshot rebuild.** Right now the snapshot is rewritten
   manually (commit `670de88` rewrote it after a classifier fix). A GitHub
   Action that rebuilds on a daily schedule with provenance per run would
   formalise this.
5. **Pre-registration of analyses.** For any figure the dashboard
   auto-renders for a forthcoming paper, pre-register the spec on OSF before
   the snapshot freezes.

**Why this matters**
The reproducibility delta between "good enough for a lab notebook" and
"good enough for Lancet" is mostly tooling: DOIs, containers, CI, OSF.
Each individually is a few hours; together they unlock methods-paper
acceptance.

---

## Axis 4 — Clinical rigour & domain authority

**Where we are now**
- Single maintainer (rheum/onc background)
- Closed-vocab disease ontology aligned with rheum-clinical convention
- Disclaimer that the tool is not for clinical decisions
- Some collaboration via GitHub issues

**What's missing**
1. **Specialty-society endorsement.** A short ("EULAR Big Data Network
   liaison" / "ACR registry advisor") line in the About tab dramatically
   changes how the tool is perceived. Reach out to DGRh / EULAR registry
   working groups.
2. **Co-authored ontology.** The disease entity / target / modality
   vocabularies should be co-developed with at least one immunologist outside
   the maintainer's institution. Add their name + affiliation to the
   ontology table.
3. **Validated case definitions.** Where ACR/EULAR criteria exist (RA, SLE,
   AAV, IIM), link to them and document how the dashboard's classification
   maps onto the criteria.
4. **IRB review of the validation κ study.** Not strictly required since
   no patient data, but documented IRB exemption letter is a credibility
   marker.
5. **Conflicts of interest disclosure.** Even if "none" — explicit COI
   statement makes the tool feel professional.

**Why this matters**
Single-person tools get dismissed regardless of code quality. A short
sentence "Ontology reviewed by [Name 1, EULAR registry], [Name 2, ACR
data committee]" turns the tool from a personal project into a community
resource.

---

## Axis 5 — UI/UX polish

**Where we are now**
- 7 top-level tabs, 5 Deep Dive sub-tabs
- Sunburst + heatmaps + lines + boxes + Sankey
- High-contrast palette toggle
- PNG/SVG export
- Functional but Streamlit-y feel

**What's missing**
1. **Saved-state URLs.** Encode filter selections in query params so users
   can share `?disease=SLE&target=CD19` URLs. Streamlit `st.query_params`
   makes this ~100 LOC.
2. **Onboarding tour.** First-time visitor sees a 4-step walkthrough:
   "this is the sunburst, this is filters, this is the data tab,
   this is publication figures." Streamlit has community packages
   (`streamlit-tour-component`) for this.
3. **Search with fuzzy matching.** Today the user clicks dropdowns;
   adding a single search bar that finds NCT IDs, sponsor names, disease
   aliases ("Lupus" → SLE) raises the perceived sophistication a lot.
4. **Saved presets.** "My SLE-only view" / "China industry trials" as
   named filter sets, persistable per user (via session_state for now,
   per-user database later).
5. **Print stylesheet / PDF export.** A "Download as PDF" button that
   exports the current state as a multi-page PDF. Streamlit doesn't do
   this natively; a workaround: render the figures + tables as HTML +
   client-side print-to-PDF.
6. **Mobile responsive layout.** The dashboard is desktop-only today.
   Streamlit's mobile rendering is poor; an iframe-friendly mobile
   variant or a separate Lite endpoint would help.
7. **Accessibility (WCAG AA).** Alt text on all charts (the high-contrast
   palette helps but isn't enough), proper landmark roles, keyboard
   navigation. Streamlit doesn't expose all these out of the box; some
   custom CSS + `aria-*` attributes via markdown injection would help.
8. **Loading states.** Replace spinners with skeleton UI.

**Why this matters**
A reviewer using the dashboard on an iPad at a conference will judge it
mostly on UX. Saved URLs + search + onboarding are ~1 day of work and
move the perceived quality from "research code" to "product".

---

## Axis 6 — Infrastructure & operations

**Where we are now**
- Streamlit Cloud (free tier)
- Snapshots in git (CSV files)
- LLM overrides in single JSON
- No CI, no monitoring, no automated rebuilds

**What's missing**
1. **Daily snapshot automation.** GitHub Action that runs at 03:00 UTC,
   fetches the API, runs the classifier, diffs against the previous snapshot,
   commits, and posts a summary issue. Closes the loop without human
   intervention.
2. **Production database.** SQLite or Postgres backing store with proper
   schema, indexes, full-text search. CSV is fine for 286 trials but breaks
   at 10k+. Migrating now (preemptively) is cheaper than later.
3. **REST API.** FastAPI alongside Streamlit, exposing
   `GET /trials?disease=SLE&phase=PHASE2`, `GET /trials/{nct}`,
   `GET /snapshots/{date}/manifest`. Makes the dashboard a *data product*,
   not just a UI.
4. **Monitoring.** Uptime, error rate, snapshot freshness as a public
   status page (status.rheum-car-t-trial-monitor.streamlit.app).
5. **Backup strategy.** Right now a hostile force-push to main (or a bug)
   could destroy work. Daily backup to S3/GCS would mitigate.
6. **Rate limiting & auth on the API.** Once the API exists, rate limit it
   (100 req/h anonymous, more with API key) and document the policy.

**Why this matters**
Every professional dashboard has a backend, scheduled jobs, and an API. A
Streamlit-only deployment caps the audience at "people who'll click through
a UI"; adding an API opens it to "any researcher who wants programmatic
access".

---

## Axis 7 — Community & governance

**Where we are now**
- Single maintainer
- GitHub Issues for community flags
- κ validation infrastructure for inter-rater agreement
- Curation-loop CSV for human-in-the-loop refinement

**What's missing**
1. **Steering committee.** 3-5 people across clinical / methods /
   infrastructure who meet quarterly. Empowered to approve ontology changes,
   review the roadmap, and disable the tool if data quality slips.
2. **Public roadmap.** A single GitHub Project board with "now / next /
   later" columns, updated quarterly. Lets the community see where the
   tool is heading.
3. **Contribution guidelines.** `CONTRIBUTING.md` covering: how to file a
   trial-classification correction, how to propose an ontology change, how
   to submit a PR, what review looks like.
4. **Code of conduct.** Standard `CODE_OF_CONDUCT.md` (Contributor
   Covenant). Required for grant funding and most institutional hosting.
5. **Funding & sustainability plan.** Documented "the dashboard runs on
   $X/month, funded by [source]". Without this, the tool is one
   maintainer-burnout away from going dark.

**Why this matters**
A single-maintainer tool, even an excellent one, is institutionally fragile.
Granting bodies, journals, and clinical societies all weight "is there a
sustainability plan?" highly.

---

## Axis 8 — Publication & dissemination

**Where we are now**
- Auto-generated methods text in the app
- CSV provenance headers
- Citation block in About tab
- Zenodo DOI on the repo

**What's missing**
1. **Companion methods paper.** A peer-reviewed paper describing the
   dashboard's methodology — classification ontology, validation results,
   figure generation, reproducibility infrastructure. Submitted to
   *Journal of Open Source Software*, *Bioinformatics*, or *PLoS ONE*.
2. **Quarterly state-of-the-pipeline reports.** Auto-generated PDF /
   preprint at each quarter end summarising the last 3 months of
   pipeline activity. Posted to bioRxiv / medRxiv.
3. **Conference presentations.** Submit to ACR, EULAR, ASGCT, ASH. A poster
   cycle dramatically increases legitimacy.
4. **Social media presence.** Auto-posted updates ("12 new trials added
   this week, top entrants: [list]") on Mastodon / Bluesky / Twitter.
5. **Media kit.** When a journalist asks about the autoimmune-CAR-T
   landscape, having a ready-to-cite figure + caption + contact
   information packaged at `dashboard.com/media` saves hours and ensures
   accurate quoting.

**Why this matters**
Tools that aren't published are tools that don't exist as far as academic
discoverability is concerned. A companion methods paper is the single
biggest move toward "professional grade" perception.

---

## Prioritised "do these next" list (12 items)

Ordered by impact-per-hour. Each is ≤ 1 working day unless noted.

1. **Saved-state URLs** — encode filters in `st.query_params`. Single best
   UX win. ~1 day.
2. **Per-snapshot Zenodo DOI** — GitHub Action on snapshot commit. ~2 hours.
3. **NCT → PubMed publication linkage** — adds outcome context. ~1 day.
4. **CONTRIBUTING.md + CODE_OF_CONDUCT.md + CHANGELOG.md** — standard files.
   ~2 hours.
5. **Limitations section** in About tab + Methods narrative — explicit list
   of known gaps. ~1 hour.
6. **Stalled-trial flag** — Recruiting status + start year ≥ 3 years ago.
   ~2 hours.
7. **Search bar** — fuzzy lookup of NCT / sponsor / disease aliases. ~4 hours.
8. **Daily snapshot CI** — GitHub Action with automated classifier rerun
   and diff posting. ~1 day.
9. **REST API endpoint** — FastAPI sidecar. ~2 days.
10. **Multi-registry cross-reference** — start with ChiCTR (highest
    rheum-CAR-T volume after CT.gov). ~3 days.
11. **Companion methods paper** — JOSS submission. ~2 weeks.
12. **Steering committee outreach** — 3-5 named clinical/methods leads.
    Mostly relationship work; no engineering effort.

---

## Quick-wins I can implement immediately

If you want me to start now, I'd suggest:

  - **Saved-state URLs** (highest UX impact, 1-day effort)
  - **Stalled-trial flag** (genuine analytic addition, 2-hour effort)
  - **CONTRIBUTING / CODE_OF_CONDUCT / CHANGELOG** (signal of seriousness, 2-hour effort)
  - **Limitations section** in About + auto-Methods (transparency, 1-hour effort)

Total ~1.5 days to ship all four. Each substantially raises the perceived
rigour without expanding scope.
