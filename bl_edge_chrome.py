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
  /* Wrapper for the Python-rendered Edge masthead. Lives OUTSIDE the
     iframe so clicks trigger real Streamlit reruns and Supabase auth
     tokens in st.session_state survive. */
  /* Kill ALL dead space above the header so the page is seamless from
     the very top — no "big black box" band. Applies on every page
     since this CSS ships with the masthead. */
  [data-testid="stMainBlockContainer"],
  section.main > div.block-container,
  .block-container {
    padding-top: 0 !important;
  }
  [data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }

  /* THE MASTHEAD IS A SINGLE FLEX ROW — no st.columns (nested columns
     auto-stack in Streamlit and inflate the header into a tall mess).
     The keyed container itself is laid out as one horizontal,
     non-wrapping bar: [brand] [nav links] ......... [user chip]. */
  .st-key-bl_edge_masthead {
    background: #0A0B0E;
    border-bottom: 1px solid rgba(244,239,230,0.08);
    padding: 12px 48px;
    position: relative;
  }
  .st-key-bl_edge_masthead,
  .st-key-bl_edge_masthead > [data-testid="stVerticalBlock"],
  .st-key-bl_edge_masthead [data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 4px !important;
    row-gap: 0 !important;
  }
  .st-key-bl_edge_masthead [data-testid="stElementContainer"] {
    width: auto !important;
    flex: 0 0 auto !important;
    margin: 0 !important;
  }
  /* Brand flush-left with breathing room; user chip pinned far-right. */
  .st-key-bl_edge_masthead [data-testid="stElementContainer"]:first-child {
    margin-right: 22px !important;
  }
  .st-key-bl_edge_masthead [data-testid="stElementContainer"]:last-child {
    margin-left: auto !important;
  }
  .st-key-bl_edge_masthead::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: -1px;
    height: 1px; pointer-events: none;
    background: linear-gradient(90deg, transparent, rgba(244,239,230,0.16) 20%,
                rgba(244,239,230,0.16) 80%, transparent);
  }
  /* BRAND column */
  .bl-edge-brand {
    display: flex; align-items: center; gap: 16px;
    min-height: 42px;
  }
  .bl-edge-brand-mark {
    width: 42px; height: 42px; display: block; flex-shrink: 0;
    object-fit: contain;
    image-rendering: -webkit-optimize-contrast;
  }
  .bl-edge-brand-mark.is-fallback {
    /* Plain dot if no logo asset is found — keeps the layout intact */
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #E64530;
    box-shadow: 0 0 0 1px rgba(244,239,230,0.10);
  }
  .bl-edge-wordmark {
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    font-weight: 600; font-size: 14px;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: #F4EFE6;
    white-space: nowrap;
  }
  .bl-edge-wordmark .sep { color: #565A62; margin: 0 10px; font-weight: 300; }
  .bl-edge-wordmark .product {
    font-family: 'Instrument Serif', 'Fraunces', Georgia, serif;
    font-style: italic; font-weight: 400;
    font-size: 17px; letter-spacing: 0; text-transform: none;
    color: #F4EFE6;
  }
  /* NAV column — integrated text tabs, NOT stretched chunky pills.
     width:fit-content so each tab hugs its label; small 8px radius so
     the active state reads as a refined tab, never a giant pill. */
  .st-key-bl_edge_masthead .stButton { display: inline-block; }
  .st-key-bl_edge_masthead .stButton > button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: #8B8E94 !important;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    font-size: 11.5px !important;
    font-weight: 500 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 7px 14px !important;
    border-radius: 8px !important;
    width: fit-content !important;
    min-height: 0 !important;
    box-shadow: none !important;
    transition: color 0.18s, background 0.18s, border-color 0.18s;
  }
  .st-key-bl_edge_masthead .stButton > button:hover {
    color: #F4EFE6 !important;
    background: rgba(244,239,230,0.05) !important;
  }
  /* Active tab — SUBTLE premium treatment: faint translucent bone
     tint + bone text + hairline border (no solid white block, no big
     pill). Covers every Streamlit button-testid variant across
     versions: kind=, baseButton-, stBaseButton-. */
  .st-key-bl_edge_masthead .stButton > button[kind="primary"],
  .st-key-bl_edge_masthead .stButton > button[data-testid="baseButton-primary"],
  .st-key-bl_edge_masthead .stButton > button[data-testid="stBaseButton-primary"] {
    color: #F4EFE6 !important;
    background: rgba(244,239,230,0.09) !important;
    border-color: rgba(244,239,230,0.16) !important;
    font-weight: 600 !important;
  }
  .st-key-bl_edge_masthead .stButton > button[kind="primary"]:hover,
  .st-key-bl_edge_masthead .stButton > button[data-testid="baseButton-primary"]:hover,
  .st-key-bl_edge_masthead .stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: rgba(244,239,230,0.13) !important;
  }
  /* Make sure secondary (inactive) never shows Streamlit's default
     border/fill — it must read as a quiet text tab. */
  .st-key-bl_edge_masthead .stButton > button[kind="secondary"],
  .st-key-bl_edge_masthead .stButton > button[data-testid="baseButton-secondary"],
  .st-key-bl_edge_masthead .stButton > button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border-color: transparent !important;
  }
  /* Wrap the 5 nav buttons in an outer pill container */
  .bl-edge-nav-pillbox {
    display: flex; gap: 4px; padding: 4px;
    border: 1px solid rgba(244,239,230,0.08); border-radius: 100px;
    background: rgba(255,255,255,0.025);
    width: fit-content; margin: 0 auto;
  }
  /* USER chip column — streak + avatar */
  .bl-edge-user-chip { display: flex; align-items: center; gap: 12px; justify-content: flex-end; }
  .bl-edge-user-streak {
    font-family: 'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;
    font-size: 11px; letter-spacing: 0.05em; color: #E8C170;
    padding: 5px 10px;
    border: 1px solid rgba(232,193,112,0.30);
    border-radius: 100px;
    background: rgba(232,193,112,0.10);
    white-space: nowrap;
  }
  .bl-edge-user-streak .dot {
    display: inline-block; width: 6px; height: 6px;
    border-radius: 50%; background: #E8C170;
    margin-right: 6px; transform: translateY(-1px);
  }
  .bl-edge-user-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, #2A2D33, #11141A);
    border: 1px solid rgba(244,239,230,0.12);
    color: #F4EFE6; font-family: 'Geist Mono', monospace; font-size: 12px;
    font-weight: 600;
    display: inline-flex; align-items: center; justify-content: center;
    text-transform: uppercase;
  }
  /* Responsive — collapse nav to scrollable strip on narrow viewports */
  @media (max-width: 1100px) {
    .st-key-bl_edge_masthead { padding: 12px 20px 10px; }
    .st-key-bl_edge_masthead div[data-testid="stHorizontalBlock"] {
      gap: 16px !important;
    }
    .bl-edge-nav-pillbox { padding: 3px; }
    .st-key-bl_edge_masthead .stButton > button {
      font-size: 10.5px !important;
      padding: 7px 10px !important;
      letter-spacing: 0.04em !important;
    }
  }
  @media (max-width: 760px) {
    .bl-edge-user-streak { display: none; }
  }
  /* Hide the in-iframe decorative nav inside mock_dashboard_template.
     The iframe's <header class="masthead"> still renders the issue
     line context, but the duplicate pill nav is suppressed so only
     the Python-rendered masthead is visible. */
  iframe[title="streamlit_component_html"] + style[data-bl-hide-iframe-nav],
  iframe + style[data-bl-hide-iframe-nav] { display: none; }
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

    # Logo data URI (or fallback dot)
    logo_uri = _logo_data_uri()
    if logo_uri:
        brand_mark = f'<img class="bl-edge-brand-mark" src="{logo_uri}" alt="BarrelLabs">'
    else:
        brand_mark = '<span class="bl-edge-brand-mark is-fallback" aria-hidden="true"></span>'

    streak = streak_days if streak_days is not None else _streak_value(user)
    initials = _initials(user)

    # IMPORTANT: a real keyed st.container is used (NOT a bare
    # `st.markdown("<div ...>")` marker). Streamlit auto-closes an
    # unclosed markdown div into an EMPTY sibling node, so descendant
    # CSS like `.st-key-bl_edge_masthead .stButton` never matched the
    # nav buttons — they fell back to chunky default Streamlit buttons,
    # and the empty marker div added dead vertical space. A keyed
    # container yields a real wrapper `.st-key-bl_edge_masthead` that
    # actually contains the columns/buttons, so the premium nav CSS
    # applies and there's no phantom spacer.
    # Single flex row — NO st.columns. Nested Streamlit columns
    # auto-stack below a width breakpoint, which wrapped the nav onto
    # multiple lines and inflated the masthead into a tall black slab.
    # Rendering brand → nav buttons → chip as plain sequential elements
    # inside one keyed container, then laying that container out as a
    # flex row via CSS, yields a clean single-line header that never
    # wraps and sits flush at the very top of the page.
    with st.container(key="bl_edge_masthead"):
        # Brand (far left)
        st.markdown(
            f"""
            <div class="bl-edge-brand">
              {brand_mark}
              <div class="bl-edge-wordmark">
                Barrellabs <span class="sep">/</span><span class="product">Edge</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Nav links (left group, next to the brand)
        for label, page_key, _alts in _NAV_ENTRIES:
            btn_type = "primary" if active == page_key else "secondary"
            if st.button(label, key=f"_edge_nav_{page_key}", type=btn_type):
                # Navigate: set page, clear any sub-page record state so
                # deep-linked records don't override the click.
                st.session_state["page"] = page_key
                st.session_state.pop("view_swing_record", None)
                st.session_state.pop("view_swing_path", None)
                st.session_state.pop("view_swing_report_id", None)
                st.session_state.pop("view", None)
                st.rerun()

        # User chip (pinned far right via margin-left:auto in CSS)
        chip_parts = []
        if streak is not None:
            chip_parts.append(
                f'<span class="bl-edge-user-streak">'
                f'<span class="dot"></span>{streak}-day streak'
                f'</span>'
            )
        chip_parts.append(
            f'<span class="bl-edge-user-avatar" aria-label="account">{initials}</span>'
        )
        st.markdown(
            '<div class="bl-edge-user-chip">' + "".join(chip_parts) + '</div>',
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
