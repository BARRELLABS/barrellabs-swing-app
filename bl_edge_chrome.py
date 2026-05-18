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


# Logo lookup — match the path dashboard_v3 uses so the iframe and the
# Python-rendered chrome share the same mark.
_LOGO_CANDIDATES = [
    Path("static/barrellabs-logo.png"),
    Path("static/logo.png"),
    Path("assets/barrellabs-logo.png"),
    Path("barrellabs-logo.png"),
]


def _logo_data_uri() -> str:
    """Return a data: URI for the BarrelLabs mark, or an empty string."""
    for p in _LOGO_CANDIDATES:
        if p.exists():
            try:
                b = p.read_bytes()
                ext = p.suffix.lstrip(".") or "png"
                mime = "image/png" if ext.lower() == "png" else f"image/{ext}"
                return f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"
            except Exception:
                continue
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
  /* ============================================================
     CRITICAL: Streamlit renders st.button widgets in SIBLING DOM
     containers, NOT as descendants of any `st.markdown` div. So we
     cannot scope styles via a wrapping `data-bl-edge-masthead` div.
     Instead we target buttons by their `key` via the `.st-key-<key>`
     class Streamlit (1.36+) adds to widget containers. This works
     regardless of where the button sits in the DOM tree.
     ============================================================ */

  /* The masthead "row" container — Streamlit's stHorizontalBlock
     wrapping our 3-column layout. We pin its appearance and tighten
     its padding so the nav row is a compact strip, not a hero band. */
  div[data-bl-edge-masthead-row] {
    background: #0A0B0E;
    border-bottom: 1px solid rgba(244,239,230,0.08);
    padding: 16px 56px 14px;
    margin: 0 -1rem 0 -1rem;  /* counter Streamlit's default block padding */
    position: relative;
  }
  div[data-bl-edge-masthead-row]::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: -1px;
    height: 1px; pointer-events: none;
    background: linear-gradient(90deg, transparent, rgba(244,239,230,0.16) 20%,
                rgba(244,239,230,0.16) 80%, transparent);
  }
  /* Streamlit puts our 3 columns inside an stHorizontalBlock. We
     vertically center their contents and cap the row's max width. */
  div[data-bl-edge-masthead-row] [data-testid="stHorizontalBlock"] {
    max-width: 1560px;
    margin: 0 auto;
    align-items: center !important;
    gap: 28px !important;
  }

  /* BRAND column */
  .bl-edge-brand {
    display: flex; align-items: center; gap: 14px;
    min-height: 40px;
  }
  .bl-edge-brand-mark {
    width: 36px; height: 36px; display: block; flex-shrink: 0;
    object-fit: contain;
    image-rendering: -webkit-optimize-contrast;
  }
  .bl-edge-brand-mark.is-fallback {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #E64530;
    box-shadow: 0 0 0 1px rgba(244,239,230,0.10);
  }
  .bl-edge-wordmark {
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    font-weight: 600; font-size: 13px;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: #F4EFE6;
    white-space: nowrap;
  }
  .bl-edge-wordmark .sep { color: #565A62; margin: 0 8px; font-weight: 300; }
  .bl-edge-wordmark .product {
    font-family: 'Instrument Serif', 'Fraunces', Georgia, serif;
    font-style: italic; font-weight: 400;
    font-size: 17px; letter-spacing: 0; text-transform: none;
    color: #F4EFE6;
  }

  /* ============================================================
     NAV BUTTONS — keyed selectors. Streamlit ≥ 1.36 sets a
     `.st-key-<KEY>` class on the widget container. Our 5 buttons
     use keys `_edge_nav_dashboard`, `_edge_nav_saved_reports`,
     `_edge_nav_compare_swings`, `_edge_nav_development_tracker`,
     `_edge_nav_historical_charts`. We hit all 5 here.
     ============================================================ */
  .st-key-_edge_nav_dashboard,
  .st-key-_edge_nav_saved_reports,
  .st-key-_edge_nav_compare_swings,
  .st-key-_edge_nav_development_tracker,
  .st-key-_edge_nav_historical_charts {
    display: inline-block !important;
    margin: 0 !important;
  }
  .st-key-_edge_nav_dashboard button,
  .st-key-_edge_nav_saved_reports button,
  .st-key-_edge_nav_compare_swings button,
  .st-key-_edge_nav_development_tracker button,
  .st-key-_edge_nav_historical_charts button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: #8B8E94 !important;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    font-size: 11.5px !important;
    font-weight: 500 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 7px 18px !important;
    border-radius: 100px !important;
    width: auto !important;
    min-width: 0 !important;
    min-height: 0 !important;
    height: auto !important;
    white-space: nowrap !important;   /* NEVER wrap nav labels */
    box-shadow: none !important;
    transition: color 0.18s, background 0.18s, border-color 0.18s !important;
  }
  /* The button's inner <p> markdown wrapper sometimes wraps too —
     pin it nowrap and inline-block to prevent the line-break. */
  .st-key-_edge_nav_dashboard button p,
  .st-key-_edge_nav_saved_reports button p,
  .st-key-_edge_nav_compare_swings button p,
  .st-key-_edge_nav_development_tracker button p,
  .st-key-_edge_nav_historical_charts button p {
    white-space: nowrap !important;
    margin: 0 !important;
    overflow: visible !important;
    display: inline-block !important;
  }
  .st-key-_edge_nav_dashboard button:hover,
  .st-key-_edge_nav_saved_reports button:hover,
  .st-key-_edge_nav_compare_swings button:hover,
  .st-key-_edge_nav_development_tracker button:hover,
  .st-key-_edge_nav_historical_charts button:hover {
    color: #F4EFE6 !important;
    background: rgba(244,239,230,0.04) !important;
    border-color: transparent !important;
    transform: none !important;
  }
  /* Active (primary) pill — bone background, dark text */
  .st-key-_edge_nav_dashboard button[kind="primary"],
  .st-key-_edge_nav_saved_reports button[kind="primary"],
  .st-key-_edge_nav_compare_swings button[kind="primary"],
  .st-key-_edge_nav_development_tracker button[kind="primary"],
  .st-key-_edge_nav_historical_charts button[kind="primary"] {
    color: #0A0B0E !important;
    background: #F4EFE6 !important;
    border-color: #F4EFE6 !important;
  }
  .st-key-_edge_nav_dashboard button[kind="primary"]:hover,
  .st-key-_edge_nav_saved_reports button[kind="primary"]:hover,
  .st-key-_edge_nav_compare_swings button[kind="primary"]:hover,
  .st-key-_edge_nav_development_tracker button[kind="primary"]:hover,
  .st-key-_edge_nav_historical_charts button[kind="primary"]:hover {
    background: #FFFFFF !important;
    border-color: #FFFFFF !important;
  }

  /* Pill cluster container — wraps the 5 nav buttons. We can't put
     a real wrapping <div> around Streamlit-rendered buttons, so we
     paint the pill-cluster appearance on the stHorizontalBlock that
     groups the 5 columns inside the nav column. */
  .bl-edge-nav-row {
    display: flex; gap: 4px; padding: 4px;
    border: 1px solid rgba(244,239,230,0.08);
    border-radius: 100px;
    background: rgba(255,255,255,0.025);
    width: fit-content;
    margin: 0 auto;
  }
  .bl-edge-nav-row [data-testid="stHorizontalBlock"] { gap: 4px !important; }
  .bl-edge-nav-row [data-testid="column"] { width: auto !important; flex: 0 0 auto !important; }

  /* USER chip column */
  .bl-edge-user-chip {
    display: flex; align-items: center; gap: 12px;
    justify-content: flex-end;
  }
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
    width: 34px; height: 34px; border-radius: 50%;
    background: linear-gradient(135deg, #2A2D33, #11141A);
    border: 1px solid rgba(244,239,230,0.12);
    color: #F4EFE6; font-family: 'Geist Mono', monospace; font-size: 12px;
    font-weight: 600;
    display: inline-flex; align-items: center; justify-content: center;
    text-transform: uppercase;
  }

  /* Responsive */
  @media (max-width: 1100px) {
    div[data-bl-edge-masthead-row] { padding: 12px 24px 10px; }
    .st-key-_edge_nav_dashboard button,
    .st-key-_edge_nav_saved_reports button,
    .st-key-_edge_nav_compare_swings button,
    .st-key-_edge_nav_development_tracker button,
    .st-key-_edge_nav_historical_charts button {
      font-size: 10.5px !important;
      padding: 6px 11px !important;
      letter-spacing: 0.04em !important;
    }
  }
  @media (max-width: 760px) {
    .bl-edge-user-streak { display: none; }
    .bl-edge-wordmark { font-size: 11px; }
    .bl-edge-wordmark .product { font-size: 14px; }
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

    # Logo data URI (or fallback dot)
    logo_uri = _logo_data_uri()
    if logo_uri:
        brand_mark = f'<img class="bl-edge-brand-mark" src="{logo_uri}" alt="BarrelLabs">'
    else:
        brand_mark = '<span class="bl-edge-brand-mark is-fallback" aria-hidden="true"></span>'

    streak = streak_days if streak_days is not None else _streak_value(user)
    initials = _initials(user)

    # We can't wrap a Streamlit row in an HTML div the way we'd like,
    # so we paint the row's appearance via a sibling `<div ...>` that
    # we then position-style. The Streamlit-native row goes inside a
    # st.container() wrapper that we tag with a marker class via the
    # `_edge_masthead_marker` key — and we hit it from CSS via the
    # `.st-key-_edge_masthead_marker` class.
    with st.container(key="_edge_masthead_marker"):
        # Anchor the masthead-row CSS scope via a sibling marker div.
        # This div is empty; the styles in _EDGE_MASTHEAD_CSS target the
        # parent stHorizontalBlock through `[data-bl-edge-masthead-row]`.
        st.markdown(
            "<div data-bl-edge-masthead-row "
            "style='position:absolute;width:0;height:0;overflow:hidden;'></div>",
            unsafe_allow_html=True,
        )
        # Layout: [brand 3] [nav 6] [user chip 3]
        c_brand, c_nav, c_user = st.columns([3, 6, 3])

        with c_brand:
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

        with c_nav:
            # Visual pill-cluster wrapper. The 5 column buttons render
            # next to each other inside it; styles in
            # `_EDGE_MASTHEAD_CSS` collapse the column gaps.
            with st.container():
                st.markdown(
                    '<div class="bl-edge-nav-row-marker" '
                    'style="display:none"></div>',
                    unsafe_allow_html=True,
                )
                nav_cols = st.columns(len(_NAV_ENTRIES), gap="small")
                for i, (label, page_key, _alts) in enumerate(_NAV_ENTRIES):
                    with nav_cols[i]:
                        btn_type = "primary" if active == page_key else "secondary"
                        if st.button(
                            label,
                            key=f"_edge_nav_{page_key}",
                            type=btn_type,
                            use_container_width=True,
                        ):
                            # Navigate: set page, clear any sub-page record
                            # state so deep-linked records don't override.
                            st.session_state["page"] = page_key
                            st.session_state.pop("view_swing_record", None)
                            st.session_state.pop("view_swing_path", None)
                            st.session_state.pop("view_swing_report_id", None)
                            st.session_state.pop("preview_swing_record", None)
                            st.session_state.pop("preview_swing_record_id", None)
                            st.session_state.pop("view", None)
                            st.rerun()

        with c_user:
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

    # Inject one final piece of CSS that uses the container's
    # `.st-key-_edge_masthead_marker` to scope masthead-row styles.
    # This is the selector that ACTUALLY works to put the dark band
    # behind the row, because the marker class IS on a DOM ancestor of
    # the buttons.
    st.markdown(
        """
        <style>
          /* Re-target the masthead-row styles via the container's
             st-key class — the only DOM scope that survives Streamlit's
             rendering through both st.container and st.columns. */
          .st-key-_edge_masthead_marker {
            background: #0A0B0E;
            border-bottom: 1px solid rgba(244,239,230,0.08);
            padding: 14px 56px 12px !important;
            margin-bottom: 0 !important;
            position: relative;
          }
          .st-key-_edge_masthead_marker::after {
            content: ""; position: absolute; left: 0; right: 0; bottom: -1px;
            height: 1px; pointer-events: none;
            background: linear-gradient(90deg, transparent,
                        rgba(244,239,230,0.16) 20%,
                        rgba(244,239,230,0.16) 80%, transparent);
          }
          .st-key-_edge_masthead_marker [data-testid="stHorizontalBlock"] {
            max-width: 1560px;
            margin: 0 auto;
            align-items: center !important;
          }
          /* Collapse the gap inside the nav column's inner column row
             so the 5 buttons sit tight against each other inside the
             pill cluster. */
          .st-key-_edge_masthead_marker [data-testid="column"]:nth-child(2)
            [data-testid="stHorizontalBlock"] {
            gap: 0 !important;
            display: inline-flex !important;
            width: auto !important;
            margin: 0 auto !important;
            padding: 4px !important;
            border: 1px solid rgba(244,239,230,0.10);
            border-radius: 100px;
            background: rgba(255,255,255,0.025);
          }
          .st-key-_edge_masthead_marker [data-testid="column"]:nth-child(2)
            [data-testid="stHorizontalBlock"] [data-testid="column"] {
            flex: 0 0 auto !important;
            width: auto !important;
          }
          /* Nav column itself should center its inner pill cluster. */
          .st-key-_edge_masthead_marker [data-testid="stHorizontalBlock"]
            > [data-testid="column"]:nth-child(2) {
            display: flex; align-items: center; justify-content: center;
          }
        </style>
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
          .bl-edge-page {{
            max-width: {max_width}px;
            margin: 0 auto;
            padding: 22px 56px 80px;
            background: #0A0B0E;
            color: #F4EFE6;
            font-family: 'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
            box-sizing: border-box;
          }}
          /* CRITICAL: kill horizontal overflow at the root. Streamlit
             sometimes lets long content (mono labels, .stHorizontalBlocks)
             push the page wider than the viewport; explicitly clamp it. */
          html, body, [data-testid="stAppViewContainer"] {{
            max-width: 100vw;
            overflow-x: hidden !important;
          }}
          .bl-edge-page * {{
            max-width: 100%;
            min-width: 0;
          }}
          @media (max-width: 1100px) {{
            .bl-edge-page {{ padding: 18px 24px 60px; }}
          }}
          /* Kill Streamlit's default block padding that pushes content
             down when there's not much above. */
          [data-testid="stAppViewContainer"] > .main {{ padding: 0 !important; }}
          .block-container {{
            padding: 0 !important;
            max-width: 100% !important;
            padding-top: 0 !important;
          }}
          [data-testid="stAppViewContainer"] section.main > div.block-container {{
            padding-top: 0 !important;
          }}
          body, html, [data-testid="stAppViewContainer"] {{ background: #0A0B0E !important; }}
          header[data-testid="stHeader"], [data-testid="stSidebar"],
          [data-testid="stToolbar"], [data-testid="stDecoration"], footer {{
            display: none !important;
          }}
          /* Tighten vertical rhythm of all Streamlit elements when
             inside the Edge page. Stops the 3rem margin Streamlit
             applies between elements which adds up to hundreds of px. */
          .bl-edge-page > div, .bl-edge-page section,
          [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {{
            gap: 0 !important;
          }}
          /* Pull masthead's `.st-key-_edge_masthead_marker` flush to
             the top so the page hero starts immediately below. */
          .st-key-_edge_masthead_marker {{
            margin-top: -1rem !important;
          }}
        </style>
        <div class="bl-edge-page">
        """,
        unsafe_allow_html=True,
    )


def render_edge_page_wrapper_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
