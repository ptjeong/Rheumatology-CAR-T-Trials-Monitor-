# Dual-focus picker pattern — port brief for the onc app

Self-contained port doc. Drop the section between `BEGIN PROMPT` and
`END PROMPT` into a fresh Claude Code session in the onc-CAR-T-trials
repo. The same UX pattern that landed in rheum (commits `e8c7bbc`
through `95d5737`) brings cross-axis focus to Deep Dive — pick an
antigen AND a modality independently, see the intersection. Useful
for any "narrow on two related dimensions at once" workflow.

## What the pattern does

Two `st.selectbox` pickers sit side-by-side at the top of a Deep
Dive sub-tab. Each represents an independent narrowing axis:

  Picker A: primary focus      (in rheum: antigen target)
  Picker B: secondary filter   (in rheum: modality — Auto / Allo /
                                CAR-NK / CAR-Treg / CAAR-T /
                                CAR-γδ T / in-vivo / unclear)

Either or both can be set. The focused-view dataframe filters
on whichever axes are non-default; the landscape view (cross-axis
heatmap + emergence timeline + phase composition) renders when
BOTH are at default.

Each picker independently URL-binds via `?ft=CD19&ft_mod=Auto`
(or your equivalents), so a reader can deep-link to any combination.

## Why this is good UX

- The reader picks once on each axis; no "ok now switch tabs and
  re-narrow" friction.
- The intersection view reveals cross-axis patterns (e.g., "are
  allogeneic CD19 trials clustering in earlier phases than
  autologous CD19?") that single-axis pickers can't surface.
- It generalises: anywhere two related dimensions are commonly
  cross-cut, the pattern fits. In rheum that's antigen × modality;
  in onc the obvious analogue is antigen × modality (same data
  shape) or perhaps DiseaseCategory × Branch.

## Architecture (rheum implementation)

Six pieces, all in `app.py`:

### 1. URL-binding helpers (already exist in onc)

`_seed_pick_from_query(state_key, options)` and
`_sync_pick_to_query(state_key, no_focus_sentinels)`. Already
present in onc — these are the single-value-selector equivalents
of `_seed_filter_from_query` / `_sync_filters_to_query`. Reuse.

### 2. Add a second `_FOCUS_PICKER_QPARAM` entry

In rheum:

    _FOCUS_PICKER_QPARAM = {
        "dd_target_pick":            "ft",
        "dd_target_modality_pick":   "ft_mod",   # NEW
        ...
    }

For onc, pick a short URL key (`ft_mod` works since onc's antigen
picker already uses `ft`).

### 3. Render the two pickers in a 2-column row

    ct1, ct2 = st.columns(2)
    with ct1:
        _seed_pick_from_query("dd_target_pick", _target_options_sorted)
        target_pick = st.selectbox(
            f"Focus on an antigen target — {len(_antigens_only)} available",
            ["(any — show landscape)"] + _target_options_sorted,
            key="dd_target_pick",
            format_func=lambda t: (
                t if t == "(any — show landscape)"
                else f"{t}  ({_target_counts.get(t, 0)} trials)"
            ),
            help="Leave at '(any — show landscape)' to see all antigens. Pick one to filter to that antigen — combine with the modality picker for cross-axis narrowing.",
        )
        _sync_pick_to_query("dd_target_pick", ("(any — show landscape)",))
    with ct2:
        _seed_pick_from_query("dd_target_modality_pick", _modality_options_dd)
        modality_pick = st.selectbox(
            f"Focus on a modality — {len(_modality_options_dd)} available",
            ["(any)"] + _modality_options_dd,
            key="dd_target_modality_pick",
            help="Applies as an additional filter on top of the antigen pick. Leave at '(any)' for no modality filter.",
        )
        _sync_pick_to_query("dd_target_modality_pick", ("(any)",))

Note the per-pick "N available" counts inline in the labels —
dynamic, no separate metric tile required. The picker option lists
need to be derived from `df_filt` at render time (NOT hardcoded
or cached) so the counts reflect the current sidebar-filter state.

### 4. Compute the focused subset

    focus = df_filt.copy()
    if target_pick != "(any — show landscape)":
        focus = focus[focus["TargetCategory"] == target_pick]
    if modality_pick != "(any)":
        focus = focus[focus["Modality"] == modality_pick]

    # Human-readable label for headings + downloads
    _focus_parts: list[str] = []
    if target_pick != "(any — show landscape)":
        _focus_parts.append(f"target = {target_pick}")
    if modality_pick != "(any)":
        _focus_parts.append(f"modality = {modality_pick}")
    _focus_label = " · ".join(_focus_parts) if _focus_parts else "all trials"

    # Sanitised version for widget keys (alphanumeric only — the
    # sentinel parens in target_pick / modality_pick break Streamlit
    # key validation otherwise)
    def _safe(s: str) -> str:
        return (
            str(s).replace("(", "").replace(")", "")
            .replace(" ", "_").replace("/", "-")
            .replace("—", "any").replace("·", "_")[:40]
        )
    _focus_token = f"t={_safe(target_pick)}_m={_safe(modality_pick)}"

`_focus_label` goes into every chart title and download button
("Trials — target = CD19 · modality = Allogeneic"). `_focus_token`
goes into widget `key=` arguments to keep Streamlit happy.

### 5. Landscape vs focused view

    if target_pick == "(any — show landscape)" and modality_pick == "(any)":
        # Cross-axis landscape: heatmap + emergence timeline +
        # phase composition (all driven by full df_filt)
        ...
    else:
        # Focused view: 4-tile metric strip + drilldown panels +
        # trial table, all driven by `focus` dataframe
        ...

### 6. URL back-compat (optional)

If the onc app already has an antigen picker keyed `dd_target_pick`,
keep that key. The new picker is `dd_target_modality_pick`. Old
bookmarks linking to `?ft=CD19` continue to work; the modality
defaults to `(any)`.

## --- BEGIN PROMPT ---

Port the dual-focus picker pattern (antigen + modality) from the
rheum monitor's Deep Dive → By target sub-tab into the onc app's
equivalent. The pattern is documented at
`https://github.com/ptjeong/Rheumatology-CAR-T-Trials-Monitor-/blob/main/docs/internal/DUAL_FOCUS_PORT_BRIEF_ONC.md`
(this file). Look at rheum's `app.py` lines ~5800-6100 for the
implementation (around the `if _active == "By antigen":` block).

### Concrete steps

1. **Find the antigen-focus block in onc's app.py.** Probably looks
   like `if _active == "By target":` or similar; has a `st.selectbox`
   keyed `dd_target_pick` that drives the antigen drilldown.

2. **Add a modality-options list.** Use onc's existing modality
   vocabulary (the rheum equivalent is `_MODALITY_ORDER` filtered
   to those present in `df_filt["Modality"]`).

3. **Add the second picker** beside the antigen picker. Use
   `st.columns(2)` to lay them out side-by-side. Wire it through
   `_seed_pick_from_query` / `_sync_pick_to_query` for URL state.

4. **Register the new key in `_FOCUS_PICKER_QPARAM`** (or onc's
   equivalent). Pick a short URL key — `ft_mod` is fine.

5. **Compute `focus` by filtering on BOTH axes** as needed (see
   "Compute the focused subset" section above).

6. **Build `_focus_label` and `_focus_token`** for headings + widget
   keys. Threading these through the existing chart titles + CSV
   download buttons + trial-table key= arguments is the bulk of
   the work — ~15 sites in rheum, similar in onc.

7. **Landscape branch** — fires when both pickers are at default.
   Use onc's existing antigen-landscape figures.

### Verification

  - Default state: both pickers at "(any...)" → landscape renders
    correctly.
  - Antigen only: target = CD19, modality = (any) → focused drilldown
    for all CD19 trials.
  - Modality only: target = (any), modality = Allogeneic → focused
    drilldown for all allogeneic trials.
  - Both: target = CD19 + modality = Allogeneic → focused drilldown
    for allogeneic CD19 trials only.
  - URL state: `?ft=CD19&ft_mod=Allogeneic` deep-link round-trips
    correctly across page reload.

### Edge cases handled by the rheum implementation

  - **Empty focus** (no trials match the combination): emit a
    `st.info(f"No trials match {_focus_label}. Broaden the upstream
    sidebar filters if a category is excluded.")` — already in
    rheum's branch for the empty case.
  - **Picker option = "(any — show landscape)" sentinel** containing
    parens / em-dash / spaces: handled by `_safe()` slug-sanitiser
    when building widget keys.
  - **No modality data in snapshot**: the `_modality_options_dd` list
    is empty → only "(any)" appears in the modality picker → it has
    no effect. Graceful degrade.

### Estimated effort

  - 30 min for the picker UI + URL plumbing
  - 30-45 min for threading `_focus_label` / `_focus_token` through
    the existing chart titles + download buttons + widget keys (the
    "boring but careful" portion — ~15 substitution sites)
  - 15 min for verification

Total: 1.25-1.5 hours.

### What this is NOT

  - Not a global cross-tab filter. The modality pick is local to the
    By target tab (in rheum) / By antigen tab (renamed in rheum); it
    doesn't affect Deep Dive's other tabs. That was a deliberate
    decision per user feedback ("there's no cross-tab filtering ...
    filtering by disease: SLE does not affect what is being displayed
    on the by target or by sponsor section, right?"). Cross-tab
    filtering is what the sidebar filters are for.
  - Not coupled to the rheum-specific modality vocabulary. Use
    whatever onc has in its `Modality` column. The pattern is
    structural, not data-specific.

## --- END PROMPT ---

## Related briefs

  - `DAILY_SNAPSHOT_PORT_BRIEF_ONC.md` — daily auto-snapshot CI
  - `KEEP_AWAKE_PORT_BRIEF_RHEUM.md` (in onc) — Streamlit Cloud
    keep-awake via empty pushes; reverse-direction port
  - `DEEP_DIVE_UX_ANALYSIS.md` — Stage 1/2 of rheum's Deep Dive
    UX work, where this dual-focus pattern landed as part of the
    picker-on-top restructure
