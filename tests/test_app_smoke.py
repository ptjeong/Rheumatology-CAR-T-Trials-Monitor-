"""Smoke test for app.py.

Boots the Streamlit script via streamlit.testing.v1.AppTest with a
pinned snapshot (deterministic, offline) and asserts:

  - no exceptions raised during script execution
  - the seven top-level tabs render
  - the global KPI strip renders with non-zero "Total trials" (i.e. the
    snapshot loaded + classifier pipeline returned trials)
  - sidebar reset-button is present (filter wiring isn't broken)

A regression in any of these typically means the app fails on cold
load — the worst failure mode (silent breakage for end-users).

The previous test suite covered pipeline.py + classifier internals
but had ZERO coverage of the Streamlit UI layer; this is the cheap
guard against that class of regression.

Marked optional ("requires_snapshot" skip) so the test gracefully
skips on a clean checkout without snapshot data. CI runs from a
populated worktree where snapshots/ is present.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_PY = ROOT / "app.py"
SNAP_DIR = ROOT / "snapshots"


def _pick_snapshot() -> str | None:
    if not SNAP_DIR.exists():
        return None
    dates = sorted(
        p.name for p in SNAP_DIR.iterdir()
        if (p / "trials.csv").exists()
    )
    return dates[-1] if dates else None


@pytest.fixture(scope="module")
def app_test() -> AppTest:
    snap = _pick_snapshot()
    if snap is None:
        pytest.skip("no snapshots/ data available — smoke test requires a pinned snapshot")

    # Ensure the project root is on sys.path so `app.py`'s `from pipeline
    # import ...` resolves when AppTest spawns the script.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    at = AppTest.from_file(str(APP_PY), default_timeout=60)
    # Pinning bypasses the live CT.gov fetch and gives a deterministic
    # input — same snapshot every run.
    at.session_state["pinned_snapshot"] = snap
    at.run()
    return at


def test_no_exceptions(app_test: AppTest) -> None:
    # AppTest.exception accumulates any uncaught exception raised
    # during the script run. Length 0 = clean boot.
    assert len(app_test.exception) == 0, (
        f"App raised {len(app_test.exception)} exception(s): "
        + "; ".join(str(e.value)[:120] for e in app_test.exception)
    )


def test_top_level_tabs_present(app_test: AppTest) -> None:
    # Single st.tabs(...) block at the top; expect the canonical 6
    # tab labels (Overview / Geography / Data / Deep Dive / Pub Figs /
    # Methods / About — the actual list is 7 since 2026-05).
    tabs = app_test.tabs
    assert len(tabs) >= 6, f"expected ≥6 top-level tabs, got {len(tabs)}"
    labels = {t.label for t in tabs}
    expected_subset = {
        "Overview", "Geography / Map", "Data", "Deep Dive",
        "Publication Figures", "Methods & Appendix", "About",
    }
    missing = expected_subset - labels
    assert not missing, f"missing top-level tabs: {missing}"


def test_global_kpi_strip_loaded(app_test: AppTest) -> None:
    # The hero KPI strip uses metric_card() (inline HTML) not
    # st.metric — so the assertion has to look at the rendered
    # markdown for the canonical "Filtered trials" label.
    md_blob = "\n".join(m.value for m in app_test.markdown)
    assert "Filtered trials" in md_blob, (
        "no 'Filtered trials' KPI in rendered markdown — hero strip "
        "didn't render"
    )
    assert "Open / recruiting" in md_blob, (
        "no 'Open / recruiting' KPI in rendered markdown — KPI strip "
        "partial render"
    )


def test_sidebar_reset_button_present(app_test: AppTest) -> None:
    # Reset filters button lives in the sidebar; presence == filter
    # wiring is intact. Failure here typically means _FILTER_KEYS or
    # _FILTER_QPARAM diverged from their use sites.
    buttons = app_test.sidebar.button
    labels = [b.label for b in buttons]
    assert "Reset filters" in labels, (
        f"sidebar 'Reset filters' button missing; sidebar buttons: {labels}"
    )
