"""
Saved Reports page — BarrelLabs premium edition.

The central archive for every swing the player has ever analyzed.
Provides search, score filtering, time-range filtering, per-report PDF
download, and delete-with-confirmation. Clicking a report opens the
full saved report (handled by app.py routing via view_swing_record).
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timedelta

import streamlit as st

from bl_theme import inject_global_theme
from bl_edge_chrome import (
    render_edge_masthead,
    render_edge_page_wrapper_open,
    render_edge_page_wrapper_close,
)
from player_storage import (
    load_swing_history,
    delete_swing_record,
)
from entitlements import can_export_pdf
from subscription_storage import load_my_plan


# ============================================================
#                    PAGE-LOCAL STYLES
# ============================================================
_SR_LOCAL_CSS = """
<style>
/* ===========  HERO  =========== */
.sr-hero {
    position: relative;
    padding: 2.2rem 2.4rem 2.4rem;
    border-radius: var(--bl-radius-xl);
    background: linear-gradient(160deg,
                rgba(255,59,48,0.08) 0%,
                rgba(255,255,255,0.025) 38%,
                rgba(255,255,255,0.015) 100%);
    border: 1px solid var(--bl-line);
    overflow: hidden;
    margin-bottom: 2rem;
}
.sr-hero::before {
    content: "";
    position: absolute;
    top: -120px; right: -160px;
    width: 420px; height: 420px;
    background: radial-gradient(circle, rgba(255,59,48,0.18), transparent 65%);
    filter: blur(60px);
    pointer-events: none;
}
.sr-hero-row {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 1.4rem; position: relative; z-index: 1;
}
.sr-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.28em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}
.sr-title {
    font-family: var(--bl-sans);
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1.05;
    margin-bottom: 0.65rem;
}
.sr-sub {
    color: var(--bl-ink-60);
    font-size: 0.96rem;
    line-height: 1.55;
    max-width: 580px;
}
.sr-mode-pill {
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-red);
    background: rgba(255,59,48,0.08);
    border: 1px solid rgba(255,59,48,0.22);
    border-radius: 999px;
    padding: 0.42rem 0.85rem;
    text-transform: uppercase;
    white-space: nowrap;
}
.sr-mode-pill-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--bl-red);
    box-shadow: 0 0 8px var(--bl-red);
}

/* ===========  FILTER BAR  =========== */
.sr-filter-card {
    padding: 1.4rem 1.6rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: 1.5rem;
}
.sr-filter-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}
.sr-filter-row {
    display: grid;
    grid-template-columns: 2.2fr 1fr 1fr;
    gap: 1rem;
}
@media (max-width: 720px) {
    .sr-filter-row { grid-template-columns: 1fr; }
}

/* Streamlit widget refinements for the filter row */
.sr-filter-card input[type="text"],
.sr-filter-card [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.022) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: 12px !important;
    color: var(--bl-ink-100) !important;
}
.sr-filter-card input[type="text"]:focus {
    border-color: rgba(255,59,48,0.35) !important;
    box-shadow: 0 0 0 3px rgba(255,59,48,0.10) !important;
}
.sr-filter-card [data-testid="stTextInput"] label,
.sr-filter-card [data-testid="stTextInput"] label p,
.sr-filter-card [data-testid="stSelectbox"] label,
.sr-filter-card [data-testid="stSelectbox"] label p {
    font-family: var(--bl-mono) !important;
    font-size: 0.58rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    color: var(--bl-ink-40) !important;
    text-transform: uppercase !important;
}

/* ===========  RESULT COUNT STRIP  =========== */
.sr-result-strip {
    display: flex; justify-content: space-between; align-items: center;
    margin: 0 0.3rem 1rem 0.3rem;
}
.sr-result-count {
    font-family: var(--bl-mono);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    color: var(--bl-ink-60);
    text-transform: uppercase;
}
.sr-result-count strong { color: var(--bl-ink-100); }

/* ===========  REPORT CARD GRID  =========== */
.sr-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
}
@media (max-width: 880px) {
    .sr-grid { grid-template-columns: 1fr; }
}

/* Each card is two markdown blocks + an action row (Streamlit cols).
   We rely on the wrapper class to bind them visually. */
.sr-card-wrap {
    padding: 1.3rem 1.4rem 1.1rem 1.4rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    transition: border-color .25s ease, transform .25s ease, box-shadow .25s ease;
    margin-bottom: 1rem;
}
.sr-card-wrap:hover {
    border-color: var(--bl-line-hi);
    transform: translateY(-2px);
    box-shadow: 0 18px 40px -28px rgba(0,0,0,0.7);
}

.sr-card-head {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 1rem; margin-bottom: 0.8rem;
}
.sr-card-num {
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-red);
    background: rgba(255,59,48,0.08);
    border: 1px solid rgba(255,59,48,0.24);
    border-radius: 999px;
    padding: 0.3rem 0.7rem;
    text-transform: uppercase;
}
.sr-card-date {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}

.sr-card-meta-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
    margin-bottom: 0.85rem;
}
.sr-card-meta-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.55rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.sr-card-meta-value {
    font-family: var(--bl-sans);
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.025em;
    line-height: 1.0;
}
.sr-card-meta-value.is-red { color: var(--bl-red); }

.sr-card-meta-sub-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
    margin-bottom: 1rem;
}
.sr-card-meta-sub {
    display: flex; flex-direction: column;
    gap: 0.25rem;
}
.sr-card-meta-sub-label {
    font-family: var(--bl-mono);
    font-size: 0.55rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}
.sr-card-meta-sub-value {
    color: var(--bl-ink-100);
    font-size: 0.92rem;
    font-weight: 500;
    letter-spacing: -0.005em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* Action buttons row — Open / Download / Delete */
.sr-card-actions {
    display: flex; align-items: center; gap: 0.5rem;
}
.sr-card-actions [data-testid="stButton"] button,
.sr-card-actions [data-testid="stDownloadButton"] button {
    background: transparent !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bl-ink-100) !important;
    border-radius: 999px !important;
    padding: 0.5rem 1rem !important;
    font-family: var(--bl-sans) !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    letter-spacing: -0.005em !important;
    transition: all .25s ease !important;
}
.sr-card-actions [data-testid="stButton"] button:hover,
.sr-card-actions [data-testid="stDownloadButton"] button:hover {
    border-color: var(--bl-line-hi) !important;
    background: rgba(255,255,255,0.03) !important;
    transform: translateY(-1px);
}
.sr-open-btn .stButton > button {
    background: linear-gradient(180deg, var(--bl-red), #e8342a) !important;
    border-color: rgba(255,59,48,0.55) !important;
    color: #ffffff !important;
    box-shadow: 0 0 18px -6px rgba(255,59,48,0.5),
                inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.sr-open-btn .stButton > button:hover {
    box-shadow: 0 0 26px -4px rgba(255,59,48,0.7),
                inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.sr-delete-btn .stButton > button {
    color: rgba(255,90,80,0.85) !important;
    border-color: rgba(255,59,48,0.22) !important;
}
.sr-delete-btn .stButton > button:hover {
    background: rgba(255,59,48,0.06) !important;
    border-color: rgba(255,59,48,0.45) !important;
    color: var(--bl-red) !important;
}

/* Confirm pill (delete warning) */
.sr-confirm-banner {
    background: rgba(255,59,48,0.07);
    border: 1px solid rgba(255,59,48,0.28);
    border-radius: var(--bl-radius-sm);
    color: var(--bl-ink-100);
    padding: 0.7rem 0.95rem;
    margin: 0.6rem 0 0.4rem 0;
    font-size: 0.85rem;
    line-height: 1.45;
}
.sr-confirm-banner strong { color: var(--bl-red); }

/* ===========  EMPTY  =========== */
.sr-empty {
    text-align: center;
    padding: 4rem 2rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px dashed var(--bl-line-hi);
}
.sr-empty-icon {
    font-size: 2.4rem;
    color: var(--bl-red);
    margin-bottom: 1rem;
    opacity: 0.7;
}
.sr-empty-title {
    font-family: var(--bl-sans);
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--bl-ink-100);
    margin-bottom: 0.55rem;
    letter-spacing: -0.012em;
}
.sr-empty-sub {
    color: var(--bl-ink-60);
    font-size: 0.95rem;
    line-height: 1.55;
    max-width: 460px;
    margin: 0 auto;
}

/* ===========  BACK NAV  =========== */
.sr-back .stButton > button {
    background: transparent !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bl-ink-60) !important;
    font-family: var(--bl-sans) !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    border-radius: 999px !important;
    padding: 0.5rem 1.1rem !important;
    transition: all .25s ease !important;
}
.sr-back .stButton > button:hover {
    border-color: rgba(255,59,48,0.35) !important;
    color: var(--bl-red) !important;
    background: rgba(255,59,48,0.05) !important;
    transform: translateX(-2px);
}

/* =========================================================
   EDGE EDITORIAL OVERRIDES — bring the Saved Reports page
   into the same visual language as the v3 dashboard.
   These layer ON TOP of the base styles above.
   ========================================================= */
.sr-hero {
    background:
        radial-gradient(ellipse at 95% -20%, rgba(230,69,48,0.10) 0%, transparent 55%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.012));
    border-color: rgba(244,239,230,0.08);
    border-radius: 24px;
}
.sr-eyebrow {
    font-family: 'Geist Mono', 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.24em !important;
    color: #E64530 !important;
}
.sr-title {
    font-family: 'Instrument Serif', 'Fraunces', Georgia, serif !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 3rem !important;
    letter-spacing: -0.01em !important;
    color: #F4EFE6 !important;
    line-height: 1.0 !important;
    margin-bottom: 0.85rem !important;
}
.sr-sub {
    color: #C8C4BB !important;
    font-family: 'Geist', -apple-system, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    max-width: 560px !important;
}
.sr-mode-pill {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10.5px !important;
    letter-spacing: 0.22em !important;
    color: #E64530 !important;
    background: rgba(230,69,48,0.08) !important;
    border-color: rgba(230,69,48,0.32) !important;
}
.sr-filter-card {
    border-color: rgba(244,239,230,0.08) !important;
    border-radius: 18px !important;
    background: rgba(255,255,255,0.018) !important;
}
.sr-filter-eyebrow {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10.5px !important;
    letter-spacing: 0.24em !important;
    color: #E64530 !important;
}
.sr-result-count {
    font-family: 'Geist Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.20em !important;
    color: #8B8E94 !important;
}
.sr-result-count strong { color: #F4EFE6 !important; }
.sr-card-wrap {
    border-color: rgba(244,239,230,0.08) !important;
    border-radius: 20px !important;
    background: rgba(255,255,255,0.018) !important;
    padding: 1.5rem 1.6rem 1.3rem !important;
    transition: border-color 0.25s ease, transform 0.25s ease,
                box-shadow 0.25s ease;
}
.sr-card-wrap:hover {
    border-color: rgba(244,239,230,0.18) !important;
    background: rgba(255,255,255,0.028) !important;
}
.sr-card-num {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10.5px !important;
    letter-spacing: 0.22em !important;
    color: #E64530 !important;
    background: rgba(230,69,48,0.08) !important;
    border-color: rgba(230,69,48,0.30) !important;
}
.sr-card-date {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10.5px !important;
    letter-spacing: 0.18em !important;
    color: #8B8E94 !important;
}
.sr-card-meta-eyebrow,
.sr-card-meta-sub-label {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 0.22em !important;
    color: #8B8E94 !important;
}
.sr-card-meta-value {
    font-family: 'Instrument Serif', Georgia, serif !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 2rem !important;
    color: #F4EFE6 !important;
}
.sr-card-meta-value.is-red { color: #E64530 !important; }
.sr-card-meta-sub-value {
    font-family: 'Geist', sans-serif !important;
    color: #F4EFE6 !important;
    font-weight: 500 !important;
}
.sr-open-btn .stButton > button {
    background: #F4EFE6 !important;
    border-color: #F4EFE6 !important;
    color: #0A0B0E !important;
    border-radius: 100px !important;
    font-family: 'Geist Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    box-shadow: none !important;
}
.sr-open-btn .stButton > button:hover {
    background: #FFFFFF !important;
    border-color: #FFFFFF !important;
    box-shadow: 0 0 24px -8px rgba(244,239,230,0.5) !important;
}
.sr-card-actions [data-testid="stButton"] button,
.sr-card-actions [data-testid="stDownloadButton"] button {
    font-family: 'Geist Mono', monospace !important;
    font-size: 10.5px !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    border-color: rgba(244,239,230,0.10) !important;
    color: #C8C4BB !important;
    border-radius: 100px !important;
}
.sr-card-actions [data-testid="stButton"] button:hover,
.sr-card-actions [data-testid="stDownloadButton"] button:hover {
    color: #F4EFE6 !important;
    border-color: rgba(244,239,230,0.22) !important;
    background: rgba(244,239,230,0.04) !important;
    transform: none;
}
.sr-empty {
    background: rgba(255,255,255,0.018) !important;
    border-color: rgba(244,239,230,0.12) !important;
}
.sr-empty-title {
    font-family: 'Instrument Serif', Georgia, serif !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 1.6rem !important;
    color: #F4EFE6 !important;
}
.sr-empty-sub {
    font-family: 'Geist', sans-serif !important;
    color: #C8C4BB !important;
}
</style>
"""


# ============================================================
#                       HELPERS
# ============================================================
def _parse_date(rec: dict):
    """Best-effort parse of the date string into a datetime."""
    for key in ("created_at", "timestamp", "date"):
        v = rec.get(key)
        if not v:
            continue
        if isinstance(v, datetime):
            return v
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(v)[:len(fmt)], fmt)
            except ValueError:
                continue
    return None


def _fmt_short_date(rec: dict) -> str:
    dt = _parse_date(rec)
    if dt is None:
        return str(rec.get("date") or rec.get("timestamp") or "Unknown")
    return dt.strftime("%b %d, %Y")


def _top_focus(rec: dict) -> str:
    narratives = rec.get("narratives") or []
    if narratives:
        return str(narratives[0].get("title", "Top Fix")).title()
    return "—"


def _filter_history(history, q: str, score_filter: str, time_filter: str) -> list:
    """Apply search + score + time-range filters to the history list."""
    q = (q or "").strip().lower()
    now = datetime.now()
    cutoff = None
    if time_filter == "Last 7 days":
        cutoff = now - timedelta(days=7)
    elif time_filter == "Last 30 days":
        cutoff = now - timedelta(days=30)
    elif time_filter == "Last 90 days":
        cutoff = now - timedelta(days=90)

    out = []
    for rec in history:
        # Search
        if q:
            haystack = " ".join([
                str(rec.get("reference_name") or ""),
                str(rec.get("filename") or ""),
                str(rec.get("date") or ""),
                str(rec.get("swing_number") or ""),
                _top_focus(rec),
            ]).lower()
            if q not in haystack:
                continue
        # Score
        s = rec.get("score") or 0
        try:
            s = float(s)
        except (TypeError, ValueError):
            s = 0
        if score_filter == "80+ (Elite)" and s < 80:
            continue
        if score_filter == "60–79 (Strong)" and not (60 <= s < 80):
            continue
        if score_filter == "Below 60 (Building)" and s >= 60:
            continue
        # Time
        if cutoff is not None:
            dt = _parse_date(rec)
            if dt is None or dt < cutoff:
                continue
        out.append(rec)
    return out


def _render_empty_state(title: str, sub: str, icon: str = "◇"):
    html = textwrap.dedent(f"""
    <div class="sr-empty">
      <div class="sr-empty-icon">{icon}</div>
      <div class="sr-empty-title">{title}</div>
      <div class="sr-empty-sub">{sub}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
#                         MAIN
# ============================================================
def render_saved_reports(user: dict, build_pdf_fn=None) -> None:
    """
    Render the Saved Reports archive page.

    Args:
        user: the logged-in user dict (must have "slug" or "id")
        build_pdf_fn: optional callable(record) -> pdf bytes. If provided,
            each report card gets a Download PDF button.
    """
    inject_global_theme()

    # Unified Edge masthead — the ONLY nav system in the app.
    # This replaces the old "← Back to Dashboard" button row, since the
    # Dashboard pill in the masthead handles that already.
    render_edge_masthead(user, active_page="saved_reports")

    # Edge-styled page wrapper (kills Streamlit chrome, applies max-width)
    render_edge_page_wrapper_open()

    st.markdown(_SR_LOCAL_CSS, unsafe_allow_html=True)
    st.markdown('<div class="bl-page">', unsafe_allow_html=True)

    # ---- Hero ----
    hero_html = textwrap.dedent("""
    <div class="sr-hero">
      <div class="sr-hero-row">
        <div style="flex:1;min-width:0;">
          <div class="sr-eyebrow">BarrelLabs Performance Lab</div>
          <div class="sr-title">Saved Reports</div>
          <div class="sr-sub">
            Every swing you've analyzed in one place. Open any report,
            export it as a PDF, or print it for your coach.
          </div>
        </div>
        <div class="sr-mode-pill"><span class="sr-mode-pill-dot"></span> Archive</div>
      </div>
    </div>
    """).strip()
    st.markdown(hero_html, unsafe_allow_html=True)

    # ---- Load history ----
    if not user:
        _render_empty_state(
            "Please sign in.",
            "Your saved reports are tied to your BarrelLabs account.",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        render_edge_page_wrapper_close()
        return

    player_id = user.get("slug") or user.get("id")
    history = load_swing_history(player_id)
    history_sorted = list(reversed(history))  # newest first

    if not history_sorted:
        _render_empty_state(
            "No saved reports yet.",
            "Analyze your first swing on the Upload page — once you do, "
            "every analysis will live here for you to revisit.",
            icon="↗",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        render_edge_page_wrapper_close()
        return

    # ---- Filter bar ----
    st.markdown('<div class="sr-filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="sr-filter-eyebrow">SEARCH & FILTER</div>', unsafe_allow_html=True)

    f_search_col, f_score_col, f_time_col = st.columns([2.2, 1, 1])
    with f_search_col:
        search_q = st.text_input(
            "Search reports",
            key="sr_search",
            placeholder="Search by MLB comp, focus area, file name…",
            label_visibility="visible",
        )
    with f_score_col:
        score_filter = st.selectbox(
            "Score range",
            ["All scores", "80+ (Elite)", "60–79 (Strong)", "Below 60 (Building)"],
            key="sr_score_filter",
        )
    with f_time_col:
        time_filter = st.selectbox(
            "Time range",
            ["All time", "Last 7 days", "Last 30 days", "Last 90 days"],
            key="sr_time_filter",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    filtered = _filter_history(history_sorted, search_q, score_filter, time_filter)

    # ---- Result count strip ----
    st.markdown(
        f'<div class="sr-result-strip">'
        f'<div class="sr-result-count">'
        f'SHOWING <strong>{len(filtered)}</strong> OF <strong>{len(history_sorted)}</strong> REPORTS'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not filtered:
        _render_empty_state(
            "No reports match those filters.",
            "Try widening the score range, choosing a longer time window, "
            "or clearing the search box.",
            icon="≡",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        render_edge_page_wrapper_close()
        return

    # ---- Render cards (one per row in this column-based layout, since
    #      Streamlit doesn't let us easily put real widgets in CSS grids).
    pending_delete_key = "sr_pending_delete_id"

    for idx, rec in enumerate(filtered):
        rec_id = rec.get("id") or rec.get("timestamp") or f"row{idx}"
        swing_num = rec.get("swing_number", "—")
        try:
            num_disp = f"#{int(swing_num):02d}"
        except Exception:
            num_disp = f"#{swing_num}"
        score = rec.get("score")
        try:
            score_disp = f"{int(round(float(score)))}"
        except (TypeError, ValueError):
            score_disp = "—"
        ref = str(rec.get("reference_name") or "—")
        focus = _top_focus(rec)
        date_disp = _fmt_short_date(rec)
        filename = str(rec.get("filename") or "—")

        # Visual card shell
        card_html = textwrap.dedent(f"""
        <div class="sr-card-wrap">
          <div class="sr-card-head">
            <span class="sr-card-num">SWING {num_disp}</span>
            <span class="sr-card-date">{date_disp}</span>
          </div>
          <div class="sr-card-meta-row">
            <div>
              <div class="sr-card-meta-eyebrow">SCORE</div>
              <div class="sr-card-meta-value is-red">{score_disp}<span style="font-size:1rem;color:var(--bl-ink-40);">/100</span></div>
            </div>
            <div>
              <div class="sr-card-meta-eyebrow">MLB COMP</div>
              <div class="sr-card-meta-value" style="font-size:1.15rem;line-height:1.2;">{ref}</div>
            </div>
          </div>
          <div class="sr-card-meta-sub-row">
            <div class="sr-card-meta-sub">
              <div class="sr-card-meta-sub-label">TOP FOCUS</div>
              <div class="sr-card-meta-sub-value">{focus}</div>
            </div>
            <div class="sr-card-meta-sub">
              <div class="sr-card-meta-sub-label">FILE</div>
              <div class="sr-card-meta-sub-value">{filename}</div>
            </div>
          </div>
        </div>
        """).strip()
        st.markdown(card_html, unsafe_allow_html=True)

        # Action row (Open / Download / Delete)
        st.markdown('<div class="sr-card-actions">', unsafe_allow_html=True)
        a_open, a_dl, a_del, _spacer = st.columns([1.3, 1.5, 1.1, 4])

        with a_open:
            st.markdown('<div class="sr-open-btn">', unsafe_allow_html=True)
            if st.button("Open Report  →", key=f"sr_open_{rec_id}"):
                # Set the record + route to the DEDICATED swing report
                # page (not back to dashboard). The page key drives the
                # app.py dispatcher to swing_report_page.render(),
                # which renders a focused single-swing view with the
                # redesigned comparison at the bottom.
                st.session_state["view_swing_record"] = rec
                st.session_state["view_swing_report_id"] = rec_id
                rp = rec.get("_record_path")
                if rp:
                    st.session_state["view_swing_path"] = rp
                else:
                    st.session_state.pop("view_swing_path", None)
                st.session_state["page"] = "swing_report"
                st.session_state.pop("view", None)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with a_dl:
            # Pro-only gate. Free users see an upgrade CTA in place of
            # the real Download PDF button; clicking it surfaces a toast
            # explaining the gate (and pointing at the beta-code path).
            _pdf_allowed = bool(can_export_pdf(load_my_plan()))
            if build_pdf_fn is not None and _pdf_allowed:
                try:
                    pdf_bytes = build_pdf_fn(rec)
                    st.download_button(
                        "⬇  Download PDF",
                        data=pdf_bytes,
                        file_name=f"swing_report_{rec.get('timestamp', rec_id)}.pdf",
                        mime="application/pdf",
                        key=f"sr_dl_{rec_id}",
                    )
                except Exception:
                    st.button("⬇  Download PDF", key=f"sr_dl_err_{rec_id}", disabled=True)
            elif build_pdf_fn is not None and not _pdf_allowed:
                if st.button("🔒  PDF — Upgrade",
                             key=f"sr_dl_locked_{rec_id}",
                             help="PDF report export is a Pro feature."):
                    st.toast(
                        "PDF export is a Pro feature. Upgrade to Solo Pro "
                        "(or redeem a beta code) to download reports.",
                        icon="🔒",
                    )
            else:
                st.button("⬇  Download PDF", key=f"sr_dl_disabled_{rec_id}", disabled=True)

        with a_del:
            st.markdown('<div class="sr-delete-btn">', unsafe_allow_html=True)
            is_pending = st.session_state.get(pending_delete_key) == rec_id
            del_label = "Confirm delete?" if is_pending else "🗑  Delete"
            if st.button(del_label, key=f"sr_del_{rec_id}"):
                if is_pending:
                    # Actually delete.
                    target_id = rec.get("id")
                    if target_id:
                        delete_swing_record(target_id)
                    st.session_state.pop(pending_delete_key, None)
                    st.rerun()
                else:
                    st.session_state[pending_delete_key] = rec_id
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Confirm banner shown after first click on Delete
        if st.session_state.get(pending_delete_key) == rec_id:
            st.markdown(
                f'<div class="sr-confirm-banner">'
                f'<strong>Delete this report?</strong> Click '
                f'"Confirm delete?" again within this session to permanently '
                f'remove Swing {num_disp} from your archive. This cannot be undone.'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Subtle spacer between cards
        st.markdown('<div style="height:.45rem;"></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close .bl-page
    render_edge_page_wrapper_close()
