"""BarrelLabs · Premium authentication experience (v2 — substantial rework).

What changed from v1
--------------------
v1 had four structural problems caught in user review:
1. The .au-card-frame "glass card" was opened/closed via raw
   st.markdown('<div>') and Streamlit 1.57 auto-closed both into empty
   sibling nodes — the card chrome rendered around NOTHING; the
   widgets sat outside it. Now the card is a real
   st.container(key="auth_card") so the widgets are descendants and
   .st-key-auth_card actually wraps them.
2. .st-key-auth_hero + .st-key-auth_panel each used
   `min-height: 100vh; justify-content: space-between` which slammed
   content to the top and bottom of each panel, leaving a vast dead
   band in the middle. Both panels are now `justify-content: center`
   with the content stack as a single nested column — vertical
   centering is real, and the auth card is the page's focal point.
3. A 1-px gradient stroke at the right edge of the hero pseudo'd in a
   "divider line." Removed entirely. The two panels share a
   continuous body background so the seam is invisible.
4. The testimonial author was hard to read at narrow widths — the
   "TRAVIS K." cite block visually compressed into a vertical strip.
   The testimonial is now a real horizontal quote card with an
   initials avatar, a name line, and a "Travel SS · Class of '27"
   meta line — no thin-strip layout possible.

Plus:
- Page max-width capped at 1480 so on 4K monitors the design stays
  tight, but the surrounding atmosphere (gradients) covers the full
  viewport so it never looks confined.
- Subtle baseball motif: a strike-zone grid + a swept bat-path arc
  painted as SVG behind the hero content at ~5% opacity.
- 52/48 desktop proportions with a content stack capped at 580 (hero)
  and 460 (panel). The card itself caps at 420.
- 5 feature rows tightened to 4 lines of copy each (denser, less air).
- Auth card chrome simplified to one glass surface with a single
  gold→red top edge; all the previous decorative bits (extra border,
  inner highlight, multiple shadows) collapsed into one.

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
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

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
  /* One continuous background. NO seam, NO divider between panels —
     the gradients overlap in the middle so the eye reads a single
     surface with two warm centers. */
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

/* ============ Cinematic ambient layers (page-wide) ============ */
.auth-grain {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.04; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.6'/></svg>");
}
/* Brand mark stamped at the page's top-left so it doesn't take up
   space in the hero content stack. */
.au-brand-fixed {
  position: fixed; top: 28px; left: 32px; z-index: 10;
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

/* ============ Root grid — capped on 4K, dead center the design ============ */
.st-key-auth_root {
  position: relative; z-index: 2;
  min-height: 100vh;
  max-width: 1480px;
  margin: 0 auto;
  display: grid !important;
  grid-template-columns: 52fr 48fr;
  gap: 0;
  color: var(--au-bone);
  font-family: var(--au-sans);
}
/* No vertical divider, no border-right anywhere. */

/* ============ LEFT HERO PANEL ============ */
.st-key-auth_hero {
  position: relative;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  align-items: flex-start !important;
  padding: 100px 56px 80px !important;
  min-height: 100vh;
  overflow: hidden;
}
.st-key-auth_hero [data-testid="stLayoutWrapper"] {
  width: 100% !important;
}

/* Subtle baseball motifs — strike zone grid in the upper-right, swept
   bat-path arc rising from bottom-left. Both at ~5% opacity, layered
   behind the content (z-index:0; content gets z-index:1). */
.au-motif {
  position: absolute; inset: 0; z-index: 0; pointer-events: none;
  overflow: hidden;
}
.au-motif::before {
  /* Strike-zone grid — 3 vertical + 3 horizontal lines forming a
     3×3 strike zone roughly in the upper-right quadrant. */
  content: ""; position: absolute;
  top: 14%; right: 8%;
  width: 280px; height: 360px;
  background-image:
    linear-gradient(90deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(90deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(90deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(90deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(0deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(0deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(0deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%),
    linear-gradient(0deg, transparent 0%, var(--au-bone-20) 50%, transparent 100%);
  background-size:
    100% 1px, 100% 1px, 100% 1px, 100% 1px,
    1px 100%, 1px 100%, 1px 100%, 1px 100%;
  background-position:
    0 0, 0 33.3%, 0 66.6%, 0 100%,
    0 0, 33.3% 0, 66.6% 0, 100% 0;
  background-repeat: no-repeat;
  opacity: 0.55;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
}
.au-motif::after {
  /* Swept bat-path arc — a soft curved glow from bottom-left rising
     to upper-mid, hinting at swing trajectory without being literal. */
  content: ""; position: absolute;
  left: -10%; bottom: -20%;
  width: 90%; height: 90%;
  background:
    radial-gradient(60% 80% at 0% 100%, rgba(232,193,112,0.10), transparent 60%),
    radial-gradient(50% 70% at 30% 70%, rgba(230,69,48,0.06), transparent 60%);
  filter: blur(8px);
  opacity: 0.85;
  transform: rotate(-12deg);
}

/* Hero content column — caps at 560 so the design stays composed even
   on ultra-wide screens. Centered horizontally within the panel. */
.au-content {
  position: relative; z-index: 1;
  width: 100%; max-width: 560px;
  display: flex; flex-direction: column;
  gap: 22px;
}

.au-eyebrow {
  font-family: var(--au-mono); font-size: 11px; font-weight: 600;
  letter-spacing: 0.30em; text-transform: uppercase;
  color: var(--au-red);
  display: inline-flex; align-items: center; gap: 9px;
  margin: 0;
}
.au-eyebrow::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--au-red); box-shadow: 0 0 10px var(--au-red);
  animation: au-pulse 2.6s ease-in-out infinite;
}
@keyframes au-pulse {
  0%, 100% { opacity: 1;    box-shadow: 0 0 10px var(--au-red); }
  50%      { opacity: 0.45; box-shadow: 0 0 2px var(--au-red); }
}

.au-title {
  font-family: var(--au-serif); font-style: italic;
  font-size: clamp(2.6rem, 4.6vw, 4.6rem); line-height: 0.98;
  letter-spacing: -0.022em; color: var(--au-bone);
  margin: 0;
}
.au-title .twin {
  background: linear-gradient(90deg, var(--au-gold) 0%, var(--au-red) 100%);
  -webkit-background-clip: text; background-clip: text;
  color: transparent;
}
.au-title .period { color: var(--au-red); }

.au-sub {
  color: var(--au-bone-60);
  font-family: var(--au-sans);
  font-size: 15px; line-height: 1.55;
  margin: 0;
}

/* Feature ladder — compact 4-row grid (instead of 5). Each row is a
   one-line heading + a one-line body, making the stack visibly
   denser. The 5th feature (Track progress) folds into the
   testimonial's meta line below. */
.au-ladder {
  display: grid; gap: 10px;
  margin-top: 4px;
}
.au-row {
  display: grid; grid-template-columns: 32px 1fr; gap: 14px;
  align-items: center;
  padding: 10px 14px;
  border-radius: var(--au-r-mid);
  background: var(--au-glass-1);
  border: 1px solid var(--au-line);
  transition: border-color .22s var(--au-ease-soft),
              background .22s var(--au-ease-soft);
}
.au-row:hover {
  border-color: var(--au-line-hi);
  background: var(--au-glass-2);
}
.au-row .au-num {
  font-family: var(--au-mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.06em;
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: var(--au-gold);
  background: var(--au-gold-soft);
  border: 1px solid var(--au-gold-line);
}
.au-row strong {
  display: block;
  font-family: var(--au-sans); font-size: 13.5px; font-weight: 600;
  color: var(--au-bone-warm);
  letter-spacing: -0.005em;
  line-height: 1.1;
}
.au-row span {
  display: block;
  color: var(--au-bone-60); font-size: 12px; line-height: 1.4;
  margin-top: 2px;
}

/* Testimonial — REAL horizontal quote card with an initials avatar
   (gold-gradient circle), the quote, a name line, and the meta
   ("Travel SS · Class of '27"). No more thin vertical cite strip. */
.au-quote-card {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 18px;
  align-items: center;
  padding: 18px 20px;
  border-radius: var(--au-r-card);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
  border: 1px solid var(--au-line-hi);
  position: relative;
  margin-top: 4px;
}
.au-quote-card::before {
  /* faint editorial "open quote" mark glowing in the upper-left */
  content: "“";
  position: absolute; top: -12px; left: 18px;
  font-family: var(--au-serif); font-style: italic;
  font-size: 4.2rem; line-height: 1; color: var(--au-gold);
  opacity: 0.35;
  pointer-events: none;
}
.au-quote-avatar {
  width: 56px; height: 56px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.4rem; color: var(--au-bone-warm);
  background: radial-gradient(120% 80% at 30% 20%,
              rgba(232,193,112,0.34) 0%,
              rgba(230,69,48,0.18) 60%,
              #14171C 100%);
  border: 1px solid var(--au-gold-line);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.10),
    inset 0 -1px 0 rgba(0,0,0,0.35);
  flex: none;
}
.au-quote-body { min-width: 0; }
.au-quote-text {
  font-family: var(--au-serif); font-style: italic;
  font-size: 14.5px; line-height: 1.45;
  color: var(--au-bone-warm);
  margin: 0 0 8px;
}
.au-quote-name {
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--au-bone-warm);
  margin: 0;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.au-quote-name .meta {
  color: var(--au-bone-40); font-weight: 500;
  letter-spacing: 0.14em;
}
.au-quote-name .meta::before {
  content: "·"; margin-right: 8px; color: var(--au-bone-40);
}

/* Stats row — three KPIs directly below the testimonial. */
.au-tele {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 0;
  padding-top: 8px;
}
.au-tele > div {
  position: relative;
  padding: 0 16px;
}
.au-tele > div + div::before {
  content: ""; position: absolute; left: 0; top: 4px; bottom: 4px;
  width: 1px; background: var(--au-line);
}
.au-tele > div:first-child { padding-left: 0; }
.au-tele .v {
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.7rem; line-height: 1; color: var(--au-bone);
  letter-spacing: -0.012em;
}
.au-tele .v .u {
  font-family: var(--au-mono); font-style: normal; font-size: 10.5px;
  font-weight: 600; letter-spacing: 0.18em;
  color: var(--au-bone-60); text-transform: uppercase;
  margin-left: 6px;
}
.au-tele .l {
  font-family: var(--au-mono); font-size: 9.5px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin-top: 6px;
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
/* The single LayoutWrapper holding the auth_card keyed container —
   constrain it so the card sits at 440px even though the panel is
   wider. */
.st-key-auth_panel > [data-testid="stLayoutWrapper"] {
  width: 100% !important; max-width: 440px !important;
  flex: 0 0 auto !important;
}

/* ============ AUTH CARD — REAL keyed container wrapping widgets ============
   Previous bug: I tried `st.markdown('<div class="au-card-frame">')`
   to open a card wrapper, but Streamlit 1.57 auto-closes it into an
   empty sibling, so the card chrome rendered around nothing. Now
   .st-key-auth_card is a real st.container(key=…) — the widgets
   below it ARE descendants — and the glass-surface CSS lands. */
.st-key-auth_card {
  position: relative;
  width: 100% !important;
  padding: 32px 32px 26px !important;
  border-radius: var(--au-r-card) !important;
  background:
    linear-gradient(180deg, rgba(20,23,28,0.78) 0%, rgba(13,15,19,0.92) 100%) !important;
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  backdrop-filter: blur(22px) saturate(1.2);
  border: 1px solid var(--au-line-hi) !important;
  box-shadow:
    0 30px 60px -24px rgba(0,0,0,0.65),
    inset 0 1px 0 rgba(255,255,255,0.05) !important;
  overflow: visible !important;
}
.st-key-auth_card::before {
  /* gold→red top-edge gradient stroke (the only decorative
     pseudo-element on the card — everything else is solid) */
  content: ""; position: absolute;
  left: 32px; right: 32px; top: 0; height: 1.5px;
  background: linear-gradient(90deg,
    transparent 0%, var(--au-gold) 30%,
    var(--au-red) 70%, transparent 100%);
  opacity: 0.9;
  border-radius: 1px;
  pointer-events: none;
}
/* Tight gap inside the card */
.st-key-auth_card > [data-testid="stLayoutWrapper"] {
  width: 100% !important;
}
.st-key-auth_card [data-testid="stElementContainer"] {
  margin-top: 0 !important; margin-bottom: 0 !important;
}

/* ============ Card eyebrow / title / sub ============ */
.au-card-eyebrow {
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.26em; text-transform: uppercase;
  color: var(--au-gold);
  display: inline-flex; align-items: center; gap: 8px;
  margin: 4px 0 8px;
}
.au-card-eyebrow::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: var(--au-gold); box-shadow: 0 0 9px var(--au-gold);
}
.au-card-title {
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.95rem; line-height: 1.0;
  letter-spacing: -0.015em; color: var(--au-bone);
  margin: 0 0 6px;
}
.au-card-sub {
  color: var(--au-bone-60);
  font-size: 13px; line-height: 1.5;
  margin: 0 0 16px;
}

/* ============ Segmented toggle ============ */
.st-key-auth_toggle {
  display: flex !important;
  flex-direction: row !important;
  background: var(--au-ink-2);
  border: 1px solid var(--au-line-hi);
  border-radius: var(--au-r-mid);
  padding: 4px;
  gap: 4px;
  margin: 0 0 20px !important;
}
.st-key-auth_toggle [data-testid="stLayoutWrapper"],
.st-key-auth_toggle [data-testid="stHorizontalBlock"],
.st-key-auth_toggle [data-testid="stColumn"],
.st-key-auth_toggle [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
  display: contents !important;
}
.st-key-auth_toggle [data-testid="stElementContainer"] {
  flex: 1 1 0 !important; margin: 0 !important;
}
.st-key-auth_toggle [data-testid="stButton"] {
  flex: 1 1 0 !important; width: 100% !important;
}
.st-key-auth_toggle [data-testid="stButton"] button {
  width: 100% !important;
  border: 1px solid transparent !important;
  background: transparent !important;
  border-radius: var(--au-r-sm) !important;
  font-family: var(--au-mono) !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase !important;
  color: var(--au-bone-60) !important;
  padding: 0.55rem 0.5rem !important;
  position: relative !important;
  min-height: 0 !important; height: 36px !important; line-height: 1.2 !important;
  box-shadow: none !important;
  transition: color .18s, background .18s;
}
.st-key-auth_toggle [data-testid="stButton"] button:hover {
  color: var(--au-bone) !important;
  background: var(--au-glass-1) !important;
}
.st-key-auth_toggle [data-testid="stButton"] button[kind="primary"],
.st-key-auth_toggle [data-testid="stButton"] button[data-testid="stBaseButton-primary"],
.st-key-auth_toggle [data-testid="stButton"] button[data-testid="baseButton-primary"] {
  background: linear-gradient(180deg,
    rgba(244,239,230,0.10), rgba(244,239,230,0.04)) !important;
  color: var(--au-bone-warm) !important;
  border-color: rgba(244,239,230,0.12) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.10),
    inset 0 -1px 0 rgba(0,0,0,0.18) !important;
}
.st-key-auth_toggle [data-testid="stButton"] button[kind="primary"]::after,
.st-key-auth_toggle [data-testid="stButton"] button[data-testid="stBaseButton-primary"]::after,
.st-key-auth_toggle [data-testid="stButton"] button[data-testid="baseButton-primary"]::after {
  content: ""; position: absolute;
  left: 16px; right: 16px; bottom: 4px;
  height: 1.5px; border-radius: 1px;
  background: linear-gradient(90deg,
    rgba(232,193,112,0) 0%, var(--au-gold) 30%,
    var(--au-red) 70%, rgba(230,69,48,0) 100%);
  box-shadow: 0 0 10px -1px rgba(232,193,112,0.5);
}

/* ============ Form widgets ============ */
.st-key-auth_card [data-testid="stTextInput"] label,
.st-key-auth_card [data-testid="stNumberInput"] label,
.st-key-auth_card [data-testid="stSelectbox"] label,
.st-key-auth_card [data-testid="stTextArea"] label {
  font-family: var(--au-mono) !important;
  font-size: 9.5px !important;
  letter-spacing: 0.20em !important;
  text-transform: uppercase !important;
  color: var(--au-bone-60) !important;
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
  padding: 0.65rem 0.9rem !important;
  transition: border-color .2s, box-shadow .2s;
  caret-color: var(--au-gold) !important;
  height: 44px !important;
  box-sizing: border-box !important;
}
.st-key-auth_card [data-testid="stTextInput"] input:focus,
.st-key-auth_card [data-testid="stNumberInput"] input:focus,
.st-key-auth_card [data-testid="stTextArea"] textarea:focus {
  border-color: var(--au-gold-line) !important;
  box-shadow: 0 0 0 3px rgba(232,193,112,0.12) !important;
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
  transition: transform .18s, border-color .18s, background .18s,
              box-shadow .18s;
  min-height: 0 !important; height: auto !important; line-height: 1.2 !important;
}
.st-key-auth_card [data-testid="stButton"] button:hover,
.st-key-auth_card [data-testid="stFormSubmitButton"] button:hover {
  border-color: var(--au-line-hi-2) !important;
  background: var(--au-glass-2) !important;
}
/* Primary CTA — the strongest visual on the page */
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
  height: 48px !important;
  padding: 0 22px !important;
  font-size: 13.5px !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.55),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(255,255,255,0.06),
    0 10px 24px -8px rgba(230,69,48,0.50),
    0 1px 0 rgba(255,255,255,0.04) !important;
  margin-top: 4px !important;
}
.st-key-auth_card [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
.st-key-auth_card [data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-1px) !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.75),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(255,255,255,0.08),
    0 14px 32px -8px rgba(230,69,48,0.62),
    0 0 28px -8px rgba(232,193,112,0.36) !important;
}
.st-key-auth_card button:focus-visible {
  outline: none !important;
  box-shadow:
    0 0 0 2px rgba(232,193,112,0.5),
    0 0 0 4px rgba(232,193,112,0.10) !important;
}

/* Forgot-password link — quiet "ghost" treatment so it doesn't fight
   the CTA for attention. Renders centered below the CTA. */
.st-key-auth_card .st-key-forgot_btn [data-testid="stButton"] button,
.st-key-auth_card .st-key-forgot_btn button {
  background: transparent !important;
  border: none !important;
  color: var(--au-bone-60) !important;
  font-family: var(--au-mono) !important;
  font-size: 10.5px !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase !important;
  font-weight: 600 !important;
  padding: 8px 12px !important;
  margin-top: 4px !important;
  width: auto !important;
}
.st-key-forgot_btn {
  display: flex !important; justify-content: center !important;
}
.st-key-forgot_btn [data-testid="stButton"] button:hover {
  color: var(--au-gold) !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

/* Google placeholder + divider */
.au-divider {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin: 16px 0 12px;
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
  margin: 16px 0 0;
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

/* ============ Recovery screen (centered single card) ============ */
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
.st-key-auth_recovery .st-key-auth_card {
  /* re-uses the same card styles */
}

/* ============ Responsive ============ */
@media (max-width: 1180px) {
  .st-key-auth_hero  { padding: 88px 44px 64px !important; }
  .st-key-auth_panel { padding: 64px 44px !important; }
  .au-title { font-size: clamp(2.4rem, 4.4vw, 3.8rem); }
  .au-content { max-width: 520px; }
}
@media (max-width: 980px) {
  .au-brand-fixed { top: 22px; left: 22px; }
  .st-key-auth_root {
    grid-template-columns: 1fr !important;
    max-width: none !important;
  }
  .st-key-auth_hero {
    min-height: auto !important;
    padding: 80px 28px 36px !important;
    align-items: center !important;
  }
  .au-content { max-width: 560px; align-items: stretch; margin: 0 auto; }
  .au-title { font-size: 2.4rem; }
  .au-motif { display: none; } /* less subtle = noisy on stacked layout */
  .st-key-auth_panel {
    min-height: auto !important;
    padding: 24px 24px 56px !important;
  }
  .st-key-auth_card { padding: 26px 24px 22px !important; }
}
@media (max-width: 640px) {
  .au-brand-fixed { font-size: 11px; }
  .au-brand-fixed .ed { font-size: 14px; }
  .st-key-auth_hero  { padding: 70px 18px 28px !important; }
  .st-key-auth_panel { padding: 18px 14px 40px !important; }
  .au-title { font-size: 2.0rem; }
  .au-row { grid-template-columns: 28px 1fr; gap: 12px; padding: 9px 12px; }
  .au-row .au-num { width: 28px; height: 28px; font-size: 9.5px; }
  .au-quote-card { grid-template-columns: 44px 1fr; padding: 16px; gap: 14px; }
  .au-quote-avatar { width: 44px; height: 44px; font-size: 1.15rem; }
  .au-tele { grid-template-columns: 1fr 1fr; gap: 14px 0; }
  .au-tele > div:nth-child(3) {
    grid-column: 1 / -1; padding-top: 14px;
    margin-top: 6px; border-top: 1px solid var(--au-line);
  }
  .au-tele > div:nth-child(3)::before { display: none; }
  .au-tele > div { padding: 0 12px; }
  .au-tele > div:first-child { padding-left: 0; }
  .st-key-auth_card { padding: 22px 18px 20px !important; border-radius: 18px !important; }
  .au-card-title { font-size: 1.7rem; }
}
</style>
"""


# =====================================================================
# Hero HTML — single self-contained markdown emit
# =====================================================================
_FEATURE_ROWS = [
    ("01", "Upload one swing",
     "A single phone clip — no mocap suit, no app gating."),
    ("02", "AI biomechanical breakdown",
     "Pose-tracked metrics across the whole swing."),
    ("03", "Compare to MLB hitters",
     "Side-by-side against pros matched to your build."),
    ("04", "Personalized drill plan",
     "Top-3 fixes ranked by impact, with rep counts."),
]


def _brand_fixed_html() -> str:
    """Brand mark stamped fixed at the page's top-left so it doesn't
    eat vertical space in the hero content stack."""
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


def _hero_html() -> str:
    """Render the LEFT hero content as ONE markdown blob.

    All content sits inside `.au-content` which is `display: flex;
    flex-direction: column; max-width: 560px` so the eye reads a
    deliberate vertical stack: eyebrow → title → sub → ladder →
    testimonial → stats. No content lives outside this column.
    """
    ladder_html = "".join(
        f'<div class="au-row">'
        f'  <div class="au-num">{n}</div>'
        f'  <div><strong>{html.escape(title)}</strong>'
        f'  <span>{html.escape(body)}</span></div>'
        f'</div>'
        for n, title, body in _FEATURE_ROWS
    )

    return f"""
<div class="au-motif"></div>
<div class="au-content">
  <span class="au-eyebrow">SwingAI · Performance Lab</span>
  <h1 class="au-title">Find your<br/>MLB <span class="twin">swing twin</span><span class="period">.</span></h1>
  <p class="au-sub">Upload one swing and walk away with an MLB-grade biomechanical breakdown, the pro you swing like, and a personalized drill plan — in under a minute.</p>
  <div class="au-ladder">{ladder_html}</div>
  <div class="au-quote-card">
    <div class="au-quote-avatar">TK</div>
    <div class="au-quote-body">
      <p class="au-quote-text">The MLB comparison alone is worth the subscription — that overlay is the unlock my hitting coach didn't have.</p>
      <p class="au-quote-name">Travis K.<span class="meta">Travel SS · Class of '27</span></p>
    </div>
  </div>
  <div class="au-tele">
    <div>
      <div class="v">10<span class="u">+</span></div>
      <div class="l">MLB references</div>
    </div>
    <div>
      <div class="v">40<span class="u">+</span></div>
      <div class="l">Biomech metrics</div>
    </div>
    <div>
      <div class="v">30<span class="u">sec</span></div>
      <div class="l">Per analysis</div>
    </div>
  </div>
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
# Forms — each renders the inside of the .st-key-auth_card container.
# =====================================================================
def _render_login_form() -> None:
    st.markdown(
        '<div class="au-card-eyebrow">Welcome back</div>'
        '<h2 class="au-card-title">Welcome back.</h2>'
        '<p class="au-card-sub">Continue your path to elite performance — '
        'your swing library is right where you left it.</p>',
        unsafe_allow_html=True,
    )

    show_pw = bool(st.session_state.get("auth_show_pw"))

    with st.form("login_form_v2", clear_on_submit=False):
        login_email = st.text_input(
            "Email", placeholder="you@example.com",
            key="login_email_v2",
        )
        login_pw = st.text_input(
            "Password",
            type=("default" if show_pw else "password"),
            placeholder="Your password",
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
            "Access your Performance Lab  →",
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

    # Forgot-password — a ghost button visually distinct from the CTA.
    # Wrapped in its own keyed container so the centered/quiet styling
    # only applies to this button, not other secondary buttons.
    with st.container(key="forgot_btn"):
        if st.button(
            "Forgot password?",
            key="forgot_link_v2",
            help="We'll email you a one-time link to set a new password.",
        ):
            st.session_state["auth_mode"] = "forgot"
            st.rerun()

    st.markdown(_google_placeholder_html(), unsafe_allow_html=True)
    st.markdown(_legal_html(), unsafe_allow_html=True)


def _render_signup_form() -> None:
    st.markdown(
        '<div class="au-card-eyebrow">Create account</div>'
        '<h2 class="au-card-title">Create your account.</h2>'
        '<p class="au-card-sub">Start analyzing your swing like the pros. '
        'One clip is all the analyzer needs.</p>',
        unsafe_allow_html=True,
    )

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
            'font-size:9.5px; letter-spacing:0.20em; '
            'text-transform:uppercase; color:var(--au-bone-60); '
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
            "Start your free analysis  →",
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

    st.markdown(_google_placeholder_html(), unsafe_allow_html=True)
    st.markdown(_legal_html(), unsafe_allow_html=True)


def _render_forgot_form() -> None:
    st.markdown(
        '<div class="au-card-eyebrow">Reset</div>'
        '<h2 class="au-card-title">Reset your password.</h2>'
        '<p class="au-card-sub">Enter the email you used to sign up. We\'ll '
        'send a one-time link to set a new password.</p>',
        unsafe_allow_html=True,
    )

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
    st.markdown(_brand_fixed_html(), unsafe_allow_html=True)

    with st.container(key="auth_root"):
        # ============== LEFT: hero panel ==============
        with st.container(key="auth_hero"):
            st.markdown(_hero_html(), unsafe_allow_html=True)

        # ============== RIGHT: auth panel ==============
        with st.container(key="auth_panel"):
            mode = st.session_state.get("auth_mode")
            if mode not in ("forgot", "signup"):
                mode = "login"

            # The REAL glass card — a keyed container so widgets are
            # descendants and .st-key-auth_card actually wraps them
            # (fixing the v1 markdown-div-trap bug where the card
            # rendered around nothing).
            with st.container(key="auth_card"):
                if mode != "forgot":
                    with st.container(key="auth_toggle"):
                        t1, t2 = st.columns(2)
                        with t1:
                            if st.button(
                                "Sign in",
                                key="auth_toggle_login",
                                type=("primary" if mode == "login" else "secondary"),
                                use_container_width=True,
                            ):
                                st.session_state.pop("auth_mode", None)
                                st.rerun()
                        with t2:
                            if st.button(
                                "Create account",
                                key="auth_toggle_signup",
                                type=("primary" if mode == "signup" else "secondary"),
                                use_container_width=True,
                            ):
                                st.session_state["auth_mode"] = "signup"
                                st.rerun()

                if mode == "login":
                    _render_login_form()
                elif mode == "signup":
                    _render_signup_form()
                else:
                    _render_forgot_form()


def render_recovery_screen() -> None:
    """Render the 'set a new password' screen shown when the user
    clicked the password-reset link in their email."""
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="auth-grain"></div>', unsafe_allow_html=True)
    st.markdown(_brand_fixed_html(), unsafe_allow_html=True)

    with st.container(key="auth_recovery"):
        with st.container(key="auth_card"):
            st.markdown(
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
