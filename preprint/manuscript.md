---
title: "CAR-T cell therapy across rheumatic and immune-mediated disease: a global registry-derived landscape (snapshot 2026-04-25)"
author: "Peter Jeong"
affiliation: "Klinik I für Innere Medizin, Hämatologie und Onkologie, Klinische Immunologie und Rheumatologie, Universitätsklinikum Köln, Köln, Germany"
correspondence: "peter.jeong@uk-koeln.de"
target: "RMD Open — Original Article"
snapshot_date: "2026-04-25"
code_commit: "540b9c1"
zenodo_doi: "10.5281/zenodo.19713049"
status: "DRAFT — Abstract to be written last; references in skeleton form"
---

# Abstract

*[To be drafted last; placeholder structure with target numbers]*

**Background.** *(~50 words on the gap)*

**Methods.** Reproducible registry-derived landscape analysis of CAR-T and related cell-therapy trials in autoimmune and rheumatic disease, drawn from ClinicalTrials.gov API v2 on 2026-04-25 and classified through a four-layer pipeline (LLM override, named-product lookup, keyword regex, CAR-core fallback) into seven L1 disease families with disease-level L2 detail. Tool, source code, and frozen snapshot are publicly available (DOI 10.5281/zenodo.19713049).

**Findings.** Two hundred eighty-four CAR-T autoimmune trials were included after exclusion of 78 oncology, indication-mismatch, and curated false-positive records. Trial initiation grew from a single trial in 2019 to 101 in 2025 (full year) and 41 in the first four months of 2026. Connective tissue disease (n=104, 36.6%) and basket/multidisease platforms (n=98, 34.5%) co-dominated; SLE alone accounted for 79 trials (27.8% of all trials, 76% of CTD). Neurologic autoimmune disease was the largest non-rheumatic disease cluster (n=43, 15.1%), led by myasthenia gravis (n=18) rather than multiple sclerosis (n=11). Vasculitis (n=5, 1.8%) and inflammatory arthritis (n=3, 1.1%) were profoundly under-represented. CD19 monotherapy (n=128, 45.1%) and CD19/BCMA dual-targeting (n=76, 26.8%) accounted for 71.8% of trials. Allogeneic and autologous platforms reached parity in 2025-initiated trials (allogeneic 41.6%, autologous 48.5%); in-vivo CAR emerged in 2024 and rose to 12.2% of 2026-initiated trials. China hosted 178 of 256 country-attributed trials; the rest of East Asia, North America, and Europe followed at lower density.

**Conclusion.** *(~50 words synthesising the landscape and forward look)*

**Keywords.** CAR-T cell therapy; chimeric antigen receptor; autoimmune disease; systemic lupus erythematosus; clinical trials registry; landscape analysis

---

# 1 · Introduction

The 2022 first-in-human report of CD19-directed chimeric antigen receptor (CAR) T cell therapy for refractory systemic lupus erythematosus (SLE) [Mackensen2022] established a new mechanistic paradigm: deep B-cell depletion, including tissue-resident populations not reached by anti-CD20 antibodies, can reset autoimmune pathology and induce drug-free remission. Within three years, single-centre and early-phase reports extended this approach to idiopathic inflammatory myopathy, systemic sclerosis, ANCA-associated vasculitis, and a heterogeneous group of antibody-mediated immune-mediated diseases [Müller2024; Mackensen2023; Schett2024]. In parallel, neurologic indications — most prominently myasthenia gravis, multiple sclerosis, neuromyelitis optica spectrum disorder (NMOSD), and antibody-mediated encephalitis — emerged as a second major arena for cellular B-cell depletion [Granit2023; Haghikia2024].

The development pipeline has diversified at the platform level as rapidly as it has expanded across indications. Autologous CD19 CAR-T therapies derived directly from oncology programmes were joined within months by allogeneic off-the-shelf products, in-vivo lipid-nanoparticle-delivered CAR mRNA, CAR natural killer (NK) cells, chimeric autoantibody receptor T cells (CAAR-T), regulatory CAR-T cells (CAR-Treg), and dual-target constructs aimed at deepening B-cell and plasma-cell depletion [Bucci2024; Cabaletta2024]. The result is a simultaneously broadening and deepening pipeline whose contours are difficult to track from individual trial reports or topical narrative reviews.

Existing landscape descriptions have so far been narrative or single-disease in focus, and rarely tied to a reproducible registry pull. ClinicalTrials.gov is the most complete prospective record of investigator- and sponsor-registered cell therapy trials, and its application programming interface (API v2) supports queryable, time-stamped extraction. We are not aware of a published systematic registry-derived landscape covering CAR-T cell therapy across autoimmune and rheumatic disease as of 2026.

We therefore developed an open-source classification pipeline and accompanying interactive monitor that ingests ClinicalTrials.gov v2 daily, classifies each trial against a curated ontology of 19 disease entities and 12+ antigen-target categories, and emits PRISMA-style provenance for every figure and export. The aim of the present analysis is a frozen, reproducible snapshot of the global CAR-T autoimmune trial landscape on 2026-04-25, with attention to (i) disease coverage across a hierarchical seven-family classification, (ii) antigen-target and cell-therapy modality mix, (iii) geographic distribution, and (iv) temporal trajectory across 2019–2026. The companion live tool, source code, and frozen dataset are publicly available [Jeong2026Zenodo]. A more detailed methodologic and validation paper is in preparation; here, methodology is summarised and validation is reported in the supplement.

---

# 2 · Methods

## 2.1 Data source and search strategy

Trial records were drawn from ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2/studies`) on 2026-04-25. The query combined CAR-T cell-therapy terminology (CAR T, CAR-T, chimeric antigen receptor, CAR-NK, CAAR-T, CAR-Treg, in-vivo CAR) with autoimmune and rheumatic disease indications, plus broader autoimmune fallbacks for basket and multi-disease trials. The full search expression and the named-product alias index are reproduced in [supp.md] §S1. The API returned records in pages of 200, cycled with `nextPageToken` until exhaustion. We applied no date filter; the 2026-04-25 snapshot date is recorded as a per-row provenance field (`SnapshotDate`).

## 2.2 Inclusion and exclusion

A trial was included if its `Conditions`, `BriefTitle`, `BriefSummary`, or `Interventions` text matched at least one of nine systemic autoimmune indications (SLE, systemic sclerosis [SSc], Sjögren disease, idiopathic inflammatory myopathy [IIM], "connective tissue disease, other" [CTD_other], ANCA-associated vasculitis [AAV], rheumatoid arthritis [RA], IgG4-related disease, Behçet disease) or one of seven non-rheumatologic immune-mediated indications (type 1 diabetes, chronic graft-versus-host disease [cGVHD], hidradenitis suppurativa, multiple sclerosis, myasthenia gravis, chronic inflammatory demyelinating polyneuropathy [CIDP], hereditary haemophagocytic lymphohistiocytosis), or matched a generic basket descriptor ("autoimmune disease," "B-cell-mediated autoimmune disease," "systemic autoimmune disease") in combination with a CAR-T modality term. Trials whose text matched two or more distinct systemic indications were classified as Basket/Multidisease.

Exclusions were applied in three layers. First, a curated list of 15 oncology and haematological-malignancy keyword stems (lymphoma, leukaemia, myeloma, B-cell malignancy, solid tumour, stem-cell transplant context, etc.) removed records whose primary indication was malignancy. Second, a hard-exclusion list of 29 NCT IDs removed manually verified false positives (CAR-T for transplant desensitization, observational-only records, trispecific engagers, tumour-context registry entries). Third, large-language-model (LLM)-derived per-trial overrides flagged as `exclude` with high or medium confidence by a Claude (`claude-opus-4-7`) second-opinion run on borderline classifications were applied [Jeong2026Zenodo]. Of 362 records identified, 35 were hard-excluded, 43 were excluded by indication keyword filters, 0 were excluded by LLM-derived rules, and 284 were included (Figure 1A).

## 2.3 Classification pipeline

For each included trial, four classification layers were applied in order, with the first match retained:

1. **Per-NCT LLM override.** A per-trial JSON record produced by `validate.py` (Claude `claude-opus-4-7`, with a constrained schema for disease entity, target category, product type, and confidence) takes precedence when the override is high- or medium-confidence and not flagged for exclusion.
2. **Named-product lookup.** A curated dictionary of approximately 70 engineered CAR-T products (e.g. obecabtagene autoleucel, rapcabtagene autoleucel, KYV-101) maps a longest-match alias to a canonical target, modality, and product type.
3. **Keyword regex on normalized text.** Antigen targets (CD19, BCMA, CD20, CD70, CD6, CD7, BAFF, dual combinations) and modalities (autologous, allogeneic, in-vivo, CAR-NK, CAR-Treg, CAAR-T) are matched on a normalized version of the combined text fields with word-boundary guards.
4. **CAR-core fallback.** Trials whose text confirms a CAR-T modality but for which no specific antigen target is identified are labelled `CAR-T_unspecified`; trials whose text confirms an autoimmune indication but no clear modality are labelled `Unclear`.

Disease entities were grouped into seven L1 families: Connective tissue (SLE, SSc, Sjögren, IIM, CTD_other, IgG4-RD), Inflammatory arthritis (RA), Vasculitis (AAV, Behçet), Neurologic autoimmune (multiple sclerosis, myasthenia gravis, NMOSD, antibody-mediated encephalitis [AIE], CIDP, MOGAD, stiff-person syndrome, Neurology_other), Other autoimmune (autoimmune cytopenias, glomerular/renal, endocrine autoimmune, dermatologic autoimmune, GVHD), Basket/Multidisease, and Other/Unclassified. Trials whose pipeline-emitted entity was a non-specific "Other immune-mediated" or "cGVHD" label and whose text matched a curated neurologic-autoimmune pattern were promoted to the Neurologic autoimmune L1 family; remaining sub-buckets (cytopenias, glomerular, endocrine, dermatologic, GVHD) were retained as L2 labels under Other autoimmune. Within Neurologic autoimmune, a second-level classifier assigned a specific disease label (MS, Myasthenia, NMOSD, AIE, CIDP, MOGAD, Stiff-person) or a `Neurology_other` fallback in the case of multi-match or non-match.

## 2.4 Outputs

The pipeline emits a per-trial dataframe with NCT identifier, brief title, conditions, interventions, brief summary, primary endpoints, lead sponsor and sponsor sector (Academic, Industry, Government, Other), phase, overall status, start year, last-update date, enrollment count, age group, countries (pipe-delimited), and the classification fields (disease entity, target category, product type, sponsor type, classification confidence, trial design [single-disease vs basket/multidisease]). A second site-level dataframe records per-facility country, city, geocoded latitude and longitude, and recruitment status. Each export carries a `#`-prefixed provenance header with the snapshot date, applied filter state, included row count, and source URL.

## 2.5 PRISMA-style flow

A trial-selection ledger is computed at run-time and recorded as `prisma.json`: records identified, after de-duplication on NCT identifier, after each exclusion class, and finally included. The 2026-04-25 ledger is shown in Figure 1A.

## 2.6 Validation

A stratified random sample of 100 trials drawn proportional to L1 family was independently re-classified by a single rater (P.J.) blinded to the pipeline output, with parallel LLM second-opinion. Cohen's κ for disease entity, target category, and product type, together with confusion matrices, are reported in [supp.md] §S3. Validation is summarized here without full results pending the companion methodology paper.

## 2.7 Statistical analysis

Analyses are descriptive. Counts are reported as n (%) of the analytic cohort (n=284) unless otherwise specified. Modality shift over time is summarized as the share of trials initiated each calendar year by `ProductType`; 2019–2026 are reported, with 2026 explicitly flagged as a partial year (snapshot 2026-04-25). Compound annual growth rate (CAGR) of cumulative trials between 2019 and the most recent complete year (2025) is computed as (cumulative₂₀₂₅/cumulative₂₀₁₉)^(1/6) − 1. No inferential testing on the registry itself was performed.

## 2.8 Reproducibility

Source code is publicly available at the project repository (commit `540b9c1`); the analytic dataset is the file `snapshots/2026-04-25/trials.csv` together with `sites.csv`, `prisma.json`, and `metadata.json`. A live continuously-updated monitor is hosted at `https://rheum-car-t-trial-monitor.streamlit.app`, with a "Frozen snapshot" toggle that loads the deposited 2026-04-25 dataset. The repository, frozen snapshot, and figure-generation script are archived under DOI 10.5281/zenodo.19713049.

---

# 3 · Results

## 3.1 Cohort assembly and overall growth

Three hundred sixty-two trial records identified by the search expression were reduced to 284 after exclusion of 35 hard-excluded false positives, 43 indication keyword excluded records, and 0 LLM-derived exclusions (Figure 1A). No duplicates on NCT identifier were observed. Trial initiation rose from a single registered trial in 2019 to 82 in 2024, 101 in 2025, and 41 in the first four months of 2026 (Figure 1B; cumulative trajectory). The compound annual growth rate of cumulative trials from 2019 to 2025 was 99.6%. Overall, 163 of 284 trials (57.4%) were actively recruiting on 2026-04-25, 66 (23.2%) were not yet recruiting, 20 (7.0%) were active and not recruiting, and 19 (6.7%) had been suspended, terminated, or withdrawn.

## 3.2 Disease landscape

Connective tissue disease and basket/multidisease platforms co-dominated the landscape (Figure 2). Connective tissue disease accounted for 104 trials (36.6%), of which SLE represented 79 (27.8% of all trials and 76.0% of the connective tissue disease family), followed by IIM (n=11), SSc (n=9), CTD_other (n=2), IgG4-related disease (n=2), and Sjögren disease (n=1). Basket/multidisease trials, which by definition recruited across two or more systemic indications, accounted for a further 98 trials (34.5%); their disease coverage by definition spans the rheumatologic and non-rheumatologic boundary.

Neurologic autoimmune disease was the largest non-rheumatologic and non-basket cluster, with 43 trials (15.1%). Within neurologic autoimmune, myasthenia gravis was the leading disease-level entity (n=18), followed by multiple sclerosis (n=11), NMOSD (n=2), and stiff-person syndrome (n=1), with 11 trials in the `Neurology_other` fallback (autoimmune encephalitis, CIDP, MOGAD, or unspecified neurologic autoimmune). Other autoimmune indications grouped under a fifth family included autoimmune cytopenias (n=16), glomerular/renal disease (n=6), endocrine autoimmune disease (n=6), dermatologic autoimmune disease (n=2), and GVHD (n=1) (Figure 2; Table 1).

Two L1 families were strikingly thin. Vasculitis was represented by only 5 trials (1.8%; AAV and Behçet combined). Inflammatory arthritis (RA) was represented by 3 trials (1.1%), of which two were CAR-Treg studies. Both gaps were marked relative to the contribution of these disease groups to global rheumatology disease burden and to the volume of biological-DMARD pipelines they support.

The temporal expansion of the landscape across 2019–2026 was driven principally by connective tissue disease (chiefly SLE), with basket/multidisease platforms accelerating from 2024 onwards and neurologic autoimmune entering the pipeline in volume from 2023 (Figure 3).

## 3.3 Antigen target landscape

The antigen-target landscape was concentrated. CD19-directed monotherapy accounted for 128 trials (45.1%); CD19/BCMA dual-targeting accounted for a further 76 (26.8%). Together, CD19 and CD19/BCMA dual constructs represented 204 of 284 trials (71.8%) and dominated the target ranking by a wide margin (Figure 4). Pure plasma-cell-directed approaches were less common: BCMA monotherapy accounted for 18 trials (6.3%), BCMA/CD70 dual for 3 (1.1%), and CD70 monotherapy for 1.

Other dual constructs included CD19/CD20 (n=12, 4.2%) and CD19/BAFF (n=1). Niche targets included CD7 (n=5), CD20 monotherapy (n=3), CD6 (n=2), and BAFF monotherapy (n=2). Specialised cell-therapy formats — CAR-Treg (n=3) and CAAR-T (n=2) — comprised a small minority. Eighteen trials (6.3%) confirmed a CAR-T modality without disclosing a specific target (`CAR-T_unspecified`); 10 (3.5%) used non-canonical or undisclosed targets (`Other_or_unknown`).

Distribution of target classes by family confirmed CD19-driven design across all rheumatologic families and the neurologic autoimmune family, with dual CD19/BCMA constructs concentrated in basket/multidisease platforms aimed at simultaneous depletion of memory B cells and long-lived plasma cells.

## 3.4 Cell-therapy modality and temporal shift

Cumulatively, autologous CAR-T cells accounted for 184 trials (64.8%), allogeneic off-the-shelf products for 81 (28.5%), in-vivo CAR therapies (lipid-nanoparticle-delivered CAR mRNA or related modalities) for 14 (4.9%), and 5 (1.8%) trials were classified `Unclear` (Figure 5A). Autologous trials predominated cumulatively, but the modality mix shifted sharply over the observation window (Figure 5B).

Trials initiated in 2019–2022 were uniformly autologous (n=14 across the four years). The first allogeneic trials appeared in 2023 (3 of 15 trials initiated, 20.0%). In 2024, allogeneic trials accounted for 13 of 82 (15.9%) and one in-vivo CAR trial appeared. In 2025, autologous and allogeneic platforms reached near-parity in newly initiated trials: 49 of 101 (48.5%) were autologous and 42 (41.6%) were allogeneic, with 8 (7.9%) in-vivo. In the first four months of 2026, 23 of 41 trials initiated (56.1%) were autologous, 13 (31.7%) were allogeneic, and 5 (12.2%) were in-vivo.

We therefore identify 2025 as the inflection year at which auto-monopoly of the CAR-T autoimmune pipeline ended, with allogeneic platforms approaching half of newly initiated trials and in-vivo CAR-T entering double-digit percentage share.

## 3.5 Global geography

Country information was available for 256 of 284 trials (90.1%); 28 trials had no country recorded. China was by far the most common location, hosting 178 trials, followed by the United States (n=59), Germany (n=20), France (n=15), Spain (n=15), the United Kingdom (n=14), Australia (n=13), Canada (n=9), Italy (n=9), and Switzerland (n=7) (Figure 6A, 6B). The remaining countries each hosted seven or fewer trials.

By region (counted as trial–country pairs, since some trials list multiple countries), East Asia hosted 187 trial-country pairs, Europe 108, North America 68, Oceania 13, and the rest of the world 21. The regional share by start year (Figure 6C) showed China-led East Asia accounting for the majority of trial-country activity since 2024; European fragmentation across 15 countries with low individual-country density; and a relatively stable North American share of approximately 20–25% over the observation window. Germany led Europe, but at a fraction of China's volume.

## 3.6 Trial design and sponsor structure

The 2026-04-25 cohort was firmly in early-phase development (Figure 7). Phase 1 trials accounted for 104 of 284 (36.6%), Early Phase 1 for 86 (30.3%), and Phase 1/2 for 47 (16.5%). Only 13 trials (4.6%) were Phase 2, 2 (0.7%) Phase 2/3, and 3 (1.1%) Phase 3. Phase information was not registered or assigned for 29 trials (10.2%).

Lead sponsor sector was Academic for 154 trials (54.2%) and Industry for 130 (45.8%); fewer than five were Government or Other. The Academic-Industry split varied by phase: Academic predominated in Early Phase 1 (64 of 86, 74.4%), while Industry led in Phase 1 (54 of 104, 51.9%) and Phase 1/2 (30 of 47, 63.8%). Of the small Phase 2+ cohort, Industry led 14 of 18 trials. The leading sponsors and named products are reproduced in Table 2; 186 trials (65.5%) were single-disease and 98 (34.5%) were basket/multidisease in design.

---

# 4 · Discussion

This registry-derived snapshot of CAR-T cell therapy in autoimmune and rheumatic disease on 2026-04-25 captures a pipeline that has expanded by approximately two orders of magnitude in five years (1 trial initiated in 2019; cumulative 284 by April 2026) and has simultaneously diversified along the disease, target, modality, and geography axes. We highlight four findings with implications for clinicians, trialists, and the rheumatology research community.

## 4.1 CTD–basket co-dominance and the SLE concentration

We had hypothesised a connective-tissue-disease-dominated landscape; the actual snapshot is more accurately described as a co-dominance of connective tissue disease (104 trials, 36.6%) and basket/multidisease platforms (98, 34.5%). Within connective tissue disease, three quarters of trials are SLE-focused — a single-disease concentration that reflects the centrality of SLE as the proof-of-concept indication for CAR-T mediated B-cell reset. Industry-driven basket platforms now match the entire connective-tissue family in volume, indicating that platform sponsors are increasingly wagering on CAR-T as a class therapy for B-cell-driven autoimmunity rather than as a sequence of single-disease bets. For clinicians, this implies that referral pathways for refractory SLE are now broadly competitive across academic and industry trials, while patients with rarer connective tissue indications (Sjögren disease, IgG4-related disease) remain dependent on basket-style enrolment.

## 4.2 Indication gaps relative to disease burden

Two L1 families are strikingly under-represented: vasculitis (n=5; AAV and Behçet combined) and inflammatory arthritis (n=3; rheumatoid arthritis only). The mismatch with global disease burden — RA alone affects an estimated 0.5–1.0% of adults and dominates rheumatology biological-DMARD spend — is notable, and worth flagging as a strategic gap. The under-representation of RA is in part explainable: existing biological and small-molecule DMARDs deliver high response rates and the regulatory bar for CAR-T as a deep-rather-than-broad B-cell intervention is unclear in a disease where response, not refractoriness, is the modal outcome. The under-representation of AAV is harder to defend on these grounds, since severe and relapsing AAV resemble SLE in their dependence on long-lived autoreactive B-cell clones and the scarcity of treatment options at the refractory end of the spectrum [vandenBrand2023]. Three of the five vasculitis trials are AAV-focused; we anticipate this number to grow rapidly.

## 4.3 Modality inflection in 2025

The auto-monopoly of the CAR-T autoimmune pipeline ended in 2025. Allogeneic off-the-shelf platforms rose from 0% of trials initiated in 2022 to 41.6% of trials initiated in 2025, at near-parity with autologous (48.5%). In-vivo CAR therapies, which would in principle eliminate ex-vivo manufacturing constraints altogether, emerged in 2024 and accounted for 12.2% of trials initiated in the first four months of 2026. Whether this shift translates into deployable, scalable therapy depends on outcomes of the early allogeneic readouts (lymphodepletion intensity, persistence, immunogenicity, infection signal) and on the regulatory framework for in-vivo CAR mRNA, both of which remain in flux. From a pipeline-design perspective, the inflection should be read as a sponsor-level bet that CAR-T can only be a class therapy for autoimmune disease if its manufacturing constraints can be relaxed; auto-only platforms scale with apheresis capacity, whereas allo and in-vivo platforms scale with vector and product manufacturing capacity.

## 4.4 The China-led geography and what it does not mean

China hosted 178 of 256 country-attributed trials. Several caveats apply. First, ClinicalTrials.gov registration is not synonymous with active recruitment; Chinese investigator-initiated trials may register early and recruit slowly. Second, the volume of academic Chinese CAR-T trials reflects a long-standing investigator-initiated culture in CAR-T cell therapy that pre-dates the autoimmune pivot. Third, multi-country registration is uncommon in the Chinese subset, so the share of trial-country pairs may overstate global activity concentration. With these caveats, the broader pattern is robust: the East Asia–Europe–North America hierarchy is steeper than the autoimmune-disease burden distribution would predict, and Europe is fragmented, with each country (including Germany, the European leader) hosting only a small fraction of the Chinese volume. Whether this pattern translates into eventual approvals and patient access in non-Chinese markets is an open question, but the emergent pattern resembles the 2017–2020 oncology CAR-T pipeline trajectory, in which Chinese registration volume preceded but did not directly translate into a corresponding regulatory approval cadence outside China [Wang2021CAR-T].

## 4.5 Limitations

Five limitations bear emphasis. First, ClinicalTrials.gov registration is not enrollment, and the 2026-04-25 cohort tells us about pipeline composition rather than actual patient exposure. Second, classification noise is unavoidable in a registry-text-driven pipeline; we mitigated it with named-product lookups, LLM second opinion, and a curation loop, with validation κ reported in the supplement, but residual misclassification — particularly within the basket/multidisease bucket and the `Neurology_other` fallback — should be assumed. Third, the temporal cuts use `StartDate`, which is itself imputed conservatively when the registry record is incomplete. Fourth, multi-country trials are recorded as a single row with a pipe-delimited country list; the regional analysis (Figure 6C) is therefore on trial–country pairs, not weighted trials, and slightly inflates regional shares for highly multi-country trials. Fifth, the underlying registry has an English-language and US-/EU-centric registration norm; non-Anglophone activity outside the major registries is under-captured. We do not attempt to correct for these biases beyond flagging them.

## 4.6 Outlook

The CAR-T autoimmune pipeline is no longer in proof-of-concept: it is in industrial scale-up with an auto-to-allo-to-in-vivo modality transition under way, an SLE-anchored connective-tissue concentration with expanding neurologic and basket arms, and persistent gaps in vasculitis and inflammatory arthritis that we expect to be filled within the next 12–24 months. We do not expect the geographic concentration in East Asia to invert in the short term, but we anticipate the European share to grow incrementally as academic centres (including German consortia) bring locally manufactured allogeneic products into Phase 1/2 testing. Continuous registry-level surveillance — of which the present analysis is one snapshot — is becoming a useful complement to outcome reporting in keeping the field honest about what is being tried, where, and in which patient population. The companion live tool [Jeong2026Zenodo] is intended to support exactly this kind of recurring readout.

---

# 5 · Display items

**Figure 1.** *Study selection and cumulative growth.* (A) PRISMA-style flow of trial selection from ClinicalTrials.gov API v2 on 2026-04-25. Of 362 records identified, 35 were excluded by a curated hard-exclusion NCT-ID list, 43 by indication keyword filters, and 0 by LLM-derived rules; 284 trials were included. (B) Cumulative number of CAR-T autoimmune trials initiated, stacked by L1 disease family, 2019–2026. Connective tissue (deep navy), Inflammatory arthritis (mid blue), Vasculitis (light blue), Neurologic autoimmune (violet), Other autoimmune (slate-600), Basket/Multidisease (slate-400). 2026 reflects a partial year (snapshot date 2026-04-25). [`figures/preprint/fig1_prisma_growth.pdf`](figures/preprint/fig1_prisma_growth.pdf)

**Figure 2.** *Disease hierarchy of CAR-T trials.* Number of trials per L1 disease family, with within-family L2 segmentation. Family colour ramp (deep navy to light blue) groups rheumatologic indications (CTD, IA, Vasculitis); violet flags Neurologic autoimmune as a separate clinical domain; slate flags non-rheumatologic and basket buckets. Within Neurologic autoimmune, L2 disease labels are MS, Myasthenia, NMOSD, AIE, CIDP, MOGAD, Stiff-person, Neurology_other. Within Other autoimmune, L2 sub-family labels are Cytopenias, Glomerular/renal, Endocrine, Dermatologic, GVHD. n=284. [`figures/preprint/fig2_disease_hierarchy.pdf`](figures/preprint/fig2_disease_hierarchy.pdf)

**Figure 3.** *Temporal expansion of CAR-T autoimmune trials by family.* Trials initiated per calendar year, 2019–2026, stacked by L1 disease family (palette as in Figure 2). 2026 reflects the first four months of the year (snapshot 2026-04-25). [`figures/preprint/fig3_temporal_by_family.pdf`](figures/preprint/fig3_temporal_by_family.pdf)

**Figure 4.** *Antigen-target landscape.* Top 15 antigen-target categories among 284 CAR-T autoimmune trials, coloured by target class: B-cell-directed (CD19, CD20, CD22, BAFF, CD7, CD6; deep navy); plasma-cell-directed (BCMA, CD70; amber); dual constructs (any combination including CD19, BCMA, CD20, BAFF, CD70; teal); other or non-canonical targets (slate); CAR-T modality confirmed but target undisclosed (`CAR-T_unspecified`; light slate). [`figures/preprint/fig4_target_landscape.pdf`](figures/preprint/fig4_target_landscape.pdf)

**Figure 5.** *Cell-therapy modality.* (A) Overall modality mix across the 284-trial cohort: Autologous (deep navy, 64.8%), Allogeneic/Off-the-shelf (teal, 28.5%), In vivo (amber, 4.9%), Unclear (slate, 1.8%). (B) Share of trials initiated each calendar year, 2019–2026, by modality. The 2025 inflection at which auto-monopoly ended and allogeneic platforms reached near-parity is visible. 2026 is partial (snapshot 2026-04-25). [`figures/preprint/fig5_modality.pdf`](figures/preprint/fig5_modality.pdf)

**Figure 6.** *Global geographic distribution.* (A) World choropleth of trials per country (log-scale colour ramp). (B) Top 10 countries by trial count. (C) Regional share of trial–country pairs by start year, 2019–2026: East Asia, Europe, North America, Oceania, Rest of World. China, hosting 178 trials, is the dominant single country. Country information was available for 256 of 284 trials. [`figures/preprint/fig6_geography.pdf`](figures/preprint/fig6_geography.pdf)

**Figure 7.** *Phase by lead-sponsor sector.* Number of trials per phase (Early Phase 1 through Phase 3 plus Phase 1/2 and Phase 2/3 split labels), stacked by lead-sponsor sector (Academic, Industry, Government, Other). The cohort is concentrated in early-phase development (Early Phase 1 + Phase 1 + Phase 1/2 = 237 of 284, 83.5%). Academic and Industry sponsors are near-balanced overall (54.2% vs 45.8%). [`figures/preprint/fig7_phase_sponsor.pdf`](figures/preprint/fig7_phase_sponsor.pdf)

**Table 1.** *Trial counts by L1 disease family, with L2 detail and recruiting status.* See `tables/table1_family_counts.csv` (to be generated from `snapshots/2026-04-25/trials.csv`).

**Table 2.** *Top 10 sponsors and top 15 named CAR-T products with target, modality, lead phase, and lead indication.* See `tables/table2_sponsors_products.csv` (to be generated).

---

# 6 · References (skeleton — to be populated with PMID/DOI)

1. **[Mackensen2022]** Mackensen A, Müller F, Mougiakakos D, et al. Anti-CD19 CAR T cell therapy for refractory systemic lupus erythematosus. *Nat Med.* 2022;28(10):2124–2132.
2. **[Müller2024]** Müller F, Taubmann J, Bucci L, et al. CD19 CAR T-cell therapy in autoimmune disease — a case series with follow-up. *N Engl J Med.* 2024;390:687–700.
3. **[Mackensen2023]** Mackensen A, Müller F, Mougiakakos D, et al. CAR T cells in systemic sclerosis and idiopathic inflammatory myopathy. *(citation to be specified — Schett group SSc/IIM 2023)*.
4. **[Schett2024]** Schett G, Mackensen A, Mougiakakos D. CAR T-cell therapy in autoimmune diseases. *Lancet.* 2023;402:2034–2044.
5. **[Bucci2024]** Bucci L, Hagen M, Rothe T, et al. Bispecific T cell engagers and CAR T cells in autoimmune disease: a comparative perspective. *Nat Rev Rheumatol.* 2024.
6. **[Cabaletta2024]** Aghajanian H, Kimura Y, Rurik JG, et al. In vivo and allogeneic CAR T cell platforms for autoimmunity. *(citation to be specified)*.
7. **[Granit2023]** Granit V, Benatar M, Kurtoglu M, et al. Safety and clinical activity of autologous RNA chimeric antigen receptor T-cell therapy in myasthenia gravis. *Lancet Neurol.* 2023;22:578–590.
8. **[Haghikia2024]** Haghikia A, Hegelmaier T, Wolleschak D, et al. Anti-CD19 CAR T cells for refractory myasthenia gravis. *Lancet Neurol.* 2023;22:1104–1105.
9. **[vandenBrand2023]** *(citation to be specified — refractory AAV B-cell biology)*.
10. **[Wang2021CAR-T]** *(citation to be specified — Chinese CAR-T pipeline registration vs approval analysis)*.
11. **[Jeong2026Zenodo]** Jeong P. CAR-T Rheumatology Trials Monitor (snapshot 2026-04-25). Zenodo. 2026. doi:10.5281/zenodo.19713049.
12. *(~40 additional references to be assembled covering: SLE B-cell biology and CD20-vs-CD19 depletion depth; specific allogeneic CAR-T platforms — Cabaletta CABA-201, Caribou CB-010, Allogene ALLO-501; in-vivo CAR mRNA platforms — Capstan CPTX2309, Umoja UB-VV111, Orna; CAR-Treg platforms — Sangamo, Quell; CAAR-T platforms — Cabaletta DSG3-CAART; basket trial design literature; ClinicalTrials.gov methodology and registry analysis; rheumatologic disease burden references — GBD 2021; specific CAR-T autoimmune disease reports — IIM, AAV, NMOSD, MOGAD, T1D, hidradenitis; safety and toxicity reports; long-lived plasma cell biology — BCMA rationale; CRS/ICANS in autoimmune CAR-T; immune reconstitution and vaccination after CAR-T; PRISMA 2020 guidelines; STROBE for routinely-collected health data.)*

---

# 7 · Funding, disclosures, data availability

**Funding.** None declared.

**Conflicts of interest.** None declared.

**Author contributions.** P.J. designed and built the classification pipeline and dashboard, performed the analysis, drafted the manuscript, and prepared the figures.

**Data and code availability.** The frozen snapshot (`trials.csv`, `sites.csv`, `prisma.json`, `metadata.json`) underlying this analysis is deposited in the project repository at commit `540b9c1` and is available under the same Zenodo DOI as the source code: 10.5281/zenodo.19713049. The live, continuously-updated monitor is hosted at `https://rheum-car-t-trial-monitor.streamlit.app`; the "Frozen snapshot" toggle reloads the deposited 2026-04-25 dataset.

**Patient and public involvement.** Not applicable (registry-derived analysis; no patient data).

**Reporting standards.** A STROBE-adapted reporting checklist for routinely collected registry data is provided as [supp.md] §S4.

---

*Manuscript draft v1.0 — figures locked at commit `540b9c1` + snapshot 2026-04-25. Abstract, Conclusion, and reference DOIs to be finalized.*
