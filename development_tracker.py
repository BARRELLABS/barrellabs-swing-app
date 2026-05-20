"""
Development Tracker page — BarrelLabs premium edition.

Loads the current logged-in player's latest swing with a drill plan
from public.swings, and reads/writes drill completion + session notes
to public.training_logs via player_storage.

This file owns:
  • Page-local CSS (.dt-* classes) layered on top of bl_theme tokens
  • A SwingAI-styled hero
  • A live progress ring (SVG, matches dashboard score ring language)
  • Priority category section headers
  • Glass drill cards with custom checkbox + reps input
  • A notes composer styled like a card
  • A red pill CTA for saving notes

Functionality preserved verbatim: load_swing_history,
load_training_log, save_training_log, the player_id / drill_id keys,
and the dirty-write pattern.
"""

from datetime import datetime
import html as _html
import textwrap

import streamlit as st

from bl_theme import inject_global_theme
from bl_edge_chrome import render_edge_masthead
from player_storage import (
    load_swing_history,
    load_training_log,
    save_training_log,
    load_all_swing_meta,
    load_player_progress,
    save_player_progress,
)
from entitlements import can_access_development_tracker
from subscription_storage import load_my_plan
from gamification import (
    ACHIEVEMENTS,
    REWARDS,
    compute_player_state,
    achievement_by_id,
    reward_by_id,
)


# ============================================================
#                    PAGE-LOCAL STYLES
# ============================================================
_DT_LOCAL_CSS = """
<style>
/* ===========  HERO  =========== */
.dt-hero {
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
.dt-hero::before {
    content: "";
    position: absolute;
    top: -120px; right: -120px;
    width: 380px; height: 380px;
    background: radial-gradient(circle, rgba(255,59,48,0.18), transparent 65%);
    filter: blur(60px);
    pointer-events: none;
}
.dt-hero-row {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 1.4rem; position: relative; z-index: 1;
}
.dt-hero-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.28em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}
.dt-hero-title {
    font-family: var(--bl-sans);
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1.05;
    margin-bottom: 0.65rem;
}
.dt-hero-sub {
    color: var(--bl-ink-60);
    font-size: 0.96rem;
    line-height: 1.55;
    max-width: 580px;
}
.dt-mode-pill {
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
.dt-mode-pill-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--bl-red);
    box-shadow: 0 0 8px var(--bl-red);
}

/* ===========  PROGRESS OVERVIEW CARD  =========== */
.dt-progress-card {
    display: grid;
    grid-template-columns: 180px 1fr;
    gap: 2rem;
    align-items: center;
    padding: 1.9rem 2.1rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: 2rem;
}
.dt-ring {
    position: relative;
    width: 150px; height: 150px;
    margin: 0 auto;
}
.dt-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.dt-ring-track {
    fill: none;
    stroke: rgba(255,255,255,0.06);
    stroke-width: 11;
}
.dt-ring-fill {
    fill: none;
    stroke: var(--bl-red);
    stroke-width: 11;
    stroke-linecap: round;
    filter: drop-shadow(0 0 12px rgba(255,59,48,0.45));
    transition: stroke-dashoffset .8s cubic-bezier(.2,.7,.2,1);
}
.dt-ring-center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.dt-ring-pct {
    font-family: var(--bl-sans);
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    color: var(--bl-ink-100);
    line-height: 1;
}
.dt-ring-pct-sym {
    font-size: 1.1rem;
    color: var(--bl-ink-40);
    margin-left: 2px;
}
.dt-ring-tag {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-60);
    text-transform: uppercase;
    margin-top: 0.35rem;
}

.dt-progress-meta-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}
.dt-progress-meta-title {
    font-family: var(--bl-sans);
    font-size: 1.4rem;
    font-weight: 600;
    letter-spacing: -0.018em;
    color: var(--bl-ink-100);
    margin-bottom: 0.7rem;
}
.dt-progress-meta-line {
    color: var(--bl-ink-60);
    font-size: 0.92rem;
    line-height: 1.55;
    margin-bottom: 1rem;
}
.dt-stat-row { display: flex; gap: 1.8rem; flex-wrap: wrap; }
.dt-stat-item {
    display: flex; flex-direction: column;
    padding: 0.7rem 1rem;
    background: rgba(255,255,255,0.015);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-sm);
    min-width: 110px;
}
.dt-stat-num {
    font-family: var(--bl-sans);
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    line-height: 1.05;
}
.dt-stat-label {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-top: 0.35rem;
}
.dt-stat-num.is-red { color: var(--bl-red); }

/* ===========  CATEGORY SECTION HEADERS  =========== */
.dt-cat-header {
    display: flex; align-items: center; gap: 0.95rem;
    margin: 2.2rem 0 1rem 0;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid var(--bl-line);
}
.dt-cat-priority-pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-red);
    background: rgba(255,59,48,0.08);
    border: 1px solid rgba(255,59,48,0.24);
    border-radius: 999px;
    padding: 0.38rem 0.75rem;
    text-transform: uppercase;
    white-space: nowrap;
}
.dt-cat-title {
    font-family: var(--bl-sans);
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    color: var(--bl-ink-100);
}
.dt-cat-count {
    margin-left: auto;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}

/* ===========  DRILL CARD  =========== */
.dt-drill {
    position: relative;
    padding: 1.4rem 1.6rem;
    border-radius: var(--bl-radius-md);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    margin-bottom: 0.85rem;
    transition: border-color .25s ease, background .25s ease, transform .25s ease;
}
.dt-drill:hover {
    border-color: var(--bl-line-hi);
    background: rgba(255,255,255,0.028);
    transform: translateY(-1px);
}
.dt-drill.is-done {
    border-color: rgba(255,59,48,0.28);
    background: linear-gradient(180deg,
                rgba(255,59,48,0.05),
                rgba(255,59,48,0.02) 60%,
                rgba(255,255,255,0.012));
}
.dt-drill.is-done::before {
    content: "";
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--bl-red);
    border-radius: 3px 0 0 3px;
    box-shadow: 0 0 12px rgba(255,59,48,0.35);
}

.dt-drill-row {
    display: flex; align-items: flex-start; gap: 1rem;
    margin-bottom: 0.7rem;
}
.dt-drill-num {
    flex: 0 0 38px;
    height: 38px;
    border-radius: 999px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bl-line);
    display: inline-flex; align-items: center; justify-content: center;
    font-family: var(--bl-mono);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--bl-ink-60);
    letter-spacing: 0.05em;
}
.dt-drill.is-done .dt-drill-num {
    background: rgba(255,59,48,0.10);
    border-color: rgba(255,59,48,0.35);
    color: var(--bl-red);
}
.dt-drill-meta { flex: 1; min-width: 0; }
.dt-drill-name {
    font-family: var(--bl-sans);
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--bl-ink-100);
    line-height: 1.25;
    margin-bottom: 0.35rem;
}
.dt-drill-reps {
    display: inline-flex; align-items: center; gap: 0.35rem;
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    color: var(--bl-ink-60);
    text-transform: uppercase;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    border-radius: 999px;
    padding: 0.32rem 0.7rem;
    margin-bottom: 0.55rem;
}
.dt-drill-how {
    color: var(--bl-ink-80);
    font-size: 0.9rem;
    line-height: 1.55;
}
.dt-drill-status-pill {
    flex: 0 0 auto;
    align-self: flex-start;
    display: inline-flex; align-items: center; gap: 0.35rem;
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    border-radius: 999px;
    padding: 0.4rem 0.75rem;
    text-transform: uppercase;
    transition: all .25s ease;
}
.dt-drill.is-done .dt-drill-status-pill {
    color: var(--bl-red);
    background: rgba(255,59,48,0.08);
    border-color: rgba(255,59,48,0.32);
    box-shadow: 0 0 16px -4px rgba(255,59,48,0.25);
}

/* ===========  STREAMLIT WIDGET TWEAKS INSIDE DRILL CARDS  =========== */
/* Make the action row (checkbox + reps input) sit cleanly together. */
.dt-actions-wrap {
    margin-top: 0.65rem;
    padding-top: 0.85rem;
    border-top: 1px dashed var(--bl-line);
}
.dt-actions-wrap [data-testid="stCheckbox"] label {
    font-family: var(--bl-mono) !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.2em !important;
    color: var(--bl-ink-80) !important;
    text-transform: uppercase !important;
}
.dt-actions-wrap [data-testid="stCheckbox"] label p {
    color: var(--bl-ink-80) !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.2em !important;
}
.dt-actions-wrap [data-testid="stCheckbox"] [data-baseweb="checkbox"] div[role="checkbox"] {
    border-radius: 6px !important;
    border-color: var(--bl-line-hi) !important;
}
.dt-actions-wrap [data-testid="stCheckbox"] [data-baseweb="checkbox"][aria-checked="true"] div[role="checkbox"] {
    background: var(--bl-red) !important;
    border-color: var(--bl-red) !important;
    box-shadow: 0 0 10px rgba(255,59,48,0.4) !important;
}
.dt-actions-wrap input[type="text"] {
    background: rgba(255,255,255,0.018) !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bl-ink-100) !important;
    font-family: var(--bl-mono) !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.04em !important;
    border-radius: 10px !important;
    transition: border-color .2s ease, background .2s ease !important;
}
.dt-actions-wrap input[type="text"]:focus {
    border-color: rgba(255,59,48,0.35) !important;
    background: rgba(255,255,255,0.028) !important;
    box-shadow: 0 0 0 3px rgba(255,59,48,0.10) !important;
}
.dt-actions-wrap [data-testid="stTextInput"] label,
.dt-actions-wrap [data-testid="stTextInput"] label p {
    font-family: var(--bl-mono) !important;
    font-size: 0.6rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    color: var(--bl-ink-40) !important;
    text-transform: uppercase !important;
}

/* ===========  NOTES CARD  =========== */
.dt-notes-header {
    display: flex; align-items: center; gap: 0.9rem;
    margin: 2.4rem 0 1rem 0;
}
.dt-notes-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    color: var(--bl-red);
    text-transform: uppercase;
}
.dt-notes-title {
    font-family: var(--bl-sans);
    font-size: 1.35rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    color: var(--bl-ink-100);
}
.dt-notes-card {
    padding: 0.4rem 0 0.1rem 0;
}
.dt-notes-card [data-testid="stTextArea"] textarea {
    background: var(--bl-surface-1) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: var(--bl-radius-md) !important;
    color: var(--bl-ink-100) !important;
    font-family: var(--bl-sans) !important;
    font-size: 0.95rem !important;
    line-height: 1.55 !important;
    padding: 1rem 1.1rem !important;
    transition: border-color .2s ease, background .2s ease !important;
}
.dt-notes-card [data-testid="stTextArea"] textarea:focus {
    border-color: rgba(255,59,48,0.35) !important;
    background: rgba(255,255,255,0.028) !important;
    box-shadow: 0 0 0 3px rgba(255,59,48,0.10) !important;
}
.dt-notes-card [data-testid="stTextArea"] label { display: none !important; }

/* ===========  PREVIOUS SESSIONS  =========== */
.dt-prev-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin: 2.4rem 0 1rem 0;
}
.dt-prev-entry {
    padding: 1rem 1.2rem;
    border-radius: var(--bl-radius-sm);
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    margin-bottom: 0.65rem;
}
.dt-prev-date {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.dt-prev-text {
    color: var(--bl-ink-80);
    font-size: 0.9rem;
    line-height: 1.55;
}

/* ===========  EMPTY STATE  =========== */
.dt-empty {
    text-align: center;
    padding: 4rem 2rem;
    border-radius: var(--bl-radius-lg);
    background: var(--bl-surface-1);
    border: 1px dashed var(--bl-line-hi);
}
.dt-empty-icon {
    font-size: 2.4rem;
    color: var(--bl-red);
    margin-bottom: 1rem;
    opacity: 0.7;
}
.dt-empty-title {
    font-family: var(--bl-sans);
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--bl-ink-100);
    margin-bottom: 0.55rem;
    letter-spacing: -0.012em;
}
.dt-empty-sub {
    color: var(--bl-ink-60);
    font-size: 0.95rem;
    line-height: 1.55;
    max-width: 460px;
    margin: 0 auto;
}

/* ===========  BACK NAV  =========== */
.dt-back .stButton > button {
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
.dt-back .stButton > button:hover {
    border-color: rgba(255,59,48,0.35) !important;
    color: var(--bl-red) !important;
    background: rgba(255,59,48,0.05) !important;
    transform: translateX(-2px);
}

/* ===========  SAVE CTA  =========== */
.dt-save .stButton > button {
    background: linear-gradient(180deg, var(--bl-red), #e8342a) !important;
    border: 1px solid rgba(255,59,48,0.55) !important;
    color: #ffffff !important;
    font-family: var(--bl-sans) !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    letter-spacing: 0.02em !important;
    border-radius: 999px !important;
    padding: 0.7rem 1.6rem !important;
    box-shadow: 0 0 24px -6px rgba(255,59,48,0.55),
                inset 0 1px 0 rgba(255,255,255,0.18) !important;
    transition: transform .25s cubic-bezier(.2,.7,.2,1),
                box-shadow .25s cubic-bezier(.2,.7,.2,1) !important;
}
.dt-save .stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 32px -4px rgba(255,59,48,0.75),
                inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.dt-save .stButton > button p {
    font-size: 0.92rem !important;
    font-weight: 600 !important;
}

/* ===========  GAMIFICATION  =========== */
/* Level / XP card */
.dt-level-card {
    position: relative;
    padding: 1.7rem 1.9rem 1.5rem;
    border-radius: var(--bl-radius-lg);
    background: linear-gradient(135deg, rgba(255,59,48,0.10), rgba(255,255,255,0.025) 60%);
    border: 1px solid rgba(255,59,48,0.22);
    margin-bottom: 1.2rem;
    overflow: hidden;
}
.dt-level-card::before {
    content:"";
    position: absolute;
    top:-90px; right:-90px;
    width:280px; height:280px;
    background: radial-gradient(circle, rgba(255,59,48,0.18), transparent 65%);
    filter: blur(40px);
    pointer-events: none;
}
.dt-level-row {
    display:flex; align-items:center; justify-content:space-between;
    gap:1.2rem; position:relative; z-index:1;
    flex-wrap: wrap;
}
.dt-level-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.28em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.45rem;
}
.dt-level-name {
    font-family: var(--bl-sans);
    font-size: 1.85rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--bl-ink-100);
    line-height: 1;
    margin-bottom: 0.35rem;
}
.dt-level-tagline {
    font-family: var(--bl-sans);
    font-size: 0.9rem;
    color: var(--bl-ink-60);
    margin-bottom: 0.1rem;
}
.dt-xp-pill {
    display:inline-flex; align-items:center; gap:0.45rem;
    font-family: var(--bl-mono);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: var(--bl-ink-100);
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bl-line-hi);
    border-radius: 999px;
    padding: 0.45rem 0.85rem;
    text-transform: uppercase;
    white-space: nowrap;
}
.dt-xp-pill .dt-xp-num { color: var(--bl-red); letter-spacing: 0.04em; }
.dt-xp-bar-wrap {
    margin-top: 1.1rem;
    position: relative; z-index:1;
}
.dt-xp-bar {
    position:relative;
    height: 10px;
    width: 100%;
    border-radius: 999px;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--bl-line);
    overflow: hidden;
}
.dt-xp-bar-fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: linear-gradient(90deg, var(--bl-red), #ff7a72);
    border-radius: 999px;
    box-shadow: 0 0 12px rgba(255,59,48,0.55);
    transition: width .6s cubic-bezier(.2,.7,.2,1);
}
.dt-xp-bar-foot {
    display:flex; justify-content:space-between;
    margin-top: 0.55rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    color: var(--bl-ink-60);
    text-transform: uppercase;
}
.dt-xp-bar-foot .dt-xp-foot-next { color: var(--bl-ink-100); }

/* Stat strip */
.dt-stat-strip {
    display:grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.7rem;
    margin-bottom: 1.4rem;
}
@media (max-width: 900px) {
    .dt-stat-strip { grid-template-columns: repeat(2, 1fr); }
}
.dt-stat-pod {
    padding: 1rem 1.05rem;
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-md);
    text-align: left;
}
.dt-stat-pod-num {
    font-family: var(--bl-sans);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    line-height: 1.05;
}
.dt-stat-pod-num.is-red { color: var(--bl-red); }
.dt-stat-pod-label {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-top: 0.4rem;
}

/* Motivational chips strip */
.dt-motivate-strip {
    display: flex; flex-wrap: wrap; gap: 0.55rem;
    margin-bottom: 1.6rem;
}
.dt-motivate-chip {
    font-family: var(--bl-sans);
    font-size: 0.82rem;
    color: var(--bl-ink-80);
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    border-radius: 999px;
    padding: 0.45rem 0.95rem;
}
.dt-motivate-chip.is-red {
    color: var(--bl-red);
    border-color: rgba(255,59,48,0.32);
    background: rgba(255,59,48,0.06);
}

/* Section header (gamification) */
.dt-gm-section-header {
    display:flex; align-items:baseline; gap:0.9rem;
    margin: 2.2rem 0 1rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px solid var(--bl-line);
}
.dt-gm-section-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.26em;
    color: var(--bl-red);
    text-transform: uppercase;
}
.dt-gm-section-title {
    font-family: var(--bl-sans);
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.018em;
    color: var(--bl-ink-100);
}
.dt-gm-section-count {
    margin-left:auto;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}

/* Achievements grid */
.dt-ach-grid {
    display:grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1rem;
}
.dt-ach {
    position: relative;
    padding: 1.15rem 1.15rem 1.1rem;
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-md);
    transition: border-color .25s ease, background .25s ease, transform .25s ease;
}
.dt-ach.is-locked {
    opacity: 0.55;
}
.dt-ach.is-unlocked {
    border-color: rgba(255,59,48,0.34);
    background: linear-gradient(180deg, rgba(255,59,48,0.06), rgba(255,255,255,0.012));
}
.dt-ach-badge {
    width: 38px; height: 38px;
    border-radius: 12px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bl-line);
    display:inline-flex; align-items:center; justify-content:center;
    font-family: var(--bl-mono);
    font-size: 1rem;
    font-weight: 700;
    color: var(--bl-ink-60);
    margin-bottom: 0.65rem;
}
.dt-ach.is-unlocked .dt-ach-badge {
    background: linear-gradient(135deg, var(--bl-red), #c91e15);
    border-color: var(--bl-red);
    color: #fff;
    box-shadow: 0 0 16px -4px rgba(255,59,48,0.55);
}
.dt-ach-title {
    font-family: var(--bl-sans);
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.012em;
    margin-bottom: 0.25rem;
}
.dt-ach-desc {
    font-family: var(--bl-sans);
    font-size: 0.82rem;
    color: var(--bl-ink-60);
    line-height: 1.4;
    margin-bottom: 0.6rem;
}
.dt-ach-foot {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}
.dt-ach.is-unlocked .dt-ach-foot { color: var(--bl-red); }
.dt-ach-progress {
    margin-top: 0.5rem;
    height: 4px;
    background: rgba(255,255,255,0.04);
    border-radius: 999px;
    overflow: hidden;
}
.dt-ach-progress-fill {
    height: 100%;
    background: rgba(255,255,255,0.35);
    border-radius: 999px;
}

/* ===========  REWARDS ROADMAP (premium loyalty progression)  =========== */
.dt-reward-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    margin-bottom: 1.4rem;
}
.dt-reward {
    position: relative;
    padding: 1.55rem 1.75rem;
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-lg);
    display: grid;
    grid-template-columns: 96px 1fr auto;
    gap: 1.4rem;
    align-items: center;
    transition: border-color .25s ease, transform .25s ease, box-shadow .25s ease;
    overflow: hidden;
}
.dt-reward:hover {
    transform: translateY(-1px);
    border-color: var(--bl-line-hi);
}
.dt-reward.is-unlocked {
    border-color: rgba(255,59,48,0.42);
    background: linear-gradient(180deg, rgba(255,59,48,0.07), rgba(255,255,255,0.012));
}

/* Day pillar (left column) */
.dt-reward-day {
    text-align: center;
    padding: 0.95rem 0.5rem;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-md);
}
.dt-reward.is-unlocked .dt-reward-day {
    background: rgba(255,59,48,0.08);
    border-color: rgba(255,59,48,0.34);
}
.dt-reward-day-num {
    font-family: var(--bl-sans);
    font-size: 1.95rem;
    font-weight: 800;
    color: var(--bl-ink-100);
    letter-spacing: -0.03em;
    line-height: 1;
}
.dt-reward.is-unlocked .dt-reward-day-num { color: var(--bl-red); }
.dt-reward-day-lbl {
    font-family: var(--bl-mono);
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    margin-top: 0.35rem;
}

/* Body (middle column) */
.dt-reward-body { min-width: 0; }
.dt-reward-title {
    font-family: var(--bl-sans);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.015em;
    margin-bottom: 0.4rem;
    line-height: 1.2;
}
.dt-reward-desc {
    font-family: var(--bl-sans);
    font-size: 0.9rem;
    color: var(--bl-ink-60);
    line-height: 1.5;
    margin-bottom: 0.7rem;
}
.dt-reward-meta-row {
    display: flex; gap: 0.55rem; flex-wrap: wrap;
}

/* Type badge — base */
.dt-reward-kind {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-ink-60);
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    border-radius: 999px;
    padding: 0.36rem 0.75rem;
    text-transform: uppercase;
}
.dt-reward-kind::before {
    content: "";
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 6px currentColor;
    opacity: 0.85;
}

/* Type badge — per-category palettes (silver, cyan, violet, orange, gold,
   red-physical, mint-perk, gold-legacy) */
.dt-reward-kind.is-status {
    color: #cfd4dc; background: rgba(207,212,220,0.06); border-color: rgba(207,212,220,0.24);
}
.dt-reward-kind.is-collectible {
    color: #6ec5ff; background: rgba(110,197,255,0.07); border-color: rgba(110,197,255,0.30);
}
.dt-reward-kind.is-graphic {
    color: #c084fc; background: rgba(192,132,252,0.08); border-color: rgba(192,132,252,0.30);
}
.dt-reward-kind.is-report {
    color: #fb923c; background: rgba(251,146,60,0.08); border-color: rgba(251,146,60,0.32);
}
.dt-reward-kind.is-title {
    color: #fbbf24; background: rgba(251,191,36,0.08); border-color: rgba(251,191,36,0.32);
}
.dt-reward-kind.is-physical {
    color: #ff7a72; background: rgba(255,59,48,0.10); border-color: rgba(255,59,48,0.38);
}
.dt-reward-kind.is-perk {
    color: #6ee7b7; background: rgba(110,231,183,0.08); border-color: rgba(110,231,183,0.32);
}
.dt-reward-kind.is-legacy {
    color: #ffd166; background: rgba(255,209,102,0.10); border-color: rgba(255,209,102,0.42);
    text-shadow: 0 0 6px rgba(255,209,102,0.45);
}

/* Status (right column) */
.dt-reward-status {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
    text-align: right;
    padding: 0.55rem 0.9rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--bl-line);
    white-space: nowrap;
}
.dt-reward.is-unlocked .dt-reward-status {
    color: var(--bl-red);
    background: rgba(255,59,48,0.12);
    border-color: rgba(255,59,48,0.38);
}

/* === Emphasis: 180-day HOODIE === */
.dt-reward.is-hoodie {
    background:
        linear-gradient(135deg, rgba(255,59,48,0.16), rgba(255,255,255,0.02) 55%),
        var(--bl-surface-1);
    border: 1px solid rgba(255,59,48,0.55);
    box-shadow: 0 0 32px -8px rgba(255,59,48,0.45),
                inset 0 0 0 1px rgba(255,59,48,0.10);
}
.dt-reward.is-hoodie::before {
    content: "FLAGSHIP REWARD";
    position: absolute;
    top: 0.7rem; right: 0.9rem;
    font-family: var(--bl-mono);
    font-size: 0.52rem;
    font-weight: 800;
    letter-spacing: 0.28em;
    color: var(--bl-red);
    text-transform: uppercase;
    opacity: 0.9;
}
.dt-reward.is-hoodie::after {
    content: "";
    position: absolute;
    top: -90px; right: -90px;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(255,59,48,0.28), transparent 60%);
    filter: blur(40px);
    pointer-events: none;
    z-index: 0;
}
.dt-reward.is-hoodie > * { position: relative; z-index: 1; }
.dt-reward.is-hoodie .dt-reward-title {
    font-size: 1.32rem;
    letter-spacing: -0.02em;
}
.dt-reward.is-hoodie .dt-reward-day-num { color: var(--bl-red); }
.dt-reward.is-hoodie .dt-reward-day {
    background: rgba(255,59,48,0.10);
    border-color: rgba(255,59,48,0.42);
}

/* === Emphasis: 365-day HALL OF FAME (legendary) === */
.dt-reward.is-hof {
    background:
        linear-gradient(135deg, rgba(255,209,102,0.14), rgba(255,255,255,0.02) 55%),
        var(--bl-surface-1);
    border: 1px solid rgba(255,209,102,0.55);
    box-shadow: 0 0 36px -8px rgba(255,209,102,0.40),
                inset 0 0 0 1px rgba(255,209,102,0.12);
}
.dt-reward.is-hof::before {
    content: "LEGENDARY";
    position: absolute;
    top: 0.7rem; right: 0.9rem;
    font-family: var(--bl-mono);
    font-size: 0.52rem;
    font-weight: 800;
    letter-spacing: 0.32em;
    color: #ffd166;
    text-shadow: 0 0 10px rgba(255,209,102,0.55);
    text-transform: uppercase;
}
.dt-reward.is-hof::after {
    content: "";
    position: absolute;
    top: -100px; left: -100px;
    width: 340px; height: 340px;
    background: radial-gradient(circle, rgba(255,209,102,0.25), transparent 60%);
    filter: blur(45px);
    pointer-events: none;
    z-index: 0;
}
.dt-reward.is-hof > * { position: relative; z-index: 1; }
.dt-reward.is-hof .dt-reward-title {
    font-size: 1.32rem;
    letter-spacing: -0.02em;
    color: #fff5dc;
    text-shadow: 0 0 8px rgba(255,209,102,0.35);
}
.dt-reward.is-hof .dt-reward-day {
    background: rgba(255,209,102,0.10);
    border-color: rgba(255,209,102,0.45);
}
.dt-reward.is-hof .dt-reward-day-num { color: #ffd166; }
.dt-reward.is-hof .dt-reward-status {
    color: #ffd166;
    background: rgba(255,209,102,0.10);
    border-color: rgba(255,209,102,0.40);
}

@media (max-width: 720px) {
    .dt-reward {
        grid-template-columns: 1fr;
        text-align: left;
        gap: 0.9rem;
        padding: 1.3rem;
    }
    .dt-reward-day { max-width: 110px; }
    .dt-reward-status { text-align: left; justify-self: start; }
    .dt-reward.is-hoodie::before,
    .dt-reward.is-hof::before { position: static; display: block; margin-bottom: 0.5rem; }
}

/* ============================================================
   TRAINING PLAN ADDITIONS (v4):
     · .dt-coach   — per-category coach-note panel (why_it_matters)
     · .dt-role    — small badge on each drill (PRIMARY / SUPPORTING / CHALLENGE)
     · .dt-retest  — re-test reminder card after the drill list
   All scoped under the existing .bl-page wrapper so nothing leaks.
   ============================================================ */
.dt-coach {
    position: relative;
    margin: 0.6rem 0 0.9rem;
    padding: 1.1rem 1.2rem 1.05rem;
    border-radius: 14px;
    border: 1px solid rgba(232,193,112,0.22);
    background:
        radial-gradient(120% 100% at 0% 0%, rgba(232,193,112,0.06) 0%, transparent 60%),
        linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.008));
}
.dt-coach-eyebrow {
    display: inline-flex; align-items: center; gap: 0.5rem;
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #E8C170;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.dt-coach-eyebrow::before {
    content: "";
    width: 14px; height: 1px;
    background: #E8C170;
    display: inline-block;
}
.dt-coach-body {
    color: var(--bl-ink-80);
    font-size: 0.94rem;
    line-height: 1.55;
    max-width: 72ch;
}
.dt-coach-body strong { color: var(--bl-ink-100); font-weight: 600; }

.dt-role {
    display: inline-block;
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    font-weight: 700;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    margin-left: 0.5rem;
    vertical-align: middle;
}
.dt-role.is-primary {
    color: #E64530;
    background: rgba(230,69,48,0.10);
    border: 1px solid rgba(230,69,48,0.32);
}
.dt-role.is-supporting {
    color: #C8C4BB;
    background: rgba(244,239,230,0.05);
    border: 1px solid rgba(244,239,230,0.16);
}
.dt-role.is-challenge {
    color: #E8C170;
    background: rgba(232,193,112,0.10);
    border: 1px solid rgba(232,193,112,0.32);
}

.dt-retest {
    margin: 1.6rem 0 1.2rem;
    padding: 1.4rem 1.5rem;
    border-radius: 16px;
    border: 1px solid rgba(74,227,140,0.22);
    background:
        radial-gradient(120% 100% at 100% 0%, rgba(74,227,140,0.07) 0%, transparent 65%),
        linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.008));
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1rem;
    align-items: center;
}
.dt-retest-icon {
    width: 44px; height: 44px;
    border-radius: 12px;
    background: rgba(74,227,140,0.12);
    border: 1px solid rgba(74,227,140,0.36);
    display: grid; place-items: center;
    color: #4AE38C;
    font-family: var(--bl-mono);
    font-size: 1.1rem;
    font-weight: 800;
}
.dt-retest-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #4AE38C;
    font-weight: 700;
    margin-bottom: 0.25rem;
}
.dt-retest-title {
    font-size: 1.08rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    line-height: 1.25;
    margin-bottom: 0.4rem;
    letter-spacing: -0.01em;
}
.dt-retest-list {
    margin: 0; padding: 0; list-style: none;
    color: var(--bl-ink-80);
    font-size: 0.9rem;
    line-height: 1.55;
}
.dt-retest-list li {
    padding-left: 0.9rem;
    position: relative;
}
.dt-retest-list li + li { margin-top: 0.2rem; }
.dt-retest-list li::before {
    content: "›";
    position: absolute;
    left: 0;
    color: #4AE38C;
    font-weight: 700;
}
@media (max-width: 720px) {
    .dt-retest { grid-template-columns: 1fr; gap: 0.7rem; padding: 1.2rem; }
    .dt-retest-icon { width: 36px; height: 36px; }
    .dt-coach { padding: 0.95rem 1.05rem; }
    .dt-role { font-size: 0.5rem; padding: 0.15rem 0.45rem; }
}

/* ============================================================
   TRAINING PLAN v2 — Edge editorial overlay.
   Wrapping the page in `.tp-shell` re-declares the bl_theme tokens
   used by every .dt-* rule above, so the existing CSS automatically
   picks up the editorial palette without any class-by-class rewrite:
     · ink  #0A0B0E (dashboard_v3 black, not bl_theme's #050505)
     · bone #F4EFE6 / #C8C4BB / #8B8E94 / #565A62 (warm, not pure white)
     · red  #E64530 (dashboard_v3 red, not bl_theme's #FF3B30)
     · gold #E8C170 accent (additive — bl_theme has no gold)
     · serif Instrument Serif italic for display
     · sans Geist + Geist Mono labels
   Then a small set of new .tp-* classes adds the editorial hero,
   bento stat strip, and consistency bar that bl_theme can't express.
   ============================================================ */
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

.tp-shell {
    /* Re-declare the cascading tokens used by .dt-* — every selector
       above resolves these from the .tp-shell wrapper instead of
       :root, so the whole tracker repaints in the editorial language
       with one cascade hop. */
    --bl-bg:          #0A0B0E;
    --bl-surface-1:   rgba(255,255,255,0.025);
    --bl-surface-2:   rgba(255,255,255,0.045);
    --bl-line:        rgba(244,239,230,0.08);
    --bl-line-hi:     rgba(244,239,230,0.16);
    --bl-ink-100:     #F4EFE6;
    --bl-ink-80:      #C8C4BB;
    --bl-ink-60:      #8B8E94;
    --bl-ink-40:      #565A62;
    --bl-red:         #E64530;
    --bl-red-hover:   #ef5f4a;
    --bl-red-glow:    rgba(230,69,48,0.28);
    --bl-red-soft:    rgba(230,69,48,0.12);

    /* Editorial-only additions (no bl_theme equivalents). */
    --tp-gold:        #E8C170;
    --tp-gold-deep:   #C9A350;
    --tp-gold-soft:   rgba(232,193,112,0.10);
    --tp-gold-line:   rgba(232,193,112,0.32);
    --tp-green:       #4AE38C;
    --tp-serif:       'Instrument Serif', 'Fraunces', Georgia, serif;

    /* Override bl_theme font stacks via the same names so any
       .dt-* selector using var(--bl-sans/mono) re-skins for free. */
    --bl-sans:        'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --bl-mono:        'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;

    /* Editorial-paper film grain over the surface for depth. */
    position: relative;
    color: var(--bl-ink-100);
    font-family: var(--bl-sans);
}
.tp-shell::before {
    content: ""; position: absolute; inset: 0;
    pointer-events: none; z-index: 0;
    opacity: 0.025; mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml;utf8,<svg viewBox='0 0 240 240' xmlns='http://www.w3.org/2000/svg'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.6 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}
/* All real content sits above the grain. */
.tp-shell > * { position: relative; z-index: 1; }

/* ---- HERO ---- */
/* Replaces the bl_theme .dt-hero. The old hero is hidden when its
   parent gets `.tp-shell` so the two never double up. */
.tp-shell .dt-hero { display: none !important; }

.tp-hero {
    text-align: center;
    padding: 1.6rem 0 0.4rem;
    margin-bottom: 1.4rem;
    position: relative;
}
.tp-hero::before {
    content: ""; position: absolute;
    top: 10px; left: 50%; transform: translateX(-50%);
    width: 720px; height: 240px;
    background: radial-gradient(ellipse at center, rgba(232,193,112,0.10) 0%, transparent 70%);
    pointer-events: none; z-index: -1; filter: blur(20px);
}
.tp-eyebrow {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 14px;
    font-family: var(--bl-mono);
    font-size: 11px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--bl-red);
    font-weight: 600;
    margin-bottom: 22px;
}
.tp-eyebrow .stitch {
    display: inline-block; width: 30px; height: 1px;
    background: var(--bl-red); opacity: 0.85;
}
.tp-display {
    font-family: var(--tp-serif);
    font-weight: 400;
    font-size: clamp(2.6rem, 6vw, 5.4rem);
    line-height: 0.99;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    margin: 0 0 20px;
}
.tp-display .ital {
    font-style: italic;
    color: var(--tp-gold);
    padding: 0 0.04em;
}
.tp-display .red { color: var(--bl-red); }
.tp-deck {
    font-family: var(--bl-sans);
    font-weight: 300;
    font-size: clamp(0.98rem, 1.1vw, 1.15rem);
    line-height: 1.55;
    color: var(--bl-ink-80);
    max-width: 620px;
    margin: 0 auto 8px;
}
.tp-deck .em { color: var(--bl-ink-100); font-weight: 500; }
.tp-deck .gold { color: var(--tp-gold); font-weight: 500; }

/* Small inline tag rendered under the headline when we have a
   concrete priority-1 issue name from the analyzer. Sits between
   the display headline and the deck so the analyzer's diagnosis
   is never invisible, but doesn't compete with the headline. */
.tp-focus-tag {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    margin: 0 auto 14px;
    border-radius: 999px;
    background: rgba(232,193,112,0.08);
    border: 1px solid rgba(232,193,112,0.28);
    font-family: var(--bl-mono);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: var(--bl-ink-80);
}
.tp-focus-tag .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--tp-gold);
    box-shadow: 0 0 8px rgba(232,193,112,0.65);
    flex-shrink: 0;
}
.tp-focus-tag .name {
    color: var(--tp-gold);
    font-weight: 700;
}

/* ---- BENTO STATS (Today / Edge / MLB Match / Streak) ---- */
.tp-bento {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 28px auto 0;
    max-width: 940px;
}
.tp-bento-card {
    padding: 18px 16px 14px;
    border-radius: 16px;
    border: 1px solid var(--bl-line);
    background:
        radial-gradient(80% 60% at 50% 0%, rgba(232,193,112,0.05) 0%, transparent 65%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.008));
    text-align: center;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    transition: border-color 0.22s ease, transform 0.22s ease;
}
.tp-bento-card:hover {
    border-color: var(--bl-line-hi);
    transform: translateY(-1px);
}
.tp-bento-card.is-gold {
    border-color: var(--tp-gold-line);
    background:
        radial-gradient(80% 60% at 50% 0%, rgba(232,193,112,0.14) 0%, transparent 65%),
        linear-gradient(180deg, rgba(255,255,255,0.030), rgba(255,255,255,0.010));
}
.tp-bento-num {
    font-family: var(--tp-serif);
    font-style: italic;
    font-weight: 400;
    font-size: clamp(1.8rem, 2.6vw, 2.6rem);
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1;
}
.tp-bento-num.is-gold { color: var(--tp-gold); }
.tp-bento-num .unit {
    font-style: normal;
    font-family: var(--bl-sans);
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--bl-ink-60);
    margin-left: 4px;
    letter-spacing: 0;
}
.tp-bento-label {
    font-family: var(--bl-mono);
    font-size: 10px;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    color: var(--bl-ink-60);
    margin-top: 10px;
    font-weight: 500;
}
.tp-bento-foot {
    font-family: var(--bl-mono);
    font-size: 9px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
    margin-top: 5px;
    font-weight: 500;
}

/* ---- SECTION HEADER (replaces the .dt-cat-header look) ---- */
.tp-section-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 1rem;
    margin: 2.4rem 0 1rem;
    padding-bottom: 0.9rem;
    border-bottom: 1px solid var(--bl-line);
    position: relative;
}
.tp-section-head::after {
    content: ""; position: absolute; left: 0; bottom: -1px;
    width: 60px; height: 1px;
    background: linear-gradient(90deg, var(--tp-gold) 0%, transparent 100%);
}
.tp-section-eyebrow {
    font-family: var(--bl-mono);
    font-size: 11px;
    letter-spacing: 0.26em;
    text-transform: uppercase;
    color: var(--bl-red);
    font-weight: 600;
}
.tp-section-title {
    font-family: var(--tp-serif);
    font-style: italic;
    font-weight: 400;
    font-size: 1.6rem;
    color: var(--bl-ink-100);
    letter-spacing: -0.01em;
}
.tp-section-meta {
    font-family: var(--bl-mono);
    font-size: 10px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
    font-weight: 500;
}

/* ---- DRILL CARD POLISH ---- */
/* The bl_theme .dt-drill already inherits the new bone/red/ink
   palette via the variable cascade. We add the editorial touches
   it can't express on its own. */
.tp-shell .dt-drill {
    border-radius: 18px !important;
    transition:
        border-color 0.22s cubic-bezier(.32,.72,0,1),
        transform 0.22s cubic-bezier(.32,.72,0,1),
        box-shadow 0.22s cubic-bezier(.32,.72,0,1) !important;
}
.tp-shell .dt-drill:hover {
    border-color: var(--tp-gold-line) !important;
    transform: translateY(-1.5px) !important;
    box-shadow: 0 20px 40px -22px rgba(232,193,112,0.25) !important;
}
.tp-shell .dt-drill-num {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    color: var(--tp-gold) !important;
    font-size: 1.65rem !important;
    letter-spacing: -0.02em !important;
}
.tp-shell .dt-drill-name {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 1.4rem !important;
    letter-spacing: -0.015em !important;
    color: var(--bl-ink-100) !important;
}
.tp-shell .dt-drill-reps {
    background: rgba(232,193,112,0.08) !important;
    border-color: var(--tp-gold-line) !important;
    color: var(--tp-gold) !important;
}
.tp-shell .dt-drill.is-done {
    border-color: rgba(74,227,140,0.22) !important;
    background:
        radial-gradient(120% 100% at 100% 0%, rgba(74,227,140,0.06) 0%, transparent 60%),
        var(--bl-surface-1) !important;
}
.tp-shell .dt-drill.is-done::before {
    background: var(--tp-green) !important;
    box-shadow: 0 0 20px rgba(74,227,140,0.5) !important;
}
.tp-shell .dt-drill.is-done .dt-drill-status-pill {
    color: var(--tp-green) !important;
    background: rgba(74,227,140,0.10) !important;
    border-color: rgba(74,227,140,0.32) !important;
    box-shadow: 0 0 16px -4px rgba(74,227,140,0.25) !important;
}
/* Role chip — keep PRIMARY red, SUPPORTING bone, CHALLENGE gold. */
.tp-shell .dt-role.is-primary {
    background: rgba(230,69,48,0.10) !important;
    border-color: rgba(230,69,48,0.32) !important;
    color: var(--bl-red) !important;
}

/* ---- COACH NOTES — make it the page's signature panel ---- */
.tp-shell .dt-coach {
    border-radius: 18px !important;
    border: 1px solid var(--tp-gold-line) !important;
    background:
        radial-gradient(120% 100% at 0% 0%, rgba(232,193,112,0.08) 0%, transparent 60%),
        linear-gradient(180deg, rgba(255,255,255,0.030), rgba(255,255,255,0.010)) !important;
    padding: 1.3rem 1.4rem 1.2rem !important;
    position: relative !important;
}
.tp-shell .dt-coach::before {
    content: "";
    position: absolute; top: 0; left: 18%; right: 18%;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--tp-gold) 50%, transparent);
    opacity: 0.6;
}
.tp-shell .dt-coach-body {
    font-family: var(--tp-serif);
    font-size: 1.06rem !important;
    line-height: 1.6 !important;
    color: var(--bl-ink-80) !important;
}

/* ---- RE-TEST READINESS CARD ---- */
.tp-shell .dt-retest {
    border-radius: 18px !important;
}
.tp-shell .dt-retest-title {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 1.3rem !important;
    letter-spacing: -0.01em !important;
}

/* ---- PROGRESS RING / OVERVIEW (existing .dt-progress-card) ---- */
.tp-shell .dt-progress-card {
    border-radius: 20px !important;
    background:
        radial-gradient(120% 100% at 0% 0%, rgba(232,193,112,0.05) 0%, transparent 65%),
        var(--bl-surface-1) !important;
}
.tp-shell .dt-ring-fill {
    stroke: var(--tp-gold) !important;
    filter: drop-shadow(0 0 14px rgba(232,193,112,0.55)) !important;
}
.tp-shell .dt-ring-pct {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
}
.tp-shell .dt-progress-meta-title {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    font-size: 1.6rem !important;
}
.tp-shell .dt-stat-num.is-red { color: var(--tp-gold) !important; }

/* ---- CONSISTENCY BAR (new — 7-day completion strip) ---- */
.tp-consistency {
    margin: 1.4rem 0 1.6rem;
    padding: 1.3rem 1.4rem;
    border-radius: 18px;
    border: 1px solid var(--bl-line);
    background:
        linear-gradient(180deg, rgba(255,255,255,0.022), rgba(255,255,255,0.008));
}
.tp-consistency-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 1rem; margin-bottom: 14px;
}
.tp-consistency-eyebrow {
    font-family: var(--bl-mono);
    font-size: 10px;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    color: var(--bl-red);
    font-weight: 600;
}
.tp-consistency-title {
    font-family: var(--tp-serif);
    font-style: italic;
    font-weight: 400;
    font-size: 1.18rem;
    color: var(--bl-ink-100);
    margin-top: 4px;
    letter-spacing: -0.01em;
}
.tp-consistency-score {
    font-family: var(--tp-serif);
    font-style: italic;
    font-size: 2rem;
    color: var(--tp-gold);
    letter-spacing: -0.025em;
    line-height: 1;
}
.tp-consistency-score .unit {
    font-style: normal;
    font-family: var(--bl-sans);
    font-size: 0.92rem;
    color: var(--bl-ink-60);
    font-weight: 500;
    margin-left: 3px;
}
.tp-consistency-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
    margin-top: 6px;
}
.tp-day {
    display: flex; flex-direction: column; align-items: center;
    padding: 10px 4px 8px;
    border-radius: 10px;
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.012);
    transition: border-color 0.2s ease;
}
.tp-day.is-complete {
    border-color: var(--tp-gold-line);
    background: var(--tp-gold-soft);
}
.tp-day.is-today {
    border-color: var(--bl-red);
    box-shadow: 0 0 0 1px var(--bl-red);
}
.tp-day-dow {
    font-family: var(--bl-mono);
    font-size: 9px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bl-ink-60);
    font-weight: 500;
}
.tp-day-mark {
    margin-top: 8px;
    font-family: var(--tp-serif);
    font-style: italic;
    font-size: 1.05rem;
    color: var(--bl-ink-40);
    line-height: 1;
}
.tp-day.is-complete .tp-day-mark { color: var(--tp-gold); }
.tp-day.is-today .tp-day-mark { color: var(--bl-red); }

/* ---- RESPONSIVE ---- */
@media (max-width: 900px) {
    .tp-bento { grid-template-columns: repeat(2, 1fr); }
    .tp-section-head { flex-direction: column; align-items: flex-start; gap: 0.4rem; }
    .tp-consistency-head { flex-direction: column; gap: 0.4rem; }
}
@media (max-width: 640px) {
    .tp-display { font-size: clamp(2.1rem, 9vw, 3rem); }
    .tp-deck { font-size: 0.98rem; padding: 0 8px; }
    .tp-eyebrow { font-size: 10px; letter-spacing: 0.22em; }
    .tp-bento { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .tp-bento-card { padding: 14px 10px 10px; }
    .tp-bento-num { font-size: 1.7rem; }
    .tp-shell .dt-drill-name { font-size: 1.2rem !important; }
    .tp-shell .dt-drill-num { font-size: 1.35rem !important; }
    .tp-consistency-grid { gap: 5px; }
    .tp-day { padding: 8px 2px 6px; }
}

/* ============================================================
   TRAINING PLAN v3 — restraint + premium completion polish.

   Goals (from the v3 brief):
     · Less red. Red is reserved for PRIMARY + TODAY + one signature
       eyebrow on the hero. Every other red surface dials to a warm
       neutral or to gold.
     · Premium completion treatment. The drill card morphs visibly
       Pending → Done with CSS-only transitions (no JS — Streamlit
       doesn't let us hand-roll widgets, so we ride the existing
       checkbox + restyle around it).
     · Mastery surfacing. Lifetime completion count for the drill
       NAME (not the per-swing instance) shows on each card.
     · Reward tier visual. 1y journey reads as Bronze → Silver →
       Gold → Diamond → Legendary alongside the existing reward
       cards.
   ============================================================ */

/* ---- 1. Restraint pass: red → neutral on non-priority eyebrows. ---- */
.tp-shell .tp-eyebrow {
    color: var(--bl-ink-60) !important;       /* not red */
}
.tp-shell .tp-eyebrow .stitch {
    background: var(--bl-ink-40) !important;  /* not red */
}
/* Section heads stay neutral too — only PRIMARY chips wear red. */
.tp-shell .tp-section-eyebrow {
    color: var(--bl-ink-60) !important;
}
.tp-shell .tp-section-head::after {
    background: linear-gradient(90deg, var(--tp-gold) 0%, transparent 100%) !important;
}
/* Consistency eyebrow: also neutral. */
.tp-shell .tp-consistency-eyebrow {
    color: var(--bl-ink-60) !important;
}
/* Category priority pill (legacy): bone instead of red. */
.tp-shell .dt-cat-priority-pill {
    color: var(--bl-ink-80) !important;
    background: rgba(244,239,230,0.04) !important;
    border-color: var(--bl-line-hi) !important;
}
/* The data-hero stitch eyebrow keeps one small dose of red so the
   page still has a deliberate accent. Override only the LAST
   .tp-eyebrow on the data hero. (No reliable last-of-type without
   restructuring; instead we add a new .is-signature variant when
   the data hero is rendered.) */
.tp-shell .tp-eyebrow.is-signature {
    color: var(--bl-red) !important;
}
.tp-shell .tp-eyebrow.is-signature .stitch {
    background: var(--bl-red) !important;
    opacity: 0.85;
}

/* Soften the ambient hero radial — was gold; keep gold but reduce
   intensity so the headline reads cleaner. */
.tp-shell .tp-hero::before {
    background: radial-gradient(ellipse at center,
        rgba(232,193,112,0.07) 0%, transparent 70%) !important;
}

/* ---- 2. Bento cards: dial down the gold-card emphasis on Edge
        Score; let it earn the emphasis only when the value's high. ---- */
.tp-shell .tp-bento-card.is-gold {
    border-color: var(--bl-line-hi) !important;
    background:
        radial-gradient(80% 60% at 50% 0%, rgba(232,193,112,0.05) 0%, transparent 65%),
        linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.009)) !important;
}

/* ---- 3. Premium completion treatment. ---- */
/* The drill card itself already morphs to a green tint when .is-done.
   Add three more details:
     a. a subtle outer ring pulse on transition;
     b. a "+XP" floating chip;
     c. a checkmark glyph that scales in. */

.tp-shell .dt-drill {
    /* Make the transition snappier so the Pending → Done morph
       feels intentional rather than incidental. */
    transition:
        border-color 0.32s cubic-bezier(.32,.72,0,1),
        background 0.32s cubic-bezier(.32,.72,0,1),
        box-shadow 0.32s cubic-bezier(.32,.72,0,1),
        transform 0.22s cubic-bezier(.32,.72,0,1) !important;
}

@keyframes tp-ring-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(74,227,140,0.55); }
    70%  { box-shadow: 0 0 0 14px rgba(74,227,140,0); }
    100% { box-shadow: 0 0 0 0 rgba(74,227,140,0); }
}
@keyframes tp-xp-fly {
    0%   { opacity: 0; transform: translate(-50%, 6px) scale(0.85); }
    20%  { opacity: 1; transform: translate(-50%, 0)  scale(1.0); }
    80%  { opacity: 1; transform: translate(-50%, -10px) scale(1.0); }
    100% { opacity: 0; transform: translate(-50%, -28px) scale(0.95); }
}
.tp-shell .dt-drill.is-done {
    /* Single-shot pulse — the keyframe runs once when the .is-done
       class lands on the card after the user toggles. */
    animation: tp-ring-pulse 0.85s ease-out 1;
}
/* The +XP chip is purely decorative — sits in the bottom-right
   corner of completed drills, fading in/up so the user can see
   the reward without a custom component. */
.tp-shell .dt-drill { position: relative; }
.tp-shell .dt-drill.is-done::after {
    content: "+25 XP";
    position: absolute;
    bottom: 12px; right: 16px;
    font-family: var(--bl-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--tp-green);
    background: rgba(74,227,140,0.08);
    border: 1px solid rgba(74,227,140,0.32);
    border-radius: 999px;
    padding: 4px 9px;
    animation: tp-xp-fly 1.8s cubic-bezier(.32,.72,0,1) 1;
    animation-fill-mode: forwards;
    /* `forwards` keeps the chip's final state — the keyframe ends
       at opacity 0, so post-animation the chip is invisible. The
       chip only appears on the transition from pending → done. */
    pointer-events: none;
    z-index: 2;
}

/* ---- 4. Drill mastery chip (lifetime completion count) ---- */
.tp-mastery {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--bl-mono);
    font-size: 9.5px;
    font-weight: 600;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: var(--tp-gold);
    background: rgba(232,193,112,0.07);
    border: 1px solid rgba(232,193,112,0.28);
    border-radius: 999px;
    padding: 3px 9px;
    margin-left: 8px;
    vertical-align: middle;
}
.tp-mastery::before {
    content: "★";
    font-size: 10px;
    line-height: 1;
    color: var(--tp-gold);
}

/* Drill timestamp on completed cards — replaces the bone status
   pill text with a friendlier "✓ COMPLETED · 14:23" string. */
.tp-shell .dt-drill.is-done .dt-drill-status-pill::before {
    content: "✓ ";
    margin-right: 1px;
}

/* ---- 5. Reward tier visual (Bronze→Legendary) ----
   Existing 8 rewards in gamification.REWARDS map to tier bands by
   day_threshold. The .is-tier-* class is added in Python before
   the reward card markup; here it just colours the border + an
   optional corner tier label. */
.tp-shell .dt-reward.is-tier-bronze     { border-color: rgba(205,127,50,0.32) !important; }
.tp-shell .dt-reward.is-tier-silver     { border-color: rgba(192,192,192,0.30) !important; }
.tp-shell .dt-reward.is-tier-gold       { border-color: rgba(232,193,112,0.38) !important; }
.tp-shell .dt-reward.is-tier-diamond    { border-color: rgba(173,216,255,0.38) !important; }
.tp-shell .dt-reward.is-tier-legendary {
    border-color: rgba(230,69,48,0.42) !important;
    background:
        radial-gradient(120% 80% at 100% 0%, rgba(230,69,48,0.10) 0%, transparent 60%),
        radial-gradient(120% 80% at 0% 100%, rgba(232,193,112,0.10) 0%, transparent 60%),
        linear-gradient(180deg, rgba(255,255,255,0.030), rgba(255,255,255,0.010)) !important;
}
.tp-tier-tag {
    position: absolute;
    top: 14px; right: 14px;
    font-family: var(--bl-mono);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(0,0,0,0.30);
    border: 1px solid var(--bl-line-hi);
    color: var(--bl-ink-80);
    backdrop-filter: blur(4px);
}
.tp-tier-tag.is-tier-bronze     { color: #CD7F32; border-color: rgba(205,127,50,0.45); }
.tp-tier-tag.is-tier-silver     { color: #DCDCDC; border-color: rgba(192,192,192,0.45); }
.tp-tier-tag.is-tier-gold       { color: #E8C170; border-color: rgba(232,193,112,0.50); }
.tp-tier-tag.is-tier-diamond    { color: #ADD8FF; border-color: rgba(173,216,255,0.55); }
.tp-tier-tag.is-tier-legendary  { color: #FFB498; border-color: rgba(230,69,48,0.60); }

/* Existing .dt-reward is `position:relative` already (verified via
   the in-place CSS above), so the absolute-positioned .tp-tier-tag
   anchors to the card. */

/* ---- 6. Empty state polish ---- */
.tp-shell .dt-empty {
    border-color: var(--bl-line-hi) !important;
}

/* ---- 7. Mode pill: reduce red noise on the hero subtitle band ---- */
.tp-shell .dt-mode-pill {
    background: rgba(244,239,230,0.04) !important;
    border-color: var(--bl-line-hi) !important;
    color: var(--bl-ink-80) !important;
}
.tp-shell .dt-mode-pill-dot {
    background: var(--tp-gold) !important;
    box-shadow: 0 0 8px rgba(232,193,112,0.55) !important;
}
</style>
"""


# ============================================================
# Training Plan helpers (v4)
# ============================================================
def _trim_drills_to_focus(categories: list, max_drills: int = 4) -> list:
    """Cap the displayed drill set to the spec's 2–4 focus drills.

    Role allocation (matches `_role_for`):
      • PRIMARY    — priority-1 cat, drill 0     (always shown if present)
      • SUPPORTING — priority-1 cat, drills 1..2 (up to 2)
      • CHALLENGE  — priority-2 cat, drill 0     (at most 1)

    So priority-2 contributes at most one drill no matter how many
    headroom slots are unused — otherwise a thin priority-1 category
    would silently let three priority-2 drills render with CHALLENGE
    labels, which is internally inconsistent with the role intent.
    """
    if not categories:
        return []
    out: list = []
    remaining = max(1, int(max_drills or 0))
    cat1 = dict(categories[0])
    take1 = min(3, remaining, len(cat1.get("drills") or []))
    cat1["drills"] = list((cat1.get("drills") or [])[:take1])
    out.append(cat1)
    remaining -= take1
    if remaining > 0 and len(categories) > 1:
        cat2 = dict(categories[1])
        # Hard cap of 1 drill from priority-2 — the "optional challenge"
        # slot. Don't backfill it with multiple drills just because
        # priority-1 had headroom; those wouldn't be challenges.
        take2 = min(1, remaining, len(cat2.get("drills") or []))
        cat2["drills"] = list((cat2.get("drills") or [])[:take2])
        if cat2["drills"]:
            out.append(cat2)
    return out


def _lifetime_completions(log: dict, drill_name: str) -> int:
    """Count how many times the player completed this drill NAME PRIOR
    to today.

    Events live inside `log["drills"]["_completion_events"]` (the same
    `_swing_meta`-style piggyback `player_storage` already uses, so
    persistence costs zero schema migration). Today's completion is
    deliberately excluded so the mastery chip on the card doesn't
    bump in lock-step with the player ticking the box — the +25 XP
    pulse is the instant feedback; the "Mastered N×" chip is the
    slower, more meaningful retrospective.

    Returns 0 for unknown drills, missing events list, or unparseable
    timestamps — safe to call before the log has any history.
    """
    events = ((log or {}).get("drills") or {}).get("_completion_events") or []
    target = (drill_name or "").strip().lower()
    if not target:
        return 0
    try:
        from datetime import datetime as _dt
        today = _dt.now().date()
    except Exception:
        today = None
    n = 0
    for e in events:
        if (e.get("drill_name", "") or "").strip().lower() != target:
            continue
        # Exclude today's events so the chip never updates in the same
        # render as the +25 XP pulse.
        if today is not None:
            iso = (e.get("completed_at") or "").strip()
            try:
                if "T" in iso:
                    when = _dt.fromisoformat(iso.replace("Z", "")).date()
                else:
                    when = _dt.fromisoformat(iso[:10]).date()
                if when >= today:
                    continue
            except Exception:
                # Unparseable timestamp — count it (better to over- than
                # under-credit on legacy data).
                pass
        n += 1
    return n


def _tier_for_day_threshold(day_threshold: int) -> str:
    """Map a reward's day_threshold to its tier (bronze/silver/gold/diamond/legendary).

    Used by the rewards roadmap to render the existing 8 milestones
    as an aspirational ladder without changing their content. The
    bands mirror the brief's "Bronze → Silver → Gold → Diamond →
    Legendary" arc:
        bronze:    < 14   days  (7d badge)
        silver:    14–30  days  (14d patch, 30d player card)
        gold:      31–90  days  (60d progress report, 90d locker title)
        diamond:   91–270 days  (180d hoodie, 270d lifetime discount)
        legendary: 271+   days  (365d Hall of Fame)
    """
    try:
        d = int(day_threshold or 0)
    except Exception:
        return "bronze"
    if d < 14:
        return "bronze"
    if d <= 30:
        return "silver"
    if d <= 90:
        return "gold"
    if d <= 270:
        return "diamond"
    return "legendary"


def _role_for(category_idx: int, drill_idx: int) -> tuple[str, str]:
    """Map a (category, drill) index to a role label + CSS class.

    Category 0 drill 0 → PRIMARY (the focus drill of the cycle)
    Category 0 drills 1,2 → SUPPORTING
    Category 1 drills → CHALLENGE (everything past the priority-1 set)
    """
    if category_idx == 0 and drill_idx == 0:
        return ("PRIMARY", "is-primary")
    if category_idx == 0:
        return ("SUPPORTING", "is-supporting")
    return ("CHALLENGE", "is-challenge")


# ============================================================
# Training Plan v2 — editorial hero + consistency strip
# ============================================================
def _safe_pct(num: int, den: int) -> int:
    """Return an integer percent, clamped 0..100, safe for zero divisors."""
    if not den:
        return 0
    return max(0, min(100, int(round(num / den * 100))))


def _hero_metrics(saved_swing: dict, gm_state: dict | None,
                  total_completed: int, total_drills: int) -> dict:
    """Compute the four bento numbers + the dynamic display headline.

    Falls back safely for any field that isn't computable (new account,
    missing reference comp, etc.) — the bento always renders four
    cards, just with a `—` placeholder where there's no real value.
    """
    # ---- Edge Score (dashboard_v3 composition) ----
    edge_score: str | int = "—"
    try:
        from dashboard_v3 import _compose_edge_score
        v = _compose_edge_score(saved_swing or {})
        if isinstance(v, (int, float)) and v > 0:
            edge_score = int(round(v))
    except Exception:
        pass

    # ---- MLB match % (the underlying similarity calc lives in dashboard) ----
    match_pct: str | int = "—"
    ref_name = ""
    try:
        from dashboard import _similarity_pct, _pretty_player_name
        sim = _similarity_pct(saved_swing or {}) or 0
        if sim:
            match_pct = int(round(float(sim)))
        ref_slug = (saved_swing or {}).get("picked_slug") or \
                   (saved_swing or {}).get("reference_name") or ""
        if ref_slug:
            try:
                ref_name = _pretty_player_name(ref_slug) or ""
            except Exception:
                ref_name = ""
    except Exception:
        pass

    # ---- Streak (from gamification state) ----
    streak_days: int = 0
    if isinstance(gm_state, dict):
        try:
            streak_days = int(gm_state.get("current_streak_days") or 0)
        except Exception:
            streak_days = 0

    today_pct = _safe_pct(total_completed, total_drills)

    # ---- Display headline ----
    # The primary issue title is the priority-1 category's display name
    # from the analyzer-built drill_plan. v3 uses it as a small "focus
    # tag" under the headline rather than awkwardly forcing it into the
    # sentence ("Master your Sharpen Timing & Quickness" → out).
    plan = (saved_swing or {}).get("drill_plan") or {}
    cats = plan.get("categories") or []
    primary_issue = ""
    if cats:
        primary_issue = (cats[0].get("title") or "").strip()
    if not primary_issue:
        primary_issue = "your swing"

    # ---- How recent is this swing? ----
    # Drives the "fresh-analysis" headline variant in
    # `_hero_copy_variant`. Defaults to 0 (treat-as-fresh) on parse
    # failure so the worst case is the most action-oriented copy.
    swing_days_old = 0
    try:
        from datetime import datetime as _dt
        iso = ((saved_swing or {}).get("timestamp")
               or (saved_swing or {}).get("date") or "").strip()
        if iso:
            if "T" in iso:
                ts = _dt.fromisoformat(iso.replace("Z", ""))
            else:
                ts = _dt.fromisoformat(iso[:10])
            swing_days_old = max(0, (_dt.now() - ts).days)
    except Exception:
        swing_days_old = 0

    return {
        "today_pct": today_pct,
        "edge_score": edge_score,
        "match_pct": match_pct,
        "streak_days": streak_days,
        "primary_issue": primary_issue,
        "ref_name": ref_name,
        "total_drills": int(total_drills or 0),
        "total_completed": int(total_completed or 0),
        "swing_days_old": int(swing_days_old or 0),
    }


def _build_hero_brand_html(
    *,
    headline: str = "Today's <span class=\"ital\">Development</span> Plan.",
    eyebrow: str = "Training Plan",
    deck: str = ("Focus on the highest-impact drills from your most "
                 "recent swing analysis. Small improvements compound."),
) -> str:
    """Render the always-on editorial brand hero — eyebrow + serif italic
    display + deck. No bento; pure identity. Branch-agnostic (renders
    the same for unauth / no-Pro / no-swing).

    The data-driven bento + consistency strip are rendered SEPARATELY
    by `_build_data_hero_html` only when we have a real swing record.
    """
    return (
        '<section class="tp-hero">'
        '<div class="tp-eyebrow">'
        f'<span class="stitch"></span>{eyebrow}'
        '<span class="stitch"></span>'
        '</div>'
        f'<h1 class="tp-display">{headline}</h1>'
        f'<p class="tp-deck">{deck}</p>'
        '</section>'
    )


def _hero_copy_variant(
    *,
    today_pct: int,
    total_drills: int,
    total_completed: int,
    streak_days: int,
    swing_days_old: int,
) -> tuple[str, str]:
    """Pick a headline + deck that reflects the player's current state.

    The previous "Master your <issue>" pattern broke on category names
    like "Sharpen Timing & Quickness" (read as "Master your Sharpen
    Timing & Quickness"). We swap to a small set of curated templates
    selected by state, so the line is always idiomatic + true.

    Returns (headline_html, deck_text).
    """
    # All-done — celebrate, then point to the next move.
    if total_drills > 0 and total_completed >= total_drills:
        return (
            "Today's <span class=\"ital\">work</span> is done.",
            ("All prescribed drills complete. Rest, then upload a fresh "
             "swing to see how today's reps moved the needle."),
        )

    # Brand new swing (< 24h) → fresh-priorities framing.
    if swing_days_old <= 0 and total_drills > 0:
        return (
            "Your <span class=\"ital\">highest-leverage</span> work.",
            ("Fresh analysis, two new priorities. The drills below are "
             "the most impactful changes available to you right now."),
        )

    # Hot streak ≥ 7 days — protect it, name it.
    if streak_days >= 7:
        return (
            f"Day <span class=\"ital\">{streak_days}</span>. Stay sharp.",
            ("You're building real momentum. Today's drills protect the "
             "streak and keep compound improvements stacking."),
        )

    # Partial progress today.
    if total_drills > 0 and total_completed > 0:
        remaining = total_drills - total_completed
        plural = "drill" if remaining == 1 else "drills"
        return (
            f"<span class=\"ital\">{remaining}</span> to go.",
            (f"You've checked {total_completed} off the list. "
             f"Finish the remaining {remaining} {plural} to bank "
             "today's work."),
        )

    # Default — neutral, action-oriented.
    return (
        "What <span class=\"ital\">moves</span> the needle today.",
        ("Focus on the two mechanical priorities most likely to "
         "improve your swing. Complete today's drills and upload "
         "again to measure progress."),
    )


def _build_data_hero_html(metrics: dict, swing_date: str) -> str:
    """Editorial hero with state-aware headline + bento.

    Only called when we have a real `saved_swing`. The headline now
    adapts to the player's current state (fresh swing / partial / done
    / streak) rather than forcing "Master your <issue>" into every
    sentence regardless of fit.
    """
    ref_name = _html.escape(metrics.get("ref_name") or "")
    date_str = _html.escape(swing_date or "your most recent swing")
    today_pct = int(metrics.get("today_pct") or 0)
    edge = metrics.get("edge_score", "—")
    mlb  = metrics.get("match_pct", "—")
    streak = int(metrics.get("streak_days") or 0)
    total_drills = int(metrics.get("total_drills") or 0)
    total_completed = int(metrics.get("total_completed") or 0)
    swing_days_old = int(metrics.get("swing_days_old") or 0)
    primary_issue = _html.escape(metrics.get("primary_issue") or "")

    headline, deck = _hero_copy_variant(
        today_pct=today_pct,
        total_drills=total_drills,
        total_completed=total_completed,
        streak_days=streak,
        swing_days_old=swing_days_old,
    )

    # The deck always references the source-of-truth — swing date +
    # optional reference name — even when the headline is state-driven.
    if ref_name:
        deck_postscript = (
            f' Drawn from your <span class="em">{date_str}</span> swing '
            f'— measured against <span class="gold">{ref_name}</span>.'
        )
    else:
        deck_postscript = (
            f' Drawn from your <span class="em">{date_str}</span> swing.'
        )
    deck = deck + deck_postscript

    # If we have a primary issue identified, list it as a small
    # "focus tag" below the headline so the analyzer's diagnosis is
    # never invisible — just no longer awkwardly hard-coded into the
    # sentence shape.
    focus_html = (
        f'<div class="tp-focus-tag">'
        f'<span class="dot"></span>'
        f'Primary focus · <span class="name">{primary_issue}</span>'
        f'</div>'
        if primary_issue and primary_issue != "your swing" else ""
    )

    edge_num_html = (
        f'<span class="tp-bento-num is-gold">{edge}</span>'
        if isinstance(edge, int) else
        f'<span class="tp-bento-num">{edge}</span>'
    )
    mlb_num_html = (
        f'<span class="tp-bento-num">{mlb}<span class="unit">%</span></span>'
        if isinstance(mlb, int) else
        f'<span class="tp-bento-num">{mlb}</span>'
    )
    today_cls = "is-gold" if today_pct >= 67 else ""
    streak_cls = "is-gold" if streak >= 3 else ""

    return (
        '<section class="tp-hero">'
        # The signature red eyebrow — the only red eyebrow on the page,
        # so it reads as deliberate rather than noise.
        '<div class="tp-eyebrow is-signature">'
        '<span class="stitch"></span>Training Plan · Today\'s Focus'
        '<span class="stitch"></span>'
        '</div>'
        f'<h1 class="tp-display">{headline}</h1>'
        f'{focus_html}'
        f'<p class="tp-deck">{deck}</p>'
        '<div class="tp-bento">'
        '<div class="tp-bento-card">'
        f'<div class="tp-bento-num {today_cls}">{today_pct}<span class="unit">%</span></div>'
        '<div class="tp-bento-label">Today</div>'
        '<div class="tp-bento-foot">Completed</div>'
        '</div>'
        '<div class="tp-bento-card is-gold">'
        f'{edge_num_html}'
        '<div class="tp-bento-label">Edge Score</div>'
        '<div class="tp-bento-foot">Latest Swing</div>'
        '</div>'
        '<div class="tp-bento-card">'
        f'{mlb_num_html}'
        '<div class="tp-bento-label">MLB Match</div>'
        f'<div class="tp-bento-foot">{ref_name or "Reference"}</div>'
        '</div>'
        '<div class="tp-bento-card">'
        f'<div class="tp-bento-num {streak_cls}">{streak}<span class="unit">d</span></div>'
        '<div class="tp-bento-label">Streak</div>'
        '<div class="tp-bento-foot">Current</div>'
        '</div>'
        '</div>'
        '</section>'
    )


def _build_consistency_html(history: list, today_pct: int) -> str:
    """Render the 7-day consistency strip + a single 'consistency score'.

    history is the player's swing_history list. The score is the number
    of unique days in the past 7 with a swing analyzed (capped 0..100%).
    Each day is a small card: marked complete if a swing was uploaded
    that day, marked today if it's, well, today.
    """
    try:
        from datetime import datetime, timedelta
        today = datetime.now().date()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]  # oldest → newest
        # Parse swing dates to a set of date objects.
        swing_days: set = set()
        for rec in (history or []):
            iso = (rec.get("timestamp") or rec.get("date") or "").strip()
            if not iso:
                continue
            try:
                # Handle both ISO timestamps and YYYY-MM-DD-only forms.
                from datetime import datetime as _dt
                if "T" in iso:
                    swing_days.add(_dt.fromisoformat(iso.replace("Z", "")).date())
                else:
                    swing_days.add(_dt.fromisoformat(iso[:10]).date())
            except Exception:
                continue
        completed_count = sum(1 for d in days if d in swing_days)
        consistency_pct = _safe_pct(completed_count, 7)

        dow_labels = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        cells = []
        for d in days:
            is_done = d in swing_days
            is_today = (d == today)
            cls = "tp-day"
            if is_done:
                cls += " is-complete"
            if is_today:
                cls += " is-today"
            mark = "●" if is_done else "○"
            cells.append(
                f'<div class="{cls}">'
                f'<div class="tp-day-dow">{dow_labels[d.weekday()]}</div>'
                f'<div class="tp-day-mark">{mark}</div>'
                f'</div>'
            )
        grid_html = "".join(cells)
    except Exception:
        # Empty/broken history → render an "—" state instead of crashing.
        grid_html = ""
        consistency_pct = 0

    return (
        '<div class="tp-consistency">'
        '<div class="tp-consistency-head">'
        '<div>'
        '<div class="tp-consistency-eyebrow">Consistency · 7 days</div>'
        '<div class="tp-consistency-title">Showing up is the work.</div>'
        '</div>'
        f'<div class="tp-consistency-score">{consistency_pct}<span class="unit">%</span></div>'
        '</div>'
        f'<div class="tp-consistency-grid">{grid_html}</div>'
        '</div>'
    )


# ============================================================
#                       HELPERS
# ============================================================
def _latest_swing_with_drill_plan(player_id: str) -> dict | None:
    """Return the most recent swing that has a drill plan, or None."""
    history = load_swing_history(player_id)
    for record in reversed(history):
        drill_plan = record.get("drill_plan") or {}
        if drill_plan.get("categories"):
            return record
    return None


def _progress_tag(pct: float) -> str:
    if pct >= 0.85:
        return "LOCKED IN"
    if pct >= 0.5:
        return "ON PACE"
    if pct > 0:
        return "WARMING UP"
    return "GET STARTED"


def _render_progress_card(total_completed: int, total_drills: int,
                          swing_date: str, player_name: str):
    pct = total_completed / total_drills if total_drills else 0.0
    pct_int = int(round(pct * 100))
    circumference = 2 * 3.14159 * 70  # r=70
    dash_offset = circumference * (1 - pct)
    tag = _progress_tag(pct)
    remaining = max(0, total_drills - total_completed)

    html = textwrap.dedent(f"""
    <div class="dt-progress-card">
      <div class="dt-ring">
        <svg viewBox="0 0 160 160">
          <circle class="dt-ring-track" cx="80" cy="80" r="70"></circle>
          <circle class="dt-ring-fill"  cx="80" cy="80" r="70"
                  stroke-dasharray="{circumference:.2f}"
                  stroke-dashoffset="{dash_offset:.2f}"></circle>
        </svg>
        <div class="dt-ring-center">
          <div class="dt-ring-pct">{pct_int}<span class="dt-ring-pct-sym">%</span></div>
          <div class="dt-ring-tag">{tag}</div>
        </div>
      </div>
      <div>
        <div class="dt-progress-meta-eyebrow">SESSION PROGRESS</div>
        <div class="dt-progress-meta-title">Training plan for {player_name}</div>
        <div class="dt-progress-meta-line">
          Built from your latest report on
          <strong style="color:var(--bl-ink-100);">{swing_date}</strong>.
          Check off drills as you complete them — progress saves automatically.
        </div>
        <div class="dt-stat-row">
          <div class="dt-stat-item">
            <div class="dt-stat-num is-red">{total_completed}</div>
            <div class="dt-stat-label">COMPLETED</div>
          </div>
          <div class="dt-stat-item">
            <div class="dt-stat-num">{remaining}</div>
            <div class="dt-stat-label">REMAINING</div>
          </div>
          <div class="dt-stat-item">
            <div class="dt-stat-num">{total_drills}</div>
            <div class="dt-stat-label">TOTAL DRILLS</div>
          </div>
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
#                   GAMIFICATION RENDERERS
# ============================================================
def _render_level_card(state: dict) -> None:
    """Big hero block: current level, XP pill, XP-to-next-level bar."""
    lp = state.get("level_progress") or {}
    current = lp.get("level") or {}
    nxt = lp.get("next")
    pct = float(lp.get("pct") or 0.0)
    pct_width = max(2.0, min(100.0, pct * 100.0))
    xp_total = int(lp.get("xp_total") or 0)

    if nxt:
        next_line = (
            f'<span class="dt-xp-foot-next">'
            f'{int(lp.get("xp_needed_for_next") or 0)} XP to {_html.escape(nxt["name"])}'
            f'</span>'
        )
    else:
        next_line = '<span class="dt-xp-foot-next">MAX LEVEL — LAB LEGEND</span>'

    card = textwrap.dedent(f"""
    <div class="dt-level-card">
      <div class="dt-level-row">
        <div style="flex:1; min-width:220px;">
          <div class="dt-level-eyebrow">CURRENT LEVEL</div>
          <div class="dt-level-name">{_html.escape(current.get("name", "Rookie"))}</div>
          <div class="dt-level-tagline">{_html.escape(current.get("tagline", ""))}</div>
        </div>
        <div class="dt-xp-pill">
          <span class="dt-xp-num">{xp_total:,}</span>&nbsp;XP TOTAL
        </div>
      </div>
      <div class="dt-xp-bar-wrap">
        <div class="dt-xp-bar">
          <div class="dt-xp-bar-fill" style="width:{pct_width:.1f}%;"></div>
        </div>
        <div class="dt-xp-bar-foot">
          <span>LEVEL PROGRESS · {int(pct * 100)}%</span>
          {next_line}
        </div>
      </div>
    </div>
    """).strip()
    st.markdown(card, unsafe_allow_html=True)


def _render_stat_strip(state: dict) -> None:
    """Five at-a-glance pods: current streak, longest, swings, drills, PB."""
    pods = [
        (state.get("current_streak_days", 0), "DAY STREAK", True),
        (state.get("longest_streak_days", 0), "LONGEST STREAK", False),
        (state.get("total_swings", 0),        "SWINGS LOGGED", False),
        (state.get("total_drills_completed", 0), "DRILLS DONE", False),
        (state.get("best_score", 0),          "BEST SCORE",    False),
    ]
    parts = ['<div class="dt-stat-strip">']
    for num, label, is_red in pods:
        cls = "dt-stat-pod-num is-red" if is_red else "dt-stat-pod-num"
        parts.append(
            f'<div class="dt-stat-pod">'
            f'<div class="{cls}">{int(num or 0)}</div>'
            f'<div class="dt-stat-pod-label">{label}</div>'
            f'</div>'
        )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_motivation_strip(state: dict) -> None:
    """Up to 3 motivational lines as red/neutral pills."""
    msgs = state.get("motivational_messages") or []
    if not msgs:
        return
    parts = ['<div class="dt-motivate-strip">']
    for i, m in enumerate(msgs):
        cls = "dt-motivate-chip is-red" if i == 0 else "dt-motivate-chip"
        parts.append(f'<div class="{cls}">{_html.escape(m)}</div>')
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _section_header(eyebrow: str, title: str, count_text: str = "") -> str:
    count_html = (
        f'<span class="dt-gm-section-count">{_html.escape(count_text)}</span>'
        if count_text else ''
    )
    return (
        f'<div class="dt-gm-section-header">'
        f'<span class="dt-gm-section-eyebrow">{_html.escape(eyebrow)}</span>'
        f'<span class="dt-gm-section-title">{_html.escape(title)}</span>'
        f'{count_html}'
        f'</div>'
    )


def _achievement_progress(state: dict, ach: dict) -> int:
    """Return integer percent progress 0..100 toward this achievement."""
    from gamification import _metric_for_category
    metric = _metric_for_category(state, ach.get("category"))
    target = max(1, int(ach.get("target") or 1))
    return max(0, min(100, int(round((metric / target) * 100))))


def _render_achievements(state: dict, persisted: dict) -> None:
    """Grid of all 19 achievements with locked/unlocked styling."""
    earned = set(state.get("achievements_earned") or [])
    a_dates = persisted.get("achievements_unlocked") or {}
    count_text = f"{len(earned)} / {len(ACHIEVEMENTS)} EARNED"

    st.markdown(
        _section_header("MILESTONES", "Achievements", count_text),
        unsafe_allow_html=True,
    )

    parts = ['<div class="dt-ach-grid">']
    for a in ACHIEVEMENTS:
        unlocked = a["id"] in earned
        cls = "dt-ach is-unlocked" if unlocked else "dt-ach is-locked"
        # Badge glyph — tiered icons by category for at-a-glance recognition.
        icon = {
            "swing": "◎",
            "drill": "◇",
            "improvement": "▲",
            "score": "★",
            "streak": "♢",
        }.get(a.get("category"), "•")

        if unlocked:
            date_str = a_dates.get(a["id"], "")
            foot = f"UNLOCKED · {_html.escape(date_str)}" if date_str else "UNLOCKED"
            progress_html = ""
        else:
            pct = _achievement_progress(state, a)
            foot = f"LOCKED · {pct}% PROGRESS"
            progress_html = (
                f'<div class="dt-ach-progress">'
                f'<div class="dt-ach-progress-fill" style="width:{pct}%;"></div>'
                f'</div>'
            )

        parts.append(
            f'<div class="{cls}">'
            f'<div class="dt-ach-badge">{icon}</div>'
            f'<div class="dt-ach-title">{_html.escape(a["title"])}</div>'
            f'<div class="dt-ach-desc">{_html.escape(a["description"])}</div>'
            f'<div class="dt-ach-foot">{foot}</div>'
            f'{progress_html}'
            f'</div>'
        )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_rewards(state: dict, persisted: dict) -> None:
    """
    Premium rewards roadmap: 8 milestones, per-category type badges,
    and emphasis treatments for the 180-day Hoodie and 365-day Hall
    of Fame. Chronological top-to-bottom.
    """
    earned = set(state.get("rewards_earned") or [])
    r_dates = persisted.get("rewards_unlocked") or {}
    longest = int(state.get("longest_streak_days") or 0)
    count_text = f"{len(earned)} / {len(REWARDS)} UNLOCKED"

    st.markdown(
        _section_header("REWARDS ROADMAP", "Earned through consistency", count_text),
        unsafe_allow_html=True,
    )

    parts = ['<div class="dt-reward-grid">']
    for r in REWARDS:
        unlocked = r["id"] in earned
        rid = r.get("id", "")
        kind = (r.get("kind") or "").lower()

        # Base card class + per-reward emphasis hooks.
        # v3: each reward also wears a tier class (bronze/silver/gold/
        # diamond/legendary) driven by `day_threshold`, so the
        # rewards roadmap reads as a single ladder rather than 8
        # disconnected milestones. The tier visuals are scoped to
        # `.tp-shell .dt-reward.is-tier-*` in _DT_LOCAL_CSS.
        tier = _tier_for_day_threshold(r.get("day_threshold"))
        classes = ["dt-reward", f"is-tier-{tier}"]
        if unlocked:
            classes.append("is-unlocked")
        if rid == "r_hoodie":
            classes.append("is-hoodie")
        elif rid == "r_hall_of_fame":
            classes.append("is-hof")
        card_cls = " ".join(classes)
        tier_tag_html = (
            f'<div class="tp-tier-tag is-tier-{tier}">{tier.upper()}</div>'
        )

        kind_cls = f"dt-reward-kind is-{kind}" if kind else "dt-reward-kind"
        kind_label = kind.upper() if kind else "REWARD"

        if unlocked:
            date_str = r_dates.get(rid, "")
            status_html = (
                f'<div class="dt-reward-status">UNLOCKED \u00b7 {_html.escape(date_str)}</div>'
                if date_str else
                '<div class="dt-reward-status">UNLOCKED</div>'
            )
        else:
            days_left = max(0, int(r["day_threshold"]) - longest)
            status_html = (
                f'<div class="dt-reward-status">{days_left} DAY'
                f'{"S" if days_left != 1 else ""} TO GO</div>'
            )

        parts.append(
            f'<div class="{card_cls}">'
            f'{tier_tag_html}'
            f'<div class="dt-reward-day">'
            f'<div class="dt-reward-day-num">{int(r["day_threshold"])}</div>'
            f'<div class="dt-reward-day-lbl">DAYS</div>'
            f'</div>'
            f'<div class="dt-reward-body">'
            f'<div class="dt-reward-title">{_html.escape(r["title"])}</div>'
            f'<div class="dt-reward-desc">{_html.escape(r["description"])}</div>'
            f'<div class="dt-reward-meta-row">'
            f'<span class="{kind_cls}">{_html.escape(kind_label)}</span>'
            f'</div>'
            f'</div>'
            f'{status_html}'
            f'</div>'
        )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_empty_state(title: str, sub: str, icon: str = "◇"):
    html = textwrap.dedent(f"""
    <div class="dt-empty">
      <div class="dt-empty-icon">{icon}</div>
      <div class="dt-empty-title">{title}</div>
      <div class="dt-empty-sub">{sub}</div>
    </div>
    """).strip()
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
#                         MAIN
# ============================================================
def render_development_tracker():
    inject_global_theme()
    # Unified Edge masthead — the single shared top nav across every
    # page (Drills tab active). Replaces the old bespoke
    # "← Back to Dashboard" row so the header is identical everywhere.
    render_edge_masthead(
        st.session_state.get("user") or {}, active_page="development_tracker"
    )
    st.markdown(_DT_LOCAL_CSS, unsafe_allow_html=True)
    # `.tp-shell` is the editorial overlay wrapper — re-declares the
    # bl_theme tokens on .dt-* selectors so the whole page repaints in
    # the dashboard_v3 editorial language (bone/gold/red + Instrument
    # Serif italic) with one cascade hop. We co-class with `.bl-page`
    # on the SAME div so the existing single `</div>` closes in every
    # return branch close both rules — no double-nesting bookkeeping.
    st.markdown(
        '<div class="tp-shell bl-page">',
        unsafe_allow_html=True,
    )
    # The new editorial brand hero — eyebrow + serif italic display +
    # deck. Always shown at the top, regardless of branch (unauth, no
    # Pro, no swing, full). The data-driven version with bento numbers
    # is rendered for the has-data branch FURTHER DOWN, replacing the
    # generic deck text. The v1 .dt-hero block is hidden by CSS so the
    # two never double up.
    st.markdown(_build_hero_brand_html(), unsafe_allow_html=True)

    # ---- Auth check ----
    user = st.session_state.get("user")
    if not user:
        _render_empty_state(
            title="Please sign in to view your Training Plan.",
            sub="Your training plan is tied to your BarrelLabs account so progress can sync across devices.",
            icon="◇",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ---- Pro entitlement gate ----
    # The Development Tracker — drills, streaks, XP, achievements, the
    # rewards roadmap — is a Pro-only feature. Free users get a paywall
    # card with a clear upgrade path (or a beta-code hint).
    _plan_snapshot = load_my_plan()
    _dt_check = can_access_development_tracker(_plan_snapshot)
    if not _dt_check.allowed:
        st.markdown("""
<div style="
    margin: 1rem 0 0.5rem 0;
    padding: 1.6rem 1.7rem;
    border-radius: 16px;
    border: 1px solid rgba(220,38,38,0.35);
    background:
      radial-gradient(120% 80% at 100% 0%, rgba(220,38,38,0.10), transparent 60%),
      linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.005));
">
  <div style="
      display: inline-block;
      padding: 0.22rem 0.7rem;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #FF3B30;
      background: rgba(255,59,48,0.14);
      border: 1px solid rgba(255,59,48,0.35);
  ">Pro feature</div>
  <div style="font-size: 1.55rem; font-weight: 800; color: #fafafa; margin-top: 0.6rem; letter-spacing: -0.01em;">
    The Training Plan is Pro-only.
  </div>
  <div style="color: #d4d4d4; line-height: 1.6; margin-top: 0.55rem; max-width: 60ch;">
    Upgrade to <strong style="color:#fafafa;">Solo Pro</strong> to unlock:
    your personalized drill plan with reps tracked across sessions,
    streaks and XP, the full Achievements grid, and the Rewards
    Roadmap — including the limited-edition BarrelLabs hoodie at 180 days
    and Hall of Fame status at 365.
  </div>
  <div style="color: #a3a3a3; font-size: 0.86rem; margin-top: 0.8rem;">
    Have a beta code? Redeem it from <em>Account Settings → Subscription</em>
    to unlock the full app for 30 days.
  </div>
</div>
""", unsafe_allow_html=True)
        _dt_up_l, _dt_up_r = st.columns([1, 1])
        if _dt_up_l.button("See plans & upgrade", type="primary",
                           width="stretch", key="dt_paywall_upgrade"):
            st.session_state["page"] = "pricing"
            st.rerun()
        if _dt_up_r.button("Back to Dashboard", width="stretch",
                           key="dt_paywall_back"):
            st.session_state["page"] = "dashboard"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    player_id = user.get("id") or user.get("slug")
    player_name = user.get("name") or "Player"

    # ---- Gamification: level / XP / streak / achievements / rewards ----
    # Derive fresh state from raw history + per-swing meta + persisted
    # streak/unlock dates. Failures fall back silently so the rest of the
    # tracker still renders.
    try:
        gm_history   = load_swing_history(player_id)
        gm_meta_map  = load_all_swing_meta(player_id)
        gm_persisted = load_player_progress(player_id)
        gm_state     = compute_player_state(
            history=gm_history,
            drill_meta_map=gm_meta_map,
            persisted=gm_persisted,
        )
        # compute_player_state stamps any newly-earned achievement/reward
        # dates onto the persisted dict — write them back if anything new
        # appeared so they survive across sessions.
        new_persisted = gm_state.get("persisted") or {}
        if (
            new_persisted.get("achievements_unlocked") != gm_persisted.get("achievements_unlocked")
            or new_persisted.get("rewards_unlocked")  != gm_persisted.get("rewards_unlocked")
        ):
            save_player_progress(player_id, new_persisted)
            gm_persisted = new_persisted

        _render_level_card(gm_state)
        _render_stat_strip(gm_state)
        _render_motivation_strip(gm_state)
    except Exception:
        gm_state = None
        gm_persisted = None

    saved_swing = _latest_swing_with_drill_plan(player_id)
    if not saved_swing:
        _render_empty_state(
            title="Upload your first swing to generate your Training Plan.",
            sub="Once you have a swing report, your personalized drill "
                "plan — built from your highest-priority issues — will "
                "appear here automatically.",
            icon="↗",
        )
        # Even without a drill plan, show the milestones + rewards roadmap so
        # brand-new users can see what they're working toward.
        if gm_state is not None and gm_persisted is not None:
            try:
                _render_achievements(gm_state, gm_persisted)
                _render_rewards(gm_state, gm_persisted)
            except Exception:
                pass
        st.markdown('</div>', unsafe_allow_html=True)
        return

    drill_plan = saved_swing.get("drill_plan") or {}
    # Cap to the spec's 2–4 daily focus drills (1 primary + 2 supporting
    # + optional 1 challenge). The full per-category drill list is still
    # available in the swing report itself; here we want the daily plan,
    # not the encyclopedia.
    categories = _trim_drills_to_focus(
        drill_plan.get("categories", []),
        max_drills=4,
    )
    weekly_guide = drill_plan.get("weekly_guide") or []
    swing_date = saved_swing.get("date", "Unknown date")

    log = load_training_log(player_id)
    drill_log = log["drills"]

    # ---- First pass: compute current totals so the progress card matches reality ----
    total_completed = 0
    total_drills = 0
    drill_states = {}
    for category in categories:
        for drill in category.get("drills", []):
            total_drills += 1
            drill_id = f"{category.get('title','')}::{drill.get('name','')}"
            saved = drill_log.get(drill_id, {})
            done_key = f"done__{player_id}__{drill_id}"
            # Read from session_state if user just toggled, else from saved log.
            current_done = st.session_state.get(done_key, bool(saved.get("completed")))
            drill_states[drill_id] = current_done
            if current_done:
                total_completed += 1

    # ---- Editorial hero (data-driven) + 7-day consistency strip ----
    # These come AFTER drill totals are computed (so the bento can show
    # the live today_pct) and BEFORE the existing progress ring + drill
    # cards, so the page reads top-down as: identity → today's numbers
    # → consistency → ring → coach notes → drill cards → re-test → notes.
    try:
        hero_metrics = _hero_metrics(
            saved_swing=saved_swing,
            gm_state=gm_state,
            total_completed=total_completed,
            total_drills=total_drills,
        )
        st.markdown(
            _build_data_hero_html(hero_metrics, swing_date),
            unsafe_allow_html=True,
        )
        st.markdown(
            _build_consistency_html(gm_history or [], hero_metrics["today_pct"]),
            unsafe_allow_html=True,
        )
    except Exception:
        # Hero is decorative — never let a fallback failure block the
        # drills the user actually came here to do.
        pass

    _render_progress_card(total_completed, total_drills, swing_date, player_name)

    # ---- Categories + drills ----
    dirty = False
    drill_counter = 0
    for cat_idx, category in enumerate(categories, start=1):
        cat_title = category.get("title", "Drills")
        cat_priority = category.get("priority", cat_idx)
        cat_drills = category.get("drills", [])
        cat_why = category.get("why_it_matters") or ""

        cat_header = textwrap.dedent(f"""
        <div class="dt-cat-header">
          <span class="dt-cat-priority-pill">Priority {cat_priority}</span>
          <span class="dt-cat-title">{cat_title}</span>
          <span class="dt-cat-count">{len(cat_drills)} DRILL{'S' if len(cat_drills) != 1 else ''}</span>
        </div>
        """).strip()
        st.markdown(cat_header, unsafe_allow_html=True)

        # ---- Coach notes ----
        # The build_drill_plan output ships a `why_it_matters` paragraph
        # per category — the analyzer's plain-language explanation of
        # why this focus area moves the swing. Surface it here so the
        # Training Plan has the "why," not just the "what."
        if cat_why:
            coach_html = (
                f'<div class="dt-coach">'
                f'<div class="dt-coach-eyebrow">Coach Notes</div>'
                f'<div class="dt-coach-body">{_html.escape(cat_why)}</div>'
                f'</div>'
            )
            st.markdown(coach_html, unsafe_allow_html=True)

        for drill_idx, drill in enumerate(cat_drills):
            drill_counter += 1
            drill_id = f"{cat_title}::{drill.get('name','')}"
            saved = drill_log.get(drill_id, {})
            done_key = f"done__{player_id}__{drill_id}"
            reps_key = f"reps__{player_id}__{drill_id}"

            is_done = drill_states.get(drill_id, False)
            done_cls = "is-done" if is_done else ""
            status_text = "✓ COMPLETE" if is_done else "○ PENDING"

            # Drill card header (HTML only, no interactive widgets here)
            name = drill.get("name", "Drill")
            reps = drill.get("reps", "")
            how = drill.get("how", "")
            num_label = f"{drill_counter:02d}"

            # Spec roles: priority-1 first drill is PRIMARY, next two
            # are SUPPORTING, anything in priority-2 is CHALLENGE.
            role_label, role_cls = _role_for(cat_idx - 1, drill_idx)
            role_chip = f'<span class="dt-role {role_cls}">{role_label}</span>'

            # v3 mastery chip: reward earned reps. Threshold ≥ 3 keeps
            # the chip out of the way until the player has actually
            # built a relationship with the drill (no "0× mastered"
            # noise on first encounter).
            lifetime = _lifetime_completions(log, name)
            mastery_chip = (
                f'<span class="tp-mastery">Mastered {lifetime}×</span>'
                if lifetime >= 3 else ""
            )

            reps_chip = f'<span class="dt-drill-reps">SUGGESTED · {reps}</span>' if reps else ''
            how_html = f'<div class="dt-drill-how">{how}</div>' if how else ''

            drill_html = (
                f'<div class="dt-drill {done_cls}">'
                f'<div class="dt-drill-row">'
                f'<div class="dt-drill-num">{num_label}</div>'
                f'<div class="dt-drill-meta">'
                f'<div class="dt-drill-name">{name}{role_chip}{mastery_chip}</div>'
                f'{reps_chip}'
                f'{how_html}'
                f'</div>'
                f'<div class="dt-drill-status-pill">{status_text}</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(drill_html, unsafe_allow_html=True)

            # Action row (Streamlit widgets, wrapped for styling)
            st.markdown('<div class="dt-actions-wrap">', unsafe_allow_html=True)
            act_col1, act_col2 = st.columns([1, 2])
            with act_col1:
                completed = st.checkbox(
                    "Mark done",
                    value=bool(saved.get("completed")),
                    key=done_key,
                )
            with act_col2:
                reps_done = st.text_input(
                    "Reps completed",
                    value=saved.get("reps_done", ""),
                    key=reps_key,
                    placeholder="e.g. 4x10",
                    label_visibility="visible",
                )
            st.markdown('</div>', unsafe_allow_html=True)

            prev_completed = bool(saved.get("completed"))
            if completed != prev_completed or reps_done != saved.get("reps_done", ""):
                drill_log[drill_id] = {
                    "completed": bool(completed),
                    "reps_done": reps_done,
                    "last_updated": datetime.now().isoformat(timespec="seconds"),
                }
                # v3 mastery archive: append a permanent event on the
                # pending → done transition (NOT on the reverse, and NOT
                # on a reps-only edit). The event is stashed INSIDE
                # drill_log under the sentinel `_completion_events` key
                # — the same piggyback pattern player_storage uses for
                # `_swing_meta`. That way it persists through
                # `save_training_log`'s existing JSON `drill_state`
                # column with zero schema migration.
                if completed and not prev_completed:
                    drill_log.setdefault("_completion_events", []).append({
                        "drill_id": drill_id,
                        "drill_name": drill.get("name", ""),
                        "completed_at": datetime.now().isoformat(timespec="seconds"),
                        "source_swing_date": swing_date,
                        "reps_done": reps_done,
                    })
                dirty = True

    # ---- Re-Test Reminder ----
    # The drill plan's `weekly_guide` is the analyzer's recommended
    # cadence + the explicit "re-film and re-run the comparison every
    # 2–3 weeks" line. Surface it here so the Training Plan answers
    # "when should I upload my next swing?" without the user digging.
    if weekly_guide:
        items_html = "".join(
            f"<li>{_html.escape(item)}</li>" for item in weekly_guide
        )
        retest_html = (
            '<div class="dt-retest">'
            '<div class="dt-retest-icon">↻</div>'
            '<div>'
            '<div class="dt-retest-eyebrow">Re-Test Reminder</div>'
            '<div class="dt-retest-title">'
            'When to upload your next swing'
            '</div>'
            f'<ul class="dt-retest-list">{items_html}</ul>'
            '</div>'
            '</div>'
        )
        st.markdown(retest_html, unsafe_allow_html=True)

    # ---- Session notes ----
    st.markdown(
        '<div class="dt-notes-header">'
        '<div>'
        '<div class="dt-notes-eyebrow">SESSION JOURNAL</div>'
        '<div class="dt-notes-title">How did today feel?</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    notes_key = f"notes__{player_id}"

    # v3 journal fix: every render starts with a BLANK textarea.
    # The previous version seeded `value=` with the last saved note,
    # so the historical entry looked permanently glued to the active
    # input. Now the input is treated as transient — a single session
    # turn — and historical entries live exclusively in the
    # `Previous sessions` expander.
    #
    # The mechanism: after a successful save we set a `_just_saved`
    # flag and `st.rerun()`. On the next render we pop the widget's
    # session-state value BEFORE the widget initialises, so Streamlit
    # treats it as a fresh widget instance with no remembered text.
    if st.session_state.pop("dt_journal_just_saved", False):
        st.session_state.pop(notes_key, None)

    st.markdown('<div class="dt-notes-card">', unsafe_allow_html=True)
    note_text = st.text_area(
        "Session Notes",
        placeholder="What felt locked in? What drill clicked? Anything off?",
        key=notes_key,
        height=130,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dt-save">', unsafe_allow_html=True)
    save_col, _ = st.columns([1, 3])
    if save_col.button("Save Session Notes", key="dt_save_notes_btn"):
        if note_text and note_text.strip():
            log["session_notes"].append({
                "note": note_text.strip(),
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                # Stamp the entry with the swing it relates to so the
                # journal can later be cross-linked to the swing report
                # in the analytics/parent-dashboard work.
                "source_swing_date": swing_date,
                "today_completed": int(total_completed),
                "today_total":     int(total_drills),
            })
            log["drills"] = drill_log
            save_training_log(player_id, log)
            # Belt-and-suspenders: write the log immediately AND set
            # the rerun flag, so the next render sees the entry in the
            # history list and the textarea blank.
            st.session_state["dt_journal_just_saved"] = True
            st.success("Session notes saved.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if dirty:
        log["drills"] = drill_log
        save_training_log(player_id, log)

    # ---- Previous session notes ----
    if log["session_notes"]:
        st.markdown(
            f'<div class="dt-prev-eyebrow">'
            f'PREVIOUS SESSIONS · {len(log["session_notes"])} ENTRIES'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.expander("View previous entries", expanded=False):
            for entry in reversed(log["session_notes"][-10:]):
                entry_html = (
                    f'<div class="dt-prev-entry">'
                    f'<div class="dt-prev-date">{entry.get("saved_at", "")}</div>'
                    f'<div class="dt-prev-text">{entry.get("note", "")}</div>'
                    f'</div>'
                )
                st.markdown(entry_html, unsafe_allow_html=True)

    # ---- Gamification: Achievements + Rewards (after drills/notes) ----
    if gm_state is not None and gm_persisted is not None:
        try:
            _render_achievements(gm_state, gm_persisted)
            _render_rewards(gm_state, gm_persisted)
        except Exception:
            pass

    st.markdown('</div>', unsafe_allow_html=True)
