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
</style>
"""


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
        classes = ["dt-reward"]
        if unlocked:
            classes.append("is-unlocked")
        if rid == "r_hoodie":
            classes.append("is-hoodie")
        elif rid == "r_hall_of_fame":
            classes.append("is-hof")
        card_cls = " ".join(classes)

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
    st.markdown('<div class="bl-page">', unsafe_allow_html=True)

    # ---- Hero ----
    hero_html = textwrap.dedent("""
    <div class="dt-hero">
      <div class="dt-hero-row">
        <div style="flex:1;min-width:0;">
          <div class="dt-hero-eyebrow">BarrelLabs Performance Lab</div>
          <div class="dt-hero-title">Development Tracker</div>
          <div class="dt-hero-sub">
            Work through the exact drills BarrelLabs prescribed from your
            latest swing report. Your progress saves automatically across
            sessions, so you can pick up where you left off.
          </div>
        </div>
        <div class="dt-mode-pill"><span class="dt-mode-pill-dot"></span> Training Mode</div>
      </div>
    </div>
    """).strip()
    st.markdown(hero_html, unsafe_allow_html=True)

    # ---- Auth check ----
    user = st.session_state.get("user")
    if not user:
        _render_empty_state(
            title="Please sign in to use the Development Tracker.",
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
    The Development Tracker is Pro-only.
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
            title="No drill plan yet.",
            sub="Analyze a swing first — once you have a swing report, your "
                "personalized drill plan will appear here automatically.",
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
    categories = drill_plan.get("categories", [])
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

    _render_progress_card(total_completed, total_drills, swing_date, player_name)

    # ---- Categories + drills ----
    dirty = False
    drill_counter = 0
    for cat_idx, category in enumerate(categories, start=1):
        cat_title = category.get("title", "Drills")
        cat_priority = category.get("priority", cat_idx)
        cat_drills = category.get("drills", [])

        cat_header = textwrap.dedent(f"""
        <div class="dt-cat-header">
          <span class="dt-cat-priority-pill">Priority {cat_priority}</span>
          <span class="dt-cat-title">{cat_title}</span>
          <span class="dt-cat-count">{len(cat_drills)} DRILL{'S' if len(cat_drills) != 1 else ''}</span>
        </div>
        """).strip()
        st.markdown(cat_header, unsafe_allow_html=True)

        for drill in cat_drills:
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

            reps_chip = f'<span class="dt-drill-reps">SUGGESTED · {reps}</span>' if reps else ''
            how_html = f'<div class="dt-drill-how">{how}</div>' if how else ''

            drill_html = (
                f'<div class="dt-drill {done_cls}">'
                f'<div class="dt-drill-row">'
                f'<div class="dt-drill-num">{num_label}</div>'
                f'<div class="dt-drill-meta">'
                f'<div class="dt-drill-name">{name}</div>'
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

            if completed != bool(saved.get("completed")) or reps_done != saved.get("reps_done", ""):
                drill_log[drill_id] = {
                    "completed": bool(completed),
                    "reps_done": reps_done,
                    "last_updated": datetime.now().isoformat(timespec="seconds"),
                }
                dirty = True

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
    last_note = log["session_notes"][-1]["note"] if log["session_notes"] else ""

    st.markdown('<div class="dt-notes-card">', unsafe_allow_html=True)
    note_text = st.text_area(
        "Session Notes",
        value=st.session_state.get(notes_key, last_note),
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
            })
            dirty = True
            st.success("Session notes saved.")
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
