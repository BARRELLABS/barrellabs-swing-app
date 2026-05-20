"""BarrelLabs · Premium authentication experience.

Split-screen Ferrari/F1/Driveline/TrackMan/Statcast inspired login and
signup. Replaces the inline `render_auth_screen()` / `render_recovery_screen()`
that used to live in `app.py`.

Design language
---------------
- Ink (#0A0B0E) + charcoal panels with subtle red (#E64530) and gold
  (#E8C170) accents.
- Instrument Serif italic display, Geist sans body, Geist Mono labels.
- LEFT: cinematic hero panel with the BarrelLabs mark, the primary
  message "Find Your MLB Swing Twin.", a 5-step feature ladder, and an
  athlete-style testimonial pull.
- RIGHT: glass auth card with a premium segmented Sign-In / Create-
  Account toggle, password show/hide, Remember Me, Forgot-Password,
  Google placeholder, and a single primary CTA per mode.

Auth wiring preserved verbatim
------------------------------
- `player_storage.authenticate(email, password)` → profile dict | None
- `player_storage.create_account(name, email, password, handedness,
   height_in, weight_lb)` → profile dict
- `auth.request_password_reset(email)`
- `auth.consume_recovery_url(access_token, refresh_token)`
- `auth.consume_recovery_token_hash(token_hash)`
- `auth.update_password(new_password)`
- Recovery JS shim + token_hash + access_token URL detection (still
  lives in `app.py` next to `st.query_params` — this module does NOT
  touch the URL).
- All session-state flags untouched:
  `st.session_state.user`, `auth_mode == "forgot"`,
  `recovery_mode`, `pasted_reset_url`, `su_pw / su_pw2`, etc.

Streamlit 1.57 layout pattern
-----------------------------
We follow the same `st.container(key=…)` + `display:contents` flattening
pattern the masthead and player-settings page use:

1. One root keyed container `.st-key-auth_root` — the page surface.
2. Two keyed siblings inside: `.st-key-auth_hero` and
   `.st-key-auth_panel`.
3. The intermediate `stVerticalBlock` is collapsed with
   `display:contents` so hero and panel sit as direct grid items.
4. Every widget reskin (text-input, button, checkbox) is scoped under
   `.st-key-auth_panel` so it never leaks into the masthead or any
   authenticated page.
"""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

# Re-use the masthead's logo helper so the auth screen always paints the
# same official PNG — never a fallback dot when one of the two pages
# can't find the asset.
try:
    from bl_edge_chrome import _logo_data_uri as _bl_logo_data_uri
except Exception:  # pragma: no cover — defensive, bl_edge_chrome is always importable
    def _bl_logo_data_uri() -> str:
        return ""


# =====================================================================
# CSS — every selector scoped under .st-key-auth_root or
# .st-key-auth_panel so this module cannot leak into authenticated
# pages. The reskins use the same `!important` discipline as the
# masthead because Streamlit 1.57 default chrome wins on specificity
# without it.
# =====================================================================
_AUTH_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

/* ------- Tokens (re-declared so this page is fully self-contained -- */
.st-key-auth_root {
  --au-ink:        #0A0B0E;
  --au-ink-2:      #0D0F13;
  --au-ink-3:      #14171C;
  --au-ink-4:      #1A1E25;
  --au-bone:       #F4EFE6;
  --au-bone-warm:  #F8F2E0;
  --au-bone-80:    rgba(244,239,230,0.82);
  --au-bone-60:    rgba(244,239,230,0.60);
  --au-bone-40:    rgba(244,239,230,0.36);
  --au-bone-20:    rgba(244,239,230,0.18);
  --au-glass-1:    rgba(255,255,255,0.025);
  --au-glass-2:    rgba(255,255,255,0.045);
  --au-glass-3:    rgba(255,255,255,0.07);
  --au-line:       rgba(244,239,230,0.08);
  --au-line-hi:    rgba(244,239,230,0.16);
  --au-line-hi-2:  rgba(244,239,230,0.24);
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

/* ------- Streamlit chrome erasure (no header, no toolbar, no top pad)
   Scoped via the page-root selector so the moment the auth screen
   exits these rules detach. */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
  background: #0A0B0E !important;
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
[data-testid="stApp"] {
  overflow-x: hidden !important;
}

/* ------- Cinematic ambient background -------------------------------
   Two radial glows + a thin film-grain SVG noise. Fixed so it stays
   in place during scroll on smaller windows. */
.auth-atmos {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(900px 700px at 14% 6%, rgba(232,193,112,0.06), transparent 60%),
    radial-gradient(800px 600px at 88% 96%, rgba(230,69,48,0.045), transparent 60%),
    radial-gradient(1400px 900px at 50% 50%, rgba(20,23,28,0.55), transparent 70%);
}
.auth-grain {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.035; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.6'/></svg>");
}

/* ====================================================================
   ROOT GRID — .st-key-auth_root holds the two-pane split. The inner
   stVerticalBlock is collapsed with display:contents so hero + panel
   land as direct grid children. (Same pattern the masthead uses.)
   ==================================================================== */
.st-key-auth_root {
  position: relative; z-index: 2;
  min-height: 100vh;
  display: grid !important;
  grid-template-columns: minmax(0, 1.05fr) minmax(460px, 0.95fr);
  gap: 0;
  color: var(--au-bone);
  font-family: var(--au-sans);
}
.st-key-auth_root > div[data-testid="stVerticalBlock"] {
  display: contents !important;
}
.st-key-auth_root > div[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
  margin: 0 !important;
}

/* ====================================================================
   LEFT HERO PANEL — .st-key-auth_hero
   Cinematic editorial column with brand mark, eyebrow, massive
   italic display headline, sub copy, feature ladder, testimonial.
   ==================================================================== */
.st-key-auth_hero {
  position: relative;
  min-height: 100vh;
  padding: 56px 64px 56px;
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;
  background:
    radial-gradient(900px 500px at -10% 110%, rgba(230,69,48,0.08), transparent 60%),
    radial-gradient(700px 700px at 90% -20%, rgba(232,193,112,0.06), transparent 60%),
    linear-gradient(180deg, #0A0B0E 0%, #0D0F13 100%);
  border-right: 1px solid var(--au-line);
  overflow: hidden;
}
.st-key-auth_hero > div[data-testid="stVerticalBlock"] {
  display: contents !important;
}
/* a thin diagonal accent line — telemetry strip vibe */
.st-key-auth_hero::before {
  content: ""; position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 1px;
  background: linear-gradient(180deg,
    transparent 0%, var(--au-gold-line) 24%,
    var(--au-red-line) 76%, transparent 100%);
  opacity: 0.55;
  pointer-events: none;
}

.au-brand {
  display: flex; align-items: center; gap: 14px;
  font-family: var(--au-sans); font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase; font-size: 13px;
  color: var(--au-bone);
}
.au-brand img {
  width: 34px; height: 34px; object-fit: contain; display: block;
}
.au-brand .sl { color: #3A3D44; margin: 0 8px; font-weight: 300; }
.au-brand .ed {
  font-family: var(--au-serif); font-style: italic; font-weight: 400;
  font-size: 18px; letter-spacing: 0; text-transform: none;
  color: #8B8E94;
}

.au-eyebrow {
  font-family: var(--au-mono); font-size: 11px; font-weight: 600;
  letter-spacing: 0.30em; text-transform: uppercase;
  color: var(--au-red);
  display: inline-flex; align-items: center; gap: 9px;
  margin-top: 64px;
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
  font-size: clamp(3rem, 5.4vw, 5.4rem); line-height: 0.98;
  letter-spacing: -0.022em; color: var(--au-bone);
  margin: 24px 0 22px;
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
  font-size: 15.5px; line-height: 1.6;
  max-width: 540px; margin: 0 0 28px;
}

/* feature ladder — 5 rows with numbered chips */
.au-ladder {
  display: grid; gap: 14px;
  margin-top: 8px;
}
.au-row {
  display: grid; grid-template-columns: 36px 1fr; gap: 18px;
  align-items: start;
  padding: 12px 14px;
  border-radius: var(--au-r-mid);
  background: var(--au-glass-1);
  border: 1px solid var(--au-line);
  transition: border-color .22s var(--au-ease-soft),
              background .22s var(--au-ease-soft),
              transform .22s var(--au-ease-soft);
}
.au-row:hover {
  border-color: var(--au-line-hi);
  background: var(--au-glass-2);
  transform: translateX(2px);
}
.au-row .au-num {
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 700;
  letter-spacing: 0.10em;
  width: 36px; height: 36px; border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  color: var(--au-gold);
  background: var(--au-gold-soft);
  border: 1px solid var(--au-gold-line);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
}
.au-row strong {
  display: block;
  font-family: var(--au-sans); font-size: 14.5px; font-weight: 600;
  color: var(--au-bone-warm); margin-bottom: 3px;
  letter-spacing: -0.005em;
}
.au-row span {
  display: block;
  color: var(--au-bone-60); font-size: 13px; line-height: 1.5;
}

/* testimonial pull — italic editorial quote with red marker */
.au-quote {
  margin-top: 36px; padding-top: 28px;
  border-top: 1px solid var(--au-line);
  display: grid; grid-template-columns: 4px 1fr; gap: 18px;
  align-items: start;
}
.au-quote::before {
  content: ""; width: 3px; background: linear-gradient(180deg,
    var(--au-red), var(--au-gold));
  border-radius: 2px; align-self: stretch;
}
.au-quote q {
  font-family: var(--au-serif); font-style: italic;
  font-size: 17.5px; line-height: 1.45;
  color: var(--au-bone-warm);
  quotes: "“" "”";
  display: block;
}
.au-quote q::before { content: open-quote; opacity: 0.5; margin-right: 4px; }
.au-quote q::after  { content: close-quote; opacity: 0.5; margin-left: 4px; }
.au-quote cite {
  display: block;
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin-top: 10px; font-style: normal;
}
.au-quote cite em {
  color: var(--au-gold); font-style: normal;
  font-weight: 700; margin-right: 6px;
}

/* footer telemetry strip — three KPIs with mono labels */
.au-tele {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 0; margin-top: 36px;
  border-top: 1px solid var(--au-line);
  padding-top: 22px;
}
.au-tele > div {
  position: relative;
  padding: 0 18px;
}
.au-tele > div + div::before {
  content: ""; position: absolute; left: 0; top: 4px; bottom: 4px;
  width: 1px; background: var(--au-line);
}
.au-tele > div:first-child { padding-left: 0; }
.au-tele .v {
  font-family: var(--au-serif); font-style: italic;
  font-size: 1.9rem; line-height: 1; color: var(--au-bone);
  letter-spacing: -0.012em;
}
.au-tele .v .u {
  font-family: var(--au-mono); font-style: normal; font-size: 11px;
  font-weight: 600; letter-spacing: 0.18em;
  color: var(--au-bone-60); text-transform: uppercase;
  margin-left: 6px;
}
.au-tele .l {
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin-top: 8px;
}

/* ====================================================================
   RIGHT AUTH PANEL — .st-key-auth_panel
   Vertically-centered glass card containing the toggle + form widgets.
   ==================================================================== */
.st-key-auth_panel {
  position: relative;
  min-height: 100vh;
  padding: 56px 64px;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  background:
    radial-gradient(700px 500px at 100% 0%, rgba(232,193,112,0.05), transparent 65%),
    radial-gradient(800px 700px at 0% 100%, rgba(230,69,48,0.04), transparent 65%),
    linear-gradient(180deg, #0B0D11 0%, #0E1116 100%);
}
/* The panel itself is the stVerticalBlock keyed container (ST 1.57
   gotcha — see toggle comment above). Layout wrappers around each
   child get the max-width treatment so the form column is a clean
   460px stack centered in the panel. */
.st-key-auth_panel > [data-testid="stLayoutWrapper"] {
  width: 100% !important; max-width: 460px !important;
  flex: 0 0 auto !important;
}
.st-key-auth_panel [data-testid="stElementContainer"] {
  margin: 0 !important;
}

/* Glass card surface — a single conceptual card; the segmented toggle
   sits inside it, then the form, then footer chips. We don't wrap the
   widgets in a real container — instead we paint the card on the
   panel's wrapping flex column via a pseudo-element so widgets can stay
   plain vertical-block children. */
.au-card-frame {
  position: relative;
  padding: 36px 36px 30px;
  border-radius: var(--au-r-card);
  background:
    linear-gradient(180deg, rgba(20,23,28,0.78) 0%, rgba(13,15,19,0.88) 100%);
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  backdrop-filter: blur(22px) saturate(1.2);
  border: 1px solid var(--au-line-hi);
  box-shadow:
    0 32px 60px -20px rgba(0,0,0,0.65),
    inset 0 1px 0 rgba(255,255,255,0.05);
  overflow: hidden;
}
.au-card-frame::before {
  /* top edge highlight — gold→red gradient like the savestrip */
  content: ""; position: absolute;
  left: 24px; right: 24px; top: 0; height: 1.5px;
  background: linear-gradient(90deg,
    transparent 0%, var(--au-gold) 30%,
    var(--au-red) 70%, transparent 100%);
  opacity: 0.85;
  border-radius: 1px;
}

.au-card-eyebrow {
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.26em; text-transform: uppercase;
  color: var(--au-gold);
  display: inline-flex; align-items: center; gap: 8px;
  margin: 0 0 12px;
}
.au-card-eyebrow::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: var(--au-gold); box-shadow: 0 0 9px var(--au-gold);
}
.au-card-title {
  font-family: var(--au-serif); font-style: italic;
  font-size: 2.2rem; line-height: 1.02;
  letter-spacing: -0.015em; color: var(--au-bone);
  margin: 0 0 6px;
}
.au-card-sub {
  color: var(--au-bone-60);
  font-size: 13.5px; line-height: 1.5;
  margin: 0 0 22px;
}

/* segmented Sign In / Create Account toggle — uses two st.button widgets
   inside a keyed container .st-key-auth_toggle.

   ST 1.57 DOM gotcha (probed live, May 2026):
     - st.container(key="X") emits a single <div class="stVerticalBlock
       st-key-X" data-testid="stVerticalBlock">. The keyed container IS
       the stVerticalBlock — there is NO outer stElementContainer wrap.
     - Inside, st.columns produces:
         stLayoutWrapper > stHorizontalBlock > stColumn > stVerticalBlock
           > stElementContainer > stButton
     - The default emotion CSS gives stVerticalBlock flex-direction:
       column, so without an explicit row override every keyed
       container that wants a horizontal layout inherits column and
       its buttons stack vertically.
   Therefore: explicit flex-direction:row + flatten *all* intermediate
   layout-wrapper / horizontal-block / column / column's inner vblock
   so the buttons land as direct flex items of the keyed container. */
.st-key-auth_toggle {
  display: flex !important;
  flex-direction: row !important;
  background: var(--au-ink-2);
  border: 1px solid var(--au-line-hi);
  border-radius: var(--au-r-mid);
  padding: 4px;
  gap: 4px;
  margin-bottom: 24px !important;
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
  letter-spacing: 0.18em !important;
  text-transform: uppercase !important;
  color: var(--au-bone-60) !important;
  padding: 0.65rem 0.5rem !important;
  position: relative !important;
  min-height: 0 !important; height: auto !important;
  line-height: 1.2 !important;
  box-shadow: none !important;
  transition: color .18s var(--au-ease-soft),
              background .18s var(--au-ease-soft);
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
.st-key-auth_toggle [data-testid="stButton"]
  button[kind="primary"]::after,
.st-key-auth_toggle [data-testid="stButton"]
  button[data-testid="stBaseButton-primary"]::after,
.st-key-auth_toggle [data-testid="stButton"]
  button[data-testid="baseButton-primary"]::after {
  content: ""; position: absolute;
  left: 16px; right: 16px; bottom: 4px;
  height: 1.5px; border-radius: 1px;
  background: linear-gradient(90deg,
    rgba(232,193,112,0) 0%, var(--au-gold) 30%,
    var(--au-red) 70%, rgba(230,69,48,0) 100%);
  box-shadow: 0 0 10px -1px rgba(232,193,112,0.5);
}

/* ====================================================================
   FORM WIDGETS — every reskin scoped to .st-key-auth_panel
   ==================================================================== */
.st-key-auth_panel [data-testid="stTextInput"] label,
.st-key-auth_panel [data-testid="stNumberInput"] label,
.st-key-auth_panel [data-testid="stSelectbox"] label,
.st-key-auth_panel [data-testid="stTextArea"] label {
  font-family: var(--au-mono) !important;
  font-size: 10px !important;
  letter-spacing: 0.20em !important;
  text-transform: uppercase !important;
  color: var(--au-bone-60) !important;
  font-weight: 600 !important;
  padding-bottom: 6px !important;
}
.st-key-auth_panel [data-testid="stTextInput"] input,
.st-key-auth_panel [data-testid="stNumberInput"] input,
.st-key-auth_panel [data-testid="stTextArea"] textarea {
  background: var(--au-ink-2) !important;
  border: 1px solid var(--au-line-hi) !important;
  border-radius: var(--au-r-mid) !important;
  color: var(--au-bone) !important;
  font-family: var(--au-sans) !important;
  font-size: 14.5px !important;
  padding: 0.7rem 0.95rem !important;
  transition: border-color .2s var(--au-ease-soft),
              box-shadow .2s var(--au-ease-soft);
  caret-color: var(--au-gold) !important;
}
.st-key-auth_panel [data-testid="stTextInput"] input:focus,
.st-key-auth_panel [data-testid="stNumberInput"] input:focus,
.st-key-auth_panel [data-testid="stTextArea"] textarea:focus {
  border-color: var(--au-gold-line) !important;
  box-shadow: 0 0 0 3px rgba(232,193,112,0.12) !important;
  outline: none !important;
}
/* placeholder */
.st-key-auth_panel input::placeholder,
.st-key-auth_panel textarea::placeholder {
  color: var(--au-bone-40) !important;
  font-family: var(--au-sans) !important;
}

/* checkbox row — Remember Me + Show Password */
.st-key-auth_panel [data-testid="stCheckbox"] label,
.st-key-auth_panel [data-testid="stCheckbox"] p {
  font-family: var(--au-sans) !important;
  font-size: 12.5px !important;
  color: var(--au-bone-80) !important;
  font-weight: 500 !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
}

/* hide native number-input spinners (signup height/weight columns) */
.st-key-auth_panel [data-testid="stNumberInput"] button {
  display: none !important;
}

/* ============= BUTTONS — base + primary CTA ========================= */
.st-key-auth_panel [data-testid="stButton"] button,
.st-key-auth_panel [data-testid="stDownloadButton"] button,
.st-key-auth_panel [data-testid="stFormSubmitButton"] button {
  font-family: var(--au-sans) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  border-radius: var(--au-r-pill) !important;
  padding: 0.7rem 1.2rem !important;
  background: var(--au-glass-1) !important;
  color: var(--au-bone) !important;
  border: 1px solid var(--au-line-hi) !important;
  transition: transform .18s var(--au-ease-soft),
              border-color .18s var(--au-ease-soft),
              background .18s var(--au-ease-soft),
              color .18s var(--au-ease-soft),
              box-shadow .18s var(--au-ease-soft);
  min-height: 0 !important; height: auto !important; line-height: 1.2 !important;
}
.st-key-auth_panel [data-testid="stButton"] button:hover,
.st-key-auth_panel [data-testid="stDownloadButton"] button:hover,
.st-key-auth_panel [data-testid="stFormSubmitButton"] button:hover {
  border-color: var(--au-line-hi-2) !important;
  background: var(--au-glass-2) !important;
}
/* Primary CTA — red→deep-red with gold inset highlight + soft red glow */
.st-key-auth_panel [data-testid="stFormSubmitButton"] button[kind="primary"],
.st-key-auth_panel [data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"],
.st-key-auth_panel [data-testid="stFormSubmitButton"] button[data-testid="baseButton-primary"],
.st-key-auth_panel [data-testid="stButton"] button[kind="primary"],
.st-key-auth_panel [data-testid="stButton"] button[data-testid="stBaseButton-primary"],
.st-key-auth_panel [data-testid="stButton"] button[data-testid="baseButton-primary"] {
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
  margin-top: 6px !important;
}
.st-key-auth_panel [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
.st-key-auth_panel [data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-1px) !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.75),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(255,255,255,0.08),
    0 14px 32px -8px rgba(230,69,48,0.62),
    0 0 28px -8px rgba(232,193,112,0.36) !important;
}
.st-key-auth_panel button:focus-visible {
  outline: none !important;
  box-shadow:
    0 0 0 2px rgba(232,193,112,0.5),
    0 0 0 4px rgba(232,193,112,0.10) !important;
}

/* ============= Form internals =====================================*/
.st-key-auth_panel [data-testid="stForm"] {
  border: none !important; padding: 0 !important; background: transparent !important;
}
.st-key-auth_panel [data-testid="stForm"] [data-testid="stVerticalBlock"] {
  gap: 14px !important;
}
.st-key-auth_panel [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
  gap: 12px !important;
}

/* options row beneath password — Remember Me / Forgot Password */
.au-opts {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; margin: 4px 0 8px;
  font-family: var(--au-sans);
}
.au-forgot {
  font-family: var(--au-mono); font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--au-bone-60);
  cursor: pointer;
}
.au-forgot:hover { color: var(--au-gold); }

/* Google placeholder + divider */
.au-divider {
  display: flex; align-items: center; gap: 14px;
  font-family: var(--au-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--au-bone-40);
  margin: 20px 0 16px;
}
.au-divider::before,
.au-divider::after {
  content: ""; flex: 1 1 auto; height: 1px;
  background: var(--au-line);
}
.au-google {
  width: 100%;
  display: flex; align-items: center; justify-content: center; gap: 10px;
  height: 44px;
  padding: 0 18px;
  border-radius: var(--au-r-pill);
  background: var(--au-glass-1);
  border: 1px solid var(--au-line-hi);
  color: var(--au-bone-80);
  font-family: var(--au-sans); font-weight: 500; font-size: 13px;
  cursor: not-allowed;
  letter-spacing: 0.01em;
  transition: border-color .18s var(--au-ease-soft);
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

/* footer legal */
.au-legal {
  text-align: center;
  margin: 22px 0 0;
  font-family: var(--au-mono); font-size: 10px; font-weight: 500;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--au-bone-40);
  line-height: 1.55;
}
.au-legal a { color: var(--au-bone-60); text-decoration: none;
              border-bottom: 1px solid var(--au-line); padding-bottom: 1px; }
.au-legal a:hover { color: var(--au-gold); border-color: var(--au-gold-line); }

/* flash messages (st.error / st.success — restyled into editorial bars) */
.st-key-auth_panel [data-testid="stAlert"] {
  border-radius: var(--au-r-mid) !important;
  font-family: var(--au-mono) !important;
  font-size: 11.5px !important;
  letter-spacing: 0.10em !important;
  text-transform: uppercase !important;
  border: 1px solid var(--au-line-hi) !important;
  padding: 0.6rem 0.9rem !important;
}
.st-key-auth_panel [data-testid="stAlert"][data-baseweb="notification"][kind="error"],
.st-key-auth_panel [data-testid="stNotificationContentError"],
.st-key-auth_panel [data-testid="stAlertContentError"] {
  background: var(--au-red-soft) !important;
  border-color: var(--au-red-line) !important;
  color: var(--au-red) !important;
}
.st-key-auth_panel [data-testid="stAlert"] svg { fill: currentColor !important; }

/* recovery screen — narrower centered card */
.st-key-auth_recovery {
  min-height: 100vh;
  display: flex !important; flex-direction: column !important;
  align-items: center !important; justify-content: center !important;
  padding: 56px 32px;
  background:
    radial-gradient(900px 600px at 50% 0%, rgba(232,193,112,0.06), transparent 60%),
    radial-gradient(700px 500px at 50% 100%, rgba(230,69,48,0.04), transparent 60%),
    #0A0B0E;
}
.st-key-auth_recovery > div[data-testid="stVerticalBlock"] {
  display: flex !important; flex-direction: column !important;
  align-items: stretch !important;
  width: 100%; max-width: 460px;
  gap: 0 !important;
}

/* ============= RESPONSIVE ========================================= */
@media (max-width: 1180px) {
  .st-key-auth_hero  { padding: 48px 44px; }
  .st-key-auth_panel { padding: 48px 44px; }
  .au-title { font-size: clamp(2.7rem, 4.6vw, 4.4rem); }
}
@media (max-width: 980px) {
  .st-key-auth_root {
    grid-template-columns: 1fr !important;
  }
  .st-key-auth_hero {
    min-height: auto;
    padding: 44px 36px 36px;
    border-right: none;
    border-bottom: 1px solid var(--au-line);
  }
  .st-key-auth_hero::before { display: none; }
  .au-eyebrow { margin-top: 28px; }
  .au-title { font-size: 2.6rem; }
  .au-ladder { grid-template-columns: 1fr; }
  .au-quote { margin-top: 24px; padding-top: 18px; }
  .au-tele { margin-top: 22px; padding-top: 16px; }
  .st-key-auth_panel {
    min-height: auto;
    padding: 36px 24px 56px;
  }
  .au-card-frame { padding: 28px 22px 24px; }
}
@media (max-width: 640px) {
  .st-key-auth_hero  { padding: 32px 22px 28px; }
  .st-key-auth_panel { padding: 26px 14px 44px; }
  .au-title { font-size: 2.15rem; }
  .au-row { grid-template-columns: 30px 1fr; gap: 12px; padding: 10px 12px; }
  .au-row .au-num { width: 30px; height: 30px; font-size: 9.5px; }
  .au-tele { grid-template-columns: 1fr 1fr; gap: 12px 0; }
  .au-tele > div:nth-child(3) {
    grid-column: 1 / -1; padding-top: 14px;
    margin-top: 6px; border-top: 1px solid var(--au-line);
  }
  .au-tele > div:nth-child(3)::before { display: none; }
  .au-tele > div { padding: 0 12px; }
  .au-tele > div:first-child { padding-left: 0; }
  .au-card-frame { padding: 24px 18px 22px; border-radius: 18px; }
  .au-card-title { font-size: 1.85rem; }
}
</style>
"""


# =====================================================================
# Helper render fragments
# =====================================================================
_FEATURE_ROWS = [
    ("01", "Upload one swing",
     "A single phone-clip is all the analyzer needs — no mocap suit, no app subscription gating."),
    ("02", "AI biomechanical breakdown",
     "Pose-tracked metrics across the whole swing — bat path, hip-shoulder separation, head drift, lag time."),
    ("03", "Compare to MLB hitters",
     "Side-by-side reference against pro swings, matched to your build and handedness."),
    ("04", "Personalized drill plan",
     "Top-3 fixes ranked by impact, with the why, the feel, and rep counts that fit your week."),
    ("05", "Track your progress",
     "Every swing logs into your Sessions library — score deltas, MLB sim%, streaks, personal bests."),
]


def _hero_html() -> str:
    """Render the LEFT hero panel as a single self-contained HTML blob.

    No widgets live in the hero, so we can emit it as one big
    `st.markdown` call without falling into the Streamlit 1.57
    markdown-div trap (the trap only matters when widgets need to be
    descendants of the markdown's div — they don't here).
    """
    logo_uri = _bl_logo_data_uri()
    if logo_uri:
        brand_mark = f'<img src="{logo_uri}" alt="BarrelLabs">'
    else:
        brand_mark = ('<span style="width:34px;height:34px;border-radius:50%;'
                      'background:#E64530;display:block;"></span>')

    ladder_html = "".join(
        f'<div class="au-row">'
        f'  <div class="au-num">{n}</div>'
        f'  <div><strong>{html.escape(title)}</strong>'
        f'  <span>{html.escape(body)}</span></div>'
        f'</div>'
        for n, title, body in _FEATURE_ROWS
    )

    return f"""
<div class="au-brand">
  {brand_mark}
  <span>BarrelLabs<span class="sl">/</span><span class="ed">Edge</span></span>
</div>

<div>
  <span class="au-eyebrow">SwingAI · Performance Lab</span>
  <h1 class="au-title">Find your<br/>MLB <span class="twin">swing twin</span><span class="period">.</span></h1>
  <p class="au-sub">
    Upload one swing and walk away with an MLB-grade biomechanical
    breakdown, a side-by-side comparison to the pro you swing like, and
    a personalized drill plan that fits your week — in under a minute.
  </p>
  <div class="au-ladder">{ladder_html}</div>
</div>

<div>
  <div class="au-quote">
    <q>The MLB comparison alone is worth the subscription. Watching my swing
    overlay an MLB hitter on the same frame, with the deltas called out —
    that's the unlock my hitting coach didn't have.</q>
    <cite><em>Travis K.</em> · 16U Travel · D1 commit '27</cite>
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
# Sub-renderers
# =====================================================================
def _render_login_form() -> None:
    """The Sign-In tab. Preserves player_storage.authenticate() exactly
    as the legacy form did."""
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
                help="Keep me signed in for the duration of this browser session.",
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

    # Forgot password — outside the form so clicking it doesn't try to
    # submit; identical session-flag contract as the legacy implementation.
    if st.button(
        "Forgot password?",
        key="forgot_link_v2",
        help="We'll email you a one-time link to set a new password.",
    ):
        st.session_state["auth_mode"] = "forgot"
        st.rerun()

    # Google placeholder + legal
    st.markdown(_google_placeholder_html(), unsafe_allow_html=True)
    st.markdown(_legal_html(), unsafe_allow_html=True)


def _render_signup_form() -> None:
    """The Create-Account tab. Preserves player_storage.create_account()
    exactly. Adds First/Last/Display fields (Display optional) and
    keeps batting hand + height + weight."""
    st.markdown(
        '<div class="au-card-eyebrow">Create account</div>'
        '<h2 class="au-card-title">Create your account.</h2>'
        '<p class="au-card-sub">Start analyzing your swing like the pros. '
        'One swing is all the analyzer needs to give you an MLB-grade report.</p>',
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
            '<div style="margin-top:8px; font-family:var(--au-mono); '
            'font-size:10px; letter-spacing:0.20em; '
            'text-transform:uppercase; color:var(--au-bone-60); '
            'font-weight:600; padding-bottom:6px;">'
            'Physical profile · refines MLB comparisons</div>',
            unsafe_allow_html=True,
        )

        # batting hand — kept as a horizontal radio (Streamlit native;
        # the analyzer needs this from day-one so we don't defer it to
        # Player Settings)
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
                    # Stash the optional display name into the player
                    # settings extras so the player profile picks it up
                    # on first render.
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
    """One-field 'send me a reset link' form. Identical session-flag
    contract as the legacy renderer (auth_mode='forgot' set on entry,
    cleared on back)."""
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

    # Paste-URL fallback — kept verbatim because the legacy flow relies on
    # it when the auto-redirect shim doesn't fire (Gmail mobile, etc.).
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
                "Use this link",
                type="primary",
                use_container_width=True,
            )
            if use_link:
                try:
                    from urllib.parse import urlparse, parse_qs
                    u = urlparse((pasted or "").strip())
                    blob = u.fragment or u.query or ""
                    parts = parse_qs(blob)
                    at = (parts.get("access_token")  or [""])[0]
                    rt = (parts.get("refresh_token") or [""])[0]
                    tp = (parts.get("type")          or [""])[0]
                    if not (at and rt) or tp != "recovery":
                        st.error(
                            "That doesn't look like a valid reset "
                            "link. Make sure you copied the whole URL."
                        )
                    else:
                        from auth import consume_recovery_url
                        if consume_recovery_url(
                            access_token=at,
                            refresh_token=rt,
                        ):
                            st.session_state["recovery_mode"] = True
                            st.rerun()
                        else:
                            st.error(
                                "Couldn't accept that link — it may "
                                "have expired. Send yourself a new "
                                "reset email."
                            )
                except Exception as exc:
                    st.error(f"Couldn't parse that link: {exc}")


# =====================================================================
# Public entry points
# =====================================================================
def render_auth_screen() -> None:
    """Render the split-screen login / signup / forgot-password page.

    Sets `st.session_state.user` on successful login or signup, exactly
    as the legacy renderer did. Routes through Supabase via
    `player_storage.authenticate` / `player_storage.create_account` and
    `auth.request_password_reset` — no auth wiring changed.
    """
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="auth-atmos"></div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-grain"></div>', unsafe_allow_html=True)

    with st.container(key="auth_root"):
        # ============== LEFT: hero panel ==============
        with st.container(key="auth_hero"):
            st.markdown(_hero_html(), unsafe_allow_html=True)

        # ============== RIGHT: auth panel ==============
        with st.container(key="auth_panel"):
            # Decide which form to render based on session flag, then
            # render the segmented toggle + the appropriate form inside
            # the glass card frame.
            mode = st.session_state.get("auth_mode")  # 'forgot' | 'signup' | None
            if mode not in ("forgot", "signup"):
                mode = "login"

            st.markdown('<div class="au-card-frame">', unsafe_allow_html=True)

            if mode != "forgot":
                # toggle — two st.button widgets restyled as segmented
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
            else:  # forgot
                _render_forgot_form()

            st.markdown('</div>', unsafe_allow_html=True)


def render_recovery_screen() -> None:
    """Render the 'set a new password' screen shown when the user
    clicked the password-reset link in their email. Supabase has
    already authenticated them via the recovery token at this point —
    we just collect a new password and call `auth.update_password`.
    """
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown('<div class="auth-atmos"></div>', unsafe_allow_html=True)
    st.markdown('<div class="auth-grain"></div>', unsafe_allow_html=True)

    logo_uri = _bl_logo_data_uri()
    brand_mark = (
        f'<img src="{logo_uri}" alt="BarrelLabs">'
        if logo_uri
        else '<span style="width:34px;height:34px;border-radius:50%;'
             'background:#E64530;display:block;"></span>'
    )

    with st.container(key="auth_recovery"):
        # We piggyback on .st-key-auth_panel widget skin scope by
        # marking the recovery container with both classes via a tiny
        # extra style block. (Cheaper than duplicating all widget CSS.)
        st.markdown(
            '<style>'
            '.st-key-auth_recovery [data-testid="stTextInput"] label,'
            '.st-key-auth_recovery [data-testid="stTextInput"] input,'
            '.st-key-auth_recovery [data-testid="stForm"],'
            '.st-key-auth_recovery [data-testid="stFormSubmitButton"] button,'
            '.st-key-auth_recovery [data-testid="stButton"] button {'
            '  /* hand the recovery container the same scope */ '
            '}'
            '/* re-scope every .st-key-auth_panel rule to also match '
            '   .st-key-auth_recovery by listing it explicitly. */ '
            '.st-key-auth_recovery [data-testid="stTextInput"] label {'
            '  font-family: var(--au-mono) !important; font-size: 10px !important;'
            '  letter-spacing: 0.20em !important; text-transform: uppercase !important;'
            '  color: var(--au-bone-60) !important; font-weight: 600 !important;'
            '  padding-bottom: 6px !important;'
            '}'
            '.st-key-auth_recovery [data-testid="stTextInput"] input {'
            '  background: var(--au-ink-2) !important;'
            '  border: 1px solid var(--au-line-hi) !important;'
            '  border-radius: var(--au-r-mid) !important;'
            '  color: var(--au-bone) !important;'
            '  font-family: var(--au-sans) !important;'
            '  font-size: 14.5px !important;'
            '  padding: 0.7rem 0.95rem !important;'
            '}'
            '.st-key-auth_recovery [data-testid="stTextInput"] input:focus {'
            '  border-color: var(--au-gold-line) !important;'
            '  box-shadow: 0 0 0 3px rgba(232,193,112,0.12) !important;'
            '  outline: none !important;'
            '}'
            '.st-key-auth_recovery [data-testid="stForm"] {'
            '  border: none !important; padding: 0 !important; background: transparent !important;'
            '}'
            '.st-key-auth_recovery [data-testid="stFormSubmitButton"] button[kind="primary"] {'
            '  background: linear-gradient(180deg, var(--au-red) 0%, var(--au-red-deep) 100%) !important;'
            '  color: #FFFAF2 !important; font-weight: 600 !important;'
            '  border: 1px solid rgba(0,0,0,0.25) !important;'
            '  height: 48px !important; padding: 0 22px !important;'
            '  border-radius: var(--au-r-pill) !important;'
            '  font-size: 13.5px !important;'
            '  box-shadow: inset 0 1px 0 rgba(232,193,112,0.55),'
            '              inset 0 -1px 0 rgba(0,0,0,0.35),'
            '              0 10px 24px -8px rgba(230,69,48,0.50) !important;'
            '}'
            '</style>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="au-brand" style="justify-content:center; margin-bottom:32px;">'
            f'{brand_mark}'
            f'<span>BarrelLabs<span class="sl">/</span>'
            f'<span class="ed">Edge</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="au-card-frame">'
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

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(_legal_html(), unsafe_allow_html=True)
