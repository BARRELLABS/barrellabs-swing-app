"""Dashboard-style Premium Swing Report — PREVIEW ONLY.

Why this file exists
--------------------
The earlier Premium Swing Report renderer shipped a self-contained
`bld2-*` visual language that no longer matched the BarrelLabs Edge dashboard.
This module is the renderer that visually matches the Edge design system.

It is intentionally:
  * A pure presentational layer — it reuses data extraction helpers
    from `swing_report` / `swing_metrics` and never touches the
    analyzer, scoring, billing, or auth pipelines.
  * Self-contained CSS under the `srd-*` namespace (swing-report-dashboard)
    so it cannot leak into `bld2-*` or `bl-*` rules.

Public API
----------
    render_swing_report_dashboard_preview(record, history=None, *, is_sample=False)
        Streamlit entry point. Renders the full preview page including the
        "PREVIEW ONLY" banner.

    build_dashboard_preview_html(record, history=None, *, is_sample=False)
        Pure-HTML builder used by `scripts/visual_qa/render_swing_report_static.py`
        for headless screenshotting.

    SAMPLE_RECORD : Dict
        Synthetic record used when no real swing is selected. Mirrors the
        field schema the renderer reads (score, reference, narratives,
        gaps, metric_table, drill_plan, strengths, score_history).
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Tuple

# Reuse data extractors from the existing report stack — we are a NEW
# presentation layer, not a new data model.
from swing_report import (
    _extract_ref_info,
    _initials,
    coach_summary,
    top_three_fixes,
    swing_progress,
    enrich_fixes_with_history,
)
from swing_metrics import (
    _flatten_metric_table,
    _find_metric_row,
    _compute_key_metrics,
)


# =====================================================================
#                          DESIGN-SYSTEM CSS
# =====================================================================
# Tokens mirror mock_dashboard_template.py / bl_edge_chrome.py so the
# preview shares the Edge masthead/dashboard visual language exactly.
# Namespace: .srd-*
# =====================================================================

_DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Fraunces:ital,wght@0,400;0,500;0,600;1,400&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

.srd-wrap {
  --srd-bg:        #0A0B0E;
  --srd-bg-2:      #0F1115;
  --srd-bone:      #F4EFE6;
  --srd-bone-80:   rgba(244,239,230,0.82);
  --srd-bone-60:   rgba(244,239,230,0.58);
  --srd-bone-40:   rgba(244,239,230,0.36);
  --srd-bone-20:   rgba(244,239,230,0.16);
  --srd-line:      rgba(244,239,230,0.08);
  --srd-line-hi:   rgba(244,239,230,0.16);
  --srd-glass-1:   rgba(255,255,255,0.025);
  --srd-glass-2:   rgba(255,255,255,0.045);
  --srd-red:       #E64530;
  --srd-red-soft:  rgba(230,69,48,0.12);
  --srd-gold:      #E8C170;
  --srd-gold-soft: rgba(232,193,112,0.14);
  --srd-green:     #4AE38C;
  --srd-green-soft:rgba(74,227,140,0.12);
  --srd-gray:      #8B8E94;
  --srd-radius:    14px;
  --srd-radius-lg: 20px;
  --srd-radius-sm: 10px;
  --srd-serif: 'Instrument Serif', 'Fraunces', Georgia, serif;
  --srd-sans:  'Geist', -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  --srd-mono:  'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

  background: var(--srd-bg);
  color: var(--srd-bone);
  font-family: var(--srd-sans);
  /* Match the masthead/dashboard content frame exactly (max-width
     1560, 40px side gutter) so text aligns with the nav on every
     page — one cohesive rhythm, never edge-crammed. */
  max-width: 1560px;
  margin: 0 auto;
  padding: 1.8rem 40px 4rem;
  font-feature-settings: "ss01", "ss02", "cv11";
  -webkit-font-smoothing: antialiased;
}

/* PREVIEW banner */
.srd-banner {
  display:flex; align-items:center; gap:14px;
  padding: 10px 16px;
  margin-bottom: 1.4rem;
  background: rgba(232,193,112,0.06);
  border: 1px solid rgba(232,193,112,0.32);
  border-radius: 12px;
  font-family: var(--srd-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--srd-gold);
}
.srd-banner-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--srd-gold); box-shadow: 0 0 12px var(--srd-gold);
}
.srd-banner-text { flex:1; color: var(--srd-bone-80); letter-spacing: 0.12em; }
.srd-banner-tag { color: var(--srd-gold); font-weight:600; }

/* Page title strip */
.srd-pagehead {
  display:flex; align-items:flex-end; justify-content:space-between;
  padding-bottom: 1.4rem;
  margin-bottom: 1.4rem;
  border-bottom: 1px solid var(--srd-line);
  gap: 2rem;
}
.srd-eyebrow {
  font-family: var(--srd-mono);
  font-size: 10.5px;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: var(--srd-red);
  font-weight: 600;
  display:flex; align-items:center; gap:8px;
}
.srd-eyebrow::before {
  content:""; width:6px; height:6px; border-radius:50%;
  background: var(--srd-red); box-shadow: 0 0 8px var(--srd-red);
}
.srd-pagehead-title {
  font-family: var(--srd-serif);
  font-size: 3.4rem;
  font-style: italic;
  line-height: 0.95;
  letter-spacing: -0.02em;
  color: var(--srd-bone);
  margin: 0.6rem 0 0;
}
.srd-pagehead-meta {
  text-align: right;
  font-family: var(--srd-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-pagehead-meta strong {
  color: var(--srd-bone); font-weight: 500;
  display:block; margin-top: 4px;
  font-family: var(--srd-serif); font-style: italic;
  font-size: 16px; letter-spacing: 0; text-transform: none;
}

/* Card primitive */
.srd-card {
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius-lg);
  padding: 1.4rem 1.5rem;
  position: relative;
  transition: border-color .2s ease, background .2s ease;
}
.srd-card.is-hover:hover {
  border-color: var(--srd-line-hi);
  background: var(--srd-glass-2);
}
.srd-card-eyebrow {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  margin-bottom: 1rem;
  display:flex; align-items:center; gap:8px;
}
.srd-card-eyebrow .dot {
  width:5px; height:5px; border-radius:50%;
  background: var(--srd-red);
}

/* ========== HERO ROW: SCORE | MLB COMP ========== */
.srd-hero {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  gap: 1rem;
  margin-bottom: 1.1rem;
}
.srd-hero-card {
  background:
    radial-gradient(ellipse at 100% 0%, rgba(230,69,48,0.07) 0%, transparent 55%),
    var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius-lg);
  padding: 1.6rem 1.7rem;
  position: relative; overflow: hidden;
}
.srd-hero-card.mlb {
  background:
    radial-gradient(ellipse at 0% 0%, rgba(232,193,112,0.06) 0%, transparent 55%),
    var(--srd-glass-1);
}

.srd-hero-grid {
  display:grid;
  grid-template-columns: 1.4fr 0.9fr;
  gap: 1.6rem;
  align-items: center;
}

/* Score side */
.srd-score-num {
  font-family: var(--srd-serif);
  font-size: 6rem;
  line-height: 0.92;
  letter-spacing: -0.04em;
  color: var(--srd-bone);
  font-style: italic;
}
.srd-score-foot {
  font-family: var(--srd-mono);
  font-size: 14px;
  color: var(--srd-bone-60);
  margin-left: 0.4rem;
  letter-spacing: 0.06em;
}
.srd-score-band {
  display:inline-flex; align-items:center; gap:8px;
  margin-top: 0.8rem;
  padding: 5px 12px;
  border-radius: 999px;
  font-family: var(--srd-mono);
  font-size: 10.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.srd-score-band.green { background: var(--srd-green-soft); color: var(--srd-green); border:1px solid rgba(74,227,140,0.25); }
.srd-score-band.amber { background: var(--srd-gold-soft); color: var(--srd-gold);  border:1px solid rgba(232,193,112,0.25); }
.srd-score-band.red   { background: var(--srd-red-soft);  color: var(--srd-red);   border:1px solid rgba(230,69,48,0.28); }
.srd-score-band .dot {
  width:6px; height:6px; border-radius:50%; background: currentColor;
  box-shadow: 0 0 8px currentColor;
}
.srd-score-blurb {
  margin-top: 1.1rem;
  color: var(--srd-bone-80);
  font-size: 14.5px;
  line-height: 1.6;
  max-width: 38ch;
  font-family: var(--srd-sans);
}
.srd-score-blurb strong { color: var(--srd-bone); font-weight: 600; }

.srd-ring-wrap { display:flex; flex-direction:column; align-items:center; gap:12px; }
.srd-ring-delta {
  font-family: var(--srd-mono);
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: center;
  padding: 6px 12px;
  border-radius: 999px;
  border:1px solid var(--srd-line);
}
.srd-ring-delta.up   { color: var(--srd-green); border-color: rgba(74,227,140,0.3); }
.srd-ring-delta.down { color: var(--srd-red);   border-color: rgba(230,69,48,0.3); }
.srd-ring-delta.flat { color: var(--srd-bone-60); }
.srd-ring-delta .sub { display:block; margin-top:3px; font-size:9.5px; opacity:.7; }

/* MLB comp side */
.srd-mlb-grid {
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.4rem;
  align-items: center;
}
.srd-mlb-name {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 2.2rem;
  letter-spacing: -0.015em;
  color: var(--srd-bone);
  line-height: 1.05;
  margin-top: 0.2rem;
}
.srd-mlb-team {
  font-family: var(--srd-mono);
  font-size: 10.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  margin-top: 0.55rem;
}
.srd-mlb-sim-row {
  display:flex; align-items:baseline; gap:10px;
  margin-top: 1rem;
}
.srd-mlb-sim {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 2.4rem;
  color: var(--srd-gold);
  letter-spacing: -0.02em;
  line-height: 1;
}
.srd-mlb-sim-foot {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-mlb-style {
  margin-top: 1rem;
  color: var(--srd-bone-80);
  font-size: 13.5px;
  line-height: 1.55;
  font-style: italic;
  font-family: var(--srd-serif);
  border-left: 2px solid var(--srd-gold);
  padding-left: 12px;
}
.srd-mlb-avatar-row { display:flex; align-items:center; gap:14px; }
.srd-mlb-avatar {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(232,193,112,0.18), rgba(232,193,112,0.04));
  border: 1px solid rgba(232,193,112,0.3);
  display:flex; align-items:center; justify-content:center;
  font-family: var(--srd-serif); font-style: italic;
  color: var(--srd-gold);
  font-size: 22px;
  flex-shrink:0;
}
.srd-mlb-radar { display:flex; justify-content:center; align-items:flex-start; }
.srd-mlb-radar svg { max-width: 190px; width: 100%; height:auto; }

/* MLB insight blocks (shared traits / biggest gap / why-matters) */
.srd-mlb-insights {
  margin-top: 1.2rem;
  display:flex; flex-direction:column; gap: 0.95rem;
}
.srd-mlb-insight-eyebrow {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  margin-bottom: 0.45rem;
  display:flex; align-items:center; gap: 7px;
}
.srd-mlb-insight-eyebrow .dot {
  width:5px; height:5px; border-radius:50%;
}
.srd-mlb-insight-eyebrow.gold .dot  { background: var(--srd-gold); }
.srd-mlb-insight-eyebrow.red  .dot  { background: var(--srd-red); }
.srd-mlb-insight-eyebrow.bone .dot  { background: var(--srd-bone-60); }

.srd-mlb-traits {
  display:flex; flex-wrap:wrap; gap: 6px;
}
.srd-mlb-trait {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--srd-gold-soft);
  color: var(--srd-gold);
  border: 1px solid rgba(232,193,112,0.28);
  font-weight: 600;
}
.srd-mlb-gap {
  background: var(--srd-red-soft);
  border: 1px solid rgba(230,69,48,0.28);
  border-radius: var(--srd-radius-sm);
  padding: 0.7rem 0.9rem;
  color: var(--srd-bone);
  font-size: 13.5px;
  line-height: 1.5;
}
.srd-mlb-why {
  color: var(--srd-bone-80);
  font-size: 13px;
  line-height: 1.55;
  font-family: var(--srd-serif);
  font-style: italic;
  border-left: 2px solid var(--srd-gold);
  padding-left: 12px;
}

/* Section title strip used between bands */
.srd-section {
  display:flex; align-items:baseline; justify-content:space-between;
  margin: 2.2rem 0 1rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid var(--srd-line);
}
.srd-section-title {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.7rem;
  letter-spacing: -0.015em;
  color: var(--srd-bone);
  margin: 0.4rem 0 0;
}
.srd-section-sub {
  font-family: var(--srd-mono);
  font-size: 10.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}

/* PRIORITIES + DRILLS GRID */
.srd-pd-grid {
  display:grid;
  grid-template-columns: 1.05fr 1fr;
  gap: 1rem;
}
.srd-pri-list, .srd-drill-list {
  display:flex; flex-direction:column; gap: 0.7rem;
}
.srd-pri {
  display:grid;
  grid-template-columns: 44px 1fr;
  gap: 1rem;
  padding: 1rem 1.1rem;
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
  align-items: start;
  transition: border-color .2s ease, background .2s ease;
}
.srd-pri:hover { border-color: var(--srd-line-hi); background: var(--srd-glass-2); }
.srd-pri-num {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 2rem;
  color: var(--srd-red);
  line-height: 1;
  text-align: center;
}
.srd-pri-head {
  display:flex; align-items:center; justify-content:space-between;
  gap: 12px; margin-bottom: 0.4rem;
}
.srd-pri-title {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.2rem;
  color: var(--srd-bone);
  letter-spacing: -0.01em;
}
.srd-pri-tag {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid;
  font-weight: 600;
  white-space: nowrap;
}
.srd-pri-tag.high { color: var(--srd-red);   border-color: rgba(230,69,48,0.35); background: var(--srd-red-soft); }
.srd-pri-tag.med  { color: var(--srd-gold);  border-color: rgba(232,193,112,0.3); background: var(--srd-gold-soft); }
.srd-pri-tag.low  { color: var(--srd-green); border-color: rgba(74,227,140,0.3); background: var(--srd-green-soft); }
.srd-pri-desc {
  color: var(--srd-bone-80);
  font-size: 13.5px;
  line-height: 1.55;
}

.srd-drill {
  display:grid;
  grid-template-columns: 56px 1fr auto;
  gap: 1rem;
  padding: 0.95rem 1.1rem;
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
  align-items: center;
  transition: border-color .2s ease, background .2s ease;
}
.srd-drill:hover { border-color: var(--srd-line-hi); background: var(--srd-glass-2); }
.srd-drill-thumb {
  width: 56px; height: 56px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(230,69,48,0.16), rgba(230,69,48,0.03));
  border: 1px solid rgba(230,69,48,0.22);
  display:flex; align-items:center; justify-content:center;
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  color: var(--srd-red);
  font-weight: 700;
  line-height: 1.1; text-align: center;
}
.srd-drill-title {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.1rem;
  color: var(--srd-bone);
  letter-spacing: -0.005em;
}
.srd-drill-pills {
  display:flex; flex-wrap:wrap; gap: 6px;
  margin-top: 5px;
}
.srd-drill-pill {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: var(--srd-bone-60);
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--srd-line);
  padding: 3px 9px;
  border-radius: 999px;
  text-transform: uppercase;
}
.srd-drill-check {
  width: 28px; height: 28px;
  border: 1px solid var(--srd-line-hi);
  border-radius: 50%;
  display:flex; align-items:center; justify-content:center;
  color: var(--srd-bone-40);
  font-size: 14px;
}

/* KEY METRICS STRIP */
.srd-km {
  display:grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
}
.srd-km-tile {
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
  padding: 1.05rem 1.1rem;
  transition: border-color .2s ease;
}
.srd-km-tile:hover { border-color: var(--srd-line-hi); }
.srd-km-label {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-km-val-row { display:flex; align-items:baseline; gap:6px; margin-top: 0.7rem; }
.srd-km-val {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.9rem;
  color: var(--srd-bone);
  letter-spacing: -0.015em;
  line-height: 1;
}
.srd-km-unit {
  font-family: var(--srd-mono);
  font-size: 11px;
  color: var(--srd-bone-60);
  letter-spacing: 0.06em;
}
.srd-km-delta {
  margin-left: auto;
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  padding: 3px 7px;
  border-radius: 999px;
  border: 1px solid var(--srd-line);
}
.srd-km-delta.up   { color: var(--srd-green); border-color: rgba(74,227,140,0.3); }
.srd-km-delta.down { color: var(--srd-red);   border-color: rgba(230,69,48,0.3); }
.srd-km-delta.flat { color: var(--srd-bone-60); }
.srd-km-spark { margin-top: 0.7rem; }
.srd-km-spark svg { width: 100%; height: 28px; }

/* BREAKDOWN TABLE */
.srd-br-table { width:100%; border-collapse: collapse; margin-top: 0.5rem; }
.srd-br-table th {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  text-align: left;
  font-weight: 600;
  padding: 10px 12px;
  border-bottom: 1px solid var(--srd-line-hi);
}
.srd-br-table th + th, .srd-br-table td + td { text-align: right; }
.srd-br-table td {
  font-family: var(--srd-sans);
  font-size: 13.5px;
  color: var(--srd-bone-80);
  padding: 11px 12px;
  border-bottom: 1px solid var(--srd-line);
}
.srd-br-table td:first-child { color: var(--srd-bone); font-weight: 500; }
.srd-br-table tbody tr:last-child td { border-bottom: 0; }
.srd-br-status {
  display:inline-flex; align-items:center; justify-content:center;
  width: 22px; height: 22px; border-radius: 50%;
  font-family: var(--srd-mono); font-size: 11px; font-weight: 600;
}
.srd-br-status.ok   { background: var(--srd-green-soft); color: var(--srd-green); }
.srd-br-status.warn { background: var(--srd-gold-soft);  color: var(--srd-gold); }
.srd-br-status.bad  { background: var(--srd-red-soft);   color: var(--srd-red); }

/* PROGRESS / VS PREVIOUS */
.srd-prog-grid {
  display:grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1rem;
}
.srd-prog-spark { height: 110px; margin-top: 0.8rem; }
.srd-prog-spark svg { width: 100%; height: 100%; }
.srd-prog-stats {
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.7rem;
  margin-top: 0.4rem;
}
.srd-prog-stat {
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
  padding: 0.85rem 1rem;
}
.srd-prog-stat-label {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-prog-stat-val {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.5rem;
  color: var(--srd-bone);
  margin-top: 0.4rem;
  letter-spacing: -0.01em;
  line-height: 1;
}
.srd-prog-stat-sub {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--srd-bone-60);
  margin-top: 0.4rem;
}

/* NEXT SESSION */
.srd-next-list {
  list-style: none; padding: 0; margin: 0.4rem 0 0;
  display:flex; flex-direction:column; gap: 0.7rem;
}
.srd-next-item {
  display:grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
  padding: 0.9rem 1rem;
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
}
.srd-next-num {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--srd-red-soft);
  color: var(--srd-red);
  font-family: var(--srd-mono);
  font-size: 11px;
  font-weight: 700;
  display:flex; align-items:center; justify-content:center;
}
.srd-next-title {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 1.1rem;
  color: var(--srd-bone);
  letter-spacing: -0.005em;
}
.srd-next-sub {
  color: var(--srd-bone-80);
  font-size: 13px;
  margin-top: 4px;
  line-height: 1.55;
}

/* STRENGTHS chip row */
.srd-chips {
  display:flex; flex-wrap:wrap; gap: 6px;
  margin-top: 1rem;
}
.srd-chip {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--srd-green-soft);
  color: var(--srd-green);
  border: 1px solid rgba(74,227,140,0.22);
  font-weight: 600;
}

/* COMPARE THIS SWING */
.srd-cmp-selector {
  margin-bottom: 1rem;
  display:grid;
  grid-template-columns: 140px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 0.85rem 1rem;
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
}
.srd-cmp-selector-label {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-cmp-selector-display {
  display:flex; align-items:center; justify-content:space-between;
  gap: 12px;
  padding: 0.55rem 0.85rem;
  background: var(--srd-bg-2);
  border: 1px solid var(--srd-line-hi);
  border-radius: var(--srd-radius-sm);
  color: var(--srd-bone);
  font-family: var(--srd-sans);
  font-size: 13px;
}
.srd-cmp-selector-caret { color: var(--srd-bone-60); font-size: 10px; }
.srd-cmp-selector-hint {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: var(--srd-bone-40);
  text-transform: uppercase;
}

.srd-cmp-summary {
  margin-bottom: 1rem;
  background:
    radial-gradient(ellipse at 0% 0%, rgba(74,227,140,0.05) 0%, transparent 55%),
    var(--srd-glass-1);
}
.srd-cmp-summary-row {
  display:flex; align-items:center; gap: 1.4rem;
}
.srd-cmp-summary-badge {
  flex-shrink:0;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  width: 104px; padding: 1rem 0.6rem;
  border-radius: var(--srd-radius);
  border: 1px solid var(--srd-line-hi);
  background: var(--srd-bg-2);
  text-align:center;
}
.srd-cmp-summary-badge .big {
  font-family: var(--srd-serif); font-style: italic;
  font-size: 2.4rem; line-height: 1;
}
.srd-cmp-summary-badge.up .big   { color: var(--srd-green); }
.srd-cmp-summary-badge.down .big { color: var(--srd-red); }
.srd-cmp-summary-badge .of {
  font-family: var(--srd-mono); font-size: 11px;
  color: var(--srd-bone-60); margin-top: 4px;
}
.srd-cmp-summary-badge .lbl {
  font-family: var(--srd-mono); font-size: 9px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--srd-bone-60); margin-top: 6px;
}
.srd-cmp-summary-text {
  color: var(--srd-bone-80);
  font-size: 14.5px; line-height: 1.65;
}
.srd-cmp-summary-text strong { color: var(--srd-bone); font-weight: 600; }

.srd-cmp-pair {
  display:grid;
  grid-template-columns: 1fr 110px 1fr;
  gap: 0.8rem;
  align-items: stretch;
  margin-bottom: 1rem;
}
.srd-cmp-card {
  background: var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius-lg);
  padding: 1.2rem 1.3rem;
}
.srd-cmp-role {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  margin-bottom: 0.85rem;
  display:flex; align-items:center; gap: 7px;
}
.srd-cmp-role .dot { width:5px; height:5px; border-radius:50%; }
.srd-cmp-head { display:flex; align-items:center; gap: 14px; }
.srd-cmp-avatar {
  width: 56px; height: 56px; border-radius: 14px;
  display:flex; align-items:center; justify-content:center;
  font-family: var(--srd-serif); font-style: italic;
  font-size: 1.5rem;
  flex-shrink:0;
}
.srd-cmp-avatar-green { background: var(--srd-green-soft); color: var(--srd-green); border: 1px solid rgba(74,227,140,0.25); }
.srd-cmp-avatar-amber { background: var(--srd-gold-soft);  color: var(--srd-gold);  border: 1px solid rgba(232,193,112,0.25); }
.srd-cmp-avatar-red   { background: var(--srd-red-soft);   color: var(--srd-red);   border: 1px solid rgba(230,69,48,0.28); }
.srd-cmp-swing {
  font-family: var(--srd-serif); font-style: italic;
  font-size: 1.25rem; color: var(--srd-bone);
  letter-spacing: -0.005em; line-height: 1.1;
}
.srd-cmp-meta {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
  margin-top: 4px;
}
.srd-cmp-mlb {
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--srd-bone-80);
}

.srd-cmp-delta-badge {
  align-self: center;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center;
  background: var(--srd-bg-2);
  border: 1px solid var(--srd-line-hi);
  border-radius: 999px;
  padding: 1rem 0.5rem;
  min-height: 110px;
}
.srd-cmp-delta-label {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-cmp-delta-val {
  font-family: var(--srd-serif); font-style: italic;
  font-size: 2rem; margin-top: 6px; letter-spacing: -0.02em;
  line-height: 1;
}
.srd-cmp-delta-val.up   { color: var(--srd-green); }
.srd-cmp-delta-val.down { color: var(--srd-red); }
.srd-cmp-delta-val.flat { color: var(--srd-bone-60); }

.srd-cmp-metrics-card { padding: 1.2rem 1.4rem 1rem; }
.srd-cmp-table {
  width:100%; border-collapse: collapse; margin-top: 0.4rem;
}
.srd-cmp-table th {
  font-family: var(--srd-mono); font-size: 9.5px; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--srd-bone-60);
  text-align: left; font-weight: 600;
  padding: 10px 12px;
  border-bottom: 1px solid var(--srd-line-hi);
}
.srd-cmp-table th.num, .srd-cmp-table td.num { text-align: right; }
.srd-cmp-table th + th, .srd-cmp-table td + td { text-align: right; }
.srd-cmp-table td {
  font-family: var(--srd-sans); font-size: 13.5px;
  color: var(--srd-bone-80); padding: 10px 12px;
  border-bottom: 1px solid var(--srd-line);
}
.srd-cmp-table td:first-child { color: var(--srd-bone); font-weight: 500; }
.srd-cmp-table tbody tr:last-child td { border-bottom: 0; }
.srd-cmp-delta {
  font-family: var(--srd-mono); font-size: 11.5px;
  letter-spacing: 0.06em; padding: 3px 9px;
  border-radius: 999px; border: 1px solid var(--srd-line);
  display:inline-block; min-width: 48px; text-align: center;
  font-weight: 600;
}
.srd-cmp-delta.up   { color: var(--srd-green); border-color: rgba(74,227,140,0.3); background: var(--srd-green-soft); }
.srd-cmp-delta.down { color: var(--srd-red);   border-color: rgba(230,69,48,0.3); background: var(--srd-red-soft); }
.srd-cmp-delta.flat { color: var(--srd-bone-60); }
.srd-cmp-footnote {
  margin-top: 0.7rem;
  font-family: var(--srd-mono); font-size: 9.5px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--srd-bone-40);
}

.srd-cmp-empty {
  padding: 1.6rem 1.7rem;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(232,193,112,0.05) 0%, transparent 55%),
    var(--srd-glass-1);
}
.srd-cmp-empty-msg {
  font-family: var(--srd-serif); font-style: italic;
  font-size: 1.4rem; color: var(--srd-bone);
  margin: 0.4rem 0 0.5rem;
}
.srd-cmp-empty-sub {
  color: var(--srd-bone-60); font-size: 13.5px; line-height: 1.55;
}

/* GRID GAPS */
.srd-stack { display:flex; flex-direction:column; gap: 1rem; }

/* RESPONSIVE */
@media (max-width: 1100px) {
  /* Track the masthead's responsive gutter so text stays aligned. */
  .srd-wrap { padding: 1.4rem 22px 3.5rem; }
}
@media (max-width: 960px) {
  .srd-hero, .srd-pd-grid, .srd-prog-grid { grid-template-columns: 1fr; }
  .srd-hero-grid, .srd-mlb-grid { grid-template-columns: 1fr; gap: 1.2rem; }
  .srd-km { grid-template-columns: repeat(2, 1fr); }
  .srd-cmp-pair { grid-template-columns: 1fr; }
  .srd-cmp-delta-badge {
    min-height: 0; padding: 0.7rem 1rem; flex-direction: row; gap: 14px;
    border-radius: var(--srd-radius);
  }
  .srd-cmp-selector { grid-template-columns: 1fr; gap: 6px; }
  .srd-cmp-summary-row { flex-direction: column; align-items: flex-start; gap: 1rem; }
  .srd-cmp-summary-badge { flex-direction: row; gap: 10px; width: auto; padding: 0.6rem 1rem; }
}
@media (max-width: 560px) {
  .srd-wrap { padding: 1rem 16px 3rem; }
  .srd-pagehead { flex-direction: column; align-items: flex-start; gap: 0.8rem; }
  .srd-pagehead-title { font-size: 2.4rem; }
  .srd-pagehead-meta { text-align: left; }
  .srd-score-num { font-size: 4.6rem; }
  .srd-mlb-name { font-size: 1.7rem; }
  .srd-km { grid-template-columns: 1fr 1fr; }
  .srd-pri { grid-template-columns: 36px 1fr; gap: 0.7rem; padding: 0.85rem 0.9rem; }
  .srd-drill { grid-template-columns: 44px 1fr; gap: 0.8rem; }
  .srd-drill-check { display: none; }
}

/* ───── Power Sequence section (new) ───── */
.srd-power-section {
    margin: 32px 0 40px 0;
    padding: 28px 32px 32px 32px;
    border: 1px solid var(--srd-line);
    border-radius: 16px;
    background:
      radial-gradient(120% 60% at 50% 0%, rgba(232,193,112,0.06), transparent 70%),
      var(--srd-glass-1);
}
.srd-power-eyebrow {
    font-family: var(--srd-mono); font-size: 11px; font-weight: 600;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--srd-gold);
    margin: 0 0 8px 0;
}
.srd-power-title {
    font-family: var(--srd-serif); font-size: 2.4rem;
    line-height: 1.05; letter-spacing: -0.018em;
    color: var(--srd-bone); font-weight: 400; margin: 0 0 8px 0;
}
.srd-power-title .ital { font-style: italic; color: var(--srd-gold); }
.srd-power-verdict {
    font-family: var(--srd-sans); font-size: 1.05rem;
    line-height: 1.5; color: var(--srd-bone-60); max-width: 60ch;
    margin: 0 0 22px 0;
}
.srd-power-tiles {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 16px; margin-top: 20px;
}
@media (max-width: 760px) {
    .srd-power-tiles { grid-template-columns: 1fr; }
}
/* Two tiles fill the row evenly instead of hugging the left 1/3. Scoped to
   desktop so the mobile 1-col rule above still wins on narrow screens. */
@media (min-width: 761px) {
    .srd-power-tiles--two { grid-template-columns: 1fr 1fr; }
}
.srd-power-tile {
    border: 1px solid var(--srd-line);
    border-radius: 12px;
    padding: 18px 22px;
    background: rgba(244,239,230,0.025);
}
.srd-power-tile.good   { border-color: rgba(232,193,112,0.42); }
.srd-power-tile.marginal { border-color: var(--srd-line-hi); }
.srd-power-tile.poor   { border-color: rgba(230,69,48,0.45); }
.srd-power-tile-label {
    font-family: var(--srd-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.20em; text-transform: uppercase;
    color: var(--srd-bone-60); margin-bottom: 6px;
}
.srd-power-tile.good     .srd-power-tile-label { color: var(--srd-gold); }
.srd-power-tile.poor     .srd-power-tile-label { color: var(--srd-red); }
.srd-power-tile-value {
    font-family: var(--srd-serif); font-style: italic;
    font-size: 2.2rem; line-height: 1; letter-spacing: -0.02em;
    color: var(--srd-bone); margin: 4px 0 8px 0;
}
.srd-power-tile-unit {
    font-family: var(--srd-mono); font-size: 11px; font-weight: 500;
    color: var(--srd-bone-60); letter-spacing: 0.12em;
    text-transform: lowercase; margin-left: 4px;
}
.srd-power-tile-coach {
    font-family: var(--srd-sans); font-size: 0.92rem;
    line-height: 1.45; color: var(--srd-bone-60); max-width: 32ch;
}

/* ───── Two-System Layout: Match Reveal + Reconciliation + Score Card ───── */

/* Match Reveal Hero (full-width, top of report) */
.srd-match-reveal {
  background:
    radial-gradient(ellipse at 30% 0%, rgba(232,193,112,0.10) 0%, transparent 60%),
    var(--srd-glass-1);
  border: 1px solid rgba(232,193,112,0.20);
  border-radius: var(--srd-radius-lg);
  padding: 2rem 2.2rem;
  margin-bottom: 1rem;
  position: relative;
  overflow: hidden;
}
.srd-match-eyebrow {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: var(--srd-gold);
  margin-bottom: 1.2rem;
  display: flex;
  align-items: center;
  gap: 8px;
}
.srd-match-eyebrow::before {
  content: "";
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--srd-gold);
  box-shadow: 0 0 10px var(--srd-gold);
}
.srd-match-body {
  display: flex;
  align-items: flex-start;
  gap: 2rem;
}
.srd-match-avatar {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(232,193,112,0.22), rgba(232,193,112,0.06));
  border: 1px solid rgba(232,193,112,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--srd-serif);
  font-style: italic;
  color: var(--srd-gold);
  font-size: 28px;
  flex-shrink: 0;
}
.srd-match-info { flex: 1; }
.srd-match-name {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 2.8rem;
  letter-spacing: -0.02em;
  color: var(--srd-bone);
  line-height: 1;
  margin-bottom: 0.5rem;
}
.srd-match-pct-row {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-top: 0.8rem;
}
.srd-match-pct {
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 2.2rem;
  color: var(--srd-gold);
  letter-spacing: -0.02em;
  line-height: 1;
}
.srd-match-pct-label {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.20em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-match-nudge {
  margin-top: 0.9rem;
  color: var(--srd-bone-60);
  font-family: var(--srd-mono);
  font-size: 11px;
  letter-spacing: 0.10em;
  font-style: italic;
}

/* Reconciliation line */
.srd-reconcile {
  margin: 1rem 0;
  padding: 0.9rem 1.2rem;
  background: rgba(244,239,230,0.03);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius);
  text-align: center;
  font-family: var(--srd-serif);
  font-style: italic;
  font-size: 14px;
  color: var(--srd-bone-60);
  line-height: 1.6;
}
.srd-reconcile strong { color: var(--srd-bone-80); font-weight: normal; }

/* Pillar mini-bars */
.srd-pillars { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 1rem; }
.srd-pillar-row {
  display: grid;
  grid-template-columns: 80px 1fr 80px;
  align-items: center;
  gap: 0.7rem;
}
.srd-pillar-label {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--srd-bone-60);
}
.srd-pillar-track {
  height: 5px;
  border-radius: 999px;
  background: rgba(244,239,230,0.08);
  overflow: hidden;
}
.srd-pillar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--srd-gold);
  transition: width 0.4s ease;
}
.srd-pillar-fill.green { background: var(--srd-green); }
.srd-pillar-fill.red   { background: var(--srd-red); }
.srd-pillar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

/* Confidence badge */
.srd-conf-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--srd-mono);
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 600;
}
.srd-conf-badge::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: currentColor;
}
.srd-conf-badge.green { color: var(--srd-green); background: var(--srd-green-soft); border: 1px solid rgba(74,227,140,0.25); }
.srd-conf-badge.amber { color: var(--srd-gold);  background: var(--srd-gold-soft);  border: 1px solid rgba(232,193,112,0.25); }
.srd-conf-badge.red   { color: var(--srd-red);   background: var(--srd-red-soft);   border: 1px solid rgba(230,69,48,0.28); }

/* What you did well */
.srd-did-well {
  margin-top: 1rem;
  padding: 0.9rem 1.1rem;
  background: var(--srd-green-soft);
  border: 1px solid rgba(74,227,140,0.22);
  border-radius: var(--srd-radius);
  color: var(--srd-bone-80);
  font-size: 14px;
  line-height: 1.6;
}
.srd-did-well-label {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.20em;
  text-transform: uppercase;
  color: var(--srd-green);
  margin-bottom: 0.4rem;
  font-weight: 600;
}

/* Filming guide */
.srd-filming-guide {
  margin-top: 1rem;
  padding: 0.85rem 1.1rem;
  background: rgba(232,193,112,0.06);
  border: 1px solid rgba(232,193,112,0.22);
  border-radius: var(--srd-radius);
}
.srd-filming-label {
  font-family: var(--srd-mono);
  font-size: 9.5px;
  letter-spacing: 0.20em;
  text-transform: uppercase;
  color: var(--srd-gold);
  margin-bottom: 0.4rem;
  font-weight: 600;
}
.srd-filming-text {
  color: var(--srd-bone-60);
  font-size: 13px;
  line-height: 1.6;
}

/* Age nudge caption */
.srd-age-nudge { margin-top:8px; font-size:12px; line-height:1.4;
  color:rgba(244,239,230,0.62); font-style:italic; }

/* New score card layout for two-system */
.srd-score-card-two {
  background:
    radial-gradient(ellipse at 100% 0%, rgba(230,69,48,0.06) 0%, transparent 55%),
    var(--srd-glass-1);
  border: 1px solid var(--srd-line);
  border-radius: var(--srd-radius-lg);
  padding: 1.6rem 1.7rem;
  margin-bottom: 1rem;
}
.srd-score-card-top {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1.6rem;
  align-items: start;
}

/* Pillar re-film warning */
.srd-pillar-warn {
  font-family: var(--srd-mono);
  font-size: 10px;
  letter-spacing: 0.10em;
  color: var(--srd-red);
  font-style: italic;
  margin-top: 0.2rem;
}
</style>
"""


# =====================================================================
#                           SECTION BUILDERS
# =====================================================================


def _band_class_srd(band_color: str, score: int) -> str:
    bc = (band_color or "").lower()
    if bc in {"green", "elite"}: return "green"
    if bc in {"red", "rebuild"}: return "red"
    if bc in {"amber", "strong", "building", "gold"}: return "amber"
    # Derive from score if no hint
    if score >= 85: return "green"
    if score < 60:  return "red"
    return "amber"


def _ring_svg(score: int, band: str, size: int = 130) -> str:
    color = {"green": "#4AE38C", "amber": "#E8C170", "red": "#E64530"}.get(band, "#E8C170")
    radius = (size / 2) - 8
    cx = cy = size / 2
    circ = 2 * 3.14159 * radius
    pct = max(0, min(100, score)) / 100
    dash = pct * circ
    return f"""
<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" style="display:block;">
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none"
          stroke="rgba(244,239,230,0.08)" stroke-width="5"/>
  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="none"
          stroke="{color}" stroke-width="5" stroke-linecap="round"
          stroke-dasharray="{dash:.2f} {circ:.2f}"
          transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy + 6}" text-anchor="middle"
        font-family="Instrument Serif, Georgia, serif" font-style="italic"
        font-size="34" fill="#F4EFE6">{score}</text>
</svg>
"""


def _radar_svg(axes: List[Tuple[str, float]], size: int = 220) -> str:
    n = len(axes)
    if n == 0:
        return ""
    import math
    cx = cy = size / 2
    R = size / 2 - 22
    # Grid rings
    rings = []
    for r_pct in (0.25, 0.5, 0.75, 1.0):
        pts = []
        for i in range(n):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            x = cx + R * r_pct * math.cos(ang)
            y = cy + R * r_pct * math.sin(ang)
            pts.append(f"{x:.1f},{y:.1f}")
        rings.append(
            f'<polygon points="{" ".join(pts)}" fill="none" '
            f'stroke="rgba(244,239,230,0.06)" stroke-width="1"/>'
        )
    # Axis lines + labels
    axis_lines, labels = [], []
    for i, (lbl, _pct) in enumerate(axes):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        x = cx + R * math.cos(ang)
        y = cy + R * math.sin(ang)
        axis_lines.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="rgba(244,239,230,0.06)" stroke-width="1"/>'
        )
        lx = cx + (R + 12) * math.cos(ang)
        ly = cy + (R + 12) * math.sin(ang) + 3
        anchor = "middle"
        if math.cos(ang) > 0.3: anchor = "start"
        elif math.cos(ang) < -0.3: anchor = "end"
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-family="Geist Mono, monospace" font-size="8.5" '
            f'fill="rgba(244,239,230,0.5)" letter-spacing="1.6">{html.escape(lbl)}</text>'
        )
    # Player polygon
    pts = []
    for i, (_lbl, pct) in enumerate(axes):
        p = max(0, min(100, float(pct or 0))) / 100
        ang = -math.pi / 2 + 2 * math.pi * i / n
        x = cx + R * p * math.cos(ang)
        y = cy + R * p * math.sin(ang)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = (
        f'<polygon points="{" ".join(pts)}" fill="rgba(232,193,112,0.18)" '
        f'stroke="#E8C170" stroke-width="1.6" stroke-linejoin="round"/>'
    )
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" style="display:block;">'
        + "".join(rings) + "".join(axis_lines) + poly + "".join(labels)
        + '</svg>'
    )


def _sparkline_svg(points: List[float], width: int = 280, height: int = 90,
                    color: str = "#E8C170") -> str:
    if not points:
        return ""
    pad_x, pad_y = 6, 8
    lo, hi = min(points), max(points)
    span = max(hi - lo, 1)
    step = (width - 2 * pad_x) / max(len(points) - 1, 1)
    coords = []
    for i, v in enumerate(points):
        x = pad_x + i * step
        y = (height - pad_y) - ((v - lo) / span) * (height - 2 * pad_y)
        coords.append((x, y))
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = path + f" L {coords[-1][0]:.1f},{height} L {coords[0][0]:.1f},{height} Z"
    last_x, last_y = coords[-1]
    return f"""
<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none">
  <defs>
    <linearGradient id="srd-spark-grad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="{color}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <path d="{area}" fill="url(#srd-spark-grad)"/>
  <path d="{path}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3.2" fill="{color}"/>
</svg>
"""


# Phrase library used to turn raw metric labels into player-traits.
# Keys are matched as case-insensitive substrings against metric labels
# so "Hip rotation at contact" → "Explosive hip rotation through contact".
_TRAIT_PHRASES: List[Tuple[str, str]] = [
    ("hip-shoulder separation", "Efficient hip-shoulder sequencing"),
    ("hip-shoulder",            "Efficient hip-shoulder sequencing"),
    ("hip rotation",            "Explosive hip rotation through contact"),
    ("bat path",                "Clean, repeatable bat path"),
    ("bat speed",               "High-end bat speed"),
    ("swing duration",          "Compact, repeatable swing tempo"),
    ("foot plant",              "Sharp, on-time foot plant"),
    ("launch",                  "Snappy launch-to-contact window"),
    ("re-extension",            "Powerful lower-body re-extension"),
    ("most bent",               "Athletic, balanced load position"),
    ("load",                    "Stable, athletic load position"),
    ("head drift",              "Stable head and locked visual line"),
    ("stride",                  "Balanced stride length"),
    ("shoulder",                "Strong shoulder load and turn"),
    ("rotation",                "Explosive rotational acceleration"),
    ("contact",                 "Consistent contact mechanics"),
]


def _trait_phrase_for(label: str) -> str:
    """Map a raw metric/category label to a player-trait phrase."""
    ll = (label or "").lower()
    for key, phrase in _TRAIT_PHRASES:
        if key in ll:
            return phrase
    # Fallback: title-case the label so we never emit raw snake_case.
    return (label or "").strip().title() or "Sound fundamentals"


def _gap_sentence(row: Dict[str, Any], ref_name: str) -> str:
    """One-sentence diagnosis of the worst metric, tied to the reference."""
    raw_label = (row.get("label") or "this mechanic").strip()
    label = raw_label[0].upper() + raw_label[1:] if raw_label else "This mechanic"
    you = row.get("player_str") or "—"
    mlb = row.get("ref_str") or "—"
    if you != "—" and mlb != "—":
        return (
            f"{label} sits at {you} versus {ref_name}'s {mlb} — "
            f"the largest mechanical gap between your swings."
        )
    return (
        f"{label} is the biggest mechanical gap between your swing and {ref_name}'s."
    )


# Templated "why this comparison matters" lines, keyed by the category of
# the top narrative. Used as a fallback when the analyzer's own copy
# isn't available.
_WHY_BY_TOPIC: List[Tuple[str, str]] = [
    ("hip",        "Closing this gap restores the elastic torque MLB hitters use to drive bat speed and exit velocity."),
    ("separation", "Tighter hip-shoulder sequencing is the single biggest unlock for bat speed at this level."),
    ("head",       "Stabilising the head improves visual tracking, contact quality, and pitch recognition under stress."),
    ("lower",      "Re-sequencing the lower body lets you keep stored energy until contact instead of bleeding it early."),
    ("rotation",   "Sharper rotation gives you more barrel time in the zone without losing balance."),
    ("contact",    "More consistent contact mechanics is what separates good high-school timing from pro-level repeatability."),
    ("timing",     "Better timing keeps your swing on-plane through more pitch locations."),
    ("stride",     "A cleaner stride sets up everything downstream — sequencing, balance, and bat path."),
]

_WHY_DEFAULT = (
    "Closing this gap is the fastest path to more bat speed, cleaner contact, "
    "and a more repeatable swing."
)


def _why_matters_sentence(record: Dict[str, Any]) -> str:
    """Single sentence explaining why the top gap matters.
    Prefer the analyzer's own narrative; fall back to a topic-templated line.
    """
    narratives = record.get("narratives") or []
    if narratives:
        paras = narratives[0].get("paragraphs") or []
        if len(paras) > 1:
            txt = (paras[1] or "").replace("Why it costs you: ", "").strip()
            if txt:
                # Already a complete sentence — trust it.
                return txt
        title = (narratives[0].get("title") or "").lower()
        for key, sentence in _WHY_BY_TOPIC:
            if key in title:
                return sentence
    return _WHY_DEFAULT


def _build_mlb_insights(record: Dict[str, Any],
                        ref_name: str) -> Tuple[List[str], str, str]:
    """Return (shared_traits, biggest_gap_sentence, why_matters_sentence).

    `shared_traits` is 2-4 deduped phrases derived from the highest sim_pct
    rows in metric_table (≥75%). If fewer than 2 qualify, we top up from
    the precomputed `strengths` list. Every output is plain text — caller
    is responsible for HTML escaping.
    """
    rows = _flatten_metric_table(record)
    scored = [r for r in rows if r.get("sim_pct") is not None]
    high = sorted(scored, key=lambda r: r.get("sim_pct", 0), reverse=True)
    low = sorted(scored, key=lambda r: r.get("sim_pct", 0))

    traits: List[str] = []
    seen = set()
    for r in high:
        if (r.get("sim_pct") or 0) < 75:
            break
        phrase = _trait_phrase_for(r.get("label", ""))
        if phrase in seen:
            continue
        seen.add(phrase)
        traits.append(phrase)
        if len(traits) >= 4:
            break

    if len(traits) < 2:
        for s in (record.get("strengths") or []):
            phrase = _trait_phrase_for(s.get("category_label") or "")
            if phrase and phrase not in seen:
                seen.add(phrase)
                traits.append(phrase)
            if len(traits) >= 3:
                break

    if not traits:
        traits = ["Shared athletic foundation"]

    biggest_gap = ""
    if low:
        biggest_gap = _gap_sentence(low[0], ref_name)

    why = _why_matters_sentence(record)
    return traits, biggest_gap, why


# =====================================================================
#                   TWO-SYSTEM SECTION BUILDERS
# =====================================================================


def _confidence_class(confidence: Optional[float]) -> str:
    """Return 'green', 'amber', or 'red' based on pillar confidence value."""
    if confidence is None:
        return "red"
    if confidence >= 0.8:
        return "green"
    if confidence >= 0.4:
        return "amber"
    return "red"


def _build_confidence_badge(confidence: Optional[float]) -> str:
    """Return an HTML confidence badge for the given confidence value."""
    cls = _confidence_class(confidence)
    labels = {"green": "High", "amber": "Medium", "red": "Low"}
    lbl = labels[cls]
    return f'<span class="srd-conf-badge {cls}">{lbl}</span>'


def _filming_guide_needed(pillars: Optional[Dict[str, Any]]) -> bool:
    """Return True if any pillar has yellow or red confidence."""
    if not pillars:
        return False
    for pillar_data in pillars.values():
        conf = pillar_data.get("confidence")
        if conf is None or conf < 0.8:
            return True
    return False


def _build_filming_guide() -> str:
    """Return the 'Film it like this' inline guide block."""
    return """
<div class="srd-filming-guide">
  <div class="srd-filming-label">Film it like this</div>
  <div class="srd-filming-text">
    Film side-on, perpendicular to the pitcher &nbsp;&middot;&nbsp; full body in
    frame &nbsp;&middot;&nbsp; good light &nbsp;&middot;&nbsp; slow-mo
    (120/240fps) if your phone supports it
  </div>
</div>
"""


def _build_match_reveal(record: Dict[str, Any]) -> str:
    """Card 1 — MLB Match reveal: full-width hero at the very top.

    Shows the pro name always. Shows the movement-match % ONLY when
    mlb_match.confident is True, labeled as 'movement match'. Never
    '/100', never red-banded. When not confident, shows a side-angle nudge.

    Falls back gracefully to the legacy `reference` block.
    """
    mlb = record.get("mlb_match") or {}
    reference = record.get("reference") or {}

    # Resolve pro name: new field first, legacy fallback
    pro_name = (
        mlb.get("pro_name")
        or reference.get("name")
        or "Your Pro Match"
    )
    initials = _initials(pro_name)

    confident = mlb.get("confident", False)
    movement_pct = mlb.get("movement_match_pct")
    locked = mlb.get("locked", False)

    # Style identity / team from reference
    team_pos = (reference.get("team") or "")
    if reference.get("position"):
        sep = " · " if team_pos else ""
        team_pos = f"{team_pos}{sep}{reference['position']}"
    style_text = (reference.get("style") or "")

    # Movement match % — only when confident and present; never /100
    if confident and movement_pct is not None and mlb:
        pct_html = f"""
<div class="srd-match-pct-row">
  <span class="srd-match-pct">{int(movement_pct)}%</span>
  <span class="srd-match-pct-label">movement match</span>
</div>
"""
        nudge_html = ""
    else:
        pct_html = ""
        if mlb:
            # New record but low confidence — show nudge
            nudge_html = (
                '<div class="srd-match-nudge">'
                'Film a cleaner side angle to confirm your match.'
                '</div>'
            )
        else:
            # Legacy record — no nudge, no %
            nudge_html = ""

    style_html = (
        f'<div class="srd-mlb-style">{html.escape(style_text)}</div>'
        if style_text else ""
    )

    team_html = (
        f'<div class="srd-mlb-team">{html.escape(team_pos)}</div>'
        if team_pos else ""
    )

    locked_tag = ""
    if locked:
        locked_tag = (
            '<span class="srd-conf-badge green" style="margin-left:10px;">LOCKED</span>'
        )

    return f"""
<div class="srd-match-reveal">
  <div class="srd-match-eyebrow">MLB Match{locked_tag}</div>
  <div class="srd-match-body">
    <div class="srd-match-avatar">{initials}</div>
    <div class="srd-match-info">
      <div class="srd-match-name">{html.escape(pro_name)}</div>
      {team_html}
      {pct_html}
      {nudge_html}
      {style_html}
    </div>
  </div>
</div>
"""


def _build_reconciliation() -> str:
    """The exact reconciliation line between Match and Score."""
    return """
<div class="srd-reconcile">
  Your Match is who you move like; your Swing Score is how well you&#39;re
  executing it &#8212; <strong>you grow your Score, not your Match.</strong>
</div>
"""


def _build_pillar_bars(pillars: Dict[str, Any]) -> str:
    """Render the 4 pillar mini-bars with compliance + confidence badges."""
    PILLAR_ORDER = [
        ("sequence",  "Sequence"),
        ("stability", "Stability"),
        ("timing",    "Timing"),
        ("stride",    "Stride"),
    ]
    rows_html = []
    for key, display in PILLAR_ORDER:
        p = pillars.get(key) or {}
        compliance = p.get("compliance")
        confidence = p.get("confidence")
        label = p.get("label") or display

        fill_pct = int(round((compliance or 0) * 100))
        conf_cls = _confidence_class(confidence)
        fill_color_cls = conf_cls  # green/amber/red maps to same bar color

        # Low-confidence warning
        if conf_cls == "red":
            warn_html = (
                '<div class="srd-pillar-warn">'
                'Couldn&#39;t read this cleanly — re-film for a better read.'
                '</div>'
            )
        else:
            warn_html = ""

        badge_html = _build_confidence_badge(confidence)
        rows_html.append(f"""
<div>
  <div class="srd-pillar-row">
    <span class="srd-pillar-label">{html.escape(display)}</span>
    <div class="srd-pillar-track">
      <div class="srd-pillar-fill {fill_color_cls}" style="width:{fill_pct}%;"></div>
    </div>
    <div class="srd-pillar-right">{badge_html}</div>
  </div>
  {warn_html}
</div>
""")
    return f'<div class="srd-pillars">{"".join(rows_html)}</div>'


def _build_score_card(record: Dict[str, Any],
                      history: Optional[List[Dict[str, Any]]]) -> str:
    """Card 2 — Swing Score: ring/number + band + pillar bars + what-you-did-well.

    Falls back gracefully when new fields are absent (legacy records).
    """
    # Headline score — new field first, legacy fallback. A swing_score of 0
    # is a legitimate value (all pillars zero), so test for None rather than
    # falsiness — an `or` chain would wrongly fall through to the legacy
    # pro-similarity score for a real zero-scoring swing.
    raw_score = record.get("swing_score")
    if raw_score is None:
        raw_score = record.get("score") or 0
    try:
        score = int(round(float(raw_score)))
    except (TypeError, ValueError):
        score = 0

    band_class = _band_class_srd(record.get("score_band_color") or "", score)
    band_label = (record.get("score_band_label") or {
        "green": "Elite", "amber": "Strong Foundation", "red": "Rebuild Zone"
    }[band_class])

    ring = _ring_svg(score, band_class, size=130)

    # Δ vs prior
    prog = swing_progress(record, history) or {}
    delta = prog.get("score_delta")
    if delta is None or not prog.get("has_prior"):
        delta_html = (
            '<div class="srd-ring-delta flat">'
            'Baseline<span class="sub">First measured swing</span></div>'
        )
    else:
        d = int(round(float(delta)))
        prev_int = int(round(float(prog.get("prev_score") or 0)))
        if d > 0:
            cls, arrow, txt = "up", "↑", f"+{d}"
        elif d < 0:
            cls, arrow, txt = "down", "↓", f"{d}"
        else:
            cls, arrow, txt = "flat", "→", "±0"
        delta_html = (
            f'<div class="srd-ring-delta {cls}">{arrow}&nbsp;{txt}'
            f'<span class="sub">vs previous · {prev_int}</span></div>'
        )

    # Overall confidence badge (mean pillar confidence or None)
    pillars = record.get("pillars")
    overall_conf_html = ""
    pillar_html = ""
    filming_guide_html = ""

    if pillars:
        confs = [p.get("confidence") for p in pillars.values()
                 if p.get("confidence") is not None]
        mean_conf = (sum(confs) / len(confs)) if confs else None
        overall_conf_html = _build_confidence_badge(mean_conf)
        pillar_html = _build_pillar_bars(pillars)
        if _filming_guide_needed(pillars):
            filming_guide_html = _build_filming_guide()
    else:
        # Legacy: show aggregate badge from band only (no exact confidence)
        overall_conf_html = ""

    # "What you did well" — renders before any fix
    well_text = record.get("what_you_did_well") or ""
    did_well_html = ""
    if well_text:
        did_well_html = f"""
<div class="srd-did-well">
  <div class="srd-did-well-label">What you did well</div>
  {html.escape(well_text)}
</div>
"""

    # Honest age nudge (#134): only on new-engine reports (those with a
    # swing_score) where age was unknown, so the score used the default band.
    _is_new_engine = record.get("swing_score") is not None
    _age_unknown = not record.get("age_known", False)
    age_nudge_html = ""
    if _is_new_engine and _age_unknown:
        age_nudge_html = (
            '<div class="srd-age-nudge">Scored on the 13–14 standard — '
            'add your birth year in Settings for an age-accurate score.</div>'
        )

    return f"""
<div class="srd-score-card-two">
  <div class="srd-card-eyebrow">
    <span class="dot"></span>Swing Score {overall_conf_html}
  </div>
  <div class="srd-score-card-top">
    <div>
      <div>
        <span class="srd-score-num">{score}</span>
      </div>
      <div class="srd-score-band {band_class}">
        <span class="dot"></span>{html.escape(band_label.upper())}
      </div>
      {age_nudge_html}
    </div>
    <div class="srd-ring-wrap">
      {ring}
      {delta_html}
    </div>
  </div>
  {pillar_html}
  {did_well_html}
  {filming_guide_html}
</div>
"""


def _fmt_date(record: Dict[str, Any]) -> str:
    return (
        record.get("date_str")
        or record.get("date")
        or (record.get("timestamp", "")[:10] if record.get("timestamp") else "")
        or "—"
    )


def _swing_label(record: Dict[str, Any]) -> str:
    num = record.get("swing_number")
    if num: return f"Swing No. {num}"
    return "Latest Swing"


# =====================================================================
#                      POWER SEQUENCE SECTION
# =====================================================================

# Plain-language coach lines per rating (spec § Tile copy).
_POWER_COPY = {
    "sequencing_lag": {
        "good":     "Pelvis-then-torso, the way pros do it.",
        "marginal": "Hips and shoulders firing close together — small power leak.",
        "poor":     "Shoulders fired before the hips. Top fix.",
        None:       "Need a cleaner side angle to read this.",
    },
    "peak_hip_omega": {
        "good":     "Solid rotational power. Good HS / college-prep range.",
        "marginal": "Build hip speed — med-ball rotational throws.",
        "poor":     "Hips aren't yet generating elite rotational power.",
        None:       "Could not measure.",
    },
    "front_side_stability": {
        "good":     "Front side stayed shut through plant.",
        "marginal": "Front side opening earlier than ideal.",
        "poor":     "Front shoulder flew open early. #1 amateur fault.",
        None:       "Not enough shoulder rotation to characterize.",
    },
    "tempo_ratio": {
        "good":     "A real gather into a crisp fire — pro tempo.",
        "marginal": "Lengthen the gather (or sharpen the fire) and the barrel jumps.",
        "poor":     "Rushed — not enough gather before you fire.",
        None:       "Gather-to-fire ratio — grade needs a cleaner read.",
    },
    "xfactor_timing": {
        "good":     "Stretch holds, then unwinds into the ball — elite.",
        "marginal": "Separation peaks right around contact — a hair earlier adds power.",
        "poor":     "Separation peaks after contact — you're unwinding late.",
        None:       "Need a cleaner side angle to read this.",
    },
}


def _format_pwr_value(metric: str, value):
    """Format the tile value + unit per metric."""
    if value is None:
        return ("—", "")
    if metric == "sequencing_lag":
        return (f"{value:.0f}", "ms")
    if metric == "peak_hip_omega":
        return (f"{value:.0f}", "°/s")
    if metric == "front_side_stability":
        return (f"{value:.0f}", "%")
    return (f"{value}", "")


def _xfactor_rating(ms):
    """Good/marginal/poor for X-Factor timing (peak hip-shoulder separation
    relative to contact, ms; negative = before contact). "Balanced" band:
    good <= -20 (unwinds into the ball), marginal -20 < ms <= 10 (~at contact),
    poor > 10 (peaks after contact). None when unmeasured."""
    if ms is None:
        return None
    if ms <= -20:
        return "good"
    if ms <= 10:
        return "marginal"
    return "poor"


def _xfactor_value(ms):
    """(value, unit) for the X-Factor tile. Sign mapped to early/late so the
    number stays coach-legible (no raw negatives). None -> ("—", "")."""
    if ms is None:
        return ("—", "")
    n = f"{abs(ms):.0f}"
    if ms < 0:
        return (n, "ms early")
    if ms > 0:
        return (n, "ms late")
    return ("0", "ms")


def _tempo_rating(record):
    """Good/marginal/poor for the Tempo (gather:fire) tile, derived from the
    Timing PILLAR's compliance so the tile can never contradict the Timing bar
    shown elsewhere. None when the pillar is unmeasured (no compliance, or zero
    confidence)."""
    p = ((record.get("pillars") or {}).get("timing")) or {}
    comp = p.get("compliance")
    if comp is None or (p.get("confidence", 0) or 0) <= 0:
        return None
    if comp >= 0.66:
        return "good"
    if comp >= 0.33:
        return "marginal"
    return "poor"


def _render_power_sequence(record) -> str:
    """Return the HTML for the Kinetic-Chain section, or empty string.

    Surfaces up to three phone-reliable reads, each as its own tile:
      1. SEQUENCING — the hips-vs-shoulders firing ORDER (categorical, never a
         false-precise ms).
      2. TEMPO — the gather:fire ratio (`tempo_ratio`); its grade REUSES the
         Timing pillar so the tile can never contradict the Timing bar.
      3. X-FACTOR — when peak hip-shoulder SEPARATION lands vs contact
         (`xfactor_timing_ms`); negative = unwinds into the ball.

    Each tile is independent: the section shows if ANY has data, and a tile
    with no data is omitted (never faked). Peak hip speed + front-side
    stability stay hidden — unreliable from a single phone video, and we never
    display a number we can't stand behind. One tile -> spans full width
    (preserves the legacy sequencing-only look); two or more -> the 3-col grid.
    The bottom verdict line is driven by sequencing only."""
    # Each tile: (rating_class, label, value, unit, coach)
    tiles = []
    verdict = ""

    # 1. Sequencing — categorical firing order.
    seq = (record.get("sequence") or {})
    lag_rating = (seq.get("rating") or {}).get("sequencing_lag")
    if lag_rating is not None and seq.get("sequencing_lag_ms") is not None:
        category = {
            "good":     "Hips lead",
            "marginal": "Nearly synced",
            "poor":     "Shoulders fire early",
        }.get(lag_rating, "—")
        tiles.append((
            lag_rating, "Sequencing — hips vs. shoulders", category, "",
            _POWER_COPY["sequencing_lag"].get(lag_rating, ""),
        ))
        verdict = {
            "good":     "Your chain fired in the right order — pelvis first, then torso. "
                        "That sequence is where real bat speed comes from.",
            "marginal": "Your chain is close. Get the hips to clearly lead the shoulders "
                        "and the barrel will jump.",
            "poor":     "Your shoulders are firing before your hips — that's casting, and "
                        "it's the single biggest power leak available to fix.",
        }.get(lag_rating, "")

    # 2. Tempo (gather:fire) — grade tracks the Timing pillar.
    tempo = record.get("tempo_ratio")
    if tempo is not None:
        t_rating = _tempo_rating(record)
        tiles.append((
            t_rating or "marginal",          # neutral border when grade uncertain
            "Tempo — gather : fire", f"{float(tempo):.1f} : 1", "",
            _POWER_COPY["tempo_ratio"].get(t_rating, _POWER_COPY["tempo_ratio"][None]),
        ))

    # 3. X-Factor timing — separation peak vs contact.
    xms = record.get("xfactor_timing_ms")
    if xms is not None:
        x_rating = _xfactor_rating(xms)
        x_val, x_unit = _xfactor_value(xms)
        tiles.append((
            x_rating or "marginal",
            "X-Factor — separation timing", x_val, x_unit,
            _POWER_COPY["xfactor_timing"].get(x_rating, ""),
        ))

    if not tiles:
        return ""

    # 1 tile -> the tile itself spans full width; 2 tiles -> fill the row 50/50
    # via a modifier class (not inline grid-template-columns, which would beat
    # the mobile 1-col media query); 3 -> the default responsive 3-col grid.
    span = ' style="grid-column: 1 / -1;"' if len(tiles) == 1 else ""
    tiles_cls = "srd-power-tiles" + (" srd-power-tiles--two" if len(tiles) == 2 else "")
    tiles_html = ""
    for cls, label, value, unit, coach in tiles:
        unit_html = f'<span class="srd-power-tile-unit">{unit}</span>' if unit else ""
        tiles_html += f"""
        <div class="srd-power-tile {cls}"{span}>
          <div class="srd-power-tile-label">{label}</div>
          <div class="srd-power-tile-value">{value}{unit_html}</div>
          <div class="srd-power-tile-coach">{coach}</div>
        </div>"""
    verdict_html = f'\n      <p class="srd-power-verdict">{verdict}</p>' if verdict else ""

    return f"""
    <div class="srd-power-section">
      <div class="srd-power-eyebrow">§ 01 · Kinetic Chain</div>
      <h2 class="srd-power-title">How your body <span class="ital">fired.</span></h2>
      <div class="{tiles_cls}">{tiles_html}
      </div>{verdict_html}
    </div>
    """


def _build_header(record: Dict[str, Any], is_sample: bool) -> str:
    swing = _swing_label(record)
    date = _fmt_date(record)
    ref = _extract_ref_info(record)
    sample_tag = '<span class="srd-banner-tag">SAMPLE DATA</span>' if is_sample else \
        '<span class="srd-banner-tag" style="color:var(--srd-bone-80);">REAL DATA</span>'
    return f"""
<div class="srd-banner">
  <span class="srd-banner-dot"></span>
  <span class="srd-banner-text">Preview only — not the live report</span>
  {sample_tag}
</div>

<div class="srd-pagehead">
  <div>
    <div class="srd-eyebrow">Premium Swing Report</div>
    <h1 class="srd-pagehead-title">{html.escape(swing)}</h1>
  </div>
  <div class="srd-pagehead-meta">
    Captured<strong>{html.escape(date)}</strong>
    <div style="margin-top:14px;">Comparison<strong>{html.escape(ref.get('name') or 'Unknown')}</strong></div>
  </div>
</div>
"""


def _build_hero(record: Dict[str, Any],
                history: Optional[List[Dict[str, Any]]]) -> str:
    # Score
    try:
        score = int(round(float(record.get("score") or 0)))
    except (TypeError, ValueError):
        score = 0
    band_class = _band_class_srd(record.get("score_band_color") or "", score)
    band_label = (record.get("score_band_label") or {"green": "Elite",
                  "amber": "Strong Foundation", "red": "Rebuild Zone"}[band_class])
    ring = _ring_svg(score, band_class, size=130)

    # Δ vs prior
    prog = swing_progress(record, history) or {}
    delta = prog.get("score_delta")
    if delta is None or not prog.get("has_prior"):
        delta_html = (
            '<div class="srd-ring-delta flat">'
            'Baseline<span class="sub">First measured swing</span></div>'
        )
    else:
        d = int(round(float(delta)))
        prev_int = int(round(float(prog.get("prev_score") or 0)))
        if d > 0:
            cls, arrow, txt = "up", "↑", f"+{d}"
        elif d < 0:
            cls, arrow, txt = "down", "↓", f"{d}"
        else:
            cls, arrow, txt = "flat", "→", "±0"
        delta_html = (
            f'<div class="srd-ring-delta {cls}">{arrow}&nbsp;{txt}'
            f'<span class="sub">vs previous · {prev_int}</span></div>'
        )

    blurb = coach_summary(record)

    # MLB comp
    ref = _extract_ref_info(record)
    initials = _initials(ref.get("name", ""))

    # Radar — same 5 dims as v2 hero
    rows = _flatten_metric_table(record)
    def _avg(needles: List[str]) -> float:
        vals = []
        for n in needles:
            r = _find_metric_row(rows, n)
            if r is not None and r.get("sim_pct") is not None:
                vals.append(float(r["sim_pct"]))
        return (sum(vals) / len(vals)) if vals else 0.0

    axes = [
        ("ROTATION",   _avg(["Hip rotation at foot plant", "Hip rotation at contact"])),
        ("SEPARATION", _avg(["Peak hip-shoulder separation", "Separation at foot plant"])),
        ("TIMING",     _avg(["Total swing duration", "Foot plant → launch", "Launch → contact"])),
        ("LOWER BODY", _avg(["Re-extension", "Most bent (load)"])),
        ("STABILITY",  _avg(["Total head drift", "Head drift Δx", "Head drift Δy"])),
    ]
    sim_pct = int(round((sum(p for _, p in axes) / max(len(axes), 1))))
    radar = _radar_svg(axes, size=190)

    team_pos = (ref.get("team") or "")
    if ref.get("position"):
        team_pos = f"{team_pos} · {ref['position']}" if team_pos else ref["position"]

    # MLB insight blocks — shared traits / biggest gap / why this matters
    traits, biggest_gap, why_matters = _build_mlb_insights(
        record, ref.get("name") or "your reference"
    )
    traits_html = "".join(
        f'<span class="srd-mlb-trait">{html.escape(t)}</span>' for t in traits
    )
    gap_html = (
        f'<div class="srd-mlb-gap">{html.escape(biggest_gap)}</div>'
        if biggest_gap else ""
    )
    why_html = (
        f'<div class="srd-mlb-why">{html.escape(why_matters)}</div>'
        if why_matters else ""
    )

    # Strengths chips
    strengths = record.get("strengths") or []
    chips = "".join(
        f'<span class="srd-chip">{html.escape(s.get("category_label",""))} · {int(s.get("sim_pct",0))}%</span>'
        for s in strengths[:3] if s.get("category_label")
    )
    chips_html = f'<div class="srd-chips">{chips}</div>' if chips else ""

    return f"""
<div class="srd-hero">
  <div class="srd-hero-card">
    <div class="srd-card-eyebrow"><span class="dot"></span>Overall Swing Score</div>
    <div class="srd-hero-grid">
      <div>
        <div>
          <span class="srd-score-num">{score}</span>
          <span class="srd-score-foot">/ 100</span>
        </div>
        <div class="srd-score-band {band_class}">
          <span class="dot"></span>{html.escape(band_label.upper())}
        </div>
        <div class="srd-score-blurb">{blurb}</div>
        {chips_html}
      </div>
      <div class="srd-ring-wrap">
        {ring}
        {delta_html}
      </div>
    </div>
  </div>

  <div class="srd-hero-card mlb">
    <div class="srd-card-eyebrow"><span class="dot" style="background:var(--srd-gold);"></span>MLB Comparison</div>
    <div class="srd-mlb-grid">
      <div>
        <div class="srd-mlb-avatar-row">
          <div class="srd-mlb-avatar">{initials}</div>
          <div>
            <div class="srd-mlb-name">{html.escape(ref.get("name") or "Unknown")}</div>
            <div class="srd-mlb-team">{html.escape(team_pos)}</div>
          </div>
        </div>
        <div class="srd-mlb-sim-row">
          <div class="srd-mlb-sim">{sim_pct}%</div>
          <div class="srd-mlb-sim-foot">Biomechanical similarity</div>
        </div>
      </div>
      <div class="srd-mlb-radar">{radar}</div>
    </div>
    <div class="srd-mlb-insights">
      <div>
        <div class="srd-mlb-insight-eyebrow gold"><span class="dot"></span>Shared Traits</div>
        <div class="srd-mlb-traits">{traits_html}</div>
      </div>
      <div>
        <div class="srd-mlb-insight-eyebrow red"><span class="dot"></span>Biggest Gap</div>
        {gap_html}
      </div>
      <div>
        <div class="srd-mlb-insight-eyebrow bone"><span class="dot"></span>Why this comparison matters</div>
        {why_html}
      </div>
    </div>
  </div>
</div>
"""


def _severity_tag(sev: str) -> Tuple[str, str]:
    s = (sev or "").lower()
    if s == "high": return ("high", "Major Gap")
    if s == "low":  return ("low",  "Light Tune")
    return ("med", "Worth Fixing")


def _build_priorities_drills(record: Dict[str, Any],
                              history: Optional[List[Dict[str, Any]]]) -> str:
    fixes = top_three_fixes(record) or []
    if history:
        try:
            fixes = enrich_fixes_with_history(fixes, history) or fixes
        except Exception:
            pass

    pri_rows = []
    if not fixes:
        pri_rows.append(
            '<div class="srd-pri"><div class="srd-pri-num">—</div>'
            '<div><div class="srd-pri-head"><div class="srd-pri-title">No priorities yet</div></div>'
            '<div class="srd-pri-desc">Upload another swing and we\u2019ll surface the biggest unlocks.</div></div></div>'
        )
    for f in fixes[:3]:
        rank = f.get("rank") or "•"
        title = (f.get("title") or "Priority").title()
        desc = (f.get("why") or f.get("headline") or "").strip()
        tag_cls, tag_lbl = _severity_tag(f.get("severity"))
        pri_rows.append(f"""
<div class="srd-pri">
  <div class="srd-pri-num">{html.escape(str(rank))}</div>
  <div>
    <div class="srd-pri-head">
      <div class="srd-pri-title">{html.escape(title)}</div>
      <div class="srd-pri-tag {tag_cls}">{tag_lbl}</div>
    </div>
    <div class="srd-pri-desc">{html.escape(desc)}</div>
  </div>
</div>
""")

    drill_plan = record.get("drill_plan") or {}
    cats = drill_plan.get("categories", []) if isinstance(drill_plan, dict) else []
    drill_rows, idx = [], 0
    for cat in cats[:2]:
        for d in (cat.get("drills") or [])[:2]:
            idx += 1
            sets, reps = d.get("sets"), d.get("reps")
            freq = d.get("frequency") or d.get("weekly")
            pills = []
            if sets: pills.append(f"{sets} sets")
            if reps: pills.append(f"{reps} reps")
            if freq: pills.append(str(freq))
            pills_html = "".join(
                f'<span class="srd-drill-pill">{html.escape(p)}</span>' for p in pills
            )
            drill_rows.append(f"""
<div class="srd-drill">
  <div class="srd-drill-thumb">DRILL<br/>{idx:02d}</div>
  <div>
    <div class="srd-drill-title">{html.escape(d.get("title") or d.get("name") or "Drill")}</div>
    <div class="srd-drill-pills">{pills_html}</div>
  </div>
  <div class="srd-drill-check">○</div>
</div>
""")
    if not drill_rows:
        drill_rows.append(
            '<div class="srd-drill"><div class="srd-drill-thumb">—</div>'
            '<div><div class="srd-drill-title">No drills assigned yet</div>'
            '<div class="srd-drill-pills"><span class="srd-drill-pill">Complete a swing analysis</span></div></div>'
            '<div class="srd-drill-check">○</div></div>'
        )

    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Top Priorities &amp; Drills</div>
    <h2 class="srd-section-title">Where to spend your next session</h2>
  </div>
  <div class="srd-section-sub">{len(fixes[:3])} priorities · {len(drill_rows)} drills</div>
</div>

<div class="srd-pd-grid">
  <div class="srd-stack">
    <div class="srd-card-eyebrow"><span class="dot"></span>Top 3 Priorities</div>
    <div class="srd-pri-list">{''.join(pri_rows)}</div>
  </div>
  <div class="srd-stack">
    <div class="srd-card-eyebrow"><span class="dot" style="background:var(--srd-gold);"></span>Recommended Drills</div>
    <div class="srd-drill-list">{''.join(drill_rows)}</div>
  </div>
</div>
"""


def _build_key_metrics(record: Dict[str, Any],
                       history: Optional[List[Dict[str, Any]]]) -> str:
    tiles = _compute_key_metrics(record, history) or []
    tile_html = []
    for t in tiles[:4]:
        unit_html = (f'<span class="srd-km-unit">{html.escape(t.get("unit") or "")}</span>'
                     if t.get("unit") else "")
        delta_html = ""
        if t.get("delta_str"):
            dcls = (t.get("delta_class") or "flat").replace("bld2-km-delta", "").strip() or "flat"
            # The v2 helper uses classes like "up"/"down"/"flat" already.
            delta_html = f'<div class="srd-km-delta {dcls}">{html.escape(t["delta_str"])}</div>'
        # Convert v2's sparkline (which uses bld2 colors) to our gold-tinted one.
        spark_pts = t.get("sparkline_points") or []
        if not spark_pts and t.get("sparkline_svg"):
            spark_html_raw = t.get("sparkline_svg")
        elif spark_pts:
            spark_html_raw = _sparkline_svg(spark_pts, width=240, height=28, color="#E8C170")
        else:
            spark_html_raw = ""
        spark_html = (f'<div class="srd-km-spark">{spark_html_raw}</div>'
                      if spark_html_raw else "")
        tile_html.append(f"""
<div class="srd-km-tile">
  <div class="srd-km-label">{html.escape(t.get("label",""))}</div>
  <div class="srd-km-val-row">
    <span class="srd-km-val">{html.escape(t.get("value",""))}</span>
    {unit_html}
    {delta_html}
  </div>
  {spark_html}
</div>
""")
    while len(tile_html) < 4:
        tile_html.append('<div class="srd-km-tile"><div class="srd-km-label">—</div>'
                         '<div class="srd-km-val-row"><span class="srd-km-val">—</span></div></div>')
    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Key Metrics</div>
    <h2 class="srd-section-title">Biomechanical readout</h2>
  </div>
  <div class="srd-section-sub">vs MLB reference</div>
</div>

<div class="srd-km">
  {''.join(tile_html)}
</div>
"""


def _build_breakdown(record: Dict[str, Any]) -> str:
    rows = _flatten_metric_table(record)
    rows_sorted = sorted(
        [r for r in rows if r.get("sim_pct") is not None],
        key=lambda r: r.get("sim_pct", 0)
    )[:10]
    body = []
    for r in rows_sorted:
        sim = r.get("sim_pct") or 0
        if sim >= 75:   st_cls, icon = "ok",   "✓"
        elif sim >= 55: st_cls, icon = "warn", "—"
        else:           st_cls, icon = "bad",  "↓"
        body.append(
            f'<tr>'
            f'<td>{html.escape(str(r.get("label","")))}</td>'
            f'<td>{html.escape(str(r.get("player_str","—")))}</td>'
            f'<td>{html.escape(str(r.get("ref_str","—")))}</td>'
            f'<td><span class="srd-br-status {st_cls}">{icon}</span></td>'
            f'</tr>'
        )
    body_html = "".join(body) or (
        '<tr><td colspan="4" style="text-align:center;padding:1.5rem 0;'
        'color:var(--srd-bone-60);font-family:var(--srd-mono);font-size:11px;">'
        'No metric breakdown available.</td></tr>'
    )
    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Mechanical Breakdown</div>
    <h2 class="srd-section-title">Every measurement, ranked by gap</h2>
  </div>
  <div class="srd-section-sub">Biggest gaps first</div>
</div>

<div class="srd-card">
  <table class="srd-br-table">
    <thead>
      <tr><th>Metric</th><th>Your Swing</th><th>MLB Reference</th><th>Status</th></tr>
    </thead>
    <tbody>{body_html}</tbody>
  </table>
</div>
"""


def _build_progress(record: Dict[str, Any],
                    history: Optional[List[Dict[str, Any]]]) -> str:
    prog = swing_progress(record, history) or {}
    series = prog.get("score_history") or []
    pts = [float(s) for _, s in series] if series else []
    spark = _sparkline_svg(pts, width=520, height=110, color="#E8C170") if pts else \
        '<div style="color:var(--srd-bone-60);font-family:var(--srd-mono);font-size:11px;">No history yet</div>'

    pb_score = int(round(float(prog.get("pb_score") or record.get("score") or 0)))
    streak = int(prog.get("streak") or 0)
    total = int(prog.get("total_swings") or 1)
    days_since = prog.get("days_since_last")
    days_label = f"{int(days_since)} days" if isinstance(days_since, (int, float)) else "—"

    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Progress</div>
    <h2 class="srd-section-title">Where you're trending</h2>
  </div>
  <div class="srd-section-sub">{total} swings logged</div>
</div>

<div class="srd-prog-grid">
  <div class="srd-card">
    <div class="srd-card-eyebrow"><span class="dot"></span>Score Trajectory</div>
    <div class="srd-prog-spark">{spark}</div>
  </div>
  <div>
    <div class="srd-prog-stats">
      <div class="srd-prog-stat">
        <div class="srd-prog-stat-label">Personal Best</div>
        <div class="srd-prog-stat-val">{pb_score}</div>
        <div class="srd-prog-stat-sub">/ 100</div>
      </div>
      <div class="srd-prog-stat">
        <div class="srd-prog-stat-label">Streak</div>
        <div class="srd-prog-stat-val">{streak}</div>
        <div class="srd-prog-stat-sub">consecutive improvements</div>
      </div>
      <div class="srd-prog-stat">
        <div class="srd-prog-stat-label">Total Swings</div>
        <div class="srd-prog-stat-val">{total}</div>
        <div class="srd-prog-stat-sub">analyzed</div>
      </div>
      <div class="srd-prog-stat">
        <div class="srd-prog-stat-label">Since Last</div>
        <div class="srd-prog-stat-val">{days_label}</div>
        <div class="srd-prog-stat-sub">between sessions</div>
      </div>
    </div>
  </div>
</div>
"""


# =====================================================================
#                       COMPARE THIS SWING
# =====================================================================
# Side-by-side comparison of the current swing vs a selected prior.
# Only renders metric rows that exist in BOTH records — never invents
# values. Used by both the Streamlit live entry point (with an
# interactive selectbox) and the static HTML preview (default = most
# recent prior, no interactivity).
# =====================================================================

# Display label -> ordered list of label substrings to match against
# rows from `_flatten_metric_table()`. First substring that matches
# wins (per swing) so we always compare like-for-like.
_COMPARE_METRICS: List[Tuple[str, List[str]]] = [
    ("Hip Rotation",       ["Hip rotation at contact", "Hip rotation at foot plant"]),
    ("Hip-Shoulder Sep",   ["Peak hip-shoulder separation", "Separation at foot plant"]),
    ("Contact Timing",     ["Launch → contact", "Foot plant → launch"]),
    ("Swing Duration",     ["Total swing duration"]),
    ("Head Drift",         ["Total head drift", "Head drift Δy"]),
    ("Re-extension",       ["Re-extension"]),
]


def _ts_of(rec: Dict[str, Any]) -> str:
    """Best-effort timestamp string used for chronological sort."""
    return str(rec.get("timestamp") or rec.get("date") or rec.get("date_str") or "")


def _priors_of(record: Dict[str, Any],
               history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Return prior swings (strictly before current) sorted newest first.

    Excludes the current record by id-or-timestamp match. Filters out
    rows missing a usable score.
    """
    hist = list(history or [])
    cur_id = record.get("id")
    cur_ts = _ts_of(record)
    priors = []
    for r in hist:
        if not isinstance(r, dict):
            continue
        if cur_id and r.get("id") == cur_id:
            continue
        rts = _ts_of(r)
        if cur_ts and rts and rts >= cur_ts:
            continue
        try:
            float(r.get("score"))
        except (TypeError, ValueError):
            continue
        priors.append(r)
    priors.sort(key=_ts_of, reverse=True)
    return priors


def _radar_sim_pct(record: Dict[str, Any]) -> Optional[int]:
    """Same 5-axis biomech radar avg used in the hero MLB card."""
    rows = _flatten_metric_table(record)
    def _avg(needles):
        vals = []
        for n in needles:
            r = _find_metric_row(rows, n)
            if r is not None and r.get("sim_pct") is not None:
                vals.append(float(r["sim_pct"]))
        return (sum(vals) / len(vals)) if vals else None
    axes = [
        _avg(["Hip rotation at foot plant", "Hip rotation at contact"]),
        _avg(["Peak hip-shoulder separation", "Separation at foot plant"]),
        _avg(["Total swing duration", "Foot plant → launch", "Launch → contact"]),
        _avg(["Re-extension", "Most bent (load)"]),
        _avg(["Total head drift", "Head drift Δx", "Head drift Δy"]),
    ]
    real = [a for a in axes if a is not None]
    if not real:
        return None
    return int(round(sum(real) / len(real)))


def _find_first(rows: List[Dict[str, Any]],
                needles: List[str]) -> Optional[Dict[str, Any]]:
    for n in needles:
        r = _find_metric_row(rows, n)
        if r is not None:
            return r
    return None


def _delta_class(delta: Optional[float], higher_is_better: bool = True) -> str:
    """Pick a CSS modifier for a delta value."""
    if delta is None:
        return "flat"
    if abs(delta) < 1e-6:
        return "flat"
    if higher_is_better:
        return "up" if delta > 0 else "down"
    return "down" if delta > 0 else "up"


def _fmt_delta(delta: Optional[float], suffix: str = "") -> str:
    if delta is None:
        return "—"
    if abs(delta) < 1e-6:
        return "±0" + suffix
    sign = "+" if delta > 0 else ""
    if abs(delta) >= 10:
        return f"{sign}{delta:.0f}{suffix}"
    return f"{sign}{delta:.1f}{suffix}"


def _opt_label(rec: Dict[str, Any], idx_from_newest: int) -> str:
    """Build a one-line dropdown label for a prior swing."""
    n = rec.get("swing_number")
    swing_label = f"Swing #{int(n)}" if isinstance(n, (int, float)) else f"Swing {idx_from_newest+1} back"
    date = (rec.get("date_str") or rec.get("date")
            or (str(rec.get("timestamp") or "")[:10]) or "—")
    try:
        sc = int(round(float(rec.get("score"))))
    except (TypeError, ValueError):
        sc = "—"
    ref = (rec.get("reference") or {}).get("name") or rec.get("reference_name")
    pieces = [swing_label, str(date), f"{sc}/100"]
    if ref:
        pieces.append(f"vs {ref}")
    return " · ".join(pieces)


def _compare_rows(curr: Dict[str, Any],
                  prev: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the metric delta rows — score, MLB sim, then biomech rows
    that exist in BOTH swings. Each row: {label, prev, curr, delta_str,
    delta_class}.
    """
    out: List[Dict[str, Any]] = []

    # Score (always present)
    try:
        cs = float(curr.get("score")); ps = float(prev.get("score"))
        d = cs - ps
        out.append({
            "label": "Overall Score",
            "prev": f"{int(round(ps))}",
            "curr": f"{int(round(cs))}",
            "delta_str": _fmt_delta(d),
            "delta_class": _delta_class(d, higher_is_better=True),
        })
    except (TypeError, ValueError):
        pass

    # MLB similarity (radar avg)
    csim = _radar_sim_pct(curr); psim = _radar_sim_pct(prev)
    if csim is not None and psim is not None:
        d = csim - psim
        out.append({
            "label": "MLB Similarity",
            "prev": f"{psim}%",
            "curr": f"{csim}%",
            "delta_str": _fmt_delta(d, "%"),
            "delta_class": _delta_class(d, higher_is_better=True),
        })

    # Biomech rows that exist in BOTH
    crows = _flatten_metric_table(curr)
    prows = _flatten_metric_table(prev)
    for display, needles in _COMPARE_METRICS:
        cr = _find_first(crows, needles)
        pr = _find_first(prows, needles)
        if cr is None or pr is None:
            continue
        # Prefer sim_pct (higher is better, comparable scale).
        c_sim = cr.get("sim_pct"); p_sim = pr.get("sim_pct")
        if c_sim is not None and p_sim is not None:
            d = float(c_sim) - float(p_sim)
            out.append({
                "label": display,
                "prev": f"{int(round(float(p_sim)))}%",
                "curr": f"{int(round(float(c_sim)))}%",
                "delta_str": _fmt_delta(d, "%"),
                "delta_class": _delta_class(d, higher_is_better=True),
            })
        else:
            # Fall back to raw string values if both swings have them —
            # never invent a delta; show "—" if non-numeric.
            cstr = cr.get("player_str"); pstr = pr.get("player_str")
            if cstr and pstr:
                out.append({
                    "label": display,
                    "prev": str(pstr),
                    "curr": str(cstr),
                    "delta_str": "—",
                    "delta_class": "flat",
                })
    return out


def _compare_card_html(rec: Dict[str, Any], *, role: str) -> str:
    """Render one side of the compare pair (Previous Swing | This Swing)."""
    ref = _extract_ref_info(rec)
    initials = _initials(ref.get("name", ""))
    try:
        score = int(round(float(rec.get("score") or 0)))
    except (TypeError, ValueError):
        score = 0
    band = _band_class_srd(rec.get("score_band_color") or "", score)
    swing_n = rec.get("swing_number")
    swing_label = f"Swing #{int(swing_n)}" if isinstance(swing_n, (int, float)) \
        else ("This Swing" if role == "current" else "Previous Swing")
    date = (rec.get("date_str") or rec.get("date")
            or (str(rec.get("timestamp") or "")[:10]) or "—")
    role_eyebrow = "This Swing" if role == "current" else "Previous Swing"
    accent_dot = "var(--srd-red)" if role == "current" else "var(--srd-bone-60)"
    return f"""
<div class="srd-cmp-card">
  <div class="srd-cmp-role"><span class="dot" style="background:{accent_dot};"></span>{role_eyebrow}</div>
  <div class="srd-cmp-head">
    <div class="srd-cmp-avatar srd-cmp-avatar-{band}">{score}</div>
    <div>
      <div class="srd-cmp-swing">{html.escape(swing_label)}</div>
      <div class="srd-cmp-meta">{html.escape(str(date))}</div>
      <div class="srd-cmp-mlb">vs. {html.escape(ref.get('name') or 'Unknown')}</div>
    </div>
  </div>
</div>
"""


def _compare_table_html(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    body = []
    for r in rows:
        body.append(
            '<tr>'
            f'<td>{html.escape(r["label"])}</td>'
            f'<td class="num">{html.escape(r["prev"])}</td>'
            f'<td class="num">{html.escape(r["curr"])}</td>'
            f'<td class="num"><span class="srd-cmp-delta {r["delta_class"]}">{html.escape(r["delta_str"])}</span></td>'
            '</tr>'
        )
    return f"""
<table class="srd-cmp-table">
  <thead>
    <tr><th>Metric</th><th>Previous</th><th>This Swing</th><th>Δ</th></tr>
  </thead>
  <tbody>{''.join(body)}</tbody>
</table>
"""


def _num_from(s: Any) -> Optional[float]:
    """Pull the first signed/decimal number out of a string like
    '+6%', '-3', '0.18s', '72'. Returns None if there isn't one."""
    import re
    m = re.search(r"-?\d+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def _compare_summary_html(prev: Dict[str, Any],
                          rows: List[Dict[str, Any]]) -> str:
    """Dynamic, real-data executive summary shown above the compare cards.

    Built ONLY from the already-computed delta rows (never invents
    data). Covers: metrics improved vs declined, overall score change,
    MLB similarity change, largest improvement, and the largest
    remaining opportunity (lowest current similarity).
    """
    # "Key metrics" = every row that produced a real delta (drop the
    # rows we couldn't compare, marked with an em-dash).
    keyrows = [r for r in rows if r.get("delta_str") not in (None, "—")]
    if not keyrows:
        return ""

    improved = sum(1 for r in keyrows if r["delta_class"] == "up")
    declined = sum(1 for r in keyrows if r["delta_class"] == "down")
    total = len(keyrows)

    score_row = next((r for r in rows if r["label"] == "Overall Score"), None)
    mlb_row = next((r for r in rows if r["label"] == "MLB Similarity"), None)

    prev_n = prev.get("swing_number")
    prev_label = (f"Swing #{int(prev_n)}"
                  if isinstance(prev_n, (int, float)) else "your previous swing")

    sentences: List[str] = []

    # 1. Improved vs declined headline
    verb = "improved"
    lead = f"<strong>{improved} of {total}</strong> key metrics {verb} since {html.escape(prev_label)}"
    if declined:
        lead += f" ({declined} declined)"
    sentences.append(lead + ".")

    # 2. Score + MLB similarity movement
    movement_bits = []
    if score_row and _num_from(score_row["prev"]) is not None:
        sp, sc = score_row["prev"], score_row["curr"]
        dnum = (_num_from(sc) or 0) - (_num_from(sp) or 0)
        direction = ("increased" if dnum > 0 else
                     "decreased" if dnum < 0 else "held")
        movement_bits.append(
            f"Your overall score {direction} from <strong>{html.escape(sp)}</strong> "
            f"to <strong>{html.escape(sc)}</strong>"
        )
    if mlb_row and _num_from(mlb_row["prev"]) is not None:
        mp, mc = mlb_row["prev"], mlb_row["curr"]
        mdir = ("rose" if (_num_from(mc) or 0) > (_num_from(mp) or 0) else
                "slipped" if (_num_from(mc) or 0) < (_num_from(mp) or 0) else "held")
        movement_bits.append(
            f"MLB similarity {mdir} from <strong>{html.escape(mp)}</strong> "
            f"to <strong>{html.escape(mc)}</strong>"
        )
    if movement_bits:
        sentences.append(", and ".join(movement_bits) + ".")

    # 3. Largest improvement (biggest positive delta, excluding score)
    ups = [
        (r, abs(_num_from(r["delta_str"]) or 0))
        for r in keyrows
        if r["delta_class"] == "up" and r["label"] != "Overall Score"
    ]
    closing = []
    if ups:
        best = max(ups, key=lambda t: t[1])[0]
        closing.append(
            f"The biggest improvement was <strong>{html.escape(best['label'])}</strong> "
            f"({html.escape(best['delta_str'])})"
        )

    # 4. Largest remaining opportunity = lowest current %-valued metric
    pct_rows = [
        r for r in rows
        if r["label"] not in ("Overall Score",)
        and str(r["curr"]).strip().endswith("%")
        and _num_from(r["curr"]) is not None
    ]
    if pct_rows:
        weak = min(pct_rows, key=lambda r: _num_from(r["curr"]))
        # Only call it out if it isn't already the headline win.
        if not (closing and weak["label"] in closing[0]):
            phrase = (f"<strong>{html.escape(weak['label'])}</strong> "
                      f"remains the largest opportunity for improvement "
                      f"(now {html.escape(str(weak['curr']))})")
            closing.append(phrase)
    if closing:
        sentences.append(", while ".join(closing) + "."
                         if len(closing) == 2 else closing[0] + ".")

    summary_text = " ".join(sentences)
    trend_cls = "up" if improved >= declined else "down"
    return f"""
<div class="srd-card srd-cmp-summary">
  <div class="srd-card-eyebrow"><span class="dot"></span>Executive Summary</div>
  <div class="srd-cmp-summary-row">
    <div class="srd-cmp-summary-badge {trend_cls}">
      <span class="big">{improved}</span><span class="of">/ {total}</span>
      <span class="lbl">improved</span>
    </div>
    <div class="srd-cmp-summary-text">{summary_text}</div>
  </div>
</div>
"""


def _compare_section_html(record: Dict[str, Any],
                          history: Optional[List[Dict[str, Any]]],
                          *,
                          selected: Optional[Dict[str, Any]] = None,
                          selector_html: str = "") -> str:
    """Full Compare This Swing section.

    `selector_html` is optional — the Streamlit path leaves it empty and
    renders the selectbox via st.selectbox separately; the static HTML
    path injects a non-interactive label here so the preview shows what
    the selector looks like.

    `selected` lets the Streamlit path override the default prior (most
    recent) once the user picks a different one.
    """
    priors = _priors_of(record, history)

    if not priors:
        empty = """
<div class="srd-card srd-cmp-empty">
  <div class="srd-card-eyebrow"><span class="dot"></span>Comparison</div>
  <div class="srd-cmp-empty-msg">Comparison unlocks after your next saved swing.</div>
  <div class="srd-cmp-empty-sub">Once you upload a second swing, this section will show side-by-side deltas vs your previous best.</div>
</div>
"""
        return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Compare This Swing</div>
    <h2 class="srd-section-title">Side-by-side with a previous swing</h2>
  </div>
  <div class="srd-section-sub">Empty state</div>
</div>
{empty}
"""

    prev = selected if (selected in priors) else priors[0]
    rows = _compare_rows(record, prev)

    # Center delta badge — score change
    score_row = next((r for r in rows if r["label"] == "Overall Score"), None)
    if score_row:
        delta_class = score_row["delta_class"]
        delta_txt = score_row["delta_str"]
    else:
        delta_class, delta_txt = "flat", "—"

    prev_card = _compare_card_html(prev, role="previous")
    curr_card = _compare_card_html(record, role="current")
    table_html = _compare_table_html(rows)
    summary_html = _compare_summary_html(prev, rows)

    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Compare This Swing</div>
    <h2 class="srd-section-title">Side-by-side with a previous swing</h2>
  </div>
  <div class="srd-section-sub">{len(priors)} prior {'swings' if len(priors) != 1 else 'swing'} on file</div>
</div>

{selector_html}

{summary_html}

<div class="srd-cmp-pair">
  {prev_card}
  <div class="srd-cmp-delta-badge">
    <div class="srd-cmp-delta-label">Score Δ</div>
    <div class="srd-cmp-delta-val {delta_class}">{html.escape(delta_txt)}</div>
  </div>
  {curr_card}
</div>

<div class="srd-card srd-cmp-metrics-card">
  <div class="srd-card-eyebrow"><span class="dot"></span>Metric Deltas</div>
  {table_html}
  <div class="srd-cmp-footnote">Only metrics that exist in both swings are shown.</div>
</div>
"""


def _build_compare_static(record: Dict[str, Any],
                          history: Optional[List[Dict[str, Any]]]) -> str:
    """Static-preview wrapper — injects a non-interactive "Compare against"
    label that mimics the Streamlit selectbox so the screenshot is honest
    about what's there.
    """
    priors = _priors_of(record, history)
    if not priors:
        return _compare_section_html(record, history)
    label = _opt_label(priors[0], 0)
    selector_html = f"""
<div class="srd-cmp-selector">
  <div class="srd-cmp-selector-label">Compare against</div>
  <div class="srd-cmp-selector-display">
    <span>{html.escape(label)}</span>
    <span class="srd-cmp-selector-caret">▾</span>
  </div>
  <div class="srd-cmp-selector-hint">Switch to any prior swing in the live app</div>
</div>
"""
    return _compare_section_html(record, history, selected=priors[0],
                                  selector_html=selector_html)


def _build_next_session(record: Dict[str, Any]) -> str:
    fixes = top_three_fixes(record) or []
    drill_plan = record.get("drill_plan") or {}
    cats = drill_plan.get("categories", []) if isinstance(drill_plan, dict) else []

    items = []
    # Item 1 — Priority focus (label includes the specific priority name
    # when available; falls back to a generic phrase when the analyzer
    # didn't surface a top fix).
    if fixes:
        f0 = fixes[0]
        feel = (f0.get("fix_feel") or f0.get("headline") or "").strip()
        priority_title = (f0.get("title") or "").strip()
        label = f"Master {priority_title}" if priority_title else "Master the Priority Fix"
        items.append((
            label,
            html.escape(feel) if feel else
            f"Lock in the {priority_title or 'top priority'} mechanic in your next session."
        ))
    else:
        items.append((
            "Master the Priority Fix",
            "Run another swing analysis to surface your top mechanical priority.",
        ))
    # Item 2 — Top drill block
    if cats and (cats[0].get("drills") or []):
        d0 = cats[0]["drills"][0]
        sets, reps = d0.get("sets"), d0.get("reps")
        freq = d0.get("frequency") or d0.get("weekly")
        plan = " · ".join(filter(None, [
            f"{sets} sets" if sets else None,
            f"{reps} reps" if reps else None,
            str(freq) if freq else None,
        ]))
        items.append((
            "Run the top drill block",
            f"{html.escape(d0.get('title') or d0.get('name') or 'Drill')} — {html.escape(plan)}"
        ))
    # Item 3 — Re-measure
    items.append((
        "Re-film in 7 days",
        "Same angle, same setup. Compare side-by-side to confirm the priority gap is closing."
    ))

    list_html = "".join(
        f'<li class="srd-next-item">'
        f'<div class="srd-next-num">{i+1:02d}</div>'
        f'<div><div class="srd-next-title">{title}</div>'
        f'<div class="srd-next-sub">{sub}</div></div></li>'
        for i, (title, sub) in enumerate(items)
    )

    return f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Next Session</div>
    <h2 class="srd-section-title">Your training plan</h2>
  </div>
  <div class="srd-section-sub">3 actions before next swing</div>
</div>

<ul class="srd-next-list">{list_html}</ul>
"""


# =====================================================================
#                          PUBLIC ENTRY POINTS
# =====================================================================


def build_dashboard_preview_html(record: Dict[str, Any],
                                  history: Optional[List[Dict[str, Any]]] = None,
                                  *, is_sample: bool = False) -> str:
    """Return the full preview as a single HTML string (no Streamlit needed).

    New section order (spec "Report UX, Data Model & Must-Haves"):
      1. MLB Match reveal (hero, full-width)
      2. Reconciliation line
      3. Swing Score card (ring + pillar bars + what-you-did-well)
      4. Top fixes + drills
      5. Key metrics / Breakdown
      6. Kinetic-Chain (power sequence)
      7. Progress / Compare / Next Session

    Used by `scripts/visual_qa/render_swing_report_static.py` to produce a
    standalone preview file you can open in any browser.
    """
    power_html = _render_power_sequence(record)
    return (
        _DASHBOARD_CSS
        + '<div class="srd-wrap">'
        + _build_header(record, is_sample)
        # Two-system layout
        + _build_match_reveal(record)
        + _build_reconciliation()
        + _build_score_card(record, history)
        # Fixes & drills
        + _build_priorities_drills(record, history)
        # Kinetic-chain (sequencing tile — kept as-is)
        + power_html
        # Biomech detail
        + _build_key_metrics(record, history)
        + _build_breakdown(record)
        # Progress / compare / next
        + _build_progress(record, history)
        + _build_compare_static(record, history)
        + _build_next_session(record)
        + '</div>'
    )


def _render_compare_streamlit(record: Dict[str, Any],
                              history: Optional[List[Dict[str, Any]]]) -> None:
    """Live-app Compare section — header HTML + st.selectbox + result HTML.

    The selectbox uses a key derived from the record id so each report
    has its own selection state.
    """
    import streamlit as st  # local — stubbed by the static renderer

    priors = _priors_of(record, history)
    if not priors:
        st.html(_compare_section_html(record, history))  # st.html avoids leaks
        return

    # Header (eyebrow + title) — same as static path
    header_html = f"""
<div class="srd-section">
  <div>
    <div class="srd-eyebrow">Compare This Swing</div>
    <h2 class="srd-section-title">Side-by-side with a previous swing</h2>
  </div>
  <div class="srd-section-sub">{len(priors)} prior {'swings' if len(priors) != 1 else 'swing'} on file</div>
</div>
"""
    st.html(header_html)  # st.html (not markdown) — avoids blank-line HTML leaks

    # Selector — built from chronologically-newest-first priors.
    labels = [_opt_label(p, i) for i, p in enumerate(priors)]
    key = f"srd_cmp_pick__{record.get('id') or _ts_of(record) or 'rec'}"
    chosen_label = st.selectbox(
        "Compare against",
        options=labels,
        index=0,
        key=key,
    )
    selected = priors[labels.index(chosen_label)] if chosen_label in labels else priors[0]

    # Render the result without the static selector_html (the real
    # st.selectbox above replaces it). We just need the cards + table.
    rows = _compare_rows(record, selected)
    score_row = next((r for r in rows if r["label"] == "Overall Score"), None)
    if score_row:
        delta_class, delta_txt = score_row["delta_class"], score_row["delta_str"]
    else:
        delta_class, delta_txt = "flat", "—"
    body = f"""
{_compare_summary_html(selected, rows)}

<div class="srd-cmp-pair">
  {_compare_card_html(selected, role='previous')}
  <div class="srd-cmp-delta-badge">
    <div class="srd-cmp-delta-label">Score Δ</div>
    <div class="srd-cmp-delta-val {delta_class}">{html.escape(delta_txt)}</div>
  </div>
  {_compare_card_html(record, role='current')}
</div>
<div class="srd-card srd-cmp-metrics-card">
  <div class="srd-card-eyebrow"><span class="dot"></span>Metric Deltas</div>
  {_compare_table_html(rows)}
  <div class="srd-cmp-footnote">Only metrics that exist in both swings are shown.</div>
</div>
"""
    st.html(body)  # st.html (not markdown) — the blank line above would leak raw HTML


def render_swing_report_dashboard_preview(
    record: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]] = None,
    *,
    is_sample: bool = False,
    is_preview: bool = True,
) -> None:
    """Streamlit entry point.

    Renders everything EXCEPT the Compare section as a single st.markdown
    chunk, then renders Compare with a live selectbox, then renders the
    Next Session block + closing wrapper. This split lets the selectbox
    drive an interactive comparison without leaving the report.

    Args:
        record: current swing record (must contain `score`, `metric_table`,
            `narratives`, `reference`, etc.).
        history: full saved-swing history list (newest or oldest first
            — sorted internally). Used for sparkline, key-metric trend,
            and Compare section.
        is_sample: True only when a synthetic record is being rendered;
            tags the banner.
        is_preview: When True, a "PREVIEW ONLY" banner is shown at the top.
            Production callers should pass False.
    """
    import streamlit as st  # local — stubbed by the static renderer

    # Top sections — new two-system order + Progress
    power_html = _render_power_sequence(record)
    top_html = (
        _DASHBOARD_CSS
        + '<div class="srd-wrap">'
        + (_build_header(record, is_sample) if is_preview else _build_header_production(record))
        # Two-system layout: Match → reconcile → Score
        + _build_match_reveal(record)
        + _build_reconciliation()
        + _build_score_card(record, history)
        # Fixes & drills
        + _build_priorities_drills(record, history)
        # Kinetic-chain tile (kept)
        + power_html
        # Biomech detail
        + _build_key_metrics(record, history)
        + _build_breakdown(record)
        # Progress
        + _build_progress(record, history)
    )
    # Use st.html (NOT st.markdown) for the big assembled report HTML. The
    # report body contains blank lines between sections, which break Streamlit's
    # markdown HTML-block parser — making chunks of raw <div> markup leak onto
    # the page as literal text (the "report overlap / raw HTML" bug). st.html
    # renders raw HTML directly, with no markdown processing, so blank lines are
    # fine. (Same class of bug as the pricing page's CSS leak.)
    st.html(top_html)

    # Live Compare section (selectbox + cards)
    _render_compare_streamlit(record, history)

    # Footer — Next Session + closing wrapper
    tail_html = _build_next_session(record) + '</div>'
    st.html(tail_html)


def _build_header_production(record: Dict[str, Any]) -> str:
    """Same page header as `_build_header` but without the preview banner.

    Used when the renderer is called from the production Open Report flow.
    """
    swing = _swing_label(record)
    date = _fmt_date(record)
    ref = _extract_ref_info(record)
    return f"""
<div class="srd-pagehead">
  <div>
    <div class="srd-eyebrow">Premium Swing Report</div>
    <h1 class="srd-pagehead-title">{html.escape(swing)}</h1>
  </div>
  <div class="srd-pagehead-meta">
    Captured<strong>{html.escape(date)}</strong>
    <div style="margin-top:14px;">Comparison<strong>{html.escape(ref.get('name') or 'Unknown')}</strong></div>
  </div>
</div>
"""


# =====================================================================
#                            SAMPLE DATA
# =====================================================================
# Mirrors the field schema the v2 + v3 renderers read. Clearly labeled.
# =====================================================================

SAMPLE_RECORD: Dict[str, Any] = {
    "id": "preview-sample-001",
    "swing_number": 7,
    "timestamp": "2026-05-18T14:23:00",
    "date_str": "May 18, 2026",
    "score": 72,
    "score_band_color": "amber",
    "score_band_label": "Strong Foundation",
    "reference": {
        "name": "Ronald Acuña Jr.",
        "team": "Atlanta Braves",
        "position": "OF",
        "style": "Explosive rotational hitter with quick hips and a flat bat path.",
        "source": "auto",
    },
    "metric_table": {
        "Hip Mechanics": [
            {"label": "Hip rotation at foot plant", "player_str": "42°",
             "ref_str": "55°", "sim_pct": 76},
            {"label": "Hip rotation at contact", "player_str": "88°",
             "ref_str": "95°", "sim_pct": 92},
        ],
        "Separation": [
            {"label": "Peak hip-shoulder separation", "player_str": "34°",
             "ref_str": "40°", "sim_pct": 85},
            {"label": "Separation at foot plant", "player_str": "18°",
             "ref_str": "20°", "sim_pct": 90},
        ],
        "Timing": [
            {"label": "Total swing duration", "player_str": "0.18s",
             "ref_str": "0.16s", "sim_pct": 88},
            {"label": "Foot plant → launch", "player_str": "0.07s",
             "ref_str": "0.06s", "sim_pct": 85},
            {"label": "Launch → contact", "player_str": "0.11s",
             "ref_str": "0.10s", "sim_pct": 91},
        ],
        "Lower Body": [
            {"label": "Re-extension", "player_str": "12°",
             "ref_str": "15°", "sim_pct": 80},
            {"label": "Most bent (load)", "player_str": "28°",
             "ref_str": "32°", "sim_pct": 78},
        ],
        "Stability": [
            {"label": "Total head drift", "player_str": "2.1\"",
             "ref_str": "1.5\"", "sim_pct": 70},
            {"label": "Head drift Δx", "player_str": "1.2\"",
             "ref_str": "0.8\"", "sim_pct": 72},
            {"label": "Head drift Δy", "player_str": "1.5\"",
             "ref_str": "1.0\"", "sim_pct": 68},
        ],
    },
    "narratives": [
        {"rank": 1, "title": "Hip Separation",
         "paragraphs": [
             "Your hips clear about 80ms after your hands start — the chain is upside down.",
             "Why it costs you: Late hip rotation bleeds 4-6 mph of exit velocity and pulls the barrel out of the zone early.",
             "What the fix feels like: Hips lead torso by a beat — feel the back pocket turn before the shoulder fires.",
         ]},
        {"rank": 2, "title": "Head Stability",
         "paragraphs": [
             "Head drifts 2.1\" toward the ball during the swing.",
             "Why it costs you: Excess head drift breaks visual lock and drops contact quality measurably.",
             "What the fix feels like: Eyes locked on the contact zone — chin stays glued to the back shoulder.",
         ]},
        {"rank": 3, "title": "Lower Body Sequence",
         "paragraphs": [
             "Back leg re-extends 80ms early, pushing power up the chain before the hands are loaded.",
             "Why it costs you: You're spending stored elastic energy before contact — bat speed leaks out the back.",
             "What the fix feels like: Stay coiled into contact — finish the turn, then release.",
         ]},
    ],
    "gaps": [
        {"category": "Hip Separation", "category_label": "Hip Separation",
         "sub_metrics": [{"sim_pct": 45}, {"sim_pct": 52}]},
        {"category": "Head Stability", "category_label": "Head Stability",
         "sub_metrics": [{"sim_pct": 65}, {"sim_pct": 70}]},
        {"category": "Lower Body Sequence", "category_label": "Lower Body Sequence",
         "sub_metrics": [{"sim_pct": 75}, {"sim_pct": 80}]},
    ],
    "drill_plan": {
        "categories": [
            {"priority": "P1", "title": "Hip Separation",
             "why_it_matters": "Builds the elastic torque that drives bat speed.",
             "drills": [
                 {"title": "Wall Hip Turns", "name": "Wall Hip Turns",
                  "sets": 3, "reps": 10, "frequency": "3x/week",
                  "why": "Trains hip-led rotation without compensation.",
                  "how": "Place ball against the wall with bat. Rotate hips fully before shoulders begin moving."},
                 {"title": "Resistance Band Hip Pull", "name": "Resistance Band Hip Pull",
                  "sets": 3, "reps": 12, "frequency": "2x/week",
                  "why": "Reinforces lower-body lead with load.",
                  "how": "Loop band around hips, drive forward into rotation while shoulders stay closed."},
             ]},
            {"priority": "P2", "title": "Head Stability",
             "why_it_matters": "Improves contact consistency.",
             "drills": [
                 {"title": "Quiet Eyes Tee", "name": "Quiet Eyes Tee",
                  "sets": 4, "reps": 8, "frequency": "3x/week",
                  "why": "Reinforces visual tracking through contact.",
                  "how": "Hit off tee with focus on tracking ball deep into contact zone."},
             ]},
        ]
    },
    "score_history": [
        {"score": 64, "date": "2026-04-12"},
        {"score": 68, "date": "2026-04-20"},
        {"score": 69, "date": "2026-04-28"},
        {"score": 71, "date": "2026-05-05"},
        {"score": 70, "date": "2026-05-12"},
        {"score": 72, "date": "2026-05-18"},
    ],
    "strengths": [
        {"category_label": "Bat Path", "sim_pct": 92},
        {"category_label": "Stride Distance", "sim_pct": 89},
        {"category_label": "Shoulder Load", "sim_pct": 86},
    ],
}


def _sample_prior(swing_number: int, score: int, date_str: str,
                   timestamp: str, ref_name: str = "Ronald Acuña Jr.",
                   sim_offsets: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Build a synthetic prior swing record that exercises the compare flow.

    `sim_offsets` lets us shift per-category similarity vs the current
    swing so the metric-delta table has real numbers to surface.
    """
    so = sim_offsets or {}
    def s(base: int, key: str) -> int:
        return max(0, min(100, base + so.get(key, 0)))
    return {
        "id": f"sample-prior-{swing_number}",
        "swing_number": swing_number,
        "timestamp": timestamp,
        "date_str": date_str,
        "score": score,
        "score_band_color": ("amber" if score < 80 else "green") if score >= 60 else "red",
        "score_band_label": "Strong Foundation" if score >= 60 else "Building",
        "reference": {"name": ref_name, "team": "Atlanta Braves",
                       "position": "OF", "style": "", "source": "auto"},
        "metric_table": {
            "Hip Mechanics": [
                {"label": "Hip rotation at foot plant",
                 "player_str": "40°", "ref_str": "55°",
                 "sim_pct": s(76, "hip_fp")},
                {"label": "Hip rotation at contact",
                 "player_str": "86°", "ref_str": "95°",
                 "sim_pct": s(92, "hip_ct")},
            ],
            "Separation": [
                {"label": "Peak hip-shoulder separation",
                 "player_str": "32°", "ref_str": "40°",
                 "sim_pct": s(85, "sep_peak")},
                {"label": "Separation at foot plant",
                 "player_str": "17°", "ref_str": "20°",
                 "sim_pct": s(90, "sep_fp")},
            ],
            "Timing": [
                {"label": "Total swing duration",
                 "player_str": "0.19s", "ref_str": "0.16s",
                 "sim_pct": s(88, "dur")},
                {"label": "Launch → contact",
                 "player_str": "0.11s", "ref_str": "0.10s",
                 "sim_pct": s(91, "lc")},
            ],
            "Lower Body": [
                {"label": "Re-extension",
                 "player_str": "13°", "ref_str": "15°",
                 "sim_pct": s(80, "reext")},
            ],
            "Stability": [
                {"label": "Total head drift",
                 "player_str": "2.3\"", "ref_str": "1.5\"",
                 "sim_pct": s(70, "head")},
            ],
        },
    }


# Rich prior-swing list used by the static preview (and by tests). The
# live production renderer always receives REAL history from saved
# storage — never this list.
SAMPLE_HISTORY: List[Dict[str, Any]] = [
    _sample_prior(6, 70, "May 12, 2026", "2026-05-12T13:05:00",
                   sim_offsets={"hip_fp": -8, "sep_peak": -5, "head": -6,
                                "lc": -6, "dur": -4, "reext": -7, "hip_ct": -3}),
    _sample_prior(5, 71, "May 5, 2026", "2026-05-05T12:20:00",
                   sim_offsets={"hip_fp": -6, "sep_peak": -4, "head": -5,
                                "lc": -4, "dur": -3, "reext": -5, "hip_ct": -2}),
    _sample_prior(4, 69, "April 28, 2026", "2026-04-28T15:55:00",
                   sim_offsets={"hip_fp": -10, "sep_peak": -7, "head": -8,
                                "lc": -8, "dur": -6, "reext": -9, "hip_ct": -5}),
    _sample_prior(3, 68, "April 20, 2026", "2026-04-20T14:10:00",
                   sim_offsets={"hip_fp": -12, "sep_peak": -9, "head": -10,
                                "lc": -10, "dur": -8, "reext": -11, "hip_ct": -7}),
    _sample_prior(2, 64, "April 12, 2026", "2026-04-12T17:00:00",
                   sim_offsets={"hip_fp": -16, "sep_peak": -12, "head": -14,
                                "lc": -14, "dur": -11, "reext": -15, "hip_ct": -11}),
]
