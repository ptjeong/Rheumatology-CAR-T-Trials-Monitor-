DISEASE_ENTITIES = {
    "SLE": [
        "SLE",
        "systemic lupus erythematosus",
        "systemic lupus erthematosus",
        "systemic lupus erythematous",
        "lupus nephritis",
        "refractory lupus nephritis",
        "lupus erythematosus, systemic",
        "lupus",
        "LN",
        "SLE-ITP",
        "recurrent or refractory systemic lupus erythematosus",
        "system lupus erythematosus(SLE)",
    ],
    "SSc": [
        "SSc",
        "systemic sclerosis",
        "systemic scleroderma",
        "scleroderma",
        "diffuse cutaneous systemic sclerosis",
        "SSc-systemic sclerosis",
        "relapsed/refractory systemic sclerosis",
        "recurrent or refractory systemic sclerosis",
    ],
    "Sjogren": [
        "sjogren syndrome",
        "sjogren's syndrome",
        "sjogren disease",
        "primary sjogren",
        "primary sjogren's syndrome",
        "primary sjogren syndrome",
        "primary sjögren syndrome",
        "relapsed/refractory sjogren's syndrome",
        "rheumatoid arthritis (RA) and sjogren's disease (SjD)",
        "SjD",
    ],
    "CTD_other": [
        "connective tissue disease",
        "mixed connective tissue disease",
        "MCTD",
        "undifferentiated connective tissue disease",
        "UCTD",
    ],
    "IIM": [
        "idiopathic inflammatory myopathies",
        "idiopathic inflammatory myopathy",
        "juvenile idiopathic inflammatory myopathy",
        "IIM",
        "dermatomyositis",
        "polymyositis",
        "myositis",
        "immune-mediated necrotizing myopathy",
        "immune mediated necrotizing myopathy",
        "IMNM",
        "anti-synthetase syndrome",
        "antisynthetase syndrome",
        "anti synthetase syndrome",
        "inflammatory myopathy",
        "inflammatory myopathies",
        "juvenile dermatomyositis",
        "juvenile myositis",
        "juvenile polymyositis",
        "relapsed/refractory idiopathic inflammatory myopathies",
        "recurrent or refractory idiopathic inflammatory myopathy",
        "idiopathic inflammatory myopathies (IIM)",
        "connective tissue disease-associated interstitial lung disease",
    ],
    "AAV": [
        "ANCA vasculitis",
        "ANCA-associated vasculitis",
        "ANCA associated vasculitis",
        "AAV",
        "GPA",
        "MPA",
        "granulomatosis with polyangiitis",
        "microscopic polyangiitis",
        "ANCA-associated glomerulonephritis",
        "antineutrophil cytoplasmic antibody-associated vasculitis",
        "anti-neutrophil cytoplasmic antibody-associated vasculitis",
        "granulomatous polyangiitis",
        "recurrent or refractory ANCA associated vasculitis",
    ],
    "RA": [
        "rheumatoid arthritis",
        "RA",
    ],
    "IgG4-RD": [
        "IgG4 related disease",
        "IgG4-related disease",
        "IgG4-related diseases",
        "IgG4-RD",
        "IgG4 RD",
        "recurrent or refractory IgG4 related diseases",
    ],
    "Behcet": [
        "behcet disease",
        "behcet's disease",
    ],
    "cGVHD": [
        "chronic graft versus host disease",
        "chronic graft versus host",
        "chronic graft-versus-host disease",
        "chronic graft-vs-host disease",
        "chronic gvhd",
        "cgvhd",
    ],
}
# NOTE on the two-vocabulary design (Phase 3 of REVIEW.md / SSOT):
# `DISEASE_ENTITIES` here is the AUTHORITATIVE full-synonym map per entity,
# used (a) by validate.py / validate_independent_llm.py as the closed-vocab
# enum the LLM must emit, and (b) as the LATE-fallback substring-match
# table inside `pipeline._classify_disease` (synonyms longer than 3 chars).
# The PRIMARY high-precision word-boundary match table inside pipeline.py
# (`_DISEASE_TERMS`) is intentionally LEANER — it carries only the canonical
# / unambiguous variants so short tokens like "lupus" or "ra" don't false-
# positive on overlapping text. Keys MUST stay aligned across the two maps
# (asserted by tests/test_classifier.py::TestVocabularyParity).

GENERIC_AUTOIMMUNE_TERMS = [
    "autoimmune disease",
    "autoimmune diseases",
    "autoimmune disorders",
    "refractory autoimmune diseases",
    "relapsed/refractory autoimmune diseases",
    "autoimmune rheumatologic disease",
    "rheumatic diseases",
    "b-cell mediated autoimmune disorders",
    "b-cell related autoimmune diseases",
    "b cell-related autoimmune diseases",
    "paediatric b cell-related autoimmune diseases",
    "relapsed/refractory b cell-mediated autoimmune diseases",
    "systemic autoimmune disease",
    "systemic autoimmune diseases",
]

OTHER_IMMUNE_MEDIATED_TERMS = [
    # Neurological autoimmune (specific)
    "multiple sclerosis",
    "neuromyelitis optica",
    "nmosd",
    "myasthenia gravis",
    "chronic inflammatory demyelinating polyneuropathy",
    "chronic inflammatory demyelinating polyradiculoneuropathy",
    "cidp",
    "autoimmune encephalitis",
    "stiff person syndrome",
    "stiff-person syndrome",
    "mogad",
    "myelin oligodendrocyte glycoprotein",
    # Neurological autoimmune (broad)
    "neurological autoimmune diseases",
    "neurologic autoimmune diseases",
    "neurologic immune disorders",
    "neurological immune disorders",
    # Endocrine
    "type 1 diabetes",
    "stage 3 type 1 diabetes",
    "t1d",
    "graves disease",
    # Dermatological
    "pemphigus vulgaris",
    "pemphigus",
    # Renal
    "anti-gbm",
    "anti gbm",
    "goodpasture",
    "membranous nephropathy",
    "membranous glomerulonephritis",
    "iga nephropathy",
    # Haematological (non-malignant)
    "autoimmune hemolytic anemia",
    "aiha",
    "immune thrombocytopenia",
    "immune thrombocytopenie",
    "aplastic anemia",
    "severe aplastic anemia",
    # Thrombotic / coagulation
    "antiphospholipid syndrome",
    "antiphospholipid antibody",
    # Inflammatory / other immune-mediated
    "hemophagocytic lymphohistiocytosis",
    "hlh",
    "hidradenitis suppurativa",
    "cppd",
    "calcium pyrophosphate deposition",
]

EXCLUDED_INDICATION_TERMS = [
    # Haematologic malignancies
    "al amyloidosis",
    "multiple myeloma",
    "leukemia",
    "lymphoma",
    "b-cell malignancies",
    "b cell malignancies",
    "hematopoetic",
    "relapsed refractory b-cell",
    # Solid oncology
    "tumor",
    "tumors",
    "cancer",
    "cancers",
    "malignancies",
    "malignan",
    "solid tumor",
    "solid tumors",
    "advanced solid",
    "advanced cancers",
    # Transplant oncology context
    "stem cell transplant",
    "stem cell transplantation",
]

HARD_EXCLUDED_NCT_IDS = {
    "NCT07284433", "NCT0594912", "NCT06825455", "NCT06643221", "NCT05302037",
    "NCT06742593", "NCT03294954", "NCT05377827", "NCT05949125", "NCT06871410",
    "NCT07040982", "NCT06323525", "NCT06481735", "NCT02028455", "NCT03971799",
    "NCT04416984", "NCT05256641", "NCT05554939", "NCT07070219", "NCT06682793",
    "NCT06861348", "NCT05640271", "NCT07441291", "NCT07087847", "NCT07464483",
    "NCT06802406", "NCT02129543",
    # False positives confirmed via curation loop (no CAR-T intervention)
    "NCT07254637",  # Tocilizumab for CPPD — IL-6 inhibitor, not CAR-T
    "NCT05277272",  # HLH disease registry — observational, no intervention
    "NCT06921980",  # Brain/psych assessment in AIHA — observational
    "NCT02445222",  # Generic CAR-T LTFU monitoring — no disease eligibility
    "NCT07251179",  # Autoreactive B-lymphocyte characterisation — blood draw only
    "NCT06888960",  # CC312 — trispecific T-cell engager (TriTE), not a CAR-T construct
    # Round 1 curation additions
    "NCT07451236",  # CD19/BCMA CAR-T for DSA desensitization in transplant — not autoimmune
    "NCT03356782",  # Sarcoma CAR-T — solid tumour oncology, out of scope
    "NCT03369353",  # PREDICT — observational IBD/GvHD study, no CAR-T intervention
}

CAR_CORE_TERMS = [
    "car-t",
    "car t",
    "chimeric antigen receptor",
    "cd19 car",
    "bcma car",
    "anti-cd19 car",
    "anti-bcma car",
    "car-nk",
    "car nk",
    "caar-t",
    "car-treg",
]

CAR_SPECIFIC_TARGET_TERMS = {
    "CD19": [
        "cd19",
        "anti-cd19",
        "cd19-directed",
        "cd19 targeted",
        "cd19-targeted",
        "car19",
    ],
    "BCMA": [
        "bcma",
        "anti-bcma",
        "bcma-directed",
        "bcma targeted",
        "bcma-targeted",
        "b cell maturation antigen",
    ],
    # Ligand-based CAR convention (synced from onc 2026-04-27).
    # BAFF-CAR (LMY-920 etc.) uses BAFF as the binding domain; the
    # receptor on the B cell is BAFF-R / TACI / BCMA. Record the
    # dominant therapeutic receptor (BAFF-R for autoimmune B-cell
    # depletion). Synonyms are construct-anchored (no bare "baff")
    # to avoid false matches in eligibility text discussing BAFF
    # biology.
    "BAFF-R": [
        "baff-r",
        "baff r",
        "baff receptor",
        "tnfrsf13c",
        "baff car",
        "baff-car",
        "baff car-t",
        "baff cart",
        "baff-car-t",
        "baff-cart",
    ],
    "CD20": [
        "cd20",
        "anti-cd20",
        "cd20-directed",
        "cd20 targeted",
    ],
    "CD70": [
        "cd70",
        "anti-cd70",
        "cd70-directed",
        "cd70 targeted",
        "cd70-targeted",
    ],
}

CAR_NK_TERMS = [
    "car-nk",
    "car nk",
]

CAAR_T_TERMS = [
    "caar-t",
    "caar t",
    "caart",    # Matches MuSK-CAART and similar no-hyphen forms
]

CAR_TREG_TERMS = [
    "car-treg",
    "car treg",
]

ALLOGENEIC_MARKERS = [
    "allogeneic",
    "off-the-shelf",
    "off the shelf",
    "universal car-t",
    "universal car t",
    "ucar",
    "ucart",
    "healthy donor",
    "donor-derived",
    "donor derived",
    "allo1",
    "umbilical cord blood",
    "cord blood",
]

AUTOL_MARKERS = [
    "autologous",
    "patient-derived",
    "patient derived",
    "patient-specific",
    "patient specific",
]

# -----------------------------------------------------------------------------
# Named product registry (single source of truth)
# -----------------------------------------------------------------------------
# Each entry captures a single engineered cell-therapy product.  Downstream
# heuristics pull **target**, **type**, and **platform** from this one table
# instead of maintaining parallel dicts — this guarantees consistency and gives
# every classification a traceable evidence trail.
#
# Fields:
#   aliases:  case-insensitive substring patterns matched against the flattened
#             trial text (name, title, intervention description, summary).
#   target:   TargetCategory value used by the app (CD19, BCMA, CD19/BCMA dual, …).
#             Use "CAR-T_unspecified" when antigen is not disclosed publicly.
#   type:     ProductType value (Autologous | Allogeneic/Off-the-shelf |
#             In vivo | Unclear).
#   platform: Modality hint (CAR-T | CAR-NK | CAR-Treg | CAAR-T | CAR-T_γδ |
#             CAR-iNKT | In-vivo_mRNA-LNP).  Overrides the text heuristics in
#             app._modality() for products where text alone is unreliable.
#   sponsor:  Company or academic sponsor (traceability only, not consumed).
#   notes:    Evidence trail — cite NCT IDs and intervention-text snippets that
#             justify the classification.  Prior curators should be able to
#             re-verify each entry in under a minute.
#
# When auditing entries, query ClinicalTrials.gov for the product alias and
# inspect the `interventions[].description` field — that is the highest-fidelity
# source (sponsor-authored, structured) for "autologous" / "allogeneic" /
# "in vivo" and antigen claims.
NAMED_PRODUCTS: dict[str, dict] = {
    # ── CD19 / Autologous CAR-T ───────────────────────────────────────────
    "caba-201": {
        "aliases": ["caba-201", "caba201"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Cabaletta Bio",
        "notes": "Fully human CD19 scFv autologous CAR-T; RESET programme (SLE/IIM/SSc/MG).",
    },
    "bms-986353": {
        "aliases": ["cc-97540", "cc97540", "zola-cel", "bms-986353"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Bristol Myers Squibb",
        "notes": "NCT05869955 (Breakfree-1): 'CC-97540, CD-19-Targeted Nex-T CAR T Cells'; autologous Nex-T platform.",
    },
    "kyv-101": {
        "aliases": ["kyv-101", "kyv101"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Kyverna Therapeutics",
        "notes": "Fully human CD19 scFv autologous CAR-T; SLE/MG/MS/SSc programmes.",
    },
    "syncar-001": {
        "aliases": ["syncar-001", "syncar001"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Synthekine",
        "notes": "Autologous CD19 CAR-T with orthogonal IL-2 receptor (STK-009).",
    },
    "mb-cart19": {
        "aliases": ["mb-cart19"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Miltenyi Biotec / academic",
        "notes": "Miltenyi MB-CART19.1 monospecific autologous CD19.",
    },
    "ol-cd19-gdt": {
        "aliases": ["ol-cd19-gdt"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T_γδ",
        "sponsor": "Beijing GoBroad",
        "notes": "Autologous γδ T-cell CD19 CAR-T.",
    },
    "ytb323": {
        "aliases": ["ytb323", "rapcabtagene autoleucel"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Novartis",
        "notes": "T-Charge rapid-manufacture autologous CD19 CAR-T; now in rheumatology trials.",
    },
    "kite-363": {
        "aliases": ["kite-363", "kite363"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Kite / Gilead",
        "notes": "NCT07038447: 'A single infusion of CAR-transduced autologous T cells'.",
    },
    "cnct19": {
        "aliases": ["cnct19"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Juventas",
        "notes": "Juventas autologous CD19 (Inaticabtagene predecessor).",
    },
    "inaticabtagene autoleucel": {
        "aliases": ["inaticabtagene autoleucel"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Juventas Cell Therapy",
        "notes": "Autologous CD19 CAR-T (SLE-ITP, B-NHL); 'autoleucel' INN stem → autologous.",
    },
    "jy231": {
        "aliases": ["jy231"],
        "target": "CD19", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "Tongji University",
        "notes": (
            "NCT06797024: 'JY231 injection is administered intravenously and produces "
            "autologous CAR-T cells in the patient's body some time after infusion' — in vivo LNP-mRNA."
        ),
    },
    "ptoc1": {
        "aliases": ["ptoc1"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Chongqing Precision",
        "notes": "Autologous CD19 CAR-T.",
    },
    "mc-1-50": {
        "aliases": ["mc-1-50"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Chongqing Precision",
        "notes": "Autologous CD19 CAR-T.",
    },
    "meta10-19": {
        "aliases": ["meta10-19"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Academic (Chinese)",
        "notes": "Metabolically-armed autologous CD19 CAR-T.",
    },
    "im19": {
        "aliases": ["im19"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Beijing ImmunoChina",
        "notes": "IM19 autologous CD19 CAR-T.",
    },
    "scri-car19v3": {
        "aliases": ["scri-car19v3"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Seattle Children's",
        "notes": "Autologous CD19 CAR-T paediatric platform; v3 construct.",
    },
    "relma-cel": {
        "aliases": ["relma-cel", "relmacabtagene autoleucel", "jwcar-029"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "JW Therapeutics",
        "notes": "'-autoleucel' stem → autologous; approved as analog of lisocabtagene maraleucel (Breyanzi).",
    },
    "obe-cel": {
        "aliases": ["obecabtagene autoleucel", "obe-cel", "obecel", "aucatzyl"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Autolus Therapeutics",
        "notes": "Autolus autologous CD19 (Aucatzyl, approved for r/r B-ALL); under study in autoimmune.",
    },
    "clbr001": {
        "aliases": ["clbr001"],
        "target": "CD19", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Cullinan Therapeutics",
        "notes": "Autologous CD19 CAR-T (CLBR001 + SWI019); originally oncology, now SLE/lupus nephritis.",
    },

    # ── CD19 / Allogeneic CAR-T ───────────────────────────────────────────
    "ctx112": {
        "aliases": ["ctx112"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "CRISPR Therapeutics",
        "notes": "Next-gen allogeneic CD19 (CRISPR-edited).",
    },
    "bms-986515": {
        "aliases": ["bms-986515"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Bristol Myers Squibb",
        "notes": "NCT07115745: 'Healthy Donor CD19-targeted Allogeneic CAR T Cells'.",
    },
    "azer-cel": {
        "aliases": ["azer-cel", "azercabtagene zapreleucel"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Precision BioSciences / Imugene",
        "notes": (
            "NCT03666000: 'Infusion of Allogeneic Anti-CD19 CAR T cells'; "
            "summary: 'azer-cel, an allogeneic anti-CD19 CAR T'. ARCUS-edited from healthy donors."
        ),
    },
    "brl-301": {
        "aliases": ["brl-301"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "BRL Medicine",
        "notes": "Universal CAR-T with TRAC/B2M KO (Zhongshan Hospital collaboration).",
    },
    "athena car-t": {
        "aliases": ["athena car-t"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Chinese academic (ATHENA consortium)",
        "notes": (
            "NCT06014073/NCT06373991: 'TRAC and Power3 (SPPL3) Genes Knock-out Allogeneic "
            "CD19-targeting CAR-T' from healthy adult volunteer donors."
        ),
    },
    "ata3219": {
        "aliases": ["ata3219"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Atara Biotherapeutics",
        "notes": "EBV-specific T cells engineered with CD19 CAR, allogeneic off-the-shelf.",
    },
    "ft819": {
        "aliases": ["ft819"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Fate Therapeutics",
        "notes": "iPSC-derived allogeneic CD19 CAR-T.",
    },

    # ── CD19 / CAR-NK (allogeneic by construction) ────────────────────────
    "tak-007": {
        "aliases": ["tak-007", "tak007"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Takeda",
        "notes": "Cord-blood-derived CD19 CAR-NK (licensed from MDACC).",
    },
    "cnty-101": {
        "aliases": ["cnty-101"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Century Therapeutics",
        "notes": "iPSC-derived allogeneic CD19 CAR-NK.",
    },
    "kn5501": {
        "aliases": ["kn5501"],
        "target": "CD19", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Kanova / Changhai",
        "notes": "NCT06613490: 'anti CD19 CAR NK cells'.",
    },

    # ── CD19 / γδ CAR-T ───────────────────────────────────────────────────
    # NOTE: adi-001 was previously mistakenly classified as CD19 — evidence
    # from NCT07100873 and NCT04735471 shows 'Anti-CD20 CAR-T'. Corrected below
    # under CD20.

    # ── CD19 / In-vivo CAR ────────────────────────────────────────────────
    "cptx2309": {
        "aliases": ["cptx2309"],
        "target": "CD19", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "Capstan Therapeutics",
        "notes": "mRNA-LNP in vivo CD19 CAR-T reprogramming.",
    },
    "rxim002": {
        "aliases": ["rxim002"],
        "target": "CD19", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "Rxim",
        "notes": "In vivo CD19 LNP-mRNA CAR-T.",
    },
    "ti-0032-iii": {
        "aliases": ["ti-0032-iii"],
        "target": "CD19", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "Triumvira",
        "notes": "In vivo CD19 platform.",
    },

    # ── CD20 ───────────────────────────────────────────────────────────────
    "adi-001": {
        "aliases": ["adi-001"],
        "target": "CD20", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T_γδ",
        "sponsor": "Adicet Bio",
        "notes": (
            "NCT07100873 (RA), NCT04735471 (B-NHL): 'Anti-CD20 CAR-T'; "
            "NCT04911478 long-term follow-up: 'Adicet allogeneic γδ CAR T cell therapy'."
            " *Corrected from prior CD19 misclassification.*"
        ),
    },

    # ── CD19/BCMA dual ────────────────────────────────────────────────────
    "gc012f": {
        "aliases": ["gc012f"],
        "target": "CD19/BCMA dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Gracell / AstraZeneca",
        "notes": "FasT-platform autologous BCMA/CD19 dual (now AstraZeneca post-acquisition).",
    },
    "azd0120": {
        "aliases": ["azd0120"],
        "target": "CD19/BCMA dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "AstraZeneca",
        "notes": (
            "NCT07295847: 'CD19/BCMA Autologous CAR T-cell therapy product'. "
            "*Corrected from prior allogeneic misclassification.*"
        ),
    },
    "qt-019c": {
        "aliases": ["qt-019c", "qt019c"],
        "target": "CD19/BCMA dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Shanghai Qihan",
        "notes": "Allogeneic CD19/BCMA dual CAR-T.",
    },
    "prg-2311": {
        "aliases": ["prg-2311"],
        "target": "CD19/BCMA dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Prologue / Tongji",
        "notes": "Autologous CD19/BCMA dual CAR-T.",
    },
    "fkc288": {
        "aliases": ["fkc288"],
        "target": "CD19/BCMA dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Academic (Chinese)",
        "notes": "Autologous BCMA/CD19 dual CAR-T (kidney indications).",
    },
    "scar02": {
        "aliases": ["scar02"],
        "target": "CD19/BCMA dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Academic (Chinese)",
        "notes": "Autologous BCMA/CD19 dual CAR-T (SLE trials).",
    },
    "rd06-05": {
        "aliases": ["rd06-05", "rd0605"],
        "target": "CD19/BCMA dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Bioheng",
        "notes": "Universal CD19/BCMA dual allogeneic CAR-T.",
    },
    "ben303": {
        "aliases": ["ben303"],
        "target": "CD19/BCMA dual", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Beijing Boren",
        "notes": "CD19/BCMA dual CAR-T; type not publicly disclosed.",
    },
    "kn5601": {
        "aliases": ["kn5601", "kn5601-k"],
        "target": "CD19/BCMA dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Kanova / Changhai",
        "notes": "NCT07283315: 'anti-CD19/BCMA CAR NK cells' (paediatric autoimmune).",
    },
    "neuk203-215": {
        "aliases": ["neuk203-215"],
        "target": "CD19/BCMA dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Academic (Chinese)",
        "notes": "HD-allogeneic CD19/BCMA CAR-NK.",
    },
    "rn1201": {
        "aliases": ["rn1201"],
        "target": "CD19/BCMA dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Academic (Chinese)",
        "notes": (
            "NCT07114432: 'BCMA/CD19-targeted allogeneic CAR-T'. "
            "*Target corrected from prior Unspecified to CD19/BCMA dual.*"
        ),
    },

    # ── CD19/CD20 dual ────────────────────────────────────────────────────
    "ct1192": {
        "aliases": ["ct1192", "ct1195e"],
        "target": "CD19/CD20 dual", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Beijing GoBroad",
        "notes": "NCT07031713/NCT07033299: 'universal CD19/20 CAR-T' (TRAC KO allogeneic).",
    },
    "zamtocabtagene autoleucel": {
        "aliases": ["zamtocabtagene autoleucel", "zamto-cel", "zamtocel", "mb-cart2019"],
        "target": "CD19/CD20 dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Miltenyi Biotec",
        "notes": "MB-CART2019.1 tandem CD19/CD20 autologous; '-autoleucel' → autologous.",
    },
    "lcar-aio": {
        "aliases": ["lcar-aio"],
        "target": "CD19/CD20 dual", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "LegendBio (Union Hospital)",
        "notes": (
            "NCT06653556 (SLE): 'LCAR-AIO T cells'; NCT05292898/NCT05318963 describe "
            "'triple-targeted CD19/CD20/CD22'. Mapped here to CD19/CD20 dual as closest fit. "
            "*Added from prior Unspecified target.*"
        ),
    },

    # ── BCMA ───────────────────────────────────────────────────────────────
    "descartes-08": {
        "aliases": ["descartes-08", "decartes-08"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Cartesian Therapeutics",
        "notes": "mRNA-transfected autologous BCMA CAR-T.",
    },
    "hbi0101": {
        "aliases": ["hbi0101"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Immix BioPharma / Hadassah",
        "notes": "Autologous BCMA CAR-T (AL amyloidosis, SLE).",
    },
    "s103": {
        "aliases": ["s103"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Academic (Chinese)",
        "notes": "Autologous BCMA CAR-T.",
    },
    "ct103a": {
        "aliases": ["ct103a"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "IASO Bio / Innovent",
        "notes": "Fully human BCMA autologous CAR-T; predecessor to equecabtagene autoleucel.",
    },
    "equecabtagene autoleucel": {
        "aliases": ["equecabtagene autoleucel", "eque-cel"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "IASO Bio / Innovent",
        "notes": "Fully human BCMA autologous CAR-T; '-autoleucel' stem → autologous (approved in China as Fucaso).",
    },
    "prg-1801": {
        "aliases": ["prg-1801"],
        "target": "BCMA", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Prologue / Tongji",
        "notes": "Autologous BCMA CAR-T.",
    },
    "sys6020": {
        "aliases": ["sys6020"],
        "target": "BCMA", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "SystImmune",
        "notes": (
            "NCT06688435 (MG): 'autologous CAR-T cells that have been temporarily transfected "
            "with LNP-mRNA targeting BCMA'. *Target corrected from Unspecified; type set to In vivo.*"
        ),
    },

    # ── BCMA/CD70 dual ────────────────────────────────────────────────────
    "bcma/cd70 dual": {
        "aliases": ["bcma/cd70", "cd70/bcma", "bcma-cd70", "cd70-bcma"],
        "target": "BCMA/CD70 dual", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Academic (pattern-based)",
        "notes": "Pattern-based detection for dual BCMA/CD70 constructs.",
    },

    # ── CD70 (mono) ───────────────────────────────────────────────────────
    "cht101": {
        "aliases": ["cht101"],
        "target": "CD70", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Nanjing Chia Tai Tianqing",
        "notes": "Universal anti-CD70 CAR-T.",
    },

    # ── CD7 ────────────────────────────────────────────────────────────────
    "rd13-02": {
        "aliases": ["rd13-02"],
        "target": "CD7", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Bioheng",
        "notes": "Universal CD7 CAR-T (SAA, T1DM).",
    },

    # ── BAFF ───────────────────────────────────────────────────────────────
    "lmy-920": {
        "aliases": ["lmy-920", "lmy920"],
        "target": "BAFF", "type": "Autologous", "platform": "CAR-T",
        "sponsor": "Luminary Therapeutics",
        "notes": "BAFF-ligand autologous CAR-T (SLE, NHL).",
    },

    # ── CAR-Treg ──────────────────────────────────────────────────────────
    "ben301": {
        "aliases": ["ben301"],
        "target": "CAR-Treg", "type": "Autologous", "platform": "CAR-Treg",
        "sponsor": "Beijing Boren",
        "notes": "Foxp3+ autologous CAR-Treg.",
    },
    "sbt777101": {
        "aliases": ["sbt777101"],
        "target": "CAR-Treg", "type": "Autologous", "platform": "CAR-Treg",
        "sponsor": "Sonoma Biotherapeutics",
        "notes": (
            "NCT07123038 (LTFU): 'Gene-Modified Regulatory T Cell (Treg) Therapeutic'. "
            "*Target/type corrected from Unknown.*"
        ),
    },

    # ── Allogeneic with undisclosed/uncertain target ─────────────────────
    "lucar-dks1": {
        "aliases": ["lucar-dks1"],
        "target": "Other_or_unknown", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-NK",
        "sponsor": "Linnaean Bio",
        "notes": "Allogeneic NK product; antigen not publicly disclosed.",
    },
    "lucar-g79": {
        "aliases": ["lucar-g79d", "lucar-g79"],
        "target": "CAR-T_unspecified", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Linnaean Bio",
        "notes": "Allogeneic T-cell products; target undisclosed.",
    },
    "qt-019b": {
        "aliases": ["qt-019b"],
        "target": "CAR-T_unspecified", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-T",
        "sponsor": "Shanghai Qihan",
        "notes": "Distinct from QT-019C; dual-target allogeneic, specific antigens not fully disclosed.",
    },

    # ── Other / uncertain products (best-effort pass-through) ────────────
    "ct1190b": {
        "aliases": ["ct1190b"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Beijing GoBroad",
        "notes": "Target unclear from accessible text.",
    },
    "ol-108": {
        "aliases": ["ol-108"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Beijing GoBroad",
        "notes": "Target unclear.",
    },
    "afn50": {
        "aliases": ["afn50"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "AlphaNa / Beijing Boren",
        "notes": "Target unclear.",
    },
    "evm18001": {
        "aliases": ["evm18001"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Union Hospital",
        "notes": "Target unclear.",
    },
    "f01": {
        "aliases": ["f01"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Shanghai Simnova",
        "notes": "Target unclear.",
    },
    "ht01": {
        "aliases": ["ht01"],
        "target": "CAR-T_unspecified", "type": "Unclear", "platform": "CAR-T",
        "sponsor": "Unknown",
        "notes": "Target unclear.",
    },

    # ── In vivo / mRNA-LNP platforms (antigen undisclosed) ────────────────
    "hn2301": {
        "aliases": ["hn2301", "hn2302"],
        "target": "Other_or_unknown", "type": "In vivo", "platform": "In-vivo_mRNA-LNP",
        "sponsor": "MagicRNA",
        "notes": "In vivo mRNA-LNP CAR-T platform; antigen undisclosed publicly.",
    },

    # ── Allogeneic iNKT ───────────────────────────────────────────────────
    "gt719": {
        "aliases": ["gt719"],
        "target": "CAR-T_unspecified", "type": "Allogeneic/Off-the-shelf", "platform": "CAR-iNKT",
        "sponsor": "Grit Biotechnology",
        "notes": "Universal iNKT cell-based construct.",
    },
}


# -----------------------------------------------------------------------------
# Derived dictionaries (backward compatibility for pipeline._lookup_named_product)
# -----------------------------------------------------------------------------
# The pipeline code looks up aliases by category, so we materialize the three
# perspectives: target-first, type-first, and platform-first.
def _build_named_product_index(field: str) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for entry in NAMED_PRODUCTS.values():
        cat = entry.get(field)
        if cat is None or cat == "Unclear":
            continue
        idx.setdefault(cat, []).extend(entry["aliases"])
    return idx


NAMED_PRODUCT_TARGETS = _build_named_product_index("target")
NAMED_PRODUCT_TYPES = _build_named_product_index("type")
NAMED_PRODUCT_PLATFORMS = _build_named_product_index("platform")