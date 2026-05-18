"""
Streamlit harness for the nav / open-report AppTest suite.

Driven by `test_nav_open_report.py` via streamlit.testing AppTest.
It patches the data/network seams of dashboard_v3 (so no production
Supabase is ever touched) and then calls the REAL fixed functions
(`render_dashboard_v3`, `_render_v3_nav`) so the test exercises the
actual shipped code, not a reimplementation.

Control inputs (set by the test on at.session_state before .run()):
    _user        : dict   - fake authenticated profile
    _hist        : list   - synthetic swing history (newest last)
    _force_idx   : int|None- index into _hist to pass as force_record
Outputs (read by the test from at.session_state after .run()):
    _captured_html : str   - the full HTML dashboard_v3 sent to the iframe
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st
import dashboard_v3

# --- Patch the seams (idempotent; runs every script rerun) ---------------
_HIST = list(st.session_state.get("_hist") or [])

# Real _safe_history hits player_storage/Supabase. Replace with the
# injected synthetic history. (_safe_history is bound into dashboard_v3's
# namespace via `from dashboard import _safe_history`, so patch it there.)
dashboard_v3._safe_history = lambda _user: list(_HIST)

# _gamification_state already returns {} on any failure (its own fallback);
# pin it to {} so the test stays off the production database deterministically.
dashboard_v3._gamification_state = lambda _user, _history: {}


def _fake_iframe(html, **_kw):
    # Capture the exact HTML the Edge template would have rendered into
    # the components.html iframe, and drop a marker AppTest can see.
    st.session_state["_captured_html"] = html
    st.markdown("V3_IFRAME_RENDERED")


dashboard_v3.components.html = _fake_iframe

# --- Drive the real code -------------------------------------------------
_user = st.session_state.get("_user") or {
    "name": "Test Player", "slug": "test-player", "id": "test-player",
}
_force_idx = st.session_state.get("_force_idx", None)
_force = _HIST[_force_idx] if (_force_idx is not None and _HIST) else None

# Mirror app.py's page routing for the two pages this flow touches.
_page = st.session_state.get("page", "dashboard")

if _page == "saved_reports":
    # Real app renders saved_reports.render_saved_reports here. For the
    # nav-routing assertion we only need to prove we *reached* this page
    # with session state intact, so emit a stable marker.
    st.markdown("SAVED_REPORTS_REACHED")
else:
    dashboard_v3.render_dashboard_v3(_user, force_record=_force)
