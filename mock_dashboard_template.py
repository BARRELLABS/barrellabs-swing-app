"""
BarrelLabs — EDGE  (mock dashboard, design exploration · v2)
==============================================================

Standalone design mockup. Mock data only. Not wired to Supabase or any
production module. Does NOT modify the real dashboard.

Run:
    cd <repo root>
    .venv/bin/python -m streamlit run mock_dashboard_experimental.py \\
        --server.port 8502 --server.headless true

Then open http://localhost:8502.

Design direction (v2)
---------------------
"Edge — a precision instrument for hitters."  Editorial publication x
broadcast Statcast x Whoop-style emotional anchor metric. Single hero
EDGE SCORE (0-100) ties the page together. Adds baseball-native
visualizations (spray chart, contact zone, velocity ladder, weekly
heat map), cinematic silhouette + stroboscopic ghosts, animated phase
clock, session highlights reel, foil-treated achievements, and a Pro
upsell band. Coal background, bone typography, baseball-leather red,
champagne-gold PR accent. Display: Instrument Serif. UI: Geist. Numerals:
Geist Mono.
"""
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="BarrelLabs — Edge",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stSidebar"],
      [data-testid="stToolbar"], [data-testid="stDecoration"],
      footer { display: none !important; }
      [data-testid="stAppViewContainer"] > .main { padding: 0 !important; }
      .block-container { padding: 0 !important; max-width: 100% !important; }
      body, html, [data-testid="stAppViewContainer"] { background: #0A0B0E !important; }
      iframe { background: #0A0B0E !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BarrelLabs — Edge</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* =========================================================
   TOKENS + BASE
   ========================================================= */
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
  --gold:      #E8C170;
  --gold-deep: #C9A350;
  --gold-soft: rgba(232, 193, 112, 0.10);
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

*, *::before, *::after { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--bone);
  font-family: var(--sans);
  font-feature-settings: "ss01", "cv01";
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
body::before {
  content: ""; position: fixed; inset: 0;
  pointer-events: none; z-index: 1000;
  opacity: 0.035; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg viewBox='0 0 240 240' xmlns='http://www.w3.org/2000/svg'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.6 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}
.app { max-width: 1560px; margin: 0 auto; padding: 28px 40px 72px; position: relative; z-index: 1; }

/* =========================================================
   MASTHEAD + NAV PILLS
   ========================================================= */
.masthead {
  display: flex; align-items: center; justify-content: space-between;
  padding: 28px 0 22px;
  border-bottom: 1px solid var(--line);
  position: relative;
}
.masthead::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line-hi) 20%, var(--line-hi) 80%, transparent);
}
.brand { display: flex; align-items: baseline; gap: 14px; }
.brand-mark {
  width: 42px; height: 42px;
  display: block; flex-shrink: 0;
  object-fit: contain;
  image-rendering: -webkit-optimize-contrast;
  /* No background, no border, no shadow — the logo's own design carries
     itself. Floats directly on the page bg, aligned to the wordmark
     baseline rather than translated downward. */
  align-self: center;
}
.brand { gap: 16px; align-items: center; }
.brand .wordmark { transform: none; }
.wordmark {
  font-family: var(--sans); font-weight: 600; font-size: 14px;
  letter-spacing: 0.22em; text-transform: uppercase; color: var(--bone);
}
.wordmark .sep { color: var(--gray-2); margin: 0 10px; font-weight: 300; }
.wordmark .product {
  font-family: var(--serif); font-style: italic; font-weight: 400;
  font-size: 17px; letter-spacing: 0; text-transform: none; color: var(--bone);
}
/* In-iframe masthead HIDDEN at template level. The functional unified
   Edge masthead (brand + nav + user chip) is rendered by Python via
   bl_edge_chrome.render_edge_masthead() OUTSIDE the iframe so clicks
   trigger real Streamlit reruns and Supabase auth survives. Keeping
   the elements in the markup for now (rather than deleting them)
   preserves the editorial template as a self-contained mock that can
   be previewed standalone. */
.masthead { display: none !important; }
.nav { display: none !important; }
.nav a { display: none !important; }
.user-chip { display: flex; align-items: center; gap: 12px; }
.user-streak {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.05em; color: var(--gold);
  padding: 5px 10px; border: 1px solid rgba(232, 193, 112, 0.3);
  border-radius: 100px; background: var(--gold-soft);
}
.user-streak .dot {
  display: inline-block; width: 5px; height: 5px;
  background: var(--gold); border-radius: 50%; margin-right: 6px;
  animation: pulse 2.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50%      { opacity: 1;   transform: scale(1.2); }
}
.user-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #2a1f1f, #1a1414);
  border: 1px solid var(--line-hi); color: var(--bone);
  font-family: var(--serif); font-size: 14px; font-style: italic;
  display: grid; place-items: center;
}
.issue-line {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 0 30px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-2);
}
.issue-line .center { color: var(--bone-dim); }

/* =========================================================
   HERO — Edge Score anchor
   ========================================================= */
.hero {
  display: grid; grid-template-columns: 0.85fr 1.15fr 0.85fr; gap: 40px;
  padding: 28px 0 56px; border-bottom: 1px solid var(--line);
  align-items: center;
}
.edge-score-wrap { display: flex; flex-direction: column; align-items: center; }
.edge-score-svg { filter: drop-shadow(0 0 24px rgba(232,193,112,0.05)); }
.edge-score-label {
  margin-top: -12px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1);
}
.edge-score-cats {
  margin-top: 22px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.06em; color: var(--gray-1);
  text-transform: uppercase;
}
.esc-row { display: flex; justify-content: space-between; gap: 14px; }
.esc-row .v { color: var(--bone); font-weight: 500; }
.esc-row .v.peak { color: var(--gold); }

.hero-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--red); margin-bottom: 24px;
}
.hero-eyebrow .swatch { display: inline-block; width: 22px; height: 1px; background: var(--red); }
.hero-headline {
  font-family: var(--serif); font-weight: 400;
  font-size: 78px; line-height: 1.02; letter-spacing: -0.025em;
  color: var(--bone); margin: 0 0 24px;
}
/* Generous breathing room around the highlighted metric so the eye
   has space to land on it. Inline-block so the margins actually take. */
.hero-headline .ital {
  font-style: italic; color: var(--gold);
  display: inline-block;
  padding: 0 0.08em;
  margin: 0 0.06em;
}
.hero-headline .red {
  color: var(--red);
  display: inline-block;
  padding: 0 0.05em;
}
.hero-deck {
  font-family: var(--sans); font-weight: 300;
  font-size: 16px; line-height: 1.55; color: var(--bone-dim);
  max-width: 520px; margin: 0 0 28px;
}
.hero-meta {
  display: flex; gap: 28px; padding-top: 22px;
  border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.08em;
}
.hero-meta-block { display: flex; flex-direction: column; gap: 6px; }
.hero-meta-label { color: var(--gray-2); }
.hero-meta-value {
  color: var(--bone); font-family: var(--sans);
  font-size: 12.5px; text-transform: none; letter-spacing: 0; font-weight: 500;
}

/* doppel card (compact) */
.doppel {
  border: 1px solid var(--line); border-radius: var(--radius);
  padding: 22px 22px;
  background: radial-gradient(120% 80% at 100% 0%, rgba(230,69,48,0.06), transparent 60%), var(--bg-glass);
  position: relative; overflow: hidden;
}
.doppel-eyebrow {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1);
  display: flex; justify-content: space-between; margin-bottom: 14px;
}
.doppel-eyebrow .num { color: var(--gold); font-weight: 500; }
.doppel-name {
  font-family: var(--serif); font-style: italic;
  font-size: 36px; line-height: 1; letter-spacing: -0.02em;
  color: var(--bone); margin: 8px 0 4px;
}
.doppel-team {
  font-family: var(--mono); font-size: 10.5px; color: var(--gray-1);
  letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 18px;
}
.doppel-score {
  display: flex; align-items: baseline; gap: 12px;
  border-top: 1px solid var(--line); padding-top: 18px;
}
.doppel-score-num {
  font-family: var(--mono); font-size: 48px; font-weight: 400;
  color: var(--bone); font-feature-settings: "tnum";
  letter-spacing: -0.02em; line-height: 1;
}
.doppel-score-num .pct { font-size: 20px; color: var(--gray-1); margin-left: 2px; }
.doppel-score-label {
  font-family: var(--sans); font-size: 11.5px; line-height: 1.4;
  color: var(--bone-dim); max-width: 150px;
}
.doppel-cta {
  margin-top: 18px;
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--bone); text-decoration: none;
  padding-bottom: 2px; border-bottom: 1px solid var(--red);
}

/* =========================================================
   SECTION HEADERS
   ========================================================= */
.section-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 56px 0 24px;
}
.section-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--red);
}
.section-title {
  font-family: var(--serif); font-size: 28px; font-weight: 400;
  letter-spacing: -0.01em; color: var(--bone); margin: 6px 0 0;
}
.section-title .ital { font-style: italic; }
.section-sub {
  font-family: var(--sans); font-size: 12.5px; color: var(--gray-1);
  font-weight: 400; letter-spacing: 0;
}
.card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass); padding: 28px;
  position: relative; transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.card:hover { transform: translateY(-2px); border-color: var(--line-hi); box-shadow: 0 12px 40px rgba(0,0,0,0.4); }
.card.glass {
  background: radial-gradient(140% 100% at 0% 0%, rgba(230,69,48,0.05), transparent 60%), var(--bg-glass);
}
.card-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--red);
}
.card-title {
  font-family: var(--serif); font-size: 26px; font-weight: 400;
  letter-spacing: -0.01em; color: var(--bone); margin: 6px 0 0;
}
.card-title .ital { font-style: italic; }

/* =========================================================
   §03 COMP RADAR CARD (replaces the prior 5-cell scoreboard +
   horizontal ticker strip — see PASS 7 / persona-critique synthesis).
   One image, not six cards: your 5-axis biomechanical shape inside
   your matched MLB comp's reference shape. Five axes only — the
   "MLB match" axis was dropped because it is itself a composite of
   the other axes (Sports Science Director critique).
   ========================================================= */
.comp-radar-card {
  display: grid; grid-template-columns: 1fr 1.05fr; gap: 56px;
  align-items: center;
  padding: 56px 48px;
  margin: 8px 0 8px;
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  background:
    radial-gradient(60% 80% at 0% 50%, rgba(232,193,112,0.06), transparent 70%),
    linear-gradient(135deg, #14171d 0%, #0a0b0e 100%);
}
.comp-radar-vis { display: grid; place-items: center; }
.comp-radar-svg { width: 100%; max-width: 440px; height: auto; }
/* Keep the fixed-size rings inside their cards on phones (was overflowing /
   half off-screen). The viewBox handles the scaling. */
.edge-score-svg { max-width: 100%; }
.match-ring-wrap svg { width: 100%; max-width: 340px; height: auto; }
@media (max-width: 640px) { .match-ring-wrap svg { max-width: 240px; } }
.comp-radar-narrative { display: flex; flex-direction: column; gap: 18px; }
.comp-radar-line {
  font-family: var(--serif); font-size: 28px; line-height: 1.3;
  color: var(--bone); margin: 0; max-width: 460px; font-weight: 400;
}
.comp-radar-line .em { font-style: italic; color: var(--gold); }
.comp-radar-deltas {
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.16em;
  text-transform: uppercase; color: var(--bone-dim); margin: 0;
}
.comp-radar-legend {
  display: flex; gap: 18px; font-family: var(--mono);
  font-size: 9.5px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gray-1);
}
.comp-radar-legend .row { display: flex; align-items: center; gap: 8px; }
.comp-radar-legend .swatch.you  { width: 12px; height: 2px; background: var(--bone); border-radius: 1px; }
.comp-radar-legend .swatch.comp { width: 12px; height: 0; border-top: 1px dashed var(--red); }
.comp-radar-cta {
  display: inline-flex; align-items: center; gap: 6px;
  align-self: flex-start;
  padding: 12px 18px;
  border: 1px solid var(--gold); border-radius: 100px;
  background: var(--gold-soft);
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gold); text-decoration: none;
  transition: background 0.2s, color 0.2s;
  margin-top: 4px;
}
.comp-radar-cta:hover { background: var(--gold); color: var(--bg); }

/* =========================================================
   HIGHLIGHTS REEL
   ========================================================= */
.reel { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.clip {
  position: relative; border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; aspect-ratio: 16 / 10;
  background: linear-gradient(160deg, #14171d 0%, #0a0b0e 100%);
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  cursor: pointer;
}
.clip:hover { transform: translateY(-3px); border-color: var(--line-hi); box-shadow: 0 18px 60px rgba(0,0,0,0.5); }
.clip-bg { position: absolute; inset: 0; opacity: 0.95; }
.clip-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 30%, rgba(0,0,0,0.85) 100%);
}
.clip-play {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 56px; height: 56px; border-radius: 50%;
  background: rgba(244,239,230,0.10); border: 1px solid var(--line-hi);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: grid; place-items: center;
  transition: background 0.2s, border-color 0.2s, transform 0.25s;
}
.clip:hover .clip-play { background: var(--bone); border-color: var(--bone); transform: translate(-50%, -50%) scale(1.05); }
.clip:hover .clip-play svg { fill: var(--bg); }
.clip-play svg { width: 18px; height: 18px; fill: var(--bone); transition: fill 0.2s; margin-left: 3px; }
.clip-meta {
  position: absolute; left: 20px; right: 20px; bottom: 18px;
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 12px;
}
.clip-meta .info { display: flex; flex-direction: column; gap: 6px; min-width: 0; flex: 1; }
.clip-meta .when {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-1);
}
.clip-meta .what {
  font-family: var(--serif); font-style: italic;
  font-size: 22px; line-height: 1.05; color: var(--bone);
}
.clip-meta .grade {
  font-family: var(--serif); font-style: italic;
  font-size: 30px; color: var(--gold); line-height: 1;
}
.clip-corner {
  position: absolute; top: 14px; left: 14px;
  font-family: var(--mono); font-size: 9.5px;
  color: var(--gray-1); letter-spacing: 0.14em; text-transform: uppercase;
  display: flex; gap: 12px; align-items: center;
}
.clip-corner .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--red); }
.clip-tc {
  position: absolute; top: 14px; right: 14px;
  font-family: var(--mono); font-size: 10px;
  color: var(--bone); background: rgba(0,0,0,0.5);
  padding: 3px 8px; border-radius: 3px; letter-spacing: 0.08em;
}

/* =========================================================
   TWO-COL: Swing of Week (with silhouette) + DNA radar
   ========================================================= */
.two-col { display: grid; grid-template-columns: 1.5fr 1fr; gap: 28px; margin-top: 8px; }
.sow-grade {
  position: absolute; top: 28px; right: 28px;
  display: flex; flex-direction: column; align-items: flex-end;
}
.sow-grade .num {
  font-family: var(--serif); font-size: 64px; line-height: 0.9;
  letter-spacing: -0.04em; color: var(--gold); font-style: italic;
}
.sow-grade .lbl {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 2px;
}
.sow-stage {
  margin: 24px 0 8px; height: 300px;
  position: relative; display: grid; place-items: center;
  background: radial-gradient(60% 70% at 50% 65%, rgba(230,69,48,0.10), transparent 70%);
  border-radius: var(--radius-sm);
}
.sow-phases {
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin-top: 28px; border-top: 1px solid var(--line); padding-top: 22px;
}
.phase {
  display: flex; flex-direction: column; gap: 8px; text-align: center;
  border-right: 1px solid var(--line-lo); padding: 0 6px;
  min-width: 0;   /* allow text to shrink instead of overflow the cell */
}
.phase:last-child { border-right: none; }
.phase .ms {
  font-family: var(--mono); font-feature-settings: "tnum";
  font-size: 13px; font-weight: 500; color: var(--bone);
  white-space: nowrap;
}
.phase .ms .sign { color: var(--gray-1); margin-right: 1px; }
.phase .name {
  font-family: var(--mono); font-size: 9px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-1);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.phase .vs {
  font-family: var(--mono); font-size: 9.5px; color: var(--gray-2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.phase.peak .ms { color: var(--gold); }

/* Below 900px the 6-col ribbon needs to wrap to 3 cols × 2 rows so the
   labels never overlap or get clipped. */
@media (max-width: 900px) {
  .sow-phases { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px 8px; }
  .phase:nth-child(3) { border-right: none; }
}
.sow-callouts {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 16px; margin-top: 24px;
}
.callout {
  padding: 16px 18px; border: 1px solid var(--line);
  border-radius: var(--radius-sm); display: flex; gap: 14px;
}
.callout .icon {
  width: 28px; height: 28px; border-radius: 50%;
  display: grid; place-items: center;
  font-family: var(--serif); font-style: italic; font-size: 16px; flex-shrink: 0;
}
.callout.good .icon { background: rgba(74, 227, 140, 0.12); color: var(--green); }
.callout.focus .icon { background: var(--red-soft); color: var(--red); }
.callout .title {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 4px;
}
.callout .body {
  font-family: var(--sans); font-size: 13px; line-height: 1.45; color: var(--bone-dim);
}

/* Swing DNA radar */
.dna { display: flex; flex-direction: column; }
.dna .radar { margin: 16px auto 0; }
.dna-legend {
  display: flex; gap: 18px; justify-content: center; margin-top: 14px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.dna-legend .row { display: flex; align-items: center; gap: 8px; color: var(--gray-1); }
.dna-legend .row .swatch { width: 12px; height: 2px; border-radius: 1px; }
.dna-legend .you .swatch  { background: var(--bone); }
.dna-legend .mlb .swatch  { border-top: 1px dashed var(--red); height: 0; }
.dna-legend .peak .swatch { border-top: 1px dashed var(--gold); height: 0; }

/* =========================================================
   CONTACT ZONE + SPRAY CHART
   ========================================================= */
.diamond-row { display: grid; grid-template-columns: 1fr 1.4fr; gap: 28px; margin-top: 8px; }
.zone-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(3, 1fr);
  gap: 6px; max-width: 320px; aspect-ratio: 1; margin: 24px auto 16px;
}
.zone-cell {
  display: grid; place-items: center;
  border: 1px solid var(--line);
  background: var(--bg-glass);
  border-radius: var(--radius-xs);
  transition: transform 0.2s, border-color 0.2s;
  position: relative;
}
.zone-cell:hover { transform: scale(1.03); border-color: var(--line-hi); }
.zone-cell .pct {
  font-family: var(--mono); font-feature-settings: "tnum";
  font-weight: 500; font-size: 22px; color: var(--bone);
}
.zone-cell .n {
  position: absolute; top: 4px; left: 6px;
  font-family: var(--mono); font-size: 9px;
  color: var(--gray-2); letter-spacing: 0.06em;
}
.zone-cell.heat-3 { background: rgba(230,69,48,0.32); border-color: rgba(230,69,48,0.5); }
.zone-cell.heat-2 { background: rgba(230,69,48,0.18); border-color: rgba(230,69,48,0.32); }
.zone-cell.heat-1 { background: rgba(230,69,48,0.08); border-color: rgba(230,69,48,0.18); }
.zone-cell.heat-0 { background: var(--bg-glass); }
.zone-axes {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-2);
  display: flex; justify-content: space-between;
  max-width: 320px; margin: 0 auto;
}

.spray { position: relative; padding: 18px 8px; }
.spray svg { display: block; margin: 0 auto; width: 100%; max-width: 540px; height: auto; }
.spray-legend {
  display: flex; gap: 22px; justify-content: center; margin-top: 12px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.spray-legend .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 6px; vertical-align: middle; }

/* =========================================================
   TREND
   ========================================================= */
.trend { padding: 28px 28px 8px; }
.trend-head { display: flex; justify-content: space-between; align-items: flex-end; }
.trend-metrics {
  display: flex; gap: 22px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-1);
}
.trend-metrics .tag { display: flex; align-items: center; gap: 8px; }
.trend-metrics .tag .swatch { width: 10px; height: 10px; border-radius: 2px; }
.trend-chart { margin-top: 24px; }
.trend-annot-bar {
  margin-top: 8px; padding-top: 14px; border-top: 1px solid var(--line);
  display: flex; justify-content: space-between; gap: 32px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-2);
}
.annot { display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; }
.annot .when { color: var(--gray-1); }
.annot .what {
  font-family: var(--sans); font-size: 12px; letter-spacing: 0;
  text-transform: none; color: var(--bone-dim);
}
.annot .what .pr {
  color: var(--gold); font-family: var(--mono);
  font-size: 10.5px; margin-right: 4px; letter-spacing: 0.08em;
}

/* =========================================================
   VELOCITY LADDER
   ========================================================= */
.ladder-card { padding: 28px; }
.ladder {
  display: grid; grid-template-columns: 1fr 1fr; gap: 36px;
  align-items: center;
}
.ladder-vis {
  position: relative; height: 280px;
  display: grid; grid-template-columns: repeat(8, 1fr); gap: 14px; align-items: end;
  padding: 0 12px;
}
.bar {
  background: linear-gradient(180deg, var(--bone) 0%, rgba(244,239,230,0.4) 100%);
  border-radius: 4px 4px 0 0; position: relative;
  transition: filter 0.2s;
}
.bar.peak {
  background: linear-gradient(180deg, var(--gold) 0%, var(--gold-deep) 100%);
  box-shadow: 0 -8px 24px rgba(232,193,112,0.32);
}
.bar:hover { filter: brightness(1.1); }
.bar .v {
  position: absolute; top: -22px; left: 50%; transform: translateX(-50%);
  font-family: var(--mono); font-feature-settings: "tnum";
  font-size: 11px; color: var(--bone-dim);
}
.bar.peak .v { color: var(--gold); font-weight: 500; font-size: 12px; }
.bar .wk {
  position: absolute; bottom: -22px; left: 50%; transform: translateX(-50%);
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-2);
}
.ladder-narrative .num {
  font-family: var(--serif); font-size: 96px;
  line-height: 1; letter-spacing: -0.04em; color: var(--bone);
}
.ladder-narrative .num .ital { font-style: italic; color: var(--gold); }
.ladder-narrative .label {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 8px;
}
.ladder-narrative .body {
  margin-top: 18px; font-family: var(--sans);
  font-size: 14.5px; line-height: 1.6; color: var(--bone-dim); max-width: 380px;
}
.ladder-narrative .body .em { color: var(--bone); }

/* =========================================================
   PHASE CLOCK SIGNATURE
   ========================================================= */
.signature {
  margin-top: 56px; display: grid;
  grid-template-columns: 1.1fr 1fr; gap: 56px;
  padding: 64px 48px;   /* horizontal padding so stats don't kiss the card edge */
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  background:
    radial-gradient(60% 50% at 50% 100%, rgba(230,69,48,0.06), transparent 70%),
    linear-gradient(135deg, #14171d 0%, #0a0b0e 100%);
}
.sig-meta { display: flex; flex-direction: column; justify-content: center; }
.sig-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--red);
}
.sig-title {
  font-family: var(--serif); font-size: 54px; line-height: 1;
  letter-spacing: -0.02em; color: var(--bone); margin: 16px 0;
}
.sig-title .ital { font-style: italic; color: var(--gold); }
.sig-body {
  font-family: var(--sans); font-size: 15px; line-height: 1.6;
  color: var(--bone-dim); max-width: 460px; margin: 12px 0 32px;
}
.sig-stats {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px 32px;
  padding-top: 28px; border-top: 1px solid var(--line); max-width: 460px;
}
.sig-stat .v {
  font-family: var(--mono); font-size: 28px; font-weight: 500;
  color: var(--bone); letter-spacing: -0.02em;
}
.sig-stat .l {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 4px;
}
.clock-wrap { display: grid; place-items: center; padding: 0 12px; }
.clock-hand-you { transform-origin: 0 0; animation: sweepYou 1.6s cubic-bezier(.34,1.1,.34,1) 0.4s both; }
.clock-hand-mlb { transform-origin: 0 0; animation: sweepMlb 1.6s cubic-bezier(.34,1.1,.34,1) 0.55s both; }
@keyframes sweepYou { from { transform: rotate(-90deg); } to { transform: rotate(180deg); } }
@keyframes sweepMlb { from { transform: rotate(-90deg); } to { transform: rotate(186deg); } }

/* =========================================================
   LEADERBOARD
   ========================================================= */
.leaderboard { margin-top: 8px; }
.lb-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
.lb-card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass); padding: 22px 20px;
  position: relative; transition: transform 0.25s ease, border-color 0.25s ease;
}
.lb-card:hover { transform: translateY(-3px); border-color: var(--line-hi); }
.lb-card .rank {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.16em; color: var(--gray-2); text-transform: uppercase;
}
.lb-card .name {
  font-family: var(--serif); font-style: italic;
  font-size: 22px; line-height: 1.05; letter-spacing: -0.01em;
  color: var(--bone); margin: 8px 0 4px;
}
.lb-card .team {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--gray-1);
}
.lb-card .sim {
  margin-top: 18px; display: flex; align-items: baseline; gap: 4px;
  font-family: var(--mono); font-size: 28px; font-weight: 500;
  color: var(--bone); font-feature-settings: "tnum"; letter-spacing: -0.02em;
}
.lb-card .sim .pct { color: var(--gray-1); font-size: 13px; }
.lb-card .sim-bar {
  margin-top: 8px; height: 2px; border-radius: 1px;
  background: var(--gray-3); overflow: hidden;
}
.lb-card .sim-bar-fill { height: 100%; background: var(--bone); }
.lb-card.top .sim-bar-fill { background: var(--gold); }
.lb-card.top .sim { color: var(--gold); }
.lb-card.top { border-color: rgba(232, 193, 112, 0.4); }
.lb-card .why {
  margin-top: 12px; font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-1); line-height: 1.5;
}

/* =========================================================
   WEEKLY HEATMAP CALENDAR
   ========================================================= */
.heat-card { padding: 28px; }
.heat-grid {
  margin-top: 22px;
  display: grid; grid-template-columns: 32px repeat(12, 1fr); gap: 4px;
}
.heat-day {
  font-family: var(--mono); font-size: 9px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--gray-2); display: grid; place-items: center;
}
.heat-cell {
  aspect-ratio: 1;
  border-radius: 3px;
  transition: transform 0.15s;
}
.heat-cell:hover { transform: scale(1.18); outline: 1px solid var(--bone); }
.heat-0 { background: rgba(244,239,230,0.04); }
.heat-1 { background: rgba(230,69,48,0.18); }
.heat-2 { background: rgba(230,69,48,0.36); }
.heat-3 { background: rgba(230,69,48,0.56); }
.heat-4 { background: rgba(230,69,48,0.78); }
.heat-pr { background: var(--gold); }
.heat-legend {
  margin-top: 18px;
  display: flex; justify-content: space-between; align-items: center;
}
.heat-legend .scale {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.heat-legend .scale .swatches { display: flex; gap: 3px; }
.heat-legend .scale .sw { width: 14px; height: 14px; border-radius: 3px; }
.heat-stats {
  display: flex; gap: 28px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.heat-stats .v { color: var(--bone); font-weight: 500; }

/* =========================================================
   LEDGER + COACH
   ========================================================= */
.lower { display: grid; grid-template-columns: 1.3fr 1fr; gap: 28px; margin-top: 8px; }
.ledger-row {
  display: grid; grid-template-columns: 110px 70px 1fr 70px 50px;
  align-items: center; padding: 16px 0; border-bottom: 1px solid var(--line-lo);
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em;
}
.ledger-row:last-child { border-bottom: none; }
.ledger-row .date { color: var(--gray-1); text-transform: uppercase; }
.ledger-row .swings { color: var(--bone); font-feature-settings: "tnum"; }
.ledger-row .top-metric {
  font-family: var(--sans); font-size: 13px;
  color: var(--bone-dim); letter-spacing: 0; text-transform: none;
}
.ledger-row .top-metric .v {
  color: var(--bone); font-family: var(--mono); font-feature-settings: "tnum";
}
.ledger-row .grade {
  font-family: var(--serif); font-style: italic; font-size: 22px;
  color: var(--bone); text-align: right; padding-right: 12px;
}
.ledger-row.pr .grade { color: var(--gold); }
.ledger-row .mood { font-size: 18px; text-align: right; }

.coach-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px; margin-top: 8px;
}
.coach-card {
  position: relative; padding: 30px 30px 26px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
  display: flex; flex-direction: column;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.coach-card:hover { transform: translateY(-3px); border-color: var(--line-hi); box-shadow: 0 12px 36px rgba(0,0,0,0.4); }
.coach-card .num {
  position: absolute; top: 22px; right: 26px;
  font-family: var(--serif); font-style: italic;
  font-size: 32px; line-height: 1; letter-spacing: -0.02em;
  color: var(--gold); opacity: 0.85;
}
.coach-card .why {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--red); margin-bottom: 10px;
}
.coach-card .drill {
  font-family: var(--serif); font-size: 26px;
  line-height: 1.05; letter-spacing: -0.015em;
  color: var(--bone); margin-bottom: 10px;
}
.coach-card .drill .ital { font-style: italic; }
.coach-card .body {
  font-family: var(--sans); font-size: 13.5px;
  line-height: 1.6; color: var(--bone-dim);
  flex: 1; margin: 0 0 22px;
}
.coach-card .target {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 14px;
  padding: 10px 12px; border: 1px dashed var(--line-hi);
  border-radius: var(--radius-sm);
}
.coach-card .target .v { color: var(--gold); }
.coach-card .cta-row {
  display: flex; justify-content: space-between; align-items: center;
}
.coach-card .cta {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--bone); text-decoration: none;
  padding-bottom: 2px; border-bottom: 1px solid var(--red);
}
.coach-card .reps {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-2);
}

/* =========================================================
   12 WEEKS OF PROGRESS · long-term retention story
   ========================================================= */
.progress-12 { margin-top: 8px; }
.progress-stats {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 0;
  border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; background: var(--bg-glass);
}
.progress-stat {
  padding: 28px 24px 24px;
  border-right: 1px solid var(--line);
  transition: background 0.2s;
  position: relative;
  min-width: 0;   /* prevent overflow when numbers are wide */
}
.progress-stat:last-child { border-right: none; }
.progress-stat:hover { background: var(--bg-glass-hi); }
.progress-stat .lbl {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--gray-1);
}
.progress-stat .num {
  font-family: var(--serif); font-style: italic;
  font-size: 50px; line-height: 1; letter-spacing: -0.03em;
  color: var(--bone); margin: 12px 0 6px;
}
.progress-stat .num .gold { color: var(--gold); }
.progress-stat .num .small {
  font-family: var(--mono); font-style: normal;
  font-size: 18px; color: var(--gray-1); margin-left: 4px;
  letter-spacing: -0.01em;
}
.progress-stat .sub {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-2);
}
.progress-stat .delta-up { color: var(--gold); }

.progress-trend-card {
  margin-top: 20px; padding: 28px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass);
}
.progress-trend-head {
  display: flex; justify-content: space-between; align-items: flex-end;
  margin-bottom: 20px;
}
.progress-trend-tag {
  display: flex; gap: 22px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-1);
}
.progress-trend-tag .row { display: flex; align-items: center; gap: 8px; }
.progress-trend-tag .row .sw { width: 10px; height: 10px; border-radius: 2px; }

.milestones-row {
  margin-top: 20px;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}
.milestone {
  padding: 22px 22px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background:
    radial-gradient(80% 80% at 100% 0%, rgba(232,193,112,0.10), transparent 60%),
    var(--bg-glass);
  display: flex; gap: 16px; align-items: flex-start;
  position: relative; overflow: hidden;
  transition: transform 0.25s ease, border-color 0.25s ease;
}
.milestone:hover { transform: translateY(-2px); border-color: var(--line-hi); }
.milestone::after {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(232,193,112,0.4), transparent);
}
.milestone .ico {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--bg);
  border: 1px solid rgba(232,193,112,0.45);
  display: grid; place-items: center;
  font-family: var(--serif); font-style: italic; font-size: 18px;
  color: var(--gold); flex-shrink: 0;
}
.milestone .info { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.milestone .name {
  font-family: var(--serif); font-size: 19px;
  letter-spacing: -0.01em; color: var(--bone); line-height: 1.15;
}
.milestone .when {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.milestone .detail {
  font-family: var(--sans); font-size: 12px;
  color: var(--bone-dim); line-height: 1.4;
}

.coach-item { padding: 18px 0; border-bottom: 1px solid var(--line-lo); }
.coach-item:last-child { border-bottom: none; padding-bottom: 0; }
.coach-item .why {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--red); margin-bottom: 8px;
}
.coach-item .drill {
  font-family: var(--serif); font-size: 20px;
  letter-spacing: -0.01em; color: var(--bone); margin-bottom: 6px;
}
.coach-item .body {
  font-family: var(--sans); font-size: 13px;
  line-height: 1.55; color: var(--bone-dim);
}
.coach-item .cta {
  margin-top: 10px; display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--bone); text-decoration: none;
  padding-bottom: 2px; border-bottom: 1px solid var(--red);
}

/* =========================================================
   ACHIEVEMENTS RAIL (with foil treatment)
   ========================================================= */
.rail { margin-top: 8px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.medal {
  padding: 24px; border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--bg-glass); position: relative; overflow: hidden;
  transition: transform 0.25s ease, border-color 0.25s ease;
}
.medal:hover { transform: translateY(-3px); border-color: var(--line-hi); }
.medal::after {
  content: ""; position: absolute; inset: -1px; border-radius: var(--radius);
  background: radial-gradient(60% 60% at 100% 0%, rgba(230,69,48,0.10), transparent 70%);
  pointer-events: none;
}
.medal.gold {
  border-color: rgba(232,193,112,0.32);
  background:
    radial-gradient(80% 100% at 100% 0%, rgba(232,193,112,0.10), transparent 60%),
    linear-gradient(135deg, rgba(232,193,112,0.05) 0%, rgba(10,11,14,0.5) 60%),
    var(--bg-elev);
}
.medal.gold::before {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(115deg, transparent 35%, rgba(232,193,112,0.18) 50%, transparent 65%);
  opacity: 0.7; pointer-events: none;
}
.medal .icon {
  width: 44px; height: 44px; border-radius: 50%;
  display: grid; place-items: center;
  background: var(--bg); border: 1px solid var(--line-hi);
  font-family: var(--serif); font-style: italic; font-size: 20px;
  color: var(--gold); margin-bottom: 18px;
  position: relative; z-index: 1;
}
.medal.gold .icon { border-color: var(--gold); color: var(--gold); }
.medal .name {
  font-family: var(--serif); font-size: 19px;
  letter-spacing: -0.01em; color: var(--bone);
  margin-bottom: 4px; position: relative; z-index: 1;
}
.medal .when {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gray-1); position: relative; z-index: 1;
}
.medal.progress .bar {
  margin-top: 12px; height: 3px; background: var(--gray-3);
  border-radius: 2px; overflow: hidden; position: relative; z-index: 1;
}
.medal.progress .bar .fill { height: 100%; background: var(--bone); }
.medal.progress.gold .bar .fill { background: var(--gold); }
.medal.progress .pct {
  margin-top: 8px; font-family: var(--mono); font-size: 10px;
  color: var(--bone-dim); letter-spacing: 0.08em;
}
.medal.locked { opacity: 0.55; }
.medal.locked .icon { color: var(--gray-2); border-color: var(--gray-3); }

/* =========================================================
   PRO UPSELL BAND
   ========================================================= */
/* =========================================================
   PRICING BAND · 3-tier (Solo / Family / Coach Pro)
   ========================================================= */
.pricing-band {
  margin-top: 56px; padding: 52px 48px;
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  background:
    radial-gradient(80% 100% at 100% 100%, rgba(230,69,48,0.10), transparent 60%),
    radial-gradient(60% 80% at 0% 0%, rgba(232,193,112,0.06), transparent 60%),
    linear-gradient(135deg, #14171d 0%, #0a0b0e 100%);
  position: relative; overflow: hidden;
}
.pricing-band::after {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}
.pricing-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 36px; position: relative; z-index: 1;
}
.pricing-head-meta { max-width: 560px; }
.pricing-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--gold);
}
.pricing-title {
  font-family: var(--serif); font-size: 46px; font-weight: 400;
  line-height: 1; letter-spacing: -0.02em; color: var(--bone); margin: 12px 0 14px;
}
.pricing-title .ital { font-style: italic; color: var(--gold); }
.pricing-sub {
  font-family: var(--sans); font-size: 14px; line-height: 1.55; color: var(--bone-dim);
}

/* Free-tier top strip */
.free-strip {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 22px; margin-bottom: 28px;
  border: 1px solid rgba(232,193,112,0.28); border-radius: 100px;
  background:
    radial-gradient(50% 200% at 50% 50%, rgba(232,193,112,0.06), transparent 70%),
    var(--bg-glass);
  position: relative; z-index: 1;
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--bone-dim);
}
.free-strip .lead { display: inline-flex; align-items: center; gap: 12px; }
.free-strip .lead .badge {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.18em; color: var(--gold);
  padding: 3px 9px; border-radius: 100px;
  background: rgba(232,193,112,0.10); border: 1px solid rgba(232,193,112,0.36);
}
.free-strip .lead .v { color: var(--bone); font-weight: 500; }
.free-strip .trail { color: var(--gray-1); }

/* Billing toggle (pure-CSS, no JS) */
.bill-radio { display: none; }
.tier-toggle {
  display: inline-flex; align-items: center; gap: 4px; padding: 4px;
  border: 1px solid var(--line); border-radius: 100px;
  background: var(--bg-glass);
  position: relative; z-index: 1;
}
.tier-toggle label {
  font-family: var(--mono); font-size: 11px; font-weight: 500;
  letter-spacing: 0.10em; text-transform: uppercase;
  color: var(--gray-1); padding: 8px 16px; border-radius: 100px;
  cursor: pointer; transition: color 0.2s, background 0.2s;
  display: inline-flex; align-items: center; gap: 8px;
}
.tier-toggle label:hover { color: var(--bone); }
#bill-m:checked ~ .pricing-band .tier-toggle label[for="bill-m"],
#bill-y:checked ~ .pricing-band .tier-toggle label[for="bill-y"] {
  color: var(--bg); background: var(--bone);
}
.save-badge {
  font-family: var(--mono); font-size: 9px;
  padding: 2px 6px; border-radius: 100px;
  background: rgba(232,193,112,0.18); color: var(--gold);
  letter-spacing: 0.08em;
}
.pricing-toggle-row {
  display: flex; justify-content: flex-end; margin-bottom: 24px;
  position: relative; z-index: 1;
}

/* Tier grid */
.tiers-row {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px;
  position: relative; z-index: 1; align-items: stretch;
}
/* Toggle: the radio inputs sit BEFORE .pricing-band as siblings; the
   .tiers-* grids live INSIDE .pricing-band. Use a descendant combinator
   after the general sibling so we actually reach the grids. */
#bill-m:checked ~ .pricing-band .tiers-annual,
#bill-y:checked ~ .pricing-band .tiers-monthly { display: none; }

.tier-card {
  position: relative; padding: 32px 28px 28px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background:
    radial-gradient(120% 60% at 50% 0%, rgba(232,193,112,0.05), transparent 60%),
    var(--bg-glass);
  display: flex; flex-direction: column;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.tier-card:hover { transform: translateY(-3px); border-color: var(--line-hi); box-shadow: 0 14px 40px rgba(0,0,0,0.45); }

.tier-card.featured {
  transform: translateY(-6px);
  border-color: rgba(232,193,112,0.42);
  background:
    radial-gradient(120% 60% at 50% 0%, rgba(232,193,112,0.12), transparent 60%),
    var(--bg-elev);
}
.tier-card.featured:hover { transform: translateY(-9px); }
.tier-card.featured::before {
  content: "Most popular";
  position: absolute; top: -1px; left: 50%; transform: translate(-50%, -50%);
  padding: 4px 14px; border-radius: 100px;
  background: var(--gold); color: var(--bg);
  font-family: var(--mono); font-size: 9.5px; font-weight: 600;
  letter-spacing: 0.16em; text-transform: uppercase;
  white-space: nowrap;
}
.tier-card.featured::after {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}

.tier-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 6px;
}
.tier-name {
  font-family: var(--serif); font-size: 28px; font-weight: 400;
  line-height: 1; letter-spacing: -0.02em; color: var(--bone);
}
.tier-name .ital { font-style: italic; }
.tier-seats {
  font-family: var(--mono); font-size: 9.5px;
  padding: 3px 9px; border-radius: 100px;
  background: var(--bg); border: 1px solid var(--line-hi);
  color: var(--bone-dim); letter-spacing: 0.10em; text-transform: uppercase;
}
.tier-tagline {
  font-family: var(--sans); font-size: 13px; line-height: 1.5;
  color: var(--bone-dim); margin-bottom: 22px;
}

.tier-price {
  display: flex; align-items: baseline; gap: 6px;
  margin-top: 4px;
}
.tier-price .dollar {
  font-family: var(--mono); font-size: 20px; color: var(--gray-1); font-weight: 400;
}
.tier-price .num {
  font-family: var(--serif); font-style: italic;
  font-size: 64px; line-height: 1; letter-spacing: -0.04em; color: var(--bone);
}
.tier-price .per {
  font-family: var(--mono); font-size: 12px; color: var(--gray-1); letter-spacing: 0.08em;
}
.tier-price-sub {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gold);
  margin-top: 6px; min-height: 14px;
}
/* Monthly tier sub-line is an assurance ("cancel anytime"), not a savings pop —
   mute it so the gold sub-line is reserved for the annual value proposition. */
.tier-price-sub.is-assurance {
  color: var(--gray-1); text-transform: none; letter-spacing: 0.04em;
}

.tier-features {
  margin: 22px 0 24px; padding: 22px 0 0;
  border-top: 1px solid var(--line);
  display: flex; flex-direction: column; gap: 10px;
  flex: 1;
}
.tier-features li {
  list-style: none;
  font-family: var(--sans); font-size: 13px; line-height: 1.4; color: var(--bone-dim);
  display: flex; align-items: flex-start; gap: 10px;
}
.tier-features li::before {
  content: "✓"; color: var(--gold);
  font-family: var(--mono); font-weight: 500; font-size: 12px;
  flex-shrink: 0; margin-top: 2px;
}
.tier-features li.extra::before { color: var(--bone); }

.tier-cta {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 13px 20px; border-radius: 100px;
  background: var(--bone); color: var(--bg);
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase; font-weight: 600;
  text-decoration: none;
  transition: background 0.2s, transform 0.2s;
}
.tier-card.featured .tier-cta { background: var(--gold); }
.tier-cta:hover { background: var(--gold); transform: translateY(-1px); }
.tier-card.featured .tier-cta:hover { background: var(--bone); }

/* =========================================================
   METHODOLOGY NOTE · with subtle logo watermark
   ========================================================= */
.methodology {
  margin-top: 48px; padding: 32px 36px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background:
    radial-gradient(60% 100% at 100% 50%, rgba(232,193,112,0.04), transparent 60%),
    var(--bg-glass);
  display: grid; grid-template-columns: 1fr auto;
  gap: 28px; align-items: center;
  position: relative; overflow: hidden;
}
.methodology-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 12px;
}
.methodology-body p {
  font-family: var(--sans); font-size: 13.5px; line-height: 1.6;
  color: var(--bone-dim); max-width: 920px; margin: 0;
}
.methodology-body .em      { color: var(--bone); }
.methodology-body .em-gold { color: var(--gold); }
.methodology-mark {
  width: 96px; height: 96px; object-fit: contain;
  opacity: 0.20; flex-shrink: 0;
  filter: grayscale(0.3) brightness(1.1);
  user-select: none; pointer-events: none;
}
@media (max-width: 760px) {
  .methodology { grid-template-columns: 1fr; gap: 18px; }
  .methodology-mark { display: none; }
}

/* =========================================================
   FOOTER
   ========================================================= */
.footer {
  margin-top: 64px; padding: 40px 0 0;
  border-top: 1px solid var(--line);
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 40px;
  align-items: start;
}
.foot-quote {
  font-family: var(--serif); font-style: italic;
  font-size: 20px; line-height: 1.45; color: var(--bone-dim);
  letter-spacing: -0.005em;
}
.footer > .foot-block:nth-child(2) { text-align: center; }
.footer > .foot-block:nth-child(2) .next-date,
.footer > .foot-block:nth-child(2) .label,
.footer > .foot-block:nth-child(2) .sub { text-align: center; }
.foot-quote .by {
  display: block; margin-top: 12px;
  font-family: var(--mono); font-style: normal; font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--gray-1);
}
.foot-block .label {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 14px;
}
.foot-block .next-date {
  font-family: var(--serif); font-size: 32px;
  color: var(--bone); letter-spacing: -0.02em;
}
.foot-block .sub {
  font-family: var(--sans); font-size: 13px;
  color: var(--bone-dim); margin-top: 6px;
}
.foot-tiny {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--gray-2); text-align: right; margin-top: 60px;
}

/* =========================================================
   RESPONSIVE BREAKPOINTS  (added via PASS 2 of visual_qa loop)
   Goal: every multi-column row collapses gracefully below 1100 px
   so the dashboard remains usable on tablets and phones.
   Production v3 stays desktop-first; these queries are additive.
   ========================================================= */

/* Tablet / narrow laptop · ≤ 1100 px */
@media (max-width: 1100px) {
  .app { padding: 0 32px 64px; }
  .spine { display: none; }                          /* R13 */

  /* R1 — hero: collapse 3-col to a vertical stack */
  .hero { grid-template-columns: 1fr; gap: 36px; padding: 24px 0 40px; }
  .edge-score-wrap { order: 1; }
  .hero > div:nth-child(2) { order: 2; }
  .doppel, .tier-card { order: 3; max-width: none; }
  .hero-headline { font-size: 58px; }
  .edge-score-svg { width: 220px; height: 220px; }
  .edge-num .v { font-size: 72px; }

  /* R2 — comp-radar card: stack radar above narrative on tablet/mobile */
  .comp-radar-card { grid-template-columns: 1fr; gap: 32px; padding: 36px 24px; }
  .comp-radar-svg { max-width: 380px; }
  .comp-radar-line { font-size: 22px; }

  /* R3 — highlight reel: 3 → 1 vertical scroll on narrow tablet/mobile */
  .reel { grid-template-columns: 1fr; gap: 16px; }
  .clip { aspect-ratio: 16 / 11; }

  /* R4 — Swing of Week + DNA: stack */
  .two-col { grid-template-columns: 1fr; gap: 18px; }

  /* R5 — Form Quadrants + Phase Timing: stack */
  .diamond-row { grid-template-columns: 1fr; gap: 18px; }

  /* R6 — Phase Clock signature: stack vertically */
  .signature {
    grid-template-columns: 1fr; gap: 32px;
    padding: 40px 28px; margin-top: 32px;
  }
  .sig-title { font-size: 38px; }

  /* R7 — 12-Week stats: 6 → 3×2 */
  .progress-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .progress-stat { border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  .progress-stat:nth-child(3n), .progress-stat:nth-last-child(-n+3) { border-right: none; }
  .progress-stat:nth-last-child(-n+3) { border-bottom: none; }
  .progress-stat:nth-child(3n) { border-right: none; }

  /* R8 — Milestones: 4 → 2×2 */
  .milestones-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }

  /* R9 — Drill cards: 3 → 1 */
  .coach-grid { grid-template-columns: 1fr; }

  /* R10 — Achievements: 4 → 2×2 */
  .rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }

  /* R11 — Pricing tiers: stack */
  .tiers-row { grid-template-columns: 1fr !important; max-width: 460px; margin: 0 auto; }
  .tier-card.featured { transform: none; }

  /* R12 — Footer: stack */
  .footer { grid-template-columns: 1fr; gap: 24px; text-align: left; }
  .footer > .foot-block:nth-child(2),
  .footer > .foot-block:nth-child(2) .next-date,
  .footer > .foot-block:nth-child(2) .label,
  .footer > .foot-block:nth-child(2) .sub,
  .footer > .foot-block:nth-child(3) { text-align: left !important; }
  .foot-tiny { text-align: left; margin-top: 32px; }

  /* Phase Clock 12-week SVG inner trend: reduce viewbox padding */
  .progress-trend-card { padding: 22px; }
  .trend { padding: 22px 22px 8px; }
  .card { border-radius: 12px; }

  /* Section heads tighten */
  .section-head { padding: 36px 0 18px; }
  .section-title { font-size: 24px; }
}

/* Mobile · ≤ 640 px */
@media (max-width: 640px) {
  .app { padding: 0 18px 48px; }

  /* R14 — Masthead nav: hide pill nav, keep logo + streak */
  .nav { display: none; }
  .user-streak { display: none; }
  .masthead { padding: 18px 0 16px; }
  .issue-line { display: none; }   /* publication metadata strip — too dense for mobile */

  /* Hero compress further */
  .hero { padding: 16px 0 32px; gap: 24px; }
  .hero-headline { font-size: 42px; line-height: 1.05; }
  .hero-deck { font-size: 14px; }
  .hero-meta { gap: 16px; flex-wrap: wrap; }
  .edge-score-svg { width: 180px; height: 180px; }
  .edge-num .v { font-size: 56px; }
  .edge-score-cats { grid-template-columns: 1fr 1fr; gap: 8px 16px; }

  /* R2 mobile: comp-radar card tightens further on phones */
  .comp-radar-svg { max-width: 320px; }
  .comp-radar-line { font-size: 20px; }

  /* R7 mobile: 12-Week stats 3 → 2 cols */
  .progress-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .progress-stat { border-right: 1px solid var(--line) !important; }
  .progress-stat:nth-child(2n) { border-right: none !important; }

  /* R8 mobile: Milestones 2 → 1 col */
  .milestones-row { grid-template-columns: 1fr; }

  /* R10 mobile: Achievements 2 → 1 col */
  .rail { grid-template-columns: 1fr; }

  /* Closest MLB Match: collapse 3-col grid → stack */
  .match-grid { grid-template-columns: 1fr; gap: 24px; padding: 28px 22px; }
  .match-name { font-size: 56px; }
  .match-bars { gap: 10px; }
  .match-cta-row {
    flex-direction: column; align-items: stretch; gap: 14px;
    padding: 18px 22px;
  }
  .match-stat-pills { flex-wrap: wrap; gap: 14px; font-size: 9.5px; }

  /* Phase Timing Spectrum SVG — let it scale fully */
  .spray svg { max-width: 100%; height: auto; }

  /* Pricing band tighten */
  .pricing-band { padding: 36px 22px; }
  .pricing-title { font-size: 36px; }
  .free-strip { flex-direction: column; gap: 8px; text-align: center; padding: 14px; border-radius: 16px; }
  .pricing-toggle-row { justify-content: center; }

  /* Card title sizing for narrow viewports */
  .card-title, .sig-title { font-size: 26px; }
  .signature { padding: 32px 20px; }

  /* Methodology stacks (already had its own @media); footer too */
  .card { padding: 22px; }

  /* Ledger rows reduce column complexity */
  .ledger-row {
    grid-template-columns: 1fr;
    gap: 4px; padding: 14px 0;
  }
  .ledger-row .top-metric, .ledger-row .swings { display: none; }
  .ledger-row .grade { text-align: left; }
  .ledger-row .mood { display: none; }
}

/* D1 — Ledger row: slightly widen the swing-count column so "1 sw"
   reads less skeletal on desktop. */
.ledger-row { grid-template-columns: 110px 80px 1fr 70px 50px; }

/* D3 — 30-day trend chart annotation pins: smaller font so 3 pins
   don't crowd each other on the right side. */
.trend-chart svg text[fill="#E8C170"] { font-size: 8px; }

/* =========================================================
   ENTRY ANIMATIONS — staggered
   ========================================================= */
.fade-in {
  opacity: 0; transform: translateY(8px);
  animation: fadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }
.d1{animation-delay:.05s}.d2{animation-delay:.12s}.d3{animation-delay:.20s}.d4{animation-delay:.28s}
.d5{animation-delay:.36s}.d6{animation-delay:.44s}.d7{animation-delay:.52s}.d8{animation-delay:.60s}
.d9{animation-delay:.68s}.d10{animation-delay:.76s}.d11{animation-delay:.84s}.d12{animation-delay:.92s}

/* =========================================================
   EDGE SCORE GAUGE (numeric)
   ========================================================= */
.edge-num {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -56%);
  text-align: center;
}
.edge-num .v {
  font-family: var(--serif); font-style: italic;
  font-size: 96px; line-height: 1; color: var(--bone); letter-spacing: -0.04em;
}
.edge-num .out {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.16em; color: var(--gray-1); text-transform: uppercase;
}
.edge-num .delta {
  margin-top: 6px;
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.08em; color: var(--gold);
}
.breathe {
  animation: breathe 4.2s ease-in-out infinite;
}

/* =========================================================
   TIER PROGRESSION (hero right column)
   ========================================================= */
.tier-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 26px 28px 22px;
  background:
    radial-gradient(140% 90% at 100% 0%, rgba(232,193,112,0.10), transparent 60%),
    radial-gradient(140% 90% at 0% 100%, rgba(230,69,48,0.06), transparent 60%),
    var(--bg-glass);
  position: relative; overflow: hidden;
}
.tier-card::after {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}
.tier-eyebrow {
  display: flex; justify-content: space-between; align-items: center;
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-1);
}
.tier-eyebrow .badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 9px; border-radius: 100px;
  border: 1px solid rgba(232,193,112,0.32);
  background: rgba(232,193,112,0.08);
  color: var(--gold); font-weight: 500;
}
.tier-eyebrow .badge .dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--gold);
  animation: pulse 2.2s ease-in-out infinite;
}
.tier-name {
  margin-top: 14px;
  font-family: var(--serif); font-style: italic;
  font-size: 56px; line-height: 0.95; letter-spacing: -0.025em;
  color: var(--bone);
}
.tier-sub {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 4px;
}

.tier-track {
  margin-top: 24px; position: relative;
}
.tier-segs {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;
}
.tier-seg {
  height: 6px; border-radius: 3px; background: var(--gray-3);
  position: relative; overflow: hidden;
}
.tier-seg.on { background: rgba(232,193,112,0.35); }
.tier-seg.on::after {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 100%;
  background: linear-gradient(90deg, var(--gold-deep), var(--gold));
  border-radius: 3px;
}
.tier-seg.current {
  background: rgba(232,193,112,0.18);
}
.tier-seg.current::after {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 65%;
  background: linear-gradient(90deg, var(--gold-deep), var(--gold));
  border-radius: 3px;
}
.tier-marker {
  position: absolute; top: -7px;
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--gold); border: 3px solid var(--bg);
  box-shadow: 0 0 0 1px rgba(232,193,112,0.55), 0 0 22px rgba(232,193,112,0.55);
  transform: translateX(-50%);
  animation: markerPulse 3s ease-in-out infinite;
}
@keyframes markerPulse {
  0%, 100% { box-shadow: 0 0 0 1px rgba(232,193,112,0.55), 0 0 12px rgba(232,193,112,0.40); }
  50%      { box-shadow: 0 0 0 1px rgba(232,193,112,0.85), 0 0 26px rgba(232,193,112,0.75); }
}
.tier-labels {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;
  margin-top: 14px;
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.14em; text-transform: uppercase;
}
.tier-labels span { color: var(--gray-2); text-align: center; }
.tier-labels span.now { color: var(--gold); }

.tier-foot {
  margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--line);
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.08em;
}
.tier-foot .lab { color: var(--gray-1); text-transform: uppercase; }
.tier-foot .next {
  font-family: var(--sans); font-size: 13px;
  letter-spacing: 0; color: var(--bone);
}
.tier-foot .next .gold { color: var(--gold); font-weight: 500; }

.just-unlocks {
  margin-top: 18px;
  display: flex; gap: 8px; flex-wrap: wrap;
}
.unlock-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px 6px 8px;
  border-radius: 100px;
  border: 1px solid rgba(232,193,112,0.32);
  background: rgba(232,193,112,0.06);
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--bone);
}
.unlock-chip .ico {
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--gold);
  display: grid; place-items: center;
  font-family: var(--serif); font-style: italic; font-size: 11px; color: var(--bg);
  flex-shrink: 0;
}
.unlock-chip .lab { color: var(--gray-1); }

/* =========================================================
   PREMIUM CLOSEST MLB MATCH FEATURE CARD
   ========================================================= */
.match-feature {
  margin-top: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(80% 100% at 100% 0%,  rgba(232,193,112,0.10), transparent 55%),
    radial-gradient(70% 100% at 0% 100%,  rgba(230,69,48,0.10), transparent 55%),
    linear-gradient(140deg, #14171d 0%, #0a0b0e 75%);
  position: relative; overflow: hidden;
}
.match-feature::after {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}
.match-feature::before {
  content: ""; position: absolute; inset: 0;
  background-image: url("data:image/svg+xml;utf8,<svg width='600' height='600' viewBox='0 0 600 600' xmlns='http://www.w3.org/2000/svg'><circle cx='300' cy='300' r='298' fill='none' stroke='rgba(232,193,112,0.05)' stroke-dasharray='3 6'/><circle cx='300' cy='300' r='250' fill='none' stroke='rgba(232,193,112,0.04)'/><circle cx='300' cy='300' r='200' fill='none' stroke='rgba(232,193,112,0.03)'/><circle cx='300' cy='300' r='150' fill='none' stroke='rgba(232,193,112,0.025)'/></svg>");
  background-position: 105% 50%; background-repeat: no-repeat;
  background-size: 720px; opacity: 0.85;
  pointer-events: none;
}
.match-grid {
  display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: 32px; padding: 44px 48px;
  position: relative; z-index: 1; align-items: center;
}
.match-meta { display: flex; flex-direction: column; gap: 14px; }
.match-eyebrow {
  display: inline-flex; align-items: center; gap: 10px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--gold);
}
.match-eyebrow .swatch { display: inline-block; width: 22px; height: 1px; background: var(--gold); }
.match-kicker {
  font-family: var(--sans); font-size: 14px; font-weight: 400;
  color: var(--bone-dim); letter-spacing: 0;
}
.match-name {
  font-family: var(--serif); font-style: italic; font-weight: 400;
  font-size: 82px; line-height: 0.92; letter-spacing: -0.03em;
  color: var(--bone); margin: 6px 0 0;
}
.match-tagline {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
  margin-top: 10px;
}
.match-bio {
  margin-top: 18px;
  font-family: var(--sans); font-size: 13.5px; line-height: 1.55;
  color: var(--bone-dim); max-width: 340px;
}
.match-bio .em { color: var(--bone); }

.match-ring-wrap { display: grid; place-items: center; position: relative; }
.match-ring-pct {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -54%);
  text-align: center; pointer-events: none;
}
.match-ring-pct .v {
  font-family: var(--serif); font-style: italic; font-size: 108px;
  line-height: 1; color: var(--bone); letter-spacing: -0.04em;
  display: inline-flex; align-items: flex-start; gap: 10px;
}
.match-ring-pct .v .pct {
  font-family: var(--mono); font-size: 24px; color: var(--gray-1);
  font-style: normal; font-weight: 400; line-height: 1;
  margin-top: 14px;
}
.match-ring-pct .lab {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--gold); margin-top: 6px;
}

.match-bars {
  display: flex; flex-direction: column; gap: 14px;
}
.match-bar-row {
  display: grid; grid-template-columns: 120px 1fr 36px;
  align-items: center; gap: 14px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.match-bar-track {
  height: 3px; background: var(--gray-3);
  border-radius: 2px; overflow: hidden; position: relative;
}
.match-bar-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, var(--red), var(--gold));
}
.match-bar-val { color: var(--bone); text-align: right; font-weight: 500; }
.match-bar-row.top .match-bar-val { color: var(--gold); }

.match-cta-row {
  border-top: 1px solid var(--line);
  padding: 22px 48px;
  display: flex; justify-content: space-between; align-items: center;
  position: relative; z-index: 1;
}
.match-stat-pills {
  display: flex; gap: 24px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.10em; text-transform: uppercase; color: var(--gray-1);
}
.match-stat-pills .v { color: var(--bone); font-weight: 500; margin-left: 6px; }
.match-stat-pills .v.gold { color: var(--gold); }
.match-cta {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 12px 22px; border-radius: 100px;
  background: var(--bone); color: var(--bg);
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase; font-weight: 600;
  text-decoration: none;
  transition: background 0.2s, transform 0.2s;
}
.match-cta:hover { background: var(--gold); transform: translateY(-1px); }

/* PR celebration burst — small star-rays element */
.pr-burst {
  display: inline-block; width: 14px; height: 14px;
  margin-left: 6px; vertical-align: middle; position: relative;
}
.pr-burst::before, .pr-burst::after {
  content: ""; position: absolute; inset: 0;
  background: var(--gold);
  clip-path: polygon(50% 0, 60% 40%, 100% 50%, 60% 60%, 50% 100%, 40% 60%, 0 50%, 40% 40%);
  animation: prSpin 8s linear infinite;
}
.pr-burst::after { animation-direction: reverse; opacity: 0.5; transform: scale(0.7); }
@keyframes prSpin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
@keyframes breathe {
  0%, 100% { filter: drop-shadow(0 0 0px rgba(232,193,112,0)); }
  50%      { filter: drop-shadow(0 0 22px rgba(232,193,112,0.16)); }
}

/* Ticker tape removed in PASS 7 — its 20+ scrolling metrics were
   "look-what-we-measure" theater that competed with the new §03 comp
   radar for attention. Persona critics flagged it as redundant once
   the radar exists. */

/* =========================================================
   SECTION SPINE  (editorial running numbers on left edge)
   ========================================================= */
.spine {
  position: absolute; left: 16px; top: 200px; bottom: 200px;
  width: 1px; background: linear-gradient(180deg, transparent, var(--line) 10%, var(--line) 90%, transparent);
  pointer-events: none; z-index: 0;
}
.spine-mark {
  position: absolute; left: -32px; width: 80px;
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--gray-2); writing-mode: vertical-rl;
  transform: rotate(180deg); text-orientation: mixed;
}
.spine-mark::before {
  content: ""; position: absolute; right: -8px; top: 50%;
  width: 6px; height: 1px; background: var(--gray-2);
}

/* =========================================================
   CINEMATIC SILHOUETTE STAGE
   ========================================================= */
.silhouette-stage {
  position: relative; width: 100%; height: 100%;
}
.ghost { opacity: 0.20; transition: opacity 0.3s; }
.ghost.g1 { opacity: 0.12; }
.ghost.g2 { opacity: 0.18; }
.ghost.g3 { opacity: 0.28; }
.silhouette-main { opacity: 1; }
.bat-trail {
  fill: none; stroke: url(#trailGrad);
  stroke-width: 2.4; stroke-linecap: round;
  opacity: 0.85;
  animation: trailDraw 1.4s cubic-bezier(.4,1.1,.4,1) 0.6s both;
}
@keyframes trailDraw {
  from { stroke-dasharray: 240; stroke-dashoffset: 240; opacity: 0; }
  to   { stroke-dasharray: 240; stroke-dashoffset: 0;   opacity: 0.85; }
}
/* `.stage-label` removed — its absolute positioning conflicted with the
   SVG ghost pose labels under the figures, producing overlap (PR #9 +
   QA assertions confirmed). The `.stage-tag` chip at top-right of the
   stage already identifies what the user is looking at, so this caption
   was redundant. */
.stage-tag {
  position: absolute; top: 16px; right: 18px;
  padding: 4px 10px; border-radius: 100px;
  background: rgba(232,193,112,0.10); border: 1px solid rgba(232,193,112,0.4);
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gold);
}

/* =========================================================
   FIELD / SPRAY GRAD
   ========================================================= */
.field-text {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.14em; text-transform: uppercase; fill: var(--gray-2);
}
.spray-stat {
  margin-top: 18px;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px;
  padding-top: 18px; border-top: 1px solid var(--line);
}
.spray-stat .v {
  font-family: var(--mono); font-size: 22px; color: var(--bone);
  font-weight: 500; letter-spacing: -0.02em;
}
.spray-stat .l {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 4px;
}

/* small detail: outline ring above lb-card on top */
.lb-card.top::before {
  content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}

/* ============================================================
   MOBILE OVERRIDES — placed LAST on purpose.
   Several component rules (.match-grid, .edge-num, the rings) are defined
   later in this stylesheet than the @media blocks above. Media queries don't
   add specificity, so those desktop base rules were winning by source order
   and the dashboard never actually went mobile for them (3-col match grid
   overlapping, score number spilling out of the ring). Re-asserting here, at
   the end, makes the mobile layout win.
   ============================================================ */
@media (max-width: 760px) {
  /* MLB match: stack name / ring / metrics instead of 3 overlapping columns */
  .match-grid { grid-template-columns: 1fr !important; gap: 22px !important; }
  .match-ring-wrap svg { width: 100% !important; max-width: 260px !important; height: auto !important; }
  .match-ring-wrap { width: 100%; }

  /* Edge score: keep the number block inside the ring */
  .edge-score-svg { width: 240px !important; height: 240px !important; max-width: 100% !important; }
  .edge-num { transform: translate(-50%, -50%) !important; }
  .edge-num .v { font-size: 60px !important; }
  .edge-num .out { font-size: 10px !important; }
  .edge-num .delta { white-space: nowrap !important; font-size: 10px !important; margin-top: 4px !important; }
}

/* ============================================================
   MOBILE: SHORTEN THE DASHBOARD TO AN "AT A GLANCE" VIEW
   ------------------------------------------------------------
   On phones the full report scrolls far too long. The deeper
   sections each already have a dedicated nav page (Form & Timing,
   Velocity Ladder, 12-Week Progress, Drill Prescription →
   Training Plan, Session Ledger → Sessions, Achievements), so on
   mobile we hide them here and let the masthead nav carry the
   user to the detail. Anything tagged `.m-hide` is the top-level
   wrapper (and its section-head) of one of those sections.

   KEPT on mobile: hero (Edge Score), § 02 MLB Match,
   § 03 "Your shape, vs. theirs", the masthead nav, and the
   pricing band (the upsell). DESKTOP IS UNCHANGED — there is no
   non-media-query rule for `.m-hide`, so it shows everywhere else.
   Appended at the END of <style> so source order keeps it winning.
   ============================================================ */
@media (max-width: 760px) {
  .m-hide { display: none !important; }
}
</style>
</head>
<body>
<div class="app">
  <div class="spine">
    <span class="spine-mark" style="top: 5%;">§ 01 / This Week's Headline</span>
    <span class="spine-mark" style="top: 14%;">§ 02 / MLB Match</span>
    <span class="spine-mark" style="top: 23%;">§ 03 / Your Shape vs Theirs</span>
    <span class="spine-mark" style="top: 32%;">§ 04 / Form &amp; Timing</span>
    <span class="spine-mark" style="top: 41%;">§ 05 / Velocity Ladder</span>
    <span class="spine-mark" style="top: 50%;">§ 06 / Long-Term Development</span>
    <span class="spine-mark" style="top: 59%;">§ 07 / Drill Prescription</span>
    <span class="spine-mark" style="top: 68%;">§ 08 / Session Ledger</span>
    <span class="spine-mark" style="top: 77%;">§ 09 / Recent Unlocks</span>
    <span class="spine-mark" style="top: 86%;">§ 10 / Edge Pro Upsell</span>
    <span class="spine-mark" style="top: 95%;">§ 11 / What We Measure</span>
  </div>

  <!-- MASTHEAD -->
  <header class="masthead fade-in d1">
    <div class="brand">
      <img class="brand-mark" src="{{LOGO_DATA_URI}}" alt="BarrelLabs">
      <div class="wordmark">Barrellabs <span class="sep">/</span><span class="product"> Edge</span></div>
    </div>
    <!-- In-iframe nav pills are DECORATIVE only. The dashboard lives
         inside a Streamlit components.html iframe, so any onclick inside
         here can only trigger a HARD browser navigation — which Streamlit
         treats as a new session, wiping Supabase auth tokens (stored in
         session_state, not browser cookies) and forcing the user to
         re-login. Functional navigation is rendered by Python in
         render_dashboard_v3() ABOVE this iframe as Streamlit-native
         buttons. They trigger in-app reruns and preserve auth. -->
    <nav class="nav">
      <a class="active" href="#" onclick="event.preventDefault();">Dashboard</a>
      <a href="#" onclick="event.preventDefault();">Sessions</a>
      <a href="#" onclick="event.preventDefault();">Compare</a>
      <a href="#" onclick="event.preventDefault();">Drills</a>
      <a href="#" onclick="event.preventDefault();">Library</a>
    </nav>
    <div class="user-chip">
      <span class="user-streak"><span class="dot"></span>17-day streak</span>
      <div class="user-avatar">L</div>
    </div>
  </header>

  <div class="issue-line fade-in d2">
    <span>Volume IV · Issue 23</span>
    <span class="center">Player Report · Logan Collins · Right-handed · 5'11" · 178 lb</span>
    <span class="right">Sunday · May 17 · 2026</span>
  </div>

  <!-- HERO: Edge Score | Headline | Doppelgänger -->
  <section class="hero">
    <div class="edge-score-wrap fade-in d3">
      <div style="position: relative;">
        <svg class="edge-score-svg breathe" width="280" height="280" viewBox="-150 -150 300 300" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#E8C170"/>
              <stop offset="100%" stop-color="#C9A350"/>
            </linearGradient>
            <linearGradient id="edgeTrack" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="rgba(244,239,230,0.08)"/>
              <stop offset="100%" stop-color="rgba(244,239,230,0.03)"/>
            </linearGradient>
          </defs>
          <circle cx="0" cy="0" r="120" fill="none" stroke="url(#edgeTrack)" stroke-width="14"/>
          <circle cx="0" cy="0" r="138" fill="none" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <circle cx="0" cy="0" r="102" fill="rgba(232,193,112,0.02)" stroke="rgba(232,193,112,0.10)"/>
          <circle cx="0" cy="0" r="120" fill="none" stroke="url(#edgeGrad)" stroke-width="14" stroke-linecap="round" stroke-dasharray="663.7" stroke-dashoffset="79.6" transform="rotate(-90)"/>
          <g stroke="rgba(244,239,230,0.18)" stroke-width="1">
            <line x1="0" y1="-138" x2="0" y2="-130"/>
            <g transform="rotate(36)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(72)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(108)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(144)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(180)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(216)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(252)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(288)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
            <g transform="rotate(324)"><line x1="0" y1="-138" x2="0" y2="-130"/></g>
          </g>
        </svg>
        <div class="edge-num">
          <div class="v">88</div>
          <div class="out">Edge Score · / 100</div>
          <div class="delta">▲ +4 vs last week</div>
        </div>
      </div>
      <div class="edge-score-label">composite · pose-derived · <span style="color:var(--gold)">ELITE tier</span></div>
      <div class="edge-score-cats">
        <div class="esc-row"><span>MLB match</span><span class="v peak">91</span></div>
        <div class="esc-row"><span>Rotation</span><span class="v peak">94</span></div>
        <div class="esc-row"><span>Knee drive</span><span class="v">86</span></div>
        <div class="esc-row"><span>Head stability</span><span class="v">89</span></div>
        <div class="esc-row"><span>Timing</span><span class="v">92</span></div>
        <div class="esc-row"><span>Tempo</span><span class="v peak">91</span></div>
      </div>
    </div>

    <div class="fade-in d4">
      <div class="hero-eyebrow"><span class="swatch"></span>§ 01 · This week's headline</div>
      <h1 class="hero-headline">Your separation<br>hit <span class="ital">42°</span><span class="pr-burst" style="width:22px;height:22px;margin:0 6px 0 8px;"></span>— MLB <span class="red">territory.</span></h1>
      <p class="hero-deck">Across 42 swings this week, your peak hip-shoulder separation climbed to 42° — a personal best by 2° and within four degrees of Mookie Betts's signature delay. Your overall match score against your MLB match ticked up to 91%, the cleanest week your pose data has registered to date.</p>
      <div class="hero-meta">
        <div class="hero-meta-block"><span class="hero-meta-label">Swings logged</span><span class="hero-meta-value">{{TOTAL_SWINGS}} swings · {{TOTAL_SESSIONS}} sessions</span></div>
        <div class="hero-meta-block"><span class="hero-meta-label">Personal records</span><span class="hero-meta-value">{{PR_TOTAL}}</span></div>
      </div>
    </div>

    <aside class="tier-card fade-in d5">
      <div class="tier-eyebrow">
        <span>Player tier · this season</span>
        <span class="badge"><span class="dot"></span>Tier 03 of 04</span>
      </div>
      <div class="tier-name">Elite</div>
      <div class="tier-sub">You're 4 Edge points from promotion to PRO</div>

      <div class="tier-track">
        <div class="tier-segs">
          <div class="tier-seg on"></div>
          <div class="tier-seg current"></div>
          <div class="tier-seg"></div>
          <div class="tier-seg"></div>
        </div>
        <!-- marker at 65% of segment 2 (Elite), which is 25% + (65% * 25%) = 41.25% across the full track -->
        <div class="tier-marker" style="left: 41%;"></div>
      </div>
      <div class="tier-labels">
        <span>Amateur</span><span class="now">Elite</span><span>Pro</span><span>MLB</span>
      </div>

      <div class="tier-foot">
        <span class="lab">Edge Score 88</span>
        <span class="next">next tier <span class="gold">Pro</span> at 92 · <span class="gold">+ 4 pts</span></span>
      </div>

      <div class="just-unlocks">
        <span class="unlock-chip"><span class="ico">★</span><span>Forty-Two Club</span><span class="lab">just unlocked</span></span>
        <span class="unlock-chip"><span class="ico">◇</span><span>17-day streak</span><span class="lab">just unlocked</span></span>
      </div>
    </aside>
  </section>

  <!-- CLOSEST MLB MATCH · § 02 · MOVED TO TOP OF PAGE PER USER HIERARCHY -->
  <div class="section-head fade-in d5">
    <div>
      <div class="section-eyebrow">§ 02 · MLB Match</div>
      <h2 class="section-title">Your closest <span class="ital">MLB match.</span></h2>
    </div>
    <div class="section-sub">Single best match across 32 pose-derived features · refreshed nightly</div>
  </div>

  <section class="match-feature fade-in d5">
    <div class="match-grid">

      <!-- Left: meta -->
      <div class="match-meta">
        <span class="match-eyebrow"><span class="swatch"></span>Closest MLB Match</span>
        <span class="match-kicker">You swing most like…</span>
        <h3 class="match-name">Mookie<br>Betts</h3>
        <div class="match-tagline">LAD · RHH · 5'10" · 180 lb · 4× All-Star</div>
        <p class="match-bio">
          You share Betts's <span class="em">compact load</span>, <span class="em">42° hip-shoulder separation</span> peak, and his signature <span class="em">delayed launch</span>. The model has compared your last 42 swings against the full reference library — Betts is the cleanest single match this season.
        </p>
      </div>

      <!-- Center: big match-score ring -->
      <div class="match-ring-wrap">
        <svg width="340" height="340" viewBox="-180 -180 360 360" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="matchRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%"  stop-color="#E8C170"/>
              <stop offset="100%" stop-color="#C9A350"/>
            </linearGradient>
          </defs>
          <!-- outer fine ring -->
          <circle cx="0" cy="0" r="165" fill="none" stroke="rgba(244,239,230,0.08)" stroke-width="1"/>
          <!-- track -->
          <circle cx="0" cy="0" r="145" fill="none" stroke="rgba(244,239,230,0.06)" stroke-width="14"/>
          <!-- 91% arc -->
          <circle cx="0" cy="0" r="145" fill="none" stroke="url(#matchRingGrad)" stroke-width="14"
                  stroke-linecap="round" stroke-dasharray="911.06" stroke-dashoffset="82.0"
                  transform="rotate(-90)"/>
          <!-- inner plate -->
          <circle cx="0" cy="0" r="120" fill="rgba(232,193,112,0.025)" stroke="rgba(232,193,112,0.10)"/>
          <!-- ticks -->
          <g stroke="rgba(244,239,230,0.16)" stroke-width="1">
            <line x1="0" y1="-165" x2="0" y2="-156"/>
            <g transform="rotate(45)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(90)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(135)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(180)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(225)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(270)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
            <g transform="rotate(315)"><line x1="0" y1="-165" x2="0" y2="-156"/></g>
          </g>
        </svg>
        <div class="match-ring-pct">
          <div class="v">91<span class="pct">%</span></div>
          <div class="lab">Match score</div>
        </div>
      </div>

      <!-- Right: comparable metric bars -->
      <div class="match-bars">
        <div class="match-bar-row top">
          <span>Hip-Sh sep peak</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:94%"></div></div>
          <span class="match-bar-val">94</span>
        </div>
        <div class="match-bar-row top">
          <span>Phase tempo</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:92%"></div></div>
          <span class="match-bar-val">92</span>
        </div>
        <div class="match-bar-row">
          <span>Hip rotation</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:88%"></div></div>
          <span class="match-bar-val">88</span>
        </div>
        <div class="match-bar-row">
          <span>Launch window</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:87%"></div></div>
          <span class="match-bar-val">87</span>
        </div>
        <div class="match-bar-row">
          <span>Head stability</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:86%"></div></div>
          <span class="match-bar-val">86</span>
        </div>
        <div class="match-bar-row">
          <span>Knee drive</span>
          <div class="match-bar-track"><div class="match-bar-fill" style="width:74%"></div></div>
          <span class="match-bar-val">74</span>
        </div>
      </div>
    </div>

    <div class="match-cta-row">
      <div class="match-stat-pills">
        <span>Match score <span class="v gold">91%</span></span>
        <span>Delta vs last wk <span class="v gold">+ 4 pts</span><span class="pr-burst"></span></span>
        <span>Sub-metric band <span class="v">Strong match</span></span>
        <span>Considered <span class="v">17 references</span></span>
      </div>
    </div>
  </section>

  <!-- SCOREBOARD -->
  <div class="section-head fade-in d6">
    <div>
      <div class="section-eyebrow">§ 03 · Your shape, vs. theirs</div>
      <h2 class="section-title">You <span class="ital">vs.</span> Mookie Betts.</h2>
    </div>
    <div class="section-sub">Five biomechanical axes. One footprint. The shape you're chasing.</div>
  </div>

  <div class="comp-radar-card fade-in d6">
    <div class="comp-radar-vis">
      <svg width="440" height="440" viewBox="-220 -220 440 440" class="comp-radar-svg" xmlns="http://www.w3.org/2000/svg">
        <!-- background concentric guides -->
        <circle cx="0" cy="0" r="170" fill="none" stroke="rgba(244,239,230,0.05)"/>
        <circle cx="0" cy="0" r="120" fill="none" stroke="rgba(244,239,230,0.05)"/>
        <circle cx="0" cy="0" r="70"  fill="none" stroke="rgba(244,239,230,0.05)"/>
        <!-- 5 axis spokes -->
        <g stroke="rgba(244,239,230,0.12)" stroke-width="0.8">
          <line x1="0" y1="0" x2="0"     y2="-170"/>
          <line x1="0" y1="0" x2="162"   y2="-52"/>
          <line x1="0" y1="0" x2="100"   y2="136"/>
          <line x1="0" y1="0" x2="-100"  y2="136"/>
          <line x1="0" y1="0" x2="-162"  y2="-52"/>
        </g>
        <!-- comp polygon (red dashed) at radius=170 (perfect reference) -->
        <polygon class="comp-poly" points="0,-170 162,-52 100,136 -100,136 -162,-52"
                 fill="none" stroke="#E64530" stroke-width="1.5"
                 stroke-dasharray="5 4" opacity="0.85"/>
        <!-- YOU polygon — replaced at render time -->
        <polygon class="you-poly" points="0,-130 124,-40 76,104 -76,104 -124,-40"
                 fill="rgba(244,239,230,0.16)" stroke="#F4EFE6" stroke-width="2"/>
        <!-- axis labels at vertex tips -->
        <g font-family="Geist Mono, monospace" font-size="10.5" fill="#8B8E94" letter-spacing="0.14em" text-anchor="middle">
          <text x="0"    y="-186">ROTATION</text>
          <text x="184"  y="-50" text-anchor="start">SEQUENCING</text>
          <text x="116"  y="160">KNEE DRIVE</text>
          <text x="-116" y="160">HEAD STABILITY</text>
          <text x="-184" y="-50" text-anchor="end">SWING DURATION</text>
        </g>
      </svg>
    </div>
    <div class="comp-radar-narrative">
      <p class="comp-radar-line">You match Betts on <span class="em">rotation</span> and <span class="em">sequencing</span>. Close the gap on <span class="em">head stability</span>.</p>
      <p class="comp-radar-deltas">−12 ROT · −8 SEQ · −22 HEAD</p>
      <div class="comp-radar-legend">
        <div class="row"><span class="swatch you"></span><span>your shape</span></div>
        <div class="row"><span class="swatch comp"></span><span>Mookie Betts</span></div>
      </div>
      <a class="comp-radar-cta" href="/?page=drills">Open my plan to close the gap →</a>
    </div>
  </div>

  <!-- FORM QUADRANTS + PHASE TIMING SPECTRUM -->
  <div class="section-head fade-in d8 m-hide">
    <div>
      <div class="section-eyebrow">§ 06 · Form &amp; Timing</div>
      <h2 class="section-title">Where you <span class="ital">match</span>, where you don't.</h2>
    </div>
    <div class="section-sub">Pose-derived sub-metrics scored vs your MLB match · last 7 days</div>
  </div>

  <div class="diamond-row m-hide">
    <div class="card">
      <div class="card-eyebrow">Form quadrants · similarity scores</div>
      <h3 class="card-title">Your <span class="ital">strong</span> regions.</h3>
      <div class="zone-axes" style="margin-top:24px;"><span>Sep · sep @ FP · sep @ contact</span></div>
      <div class="zone-grid">
        <div class="zone-cell heat-3"><span class="n">SEP PEAK</span><span class="pct">94</span></div>
        <div class="zone-cell heat-2"><span class="n">SEP @ FP</span><span class="pct">81</span></div>
        <div class="zone-cell heat-3"><span class="n">SEP @ CON</span><span class="pct">89</span></div>
        <div class="zone-cell heat-2"><span class="n">HIP @ FP</span><span class="pct">76</span></div>
        <div class="zone-cell heat-3"><span class="n">HIP @ CON</span><span class="pct">88</span></div>
        <div class="zone-cell heat-3"><span class="n">HIP RANGE</span><span class="pct">86</span></div>
        <div class="zone-cell heat-1"><span class="n">KNEE @ FP</span><span class="pct">62</span></div>
        <div class="zone-cell heat-2"><span class="n">KNEE MIN</span><span class="pct">74</span></div>
        <div class="zone-cell heat-3"><span class="n">RE-EXT</span><span class="pct">91</span></div>
      </div>
      <div class="zone-axes"><span>rotation</span><span>knee drive</span></div>
      <div class="spray-stat">
        <div><div class="v">94</div><div class="l">peak sep — top sub-metric</div></div>
        <div><div class="v">83</div><div class="l">9-cell weighted average</div></div>
        <div><div class="v">62</div><div class="l">knee @ FP — focus area</div></div>
      </div>
    </div>

    <div class="card spray">
      <div class="card-eyebrow">Phase timing spectrum · vs MLB band</div>
      <h3 class="card-title">Your <span class="ital">tempo</span>, phase by phase.</h3>
      <svg viewBox="0 0 540 380" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bandGrad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%"  stop-color="rgba(230,69,48,0.05)"/>
            <stop offset="50%" stop-color="rgba(230,69,48,0.22)"/>
            <stop offset="100%" stop-color="rgba(230,69,48,0.05)"/>
          </linearGradient>
        </defs>

        <!-- horizontal phase rows, each row is a phase interval; -->
        <!-- the red band is the MLB reference range, the bone dot is the user. -->
        <!-- 5 phases: Load→FP, FP→Launch, Launch→Contact, Contact→PeakRot, PeakRot→Finish -->
        <!-- y positions: 50, 110, 170, 230, 290 -->
        <!-- x range: 60 (start) to 480 (end). values shown to scale 0..1000 ms -->

        <!-- phase 1: Load → Foot plant -->
        <g>
          <text class="field-text" x="60"  y="36">LOAD → FOOT PLANT</text>
          <text class="field-text" x="480" y="36" text-anchor="end">496 ms · MLB 488 ± 60</text>
          <line x1="60" y1="50" x2="480" y2="50" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <!-- MLB band 428-548 ms → scaled across x60..x480 with 1000ms = 420px → x = 60 + (ms/1000)*420 -->
          <rect x="240" y="44" width="50" height="12" rx="2" fill="url(#bandGrad)" stroke="rgba(230,69,48,0.5)" stroke-width="0.8"/>
          <!-- user dot at 496 ms -->
          <line x1="268" y1="42" x2="268" y2="58" stroke="#F4EFE6" stroke-width="1.4"/>
          <circle cx="268" cy="50" r="4.5" fill="#F4EFE6"/>
        </g>

        <!-- phase 2: Foot plant → Launch -->
        <g>
          <text class="field-text" x="60"  y="96">FOOT PLANT → LAUNCH</text>
          <text class="field-text" x="480" y="96" text-anchor="end">156 ms · MLB 171 ± 25</text>
          <line x1="60" y1="110" x2="480" y2="110" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <rect x="121" y="104" width="22" height="12" rx="2" fill="url(#bandGrad)" stroke="rgba(230,69,48,0.5)" stroke-width="0.8"/>
          <line x1="125" y1="102" x2="125" y2="118" stroke="#F4EFE6" stroke-width="1.4"/>
          <circle cx="125" cy="110" r="4.5" fill="#F4EFE6"/>
        </g>

        <!-- phase 3: Launch → Contact -->
        <g>
          <text class="field-text" x="60"  y="156">LAUNCH → CONTACT</text>
          <text class="field-text" x="480" y="156" text-anchor="end">184 ms · MLB 175 ± 22</text>
          <line x1="60" y1="170" x2="480" y2="170" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <rect x="124" y="164" width="22" height="12" rx="2" fill="url(#bandGrad)" stroke="rgba(230,69,48,0.5)" stroke-width="0.8"/>
          <line x1="137" y1="162" x2="137" y2="178" stroke="#E8C170" stroke-width="1.6"/>
          <circle cx="137" cy="170" r="5" fill="#E8C170"/>
        </g>

        <!-- phase 4: Contact → Peak rotation -->
        <g>
          <text class="field-text" x="60"  y="216">CONTACT → PEAK ROTATION</text>
          <text class="field-text" x="480" y="216" text-anchor="end">122 ms · MLB 119 ± 18</text>
          <line x1="60" y1="230" x2="480" y2="230" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <rect x="105" y="224" width="20" height="12" rx="2" fill="url(#bandGrad)" stroke="rgba(230,69,48,0.5)" stroke-width="0.8"/>
          <line x1="111" y1="222" x2="111" y2="238" stroke="#F4EFE6" stroke-width="1.4"/>
          <circle cx="111" cy="230" r="4.5" fill="#F4EFE6"/>
        </g>

        <!-- phase 5: Peak rotation → Finish -->
        <g>
          <text class="field-text" x="60"  y="276">PEAK ROTATION → FINISH</text>
          <text class="field-text" x="480" y="276" text-anchor="end">244 ms · MLB 265 ± 32</text>
          <line x1="60" y1="290" x2="480" y2="290" stroke="rgba(244,239,230,0.06)" stroke-width="1"/>
          <rect x="158" y="284" width="28" height="12" rx="2" fill="url(#bandGrad)" stroke="rgba(230,69,48,0.5)" stroke-width="0.8"/>
          <line x1="162" y1="282" x2="162" y2="298" stroke="#F4EFE6" stroke-width="1.4"/>
          <circle cx="162" cy="290" r="4.5" fill="#F4EFE6"/>
        </g>

        <!-- timeline ruler -->
        <g stroke="rgba(244,239,230,0.10)" stroke-dasharray="2 4">
          <line x1="60"  y1="320" x2="60"  y2="358"/>
          <line x1="186" y1="320" x2="186" y2="358"/>
          <line x1="312" y1="320" x2="312" y2="358"/>
          <line x1="438" y1="320" x2="438" y2="358"/>
        </g>
        <g font-family="Geist Mono, monospace" font-size="9.5" fill="#565A62" letter-spacing="0.12em">
          <text x="60"  y="358">0 ms</text>
          <text x="186" y="358">300</text>
          <text x="312" y="358">600</text>
          <text x="438" y="358" text-anchor="end">900 ms</text>
        </g>
      </svg>

      <div class="spray-legend">
        <span><span class="dot" style="background:#F4EFE6"></span>You · this swing</span>
        <span><span class="dot" style="background:rgba(230,69,48,0.55);border:1px solid rgba(230,69,48,0.5)"></span>MLB ref range</span>
        <span><span class="dot" style="background:#E8C170"></span>Citrine = sweet spot</span>
      </div>
      <div class="spray-stat">
        <div><div class="v">1,202 ms</div><div class="l">total swing window</div></div>
        <div><div class="v">96.9%</div><div class="l">phase-alignment score</div></div>
        <div><div class="v">3 of 5</div><div class="l">phases inside MLB band</div></div>
      </div>
    </div>
  </div>

  <!-- VELOCITY LADDER -->
  <div class="card ladder-card fade-in d9 m-hide" style="margin-top:28px;">
    <div class="ladder">
      <div class="ladder-vis" style="padding-bottom: 24px;">
        <div class="bar" style="height: 38%;"><span class="v">62</span><span class="wk">WK 1</span></div>
        <div class="bar" style="height: 46%;"><span class="v">66</span><span class="wk">WK 2</span></div>
        <div class="bar" style="height: 52%;"><span class="v">71</span><span class="wk">WK 3</span></div>
        <div class="bar" style="height: 58%;"><span class="v">76</span><span class="wk">WK 4</span></div>
        <div class="bar" style="height: 64%;"><span class="v">80</span><span class="wk">WK 5</span></div>
        <div class="bar" style="height: 73%;"><span class="v">83</span><span class="wk">WK 6</span></div>
        <div class="bar" style="height: 84%;"><span class="v">87</span><span class="wk">WK 7</span></div>
        <div class="bar peak" style="height: 100%;"><span class="v">91</span><span class="wk">WK 8</span></div>
      </div>
      <div class="ladder-narrative">
        <div class="card-eyebrow">Match score · 8 wk progression · vs MLB match</div>
        <div class="num">+ <span class="ital">29</span> pts</div>
        <div class="label">composite gain over 8 weeks</div>
        <div class="body">
          You started this block at a <span class="em">62%</span> match against your MLB match; you sit at <span class="em">91%</span> tonight — a climb out of the "decent match" band into "strong match" territory. Most of the gain came from <span class="em">hip-shoulder separation</span> and <span class="em">launch-to-contact timing</span>; knee drive is the next lever.
        </div>
      </div>
    </div>
  </div>



  <!-- 12 WEEKS OF PROGRESS · long-term development story -->
  <div class="section-head fade-in d10 m-hide">
    <div>
      <div class="section-eyebrow">§ 09 · Long-Term Development</div>
      <h2 class="section-title">The last <span class="ital">twelve</span> weeks.</h2>
    </div>
    <div class="section-sub">Your full development arc · since Feb 23</div>
  </div>

  <div class="progress-12 fade-in d10 m-hide">
    <!-- six hero KPIs strip -->
    <div class="progress-stats">
      <div class="progress-stat">
        <span class="lbl">Swings analyzed</span>
        <div class="num">214</div>
        <span class="sub">across 12 weeks</span>
      </div>
      <div class="progress-stat">
        <span class="lbl">Active days</span>
        <div class="num">37</div>
        <span class="sub">of 84 possible</span>
      </div>
      <div class="progress-stat">
        <span class="lbl">Current streak</span>
        <div class="num"><span class="gold">17</span><span class="small">d</span></div>
        <span class="sub">longest of season</span>
      </div>
      <div class="progress-stat">
        <span class="lbl">Personal records</span>
        <div class="num"><span class="gold">6</span></div>
        <span class="sub">2 unlocked this week</span>
      </div>
      <div class="progress-stat">
        <span class="lbl">Edge Score · 12 wk Δ</span>
        <div class="num">+ <span class="gold">29</span></div>
        <span class="sub">59 → 88 · ELITE tier</span>
      </div>
      <div class="progress-stat">
        <span class="lbl">MLB Match · 12 wk Δ</span>
        <div class="num">+ <span class="gold">17</span></div>
        <span class="sub">74% → 91% · Mookie Betts</span>
      </div>
    </div>

    <!-- 12-week trend chart -->
    <div class="progress-trend-card">
      <div class="progress-trend-head">
        <div>
          <div class="card-eyebrow">Edge Score &amp; MLB Match · 12 weeks</div>
          <h3 class="card-title">The <span class="ital">climb.</span></h3>
        </div>
        <div class="progress-trend-tag">
          <div class="row"><span class="sw" style="background:#F4EFE6"></span>Edge Score</div>
          <div class="row"><span class="sw" style="background:#E64530"></span>MLB Match %</div>
          <div class="row"><span class="sw" style="background:var(--gold)"></span>Personal records</div>
        </div>
      </div>

      <svg viewBox="0 0 1280 280" width="100%" height="280" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="edgeAreaGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stop-color="rgba(244,239,230,0.18)"/>
            <stop offset="100%" stop-color="rgba(244,239,230,0)"/>
          </linearGradient>
          <linearGradient id="matchAreaGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"  stop-color="rgba(230,69,48,0.20)"/>
            <stop offset="100%" stop-color="rgba(230,69,48,0)"/>
          </linearGradient>
        </defs>
        <!-- y gridlines -->
        <g stroke="rgba(244,239,230,0.05)" stroke-dasharray="2 4">
          <line x1="0" y1="40"  x2="1280" y2="40"/>
          <line x1="0" y1="100" x2="1280" y2="100"/>
          <line x1="0" y1="160" x2="1280" y2="160"/>
          <line x1="0" y1="220" x2="1280" y2="220"/>
        </g>
        <!-- PR vertical markers -->
        <g>
          <line x1="200" y1="0" x2="200" y2="280" stroke="rgba(232,193,112,0.18)" stroke-dasharray="2 4"/>
          <line x1="430" y1="0" x2="430" y2="280" stroke="rgba(232,193,112,0.18)" stroke-dasharray="2 4"/>
          <line x1="640" y1="0" x2="640" y2="280" stroke="rgba(232,193,112,0.18)" stroke-dasharray="2 4"/>
          <line x1="900" y1="0" x2="900" y2="280" stroke="rgba(232,193,112,0.18)" stroke-dasharray="2 4"/>
          <line x1="1080" y1="0" x2="1080" y2="280" stroke="rgba(232,193,112,0.18)" stroke-dasharray="2 4"/>
          <line x1="1200" y1="0" x2="1200" y2="280" stroke="rgba(232,193,112,0.32)" stroke-dasharray="2 4"/>
        </g>
        <!-- Edge Score area+line: 59 → 88 over 12 weeks -->
        <path d="M0,200 C 70,196 140,188 210,182 S 350,170 420,160 S 560,148 630,140 S 770,125 840,118 S 980,105 1050,92 S 1190,72 1280,60 L1280,280 L0,280 Z" fill="url(#edgeAreaGrad)"/>
        <path d="M0,200 C 70,196 140,188 210,182 S 350,170 420,160 S 560,148 630,140 S 770,125 840,118 S 980,105 1050,92 S 1190,72 1280,60" fill="none" stroke="#F4EFE6" stroke-width="2"/>
        <!-- MLB Match area+line: 74% → 91% -->
        <path d="M0,168 C 80,166 160,162 240,158 S 380,150 460,144 S 600,134 680,128 S 820,118 900,108 S 1060,92 1140,80 S 1240,68 1280,60 L1280,280 L0,280 Z" fill="url(#matchAreaGrad)" opacity="0.7"/>
        <path d="M0,168 C 80,166 160,162 240,158 S 380,150 460,144 S 600,134 680,128 S 820,118 900,108 S 1060,92 1140,80 S 1240,68 1280,60" fill="none" stroke="#E64530" stroke-width="2" opacity="0.92"/>
        <!-- PR pins as gold dots on Edge Score line -->
        <g>
          <circle cx="200"  cy="182" r="5" fill="#E8C170"/>
          <circle cx="430"  cy="160" r="5" fill="#E8C170"/>
          <circle cx="640"  cy="140" r="5" fill="#E8C170"/>
          <circle cx="900"  cy="105" r="5" fill="#E8C170"/>
          <circle cx="1080" cy="82" r="5" fill="#E8C170"/>
          <circle cx="1200" cy="65" r="6" fill="#E8C170"/>
          <circle cx="1200" cy="65" r="11" fill="none" stroke="#E8C170" opacity="0.4"/>
        </g>
        <!-- x labels: 12 weeks -->
        <g font-family="Geist Mono, monospace" font-size="9.5" fill="#565A62" letter-spacing="0.10em">
          <text x="0"    y="272">WK 1 · FEB 23</text>
          <text x="320"  y="272">WK 4 · MAR 16</text>
          <text x="640"  y="272">WK 7 · APR 06</text>
          <text x="960"  y="272">WK 10 · APR 27</text>
          <text x="1224" y="272" text-anchor="end">WK 12 · MAY 17</text>
        </g>
      </svg>
    </div>

    <!-- milestones row: 4 badges earned over 12 weeks -->
    <div class="milestones-row">
      <div class="milestone">
        <div class="ico">★</div>
        <div class="info">
          <div class="name">Forty-Two Club</div>
          <div class="when">May 17 · this week</div>
          <div class="detail">Hip-shoulder sep ≥ 42°</div>
        </div>
      </div>
      <div class="milestone">
        <div class="ico">◇</div>
        <div class="info">
          <div class="name">17-day streak</div>
          <div class="when">May 17 · this week</div>
          <div class="detail">Longest of the season</div>
        </div>
      </div>
      <div class="milestone">
        <div class="ico">◈</div>
        <div class="info">
          <div class="name">Strong-match band</div>
          <div class="when">Apr 29 · wk 10</div>
          <div class="detail">Match score crossed 80%</div>
        </div>
      </div>
      <div class="milestone">
        <div class="ico">∮</div>
        <div class="info">
          <div class="name">100 swings analyzed</div>
          <div class="when">Apr 22 · wk 9</div>
          <div class="detail">First century cut</div>
        </div>
      </div>
    </div>
  </div>

  <!-- DRILL PRESCRIPTION · § 10 · the personalized action plan -->
  <div class="section-head fade-in d11 m-hide">
    <div>
      <div class="section-eyebrow">§ 10 · Drill Prescription</div>
      <h2 class="section-title">Three <span class="ital">drills</span>, prescribed.</h2>
    </div>
    <div class="section-sub">AI-generated from your top gap categories · refreshed after each session</div>
  </div>

  <div class="coach-grid fade-in d11 m-hide">
    <div class="coach-card">
      <div class="num">01</div>
      <div class="why">▲ flatten bat path · −3° steep entry</div>
      <div class="drill">Early hand-set <span class="ital">tee work.</span></div>
      <div class="target">Target · barrel "tips" toward ball <span class="v">before front foot lands</span></div>
      <p class="body">Set the tee middle-up. Cock your hands to launch-position before the leg lift starts. Feel the barrel tip toward the ball before the front foot plants.</p>
      <div class="cta-row">
        <a class="cta" href="#">Open drill →</a>
        <span class="reps">3 × 8 swings</span>
      </div>
    </div>
    <div class="coach-card">
      <div class="num">02</div>
      <div class="why">▲ lock in 42° hip-shoulder separation</div>
      <div class="drill">Walking stride <span class="ital">hip-leads.</span></div>
      <div class="target">Target · hip-Sh sep peak <span class="v">≥ 42° for 5 of 8 reps</span></div>
      <p class="body">Replicate your Tuesday-night sequence. Walk into a slow stride and stall at foot plant for a half-second before launching. Builds muscle memory for the separation peak.</p>
      <div class="cta-row">
        <a class="cta" href="#">Open drill →</a>
        <span class="reps">3 × 6 reps</span>
      </div>
    </div>
    <div class="coach-card">
      <div class="num">03</div>
      <div class="why">▲ tighten knee re-extension · 74 → 90+</div>
      <div class="drill">Overload / underload <span class="ital">set.</span></div>
      <div class="target">Target · knee re-ext score <span class="v">≥ 90 by next session</span></div>
      <p class="body">2 swings with a +6 oz weighted bat, 2 with a −6 oz speed bat, 2 game bats. Cue: drive the front knee back into extension through contact.</p>
      <div class="cta-row">
        <a class="cta" href="#">Open drill →</a>
        <span class="reps">3 full rounds</span>
      </div>
    </div>
  </div>

  <!-- SESSION LEDGER (standalone, full width) -->
  <div class="section-head fade-in d11 m-hide">
    <div>
      <div class="section-eyebrow">§ 11 · Session Ledger</div>
      <h2 class="section-title">The <span class="ital">paper trail.</span></h2>
    </div>
    <div class="section-sub">last 5 cuts · trailing 14d</div>
  </div>

  <div class="card fade-in d11 m-hide">
    <div style="margin-top:4px;">
      <div class="ledger-row pr">
        <span class="date">Sun · May 17</span><span class="swings">12 sw</span>
        <span class="top-metric">Match <span class="v">91%</span> · sep peak <span class="v">42°</span></span>
        <span class="grade">A−</span><span class="mood">🔥</span>
      </div>
      <div class="ledger-row">
        <span class="date">Fri · May 15</span><span class="swings">8 sw</span>
        <span class="top-metric">Match <span class="v">84%</span> · launch→contact <span class="v">192 ms</span></span>
        <span class="grade">B+</span><span class="mood">💪</span>
      </div>
      <div class="ledger-row pr">
        <span class="date">Wed · May 13</span><span class="swings">15 sw</span>
        <span class="top-metric">Sep peak <span class="v">42°</span> · knee re-ext <span class="v">26°</span></span>
        <span class="grade">A−</span><span class="mood">⚡</span>
      </div>
      <div class="ledger-row">
        <span class="date">Mon · May 11</span><span class="swings">7 sw</span>
        <span class="top-metric">Match <span class="v">78%</span> · head drift <span class="v">0.22</span></span>
        <span class="grade">B</span><span class="mood">🟡</span>
      </div>
      <div class="ledger-row">
        <span class="date">Sat · May 09</span><span class="swings">10 sw</span>
        <span class="top-metric">Match <span class="v">82%</span> · hip rot @ contact <span class="v">48°</span></span>
        <span class="grade">B+</span><span class="mood">👀</span>
      </div>
    </div>
  </div>
  <!-- ACHIEVEMENTS RAIL -->
  <div class="section-head fade-in d11 m-hide">
    <div>
      <div class="section-eyebrow">§ 12 · Recent Unlocks</div>
      <h2 class="section-title">Recent <span class="ital">unlocks.</span></h2>
    </div>
    <div class="section-sub">2 new this week · next badge in 6 swings</div>
  </div>

  <div class="rail fade-in d11 m-hide">
    <div class="medal gold">
      <div class="icon">★</div>
      <div class="name">Forty-two club</div>
      <div class="when">Unlocked · May 17 · hip-sh sep ≥ 42°</div>
    </div>
    <div class="medal gold">
      <div class="icon">◇</div>
      <div class="name">17-day streak</div>
      <div class="when">Unlocked · May 17</div>
    </div>
    <div class="medal progress">
      <div class="icon">∮</div>
      <div class="name">Strong match band</div>
      <div class="when">Hold ≥ 75% match for 5 straight sessions · 4 / 5</div>
      <div class="bar"><div class="fill" style="width:80%"></div></div>
      <div class="pct">80% complete</div>
    </div>
    <div class="medal progress locked">
      <div class="icon">⌖</div>
      <div class="name">500 lifetime swings</div>
      <div class="when">416 of 500</div>
      <div class="bar"><div class="fill" style="width:83%"></div></div>
      <div class="pct">83% — 84 swings to go</div>
    </div>
  </div>

  <!-- PRICING BAND · 3 tiers (Solo / Family / Coach Pro) -->
  <input type="radio" name="bill" id="bill-m" class="bill-radio">
  <input type="radio" name="bill" id="bill-y" class="bill-radio" checked>
  <section class="pricing-band fade-in d12">

    <div class="pricing-head">
      <div class="pricing-head-meta">
        <div class="pricing-eyebrow">§ 13 · Edge Pro Upsell</div>
        <h2 class="pricing-title">Lock in your <span class="ital">edge.</span></h2>
        <p class="pricing-sub">Three tiers. One source of truth. Pick the seat count that matches your household or roster — cancel any time.</p>
      </div>
    </div>

    <div class="free-strip">
      <span class="lead">
        <span class="badge">Start Free</span>
        <span><span class="v">{{FREE_SWING_LIMIT}}</span> swing analyses included · no card required</span>
      </span>
      <span class="trail">Upgrade anytime · keep your full swing history</span>
    </div>

    <div class="pricing-toggle-row">
      <div class="tier-toggle">
        <label for="bill-m">Monthly</label>
        <label for="bill-y">Annual <span class="save-badge">save {{SOLO_PRO_SAVE_PCT}}</span></label>
      </div>
    </div>

    <!-- Annual price grid (default visible) -->
    <div class="tiers-row tiers-annual">
      <div class="tier-card">
        <div class="tier-head">
          <div class="tier-name">{{SOLO_PRO_NAME}}</div>
          <div class="tier-seats">{{SOLO_PRO_SEATS}} seat</div>
        </div>
        <div class="tier-tagline">{{SOLO_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{SOLO_PRO_ANNUAL_NUM}}</span><span class="per">/yr</span>
        </div>
        <div class="tier-price-sub">or {{SOLO_PRO_ANNUAL_EQUIV}}/mo billed annually</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>

      <div class="tier-card featured">
        <div class="tier-head">
          <div class="tier-name">{{FAMILY_PRO_NAME}}</div>
          <div class="tier-seats">{{FAMILY_PRO_SEATS}} seats</div>
        </div>
        <div class="tier-tagline">{{FAMILY_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{FAMILY_PRO_ANNUAL_NUM}}</span><span class="per">/yr</span>
        </div>
        <div class="tier-price-sub">or {{FAMILY_PRO_ANNUAL_EQUIV}}/mo billed annually</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
          <li class="extra">Up to 4 family member accounts</li>
          <li class="extra">Each member gets their own swing history</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>

      <div class="tier-card">
        <div class="tier-head">
          <div class="tier-name">{{COACH_PRO_NAME}}</div>
          <div class="tier-seats">{{COACH_PRO_SEATS}} seats</div>
        </div>
        <div class="tier-tagline">{{COACH_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{COACH_PRO_ANNUAL_NUM}}</span><span class="per">/yr</span>
        </div>
        <div class="tier-price-sub">or {{COACH_PRO_ANNUAL_EQUIV}}/mo billed annually</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
          <li class="extra">Up to 20 player rosters</li>
          <li class="extra">Read-only views of each player's swings</li>
          <li class="extra">Priority support</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>
    </div>

    <!-- Monthly price grid -->
    <div class="tiers-row tiers-monthly">
      <div class="tier-card">
        <div class="tier-head">
          <div class="tier-name">{{SOLO_PRO_NAME}}</div>
          <div class="tier-seats">{{SOLO_PRO_SEATS}} seat</div>
        </div>
        <div class="tier-tagline">{{SOLO_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{SOLO_PRO_MONTHLY_NUM}}</span><span class="per">/mo</span>
        </div>
        <div class="tier-price-sub is-assurance">billed monthly · cancel anytime</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>

      <div class="tier-card featured">
        <div class="tier-head">
          <div class="tier-name">{{FAMILY_PRO_NAME}}</div>
          <div class="tier-seats">{{FAMILY_PRO_SEATS}} seats</div>
        </div>
        <div class="tier-tagline">{{FAMILY_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{FAMILY_PRO_MONTHLY_NUM}}</span><span class="per">/mo</span>
        </div>
        <div class="tier-price-sub is-assurance">billed monthly · cancel anytime</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
          <li class="extra">Up to 4 family member accounts</li>
          <li class="extra">Each member gets their own swing history</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>

      <div class="tier-card">
        <div class="tier-head">
          <div class="tier-name">{{COACH_PRO_NAME}}</div>
          <div class="tier-seats">{{COACH_PRO_SEATS}} seats</div>
        </div>
        <div class="tier-tagline">{{COACH_PRO_TAGLINE}}</div>
        <div class="tier-price">
          <span class="dollar">$</span><span class="num">{{COACH_PRO_MONTHLY_NUM}}</span><span class="per">/mo</span>
        </div>
        <div class="tier-price-sub is-assurance">billed monthly · cancel anytime</div>
        <ul class="tier-features">
          <li>Unlimited swing analyses</li>
          <li>Full personalized drill plan</li>
          <li>Swing video saved to your history</li>
          <li>Full Development Tracker (XP, streaks, achievements)</li>
          <li>Rewards Roadmap (incl. limited-edition hoodie at 180d)</li>
          <li>PDF report export</li>
          <li>Side-by-side swing comparisons</li>
          <li>Full MLB comp library</li>
          <li class="extra">Up to 20 player rosters</li>
          <li class="extra">Read-only views of each player's swings</li>
          <li class="extra">Priority support</li>
        </ul>
        <a class="tier-cta" href="/?page=pricing">Start free trial ↗</a>
      </div>
    </div>

  </section>

  <!-- METHODOLOGY NOTE -->
  <div class="methodology">
    <div class="methodology-body">
      <div class="methodology-eyebrow">§ 14 · What We Measure</div>
      <p>Everything on this dashboard is derived from <span class="em">MediaPipe pose detection</span> on your uploaded video — no Blast Motion, HitTrax, Rapsodo, or radar hardware required. Real measurements: <span class="em">hip-shoulder separation</span> (°), <span class="em">hip rotation</span> (°), <span class="em">front-knee angle &amp; re-extension</span> (°), <span class="em">head drift</span> (torso-normalized), and <span class="em">phase intervals</span> (ms: load → foot plant → launch → contact → peak rotation → finish). The <span class="em-gold">Match Score</span> and <span class="em-gold">Edge Score</span> are composite indices built from those measurements compared against your assigned MLB match. We deliberately do not estimate bat speed, exit velocity, or projected distance from video — those require radar or sensors we don't pretend to have.</p>
    </div>
    <img class="methodology-mark" src="{{LOGO_DATA_URI}}" alt="" aria-hidden="true">
  </div>

  <!-- FOOTER -->
  <footer class="footer">
    <div class="foot-quote">
      "Hitting is timing. Pitching is upsetting timing."
      <span class="by">— Warren Spahn</span>
    </div>
    <div class="foot-block">
      <div class="label">Next session</div>
      <div class="next-date">Tue · May 19</div>
      <div class="sub">8:00 PM · cage at home · tee + flips</div>
    </div>
    <div class="foot-block" style="text-align:right;">
      <div class="label">Report ID</div>
      <div class="next-date" style="font-family: var(--mono); font-size: 17px; letter-spacing: 0.06em;">BL-2026-W20-LC</div>
      <div class="sub">Mock data · design exploration only</div>
    </div>
  </footer>

  <div class="foot-tiny">
    BarrelLabs &nbsp;·&nbsp; Edge mock dashboard &nbsp;·&nbsp; v 0.2 ·
    generated for design review &nbsp;·&nbsp; not connected to production data
  </div>
</div>
<script>
/* Auto-height bridge — removes the nested-iframe scrollbar so the
   Streamlit page is the ONLY scroll container and the shared masthead
   scrolls naturally with the content. Measures real rendered height
   and pushes it up through every channel a Streamlit components.html
   iframe can honour (setFrameHeight API, the streamlit:setFrameHeight
   postMessage, and a direct frameElement fallback). All wrapped in
   try/catch so an opaque-origin sandbox can never throw. */
(function () {
  function contentHeight() {
    var d = document;
    return Math.ceil(Math.max(
      d.body ? d.body.scrollHeight : 0,
      d.body ? d.body.offsetHeight : 0,
      d.documentElement ? d.documentElement.scrollHeight : 0,
      d.documentElement ? d.documentElement.offsetHeight : 0
    ));
  }
  var last = 0;
  function push() {
    var h = contentHeight();
    if (!h || Math.abs(h - last) < 2) return;
    last = h;
    try { if (window.Streamlit && Streamlit.setFrameHeight) Streamlit.setFrameHeight(h); } catch (e) {}
    try {
      window.parent.postMessage(
        { isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: h }, "*"
      );
    } catch (e) {}
    try {
      if (window.frameElement) {
        window.frameElement.style.height = h + "px";
        window.frameElement.setAttribute("scrolling", "no");
      }
    } catch (e) {}
  }
  window.addEventListener("load", push);
  window.addEventListener("resize", push);
  try { if (window.ResizeObserver) new ResizeObserver(push).observe(document.body); } catch (e) {}
  [60, 200, 600, 1200, 2500].forEach(function (t) { setTimeout(push, t); });
  push();
})();
</script>
</body>
</html>"""

components.html(DASHBOARD_HTML, height=5800, scrolling=False)
