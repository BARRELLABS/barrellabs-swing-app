"""
Performance Over Time — BarrelLabs premium edition.

A full player-development analytics center, layered on top of the
bl_theme design system. Reads the current logged-in player's swing
history from public.swings and surfaces:

  • KPI summary cards (Total analyses, Best score, Average score,
    Total improvement, Last upload)
  • Personal-best / streak badges
  • Time-range filter (7 / 30 / 90 / All)
  • Metric selector + optional moving-average overlay
  • Smooth Plotly chart with gradient fill, PB marker, and hover
  • Auto-generated Trend Insights (observations about progress)
  • Metric Comparison Table (first / latest / net / pct)
  • Milestone tracker
  • Quick-access cards to the most recent reports (click → opens)
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from bl_theme import (
    inject_global_theme,
    BL_RED,
    BL_GOLD,
    BL_POSITIVE,
    BL_NEGATIVE,
    BL_SECONDARY,
    BL_FONT_SANS,
    BL_FONT_MONO,
)
from bl_edge_chrome import render_edge_masthead
from player_storage import load_swing_history


_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")


# ============================================================
#                    PAGE-LOCAL STYLES
# ============================================================
_HC_LOCAL_CSS = """
<style>
/* ===========  HERO  =========== */
.hc-hero {
    position: relative;
    padding: 2.2rem 2.4rem 2.4rem;
    border-radius: var(--bl-radius-xl);
    background: linear-gradient(160deg,
                rgba(232,193,112,0.07) 0%,
                rgba(255,255,255,0.025) 38%,
                rgba(255,255,255,0.015) 100%);
    border: 1px solid var(--bl-line);
    overflow: hidden;
    margin-bottom: 2rem;
}
.hc-hero::before {
    content: "";
    position: absolute;
    top: -120px; right: -160px;
    width: 420px; height: 420px;
    background: radial-gradient(circle, rgba(232,193,112,0.14), transparent 65%);
    filter: blur(60px);
    pointer-events: none;
}
.hc-hero-row {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 1.4rem; position: relative; z-index: 1;
}
.hc-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.28em;
    color: var(--bl-gold);
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}
.hc-title {
    font-family: var(--bl-sans);
    font-style: normal;
    font-size: clamp(2rem, 7vw, 2.8rem);
    font-weight: 700;
    letter-spacing: -0.01em;
    text-transform: uppercase;
    color: var(--bl-ink-100);
    line-height: 1.04;
    margin-bottom: 0.65rem;
    overflow-wrap: break-word;
    word-break: normal;
}
.hc-sub {
    color: var(--bl-ink-60);
    font-size: 0.96rem;
    line-height: 1.55;
    max-width: 580px;
}
.hc-mode-pill {
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-gold);
    background: rgba(232,193,112,0.08);
    border: 1px solid rgba(232,193,112,0.22);
    border-radius: 999px;
    padding: 0.42rem 0.85rem;
    text-transform: uppercase;
    white-space: nowrap;
}
.hc-mode-pill-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--bl-gold);
    box-shadow: 0 0 8px rgba(232,193,112,0.6);
}

/* ===========  BADGE STRIP (Personal Best / Above Avg / Trending Up)  =========== */
.hc-badges {
    display: flex; flex-wrap: wrap; gap: 0.55rem;
    margin: 0 0 1.5rem 0;
}
.hc-badge {
    display: inline-flex; align-items: center; gap: 0.5rem;
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    padding: 0.45rem 0.85rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    color: var(--bl-ink-60);
}
.hc-badge .hc-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: currentColor;
}
.hc-badge.is-pb {
    color: var(--bl-gold);
    background: rgba(232,193,112,0.06);
    border-color: rgba(232,193,112,0.32);
    box-shadow: 0 0 18px -8px rgba(232,193,112,0.5);
}
.hc-badge.is-up {
    color: var(--bl-gold);
    background: rgba(232,193,112,0.06);
    border-color: rgba(232,193,112,0.32);
}
.hc-badge.is-above {
    color: var(--bl-ink-80);
    background: rgba(244,239,230,0.05);
    border-color: var(--bl-line-hi);
}
.hc-badge.is-streak {
    color: var(--bl-ink-80);
    background: rgba(200,196,187,0.06);
    border-color: rgba(200,196,187,0.30);
}

/* ===========  KPI STRIP  =========== */
.hc-stat-strip {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.85rem;
    margin-bottom: 2rem;
}
@media (max-width: 980px) { .hc-stat-strip { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 720px) { .hc-stat-strip { grid-template-columns: repeat(2, 1fr); } }
.hc-stat {
    padding: 1.1rem 1.2rem;
    border-radius: var(--bl-radius-md);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    transition: border-color .25s ease, transform .25s ease;
}
.hc-stat:hover {
    border-color: var(--bl-line-hi);
    transform: translateY(-1px);
}
.hc-stat-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 600;
    letter-spacing: 0.24em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}
.hc-stat-value {
    font-family: var(--bl-mono);
    font-size: 1.55rem;
    font-weight: 600;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    line-height: 1.05;
    font-variant-numeric: tabular-nums;
}
.hc-stat-value.is-red   { color: var(--bl-red); }
.hc-stat-value.is-gold  { color: var(--bl-gold); }
.hc-stat-value.is-up    { color: var(--bl-gold); }
.hc-stat-value.is-down  { color: var(--bl-red); }
.hc-stat-foot {
    margin-top: 0.5rem;
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    letter-spacing: 0.14em;
    color: var(--bl-ink-60);
    text-transform: uppercase;
}

/* ===========  SECTION HEADERS  =========== */
.hc-section-header {
    display: flex; align-items: center; gap: 0.9rem;
    margin: 2rem 0 0.95rem 0;
}
.hc-section-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    color: var(--bl-gold);
    text-transform: uppercase;
}
.hc-section-title {
    font-family: var(--bl-sans);
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: 0.005em;
    text-transform: uppercase;
    color: var(--bl-ink-100);
}
.hc-section-count {
    margin-left: auto;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}

/* ===========  CONTROL BAR (metric picker + filters)  =========== */
.hc-controls-card {
    padding: 1.3rem 1.5rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: 1.5rem;
}
.hc-controls-card [data-baseweb="select"] > div,
.hc-controls-card input[type="text"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bl-ink-100) !important;
    border-radius: 12px !important;
    transition: border-color .2s ease !important;
}
.hc-controls-card [data-baseweb="select"] > div:hover {
    border-color: var(--bl-line-hi) !important;
}
.hc-controls-card [data-testid="stSelectbox"] label,
.hc-controls-card [data-testid="stSelectbox"] label p,
.hc-controls-card [data-testid="stCheckbox"] label,
.hc-controls-card [data-testid="stCheckbox"] label p,
.hc-controls-card [data-testid="stRadio"] label,
.hc-controls-card [data-testid="stRadio"] label p {
    font-family: var(--bl-mono) !important;
    font-size: 0.6rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    color: var(--bl-ink-40) !important;
    text-transform: uppercase !important;
}
.hc-controls-card [data-testid="stCheckbox"] [data-baseweb="checkbox"][aria-checked="true"] div[role="checkbox"] {
    background: var(--bl-gold) !important;
    border-color: var(--bl-gold) !important;
    box-shadow: 0 0 8px rgba(232,193,112,0.4) !important;
}

/* ===========  CHART CARD  =========== */
.hc-chart-card {
    padding: 1.7rem 1.8rem 1.4rem 1.8rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: 1.5rem;
}
.hc-chart-head {
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 1rem; margin-bottom: 0.7rem;
}
.hc-chart-title {
    font-family: var(--bl-sans);
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.005em;
    text-transform: uppercase;
    color: var(--bl-ink-100);
}
.hc-chart-sub {
    margin-top: 0.2rem;
    color: var(--bl-ink-60);
    font-size: 0.85rem;
}
.hc-chart-trend {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 0.4rem 0.8rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    color: var(--bl-ink-60);
    white-space: nowrap;
}
.hc-chart-trend.is-up   { color: var(--bl-gold); border-color: rgba(232,193,112,0.32); background: rgba(232,193,112,0.06); }
.hc-chart-trend.is-down { color: var(--bl-red); border-color: rgba(230,69,48,0.32); background: rgba(230,69,48,0.06); }

/* ===========  INSIGHTS CARD  =========== */
.hc-insights {
    padding: 1.6rem 1.8rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: 1.5rem;
}
.hc-insight-row {
    display: flex; align-items: flex-start; gap: 0.85rem;
    padding: 0.65rem 0;
    border-top: 1px solid var(--bl-line);
}
.hc-insight-row:first-of-type { border-top: none; padding-top: 0; }
.hc-insight-icon {
    flex: 0 0 32px;
    width: 32px; height: 32px;
    border-radius: 999px;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.95rem; font-weight: 700;
    background: rgba(230,69,48,0.08);
    color: var(--bl-red);
    border: 1px solid rgba(230,69,48,0.25);
}
.hc-insight-text {
    flex: 1;
    color: var(--bl-ink-80);
    font-size: 0.95rem;
    line-height: 1.5;
}
.hc-insight-text strong { color: var(--bl-ink-100); }

/* ===========  COMPARISON TABLE  =========== */
.hc-table-wrap {
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    overflow: hidden;
    margin-bottom: 1.5rem;
}
.hc-table-head, .hc-table-row {
    display: grid;
    grid-template-columns: 2.4fr 1fr 1fr 1fr 1fr;
    align-items: center;
    padding: 0.85rem 1.4rem;
}
.hc-table-head {
    background: rgba(255,255,255,0.015);
    border-bottom: 1px solid var(--bl-line);
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}
.hc-table-row { border-top: 1px solid var(--bl-line); }
.hc-table-row:first-of-type { border-top: none; }
.hc-table-row:hover { background: rgba(255,255,255,0.012); }
.hc-table-metric {
    color: var(--bl-ink-100);
    font-size: 0.92rem;
    font-weight: 500;
    letter-spacing: -0.005em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    padding-right: 0.5rem;
}
.hc-table-num {
    font-family: var(--bl-mono);
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--bl-ink-80);
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-variant-numeric: tabular-nums;
}
.hc-table-num.is-up   { color: var(--bl-gold); }
.hc-table-num.is-down { color: var(--bl-red); }
.hc-table-num.is-strong { color: var(--bl-ink-100); font-weight: 600; }

/* "What's changed" plain-language highlight cards (replaced the dense table) */
.hc-change-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem;
    margin: 0.4rem 0 0.7rem;
}
@media (max-width: 760px) { .hc-change-grid { grid-template-columns: 1fr; } }
.hc-change-card {
    border: 1px solid var(--bl-line); border-radius: 14px;
    background: rgba(255,255,255,0.02); padding: 1.15rem 1.25rem;
}
.hc-change-label {
    font-family: var(--bl-mono); font-size: 0.58rem; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--bl-gold); margin-bottom: 0.55rem;
}
.hc-change-big {
    font-family: var(--bl-mono); font-size: 1.5rem; font-weight: 600;
    color: var(--bl-ink-100); letter-spacing: -0.01em; line-height: 1.12;
    font-variant-numeric: tabular-nums;
}
.hc-change-to { color: var(--bl-ink-80); margin: 0 0.12em; }
.hc-change-sub { margin-top: 0.55rem; font-size: 0.84rem; color: var(--bl-ink-80); }
.hc-change-sub.is-up { color: var(--bl-gold); }
.hc-change-sub.is-down { color: var(--bl-red); }

/* ===========  MILESTONES  =========== */
.hc-milestones {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.85rem;
    margin-bottom: 1.5rem;
}
@media (max-width: 720px) { .hc-milestones { grid-template-columns: 1fr; } }
.hc-milestone {
    padding: 1rem 1.2rem;
    border-radius: var(--bl-radius-md);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    display: grid;
    grid-template-columns: 40px 1fr auto;
    align-items: center;
    gap: 1rem;
    transition: border-color .25s ease, background .25s ease;
}
.hc-milestone.is-done {
    border-color: rgba(232,193,112,0.32);
    background: linear-gradient(180deg, rgba(232,193,112,0.04), rgba(255,255,255,0.012) 70%);
}
.hc-milestone-icon {
    width: 40px; height: 40px;
    border-radius: 999px;
    display: inline-flex; align-items: center; justify-content: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bl-line);
    color: var(--bl-ink-60);
    font-size: 1.05rem;
}
.hc-milestone.is-done .hc-milestone-icon {
    background: rgba(232,193,112,0.10);
    border-color: rgba(232,193,112,0.42);
    color: var(--bl-gold);
}
.hc-milestone-body { min-width: 0; }
.hc-milestone-title {
    color: var(--bl-ink-100);
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.005em;
}
.hc-milestone-sub {
    color: var(--bl-ink-60);
    font-size: 0.78rem;
    margin-top: 0.2rem;
}
.hc-milestone-status {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    text-transform: uppercase;
}
.hc-milestone.is-done .hc-milestone-status {
    color: var(--bl-gold);
    background: rgba(232,193,112,0.07);
    border-color: rgba(232,193,112,0.32);
}

/* ===========  QUICK-OPEN REPORT ROWS  =========== */
.hc-quick-list {
    display: flex; flex-direction: column; gap: 0.55rem;
    margin-bottom: 1rem;
}
/* The recent-report buttons. Targeted by their st-key wrapper (the old
   .hc-quick-btn wrapper div never actually wrapped the widget, so these
   rendered as default Streamlit buttons). */
[class*="st-key-hc_quick_"] button {
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    background: rgba(244,239,230,0.025) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: var(--bl-radius-md) !important;
    color: var(--bl-ink-80) !important;
    padding: 0.85rem 1.1rem !important;
    min-height: 0 !important; height: auto !important;
    font-family: var(--bl-mono) !important;
    font-weight: 500 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    box-shadow: none !important;
    transition: border-color .2s ease, background .2s ease, transform .2s ease !important;
}
[class*="st-key-hc_quick_"] button p {
    font: inherit !important; color: inherit !important; margin: 0 !important;
    letter-spacing: inherit !important; text-align: left !important; width: 100% !important;
}
[class*="st-key-hc_quick_"] button:hover {
    border-color: rgba(232,193,112,0.4) !important;
    background: rgba(232,193,112,0.06) !important;
    color: var(--bl-ink-100) !important;
    transform: translateX(2px);
}

/* ===========  EMPTY  =========== */
.hc-empty {
    text-align: center;
    padding: 4rem 2rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px dashed var(--bl-line-hi);
}
.hc-empty-icon { font-size: 2.4rem; color: var(--bl-gold); margin-bottom: 1rem; opacity: 0.7; }
.hc-empty-title { font-family: var(--bl-sans); font-size: 1.3rem; font-weight: 600; color: var(--bl-ink-100); margin-bottom: 0.55rem; letter-spacing: -0.012em; }
.hc-empty-sub { color: var(--bl-ink-60); font-size: 0.95rem; line-height: 1.55; max-width: 460px; margin: 0 auto; }

/* ===========  BACK NAV  =========== */
.hc-back .stButton > button {
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
.hc-back .stButton > button:hover {
    border-color: rgba(230,69,48,0.35) !important;
    color: var(--bl-red) !important;
    background: rgba(230,69,48,0.05) !important;
    transform: translateX(-2px);
}

.hc-data-wrap details {
    background: var(--bl-surface-1) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: var(--bl-radius-md) !important;
    overflow: hidden;
}
.hc-data-wrap details > summary {
    padding: 0.85rem 1.1rem !important;
    font-family: var(--bl-mono) !important;
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    color: var(--bl-ink-60) !important;
    text-transform: uppercase !important;
}
</style>
"""


# ============================================================
#                       HELPERS
# ============================================================
def parse_numeric(value):
    """Best-effort: pull a signed number out of strings like '+8.8°'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _NUMERIC_RE.search(value)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _parse_date_record(rec: dict) -> Optional[datetime]:
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


def load_player_history_df(player_id: str) -> pd.DataFrame:
    """Build a wide DataFrame from this player's saved swings."""
    swings = load_swing_history(player_id)
    if not swings:
        return pd.DataFrame()

    rows = []
    for swing in swings:
        dt = _parse_date_record(swing)
        row = {
            "file": swing.get("filename") or swing.get("timestamp"),
            "date": swing.get("date") or swing.get("timestamp"),
            "_dt": dt,
            "Swing Score": swing.get("score"),
            "Swing Duration (ms)": swing.get("swing_duration_ms"),
        }

        metric_table = swing.get("metric_table") or {}
        if isinstance(metric_table, dict):
            for group_rows in metric_table.values():
                if not isinstance(group_rows, list):
                    continue
                for m in group_rows:
                    if not isinstance(m, dict):
                        continue
                    label = m.get("label")
                    if not label:
                        continue
                    numeric_value = parse_numeric(m.get("player_str"))
                    if numeric_value is not None:
                        row[label] = numeric_value
                    sim = m.get("sim_pct")
                    if isinstance(sim, (int, float)):
                        row[f"{label} (Match %)"] = float(sim)

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).reset_index(drop=True)
    df["Analysis #"] = range(1, len(df) + 1)
    return df


def _fmt_value(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _style_plotly(fig: go.Figure, y_title: str) -> go.Figure:
    """Apply BarrelLabs theme to a Plotly chart."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=460,
        margin=dict(l=10, r=10, t=10, b=40),
        font=dict(
            family=BL_FONT_SANS,
            color="rgba(255,255,255,0.78)",
            size=12,
        ),
        xaxis=dict(
            title=dict(text="ANALYSIS #", font=dict(size=10, color="rgba(255,255,255,0.42)")),
            gridcolor="rgba(255,255,255,0.045)",
            zerolinecolor="rgba(255,255,255,0.08)",
            tickfont=dict(size=11, color="rgba(255,255,255,0.55)"),
        ),
        yaxis=dict(
            title=dict(text=y_title.upper(), font=dict(size=10, color="rgba(255,255,255,0.42)")),
            gridcolor="rgba(255,255,255,0.045)",
            zerolinecolor="rgba(255,255,255,0.08)",
            tickfont=dict(size=11, color="rgba(255,255,255,0.55)"),
        ),
        hoverlabel=dict(
            bgcolor="rgba(10,10,12,0.95)",
            bordercolor="rgba(230,69,48,0.35)",
            font=dict(family=BL_FONT_SANS, color="#fafafa", size=12),
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color="rgba(255,255,255,0.6)"),
        ),
    )
    return fig


def _render_empty_state(title: str, sub: str, icon: str = "◇"):
    html = textwrap.dedent(f"""
    <div class="hc-empty">
      <div class="hc-empty-icon">{icon}</div>
      <div class="hc-empty-title">{title}</div>
      <div class="hc-empty-sub">{sub}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _strongest_improver(df: pd.DataFrame, numeric_metrics: list) -> Optional[tuple]:
    """Return (metric, pct_change) for the metric that improved the most.
    'Improved' = larger latest value than first. Used for Trend Insights."""
    best = None
    for m in numeric_metrics:
        s = df[m].dropna()
        if len(s) < 2:
            continue
        first, last = s.iloc[0], s.iloc[-1]
        if first == 0 or pd.isna(first) or pd.isna(last):
            continue
        pct = (last - first) / abs(first) * 100
        if best is None or pct > best[1]:
            best = (m, pct)
    return best


def _largest_opportunity(df: pd.DataFrame, numeric_metrics: list) -> Optional[tuple]:
    """Return (metric, latest_value) for the Match % metric with the
    LOWEST latest reading — that's where the player has the most room."""
    candidates = [m for m in numeric_metrics if m.endswith("(Match %)")]
    worst = None
    for m in candidates:
        s = df[m].dropna()
        if not len(s):
            continue
        last = s.iloc[-1]
        if pd.isna(last):
            continue
        if worst is None or last < worst[1]:
            worst = (m, last)
    return worst


# Plain-language labels so the page never shows raw jargon like
# "Peak hip-shoulder separation (Match %)". Maps the analysis column names
# to friendly names; the underlying data/columns are untouched.
_FRIENDLY_METRIC = {
    "Swing Score":                                  "Swing Score",
    "Swing Duration (ms)":                          "Swing length",
    "Peak hip-shoulder separation":                 "Hip-shoulder turn",
    "Peak hip-shoulder separation (Match %)":       "Hip-shoulder turn (vs pros)",
    "Launch → contact":                             "Swing timing",
    "Launch → contact (Match %)":                   "Swing timing (vs pros)",
    "Total head drift (torso-rel)":                 "Head movement",
    "Total head drift (torso-rel) (Match %)":       "Head movement (vs pros)",
}


def _friendly_metric(col) -> str:
    """Friendly display name for a metric column (no jargon)."""
    if col in _FRIENDLY_METRIC:
        return _FRIENDLY_METRIC[col]
    label = str(col)
    label = label.replace(" (torso-rel)", "")
    label = label.replace("(Match %)", "(vs pros)").replace("Match %", "vs pros")
    label = label.replace("→", "to")
    return label


def build_progress_pdf(player_name: str, df: pd.DataFrame,
                       numeric_metrics: list) -> bytes:
    """One-page printable Progress summary, dark-themed to match the app.
    Header + key stats + a first->latest table for the friendly metrics
    (the full numbers the on-screen page intentionally keeps simple)."""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as _canvas

    INK, BONE, GOLD, MUT, RED = (
        (0.039, 0.043, 0.055), (0.957, 0.937, 0.902),
        (0.910, 0.757, 0.439), (0.55, 0.55, 0.58), (0.90, 0.27, 0.19),
    )
    buf = BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    W, H = letter
    M = 0.85 * inch
    c.setFillColorRGB(*INK); c.rect(0, 0, W, H, fill=1, stroke=0)

    y = H - 0.95 * inch
    c.setFillColorRGB(*GOLD); c.setFont("Helvetica-Bold", 9)
    c.drawString(M, y, "BARRELLABS  ·  PROGRESS OVER TIME")
    y -= 0.42 * inch
    c.setFillColorRGB(*BONE); c.setFont("Helvetica-Bold", 24)
    c.drawString(M, y, str(player_name or "Player"))
    y -= 0.18 * inch
    c.setFillColorRGB(*MUT); c.setFont("Helvetica", 10)
    try:
        _dts = df["date"].dropna()
        c.drawString(M, y, f"{len(df)} swings   ·   {str(_dts.iloc[0])[:10]} to {str(_dts.iloc[-1])[:10]}")
    except Exception:
        c.drawString(M, y, f"{len(df)} swings")
    y -= 0.55 * inch

    ss = df["Swing Score"].dropna() if "Swing Score" in df.columns else None
    cells = []
    if ss is not None and len(ss):
        cells.append(("LATEST SCORE", _fmt_value(ss.iloc[-1])))
        if len(ss) >= 2:
            d = ss.iloc[-1] - ss.iloc[0]
            cells.append(("CHANGE", f'{"+" if d >= 0 else ""}{_fmt_value(d)}'))
        cells.append(("BEST", _fmt_value(ss.max())))
    cells.append(("SESSIONS", str(len(df))))
    cw = (W - 2 * M) / max(1, len(cells))
    for k, (lab, val) in enumerate(cells):
        x = M + k * cw
        c.setFillColorRGB(*MUT); c.setFont("Helvetica", 7.5); c.drawString(x, y, lab)
        c.setFillColorRGB(*BONE); c.setFont("Helvetica-Bold", 20)
        c.drawString(x, y - 0.3 * inch, str(val))
    y -= 0.95 * inch

    c.setFillColorRGB(*GOLD); c.setFont("Helvetica-Bold", 8)
    c.drawString(M, y, "METRIC")
    c.drawRightString(W - M - 1.7 * inch, y, "FIRST")
    c.drawRightString(W - M - 0.85 * inch, y, "LATEST")
    c.drawRightString(W - M, y, "CHANGE")
    y -= 0.1 * inch
    c.setStrokeColorRGB(0.2, 0.2, 0.22); c.line(M, y, W - M, y)
    y -= 0.28 * inch

    ordered = ["Swing Score"] + [m for m in numeric_metrics if m != "Swing Score"]
    shown = 0
    for m in ordered:
        if m not in df.columns:
            continue
        s = df[m].dropna()
        if len(s) < 1:
            continue
        first, last = s.iloc[0], s.iloc[-1]
        net = (last - first) if len(s) >= 2 else None
        c.setFillColorRGB(*BONE); c.setFont("Helvetica", 9.5)
        c.drawString(M, y, _friendly_metric(m)[:44])
        c.drawRightString(W - M - 1.7 * inch, y, _fmt_value(first))
        c.drawRightString(W - M - 0.85 * inch, y, _fmt_value(last))
        if net is None:
            c.setFillColorRGB(*MUT); c.drawRightString(W - M, y, "—")
        else:
            c.setFillColorRGB(*(GOLD if net >= 0 else RED))
            c.drawRightString(W - M, y, f'{"+" if net >= 0 else ""}{_fmt_value(net)}')
        y -= 0.27 * inch
        shown += 1
        if y < 1.0 * inch or shown >= 16:
            break

    c.setFillColorRGB(*MUT); c.setFont("Helvetica", 7.5)
    c.drawString(M, 0.6 * inch, "Generated by BarrelLabs  ·  barrellabsai.com")
    c.showPage(); c.save()
    return buf.getvalue()


# ============================================================
#                         MAIN
# ============================================================
def render_historical_charts():
    inject_global_theme()
    # Unified Edge masthead — the single shared top nav across every
    # page (Library tab active). Replaces the old bespoke
    # "← Back to Dashboard" row so the header is identical everywhere.
    render_edge_masthead(
        st.session_state.get("user") or {}, active_page="historical_charts"
    )
    st.markdown(_HC_LOCAL_CSS, unsafe_allow_html=True)
    st.markdown('<div class="bl-page">', unsafe_allow_html=True)

    # ---- Hero ----
    hero_html = textwrap.dedent("""
    <div class="hc-hero">
      <div class="hc-hero-row">
        <div style="flex:1;min-width:0;">
          <div class="hc-eyebrow">BarrelLabs Progress</div>
          <div class="hc-title">Your progress over time</div>
          <div class="hc-sub">
            See how your swing is trending. Every analysis you run
            lands here so you can watch your score climb and spot what
            is getting better.
          </div>
        </div>
        <div class="hc-mode-pill"><span class="hc-mode-pill-dot"></span> Progress Mode</div>
      </div>
    </div>
    """).strip()
    st.markdown(hero_html, unsafe_allow_html=True)

    # ---- Auth ----
    user = st.session_state.get("user")
    if not user:
        _render_empty_state(
            "Please sign in to view your performance history.",
            "Your chart data is tied to your BarrelLabs account.",
            icon="◇",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    player_id = user.get("id") or user.get("slug")
    # Escaped: rendered raw into HTML below, so an XSS-y display name can't
    # inject markup (self-XSS hardening).
    import html as _html
    player_name = _html.escape(str(user.get("name") or "Player"))

    df = load_player_history_df(player_id)
    if df.empty:
        _render_empty_state(
            "No swing history yet.",
            "Upload your first swing on the Analyze page — once you have a "
            "saved analysis, your performance trends will start charting here.",
            icon="↗",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if len(df) < 2:
        # Soft empty state — show one stat card but encourage more uploads.
        st.markdown(
            '<div class="hc-empty" style="margin-bottom:1.4rem;">'
            '<div class="hc-empty-icon">↗</div>'
            '<div class="hc-empty-title">One swing on file. Trends start at two.</div>'
            f'<div class="hc-empty-sub">Upload one more swing and this page starts '
            f'charting your progress, so you can see what is improving over time.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ---- Numeric metrics ----
    excluded = {"file", "date", "_dt", "Analysis #"}
    numeric_metrics = [
        col for col in df.columns
        if col not in excluded
        and getattr(df[col], "dtype", None) is not None
        and str(df[col].dtype) in ("int64", "float64", "int32", "float32")
        and df[col].notna().any()
    ]
    if not numeric_metrics:
        _render_empty_state(
            "No chartable metrics yet.",
            "Your saved analyses don't include any numeric metrics that can be plotted yet. "
            "Upload a fresh swing to refresh the charts.",
            icon="≡",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ==========================================================
    #             KPI / SUMMARY STATS
    # ==========================================================
    scores = df["Swing Score"].dropna() if "Swing Score" in df.columns else pd.Series([], dtype=float)
    total_analyses = len(df)
    best_score = scores.max() if len(scores) else None
    avg_score = scores.mean() if len(scores) else None
    first_score = scores.iloc[0] if len(scores) else None
    latest_score = scores.iloc[-1] if len(scores) else None
    score_delta = (latest_score - first_score) if (first_score is not None and latest_score is not None) else None
    last_date = df["date"].dropna().iloc[-1] if df["date"].notna().any() else "—"

    is_new_pb = (best_score is not None and latest_score is not None and latest_score >= best_score)
    is_trending_up = (score_delta is not None and score_delta > 0)
    is_above_avg = (avg_score is not None and latest_score is not None and latest_score > avg_score)

    # ---- Badge strip ----
    badges = []
    if is_new_pb and len(scores) >= 2:
        badges.append('<span class="hc-badge is-pb"><span class="hc-dot"></span> NEW PERSONAL BEST</span>')
    if is_above_avg:
        badges.append('<span class="hc-badge is-above"><span class="hc-dot"></span> ABOVE YOUR AVERAGE</span>')
    if is_trending_up:
        badges.append('<span class="hc-badge is-up"><span class="hc-dot"></span> TRENDING UP</span>')
    # Streak: more than 3 consecutive non-decreasing scores?
    if len(scores) >= 4:
        last3 = list(scores.iloc[-4:])
        ups = all(last3[i] >= last3[i - 1] for i in range(1, len(last3)))
        if ups:
            badges.append('<span class="hc-badge is-streak"><span class="hc-dot"></span> 3-SWING STREAK</span>')
    if badges:
        st.markdown('<div class="hc-badges">' + "".join(badges) + '</div>', unsafe_allow_html=True)

    # ---- Stat strip (5 cards) ----
    stat_strip = (
        '<div class="hc-stat-strip">'
        f'<div class="hc-stat">'
        f'<div class="hc-stat-eyebrow">TOTAL ANALYSES</div>'
        f'<div class="hc-stat-value">{total_analyses}</div>'
        f'<div class="hc-stat-foot">Lifetime swings on file</div>'
        f'</div>'
        f'<div class="hc-stat">'
        f'<div class="hc-stat-eyebrow">BEST SCORE EVER</div>'
        f'<div class="hc-stat-value is-gold">{_fmt_value(best_score)}</div>'
        f'<div class="hc-stat-foot">Personal best</div>'
        f'</div>'
        f'<div class="hc-stat">'
        f'<div class="hc-stat-eyebrow">AVERAGE SCORE</div>'
        f'<div class="hc-stat-value">{_fmt_value(avg_score)}</div>'
        f'<div class="hc-stat-foot">Across all uploads</div>'
        f'</div>'
        f'<div class="hc-stat">'
        f'<div class="hc-stat-eyebrow">TOTAL IMPROVEMENT</div>'
        f'<div class="hc-stat-value {"is-up" if (score_delta or 0) >= 0 else "is-down"}">'
        f'{"+" if (score_delta or 0) >= 0 else ""}{_fmt_value(score_delta)}'
        f'</div>'
        f'<div class="hc-stat-foot">First → latest</div>'
        f'</div>'
        f'<div class="hc-stat">'
        f'<div class="hc-stat-eyebrow">LAST UPLOAD</div>'
        f'<div class="hc-stat-value" style="font-size:0.98rem;line-height:1.35;font-weight:600;">{last_date}</div>'
        f'<div class="hc-stat-foot">For {player_name}</div>'
        f'</div>'
        '</div>'
    )
    st.markdown(stat_strip, unsafe_allow_html=True)

    # Download a standalone Progress PDF (the "print progress over time" ask).
    _pdf_l, _pdf_r = st.columns([1.3, 4])
    with _pdf_l:
        try:
            _prog_pdf = build_progress_pdf(player_name, df, numeric_metrics)
            st.download_button(
                "⬇  Download Progress PDF",
                data=_prog_pdf,
                file_name="barrellabs_progress.pdf",
                mime="application/pdf",
                width="stretch",
                key="hc_progress_pdf",
            )
        except Exception:
            pass

    # ==========================================================
    #             CONTROLS (metric, time range, MA)
    # ==========================================================
    st.markdown(
        '<div class="hc-section-header">'
        '<div>'
        '<div class="hc-section-eyebrow">TRENDS</div>'
        '<div class="hc-section-title">Pick what to track</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    preferred_order = [
        "Swing Score",
        "Swing Duration (ms)",
        "Peak hip-shoulder separation",
        "Peak hip-shoulder separation (Match %)",
        "Launch → contact",
        "Launch → contact (Match %)",
        "Total head drift (torso-rel)",
        "Total head drift (torso-rel) (Match %)",
    ]
    ordered = [m for m in preferred_order if m in numeric_metrics]
    ordered += [m for m in numeric_metrics if m not in ordered]

    st.markdown('<div class="hc-controls-card">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([2, 1.4, 1, 1])
    with c1:
        selected_metric = st.selectbox(
            "WHAT TO TRACK", ordered, key="hc_metric_select",
            format_func=_friendly_metric,
        )
    with c2:
        compare_options = ["None"] + [m for m in ordered if m != selected_metric]
        compare_metric = st.selectbox(
            "COMPARE WITH (OPTIONAL)",
            compare_options,
            key="hc_compare_metric",
            format_func=_friendly_metric,
        )
    with c3:
        time_range = st.selectbox(
            "TIME RANGE",
            ["All time", "Last 7 days", "Last 30 days", "Last 90 days"],
            key="hc_time_range",
        )
    with c4:
        show_ma = st.checkbox(
            "MOVING AVG",
            value=False,
            key="hc_show_ma",
            help="Overlay a 3-point rolling average on the primary metric.",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # Apply time filter
    df_filt = df.copy()
    cutoff = None
    now = datetime.now()
    if time_range == "Last 7 days":
        cutoff = now - timedelta(days=7)
    elif time_range == "Last 30 days":
        cutoff = now - timedelta(days=30)
    elif time_range == "Last 90 days":
        cutoff = now - timedelta(days=90)
    if cutoff is not None:
        if "_dt" in df_filt.columns:
            df_filt = df_filt[df_filt["_dt"].apply(lambda d: isinstance(d, datetime) and d >= cutoff)]
        if df_filt.empty:
            df_filt = df.copy()  # fallback if no dates parse
            time_range = "All time (no dates)"

    # ==========================================================
    #             CHART CARD
    # ==========================================================
    chart_df = df_filt[["Analysis #", selected_metric]].dropna()
    has_data = len(chart_df) >= 1

    first_val = chart_df[selected_metric].iloc[0] if has_data else None
    last_val = chart_df[selected_metric].iloc[-1] if has_data else None
    delta_val = (last_val - first_val) if (has_data and len(chart_df) >= 2) else None

    trend_html = ""
    if delta_val is not None:
        if delta_val > 0:
            trend_html = f'<span class="hc-chart-trend is-up">▲ {abs(delta_val):.2f} GAINED</span>'
        elif delta_val < 0:
            trend_html = f'<span class="hc-chart-trend is-down">▼ {abs(delta_val):.2f} LOST</span>'
        else:
            trend_html = '<span class="hc-chart-trend">— FLAT</span>'
    elif has_data and len(chart_df) == 1:
        trend_html = '<span class="hc-chart-trend">⌖ FIRST READING IN RANGE</span>'

    chart_head = (
        '<div class="hc-chart-card">'
        '<div class="hc-chart-head">'
        '<div>'
        f'<div class="hc-chart-title">{_friendly_metric(selected_metric)}</div>'
        f'<div class="hc-chart-sub">{len(chart_df)} reading{"s" if len(chart_df) != 1 else ""} · {time_range}</div>'
        '</div>'
        f'{trend_html}'
        '</div>'
    )
    st.markdown(chart_head, unsafe_allow_html=True)

    # Build chart
    fig = go.Figure()

    if has_data:
        # Primary metric line
        fig.add_trace(go.Scatter(
            x=chart_df["Analysis #"],
            y=chart_df[selected_metric],
            mode="lines+markers",
            line=dict(color="rgba(232,193,112,0.95)", width=2.5, shape="spline", smoothing=0.7),
            marker=dict(color=BL_GOLD, size=8, line=dict(color="#0a0a0c", width=2)),
            fill="tozeroy" if len(chart_df) >= 2 else None,
            fillcolor="rgba(232,193,112,0.10)",
            hovertemplate=("<b>Analysis %{x}</b><br>" + f"{selected_metric}: " + "%{y:.2f}<extra></extra>"),
            name=selected_metric,
        ))

        # Personal best marker (only if the selected metric has a clear PB).
        try:
            pb_idx = chart_df[selected_metric].idxmax()
            pb_x = int(chart_df.loc[pb_idx, "Analysis #"])
            pb_y = float(chart_df.loc[pb_idx, selected_metric])
            fig.add_trace(go.Scatter(
                x=[pb_x], y=[pb_y],
                mode="markers+text",
                marker=dict(color=BL_GOLD, size=14, symbol="star",
                            line=dict(color="#0a0a0c", width=2)),
                text=["PB"],
                textposition="top center",
                textfont=dict(size=10, color=BL_GOLD,
                              family=BL_FONT_MONO),
                hovertemplate=f"<b>Personal Best</b><br>{selected_metric}: {pb_y:.2f}<extra></extra>",
                name="Personal Best",
                showlegend=False,
            ))
        except Exception:
            pass

        # Moving average overlay
        if show_ma and len(chart_df) >= 3:
            ma_series = chart_df[selected_metric].rolling(window=3, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=chart_df["Analysis #"],
                y=ma_series,
                mode="lines",
                line=dict(color="rgba(255,255,255,0.55)", width=1.6, dash="dot"),
                name="3-pt moving avg",
                hovertemplate="<b>3-pt avg</b><br>%{y:.2f}<extra></extra>",
            ))

    # Comparison metric (secondary axis to handle very different scales)
    if compare_metric and compare_metric != "None":
        cmp_df = df_filt[["Analysis #", compare_metric]].dropna()
        if len(cmp_df) >= 1:
            fig.add_trace(go.Scatter(
                x=cmp_df["Analysis #"],
                y=cmp_df[compare_metric],
                mode="lines+markers",
                line=dict(color="rgba(200,196,187,0.85)", width=2, shape="spline", smoothing=0.5),
                marker=dict(color=BL_SECONDARY, size=6, line=dict(color="#0a0a0c", width=1.5)),
                hovertemplate=("<b>Analysis %{x}</b><br>" + f"{compare_metric}: " + "%{y:.2f}<extra></extra>"),
                yaxis="y2",
                name=compare_metric,
            ))
            fig.update_layout(yaxis2=dict(
                overlaying="y", side="right",
                gridcolor="rgba(200,196,187,0.05)",
                zerolinecolor="rgba(200,196,187,0.1)",
                title=dict(text=compare_metric.upper(), font=dict(size=10, color="rgba(200,196,187,0.55)")),
                tickfont=dict(size=11, color="rgba(200,196,187,0.6)"),
            ))

    _style_plotly(fig, selected_metric)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Inline summary row under the chart
    if len(chart_df) >= 2:
        first_v = _fmt_value(first_val)
        last_v = _fmt_value(last_val)
        delta_v = _fmt_value(delta_val)
        sign = "+" if (delta_val is not None and delta_val >= 0) else ""
        delta_color = f"color:{BL_POSITIVE};" if (delta_val is not None and delta_val >= 0) else f"color:{BL_NEGATIVE};"
        summary_row = (
            '<div style="display:flex;gap:2.2rem;flex-wrap:wrap;padding:0.3rem 0.2rem 0.4rem;">'
            '<div>'
            '<div style="font-family:var(--bl-mono);font-size:0.56rem;font-weight:600;letter-spacing:0.22em;color:var(--bl-ink-40);text-transform:uppercase;">FIRST</div>'
            f'<div style="font-family:var(--bl-sans);font-size:1.35rem;font-weight:700;color:var(--bl-ink-100);letter-spacing:-0.02em;">{first_v}</div>'
            '</div>'
            '<div>'
            '<div style="font-family:var(--bl-mono);font-size:0.56rem;font-weight:600;letter-spacing:0.22em;color:var(--bl-ink-40);text-transform:uppercase;">LATEST</div>'
            f'<div style="font-family:var(--bl-sans);font-size:1.35rem;font-weight:700;color:var(--bl-ink-100);letter-spacing:-0.02em;">{last_v}</div>'
            '</div>'
            '<div>'
            '<div style="font-family:var(--bl-mono);font-size:0.56rem;font-weight:600;letter-spacing:0.22em;color:var(--bl-ink-40);text-transform:uppercase;">CHANGE</div>'
            f'<div style="font-family:var(--bl-sans);font-size:1.35rem;font-weight:700;letter-spacing:-0.02em;{delta_color}">{sign}{delta_v}</div>'
            '</div>'
            '</div>'
        )
        st.markdown(summary_row, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close hc-chart-card

    # ==========================================================
    #             TREND INSIGHTS
    # ==========================================================
    insights = []
    if score_delta is not None and len(scores) >= 2:
        if score_delta > 0:
            insights.append((
                "⬆", f"Your <strong>swing score improved {abs(score_delta):.1f} point"
                f"{'s' if abs(score_delta) != 1 else ''}</strong> since your first upload "
                f"({_fmt_value(first_score)} → {_fmt_value(latest_score)})."
            ))
        elif score_delta < 0:
            insights.append((
                "⚠", f"Your swing score has dropped <strong>{abs(score_delta):.1f} points</strong> "
                f"since your first analysis ({_fmt_value(first_score)} → {_fmt_value(latest_score)}). "
                f"Time to revisit the drill plan."
            ))
        else:
            insights.append((
                "·", "Your swing score is right where it started. Consistency is good — "
                "now push for the next breakthrough."
            ))

    improver = _strongest_improver(df, numeric_metrics)
    if improver is not None:
        m, pct = improver
        if pct > 5:
            insights.append((
                "★", f"<strong>{m}</strong> has shown the strongest improvement — "
                f"up <strong>{pct:+.1f}%</strong> over your history."
            ))

    opp = _largest_opportunity(df, numeric_metrics)
    if opp is not None:
        m, v = opp
        if v < 75:
            insights.append((
                "→", f"<strong>{m}</strong> is your largest opportunity right now "
                f"(latest: {v:.0f}%). Focus drill work there for the biggest jump."
            ))

    if is_new_pb and len(scores) >= 2:
        insights.append((
            "✦", f"Your latest swing — <strong>{_fmt_value(latest_score)}</strong> — is a "
            f"new personal best. Keep that mechanic locked in."
        ))

    # Normalize entries to (icon, text) tuples (fix one accidental tuple-vs-args earlier)
    normalized = []
    for entry in insights:
        if isinstance(entry, tuple) and len(entry) == 2:
            normalized.append(entry)
    insights = normalized

    if insights:
        st.markdown(
            '<div class="hc-section-header">'
            '<div>'
            '<div class="hc-section-eyebrow">AUTOMATED OBSERVATIONS</div>'
            '<div class="hc-section-title">Trend insights</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        insights_html = ['<div class="hc-insights">']
        for icon, text in insights:
            insights_html.append(
                f'<div class="hc-insight-row">'
                f'<div class="hc-insight-icon">{icon}</div>'
                f'<div class="hc-insight-text">{text}</div>'
                f'</div>'
            )
        insights_html.append('</div>')
        st.markdown("".join(insights_html), unsafe_allow_html=True)

    # ==========================================================
    #   WHAT CHANGED — plain-language highlights. Replaced the dense
    #   first-vs-latest, 5-column x 25-row metric table (hard to parse;
    #   "numbers no one understands"). The full numbers still live in the
    #   downloadable Progress PDF for anyone who wants them.
    # ==========================================================
    st.markdown(
        '<div class="hc-section-header"><div>'
        '<div class="hc-section-eyebrow">THE HEADLINE</div>'
        '<div class="hc-section-title">What\'s changed</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    _chg = []
    _ss = df["Swing Score"].dropna() if "Swing Score" in df.columns else None
    if _ss is not None and len(_ss) >= 1:
        _f, _l = _ss.iloc[0], _ss.iloc[-1]
        _d = _l - _f
        _cls = "is-up" if _d > 0 else ("is-down" if _d < 0 else "")
        _arrow = "\u25b2" if _d > 0 else ("\u25bc" if _d < 0 else "\u2014")
        _chg.append(
            '<div class="hc-change-card">'
            '<div class="hc-change-label">Swing Score</div>'
            f'<div class="hc-change-big">{_fmt_value(_f)} <span class="hc-change-to">\u2192</span> {_fmt_value(_l)}</div>'
            f'<div class="hc-change-sub {_cls}">{_arrow} {"+" if _d >= 0 else ""}{_fmt_value(_d)} since your first swing</div>'
            '</div>'
        )
    _imp = _strongest_improver(df, numeric_metrics)
    if _imp:
        _m, _pct = _imp
        _chg.append(
            '<div class="hc-change-card">'
            '<div class="hc-change-label">Most improved</div>'
            f'<div class="hc-change-big">{_friendly_metric(_m)}</div>'
            f'<div class="hc-change-sub is-up">\u25b2 {"+" if _pct >= 0 else ""}{_pct:.0f}% better than your first</div>'
            '</div>'
        )
    _opp = _largest_opportunity(df, numeric_metrics)
    if _opp:
        _m2, _ = _opp
        _chg.append(
            '<div class="hc-change-card">'
            '<div class="hc-change-label">Focus next</div>'
            f'<div class="hc-change-big">{_friendly_metric(_m2)}</div>'
            '<div class="hc-change-sub">Your biggest room to grow</div>'
            '</div>'
        )
    if _chg:
        st.markdown('<div class="hc-change-grid">' + "".join(_chg) + '</div>',
                    unsafe_allow_html=True)
    # ==========================================================
    #             MILESTONE TRACKER
    # ==========================================================
    milestones = [
        {
            "title": "First Swing Logged",
            "sub":   "Welcome to BarrelLabs. The journey starts here.",
            "icon":  "◇",
            "done":  total_analyses >= 1,
        },
        {
            "title": "5 Analyses Completed",
            "sub":   "You're building a real performance history.",
            "icon":  "✓",
            "done":  total_analyses >= 5,
        },
        {
            "title": "10 Analyses Completed",
            "sub":   "Enough history to see real trends.",
            "icon":  "✓",
            "done":  total_analyses >= 10,
        },
        {
            "title": "First 80+ Score",
            "sub":   "A really strong swing. Great work.",
            "icon":  "★",
            "done":  (best_score or 0) >= 80,
        },
        {
            "title": "20-Point Improvement",
            "sub":   "Big jump from your first swing to your latest.",
            "icon":  "✦",
            "done":  (score_delta or 0) >= 20,
        },
        {
            "title": "3-Swing Improvement Streak",
            "sub":   "Three consecutive uploads, all moving the right way.",
            "icon":  "⌃",
            "done":  any(
                len(scores) >= 4 and all(
                    list(scores)[i] >= list(scores)[i - 1]
                    for i in range(len(scores) - 3, len(scores))
                )
                for _ in [0]
            ) if len(scores) >= 4 else False,
        },
    ]

    st.markdown(
        '<div class="hc-section-header">'
        '<div>'
        '<div class="hc-section-eyebrow">MILESTONES</div>'
        '<div class="hc-section-title">Your development achievements</div>'
        '</div>'
        f'<div class="hc-section-count">'
        f'{sum(1 for m in milestones if m["done"])} OF {len(milestones)} UNLOCKED'
        f'</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    miles_html = ['<div class="hc-milestones">']
    for m in milestones:
        cls = "is-done" if m["done"] else ""
        status = "UNLOCKED" if m["done"] else "LOCKED"
        miles_html.append(
            f'<div class="hc-milestone {cls}">'
            f'<div class="hc-milestone-icon">{m["icon"]}</div>'
            f'<div class="hc-milestone-body">'
            f'<div class="hc-milestone-title">{m["title"]}</div>'
            f'<div class="hc-milestone-sub">{m["sub"]}</div>'
            f'</div>'
            f'<div class="hc-milestone-status">{status}</div>'
            f'</div>'
        )
    miles_html.append('</div>')
    st.markdown("".join(miles_html), unsafe_allow_html=True)

    # ==========================================================
    #             QUICK ACCESS TO RECENT REPORTS
    # ==========================================================
    history = load_swing_history(player_id)
    recent = list(reversed(history))[:4]
    if recent:
        st.markdown(
            '<div class="hc-section-header">'
            '<div>'
            '<div class="hc-section-eyebrow">QUICK ACCESS</div>'
            '<div class="hc-section-title">Open a recent report</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="hc-quick-list">', unsafe_allow_html=True)
        for idx, rec in enumerate(recent):
            n = rec.get("swing_number") or "—"
            try:
                num_disp = f"#{int(n):02d}"
            except Exception:
                num_disp = f"#{n}"
            score = rec.get("score")
            try:
                score_disp = f"{int(round(float(score)))}"
            except (TypeError, ValueError):
                score_disp = "—"
            ref = str(rec.get("reference_name") or "—")
            date_disp = str(rec.get("date") or "—")
            label = f"SWING {n}   ·   VS {ref.upper()}   ·   {date_disp.upper()}   ·   SCORE {score_disp}"

            if st.button(label, key=f"hc_quick_{idx}_{rec.get('id') or rec.get('timestamp') or idx}", width="stretch"):
                st.session_state["view_swing_record"] = rec
                rp = rec.get("_record_path")
                if rp:
                    st.session_state["view_swing_path"] = rp
                else:
                    st.session_state.pop("view_swing_path", None)
                st.session_state.pop("page", None)
                st.session_state.pop("view", None)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================================
    #             RAW DATA TABLE
    # ==========================================================
    st.markdown('<div class="hc-data-wrap">', unsafe_allow_html=True)
    with st.expander("View Raw Data Table", expanded=False):
        # Drop the internal _dt parsing column from the user-facing table.
        display_df = df.drop(columns=["_dt"]) if "_dt" in df.columns else df
        # Show the most-recent 25 analyses (mirrors the comparison table cap).
        display_df = display_df.tail(25).iloc[::-1]

        def _fmt_cell(v) -> str:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "—"
            if isinstance(v, (int, float)):
                return _fmt_value(v)
            return str(v)

        cols = list(display_df.columns)
        head_cells = "".join(
            f'<th style="padding:0.7rem 1.1rem;text-align:left;white-space:nowrap;'
            f'font-family:var(--bl-mono);font-size:0.56rem;font-weight:600;'
            f'letter-spacing:0.18em;color:var(--bl-ink-40);text-transform:uppercase;">'
            f'{_friendly_metric(c)}</th>'
            for c in cols
        )
        body_rows = []
        for _, rec in display_df.iterrows():
            cells = "".join(
                f'<td style="padding:0.65rem 1.1rem;white-space:nowrap;'
                f'font-family:var(--bl-sans);font-size:0.88rem;color:var(--bl-ink-80);'
                f'font-variant-numeric:tabular-nums;border-top:1px solid var(--bl-line);">'
                f'{_fmt_cell(rec[c])}</td>'
                for c in cols
            )
            body_rows.append(f'<tr>{cells}</tr>')

        raw_table_html = (
            '<div class="hc-table-wrap" style="overflow-x:auto;margin-bottom:0;">'
            '<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="background:rgba(255,255,255,0.015);">{head_cells}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody>'
            '</table>'
            '</div>'
        )
        st.markdown(raw_table_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close .bl-page
