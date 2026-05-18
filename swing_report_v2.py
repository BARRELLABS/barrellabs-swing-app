"""
BarrelLabs / SwingAI — Swing Report v2 (premium redesign).

This is the PRESENTATION layer for the v2 swing report. All analysis
data is computed elsewhere (analyzer.py, drills.py) and surfaced via
helper functions in swing_report.py — this module just renders.

The v2 design is intentionally biomechanics-first. Where the mockup
showed launch-monitor numbers (bat speed / exit velocity / launch
angle / attack angle) we substitute the real measurements BarrelLabs
captures from pose data:

    HIP ROTATION         peak hip-shoulder separation (°)
    HIP-SHOULDER SEP     separation at foot plant (°)
    BAT TIMING           total swing duration (ms, slow-mo corrected)
    CONTACT TIMING       launch → contact (ms)
    KNEE RE-EXTENSION    front-knee re-extension during contact (°)
    HEAD STABILITY       total drift, torso-relative (inches)

The side-by-side pose overlay is a deliberate placeholder in this
push (Push 1). Push 2 will swap the placeholder for the real
SVG-skeleton renderer that consumes the .pose.json stored in
Supabase Storage.

Render path:
    render_swing_report_v2(record, history=, phase_chart_path=, ...)

`record` shape is the same dict consumed by swing_report.py — a live
`result` from analyzer.analyze() OR a saved swing row normalized to
the legacy shape.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
import html
import math

import streamlit as st

# ---------------------------------------------------------------------------
# KILL SWITCH for the side-by-side comparison viewer (Push 1.3).
# Set to False to skip the comparison block on every report — instant rollback
# without redeploying. Leave True in normal operation.
# ---------------------------------------------------------------------------
USE_SWING_COMPARE = True

# Reuse every data helper from swing_report.py — this file is render-only.
from swing_report import (
    _md,
    _score_band_from_score,
    _band_class_for_pct,
    _extract_ref_info,
    _initials,
    coach_summary,
    top_three_fixes,
    swing_dna,
    swing_progress,
    compare_to_last,
    enrich_fixes_with_history,
    mlb_signature_traits,
)


# =====================================================================
#                              CSS
# =====================================================================
_CSS_FLAG = "_swr_v2_css_injected"


def _ensure_css_v2():
    """Inject the v2 stylesheet on every Streamlit rerun.

    IMPORTANT: do NOT gate this with st.session_state. Streamlit rebuilds
    the entire DOM on every rerun (sidebar toggles, widget interactions,
    page navigations, etc.) so a previously-injected <style> tag is gone.
    If we skip re-injection because a session flag is set, the page
    renders unstyled — that's the "everything breaks when I touch the
    sidebar" bug. We keep the flag name around in case any other code
    reads it, but we always re-inject.
    """
    st.session_state[_CSS_FLAG] = True
    _md("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700&display=swap');

  :root {
    --bld2-bg:        #0a0a0c;
    --bld2-surface-0: #0f0f12;
    --bld2-surface-1: #15151a;
    --bld2-surface-2: #1c1c22;
    --bld2-line:      rgba(255,255,255,0.06);
    --bld2-line-2:    rgba(255,255,255,0.10);
    --bld2-ink-100:   #f5f5f7;
    --bld2-ink-80:    #cdcdd2;
    --bld2-ink-60:    #8a8a92;
    --bld2-ink-40:    #5a5a62;
    --bld2-red:       #ff3b30;
    --bld2-red-dim:   rgba(255,59,48,0.18);
    --bld2-green:     #6ee7b7;
    --bld2-amber:     #fbbf24;
    --bld2-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --bld2-mono: 'JetBrains Mono', ui-monospace, Menlo, monospace;
  }
  .bld2-wrap { max-width: 1400px; margin: 0 auto; padding: 0.5rem 0 2rem; }
  .bld2-wrap *, .bld2-wrap *::before, .bld2-wrap *::after { box-sizing: border-box; }

  /* ===== HEADER ===== */
  .bld2-hdr { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.6rem; gap: 1.2rem; flex-wrap: wrap; }
  .bld2-hdr-title { display: flex; align-items: center; gap: 0.85rem; margin-bottom: 0.45rem; }
  .bld2-hdr-title h1 { font-size: 1.85rem; font-weight: 800; letter-spacing: -0.025em; color: var(--bld2-ink-100); margin: 0; }
  .bld2-pill-new {
    background: var(--bld2-red-dim);
    color: var(--bld2-red);
    border: 1px solid rgba(255,59,48,0.35);
    padding: 0.28rem 0.7rem;
    border-radius: 999px;
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }
  .bld2-pill-saved {
    background: rgba(255,255,255,0.04);
    color: var(--bld2-ink-60);
    border: 1px solid var(--bld2-line-2);
    padding: 0.28rem 0.7rem;
    border-radius: 999px;
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }
  .bld2-hdr-meta {
    font-family: var(--bld2-mono);
    font-size: 0.72rem;
    color: var(--bld2-ink-60);
    letter-spacing: 0.1em;
  }
  .bld2-hdr-meta span.sep { margin: 0 0.65rem; opacity: 0.4; }

  /* ===== CARDS ===== */
  /* Padding standardized to 1.25rem 1.4rem and inter-card gap tightened to
     0.85rem so the report scans faster — tighter rhythm = more "premium". */
  .bld2-card {
    background: var(--bld2-surface-0);
    border: 1px solid var(--bld2-line);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    position: relative;
  }
  .bld2-eyebrow {
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    letter-spacing: 0.22em;
    color: var(--bld2-ink-60);
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 0.85rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .bld2-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem; margin-bottom: 0.85rem; }
  .bld2-grid-2-tilt { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 0.85rem; margin-bottom: 0.85rem; }

  /* ===== HERO ===== */
  .bld2-score-body { display: grid; grid-template-columns: 1fr 140px; gap: 1.3rem; align-items: center; }
  .bld2-score-num {
    font-size: 4.2rem;
    font-weight: 900;
    color: var(--bld2-red);
    letter-spacing: -0.05em;
    line-height: 0.9;
  }
  .bld2-score-num-foot {
    font-family: var(--bld2-mono);
    font-size: 0.78rem;
    color: var(--bld2-ink-60);
    font-weight: 600;
    margin-left: 0.3rem;
  }
  .bld2-score-band {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin: 0.6rem 0 0.85rem;
    border: 1px solid;
  }
  .bld2-band-green { color: var(--bld2-green); background: rgba(110,231,183,0.08); border-color: rgba(110,231,183,0.3); }
  .bld2-band-amber { color: var(--bld2-amber); background: rgba(251,191,36,0.08); border-color: rgba(251,191,36,0.3); }
  .bld2-band-red   { color: var(--bld2-red);   background: rgba(255,59,48,0.08); border-color: rgba(255,59,48,0.35); }
  .bld2-band-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .bld2-score-blurb { color: var(--bld2-ink-80); font-size: 0.86rem; line-height: 1.5; }

  .bld2-ring-wrap { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .bld2-ring-delta {
    display: flex; align-items: center; justify-content: center; gap: 0.4rem;
    font-family: var(--bld2-mono);
    font-size: 0.6rem;
    letter-spacing: 0.14em;
    font-weight: 700;
    text-transform: uppercase;
    margin-top: 0.55rem;
  }
  .bld2-ring-delta .sub { color: var(--bld2-ink-60); }
  .bld2-ring-delta.up   { color: var(--bld2-green); }
  .bld2-ring-delta.down { color: var(--bld2-red); }
  .bld2-ring-delta.flat { color: var(--bld2-ink-60); }

  /* MLB card */
  .bld2-mlb-grid { display: grid; grid-template-columns: 1fr 1.1fr; gap: 1rem; align-items: center; }
  .bld2-mlb-sim {
    font-size: 3.2rem;
    font-weight: 900;
    color: var(--bld2-ink-100);
    letter-spacing: -0.04em;
    line-height: 0.95;
  }
  .bld2-mlb-sim .pct { color: var(--bld2-red); }
  .bld2-mlb-foot { font-family: var(--bld2-mono); font-size: 0.7rem; color: var(--bld2-ink-60); letter-spacing: 0.16em; font-weight: 600; margin-top: 0.15rem; }
  .bld2-mlb-label { margin-top: 1rem; color: var(--bld2-ink-60); font-family: var(--bld2-mono); font-size: 0.62rem; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 700; margin-bottom: 0.45rem; }
  .bld2-mlb-row { display: flex; align-items: center; gap: 0.65rem; }
  .bld2-mlb-avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(255,59,48,0.25), rgba(255,59,48,0.05));
    border: 1px solid rgba(255,59,48,0.35);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--bld2-sans); font-weight: 800; font-size: 0.78rem;
    color: var(--bld2-red);
  }
  .bld2-mlb-name { font-weight: 700; font-size: 0.95rem; color: var(--bld2-ink-100); }
  .bld2-mlb-team { font-family: var(--bld2-mono); font-size: 0.65rem; color: var(--bld2-ink-60); letter-spacing: 0.1em; margin-top: 0.15rem; }
  .bld2-mlb-style { color: var(--bld2-ink-60); font-size: 0.78rem; margin-top: 0.6rem; line-height: 1.45; }
  .bld2-radar-host { display: flex; align-items: center; justify-content: center; min-height: 220px; }

  /* ===== KEY METRICS ===== */
  .bld2-km-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.7rem; margin-bottom: 0.85rem; }
  .bld2-km {
    background: var(--bld2-surface-0);
    border: 1px solid var(--bld2-line);
    border-radius: 12px;
    padding: 0.95rem 1rem 0.85rem;
    min-width: 0;
  }
  .bld2-km-label {
    font-family: var(--bld2-mono);
    font-size: 0.55rem;
    letter-spacing: 0.18em;
    color: var(--bld2-ink-60);
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 0.6rem;
  }
  .bld2-km-row-val { display: flex; align-items: baseline; gap: 0.4rem; flex-wrap: wrap; }
  .bld2-km-val {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--bld2-ink-100);
    letter-spacing: -0.035em;
    line-height: 1;
  }
  .bld2-km-unit { font-family: var(--bld2-mono); font-size: 0.6rem; color: var(--bld2-ink-60); letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; }
  .bld2-km-delta { display: inline-flex; align-items: center; gap: 0.18rem; font-family: var(--bld2-mono); font-size: 0.62rem; font-weight: 700; margin-left: auto; }
  .bld2-km-delta.up   { color: var(--bld2-green); }
  .bld2-km-delta.down { color: var(--bld2-red); }
  .bld2-km-delta.flat { color: var(--bld2-ink-60); }
  .bld2-km-ref { margin-top: 0.55rem; font-family: var(--bld2-mono); font-size: 0.55rem; color: var(--bld2-ink-40); letter-spacing: 0.1em; }

  /* ===== BREAKDOWN TABLE ===== */
  .bld2-br-table { width: 100%; border-collapse: collapse; }
  .bld2-br-table th {
    font-family: var(--bld2-mono);
    font-size: 0.55rem;
    letter-spacing: 0.18em;
    color: var(--bld2-ink-60);
    text-transform: uppercase;
    font-weight: 700;
    padding: 0.5rem 0.55rem;
    border-bottom: 1px solid var(--bld2-line);
    text-align: left;
  }
  .bld2-br-table th:nth-child(2), .bld2-br-table th:nth-child(3) { text-align: right; }
  .bld2-br-table th:last-child { text-align: center; width: 50px; }
  .bld2-br-table td {
    padding: 0.6rem 0.55rem;
    border-bottom: 1px solid var(--bld2-line);
    font-size: 0.8rem;
    color: var(--bld2-ink-80);
  }
  .bld2-br-table td:nth-child(2), .bld2-br-table td:nth-child(3) {
    text-align: right;
    font-family: var(--bld2-mono);
    font-weight: 600;
  }
  .bld2-br-table td:last-child { text-align: center; }
  .bld2-br-table tr:last-child td { border-bottom: none; }
  .bld2-status {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    font-weight: 800; font-size: 0.7rem;
  }
  .bld2-st-ok   { background: rgba(110,231,183,0.12); color: var(--bld2-green); }
  .bld2-st-warn { background: rgba(251,191,36,0.12); color: var(--bld2-amber); }
  .bld2-st-bad  { background: rgba(255,59,48,0.12);  color: var(--bld2-red); }
  .bld2-legend { margin-top: 0.85rem; display: flex; gap: 1rem; font-family: var(--bld2-mono); font-size: 0.55rem; color: var(--bld2-ink-60); letter-spacing: 0.14em; text-transform: uppercase; font-weight: 600; }
  .bld2-legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.35rem; vertical-align: middle; }

  /* ===== VISUALIZATION (pose overlay placeholder) ===== */
  .bld2-viz-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; margin-bottom: 0.9rem; }
  .bld2-viz-frame {
    aspect-ratio: 1 / 1;
    background: linear-gradient(135deg, #1a1a22, #0a0a12);
    border-radius: 10px;
    border: 1px solid var(--bld2-line);
    position: relative;
    overflow: hidden;
  }
  .bld2-viz-tag {
    position: absolute; top: 0.5rem; left: 0.5rem;
    font-family: var(--bld2-mono);
    font-size: 0.5rem;
    letter-spacing: 0.18em;
    color: var(--bld2-ink-60);
    background: rgba(0,0,0,0.55);
    border: 1px solid var(--bld2-line);
    padding: 0.22rem 0.45rem;
    border-radius: 6px;
    font-weight: 700;
    text-transform: uppercase;
    z-index: 2;
  }
  .bld2-viz-empty {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    text-align: center;
    font-family: var(--bld2-mono);
    font-size: 0.65rem;
    color: var(--bld2-ink-40);
    letter-spacing: 0.15em;
    padding: 1rem;
    line-height: 1.6;
  }
  .bld2-viz-soon {
    background: rgba(255,59,48,0.08);
    border-top: 1px solid rgba(255,59,48,0.25);
    color: var(--bld2-red);
    font-family: var(--bld2-mono);
    font-size: 0.58rem;
    letter-spacing: 0.18em;
    font-weight: 700;
    padding: 0.6rem;
    text-align: center;
    text-transform: uppercase;
    border-radius: 8px;
    margin-top: 0.85rem;
  }

  /* ===== PRIORITIES ===== */
  .bld2-pri { display: flex; gap: 0.85rem; padding: 0.85rem 0; border-bottom: 1px solid var(--bld2-line); }
  .bld2-pri:last-child { border-bottom: none; }
  .bld2-pri-num {
    width: 30px; height: 30px;
    border-radius: 8px;
    background: rgba(255,59,48,0.1);
    border: 1px solid rgba(255,59,48,0.25);
    color: var(--bld2-red);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--bld2-mono); font-weight: 700; font-size: 0.78rem;
    flex-shrink: 0;
  }
  .bld2-pri-body { flex: 1; min-width: 0; }
  .bld2-pri-head { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.3rem; flex-wrap: wrap; }
  .bld2-pri-title { font-weight: 700; font-size: 0.9rem; color: var(--bld2-ink-100); }
  .bld2-pri-tag {
    font-family: var(--bld2-mono);
    font-size: 0.52rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-weight: 700;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    border: 1px solid;
  }
  .bld2-pri-tag.high { color: var(--bld2-red); border-color: rgba(255,59,48,0.4); background: rgba(255,59,48,0.07); }
  .bld2-pri-tag.med  { color: var(--bld2-amber); border-color: rgba(251,191,36,0.4); background: rgba(251,191,36,0.07); }
  .bld2-pri-tag.low  { color: var(--bld2-green); border-color: rgba(110,231,183,0.35); background: rgba(110,231,183,0.07); }
  .bld2-pri-desc { font-size: 0.8rem; color: var(--bld2-ink-60); line-height: 1.45; }

  /* ===== DRILLS ===== */
  .bld2-drill { display: flex; gap: 0.85rem; padding: 0.85rem 0; border-bottom: 1px solid var(--bld2-line); align-items: center; }
  .bld2-drill:last-child { border-bottom: none; }
  .bld2-drill-thumb {
    width: 70px; height: 50px;
    border-radius: 8px;
    background: linear-gradient(135deg, #2a1010, #0a0a12);
    border: 1px solid var(--bld2-line);
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--bld2-mono); font-size: 0.55rem; color: var(--bld2-red);
    letter-spacing: 0.12em; font-weight: 700;
  }
  .bld2-drill-body { flex: 1; min-width: 0; }
  .bld2-drill-title { font-weight: 700; font-size: 0.88rem; margin-bottom: 0.32rem; color: var(--bld2-ink-100); }
  .bld2-drill-pills { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.28rem; }
  .bld2-drill-pill {
    font-family: var(--bld2-mono);
    font-size: 0.52rem;
    letter-spacing: 0.14em;
    color: var(--bld2-ink-60);
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bld2-line);
    padding: 0.18rem 0.45rem;
    border-radius: 5px;
    font-weight: 600;
    text-transform: uppercase;
  }
  .bld2-drill-why { font-size: 0.75rem; color: var(--bld2-ink-60); line-height: 1.4; }

  /* ===== PROGRESS CHART ===== */
  .bld2-pc-host { min-height: 220px; }
  .bld2-pc-empty {
    text-align: center; padding: 2.5rem 0.5rem;
    font-family: var(--bld2-mono);
    font-size: 0.7rem;
    color: var(--bld2-ink-60);
    letter-spacing: 0.14em;
    line-height: 1.8;
  }

  /* ===== WHAT'S NEXT ===== */
  .bld2-next { display: flex; flex-direction: column; justify-content: space-between; height: 100%; }
  .bld2-next h3 { font-size: 1.25rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 0.65rem; color: var(--bld2-ink-100); }
  .bld2-next-blurb { color: var(--bld2-ink-80); font-size: 0.9rem; line-height: 1.55; margin-bottom: 1rem; }

  /* ===== DNA ===== */
  .bld2-dna-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.7rem; }
  .bld2-dna-cell {
    background: var(--bld2-surface-1);
    border: 1px solid var(--bld2-line);
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
  }
  .bld2-dna-label { font-family: var(--bld2-mono); font-size: 0.55rem; letter-spacing: 0.16em; color: var(--bld2-ink-60); font-weight: 700; text-transform: uppercase; margin-bottom: 0.4rem; }
  .bld2-dna-bar { height: 4px; background: rgba(255,255,255,0.05); border-radius: 999px; overflow: hidden; margin-bottom: 0.35rem; }
  .bld2-dna-fill { height: 100%; border-radius: 999px; }
  .bld2-dna-pct { font-family: var(--bld2-mono); font-weight: 700; font-size: 0.78rem; }

  /* ===== STRENGTHS ===== */
  .bld2-str-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.85rem; }
  .bld2-str {
    background: linear-gradient(135deg, rgba(110,231,183,0.06), rgba(110,231,183,0.01));
    border: 1px solid rgba(110,231,183,0.2);
    border-radius: 10px;
    padding: 0.85rem 0.95rem;
  }
  .bld2-str-head { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }
  .bld2-str-check { color: var(--bld2-green); font-weight: 800; font-size: 0.95rem; }
  .bld2-str-title { font-weight: 700; font-size: 0.88rem; color: var(--bld2-ink-100); }
  .bld2-str-pct { font-family: var(--bld2-mono); font-size: 1.4rem; font-weight: 800; color: var(--bld2-green); letter-spacing: -0.03em; margin-bottom: 0.25rem; }
  .bld2-str-sub { font-family: var(--bld2-mono); font-size: 0.6rem; color: var(--bld2-ink-60); letter-spacing: 0.1em; }

  /* ===== COACH QUOTE ===== */
  .bld2-coach-quote {
    border-left: 3px solid var(--bld2-red);
    padding: 0.45rem 0 0.45rem 0.95rem;
    color: var(--bld2-ink-80);
    font-style: italic;
    font-size: 0.92rem;
    line-height: 1.6;
    margin-bottom: 0.85rem;
  }
  .bld2-coach-body { color: var(--bld2-ink-80); font-size: 0.88rem; line-height: 1.65; }
  .bld2-coach-body p { margin: 0 0 0.85rem; }
  .bld2-coach-body p:last-child { margin-bottom: 0; }

  /* ===== HEADER ACTION BUTTONS ===== */
  .bld2-hdr-actions { display: flex; gap: 0.55rem; flex-wrap: wrap; }
  .bld2-btn {
    display: inline-flex; align-items: center; gap: 0.45rem;
    padding: 0.65rem 0.95rem;
    border-radius: 10px;
    font-family: var(--bld2-sans); font-size: 0.8rem; font-weight: 600;
    border: 1px solid var(--bld2-line-2);
    cursor: pointer;
    transition: all .2s cubic-bezier(.2,.7,.2,1);
    text-decoration: none;
  }
  .bld2-btn-ghost { background: var(--bld2-surface-1); color: var(--bld2-ink-100); }
  .bld2-btn-ghost:hover { border-color: rgba(255,255,255,0.22); }
  .bld2-btn-primary {
    background: var(--bld2-red); color: #fff; border-color: var(--bld2-red);
    box-shadow: 0 10px 30px -12px rgba(255,59,48,0.55);
  }
  .bld2-btn-primary:hover { transform: translateY(-1px); box-shadow: 0 14px 36px -12px rgba(255,59,48,0.7); }

  /* ===== KEY METRICS — SPARKLINES ===== */
  .bld2-km-spark { margin-top: 0.55rem; width: 100%; height: 28px; display: block; }

  /* ===== VISUALIZATION TABS + SCRUBBER ===== */
  .bld2-viz-tabs { display: flex; gap: 0.35rem; margin-bottom: 0.85rem; }
  .bld2-viz-tab {
    padding: 0.45rem 0.85rem;
    border-radius: 8px;
    font-family: var(--bld2-mono); font-size: 0.6rem; letter-spacing: 0.14em;
    font-weight: 700; text-transform: uppercase;
    color: var(--bld2-ink-60);
    background: transparent;
    border: 1px solid var(--bld2-line);
    cursor: default;
  }
  .bld2-viz-tab.active {
    color: var(--bld2-red);
    border-color: rgba(255,59,48,0.45);
    background: rgba(255,59,48,0.06);
  }
  .bld2-scrub-row {
    display: flex; align-items: center; gap: 0.55rem;
    padding-top: 0.6rem;
    border-top: 1px solid var(--bld2-line);
    margin-top: 0.85rem;
  }
  .bld2-scrub-play {
    width: 30px; height: 30px;
    border-radius: 50%;
    background: var(--bld2-red);
    border: none; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem;
    flex-shrink: 0;
  }
  .bld2-scrub-bar {
    flex: 1; height: 4px;
    background: var(--bld2-line);
    border-radius: 999px;
    position: relative;
  }
  .bld2-scrub-fill { width: 60%; height: 100%; background: var(--bld2-red); border-radius: 999px; }
  .bld2-scrub-knob {
    position: absolute; left: 60%; top: 50%;
    transform: translate(-50%, -50%);
    width: 14px; height: 14px;
    background: var(--bld2-red);
    border-radius: 50%;
    box-shadow: 0 0 0 4px rgba(255,59,48,0.18);
  }
  .bld2-scrub-time {
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    color: var(--bld2-ink-60);
    letter-spacing: 0.08em;
  }

  /* ===== CARD FOOTER LINKS ===== */
  .bld2-card-foot-link {
    margin-top: 0.85rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--bld2-line);
    text-align: center;
    color: var(--bld2-red);
    font-family: var(--bld2-mono);
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    font-weight: 700;
    text-transform: uppercase;
  }

  /* ===== DRILL CHECKBOX ===== */
  .bld2-drill-check {
    width: 22px; height: 22px;
    border-radius: 6px;
    border: 1.5px solid var(--bld2-line-2);
    flex-shrink: 0;
  }

  /* ===== WHAT'S NEXT — BIG CTA BUTTON ===== */
  .bld2-next-cta {
    background: var(--bld2-red);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0.9rem;
    font-family: var(--bld2-sans);
    font-weight: 700;
    font-size: 0.92rem;
    width: 100%;
    box-shadow: 0 10px 30px -12px rgba(255,59,48,0.55);
    text-align: center;
    display: block;
  }

  /* ===== HTML ACCORDIONS (replaces st.expander for visual cohesion) ===== */
  .bld2-accord {
    background: var(--bld2-surface-0);
    border: 1px solid var(--bld2-line);
    border-radius: 14px;
    overflow: hidden;
    margin-top: 1rem;
  }
  .bld2-accord > summary {
    list-style: none;
    cursor: pointer;
    padding: 1.1rem 1.5rem;
    display: flex; align-items: center; justify-content: space-between;
    gap: 0.65rem;
  }
  .bld2-accord > summary::-webkit-details-marker { display: none; }
  .bld2-accord > summary::marker { content: ""; }
  .bld2-accord-head-l { display: flex; gap: 0.65rem; align-items: center; }
  .bld2-accord-eyebrow {
    font-family: var(--bld2-mono);
    font-size: 0.6rem;
    letter-spacing: 0.22em;
    color: var(--bld2-red);
    text-transform: uppercase;
    font-weight: 700;
  }
  .bld2-accord-title { font-weight: 700; font-size: 1rem; color: var(--bld2-ink-100); }
  .bld2-accord-caret {
    color: var(--bld2-ink-60);
    font-family: var(--bld2-mono);
    font-size: 0.9rem;
    transition: transform 0.2s;
  }
  .bld2-accord[open] .bld2-accord-caret { transform: rotate(180deg); }
  .bld2-accord-body {
    padding: 1.1rem 1.5rem 1.4rem;
    border-top: 1px solid var(--bld2-line);
  }

  /* =====================================================================
     BARRELLABS POLISH LAYER — depth, glow, motion. Subtle enough to feel
     premium without overpowering the data. Everything here is additive
     on top of the base styles above.
     ===================================================================== */

  /* Background bloom — red-tinged radial glow drifting across the report.
     Gives the whole page a subtle atmospheric depth instead of flat black. */
  .bld2-wrap {
    background-image:
      radial-gradient(ellipse 800px 400px at 85% 0%, rgba(255,59,48,0.05), transparent 60%),
      radial-gradient(ellipse 600px 500px at 15% 100%, rgba(255,59,48,0.03), transparent 60%);
    background-attachment: scroll;
    background-repeat: no-repeat;
    padding: 1.2rem 0 2.5rem;
  }

  /* Card depth — subtle inner gradient + transition for hover lift. */
  .bld2-card {
    background:
      linear-gradient(135deg, rgba(255,255,255,0.025), rgba(255,255,255,0) 40%),
      var(--bld2-surface-0);
    transition: border-color .25s ease, transform .25s ease, box-shadow .25s ease;
  }
  .bld2-card:hover {
    border-color: rgba(255,255,255,0.11);
    transform: translateY(-1px);
    box-shadow: 0 12px 36px -18px rgba(0,0,0,0.6);
  }

  /* Card eyebrow — add a glowing red accent dot before the label. */
  .bld2-eyebrow::before {
    content: "";
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--bld2-red);
    box-shadow: 0 0 8px var(--bld2-red), 0 0 2px var(--bld2-red);
    margin-right: 0.55rem;
    flex-shrink: 0;
  }

  /* Score number — drop a soft red halo behind the big 78. */
  .bld2-score-num {
    text-shadow:
      0 0 32px rgba(255,59,48,0.35),
      0 0 8px rgba(255,59,48,0.2);
  }

  /* NEW ANALYSIS pill — pulse the background so the eye is drawn to it. */
  @keyframes bld2-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255,59,48,0.5); }
    50%      { box-shadow: 0 0 0 6px rgba(255,59,48,0); }
  }
  .bld2-pill-new {
    animation: bld2-pulse 2.4s ease-in-out infinite;
  }

  /* Score band pill — slight glow so the strong-swing badge pops. */
  .bld2-band-green { box-shadow: 0 0 18px -6px rgba(110,231,183,0.4); }
  .bld2-band-amber { box-shadow: 0 0 18px -6px rgba(251,191,36,0.35); }
  .bld2-band-red   { box-shadow: 0 0 18px -6px rgba(255,59,48,0.4); }

  /* MLB avatar — outer ring glow */
  .bld2-mlb-avatar {
    box-shadow: 0 0 24px -6px rgba(255,59,48,0.45);
  }

  /* MLB similarity % — slight glow on the %. */
  .bld2-mlb-sim .pct {
    text-shadow: 0 0 16px rgba(255,59,48,0.4);
  }

  /* Key metrics value — small white-glow lift so the numbers feel sharper. */
  .bld2-km-val { text-shadow: 0 0 14px rgba(255,255,255,0.06); }
  .bld2-km:hover { border-color: rgba(255,255,255,0.12); }

  /* What's Next card — subtle red wash so the CTA feels charged. */
  .bld2-next {
    background:
      radial-gradient(ellipse at top right, rgba(255,59,48,0.06), transparent 60%),
      var(--bld2-surface-0);
    border-color: rgba(255,59,48,0.18);
  }
  .bld2-next-cta {
    box-shadow:
      0 12px 32px -14px rgba(255,59,48,0.6),
      inset 0 1px 0 rgba(255,255,255,0.18);
    transition: transform .2s ease, box-shadow .2s ease;
  }
  .bld2-next-cta:hover {
    transform: translateY(-2px);
    box-shadow:
      0 16px 40px -10px rgba(255,59,48,0.75),
      inset 0 1px 0 rgba(255,255,255,0.22);
  }

  /* Header primary button — match the same heat as the bottom CTA. */
  .bld2-btn-primary {
    box-shadow:
      0 10px 30px -12px rgba(255,59,48,0.55),
      inset 0 1px 0 rgba(255,255,255,0.18);
  }
  .bld2-btn-primary:hover {
    transform: translateY(-1px);
    box-shadow:
      0 14px 36px -10px rgba(255,59,48,0.7),
      inset 0 1px 0 rgba(255,255,255,0.22);
  }

  /* Card footer links — arrow nudges right on hover. */
  .bld2-card-foot-link { transition: color .2s ease; cursor: pointer; }
  .bld2-card-foot-link:hover { color: #ff6e66; }

  /* Coach quote — stronger left bar + soft red glow. */
  .bld2-coach-quote {
    border-left-width: 3px;
    box-shadow: -2px 0 18px -10px rgba(255,59,48,0.5);
  }

  /* Strength cards — stronger green glow. */
  .bld2-str {
    box-shadow: 0 0 24px -10px rgba(110,231,183,0.35);
  }

  /* Sparklines — drop-shadow makes the line feel like a glowing trace. */
  .bld2-km-spark polyline {
    filter: drop-shadow(0 0 4px rgba(255,59,48,0.45));
  }

  /* =====================================================================
     OVERFLOW + RESPONSIVE PROTECTION — keeps the layout from breaking
     when Streamlit changes the content-area width (e.g. sidebar collapse).
     ===================================================================== */
  /* Every grid child gets min-width:0 so flex/grid items can shrink below
     their content size instead of forcing the parent to overflow. */
  .bld2-grid-2 > *,
  .bld2-grid-2-tilt > *,
  .bld2-km-row > *,
  .bld2-mlb-grid > *,
  .bld2-score-body > *,
  .bld2-dna-grid > *,
  .bld2-str-row > *,
  .bld2-viz-pair > * { min-width: 0; }

  /* SVGs scale to their container instead of clipping or overflowing. */
  .bld2-radar-host svg,
  .bld2-pc-host svg,
  .bld2-km-spark { max-width: 100%; height: auto; display: block; }
  .bld2-radar-host { width: 100%; }
  .bld2-radar-host svg { width: 100%; max-width: 280px; }

  /* Long-content guards — names / titles / table cells truncate gracefully
     rather than pushing the box wider. */
  .bld2-mlb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bld2-pri-title, .bld2-drill-title { overflow-wrap: anywhere; }
  .bld2-br-table td:first-child { overflow-wrap: anywhere; }

  /* Cards never force horizontal overflow on the parent. */
  .bld2-card { overflow: hidden; }
  /* …except the hero score card, where the ring's drop-shadow needs to
     escape. Use overflow:visible there. */
  .bld2-grid-2 > .bld2-card:first-child { overflow: visible; }

  /* =====================================================================
     BREAKPOINTS — re-tier the layout as the content area shrinks. We use
     three steps so the report works whether the sidebar is open, closed,
     or the window itself is narrow.
     ===================================================================== */
  @media (max-width: 1280px) {
    .bld2-km-row { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 1024px) {
    .bld2-grid-2, .bld2-grid-2-tilt { grid-template-columns: 1fr; }
    .bld2-hdr { flex-direction: column; align-items: stretch; }
    .bld2-hdr-actions { justify-content: flex-start; }
  }
  @media (max-width: 760px) {
    .bld2-km-row { grid-template-columns: repeat(2, 1fr); }
    .bld2-dna-grid { grid-template-columns: repeat(2, 1fr); }
    .bld2-str-row { grid-template-columns: 1fr; }
    .bld2-mlb-grid { grid-template-columns: 1fr; }
    .bld2-score-body { grid-template-columns: 1fr; }
    .bld2-hdr-actions .bld2-btn { font-size: 0.74rem; padding: 0.55rem 0.75rem; }
  }
  /* Phone-sized viewports — tighten card padding, scale the hero score down
     so it doesn't overflow, and stack priority/drill rows so the numbered
     thumb stays prominent above the title instead of competing for width. */
  @media (max-width: 640px) {
    .bld2-card { padding: 1rem 1.05rem; }
    .bld2-score-num { font-size: 3.2rem; }
    .bld2-radar-host svg { max-width: 220px; }
    .bld2-pri, .bld2-drill {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.55rem;
    }
    .bld2-pri-num, .bld2-drill-thumb {
      width: auto;
      min-width: 2.25rem;
    }
    .bld2-drill-check { display: none; }
    .bld2-eyebrow { margin-bottom: 0.7rem; }
  }
  @media (max-width: 480px) {
    .bld2-km-row { grid-template-columns: 1fr; }
  }
</style>
""")


# =====================================================================
#                          BAND HELPERS
# =====================================================================

def _band_class_v2(band_color: str) -> str:
    """Map score_band_color → CSS band class."""
    c = (band_color or "").lower()
    if c in ("green", "good", "strong", "elite"):
        return "bld2-band-green"
    if c in ("yellow", "amber", "building", "warn"):
        return "bld2-band-amber"
    return "bld2-band-red"


def _band_from_pct(pct: float) -> str:
    """Map a 0-100 match% → status class for breakdown rows / DNA cells."""
    if pct is None:
        return "bld2-st-warn"
    if pct >= 75:
        return "bld2-st-ok"
    if pct >= 55:
        return "bld2-st-warn"
    return "bld2-st-bad"


def _dna_fill_color(pct: float) -> str:
    if pct is None:
        return "var(--bld2-ink-40)"
    if pct >= 75:
        return "var(--bld2-green)"
    if pct >= 55:
        return "var(--bld2-amber)"
    return "var(--bld2-red)"


def _severity_class_from_sim(sim_pct: Optional[float]) -> Tuple[str, str]:
    """Return (css_class, label) for the impact pill on a priority row."""
    if sim_pct is None:
        return ("med", "MEDIUM IMPACT")
    if sim_pct < 50:
        return ("high", "HIGH IMPACT")
    if sim_pct < 70:
        return ("med", "MEDIUM IMPACT")
    return ("low", "LOW IMPACT")


# =====================================================================
#                       INLINE SVG HELPERS
# =====================================================================

def _score_ring_svg(score: int, band_class: str) -> str:
    """Build the score ring SVG that sits in the hero score card."""
    pct = max(0, min(100, int(score)))
    color_map = {
        "bld2-band-green": "#6ee7b7",
        "bld2-band-amber": "#fbbf24",
        "bld2-band-red":   "#ff3b30",
    }
    color = color_map.get(band_class, "#ff3b30")
    radius = 56
    stroke = 9
    cx, cy = 70, 70
    circ = 2 * math.pi * radius
    offset = circ * (1 - pct / 100.0)
    return f"""
<svg viewBox="0 0 140 140" width="140" height="140" style="overflow:visible">
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none"
          stroke="rgba(255,255,255,0.06)" stroke-width="{stroke}"/>
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none"
          stroke="{color}" stroke-width="{stroke}"
          stroke-dasharray="{circ:.2f}" stroke-dashoffset="{offset:.2f}"
          stroke-linecap="round"
          transform="rotate(-90 {cx} {cy})"
          style="filter: drop-shadow(0 0 8px {color}55);"/>
  <text x="{cx}" y="{cy + 6}" text-anchor="middle"
        fill="{color}" font-family="Inter" font-weight="900" font-size="28"
        letter-spacing="-1">{pct}</text>
</svg>
"""


def _radar_svg(axes: List[Tuple[str, float]]) -> str:
    """Build a 5-axis radar SVG. `axes` is [(label, pct_0_to_100), ...] in
    clockwise order from the top. The reference polygon (the MLB hitter)
    is the 100%-on-every-axis pentagon. Player polygon is overlaid.
    """
    n = max(len(axes), 3)
    # Widen the viewBox horizontally so the side labels ("SEPARATION",
    # "LOWER BODY") never overflow the SVG bounds when the sidebar
    # collapses or the card narrows. Height stays the same.
    W = 320
    H = 260
    cx, cy = W / 2, H / 2
    R = 88
    levels = [0.25, 0.5, 0.75, 1.0]
    angles = [-math.pi / 2 + i * (2 * math.pi / n) for i in range(n)]

    parts = [
        f'<svg viewBox="0 0 {W} {H}" width="100%" height="auto" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'style="display:block;max-width:340px;margin:0 auto;overflow:visible">'
    ]

    # Grid pentagons
    for lvl in levels:
        pts = []
        for a in angles:
            x = cx + math.cos(a) * R * lvl
            y = cy + math.sin(a) * R * lvl
            pts.append(f"{x:.1f},{y:.1f}")
        parts.append(
            f'<polygon points="{" ".join(pts)}" fill="none" '
            f'stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
        )

    # Axis lines + labels
    for a, (label, _pct) in zip(angles, axes):
        x = cx + math.cos(a) * R
        y = cy + math.sin(a) * R
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
        )
        # Label position just outside the ring
        lx = cx + math.cos(a) * (R + 18)
        ly = cy + math.sin(a) * (R + 18) + 3
        anchor = "middle"
        if math.cos(a) > 0.3:
            anchor = "start"
        elif math.cos(a) < -0.3:
            anchor = "end"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'fill="#8a8a92" font-family="JetBrains Mono" font-size="8.5" '
            f'letter-spacing="1.6" font-weight="700">{html.escape(label.upper())}</text>'
        )

    # MLB reference polygon (always 100% — it IS the reference)
    ref_pts = []
    for a in angles:
        x = cx + math.cos(a) * R
        y = cy + math.sin(a) * R
        ref_pts.append(f"{x:.1f},{y:.1f}")
    parts.append(
        f'<polygon points="{" ".join(ref_pts)}" '
        f'fill="rgba(110,231,183,0.04)" '
        f'stroke="rgba(110,231,183,0.4)" stroke-width="1.2" '
        f'stroke-dasharray="3 3"/>'
    )

    # Player polygon
    player_pts = []
    for a, (_label, pct) in zip(angles, axes):
        pct = max(0.0, min(100.0, float(pct or 0.0)))
        r = R * (pct / 100.0)
        x = cx + math.cos(a) * r
        y = cy + math.sin(a) * r
        player_pts.append(f"{x:.1f},{y:.1f}")
    parts.append(
        f'<polygon points="{" ".join(player_pts)}" '
        f'fill="rgba(255,59,48,0.18)" '
        f'stroke="#ff3b30" stroke-width="2"/>'
    )
    for a, (_label, pct) in zip(angles, axes):
        pct = max(0.0, min(100.0, float(pct or 0.0)))
        r = R * (pct / 100.0)
        x = cx + math.cos(a) * r
        y = cy + math.sin(a) * r
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#ff3b30"/>')

    parts.append("</svg>")
    return "".join(parts)


def _progress_chart_svg(score_history: List[Tuple[Any, float]]) -> str:
    """Build the v2-style score-over-time line+area chart."""
    if not score_history:
        return ('<div class="bld2-pc-empty">No score history yet — '
                'this chart fills in as you upload more swings.</div>')

    W = 600
    H = 220
    PAD_L = 44
    PAD_R = 24
    PAD_T = 26
    PAD_B = 34
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    n = len(score_history)
    scores = [float(s) for _, s in score_history]
    s_min = min(scores + [0])
    s_max = max(scores + [100])
    # Pin to 0..100 baseline so the eye reads the score band, not just trend.
    s_min, s_max = 0.0, 100.0

    def _x(i):
        if n == 1:
            return PAD_L + plot_w / 2
        return PAD_L + (i / (n - 1)) * plot_w

    def _y(s):
        return PAD_T + (1 - (s - s_min) / (s_max - s_min)) * plot_h

    pts = [(_x(i), _y(s)) for i, s in enumerate(scores)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    parts = [f'<svg width="100%" height="{H}" viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="overflow:visible">']

    # Grid lines @ 25 / 50 / 75 / 100
    for lvl in (25, 50, 75, 100):
        y = _y(lvl)
        parts.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
            f'stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PAD_L - 8}" y="{y + 3:.1f}" text-anchor="end" '
            f'fill="#5a5a62" font-family="JetBrains Mono" font-size="9">{lvl}</text>'
        )

    # Area fill
    area = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for x, y in pts[1:]:
        area += f"L {x:.1f},{y:.1f} "
    area += f"L {pts[-1][0]:.1f},{_y(s_min):.1f} "
    area += f"L {pts[0][0]:.1f},{_y(s_min):.1f} Z"
    parts.append(f'<path d="{area}" fill="rgba(255,59,48,0.10)"/>')

    # Line
    parts.append(
        f'<polyline fill="none" stroke="#ff3b30" stroke-width="2.5" '
        f'points="{poly}" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # Points + score labels above
    for i, ((x, y), s) in enumerate(zip(pts, scores)):
        is_last = (i == n - 1)
        if is_last:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#ff3b30" '
                f'stroke="#0a0a0c" stroke-width="3"/>'
            )
            parts.append(
                f'<text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" '
                f'fill="#ff3b30" font-family="Inter" font-weight="800" font-size="13">'
                f'{int(round(s))}</text>'
            )
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#ff3b30"/>')
            parts.append(
                f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" '
                f'fill="#cdcdd2" font-family="Inter" font-weight="700" font-size="11">'
                f'{int(round(s))}</text>'
            )

    # X-axis labels: show swing number
    for i, ((x, _y_), (num, _s)) in enumerate(zip(pts, score_history)):
        parts.append(
            f'<text x="{x:.1f}" y="{H - 10}" text-anchor="middle" '
            f'fill="#5a5a62" font-family="JetBrains Mono" font-size="9" '
            f'letter-spacing="1">#{num}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _sparkline_svg(values: List[float], direction: str = "match") -> str:
    """Tiny inline trend chart for a key-metric tile.

    `values` is oldest-→-newest. `direction` controls the line color hint
    (we use red for 'attention' trend, green for 'improving'). For Push 1
    we keep it simple and always red so it visually matches the mockup.
    """
    if not values or len(values) < 2:
        # Render a flat baseline so the tile doesn't look empty.
        return (
            '<svg class="bld2-km-spark" viewBox="0 0 100 28" '
            'preserveAspectRatio="none">'
            '<line x1="0" y1="18" x2="100" y2="18" '
            'stroke="rgba(255,255,255,0.08)" stroke-width="1.5" '
            'stroke-dasharray="2 3"/></svg>'
        )

    n = len(values)
    v_min = min(values)
    v_max = max(values)
    span = (v_max - v_min) or 1.0
    pts = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * 100.0
        # Invert y because SVG origin is top-left; pad 4 each side.
        y = 24 - ((v - v_min) / span) * 20
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    return (
        f'<svg class="bld2-km-spark" viewBox="0 0 100 28" '
        f'preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="#ff3b30" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{poly}"/>'
        f'</svg>'
    )


# =====================================================================
#                  KEY METRICS COMPUTATION (biomechanics)
# =====================================================================

# Map of (tile_label, [metric_label substrings to match], unit, direction)
# direction:
#   "match"        higher sim_pct = better (used when value itself is unitless)
#   "higher"       higher VALUE = better (more separation = better)
#   "lower"        lower VALUE = better (less drift, faster timing)
_V2_TILES = [
    # (label,                metric_label_match,                       unit,  direction)
    ("HIP ROTATION",         "Hip rotation at contact",                "°",   "match"),
    ("HIP-SHOULDER SEP",     "Peak hip-shoulder separation",           "°",   "higher"),
    ("BAT TIMING",           "Total swing duration",                    "ms",  "lower"),
    ("CONTACT TIMING",       "Launch → contact",                        "ms",  "lower"),
    ("KNEE RE-EXTENSION",    "Re-extension",                            "°",   "higher"),
    ("HEAD STABILITY",       "Total head drift",                        "",    "lower"),
]


def _flatten_metric_table(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten {group: [rows]} → [rows] for label-based lookup."""
    out = []
    mt = record.get("metric_table") or {}
    for group, rows in mt.items():
        for r in rows:
            r2 = dict(r)
            r2["__group"] = group
            out.append(r2)
    return out


def _find_metric_row(rows: List[Dict[str, Any]], needle: str) -> Optional[Dict[str, Any]]:
    needle = (needle or "").lower()
    for r in rows:
        if needle in str(r.get("label", "")).lower():
            return r
    return None


def _parse_value_from_str(s: str) -> Optional[float]:
    """Pull the leading number out of a formatted metric string like '58.3°',
    '152ms', '~3 in', '+1.5°', '-0.4T'. Returns None if no number."""
    if not s:
        return None
    s = str(s).strip().lstrip("+~").replace(",", "")
    # Find first contiguous number (allow leading sign)
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    n = ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            n += ch
        else:
            break
    try:
        return sign * float(n) if n else None
    except ValueError:
        return None


def _compute_key_metrics(record: Dict[str, Any],
                          history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Build the 6-tile key-metrics row. Each tile: {label, value, unit,
    delta_str, delta_class, ref_str, sparkline_svg}."""
    curr_rows = _flatten_metric_table(record)
    # Previous swing's metric_table for delta computation. We look at the
    # most-recent prior swing in history (history is sorted oldest→newest
    # in app.py's flow; defensive sort here just in case).
    prev_rows: List[Dict[str, Any]] = []
    # Also build a sorted-prior history (last 8 swings, current included)
    # so we can pull a per-metric series for the tile sparklines.
    series_records: List[Dict[str, Any]] = []
    if history:
        def _ts(r): return str(r.get("timestamp") or r.get("date") or "")
        sorted_hist = sorted(history, key=_ts)
        # Drop the current record from the tail if it's in history.
        curr_id = record.get("id")
        curr_ts = record.get("timestamp")
        prior = [r for r in sorted_hist
                 if not ((curr_id is not None and r.get("id") == curr_id)
                         or (curr_ts is not None and r.get("timestamp") == curr_ts))]
        if prior:
            prev_rec = prior[-1]
            prev_rows = _flatten_metric_table(prev_rec)
        # Last 7 historical + current = up to 8 points
        series_records = (prior[-7:] if prior else []) + [record]
    else:
        series_records = [record]

    out = []
    for (label, needle, unit_hint, direction) in _V2_TILES:
        curr_row = _find_metric_row(curr_rows, needle)
        if curr_row is None:
            out.append({
                "label": label, "value": "—", "unit": unit_hint,
                "delta_str": "", "delta_class": "flat",
                "ref_str": "", "tooltip": "Metric not available for this swing.",
                "sparkline_svg": _sparkline_svg([], direction),
            })
            continue

        # Sparkline series for this metric across recent history.
        series_vals: List[float] = []
        for rec in series_records:
            rec_rows = _flatten_metric_table(rec)
            rec_row = _find_metric_row(rec_rows, needle)
            if rec_row is None:
                continue
            v = _parse_value_from_str(rec_row.get("player_str", ""))
            if v is not None:
                series_vals.append(v)
        spark_svg = _sparkline_svg(series_vals, direction)

        # Value / ref strings come pre-formatted from analyzer.py — use as-is.
        p_str = str(curr_row.get("player_str") or "—")
        r_str = str(curr_row.get("ref_str") or "")
        # Some labels include the unit in the formatted string already
        # (e.g. "58.3°", "152ms"). For HEAD STABILITY we keep the inches
        # string ("~3 in") whole so we don't have to know the conversion.
        # We strip leading ~ for cleaner display.
        display_val = p_str.lstrip("~+").strip()
        # If the value already carries its unit (most do), don't double-print.
        # Heuristic: if any letter or ° appears in display_val, treat as
        # self-contained and blank the explicit unit chip.
        explicit_unit = ""
        if not any(c.isalpha() or c == "°" for c in display_val):
            explicit_unit = unit_hint

        # Delta vs previous swing
        delta_str = ""
        delta_class = "flat"
        if prev_rows:
            prev_row = _find_metric_row(prev_rows, needle)
            if prev_row is not None:
                p_val = _parse_value_from_str(curr_row.get("player_str", ""))
                v_prev = _parse_value_from_str(prev_row.get("player_str", ""))
                if p_val is not None and v_prev is not None:
                    raw = p_val - v_prev
                    # Tile-specific formatting
                    if abs(raw) < 0.05:
                        delta_str = "± 0"
                        delta_class = "flat"
                    else:
                        sign = "↑" if raw > 0 else "↓"
                        # Determine green/red based on direction
                        if direction == "higher":
                            delta_class = "up" if raw > 0 else "down"
                        elif direction == "lower":
                            delta_class = "up" if raw < 0 else "down"
                        else:  # "match" — use sim_pct trend instead
                            cur_sim = curr_row.get("sim_pct", 0) or 0
                            prv_sim = prev_row.get("sim_pct", 0) or 0
                            delta_class = "up" if cur_sim >= prv_sim else "down"
                        delta_str = f"{sign}{abs(raw):.1f}"

        # Reference subtitle so the player sees what they're tracking toward.
        ref_short = r_str.lstrip("~+").strip()
        ref_label = f"vs {ref_short}" if ref_short else ""

        out.append({
            "label": label,
            "value": display_val,
            "unit": explicit_unit,
            "delta_str": delta_str,
            "delta_class": delta_class,
            "ref_str": ref_label,
            "sparkline_svg": spark_svg,
        })

    return out


# =====================================================================
#                    SECTION RENDERERS
# =====================================================================

def _build_v2_header(record: Dict[str, Any], is_live: bool) -> str:
    """Top header with title, status pill, swing meta, and action buttons.
    Returns HTML string (no st.markdown call)."""
    pill_html = (
        '<span class="bld2-pill-new">New Analysis</span>' if is_live
        else '<span class="bld2-pill-saved">Saved Report</span>'
    )
    ref = _extract_ref_info(record)
    when = record.get("timestamp") or record.get("date") or ""
    when_short = str(when).replace("T", " ").split(".")[0] if when else ""
    swing_num = record.get("swing_number")
    meta_bits = []
    if swing_num is not None:
        meta_bits.append(f"<strong style=\"color:var(--bld2-ink-80);\">SWING #{swing_num}</strong>")
    if when_short:
        meta_bits.append(html.escape(when_short))
    if ref.get("name"):
        meta_bits.append(f"VS {html.escape(ref['name']).upper()}")
    meta_html = '<span class="sep">·</span>'.join(meta_bits) if meta_bits else ""

    # Action buttons are visual affordances. Real Share/Download/Upload
    # actions are wired through Streamlit elsewhere in app.py.
    return f"""
<div class="bld2-hdr">
  <div>
    <div class="bld2-hdr-title">
      <h1>SWING REPORT</h1>
      {pill_html}
    </div>
    <div class="bld2-hdr-meta">{meta_html}</div>
  </div>
  <div class="bld2-hdr-actions">
    <span class="bld2-btn bld2-btn-ghost">⬆ Share Report</span>
    <span class="bld2-btn bld2-btn-ghost">⤓ Download PDF</span>
    <span class="bld2-btn bld2-btn-primary">↑ Upload New Swing</span>
  </div>
</div>
"""


def _build_v2_hero(record: Dict[str, Any],
                    history: Optional[List[Dict[str, Any]]]) -> str:
    """Hero row — score card + MLB comparison card side-by-side.
    Returns HTML string."""
    score = record.get("score")
    try:
        score_int = int(round(float(score)))
    except (TypeError, ValueError):
        score_int = 0
    band_color = record.get("score_band_color") or ""
    band_label = record.get("score_band_label") or ""
    band_class = _band_class_v2(band_color)
    ring_svg = _score_ring_svg(score_int, band_class)

    # Delta vs prior swing
    prog = swing_progress(record, history) or {}
    delta = prog.get("score_delta")
    if delta is None or not prog.get("has_prior"):
        delta_block = ('<div class="bld2-ring-delta flat">'
                       '<span class="sub">BASELINE SWING</span></div>')
    else:
        d_int = int(round(float(delta)))
        if d_int > 0:
            arrow = "↑"; cls = "up"; txt = f"+{d_int}"
        elif d_int < 0:
            arrow = "↓"; cls = "down"; txt = f"{d_int}"
        else:
            arrow = "→"; cls = "flat"; txt = "±0"
        prev_int = int(round(float(prog.get("prev_score") or 0)))
        delta_block = (
            f'<div class="bld2-ring-delta {cls}">'
            f'{arrow}{txt} <span class="sub">VS PREVIOUS ({prev_int})</span></div>'
        )

    blurb_text = coach_summary(record)

    # MLB COMP card data
    ref = _extract_ref_info(record)
    ref_initials = _initials(ref.get("name", ""))
    ref_style = (ref.get("style") or "").strip()

    # Build radar axes — 5 biomechanics dimensions sourced from metric_table
    rows = _flatten_metric_table(record)

    def _sim_avg(needles: List[str]) -> float:
        vals = []
        for n in needles:
            r = _find_metric_row(rows, n)
            if r is not None and r.get("sim_pct") is not None:
                vals.append(float(r["sim_pct"]))
        return (sum(vals) / len(vals)) if vals else 0.0

    radar_axes = [
        ("ROTATION",   _sim_avg(["Hip rotation at foot plant", "Hip rotation at contact"])),
        ("SEPARATION", _sim_avg(["Peak hip-shoulder separation", "Separation at foot plant"])),
        ("TIMING",     _sim_avg(["Total swing duration", "Foot plant → launch", "Launch → contact"])),
        ("LOWER BODY", _sim_avg(["Re-extension", "Most bent (load)"])),
        ("STABILITY",  _sim_avg(["Total head drift", "Head drift Δx", "Head drift Δy"])),
    ]
    radar_avg = (sum(p for _l, p in radar_axes) / max(len(radar_axes), 1))
    sim_pct = int(round(radar_avg))
    radar_html = _radar_svg(radar_axes)

    style_html = (
        f'<div class="bld2-mlb-style">{html.escape(ref_style)}</div>'
        if ref_style else ""
    )

    return f"""
<div class="bld2-grid-2">
  <div class="bld2-card">
    <div class="bld2-eyebrow">OVERALL SWING SCORE</div>
    <div class="bld2-score-body">
      <div>
        <div>
          <span class="bld2-score-num">{score_int}</span>
          <span class="bld2-score-num-foot">/ 100</span>
        </div>
        <div class="bld2-score-band {band_class}">
          <span class="bld2-band-dot"></span>{html.escape(band_label.upper())}
        </div>
        <div class="bld2-score-blurb">{blurb_text}</div>
      </div>
      <div class="bld2-ring-wrap">
        {ring_svg}
        {delta_block}
      </div>
    </div>
  </div>

  <div class="bld2-card">
    <div class="bld2-eyebrow">MLB COMPARISON</div>
    <div class="bld2-mlb-grid">
      <div>
        <div class="bld2-mlb-sim">{sim_pct}<span class="pct">%</span></div>
        <div class="bld2-mlb-foot">MLB SIMILARITY</div>
        <div class="bld2-mlb-label">MOST SIMILAR TO:</div>
        <div class="bld2-mlb-row">
          <div class="bld2-mlb-avatar">{ref_initials}</div>
          <div>
            <div class="bld2-mlb-name">{html.escape(ref.get("name") or "Unknown")}</div>
            <div class="bld2-mlb-team">{html.escape((ref.get("team") or "") + (" · " + ref.get("position") if ref.get("position") else ""))}</div>
          </div>
        </div>
        {style_html}
      </div>
      <div class="bld2-radar-host">{radar_html}</div>
    </div>
  </div>
</div>
"""


def _build_v2_key_metrics(record: Dict[str, Any],
                           history: Optional[List[Dict[str, Any]]]) -> str:
    """6-tile biomechanics key-metrics row. Returns HTML string."""
    tiles = _compute_key_metrics(record, history)

    tile_html_chunks = []
    for t in tiles:
        delta_inner = ""
        if t.get("delta_str"):
            delta_inner = f'<div class="bld2-km-delta {t["delta_class"]}">{html.escape(t["delta_str"])}</div>'
        unit_html = (f'<div class="bld2-km-unit">{html.escape(t["unit"])}</div>'
                     if t.get("unit") else "")
        spark_html = t.get("sparkline_svg") or ""
        tile_html_chunks.append(f"""
  <div class="bld2-km">
    <div class="bld2-km-label">{html.escape(t["label"])}</div>
    <div class="bld2-km-row-val">
      <div class="bld2-km-val">{html.escape(t["value"])}</div>
      {unit_html}
      {delta_inner}
    </div>
    {spark_html}
  </div>
""")

    tiles_html = "".join(tile_html_chunks)

    return f"""
<div class="bld2-card" style="margin-bottom:1rem;">
  <div class="bld2-eyebrow">KEY METRICS — BIOMECHANICS</div>
  <div class="bld2-km-row">
    {tiles_html}
  </div>
</div>
"""


def _build_v2_breakdown_and_viz(record: Dict[str, Any],
                                 phase_chart_path: Optional[str]) -> str:
    """Breakdown table + pose overlay placeholder, side-by-side.
    Returns HTML string."""
    rows = _flatten_metric_table(record)
    # Show ALL rows that have a sim_pct (mockup shows 10). Sort by sim_pct
    # ascending so the biggest gaps surface first.
    rows_sorted = sorted(
        [r for r in rows if r.get("sim_pct") is not None],
        key=lambda r: r.get("sim_pct", 0)
    )[:10]

    body_rows = []
    for r in rows_sorted:
        sim_pct = r.get("sim_pct") or 0
        if sim_pct >= 75:
            st_cls, icon = "bld2-st-ok", "✓"
        elif sim_pct >= 55:
            st_cls, icon = "bld2-st-warn", "—"
        else:
            st_cls, icon = "bld2-st-bad", "↓"
        body_rows.append(f"""
    <tr>
      <td>{html.escape(str(r.get("label","")))}</td>
      <td>{html.escape(str(r.get("player_str","—")))}</td>
      <td>{html.escape(str(r.get("ref_str","—")))}</td>
      <td><span class="bld2-status {st_cls}">{icon}</span></td>
    </tr>
""")

    table_body = "".join(body_rows) if body_rows else (
        '<tr><td colspan="4" style="text-align:center;padding:1.5rem 0;'
        'color:var(--bld2-ink-60);font-family:var(--bld2-mono);font-size:0.75rem;">'
        'No metric breakdown available.</td></tr>'
    )

    # Pose overlay placeholder. Push 2 will replace this block with the real
    # SVG skeleton renderer driven by the stored .pose.json. Tabs + scrubber
    # are visual affordances for the upcoming feature.
    pose_block = """
  <div class="bld2-viz-tabs">
    <span class="bld2-viz-tab active">Side View</span>
    <span class="bld2-viz-tab">Front View</span>
    <span class="bld2-viz-tab">Top View</span>
  </div>
  <div class="bld2-viz-pair">
    <div class="bld2-viz-frame">
      <div class="bld2-viz-tag">AT LOAD</div>
      <div class="bld2-viz-empty">[ pose overlay frame ]</div>
    </div>
    <div class="bld2-viz-frame">
      <div class="bld2-viz-tag">AT CONTACT</div>
      <div class="bld2-viz-empty">[ pose overlay frame ]</div>
    </div>
  </div>
  <div class="bld2-scrub-row">
    <span class="bld2-scrub-play">▶</span>
    <div class="bld2-scrub-bar">
      <div class="bld2-scrub-fill"></div>
      <div class="bld2-scrub-knob"></div>
    </div>
    <div class="bld2-scrub-time">0.00 / 0.60</div>
  </div>
  <div style="margin-top:0.7rem;display:flex;gap:1rem;font-family:var(--bld2-mono);font-size:0.55rem;color:var(--bld2-ink-60);letter-spacing:0.14em;text-transform:uppercase;font-weight:600;">
    <div><span class="bld2-legend-dot" style="background:#ff3b30;"></span>Your Swing</div>
    <div><span class="bld2-legend-dot" style="background:rgba(255,255,255,0.4);"></span>MLB Reference</div>
  </div>
  <div class="bld2-viz-soon">POSE SKELETON RENDERING — SHIPPING NEXT</div>
"""

    return f"""
<div class="bld2-grid-2-tilt">
  <div class="bld2-card">
    <div class="bld2-eyebrow">SWING BREAKDOWN</div>
    <table class="bld2-br-table">
      <thead>
        <tr><th>METRIC</th><th>YOUR SWING</th><th>MLB AVG</th><th>STATUS</th></tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>
    <div class="bld2-legend">
      <span><span class="bld2-legend-dot" style="background:var(--bld2-green);"></span>Above MLB Avg</span>
      <span><span class="bld2-legend-dot" style="background:var(--bld2-amber);"></span>Average</span>
      <span><span class="bld2-legend-dot" style="background:var(--bld2-red);"></span>Below MLB Avg</span>
    </div>
  </div>

  <div class="bld2-card">
    <div class="bld2-eyebrow">SWING VISUALIZATION</div>
    {pose_block}
  </div>
</div>
"""


def _build_v2_priorities_and_drills(record: Dict[str, Any],
                                      history: Optional[List[Dict[str, Any]]]) -> str:
    """Top 3 priorities + recommended drills, side-by-side. Returns HTML."""
    fixes = top_three_fixes(record) or []
    # Enrich with history-aware "recurring" flags
    if history:
        try:
            fixes = enrich_fixes_with_history(fixes, history) or fixes
        except Exception:
            pass

    pri_rows = []
    if not fixes:
        pri_rows.append(
            '<div class="bld2-pri">'
            '<div class="bld2-pri-num">—</div>'
            '<div class="bld2-pri-body">'
            '<div class="bld2-pri-head"><div class="bld2-pri-title">No priorities yet</div></div>'
            '<div class="bld2-pri-desc">Upload another swing and we\u2019ll surface the biggest unlocks.</div>'
            '</div></div>'
        )
    else:
        for f in fixes[:3]:
            rank = f.get("rank") or "•"
            title = (f.get("title") or "Priority").title()
            why = (f.get("why") or f.get("headline") or "").strip()
            tag_cls, tag_label = _severity_class_from_sim(f.get("worst_sim_pct"))
            pri_rows.append(f"""
      <div class="bld2-pri">
        <div class="bld2-pri-num">{html.escape(str(rank))}</div>
        <div class="bld2-pri-body">
          <div class="bld2-pri-head">
            <div class="bld2-pri-title">{html.escape(title)}</div>
            <div class="bld2-pri-tag {tag_cls}">{tag_label}</div>
          </div>
          <div class="bld2-pri-desc">{html.escape(why)}</div>
        </div>
      </div>
""")
    pri_html = "".join(pri_rows)

    # Drill plan rows
    drill_plan = record.get("drill_plan") or {}
    cats = drill_plan.get("categories", []) if isinstance(drill_plan, dict) else []
    drill_rows = []
    drill_count = 0
    for cat in cats[:2]:  # top 2 categories
        for d in (cat.get("drills") or [])[:2]:  # up to 2 drills per category
            drill_count += 1
            sets = d.get("sets")
            reps = d.get("reps")
            freq = d.get("frequency") or d.get("weekly")
            pills = []
            if sets: pills.append(f"{sets} Sets")
            if reps: pills.append(f"{reps} Reps")
            if freq: pills.append(html.escape(str(freq)))
            pills_html = "".join(
                f'<div class="bld2-drill-pill">{html.escape(p)}</div>' for p in pills
            )
            drill_rows.append(f"""
    <div class="bld2-drill">
      <div class="bld2-drill-thumb">DRILL {drill_count:02d}</div>
      <div class="bld2-drill-body">
        <div class="bld2-drill-title">{html.escape(d.get("title") or d.get("name") or "Drill")}</div>
        <div class="bld2-drill-pills">{pills_html}</div>
        <div class="bld2-drill-why">{html.escape(d.get("why") or d.get("benefit") or "Reinforces this category.")}</div>
      </div>
      <div class="bld2-drill-check"></div>
    </div>
""")
            if drill_count >= 3:
                break
        if drill_count >= 3:
            break

    if not drill_rows:
        drill_rows.append(
            '<div class="bld2-drill">'
            '<div class="bld2-drill-thumb">—</div>'
            '<div class="bld2-drill-body">'
            '<div class="bld2-drill-title">Drill plan unavailable</div>'
            '<div class="bld2-drill-why">Re-run analysis to regenerate.</div>'
            '</div></div>'
        )

    drills_html = "".join(drill_rows)

    return f"""
<div class="bld2-grid-2">
  <div class="bld2-card">
    <div class="bld2-eyebrow">TOP 3 PRIORITIES</div>
    {pri_html}
    <div class="bld2-card-foot-link">View All Insights ›</div>
  </div>
  <div class="bld2-card">
    <div class="bld2-eyebrow">RECOMMENDED DRILLS</div>
    {drills_html}
    <div class="bld2-card-foot-link">View Full Drill Plan ›</div>
  </div>
</div>
"""


def _build_v2_progress_and_next(record: Dict[str, Any],
                                  history: Optional[List[Dict[str, Any]]]) -> str:
    """Score-over-time chart + What's Next CTA. Returns HTML."""
    prog = swing_progress(record, history) or {}
    chart_svg = _progress_chart_svg(prog.get("score_history") or [])

    # Pull the #1 priority for the What's Next nudge
    fixes = top_three_fixes(record) or []
    headline = "Re-upload after your next session to track the trend."
    body = (
        "Keep filming and re-uploading every 5–7 days. The more swings we "
        "see, the sharper the priority targeting and the drill plan get."
    )
    if fixes:
        top = fixes[0]
        title = (top.get("title") or "your top fix").title()
        headline = f"Lock in the {title} work this week."
        body = (
            top.get("fix_feel") or top.get("why")
            or "Work the priority drill block 3-4 sessions, then re-upload."
        )

    return f"""
<div class="bld2-grid-2">
  <div class="bld2-card">
    <div class="bld2-eyebrow">SWING SCORE OVER TIME</div>
    <div class="bld2-pc-host">{chart_svg}</div>
  </div>
  <div class="bld2-card bld2-next">
    <div>
      <div class="bld2-eyebrow">WHAT'S NEXT</div>
      <h3>{html.escape(headline)}</h3>
      <div class="bld2-next-blurb">{html.escape(body)}</div>
    </div>
    <div class="bld2-next-cta">↑ Upload New Swing</div>
  </div>
</div>
"""


def _build_v2_accordions(record: Dict[str, Any],
                           history: Optional[List[Dict[str, Any]]]) -> str:
    """Three HTML <details> accordions — coach notes, DNA, strengths.
    Returns HTML string. We use native <details> instead of st.expander so
    the dark-themed visual treatment is preserved (st.expander injects its
    own Streamlit chrome that breaks the design)."""
    parts: List[str] = []

    # ----- Coach's Full Notes -----
    coach_top = coach_summary(record)
    narratives = record.get("narratives") or []
    ref = _extract_ref_info(record)
    extra_paras = []
    if narratives:
        n0 = narratives[0]
        extra_paras.append(
            f"The biggest unlock right now is <strong>{html.escape((n0.get('title') or 'the top mechanic').title())}</strong>. "
            f"{html.escape(n0.get('why') or '')}"
        )
        if n0.get("fix_feel"):
            extra_paras.append(
                f"What the fix should feel like: <em>{html.escape(n0['fix_feel'])}</em>"
            )
    if ref.get("style") and ref.get("name"):
        extra_paras.append(
            f"Watch {html.escape(ref['name'])} for the model — "
            f"{html.escape(ref['style'].lower().rstrip('.'))}."
        )
    extra_html = "".join(f"<p>{p}</p>" for p in extra_paras)

    parts.append(f"""
<details class="bld2-accord">
  <summary>
    <div class="bld2-accord-head-l">
      <div class="bld2-accord-eyebrow">08</div>
      <div class="bld2-accord-title">Coach's Full Notes</div>
    </div>
    <div class="bld2-accord-caret">▼</div>
  </summary>
  <div class="bld2-accord-body">
    <div class="bld2-coach-quote">{coach_top}</div>
    <div class="bld2-coach-body">{extra_html}</div>
  </div>
</details>
""")

    # ----- Swing DNA -----
    dna_rows = swing_dna(record) or []
    if dna_rows:
        cells_html_parts = []
        for d in dna_rows:
            pct = float(d.get("pct") or 0)
            color = _dna_fill_color(pct)
            cells_html_parts.append(f"""
      <div class="bld2-dna-cell">
        <div class="bld2-dna-label">{html.escape(str(d.get("label","")))}</div>
        <div class="bld2-dna-bar"><div class="bld2-dna-fill" style="width:{max(0,min(100,pct))}%;background:{color};"></div></div>
        <div class="bld2-dna-pct" style="color:{color};">{int(round(pct))}%</div>
      </div>
""")
        parts.append(f"""
<details class="bld2-accord">
  <summary>
    <div class="bld2-accord-head-l">
      <div class="bld2-accord-eyebrow">09</div>
      <div class="bld2-accord-title">Swing DNA — Category Match</div>
    </div>
    <div class="bld2-accord-caret">▼</div>
  </summary>
  <div class="bld2-accord-body">
    <div class="bld2-dna-grid">
      {"".join(cells_html_parts)}
    </div>
  </div>
</details>
""")

    # ----- Strengths -----
    strengths = record.get("strengths") or []
    if strengths:
        cells_html_parts = []
        for s in strengths[:3]:
            pct = s.get("sim_pct") or 0
            cat_label = s.get("category_label") or s.get("label") or "Strength"
            p_str = s.get("player_str") or ""
            r_str = s.get("ref_str") or ""
            sub = f"You: {p_str} · Ref: {r_str}" if (p_str or r_str) else ""
            cells_html_parts.append(f"""
      <div class="bld2-str">
        <div class="bld2-str-head">
          <div class="bld2-str-check">✓</div>
          <div class="bld2-str-title">{html.escape(str(cat_label))}</div>
        </div>
        <div class="bld2-str-pct">{int(round(float(pct)))}%</div>
        <div class="bld2-str-sub">{html.escape(sub)}</div>
      </div>
""")
        parts.append(f"""
<details class="bld2-accord">
  <summary>
    <div class="bld2-accord-head-l">
      <div class="bld2-accord-eyebrow">10</div>
      <div class="bld2-accord-title">What You Did Well</div>
    </div>
    <div class="bld2-accord-caret">▼</div>
  </summary>
  <div class="bld2-accord-body">
    <div class="bld2-str-row">
      {"".join(cells_html_parts)}
    </div>
  </div>
</details>
""")

    return "".join(parts)


# =====================================================================
#                       MAIN ENTRY POINT
# =====================================================================

def render_swing_report_v2(
    record: Dict[str, Any],
    *,
    history: Optional[List[Dict[str, Any]]] = None,
    phase_chart_path: Optional[str] = None,
    show_diagnostics: bool = True,
    show_section_numbers: bool = True,
):
    """Render the v2 swing report — same call signature as
    swing_report.render_swing_report() so the orchestrator can delegate
    1:1.

    `show_section_numbers` is accepted for API compatibility but the v2
    layout uses card eyebrows instead of numbered section headers so the
    parameter is currently a no-op.
    """
    _ensure_css_v2()

    # Live results don't have a DB id yet; saved records do.
    is_live = not record.get("id")

    # Build the WHOLE report as one HTML string and emit it in ONE markdown
    # call. This is critical for visual cohesion — if we call _md() per
    # section, Streamlit wraps each in its own stMarkdownContainer chrome
    # and the cards get pushed apart with extra padding, killing the
    # mockup's tight rhythm.
    #
    # EXCEPTION: the swing-compare viewer needs <script> + <canvas>,
    # which Streamlit strips from st.markdown. So we split the render
    # into THREE chunks and slot st.components.v1.html() in between
    # hero and key metrics. The seam is invisible to the user because
    # the bld2-wrap spacing rules are consistent on both sides.

    # Chunk 1: header + hero
    top_html = (
        _build_v2_header(record, is_live)
        + _build_v2_hero(record, history)
    )
    _md('<div class="bld2-wrap">' + top_html + "</div>")

    # Chunk 2: side-by-side comparison block (Pro users) — fail-soft so
    # any error here never blocks the rest of the report from rendering.
    # Gated by USE_SWING_COMPARE kill switch at top of module for instant
    # rollback without redeploying.
    _compare = None
    if USE_SWING_COMPARE:
        try:
            from swing_compare_viewer import build_compare_section
            _compare = build_compare_section(record)
        except Exception:
            _compare = None
    if _compare and _compare.get("html"):
        # Eyebrow rendered as a bld2 card so it inherits the v2 styling
        # and visually flows with the rest of the report (avoiding a
        # naked "iframe in a sea of cards" look).
        _md(
            '<div class="bld2-wrap" style="margin-bottom:0;">'
            '<div class="bld2-card" style="margin-bottom:0.75rem;'
            'padding-bottom:0.5rem;">'
            '<div class="bld2-eyebrow">SIDE-BY-SIDE COMPARISON</div>'
            '<div style="color:#a0a0a8;font-size:12px;line-height:1.5;'
            'margin-top:6px;">'
            'Your swing on the left, the MLB reference on the right — '
            'synchronized at foot plant so you can see the timing '
            'difference frame-by-frame.'
            '</div>'
            '</div></div>'
        )
        # If pose data is missing (Free user), render a small upgrade
        # nudge above the MLB-only viewer. Uses inline styles so we don't
        # need to add a new CSS class to _ensure_css_v2.
        if not _compare.get("ready"):
            _md(
                '<div class="bld2-wrap" style="margin-bottom:0.75rem;">'
                '<div style="background:#1a0f0f;border:1px solid #3a1f1f;'
                'border-left:3px solid #ff3b30;border-radius:10px;'
                'padding:12px 16px;color:#ffb3a8;font-size:13px;'
                'line-height:1.5;">'
                '<strong style="color:#fff;">Upgrade to Pro</strong> '
                'to see your own swing skeleton overlaid next to the '
                'MLB reference. Free reports show the MLB side only.'
                '</div></div>'
            )
        try:
            import streamlit.components.v1 as components
            components.html(
                _compare["html"],
                height=int(_compare.get("height", 680)),
                scrolling=False,
            )
        except Exception:
            pass

    # Chunk 3: rest of the report.
    # ORDER IS DELIBERATE — actionable insights (priorities + drills) come
    # immediately after the hero so the user sees WHAT TO FIX before they
    # scroll into the diagnostic charts and breakdown table. This mirrors
    # the section priority of TrackMan / Hudl-style premium reports.
    bottom_html = (
        _build_v2_priorities_and_drills(record, history)
        + _build_v2_key_metrics(record, history)
        + _build_v2_breakdown_and_viz(record, phase_chart_path)
        + _build_v2_progress_and_next(record, history)
        + _build_v2_accordions(record, history)
    )
    _md('<div class="bld2-wrap">' + bottom_html + "</div>")

    # ====== DIAGNOSTICS (kept from v1 — useful expandables) ======
    if show_diagnostics:
        if phase_chart_path:
            try:
                from pathlib import Path
                if Path(phase_chart_path).is_file():
                    with st.expander("Swing phases chart"):
                        st.image(phase_chart_path, use_column_width=True)
            except Exception:
                pass

        slow_mo = record.get("slow_mo") or {}
        if slow_mo.get("any"):
            with st.expander("Slow-motion correction details"):
                st.markdown(
                    "**Slow-mo detected.** A real MLB swing (foot plant → contact) "
                    "takes about 150ms. Anything significantly longer is almost always "
                    "slow-motion footage being scaled back to real-time so we can "
                    "compare apples-to-apples."
                )
                if slow_mo.get("player_factor", 1) > 1.05:
                    st.markdown(
                        f"**Your clip:** slow-mo `{slow_mo.get('player_factor', 1):.1f}×` · "
                        f"raw {slow_mo.get('player_raw_swing_ms', 0):.0f}ms → "
                        f"corrected {slow_mo.get('player_corrected_swing_ms', 0):.0f}ms"
                    )
                if slow_mo.get("ref_factor", 1) > 1.05:
                    st.markdown(
                        f"**Reference clip:** slow-mo `{slow_mo.get('ref_factor', 1):.1f}×` · "
                        f"raw {slow_mo.get('ref_raw_swing_ms', 0):.0f}ms → "
                        f"corrected {slow_mo.get('ref_corrected_swing_ms', 0):.0f}ms"
                    )

        cam = record.get("camera_view") or {}
        if cam.get("rotation_view_sensitive"):
            with st.expander("Camera angle note"):
                st.markdown(
                    "Rotation metrics for this swing have reduced confidence "
                    "due to camera-angle mismatch with the reference clip. "
                    "**Tip:** film from the side, perpendicular to the pitcher, "
                    "for the cleanest read on hip & shoulder rotation."
                )
