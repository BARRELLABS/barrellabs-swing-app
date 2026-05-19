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
    ("Dashboard", "dashboard",            ()),
    ("Sessions",  "saved_reports",        ("swing_report",)),  # active for reports too
    ("Compare",   "compare_swings",       ()),
    ("Drills",    "development_tracker",  ()),
    ("Library",   "historical_charts",    ()),
]


_EDGE_MASTHEAD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

/* ---- Strip every scrap of Streamlit chrome + top dead space so the
   masthead is the FIRST thing on the page, flush to the very top. ---- */
header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
.stAppDeployButton, .stDeployButton, #MainMenu, footer {
  display: none !important; height: 0 !important; visibility: hidden !important;
}
[data-testid="stAppViewContainer"] { background: #0A0B0E !important; }
[data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }
section.main > div.block-container,
[data-testid="stMainBlockContainer"], .block-container {
  padding-top: 0 !important; margin-top: 0 !important;
}
[data-testid="stMainBlockContainer"] > div:first-child,
.block-container > div:first-child { margin-top: 0 !important; }
/* The single st.markdown that holds the masthead must add no box of its
   own — it should be invisible structurally so the bar is seamless. */
.st-key-bl_edge_masthead, .ble-host { margin: 0 !important; padding: 0 !important; }

/* ---- Full-bleed flex bar, edge-to-edge, same ink as the dashboard ---- */
.ble-mast {
  position: relative;
  width: 100vw; left: 50%; right: 50%;
  margin-left: -50vw; margin-right: -50vw;
  background: #0A0B0E;
  border-bottom: 1px solid rgba(244,239,230,0.07);
}
.ble-mast::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 1px;
  background: linear-gradient(90deg, transparent,
              rgba(232,193,112,0.22) 32%, rgba(230,69,48,0.22) 68%, transparent);
  pointer-events: none;
}
.ble-inner {
  max-width: 1560px; margin: 0 auto;
  padding: 15px 40px;
  display: flex; align-items: center; gap: 44px;
  font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
}

/* brand */
.ble-brand { display: flex; align-items: center; gap: 13px; flex: 0 0 auto;
  text-decoration: none; }
.ble-brand img { width: 30px; height: 30px; object-fit: contain; display: block; }
.ble-brand .wm { font-size: 13px; font-weight: 600; letter-spacing: 0.24em;
  text-transform: uppercase; color: #F4EFE6; white-space: nowrap; }
.ble-brand .wm .sl { color: #3A3D44; margin: 0 9px; font-weight: 300; }
.ble-brand .wm .ed { font-family: 'Instrument Serif', Georgia, serif;
  font-style: italic; font-weight: 400; font-size: 16px; letter-spacing: 0;
  text-transform: none; color: #8B8E94; }

/* nav — refined editorial text tabs, no pills, no boxes */
.ble-nav { display: flex; align-items: center; gap: 2px; flex: 1 1 auto; }
.ble-tab { position: relative; text-decoration: none;
  font-family: 'Geist Mono', ui-monospace, SFMono-Regular, monospace;
  font-size: 11px; font-weight: 500; letter-spacing: 0.16em;
  text-transform: uppercase; color: #76797F;
  padding: 9px 16px; border-radius: 7px;
  transition: color .18s ease, background .18s ease; }
.ble-tab:hover { color: #F4EFE6; background: rgba(244,239,230,0.04); }
.ble-tab.is-active { color: #F4EFE6; }
.ble-tab.is-active::after { content: ""; position: absolute;
  left: 16px; right: 16px; bottom: 3px; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, #E8C170, #E64530); }

/* user chip */
.ble-user { display: flex; align-items: center; gap: 12px; flex: 0 0 auto;
  margin-left: auto; }
.ble-streak { font-family: 'Geist Mono', monospace; font-size: 10.5px;
  letter-spacing: 0.04em; color: #E8C170; padding: 5px 11px; border-radius: 999px;
  border: 1px solid rgba(232,193,112,0.26); background: rgba(232,193,112,0.07);
  white-space: nowrap; display: flex; align-items: center; gap: 6px; }
.ble-streak .d { width: 5px; height: 5px; border-radius: 50%; background: #E8C170; }
.ble-av { width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, #23262C, #101319);
  border: 1px solid rgba(244,239,230,0.12); color: #F4EFE6;
  font-family: 'Instrument Serif', Georgia, serif; font-style: italic;
  font-size: 14px; display: flex; align-items: center; justify-content: center; }

@media (max-width: 1100px) {
  .ble-inner { padding: 12px 22px; gap: 22px; }
  .ble-tab { padding: 8px 11px; font-size: 10px; letter-spacing: 0.12em; }
  .ble-brand .wm { font-size: 12px; }
}
@media (max-width: 720px) {
  /* Mobile: brand + avatar on one row, nav becomes a clean
     single-line swipeable strip beneath — never a vertical stack. */
  .ble-inner { flex-wrap: wrap; row-gap: 10px; padding: 11px 16px; gap: 0; }
  .ble-brand { flex: 1 1 auto; }
  .ble-streak { display: none; }
  .ble-user { margin-left: auto; }
  .ble-nav {
    order: 3; flex: 1 0 100%;
    flex-wrap: nowrap; gap: 2px;
    overflow-x: auto; -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    margin: 2px -16px -11px; padding: 6px 16px 8px;
    border-top: 1px solid rgba(244,239,230,0.06);
  }
  .ble-nav::-webkit-scrollbar { display: none; }
  .ble-tab { padding: 7px 12px; flex: 0 0 auto; }
  .ble-tab.is-active::after { bottom: 2px; }
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
    for label, key, alts in _NAV_ENTRIES:
        if active_page == key or active_page in alts:
            return key
    return "dashboard"


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

    tabs = []
    for label, page_key, _alts in _NAV_ENTRIES:
        cls = "ble-tab is-active" if active == page_key else "ble-tab"
        tabs.append(
            f'<a class="{cls}" href="?page={page_key}" target="_self">{label}</a>'
        )
    nav_html = "".join(tabs)

    # ONE pure-HTML block — no st.columns, no st.button. Navigation
    # rides the existing ?page= URL bridge (auth is restored on reload
    # via auth.current_profile), so there is zero Streamlit widget
    # chrome: the bar is fully designed, full-bleed, and seamless with
    # the dashboard below it.
    st.markdown(
        f"""
<div class="ble-host"></div>
<div class="ble-mast"><div class="ble-inner">
  <a class="ble-brand" href="?page=dashboard" target="_self">
    {brand_mark}
    <span class="wm">BarrelLabs<span class="sl">/</span><span class="ed">Edge</span></span>
  </a>
  <div class="ble-nav">{nav_html}</div>
  <div class="ble-user">{streak_html}<span class="ble-av">{initials}</span></div>
</div></div>
""",
        unsafe_allow_html=True,
    )




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
