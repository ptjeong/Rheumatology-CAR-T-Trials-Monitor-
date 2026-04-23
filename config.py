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

# Named product → TargetCategory.  Checked as normalized-substring fallback in _assign_target
# when explicit antigen terms (cd19, bcma, …) are absent from the study text.
NAMED_PRODUCT_TARGETS = {
    "CD19": [
        "caba-201",
        "cc-97540", "cc97540", "zola-cel", "bms-986353",
        "kyv-101", "kyv101",
        "adi-001",
        "ft819",
        "syncar-001",
        "ctx112",
        "cnty-101",
        "azer-cel", "azercabtagene zapreleucel",
        "bms-986515",
        "mb-cart19", "mb-cart2019",
        "ol-cd19-gdt",
        "ytb323", "rapcabtagene autoleucel",
        "rxim002",
        "ti-0032-iii",
        "kn5501",
        # From curation loop validation
        "cnct19",                           # Juventas anti-CD19
        "jy231",                            # CD19 CAR-T (Tongji)
        "kite-363", "kite363",              # Kite/Gilead CD19 for neurological
        "ptoc1",                            # CD19 CAR-T (Chongqing Precision)
        "mc-1-50",                          # CD19 CAR-T (Chongqing Precision)
        "meta10-19",                        # Metabolically armed CD19
        "im19",                             # IM19 CAR-T, CD19
        "scri-car19v3",                     # SCRI pediatric CD19
    ],
    "CD19/BCMA dual": [
        "gc012f",
        # From curation loop validation
        "azd0120",                          # AstraZeneca BCMA/CD19 dual
        "qt-019c", "qt019c",               # QT-019C (CD19/BCMA)
        "prg-2311",                         # PRG-2311 CD19/BCMA (Tongji)
        "fkc288",                           # FKC288 BCMA/CD19 dual kidney
        "scar02",                           # SCAR02 anti-BCMA/CD19
        "rd06-05", "rd0605",               # RD06-05 CD19/BCMA (Bioheng)
        "ben303",                           # CD19/BCMA dual
        "kn5601", "kn5601-k",             # anti-CD19/BCMA CAR-NK (Changhai paediatric)
        "neuk203-215",                      # HD allogeneic CD19/BCMA CAR-NK
    ],
    "CD19/CD20 dual": [
        "ct1192",                           # Universal CD19/20 CAR-T (Beijing GoBroad)
        "ct1195e",                          # Same product family
    ],
    "BCMA": [
        "descartes-08", "decartes-08",
        "prg-1801",
        "hbi0101",
        "s103",
        "ct103a",
        "equecabtagene autoleucel", "eque-cel",
    ],
    "BCMA/CD70 dual": [
        "bcma/cd70",
        "cd70/bcma",
        "bcma-cd70",
        "cd70-bcma",
    ],
    "BAFF": [
        "lmy-920", "lmy920",               # BAFF-ligand CAR-T (Luminary Therapeutics)
    ],
    "CAR-Treg": [
        "ben301",                           # BEN301 CAR-Treg (Foxp3+, Beijing Boren)
    ],
    "CD7": [
        "rd13-02",                          # Universal CD7 CAR-T (Bioheng; SAA, T1DM)
    ],
    "CAR-T_unspecified": [
        "ct1190b",                          # Target unclear from accessible text
        "lcar-aio",                         # Target unclear (Union Hospital)
        "ol-108",                           # Target unclear (Beijing GoBroad)
        "afn50",                            # Target unclear (AlphaNa / Beijing Boren)
        "evm18001",                         # Target unclear (Union Hospital)
        "f01",                              # Target unclear (Shanghai Simnova)
        "ht01",                             # Target unclear
        "brl-301",                          # Universal CAR-T for SLE (target not public)
        "qt-019b",                          # Dual-target allo (distinct from qt-019c)
        "rn1201",                           # Allogeneic CAR-T (target unspecified)
        "inaticabtagene autoleucel",        # Autologous for SLE-ITP (target not public)
        "sys6020",                          # CAR-T for MG (target not disclosed)
        "lucar-g79d", "lucar-g79",          # T-cell products (Linnaean Bio)
        "athena car-t",                     # ATHENA CAR-T for SLE (target not public)
    ],
    "Other_or_unknown": [
        "lucar-dks1",                       # NK-cell product, antigen undisclosed
        "sbt777101",                        # HS treatment (Starpax Bio)
    ],
}

# Named product → ProductType.  Checked as fallback in _assign_product_type when generic
# autologous/allogeneic markers are absent.  Order matters: In vivo checked first.
NAMED_PRODUCT_TYPES = {
    "In vivo": [
        "rxim002",
        "ti-0032-iii",
        "cptx2309",
        "hn2301", "hn2302",                 # MagicRNA mRNA-LNP in vivo CAR-T
    ],
    "Allogeneic/Off-the-shelf": [
        "cc-97540", "cc97540", "zola-cel", "bms-986353",
        "adi-001",
        "ft819",
        "ctx112",
        "cnty-101",
        "bms-986515",
        "kn5501",
        # From curation loop validation
        "azd0120",                          # AstraZeneca iPSC-derived allogeneic
        "ct1192", "ct1195e",               # Universal CD19/20 CAR-T (GoBroad/Tongji)
        "kn5601", "kn5601-k",             # CAR-NK (Changhai, allogeneic NK)
        "cht101",                           # Universal anti-CD70 CAR-T (Nanjing)
        "rd06-05", "rd0605",               # Universal CAR-T (Bioheng)
        "qt-019c", "qt019c",               # CD19/BCMA allogeneic
        "gt719",                            # Universal iNKT (Grit Biotechnology)
        "neuk203-215",                      # HD allogeneic CD19/BCMA CAR-NK
        "brl-301",                          # Universal CAR-T (allogeneic) for SLE
        "lucar-dks1",                       # Allogeneic NK-cell product
        "lucar-g79d", "lucar-g79",          # Allogeneic T-cell products
        "rd13-02",                          # Universal CD7 CAR-T (allogeneic)
        "qt-019b",                          # Allogeneic dual-target CAR-T
        "rn1201",                           # Allogeneic CAR-T (autoimmune)
    ],
    "Autologous": [
        "caba-201",
        "kyv-101", "kyv101",
        "gc012f",
        "descartes-08", "decartes-08",
        "hbi0101",
        "s103",
        "ct103a",
        "syncar-001",
        "mb-cart19", "mb-cart2019",
        "ol-cd19-gdt",
        # From curation loop validation
        "cnct19",                           # Juventas autologous CD19
        "jy231",                            # Autologous CD19 (Tongji)
        "ptoc1",                            # Autologous CD19 (Chongqing Precision)
        "mc-1-50",                          # Autologous CD19
        "meta10-19",                        # Autologous metabolically armed CD19
        "im19",                             # Autologous IM19
        "scri-car19v3",                     # Autologous SCRI pediatric CD19
        "prg-2311",                         # Autologous CD19/BCMA dual (Tongji)
        "fkc288",                           # Autologous BCMA/CD19
        "scar02",                           # Autologous anti-BCMA/CD19
        "lmy-920",                          # Autologous BAFF-ligand CAR-T
        "ben301",                           # Autologous CAR-Treg
        "inaticabtagene autoleucel",        # Autologous for SLE-ITP
        "ytb323", "rapcabtagene autoleucel", # Novartis autologous CD19 (Juno)
        "kite-363", "kite363",              # Kite/Gilead autologous CD19
    ],
}