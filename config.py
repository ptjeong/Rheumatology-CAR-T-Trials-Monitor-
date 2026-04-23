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
    "IIM": [
        "idiopathic inflammatory myopathies",
        "idiopathic inflammatory myopathy",
        "IIM",
        "dermatomyositis",
        "polymyositis",
        "myositis",
        "immune-mediated necrotizing myopathy",
        "IMNM",
        "anti-synthetase syndrome",
        "antisynthetase syndrome",
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
    "Sjogren": [
        "sjogren syndrome",
        "sjogren's syndrome",
        "primary sjogren's syndrome",
        "primary sjogren syndrome",
        "primary sjögren syndrome",
        "relapsed/refractory sjogren's syndrome",
        "rheumatoid arthritis (RA) and sjogren's disease (SjD)",
    ],
    "AAV": [
        "ANCA vasculitis",
        "ANCA-associated vasculitis",
        "ANCA associated vasculitis",
        "AAV",
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
        "recurrent or refractory IgG4 related diseases",
    ],
    "Behcet": [
        "behcet disease",
        "behcet's disease",
    ],
}

GENERIC_AUTOIMMUNE_TERMS = [
    "autoimmune disease",
    "autoimmune diseases",
    "autoimmune disorders",
    "refractory autoimmune diseases",
    "relapsed/refractory autoimmune diseases",
    "autoimmune rheumatologic disease",
    "rheumatic diseases",
    "b-cell mediated autoimmune disorders",
    "systemic autoimmune disease",
    "systemic autoimmune diseases",
]

EXCLUDED_INDICATION_TERMS = [
    "multiple sclerosis",
    "myasthenia gravis",
    "neuromyelitis optica",
    "nmosd",
    "pemphigus vulgaris",
    "al amyloidosis",
    "multiple myeloma",
    "anti-gbm",
    "anti gbm",
    "antiphospholipid syndrome",
    "immune thrombocytopenie",
    "immune thrombocytopenia",
    "aiha",
    "graves disease",
    "membranous nephropathy",
    "tumor",
    "tumors",
    "cancer",
    "cancers",
    "malignancies",
    "malignan",
    "leukemia",
    "lymphoma",
    "solid tumor",
    "solid tumors",
    "advanced solid",
    "b-cell malignancies",
    "b cell malignancies",
    "hematopoetic",
    "stem cell transplant",
    "stem cell transplantation",
    "advanced cancers",
    "relapsed refractory b-cell",
]

HARD_EXCLUDED_NCT_IDS = {
    "NCT07284433", "NCT0594912", "NCT06825455", "NCT06643221", "NCT05302037",
    "NCT06742593", "NCT03294954", "NCT05377827", "NCT05949125", "NCT06871410",
    "NCT07040982", "NCT06323525", "NCT06481735", "NCT02028455", "NCT03971799",
    "NCT04416984", "NCT05256641", "NCT05554939", "NCT07070219", "NCT06682793",
    "NCT06861348", "NCT05640271", "NCT07441291", "NCT07087847", "NCT07464483",
    "NCT06802406", "NCT02129543",
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
    ],
}

CAR_NK_TERMS = [
    "car-nk",
    "car nk",
]

CAAR_T_TERMS = [
    "caar-t",
    "caar t",
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
]

AUTOL_MARKERS = [
    "autologous",
    "patient-derived",
    "patient derived",
    "patient-specific",
    "patient specific",
]