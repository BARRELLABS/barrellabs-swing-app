"""
Standalone Streamlit harness that renders ONLY the Phase 1 preview
pages, with a synthetic user — so the design can be captured without
needing live Supabase auth.

Usage:
    streamlit run scripts/visual_qa/preview_harness.py \\
        --server.port 8765 --server.headless true \\
        -- --page saved_reports_preview

URL:
    http://localhost:8765/?page=saved_reports_preview
    http://localhost:8765/?page=swing_report_preview
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

st.set_page_config(
    page_title="BarrelLabs · Preview",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide all Streamlit chrome (sidebar, header, footer)
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stSidebar"],
      [data-testid="stToolbar"], [data-testid="stDecoration"],
      footer { display: none !important; }
      .block-container { padding: 0 !important; max-width: 100% !important; }
      body, html, [data-testid="stAppViewContainer"] { background: #0A0B0E !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Synthetic user — preview pages just need name/slug for display.
SYNTHETIC_USER = {
    "slug": "preview_user",
    "id": "preview_user",
    "name": "Logan Collins",
    "email": "logan@barrellabs.example",
    "handedness": "Right-handed",
    "gamification": {"current_streak_days": 17},
}

# Resolve page from query string (?page=...). Default to saved_reports_preview.
PAGES = {
    "saved_reports_preview": "saved_reports_preview",
    "swing_report_preview":  "swing_report_preview",
}
url_page = st.query_params.get("page", "saved_reports_preview")
if url_page not in PAGES:
    url_page = "saved_reports_preview"

# Persist routing state so Open Report → swing_report_preview works
# inside the harness too.
if "page" not in st.session_state:
    st.session_state["page"] = url_page
else:
    # Allow URL to override on each load — useful for direct deep links
    if st.query_params.get("page") in PAGES:
        st.session_state["page"] = st.query_params["page"]

page = st.session_state.get("page", "saved_reports_preview")

if page == "saved_reports_preview":
    from saved_reports_preview import render_saved_reports_preview
    render_saved_reports_preview(SYNTHETIC_USER)
elif page == "swing_report_preview":
    from swing_report_preview import render_swing_report_preview
    render_swing_report_preview(SYNTHETIC_USER)
else:
    st.error(f"Unknown preview page: {page}")
