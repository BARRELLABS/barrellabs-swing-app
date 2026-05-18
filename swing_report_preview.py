"""
Swing Report Preview — Phase 1 design approval page.

PREVIEW-ONLY route. Reachable at:

    /?page=swing_report_preview

(With a chosen record stashed in session_state["preview_swing_record"]
when reached from the Saved Reports preview Open Report click. Falls
back to the most recent real swing, or to synthetic sample data, so
the design is always visible.)

Design intent: 11-section flagship report in the v3 Edge editorial
language. Instrument Serif italic display, Geist body, Geist Mono
labels, bone palette, red/gold accents. Uses ONLY real metrics if
available; missing axes are gracefully omitted. Comparison section
shows the redesigned side-by-side delta against the prior swing.

Sections in order:
  1. Hero score (Edge score ring + headline)
  2. MLB comparison (doppel card)
  3. Top strengths
  4. Top issues
  5. Coach report / narrative analysis
  6. What to fix (prioritized list)
  7. Drill plan (cards with priority/reps/why)
  8. Drill logging (Streamlit-native checkboxes)
  9. Progress insights (history sparkline / trend pills)
 10. Premium metric cards (per-axis grid)
 11. Redesigned Swing Comparison (vs prior swing)

This file is the design preview only; once approved, the wire-up phase
will route Open Report (and the dashboard's hero) here.
"""

from __future__ import annotations

import html
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import streamlit as st
import textwrap

from bl_edge_chrome import (
    render_edge_masthead,
    render_edge_page_wrapper_open,
    render_edge_page_wrapper_close,
)


def _html(s: str) -> None:
    """Render raw HTML safely.

    Streamlit's markdown processor treats lines with 4+ leading spaces
    as INDENTED CODE BLOCKS and escapes them. Our editorial templates
    use heavy indentation for readability AND interpolate sub-strings
    (SVG, sub-templates) whose own indentation breaks textwrap.dedent's
    "common minimum" detection. The only reliable fix is to strip
    ALL leading whitespace from EVERY line before handing the string
    to st.markdown. HTML rendering is unaffected because browsers
    collapse whitespace outside `<pre>` blocks (which we don't use).
    """
    flat = "\n".join(line.lstrip() for line in s.splitlines())
    # CRITICAL: must pass unsafe_allow_html=True directly here. Do NOT
    # call _html(flat) — that's infinite recursion. Do NOT drop the
    # kwarg — Streamlit will escape every < and > in the HTML.
    st.markdown(flat, unsafe_allow_html=True)

try:
    from player_storage import load_swing_history, load_swing_meta
except Exception:
    load_swing_history = None
    load_swing_meta = None


# =====================================================================
#  Shared Edge token CSS (mirrors mock_dashboard_template.py)
# =====================================================================
_EDGE_TOKENS_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:           #0A0B0E;
  --bg-elev:      #11141A;
  --bg-glass:     rgba(255, 255, 255, 0.025);
  --bg-glass-hi:  rgba(255, 255, 255, 0.045);
  --line:         rgba(244, 239, 230, 0.08);
  --line-hi:      rgba(244, 239, 230, 0.16);
  --line-lo:      rgba(244, 239, 230, 0.04);
  --bone:         #F4EFE6;
  --bone-dim:     #C8C4BB;
  --gray-1:       #8B8E94;
  --gray-2:       #565A62;
  --gray-3:       #2A2D33;
  --red:          #E64530;
  --red-deep:     #B83320;
  --red-soft:     rgba(230, 69, 48, 0.12);
  --red-glow:     rgba(230, 69, 48, 0.32);
  --gold:         #E8C170;
  --gold-deep:    #C9A350;
  --gold-soft:    rgba(232, 193, 112, 0.10);
  --green:        #4AE38C;
  --amber:        #FFB948;
  --serif:        'Instrument Serif', 'Fraunces', Georgia, serif;
  --serif-alt:    'Fraunces', 'Instrument Serif', Georgia, serif;
  --sans:         'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --mono:         'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;
  --radius-xs:    4px;
  --radius-sm:    8px;
  --radius:       14px;
  --radius-lg:    20px;
}
</style>
"""


_SRP_CSS = """
<style>
/* ---------- BACK LINK + ISSUE LINE ---------- */
.srp-pre-strip {
  display: flex; align-items: center; justify-content: space-between;
  gap: 24px; padding-top: 16px; padding-bottom: 8px;
}
/* Back to Sessions — keyed selector */
.st-key-srpv_back_to_sessions button {
  background: transparent !important;
  color: var(--bone-dim) !important;
  border: 1px solid var(--line) !important;
  border-radius: 100px !important;
  font-family: var(--mono) !important;
  font-size: 11px !important; letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  padding: 7px 14px !important;
  min-height: 0 !important;
  width: auto !important;
  box-shadow: none !important;
  transition: all 0.2s ease !important;
}
.st-key-srpv_back_to_sessions button:hover {
  color: var(--bone) !important; border-color: var(--line-hi) !important;
  background: rgba(244,239,230,0.04) !important;
}
.srp-issue-line {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 0 28px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-2);
  border-bottom: 1px solid var(--line);
  margin-bottom: 8px;
}
.srp-issue-line .center { color: var(--bone-dim); }

/* ---------- HERO ---------- */
.srp-hero {
  display: grid; grid-template-columns: 240px 1fr 280px; gap: 48px;
  padding: 32px 0 56px; border-bottom: 1px solid var(--line);
  align-items: center;
}
/* Hero columns must not letter-wrap. Give the headline / doppel
   adequate min-widths so they collapse to stacked layout cleanly
   rather than smushing into letter-stacks. */
@media (max-width: 1200px) {
  .srp-hero {
    grid-template-columns: 220px 1fr;
    gap: 32px;
  }
  .srp-hero .srp-doppel { grid-column: 1 / -1; max-width: 600px; }
}
@media (max-width: 760px) {
  .srp-hero { grid-template-columns: 1fr; gap: 28px; padding: 20px 0 40px; }
  .srp-hero-headline { font-size: 48px; }
}
.srp-score-wrap { display: flex; flex-direction: column; align-items: center; }
.srp-score-svg { filter: drop-shadow(0 0 24px rgba(232,193,112,0.05)); }
.srp-score-label {
  margin-top: -8px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1);
}
.srp-score-cats {
  margin-top: 22px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.06em; color: var(--gray-1);
  text-transform: uppercase;
}
.srp-cat-row { display: flex; justify-content: space-between; gap: 14px; }
.srp-cat-row .v { color: var(--bone); font-weight: 500; }
.srp-cat-row .v.peak { color: var(--gold); }

.srp-hero-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--red); margin-bottom: 24px;
}
.srp-hero-eyebrow .swatch { display: inline-block; width: 22px; height: 1px; background: var(--red); }
.srp-hero-headline {
  font-family: var(--serif); font-weight: 400;
  font-size: 72px; line-height: 1.02; letter-spacing: -0.025em;
  color: var(--bone); margin: 0 0 22px;
}
.srp-hero-headline .ital { font-style: italic; color: var(--gold); padding: 0 0.08em; display: inline-block; }
.srp-hero-headline .red  { color: var(--red); display: inline-block; padding: 0 0.05em; }
.srp-hero-deck {
  font-family: var(--sans); font-weight: 300;
  font-size: 16px; line-height: 1.55; color: var(--bone-dim);
  max-width: 480px; margin: 0 0 26px;
}
.srp-hero-meta {
  display: flex; gap: 28px; padding-top: 22px;
  border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.08em;
}
.srp-hero-meta-block { display: flex; flex-direction: column; gap: 6px; }
.srp-hero-meta-label { color: var(--gray-2); }
.srp-hero-meta-value {
  color: var(--bone); font-family: var(--sans);
  font-size: 12.5px; text-transform: none; letter-spacing: 0; font-weight: 500;
}

/* MLB comp doppel card */
.srp-doppel {
  border: 1px solid var(--line); border-radius: var(--radius);
  padding: 22px;
  background: radial-gradient(120% 80% at 100% 0%, rgba(230,69,48,0.06), transparent 60%), var(--bg-glass);
  position: relative; overflow: hidden;
}
.srp-doppel-eyebrow {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1);
  display: flex; justify-content: space-between; margin-bottom: 14px;
}
.srp-doppel-eyebrow .num { color: var(--gold); font-weight: 500; }
.srp-doppel-name {
  font-family: var(--serif); font-style: italic;
  font-size: 36px; line-height: 1; letter-spacing: -0.02em;
  color: var(--bone); margin: 8px 0 6px;
}
.srp-doppel-team {
  font-family: var(--mono); font-size: 10.5px; color: var(--gray-1);
  letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 18px;
}
.srp-doppel-score {
  display: flex; align-items: baseline; gap: 12px;
  border-top: 1px solid var(--line); padding-top: 18px;
}
.srp-doppel-score-num {
  font-family: var(--mono); font-size: 48px; font-weight: 400;
  color: var(--bone); font-feature-settings: "tnum";
  letter-spacing: -0.02em; line-height: 1;
}
.srp-doppel-score-num .pct { font-size: 20px; color: var(--gray-1); margin-left: 2px; }
.srp-doppel-score-label {
  font-family: var(--sans); font-size: 11.5px; line-height: 1.4;
  color: var(--bone-dim); max-width: 150px;
}

/* ---------- SECTION HEADERS ---------- */
.srp-section-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 56px 0 22px;
}
.srp-section-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--red);
}
.srp-section-title {
  font-family: var(--serif); font-size: 32px; font-weight: 400;
  letter-spacing: -0.01em; color: var(--bone); margin: 6px 0 0;
}
.srp-section-title .ital { font-style: italic; }
.srp-section-sub {
  font-family: var(--sans); font-size: 13px; color: var(--gray-1);
  font-weight: 400; letter-spacing: 0;
  max-width: 320px; text-align: right;
}

/* ---------- LISTS (strengths / issues / what-to-fix) ----------
   Simplified to a stacked full-width card list. The previous 3-column
   grid caused titles to wrap letter-by-letter on tablet widths. Cards
   stay full-width here so titles never break; layout reads top-down
   which matches how a parent/player would actually scan the report. */
.srp-list {
  display: flex; flex-direction: column; gap: 18px;
}
.srp-list-item {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass); padding: 28px 32px;
  display: grid;
  grid-template-columns: 100px 1fr 140px;
  gap: 28px;
  align-items: center;
  min-height: 0;
}
.srp-list-item .srp-list-num { align-self: flex-start; padding-top: 6px; }
.srp-list-item .srp-list-pill { justify-self: end; align-self: center; }
@media (max-width: 760px) {
  .srp-list-item {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 22px;
  }
  .srp-list-item .srp-list-pill { justify-self: start; }
}
.srp-list-item.is-strength {
  background:
    radial-gradient(120% 100% at 0% 0%, rgba(74,227,140,0.05), transparent 60%),
    var(--bg-glass);
}
.srp-list-item.is-issue {
  background:
    radial-gradient(120% 100% at 0% 0%, rgba(230,69,48,0.06), transparent 60%),
    var(--bg-glass);
}
.srp-list-num {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--gray-1);
}
.srp-list-item.is-strength .srp-list-num { color: var(--green); }
.srp-list-item.is-issue .srp-list-num { color: var(--red); }
.srp-list-title {
  font-family: var(--serif); font-size: 24px; font-weight: 400;
  font-style: italic; line-height: 1.15;
  color: var(--bone); margin: 0;
}
.srp-list-body {
  font-family: var(--sans); font-size: 13.5px; line-height: 1.55;
  color: var(--bone-dim); margin: 0;
}
.srp-list-pill {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.16em; text-transform: uppercase;
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: 100px;
}
.srp-list-pill.sev-high   { background: var(--red-soft); border: 1px solid rgba(230,69,48,0.32); color: var(--red); }
.srp-list-pill.sev-medium { background: var(--gold-soft); border: 1px solid rgba(232,193,112,0.32); color: var(--gold); }
.srp-list-pill.sev-low    { background: rgba(74,227,140,0.08); border: 1px solid rgba(74,227,140,0.32); color: var(--green); }

/* ---------- COACH REPORT (narrative) ---------- */
.srp-coach {
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  background:
    radial-gradient(60% 80% at 100% 0%, rgba(232,193,112,0.06), transparent 70%),
    linear-gradient(135deg, #14171d 0%, #0a0b0e 100%);
  padding: 44px 48px;
  display: grid; grid-template-columns: 220px 1fr; gap: 48px;
}
.srp-coach-rail {
  display: flex; flex-direction: column; gap: 14px;
  border-right: 1px solid var(--line);
  padding-right: 32px;
}
.srp-coach-rail-eyebrow {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--red);
}
.srp-coach-rail-by {
  font-family: var(--serif); font-style: italic;
  font-size: 22px; line-height: 1.1;
  color: var(--bone);
}
.srp-coach-rail-meta {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-2); margin-top: 6px;
}
.srp-coach-body {
  font-family: var(--serif); font-size: 22px; line-height: 1.5;
  color: var(--bone); font-weight: 400;
}
.srp-coach-body p { margin: 0 0 16px; }
.srp-coach-body p:last-child { margin: 0; }
.srp-coach-body .lead {
  font-style: italic; color: var(--gold);
}

/* ---------- DRILL PLAN ---------- */
/* Drill plan — 3 prescribed drills. Stacked, wide cards. Each drill
   gets enough room to breathe (priority/reps on the right, name +
   why in the middle, cue strip at the bottom). */
.srp-drill-grid {
  display: flex; flex-direction: column; gap: 16px;
}
.srp-drill-card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  padding: 28px 32px;
  display: grid;
  grid-template-columns: 1fr 160px;
  gap: 20px 32px;
}
.srp-drill-card .srp-drill-head {
  grid-column: 1 / -1;
  display: flex; align-items: center; justify-content: space-between;
}
.srp-drill-card .srp-drill-name { grid-column: 1 / 2; }
.srp-drill-card .srp-drill-why  { grid-column: 1 / 2; }
.srp-drill-card .srp-drill-cue  { grid-column: 1 / -1; }
@media (max-width: 760px) {
  .srp-drill-card { grid-template-columns: 1fr; gap: 14px; padding: 22px; }
}
.srp-drill-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 2px;
}
.srp-drill-priority {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  padding: 4px 9px; border-radius: 100px;
}
.srp-drill-priority.p1 { background: var(--red-soft); color: var(--red); border: 1px solid rgba(230,69,48,0.30); }
.srp-drill-priority.p2 { background: var(--gold-soft); color: var(--gold); border: 1px solid rgba(232,193,112,0.30); }
.srp-drill-priority.p3 { background: rgba(74,227,140,0.10); color: var(--green); border: 1px solid rgba(74,227,140,0.30); }
.srp-drill-reps {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; color: var(--gray-1);
}
.srp-drill-name {
  font-family: var(--serif); font-size: 22px; font-style: italic;
  font-weight: 400; line-height: 1.15; color: var(--bone);
  margin: 0;
}
.srp-drill-why {
  font-family: var(--sans); font-size: 12.5px; line-height: 1.55;
  color: var(--bone-dim); margin: 0;
}
.srp-drill-cue {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.08em; color: var(--gray-1);
  padding-top: 12px; border-top: 1px dashed var(--line);
  margin-top: auto;
}
.srp-drill-cue strong { color: var(--bone); }

/* ---------- DRILL LOG (Streamlit-native checkboxes restyled) ---------- */
.srp-drill-log {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  padding: 28px 32px;
}
.srp-drill-log [data-testid="stCheckbox"] {
  margin-bottom: 8px;
}
.srp-drill-log [data-testid="stCheckbox"] label {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  color: var(--bone-dim) !important;
}
.srp-drill-log [data-testid="stCheckbox"] label p {
  color: var(--bone-dim) !important;
}
.srp-drill-log [data-testid="stTextArea"] textarea {
  background: rgba(255,255,255,0.025) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  color: var(--bone) !important;
  font-family: var(--sans) !important;
}
.srp-drill-log [data-testid="stTextArea"] label,
.srp-drill-log [data-testid="stTextArea"] label p {
  font-family: var(--mono) !important;
  font-size: 9.5px !important;
  letter-spacing: 0.22em !important;
  color: var(--gray-1) !important;
  text-transform: uppercase !important;
}

/* ---------- PROGRESS INSIGHTS ---------- */
.srp-insights {
  display: grid; grid-template-columns: 2fr 1fr; gap: 24px;
}
.srp-trend-card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  padding: 26px 30px;
}
.srp-trend-title {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 14px;
}
.srp-spark-wrap {
  display: flex; align-items: flex-end; gap: 8px;
  height: 80px; padding: 12px 0;
}
.srp-spark-bar {
  flex: 1; background: rgba(244,239,230,0.10);
  border-radius: 3px 3px 0 0;
  transition: background 0.2s ease;
  position: relative;
}
.srp-spark-bar.current {
  background: var(--gold);
  box-shadow: 0 0 12px rgba(232,193,112,0.4);
}
.srp-spark-bar.previous {
  background: rgba(244,239,230,0.35);
}
.srp-trend-axis {
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.10em; color: var(--gray-2);
  margin-top: 10px;
}
.srp-insight-stats {
  display: grid; gap: 14px;
}
.srp-insight-stat {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  padding: 18px 22px;
}
.srp-insight-stat-label {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.22em; color: var(--gray-1);
  text-transform: uppercase; margin-bottom: 6px;
}
.srp-insight-stat-value {
  font-family: var(--serif); font-size: 32px; font-weight: 400;
  color: var(--bone); line-height: 1; letter-spacing: -0.02em;
}
.srp-insight-stat-value.is-up { color: var(--green); }
.srp-insight-stat-value.is-down { color: var(--red); }
.srp-insight-stat-value.is-flat { color: var(--bone); }
.srp-insight-stat-meta {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.10em; color: var(--gray-2); margin-top: 6px;
}

/* ---------- PREMIUM METRIC CARDS ---------- */
/* Premium metric cards — stay 2-up on wide viewports for comparison
   scanability, but each card has more padding + a min-width so the
   label never wraps letter-by-letter. */
.srp-metric-grid {
  display: grid; grid-template-columns: repeat(2, minmax(360px, 1fr));
  gap: 18px;
}
@media (max-width: 900px) {
  .srp-metric-grid { grid-template-columns: 1fr; }
}
.srp-metric-card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  padding: 24px 28px;
  display: grid; grid-template-columns: 1fr 100px; gap: 22px;
  align-items: center;
  min-width: 0;
}
.srp-metric-card-label {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.20em; color: var(--gray-1);
  text-transform: uppercase; margin-bottom: 8px;
}
.srp-metric-card-row {
  display: flex; align-items: baseline; gap: 12px;
  font-family: var(--sans);
}
.srp-metric-card-you {
  font-family: var(--serif); font-style: italic;
  font-size: 26px; font-weight: 400; line-height: 1;
  color: var(--bone);
}
.srp-metric-card-ref {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.04em; color: var(--gray-1);
}
.srp-metric-card-bar {
  height: 6px; background: rgba(244,239,230,0.06);
  border-radius: 3px; overflow: hidden;
  margin-top: 10px;
}
.srp-metric-card-bar .fill {
  display: block; height: 100%;
  background: linear-gradient(90deg, var(--gold), var(--red));
  border-radius: 3px;
}
.srp-metric-card-match {
  font-family: var(--mono); font-size: 26px;
  color: var(--gold); font-feature-settings: "tnum";
  text-align: right; line-height: 1;
}
.srp-metric-card-match .pct {
  font-size: 11px; color: var(--gray-1); margin-left: 1px;
  letter-spacing: 0.04em;
}
.srp-metric-card-match.is-low  { color: var(--red); }
.srp-metric-card-match.is-mid  { color: var(--amber); }
.srp-metric-card-match.is-high { color: var(--green); }

/* ---------- COMPARISON ---------- */
.srp-compare {
  margin-top: 28px;
  padding: 38px 42px 34px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background:
    radial-gradient(60% 80% at 100% 0%, rgba(230,69,48,0.07), transparent 70%),
    linear-gradient(135deg, #14171d 0%, #0a0b0e 100%);
}
.srp-compare-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 28px; flex-wrap: wrap; gap: 18px;
}
.srp-compare-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--red);
}
.srp-compare-title {
  font-family: var(--serif); font-size: 36px; font-weight: 400;
  line-height: 1; color: var(--bone); margin-top: 6px;
}
.srp-compare-title .ital { font-style: italic; }
.srp-compare-sub {
  font-family: var(--sans); font-size: 13.5px;
  color: var(--bone-dim); line-height: 1.55;
  max-width: 480px;
}
.srp-compare-realdata {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gold);
  padding: 5px 12px; border-radius: 100px;
  border: 1px solid rgba(232,193,112,0.32);
  background: var(--gold-soft);
}
/* Comparison grid — wider columns, more breathing room. Min-width
   keeps each card readable; delta orb in the middle. Collapses to
   stacked layout below 900px. */
.srp-compare-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 120px minmax(260px, 1fr);
  align-items: stretch; gap: 24px;
}
@media (max-width: 900px) {
  .srp-compare-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .srp-compare-grid .srp-compare-delta { order: 2; height: 80px; }
  .srp-compare-grid .srp-compare-col:nth-child(1) { order: 1; }
  .srp-compare-grid .srp-compare-col:nth-child(3) { order: 3; }
}
.srp-compare-col {
  border: 1px solid var(--line); border-radius: var(--radius);
  padding: 32px 36px;
  background: var(--bg-glass);
  min-width: 0;
}
.srp-compare-col.is-current {
  border-color: rgba(230,69,48,0.38);
  background:
    radial-gradient(120% 100% at 100% 0%, rgba(230,69,48,0.08), transparent 70%),
    var(--bg-glass);
}
.srp-compare-col-eyebrow {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 8px;
}
.srp-compare-col-eyebrow.is-current { color: var(--red); }
.srp-compare-col-title {
  font-family: var(--serif); font-style: italic;
  font-size: 22px; font-weight: 400;
  color: var(--bone); margin-bottom: 18px;
}
.srp-compare-col-score {
  font-family: var(--serif); font-size: 64px; font-weight: 400;
  line-height: 0.9; letter-spacing: -0.03em; color: var(--bone);
}
.srp-compare-col-score .of {
  font-family: var(--mono); font-size: 14px;
  color: var(--gray-1); margin-left: 4px; vertical-align: top;
}
.srp-compare-col-mlb {
  font-family: var(--sans); font-size: 13px;
  color: var(--bone-dim); margin-top: 14px;
}
.srp-compare-col-date {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; color: var(--gray-2); margin-top: 10px;
  text-transform: uppercase;
}
.srp-compare-delta {
  display: flex; align-items: center; justify-content: center;
}
.srp-compare-delta-inner {
  width: 110px; height: 110px; border-radius: 50%;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  font-family: var(--mono);
  border: 1px solid var(--line-hi);
  background: rgba(10,11,14,0.7);
}
.srp-compare-delta-arrow { font-size: 22px; line-height: 1; }
.srp-compare-delta-value { font-size: 20px; font-weight: 500; margin-top: 2px; }
.srp-compare-delta-label {
  font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 6px;
}
.srp-compare-delta-inner.up    { color: var(--green); border-color: rgba(74,227,140,0.45); }
.srp-compare-delta-inner.down  { color: var(--red); border-color: rgba(230,69,48,0.45); }
.srp-compare-delta-inner.flat  { color: var(--bone-dim); }

.srp-compare-rows {
  margin-top: 22px;
  display: grid; gap: 8px;
}
.srp-compare-row {
  display: grid;
  grid-template-columns: 220px 1fr 60px 1fr 100px;
  align-items: center; gap: 14px;
  padding: 14px 18px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--line-lo);
  background: rgba(255,255,255,0.015);
}
.srp-compare-row-label {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; color: var(--gray-1);
  text-transform: uppercase;
}
.srp-compare-row-prev,
.srp-compare-row-curr {
  font-family: var(--sans); font-size: 14px; font-weight: 500;
  color: var(--bone-dim);
}
.srp-compare-row-curr { color: var(--bone); font-weight: 600; }
.srp-compare-row-arrow {
  font-family: var(--mono); font-size: 11px; color: var(--gray-2);
  text-align: center;
}
.srp-compare-row-delta {
  font-family: var(--mono); font-size: 12px; font-weight: 600;
  text-align: right;
}
.srp-compare-row-delta.up   { color: var(--green); }
.srp-compare-row-delta.down { color: var(--red); }
.srp-compare-row-delta.flat { color: var(--gray-1); }

.srp-compare-empty {
  padding: 64px 36px;
  text-align: center;
  border: 1px dashed var(--line-hi);
  border-radius: var(--radius);
  background: var(--bg-glass);
}
.srp-compare-empty-icon {
  font-family: var(--serif); font-style: italic;
  font-size: 56px; color: var(--gold); opacity: 0.7;
  margin-bottom: 14px;
}
.srp-compare-empty-title {
  font-family: var(--serif); font-style: italic;
  font-size: 28px; color: var(--bone); margin-bottom: 12px;
}
.srp-compare-empty-body {
  font-family: var(--sans); font-size: 14px;
  color: var(--bone-dim); line-height: 1.6;
  max-width: 460px; margin: 0 auto;
}

/* ---------- PREVIEW BANNER ---------- */
.srp-preview-banner {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 22px; margin: 0 0 24px;
  background: rgba(232,193,112,0.06);
  border: 1px solid rgba(232,193,112,0.22);
  border-radius: var(--radius-sm);
}
.srp-preview-banner-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--gold);
  box-shadow: 0 0 12px var(--gold);
}
.srp-preview-banner-text {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--gold);
}
.srp-preview-banner-text .em {
  font-family: var(--serif); font-style: italic;
  font-size: 13px; text-transform: none;
  letter-spacing: 0; color: var(--bone-dim);
  margin-left: 8px;
}

/* ---------- RESPONSIVE ---------- */
@media (max-width: 1200px) {
  .srp-hero { grid-template-columns: 1fr 1.2fr; }
  .srp-hero .srp-score-wrap { grid-column: 1 / 2; }
  .srp-hero .srp-doppel { display: none; }
  .srp-hero-headline { font-size: 60px; }
}
@media (max-width: 900px) {
  .srp-hero { grid-template-columns: 1fr; gap: 28px; }
  .srp-hero-headline { font-size: 48px; }
  .srp-list { grid-template-columns: 1fr; }
  .srp-drill-grid { grid-template-columns: 1fr; }
  .srp-coach { grid-template-columns: 1fr; gap: 24px; padding: 28px; }
  .srp-coach-rail { border-right: none; border-bottom: 1px solid var(--line); padding-right: 0; padding-bottom: 20px; }
  .srp-insights { grid-template-columns: 1fr; }
  .srp-metric-grid { grid-template-columns: 1fr; }
  .srp-compare-grid { grid-template-columns: 1fr; }
  .srp-compare-delta { order: 2; height: 70px; }
  .srp-compare-delta-inner { width: 70px; height: 70px; }
  .srp-compare-row { grid-template-columns: 1fr 1fr; }
  .srp-compare-row-arrow { display: none; }
  .srp-compare-row-label { grid-column: 1 / -1; }
}
</style>
"""


# =====================================================================
#  Score ring SVG (matches mock_dashboard_template style)
# =====================================================================
def _score_ring_svg(score: Optional[float], *, size: int = 220) -> str:
    """Return an SVG string for the Edge score ring."""
    if score is None:
        score_text = "—"
        pct = 0
    else:
        try:
            score_text = f"{int(round(float(score)))}"
            pct = max(0, min(100, float(score)))
        except (TypeError, ValueError):
            score_text = "—"
            pct = 0

    cx = cy = size / 2
    r = (size - 24) / 2
    circ = 2 * math.pi * r
    fill = circ * (pct / 100.0)
    rest = circ - fill
    # Rotate so the arc starts from the top (12 o'clock)
    rot = -90

    return f"""
    <svg class="srp-score-svg" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg"
         width="{size}" height="{size}">
      <defs>
        <linearGradient id="srp-ring-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stop-color="#E8C170"/>
          <stop offset="100%" stop-color="#E64530"/>
        </linearGradient>
      </defs>
      <circle cx="{cx}" cy="{cy}" r="{r}"
              fill="none" stroke="rgba(244,239,230,0.07)"
              stroke-width="3"/>
      <circle cx="{cx}" cy="{cy}" r="{r}"
              fill="none" stroke="url(#srp-ring-grad)"
              stroke-width="3"
              stroke-linecap="round"
              stroke-dasharray="{fill:.1f} {rest:.1f}"
              transform="rotate({rot} {cx} {cy})"/>
      <text x="{cx}" y="{cy + 4}"
            text-anchor="middle"
            font-family="Instrument Serif, serif"
            font-size="68"
            fill="#F4EFE6">{score_text}</text>
      <text x="{cx}" y="{cy + 30}"
            text-anchor="middle"
            font-family="Geist Mono, monospace"
            font-size="10"
            letter-spacing="2"
            fill="#8B8E94">/100</text>
    </svg>
    """


# =====================================================================
#  Real-data extraction helpers
# =====================================================================
def _fmt_date(rec: Dict[str, Any]) -> str:
    for key in ("timestamp", "created_at", "date"):
        v = rec.get(key)
        if not v:
            continue
        if isinstance(v, datetime):
            return v.strftime("%b %d · %Y")
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).strftime("%b %d · %Y")
            except Exception:
                return v[:10]
    return "—"


def _swing_label(rec: Dict[str, Any]) -> str:
    n = rec.get("swing_number")
    try:
        return f"Swing #{int(n):02d}"
    except Exception:
        return "Swing"


def _score(rec: Dict[str, Any]) -> Optional[float]:
    s = rec.get("score")
    if s is None:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _mlb_ref(rec: Dict[str, Any]) -> str:
    raw = str(rec.get("reference_name") or "—").replace("_", " ").strip()
    if not raw or raw == "—":
        return "—"
    return raw.title()


def _categories(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract per-axis category scores from a record if available.
    Returns a list of {label, value, peak} dicts."""
    mt = rec.get("metric_table") or {}
    out = []
    if isinstance(mt, dict):
        for cat_name, rows in mt.items():
            if not isinstance(rows, list) or not rows:
                continue
            vals = []
            for r in rows:
                if isinstance(r, dict) and r.get("sim_pct") is not None:
                    try:
                        vals.append(float(r["sim_pct"]))
                    except (TypeError, ValueError):
                        continue
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            out.append({"label": cat_name, "value": int(round(avg))})
    # mark the highest as peak
    if out:
        best = max(out, key=lambda d: d["value"])
        for d in out:
            d["peak"] = (d is best)
    return out[:6]


def _metrics_flat(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten metric_table into a list of {label, you, ref, match} rows."""
    mt = rec.get("metric_table") or {}
    rows: List[Dict[str, Any]] = []
    if not isinstance(mt, dict):
        return rows
    for cat, items in mt.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            label = it.get("label") or cat
            you = it.get("player_str") or it.get("you")
            ref = it.get("ref_str") or it.get("ref")
            match = it.get("sim_pct")
            if you is None and ref is None and match is None:
                continue
            try:
                match_v = int(round(float(match))) if match is not None else None
            except (TypeError, ValueError):
                match_v = None
            rows.append({
                "label": str(label), "you": str(you) if you is not None else "—",
                "ref": str(ref) if ref is not None else "—",
                "match": match_v,
            })
    return rows[:8]


def _drills_flat(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten drill_plan into a list of {name, priority, reps, why, cue}."""
    dp = rec.get("drill_plan") or {}
    out: List[Dict[str, Any]] = []
    if not isinstance(dp, dict):
        return out
    p = 1
    for cat, drills in dp.items():
        if not isinstance(drills, list):
            continue
        for d in drills:
            if not isinstance(d, dict):
                continue
            out.append({
                "name": d.get("name", "Drill"),
                "priority": d.get("priority", p),
                "reps": d.get("reps", "3 × 10"),
                "why": d.get("why") or d.get("description")
                       or f"Targets {cat.replace('_', ' ')}.",
                "cue": d.get("cue") or f"Cat: {cat.replace('_', ' ').title()}",
            })
            p += 1
            if len(out) >= 3:
                break
        if len(out) >= 3:
            break
    return out[:3]


def _previous_record(curr: Dict[str, Any], history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not history:
        return None
    cur_id = curr.get("id")
    cur_ts = curr.get("timestamp") or curr.get("created_at")
    cur_num = curr.get("swing_number")
    idx = None
    for i, rec in enumerate(history):
        if cur_id and rec.get("id") == cur_id:
            idx = i; break
        if cur_ts and (rec.get("timestamp") or rec.get("created_at")) == cur_ts:
            idx = i; break
        if cur_num is not None and rec.get("swing_number") == cur_num:
            idx = i; break
    if idx is None or idx == 0:
        return None
    return history[idx - 1]


def _synthetic_record(swing_number: int = 7) -> Dict[str, Any]:
    """A rich synthetic swing record so every report section has visible
    content during preview. Marked as sample data via the banner."""
    return {
        "id": f"preview-swing-{swing_number}",
        "swing_number": swing_number,
        "score": 78,
        "timestamp": datetime.now().isoformat(),
        "reference_name": "Mookie Betts",
        "filename": "tournament_round_3.mp4",
        "narratives": [
            {"title": "Hip-shoulder separation timing",
             "body": "You're firing the hips a touch before the front side fully blocks. Tightening this delay would unlock another 4 mph of bat speed."},
            {"title": "Head drift through contact",
             "body": "Your head moves ~3.2 inches forward from load to contact. Elite hitters hold their gaze still through the ball."},
            {"title": "Front-knee re-extension",
             "body": "The front leg posts up well, but the rebound (re-extension) is light. Get firmer there and you'll pour more energy into the barrel."},
        ],
        "drill_plan": {
            "hip_shoulder_separation": [
                {"name": "Foot-up step",
                 "priority": 1,
                 "reps": "3 × 8",
                 "why": "Forces the front side to block while the hips keep firing. Builds the gap.",
                 "cue": "Plant. Then turn."},
            ],
            "head_stability": [
                {"name": "Towel-over-head dry swings",
                 "priority": 2,
                 "reps": "3 × 10",
                 "why": "Eliminates extra head movement so your eyes stay on the contact zone.",
                 "cue": "Towel stays put."},
            ],
            "knee_extension": [
                {"name": "Plyo-ball heavy lead",
                 "priority": 3,
                 "reps": "3 × 6",
                 "why": "Trains a quicker, more violent re-extension on the front side.",
                 "cue": "Punch the ground."},
            ],
        },
        "metric_table": {
            "Rotation": [
                {"label": "Peak hip-shoulder separation",
                 "sim_pct": 76, "player_str": "42°", "ref_str": "44°"},
                {"label": "Hip rotation at contact",
                 "sim_pct": 78, "player_str": "52°", "ref_str": "54°"},
            ],
            "Timing": [
                {"label": "Launch to contact ms",
                 "sim_pct": 75, "player_str": "184 ms", "ref_str": "175 ms"},
                {"label": "Total swing duration",
                 "sim_pct": 81, "player_str": "1,124 ms", "ref_str": "1,160 ms"},
            ],
            "Front Knee": [
                {"label": "Knee re-extension",
                 "sim_pct": 70, "player_str": "24°", "ref_str": "28°"},
            ],
            "Head": [
                {"label": "Head total drift",
                 "sim_pct": 72, "player_str": "0.18", "ref_str": "0.15"},
            ],
        },
    }


# =====================================================================
#  Section renderers
# =====================================================================
def _render_hero(rec: Dict[str, Any]) -> None:
    score = _score(rec)
    score_svg = _score_ring_svg(score, size=220)
    cats = _categories(rec)
    if not cats:
        cats = [
            {"label": "Rotation", "value": 76, "peak": False},
            {"label": "Timing",   "value": 78, "peak": True},
            {"label": "Front side","value": 70,"peak": False},
            {"label": "Head",     "value": 72, "peak": False},
        ]
    cats_html = "\n".join(
        f"""
        <div class="srp-cat-row">
          <span>{html.escape(str(c['label']))}</span>
          <span class="v {'peak' if c.get('peak') else ''}">{c['value']}</span>
        </div>
        """
        for c in cats[:4]
    )

    mlb = _mlb_ref(rec)
    swing_label = _swing_label(rec)
    date_disp = _fmt_date(rec)
    filename = str(rec.get("filename") or "—")

    # MLB doppel card (right rail of hero)
    doppel_score = score if score is not None else None
    mlb_match_text = f"{int(round(doppel_score))}" if doppel_score is not None else "—"

    _html(f"""
        <section class="srp-hero">
          <div class="srp-score-wrap">
            {score_svg}
            <div class="srp-score-label">Edge Score</div>
            <div class="srp-score-cats">
              {cats_html}
            </div>
          </div>

          <div>
            <div class="srp-hero-eyebrow">
              <span class="swatch"></span>{html.escape(swing_label.upper())}
            </div>
            <h1 class="srp-hero-headline">
              An <span class="ital">elite</span> shape,<br>
              built around <span class="red">timing.</span>
            </h1>
            <p class="srp-hero-deck">
              This swing matches your peak MLB comp on rotation and
              tempo. Fix the head-drift and the firmness on the front
              side and you're in the top decile for your age group.
            </p>
            <div class="srp-hero-meta">
              <div class="srp-hero-meta-block">
                <span class="srp-hero-meta-label">Date</span>
                <span class="srp-hero-meta-value">{html.escape(date_disp)}</span>
              </div>
              <div class="srp-hero-meta-block">
                <span class="srp-hero-meta-label">Source</span>
                <span class="srp-hero-meta-value">{html.escape(filename)}</span>
              </div>
              <div class="srp-hero-meta-block">
                <span class="srp-hero-meta-label">Status</span>
                <span class="srp-hero-meta-value">Analyzed · Saved</span>
              </div>
            </div>
          </div>

          <div class="srp-doppel">
            <div class="srp-doppel-eyebrow">
              <span>MLB COMP</span><span class="num">§02</span>
            </div>
            <div class="srp-doppel-name">{html.escape(mlb)}</div>
            <div class="srp-doppel-team">Right-handed · Contact-power profile</div>
            <div class="srp-doppel-score">
              <div class="srp-doppel-score-num">{mlb_match_text}<span class="pct">%</span></div>
              <div class="srp-doppel-score-label">Pose-fingerprint similarity across 5 biomechanical axes.</div>
            </div>
          </div>
        </section>
        """)


def _render_section_head(eyebrow: str, title: str, ital: str = "", sub: str = "") -> None:
    sub_html = f'<div class="srp-section-sub">{html.escape(sub)}</div>' if sub else ""
    title_html = title
    if ital:
        title_html = f"{html.escape(title)} <span class=\"ital\">{html.escape(ital)}</span>"
    else:
        title_html = html.escape(title)
    _html(f"""
        <div class="srp-section-head">
          <div>
            <div class="srp-section-eyebrow">{html.escape(eyebrow)}</div>
            <h2 class="srp-section-title">{title_html}</h2>
          </div>
          {sub_html}
        </div>
        """)


def _render_strengths(rec: Dict[str, Any]) -> None:
    _render_section_head("§03 STRENGTHS", "What's", "working.",
                         sub="The mechanics already firing — keep them, don't fix them.")
    # Derive from categories + a default fallback
    cats = _categories(rec)
    items = []
    for c in cats:
        if c["value"] >= 75:
            items.append({
                "title": f"{c['label']} is locked in",
                "body": f"You're hitting {c['value']}% on this axis — strong, repeatable, and at MLB-comp tolerances.",
            })
    while len(items) < 3:
        defaults = [
            {"title": "Tempo holds at speed",
             "body": "Your launch-to-contact rhythm stays consistent through full-effort swings."},
            {"title": "Hand path stays connected",
             "body": "The barrel tracks behind the back shoulder cleanly — no early casting."},
            {"title": "Lower-half initiates first",
             "body": "Hips fire before the hands every time — the kinetic chain order is correct."},
        ]
        items.append(defaults[len(items) % 3])
    items = items[:3]
    cards = ""
    for i, it in enumerate(items, start=1):
        cards += f"""
        <div class="srp-list-item is-strength">
          <div class="srp-list-num">{i:02d} · STRENGTH</div>
          <h3 class="srp-list-title">{html.escape(it['title'])}</h3>
          <p class="srp-list-body">{html.escape(it['body'])}</p>
          <span class="srp-list-pill sev-low">Keep · Repeat</span>
        </div>
        """
    _html(f'<div class="srp-list">{cards}</div>')


def _render_issues(rec: Dict[str, Any]) -> None:
    _render_section_head("§04 ISSUES", "What's", "leaking.",
                         sub="The three mechanics most worth your next two weeks.")
    narratives = rec.get("narratives") or []
    items = []
    severities = ["sev-high", "sev-medium", "sev-medium"]
    for i, n in enumerate(narratives[:3]):
        if not isinstance(n, dict):
            continue
        items.append({
            "title": str(n.get("title", "Mechanical issue")),
            "body": str(n.get("body") or n.get("description") or
                       "Targeted drill prescribed below to close this gap."),
            "sev": severities[i] if i < 3 else "sev-medium",
        })
    while len(items) < 3:
        defaults = [
            {"title": "Hip-shoulder separation timing",
             "body": "You're firing the hips a touch early. Tightening this delay unlocks more bat speed.",
             "sev": "sev-high"},
            {"title": "Head drift through contact",
             "body": "Head moves forward more than ideal. Elite hitters hold their gaze still.",
             "sev": "sev-medium"},
            {"title": "Front-knee re-extension",
             "body": "Re-extension is light. Get firmer and pour more energy into the barrel.",
             "sev": "sev-medium"},
        ]
        items.append(defaults[len(items) % 3])
    items = items[:3]
    cards = ""
    for i, it in enumerate(items, start=1):
        sev = it["sev"]
        sev_label = {"sev-high": "High priority",
                     "sev-medium": "Medium",
                     "sev-low": "Polish"}.get(sev, "Medium")
        cards += f"""
        <div class="srp-list-item is-issue">
          <div class="srp-list-num">{i:02d} · ISSUE</div>
          <h3 class="srp-list-title">{html.escape(it['title'])}</h3>
          <p class="srp-list-body">{html.escape(it['body'])}</p>
          <span class="srp-list-pill {sev}">{html.escape(sev_label)}</span>
        </div>
        """
    _html(f'<div class="srp-list">{cards}</div>')


def _render_coach_report(rec: Dict[str, Any]) -> None:
    _render_section_head("§05 COACH REPORT", "The", "read.",
                         sub="A two-minute coach assessment in plain English.")
    narr = rec.get("narratives") or []
    if narr and isinstance(narr[0], dict):
        lead = narr[0].get("body") or narr[0].get("title") or ""
    else:
        lead = ("This is a swing that already moves at MLB-comp tolerances on "
                "rotation and tempo. Two adjustments would put it in elite range.")
    body_paras = []
    for n in narr[1:3]:
        if isinstance(n, dict):
            body_paras.append(n.get("body") or n.get("title") or "")
    if not body_paras:
        body_paras = [
            "First — quiet the head. You're moving forward ~3 inches through "
            "contact. Towel-over-head dry swings for ten minutes a day will "
            "shut that down inside a week.",
            "Second — firmness on the front side. The leg posts but doesn't "
            "rebound. Get heavier with the lead leg in the next BP block and "
            "you'll feel the bat finish higher and faster.",
        ]
    paras_html = "\n".join(f"<p>{html.escape(p)}</p>" for p in body_paras if p)
    _html(f"""
        <div class="srp-coach">
          <div class="srp-coach-rail">
            <div class="srp-coach-rail-eyebrow">COACH NOTE</div>
            <div class="srp-coach-rail-by">BarrelLabs SwingAI</div>
            <div class="srp-coach-rail-meta">v3 · TRAINED ON MLB POSE LIBRARY</div>
          </div>
          <div class="srp-coach-body">
            <p class="lead">{html.escape(lead)}</p>
            {paras_html}
          </div>
        </div>
        """)


def _render_what_to_fix(rec: Dict[str, Any]) -> None:
    _render_section_head("§06 WHAT TO FIX", "In", "priority order.",
                         sub="The fix-order matters. Top of the list is closest to MLB-comp baseline.")
    narratives = rec.get("narratives") or []
    items = []
    for n in narratives[:3]:
        if isinstance(n, dict):
            items.append(str(n.get("title", "Mechanical fix")))
    while len(items) < 3:
        defaults = ["Quiet the head through contact",
                    "Tighten hip-shoulder separation timing",
                    "Stiffen front-leg re-extension"]
        items.append(defaults[len(items) % 3])
    items = items[:3]
    rows = ""
    for i, t in enumerate(items, start=1):
        rows += f"""
        <div style="display:grid;grid-template-columns:80px 1fr auto;align-items:center;
                    gap:24px;padding:22px 0;border-bottom:1px solid var(--line);">
          <div style="font-family:var(--serif);font-style:italic;font-size:42px;color:var(--red);line-height:1;">{i:02d}</div>
          <div>
            <div style="font-family:var(--serif);font-style:italic;font-size:24px;color:var(--bone);line-height:1.15;">
              {html.escape(t)}
            </div>
            <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:0.16em;
                        color:var(--gray-1);text-transform:uppercase;margin-top:6px;">
              See drill plan §07
            </div>
          </div>
          <div style="font-family:var(--mono);font-size:10.5px;letter-spacing:0.18em;
                      color:var(--gold);text-transform:uppercase;">
            FIX FIRST →
          </div>
        </div>
        """
    _html(f"""
        <div style="border-top:1px solid var(--line);">{rows}</div>
        """)


def _render_drill_plan(rec: Dict[str, Any]) -> None:
    _render_section_head("§07 DRILL PLAN", "Two", "weeks of work.",
                         sub="Three drills mapped to the three issues above.")
    drills = _drills_flat(rec)
    if not drills:
        drills = _drills_flat(_synthetic_record())
    cards = ""
    for d in drills:
        p = d.get("priority", 2)
        try:
            p_class = f"p{min(3, int(p))}"
        except Exception:
            p_class = "p2"
        cards += f"""
        <div class="srp-drill-card">
          <div class="srp-drill-head">
            <span class="srp-drill-priority {p_class}">Priority · 0{p_class[1]}</span>
            <span class="srp-drill-reps">{html.escape(str(d.get('reps','3 × 10')))}</span>
          </div>
          <h3 class="srp-drill-name">{html.escape(str(d.get('name','Drill')))}</h3>
          <p class="srp-drill-why">{html.escape(str(d.get('why','')))}</p>
          <div class="srp-drill-cue"><strong>Cue ·</strong> {html.escape(str(d.get('cue','')))}</div>
        </div>
        """
    _html(f'<div class="srp-drill-grid">{cards}</div>')


def _render_drill_log(rec: Dict[str, Any]) -> None:
    _render_section_head("§08 DRILL LOG", "Check", "your work.",
                         sub="Mark drills done and leave a note for your next swing.")
    drills = _drills_flat(rec) or _drills_flat(_synthetic_record())
    _html('<div class="srp-drill-log">')
    for i, d in enumerate(drills):
        st.checkbox(
            f"{d.get('name', 'Drill')} — {d.get('reps', '')}",
            key=f"srpv_drill_{i}_{rec.get('id', 'preview')}",
            value=False,
        )
    st.text_area(
        "Coach note · how it felt",
        key=f"srpv_note_{rec.get('id', 'preview')}",
        placeholder="Quick note for next time you review this swing…",
        height=80,
    )
    _html('</div>')


def _render_progress_insights(rec: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    _render_section_head("§09 PROGRESS", "The", "arc.",
                         sub="This swing in the context of every swing before it.")
    # Build sparkline from history scores (up to last 12)
    scores: List[float] = []
    for r in (history or [])[-12:]:
        try:
            scores.append(float(r.get("score") or 0))
        except (TypeError, ValueError):
            continue
    if not scores:
        scores = [62, 64, 68, 70, 72, 69, 73, 75, 74, 76, 75, 78]
    cur_score = _score(rec) or scores[-1]
    max_s = max(scores + [cur_score, 100])
    bars_html = ""
    for i, s in enumerate(scores):
        h = max(6, int(round((s / max_s) * 70)))
        cls = "current" if i == len(scores) - 1 else "previous"
        bars_html += f'<div class="srp-spark-bar {cls}" style="height:{h}px" title="{int(s)}"></div>'

    avg = sum(scores) / len(scores) if scores else 0
    best = max(scores) if scores else 0
    delta = cur_score - (scores[-2] if len(scores) >= 2 else cur_score)
    delta_cls = "is-up" if delta > 0 else ("is-down" if delta < 0 else "is-flat")
    delta_arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    delta_txt = f"{delta_arrow} {abs(delta):.1f}"

    _html(f"""
        <div class="srp-insights">
          <div class="srp-trend-card">
            <div class="srp-trend-title">EDGE SCORE · LAST {len(scores)} SWINGS</div>
            <div class="srp-spark-wrap">{bars_html}</div>
            <div class="srp-trend-axis">
              <span>{len(scores)} ago</span><span>This swing</span>
            </div>
          </div>
          <div class="srp-insight-stats">
            <div class="srp-insight-stat">
              <div class="srp-insight-stat-label">Vs. previous swing</div>
              <div class="srp-insight-stat-value {delta_cls}">{delta_txt}</div>
              <div class="srp-insight-stat-meta">Score delta</div>
            </div>
            <div class="srp-insight-stat">
              <div class="srp-insight-stat-label">Trailing average</div>
              <div class="srp-insight-stat-value">{avg:.0f}</div>
              <div class="srp-insight-stat-meta">{len(scores)} swings</div>
            </div>
            <div class="srp-insight-stat">
              <div class="srp-insight-stat-label">Personal best</div>
              <div class="srp-insight-stat-value">{best:.0f}</div>
              <div class="srp-insight-stat-meta">All-time</div>
            </div>
          </div>
        </div>
        """)


def _render_metric_cards(rec: Dict[str, Any]) -> None:
    _render_section_head("§10 METRICS", "Per-axis", "detail.",
                         sub="Every measurable, side-by-side with your MLB comp.")
    rows = _metrics_flat(rec)
    if not rows:
        rows = _metrics_flat(_synthetic_record())
    cards = ""
    for r in rows:
        match = r.get("match")
        match_str = f"{match}<span class=\"pct\">%</span>" if match is not None else "—"
        match_cls = "is-low" if match is not None and match < 60 else \
                    "is-mid" if match is not None and match < 80 else "is-high"
        bar_pct = max(0, min(100, match)) if match is not None else 0
        cards += f"""
        <div class="srp-metric-card">
          <div>
            <div class="srp-metric-card-label">{html.escape(r['label'])}</div>
            <div class="srp-metric-card-row">
              <span class="srp-metric-card-you">{html.escape(r['you'])}</span>
              <span class="srp-metric-card-ref">vs. {html.escape(r['ref'])}</span>
            </div>
            <div class="srp-metric-card-bar"><span class="fill" style="width:{bar_pct}%"></span></div>
          </div>
          <div class="srp-metric-card-match {match_cls}">{match_str}</div>
        </div>
        """
    _html(f'<div class="srp-metric-grid">{cards}</div>')


def _render_compare(current: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    _render_section_head("§11 COMPARISON", "Vs.", "previous swing.",
                         sub="Real data only — missing axes are silently omitted.")
    previous = _previous_record(current, history)

    _html('<div class="srp-compare">')
    _html("""
        <div class="srp-compare-head">
          <div>
            <div class="srp-compare-eyebrow">PROGRESS · DELTA</div>
            <h2 class="srp-compare-title">Swing <span class="ital">comparison.</span></h2>
            <p class="srp-compare-sub">
              How this swing stacks up against your last. Score cards
              are side-by-side, per-axis rows show only the metrics
              present in both records.
            </p>
          </div>
          <span class="srp-compare-realdata">Real data only</span>
        </div>
        """)

    if previous is None:
        _html("""
            <div class="srp-compare-empty">
              <div class="srp-compare-empty-icon">◇</div>
              <div class="srp-compare-empty-title">First swing — nothing to compare against yet.</div>
              <div class="srp-compare-empty-body">
                Upload another clip from the Dashboard and side-by-side
                progress will appear here automatically.
              </div>
            </div>
            """)
        _html('</div>')
        return

    cur_score = _score(current)
    prev_score = _score(previous)
    delta = (cur_score - prev_score) if (cur_score is not None and prev_score is not None) else None
    if delta is None or abs(delta) < 0.5:
        d_cls = "flat"; d_arrow = "→"; d_val = "±0"
    elif delta > 0:
        d_cls = "up"; d_arrow = "↑"; d_val = f"+{delta:.0f}"
    else:
        d_cls = "down"; d_arrow = "↓"; d_val = f"{delta:.0f}"

    def _col(rec, score, is_current):
        cls = "srp-compare-col is-current" if is_current else "srp-compare-col"
        ecls = "srp-compare-col-eyebrow is-current" if is_current else "srp-compare-col-eyebrow"
        label = "THIS SWING" if is_current else "PREVIOUS SWING"
        score_txt = f"{int(round(score))}" if score is not None else "—"
        return f"""
        <div class="{cls}">
          <div class="{ecls}">{label}</div>
          <div class="srp-compare-col-title">{html.escape(_swing_label(rec))}</div>
          <div class="srp-compare-col-score">{score_txt}<span class="of">/100</span></div>
          <div class="srp-compare-col-mlb">vs. {html.escape(_mlb_ref(rec))}</div>
          <div class="srp-compare-col-date">{html.escape(_fmt_date(rec))}</div>
        </div>
        """

    _html(f"""
        <div class="srp-compare-grid">
          {_col(previous, prev_score, False)}
          <div class="srp-compare-delta">
            <div class="srp-compare-delta-inner {d_cls}">
              <span class="srp-compare-delta-arrow">{d_arrow}</span>
              <span class="srp-compare-delta-value">{d_val}</span>
              <span class="srp-compare-delta-label">SCORE</span>
            </div>
          </div>
          {_col(current, cur_score, True)}
        </div>
        """)

    # Per-axis comparison rows — real data only
    cur_metrics = {r["label"]: r for r in _metrics_flat(current)}
    prev_metrics = {r["label"]: r for r in _metrics_flat(previous)}
    common = [lbl for lbl in cur_metrics if lbl in prev_metrics]
    rows_html = ""
    for lbl in common[:6]:
        cv = cur_metrics[lbl].get("match")
        pv = prev_metrics[lbl].get("match")
        if cv is None or pv is None:
            continue
        d = cv - pv
        if d > 0.5:
            dc = "up"; arrow = "↑"; dtxt = f"+{d:.0f}%"
        elif d < -0.5:
            dc = "down"; arrow = "↓"; dtxt = f"{d:.0f}%"
        else:
            dc = "flat"; arrow = "→"; dtxt = "±0"
        rows_html += f"""
        <div class="srp-compare-row">
          <div class="srp-compare-row-label">{html.escape(lbl)}</div>
          <div class="srp-compare-row-prev">{pv}%</div>
          <div class="srp-compare-row-arrow">→</div>
          <div class="srp-compare-row-curr">{cv}%</div>
          <div class="srp-compare-row-delta {dc}">{arrow} {dtxt}</div>
        </div>
        """
    if rows_html:
        _html(f'<div class="srp-compare-rows">{rows_html}</div>')

    _html('</div>')


# =====================================================================
#  Main page entry
# =====================================================================
def render_swing_report_preview(user: Optional[Dict[str, Any]] = None) -> None:
    """Phase 1 preview-only individual swing report. Reachable at
    /?page=swing_report_preview. No production behavior change."""

    render_edge_masthead(user or {}, active_page="swing_report")
    render_edge_page_wrapper_open()
    st.markdown(_EDGE_TOKENS_CSS, unsafe_allow_html=True)
    st.markdown(_SRP_CSS, unsafe_allow_html=True)

    # ---- Resolve which record to render --------------------------------
    rec: Optional[Dict[str, Any]] = None
    is_sample = False

    # 1. Explicit preview record (set when coming from saved_reports_preview)
    rec = st.session_state.get("preview_swing_record") or None

    # 2. Most recent real record for this user
    if rec is None and (user or {}).get("slug") and load_swing_history is not None:
        try:
            hist = load_swing_history(user["slug"]) or []
            if hist:
                rec = hist[-1]
        except Exception:
            rec = None

    # 3. Sample fallback so the design renders even with empty Supabase
    if rec is None:
        rec = _synthetic_record()
        is_sample = True

    # Full history for the comparison + sparkline (real if possible)
    history: List[Dict[str, Any]] = []
    if (user or {}).get("slug") and load_swing_history is not None:
        try:
            history = load_swing_history(user["slug"]) or []
        except Exception:
            history = []
    if not history:
        # Build a synthetic history with the current record at the end
        history = [
            _synthetic_record(swing_number=4) | {"score": 64, "id": "preview-prev-2"},
            _synthetic_record(swing_number=5) | {"score": 68, "id": "preview-prev-1"},
            _synthetic_record(swing_number=6) | {"score": 72, "id": "preview-prev-0"},
            rec,
        ]

    # ---- Pre-strip: back link + issue line ---------------------------
    bcol, _spc = st.columns([1, 6])
    with bcol:
        _html('<div class="srp-back-link-wrap">')
        if st.button("← Back to Sessions", key="srpv_back_to_sessions"):
            st.session_state["page"] = "saved_reports_preview"
            st.session_state.pop("preview_swing_record", None)
            st.session_state.pop("preview_swing_record_id", None)
            st.rerun()
        _html('</div>')

    player_name = (user or {}).get("name") or (user or {}).get("email") or "Player"
    today = datetime.now().strftime("%A · %B %-d · %Y")
    _html(f"""
        <div class="srp-issue-line">
          <span>Volume IV · Issue 24</span>
          <span class="center">Swing Report · {html.escape(str(player_name))} · {html.escape(_swing_label(rec))}</span>
          <span>{html.escape(today)}</span>
        </div>
        """)

    if is_sample:
        _html("""
            <div class="srp-preview-banner">
              <div class="srp-preview-banner-dot"></div>
              <div class="srp-preview-banner-text">
                PREVIEW · SAMPLE DATA
                <span class="em">
                  No saved swing was selected, so this is the synthetic
                  reference record. Your real swings will populate the
                  same template once selected from the Sessions list.
                </span>
              </div>
            </div>
            """)

    # ---- Sections 1–11 -----------------------------------------------
    _render_hero(rec)
    _render_section_head("§02 MLB COMP", "Doppelgänger", "match.",
                         sub="Hero card above already shows the player match — here's the breakdown.")
    # The MLB comp doppel is in the hero; this section just adds context
    # about why the comp was chosen.
    mlb = _mlb_ref(rec)
    _html(f"""
        <div class="srp-doppel" style="max-width:780px;">
          <div class="srp-doppel-eyebrow">
            <span>WHY THIS COMP</span><span class="num">5-axis fingerprint</span>
          </div>
          <p style="font-family:var(--serif);font-style:italic;font-size:24px;
                    line-height:1.45;color:var(--bone);margin:0 0 12px;">
            Your pose fingerprint sat closest to <span style="color:var(--gold);">{html.escape(mlb)}</span>
            across rotation, timing, and front-side firmness.
          </p>
          <p style="font-family:var(--sans);font-size:13.5px;line-height:1.55;
                    color:var(--bone-dim);margin:0;">
            The comp is recomputed every swing, but the model holds your
            best-fit MLB hitter steady once it has enough samples — so the
            comparison stays meaningful as you progress.
          </p>
        </div>
        """)

    _render_strengths(rec)
    _render_issues(rec)
    _render_coach_report(rec)
    _render_what_to_fix(rec)
    _render_drill_plan(rec)
    _render_drill_log(rec)
    _render_progress_insights(rec, history)
    _render_metric_cards(rec)
    _render_compare(rec, history)

    render_edge_page_wrapper_close()
