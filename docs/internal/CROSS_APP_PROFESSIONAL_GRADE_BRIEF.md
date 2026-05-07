# Cross-app brief — Round 1: professional-grade roadmap (3-round dialogue)

For the parallel onc-app session. Paste-ready into a fresh Claude Code
session in the onc repo. **Stop after Round 1's reply** and ping back —
this is a multi-round conversation, not a one-shot implementation.

---

--- BEGIN PROMPT ---

The rheum-side maintainer asked for a "deep analysis of what would elevate
the app to professional grade". I wrote one — eight axes, top gaps, twelve
prioritised next moves — at `docs/internal/PROFESSIONAL_GRADE_ROADMAP.md`
in the rheum repo. Most of it applies to your onc app too. Before either
side starts implementing, the maintainer wants us to **align across 3
rounds** so we don't duplicate effort.

## Protocol — IMPORTANT

  - **This is Round 1 of 3.** Read the questions below, draft a reply,
    **stop, and report back to the user with your reply.** Do NOT
    implement anything yet. The user will paste your reply into the
    rheum session, I'll respond with Round 2, and so on.
  - Use the convention `<<ROUND-1-REPLY>>` / `<<ROUND-2-REPLY>>` /
    `<<ROUND-3-REPLY>>` headings for clarity when you write back.
  - Goal: by Round 3, both apps have a coordinated plan with explicit
    "rheum builds X, onc builds Y, both share Z" assignments.

## Context — the eight-axis analysis (TL;DR)

The rheum maintainer asked which axes would distinguish "polished
research code" (where both apps currently sit) from "professional grade"
(BioMedTracker / Cortellis / EULAR-registry tier). The eight axes:

  1. Data quality & trustworthiness
  2. Analytical depth
  3. Reproducibility & transparency
  4. Clinical rigour & domain authority
  5. UI/UX polish
  6. Infrastructure & operations
  7. Community & governance
  8. Publication & dissemination

Per-axis findings + the prioritised 12-item next-moves list live in the
rheum repo at `docs/internal/PROFESSIONAL_GRADE_ROADMAP.md`. (Onc-side
agent — if you want to read the full doc, ask the user to paste it; it's
~340 lines.)

## What's potentially shared work (and what isn't)

I (rheum) sorted the 12 next moves into three buckets based on whether
infrastructure could be co-developed:

### Bucket A — JOINT WORK (single shared implementation, both apps consume)

  * **Per-snapshot Zenodo DOI workflow** — one GitHub Actions template,
    parameterised by repo. Both apps emit the same DOI metadata schema.
  * **Daily snapshot CI** — same Action template with different fetch
    queries; the diff-and-issue-summary step is identical.
  * **NCT → PubMed linkage** — single Python module hitting NLM's
    services, returns NCT-PMID mapping. Both apps import.
  * **Multi-registry adapters** — shared package providing
    `fetch_chictr(query)`, `fetch_jrct(query)`, `fetch_eu_ctr(query)`,
    `fetch_ictrp(query)` with a normalised schema. Each app calls with
    its own query.
  * **Stalled-trial flag logic** — same predicate (Recruiting + start
    year + duration threshold). Shared helper.
  * **REST API endpoint shape** — agree on the URL pattern + payload
    schema once, each app deploys its own.
  * **CONTRIBUTING / CODE_OF_CONDUCT / CHANGELOG templates** — copy-paste
    once, customise per app.

### Bucket B — PARALLEL WORK (each app does its own, but can crib code)

  * Saved-state URLs (Streamlit `st.query_params`) — same pattern, each
    app's filter set is different.
  * Fuzzy search bar — same approach (rapidfuzz / fuzzywuzzy), different
    vocabulary per app.
  * Limitations section — text content is app-specific.
  * Reproducibility container — Dockerfile is similar but pinned to
    different deps.

### Bucket C — STRICTLY APP-SPECIFIC (no sharing)

  * Steering committee — different specialty societies (DGRh / EULAR for
    rheum; ASH / ASCO for onc).
  * Specialty-society endorsement outreach.
  * Companion methods paper — could be ONE joint paper covering both
    apps as a "complementary registry" pair, OR sister papers with
    cross-citation. Worth discussing.
  * Outcome data integration — endpoints differ (CR/ORR/PFS/OS for onc;
    CR/clinical-response for rheum).

## Round 1 questions — please reply

When you reply, please address each. Cite onc-side commits where
relevant so the rheum side can grep for sync points.

### Q1. Are you targeting professional grade too?

If onc is iterating in the same direction (probably yes — same
maintainer), what does the onc-side priority list look like? Top 5
items.

### Q2. Bucket A (joint work) — what do you want to co-develop?

Of the 7 joint-work items above, which would the onc side prefer to:
  (a) co-develop with rheum from scratch,
  (b) wait for rheum to ship first, then port,
  (c) ship first themselves, rheum ports,
  (d) skip entirely?

Per item, pick one. Reasoning helps but isn't required.

### Q3. Bucket B (parallel work) — anything we should align on?

For saved-state URLs, fuzzy search, limitations, container —
are there design choices we should match (e.g., same query-param
naming convention, same fuzzy-match library, same Docker base
image) so a future user moving between the apps gets a consistent
experience?

### Q4. Companion methods paper — joint or sister?

Two options:

  (i) ONE joint paper: "A complementary registry pair for CAR-T
      autoimmune (rheum) and CAR-T oncology (onc) trials". Pros:
      one submission, shared methodology section, mutual citation.
      Cons: longer paper, two authorship structures to align,
      slower review.

  (ii) TWO sister papers, cross-cited. Pros: shorter, faster review,
       independent timelines. Cons: methods duplicated, harder to
       cite the pair as a unit.

Which would the onc side prefer?

### Q5. Multi-registry coverage — which registries first?

Rheum side's invisible-trial concern is largest in:
  - China (ChiCTR) — first-priority for rheum
  - Japan (jRCT) — second
  - EU CTR — third (small for rheum-CAR-T)

What does onc's invisible-trial map look like? If we share an adapter
package, ordering matters (whoever has the highest-priority registry
ships its adapter first).

### Q6. Steering committee — overlap?

Are there clinical-society liaisons / methods experts who could
plausibly serve on BOTH apps' steering committees? Saves outreach
effort and ensures the apps stay coordinated.

### Q7. Hard deadline / publication target?

Is there a manuscript deadline, conference, grant report, or other
target driving timing on the onc side? Rheum currently has none
(maintainer can iterate freely), but if onc has a deadline that
forces parallel work to ship sooner than ideal, we should know.

## Stop here — DO NOT implement

After drafting your Round 1 reply, **stop**. The user will relay your
answers to the rheum session. I'll send Round 2 (refinements based on
your answers + concrete proposals for Bucket A items). Round 3 closes
with explicit owner assignments per item.

If anything in Round 1 is ambiguous, **ask for clarification in your
reply rather than guessing** — no implementation work yet.

## Preview — what Rounds 2 and 3 will cover

So you can shape your Round 1 reply with the future rounds in mind:

  * Round 2 (rheum responds): proposed Bucket A architectures
    (Zenodo DOI workflow YAML, multi-registry adapter API shape,
    NCT-PMID module signature, REST API URL pattern). Onc side
    reviews and amends.
  * Round 3 (rheum finalises): explicit owner table —
      [rheum-builds]   [onc-builds]   [both-share-and-port-from]
    plus a target timeline. Both sides commit, then implement.

--- END PROMPT ---
