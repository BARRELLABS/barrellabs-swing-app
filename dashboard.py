"""
BarrelLabs / SwingAI — Dashboard view.

The post-auth landing page. Pulls the latest swing from history and
renders score, MLB comparison, biomechanical radar, and recent swings
in a refined, minimal, premium dashboard.

The dashboard now consumes the global design system in `bl_theme.py`
(tokens, .bl-page / .bl-card / .bl-cta / etc.) and only adds local
styling for dashboard-specific components: the score ring, the MLB
avatar, the similarity bar, the recent-swings list, and the KPI strip.

Public API:
    render_dashboard(user) -> None
        Renders the full dashboard. Caller should `st.stop()` after.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import plotly.graph_objects as go

from bl_theme import inject_global_theme
from player_storage import load_swing_history


# ------------------------------------------------------------------
#  Local CSS — only the bits that aren't part of the global system
# ------------------------------------------------------------------
_DASHBOARD_LOCAL_CSS = """
<style>
/* ===========  HERO (uses .bl-section-header from bl_theme)  =========== */
.bld-hero {
    position: relative; z-index: 1;
    padding: 0.4rem 0 2.2rem 0;
    margin-bottom: 2.6rem;
    border-bottom: 1px solid var(--bl-line);
}
.bld-hero-row {
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 2rem; flex-wrap: wrap;
}
.bld-greeting {
    font-size: 3.4rem;
    line-height: 1.02;
    font-weight: 700;
    letter-spacing: -0.045em;
    color: var(--bl-ink-100);
    margin: 0;
}
.bld-greeting .bl-period { color: var(--bl-red); }
.bld-subline {
    margin-top: 0.95rem;
    color: var(--bl-ink-60);
    font-size: 1rem;
    max-width: 580px;
    line-height: 1.55;
}
.bld-status-stack {
    display: flex; flex-direction: column; align-items: flex-end; gap: 0.6rem;
}
.bld-status-pill {
    display: inline-flex; align-items: center; gap: 0.55rem;
    padding: 0.45rem 0.9rem;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--bl-line);
    border-radius: 999px;
    font-family: var(--bl-mono);
    font-size: 0.66rem; letter-spacing: 0.18em; font-weight: 600;
    color: var(--bl-ink-80); text-transform: uppercase;
}
.bld-status-pill::before {
    content: ""; width: 6px; height: 6px; border-radius: 50%;
    background: #34c759;
    box-shadow: 0 0 8px rgba(52,199,89,0.55);
}
.bld-trailing-meta {
    font-family: var(--bl-mono);
    font-size: 0.66rem;
    color: var(--bl-ink-40);
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

/* ===========  SCORE CARD (specific to dashboard)  =========== */
.bld-score-card {
    text-align: center;
    padding: 1.9rem 1.6rem 2rem 1.6rem;
    display: flex;
    flex-direction: column;
    align-items: stretch;
}
.bld-score-ring {
    position: relative;
    width: 220px; height: 220px;
    margin: 1.4rem auto 1rem auto;
}
.bld-score-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.bld-score-track {
    fill: none;
    stroke: rgba(255,255,255,0.05);
    stroke-width: 7;
}
.bld-score-fill {
    fill: none;
    stroke-width: 7;
    stroke-linecap: round;
    transition: stroke-dashoffset 1.4s cubic-bezier(.2,.7,.2,1);
}
.bld-score-center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 0 1.5rem;             /* prevents overflow outside the ring */
}
.bld-score-number {
    font-family: var(--bl-sans);
    font-size: 4.2rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    line-height: 1;
    letter-spacing: -0.05em;
}
.bld-score-tag {
    margin-top: 0.55rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.28em;
    font-weight: 600;
    text-transform: uppercase;
    max-width: 130px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.bld-score-band {
    margin-top: 1.1rem;
    font-family: var(--bl-sans);
    color: var(--bl-ink-80);
    font-size: 0.96rem;
    font-weight: 500;
    letter-spacing: -0.005em;
    line-height: 1.4;
}
.bld-score-foot {
    color: var(--bl-ink-60);
    font-size: 0.82rem;
    margin-top: 0.5rem;
    line-height: 1.5;
}

/* ===========  MLB CARD  =========== */
.bld-mlb-card { display: flex; flex-direction: column; gap: 1.4rem; }
.bld-mlb-row {
    display: flex; align-items: center; gap: 1.4rem;
    margin-top: 0.4rem;
}
.bld-mlb-avatar {
    width: 92px; height: 92px;
    flex-shrink: 0;
    position: relative;
    background: radial-gradient(circle,
                rgba(255,59,48,0.12) 0%,
                rgba(255,59,48,0.02) 60%,
                transparent 100%);
    border: 1px solid rgba(255,59,48,0.2);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
}
.bld-mlb-avatar svg { width: 62%; height: 62%; }
.bld-mlb-meta { flex: 1; min-width: 0; }
.bld-mlb-tag {
    font-family: var(--bl-mono);
    font-size: 0.64rem;
    color: var(--bl-ink-60);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    font-weight: 600;
}
.bld-mlb-name {
    font-size: 1.85rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: var(--bl-ink-100);
    line-height: 1.1;
    margin-top: 0.35rem;
}
.bld-mlb-sub {
    color: var(--bl-ink-60);
    font-size: 0.86rem;
    margin-top: 0.35rem;
}
.bld-sim-bar-wrap {
    position: relative;
    height: 4px; border-radius: 2px;
    background: rgba(255,255,255,0.05);
    overflow: hidden;
    margin-top: 0.5rem;
}
.bld-sim-bar-fill {
    position: absolute; inset: 0;
    background: var(--bl-red);
    border-radius: 2px;
}
.bld-sim-foot {
    display: flex; justify-content: space-between; align-items: baseline;
    margin-top: 0.85rem;
    font-family: var(--bl-mono);
    font-size: 0.66rem; letter-spacing: 0.16em; font-weight: 600;
    text-transform: uppercase; color: var(--bl-ink-60);
}
.bld-sim-foot strong {
    color: var(--bl-ink-100);
    font-family: var(--bl-sans);
    font-size: 1rem;
    letter-spacing: -0.01em;
    font-weight: 600;
}

/* ===========  RECENT SWINGS  =========== */
.bld-recent-list {
    display: flex; flex-direction: column; gap: 0.5rem;
    margin-top: 1.2rem;
}
.bld-recent-row {
    display: grid;
    grid-template-columns: 42px 1fr auto 14px;
    align-items: center;
    column-gap: 1rem;
    padding: 0.95rem 1.05rem;
    background: transparent;
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-md);
    cursor: pointer;
    transition:
        background .22s ease,
        border-color .22s ease,
        transform .22s ease,
        box-shadow .22s ease;
}
.bld-recent-row:hover {
    background: rgba(255,255,255,0.03);
    border-color: var(--bl-line-hi);
    transform: translateX(2px);
    box-shadow: 0 8px 24px -16px rgba(0,0,0,0.6);
}
.bld-recent-row:hover .bld-recent-chev { color: var(--bl-red); transform: translateX(2px); }
.bld-recent-num {
    font-family: var(--bl-mono);
    font-size: 0.72rem;
    color: var(--bl-ink-60);
    letter-spacing: 0.1em;
    font-weight: 500;
}
.bld-recent-body { min-width: 0; }
.bld-recent-title {
    color: var(--bl-ink-100);
    font-weight: 500;
    font-size: 0.96rem;
    letter-spacing: -0.005em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bld-recent-date {
    color: var(--bl-ink-60);
    font-size: 0.72rem;
    margin-top: 0.25rem;
    font-family: var(--bl-mono);
    letter-spacing: 0.06em;
}
.bld-recent-score-wrap { text-align: right; }
.bld-recent-score {
    font-family: var(--bl-sans);
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--bl-ink-100);
    line-height: 1;
    letter-spacing: -0.02em;
}
.bld-recent-score-foot {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    letter-spacing: 0.18em;
    color: var(--bl-ink-60);
    text-align: right;
    margin-top: 0.35rem;
    text-transform: uppercase;
}
.bld-recent-chev {
    color: var(--bl-ink-40);
    font-size: 1rem;
    line-height: 1;
    transition: color .22s ease, transform .22s ease;
    text-align: right;
}
.bld-recent-empty {
    color: var(--bl-ink-60);
    font-size: 0.88rem;
    padding: 1rem 0;
    text-align: center;
}
.bld-recent-empty-wrap {
    padding: 1.6rem;
    border: 1px dashed var(--bl-line-hi);
    border-radius: var(--bl-radius-md);
    background: var(--bl-surface-1);
}

/* The "tap any swing" hint sits just under the card title. */
.bld-recent-card .bld-recent-hint {
    color: var(--bl-ink-40);
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 500;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-top: 0.55rem;
    margin-bottom: 0.45rem;
}

/* ---- Clickable Streamlit-button rows ---- */
.bld-recent-list-real {
    display: flex; flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.35rem;
}
.bld-recent-row-btn .stButton > button {
    width: 100% !important;
    text-align: left !important;
    background: transparent !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: var(--bl-radius-md) !important;
    color: var(--bl-ink-100) !important;
    padding: 0.95rem 1.1rem !important;
    font-family: var(--bl-sans) !important;
    font-weight: 500 !important;
    font-size: 0.96rem !important;
    letter-spacing: -0.005em !important;
    line-height: 1.35 !important;
    justify-content: flex-start !important;
    cursor: pointer !important;
    transition: background .22s ease,
                border-color .22s ease,
                transform .22s ease,
                box-shadow .22s ease !important;
    box-shadow: none !important;
    white-space: pre-wrap !important;
}
.bld-recent-row-btn .stButton > button:hover {
    background: rgba(255,255,255,0.03) !important;
    border-color: var(--bl-line-hi) !important;
    transform: translateX(2px) !important;
    box-shadow: 0 10px 28px -18px rgba(0,0,0,0.65) !important;
}
.bld-recent-row-btn .stButton > button:active {
    transform: translateX(2px) scale(0.997) !important;
}
.bld-recent-row-btn .stButton > button:focus {
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(255,59,48,0.18) !important;
}
.bld-recent-row-btn .stButton > button p {
    margin: 0 !important;
    color: inherit !important;
    font-size: 0.96rem !important;
    font-weight: 500 !important;
    line-height: 1.35 !important;
}
.bld-recent-row-btn .stButton > button:hover p {
    color: #ffffff !important;
}

/* ===========  EMPTY STATE  =========== */
.bld-empty {
    padding: 3.2rem 1.8rem;
    text-align: center;
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-lg);
}
.bld-empty-icon {
    font-size: 2.6rem;
    margin-bottom: 0.8rem;
    color: var(--bl-red);
    opacity: 0.9;
}
.bld-empty-title {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
}
.bld-empty-sub {
    color: var(--bl-ink-60);
    margin-top: 0.6rem;
    font-size: 0.95rem;
    max-width: 480px;
    margin-left: auto; margin-right: auto;
    line-height: 1.55;
}

/* ===========  KPI CHIPS  =========== */
.bld-kpi-strip {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 0.65rem; margin-top: 1.3rem;
}
.bld-kpi {
    padding: 0.95rem 1rem;
    background: rgba(255,255,255,0.018);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-md);
    transition: border-color .22s ease, background .22s ease;
}
.bld-kpi:hover {
    border-color: var(--bl-line-hi);
    background: rgba(255,255,255,0.03);
}
.bld-kpi-label {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    color: var(--bl-ink-60);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 600;
}
.bld-kpi-value {
    font-family: var(--bl-sans);
    font-size: 1.32rem;
    font-weight: 600;
    color: var(--bl-ink-100);
    margin-top: 0.35rem;
    letter-spacing: -0.02em;
}
@media (max-width: 720px) {
    .bld-kpi-strip { grid-template-columns: repeat(2, 1fr); }
    .bld-greeting  { font-size: 2.3rem; }
}

.bld-radar-host .js-plotly-plot { margin-top: -6px !important; }
.bl-page div[data-testid="column"] { padding: 0 0.35rem; }
</style>
"""


# ------------------------------------------------------------------
#  Public entry point
# ------------------------------------------------------------------
def render_dashboard(user: Dict[str, Any]) -> None:
    """Render the BarrelLabs dashboard for the given user."""
    # Global design system + dashboard-specific styles
    inject_global_theme()
    st.markdown(_DASHBOARD_LOCAL_CSS, unsafe_allow_html=True)
    st.markdown('<div class="bl-page">', unsafe_allow_html=True)

    history = _safe_history(user)
    latest = history[-1] if history else None

    _render_header(user, latest)

    if not latest:
        _render_empty_state()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Top row: score gauge (5) | MLB compare (7)
    top_l, top_r = st.columns([5, 7], gap="large")
    with top_l:
        _render_score_card(latest)
    with top_r:
        _render_mlb_card(latest)

    st.markdown('<div style="height:1.8rem;"></div>', unsafe_allow_html=True)

    # Radar (7) | Recent swings (5)
    mid_l, mid_r = st.columns([7, 5], gap="large")
    with mid_l:
        _render_radar_card(latest)
    with mid_r:
        _render_recent_card(history)

    _render_cta()
    st.markdown('</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
#  Section renderers
# ------------------------------------------------------------------
def _render_header(user: Dict[str, Any], latest: Optional[Dict[str, Any]]) -> None:
    first = (user.get("name") or "Player").split()[0]
    swing_count = _swing_count_str(user)
    when_label = _format_when(latest.get("timestamp") if latest else None)

    sub_html = (
        f"Last swing analyzed {when_label}."
        if latest else
        "Drop your first swing to populate the dashboard."
    )

    html = textwrap.dedent(f"""
    <div class="bld-hero">
      <div class="bld-hero-row">
        <div>
          <div class="bl-section-eyebrow">BARRELLABS · SWINGAI · DASHBOARD</div>
          <div class="bld-greeting">Welcome back, {first}<span class="bl-period">.</span></div>
          <div class="bld-subline">Your hitting lab is live. {sub_html}</div>
        </div>
        <div class="bld-status-stack">
          <div class="bld-status-pill">Live</div>
          <div class="bld-trailing-meta">{swing_count}</div>
          <div class="bld-trailing-meta">SwingAI v1.0</div>
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_empty_state() -> None:
    html = textwrap.dedent("""
    <div class="bld-empty">
      <div class="bld-empty-icon">⌖</div>
      <div class="bld-empty-title">Your first swing unlocks everything.</div>
      <div class="bld-empty-sub">
        Drop a side-angle clip and we'll generate your swing score,
        MLB comparison, biomechanical radar, and a personalized drill
        plan in under a minute.
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)
    _render_cta()


def _render_score_card(record: Dict[str, Any]) -> None:
    """
    Score ring:
      * Inside the circle: large number + ONE short tag (≤ 1 word).
      * Below the circle: full `score_band_label` descriptor if it's
        longer than the inside tag, then the "Out of 100" footnote.
    Prevents long phrases (e.g. "Decent match — clear fixes available")
    from overflowing the ring.
    """
    score = max(0, min(100, int(round(record.get("score") or 0))))
    full_label = (record.get("score_band_label") or "").strip()
    band_color = record.get("score_band_color") or "amber"
    hex_color, _ = _score_color(band_color)

    short_tag = _short_band_tag(band_color)
    band_descriptor = full_label  # rendered BELOW the ring

    radius = 92
    circumf = 2 * 3.14159265 * radius
    dashoffset = circumf * (1 - score / 100.0)

    descriptor_html = (
        f'<div class="bld-score-band">{band_descriptor}</div>'
        if band_descriptor else ""
    )

    html = textwrap.dedent(f"""
    <div class="bl-card bld-score-card">
      <div>
        <div class="bl-card-eyebrow">SWING SCORE</div>
        <div class="bl-card-title">Latest performance index</div>
      </div>
      <div class="bld-score-ring">
        <svg viewBox="0 0 200 200">
          <circle class="bld-score-track" cx="100" cy="100" r="{radius}"></circle>
          <circle class="bld-score-fill"
                  cx="100" cy="100" r="{radius}"
                  stroke="{hex_color}"
                  style="stroke-dasharray:{circumf};stroke-dashoffset:{dashoffset};"></circle>
        </svg>
        <div class="bld-score-center">
          <div class="bld-score-number">{score}</div>
          <div class="bld-score-tag" style="color:{hex_color};">{short_tag}</div>
        </div>
      </div>
      {descriptor_html}
      <div class="bld-score-foot">Out of 100 · mechanics &amp; reference match.</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_mlb_card(record: Dict[str, Any]) -> None:
    ref_name = record.get("reference_name") or "Reference"
    sim_pct = _similarity_pct(record)
    sim_disp = f"{int(round(sim_pct))}%"
    pretty = _pretty_player_name(ref_name)
    handed = (record.get("player_handedness") or "").upper()
    hand_disp = (
        "RIGHT-HANDED" if handed.startswith("R") else
        "LEFT-HANDED"  if handed.startswith("L") else "—"
    )

    html = textwrap.dedent(f"""
    <div class="bl-card bld-mlb-card">
      <div>
        <div class="bl-card-eyebrow">MLB COMPARISON</div>
        <div class="bl-card-title">Closest pro swing match</div>
      </div>
      <div class="bld-mlb-row">
        <div class="bld-mlb-avatar">
          <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="42" cy="20" r="6" stroke="#FF3B30" stroke-width="2"/>
            <path d="M42 26 L42 50 L52 56" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/>
            <path d="M42 32 L60 38 L78 30 L88 22" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/>
            <path d="M52 56 L42 78" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/>
            <path d="M52 56 L68 80" stroke="#FF3B30" stroke-width="2" stroke-linecap="round"/>
            <circle cx="88" cy="22" r="2" fill="#FF3B30"/>
          </svg>
        </div>
        <div class="bld-mlb-meta">
          <div class="bld-mlb-tag">YOU SWING MOST LIKE</div>
          <div class="bld-mlb-name">{pretty}</div>
          <div class="bld-mlb-sub">{hand_disp} reference swing</div>
        </div>
      </div>
      <div>
        <div class="bld-sim-bar-wrap">
          <div class="bld-sim-bar-fill" style="width:{sim_pct:.1f}%;"></div>
        </div>
        <div class="bld-sim-foot">
          <span>SIMILARITY</span>
          <strong>{sim_disp}</strong>
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_radar_card(record: Dict[str, Any]) -> None:
    metrics = _radar_from_record(record)

    open_html = textwrap.dedent("""
    <div class="bl-card bld-radar-host">
      <div class="bl-card-eyebrow">SWING BREAKDOWN</div>
      <div class="bl-card-title">Biomechanical signature</div>
    """).strip()
    st.markdown(open_html, unsafe_allow_html=True)

    fig = _build_radar_figure(metrics)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # KPI chips — built as one flat string so Streamlit's Markdown
    # parser can never treat indented HTML as a code block.
    parts = ['<div class="bld-kpi-strip">']
    for label, value in metrics[:4]:
        parts.append(
            f'<div class="bld-kpi">'
            f'<div class="bld-kpi-label">{label}</div>'
            f'<div class="bld-kpi-value">{int(round(value))}</div>'
            f'</div>'
        )
    parts.append("</div></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_recent_card(history: List[Dict[str, Any]]) -> None:
    """
    Recent Swings — each row is a Streamlit button styled (via CSS) to
    look like the original glass row. Clicking opens the saved report.
    """
    recent = list(reversed(history))[:5]

    # Card shell (eyebrow + title) — rendered as HTML so it sits visually
    # above the button rows.
    st.markdown(
        '<div class="bl-card bld-recent-card">'
        '<div class="bl-card-eyebrow">RECENT SWINGS</div>'
        f'<div class="bl-card-title">Your last {len(recent)} uploads</div>'
        '<div class="bld-recent-hint">Tap any swing to open the full report</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not recent:
        st.markdown(
            '<div class="bld-recent-empty-wrap">'
            '<div class="bld-recent-empty">No swings yet. Upload one to get started.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Wrap all the rows in a flex column so they look like one stacked
    # list, but each row is a real, clickable Streamlit button.
    st.markdown('<div class="bld-recent-list-real">', unsafe_allow_html=True)

    for idx, rec in enumerate(recent):
        n = rec.get("swing_number") or "—"
        try:
            num_disp = f"#{int(n):02d}"
        except Exception:
            num_disp = f"#{n}"
        date = _format_short_date(rec.get("timestamp"))
        score = int(round(rec.get("score") or 0))
        ref = _pretty_player_name(rec.get("reference_name") or "")
        title = f"Swing {n}" + (f" · vs {ref}" if ref else "")

        # Streamlit button labels don't render HTML, so we use a 3-line
        # plain-text label and rely on CSS to lay it out. The dot
        # separator is a soft visual cue between fields.
        # Format: "#04   Swing 4 · vs Mike Trout   ·   May 12 · SCORE 78"
        label = f"{num_disp}     {title}     ·     {date}     ·     {score}    ›"

        st.markdown(
            f'<div class="bld-recent-row-btn" data-score="{score}">',
            unsafe_allow_html=True,
        )
        btn_key = f"bld_recent_open_{idx}_{rec.get('id') or rec.get('timestamp') or idx}"
        if st.button(label, key=btn_key, width="stretch"):
            # Prefer storing the full record so we don't depend on a disk
            # path (Supabase records have _record_path = None).
            st.session_state["view_swing_record"] = rec
            # Keep legacy path-based key in sync for older code paths.
            rp = rec.get("_record_path")
            if rp:
                st.session_state["view_swing_path"] = rp
            else:
                st.session_state.pop("view_swing_path", None)
            st.session_state.pop("page", None)
            st.session_state.pop("view", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def _render_cta() -> None:
    st.markdown('<div style="height:2.6rem;"></div>', unsafe_allow_html=True)
    _, cta_c, _ = st.columns([1, 1.4, 1])
    with cta_c:
        st.markdown('<div class="bl-cta">', unsafe_allow_html=True)
        clicked = st.button(
            "Analyze a new swing  →",
            width="stretch",
            key="bld_cta_upload",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if clicked:
            st.session_state.pop("page", None)
            st.session_state["view"] = "upload"
            st.rerun()


# ------------------------------------------------------------------
#  Plotly radar figure
# ------------------------------------------------------------------
def _build_radar_figure(metrics: List[Tuple[str, float]]) -> go.Figure:
    labels = [m[0] for m in metrics]
    values = [m[1] for m in metrics]
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        mode="lines+markers",
        line=dict(color="#FF3B30", width=2),
        marker=dict(color="#FF3B30", size=6, line=dict(color="#050505", width=2)),
        fill="toself",
        fillcolor="rgba(255,59,48,0.12)",
        hovertemplate="<b>%{theta}</b><br>%{r:.0f}<extra></extra>",
        name="Latest swing",
    ))
    fig.update_layout(
        height=360,
        margin=dict(l=46, r=46, t=24, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        polar=dict(
            bgcolor="rgba(255,255,255,0.008)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[20, 40, 60, 80, 100],
                tickfont=dict(family="JetBrains Mono", size=9, color="#5c5c5c"),
                gridcolor="rgba(255,255,255,0.045)",
                linecolor="rgba(255,255,255,0.04)",
            ),
            angularaxis=dict(
                tickfont=dict(family="Inter", size=11, color="#d4d4d4"),
                gridcolor="rgba(255,255,255,0.04)",
                linecolor="rgba(255,255,255,0.06)",
            ),
        ),
    )
    return fig


# ------------------------------------------------------------------
#  Data helpers
# ------------------------------------------------------------------
def _safe_history(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        pid = user.get("id") or user.get("slug")
        if not pid:
            return []
        return load_swing_history(pid) or []
    except Exception:
        return []


def _similarity_pct(record: Dict[str, Any]) -> float:
    score = record.get("score")
    if isinstance(score, (int, float)) and 0 <= float(score) <= 100:
        return float(score)
    sims: List[float] = []
    mt = record.get("metric_table") or {}
    if isinstance(mt, dict):
        for group_rows in mt.values():
            if not isinstance(group_rows, list):
                continue
            for r in group_rows:
                try:
                    sims.append(float(r.get("sim_pct", 0)))
                except Exception:
                    pass
    return (sum(sims) / len(sims)) if sims else 0.0


def _radar_from_record(record: Dict[str, Any]) -> List[Tuple[str, float]]:
    buckets: Dict[str, List[float]] = {
        "Bat Speed":        [],
        "Attack Angle":     [],
        "Rotational Power": [],
        "Connection":       [],
        "Barrel Control":   [],
    }
    keyword_map = {
        "Bat Speed":        ["bat speed", "speed", "velocity", "swing speed", "exit"],
        "Attack Angle":     ["angle", "attack", "tilt", "plane"],
        "Rotational Power": ["hip", "rotation", "rotational", "power", "torque", "shoulder"],
        "Connection":       ["connection", "lag", "sync", "timing", "stride"],
        "Barrel Control":   ["barrel", "contact", "extension", "path", "control"],
    }

    mt = record.get("metric_table") or {}
    if isinstance(mt, dict):
        for group_rows in mt.values():
            if not isinstance(group_rows, list):
                continue
            for r in group_rows:
                label = (r.get("label") or "").lower()
                try:
                    sim = float(r.get("sim_pct", 0))
                except Exception:
                    continue
                for axis, kws in keyword_map.items():
                    if any(k in label for k in kws):
                        buckets[axis].append(sim)
                        break

    overall = _similarity_pct(record)
    out: List[Tuple[str, float]] = []
    for axis, sims in buckets.items():
        out.append((axis, (sum(sims) / len(sims)) if sims else overall * 0.9))
    return out


def _swing_count_str(user: Dict[str, Any]) -> str:
    try:
        n = len(_safe_history(user))
    except Exception:
        n = 0
    return f"{n:03d} SWINGS LOGGED"


def _score_color(band_color: Optional[str]) -> Tuple[str, str]:
    band = (band_color or "").lower()
    if band in ("green", "emerald"):
        return ("#34c759", "🟢")
    if band in ("amber", "yellow"):
        return ("#ffcc00", "🟡")
    if band in ("red", "crimson"):
        return ("#FF3B30", "🔴")
    return ("#FF3B30", "🔴")


def _short_band_tag(band_color: Optional[str]) -> str:
    """Map the raw band color to a single-word descriptor that fits inside
    the score ring without overflowing."""
    band = (band_color or "").lower()
    if band in ("green", "emerald"):
        return "DIALED"
    if band in ("amber", "yellow"):
        return "TRACKING"
    if band in ("red", "crimson"):
        return "BUILDING"
    return "TRACKING"


def _pretty_player_name(slug: str) -> str:
    if not slug:
        return ""
    base = str(slug)
    for suffix in ("_swing", " copy", ".mp4"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    base = base.replace("_", " ").replace("-", " ").strip()
    return " ".join(
        w.capitalize() if w.lower() not in ("jr", "sr") else w.upper() + "."
        for w in base.split()
    )


def _format_when(ts: Optional[str]) -> str:
    if not ts:
        return "moments ago"
    try:
        dt: Optional[datetime] = None
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
            except Exception:
                pass
        if not dt:
            return ts
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        if delta.days >= 1:
            return f"{delta.days}d ago"
        hrs = delta.seconds // 3600
        if hrs >= 1:
            return f"{hrs}h ago"
        mins = max(1, delta.seconds // 60)
        return f"{mins}m ago"
    except Exception:
        return ts


def _format_short_date(ts: Optional[str]) -> str:
    if not ts:
        return ""
    try:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
        return dt.strftime("%b %d, %Y").upper()
    except Exception:
        return str(ts)
