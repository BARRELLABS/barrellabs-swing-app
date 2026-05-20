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

/* ============================================================
   TRAINING PLAN v3.1 — gamification restraint.
   The legacy bl_theme level card uses a red gradient + red glow +
   red border + red eyebrow + red XP num + red XP fill. That stacks
   to "screaming red" the moment the page loads. We dial every one
   of those reds back to subtle bone/gold treatments here.
   ============================================================ */

/* Level card: replace the red gradient with a calm neutral surface +
   a single thin gold hairline at the top. */
.tp-shell .dt-level-card {
    background:
        radial-gradient(120% 80% at 0% 0%, rgba(232,193,112,0.05) 0%, transparent 60%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.008)) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: 20px !important;
    margin-top: 1.4rem !important;
}
.tp-shell .dt-level-card::before {
    /* Kill the red radial glow behind the card. */
    display: none !important;
}
.tp-shell .dt-level-card::after {
    content: "";
    position: absolute;
    top: 0; left: 16%; right: 16%;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--tp-gold) 50%, transparent);
    opacity: 0.45;
}
.tp-shell .dt-level-eyebrow {
    color: var(--bl-ink-60) !important;
}
.tp-shell .dt-level-name {
    /* Promote to serif italic so the level name reads as the same
       editorial family as the hero, not a SaaS-y sans-bold. */
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    letter-spacing: -0.015em !important;
}
.tp-shell .dt-xp-pill {
    background: rgba(232,193,112,0.06) !important;
    border-color: var(--tp-gold-line) !important;
}
.tp-shell .dt-xp-pill .dt-xp-num {
    color: var(--tp-gold) !important;
}
.tp-shell .dt-xp-bar-fill {
    background: linear-gradient(90deg, var(--tp-gold-deep), var(--tp-gold)) !important;
    box-shadow: 0 0 14px rgba(232,193,112,0.50) !important;
}

/* Stat strip: pods stay neutral. The "is-red" emphasis on
   numbers (used for things like today's completed drills) is
   already gold via the v3 rule at the top of this file. Make
   sure the labels read clean and the pod surface matches the
   rest of the bento. */
.tp-shell .dt-stat-pod {
    background: rgba(255,255,255,0.022) !important;
    border-color: var(--bl-line) !important;
    border-radius: 14px !important;
}
.tp-shell .dt-stat-pod-num {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    letter-spacing: -0.02em !important;
}
.tp-shell .dt-stat-pod-num.is-red {
    /* `is-red` on the legacy class was meant to call attention to
       a stat — make it gold-italic instead so red stays rare. */
    color: var(--tp-gold) !important;
}
.tp-shell .dt-stat-pod-label {
    color: var(--bl-ink-60) !important;
}

/* Motivation chips: the "is-red" variant is the only acceptable
   red-tinted chip on the page (it carries a real urgency signal —
   "1 drill away from unlocking First Reps"). Soften the saturation
   so it doesn't shout. Non-red chips already read clean. */
.tp-shell .dt-motivate-strip {
    margin-top: 1.0rem !important;
    margin-bottom: 1.4rem !important;
}
.tp-shell .dt-motivate-chip {
    background: rgba(255,255,255,0.022) !important;
    border-color: var(--bl-line) !important;
    color: var(--bl-ink-80) !important;
    font-family: var(--bl-sans) !important;
    font-size: 0.85rem !important;
}
.tp-shell .dt-motivate-chip.is-red {
    /* Was: bright red text on bright red background. Now: a quiet
       bone chip with a single gold accent dot. */
    color: var(--bl-ink-100) !important;
    background: rgba(232,193,112,0.06) !important;
    border-color: var(--tp-gold-line) !important;
}
.tp-shell .dt-motivate-chip.is-red::before {
    content: "★ ";
    color: var(--tp-gold);
    font-weight: 700;
    margin-right: 3px;
}

/* Gamification section headers (Achievements / Rewards) — promote
   the title to serif italic to match the rest of v3. */
.tp-shell .dt-gm-section-header {
    border-bottom-color: var(--bl-line) !important;
    position: relative !important;
}
.tp-shell .dt-gm-section-header::after {
    content: "";
    position: absolute; left: 0; bottom: -1px;
    width: 60px; height: 1px;
    background: linear-gradient(90deg, var(--tp-gold) 0%, transparent 100%);
}
.tp-shell .dt-gm-section-eyebrow {
    color: var(--bl-ink-60) !important;
}
.tp-shell .dt-gm-section-title {
    font-family: var(--tp-serif) !important;
    font-style: italic !important;
    font-weight: 400 !important;
    letter-spacing: -0.01em !important;
}

/* ============================================================
   TRAINING PLAN v3.1 — premium drill action row.
   The "Mark done" checkbox + "Reps completed" input still look
   like raw Streamlit. Make them feel like a real card footer:
   bone-on-dark surface, gold focus, clear tap target.
   ============================================================ */

/* The action row container becomes a soft card footer attached to
   the drill card visually (negative margin pulls it under). */
.tp-shell .dt-actions-wrap {
    background: rgba(0,0,0,0.18) !important;
    border: 1px solid var(--bl-line) !important;
    border-top: 0 !important;
    border-radius: 0 0 18px 18px !important;
    padding: 14px 18px !important;
    margin: -10px 0 1rem !important;
    /* Slot it under the drill card so the two read as one shape. */
    position: relative;
    z-index: 0;
}

/* Mark-done checkbox styling — bone label, larger tap area, gold
   accent on hover/check. */
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] {
    margin: 0 !important;
}
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] label {
    font-family: var(--bl-mono) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    color: var(--bl-ink-80) !important;
    padding: 6px 4px !important;
    cursor: pointer;
}
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] label:hover {
    color: var(--tp-gold) !important;
}
/* The native checkbox box itself. Streamlit wraps it in a span
   with role="checkbox" — style the inner span so we don't fight
   the underlying input directly. */
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] span[role="checkbox"],
.tp-shell .dt-actions-wrap [data-baseweb="checkbox"] {
    /* Slight enlargement for better touch + the gold accent on check. */
}
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] [data-baseweb="checkbox"] div:first-child {
    border: 1px solid var(--bl-line-hi) !important;
    border-radius: 6px !important;
    background: rgba(0,0,0,0.30) !important;
    width: 18px !important; height: 18px !important;
    transition: border-color 0.18s ease, background 0.18s ease !important;
}
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"]:hover [data-baseweb="checkbox"] div:first-child {
    border-color: var(--tp-gold-line) !important;
}
/* Checked state — gold fill, dark check inside. */
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] [data-baseweb="checkbox"][aria-checked="true"] div:first-child,
.tp-shell .dt-actions-wrap [data-testid="stCheckbox"] input:checked + div div:first-child {
    background: var(--tp-gold) !important;
    border-color: var(--tp-gold) !important;
}

/* Reps-completed input — editorial style, gold focus, bone text. */
.tp-shell .dt-actions-wrap [data-testid="stTextInput"] {
    margin: 0 !important;
}
.tp-shell .dt-actions-wrap [data-testid="stTextInput"] label {
    font-family: var(--bl-mono) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    color: var(--bl-ink-60) !important;
    margin-bottom: 4px !important;
}
.tp-shell .dt-actions-wrap [data-testid="stTextInput"] input {
    background: rgba(0,0,0,0.30) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: 10px !important;
    color: var(--bl-ink-100) !important;
    font-family: var(--bl-sans) !important;
    font-size: 0.92rem !important;
    padding: 9px 12px !important;
    caret-color: var(--tp-gold) !important;
    transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
}
.tp-shell .dt-actions-wrap [data-testid="stTextInput"] input::placeholder {
    color: var(--bl-ink-40) !important;
}
.tp-shell .dt-actions-wrap [data-testid="stTextInput"] input:focus {
    border-color: var(--tp-gold) !important;
    box-shadow: 0 0 0 3px rgba(232,193,112,0.16) !important;
    outline: none !important;
}
.tp-shell .dt-actions-wrap [data-baseweb="input"],
.tp-shell .dt-actions-wrap [data-baseweb="base-input"] {
    background: transparent !important;
    border: 0 !important;
}

/* ============================================================
   TRAINING PLAN v4 — premium drill card.
     · metadata strip (time · equipment · difficulty · category)
     · expandable how-to (<details> — pure CSS, no JS)
     · emerald "Complete Drill" button (replaces the checkbox)
     · "Drill Completed" stamp + +150 XP burst on transition
     · richer hover / shadow / glow
   ============================================================ */

/* ---- Drill card structural lift: bigger, with depth ---- */
.tp-shell .dt-drill {
    padding: 1.6rem 1.8rem 1.4rem !important;
    border-radius: 22px !important;
    background:
        radial-gradient(120% 80% at 0% 0%, rgba(232,193,112,0.04) 0%, transparent 65%),
        var(--bl-surface-1) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.03) inset,
        0 20px 50px -30px rgba(0,0,0,0.65) !important;
}
.tp-shell .dt-drill:hover {
    transform: translateY(-2px) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.05) inset,
        0 26px 60px -28px rgba(0,0,0,0.7),
        0 0 24px -8px rgba(232,193,112,0.18) !important;
}

/* ---- Metadata strip (under the name) ---- */
.tp-drill-meta-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    margin: 12px 0 14px;
    padding: 10px 0 12px;
    border-top: 1px solid var(--bl-line);
    border-bottom: 1px solid var(--bl-line);
}
.tp-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-family: var(--bl-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bl-ink-60);
    line-height: 1;
}
.tp-meta-item .ico {
    color: var(--tp-gold);
    font-size: 12px;
    line-height: 1;
}

/* ---- "How to Perform This Drill" expandable ---- */
.tp-howto {
    margin: 14px 0 4px;
    border-radius: 14px;
    background: rgba(0,0,0,0.20);
    border: 1px solid var(--bl-line);
    overflow: hidden;
    transition: border-color 0.22s ease, background 0.22s ease;
}
.tp-howto:hover { border-color: var(--bl-line-hi); }
.tp-howto[open] {
    border-color: var(--tp-gold-line);
    background: rgba(0,0,0,0.30);
}
.tp-howto summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    font-family: var(--bl-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--bl-ink-80);
    user-select: none;
    transition: color 0.18s ease;
}
.tp-howto summary::-webkit-details-marker { display: none; }
.tp-howto summary::marker { display: none; }
.tp-howto summary:hover { color: var(--tp-gold); }
.tp-howto-label {
    display: inline-flex;
    align-items: center;
    gap: 10px;
}
.tp-howto-label::before {
    content: "▸";
    color: var(--tp-gold);
    font-size: 11px;
    transition: transform 0.22s cubic-bezier(.32,.72,0,1);
}
.tp-howto[open] .tp-howto-label::before {
    transform: rotate(90deg);
}
.tp-howto-chev {
    font-size: 18px;
    line-height: 1;
    color: var(--bl-ink-60);
    transition: transform 0.22s cubic-bezier(.32,.72,0,1), color 0.18s ease;
}
.tp-howto[open] .tp-howto-chev {
    transform: rotate(90deg);
    color: var(--tp-gold);
}

.tp-howto-body {
    padding: 6px 22px 22px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px 28px;
}
.tp-howto-block {
    /* Each section is its own subgrid cell so the layout reads as a
       coaching brief, not a wall of text. */
}
.tp-howto-block:first-child,
.tp-howto-block:nth-child(2) {
    /* Setup + Execution span both columns each on desktop because they
       carry the most copy. */
    grid-column: 1 / -1;
}
.tp-howto-block:nth-child(2) {
    /* Execution back to spanning both. */
}
.tp-howto-eyebrow {
    font-family: var(--bl-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    color: var(--bl-ink-60);
    margin-bottom: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.tp-howto-eyebrow::before {
    content: "";
    display: inline-block;
    width: 14px;
    height: 1px;
    background: var(--tp-gold);
}
.tp-howto-eyebrow.is-red { color: var(--bl-red); }
.tp-howto-eyebrow.is-red::before { background: var(--bl-red); }
.tp-howto-eyebrow.is-gold { color: var(--tp-gold); }
.tp-howto-eyebrow.is-gold::before { background: var(--tp-gold); }

.tp-howto-list {
    margin: 0;
    padding-left: 18px;
    list-style: none;
    color: var(--bl-ink-80);
    font-size: 0.92rem;
    line-height: 1.55;
}
.tp-howto-list li {
    position: relative;
    padding-left: 18px;
    margin-bottom: 6px;
}
.tp-howto-list li::before {
    content: "›";
    position: absolute;
    left: 0;
    color: var(--tp-gold);
    font-weight: 700;
    line-height: 1.55;
}
.tp-howto-list.is-ordered {
    counter-reset: tp-step;
}
.tp-howto-list.is-ordered li {
    counter-increment: tp-step;
}
.tp-howto-list.is-ordered li::before {
    content: counter(tp-step, decimal-leading-zero);
    font-family: var(--bl-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    color: var(--tp-gold);
    top: 2px;
}
.tp-howto-list.is-mistakes li::before {
    content: "✕";
    color: var(--bl-red);
    font-weight: 700;
}
.tp-howto-success {
    color: var(--bl-ink-100);
    font-family: var(--tp-serif);
    font-style: italic;
    font-size: 1.02rem;
    line-height: 1.5;
    padding: 12px 16px;
    border-radius: 10px;
    background: rgba(232,193,112,0.06);
    border: 1px solid rgba(232,193,112,0.22);
}

/* Reserved video thumbnail slot. */
.tp-howto-video {
    display: grid;
    grid-template-columns: 92px 1fr;
    gap: 14px;
    align-items: center;
    padding: 12px 14px;
    border-radius: 10px;
    background: rgba(0,0,0,0.30);
    border: 1px dashed var(--bl-line-hi);
}
.tp-howto-video-thumb {
    width: 92px;
    height: 56px;
    display: grid; place-items: center;
    background:
        radial-gradient(circle at 50% 50%, rgba(232,193,112,0.10), transparent 65%),
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
    border: 1px solid var(--bl-line);
    border-radius: 8px;
    color: var(--tp-gold);
    font-size: 18px;
    line-height: 1;
}
.tp-howto-video-caption {
    font-family: var(--bl-mono);
    font-size: 10.5px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
    font-weight: 500;
}

/* ---- Action row container (keyed st.container `tp_action_*`) ---- */
.tp-shell [class*="st-key-tp_action_"] {
    margin: 0 0 1.6rem !important;
    padding: 16px 18px 14px !important;
    border: 1px solid var(--bl-line) !important;
    border-top: 0 !important;
    border-radius: 0 0 22px 22px !important;
    background:
        linear-gradient(180deg, rgba(255,255,255,0.018), rgba(255,255,255,0.008)) !important;
    /* Visually attach to the drill card above. */
    margin-top: -14px !important;
}
.tp-shell [class*="st-key-tp_action_"] [data-testid="stTextInput"] label {
    font-family: var(--bl-mono) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    color: var(--bl-ink-60) !important;
    margin-bottom: 6px !important;
}
.tp-shell [class*="st-key-tp_action_"] [data-testid="stTextInput"] input {
    background: rgba(0,0,0,0.30) !important;
    border: 1px solid var(--bl-line) !important;
    border-radius: 10px !important;
    color: var(--bl-ink-100) !important;
    font-family: var(--bl-sans) !important;
    font-size: 0.95rem !important;
    padding: 10px 13px !important;
    caret-color: var(--tp-gold) !important;
}
.tp-shell [class*="st-key-tp_action_"] [data-testid="stTextInput"] input:focus {
    border-color: var(--tp-gold) !important;
    box-shadow: 0 0 0 3px rgba(232,193,112,0.16) !important;
    outline: none !important;
}

/* ---- The premium "Complete Drill" button (the big emerald CTA) ---- */
@keyframes tp-glow-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(74,227,140,0.40), 0 18px 36px -16px rgba(74,227,140,0.55); }
    50%      { box-shadow: 0 0 0 4px rgba(74,227,140,0.10), 0 18px 36px -16px rgba(74,227,140,0.55); }
}
.tp-shell [class*="st-key-tp_action_"] .stButton > button[kind="primary"],
.tp-shell [class*="st-key-tp_action_"] [data-testid="stButton"] button[kind="primary"] {
    /* Override the global red-gradient primary button completely. */
    background: linear-gradient(180deg, #43d985 0%, #2cb86b 100%) !important;
    color: #062414 !important;
    border: 1px solid rgba(74,227,140,0.55) !important;
    border-radius: 14px !important;
    padding: 16px 22px !important;
    font-family: var(--bl-sans) !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    text-transform: none !important;
    width: 100% !important;
    box-shadow:
        0 18px 36px -16px rgba(74,227,140,0.55),
        inset 0 1px 0 rgba(255,255,255,0.32),
        inset 0 -1px 0 rgba(0,0,0,0.10) !important;
    transition:
        transform 0.18s cubic-bezier(.34,1.4,.64,1),
        box-shadow 0.22s var(--au-ease, cubic-bezier(.32,.72,0,1)),
        background 0.22s ease !important;
    margin-top: 12px !important;
    animation: tp-glow-pulse 2.6s ease-in-out infinite;
}
.tp-shell [class*="st-key-tp_action_"] .stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    background: linear-gradient(180deg, #58e596 0%, #38c876 100%) !important;
    box-shadow:
        0 22px 44px -14px rgba(74,227,140,0.65),
        inset 0 1px 0 rgba(255,255,255,0.40),
        inset 0 -1px 0 rgba(0,0,0,0.12) !important;
    animation: none;
}
.tp-shell [class*="st-key-tp_action_"] .stButton > button[kind="primary"]:active {
    transform: translateY(0) scale(0.985) !important;
    transition-duration: 100ms !important;
}
.tp-shell [class*="st-key-tp_action_"] .stButton > button[kind="primary"]:focus-visible {
    outline: 2px solid rgba(74,227,140,0.65) !important;
    outline-offset: 3px !important;
}

/* The "Mark as not done" undo button (small ghost link). */
.tp-shell [class*="st-key-tp_action_"] .stButton > button:not([kind="primary"]) {
    background: transparent !important;
    border: 0 !important;
    color: var(--bl-ink-60) !important;
    font-family: var(--bl-mono) !important;
    font-size: 10.5px !important;
    font-weight: 500 !important;
    letter-spacing: 0.20em !important;
    text-transform: uppercase !important;
    padding: 8px 6px !important;
    box-shadow: none !important;
    width: auto !important;
    margin-top: 8px !important;
}
.tp-shell [class*="st-key-tp_action_"] .stButton > button:not([kind="primary"]):hover {
    color: var(--bl-red) !important;
    background: transparent !important;
}

/* ---- "Drill Completed" stamp (replaces the button when done) ---- */
@keyframes tp-stamp-in {
    from { opacity: 0; transform: scale(0.92); }
    to   { opacity: 1; transform: scale(1.0); }
}
.tp-done-stamp {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    border-radius: 14px;
    background:
        radial-gradient(120% 100% at 0% 0%, rgba(74,227,140,0.12) 0%, transparent 65%),
        rgba(74,227,140,0.06);
    border: 1px solid rgba(74,227,140,0.42);
    font-family: var(--bl-mono);
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
    color: var(--tp-green);
    margin-top: 8px;
    animation: tp-stamp-in 0.42s cubic-bezier(.34,1.4,.64,1);
    box-shadow:
        0 0 20px -8px rgba(74,227,140,0.45),
        inset 0 1px 0 rgba(255,255,255,0.05);
}
.tp-done-stamp .tick {
    display: inline-grid;
    place-items: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: var(--tp-green);
    color: #062414;
    font-size: 13px;
    font-weight: 800;
    line-height: 1;
}
.tp-done-stamp .stamp-time {
    color: var(--bl-ink-60);
    font-weight: 500;
    letter-spacing: 0.16em;
    margin-left: auto;
}

/* ---- The completed drill card visual treatment (emerald + brightened) ---- */
.tp-shell .dt-drill.is-done {
    border-color: rgba(74,227,140,0.34) !important;
    background:
        radial-gradient(120% 80% at 100% 0%, rgba(74,227,140,0.10) 0%, transparent 60%),
        radial-gradient(120% 80% at 0% 100%, rgba(74,227,140,0.05) 0%, transparent 60%),
        rgba(255,255,255,0.030) !important;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.05) inset,
        0 0 0 1px rgba(74,227,140,0.10),
        0 22px 50px -28px rgba(74,227,140,0.30) !important;
}
.tp-shell .dt-drill.is-done .dt-drill-status-pill {
    background: rgba(74,227,140,0.12) !important;
    border-color: rgba(74,227,140,0.45) !important;
    color: var(--tp-green) !important;
}
/* Bump the completed +25 XP chip up to +150 XP and make it bolder. */
.tp-shell .dt-drill.is-done::after {
    content: "+150 XP" !important;
    font-size: 11px !important;
    padding: 5px 11px !important;
}

/* ---- Responsive ---- */
@media (max-width: 720px) {
    .tp-howto-body {
        grid-template-columns: 1fr;
        gap: 16px;
        padding: 4px 16px 18px;
    }
    .tp-howto-block:first-child,
    .tp-howto-block:nth-child(2) {
        grid-column: 1 / -1;
    }
    .tp-howto summary { padding: 12px 14px; font-size: 10px; letter-spacing: 0.18em; }
    .tp-drill-meta-strip { gap: 6px 12px; padding: 8px 0 10px; }
    .tp-meta-item { font-size: 9.5px; letter-spacing: 0.14em; }
    .tp-shell .dt-drill { padding: 1.3rem 1.3rem 1.1rem !important; }
    .tp-howto-video { grid-template-columns: 72px 1fr; }
    .tp-howto-video-thumb { width: 72px; height: 44px; }
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


# ============================================================
# Drill instruction library (v4 — premium how-to content)
# ============================================================
# Every drill name in the bank gets a structured instructional module:
#   estimated_time   — display string ("5 min", "8 min", "10 min")
#   equipment        — short list of what's needed
#   difficulty       — "Beginner" / "Intermediate" / "Advanced"
#   setup            — list of bullets (where to stand, what to grab)
#   execution        — numbered steps the player follows
#   focus_points     — 3–5 coaching cues
#   common_mistakes  — bullets of what to avoid
#   success_feels_like — one sentence on the felt sense of doing it right
#
# Unknown drill names fall through to `_GENERIC_INSTRUCTIONS` — a clean
# wrapper around the existing `how` text. So the analyzer can still
# prescribe new drills without crashing the page; they just lose the
# premium instructional layer until a content entry is added.
_DRILL_INSTRUCTIONS: dict[str, dict] = {
    # --------- HEAD STABILITY ---------
    "Wall Drill": {
        "estimated_time": "5 min",
        "equipment": "Open wall · normal stance",
        "difficulty": "Beginner",
        "setup": [
            "Face a blank wall, ~3 feet away.",
            "Take your normal stance — no bat needed.",
            "Pick a single spot on the wall at eye level.",
        ],
        "execution": [
            "Take your normal stride.",
            "Swing dry, slowly, keeping your eyes locked on the spot.",
            "Reset fully between every rep — no rushing.",
            "Build speed only once your head stays still at 50%.",
        ],
        "focus_points": [
            "Eyes glued to one spot on the wall.",
            "Chin tracks over the front shoulder.",
            "No vertical drop or bob through contact.",
        ],
        "common_mistakes": [
            "Letting the head dip on acceleration.",
            "Drifting forward into the wall.",
            "Looking up to track an imagined ball.",
        ],
        "success_feels_like": "Your gaze stays locked. The wall doesn't shift in your field of view through the swing.",
    },
    "Towel-on-Head Drill": {
        "estimated_time": "5 min",
        "equipment": "Light towel · tee · ball",
        "difficulty": "Beginner",
        "setup": [
            "Place a small towel folded on top of your head.",
            "Set the tee at your normal contact point.",
            "Take your stance.",
        ],
        "execution": [
            "Swing at the ball without the towel falling off.",
            "Slow the swing down if the towel slips.",
            "Build to game speed once you can hold it through contact.",
        ],
        "focus_points": [
            "Quiet head equals stable towel.",
            "Trust the legs and hips to drive the swing — not the head.",
            "Stay tall through finish.",
        ],
        "common_mistakes": [
            "Diving forward and tipping the towel off.",
            "Rolling shoulders over instead of rotating.",
        ],
        "success_feels_like": "The towel stays glued from load to finish, even on hard swings.",
    },
    "Eye-on-the-Tee": {
        "estimated_time": "6 min",
        "equipment": "Tee · ball",
        "difficulty": "Beginner",
        "setup": [
            "Set the tee at your normal contact point.",
            "Mark a single point on the ball — a logo, a dot, a seam.",
        ],
        "execution": [
            "Stare at the point through the entire swing.",
            "Try to read the mark at contact.",
            "Reset, breathe, repeat.",
        ],
        "focus_points": [
            "Hard focus on one tiny point.",
            "No head rotation toward the imaginary pitcher.",
            "See contact happen — don't just hit and look up.",
        ],
        "common_mistakes": [
            "Eyes pulling off the ball early.",
            "Tracking the bat path instead of the target.",
        ],
        "success_feels_like": "You can describe what the mark on the ball looked like at impact.",
    },
    "Mirror Feedback": {
        "estimated_time": "5 min",
        "equipment": "Full-length mirror",
        "difficulty": "Beginner",
        "setup": [
            "Stand square to a mirror, ~6 feet away.",
            "Take your stance so you can see your full body.",
        ],
        "execution": [
            "Swing slowly, watching head position frame by frame.",
            "Hold the finish for 1 second — verify head hasn't moved.",
            "Add tempo gradually.",
        ],
        "focus_points": [
            "Use your eyes to audit yourself in real time.",
            "Look for vertical and lateral head drift.",
            "Note where the chin is at finish.",
        ],
        "common_mistakes": [
            "Watching the bat instead of the head.",
            "Cheating slow reps to look clean — go honest speed.",
        ],
        "success_feels_like": "The head in the mirror is in the same spot at finish as at setup.",
    },
    # --------- HIP ROTATION ---------
    "Hip Turn Step-Throughs": {
        "estimated_time": "8 min",
        "equipment": "Bat · open space",
        "difficulty": "Intermediate",
        "setup": [
            "Take your normal stance with the bat.",
            "Pick a target line in front of you.",
        ],
        "execution": [
            "Initiate the swing with the back hip turning aggressively.",
            "Let the back foot step through naturally as you rotate.",
            "Finish balanced with the back foot ahead of the front.",
        ],
        "focus_points": [
            "Rotation starts in the hips — not the arms.",
            "Step-through is a RESULT of full rotation, not a goal.",
            "Stay balanced at finish — no falling off.",
        ],
        "common_mistakes": [
            "Stepping through with the back foot too early.",
            "Arms firing before hips rotate.",
        ],
        "success_feels_like": "Your hips outrun your hands — and the bat snaps through almost involuntarily.",
    },
    "Belt-Tug Drill": {
        "estimated_time": "5 min",
        "equipment": "Resistance band or training partner",
        "difficulty": "Intermediate",
        "setup": [
            "Tie a band around your front belt loop OR have a partner hold it.",
            "Stand with the resistance pulling AWAY from the pitcher (toward your back side).",
        ],
        "execution": [
            "Initiate the swing by driving the front hip AGAINST the resistance.",
            "Feel the hip lead the rotation.",
            "Add bat swings once the lead-hip feel is locked in.",
        ],
        "focus_points": [
            "Front hip pulls the swing through.",
            "Don't muscle up — let the leverage do the work.",
            "Stay tall and balanced.",
        ],
        "common_mistakes": [
            "Pulling with the upper body instead of the hip.",
            "Lunging forward to beat the band.",
        ],
        "success_feels_like": "Your hips are doing the heavy lifting — your arms and hands feel light.",
    },
    "Resistance Band Rotations": {
        "estimated_time": "6 min",
        "equipment": "Resistance band · anchor point",
        "difficulty": "Intermediate",
        "setup": [
            "Anchor a band at chest height to your side.",
            "Hold the band with both hands like a bat.",
            "Stand far enough away that there's real tension.",
        ],
        "execution": [
            "Rotate through the swing path against the band's resistance.",
            "Pause at full rotation — feel the load.",
            "Return slowly, repeat.",
        ],
        "focus_points": [
            "Lead with hips, follow with shoulders.",
            "Full range of motion — no shortcuts.",
            "Slow and controlled on the return.",
        ],
        "common_mistakes": [
            "Yanking with arms.",
            "Cutting the rotation short.",
        ],
        "success_feels_like": "Your rotation is smooth and powerful, like winding and unwinding a spring.",
    },
    "Closed-Stance Tee Work": {
        "estimated_time": "8 min",
        "equipment": "Tee · ball · bat",
        "difficulty": "Intermediate",
        "setup": [
            "Set up with your stance more closed than normal (front foot 3–4 inches in toward the plate).",
            "Tee at your normal contact point.",
        ],
        "execution": [
            "Swing normally — the closed stance forces full hip rotation to clear the path.",
            "Focus on driving the back hip through.",
            "Hit 8–10 balls, reset, repeat.",
        ],
        "focus_points": [
            "Closed stance is the constraint — let it teach you.",
            "Hips MUST rotate fully or you can't reach the ball clean.",
            "Stay balanced through contact.",
        ],
        "common_mistakes": [
            "Trying to muscle the swing instead of rotating.",
            "Reverting to an open stance mid-rep.",
        ],
        "success_feels_like": "Contact is clean and the bat path feels natural despite the closed stance.",
    },
    # --------- SEPARATION ---------
    "Connection Ball Drill": {
        "estimated_time": "8 min",
        "equipment": "Small ball or rolled towel · bat",
        "difficulty": "Intermediate",
        "setup": [
            "Place a small ball (or rolled-up towel) between your front forearm and chest.",
            "Take your normal stance.",
        ],
        "execution": [
            "Swing without dropping the ball.",
            "If the ball falls, your arms disconnected from your torso early.",
            "Start slow, then build speed.",
        ],
        "focus_points": [
            "Lead arm stays connected to the torso through the swing.",
            "Power transfers from hips → torso → arms — in order.",
            "No early arm extension.",
        ],
        "common_mistakes": [
            "Casting the arms out before hip turn.",
            "Squeezing the ball too hard (forcing a tight swing).",
        ],
        "success_feels_like": "The ball stays put effortlessly — your swing feels connected and powerful.",
    },
    "Hips First, Hands Last": {
        "estimated_time": "6 min",
        "equipment": "Bat",
        "difficulty": "Intermediate",
        "setup": [
            "Take your normal stance.",
            "Start with your hands LOW — at your hip level — and exaggerate the load.",
        ],
        "execution": [
            "Start the swing by rotating the back hip aggressively.",
            "Force the hands to stay back as the hips rotate.",
            "Let the hands fire LAST, after maximum separation.",
        ],
        "focus_points": [
            "Feel the stretch between hips and shoulders.",
            "Hands stay loaded as hips clear.",
            "Whip-like finish — not a push.",
        ],
        "common_mistakes": [
            "Hands and hips firing together (no separation).",
            "Lunging instead of rotating.",
        ],
        "success_feels_like": "The bat whips through contact like it's catching up to your body.",
    },
    "Heavy Bat Swings": {
        "estimated_time": "6 min",
        "equipment": "Weighted bat (1.5–2× normal)",
        "difficulty": "Advanced",
        "setup": [
            "Grab a heavier-than-normal bat (weighted donut, fungo, or training bat).",
            "Take your normal stance.",
        ],
        "execution": [
            "Take controlled swings at 60–70% speed.",
            "Focus on rotating through the swing — let the weight teach the path.",
            "8–12 swings per set. Switch back to a normal bat after.",
        ],
        "focus_points": [
            "Drive from the hips — the weight punishes upper-body swings.",
            "Stay tall, balanced.",
            "Quality over speed.",
        ],
        "common_mistakes": [
            "Going full speed and breaking form.",
            "Overdoing reps — fatigue trains bad mechanics.",
        ],
        "success_feels_like": "The bat feels effortless to rotate through your zone afterward.",
    },
    "Cross-Arm Rotation": {
        "estimated_time": "5 min",
        "equipment": "Bat · open space",
        "difficulty": "Intermediate",
        "setup": [
            "Cross your arms across your chest, holding the bat against your sternum.",
            "Take your normal stance.",
        ],
        "execution": [
            "Rotate through the swing using ONLY hips and torso.",
            "Feel the separation between hip rotation and shoulder rotation.",
            "Slow reps for feel, then add tempo.",
        ],
        "focus_points": [
            "Hips lead. Shoulders follow.",
            "No arm involvement — that's the point.",
            "Sense the stretch and snap.",
        ],
        "common_mistakes": [
            "Rotating shoulders with the hips (no separation).",
            "Adding arm movement once it gets faster.",
        ],
        "success_feels_like": "You feel like a coiled spring releasing in sequence.",
    },
    # --------- KNEE ---------
    "Front Knee Block Drill": {
        "estimated_time": "7 min",
        "equipment": "Bat · tee · ball",
        "difficulty": "Intermediate",
        "setup": [
            "Tee at normal contact point.",
            "Take your normal stance.",
        ],
        "execution": [
            "Take your stride and PLANT the front foot firmly.",
            "Lock the front knee straight as the swing fires.",
            "Feel the front leg become a wall — energy transfers UP through it.",
        ],
        "focus_points": [
            "Front leg goes from soft (stride) to firm (block) at contact.",
            "Don't drift forward — pivot AROUND the front leg.",
            "Stay tall at finish.",
        ],
        "common_mistakes": [
            "Front knee collapsing inward.",
            "Continuing to drift after the block.",
        ],
        "success_feels_like": "Your front leg locks and your swing fires through it like a hinge.",
    },
    "Wall Sit Holds": {
        "estimated_time": "5 min",
        "equipment": "Wall",
        "difficulty": "Beginner",
        "setup": [
            "Back against a wall, feet shoulder-width apart.",
            "Slide down to a 90° squat position.",
        ],
        "execution": [
            "Hold for 30–45 seconds.",
            "Rest 30 seconds, repeat 3–5 times.",
            "Squeeze the front quad on each hold.",
        ],
        "focus_points": [
            "Builds the front-leg strength that powers the block.",
            "Stay tall — chest up, shoulders back.",
            "Engage the core.",
        ],
        "common_mistakes": [
            "Letting the knees collapse inward.",
            "Resting weight on the wall instead of the legs.",
        ],
        "success_feels_like": "Your front leg feels rock-solid by the end of the set.",
    },
    "Step-Back Drill": {
        "estimated_time": "8 min",
        "equipment": "Bat · tee · ball",
        "difficulty": "Intermediate",
        "setup": [
            "Start with weight already loaded on the back leg, front foot lifted.",
            "Tee at normal contact point.",
        ],
        "execution": [
            "Take an exaggerated stride into a FIRM front-leg block.",
            "Swing.",
            "Trains the load → block → fire sequence in slow motion.",
        ],
        "focus_points": [
            "Big load. Hard block. Smooth fire.",
            "Front leg blocks, doesn't bend.",
            "Reset slowly between reps.",
        ],
        "common_mistakes": [
            "Soft block (front knee collapses).",
            "Rushing the sequence.",
        ],
        "success_feels_like": "Power flows from back leg → front leg → bat in a clear chain.",
    },
    # --------- TIMING ---------
    "Short-Toss Quick Hands": {
        "estimated_time": "10 min",
        "equipment": "Partner · soft balls (tennis or baseballs)",
        "difficulty": "Intermediate",
        "setup": [
            "Partner stands 8–10 feet in front of you.",
            "Use tennis balls for safety, baseballs for game-rep feel.",
            "Take your normal stance.",
        ],
        "execution": [
            "Start in load position with the bat.",
            "Partner soft-tosses underhand to the inner third.",
            "Attack with the shortest possible hand path.",
            "Focus on immediate acceleration — no buildup.",
            "Reset fully between reps. Quality over quantity.",
        ],
        "focus_points": [
            "Shortest possible path from load to contact.",
            "Hands ACCELERATE — they don't drift.",
            "No wasted motion.",
            "Feel the barrel get there early.",
        ],
        "common_mistakes": [
            "Casting the barrel out.",
            "Over-striding.",
            "Pulling off the ball.",
        ],
        "success_feels_like": "Contact happens earlier and more effortlessly than your normal swing.",
    },
    "Tennis Ball Reactions": {
        "estimated_time": "10 min",
        "equipment": "Partner · 5–8 tennis balls",
        "difficulty": "Intermediate",
        "setup": [
            "Partner stands 8–10 feet away with a bucket of tennis balls.",
            "Take your normal stance.",
            "No expectation of rhythm — you DON'T know when the next ball comes.",
        ],
        "execution": [
            "Partner tosses unpredictably — different speeds, small intentional pauses.",
            "React to each ball. Don't time a rhythm.",
            "Focus on reading the ball, not timing the toss.",
            "Reset between reps.",
        ],
        "focus_points": [
            "READ the pitch — don't time the pattern.",
            "Stay loaded and ready.",
            "Quick recognition, quick decision.",
        ],
        "common_mistakes": [
            "Locking into a rhythm with the partner.",
            "Pre-loading too early and getting beat.",
        ],
        "success_feels_like": "You stop guessing — you react instead.",
    },
    "One-Hand Top-Hand Tee": {
        "estimated_time": "8 min",
        "equipment": "Tee · ball · bat",
        "difficulty": "Intermediate",
        "setup": [
            "Take your normal stance with the bat in your TOP (back) hand only.",
            "Drop the bottom hand off the bat.",
            "Tee at normal contact point.",
        ],
        "execution": [
            "Swing one-handed through the ball.",
            "Focus on a compact, quick path — there's no leverage to muscle it.",
            "Stay short to the ball, long through it.",
        ],
        "focus_points": [
            "Force a tight path — no looping.",
            "Top hand drives through contact.",
            "Quick acceleration, not a long backswing.",
        ],
        "common_mistakes": [
            "Looping the bat to generate force (impossible one-handed).",
            "Dragging the bat through the zone.",
        ],
        "success_feels_like": "The bat fires through the ball in a tight, direct line — even with just one hand.",
    },
}

# Generic fallback for any drill name not in `_DRILL_INSTRUCTIONS`.
# The analyzer can ship new drills before the content library catches
# up; this keeps those drills renderable instead of crashing the page.
_GENERIC_INSTRUCTIONS = {
    "estimated_time": "5–10 min",
    "equipment": "Standard hitting gear",
    "difficulty": "Intermediate",
    "setup": [
        "Set up in your normal stance with the equipment listed above.",
        "Use the suggested reps as a guideline — adjust to your level.",
    ],
    "execution": [
        "Follow the drill description in the coach's notes above.",
        "Move with intent on every rep.",
        "Reset fully between reps — quality over speed.",
    ],
    "focus_points": [
        "Stay athletic and balanced.",
        "Move with intent.",
        "Quality of movement beats quantity of reps.",
    ],
    "common_mistakes": [
        "Rushing reps without resetting.",
        "Losing posture between swings.",
        "Skipping the slow / feel-building phase.",
    ],
    "success_feels_like": "The movement starts to feel automatic and repeatable.",
}


def _drill_instructions(drill_name: str) -> dict:
    """Look up the instructional module for this drill name."""
    return _DRILL_INSTRUCTIONS.get(
        (drill_name or "").strip(),
        _GENERIC_INSTRUCTIONS,
    )


# ============================================================
# Hero category → coaching-language mapping
# ============================================================
# The analyzer's category titles ("Sharpen Timing & Quickness") are
# accurate but read as feature names. v4 promotes a more athletic
# verb phrase for the hero focus chip + deck — closer to "Build
# Quicker Hands" — without changing the underlying category title
# (which is used as a drill_id key for completion tracking).
_CATEGORY_COACHING_PHRASE = {
    "Sharpen Timing & Quickness":    "Build Quicker Hands",
    "Drive Hip-Shoulder Separation": "Build Hip-to-Hand Sequencing",
    "Open the Hips Sooner":          "Fire the Back Hip Earlier",
    "Block With the Front Knee":     "Stabilize the Contact Point",
    "Quiet the Head":                "Steady Your Eye-Line",
}


def _coaching_phrase_for(category_title: str) -> str:
    """Return the athletic verb-phrase version of a category title.

    Falls through to the original title for unknown categories so
    nothing breaks when the analyzer ships a new focus area before
    the mapping catches up.
    """
    raw = (category_title or "").strip()
    return _CATEGORY_COACHING_PHRASE.get(raw, raw)


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
    # from the analyzer-built drill_plan. v4: we promote the raw
    # category name ("Sharpen Timing & Quickness") through the
    # coaching-phrase mapping so the focus chip reads as an athletic
    # outcome ("Build Quicker Hands") instead of a feature name.
    plan = (saved_swing or {}).get("drill_plan") or {}
    cats = plan.get("categories") or []
    primary_issue = ""
    if cats:
        primary_issue = _coaching_phrase_for(cats[0].get("title") or "")
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
    # NOTE: the editorial brand hero is rendered ONLY inside the
    # early-return branches (unauth / no-Pro / no-swing). In the
    # has-data branch the data-driven hero (with bento + state-aware
    # headline) is the single hero — see below. v3 fix: previously the
    # brand hero rendered unconditionally at the top AND the data hero
    # rendered again later, so the page showed two heroes.

    # ---- Auth check ----
    user = st.session_state.get("user")
    if not user:
        st.markdown(_build_hero_brand_html(), unsafe_allow_html=True)
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
        st.markdown(_build_hero_brand_html(), unsafe_allow_html=True)
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

    except Exception:
        gm_state = None
        gm_persisted = None
    # v3 ordering: defer rendering the gamification cards (level / stat
    # strip / motivation chips) until AFTER the data hero so the page's
    # first impression is the editorial hero + bento, not the legacy
    # red-heavy level card. We still compute gm_state above so the
    # data hero can read the streak.

    saved_swing = _latest_swing_with_drill_plan(player_id)
    if not saved_swing:
        st.markdown(_build_hero_brand_html(), unsafe_allow_html=True)
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
    # These come FIRST in the has-data path so the page's identity is
    # the editorial hero + bento, not the legacy red-heavy level card.
    # Order: data hero → consistency → gamification (level/stat/motiv)
    # → progress ring → coach notes → drill cards → re-test → notes.
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

    # ---- Gamification (level / stat strip / motivation chips) ----
    # Rendered AFTER the data hero so the page reads top-down as:
    # identity → today's numbers → consistency → level + stats →
    # progress ring → drills. Wrapped in try/except so a gamification
    # render failure can never block the drills below.
    if gm_state is not None:
        try:
            _render_level_card(gm_state)
            _render_stat_strip(gm_state)
            _render_motivation_strip(gm_state)
        except Exception:
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
            undo_key = f"undo__{player_id}__{drill_id}"
            reps_key = f"reps__{player_id}__{drill_id}"
            complete_btn_key = f"complete_btn__{player_id}__{drill_id}"

            is_done = drill_states.get(drill_id, False)
            done_cls = "is-done" if is_done else ""

            name = drill.get("name", "Drill")
            reps = drill.get("reps", "")
            how = drill.get("how", "")
            num_label = f"{drill_counter:02d}"
            role_label, role_cls = _role_for(cat_idx - 1, drill_idx)

            # Mastery chip threshold ≥ 3 → no "0× mastered" noise on first encounter.
            lifetime = _lifetime_completions(log, name)
            mastery_chip = (
                f'<span class="tp-mastery">Mastered {lifetime}×</span>'
                if lifetime >= 3 else ""
            )

            # v4 instructional module — pulled from the drill library.
            instr = _drill_instructions(name)
            status_text = (
                f'✓ COMPLETED · {(saved.get("last_updated") or "")[11:16]}'
                if is_done else "○ PENDING"
            )

            # ---- Premium drill card (header + metadata + body) ----
            role_chip = f'<span class="dt-role {role_cls}">{role_label}</span>'
            reps_chip = (
                f'<span class="dt-drill-reps">SUGGESTED · '
                f'{_html.escape(str(reps))}</span>'
                if reps else ""
            )
            description_html = (
                f'<div class="dt-drill-how">{_html.escape(how)}</div>'
                if how else ""
            )

            # Metadata strip — time · equipment · difficulty · category.
            meta_strip = (
                f'<div class="tp-drill-meta-strip">'
                f'<span class="tp-meta-item"><span class="ico">◷</span>{_html.escape(instr["estimated_time"])}</span>'
                f'<span class="tp-meta-item"><span class="ico">⚙</span>{_html.escape(instr["equipment"])}</span>'
                f'<span class="tp-meta-item"><span class="ico">▲</span>{_html.escape(instr["difficulty"])}</span>'
                f'<span class="tp-meta-item"><span class="ico">◎</span>{_html.escape(cat_title)}</span>'
                f'</div>'
            )

            # How-to expandable — pure HTML <details>, CSS-only animation.
            def _li(items: list[str]) -> str:
                return "".join(
                    f"<li>{_html.escape(i)}</li>" for i in (items or [])
                )

            def _ol(items: list[str]) -> str:
                return "".join(
                    f"<li>{_html.escape(i)}</li>" for i in (items or [])
                )

            howto_html = (
                f'<details class="tp-howto">'
                f'<summary>'
                f'<span class="tp-howto-label">How to Perform This Drill</span>'
                f'<span class="tp-howto-chev">›</span>'
                f'</summary>'
                f'<div class="tp-howto-body">'
                # SETUP
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow">Setup</div>'
                f'<ul class="tp-howto-list">{_li(instr.get("setup", []))}</ul>'
                f'</div>'
                # EXECUTION
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow">Execution</div>'
                f'<ol class="tp-howto-list is-ordered">{_ol(instr.get("execution", []))}</ol>'
                f'</div>'
                # FOCUS POINTS
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow">Focus Points</div>'
                f'<ul class="tp-howto-list">{_li(instr.get("focus_points", []))}</ul>'
                f'</div>'
                # COMMON MISTAKES
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow is-red">Common Mistakes</div>'
                f'<ul class="tp-howto-list is-mistakes">{_li(instr.get("common_mistakes", []))}</ul>'
                f'</div>'
                # SUCCESS FEELS LIKE
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow is-gold">Success Feels Like</div>'
                f'<div class="tp-howto-success">{_html.escape(instr.get("success_feels_like", ""))}</div>'
                f'</div>'
                # VIDEO PLACEHOLDER — reserved space for a future drill clip.
                f'<div class="tp-howto-block">'
                f'<div class="tp-howto-eyebrow">Video</div>'
                f'<div class="tp-howto-video">'
                f'<div class="tp-howto-video-thumb">▶</div>'
                f'<div class="tp-howto-video-caption">'
                f'Drill demo video — coming soon.'
                f'</div>'
                f'</div>'
                f'</div>'
                f'</div>'  # /tp-howto-body
                f'</details>'
            )

            # Drill card body — header row + meta strip + description + howto.
            # The action row (real Streamlit button) comes AFTER the markdown
            # block so it can persist completion state.
            drill_html = (
                f'<div class="dt-drill {done_cls}">'
                f'<div class="dt-drill-row">'
                f'<div class="dt-drill-num">{num_label}</div>'
                f'<div class="dt-drill-meta">'
                f'<div class="dt-drill-name">{_html.escape(name)}{role_chip}{mastery_chip}</div>'
                f'{reps_chip}'
                f'</div>'
                f'<div class="dt-drill-status-pill">{status_text}</div>'
                f'</div>'
                f'{meta_strip}'
                f'{description_html}'
                f'{howto_html}'
                f'</div>'
            )
            st.markdown(drill_html, unsafe_allow_html=True)

            # ---- Action row: real Streamlit widgets, scoped to a keyed
            # container so the v4 CSS can give the premium button +
            # reps input their custom shell. ----
            with st.container(key=f"tp_action_{drill_id}"):
                # Reps tracker first (always visible).
                reps_done = st.text_input(
                    "Reps completed",
                    value=saved.get("reps_done", ""),
                    key=reps_key,
                    placeholder="e.g. 4×10",
                    label_visibility="visible",
                )

                if is_done:
                    # Completed: emerald confirmation badge + undo link.
                    last_updated = saved.get("last_updated") or ""
                    stamp = last_updated[11:16] if last_updated else ""
                    st.markdown(
                        f'<div class="tp-done-stamp">'
                        f'<span class="tick">✓</span>'
                        f'<span>Drill Completed</span>'
                        f'<span class="stamp-time">{stamp}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Mark as not done",
                        key=undo_key,
                        help="Reverts this drill back to pending.",
                    ):
                        drill_log[drill_id] = {
                            "completed": False,
                            "reps_done": reps_done,
                            "last_updated": datetime.now().isoformat(timespec="seconds"),
                        }
                        log["drills"] = drill_log
                        save_training_log(player_id, log)
                        st.rerun()
                else:
                    # Pending: premium emerald "Complete Drill" button.
                    if st.button(
                        "⚡  Complete Drill",
                        key=complete_btn_key,
                        type="primary",
                        use_container_width=True,
                        help="Mark this drill complete and earn +150 XP.",
                    ):
                        drill_log[drill_id] = {
                            "completed": True,
                            "reps_done": reps_done,
                            "last_updated": datetime.now().isoformat(timespec="seconds"),
                        }
                        # Append a mastery event (same pattern as before).
                        drill_log.setdefault("_completion_events", []).append({
                            "drill_id": drill_id,
                            "drill_name": name,
                            "completed_at": datetime.now().isoformat(timespec="seconds"),
                            "source_swing_date": swing_date,
                            "reps_done": reps_done,
                        })
                        log["drills"] = drill_log
                        save_training_log(player_id, log)
                        # XP burst flag — picked up on the next render to
                        # play the +150 XP floating chip via CSS.
                        st.session_state[f"_xp_burst_{drill_id}"] = True
                        st.rerun()

            # Reps-only edits (no completion change) still need to be
            # saved to the log on the same render they happen.
            if (not is_done) and reps_done != saved.get("reps_done", ""):
                drill_log[drill_id] = {
                    "completed": False,
                    "reps_done": reps_done,
                    "last_updated": datetime.now().isoformat(timespec="seconds"),
                }
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
