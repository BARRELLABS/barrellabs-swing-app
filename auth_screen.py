"""BarrelLabs · Premium authentication experience (v3 — Telemetry-Editorial).

What changed from v2
--------------------
The user hated the Sign In / Create Account toggle pill at the top of
the card. v3 kills it entirely.

  • The mode (login / signup) is signaled by a small mono-caps STATE
    LOZENGE in the card's top-right (`· ACCESS · MODE 01` /
    `· NEW MEMBER · MODE 02`) — non-interactive, just a label that
    reflects current mode.
  • Mode switching happens via ONE quiet line at the bottom of the
    card: "New to BarrelLabs? **Create your account →**" (or the
    inverse). Apple / Stripe / Linear pattern — one clear primary
    purpose, no toggle competing for attention.

Plus a substantial visual upgrade everywhere else:

  • Card chrome: industrial NOTCHED CORNER at top-right via clip-path
    (Ferrari/F1 vibe). Top edge is no longer a gradient stroke — it's
    a TELEMETRY TICK STRIP (small vertical hairlines + one active
    gold tick). Registration-mark "+" ornament in the bottom-left.
  • Hero feature ladder collapsed into a 2x2 TELEMETRY GRID. Each
    micro-card has a mono-caps label, an italic-serif value, and a
    thin progress bar that animates on load.
  • SESSION-ID kicker at the top of the hero
    (`SESSION 04.2027 · PERFORMANCE LAB`) — lab-notebook feel.
  • LIVE STATUS TICKER at the bottom of the hero — horizontal marquee
    scrolling fake-but-feels-real stats: "ANALYZER ONLINE · 23 SWINGS
    PROCESSED TODAY · 1,247 PRO REFS LOADED · MLB SIM% 87 · …"
  • Inline SVG SWING-TRAJECTORY PATH behind the hero content, drawing
    itself on load via stroke-dashoffset animation. Gold→red stroke
    gradient. The single "wow" decorative element.
  • Stagger fade-up on load (eyebrow → title → sub → grid →
    testimonial → ticker), driven by CSS animation-delay.
  • CTA gets a subtle radial-pulse hover ripple via pseudo-element.
  • Forgot-password link moved beneath the CTA inside the form, no
    longer a separate ghost button — tighter form rhythm.
  • Typography pushed harder on the mono-caps treatment everywhere
    (labels, ticker, kickers, telemetry-grid labels, mode lozenge).

Wiring (unchanged)
------------------
- player_storage.authenticate(email, password)
- player_storage.create_account(name, email, password, handedness,
                                height_in, weight_lb)
- auth.request_password_reset / consume_recovery_url /
  consume_recovery_token_hash / update_password
- Session flags: st.session_state.user, auth_mode, recovery_mode
- Recovery JS hash→query shim lives in app.py (untouched)
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

import streamlit as st

try:
    from bl_edge_chrome import _logo_data_uri as _bl_logo_data_uri
except Exception:  # pragma: no cover
    def _bl_logo_data_uri() -> str:
        return ""


# =====================================================================
# CSS
# =====================================================================
_AUTH_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600;700&display=swap');

/* ============ Tokens ============ */
.st-key-auth_root {
  --au-ink:        #0A0B0E;
  --au-ink-2:      #0D0F13;
  --au-ink-3:      #14171C;
  --au-ink-4:      #1A1E25;
  --au-bone:       #F4EFE6;
  --au-bone-warm:  #F8F2E0;
  --au-bone-80:    rgba(244,239,230,0.82);
  --au-bone-60:    rgba(244,239,230,0.58);
  --au-bone-40:    rgba(244,239,230,0.34);
  --au-bone-20:    rgba(244,239,230,0.16);
  --au-glass-1:    rgba(255,255,255,0.025);
  --au-glass-2:    rgba(255,255,255,0.045);
  --au-glass-3:    rgba(255,255,255,0.08);
  --au-line:       rgba(244,239,230,0.075);
  --au-line-hi:    rgba(244,239,230,0.14);
  --au-line-hi-2:  rgba(244,239,230,0.22);
  --au-red:        #E64530;
  --au-red-deep:   #C53620;
  --au-red-soft:   rgba(230,69,48,0.12);
  --au-red-line:   rgba(230,69,48,0.32);
  --au-gold:       #E8C170;
  --au-gold-soft:  rgba(232,193,112,0.12);
  --au-gold-line:  rgba(232,193,112,0.32);
  --au-green:      #4AE38C;
  --au-serif:      'Instrument Serif', 'Fraunces', Georgia, serif;
  --au-sans:       'Geist', -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  --au-mono:       'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --au-r-pill:     999px;
  --au-r-card:     22px;
  --au-r-mid:      14px;
  --au-r-sm:       10px;
  --au-ease-soft:  cubic-bezier(.32,.72,0,1);
  --au-ease-snap:  cubic-bezier(.34,1.4,.64,1);
  --au-ease-cinema: cubic-bezier(.2,.8,.2,1);
}

/* ============ Streamlit chrome erasure ============ */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
  background: #0A0B0E !important;
}
[data-testid="stApp"] {
  background:
    radial-gradient(1200px 800px at 22% 22%, rgba(232,193,112,0.075), transparent 60%),
    radial-gradient(1100px 800px at 78% 78%, rgba(230,69,48,0.055), transparent 60%),
    radial-gradient(1400px 900px at 50% 50%, rgba(20,23,28,0.45), transparent 70%),
    linear-gradient(180deg, #0A0B0E 0%, #0E1116 100%) !important;
  overflow-x: hidden !important;
}
[data-testid="stHeader"],
[data-testid="stAppHeader"],
[data-testid="stToolbar"],
[data-testid="stAppToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stMainMenu"] {
  display: none !important; visibility: hidden !important;
}
[data-testid="stMainBlockContainer"],
.block-container {
  padding: 0 !important; max-width: none !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {
  gap: 0 !important;
}
[data-testid="stMain"] [data-testid="stElementContainer"] {
  margin: 0 !important;
}

/* ============ Cinematic ambient layers ============ */
.auth-grain {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.04; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.6'/></svg>");
}

/* Inline SVG bat-path swing trail. Fixed behind the hero column,
   drawing itself on page load via stroke-dashoffset animation. Gold
   → red linear gradient stroke. Subtle (opacity .35), but enough to
   give the hero column real depth + an unmistakable swing metaphor. */
.au-swingpath {
  position: fixed; left: 0; top: 0; z-index: 0;
  width: 56vw; height: 100vh; pointer-events: none;
  opacity: 0.42;
}
.au-swingpath svg { width: 100%; height: 100%; display: block; }
.au-swingpath path {
  fill: none;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-dasharray: 2400;
  stroke-dashoffset: 2400;
  animation: au-draw 2.4s var(--au-ease-cinema) 0.4s forwards;
}
.au-swingpath .blur {
  stroke-width: 22;
  opacity: 0.45;
  filter: blur(14px);
  animation: au-draw 2.4s var(--au-ease-cinema) 0.4s forwards;
}
.au-swingpath .dot {
  fill: var(--au-gold);
  opacity: 0;
  animation: au-dot 1.4s var(--au-ease-cinema) 2.0s forwards;
}
@keyframes au-draw {
  to { stroke-dashoffset: 0; }
}
@keyframes au-dot {
  0%   { opacity: 0; transform: scale(0.6); }
  60%  { opacity: 1; transform: scale(1.0); }
  100% { opacity: 0.85; transform: scale(1.0); }
}

/* Brand mark, stamped fixed at top-left so it doesn't eat hero
   vertical space. */
.au-brand-fixed {
  position: fixed; top: 28px; left: 36px; z-index: 10;
  display: flex; align-items: center; gap: 12px;
  font-family: var(--au-sans); font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase; font-size: 12px;
  color: var(--au-bone);
}
.au-brand-fixed img {
  width: 30px; height: 30px; object-fit: contain; display: block;
}
.au-brand-fixed .sl { color: #3A3D44; margin: 0 6px; font-weight: 300; }
.au-brand-fixed .ed {
  font-family: var(--au-serif); font-style: italic; font-weight: 400;
  font-size: 16px; letter-spacing: 0; text-transform: none;
  color: #8B8E94;
}

/* Top-right tiny telemetry header — date + LIVE status. Sits in the
   page corner opposite the brand, mirrors the lab-notebook header
   metaphor. */
.au-corner-tele {
  position: fixed; top: 28px; right: 36px; z-index: 10;
  display: flex; align-items: center; gap: 18px;
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
}
.au-corner-tele .live {
  display: inline-flex; align-items: center; gap: 7px;
  color: var(--au-green);
}
.au-corner-tele .live::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--au-green);
  box-shadow: 0 0 8px var(--au-green);
  animation: au-pulse-green 1.8s ease-in-out infinite;
}
@keyframes au-pulse-green {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px var(--au-green); }
  50%      { opacity: 0.4; box-shadow: 0 0 2px var(--au-green); }
}

/* ============ Root grid ============ */
.st-key-auth_root {
  position: relative; z-index: 2;
  min-height: 100vh;
  max-width: 1480px;
  margin: 0 auto;
  display: grid !important;
  grid-template-columns: 54fr 46fr;
  gap: 0;
  color: var(--au-bone);
  font-family: var(--au-sans);
}

/* ============ LEFT HERO PANEL ============ */
.st-key-auth_hero {
  position: relative;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  align-items: flex-start !important;
  padding: 100px 60px 90px !important;
  min-height: 100vh;
  overflow: hidden;
}
.st-key-auth_hero [data-testid="stLayoutWrapper"] {
  width: 100% !important;
}

/* Hero content column */
.au-content {
  position: relative; z-index: 2;
  width: 100%; max-width: 580px;
  display: flex; flex-direction: column;
  gap: 24px;
}

/* Stagger fade-up for hero children */
.au-content > * {
  opacity: 0;
  transform: translateY(14px);
  animation: au-fade-up 760ms var(--au-ease-cinema) forwards;
}
.au-content > *:nth-child(1) { animation-delay: 80ms; }
.au-content > *:nth-child(2) { animation-delay: 200ms; }
.au-content > *:nth-child(3) { animation-delay: 340ms; }
.au-content > *:nth-child(4) { animation-delay: 480ms; }
.au-content > *:nth-child(5) { animation-delay: 620ms; }
.au-content > *:nth-child(6) { animation-delay: 740ms; }
.au-content > *:nth-child(7) { animation-delay: 860ms; }
@keyframes au-fade-up {
  to { opacity: 1; transform: translateY(0); }
}

/* SESSION-ID kicker — lab-notebook header above the eyebrow. */
.au-session-id {
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.28em; text-transform: uppercase;
  color: var(--au-bone-40);
  display: flex; align-items: center; gap: 14px;
}
.au-session-id .sep {
  flex: 0 0 36px; height: 1px; background: var(--au-bone-20);
}
.au-session-id .tag { color: var(--au-bone-60); }

.au-eyebrow {
  font-family: var(--au-mono); font-size: 11px; font-weight: 600;
  letter-spacing: 0.30em; text-transform: uppercase;
  color: var(--au-red);
  display: inline-flex; align-items: center; gap: 9px;
}
.au-eyebrow::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--au-red); box-shadow: 0 0 10px var(--au-red);
  animation: au-pulse-red 2.6s ease-in-out infinite;
}
@keyframes au-pulse-red {
  0%, 100% { opacity: 1;    box-shadow: 0 0 10px var(--au-red); }
  50%      { opacity: 0.45; box-shadow: 0 0 2px var(--au-red); }
}

.au-title {
  font-family: var(--au-serif); font-style: italic;
  font-size: clamp(2.8rem, 4.8vw, 4.8rem); line-height: 0.95;
  letter-spacing: -0.022em; color: var(--au-bone);
  margin: 0;
  font-weight: 400;
}
.au-title .twin {
  background: linear-gradient(90deg,
    var(--au-gold) 0%, #f3d896 30%,
    var(--au-red) 70%, var(--au-red-deep) 100%);
  background-size: 200% 100%;
  -webkit-background-clip: text; background-clip: text;
  color: transparent;
  animation: au-shimmer 6s ease-in-out infinite;
}
@keyframes au-shimmer {
  0%, 100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
.au-title .period { color: var(--au-red); }

.au-sub {
  color: var(--au-bone-60);
  font-family: var(--au-sans);
  font-size: 15px; line-height: 1.55;
  margin: 0; max-width: 520px;
}

/* 2x2 TELEMETRY GRID — replaces the v2 feature ladder. Each cell:
   mono-caps label · italic serif value · thin progress bar. */
.au-tgrid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  margin-top: 6px;
}
.au-tcell {
  position: relative;
  padding: 14px 16px 16px;
  border-radius: var(--au-r-mid);
  background: var(--au-glass-1);
  border: 1px solid var(--au-line);
  transition: border-color .22s var(--au-ease-soft),
              background .22s var(--au-ease-soft);
  overflow: hidden;
}
.au-tcell:hover {
  border-color: var(--au-line-hi);
  background: var(--au-glass-2);
}
.au-tcell .label {
  font-family: var(--au-mono); font-size: 9.5px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.au-tcell .label .id {
  color: var(--au-gold-line); font-weight: 700;
}
.au-tcell .v {
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.65rem; line-height: 1; color: var(--au-bone);
  letter-spacing: -0.012em;
}
.au-tcell .v .u {
  font-family: var(--au-mono); font-style: normal; font-size: 10.5px;
  font-weight: 600; letter-spacing: 0.16em;
  color: var(--au-bone-60); text-transform: uppercase;
  margin-left: 5px;
}
.au-tcell .bar {
  margin-top: 10px;
  height: 2px; border-radius: 1px;
  background: rgba(244,239,230,0.06);
  overflow: hidden; position: relative;
}
.au-tcell .bar::before {
  content: ""; position: absolute;
  left: 0; top: 0; bottom: 0;
  width: var(--bar, 0%);
  background: linear-gradient(90deg, var(--au-gold) 0%, var(--au-red) 100%);
  box-shadow: 0 0 8px -2px var(--au-gold);
  animation: au-bar-grow 1.6s var(--au-ease-cinema) 0.8s both;
  transform: scaleX(0); transform-origin: 0 50%;
}
@keyframes au-bar-grow { to { transform: scaleX(1); } }

/* Testimonial card — same as v2 but slightly tighter padding. */
.au-quote-card {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 16px;
  align-items: center;
  padding: 16px 18px;
  border-radius: var(--au-r-card);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
  border: 1px solid var(--au-line-hi);
  position: relative;
}
.au-quote-card::before {
  content: "“";
  position: absolute; top: -10px; left: 16px;
  font-family: var(--au-serif); font-style: italic;
  font-size: 3.6rem; line-height: 1; color: var(--au-gold);
  opacity: 0.3;
  pointer-events: none;
}
.au-quote-avatar {
  width: 52px; height: 52px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.3rem; color: var(--au-bone-warm);
  background: radial-gradient(120% 80% at 30% 20%,
              rgba(232,193,112,0.34) 0%,
              rgba(230,69,48,0.18) 60%,
              #14171C 100%);
  border: 1px solid var(--au-gold-line);
  flex: none;
}
.au-quote-body { min-width: 0; }
.au-quote-text {
  font-family: var(--au-serif); font-style: italic;
  font-size: 14px; line-height: 1.45;
  color: var(--au-bone-warm);
  margin: 0 0 6px;
}
.au-quote-name {
  font-family: var(--au-mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--au-bone-warm);
  margin: 0;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.au-quote-name .meta {
  color: var(--au-bone-40); font-weight: 500;
  letter-spacing: 0.14em;
}
.au-quote-name .meta::before {
  content: "·"; margin-right: 6px; color: var(--au-bone-40);
}

/* LIVE STATUS TICKER — horizontal marquee at the bottom of the hero
   stack. Mono caps, with a tiny red live dot at the start, and a
   masked fade on each end so items appear/disappear gracefully. */
.au-ticker {
  position: relative;
  margin-top: 6px;
  padding: 12px 0;
  border-top: 1px solid var(--au-line);
  border-bottom: 1px solid var(--au-line);
  overflow: hidden;
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--au-bone-60);
  display: flex; align-items: center; gap: 12px;
  -webkit-mask-image: linear-gradient(90deg,
    transparent 0%, black 8%, black 92%, transparent 100%);
  mask-image: linear-gradient(90deg,
    transparent 0%, black 8%, black 92%, transparent 100%);
}
.au-ticker .live {
  display: inline-flex; align-items: center; gap: 7px;
  color: var(--au-red); flex: none; padding-right: 6px;
  border-right: 1px solid var(--au-line);
  font-weight: 700; letter-spacing: 0.24em;
  padding-right: 16px; margin-right: 4px;
}
.au-ticker .live::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--au-red); box-shadow: 0 0 9px var(--au-red);
  animation: au-pulse-red 1.8s ease-in-out infinite;
}
.au-ticker-track {
  display: inline-flex; gap: 32px;
  white-space: nowrap; flex-shrink: 0;
  animation: au-ticker-scroll 38s linear infinite;
}
.au-ticker-track span {
  display: inline-flex; align-items: center; gap: 8px;
}
.au-ticker-track span .v {
  color: var(--au-bone); font-weight: 700;
  letter-spacing: 0.10em;
}
.au-ticker-track span .v.gold { color: var(--au-gold); }
@keyframes au-ticker-scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* ============ RIGHT AUTH PANEL ============ */
.st-key-auth_panel {
  position: relative;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  align-items: center !important;
  padding: 80px 56px 80px !important;
  min-height: 100vh;
}
.st-key-auth_panel > [data-testid="stLayoutWrapper"] {
  width: 100% !important; max-width: 460px !important;
  flex: 0 0 auto !important;
}

/* ============ AUTH CARD — industrial notched corner, telemetry tick strip top ============ */
.st-key-auth_card {
  position: relative;
  width: 100% !important;
  padding: 36px 36px 28px !important;
  /* Industrial NOTCHED CORNER at top-right.
     The clip-path defines the visible shape; the same path is
     redrawn as a border via the ::after pseudo. */
  --notch: 24px;
  background:
    linear-gradient(180deg, rgba(20,23,28,0.78) 0%, rgba(13,15,19,0.92) 100%) !important;
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  backdrop-filter: blur(22px) saturate(1.2);
  border: 1px solid var(--au-line-hi) !important;
  border-radius: var(--au-r-card) !important;
  box-shadow:
    0 36px 70px -26px rgba(0,0,0,0.7),
    inset 0 1px 0 rgba(255,255,255,0.05),
    0 0 0 1px rgba(232,193,112,0.05) !important;
  overflow: visible !important;
  animation: au-card-rise 900ms var(--au-ease-cinema) 0.2s both;
}
@keyframes au-card-rise {
  from { opacity: 0; transform: translateY(20px) scale(0.985); }
  to   { opacity: 1; transform: translateY(0)    scale(1); }
}

/* Telemetry tick strip at the top edge of the card. A row of tiny
   vertical hairlines with one slightly taller "active" gold tick —
   reads as an F1 timing-gate readout, not a generic gradient stroke. */
.st-key-auth_card::before {
  content: ""; position: absolute;
  left: 28px; right: 28px; top: 0; height: 16px;
  pointer-events: none;
  background-image:
    /* one gold active tick, doubled for emphasis */
    linear-gradient(to bottom, var(--au-gold) 0 9px, transparent 9px),
    /* the row of dim ticks behind it */
    repeating-linear-gradient(to right,
      var(--au-bone-20) 0 1px,
      transparent 1px 14px);
  background-position: 28px 0, 0 0;
  background-size: 1.5px 9px, 14px 6px;
  background-repeat: no-repeat, repeat-x;
  filter: drop-shadow(0 0 5px rgba(232,193,112,0.5));
  opacity: 0.85;
}

/* Registration mark "+" ornament in the bottom-left, lab notebook
   style. */
.st-key-auth_card::after {
  content: ""; position: absolute;
  left: 16px; bottom: 16px;
  width: 10px; height: 10px;
  background-image:
    linear-gradient(to right, transparent 4.5px,
                              var(--au-bone-20) 4.5px,
                              var(--au-bone-20) 5.5px,
                              transparent 5.5px),
    linear-gradient(to bottom, transparent 4.5px,
                               var(--au-bone-20) 4.5px,
                               var(--au-bone-20) 5.5px,
                               transparent 5.5px);
  pointer-events: none;
  opacity: 0.7;
}

/* Inner content spacing */
.st-key-auth_card > [data-testid="stLayoutWrapper"] {
  width: 100% !important;
}
.st-key-auth_card [data-testid="stElementContainer"] {
  margin-top: 0 !important; margin-bottom: 0 !important;
}

/* ============ CARD HEAD ROW — eyebrow + mode lozenge ============
   The mode lozenge replaces the v2 toggle. Sits on the RIGHT side of
   a flex row at the top of the card content; the eyebrow sits on
   the LEFT. Both are subtle mono-caps labels — the right one (mode
   pill) carries a tiny gold dot + numeric step like an F1 timing
   gate readout. */
.au-card-head {
  display: flex !important;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 6px 0 10px;
}
.au-card-eyebrow {
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.26em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin: 0;
  flex: 0 0 auto;
}
.au-mode-pill {
  font-family: var(--au-mono); font-size: 9.5px; font-weight: 700;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-gold);
  display: inline-flex; align-items: center; gap: 7px;
  padding: 0;
  flex: 0 0 auto;
  white-space: nowrap;
}
.au-mode-pill::before {
  content: ""; width: 4px; height: 4px; border-radius: 50%;
  background: var(--au-gold);
  box-shadow: 0 0 7px var(--au-gold);
}
.au-mode-pill .num {
  color: var(--au-bone-40); font-weight: 500;
  margin-left: 6px;
  padding-left: 8px;
  border-left: 1px solid var(--au-bone-20);
}
.au-card-title {
  font-family: var(--au-serif); font-style: italic;
  font-size: 2.1rem; line-height: 0.98;
  letter-spacing: -0.018em; color: var(--au-bone);
  margin: 0 0 6px;
  font-weight: 400;
}
.au-card-sub {
  color: var(--au-bone-60);
  font-size: 13px; line-height: 1.5;
  margin: 0 0 18px;
}

/* ============ Form widgets ============ */
.st-key-auth_card [data-testid="stTextInput"] label,
.st-key-auth_card [data-testid="stNumberInput"] label,
.st-key-auth_card [data-testid="stSelectbox"] label,
.st-key-auth_card [data-testid="stTextArea"] label {
  font-family: var(--au-mono) !important;
  font-size: 9.5px !important;
  letter-spacing: 0.22em !important;
  text-transform: uppercase !important;
  color: var(--au-bone-40) !important;
  font-weight: 600 !important;
  padding-bottom: 5px !important;
}
.st-key-auth_card [data-testid="stTextInput"] input,
.st-key-auth_card [data-testid="stNumberInput"] input,
.st-key-auth_card [data-testid="stTextArea"] textarea {
  background: var(--au-ink-2) !important;
  border: 1px solid var(--au-line-hi) !important;
  border-radius: var(--au-r-mid) !important;
  color: var(--au-bone) !important;
  font-family: var(--au-sans) !important;
  font-size: 14px !important;
  padding: 0.65rem 0.95rem !important;
  transition: border-color .22s var(--au-ease-soft),
              box-shadow .22s var(--au-ease-soft);
  caret-color: var(--au-gold) !important;
  height: 44px !important;
  box-sizing: border-box !important;
}
.st-key-auth_card [data-testid="stTextInput"] input:focus,
.st-key-auth_card [data-testid="stNumberInput"] input:focus,
.st-key-auth_card [data-testid="stTextArea"] textarea:focus {
  border-color: var(--au-gold-line) !important;
  box-shadow:
    0 0 0 3px rgba(232,193,112,0.12),
    inset 0 0 0 1px rgba(232,193,112,0.08) !important;
  outline: none !important;
}
.st-key-auth_card input::placeholder,
.st-key-auth_card textarea::placeholder {
  color: var(--au-bone-40) !important;
  font-family: var(--au-sans) !important;
}
.st-key-auth_card [data-testid="stCheckbox"] label,
.st-key-auth_card [data-testid="stCheckbox"] p {
  font-family: var(--au-sans) !important;
  font-size: 12px !important;
  color: var(--au-bone-80) !important;
  font-weight: 500 !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
}
.st-key-auth_card [data-testid="stNumberInput"] button {
  display: none !important;
}

/* form internals */
.st-key-auth_card [data-testid="stForm"] {
  border: none !important; padding: 0 !important; background: transparent !important;
}
.st-key-auth_card [data-testid="stForm"] [data-testid="stVerticalBlock"] {
  gap: 12px !important;
}
.st-key-auth_card [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
  gap: 10px !important;
}

/* ============ Buttons ============ */
.st-key-auth_card [data-testid="stButton"] button,
.st-key-auth_card [data-testid="stFormSubmitButton"] button {
  font-family: var(--au-sans) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  border-radius: var(--au-r-pill) !important;
  padding: 0.6rem 1.1rem !important;
  background: var(--au-glass-1) !important;
  color: var(--au-bone) !important;
  border: 1px solid var(--au-line-hi) !important;
  transition: transform .22s var(--au-ease-soft),
              border-color .22s var(--au-ease-soft),
              background .22s var(--au-ease-soft),
              box-shadow .22s var(--au-ease-soft);
  min-height: 0 !important; height: auto !important; line-height: 1.2 !important;
}
.st-key-auth_card [data-testid="stButton"] button:hover,
.st-key-auth_card [data-testid="stFormSubmitButton"] button:hover {
  border-color: var(--au-line-hi-2) !important;
  background: var(--au-glass-2) !important;
}

/* Primary CTA — the strongest visual on the page. Now ALSO carries
   a subtle "energy ripple" pseudo that pulses outward on hover. */
.st-key-auth_card [data-testid="stFormSubmitButton"] button[kind="primary"],
.st-key-auth_card [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"],
.st-key-auth_card [data-testid="stFormSubmitButton"] button[data-testid="baseButton-primary"],
.st-key-auth_card [data-testid="stButton"] button[kind="primary"],
.st-key-auth_card [data-testid="stButton"] button[data-testid="stBaseButton-primary"],
.st-key-auth_card [data-testid="stButton"] button[data-testid="baseButton-primary"] {
  background: linear-gradient(180deg, var(--au-red) 0%, var(--au-red-deep) 100%) !important;
  color: #FFFAF2 !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
  border: 1px solid rgba(0,0,0,0.25) !important;
  height: 50px !important;
  padding: 0 24px !important;
  font-size: 13.5px !important;
  position: relative !important;
  overflow: hidden !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.55),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(255,255,255,0.06),
    0 12px 28px -10px rgba(230,69,48,0.52),
    0 1px 0 rgba(255,255,255,0.04) !important;
  margin-top: 6px !important;
}
.st-key-auth_card [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
.st-key-auth_card [data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-1px) !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.85),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(255,255,255,0.08),
    0 18px 36px -10px rgba(230,69,48,0.65),
    0 0 32px -8px rgba(232,193,112,0.38) !important;
}
.st-key-auth_card button:focus-visible {
  outline: none !important;
  box-shadow:
    0 0 0 2px rgba(232,193,112,0.5),
    0 0 0 4px rgba(232,193,112,0.10) !important;
}

/* Inline forgot-password link under the form. Sized as a quiet
   tertiary action, mono caps, centered, no fill. */
.st-key-forgot_btn {
  display: flex !important; justify-content: center !important;
  margin-top: 4px !important;
}
.st-key-forgot_btn [data-testid="stButton"] button {
  background: transparent !important;
  border: none !important;
  color: var(--au-bone-40) !important;
  font-family: var(--au-mono) !important;
  font-size: 10.5px !important;
  letter-spacing: 0.18em !important;
  text-transform: uppercase !important;
  font-weight: 600 !important;
  padding: 6px 12px !important;
  width: auto !important;
}
.st-key-forgot_btn [data-testid="stButton"] button:hover {
  color: var(--au-gold) !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

/* ============ MODE SWITCHER (bottom of card) ============
   The replacement for the hated toggle. A single quiet line. */
.au-mode-switch {
  margin: 18px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--au-line);
  text-align: center;
  font-family: var(--au-sans); font-size: 13px; font-weight: 500;
  color: var(--au-bone-60);
  display: flex; align-items: center; justify-content: center; gap: 6px;
  flex-wrap: wrap;
}
.st-key-mode_switch [data-testid="stButton"] button {
  background: transparent !important;
  border: none !important;
  color: var(--au-bone-warm) !important;
  font-family: var(--au-mono) !important;
  font-size: 10.5px !important;
  letter-spacing: 0.20em !important;
  text-transform: uppercase !important;
  font-weight: 700 !important;
  padding: 6px 4px !important;
  position: relative !important;
  width: auto !important;
  height: auto !important;
}
.st-key-mode_switch [data-testid="stButton"] button:hover {
  color: var(--au-gold) !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.st-key-mode_switch [data-testid="stButton"] button::after {
  content: ""; position: absolute;
  left: 8px; right: 8px; bottom: 2px;
  height: 1px;
  background: linear-gradient(90deg, var(--au-gold), var(--au-red));
  transform: scaleX(0);
  transform-origin: 50% 50%;
  transition: transform .25s var(--au-ease-cinema);
}
.st-key-mode_switch [data-testid="stButton"] button:hover::after {
  transform: scaleX(1);
}
.st-key-mode_switch {
  display: flex !important; justify-content: center !important;
  margin-top: 14px !important;
  padding-top: 14px !important;
  border-top: 1px solid var(--au-line);
}

/* Google placeholder + "or" divider */
.au-divider {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--au-mono); font-size: 9.5px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin: 14px 0 10px;
}
.au-divider::before,
.au-divider::after {
  content: ""; flex: 1 1 auto; height: 1px;
  background: var(--au-line);
}
.au-google {
  width: 100%;
  display: flex; align-items: center; justify-content: center; gap: 10px;
  height: 42px;
  padding: 0 18px;
  border-radius: var(--au-r-pill);
  background: var(--au-glass-1);
  border: 1px solid var(--au-line-hi);
  color: var(--au-bone-80);
  font-family: var(--au-sans); font-weight: 500; font-size: 13px;
  cursor: not-allowed;
  letter-spacing: 0.01em;
  transition: border-color .18s;
}
.au-google:hover { border-color: var(--au-line-hi-2); }
.au-google .ic {
  width: 16px; height: 16px; border-radius: 50%;
  background: linear-gradient(135deg, #4285F4, #34A853 35%, #FBBC05 65%, #EA4335);
  flex: none;
}
.au-google .soon {
  font-family: var(--au-mono); font-size: 9px; font-weight: 700;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40); margin-left: 6px;
}

/* legal */
.au-legal {
  text-align: center;
  margin: 12px 0 0;
  font-family: var(--au-mono); font-size: 9.5px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--au-bone-40);
  line-height: 1.5;
}
.au-legal a { color: var(--au-bone-60); text-decoration: none;
              border-bottom: 1px solid var(--au-line); padding-bottom: 1px; }
.au-legal a:hover { color: var(--au-gold); border-color: var(--au-gold-line); }

/* Alerts */
.st-key-auth_card [data-testid="stAlert"] {
  border-radius: var(--au-r-mid) !important;
  font-family: var(--au-mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.10em !important;
  text-transform: uppercase !important;
  border: 1px solid var(--au-line-hi) !important;
  padding: 0.55rem 0.85rem !important;
  margin: 6px 0 !important;
}
.st-key-auth_card [data-testid="stAlert"] svg { fill: currentColor !important; }

/* ============ Recovery screen ============ */
.st-key-auth_recovery {
  min-height: 100vh;
  display: flex !important; flex-direction: column !important;
  align-items: center !important; justify-content: center !important;
  padding: 64px 24px !important;
}
.st-key-auth_recovery > [data-testid="stLayoutWrapper"] {
  width: 100% !important; max-width: 460px !important;
  flex: 0 0 auto !important;
}

/* ============ Responsive ============ */
@media (max-width: 1180px) {
  .st-key-auth_hero  { padding: 90px 44px 70px !important; }
  .st-key-auth_panel { padding: 64px 44px !important; }
  .au-title { font-size: clamp(2.4rem, 4.4vw, 3.8rem); }
  .au-content { max-width: 540px; }
  .au-swingpath { width: 60vw; }
}
@media (max-width: 980px) {
  .au-brand-fixed { top: 22px; left: 22px; }
  .au-corner-tele { top: 22px; right: 22px; gap: 12px; }
  .au-corner-tele .live { font-size: 9.5px; }
  .au-swingpath { display: none; }
  .st-key-auth_root {
    grid-template-columns: 1fr !important;
    max-width: none !important;
  }
  .st-key-auth_hero {
    min-height: auto !important;
    padding: 88px 28px 40px !important;
    align-items: center !important;
  }
  .au-content { max-width: 580px; align-items: stretch; margin: 0 auto; }
  .au-title { font-size: 2.4rem; }
  .st-key-auth_panel {
    min-height: auto !important;
    padding: 28px 24px 56px !important;
  }
  .st-key-auth_card { padding: 28px 24px 24px !important; }
}
@media (max-width: 640px) {
  .au-brand-fixed { font-size: 11px; }
  .au-brand-fixed .ed { font-size: 14px; }
  .au-corner-tele { display: none; }
  .st-key-auth_hero  { padding: 70px 18px 30px !important; }
  .st-key-auth_panel { padding: 18px 14px 40px !important; }
  .au-title { font-size: 2.0rem; }
  .au-tgrid { grid-template-columns: 1fr; gap: 8px; }
  .au-tcell { padding: 12px 14px 14px; }
  .au-quote-card { grid-template-columns: 44px 1fr; padding: 14px; gap: 12px; }
  .au-quote-avatar { width: 44px; height: 44px; font-size: 1.1rem; }
  .au-ticker { font-size: 9.5px; padding: 10px 0; }
  .st-key-auth_card {
    padding: 26px 20px 22px !important;
    border-radius: 18px !important;
  }
  .au-card-title { font-size: 1.75rem; }
  .au-mode-pill { top: 18px; right: 20px; font-size: 9px; }
}
</style>
"""


# =====================================================================
# Hero HTML
# =====================================================================
def _brand_fixed_html() -> str:
    logo_uri = _bl_logo_data_uri()
    if logo_uri:
        mark = f'<img src="{logo_uri}" alt="BarrelLabs">'
    else:
        mark = ('<span style="width:30px;height:30px;border-radius:50%;'
                'background:#E64530;display:block;"></span>')
    return (
        f'<div class="au-brand-fixed">{mark}'
        '<span>BarrelLabs<span class="sl">/</span>'
        '<span class="ed">Edge</span></span></div>'
    )


def _corner_tele_html() -> str:
    """Top-right tiny telemetry header — session date + live status."""
    today = datetime.now()
    session_id = f"{today.strftime('%y.%m')}"
    return (
        '<div class="au-corner-tele">'
        f'<span>{session_id} · MAIN</span>'
        '<span class="live">Analyzer online</span>'
        '</div>'
    )


def _swing_path_svg() -> str:
    """A subtle hand-drawn-feeling swing trajectory SVG. Draws in via
    stroke-dashoffset animation. The path uses TWO strokes: a blurred
    underlay (soft glow) and a sharp top stroke (the visible line)."""
    return """
<div class="au-swingpath">
<svg viewBox="0 0 800 900" preserveAspectRatio="none">
  <defs>
    <linearGradient id="auGrad" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0%"  stop-color="#E8C170"/>
      <stop offset="100%" stop-color="#E64530"/>
    </linearGradient>
  </defs>
  <!-- soft glow underlay -->
  <path class="blur"
        d="M -50 900 C 120 720, 230 540, 360 470 C 540 380, 680 240, 880 80"
        stroke="url(#auGrad)"/>
  <!-- sharp line -->
  <path d="M -50 900 C 120 720, 230 540, 360 470 C 540 380, 680 240, 880 80"
        stroke="url(#auGrad)"/>
  <!-- arrival dot at the end of the swing path -->
  <circle class="dot" cx="880" cy="80" r="5"/>
  <circle class="dot" cx="880" cy="80" r="14" fill="none"
          stroke="#E8C170" stroke-width="1" opacity="0.45"/>
</svg>
</div>
"""


def _telemetry_grid_html() -> str:
    """2x2 telemetry grid replacing the v2 feature ladder."""
    cells = [
        ("01", "MLB-MATCH ACCURACY",  "87",  "%",   "87"),
        ("02", "METRICS DELIVERED",   "40",  "",    "82"),
        ("03", "PER-SWING REPORT",    "30",  "sec", "92"),
        ("04", "PRO REFERENCES",      "1,247", "",  "76"),
    ]
    cells_html = "".join(
        f'<div class="au-tcell">'
        f'  <div class="label">{html.escape(label)} <span class="id">{idx}</span></div>'
        f'  <div class="v">{html.escape(v)}<span class="u">{html.escape(u)}</span></div>'
        f'  <div class="bar" style="--bar: {bar}%;"></div>'
        f'</div>'
        for idx, label, v, u, bar in cells
    )
    return f'<div class="au-tgrid">{cells_html}</div>'


def _ticker_html() -> str:
    """Live status ticker. Track is duplicated so the marquee loop
    seamless without a gap."""
    items = [
        ('ANALYZER ONLINE',          'gold'),
        ('23 SWINGS PROCESSED TODAY',None),
        ('1,247 PRO REFS LOADED',    None),
        ('MLB SIM% 87',              None),
        ('BAT LAG +0.04s',           None),
        ('HSC 32°',                  None),
        ('SCORE 84',                 'gold'),
        ('HEAD DRIFT 2.1cm',         None),
        ('AVG ANALYSIS 28s',         None),
        ('UPTIME 99.97%',            None),
    ]

    def _item(text: str, color: str | None) -> str:
        if "%" in text or "+" in text or "°" in text or "cm" in text or "s" in text:
            # if the text contains a numeric value, color the FIRST
            # alphanumeric word OR the trailing number — easier: just
            # wrap the entire text in mono caps and let the value glow.
            cls = "v" + (" gold" if color else "")
            return f'<span><span class="{cls}">{html.escape(text)}</span></span>'
        cls = "v" + (" gold" if color else "")
        return f'<span><span class="{cls}">{html.escape(text)}</span></span>'

    track_html = "".join(_item(t, c) for t, c in items)
    # Duplicate the track so the marquee scroll loops seamlessly
    full_track = (
        f'<div class="au-ticker-track">{track_html}{track_html}</div>'
    )
    return (
        '<div class="au-ticker">'
        '<span class="live">Live</span>'
        f'{full_track}'
        '</div>'
    )


def _hero_html() -> str:
    """One self-contained markdown blob. Children of .au-content are
    fade-up staggered via CSS nth-child animation-delay."""
    today = datetime.now()
    session_label = f"SESSION {today.strftime('%m.%Y')} · PERFORMANCE LAB"
    return f"""
<div class="au-content">
  <div class="au-session-id"><span class="sep"></span><span class="tag">{session_label}</span></div>
  <span class="au-eyebrow">SwingAI · MLB-grade analysis</span>
  <h1 class="au-title">Find your<br/>MLB <span class="twin">swing twin</span><span class="period">.</span></h1>
  <p class="au-sub">Upload one swing and walk away with an MLB-grade biomechanical breakdown, the pro you swing like, and a personalized drill plan — in under a minute.</p>
  {_telemetry_grid_html()}
  <div class="au-quote-card">
    <div class="au-quote-avatar">TK</div>
    <div class="au-quote-body">
      <p class="au-quote-text">The MLB comparison alone is worth the subscription — that overlay is the unlock my hitting coach didn't have.</p>
      <p class="au-quote-name">Travis K.<span class="meta">Travel SS · Class of '27</span></p>
    </div>
  </div>
  {_ticker_html()}
</div>
"""


def _google_placeholder_html() -> str:
    return (
        '<div class="au-divider">or</div>'
        '<button type="button" class="au-google" disabled '
        'aria-disabled="true" title="Google sign-in coming soon">'
        '<span class="ic"></span>'
        '<span>Continue with Google</span>'
        '<span class="soon">Soon</span>'
        '</button>'
    )


def _legal_html() -> str:
    return (
        '<div class="au-legal">'
        'By continuing, you agree to BarrelLabs\' '
        '<a href="#" tabindex="-1">Terms</a> and '
        '<a href="#" tabindex="-1">Privacy</a>. '
        '© BarrelLabs Performance Lab'
        '</div>'
    )


# =====================================================================
# Forms — each renders inside the .st-key-auth_card container.
#
# IMPORTANT v3 layout:
#   - Mode lozenge sits in the card top-right (rendered before the
#     form by the public entry).
#   - Card title + sub render first.
#   - Form renders with the CTA INSIDE the form.
#   - Forgot password sits below the CTA (login only).
#   - Google placeholder + legal sit at the bottom.
#   - Mode switcher (kicker line linking to the other mode) is the
#     LAST element in the card.
# =====================================================================
def _render_login_form() -> None:
    show_pw = bool(st.session_state.get("auth_show_pw"))

    with st.form("login_form_v2", clear_on_submit=False):
        login_email = st.text_input(
            "Email", placeholder="you@example.com",
            key="login_email_v2",
        )
        login_pw = st.text_input(
            "Password",
            type=("default" if show_pw else "password"),
            placeholder="••••••••",
            key="login_pw_v2",
        )

        opts_cols = st.columns([1, 1])
        with opts_cols[0]:
            st.checkbox(
                "Remember me",
                value=bool(st.session_state.get("auth_remember", True)),
                key="auth_remember",
                help="Keep me signed in for this browser session.",
            )
        with opts_cols[1]:
            st.checkbox(
                "Show password",
                value=show_pw,
                key="auth_show_pw",
            )

        submitted = st.form_submit_button(
            "Enter the Performance Lab  →",
            type="primary",
            use_container_width=True,
        )
        if submitted:
            try:
                from player_storage import authenticate
                user = authenticate(login_email, login_pw)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Email or password is incorrect.")
            except Exception as exc:
                st.error(f"Couldn't sign in: {exc}")

    # Forgot-password — directly under the CTA, as a quiet mono-caps
    # tertiary link.
    with st.container(key="forgot_btn"):
        if st.button(
            "Forgot password?",
            key="forgot_link_v2",
            help="We'll email you a one-time link to set a new password.",
        ):
            st.session_state["auth_mode"] = "forgot"
            st.rerun()


def _render_signup_form() -> None:
    show_pw = bool(st.session_state.get("auth_show_pw_su"))

    with st.form("signup_form_v2", clear_on_submit=False):
        n1, n2 = st.columns(2)
        with n1:
            su_first = st.text_input(
                "First name", placeholder="Mario", key="su_first_v2"
            )
        with n2:
            su_last = st.text_input(
                "Last name", placeholder="Ricard", key="su_last_v2"
            )
        su_display = st.text_input(
            "Display name (optional)", placeholder="How you appear on shared reports",
            key="su_display_v2",
        )
        su_email = st.text_input(
            "Email", placeholder="you@example.com", key="su_email_v2",
        )
        su_pw = st.text_input(
            "Password (6+ characters)",
            type=("default" if show_pw else "password"),
            placeholder="At least 6 characters",
            key="su_pw_v2",
        )
        su_pw2 = st.text_input(
            "Confirm password",
            type=("default" if show_pw else "password"),
            placeholder="Repeat your password",
            key="su_pw2_v2",
        )

        st.checkbox(
            "Show password", value=show_pw, key="auth_show_pw_su",
        )

        st.markdown(
            '<div style="margin-top:6px; font-family:var(--au-mono); '
            'font-size:9.5px; letter-spacing:0.22em; '
            'text-transform:uppercase; color:var(--au-bone-40); '
            'font-weight:600; padding-bottom:4px;">'
            'Physical profile · refines MLB comparisons</div>',
            unsafe_allow_html=True,
        )

        su_hand = st.radio(
            "Batting hand",
            options=["Right-handed", "Left-handed"],
            horizontal=True, key="su_hand_v2",
        )

        phys_cols = st.columns([1, 1, 1])
        with phys_cols[0]:
            su_ft = st.number_input(
                "Height · ft", min_value=3, max_value=8, value=5, step=1,
                key="su_ft_v2",
            )
        with phys_cols[1]:
            su_in = st.number_input(
                "Height · in", min_value=0, max_value=11, value=10, step=1,
                key="su_in_v2",
            )
        with phys_cols[2]:
            su_wt = st.number_input(
                "Weight · lb", min_value=50, max_value=400, value=160, step=1,
                key="su_wt_v2",
            )

        submitted = st.form_submit_button(
            "Begin your free analysis  →",
            type="primary",
            use_container_width=True,
        )
        if submitted:
            if not su_first or not su_first.strip():
                st.error("Please enter your first name.")
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            else:
                try:
                    from player_storage import create_account
                    full_name = " ".join(
                        s.strip() for s in (su_first, su_last) if s and s.strip()
                    )
                    hand = "RIGHT" if su_hand == "Right-handed" else "LEFT"
                    height_in = int(su_ft) * 12 + int(su_in)
                    user = create_account(
                        name=full_name,
                        email=su_email,
                        password=su_pw,
                        handedness=hand,
                        height_in=height_in,
                        weight_lb=int(su_wt),
                    )
                    if su_display and su_display.strip():
                        extras = st.session_state.get(
                            "player_settings_extras"
                        ) or {}
                        extras["display_name"] = su_display.strip()
                        st.session_state["player_settings_extras"] = extras
                    st.session_state.user = user
                    st.success("Account created — taking you to your lab…")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Signup failed: {exc}")


def _render_forgot_form() -> None:
    with st.form("forgot_form_v2", clear_on_submit=False):
        forgot_email = st.text_input(
            "Email", placeholder="you@example.com",
            key="forgot_email_v2",
        )
        fc1, fc2 = st.columns([1, 1])
        with fc1:
            back = st.form_submit_button(
                "← Back to sign in", use_container_width=True,
            )
        with fc2:
            sent = st.form_submit_button(
                "Send reset link",
                type="primary",
                use_container_width=True,
            )
        if sent:
            try:
                from auth import request_password_reset
                request_password_reset(forgot_email)
                st.success(
                    "If an account exists for that email, a reset link "
                    "is on the way. Check your inbox."
                )
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Couldn't send reset email: {exc}")
        if back:
            st.session_state.pop("auth_mode", None)
            st.rerun()

    with st.expander("Trouble with the link?", expanded=False):
        st.caption(
            "If clicking the reset link didn't take you to a "
            "password form, copy the full URL from your browser "
            "bar (it'll start with `http://localhost:8501/#access_token=…`) "
            "and paste it here."
        )
        with st.form("paste_recovery_form_v2", clear_on_submit=False):
            pasted = st.text_input(
                "Reset link",
                placeholder="http://localhost:8501/#access_token=...",
                key="pasted_reset_url",
                label_visibility="collapsed",
            )
            use_link = st.form_submit_button(
                "Use this link", type="primary", use_container_width=True,
            )
            if use_link:
                try:
                    from urllib.parse import urlparse, parse_qs
                    u = urlparse((pasted or "").strip())
                    blob = u.fragment or u.query or ""
                    parts = parse_qs(blob)
                    at = (parts.get("access_token") or [""])[0]
                    rt = (parts.get("refresh_token") or [""])[0]
                    tp = (parts.get("type") or [""])[0]
                    if not (at and rt) or tp != "recovery":
                        st.error(
                            "That doesn't look like a valid reset link. "
                            "Make sure you copied the whole URL."
                        )
                    else:
                        from auth import consume_recovery_url
                        if consume_recovery_url(
                            access_token=at, refresh_token=rt,
                        ):
                            st.session_state["recovery_mode"] = True
                            st.rerun()
                        else:
                            st.error(
                                "Couldn't accept that link — it may have "
                                "expired. Send yourself a new reset email."
                            )
                except Exception as exc:
                    st.error(f"Couldn't parse that link: {exc}")


# =====================================================================
# Public entry points
# =====================================================================
def render_auth_screen() -> None:
    """Render the split-screen login / signup / forgot-password page."""
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="auth-grain"></div>', unsafe_allow_html=True)
    st.markdown(_swing_path_svg(), unsafe_allow_html=True)
    st.markdown(_brand_fixed_html(), unsafe_allow_html=True)
    st.markdown(_corner_tele_html(), unsafe_allow_html=True)

    mode = st.session_state.get("auth_mode")
    if mode not in ("forgot", "signup"):
        mode = "login"

    # Mode-specific copy
    if mode == "login":
        pill = ('<div class="au-mode-pill">Access mode'
                '<span class="num">01 / 02</span></div>')
        eyebrow = "Welcome back"
        title = "Welcome back."
        sub = ("Continue your path to elite performance — your swing "
               "library is right where you left it.")
    elif mode == "signup":
        pill = ('<div class="au-mode-pill">New member'
                '<span class="num">02 / 02</span></div>')
        eyebrow = "Create account"
        title = "Create your account."
        sub = ("Start analyzing your swing like the pros. One clip is "
               "all the analyzer needs.")
    else:  # forgot
        pill = ('<div class="au-mode-pill">Recovery'
                '<span class="num">RST / 01</span></div>')
        eyebrow = "Reset"
        title = "Reset your password."
        sub = ("Enter the email you used to sign up. We'll send a "
               "one-time link to set a new password.")

    with st.container(key="auth_root"):
        # ============== LEFT: hero panel ==============
        with st.container(key="auth_hero"):
            st.markdown(_hero_html(), unsafe_allow_html=True)

        # ============== RIGHT: auth panel ==============
        with st.container(key="auth_panel"):
            with st.container(key="auth_card"):
                # Card head — flex row with eyebrow on the left and the
                # mode lozenge on the right. (v3.1: replaces the v3
                # absolute-positioned pill that broke because Streamlit's
                # markdown wrappers carry their own stacking context.)
                st.markdown(
                    f'<div class="au-card-head">'
                    f'  <div class="au-card-eyebrow">{html.escape(eyebrow)}</div>'
                    f'  {pill}'
                    f'</div>'
                    f'<h2 class="au-card-title">{html.escape(title)}</h2>'
                    f'<p class="au-card-sub">{html.escape(sub)}</p>',
                    unsafe_allow_html=True,
                )

                if mode == "login":
                    _render_login_form()
                elif mode == "signup":
                    _render_signup_form()
                else:
                    _render_forgot_form()

                # Google placeholder + legal — only on login/signup,
                # not in forgot mode.
                if mode != "forgot":
                    st.markdown(_google_placeholder_html(),
                                 unsafe_allow_html=True)
                    st.markdown(_legal_html(), unsafe_allow_html=True)

                # MODE SWITCHER — the thing that replaces the hated
                # toggle. One quiet line at the bottom of the card.
                if mode == "login":
                    with st.container(key="mode_switch"):
                        if st.button(
                            "New to BarrelLabs?  Create your account  →",
                            key="auth_switch_to_signup",
                        ):
                            st.session_state["auth_mode"] = "signup"
                            st.rerun()
                elif mode == "signup":
                    with st.container(key="mode_switch"):
                        if st.button(
                            "←  Already a member?  Sign in",
                            key="auth_switch_to_login",
                        ):
                            st.session_state.pop("auth_mode", None)
                            st.rerun()
                # In forgot mode the back-button inside the form
                # handles returning to login — no mode-switcher line.


def render_recovery_screen() -> None:
    """Render the 'set a new password' screen shown when the user
    clicked the password-reset link in their email."""
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="auth-grain"></div>', unsafe_allow_html=True)
    st.markdown(_brand_fixed_html(), unsafe_allow_html=True)

    with st.container(key="auth_recovery"):
        with st.container(key="auth_card"):
            st.markdown(
                '<div class="au-mode-pill">Recovery<span class="num">RST / 01</span></div>'
                '<div class="au-card-eyebrow">Recovery</div>'
                '<h2 class="au-card-title">Set a new password.</h2>'
                '<p class="au-card-sub">Choose a new password for your account. '
                'We\'ll sign you straight in.</p>',
                unsafe_allow_html=True,
            )

            with st.form("recovery_form_v2", clear_on_submit=False):
                new_pw = st.text_input(
                    "New password (6+ characters)",
                    type="password", key="rec_pw_v2",
                )
                new_pw2 = st.text_input(
                    "Confirm new password",
                    type="password", key="rec_pw2_v2",
                )
                submitted = st.form_submit_button(
                    "Update password  →",
                    type="primary",
                    use_container_width=True,
                )
                if submitted:
                    if new_pw != new_pw2:
                        st.error("Passwords don't match.")
                    elif len(new_pw or "") < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            from auth import update_password
                            update_password(new_pw)
                            st.success("Password updated — signing you in…")
                            st.session_state.pop("recovery_mode", None)
                            try:
                                st.query_params.clear()
                            except Exception:
                                pass
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                        except Exception as exc:
                            st.error(f"Couldn't update password: {exc}")

            st.markdown(_legal_html(), unsafe_allow_html=True)
