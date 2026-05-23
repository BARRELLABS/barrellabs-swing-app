"""
BarrelLabs / SwingAI — Premium Swing Report renderer.

Single shared module used by:
  • the live post-analysis flow (after a new swing is analyzed in app.py)
  • the Saved Reports viewer (`render_saved_swing_report`)
  • the PDF export (`build_swing_report_pdf` reads from the same intel helpers)

The goal: every surface that shows a swing report renders the same
data, the same way — with all the new premium sections:

    1. HERO              score ring + band + MLB comp featured card
    2. COACH'S SUMMARY   auto-generated opening paragraph
    3. TOP 3 FIXES       prioritized list w/ severity, why it costs you,
                         what the fix feels like, linked drill anchor
    4. SWING DNA         visual radar / bar set of category match %
    5. VS LAST SWING     mini comparison vs previous swing (if any)
    6. MLB COMP CARD     featured comparison — signature traits,
                         what they do that you should mimic
    7. DRILL PLAN        premium drill cards w/ priority + reps + why
    8. STRENGTHS         what you did well
    9. METRIC DETAIL     grouped, scannable, mini match bars
   10. DIAGNOSTICS       slow-mo, camera, phase chart in expanders

A "record" here can be either:
  - a live `result` dict (from analyzer.analyze())
  - a saved record dict (from player_storage._swing_row_to_legacy)

Both shapes are normalized through `_extract_ref_info()`,
`_normalize_metric_table()`, etc.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
import html
import math

import streamlit as st


def _md(html_blob: str) -> None:
    """Render an HTML blob via st.markdown after stripping per-line leading
    whitespace.

    Why: Streamlit's markdown parser runs BEFORE unsafe_allow_html is applied,
    which means any line indented by 4+ spaces (especially after a blank line)
    gets converted to a CommonMark indented code block. That turns our pretty
    multi-line HTML templates into <pre><code> blobs on screen. Stripping the
    leading whitespace per line keeps the HTML semantically identical while
    immunizing it from that markdown trap.
    """
    lines = [ln.lstrip() for ln in html_blob.splitlines()]
    st.markdown("\n".join(lines), unsafe_allow_html=True)


# ============================================================
#                       CSS — LOCAL STYLES
# ============================================================

_SR_LOCAL_CSS = """
<style>
/* ============================================================
   SWING REPORT — LOCAL STYLE NAMESPACE
   All classes prefixed `.swr-` to avoid cross-page collisions.
   ============================================================ */

/* ---------- HERO ---------- */
.swr-hero {
    position: relative;
    border-radius: var(--bl-radius-xl);
    border: 1px solid var(--bl-line);
    background:
        radial-gradient(ellipse at 80% -10%, rgba(255,59,48,0.10) 0%, transparent 60%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.012));
    padding: 1.8rem 2rem 1.6rem;
    overflow: hidden;
    margin-bottom: 1.2rem;
}
.swr-hero-grid {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 2rem;
    align-items: center;
}
@media (max-width: 760px) {
    .swr-hero-grid { grid-template-columns: 1fr; }
}

.swr-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.24em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

.swr-hero-title {
    font-family: var(--bl-sans);
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1.1;
    margin-bottom: 0.35rem;
}
.swr-hero-sub {
    font-family: var(--bl-sans);
    font-size: 0.95rem;
    color: var(--bl-ink-60);
    margin-bottom: 0.6rem;
}

/* Score ring */
.swr-ring-wrap {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    position: relative;
}
.swr-ring-stack {
    position: relative;
    width: 200px;
    height: 200px;
}
.swr-ring-svg { display: block; }
.swr-ring-bg  { stroke: rgba(255,255,255,0.06); }
.swr-ring-fg  {
    transition: stroke-dashoffset 0.8s ease, stroke 0.4s ease;
    filter: drop-shadow(0 0 18px rgba(255,59,48,0.35));
}
.swr-ring-center {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center;
}
.swr-ring-num {
    font-family: var(--bl-sans);
    font-size: 3.2rem;
    font-weight: 800;
    letter-spacing: -0.045em;
    line-height: 1;
    color: var(--bl-ink-100);
}
.swr-ring-out-of {
    font-family: var(--bl-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    margin-top: 0.35rem;
}
/* Band pill is a SIBLING of the ring (sits below the SVG), so wide labels
   like "BUILDING BLOCK" don't overflow the circle's right edge. */
.swr-ring-band {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-top: 0.75rem;
    padding: 0.28rem 0.7rem;
    border-radius: 999px;
    border: 1px solid;
    white-space: nowrap;
    display: inline-block;
}

/* Hero chips on the right */
.swr-chip-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.55rem;
    margin-top: 0.85rem;
}
@media (max-width: 540px) {
    .swr-chip-row { grid-template-columns: repeat(2, 1fr); }
}
.swr-chip {
    border-radius: var(--bl-radius-md);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.025);
    padding: 0.55rem 0.7rem;
}
.swr-chip-label {
    font-family: var(--bl-mono);
    font-size: 0.55rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}
.swr-chip-value {
    font-family: var(--bl-sans);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    margin-top: 0.18rem;
    letter-spacing: -0.01em;
    line-height: 1.15;
}

/* ---------- SECTION HEADERS ----------
   The whole section header (number · title · optional sub) lives inside
   one container so Streamlit can't insert margin between the title row and
   the subtitle. This was the source of the previous "cramped" look — the
   subtitle used a negative margin-top to compensate for Streamlit's stMarkdown
   wrapper, which was fragile and overlapped at certain font sizes. */
.swr-sec-wrap {
    margin: 2rem 0 1.1rem;
}
.swr-sec-head {
    display: flex;
    align-items: baseline;
    gap: 0.85rem;
    margin: 0;
}
.swr-sec-num {
    font-family: var(--bl-mono);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    color: var(--bl-red);
}
.swr-sec-title {
    font-family: var(--bl-sans);
    font-size: 1.45rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1.15;
}
.swr-sec-sub {
    font-family: var(--bl-sans);
    font-size: 0.92rem;
    line-height: 1.4;
    color: var(--bl-ink-60);
    margin-top: 0.4rem;
}

/* ---------- COACH'S SUMMARY CARD ---------- */
.swr-coach {
    position: relative;
    border-radius: var(--bl-radius-lg);
    border: 1px solid rgba(255,59,48,0.22);
    background:
        linear-gradient(135deg, rgba(255,59,48,0.06), rgba(255,255,255,0.018));
    padding: 1.4rem 1.5rem 1.3rem;
    margin-bottom: 1.4rem;
}
.swr-coach-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.24em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.55rem;
    display: flex; align-items: center; gap: 0.5rem;
}
.swr-coach-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 20px; height: 20px;
    border-radius: 50%;
    background: var(--bl-red);
    color: #fff;
    font-size: 0.7rem; font-weight: 800;
    letter-spacing: 0;
}
.swr-coach-body {
    font-family: var(--bl-sans);
    font-size: 1.02rem;
    line-height: 1.55;
    color: var(--bl-ink-80);
}
.swr-coach-body strong { color: var(--bl-ink-100); }

/* ---------- TOP 3 FIXES ---------- */
.swr-fixes {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.9rem;
}
.swr-fix {
    position: relative;
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: var(--bl-surface-1);
    padding: 1.1rem 1.3rem 1.2rem;
    transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}
.swr-fix:hover {
    transform: translateY(-1px);
    border-color: var(--bl-line-hi);
    box-shadow: 0 12px 30px -18px rgba(0,0,0,0.5);
}
.swr-fix-head {
    display: flex; align-items: center; gap: 0.85rem;
    margin-bottom: 0.6rem;
}
.swr-fix-rank {
    flex: 0 0 auto;
    width: 40px; height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--bl-red), #c91e15);
    color: #fff;
    font-family: var(--bl-sans);
    font-weight: 800;
    font-size: 1.05rem;
    letter-spacing: -0.02em;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 8px 20px -10px rgba(255,59,48,0.55);
}
.swr-fix-title {
    font-family: var(--bl-sans);
    font-size: 1.12rem;
    font-weight: 800;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    line-height: 1.2;
    flex: 1 1 auto;
}
.swr-fix-severity {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 0.22rem 0.55rem;
    border-radius: 999px;
    border: 1px solid;
    white-space: nowrap;
}
.swr-fix-severity.is-high  { color: #ff6058; border-color: rgba(255,96,88,0.4); background: rgba(255,96,88,0.08); }
.swr-fix-severity.is-med   { color: #f6c453; border-color: rgba(246,196,83,0.4); background: rgba(246,196,83,0.07); }
.swr-fix-severity.is-low   { color: #6ee7b7; border-color: rgba(110,231,183,0.4); background: rgba(110,231,183,0.07); }

.swr-fix-body {
    font-family: var(--bl-sans);
    font-size: 0.96rem;
    color: var(--bl-ink-80);
    line-height: 1.55;
}
.swr-fix-body p { margin: 0 0 0.6rem; }
.swr-fix-body p:last-child { margin-bottom: 0; }
.swr-fix-sub-label {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--bl-red);
    display: block;
    margin: 0.65rem 0 0.18rem;
}

/* ---------- SWING DNA ---------- */
.swr-dna-wrap {
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: var(--bl-surface-1);
    padding: 1.4rem 1.6rem 1.5rem;
    margin-bottom: 1.2rem;
}
.swr-dna-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.55rem;
    margin-top: 0.4rem;
}
.swr-dna-row {
    display: grid;
    grid-template-columns: 170px 1fr 56px;
    gap: 0.85rem;
    align-items: center;
}
@media (max-width: 640px) {
    .swr-dna-row { grid-template-columns: 130px 1fr 48px; }
}
.swr-dna-label {
    font-family: var(--bl-sans);
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--bl-ink-80);
    letter-spacing: -0.005em;
}
.swr-dna-bar {
    position: relative;
    height: 10px;
    border-radius: 6px;
    background: rgba(255,255,255,0.05);
    overflow: hidden;
}
.swr-dna-fill {
    position: absolute; left: 0; top: 0; bottom: 0;
    border-radius: 6px;
    transition: width 0.6s ease;
}
.swr-dna-fill.is-elite   { background: linear-gradient(90deg, #6ee7b7, #34d399); }
.swr-dna-fill.is-strong  { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.swr-dna-fill.is-building{ background: linear-gradient(90deg, #ff6058, #c91e15); }
.swr-dna-pct {
    font-family: var(--bl-mono);
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    text-align: right;
    letter-spacing: -0.01em;
}

/* ---------- VS LAST SWING ---------- */
.swr-vs-card {
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: var(--bl-surface-1);
    padding: 1.2rem 1.4rem 1.3rem;
    margin-bottom: 1.2rem;
}
.swr-vs-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.7rem;
    margin-top: 0.6rem;
}
@media (max-width: 640px) {
    .swr-vs-row { grid-template-columns: repeat(2, 1fr); }
}
.swr-vs-tile {
    border-radius: var(--bl-radius-md);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.02);
    padding: 0.7rem 0.85rem;
}
.swr-vs-label {
    font-family: var(--bl-mono);
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
}
.swr-vs-value {
    font-family: var(--bl-sans);
    font-size: 1.25rem;
    font-weight: 800;
    letter-spacing: -0.022em;
    color: var(--bl-ink-100);
    margin-top: 0.22rem;
    line-height: 1.15;
}
.swr-vs-delta {
    font-family: var(--bl-mono);
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.18rem;
}
.swr-vs-delta.is-up   { color: #34d399; }
.swr-vs-delta.is-down { color: #ff6058; }
.swr-vs-delta.is-flat { color: var(--bl-ink-60); }

/* ---------- SWING PROGRESS — premium history block ---------- */
.swr-prog {
    position: relative;
    border-radius: var(--bl-radius-xl);
    border: 1px solid var(--bl-line);
    background:
        radial-gradient(ellipse at 0% 0%, rgba(255,59,48,0.06) 0%, transparent 55%),
        linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.012));
    padding: 1.6rem 1.7rem 1.5rem;
    margin-bottom: 1.4rem;
    overflow: hidden;
}
.swr-prog-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.1rem;
    flex-wrap: wrap;
}
.swr-prog-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.24em;
    color: var(--bl-red);
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.swr-prog-title {
    font-family: var(--bl-sans);
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--bl-ink-100);
    line-height: 1.15;
}
.swr-prog-sub {
    font-family: var(--bl-sans);
    font-size: 0.88rem;
    color: var(--bl-ink-60);
    margin-top: 0.3rem;
    line-height: 1.4;
}

/* KPI strip */
.swr-prog-kpis {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.7rem;
    margin-bottom: 1.3rem;
}
@media (max-width: 720px) {
    .swr-prog-kpis { grid-template-columns: repeat(2, 1fr); }
}
.swr-prog-kpi {
    border-radius: var(--bl-radius-md);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.025);
    padding: 0.85rem 0.95rem 0.9rem;
    position: relative;
}
.swr-prog-kpi.is-pb {
    border-color: rgba(110,231,183,0.32);
    background:
        linear-gradient(135deg, rgba(110,231,183,0.08), rgba(255,255,255,0.025));
}
.swr-prog-kpi-label {
    font-family: var(--bl-mono);
    font-size: 0.54rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
}
.swr-prog-kpi-value {
    font-family: var(--bl-sans);
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.028em;
    color: var(--bl-ink-100);
    margin-top: 0.32rem;
    line-height: 1.05;
}
.swr-prog-kpi-foot {
    font-family: var(--bl-mono);
    font-size: 0.66rem;
    font-weight: 700;
    margin-top: 0.32rem;
    color: var(--bl-ink-60);
    letter-spacing: 0.04em;
}
.swr-prog-kpi-foot.is-up   { color: #34d399; }
.swr-prog-kpi-foot.is-down { color: #ff6058; }
.swr-prog-kpi-foot.is-flat { color: var(--bl-ink-60); }
.swr-prog-kpi-foot.is-pb   { color: #6ee7b7; }

/* Trendline (SVG sparkline) */
.swr-prog-trend {
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.018);
    padding: 1.1rem 1.2rem 0.95rem;
    margin-bottom: 1.1rem;
}
.swr-prog-trend-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.55rem;
}
.swr-prog-trend-title {
    font-family: var(--bl-sans);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.01em;
}
.swr-prog-trend-meta {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
}
.swr-prog-trend-svg {
    display: block;
    width: 100%;
    height: 110px;
}

/* Movers — two big callouts (Biggest Gain | Biggest Slip) */
.swr-prog-movers {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
    margin-bottom: 1.1rem;
}
@media (max-width: 640px) {
    .swr-prog-movers { grid-template-columns: 1fr; }
}
.swr-prog-mover {
    position: relative;
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.02);
    padding: 1rem 1.2rem 1.05rem;
    overflow: hidden;
}
.swr-prog-mover.is-up {
    border-color: rgba(110,231,183,0.28);
    background:
        linear-gradient(135deg, rgba(110,231,183,0.06), rgba(255,255,255,0.018));
}
.swr-prog-mover.is-down {
    border-color: rgba(255,96,88,0.28);
    background:
        linear-gradient(135deg, rgba(255,96,88,0.06), rgba(255,255,255,0.018));
}
.swr-prog-mover-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.56rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
    display: flex; align-items: center; gap: 0.45rem;
}
.swr-prog-mover.is-up .swr-prog-mover-eyebrow   { color: #34d399; }
.swr-prog-mover.is-down .swr-prog-mover-eyebrow { color: #ff6058; }
.swr-prog-mover.is-flat .swr-prog-mover-eyebrow { color: var(--bl-ink-40); }
.swr-prog-mover-arrow {
    display: inline-flex; align-items: center; justify-content: center;
    width: 14px; height: 14px; border-radius: 4px;
    background: currentColor;
    color: #0a0a0a;
    font-size: 0.62rem; font-weight: 900;
    letter-spacing: 0;
}
.swr-prog-mover-cat {
    font-family: var(--bl-sans);
    font-size: 1.1rem;
    font-weight: 800;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    line-height: 1.15;
}
.swr-prog-mover-delta {
    font-family: var(--bl-mono);
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.018em;
    margin-top: 0.32rem;
    line-height: 1;
}
.swr-prog-mover.is-up .swr-prog-mover-delta    { color: #34d399; }
.swr-prog-mover.is-down .swr-prog-mover-delta  { color: #ff6058; }
.swr-prog-mover.is-flat .swr-prog-mover-delta  { color: var(--bl-ink-60); }
.swr-prog-mover-detail {
    font-family: var(--bl-sans);
    font-size: 0.82rem;
    color: var(--bl-ink-60);
    margin-top: 0.45rem;
    line-height: 1.4;
}

/* Category deltas grid */
.swr-prog-cats {
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.018);
    padding: 1rem 1.15rem 1.05rem;
}
.swr-prog-cats-head {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--bl-ink-40);
    margin-bottom: 0.6rem;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
}
.swr-prog-cats-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.4rem;
}
.swr-prog-cat-row {
    display: grid;
    grid-template-columns: 140px 1fr 70px;
    gap: 0.9rem;
    align-items: center;
}
@media (max-width: 640px) {
    .swr-prog-cat-row { grid-template-columns: 110px 1fr 64px; }
}
.swr-prog-cat-label {
    font-family: var(--bl-sans);
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--bl-ink-80);
    letter-spacing: -0.005em;
}
.swr-prog-cat-bar {
    position: relative;
    height: 8px;
    border-radius: 5px;
    background: rgba(255,255,255,0.06);
    overflow: hidden;
}
.swr-prog-cat-fill-prev {
    position: absolute; left: 0; top: 0; bottom: 0;
    background: rgba(255,255,255,0.16);
    border-radius: 5px;
}
.swr-prog-cat-fill-curr {
    position: absolute; left: 0; top: 0; bottom: 0;
    border-radius: 5px;
    transition: width 0.6s ease;
}
.swr-prog-cat-fill-curr.is-up   { background: linear-gradient(90deg, #6ee7b7, #34d399); }
.swr-prog-cat-fill-curr.is-down { background: linear-gradient(90deg, #ff6058, #c91e15); }
.swr-prog-cat-fill-curr.is-flat { background: linear-gradient(90deg, #d4d4d4, #8b8b8b); }
.swr-prog-cat-fill-curr.is-new  { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.swr-prog-cat-delta {
    font-family: var(--bl-mono);
    font-size: 0.78rem;
    font-weight: 700;
    text-align: right;
    letter-spacing: -0.005em;
}
.swr-prog-cat-delta.is-up   { color: #34d399; }
.swr-prog-cat-delta.is-down { color: #ff6058; }
.swr-prog-cat-delta.is-flat { color: var(--bl-ink-60); }
.swr-prog-cat-delta.is-new  { color: #fbbf24; }

/* Baseline empty state — first-ever swing */
.swr-prog-baseline {
    border-radius: var(--bl-radius-lg);
    border: 1px dashed var(--bl-line-hi);
    background: rgba(255,255,255,0.018);
    padding: 1.2rem 1.4rem;
    text-align: center;
}
.swr-prog-baseline-title {
    font-family: var(--bl-sans);
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--bl-ink-100);
    letter-spacing: -0.015em;
    margin-bottom: 0.35rem;
}
.swr-prog-baseline-sub {
    font-family: var(--bl-sans);
    font-size: 0.9rem;
    color: var(--bl-ink-60);
    line-height: 1.45;
}

/* Recurring-fix badge (used in Top Fixes when a fix has recurred) */
.swr-fix-recurring {
    display: inline-flex;
    align-items: center;
    gap: 0.36rem;
    font-family: var(--bl-mono);
    font-size: 0.54rem;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #fbbf24;
    padding: 0.22rem 0.5rem;
    border-radius: 999px;
    border: 1px solid rgba(251,191,36,0.35);
    background: rgba(251,191,36,0.08);
    margin-left: 0.55rem;
}
.swr-fix-history {
    font-family: var(--bl-sans);
    font-size: 0.82rem;
    color: var(--bl-ink-60);
    margin-top: 0.55rem;
    padding: 0.5rem 0.75rem;
    border-left: 2px solid rgba(251,191,36,0.45);
    background: rgba(251,191,36,0.05);
    border-radius: 0 8px 8px 0;
    line-height: 1.45;
}
.swr-fix-history strong { color: var(--bl-ink-100); }
.swr-fix-history .is-up   { color: #34d399; font-weight: 700; }
.swr-fix-history .is-down { color: #ff6058; font-weight: 700; }

/* ---------- MLB COMP FEATURED CARD ---------- */
.swr-mlb {
    position: relative;
    border-radius: var(--bl-radius-xl);
    border: 1px solid var(--bl-line);
    background:
        linear-gradient(135deg, rgba(255,59,48,0.05), rgba(255,255,255,0.022));
    padding: 1.5rem 1.6rem;
    overflow: hidden;
    margin-bottom: 1.2rem;
}
.swr-mlb-grid {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 1.3rem;
    align-items: center;
}
@media (max-width: 540px) {
    .swr-mlb-grid { grid-template-columns: 88px 1fr; }
}
.swr-mlb-avatar {
    width: 110px; height: 110px;
    border-radius: 50%;
    background:
        radial-gradient(circle at 35% 30%, rgba(255,255,255,0.08), rgba(255,255,255,0.01)),
        linear-gradient(135deg, #1a1a1a, #0b0b0b);
    border: 1px solid var(--bl-line-hi);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--bl-sans);
    font-weight: 800;
    font-size: 2.2rem;
    color: var(--bl-ink-100);
    letter-spacing: -0.04em;
    box-shadow: 0 14px 30px -15px rgba(255,59,48,0.4);
}
@media (max-width: 540px) {
    .swr-mlb-avatar { width: 88px; height: 88px; font-size: 1.7rem; }
}
.swr-mlb-name {
    font-family: var(--bl-sans);
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--bl-ink-100);
    line-height: 1.1;
}
.swr-mlb-meta {
    font-family: var(--bl-sans);
    font-size: 0.88rem;
    color: var(--bl-ink-60);
    margin-top: 0.25rem;
}
.swr-mlb-style {
    font-family: var(--bl-sans);
    font-size: 0.95rem;
    color: var(--bl-ink-80);
    font-style: italic;
    margin-top: 0.5rem;
    line-height: 1.4;
}
.swr-mlb-traits {
    display: flex; flex-wrap: wrap; gap: 0.4rem;
    margin-top: 0.7rem;
}
.swr-mlb-trait {
    font-family: var(--bl-mono);
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--bl-red);
    padding: 0.25rem 0.55rem;
    border-radius: 999px;
    border: 1px solid rgba(255,59,48,0.3);
    background: rgba(255,59,48,0.06);
}

/* ---------- DRILL PLAN — premium drill cards ---------- */
.swr-priority {
    margin-bottom: 1rem;
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: var(--bl-surface-1);
    overflow: hidden;
}
.swr-priority-head {
    display: flex; align-items: center; gap: 0.85rem;
    padding: 0.95rem 1.2rem 0.9rem;
    border-bottom: 1px solid var(--bl-line);
    background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.005));
}
.swr-priority-num {
    width: 32px; height: 32px;
    border-radius: 10px;
    background: var(--bl-red);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--bl-mono);
    font-weight: 800;
    font-size: 0.88rem;
    letter-spacing: -0.01em;
}
.swr-priority-title {
    font-family: var(--bl-sans);
    font-size: 1.05rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--bl-ink-100);
    flex: 1 1 auto;
}
.swr-priority-count {
    font-family: var(--bl-mono);
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    color: var(--bl-ink-40);
    text-transform: uppercase;
}
.swr-priority-why {
    padding: 0.85rem 1.2rem 0.4rem;
    font-family: var(--bl-sans);
    font-size: 0.9rem;
    color: var(--bl-ink-60);
    font-style: italic;
    line-height: 1.45;
}
.swr-drill-list {
    padding: 0.6rem 1.2rem 1.1rem;
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.55rem;
}
.swr-drill {
    position: relative;
    border-radius: var(--bl-radius-md);
    border: 1px solid var(--bl-line);
    background: rgba(255,255,255,0.022);
    padding: 0.85rem 1rem 0.9rem 1.1rem;
    transition: transform .2s ease, border-color .2s ease;
}
.swr-drill:hover {
    transform: translateX(2px);
    border-color: rgba(255,59,48,0.35);
}
.swr-drill::before {
    content: "";
    position: absolute;
    left: 0; top: 12%; bottom: 12%;
    width: 3px;
    background: var(--bl-red);
    border-radius: 2px;
    opacity: 0.6;
}
.swr-drill-row {
    display: flex; align-items: baseline; gap: 0.7rem;
    margin-bottom: 0.3rem;
}
.swr-drill-num {
    font-family: var(--bl-mono);
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--bl-red);
    letter-spacing: 0.06em;
    min-width: 18px;
}
.swr-drill-name {
    font-family: var(--bl-sans);
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.015em;
    flex: 1 1 auto;
}
.swr-drill-reps {
    font-family: var(--bl-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--bl-ink-60);
    padding: 0.18rem 0.55rem;
    border-radius: 6px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--bl-line);
    white-space: nowrap;
}
.swr-drill-how {
    font-family: var(--bl-sans);
    font-size: 0.9rem;
    color: var(--bl-ink-80);
    line-height: 1.5;
    margin-left: calc(18px + 0.7rem);
}

/* ---------- STRENGTHS ---------- */
.swr-strength-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
}
@media (max-width: 640px) {
    .swr-strength-row { grid-template-columns: 1fr; }
}
.swr-strength {
    border-radius: var(--bl-radius-md);
    border: 1px solid rgba(110,231,183,0.18);
    background:
        linear-gradient(135deg, rgba(52,211,153,0.06), rgba(255,255,255,0.012));
    padding: 0.95rem 1.05rem 1rem;
}
.swr-strength-head {
    display: flex; align-items: center; gap: 0.5rem;
    margin-bottom: 0.45rem;
}
.swr-strength-mark {
    width: 24px; height: 24px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6ee7b7, #34d399);
    color: #062919;
    display: flex; align-items: center; justify-content: center;
    font-weight: 900;
    font-size: 0.75rem;
}
.swr-strength-cat {
    font-family: var(--bl-sans);
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.015em;
    flex: 1 1 auto;
}
.swr-strength-pct {
    font-family: var(--bl-sans);
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: #6ee7b7;
    line-height: 1;
    margin: 0.25rem 0 0.3rem;
}
.swr-strength-sub {
    font-family: var(--bl-mono);
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    color: var(--bl-ink-60);
}

/* ---------- METRIC DETAIL ---------- */
.swr-metric-group {
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: var(--bl-surface-1);
    padding: 1.1rem 1.3rem 1.2rem;
    margin-bottom: 0.85rem;
}
.swr-metric-group-title {
    font-family: var(--bl-sans);
    font-size: 1.02rem;
    font-weight: 800;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    margin-bottom: 0.65rem;
    display: flex; align-items: center; gap: 0.55rem;
}
.swr-metric-group-title::after {
    content: "";
    flex: 1 1 auto;
    height: 1px;
    background: var(--bl-line);
    margin-left: 0.4rem;
}
.swr-metric-row {
    display: grid;
    grid-template-columns: 200px 1fr 90px 56px;
    gap: 0.7rem;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px dashed var(--bl-line);
}
.swr-metric-row:last-child { border-bottom: 0; }
@media (max-width: 720px) {
    .swr-metric-row { grid-template-columns: 1fr 60px 48px; }
    .swr-metric-row .swr-metric-bar-wrap { display: none; }
}
.swr-metric-label {
    font-family: var(--bl-sans);
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--bl-ink-80);
    letter-spacing: -0.005em;
    line-height: 1.3;
}
.swr-metric-label.is-flagged::before {
    content: "⚠ ";
    color: #f6c453;
}
.swr-metric-bar-wrap {
    height: 7px;
    background: rgba(255,255,255,0.04);
    border-radius: 5px;
    overflow: hidden;
}
.swr-metric-bar {
    height: 100%;
    border-radius: 5px;
    transition: width 0.5s ease;
}
.swr-metric-bar.is-elite   { background: linear-gradient(90deg, #6ee7b7, #34d399); }
.swr-metric-bar.is-strong  { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.swr-metric-bar.is-building{ background: linear-gradient(90deg, #ff6058, #c91e15); }
.swr-metric-vals {
    font-family: var(--bl-mono);
    font-size: 0.72rem;
    color: var(--bl-ink-60);
    letter-spacing: -0.01em;
    line-height: 1.25;
    text-align: right;
}
.swr-metric-vals strong {
    display: block;
    color: var(--bl-ink-100);
    font-weight: 700;
}
.swr-metric-pct {
    font-family: var(--bl-mono);
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--bl-ink-100);
    letter-spacing: -0.02em;
    text-align: right;
}

/* ---------- EXPORT BAR (Print / PDF) ---------- */
.swr-export-bar {
    display: flex; gap: 0.55rem; flex-wrap: wrap;
    margin-bottom: 1rem;
}

/* ---------- PRINT MEDIA OVERRIDES ---------- */
@media print {
    [data-testid="stSidebar"], header, footer, .stApp [data-testid="stToolbar"] {
        display: none !important;
    }
    .swr-hero, .swr-coach, .swr-fix, .swr-dna-wrap, .swr-mlb, .swr-priority,
    .swr-strength, .swr-metric-group {
        break-inside: avoid;
        box-shadow: none !important;
    }
}
</style>
"""

# Inject CSS on EVERY render — see comment for why a session-state guard
# breaks here.
def _ensure_css():
    """Inject the swing-report local CSS namespace.

    IMPORTANT: this MUST run on every render, NOT just the first time per
    session. Streamlit replays the entire script on every interaction, and
    `st.markdown(_SR_LOCAL_CSS, unsafe_allow_html=True)` only puts the <style>
    tag into the DOM on the script path that produced it. If the user
    navigates to a different page (e.g. lands on Dashboard first, then opens
    a saved report), the previous <style> element belongs to a render tree
    that no longer exists and the saved-report page renders fully unstyled.
    A `session_state["_swr_css_loaded"]` guard makes this worse — it sticks
    True across pages so injection is permanently skipped for the rest of
    the session.

    The cost of always-injecting is one extra <style> tag in the DOM per
    render, which is harmless: the browser dedupes identical rules and a
    single 700-line stylesheet is trivial.
    """
    st.markdown(_SR_LOCAL_CSS, unsafe_allow_html=True)


# ============================================================
#                     DATA HELPERS
# ============================================================

def _score_band_from_score(score) -> Tuple[str, str, str]:
    """Returns (band_key, band_label, hex_color)."""
    try:
        s = float(score)
    except Exception:
        return ("unknown", "—", "#8b8b8b")
    if s >= 80:
        return ("elite", "Elite Mechanics", "#34d399")
    if s >= 60:
        return ("strong", "Strong Foundation", "#fbbf24")
    if s >= 40:
        return ("building", "Building Block", "#ff6058")
    return ("ground", "Ground Floor", "#ff6058")


def _band_class_for_pct(pct: float) -> str:
    """Returns swr-dna-fill / swr-metric-bar variant class for a 0-100 match %."""
    if pct >= 80:
        return "is-elite"
    if pct >= 60:
        return "is-strong"
    return "is-building"


def _extract_ref_info(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize MLB reference info regardless of whether record came from
    live `result` (has `reference` dict) or saved record (only `reference_name`).
    """
    ref = record.get("reference")
    if isinstance(ref, dict) and ref.get("name"):
        return {
            "name":   ref.get("name") or "Unknown",
            "team":   ref.get("team", ""),
            "position": ref.get("position", ""),
            "style":  ref.get("style", ""),
            "source": ref.get("source", ""),
            "auto_reason": ref.get("auto_reason", ""),
        }
    return {
        "name":   record.get("reference_name") or "Unknown",
        "team":   "",
        "position": "",
        "style":  "",
        "source": "",
        "auto_reason": "",
    }


def _initials(name: str) -> str:
    if not name:
        return "??"
    parts = [p for p in name.replace(".", "").split() if p]
    if not parts:
        return name[:2].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ----- Coach's Summary -----------------------------------------------------

def coach_summary(record: Dict[str, Any]) -> str:
    """
    Auto-generate a one-paragraph coach's summary from the record:
    leads with score & band, names the MLB comp, names the #1 strength,
    names the #1 fix, closes with a confidence statement.
    """
    score = record.get("score")
    band_key, band_label, _ = _score_band_from_score(score)
    ref = _extract_ref_info(record)
    narratives = record.get("narratives") or []
    strengths = record.get("strengths") or []

    bits: List[str] = []

    if isinstance(score, (int, float)):
        bits.append(
            f"Your swing landed at <strong>{int(round(float(score)))}/100</strong> "
            f"versus <strong>{html.escape(ref['name'])}</strong> — "
            f"that's <strong>{band_label.lower()}</strong>."
        )
    else:
        bits.append(f"Your swing was compared to <strong>{html.escape(ref['name'])}</strong>.")

    # Strength callout
    if strengths:
        s0 = strengths[0]
        cat = s0.get("category_label", "your foundation")
        pct = s0.get("sim_pct")
        if pct is not None:
            bits.append(
                f"What's already working: <strong>{html.escape(str(cat))}</strong> "
                f"is a <strong>{int(pct)}% match</strong> — keep that locked in."
            )
        else:
            bits.append(f"<strong>{html.escape(str(cat))}</strong> is already a strong point.")

    # Top fix callout
    if narratives:
        n0 = narratives[0]
        title = (n0.get("title") or "the top mechanic").strip().title()
        bits.append(
            f"The biggest unlock is <strong>{html.escape(title)}</strong> — "
            f"that's where the next jump in your score lives."
        )

    # Outlook
    if band_key == "elite":
        bits.append("You're already in MLB territory on the fundamentals. Polish the details and stay consistent.")
    elif band_key == "strong":
        bits.append("You've got the bones of a legit swing. Lock in the priority fix and the score moves fast.")
    elif band_key == "building":
        bits.append("Real foundation here — focus on the priority drill block and you'll see a measurable jump in 2-3 sessions.")
    else:
        bits.append("Start with the Priority 1 drills, film again in a week, and track the gap close.")

    return " ".join(bits)


# ----- Top 3 Fixes ---------------------------------------------------------

def top_three_fixes(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return up to 3 prioritized fixes (already provided in record["narratives"]),
    enriched with a severity tier derived from the matching gap's sim_pct.

    Each item: {rank, title, headline, why, fix_feel, severity}
    """
    narratives = record.get("narratives") or []
    gaps = record.get("gaps") or []
    # Build a lookup of gap category -> avg sim_pct
    gap_sim = {}
    for g in gaps:
        sub = g.get("sub_metrics") or []
        if sub:
            avg = sum((s.get("sim_pct") or 0) for s in sub) / max(len(sub), 1)
            gap_sim[(g.get("category") or "").lower()] = avg
            gap_sim[(g.get("category_label") or "").lower()] = avg

    out: List[Dict[str, Any]] = []
    for n in narratives[:3]:
        paras = n.get("paragraphs") or []
        headline = paras[0] if len(paras) > 0 else ""
        why      = paras[1].replace("Why it costs you: ", "") if len(paras) > 1 else ""
        fix_feel = paras[2].replace("What the fix feels like: ", "") if len(paras) > 2 else ""

        # Severity from matching gap (lower sim_pct == higher severity)
        title = (n.get("title") or "").lower()
        sim = gap_sim.get(title)
        if sim is None:
            # Try a partial match
            for k, v in gap_sim.items():
                if k and (k in title or title in k):
                    sim = v
                    break
        if sim is None:
            severity = "med"
        elif sim < 50:
            severity = "high"
        elif sim < 70:
            severity = "med"
        else:
            severity = "low"

        out.append({
            "rank":     n.get("rank", len(out) + 1),
            "title":    (n.get("title") or "Fix").title(),
            "headline": headline,
            "why":      why,
            "fix_feel": fix_feel,
            "severity": severity,
        })
    return out


# ----- Swing DNA -----------------------------------------------------------

_DNA_FALLBACK_ORDER = [
    "Stride", "Load", "Rotation", "Hands", "Bat path", "Contact", "Timing", "Posture", "Balance",
]


def swing_dna(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build a Swing DNA list — one row per category in metric_table,
    each with {label, pct, band_class}.

    Picks up to 8 categories sorted by sim_pct DESC (so strengths bubble up).
    """
    metric_table = record.get("metric_table") or {}
    rows: List[Dict[str, Any]] = []
    for group, items in metric_table.items():
        if not items:
            continue
        # Ignore flagged-only groups
        pcts = [r.get("sim_pct") for r in items if r.get("sim_pct") is not None and not r.get("flagged")]
        if not pcts:
            # Fall back to including flagged so the row still shows
            pcts = [r.get("sim_pct") for r in items if r.get("sim_pct") is not None]
        if not pcts:
            continue
        avg = sum(pcts) / max(len(pcts), 1)
        rows.append({
            "label": str(group),
            "pct":   round(avg, 1),
            "band_class": _band_class_for_pct(avg),
        })

    # Stable sort: highest match first (strengths) — feels celebratory
    rows.sort(key=lambda r: r["pct"], reverse=True)
    return rows[:8]


# ----- Compare to Last Swing ----------------------------------------------

def compare_to_last(record: Dict[str, Any], history: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    Find the previous swing in `history` (excluding the current record by id
    if possible) and compute a small score delta + biggest mover.

    Returns None if no prior swing.
    """
    if not history or len(history) < 2:
        return None

    current_id = record.get("id")
    current_ts = record.get("timestamp")

    # Sort history by timestamp ascending if possible (Supabase usually returns ascending,
    # but we don't want to assume)
    def _ts(rec):
        return str(rec.get("timestamp") or rec.get("date") or "")
    sorted_hist = sorted(history, key=_ts)

    # Find index of current
    idx = None
    for i, rec in enumerate(sorted_hist):
        if (current_id is not None and rec.get("id") == current_id) or \
           (current_ts is not None and rec.get("timestamp") == current_ts):
            idx = i
            break

    if idx is None:
        # If we can't find the current record in history, assume current is "the latest"
        idx = len(sorted_hist) - 1

    if idx <= 0:
        return None  # current is the first swing — nothing to compare

    prev = sorted_hist[idx - 1]
    curr_score = record.get("score")
    prev_score = prev.get("score")

    try:
        score_delta = float(curr_score) - float(prev_score)
    except Exception:
        score_delta = None

    # Biggest mover by category match %
    curr_dna = {r["label"]: r["pct"] for r in swing_dna(record)}
    prev_dna = {r["label"]: r["pct"] for r in swing_dna(prev)}

    biggest_up = None
    biggest_down = None
    for label, curr_pct in curr_dna.items():
        prev_pct = prev_dna.get(label)
        if prev_pct is None:
            continue
        delta = curr_pct - prev_pct
        if biggest_up is None or delta > biggest_up[1]:
            biggest_up = (label, delta)
        if biggest_down is None or delta < biggest_down[1]:
            biggest_down = (label, delta)

    return {
        "prev_score":   prev_score,
        "curr_score":   curr_score,
        "score_delta":  score_delta,
        "prev_ref":     prev.get("reference_name") or "—",
        "prev_date":    prev.get("date") or "previous swing",
        "biggest_up":   biggest_up,
        "biggest_down": biggest_down,
    }


# ----- Swing Progress (richer, history-aware) -----------------------------

def swing_progress(record: Dict[str, Any],
                   history: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Richer "how you're tracking" data for the Swing Progress section.

    Returns a dict with everything the premium progress renderer needs:
        * score_history    list[(swing_num, score)]  — chronologically asc
        * curr_score       float                     — current swing score
        * prev_score       float | None              — immediately prior score
        * score_delta      float | None              — curr - prev
        * personal_best    bool                      — curr is the highest score
        * pb_score         float                     — historical max (incl curr)
        * pb_gap           float                     — pb - curr (0 if PB)
        * streak           int                       — consecutive improvements (incl curr)
        * total_swings     int                       — count of distinct swings seen
        * days_since_last  int | None                — days between this & prior
        * prev_date        str                       — prior swing's date string
        * prev_ref         str                       — prior swing's MLB ref
        * biggest_up       (label, delta) | None     — best category mover up
        * biggest_down     (label, delta) | None     — worst category mover down
        * category_deltas  list[{label, prev_pct, curr_pct, delta, direction}]
                                                    — one row per DNA category
                                                      shared between curr/prev
        * has_prior        bool                      — True iff prev exists

    Returns None ONLY if there is no current score to anchor the view.
    Even with a single swing (no prior), returns a populated dict with
    has_prior=False so the renderer can show a "baseline" empty state.
    """
    try:
        curr_score_f = float(record.get("score"))
    except (TypeError, ValueError):
        return None

    # Build chronologically-ascending history of (swing_num, score) tuples.
    # Falls back to enumerating positions if swing_number isn't set.
    def _ts(rec):
        return str(rec.get("timestamp") or rec.get("date") or "")

    sorted_hist = sorted(history or [], key=_ts)
    score_history: List[Tuple[Any, float]] = []
    for i, rec in enumerate(sorted_hist, start=1):
        try:
            s = float(rec.get("score"))
        except (TypeError, ValueError):
            continue
        num = rec.get("swing_number") or i
        score_history.append((num, s))

    # If the current record isn't already in the history (e.g. live result
    # before save), append it so the sparkline & trend math include it.
    current_id = record.get("id")
    current_ts = record.get("timestamp")
    in_history = False
    for rec in sorted_hist:
        if (current_id is not None and rec.get("id") == current_id) or \
           (current_ts is not None and rec.get("timestamp") == current_ts):
            in_history = True
            break
    if not in_history:
        num = record.get("swing_number") or (len(score_history) + 1)
        score_history.append((num, curr_score_f))

    # Locate the prior swing (the one immediately before current, by ts).
    prev_rec: Optional[Dict[str, Any]] = None
    if sorted_hist:
        # Find current's index, fall back to "last in list" if not found.
        idx = None
        for i, rec in enumerate(sorted_hist):
            if (current_id is not None and rec.get("id") == current_id) or \
               (current_ts is not None and rec.get("timestamp") == current_ts):
                idx = i
                break
        if idx is None:
            idx = len(sorted_hist)  # past the end -> prev is last sorted
        if idx > 0:
            prev_rec = sorted_hist[idx - 1]
        elif idx == 0 and len(sorted_hist) > 1:
            # current is first in history; nothing prior
            prev_rec = None

    # Score delta vs prior
    prev_score_f: Optional[float] = None
    score_delta: Optional[float] = None
    prev_date = ""
    prev_ref = ""
    days_since_last: Optional[int] = None
    if prev_rec is not None:
        try:
            prev_score_f = float(prev_rec.get("score"))
            score_delta = curr_score_f - prev_score_f
        except (TypeError, ValueError):
            prev_score_f = None
            score_delta = None
        prev_date = str(prev_rec.get("date") or "previous swing")
        prev_ref = str(prev_rec.get("reference_name") or "—")
        # Try to compute days between (best-effort)
        try:
            from datetime import datetime
            curr_ts_str = str(record.get("timestamp") or record.get("date") or "")
            prev_ts_str = str(prev_rec.get("timestamp") or prev_rec.get("date") or "")
            # Accept ISO-ish or date-only formats
            def _parse(t: str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%b %d, %Y",
                            "%B %d, %Y"):
                    try:
                        return datetime.strptime(t[:len(fmt)+4], fmt)
                    except Exception:
                        continue
                return None
            c_dt = _parse(curr_ts_str)
            p_dt = _parse(prev_ts_str)
            if c_dt and p_dt:
                days_since_last = max(0, (c_dt.date() - p_dt.date()).days)
        except Exception:
            days_since_last = None

    # Personal best
    all_scores = [s for _, s in score_history]
    pb_score = max(all_scores) if all_scores else curr_score_f
    personal_best = curr_score_f >= pb_score
    pb_gap = max(0.0, pb_score - curr_score_f)

    # Improvement streak: how many consecutive swings (ending at current)
    # show a non-negative delta vs the one before it.
    streak = 0
    if len(score_history) >= 2:
        # Walk backwards from the end (curr is last). Count while each
        # score >= the previous one.
        for i in range(len(score_history) - 1, 0, -1):
            if score_history[i][1] >= score_history[i - 1][1]:
                streak += 1
            else:
                break

    # Category deltas via DNA helper
    curr_dna_rows = swing_dna(record)
    prev_dna = {r["label"]: r["pct"] for r in swing_dna(prev_rec)} if prev_rec else {}

    category_deltas: List[Dict[str, Any]] = []
    biggest_up: Optional[Tuple[str, float]] = None
    biggest_down: Optional[Tuple[str, float]] = None

    for row in curr_dna_rows:
        label = row["label"]
        curr_pct = row["pct"]
        prev_pct = prev_dna.get(label)
        if prev_pct is None:
            category_deltas.append({
                "label": label,
                "prev_pct": None,
                "curr_pct": curr_pct,
                "delta": None,
                "direction": "new",
            })
            continue
        d = curr_pct - prev_pct
        if d > 0.5:
            direction = "up"
        elif d < -0.5:
            direction = "down"
        else:
            direction = "flat"
        category_deltas.append({
            "label": label,
            "prev_pct": prev_pct,
            "curr_pct": curr_pct,
            "delta": d,
            "direction": direction,
        })
        if biggest_up is None or d > biggest_up[1]:
            biggest_up = (label, d)
        if biggest_down is None or d < biggest_down[1]:
            biggest_down = (label, d)

    return {
        "score_history":   score_history,
        "curr_score":      curr_score_f,
        "prev_score":      prev_score_f,
        "score_delta":     score_delta,
        "personal_best":   personal_best,
        "pb_score":        pb_score,
        "pb_gap":          pb_gap,
        "streak":          streak,
        "total_swings":    len({(r.get("id") or r.get("timestamp") or i)
                                for i, r in enumerate(sorted_hist)}) +
                            (0 if in_history else 1),
        "days_since_last": days_since_last,
        "prev_date":       prev_date,
        "prev_ref":        prev_ref,
        "biggest_up":      biggest_up,
        "biggest_down":    biggest_down,
        "category_deltas": category_deltas,
        "has_prior":       prev_rec is not None,
    }


# ----- Recurrence-aware Top Fixes -----------------------------------------

def enrich_fixes_with_history(
    fixes: List[Dict[str, Any]],
    record: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Annotate each fix with recurrence info from prior swings.

    Adds the following fields to each fix dict (in place + returned):
        * recurrence_count    int   — # of prior swings flagging this fix
        * first_flagged_in    int|None — first prior swing_number where it appeared
        * prev_sim_pct        float|None — sim_pct on this category in prior swing
        * curr_sim_pct        float|None — sim_pct on this category in current swing
        * delta_since_last    float|None — curr - prev
        * is_recurring        bool  — recurrence_count > 0

    Why: Logan's concern was that a player uploading 5 swings would see the
    EXACT same "Why it costs you" block on swing #1 and #5 if the same flaw
    persists. The narrative text itself is deterministic (analyzer output)
    so we don't rewrite it — instead we contextualize it: the renderer can
    say "We flagged this in Swing #2 — you've closed +6pts since then" or
    "Same issue 3 swings in a row — let's lock in the drill plan." That
    makes recurring feedback feel like coaching memory, not a stuck record.
    """
    if not fixes:
        return fixes

    def _ts(rec):
        return str(rec.get("timestamp") or rec.get("date") or "")
    sorted_hist = sorted(history or [], key=_ts)

    # Identify the prior swings (everything strictly before current).
    current_id = record.get("id")
    current_ts = record.get("timestamp")
    prior_swings: List[Dict[str, Any]] = []
    for rec in sorted_hist:
        if (current_id is not None and rec.get("id") == current_id) or \
           (current_ts is not None and rec.get("timestamp") == current_ts):
            break
        prior_swings.append(rec)

    # Build a lookup of {fix_title_lower: [(swing_num, sim_pct_for_category)]}
    # by scanning each prior swing's narratives + gaps.
    def _fix_keys(rec: Dict[str, Any]) -> List[Tuple[str, Optional[float]]]:
        out: List[Tuple[str, Optional[float]]] = []
        ns = rec.get("narratives") or []
        gaps = rec.get("gaps") or []
        gap_sim = {}
        for g in gaps:
            sub = g.get("sub_metrics") or []
            if sub:
                avg = sum((s.get("sim_pct") or 0) for s in sub) / max(len(sub), 1)
                cat = (g.get("category") or "").lower()
                lbl = (g.get("category_label") or "").lower()
                if cat: gap_sim[cat] = avg
                if lbl: gap_sim[lbl] = avg
        for n in ns:
            title = (n.get("title") or "").lower().strip()
            if not title:
                continue
            sim = gap_sim.get(title)
            if sim is None:
                for k, v in gap_sim.items():
                    if k and (k in title or title in k):
                        sim = v
                        break
            out.append((title, sim))
        return out

    prior_index: Dict[str, List[Tuple[int, Optional[float]]]] = {}
    for i, prior in enumerate(prior_swings, start=1):
        swing_num = prior.get("swing_number") or i
        for title, sim in _fix_keys(prior):
            prior_index.setdefault(title, []).append((swing_num, sim))

    # Current swing's sim_pct lookup (so we can compute delta_since_last)
    curr_sim_by_title: Dict[str, Optional[float]] = {
        t: s for t, s in _fix_keys(record)
    }

    for fx in fixes:
        title_l = (fx.get("title") or "").lower().strip()
        # Try exact then partial match
        hits = prior_index.get(title_l, [])
        if not hits:
            for k, v in prior_index.items():
                if k and (k in title_l or title_l in k):
                    hits = v
                    break

        recurrence_count = len(hits)
        first_flagged_in = hits[0][0] if hits else None
        prev_sim = hits[-1][1] if hits and hits[-1][1] is not None else None
        curr_sim = curr_sim_by_title.get(title_l)
        if curr_sim is None:
            for k, v in curr_sim_by_title.items():
                if k and (k in title_l or title_l in k):
                    curr_sim = v
                    break
        delta = None
        if prev_sim is not None and curr_sim is not None:
            delta = curr_sim - prev_sim

        fx["recurrence_count"]  = recurrence_count
        fx["first_flagged_in"]  = first_flagged_in
        fx["prev_sim_pct"]      = prev_sim
        fx["curr_sim_pct"]      = curr_sim
        fx["delta_since_last"]  = delta
        fx["is_recurring"]      = recurrence_count > 0

    return fixes


# ----- MLB Signature Traits -----------------------------------------------

_MLB_TRAITS = {
    "mike trout":      ["Compact load", "Quick hands", "Explosive rotation"],
    "shohei ohtani":   ["Elite balance", "Big leg lift", "Whip-fast hands"],
    "aaron judge":     ["Massive launch angle", "Towering finish", "Late hand fire"],
    "juan soto":       ["Patient load", "Sharp barrel direction", "Hip-led rotation"],
    "ronald acuna jr": ["Explosive stride", "Fast bat path", "Aggressive hip drive"],
    "freddie freeman": ["Smooth tempo", "Tall posture", "On-time barrel"],
    "jose altuve":     ["Compact swing", "Quick rotation", "Stays balanced"],
    "bryce harper":    ["Big leg kick", "Long extension", "Hip-shoulder separation"],
    "fernando tatis jr": ["Explosive load", "Quick hands", "Aggressive finish"],
    "manny machado":   ["Tall stance", "Smooth load", "Whippy hands"],
    "matt olson":      ["Quiet load", "Compact path", "Drives through"],
    "vladimir guerrero jr": ["Quick wrists", "Bat speed", "Aggressive attack"],
    "yordan alvarez":  ["Smooth tempo", "Big extension", "Stays through it"],
    "kyle tucker":     ["Late hands", "Flat barrel", "Smooth finish"],
}


def mlb_signature_traits(ref_name: str) -> List[str]:
    if not ref_name:
        return []
    key = ref_name.strip().lower()
    return _MLB_TRAITS.get(key, [])


# ============================================================
#                       RENDERERS
# ============================================================

def _render_hero(record: Dict[str, Any]):
    score = record.get("score")
    band_key, band_label, hex_color = _score_band_from_score(score)
    ref = _extract_ref_info(record)
    handedness = record.get("player_handedness", "—")
    duration_ms = record.get("swing_duration_ms")
    date_str = record.get("date", "—")
    swing_num = record.get("swing_number")

    # Display score (rounded)
    try:
        score_display = int(round(float(score)))
        score_pct = max(0.0, min(1.0, float(score) / 100.0))
    except Exception:
        score_display = "—"
        score_pct = 0.0

    # SVG ring math
    radius = 78
    stroke = 12
    circumference = 2 * math.pi * radius
    dash_offset = circumference * (1 - score_pct)

    band_border = {
        "elite":    f"rgba(110,231,183,0.45);background:rgba(110,231,183,0.08);color:#6ee7b7",
        "strong":   f"rgba(251,191,36,0.45);background:rgba(251,191,36,0.08);color:#fbbf24",
        "building": f"rgba(255,96,88,0.45);background:rgba(255,96,88,0.08);color:#ff6058",
        "ground":   f"rgba(255,96,88,0.45);background:rgba(255,96,88,0.08);color:#ff6058",
    }.get(band_key, "rgba(255,255,255,0.18);background:rgba(255,255,255,0.04);color:#d4d4d4")

    swing_label = f"SWING #{swing_num}" if swing_num else "SWING ANALYSIS"

    dur_str = f"{int(round(duration_ms))} ms" if isinstance(duration_ms, (int, float)) and duration_ms else "—"

    html_blob = f"""
<div class="swr-hero">
  <div class="swr-hero-grid">
    <div class="swr-ring-wrap">
      <div class="swr-ring-stack">
        <svg class="swr-ring-svg" width="200" height="200" viewBox="0 0 200 200">
          <circle class="swr-ring-bg" cx="100" cy="100" r="{radius}"
                  fill="none" stroke-width="{stroke}" />
          <circle class="swr-ring-fg" cx="100" cy="100" r="{radius}"
                  fill="none" stroke="{hex_color}" stroke-width="{stroke}"
                  stroke-linecap="round"
                  stroke-dasharray="{circumference:.2f}"
                  stroke-dashoffset="{dash_offset:.2f}"
                  transform="rotate(-90 100 100)" />
        </svg>
        <div class="swr-ring-center">
          <div class="swr-ring-num">{score_display}</div>
          <div class="swr-ring-out-of">/ 100 · SCORE</div>
        </div>
      </div>
      <div class="swr-ring-band" style="border-color:{band_border}">{html.escape(band_label)}</div>
    </div>

    <div>
      <div class="swr-eyebrow">{swing_label} · {html.escape(str(date_str))}</div>
      <div class="swr-hero-title">vs. {html.escape(ref['name'])}</div>
      <div class="swr-hero-sub">{html.escape(ref.get('style') or 'AI-powered mechanical comparison · BarrelLabs Performance Lab')}</div>

      <div class="swr-chip-row">
        <div class="swr-chip">
          <div class="swr-chip-label">Handedness</div>
          <div class="swr-chip-value">{html.escape(str(handedness))}</div>
        </div>
        <div class="swr-chip">
          <div class="swr-chip-label">Swing Duration</div>
          <div class="swr-chip-value">{dur_str}</div>
        </div>
        <div class="swr-chip">
          <div class="swr-chip-label">MLB Comp</div>
          <div class="swr-chip-value">{html.escape(ref['name'])}</div>
        </div>
      </div>
    </div>
  </div>
</div>
"""
    _md(html_blob)


def _render_section_header(num: str, title: str, sub: Optional[str] = None):
    """Render a section header as ONE st.markdown call so Streamlit's stMarkdown
    wrapper can't insert phantom margin between the title row and the subtitle.
    The wrapper div .swr-sec-wrap owns the top/bottom spacing; .swr-sec-sub uses
    a small positive margin-top to sit cleanly under the title row."""
    sub_html = (
        f'<div class="swr-sec-sub">{html.escape(sub)}</div>' if sub else ""
    )
    st.markdown(
        f'<div class="swr-sec-wrap">'
        f'<div class="swr-sec-head">'
        f'<div class="swr-sec-num">{html.escape(num)}</div>'
        f'<div class="swr-sec-title">{html.escape(title)}</div>'
        f'</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_coach_summary(record: Dict[str, Any]):
    summary = coach_summary(record)
    _md(f"""
<div class="swr-coach">
  <div class="swr-coach-eyebrow"><span class="swr-coach-icon">C</span> Coach's Summary</div>
  <div class="swr-coach-body">{summary}</div>
</div>
""")


def _render_top_fixes(record: Dict[str, Any],
                      history: Optional[List[Dict[str, Any]]] = None):
    """Render the Top 3 Fixes block.

    When history is provided, each fix is enriched with recurrence data
    (was this same issue flagged in earlier swings? has the player closed
    or widened the gap since?). Recurring fixes get a "RECURRING N×" pill
    and a coaching-memory line under the narrative — addressing the
    redundant-text concern by adding context instead of rewriting the
    deterministic analyzer narrative.
    """
    fixes = top_three_fixes(record)
    if not fixes:
        st.info("No specific fixes flagged for this swing — your mechanics are tracking well.")
        return

    # Enrich with history. Safe no-op if history is empty.
    fixes = enrich_fixes_with_history(fixes, record, history)

    sev_label = {"high": "HIGH IMPACT", "med": "MEDIUM IMPACT", "low": "LOW IMPACT"}

    cards_html = '<div class="swr-fixes">'
    for f in fixes:
        sev_cls = f"is-{f['severity']}"
        body_parts = []
        if f["headline"]:
            body_parts.append(f"<p>{f['headline']}</p>")
        if f["why"]:
            body_parts.append('<span class="swr-fix-sub-label">Why it costs you</span>')
            body_parts.append(f"<p>{f['why']}</p>")
        if f["fix_feel"]:
            body_parts.append('<span class="swr-fix-sub-label">What the fix feels like</span>')
            body_parts.append(f"<p>{f['fix_feel']}</p>")

        # Recurring pill in header
        recur_count = f.get("recurrence_count") or 0
        if recur_count == 1:
            recur_badge = '<span class="swr-fix-recurring">⟳ RECURRING</span>'
        elif recur_count >= 2:
            recur_badge = f'<span class="swr-fix-recurring">⟳ RECURRING · {recur_count + 1}×</span>'
        else:
            recur_badge = ""

        # Coaching-memory line — only when we have prior context
        history_line = ""
        if f.get("is_recurring"):
            first_n = f.get("first_flagged_in")
            prev_p  = f.get("prev_sim_pct")
            curr_p  = f.get("curr_sim_pct")
            delta_p = f.get("delta_since_last")

            # Compose a single contextual line that says "we've seen this before"
            # and quantifies movement (if measurable) so the player knows
            # whether they're closing the gap or it's still leaking points.
            parts: List[str] = []
            if first_n is not None:
                parts.append(f"Same flag in <strong>Swing #{html.escape(str(first_n))}</strong>")
            else:
                parts.append("Flagged before")

            if delta_p is not None and prev_p is not None and curr_p is not None:
                if delta_p > 1.0:
                    parts.append(
                        f"You've closed <span class='is-up'>+{delta_p:.1f}%</span> "
                        f"on this category ({prev_p:.0f}% → {curr_p:.0f}%) — keep stacking it."
                    )
                elif delta_p < -1.0:
                    parts.append(
                        f"Slipped <span class='is-down'>{delta_p:.1f}%</span> "
                        f"({prev_p:.0f}% → {curr_p:.0f}%) — revisit this drill block."
                    )
                else:
                    parts.append(
                        f"Match % held flat at {curr_p:.0f}% — small unlock, big payoff."
                    )
            elif recur_count >= 2:
                parts.append("Three swings running — let's commit to the drill plan below.")
            else:
                parts.append("If it keeps showing up, prioritize the drill below over volume.")

            history_line = (
                f'<div class="swr-fix-history">'
                f'<strong>Coach memory:</strong> {" · ".join(parts)}'
                f'</div>'
            )

        cards_html += f"""
<div class="swr-fix">
  <div class="swr-fix-head">
    <div class="swr-fix-rank">{f['rank']}</div>
    <div class="swr-fix-title">{html.escape(f['title'])}{recur_badge}</div>
    <div class="swr-fix-severity {sev_cls}">{sev_label.get(f['severity'], 'IMPACT')}</div>
  </div>
  <div class="swr-fix-body">{''.join(body_parts)}{history_line}</div>
</div>
"""
    cards_html += "</div>"
    _md(cards_html)


def _render_swing_dna(record: Dict[str, Any]):
    rows = swing_dna(record)
    if not rows:
        return

    rows_html = ""
    for r in rows:
        pct = r["pct"]
        pct_disp = f"{int(round(pct))}%"
        rows_html += f"""
<div class="swr-dna-row">
  <div class="swr-dna-label">{html.escape(r['label'])}</div>
  <div class="swr-dna-bar">
    <div class="swr-dna-fill {r['band_class']}" style="width:{pct:.1f}%;"></div>
  </div>
  <div class="swr-dna-pct">{pct_disp}</div>
</div>
"""

    _md(f"""
<div class="swr-dna-wrap">
  <div class="swr-dna-grid">{rows_html}</div>
</div>
""")


def _render_vs_last(record: Dict[str, Any], history: Optional[List[Dict[str, Any]]]):
    comp = compare_to_last(record, history)
    if not comp:
        return

    sd = comp["score_delta"]
    if sd is None:
        sd_disp = "—"
        sd_cls = "is-flat"
    elif sd > 0:
        sd_disp = f"+{sd:.1f}"
        sd_cls = "is-up"
    elif sd < 0:
        sd_disp = f"{sd:.1f}"
        sd_cls = "is-down"
    else:
        sd_disp = "0.0"
        sd_cls = "is-flat"

    up = comp.get("biggest_up")
    down = comp.get("biggest_down")

    if up and up[1] > 0.5:
        up_disp_label = up[0]
        up_disp_val = f"+{up[1]:.1f}%"
        up_cls = "is-up"
    else:
        up_disp_label = "—"
        up_disp_val = "—"
        up_cls = "is-flat"

    if down and down[1] < -0.5:
        down_disp_label = down[0]
        down_disp_val = f"{down[1]:.1f}%"
        down_cls = "is-down"
    else:
        down_disp_label = "—"
        down_disp_val = "—"
        down_cls = "is-flat"

    prev_score = comp.get("prev_score")
    curr_score = comp.get("curr_score")

    _md(f"""
<div class="swr-vs-card">
  <div style="font-family:var(--bl-sans);font-size:0.92rem;color:var(--bl-ink-60);">
    Compared to your previous swing on <strong style="color:var(--bl-ink-100);">{html.escape(str(comp.get('prev_date')))}</strong>
    (vs. {html.escape(str(comp.get('prev_ref')))}).
  </div>
  <div class="swr-vs-row">
    <div class="swr-vs-tile">
      <div class="swr-vs-label">Swing Score</div>
      <div class="swr-vs-value">{curr_score} <span style="color:var(--bl-ink-40);font-size:0.85rem;font-weight:500;">vs {prev_score}</span></div>
      <div class="swr-vs-delta {sd_cls}">{sd_disp} pts</div>
    </div>
    <div class="swr-vs-tile">
      <div class="swr-vs-label">Biggest Gain</div>
      <div class="swr-vs-value">{html.escape(str(up_disp_label))}</div>
      <div class="swr-vs-delta {up_cls}">{up_disp_val}</div>
    </div>
    <div class="swr-vs-tile">
      <div class="swr-vs-label">Biggest Slip</div>
      <div class="swr-vs-value">{html.escape(str(down_disp_label))}</div>
      <div class="swr-vs-delta {down_cls}">{down_disp_val}</div>
    </div>
  </div>
</div>
""")


def _render_swing_progress(record: Dict[str, Any],
                           history: Optional[List[Dict[str, Any]]]):
    """Premium Swing Progress section — renders right after the hero when
    the player has at least one prior swing. Replaces the old, sparse
    "vs. Your Last Swing" 3-tile strip.

    Layout (top to bottom):
        1. Header eyebrow + title + contextual subline (delta-aware)
        2. 4 KPI tiles: Score (+delta), Personal Best, Streak, Total Swings
        3. Score trendline (SVG sparkline w/ current highlighted)
        4. Two big movers: Biggest Gain | Biggest Slip
        5. Per-category delta grid (full DNA categories incl. flats / new)

    For a first-ever swing (no history yet), renders a slim "this is your
    baseline" empty state so the section doesn't simply vanish.
    """
    prog = swing_progress(record, history)
    if not prog:
        return

    # ---- HEADER (always shown) ----
    if not prog["has_prior"]:
        # First-ever swing — show a baseline empty state and bail
        _md(f"""
<div class="swr-prog">
  <div class="swr-prog-head">
    <div>
      <div class="swr-prog-eyebrow">SWING PROGRESS · BASELINE</div>
      <div class="swr-prog-title">This is your starting line.</div>
      <div class="swr-prog-sub">
        We logged this swing as your baseline. Upload another swing and you'll
        see live deltas across score, category match %, biggest movers, and
        an improvement streak.
      </div>
    </div>
  </div>
  <div class="swr-prog-baseline">
    <div class="swr-prog-baseline-title">Score · {int(round(prog['curr_score']))} / 100</div>
    <div class="swr-prog-baseline-sub">
      Drop your next swing to start tracking progress. Coach gets sharper
      with every rep — recurring issues will surface with history-aware
      context.
    </div>
  </div>
</div>
""")
        return

    # ---- We have a prior swing — full render ----
    curr = int(round(prog["curr_score"]))
    prev = prog["prev_score"]
    delta = prog["score_delta"]

    # KPI 1: Score with delta
    if delta is None:
        delta_cls = "is-flat"
        delta_text = "—"
    elif delta > 0:
        delta_cls = "is-up"
        delta_text = f"▲ +{delta:.1f} pts"
    elif delta < 0:
        delta_cls = "is-down"
        delta_text = f"▼ {delta:.1f} pts"
    else:
        delta_cls = "is-flat"
        delta_text = "→ no change"

    # KPI 2: Personal best
    pb_class = "is-pb" if prog["personal_best"] else ""
    if prog["personal_best"]:
        pb_value = "✓ NEW PB"
        pb_foot_cls = "is-pb"
        pb_foot = f"Tied or surpassed {int(round(prog['pb_score']))}"
    else:
        pb_value = f"{prog['pb_gap']:.0f}"
        pb_foot_cls = "is-flat"
        pb_foot = f"pts to PB ({int(round(prog['pb_score']))})"

    # KPI 3: Streak
    streak = prog["streak"]
    if streak >= 2:
        streak_value = f"{streak}🔥"
        streak_foot_cls = "is-up"
        streak_foot = "in a row"
    elif streak == 1:
        streak_value = "1"
        streak_foot_cls = "is-up"
        streak_foot = "first improvement"
    else:
        streak_value = "—"
        streak_foot_cls = "is-flat"
        streak_foot = "broken — reset"

    # KPI 4: Total swings
    total = prog["total_swings"]
    total_value = str(total)
    total_foot_cls = "is-flat"
    if prog["days_since_last"] is not None:
        d = prog["days_since_last"]
        total_foot = f"+{d} day{'s' if d != 1 else ''} since last" if d > 0 else "same day"
    else:
        total_foot = "logged total"

    # Headline subtitle: dynamic phrasing
    if delta is None:
        sub = f"Tracking against your previous swing on {html.escape(prog['prev_date'])}."
    elif delta > 1:
        sub = (f"You're <strong style='color:#34d399;'>+{delta:.1f} pts</strong> over "
               f"<strong style='color:var(--bl-ink-100);'>{html.escape(prog['prev_date'])}</strong>"
               f" — keep stacking these reps.")
    elif delta < -1:
        sub = (f"You're <strong style='color:#ff6058;'>{delta:.1f} pts</strong> below "
               f"<strong style='color:var(--bl-ink-100);'>{html.escape(prog['prev_date'])}</strong>"
               f" — the drill plan has what to lock back in.")
    else:
        sub = (f"Holding steady against "
               f"<strong style='color:var(--bl-ink-100);'>{html.escape(prog['prev_date'])}</strong>"
               f" — push for breakthroughs in the category deltas below.")

    # ---- Build trendline SVG sparkline ----
    score_history = prog["score_history"]
    sparkline_svg = _build_sparkline_svg(score_history)

    # ---- Movers ----
    up = prog["biggest_up"]
    down = prog["biggest_down"]

    if up and up[1] > 0.5:
        up_cat = up[0]
        up_delta = f"+{up[1]:.1f}%"
        up_detail = f"Strongest category gain since last swing."
        up_cls = "is-up"
        up_arrow_char = "↑"
    elif up and up[1] >= -0.5:
        up_cat = up[0]
        up_delta = "Flat"
        up_detail = "Held even — no major regression here."
        up_cls = "is-flat"
        up_arrow_char = "→"
    else:
        up_cat = "Across the board"
        up_delta = "—"
        up_detail = "No category improved this rep. Focus on Priority 1 in the drill plan."
        up_cls = "is-flat"
        up_arrow_char = "→"

    if down and down[1] < -0.5:
        down_cat = down[0]
        down_delta = f"{down[1]:.1f}%"
        down_detail = f"Biggest regression — revisit this drill block."
        down_cls = "is-down"
        down_arrow_char = "↓"
    elif down and down[1] <= 0.5:
        down_cat = down[0]
        down_delta = "Flat"
        down_detail = "Closest to flat — small target for next swing."
        down_cls = "is-flat"
        down_arrow_char = "→"
    else:
        down_cat = "Nothing major"
        down_delta = "✓"
        down_detail = "No category dropped meaningfully — clean rep."
        down_cls = "is-up"
        down_arrow_char = "↑"

    # When BOTH biggest_up and biggest_down land inside the ±0.5% flat band,
    # the two cards would show identical "Flat" deltas on the same (or
    # near-identical) category — visually broken UX even though the math is
    # right. Collapse to a single "Steady Rep" card in that case.
    both_flat = (
        up is not None and down is not None
        and -0.5 <= float(up[1]) <= 0.5
        and -0.5 <= float(down[1]) <= 0.5
    )
    if both_flat:
        movers_html = """
  <div class="swr-prog-movers" style="grid-template-columns: 1fr;">
    <div class="swr-prog-mover is-flat">
      <div class="swr-prog-mover-eyebrow">
        <span class="swr-prog-mover-arrow">→</span> STEADY REP
      </div>
      <div class="swr-prog-mover-cat">No meaningful change vs. last swing</div>
      <div class="swr-prog-mover-delta">Held the line</div>
      <div class="swr-prog-mover-detail">Every category landed within the margin of your previous swing — clean consistency. Push for a breakthrough in the deltas below.</div>
    </div>
  </div>
"""
    else:
        movers_html = f"""
  <div class="swr-prog-movers">
    <div class="swr-prog-mover {up_cls}">
      <div class="swr-prog-mover-eyebrow">
        <span class="swr-prog-mover-arrow">{up_arrow_char}</span> BIGGEST GAIN
      </div>
      <div class="swr-prog-mover-cat">{html.escape(str(up_cat))}</div>
      <div class="swr-prog-mover-delta">{up_delta}</div>
      <div class="swr-prog-mover-detail">{up_detail}</div>
    </div>
    <div class="swr-prog-mover {down_cls}">
      <div class="swr-prog-mover-eyebrow">
        <span class="swr-prog-mover-arrow">{down_arrow_char}</span> BIGGEST SLIP
      </div>
      <div class="swr-prog-mover-cat">{html.escape(str(down_cat))}</div>
      <div class="swr-prog-mover-delta">{down_delta}</div>
      <div class="swr-prog-mover-detail">{down_detail}</div>
    </div>
  </div>
"""

    # ---- Per-category delta rows ----
    cat_rows_html = ""
    for cd in prog["category_deltas"]:
        label = html.escape(str(cd["label"]))
        curr_pct = cd["curr_pct"]
        prev_pct = cd["prev_pct"]
        delta_v = cd["delta"]
        direction = cd["direction"]
        curr_w = max(0.0, min(100.0, curr_pct or 0))
        prev_w = max(0.0, min(100.0, prev_pct or 0))
        if direction == "new":
            delta_disp = "NEW"
            delta_cls = "is-new"
        elif delta_v is None:
            delta_disp = "—"
            delta_cls = "is-flat"
        elif delta_v > 0.5:
            delta_disp = f"+{delta_v:.1f}%"
            delta_cls = "is-up"
        elif delta_v < -0.5:
            delta_disp = f"{delta_v:.1f}%"
            delta_cls = "is-down"
        else:
            delta_disp = "flat"
            delta_cls = "is-flat"
        cat_rows_html += f"""
<div class="swr-prog-cat-row">
  <div class="swr-prog-cat-label">{label}</div>
  <div class="swr-prog-cat-bar">
    <div class="swr-prog-cat-fill-prev" style="width:{prev_w:.1f}%;"></div>
    <div class="swr-prog-cat-fill-curr {direction if direction in ('up','down','flat','new') else 'is-flat'}"
         style="width:{curr_w:.1f}%; opacity:.95;"></div>
  </div>
  <div class="swr-prog-cat-delta {delta_cls}">{delta_disp}</div>
</div>
"""

    # Map direction classes for the bar to include "is-" prefix.
    cat_rows_html = (cat_rows_html
                     .replace('class="swr-prog-cat-fill-curr up"', 'class="swr-prog-cat-fill-curr is-up"')
                     .replace('class="swr-prog-cat-fill-curr down"', 'class="swr-prog-cat-fill-curr is-down"')
                     .replace('class="swr-prog-cat-fill-curr flat"', 'class="swr-prog-cat-fill-curr is-flat"')
                     .replace('class="swr-prog-cat-fill-curr new"', 'class="swr-prog-cat-fill-curr is-new"'))

    _md(f"""
<div class="swr-prog">
  <div class="swr-prog-head">
    <div>
      <div class="swr-prog-eyebrow">SWING PROGRESS · {html.escape(str(total))} SWING{'S' if total != 1 else ''} LOGGED</div>
      <div class="swr-prog-title">Where you are vs. where you were.</div>
      <div class="swr-prog-sub">{sub}</div>
    </div>
  </div>

  <div class="swr-prog-kpis">
    <div class="swr-prog-kpi">
      <div class="swr-prog-kpi-label">Score</div>
      <div class="swr-prog-kpi-value">{curr}<span style="font-size:0.65rem;color:var(--bl-ink-40);font-weight:600;letter-spacing:0.04em;"> / 100</span></div>
      <div class="swr-prog-kpi-foot {delta_cls}">{delta_text}</div>
    </div>
    <div class="swr-prog-kpi {pb_class}">
      <div class="swr-prog-kpi-label">Personal Best</div>
      <div class="swr-prog-kpi-value">{pb_value}</div>
      <div class="swr-prog-kpi-foot {pb_foot_cls}">{pb_foot}</div>
    </div>
    <div class="swr-prog-kpi">
      <div class="swr-prog-kpi-label">Improvement Streak</div>
      <div class="swr-prog-kpi-value">{streak_value}</div>
      <div class="swr-prog-kpi-foot {streak_foot_cls}">{streak_foot}</div>
    </div>
    <div class="swr-prog-kpi">
      <div class="swr-prog-kpi-label">Total Swings</div>
      <div class="swr-prog-kpi-value">{total_value}</div>
      <div class="swr-prog-kpi-foot {total_foot_cls}">{total_foot}</div>
    </div>
  </div>

  <div class="swr-prog-trend">
    <div class="swr-prog-trend-head">
      <div class="swr-prog-trend-title">Score Trajectory</div>
      <div class="swr-prog-trend-meta">Last {len(score_history)} swing{'s' if len(score_history) != 1 else ''}</div>
    </div>
    {sparkline_svg}
  </div>

  {movers_html}

  <div class="swr-prog-cats">
    <div class="swr-prog-cats-head">
      <span>Category Match % · prev → now</span>
      <span style="color:var(--bl-ink-40);">{html.escape(prog['prev_date'])} → today</span>
    </div>
    <div class="swr-prog-cats-grid">
      {cat_rows_html}
    </div>
  </div>
</div>
""")


def _build_sparkline_svg(score_history: List[Tuple[Any, float]]) -> str:
    """Build a premium SVG sparkline for the score trajectory.

    Each (swing_num, score) point becomes a circle, all points connected by
    a smooth red gradient line. Y-axis is auto-scaled to the data with a
    small padding band. The LAST point (current swing) gets a larger
    highlighted ring + a score label so it pops as "you are here".
    """
    if not score_history:
        return ('<svg class="swr-prog-trend-svg" viewBox="0 0 800 110">'
                '<text x="400" y="60" text-anchor="middle" '
                'fill="#5c5c5c" font-family="Inter" font-size="14">'
                'No score history yet.</text></svg>')

    W = 800
    H = 110
    PAD_L = 28
    PAD_R = 36
    PAD_T = 18
    PAD_B = 22
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    scores = [s for _, s in score_history]
    s_min = min(scores)
    s_max = max(scores)
    if s_max - s_min < 5:
        # Tiny range — pad it so the line isn't flat against the top.
        mid = (s_max + s_min) / 2
        s_min = max(0, mid - 5)
        s_max = min(100, mid + 5)
    if s_max == s_min:
        s_max = s_min + 1  # avoid div by zero

    n = len(score_history)
    if n == 1:
        # Single-point: render as a centered dot with score label
        cx = PAD_L + plot_w / 2
        cy = PAD_T + plot_h / 2
        return f'''
<svg class="swr-prog-trend-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">
  <defs>
    <linearGradient id="sparkLine" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#FF3B30" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#FF3B30" stop-opacity="1"/>
    </linearGradient>
  </defs>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="#FF3B30" opacity="0.18"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="#FF3B30" stroke="#0a0a0a" stroke-width="2"/>
  <text x="{cx:.1f}" y="{cy - 14:.1f}" text-anchor="middle"
        fill="#fafafa" font-family="Inter" font-size="13" font-weight="800">{int(round(scores[0]))}</text>
</svg>'''

    # Compute point coords
    pts: List[Tuple[float, float]] = []
    for i, (_, s) in enumerate(score_history):
        x = PAD_L + (i / max(n - 1, 1)) * plot_w
        y = PAD_T + (1 - (s - s_min) / (s_max - s_min)) * plot_h
        pts.append((x, y))

    # Path
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    # Area under the line (subtle gradient fill)
    area_d = (path_d
              + f" L {pts[-1][0]:.1f},{PAD_T + plot_h:.1f}"
              + f" L {pts[0][0]:.1f},{PAD_T + plot_h:.1f} Z")

    # Y gridline ticks (3 lines)
    grid_lines = ""
    for frac in (0.0, 0.5, 1.0):
        gy = PAD_T + frac * plot_h
        grid_lines += (
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}" '
            f'stroke="rgba(255,255,255,0.05)" stroke-width="1" stroke-dasharray="2,3"/>'
        )
        score_val = s_max - frac * (s_max - s_min)
        grid_lines += (
            f'<text x="{PAD_L - 6}" y="{gy + 3.5:.1f}" text-anchor="end" '
            f'fill="#5c5c5c" font-family="JetBrains Mono" font-size="9">{score_val:.0f}</text>'
        )

    # Points
    pts_html = ""
    for i, ((sn, s), (x, y)) in enumerate(zip(score_history, pts)):
        is_last = (i == n - 1)
        if is_last:
            # Big highlighted ring + label above
            pts_html += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#FF3B30" opacity="0.18"/>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#FF3B30" '
                f'stroke="#0a0a0a" stroke-width="2"/>'
                f'<text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" '
                f'fill="#fafafa" font-family="Inter" font-size="12" font-weight="800">'
                f'{int(round(s))}</text>'
            )
        else:
            pts_html += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#FF3B30" '
                f'fill-opacity="0.55" stroke="#0a0a0a" stroke-width="1.5"/>'
            )

    # X-axis swing-number ticks (first + last only, to stay clean)
    first_sn = score_history[0][0]
    last_sn = score_history[-1][0]
    x_ticks = (
        f'<text x="{pts[0][0]:.1f}" y="{H - 6}" text-anchor="middle" '
        f'fill="#5c5c5c" font-family="JetBrains Mono" font-size="9" letter-spacing="0.1em">'
        f'#{html.escape(str(first_sn))}</text>'
        f'<text x="{pts[-1][0]:.1f}" y="{H - 6}" text-anchor="middle" '
        f'fill="#8b8b8b" font-family="JetBrains Mono" font-size="9" font-weight="700" letter-spacing="0.1em">'
        f'#{html.escape(str(last_sn))}</text>'
    )

    return f'''
<svg class="swr-prog-trend-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">
  <defs>
    <linearGradient id="sparkArea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FF3B30" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#FF3B30" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="sparkLine" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#FF3B30" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#FF3B30" stop-opacity="1"/>
    </linearGradient>
  </defs>
  {grid_lines}
  <path d="{area_d}" fill="url(#sparkArea)"/>
  <path d="{path_d}" stroke="url(#sparkLine)" stroke-width="2.2" fill="none"
        stroke-linecap="round" stroke-linejoin="round"/>
  {pts_html}
  {x_ticks}
</svg>'''


def _render_mlb_card(record: Dict[str, Any]):
    ref = _extract_ref_info(record)
    name = ref["name"]
    initials = _initials(name)
    traits = mlb_signature_traits(name)

    meta_parts = []
    if ref.get("team"):     meta_parts.append(ref["team"])
    if ref.get("position"): meta_parts.append(ref["position"])
    meta = " · ".join(meta_parts) if meta_parts else "MLB Reference"

    style_line = ref.get("style") or f"Reference swing for mechanical comparison."

    traits_html = ""
    if traits:
        traits_html = '<div class="swr-mlb-traits">'
        for t in traits:
            traits_html += f'<span class="swr-mlb-trait">{html.escape(t)}</span>'
        traits_html += "</div>"

    _md(f"""
<div class="swr-mlb">
  <div class="swr-mlb-grid">
    <div class="swr-mlb-avatar">{html.escape(initials)}</div>
    <div>
      <div class="swr-mlb-name">{html.escape(name)}</div>
      <div class="swr-mlb-meta">{html.escape(meta)}</div>
      <div class="swr-mlb-style">{html.escape(style_line)}</div>
      {traits_html}
    </div>
  </div>
</div>
""")


def _render_drill_plan(record: Dict[str, Any]):
    drill_plan = record.get("drill_plan") or {}
    cats = drill_plan.get("categories", []) if isinstance(drill_plan, dict) else []
    if not cats:
        st.info("No drill plan generated for this swing.")
        return

    for cat in cats:
        drills = cat.get("drills", []) or []
        drill_html_parts = []
        for j, d in enumerate(drills, 1):
            name = d.get("name", "Drill")
            reps = d.get("reps", "")
            how  = d.get("how", "")
            drill_html_parts.append(f"""
<div class="swr-drill">
  <div class="swr-drill-row">
    <div class="swr-drill-num">#{j}</div>
    <div class="swr-drill-name">{html.escape(str(name))}</div>
    {'<div class="swr-drill-reps">' + html.escape(str(reps)) + '</div>' if reps else ''}
  </div>
  {'<div class="swr-drill-how">' + html.escape(str(how)) + '</div>' if how else ''}
</div>
""")

        why_html = ""
        if cat.get("why_it_matters"):
            why_html = f'<div class="swr-priority-why">{html.escape(str(cat["why_it_matters"]))}</div>'

        _md(f"""
<div class="swr-priority">
  <div class="swr-priority-head">
    <div class="swr-priority-num">{cat.get('priority', '·')}</div>
    <div class="swr-priority-title">{html.escape(str(cat.get('title', 'Drills')))}</div>
    <div class="swr-priority-count">{len(drills)} drill{'s' if len(drills) != 1 else ''}</div>
  </div>
  {why_html}
  <div class="swr-drill-list">{''.join(drill_html_parts)}</div>
</div>
""")

    weekly = drill_plan.get("weekly_guide") if isinstance(drill_plan, dict) else None
    if weekly:
        lines = "".join(f'<div style="padding:0.3rem 0;color:var(--bl-ink-80);font-family:var(--bl-sans);">• {html.escape(str(b))}</div>' for b in weekly)
        _md(f"""
<div style="border-radius:var(--bl-radius-md);border:1px solid var(--bl-line);background:var(--bl-surface-1);padding:1rem 1.2rem;margin-top:0.4rem;">
  <div style="font-family:var(--bl-mono);font-size:0.6rem;font-weight:700;letter-spacing:0.22em;color:var(--bl-red);text-transform:uppercase;margin-bottom:0.45rem;">Weekly Practice Guide</div>
  {lines}
</div>
""")


def _render_strengths(record: Dict[str, Any]):
    strengths = record.get("strengths") or []
    if not strengths:
        return

    cards = '<div class="swr-strength-row">'
    for s in strengths[:3]:
        tier_mark = "✓" if s.get("tier") == "confirmed" else "≈"
        pct = s.get("sim_pct")
        pct_disp = f"{pct}%" if pct is not None else "—"
        cards += f"""
<div class="swr-strength">
  <div class="swr-strength-head">
    <div class="swr-strength-mark">{tier_mark}</div>
    <div class="swr-strength-cat">{html.escape(str(s.get('category_label', 'Strength')))}</div>
  </div>
  <div class="swr-strength-pct">{pct_disp}</div>
  <div class="swr-strength-sub">You: {html.escape(str(s.get('player_str', '—')))} · Ref: {html.escape(str(s.get('ref_str', '—')))}</div>
</div>
"""
    cards += "</div>"
    _md(cards)


def _render_metric_detail(record: Dict[str, Any]):
    metric_table = record.get("metric_table") or {}
    if not metric_table:
        return

    for group, rows in metric_table.items():
        if not rows:
            continue
        rows_html = ""
        for r in rows:
            pct = r.get("sim_pct")
            pct_val = float(pct) if pct is not None else 0.0
            band_cls = _band_class_for_pct(pct_val) if pct is not None else "is-building"
            flagged_cls = "is-flagged" if r.get("flagged") else ""
            label_str = str(r.get("label", "—"))
            player_str = str(r.get("player_str", "—"))
            ref_str = str(r.get("ref_str", "—"))
            pct_disp = f"{int(round(pct_val))}%" if pct is not None else "—"
            rows_html += f"""
<div class="swr-metric-row">
  <div class="swr-metric-label {flagged_cls}">{html.escape(label_str)}</div>
  <div class="swr-metric-bar-wrap">
    <div class="swr-metric-bar {band_cls}" style="width:{pct_val:.1f}%;"></div>
  </div>
  <div class="swr-metric-vals">
    <strong>{html.escape(player_str)}</strong>
    {html.escape(ref_str)}
  </div>
  <div class="swr-metric-pct">{pct_disp}</div>
</div>
"""
        _md(f"""
<div class="swr-metric-group">
  <div class="swr-metric-group-title">{html.escape(str(group))}</div>
  {rows_html}
</div>
""")


# ============================================================
#          SWING VIDEO + END-OF-REPORT CTA
# ============================================================

def _resolve_swing_video_url(record: Dict[str, Any]) -> Optional[str]:
    """
    Return a playable URL for the swing video, or None if we can't find one.
    Order of preference:
      1. Local path on disk (live post-analysis flow). Already a file path
         that Streamlit can stream.
      2. Supabase Storage path (saved swings, via signed URL).
    """
    # Live flow: analyzer/app may stash the local upload path on the record.
    for key in ("video_path", "_video_local_path", "uploaded_video_path"):
        local = record.get(key)
        if local:
            try:
                from pathlib import Path
                if Path(local).is_file():
                    return str(local)
            except Exception:
                pass

    # Saved-swing flow: signed URL from Supabase Storage.
    storage_path = record.get("_video_path") or record.get("video_storage_path")
    if storage_path:
        try:
            from player_storage import get_swing_video_signed_url
            url = get_swing_video_signed_url(storage_path)
            if url:
                return url
        except Exception:
            return None
    return None


def _render_swing_video(record: Dict[str, Any]):
    """
    Render the original swing video inside a premium card, directly under
    the hero. Silently no-ops if no video is available (older swings).
    """
    video_url = _resolve_swing_video_url(record)
    if not video_url:
        return

    swing_num = record.get("swing_number")
    eyebrow_num = f"SWING #{swing_num} · FILM" if swing_num else "YOUR SWING · FILM"

    _md(f"""
<div style="
    border-radius: var(--bl-radius-lg);
    border: 1px solid var(--bl-line);
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0));
    padding: 1.05rem 1.15rem 1.1rem 1.15rem;
    margin: 0.4rem 0 1.1rem 0;
">
  <div style="
      display:flex;align-items:center;justify-content:space-between;
      margin-bottom:0.55rem;
  ">
    <div style="
        font-family: var(--bl-mono);
        font-size: 0.62rem;
        letter-spacing: 0.24em;
        font-weight: 700;
        color: var(--bl-red);
        text-transform: uppercase;
    ">{html.escape(eyebrow_num)}</div>
    <div style="
        font-family: var(--bl-mono);
        font-size: 0.58rem;
        letter-spacing: 0.2em;
        font-weight: 600;
        color: var(--bl-ink-60);
        text-transform: uppercase;
    ">Re-watch with the report open</div>
  </div>
</div>
""")
    try:
        st.video(video_url)
    except Exception:
        # Bad URL or unsupported format — fail quiet, the rest of the
        # report should still render fine.
        pass


def _render_next_step_cta(record: Dict[str, Any]):
    """
    Drill-aware closing strip. Pulls the Priority 1 drill from the swing's
    drill plan (or the top fix if no plan exists), and shows a single
    next-step CTA: "Do this drill, then upload your next swing."
    """
    # Pull priority-1 drill from drill_plan first.
    drill_plan = record.get("drill_plan") or {}
    cats = drill_plan.get("categories", []) if isinstance(drill_plan, dict) else []

    p1_title = None
    p1_drill_name = None
    p1_drill_reps = None
    p1_why = None

    if cats:
        first = cats[0] or {}
        p1_title = first.get("title")
        p1_why = first.get("why_it_matters")
        drills = first.get("drills") or []
        if drills:
            d0 = drills[0] or {}
            p1_drill_name = d0.get("name")
            p1_drill_reps = d0.get("reps")

    # Fallback: derive from top fixes if no drill plan.
    if not p1_title:
        try:
            fixes = top_three_fixes(record) or []
        except Exception:
            fixes = []
        if fixes:
            f0 = fixes[0] or {}
            p1_title = f0.get("category_label") or f0.get("title") or "Top Fix"
            p1_why = f0.get("why_it_costs_you") or f0.get("why")
            p1_drill_name = f0.get("feel") or f0.get("fix") or "Work the feel from your Top Fix"

    if not p1_title and not p1_drill_name:
        return  # nothing useful to show

    title_safe = html.escape(str(p1_title or "Priority 1"))
    drill_safe = html.escape(str(p1_drill_name or "Start with your Priority 1 drill"))
    reps_safe  = html.escape(str(p1_drill_reps)) if p1_drill_reps else ""
    why_safe   = html.escape(str(p1_why)) if p1_why else ""

    if reps_safe:
        reps_chip = (
            f'<span style="font-family:var(--bl-mono);font-size:0.62rem;letter-spacing:0.2em;'
            f'text-transform:uppercase;color:#fbbf24;background:rgba(251,191,36,0.10);'
            f'border:1px solid rgba(251,191,36,0.35);border-radius:999px;'
            f'padding:0.2rem 0.55rem;margin-left:0.5rem;">{reps_safe}</span>'
        )
    else:
        reps_chip = ""

    why_block = (
        f'<div style="margin-top:0.55rem;color:var(--bl-ink-80);font-size:0.86rem;'
        f'line-height:1.5;">{why_safe}</div>'
        if why_safe else ""
    )

    _md(f"""
<div style="
    margin: 1.4rem 0 0.6rem 0;
    border-radius: var(--bl-radius-lg);
    border: 1px solid rgba(255, 59, 48, 0.32);
    background:
        radial-gradient(circle at 0% 0%, rgba(255,59,48,0.12), rgba(255,59,48,0) 55%),
        linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0));
    padding: 1.15rem 1.25rem 1.2rem 1.25rem;
">
  <div style="
      font-family: var(--bl-mono);
      font-size: 0.6rem;
      letter-spacing: 0.26em;
      font-weight: 700;
      color: var(--bl-red);
      text-transform: uppercase;
      margin-bottom: 0.45rem;
  ">Your Next Step</div>

  <div style="
      display:flex;flex-wrap:wrap;align-items:baseline;
      gap:0.4rem 0.6rem;
  ">
    <div style="
        font-family: var(--bl-sans);
        font-size: 1.15rem;
        font-weight: 800;
        letter-spacing: -0.01em;
        color: var(--bl-ink-100);
    ">Priority 1 · {title_safe}</div>
  </div>

  <div style="
      margin-top: 0.55rem;
      display:flex;flex-wrap:wrap;align-items:center;
      gap:0.35rem 0.55rem;
  ">
    <div style="
        font-family: var(--bl-sans);
        font-size: 0.98rem;
        font-weight: 600;
        color: var(--bl-ink-100);
    ">{drill_safe}</div>
    {reps_chip}
  </div>

  {why_block}

  <div style="
      margin-top: 0.95rem;
      display:flex;flex-wrap:wrap;align-items:center;
      gap:0.6rem;
      font-family: var(--bl-sans);
      font-size: 0.88rem;
      color: var(--bl-ink-80);
  ">
    <span style="
        display:inline-flex;align-items:center;justify-content:center;
        width:1.4rem;height:1.4rem;border-radius:50%;
        background: var(--bl-red);color:#fff;font-weight:800;
        font-size:0.78rem;letter-spacing:0;
    ">→</span>
    <span><b style="color:var(--bl-ink-100);">Train it.</b> Run the drill above, then film a new cut and re-upload.</span>
  </div>
  <div style="
      margin-top: 0.35rem;
      display:flex;flex-wrap:wrap;align-items:center;
      gap:0.6rem;
      font-family: var(--bl-sans);
      font-size: 0.88rem;
      color: var(--bl-ink-80);
  ">
    <span style="
        display:inline-flex;align-items:center;justify-content:center;
        width:1.4rem;height:1.4rem;border-radius:50%;
        background: rgba(255,255,255,0.06);color:var(--bl-ink-100);font-weight:800;
        font-size:0.78rem;letter-spacing:0;border:1px solid var(--bl-line);
    ">↺</span>
    <span><b style="color:var(--bl-ink-100);">Compare it.</b> Your next swing's report will diff this one and tell you if the fix is sticking.</span>
  </div>
</div>
""")


# ============================================================
#                      PUBLIC ENTRY
# ============================================================

def render_swing_report(
    record: Dict[str, Any],
    *,
    history: Optional[List[Dict[str, Any]]] = None,
    phase_chart_path: Optional[str] = None,
    show_diagnostics: bool = True,
    show_section_numbers: bool = True,
):
    """
    Legacy swing-report entry point — retained as a safety stub.

    The live on-screen report is rendered by
    `swing_report_dashboard_preview.render_swing_report_dashboard_preview`.
    This function is only reachable on rare fallback paths (e.g. an
    unexpected post-analyze exception). It no longer has a renderer of its
    own, so it shows a graceful error instead of a stack trace.
    """
    import streamlit as _st
    _st.error("This report couldn't be rendered — please retry.")


# ============================================================
#                  PDF EXPORT — PREMIUM REPORT
# ============================================================

def build_swing_report_pdf(record: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """
    Build the premium BarrelLabs swing report PDF.

    Delegates to the dark-theme v2 PDF renderer (`swing_report_v2_pdf`),
    which mirrors the on-screen v2 layout: hero w/ score ring + coach
    blurb, MLB comp card, key-metric tiles with sparklines, radar,
    detailed breakdown, top priorities, drill plan, score history, next
    step, and full coach notes.

    Args:
        record:  swing record (live result OR saved record).
        history: optional list of prior swings for "vs. last swing".

    Returns:
        PDF bytes.
    """
    # The dark-theme v2 PDF is now the only renderer. If it fails we
    # re-raise so the caller can surface a download error rather than
    # silently producing a broken/empty PDF.
    from swing_report_v2_pdf import build_swing_report_pdf_v2
    return build_swing_report_pdf_v2(record, history=history)

