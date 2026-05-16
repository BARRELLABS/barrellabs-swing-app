"""
BarrelLabs / SwingAI — Dashboard V2 (futuristic redesign).

A full visual + structural overhaul that mirrors the dashboard_mockup.html
preview. Same data sources as v1 (Supabase swings via load_swing_history),
but a wider layout with new sections:

    [ Topbar: breadcrumb + LIVE pill ]
    [ Hero: greeting + last-swing meta ]
    [ KPI row: Score ring | MLB jersey | Top Focus | Improvement ]
    [ Performance Over Time (7D/30D/90D tabs) | Drill Recommendations ]
    [ Biomechanical Radar | Recent Swings ]
    [ Achievements row ]
    [ Footer strip ]

The score ring is a 3/4 arc with tick marks, a scan effect and an
endpoint cap dot. The MLB card renders a copyright-safe back-of-jersey
SVG with the comp player's last name arched at the top and their number
big and centered.

Public API:
    render_dashboard_v2(user) -> None
        Renders the full v2 dashboard. Caller should `st.stop()` after.

A small feature-flag wrapper `render_dashboard_auto(user)` is exported
too — it reads st.session_state["use_dashboard_v2"] (default False) and
falls back to v1 when off.
"""

from __future__ import annotations

import math
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import plotly.graph_objects as go

from bl_theme import inject_global_theme
from player_storage import load_swing_history

# Reuse the well-tested helpers from v1 so behavior stays consistent.
from dashboard import (
    _safe_history,
    _similarity_pct,
    _radar_from_record,
    _pretty_player_name,
    _format_when,
    _format_short_date,
    _swing_count_str,
    _score_color,
    _short_band_tag,
)


# ------------------------------------------------------------------
#  MLB player → jersey number lookup (copyright-safe rendering).
#  Falls back to "00" when a reference slug isn't in the table.
# ------------------------------------------------------------------
JERSEY_NUMBERS: Dict[str, str] = {
    "trout":            "27",
    "judge":            "99",
    "ronald_acuna_jr":  "13",
    "acuna":            "13",
    "juan_soto":        "22",
    "soto":             "22",
    "shohei":           "17",
    "ohtani":           "17",
    "mookie":           "50",
    "bryce_harper":     "3",
    "harper":           "3",
    "freddie_freeman":  "5",
    "freeman":          "5",
    "francisco_lindor": "12",
    "lindor":           "12",
    "kyle_tucker":      "30",
    "tucker":           "30",
    "kyle_schwarber":   "12",
    "schwarber":        "12",
    "manny_machado":    "13",
    "machado":          "13",
    "alex_bregman":     "2",
    "bregman":          "2",
    "jose_ramirez":     "11",
    "ramirez":          "11",
    "yandy_diaz":       "26",
    "diaz":             "26",
    "yordan_alvarez":   "44",
    "alvarez":          "44",
    "spencer_torkelson":"20",
    "torkelson":        "20",
    "gunnar_henderson": "2",
    "henderson":        "2",
}


def _jersey_number_for(reference_slug: Optional[str]) -> str:
    if not reference_slug:
        return "00"
    base = str(reference_slug).lower()
    for suffix in ("_swing", " copy", ".mp4"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    base = base.strip().replace(" ", "_")
    # Exact match first
    if base in JERSEY_NUMBERS:
        return JERSEY_NUMBERS[base]
    # Fallback to last-name match
    last = base.split("_")[-1]
    return JERSEY_NUMBERS.get(last, "00")


def _last_name_upper(reference_slug: Optional[str]) -> str:
    """Get the JERSEY-style last name (UPPER, no underscores) for a slug."""
    if not reference_slug:
        return "PLAYER"
    base = str(reference_slug)
    for suffix in ("_swing", " copy", ".mp4"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    parts = [p for p in base.replace("-", "_").split("_") if p]
    if not parts:
        return "PLAYER"
    last = parts[-1]
    # Strip "jr" / "sr" suffixes which sit awkwardly on a jersey.
    if last.lower() in ("jr", "sr") and len(parts) >= 2:
        last = parts[-2]
    return last.upper()


# ------------------------------------------------------------------
#  CSS — heavy block matching the mockup aesthetic.
# ------------------------------------------------------------------
_DASHBOARD_V2_CSS = """
<style>
:root {
  --bld2-red:        #FF3B30;
  --bld2-red-glow:   rgba(255,59,48,0.45);
  --bld2-line:       rgba(255,255,255,0.06);
  --bld2-line-hi:    rgba(255,255,255,0.12);
  --bld2-surface-0:  rgba(255,255,255,0.018);
  --bld2-surface-1:  rgba(255,255,255,0.035);
  --bld2-ink-100:    #ffffff;
  --bld2-ink-80:     #d4d4d4;
  --bld2-ink-60:     #9a9a9a;
  --bld2-ink-40:     #6a6a6a;
  --bld2-mono:       'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
  --bld2-sans:       'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ===== TOPBAR ===== */
.bld2-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.75rem 0 1.25rem 0;
  border-bottom: 1px solid var(--bld2-line);
  margin-bottom: 1.6rem;
}
.bld2-crumbs {
  font-family: var(--bld2-mono);
  font-size: 0.66rem;
  letter-spacing: 0.2em;
  font-weight: 600;
  color: var(--bld2-ink-60);
  text-transform: uppercase;
}
.bld2-crumbs .sep { color: var(--bld2-ink-40); margin: 0 0.55rem; }
.bld2-crumbs .now { color: var(--bld2-ink-100); }
.bld2-live {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.42rem 0.85rem;
  background: rgba(52,199,89,0.08);
  border: 1px solid rgba(52,199,89,0.3);
  border-radius: 999px;
  font-family: var(--bld2-mono);
  font-size: 0.62rem; letter-spacing: 0.22em; font-weight: 700;
  color: #34c759;
  text-transform: uppercase;
}
.bld2-live::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: #34c759;
  box-shadow: 0 0 8px rgba(52,199,89,0.7);
  animation: bld2Pulse 1.6s ease-in-out infinite;
}
@keyframes bld2Pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.55; transform: scale(0.85); }
}

/* ===== HERO ===== */
.bld2-hero {
  margin-bottom: 1.5rem;
}
.bld2-hero h1 {
  font-family: var(--bld2-sans);
  font-size: 2.8rem;
  font-weight: 700;
  letter-spacing: -0.045em;
  color: var(--bld2-ink-100);
  margin: 0;
  line-height: 1.05;
}
.bld2-hero h1 .red { color: var(--bld2-red); }
.bld2-hero .sub {
  margin-top: 0.85rem;
  color: var(--bld2-ink-60);
  font-size: 0.96rem;
  line-height: 1.55;
  max-width: 640px;
}

/* ===== CARD BASE ===== */
.bld2-card {
  position: relative;
  background: var(--bld2-surface-0);
  border: 1px solid var(--bld2-line);
  border-radius: 12px;
  padding: 1.2rem 1.3rem;
  transition: border-color .22s ease, transform .22s ease, box-shadow .22s ease;
}
.bld2-card:hover {
  border-color: rgba(255,59,48,0.4);
  transform: translateY(-1px);
  box-shadow: 0 14px 36px -22px rgba(0,0,0,0.7);
}
.bld2-card::before, .bld2-card::after {
  content: ""; position: absolute; width: 10px; height: 10px;
  pointer-events: none;
  transition: opacity .22s ease, border-color .22s ease;
}
.bld2-card::before {
  top: -1px; left: -1px;
  border-top: 1px solid var(--bld2-red);
  border-left: 1px solid var(--bld2-red);
  opacity: 0.5;
}
.bld2-card::after {
  bottom: -1px; right: -1px;
  border-bottom: 1px solid var(--bld2-red);
  border-right: 1px solid var(--bld2-red);
  opacity: 0.5;
}
.bld2-card:hover::before, .bld2-card:hover::after { opacity: 1; }
.bld2-card-eyebrow {
  font-family: var(--bld2-mono);
  font-size: 0.58rem;
  letter-spacing: 0.22em;
  font-weight: 700;
  color: var(--bld2-ink-60);
  text-transform: uppercase;
  margin-bottom: 0.85rem;
  display: flex; align-items: center; justify-content: space-between;
}
.bld2-card-eyebrow .info-i {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 50%;
  border: 1px solid var(--bld2-ink-40);
  color: var(--bld2-ink-40);
  font-size: 9px;
  font-family: var(--bld2-sans);
  font-style: italic;
}

/* ===== SCORE RING ===== */
.bld2-score-body {
  display: flex; align-items: center; gap: 1.2rem;
  margin-top: 0.4rem;
}
.bld2-score-ring-wrap {
  position: relative;
  width: 116px; height: 116px;
  flex-shrink: 0;
}
.bld2-score-ring-wrap svg { width: 100%; height: 100%; display: block; }
.bld2-score-scan {
  position: absolute; inset: 6px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent 0%, rgba(255,59,48,0.18) 8%, transparent 16%);
  animation: bld2ScanRotate 4.2s linear infinite;
  pointer-events: none;
  mix-blend-mode: screen;
}
@keyframes bld2ScanRotate { to { transform: rotate(360deg); } }
.bld2-score-center {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  pointer-events: none;
}
.bld2-score-num {
  font-family: var(--bld2-sans);
  font-size: 2.1rem;
  font-weight: 800;
  color: var(--bld2-ink-100);
  letter-spacing: -0.05em;
  line-height: 1;
}
.bld2-score-num-foot {
  font-family: var(--bld2-mono);
  font-size: 0.5rem;
  letter-spacing: 0.18em;
  color: var(--bld2-ink-60);
  margin-top: 3px;
  font-weight: 700;
}
.bld2-score-meta { flex: 1; min-width: 0; }
.bld2-score-band {
  color: var(--bld2-ink-100);
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: -0.01em;
  line-height: 1.25;
}
.bld2-score-delta {
  margin-top: 0.4rem;
  font-family: var(--bld2-mono);
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  color: var(--bld2-ink-60);
  text-transform: uppercase;
  font-weight: 600;
}
.bld2-score-delta b { color: #4ADE80; font-weight: 800; }
.bld2-score-delta b.down { color: var(--bld2-red); }

/* ===== MLB JERSEY ===== */
.bld2-mlb-body {
  display: flex; align-items: center; gap: 1rem;
  margin-top: 0.3rem;
}
.bld2-jersey {
  width: 62px; height: 78px;
  flex-shrink: 0;
  position: relative;
  filter: drop-shadow(0 0 14px rgba(255,59,48,0.3));
}
.bld2-jersey svg { width: 100%; height: 100%; display: block; }
.bld2-jersey::before {
  content: ""; position: absolute; top: -4px; left: -4px;
  width: 8px; height: 8px;
  border-top: 1px solid var(--bld2-red);
  border-left: 1px solid var(--bld2-red);
  opacity: 0.7;
}
.bld2-jersey::after {
  content: ""; position: absolute; bottom: -4px; right: -4px;
  width: 8px; height: 8px;
  border-bottom: 1px solid var(--bld2-red);
  border-right: 1px solid var(--bld2-red);
  opacity: 0.7;
}
.bld2-mlb-name {
  font-weight: 800;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
  color: var(--bld2-ink-100);
}
.bld2-mlb-pct {
  color: var(--bld2-red);
  font-weight: 700;
  font-size: 0.7rem;
  font-family: var(--bld2-mono);
  letter-spacing: 0.1em;
  margin-top: 3px;
}
.bld2-mlb-hand {
  color: var(--bld2-ink-60);
  font-size: 0.7rem;
  margin-top: 3px;
}
.bld2-mlb-progress {
  display: flex; gap: 3px; margin-top: 0.85rem;
}
.bld2-mlb-progress span {
  flex: 1; height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.05);
}
.bld2-mlb-progress span.fill {
  background: var(--bld2-red);
  box-shadow: 0 0 8px var(--bld2-red-glow);
}

/* ===== TOP FOCUS ===== */
.bld2-focus-body {
  display: flex; align-items: center; gap: 1rem;
  margin-top: 0.3rem;
}
.bld2-focus-icon {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: rgba(255,59,48,0.08);
  border: 1px solid rgba(255,59,48,0.3);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.bld2-focus-icon svg { width: 28px; height: 28px; color: var(--bld2-red); }
.bld2-focus-name {
  font-weight: 800;
  font-size: 1.05rem;
  letter-spacing: -0.015em;
  line-height: 1.15;
  color: var(--bld2-ink-100);
}
.bld2-focus-impact {
  margin-top: 4px;
  font-family: var(--bld2-mono);
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: var(--bld2-red);
  text-transform: uppercase;
  font-weight: 700;
}
.bld2-focus-foot {
  margin-top: 0.85rem;
  font-family: var(--bld2-mono);
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: var(--bld2-ink-60);
  text-transform: uppercase;
}

/* ===== IMPROVEMENT ===== */
.bld2-imp-body {
  display: flex; align-items: center; gap: 1rem;
  margin-top: 0.3rem;
}
.bld2-imp-icon {
  width: 56px; height: 56px;
  border-radius: 8px;
  background: rgba(74,222,128,0.06);
  border: 1px solid rgba(74,222,128,0.25);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  padding: 6px;
}
.bld2-imp-icon svg { width: 100%; height: 100%; }
.bld2-imp-num {
  font-weight: 800;
  font-size: 1.5rem;
  color: var(--bld2-ink-100);
  letter-spacing: -0.04em;
  line-height: 1;
}
.bld2-imp-num .unit {
  font-size: 0.7rem;
  font-family: var(--bld2-mono);
  color: var(--bld2-ink-60);
  font-weight: 600;
  letter-spacing: 0.08em;
  margin-left: 4px;
}
.bld2-imp-tag {
  margin-top: 4px;
  font-family: var(--bld2-mono);
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  color: #4ADE80;
  text-transform: uppercase;
  font-weight: 700;
}
.bld2-imp-foot {
  margin-top: 4px;
  color: var(--bld2-ink-60);
  font-size: 0.66rem;
}

/* ===== PERFORMANCE OVER TIME (tabs styled in v2) ===== */
.bld2-perf-host .stTabs [data-baseweb="tab-list"] {
  gap: 4px;
  border-bottom: 1px solid var(--bld2-line);
  margin-bottom: 0.9rem;
}
.bld2-perf-host .stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--bld2-ink-60) !important;
  font-family: var(--bld2-mono) !important;
  font-size: 0.66rem !important;
  letter-spacing: 0.2em !important;
  font-weight: 700 !important;
  padding: 0.55rem 0.9rem !important;
  border-radius: 6px 6px 0 0 !important;
  border: none !important;
  text-transform: uppercase !important;
}
.bld2-perf-host .stTabs [aria-selected="true"] {
  color: var(--bld2-ink-100) !important;
  background: rgba(255,59,48,0.06) !important;
  border-bottom: 2px solid var(--bld2-red) !important;
}

/* ===== DRILL RECOMMENDATIONS ===== */
.bld2-drill-list {
  display: flex; flex-direction: column; gap: 0.6rem;
  margin-top: 0.3rem;
}
.bld2-drill-row {
  display: flex; align-items: center; gap: 0.9rem;
  padding: 0.75rem 0.85rem;
  background: var(--bld2-surface-0);
  border: 1px solid var(--bld2-line);
  border-radius: 8px;
  transition: border-color .22s, transform .22s, background .22s;
}
.bld2-drill-row:hover {
  border-color: rgba(255,59,48,0.4);
  transform: translateX(2px);
  background: var(--bld2-surface-1);
}
.bld2-drill-badge {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: rgba(255,59,48,0.1);
  border: 1px solid rgba(255,59,48,0.3);
  color: var(--bld2-red);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--bld2-mono);
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}
.bld2-drill-body { flex: 1; min-width: 0; }
.bld2-drill-title {
  color: var(--bld2-ink-100);
  font-weight: 600;
  font-size: 0.92rem;
  letter-spacing: -0.01em;
}
.bld2-drill-meta {
  margin-top: 3px;
  color: var(--bld2-ink-60);
  font-size: 0.7rem;
  font-family: var(--bld2-mono);
  letter-spacing: 0.08em;
}
.bld2-drill-arrow {
  color: var(--bld2-ink-40);
  font-size: 1rem;
  transition: color .22s, transform .22s;
}
.bld2-drill-row:hover .bld2-drill-arrow {
  color: var(--bld2-red);
  transform: translateX(2px);
}

/* ===== RECENT SWINGS ===== */
.bld2-recent-list {
  display: flex; flex-direction: column; gap: 0.5rem;
  margin-top: 0.3rem;
}
.bld2-recent-row {
  display: grid;
  grid-template-columns: 38px 1fr auto 12px;
  align-items: center;
  column-gap: 0.85rem;
  padding: 0.75rem 0.85rem;
  background: transparent;
  border: 1px solid var(--bld2-line);
  border-radius: 8px;
  transition: background .22s, border-color .22s, transform .22s, box-shadow .22s;
}
.bld2-recent-row:hover {
  background: var(--bld2-surface-1);
  border-color: rgba(255,59,48,0.4);
  transform: translateX(2px);
  box-shadow: 0 8px 24px -16px rgba(0,0,0,0.6);
}
.bld2-recent-num {
  font-family: var(--bld2-mono);
  font-size: 0.66rem;
  color: var(--bld2-ink-60);
  letter-spacing: 0.1em;
  font-weight: 700;
}
.bld2-recent-title {
  color: var(--bld2-ink-100);
  font-weight: 500;
  font-size: 0.88rem;
  letter-spacing: -0.005em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bld2-recent-meta {
  color: var(--bld2-ink-60);
  font-size: 0.66rem;
  margin-top: 3px;
  font-family: var(--bld2-mono);
  letter-spacing: 0.06em;
}
.bld2-recent-meta b { color: var(--bld2-ink-80); font-family: var(--bld2-sans); font-weight: 600; }
.bld2-recent-meta .v { color: var(--bld2-ink-40); }
.bld2-recent-score {
  font-family: var(--bld2-sans);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--bld2-ink-100);
  line-height: 1;
  letter-spacing: -0.02em;
  text-align: right;
}
.bld2-recent-score-foot {
  font-family: var(--bld2-mono);
  font-size: 0.54rem;
  letter-spacing: 0.18em;
  color: var(--bld2-ink-60);
  text-align: right;
  margin-top: 3px;
}
.bld2-recent-chev {
  color: var(--bld2-ink-40);
  font-size: 0.95rem;
  text-align: right;
  transition: color .22s, transform .22s;
}
.bld2-recent-row:hover .bld2-recent-chev {
  color: var(--bld2-red);
  transform: translateX(2px);
}

/* Recent rows wrapped around a real Streamlit button so they're clickable */
.bld2-recent-btn .stButton > button {
  width: 100% !important;
  text-align: left !important;
  background: transparent !important;
  border: 1px solid var(--bld2-line) !important;
  border-radius: 8px !important;
  color: var(--bld2-ink-100) !important;
  padding: 0.75rem 0.9rem !important;
  font-family: var(--bld2-sans) !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  line-height: 1.35 !important;
  justify-content: flex-start !important;
  cursor: pointer !important;
  transition: background .22s, border-color .22s, transform .22s, box-shadow .22s !important;
  box-shadow: none !important;
  white-space: pre-wrap !important;
}
.bld2-recent-btn .stButton > button:hover {
  background: var(--bld2-surface-1) !important;
  border-color: rgba(255,59,48,0.4) !important;
  transform: translateX(2px) !important;
  box-shadow: 0 10px 28px -18px rgba(0,0,0,0.65) !important;
}
.bld2-recent-btn .stButton > button p { margin: 0 !important; color: inherit !important; }

/* ===== ACHIEVEMENTS ===== */
.bld2-achievements {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0.75rem;
  margin-top: 0.4rem;
}
.bld2-achv {
  padding: 0.9rem 0.7rem;
  background: var(--bld2-surface-0);
  border: 1px solid var(--bld2-line);
  border-radius: 10px;
  text-align: center;
  position: relative;
  transition: border-color .22s, transform .22s;
}
.bld2-achv:hover {
  border-color: rgba(255,59,48,0.5);
  transform: translateY(-1px);
}
.bld2-achv-icon {
  font-size: 1.6rem;
  margin-bottom: 0.4rem;
  color: var(--bld2-red);
  filter: drop-shadow(0 0 6px rgba(255,59,48,0.4));
}
.bld2-achv.locked .bld2-achv-icon { color: var(--bld2-ink-40); filter: none; }
.bld2-achv-title {
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--bld2-ink-100);
  letter-spacing: -0.005em;
  line-height: 1.2;
}
.bld2-achv.locked .bld2-achv-title { color: var(--bld2-ink-60); }
.bld2-achv-foot {
  font-family: var(--bld2-mono);
  font-size: 0.52rem;
  letter-spacing: 0.18em;
  color: var(--bld2-ink-60);
  text-transform: uppercase;
  margin-top: 4px;
  font-weight: 600;
}

/* ===== FOOTER STRIP ===== */
.bld2-footer {
  margin-top: 2.2rem;
  padding: 1rem 0 0.6rem 0;
  border-top: 1px solid var(--bld2-line);
  display: flex; justify-content: space-between;
  font-family: var(--bld2-mono);
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  color: var(--bld2-ink-40);
  text-transform: uppercase;
}

/* ===== EMPTY STATE ===== */
.bld2-empty {
  padding: 3.2rem 1.8rem;
  text-align: center;
  background: var(--bld2-surface-0);
  border: 1px solid var(--bld2-line);
  border-radius: 14px;
  margin-bottom: 1.5rem;
}
.bld2-empty-icon { font-size: 2.5rem; margin-bottom: 0.7rem; color: var(--bld2-red); }
.bld2-empty-title {
  font-size: 1.5rem; font-weight: 700; letter-spacing: -0.025em;
  color: var(--bld2-ink-100);
}
.bld2-empty-sub {
  color: var(--bld2-ink-60);
  margin: 0.55rem auto 0;
  font-size: 0.95rem;
  max-width: 480px; line-height: 1.55;
}

/* Tighten Streamlit's column gutters so the cards align with the mockup */
.bl-page div[data-testid="column"] { padding: 0 0.35rem; }

/* The radar plot host */
.bld2-radar-host .js-plotly-plot { margin-top: -6px !important; }
</style>
"""


# ------------------------------------------------------------------
#  Feature-flag wrapper. Keeps v1 the default until Logan flips it.
# ------------------------------------------------------------------
def render_dashboard_auto(user: Dict[str, Any]) -> None:
    """Pick v1 or v2 based on `st.session_state['use_dashboard_v2']`."""
    if st.session_state.get("use_dashboard_v2"):
        render_dashboard_v2(user)
    else:
        from dashboard import render_dashboard
        render_dashboard(user)


# ------------------------------------------------------------------
#  Public entry — v2
# ------------------------------------------------------------------
def render_dashboard_v2(user: Dict[str, Any]) -> None:
    inject_global_theme()
    st.markdown(_DASHBOARD_V2_CSS, unsafe_allow_html=True)
    st.markdown('<div class="bl-page bld2-root">', unsafe_allow_html=True)

    history = _safe_history(user)
    latest = history[-1] if history else None

    _render_topbar(user, latest)
    _render_hero(user, latest)

    if not latest:
        _render_empty_state()
        _render_footer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ----- KPI ROW (4 cards) -----
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1: _render_score_card(history, latest)
    with c2: _render_mlb_jersey_card(latest)
    with c3: _render_top_focus_card(latest)
    with c4: _render_improvement_card(history, latest)

    st.markdown('<div style="height:1.2rem;"></div>', unsafe_allow_html=True)

    # ----- PERF + DRILLS -----
    perf_col, drill_col = st.columns([7, 5], gap="medium")
    with perf_col: _render_performance_card(history)
    with drill_col: _render_drills_card(latest)

    st.markdown('<div style="height:1.2rem;"></div>', unsafe_allow_html=True)

    # ----- RADAR + RECENT -----
    radar_col, recent_col = st.columns([7, 5], gap="medium")
    with radar_col: _render_radar_card(latest)
    with recent_col: _render_recent_card(history)

    st.markdown('<div style="height:1.2rem;"></div>', unsafe_allow_html=True)

    # ----- ACHIEVEMENTS -----
    _render_achievements_card(user, history)

    # ----- FOOTER -----
    _render_footer()

    st.markdown('</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
#  Section renderers
# ------------------------------------------------------------------
def _render_topbar(user: Dict[str, Any], latest: Optional[Dict[str, Any]]) -> None:
    first = (user.get("name") or "Player").split()[0]
    html = textwrap.dedent(f"""
    <div class="bld2-topbar">
      <div class="bld2-crumbs">
        BARRELLABS <span class="sep">›</span>
        SWINGAI <span class="sep">›</span>
        <span class="now">{first}'s Lab</span>
      </div>
      <div class="bld2-live">Live</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_hero(user: Dict[str, Any], latest: Optional[Dict[str, Any]]) -> None:
    first = (user.get("name") or "Player").split()[0]
    if latest:
        sub = f"Last swing analyzed {_format_when(latest.get('timestamp'))} · {_swing_count_str(user)}"
    else:
        sub = "Drop your first swing to populate the dashboard."
    html = textwrap.dedent(f"""
    <div class="bld2-hero">
      <h1>Welcome back, {first}<span class="red">.</span></h1>
      <div class="sub">Your hitting lab is live. {sub}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_empty_state() -> None:
    html = textwrap.dedent("""
    <div class="bld2-empty">
      <div class="bld2-empty-icon">⌖</div>
      <div class="bld2-empty-title">Your first swing unlocks everything.</div>
      <div class="bld2-empty-sub">
        Drop a side-angle clip and we'll generate your swing score,
        MLB comparison, biomechanical radar, and a personalized drill
        plan in under a minute.
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_score_card(history: List[Dict[str, Any]], latest: Dict[str, Any]) -> None:
    score = max(0, min(100, int(round(latest.get("score") or 0))))
    band_color = latest.get("score_band_color") or "amber"
    hex_color, _ = _score_color(band_color)
    band_label = (latest.get("score_band_label") or _short_band_tag(band_color))

    # Δ vs previous swing
    prev = history[-2] if len(history) >= 2 else None
    delta = None
    if prev:
        try:
            delta = int(round(score - float(prev.get("score") or 0)))
        except Exception:
            delta = None

    # 3/4 arc geometry (80%-style). 270° sweep starting at 12 o'clock.
    radius = 42
    center = 50
    circumf = 2 * math.pi * radius
    fill_frac = score / 100.0
    # We use a 3/4 circle visually: dasharray=circumf * 0.75 + gap.
    arc_len = circumf * 0.75
    dashoffset = arc_len * (1 - fill_frac)

    # Endpoint cap dot position. Starts at top (12 o'clock), sweeps
    # clockwise. The track is rendered with stroke-dashoffset, but the
    # *math* for the endpoint is the angle from -90deg + fill_frac * 270deg.
    end_angle_deg = -90.0 + fill_frac * 270.0
    end_rad = math.radians(end_angle_deg)
    cap_x = center + radius * math.cos(end_rad)
    cap_y = center + radius * math.sin(end_rad)

    delta_html = ""
    if delta is not None:
        sign = "↑ +" if delta >= 0 else "↓ "
        cls = "" if delta >= 0 else "down"
        delta_html = f'<div class="bld2-score-delta"><b class="{cls}">{sign}{abs(delta)}</b> vs last swing</div>'

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">SWING SCORE <span class="info-i">i</span></div>
      <div class="bld2-score-body">
        <div class="bld2-score-ring-wrap">
          <div class="bld2-score-scan"></div>
          <svg viewBox="0 0 100 100">
            <!-- track: 3/4 arc, rotated so the gap sits at the bottom -->
            <circle cx="50" cy="50" r="{radius}"
                    fill="none" stroke="rgba(255,255,255,0.06)"
                    stroke-width="5" stroke-linecap="round"
                    stroke-dasharray="{arc_len:.3f} {circumf:.3f}"
                    transform="rotate(135 50 50)"/>
            <!-- tick marks around the outer ring -->
            <circle cx="50" cy="50" r="{radius + 6}"
                    fill="none" stroke="rgba(255,255,255,0.18)"
                    stroke-width="3"
                    stroke-dasharray="1 22.83"
                    transform="rotate(135 50 50)"/>
            <!-- inner dashed marker ring -->
            <circle cx="50" cy="50" r="{radius - 8}"
                    fill="none" stroke="rgba(255,59,48,0.18)"
                    stroke-width="0.6"
                    stroke-dasharray="2 3"/>
            <!-- fill: animated stroke-dashoffset -->
            <circle cx="50" cy="50" r="{radius}"
                    fill="none" stroke="{hex_color}"
                    stroke-width="5" stroke-linecap="round"
                    stroke-dasharray="{arc_len:.3f} {circumf:.3f}"
                    stroke-dashoffset="{dashoffset:.3f}"
                    transform="rotate(135 50 50)"
                    style="filter: drop-shadow(0 0 6px {hex_color});"/>
            <!-- endpoint cap dot -->
            <circle cx="{cap_x:.2f}" cy="{cap_y:.2f}" r="2.4" fill="{hex_color}"
                    style="filter: drop-shadow(0 0 4px {hex_color});"/>
          </svg>
          <div class="bld2-score-center">
            <div class="bld2-score-num">{score}</div>
            <div class="bld2-score-num-foot">/ 100</div>
          </div>
        </div>
        <div class="bld2-score-meta">
          <div class="bld2-score-band">{band_label}</div>
          {delta_html}
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_mlb_jersey_card(latest: Dict[str, Any]) -> None:
    ref_slug = latest.get("reference_name") or ""
    pretty = _pretty_player_name(ref_slug) or "—"
    last_name = _last_name_upper(ref_slug)
    number = _jersey_number_for(ref_slug)
    pct = _similarity_pct(latest)
    pct_int = int(round(pct))
    handed = (latest.get("player_handedness") or "").upper()
    hand_disp = (
        "Right-handed swing" if handed.startswith("R") else
        "Left-handed swing"  if handed.startswith("L") else "—"
    )

    # Progress segments: 10 total, fill `pct/10` rounded
    fill_count = max(0, min(10, int(round(pct / 10.0))))
    segs = "".join(
        '<span class="fill"></span>' if i < fill_count else '<span></span>'
        for i in range(10)
    )

    # Adjust font-size dynamically based on name length so long surnames still fit.
    font_size = 6.5 if len(last_name) <= 8 else (5.8 if len(last_name) <= 10 else 5.0)
    letter_spacing = 1.1 if len(last_name) <= 8 else 0.6

    # Adjust number font-size for 3-digit numbers
    num_font = 34 if len(number) <= 2 else 28

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">MLB COMPARISON <span class="info-i">i</span></div>
      <div class="bld2-mlb-body">
        <div class="bld2-jersey">
          <svg viewBox="0 0 60 80" fill="none">
            <defs>
              <linearGradient id="jFill_{number}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#1e0808"/>
                <stop offset="0.4" stop-color="#140505"/>
                <stop offset="1" stop-color="#060101"/>
              </linearGradient>
              <linearGradient id="jSheen_{number}" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="rgba(255,255,255,0.09)"/>
                <stop offset="0.45" stop-color="rgba(255,255,255,0)"/>
              </linearGradient>
              <linearGradient id="jShadow_{number}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="rgba(0,0,0,0)"/>
                <stop offset="1" stop-color="rgba(0,0,0,0.5)"/>
              </linearGradient>
              <path id="jArch_{number}" d="M 11 30 Q 30 22 49 30" />
            </defs>
            <path d="M 4,10 L 20,5 Q 30,14 40,5 L 56,10 L 58,76 L 2,76 Z"
                  fill="url(#jFill_{number})" stroke="#FF3B30" stroke-width="1.1"
                  stroke-linejoin="round"/>
            <path d="M 4,10 L 20,5 Q 30,14 40,5 L 56,10 L 58,76 L 2,76 Z"
                  fill="url(#jSheen_{number})"/>
            <path d="M 20,5 Q 30,14 40,5 L 40,18 L 20,18 Z"
                  fill="url(#jShadow_{number})" opacity="0.6"/>
            <path d="M 20,7 Q 30,15 40,7" stroke="#FF3B30" stroke-width="1.4"
                  fill="none" stroke-linecap="round"/>
            <path d="M 21,9 Q 30,16.5 39,9" stroke="rgba(255,59,48,0.5)"
                  stroke-width="0.6" fill="none"/>
            <path d="M 5,11 Q 9,12 13,13" stroke="rgba(255,59,48,0.5)"
                  stroke-width="0.7" fill="none"/>
            <path d="M 55,11 Q 51,12 47,13" stroke="rgba(255,59,48,0.5)"
                  stroke-width="0.7" fill="none"/>
            <path d="M 4,18 L 4.5,70" stroke="rgba(255,59,48,0.35)"
                  stroke-width="0.5" stroke-dasharray="1.5 2"/>
            <path d="M 56,18 L 55.5,70" stroke="rgba(255,59,48,0.35)"
                  stroke-width="0.5" stroke-dasharray="1.5 2"/>
            <path d="M 2.5,72 L 57.5,72" stroke="rgba(255,255,255,0.14)" stroke-width="0.6"/>
            <text font-family="Inter, sans-serif" font-weight="800"
                  font-size="{font_size}" letter-spacing="{letter_spacing}" fill="#FF3B30">
              <textPath href="#jArch_{number}" startOffset="50%" text-anchor="middle">{last_name}</textPath>
            </text>
            <text x="30" y="62" font-family="Inter, sans-serif" font-weight="900"
                  font-size="{num_font}" fill="none" stroke="#FF3B30" stroke-width="1.2"
                  text-anchor="middle" letter-spacing="-0.04em" opacity="0.55">{number}</text>
            <text x="30" y="62" font-family="Inter, sans-serif" font-weight="900"
                  font-size="{num_font}" fill="#ffffff" text-anchor="middle"
                  letter-spacing="-0.04em">{number}</text>
          </svg>
        </div>
        <div>
          <div class="bld2-mlb-name">{pretty}</div>
          <div class="bld2-mlb-pct">{pct_int}% MATCH</div>
          <div class="bld2-mlb-hand">{hand_disp}</div>
        </div>
      </div>
      <div class="bld2-mlb-progress">{segs}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_top_focus_card(latest: Dict[str, Any]) -> None:
    metrics = _radar_from_record(latest)
    # Pick lowest-scoring axis as the focus
    if metrics:
        focus_axis, focus_value = min(metrics, key=lambda m: m[1])
    else:
        focus_axis, focus_value = "Hip Rotation", 70.0

    # Two-line name display
    name_parts = focus_axis.split()
    if len(name_parts) >= 2:
        name_html = f"{name_parts[0]}<br>{' '.join(name_parts[1:])}"
    else:
        name_html = focus_axis

    # Impact category
    impact = "High Impact" if focus_value < 65 else "Medium Impact" if focus_value < 80 else "Low Impact"

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">TOP FOCUS <span class="info-i">i</span></div>
      <div class="bld2-focus-body">
        <div class="bld2-focus-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <circle cx="12" cy="12" r="8"/>
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>
          </svg>
        </div>
        <div>
          <div class="bld2-focus-name">{name_html}</div>
          <div class="bld2-focus-impact">{impact}</div>
        </div>
      </div>
      <div class="bld2-focus-foot">View Details →</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_improvement_card(history: List[Dict[str, Any]], latest: Dict[str, Any]) -> None:
    """Improvement = current_score - mean(last 7 days, excluding latest)."""
    latest_score = float(latest.get("score") or 0)
    # 7-day rolling avg from prior swings
    now = _record_dt(latest)
    cutoff = (now or datetime.utcnow()) - timedelta(days=7)
    prior = []
    for r in history[:-1]:
        d = _record_dt(r)
        try:
            s = float(r.get("score") or 0)
        except Exception:
            continue
        if not d or d >= cutoff:
            prior.append(s)
    avg = (sum(prior) / len(prior)) if prior else latest_score
    delta = latest_score - avg

    # Sparkline trend (last 8 scores)
    recent_scores = []
    for r in history[-8:]:
        try:
            recent_scores.append(float(r.get("score") or 0))
        except Exception:
            pass
    if not recent_scores:
        recent_scores = [latest_score]
    if len(recent_scores) == 1:
        recent_scores = [recent_scores[0], recent_scores[0]]

    sparkline_path = _build_sparkline_path(recent_scores, width=56, height=24)
    sparkline_fill = sparkline_path + f" L 56 28 L 0 28 Z"

    sign = "+" if delta >= 0 else ""
    tag = "New Personal Best" if (delta > 0 and latest_score == max(float(r.get("score") or 0) for r in history)) else ("Trending Up" if delta > 0 else "Trending Down")
    tag_color = "#4ADE80" if delta >= 0 else "#FF3B30"

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">IMPROVEMENT <span class="info-i">i</span></div>
      <div class="bld2-imp-body">
        <div class="bld2-imp-icon">
          <svg viewBox="0 0 60 30" fill="none">
            <path d="{sparkline_fill}" fill="rgba(74,222,128,0.15)"/>
            <path d="{sparkline_path}" stroke="#4ADE80" stroke-width="2"
                  stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
        </div>
        <div>
          <div class="bld2-imp-num">{sign}{delta:.1f}<span class="unit">PTS</span></div>
          <div class="bld2-imp-tag" style="color:{tag_color};">{tag}</div>
          <div class="bld2-imp-foot">vs. 7-day avg</div>
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_performance_card(history: List[Dict[str, Any]]) -> None:
    st.markdown(
        '<div class="bld2-card bld2-perf-host">'
        '<div class="bld2-card-eyebrow">PERFORMANCE OVER TIME <span class="info-i">i</span></div>',
        unsafe_allow_html=True,
    )
    tab_7, tab_30, tab_90 = st.tabs(["7D", "30D", "90D"])
    with tab_7:  st.plotly_chart(_build_perf_figure(history, 7),  width="stretch", config={"displayModeBar": False})
    with tab_30: st.plotly_chart(_build_perf_figure(history, 30), width="stretch", config={"displayModeBar": False})
    with tab_90: st.plotly_chart(_build_perf_figure(history, 90), width="stretch", config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)


def _render_drills_card(latest: Dict[str, Any]) -> None:
    drill_plan = latest.get("drill_plan") or {}

    # drill_plan can be either: dict of category -> list of drill dicts,
    # OR a list of drill dicts. Normalize.
    drills: List[Dict[str, Any]] = []
    if isinstance(drill_plan, dict):
        for cat, items in drill_plan.items():
            if isinstance(items, list):
                for d in items:
                    if isinstance(d, dict):
                        d = dict(d)
                        d["_category"] = cat
                        drills.append(d)
                    elif isinstance(d, str):
                        drills.append({"name": d, "_category": cat})
    elif isinstance(drill_plan, list):
        for d in drill_plan:
            if isinstance(d, dict):
                drills.append(d)
            elif isinstance(d, str):
                drills.append({"name": d})

    drills = drills[:4]  # top 4 for card

    rows_html = ""
    if drills:
        for i, d in enumerate(drills, 1):
            name = d.get("name") or d.get("title") or "Drill"
            cat = d.get("_category") or d.get("category") or ""
            duration = d.get("duration") or d.get("time") or "10 min"
            meta = f"{cat.replace('_', ' ').title()} · {duration}" if cat else duration
            rows_html += textwrap.dedent(f"""
            <div class="bld2-drill-row">
              <div class="bld2-drill-badge">{i:02d}</div>
              <div class="bld2-drill-body">
                <div class="bld2-drill-title">{name}</div>
                <div class="bld2-drill-meta">{meta}</div>
              </div>
              <div class="bld2-drill-arrow">›</div>
            </div>
            """).strip()
    else:
        rows_html = (
            '<div style="padding:1rem;color:var(--bld2-ink-60);'
            'font-size:0.85rem;text-align:center;">'
            'No drill plan generated for this swing yet.</div>'
        )

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">DRILL RECOMMENDATIONS <span class="info-i">i</span></div>
      <div class="bld2-drill-list">
        {rows_html}
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_radar_card(latest: Dict[str, Any]) -> None:
    metrics = _radar_from_record(latest)
    st.markdown(
        '<div class="bld2-card bld2-radar-host">'
        '<div class="bld2-card-eyebrow">BIOMECHANICAL SIGNATURE <span class="info-i">i</span></div>',
        unsafe_allow_html=True,
    )
    fig = _build_radar_figure(metrics)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)


def _render_recent_card(history: List[Dict[str, Any]]) -> None:
    recent = list(reversed(history))[:5]

    st.markdown(
        '<div class="bld2-card">'
        '<div class="bld2-card-eyebrow">RECENT SWINGS <span class="info-i">i</span></div>'
        '<div class="bld2-recent-list">',
        unsafe_allow_html=True,
    )

    if not recent:
        st.markdown(
            '<div style="padding:1rem;text-align:center;color:var(--bld2-ink-60);'
            'font-size:0.85rem;">No swings yet.</div></div></div>',
            unsafe_allow_html=True,
        )
        return

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
        label = f"{num_disp}     {title}     ·     {date}     ·     SCORE {score}    ›"

        st.markdown('<div class="bld2-recent-btn">', unsafe_allow_html=True)
        btn_key = f"bld2_recent_{idx}_{rec.get('id') or rec.get('timestamp') or idx}"
        if st.button(label, key=btn_key, width="stretch"):
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

    st.markdown('</div></div>', unsafe_allow_html=True)


def _render_achievements_card(user: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    """Render 6 achievement tiles. Earned ones glow red; locked ones gray."""
    try:
        from gamification import ACHIEVEMENTS, determine_achievements
    except Exception:
        return  # gamification module missing — skip silently

    # Pull out scores + biggest score-to-score improvement
    scores: List[float] = []
    for r in history:
        try:
            scores.append(float(r.get("score") or 0))
        except Exception:
            pass
    best_score = max(scores) if scores else 0
    max_improve = 0
    for i in range(1, len(scores)):
        max_improve = max(max_improve, int(round(scores[i] - scores[i - 1])))

    # Build the player state shape gamification expects.
    state = {
        "total_swings":            len(history),
        "best_score":              best_score,
        "total_drills_completed":  int(user.get("total_drills_completed", 0)),
        "max_score_improvement":   max_improve,
        "longest_streak_days":     int(user.get("longest_streak_days", 0)),
    }
    try:
        earned = set(determine_achievements(state))
    except Exception:
        earned = set()

    # Category → icon mapping (gamification.py doesn't store icons)
    cat_icon = {
        "swing":       "◎",
        "drill":       "✦",
        "score":       "★",
        "streak":      "▲",
        "improvement": "↗",
    }

    # Prioritize: show the first 6 either-earned-or-just-above-current-target
    def _sort_key(a: Dict[str, Any]) -> Tuple[int, int]:
        # earned first, then by target ascending
        return (0 if a["id"] in earned else 1, int(a.get("target") or 0))

    pick = sorted(ACHIEVEMENTS, key=_sort_key)[:6]

    tiles = []
    for a in pick:
        is_earned = a.get("id") in earned
        icon = cat_icon.get(a.get("category"), "★")
        title = a.get("title") or "Achievement"
        cls = "" if is_earned else "locked"
        foot = "UNLOCKED" if is_earned else "LOCKED"
        tiles.append(textwrap.dedent(f"""
        <div class="bld2-achv {cls}">
          <div class="bld2-achv-icon">{icon}</div>
          <div class="bld2-achv-title">{title}</div>
          <div class="bld2-achv-foot">{foot}</div>
        </div>
        """).strip())

    html = textwrap.dedent(f"""
    <div class="bld2-card">
      <div class="bld2-card-eyebrow">ACHIEVEMENTS <span class="info-i">i</span></div>
      <div class="bld2-achievements">
        {"".join(tiles)}
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


def _render_footer() -> None:
    now = datetime.now().strftime("%H:%M:%S")
    html = textwrap.dedent(f"""
    <div class="bld2-footer">
      <div>BARRELLABS · SWINGAI v1.0</div>
      <div>SYSTEM ONLINE · {now}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


# ------------------------------------------------------------------
#  Plotly figures
# ------------------------------------------------------------------
def _build_perf_figure(history: List[Dict[str, Any]], days: int) -> go.Figure:
    cutoff = datetime.utcnow() - timedelta(days=days)
    xs: List[datetime] = []
    ys: List[float] = []
    for r in history:
        d = _record_dt(r)
        if not d:
            continue
        # Strip tz so the comparison is naive-to-naive
        d_naive = d.replace(tzinfo=None) if d.tzinfo else d
        if d_naive < cutoff:
            continue
        try:
            ys.append(float(r.get("score") or 0))
            xs.append(d_naive)
        except Exception:
            pass

    fig = go.Figure()

    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines+markers",
            line=dict(color="#FF3B30", width=2.5, shape="spline", smoothing=0.8),
            marker=dict(color="#FF3B30", size=7, line=dict(color="#050505", width=1.5)),
            fill="tozeroy",
            fillcolor="rgba(255,59,48,0.10)",
            hovertemplate="<b>%{y:.0f}</b><br>%{x|%b %d}<extra></extra>",
        ))
    else:
        # Empty state — show a flat baseline so the card doesn't look broken
        fig.add_annotation(
            text="No swings in this window yet.",
            showarrow=False,
            font=dict(family="JetBrains Mono", size=11, color="#6a6a6a"),
            xref="paper", yref="paper", x=0.5, y=0.5,
        )

    fig.update_layout(
        height=260,
        margin=dict(l=36, r=18, t=14, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            tickfont=dict(family="JetBrains Mono", size=9, color="#9a9a9a"),
            gridcolor="rgba(255,255,255,0.04)",
            linecolor="rgba(255,255,255,0.06)",
            showgrid=True,
        ),
        yaxis=dict(
            range=[0, 100],
            tickvals=[0, 25, 50, 75, 100],
            tickfont=dict(family="JetBrains Mono", size=9, color="#9a9a9a"),
            gridcolor="rgba(255,255,255,0.05)",
            linecolor="rgba(255,255,255,0.06)",
        ),
    )
    return fig


def _build_radar_figure(metrics: List[Tuple[str, float]]) -> go.Figure:
    labels = [m[0] for m in metrics] or ["—"]
    values = [m[1] for m in metrics] or [0]
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed, theta=labels_closed,
        mode="lines+markers",
        line=dict(color="#FF3B30", width=2),
        marker=dict(color="#FF3B30", size=6, line=dict(color="#050505", width=2)),
        fill="toself",
        fillcolor="rgba(255,59,48,0.13)",
        hovertemplate="<b>%{theta}</b><br>%{r:.0f}<extra></extra>",
        name="Latest swing",
    ))
    fig.update_layout(
        height=340,
        margin=dict(l=46, r=46, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        polar=dict(
            bgcolor="rgba(255,255,255,0.008)",
            radialaxis=dict(
                visible=True, range=[0, 100],
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
#  Tiny helpers
# ------------------------------------------------------------------
def _record_dt(rec: Dict[str, Any]) -> Optional[datetime]:
    ts = rec.get("timestamp") or rec.get("created_at")
    if not ts:
        return None
    try:
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            return datetime.strptime(str(ts), "%Y%m%d-%H%M%S")
    except Exception:
        return None


def _build_sparkline_path(values: List[float], width: int = 56, height: int = 24) -> str:
    if not values:
        return f"M 0 {height} L {width} {height}"
    lo = min(values)
    hi = max(values)
    span = max(1.0, hi - lo)
    n = len(values)
    pts: List[Tuple[float, float]] = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * width if n > 1 else 0
        y = height - ((v - lo) / span) * height
        # Inset by a couple px so the line doesn't sit on the very edge
        y = max(2, min(height - 2, y))
        pts.append((x, y))
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts)
