"""
BarrelLabs Edge chrome — shared header (masthead + nav) used across every
authenticated page (Dashboard, Sessions, Swing Report, etc.).

Why this exists
---------------
Before this module, the v3 dashboard had its own Python-rendered nav row
(_render_v3_nav in dashboard_v3.py) AND the in-iframe editorial template
rendered a *decorative* second nav inside the masthead. Two visible navs,
one functional. Sessions appeared to do nothing because the only
functional one looked unrelated to the editorial design.

This module replaces both with a single Edge-styled masthead rendered in
Python so:
  - clicks trigger real Streamlit reruns (auth preserved)
  - the visual language matches the editorial Edge mock exactly
  - every page (Dashboard, Sessions, Report, etc.) shares the same chrome

The in-iframe decorative <nav> in mock_dashboard_template.py is hidden
via CSS injection from render_dashboard_v3() so the editorial template
no longer paints its own nav under this one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import base64
import streamlit as st


# Logo lookup. Resolve relative to THIS file's directory so the asset
# is found regardless of the process working directory (Streamlit can
# launch from anywhere). The official BarrelLabs mark ships at the repo
# root as `barrellabs_logo.png` (underscore) and is mirrored into
# static/ + assets/ as `barrellabs-logo.png` (hyphen). We accept all of
# them so the masthead always finds the real logo — never a fallback.
_HERE = Path(__file__).resolve().parent
_LOGO_CANDIDATES = [
    _HERE / "static" / "barrellabs-logo.png",
    _HERE / "assets" / "barrellabs-logo.png",
    _HERE / "barrellabs_logo.png",   # official repo-root asset (underscore)
    _HERE / "barrellabs-logo.png",
    _HERE / "static" / "logo.png",
]

_LOGO_DATA_URI_CACHE: Optional[str] = None


def _logo_data_uri() -> str:
    """Return a base64 PNG data URI for the official BarrelLabs mark.

    The source PNG is 2000×2000; we downscale to 256×256 with Lanczos
    so the masthead mark is crisp and never stretched/blurred, and we
    cache the result (the logo never changes within a session). Falls
    back to the raw bytes if Pillow is unavailable, and finally to an
    empty string (the masthead then shows its CSS fallback dot).
    """
    global _LOGO_DATA_URI_CACHE
    if _LOGO_DATA_URI_CACHE is not None:
        return _LOGO_DATA_URI_CACHE

    for p in _LOGO_CANDIDATES:
        if not p.exists():
            continue
        # Preferred path: Pillow resize for a crisp, optimized mark.
        try:
            import io
            from PIL import Image
            img = Image.open(p).convert("RGBA").resize((256, 256), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            _LOGO_DATA_URI_CACHE = "data:image/png;base64," + b64
            return _LOGO_DATA_URI_CACHE
        except Exception:
            # Fallback: embed the raw bytes untouched (still crisp, just
            # larger). Never stretch/crop — the <img> CSS uses
            # object-fit:contain so aspect ratio is preserved.
            try:
                b = p.read_bytes()
                ext = p.suffix.lstrip(".").lower() or "png"
                mime = "image/png" if ext == "png" else f"image/{ext}"
                _LOGO_DATA_URI_CACHE = (
                    f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"
                )
                return _LOGO_DATA_URI_CACHE
            except Exception:
                continue

    _LOGO_DATA_URI_CACHE = ""
    return ""


# Nav entries: (label, page_key, alt_keys)
# alt_keys lets a page like swing_report stay active while still hilighting
# Sessions (since reports are accessed *from* the Sessions list).
_NAV_ENTRIES: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("Dashboard",    "dashboard",            ()),
    ("Sessions",     "saved_reports",        ("swing_report",)),  # active for reports too
    ("Compare",      "compare_swings",       ()),
    # "Training Plan" is the user-facing label; page_key stays
    # `development_tracker` so the existing routing, drill-completion
    # storage, gamification (streaks/XP/achievements/rewards), and
    # paywall code keep working untouched. Rename only — no refactor.
    ("Training Plan", "development_tracker", ()),
    ("Library",      "historical_charts",    ()),
]

# Family nav entry is built dynamically per-user in render_edge_masthead
# so it only appears for Family Pro households. We keep a sentinel here
# for callers that introspect _NAV_ENTRIES to resolve active pages.
_FAMILY_NAV_ENTRY: Tuple[str, str, Tuple[str, ...]] = ("Family", "family", ())


_EDGE_MASTHEAD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

/* ====================================================================
   STREAMLIT 1.57 CHROME KILL — verified against the live DOM via
   Playwright. Streamlit 1.57 uses [data-testid="stMain"] (NOT
   section.main) and a [data-testid="stVerticalBlock"] with a DEFAULT
   16px flex gap, plus [data-testid="stMainBlockContainer"] with a
   DEFAULT 96px (6rem) top padding, and an absolute 60px
   [data-testid="stHeader"] (z 999990). The old selectors were scoped
   to section.main / .main / .st-key-* which DO NOT EXIST in 1.57, so
   the 16px gap + 96px padding survived = the "slit" + top dead band.
   Every rule below uses the real 1.57 testids, unscoped, !important,
   in this (last-injected, winning) sheet.
   ==================================================================== */
header[data-testid="stHeader"], .stAppHeader,
[data-testid="stToolbar"], .stAppToolbar,
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stMainMenu"], #MainMenu,
.stAppDeployButton, .stDeployButton, footer {
  display: none !important;
  height: 0 !important; min-height: 0 !important;
  visibility: hidden !important;
}

/* ONE ink on EVERY surface — html→body→stApp→viewContainer→stMain→
   blockContainer→iframe. If every layer is the exact same colour, no
   residual gap/padding can EVER read as a slit or band. */
html, body,
[data-testid="stApp"], .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"], .block-container,
section.main, .main {
  background: #0A0B0E !important;
}

/* Collapse ALL top space with the CORRECT 1.57 testids (unscoped). */
[data-testid="stMain"] { padding-top: 0 !important; margin-top: 0 !important; }
[data-testid="stMainBlockContainer"], .block-container,
section.main > div.block-container {
  padding-top: 0 !important; margin-top: 0 !important;
}
[data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"] { margin: 0 !important; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:first-child {
  margin-top: 0 !important; padding-top: 0 !important;
}
/* legacy fallbacks (harmless if they match nothing) */
section.main [data-testid="stVerticalBlock"] { gap: 0 !important; }
[data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }

/* iframe (dashboard body) butts flush, same ink, no inline gap */
[data-testid="stIFrame"], [data-testid="stCustomComponentV1"],
[data-testid="stElementContainer"] { margin: 0 !important; }
iframe {
  display: block !important; margin: 0 !important;
  vertical-align: top !important; background: #0A0B0E !important;
}
/* the empty anchor div the masthead emits must take zero space */
.ble-host { display: none !important; }

/* Kill the decorative bl_theme glow ONLY where it would tint the very
   top — the masthead sits above it with its own solid ink + z-index. */
[data-testid="stAppViewContainer"]::before { z-index: 0 !important; }

/* ---- Full-bleed bar: ONE solid ink, NO border, NO gradient, NO
   divider — the user wants zero slit, so the bar and the dashboard
   are literally the same surface. z-index lifts it above the glow. */
/* ====================================================================
   MASTHEAD LAYOUT — built from st.container(key=) + st.button so nav
   is IN-SESSION (auth preserved). Streamlit's wrapper divs are made
   display:contents so brand / navbar / chip become direct flex
   children of the keyed bar; the buttons are restyled into premium
   glass tabs. Full-bleed via 100vw + calc() side padding (content
   capped at 1560, bg edge-to-edge, no nested wrapper needed).
   ==================================================================== */
.st-key-bl_edge_masthead {
  position: relative; z-index: 10;
  width: 100vw; left: 50%; right: 50%;
  margin-left: -50vw !important; margin-right: -50vw !important;
  background: #0A0B0E !important; border: 0 !important;
  display: flex !important; flex-direction: row !important;
  flex-wrap: nowrap !important; align-items: center !important;
  gap: 40px !important;
  padding: 13px max(40px, calc((100vw - 1560px) / 2)) !important;
  box-sizing: border-box !important;
}
/* flatten Streamlit's structural wrappers inside the masthead so the
   real children (brand container, navbar, chip) lay out as flex items */
.st-key-bl_edge_masthead > div,
.st-key-bl_edge_masthead > div > div[data-testid="stVerticalBlock"] {
  display: contents !important;
}
.st-key-bl_edge_masthead
  > div > div[data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"] {
  flex: 0 0 auto !important; width: auto !important; margin: 0 !important;
}
/* user chip (streak + avatar button) pinned far right */
.st-key-bl_edge_masthead .st-key-bl_edge_userchip {
  margin-left: auto !important;
}

/* ---- the segmented nav bar — a *recessed slot* in the masthead.
   The previous version had a hard 1px border + 3px drop shadow which
   read as a card "floating" on the masthead. We replace the border
   with an inset shadow gradient (light-top / dark-bottom = looks set
   INTO the surface), drop the outer shadow, and whisper the bg so it
   reads as a refinement of the masthead, not a separate control. */
.st-key-bl_edge_navbar {
  flex: 0 0 auto !important;
  display: flex !important; flex-direction: row !important;
  flex-wrap: nowrap !important; align-items: center !important;
  gap: 2px !important; padding: 4px !important;
  background: rgba(255,255,255,0.012) !important;
  border: 0 !important;
  border-radius: 12px !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.035),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    inset 0 0 0 1px rgba(244,239,230,0.028) !important;
  -webkit-backdrop-filter: blur(8px) saturate(1.1);
  backdrop-filter: blur(8px) saturate(1.1);
}
.st-key-bl_edge_navbar > div,
.st-key-bl_edge_navbar > div > div[data-testid="stVerticalBlock"] {
  display: contents !important;
}
.st-key-bl_edge_navbar [data-testid="stElementContainer"],
.st-key-bl_edge_navbar [data-testid="stButton"] {
  flex: 0 0 auto !important; width: auto !important; margin: 0 !important;
}

/* ---- the tabs: Streamlit buttons restyled, all 1.57 testid variants.
   Apple-style easing (cubic-bezier(.32,.72,0,1)) for color/bg so motion
   feels considered, not generic. Tightened letter-spacing (0.17→0.16em)
   and added Geist Mono stylistic alternates for refined glyphs. */
.st-key-bl_edge_navbar button {
  background: transparent !important;
  border: 1px solid transparent !important;
  color: #80838B !important;
  font-family: 'Geist Mono', ui-monospace, SFMono-Regular, monospace !important;
  font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: 0.16em !important; text-transform: uppercase !important;
  padding: 9px 18px !important; border-radius: 8px !important;
  min-height: 0 !important; height: auto !important; line-height: 1.1 !important;
  box-shadow: none !important; width: auto !important;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "ss01" 1, "ss02" 1, "tnum" 1, "cv11" 1;
  white-space: nowrap !important;
  position: relative;
  transition:
    color 220ms cubic-bezier(.32,.72,0,1),
    background-color 220ms cubic-bezier(.32,.72,0,1),
    border-color 220ms cubic-bezier(.32,.72,0,1),
    box-shadow 220ms cubic-bezier(.32,.72,0,1),
    transform 260ms cubic-bezier(.34,1.4,.64,1);
}
.st-key-bl_edge_navbar button p,
.st-key-bl_edge_navbar button div,
.st-key-bl_edge_navbar button span {
  font: inherit !important; letter-spacing: inherit !important;
  color: inherit !important; margin: 0 !important;
}
.st-key-bl_edge_navbar button:hover {
  color: #EFE9DB !important;
  background: rgba(244,239,230,0.045) !important;
  border-color: rgba(244,239,230,0.075) !important;
  transform: translateY(-0.5px);
}
.st-key-bl_edge_navbar button:active {
  transform: translateY(0) scale(0.985) !important;
  transition-duration: 100ms !important;
}
/* outline: hide on mouse, show subtle gold ring for keyboard users */
.st-key-bl_edge_navbar button:focus { outline: none !important; }
.st-key-bl_edge_navbar button:focus:not(:focus-visible) {
  box-shadow: none !important;
}
.st-key-bl_edge_navbar button:focus-visible {
  outline: none !important;
  box-shadow:
    0 0 0 2px rgba(232,193,112,0.45),
    0 0 0 4px rgba(232,193,112,0.10) !important;
}

/* active tab = type="primary" (cover every 1.57 testid spelling).
   Warmer text (hint of gold sympathy), softer top highlight, faint
   bottom inset darkening, refined gold→red underline that fades at
   both edges so it reads as a glow rather than a hard line. */
.st-key-bl_edge_navbar button[kind="primary"],
.st-key-bl_edge_navbar button[data-testid="stBaseButton-primary"],
.st-key-bl_edge_navbar button[data-testid="baseButton-primary"] {
  color: #F8F2E0 !important;
  background: linear-gradient(180deg,
              rgba(244,239,230,0.095),
              rgba(244,239,230,0.035)) !important;
  border-color: rgba(244,239,230,0.12) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.10),
    inset 0 -1px 0 rgba(0,0,0,0.18),
    0 1px 2px rgba(0,0,0,0.35),
    0 0 16px -6px rgba(232,193,112,0.45) !important;
}
.st-key-bl_edge_navbar button[kind="primary"]:hover,
.st-key-bl_edge_navbar button[data-testid="stBaseButton-primary"]:hover,
.st-key-bl_edge_navbar button[data-testid="baseButton-primary"]:hover {
  color: #FFFAEB !important;
  transform: none !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.14),
    inset 0 -1px 0 rgba(0,0,0,0.18),
    0 1px 2px rgba(0,0,0,0.35),
    0 0 22px -6px rgba(232,193,112,0.6) !important;
}
.st-key-bl_edge_navbar button[kind="primary"]::after,
.st-key-bl_edge_navbar button[data-testid="stBaseButton-primary"]::after,
.st-key-bl_edge_navbar button[data-testid="baseButton-primary"]::after {
  content: ""; position: absolute;
  left: 16px; right: 16px; bottom: 1.5px;
  height: 1.5px; border-radius: 2px;
  background: linear-gradient(90deg,
              rgba(232,193,112,0) 0%,
              #E8C170 28%,
              #E64530 72%,
              rgba(230,69,48,0) 100%);
  box-shadow:
    0 0 10px -1px rgba(232,193,112,0.55),
    0 0 4px -1px rgba(230,69,48,0.35);
}

/* ---- the "extra touch": whisper-thin separator hairline between
   adjacent inactive tabs, like a premium segmented control (Linear,
   Trackman). The hairline is a ::before on each button positioned in
   the half-gap to its LEFT. Hidden on the first button, on the active
   button, and on the button immediately after an active one (so the
   active state never sits next to a divider line on either side). */
.st-key-bl_edge_navbar button::before {
  content: "";
  position: absolute;
  left: -2px;            /* sit in the 2px gap between buttons */
  top: 28%;
  bottom: 28%;
  width: 1px;
  background: linear-gradient(180deg,
              rgba(244,239,230,0) 0%,
              rgba(244,239,230,0.10) 50%,
              rgba(244,239,230,0) 100%);
  opacity: 1;
  pointer-events: none;
  transition: opacity 220ms cubic-bezier(.32,.72,0,1);
}
/* Hide on the first nav item (no left neighbour) */
.st-key-bl_edge_navbar > div > div[data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:first-child button::before {
  opacity: 0;
}
/* Hide on the active button itself (it has its own visual frame) */
.st-key-bl_edge_navbar button[kind="primary"]::before,
.st-key-bl_edge_navbar button[data-testid="stBaseButton-primary"]::before,
.st-key-bl_edge_navbar button[data-testid="baseButton-primary"]::before {
  opacity: 0;
}
/* Hide on the button immediately AFTER an active button (so the
   active tab doesn't have a divider hugging its right edge). Uses
   :has() to detect "the previous stElementContainer wraps a primary
   button" — modern Chrome/Safari/Firefox all support this. */
[data-testid="stElementContainer"]:has(> [data-testid="stButton"]
  > button[kind="primary"])
  + [data-testid="stElementContainer"]
  button::before {
  opacity: 0;
}
/* Hide on hovered button and the button that follows it (so the hover
   bg sits cleanly without a divider biting into it) */
.st-key-bl_edge_navbar button:hover::before {
  opacity: 0;
}
[data-testid="stElementContainer"]:has(> [data-testid="stButton"]
  > button:hover)
  + [data-testid="stElementContainer"]
  button::before {
  opacity: 0;
}

/* ====================================================================
   USER CHIP — streak + clickable avatar button.
   The avatar is a real st.button (auth-safe in-session rerun) restyled
   into a perfect circle showing the player's initials. Clicking it
   routes to the player_settings page.
   ==================================================================== */
.st-key-bl_edge_userchip {
  flex: 0 0 auto !important;
  display: flex !important; flex-direction: row !important;
  align-items: center !important;
  gap: 12px !important;
}
.st-key-bl_edge_userchip > div,
.st-key-bl_edge_userchip > div > div[data-testid="stVerticalBlock"] {
  display: contents !important;
}
.st-key-bl_edge_userchip [data-testid="stElementContainer"],
.st-key-bl_edge_userchip [data-testid="stButton"] {
  flex: 0 0 auto !important; width: auto !important; margin: 0 !important;
}

/* Avatar button — perfect circle with the player's initials,
   gold-tinted ring on hover so the player understands it's clickable
   and feels like the editorial brand "stamp". */
.st-key-bl_edge_userchip button {
  width: 38px !important; height: 38px !important;
  min-height: 38px !important; max-height: 38px !important;
  padding: 0 !important;
  border-radius: 50% !important;
  background: linear-gradient(135deg, #23262C, #101319) !important;
  border: 1px solid rgba(244,239,230,0.14) !important;
  color: #F4EFE6 !important;
  font-family: 'Instrument Serif', Georgia, serif !important;
  font-style: italic !important;
  font-size: 15px !important;
  font-weight: 400 !important;
  letter-spacing: 0 !important;
  line-height: 1 !important;
  text-transform: none !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.06),
    inset 0 -1px 0 rgba(0,0,0,0.30),
    0 1px 3px rgba(0,0,0,0.45) !important;
  position: relative;
  cursor: pointer;
  transition:
    border-color 220ms cubic-bezier(.32,.72,0,1),
    box-shadow 220ms cubic-bezier(.32,.72,0,1),
    transform 260ms cubic-bezier(.34,1.4,.64,1),
    color 220ms cubic-bezier(.32,.72,0,1);
}
.st-key-bl_edge_userchip button p,
.st-key-bl_edge_userchip button div,
.st-key-bl_edge_userchip button span {
  font: inherit !important; letter-spacing: 0 !important;
  color: inherit !important; margin: 0 !important; line-height: 1 !important;
  text-transform: none !important;
}
.st-key-bl_edge_userchip button:hover {
  color: #FFFAEB !important;
  border-color: rgba(232,193,112,0.55) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.10),
    inset 0 -1px 0 rgba(0,0,0,0.30),
    0 0 0 3px rgba(232,193,112,0.10),
    0 0 16px -4px rgba(232,193,112,0.45) !important;
  transform: translateY(-0.5px);
}
.st-key-bl_edge_userchip button:active {
  transform: translateY(0) scale(0.96) !important;
  transition-duration: 100ms !important;
}
.st-key-bl_edge_userchip button:focus { outline: none !important; }
.st-key-bl_edge_userchip button:focus:not(:focus-visible) {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.06),
    inset 0 -1px 0 rgba(0,0,0,0.30),
    0 1px 3px rgba(0,0,0,0.45) !important;
}
.st-key-bl_edge_userchip button:focus-visible {
  outline: none !important;
  border-color: rgba(232,193,112,0.60) !important;
  box-shadow:
    0 0 0 2px rgba(232,193,112,0.50),
    0 0 0 4px rgba(232,193,112,0.12) !important;
}

/* ---- brand (left) + user chip (right) — unchanged look ---- */
.ble-brand { display: flex; align-items: center; gap: 13px;
  flex: 0 0 auto; }
.ble-brand img { width: 30px; height: 30px; object-fit: contain;
  display: block; }
.ble-brand .wm { font-size: 13px; font-weight: 600; letter-spacing: 0.24em;
  text-transform: uppercase; color: #F4EFE6; white-space: nowrap; }
.ble-brand .wm .sl { color: #3A3D44; margin: 0 9px; font-weight: 300; }
.ble-brand .wm .ed { font-family: 'Instrument Serif', Georgia, serif;
  font-style: italic; font-weight: 400; font-size: 16px; letter-spacing: 0;
  text-transform: none; color: #8B8E94; }
.ble-streak { font-family: 'Geist Mono', monospace; font-size: 10.5px;
  letter-spacing: 0.04em; color: #E8C170; padding: 5px 11px;
  border-radius: 999px; border: 1px solid rgba(232,193,112,0.26);
  background: rgba(232,193,112,0.07); white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px; }
.ble-streak .d { width: 5px; height: 5px; border-radius: 50%;
  background: #E8C170; }

@media (max-width: 1100px) {
  .st-key-bl_edge_masthead {
    gap: 22px !important;
    padding: 11px max(20px, calc((100vw - 1560px) / 2)) !important;
  }
  .st-key-bl_edge_navbar button {
    padding: 8px 12px !important; font-size: 10px !important;
    letter-spacing: 0.13em !important;
  }
  .st-key-bl_edge_navbar button[kind="primary"]::after,
  .st-key-bl_edge_navbar button[data-testid="stBaseButton-primary"]::after,
  .st-key-bl_edge_navbar button[data-testid="baseButton-primary"]::after {
    left: 12px; right: 12px;
  }
  .ble-brand .wm { font-size: 12px; }
}
@media (max-width: 720px) {
  .st-key-bl_edge_masthead {
    flex-wrap: wrap !important; row-gap: 10px !important;
    padding: 11px 14px !important; gap: 0 !important;
  }
  .ble-streak { display: none; }
  .st-key-bl_edge_masthead [data-testid="stElementContainer"]:has(.ble-brand) {
    flex: 1 1 auto !important;
  }
  .st-key-bl_edge_navbar {
    order: 3; flex: 1 0 100% !important;
    overflow-x: auto; -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .st-key-bl_edge_navbar::-webkit-scrollbar { display: none; }
  .st-key-bl_edge_navbar button { padding: 7px 13px !important; }
}
</style>
"""


def _initials(user: Dict[str, Any]) -> str:
    name = (user or {}).get("name") or (user or {}).get("display_name") or ""
    name = str(name).strip()
    if name:
        parts = [p for p in name.split() if p]
        if parts:
            return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    email = (user or {}).get("email") or ""
    if email:
        return email[:1].upper()
    return "B"


def _streak_value(user: Dict[str, Any]) -> Optional[int]:
    """Pull current streak from the gamification fields if present."""
    gam = (user or {}).get("gamification") or {}
    try:
        v = gam.get("current_streak_days") or (user or {}).get("current_streak_days")
        if v is None:
            return None
        v = int(v)
        return v if v > 0 else None
    except Exception:
        return None


def _resolve_active(active_page: str) -> str:
    """Map sub-pages (e.g., swing_report) to their parent nav entry."""
    all_entries = list(_NAV_ENTRIES) + [_FAMILY_NAV_ENTRY]
    for label, key, alts in all_entries:
        if active_page == key or active_page in alts:
            return key
    return "dashboard"


def _show_family_nav(user: Optional[Dict[str, Any]]) -> bool:
    """Return True if the Family nav item should appear for this user."""
    try:
        import family_storage
        uid = (user or {}).get("user_id") or (user or {}).get("id") or ""
        return bool(
            family_storage.is_family_pro_member(uid)
            or family_storage.load_family_for_user(uid) is not None
        )
    except Exception:
        return False


def render_edge_masthead(
    user: Optional[Dict[str, Any]] = None,
    *,
    active_page: str = "dashboard",
    streak_days: Optional[int] = None,
) -> None:
    """
    Render the unified Edge masthead: brand + functional nav + user chip.

    This is the ONLY navigation system in the app. It replaces the old
    full-width 5-button row and the in-iframe decorative pill row.

    Args:
        user: the logged-in user dict (used for streak + initials).
        active_page: the page_key currently selected. Sub-pages like
            'swing_report' will resolve to their parent ('saved_reports').
        streak_days: optional explicit streak override; falls back to
            user["gamification"]["current_streak_days"] when omitted.
    """
    st.markdown(_EDGE_MASTHEAD_CSS, unsafe_allow_html=True)

    user = user or {}
    active = _resolve_active(active_page)

    logo_uri = _logo_data_uri()
    if logo_uri:
        brand_mark = f'<img src="{logo_uri}" alt="BarrelLabs">'
    else:
        brand_mark = ('<span style="width:30px;height:30px;border-radius:50%;'
                      'background:#E64530;display:block;"></span>')

    streak = streak_days if streak_days is not None else _streak_value(user)
    initials = _initials(user)
    streak_html = (
        f'<span class="ble-streak"><span class="d"></span>{streak}-day streak</span>'
        if streak is not None else ""
    )

    # IN-SESSION nav (st.button + st.rerun) — NOT <a href> anchors.
    # A full browser navigation starts a fresh Streamlit session with
    # empty st.session_state, and this app keeps the Supabase auth
    # session ONLY in st.session_state (no durable cookie), so anchor
    # nav logged the user out on every click and the stale ?page= in
    # the address bar made re-login land on the swing-report page.
    # st.button triggers an in-session rerun: session_state (incl.
    # auth) is preserved and no ?page= is ever written to the URL.
    # The buttons are restyled into the premium glass tabs via CSS
    # scoped to .st-key-bl_edge_navbar.
    with st.container(key="bl_edge_masthead"):
        st.markdown(
            f"""
<div class="ble-brand">
  {brand_mark}
  <span class="wm">BarrelLabs<span class="sl">/</span><span class="ed">Edge</span></span>
</div>
""",
            unsafe_allow_html=True,
        )
        # Leave-page guard: when the user is on the Player Settings page,
        # ALWAYS route nav clicks through ps_pending_nav_to instead of
        # navigating immediately. The Player Settings page itself decides
        # whether to show the leave dialog (if there are unsaved edits)
        # or to navigate through immediately (if nothing's dirty).
        #
        # We don't gate this on ps_is_dirty here, because the masthead
        # renders BEFORE the page's dirty-state recompute on each rerun
        # — so reading session_state["ps_is_dirty"] at masthead time
        # would give stale (N-1) state. Letting the page own the dirty
        # decision keeps the prompt accurate even when the user types
        # and immediately clicks a nav tab in the same rerun.
        _ps_intercept = (st.session_state.get("page") == "player_settings")

        # Build nav entry list: static entries + conditional Family item.
        # Family appears after Sessions (index 1) so it reads as a
        # sibling to the individual player's session view.
        _show_fam = _show_family_nav(user)
        _nav_to_render = []
        for _entry in _NAV_ENTRIES:
            _nav_to_render.append(_entry)
            if _entry[1] == "saved_reports" and _show_fam:
                _nav_to_render.append(_FAMILY_NAV_ENTRY)

        with st.container(key="bl_edge_navbar"):
            for label, page_key, _alts in _nav_to_render:
                if st.button(
                    label,
                    key=f"_ble_nav_{page_key}",
                    type=("primary" if active == page_key else "secondary"),
                ):
                    if _ps_intercept and page_key != "player_settings":
                        # Stash the destination; the Player Settings page
                        # picks it up on the next rerun and either shows
                        # the leave dialog (dirty) or navs through (clean).
                        st.session_state["ps_pending_nav_to"] = page_key
                        st.rerun()
                    st.session_state["page"] = page_key
                    # Scrub stale open-report state so a nav click can't
                    # be hijacked by the _should_open_report guard.
                    if page_key != "swing_report":
                        for _k in ("view_swing_record", "view_swing_path",
                                   "view_swing_report_id", "view"):
                            st.session_state.pop(_k, None)
                    st.rerun()
        # Switch Profile button — visible only for multi-profile households.
        # Sets _action so app.py drops the active profile and re-shows picker.
        try:
            import auth as _auth_chrome
            _show_switch = _auth_chrome.current_household_seats() > 1
        except Exception:
            _show_switch = False
        if _show_switch:
            if st.button(
                "Switch profile",
                key="bl_switch_profile",
                type="secondary",
            ):
                st.session_state["_action"] = "switch_profile"
                st.rerun()

        # User chip: streak (markdown) + clickable avatar (st.button).
        # The avatar is a real button so clicking it triggers an in-session
        # rerun (auth preserved) and routes to the Player Settings page.
        with st.container(key="bl_edge_userchip"):
            if streak_html:
                st.markdown(streak_html, unsafe_allow_html=True)
            if st.button(
                initials,
                key="_ble_avatar_btn",
                type=("primary" if active == "player_settings" else "secondary"),
                help="Player Settings",
            ):
                # Clicking the avatar from the settings page itself is a
                # no-op (it's the page you're already on) — but we still
                # rerun cleanly. Otherwise route to settings.
                if active != "player_settings":
                    st.session_state["page"] = "player_settings"
                    for _k in ("view_swing_record", "view_swing_path",
                               "view_swing_report_id", "view"):
                        st.session_state.pop(_k, None)
                st.rerun()




def hide_iframe_decorative_nav() -> None:
    """
    Inject CSS that hides the decorative <nav class="nav"> inside the
    Edge mock iframe so it doesn't double up with the Python-rendered
    masthead above. Targets the iframe content by injecting a CSS rule
    that piggybacks on the iframe's parent document scope where
    possible; the iframe also internally hides its nav on small
    viewports already (mock_dashboard_template line 1452).
    """
    st.markdown(
        """
        <style>
          /* Try to hide via the iframe's own document scope (works when
             the iframe inherits styles — for components.html it does NOT,
             so the editorial template was patched to hide .nav itself).
             This is a defense-in-depth declaration for any pages that
             render the same iframe content. */
          iframe[title="streamlit_component_html"] { /* no-op anchor */ }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_edge_page_wrapper_open(*, max_width: int = 1560) -> None:
    """Open a centered Edge-styled content wrapper below the masthead."""
    st.markdown(
        f"""
        <style>
          /* NOTE: render_edge_page_wrapper_open emits an *unclosed*
             <div class="bl-edge-page"> which Streamlit auto-closes into
             an EMPTY sibling node — it never actually wraps the page
             content. Previously it carried `min-height:60vh` + 36px
             padding, so that phantom box rendered as a huge blank
             spacer ABOVE every page (the "massive dead space" on
             Sessions). The real layout/max-width/padding is owned by
             each page's own wrapper (.srl-wrap, .srd-wrap, .bl-page),
             so this is now a zero-impact no-op. */
          /* display:contents — the phantom wrapper div generates NO box
             at all, so it can never add a sliver of dead space between
             the masthead and the real page content. */
          .bl-edge-page {{
            display: contents;
          }}
          /* Make sure Streamlit's own block-container doesn't fight us,
             and collapse the default inter-block gap so the page hugs
             the masthead's bottom divider (no excessive blank band).
             Each page owns its real spacing via .srl-wrap / .srd-wrap. */
          [data-testid="stAppViewContainer"] > .main {{ padding: 0 !important; }}
          .block-container {{ padding: 0 !important; max-width: 100% !important; }}
          [data-testid="stMainBlockContainer"] {{ padding-top: 0 !important; }}
          [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] {{
            gap: 0.25rem !important;
          }}
          body, html, [data-testid="stAppViewContainer"] {{ background: #0A0B0E !important; }}
          header[data-testid="stHeader"], [data-testid="stSidebar"],
          [data-testid="stToolbar"], [data-testid="stDecoration"], footer {{
            display: none !important;
          }}
        </style>
        <div class="bl-edge-page">
        """,
        unsafe_allow_html=True,
    )


def render_edge_page_wrapper_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
