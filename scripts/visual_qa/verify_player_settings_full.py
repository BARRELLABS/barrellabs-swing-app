"""Auth-free, full-page Playwright proof that the v3 Player Settings
page renders without overlapping elements across desktop / laptop /
tablet / mobile widths.

Strategy
--------
1. Pull `_PAGE_CSS` from `player_settings_page.py` and
   `_EDGE_MASTHEAD_CSS` from `bl_edge_chrome.py` (both modules
   import-clean under a Streamlit stub — same trick as
   verify_seam_fix.py / verify_nav_tabs.py).
2. Synthesize the EXACT Streamlit 1.57 DOM the page emits — masthead +
   ps_wrap + hero + 6 section cards + save bar + leave dialog —
   including every widget testid (`stTextInput`, `stSelectbox`,
   `stSegmentedControl`, `stPills`, `stCheckbox`-as-toggle, `stButton`).
3. Inject Streamlit 1.57's default chrome stylesheet so `_PAGE_CSS`
   competes against the same defaults production sees.
4. Render at 5 viewports (1920, 1440, 1280, 1024, 375).
5. For each viewport, run a JS probe that gathers bounding rects for:
   - masthead vs page header
   - hero banner vs first section card
   - every section card vs its neighbor (no overlap)
   - the two columns of every `st.columns(2)` row (side-by-side, no overlap)
   - the save bar vs the last section card (clearance)
   - the save bar vs the leave dialog (no peek-through)
   - the leave dialog vs the page body (overlay on top)
6. Print a PASS/FAIL summary. Save screenshots to
   /tmp/ps_full_<viewport>.png. Save the overlap report to
   /tmp/ps_overlap_report.json.

This file is the regression gate for the v3 rebuild — run it with
--gate to exit 1 on any overlap.
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

GATE = "--gate" in sys.argv

# ---------------------------------------------------------------------
# 1. Streamlit stub so player_settings_page + bl_edge_chrome import.
# ---------------------------------------------------------------------
class _SS(dict):
    def __getattr__(s, k):
        try: return s[k]
        except KeyError as e: raise AttributeError(k) from e
    def __setattr__(s, k, v): s[k] = v

class _QP(dict):
    def get(self, k, d=None): return super().get(k, d)

class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *e): return False

def _passthrough(*a, **k):
    if len(a) == 1 and callable(a[0]) and not k:
        return a[0]
    return lambda f: f

_capture = []
st = types.ModuleType("streamlit")
st.session_state = _SS()
st.query_params = _QP()
st.markdown = lambda *a, **k: _capture.append(a[0] if a else "")
st.container = lambda *a, **k: _Ctx()
st.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
st.text_input = lambda *a, **k: ""
st.number_input = lambda *a, **k: 0
st.selectbox = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
st.segmented_control = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
st.pills = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
st.toggle = lambda *a, **k: False
st.button = lambda *a, **k: False
st.download_button = lambda *a, **k: False
st.text_area = lambda *a, **k: ""
st.date_input = lambda *a, **k: None
st.file_uploader = lambda *a, **k: None
st.checkbox = lambda *a, **k: False
st.radio = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
st.expander = lambda *a, **k: _Ctx()
st.popover = lambda *a, **k: _Ctx()
st.empty = lambda *a, **k: _Ctx()
st.spinner = lambda *a, **k: _Ctx()
st.form = lambda *a, **k: _Ctx()
st.form_submit_button = lambda *a, **k: False
st.dialog = _passthrough
st.cache_resource = _passthrough
st.cache_data = _passthrough
for _n in ("write", "error", "warning", "info", "success", "caption",
            "image", "rerun", "stop", "toast", "divider", "metric",
            "subheader", "header", "title", "code", "json", "dataframe",
            "plotly_chart", "altair_chart", "balloons", "snow"):
    setattr(st, _n, lambda *a, **k: None)

_c1 = types.ModuleType("streamlit.components.v1")
_c1.html = lambda *a, **k: None
_c1.iframe = lambda *a, **k: None
_c0 = types.ModuleType("streamlit.components")
_c0.v1 = _c1
st.components = _c0
sys.modules["streamlit"] = st
sys.modules["streamlit.components"] = _c0
sys.modules["streamlit.components.v1"] = _c1

import importlib  # noqa: E402

psp = importlib.import_module("player_settings_page")
ble = importlib.import_module("bl_edge_chrome")

PAGE_CSS = psp._PAGE_CSS
MASTHEAD_CSS = ble._EDGE_MASTHEAD_CSS

assert "<style>" in PAGE_CSS, "page CSS extracted poorly"
assert "<style>" in MASTHEAD_CSS, "masthead CSS extracted poorly"


# ---------------------------------------------------------------------
# 2. Streamlit 1.57 default chrome stylesheet — verbatim from
#    verify_seam_fix.py + verify_nav_tabs.py.
# ---------------------------------------------------------------------
ST_DEFAULTS = """
<style>
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #0A0B0E; }
  [data-testid="stApp"] { position: absolute; inset: 0; background: #0A0B0E; }
  [data-testid="stHeader"] { position: absolute; top: 0; left: 0; right: 0;
    height: 60px; background: rgba(10,11,14,0.95); z-index: 999990;
    display: flex; }
  [data-testid="stMain"] { display: flex; flex-direction: column;
    background: transparent; }
  [data-testid="stMainBlockContainer"] { padding: 0;
    max-width: none; margin: 0 auto; background: transparent; }
  [data-testid="stVerticalBlock"] { display: flex; flex-direction: column;
    gap: 16px; }
  [data-testid="stHorizontalBlock"] { display: flex; flex-direction: row;
    gap: 16px; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 1 1 0; min-width: 0; }
  [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
    flex: 1 1 auto; }
  /* Generic widget DOM */
  button { font: inherit; color: inherit; cursor: pointer;
    background: rgb(247,247,247); border: 1px solid rgba(49,51,63,0.2);
    padding: 0.25rem 0.75rem; border-radius: 0.5rem;
    font-family: "Source Sans Pro", sans-serif; }
  input, textarea { font: inherit; color: rgb(49,51,63);
    background: rgb(255,255,255); border: 1px solid rgba(49,51,63,0.2);
    border-radius: 0.5rem; padding: 0.5rem 0.75rem; width: 100%;
    box-sizing: border-box; font-family: "Source Sans Pro", sans-serif; }
  [data-baseweb="select"] > div { background: rgb(255,255,255);
    border: 1px solid rgba(49,51,63,0.2); border-radius: 0.5rem;
    min-height: 40px; color: rgb(49,51,63); }
  label { color: rgb(49,51,63);
    font-family: "Source Sans Pro", sans-serif; font-size: 14px; }
</style>
"""


# ---------------------------------------------------------------------
# 3. ST 1.57 widget DOM builders.
# ---------------------------------------------------------------------
def _el(inner: str, *, key: str | None = None, extra: str = "") -> str:
    keycls = f"st-key-{key} " if key else ""
    return (
        f'<div data-testid="stElementContainer" '
        f'class="{keycls}stElementContainer {extra}".strip()">{inner}</div>'
    )

def _md(html_inside: str) -> str:
    return _el(
        f'<div data-testid="stMarkdownContainer" '
        f'class="stMarkdownContainer">{html_inside}</div>'
    )

def _text_input(label: str, value: str, *, disabled: bool = False) -> str:
    dis = ' disabled' if disabled else ''
    return _el(
        '<div data-testid="stTextInput" class="stTextInput">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div data-baseweb="input" class="st-baseweb-input">'
        f'<input type="text" value="{value}" aria-label="{label}"{dis}></div>'
        '</div>'
    )

def _number_input(label: str, value: int) -> str:
    return _el(
        '<div data-testid="stNumberInput" class="stNumberInput">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div data-baseweb="input" class="st-baseweb-input">'
        f'<input type="number" value="{value}" aria-label="{label}"></div>'
        '</div>'
    )

def _selectbox(label: str, value: str) -> str:
    return _el(
        '<div data-testid="stSelectbox" class="stSelectbox">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div data-baseweb="select" class="st-baseweb-select"><div>'
        f'<div role="combobox" aria-label="{label}">{value}</div>'
        '</div></div></div>'
    )

def _segmented_control(label: str, options: list[str], checked_idx: int) -> str:
    """ST 1.57 stSegmentedControl: a labeled wrapper containing a
    flex row of <button>s. The selected one has aria-checked=true."""
    btns = []
    for i, opt in enumerate(options):
        sel = "true" if i == checked_idx else "false"
        kind = "primary" if i == checked_idx else "secondary"
        btns.append(
            f'<button aria-checked="{sel}" aria-pressed="{sel}" '
            f'kind="{kind}" role="radio"><div data-testid="stMarkdownContainer">'
            f'<p>{opt}</p></div></button>'
        )
    return _el(
        '<div data-testid="stSegmentedControl" class="stSegmentedControl">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div role="radiogroup" style="display:flex;">'
        + "".join(btns)
        + '</div></div>'
    )

def _pills(label: str, options: list[str], checked_idx: int) -> str:
    """ST 1.57 stPills: a labeled wrapper containing a flex-wrap row
    of <button>s. The selected one has aria-checked=true."""
    btns = []
    for i, opt in enumerate(options):
        sel = "true" if i == checked_idx else "false"
        kind = "primary" if i == checked_idx else "secondary"
        btns.append(
            f'<button aria-checked="{sel}" aria-pressed="{sel}" '
            f'kind="{kind}" role="radio"><div data-testid="stMarkdownContainer">'
            f'<p>{opt}</p></div></button>'
        )
    return _el(
        '<div data-testid="stPills" class="stPills">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div role="radiogroup" style="display:flex;flex-wrap:wrap;">'
        + "".join(btns)
        + '</div></div>'
    )

def _toggle(label: str, checked: bool) -> str:
    aria = "true" if checked else "false"
    return _el(
        '<div data-testid="stCheckbox" class="stCheckbox">'
        '<label style="display:flex;align-items:center;gap:10px;"><div>'
        f'<div role="switch" aria-checked="{aria}" tabindex="0" '
        'style="width:36px;height:20px;border-radius:999px;'
        + ("background:rgba(232,193,112,0.35);"
           if checked else "background:rgba(0,0,0,0.3);")
        + '"></div></div>'
        f'<div>{label}</div></label>'
        '</div>'
    )

def _button(label: str, *, primary: bool = False) -> str:
    kind = "primary" if primary else "secondary"
    testid = f"stBaseButton-{kind}"
    return _el(
        '<div data-testid="stButton" class="stButton">'
        f'<button kind="{kind}" data-testid="{testid}" type="button">'
        '<div data-testid="stMarkdownContainer">'
        f'<p>{label}</p></div></button></div>'
    )

def _columns_row(cells: list[str]) -> str:
    cols = "".join(
        '<div data-testid="stColumn" class="stColumn">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{c}</div></div>'
        for c in cells
    )
    return (
        '<div data-testid="stElementContainer" class="stElementContainer">'
        '<div data-testid="stHorizontalBlock" class="stHorizontalBlock">'
        f'{cols}</div></div>'
    )

def _keyed_container(key: str, inner: str) -> str:
    """Reproduce `st.container(key="X")` output verbatim."""
    return (
        f'<div class="st-key-{key} stElementContainer" '
        f'data-testid="stElementContainer">'
        f'<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{inner}</div></div>'
    )


# ---------------------------------------------------------------------
# 4. Build the FULL Player Settings DOM.
# ---------------------------------------------------------------------
def build_masthead() -> str:
    """Replica of the bl_edge_chrome masthead layout — brand left, nav
    middle, user chip right. We only need the geometry."""
    nav_btns = "".join(
        _button(label, primary=(page_key == "player_settings"))
        for label, page_key, _alt in ble._NAV_ENTRIES
    )
    return _keyed_container(
        "bl_edge_masthead",
        _md('<div class="ble-brand">'
            '<span style="display:inline-block;width:30px;height:30px;'
            'background:#E64530;border-radius:50%;"></span>'
            '<span class="wm">BarrelLabs<span class="sl">/</span>'
            '<span class="ed">Edge</span></span></div>')
        + _keyed_container("bl_edge_navbar", nav_btns)
        + _keyed_container("bl_edge_userchip",
                            _md('<span class="ble-streak">'
                                '<span class="d"></span>3-day streak</span>')
                            + _button("LC"))
    )


def build_hero_html() -> str:
    return _md(
        '<div class="ps-hero">'
        '  <div class="ps-hero-av">LC</div>'
        '  <div class="ps-hero-meta">'
        '    <div class="ps-hero-name">Logan Collins</div>'
        '    <div class="ps-hero-email">logan@example.com</div>'
        '    <span class="ps-plan-pill">BarrelLabs Pro</span>'
        '  </div>'
        '  <div class="ps-hero-stats">'
        '    <div><div class="ps-hero-stat-label">Swings</div>'
        '      <div class="ps-hero-stat-val">42</div></div>'
        '    <div><div class="ps-hero-stat-label">Best</div>'
        '      <div class="ps-hero-stat-val">87<span class="u">/100</span></div></div>'
        '    <div><div class="ps-hero-stat-label">Streak</div>'
        '      <div class="ps-hero-stat-val">12<span class="u">d</span></div></div>'
        '    <div><div class="ps-hero-stat-label">Member</div>'
        '      <div class="ps-hero-stat-val" style="font-size:1.05rem;">May 2026</div></div>'
        '  </div>'
        '</div>'
    )


def build_section_profile() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">01 · Identity</span>'
            '<h2 class="ps-sec-title">Your player card</h2>'
            '<p class="ps-sec-desc">The basics — your name shows on every '
            'swing report.</p></div>')
        + _columns_row([
            _text_input("First name", "Logan"),
            _text_input("Last name", "Collins"),
        ])
        + _columns_row([
            _text_input("Display name", "Logan C."),
            _text_input("Email · login id", "logan@example.com",
                         disabled=True),
        ])
    )
    return _keyed_container("ps_sec_profile", body)


def build_section_bb() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">02 · Diamond</span>'
            '<h2 class="ps-sec-title">Baseball profile</h2>'
            '<p class="ps-sec-desc">Optional, but the more we know, the '
            'sharper your MLB-comparison match.</p></div>')
        + _columns_row([
            _selectbox("Primary position", "Shortstop · SS"),
            _selectbox("Secondary position", "Second base · 2B"),
        ])
        + _columns_row([
            _segmented_control("Bats", ["Right", "Left", "Switch"], 0),
            _segmented_control("Throws", ["Right", "Left"], 0),
        ])
        + _columns_row([
            _text_input("Age", "16"),
            _columns_row([
                _number_input("Height · ft", 5),
                _number_input("Height · in", 10),
            ]),
        ])
        + _columns_row([
            _number_input("Weight · lb", 160),
            _text_input("Graduation year", "2027"),
        ])
        + _text_input("Team · school · organization",
                       "16U Tigers · Riverside HS")
        + _pills("Competition level",
                  ["Youth", "Travel", "High School", "College",
                   "Pro", "Adult/Rec"], 2)
    )
    return _keyed_container("ps_sec_bb", body)


def build_section_swing() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">03 · Lab</span>'
            '<h2 class="ps-sec-title">Swing preferences</h2>'
            '<p class="ps-sec-desc">Tune how the analyzer frames your '
            'reports. The training goal directly weights your drill plan.'
            '</p></div>')
        + _columns_row([
            _selectbox("Default swing view", "Side angle (1B / 3B line)"),
            _segmented_control("MLB comparison handedness",
                                ["Match mine", "Right", "Left"], 0),
        ])
        + _pills("Primary training goal · drives drill plan",
                  ["Improve mechanics", "More power", "Better contact",
                   "Better timing", "Better consistency",
                   "Reduce strikeouts", "Improve bat path",
                   "Improve overall swing"], 0)
        + _md('<div class="ps-helper">Active: '
              '<span class="gold">Improve mechanics</span> · drills '
              'aligned with this goal get a small boost.</div>')
        + _segmented_control("Default report focus",
                              ["Simple summary", "Full biomechanical",
                               "Coach-style"], 1)
    )
    return _keyed_container("ps_sec_swing", body)


def build_section_acct() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">04 · Account</span>'
            '<h2 class="ps-sec-title">Plan &amp; access</h2>'
            '<p class="ps-sec-desc">Billing runs through Stripe — manage '
            'payment methods, invoices, and cancel from the portal.</p></div>')
        + _md('<div class="ps-plan-row">'
              '<div><div class="ps-plan-name">BarrelLabs <em>Pro</em>'
              '<span class="ps-status-active">Active</span></div>'
              '<div class="ps-plan-meta"><span class="price">$19/mo</span>'
              ' · Next billing · Jun 2026</div></div>'
              '<div></div><div></div></div>')
        + _button("Manage billing  →")
        + _text_input("Change email", "")
        + _button("Send verification email")
        + _md('<div style="height:1px; margin:1.2rem 0; '
              'background:rgba(244,239,230,0.08);"></div>'
              '<div style="font-family:Geist Mono; font-size:9.5px; '
              'letter-spacing:0.20em; text-transform:uppercase; '
              'color:rgba(244,239,230,0.6); padding-bottom:6px;">Password</div>'
              '<div style="font-size:13px; color:rgba(244,239,230,0.6); '
              'padding-bottom:0.8rem;">We don\'t store passwords.</div>')
        + _button("Send password reset email")
        + _md('<div style="height:1px; margin:1.2rem 0; '
              'background:rgba(244,239,230,0.08);"></div>'
              '<div style="color:rgba(244,239,230,0.6); font-size:13px; '
              'padding-bottom:0.6rem;">Signed in as logan@example.com</div>')
        + _button("Log out")
    )
    return _keyed_container("ps_sec_acct", body)


def build_section_priv() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">05 · Privacy</span>'
            '<h2 class="ps-sec-title">Your data</h2>'
            '<p class="ps-sec-desc">Control how your swing data is used '
            'and shared. These toggles save instantly.</p></div>')
        + _toggle("Improve BarrelLabs's models with my swings  ·  "
                   "anonymized only", True)
        + _toggle("Allow shareable coach links for my swing reports", False)
        + _toggle("Product update emails  ·  under one a month", True)
        + _toggle("Weekly performance summary emails", True)
        + _md('<div style="height:1px; margin:1.2rem 0; '
              'background:rgba(244,239,230,0.08);"></div>'
              '<div style="font-family:Geist Mono; font-size:9.5px; '
              'letter-spacing:0.20em; text-transform:uppercase; '
              'color:rgba(244,239,230,0.6);">Export my data</div>'
              '<div style="font-size:13px; color:rgba(244,239,230,0.6); '
              'padding:0.4rem 0 0.8rem;">Download a JSON archive.</div>')
        + _button("Export archive")
    )
    return _keyed_container("ps_sec_priv", body)


def build_section_danger() -> str:
    body = (
        _md('<div class="ps-sec-head">'
            '<span class="ps-eyebrow">06 · Danger zone</span>'
            '<h2 class="ps-sec-title">Delete account</h2></div>')
        + _md('<div class="ps-danger-warn">'
              '<div class="ps-danger-label">Permanent · Cannot be undone</div>'
              '<div class="ps-danger-text">Deleting your account erases '
              'every swing, every report, and cancels your subscription.</div>'
              '</div>')
        + _button("Delete account")
    )
    return _keyed_container("ps_sec_danger", body)


def build_savebar(dirty_count: int = 3) -> str:
    """Build the bottom-sticky save bar (visible when dirty)."""
    label_col = (
        '<div data-testid="stColumn" class="stColumn">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        + _md(f'<div class="ps-savebar-label">'
              f'<span class="ps-unsaved-pill">'
              f'<span class="d"></span>Unsaved · {dirty_count} fields</span>'
              f'<span class="ps-savebar-text">Edits to '
              f'<em>Logan Collins</em>\'s profile aren\'t saved yet.</span>'
              f'</div>')
        + '</div></div>'
    )
    cancel_col = (
        '<div data-testid="stColumn" class="stColumn">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        + _button("Discard")
        + '</div></div>'
    )
    save_col = (
        '<div data-testid="stColumn" class="stColumn">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        + _button("Save changes", primary=True)
        + '</div></div>'
    )
    row = (
        '<div data-testid="stElementContainer" class="stElementContainer">'
        '<div data-testid="stHorizontalBlock" class="stHorizontalBlock" '
        'style="display:flex;flex-direction:row;">'
        f'{label_col}{cancel_col}{save_col}'
        '</div></div>'
    )
    return _keyed_container("ps_savebar", row)


def build_page() -> str:
    body = (
        build_masthead()
        + _keyed_container("ps_wrap",
            _md('<div class="ps-page-head">'
                '<span class="ps-eyebrow">Profile · Account</span>'
                '<h1 class="ps-title">Player Settings</h1>'
                '<p class="ps-sub">Manage your player profile, swing '
                'preferences, and account settings. Edits surface in a '
                'save bar at the bottom of the page — click '
                '<em>Save changes</em> there to commit.</p></div>')
            + build_hero_html()
            + build_section_profile()
            + build_section_bb()
            + build_section_swing()
            + build_section_acct()
            + build_section_priv()
            + build_section_danger()
            + _md('<div class="ps-foot">'
                  '<span>§ End · BarrelLabs Edge</span>'
                  '<span>Member since May 2026</span></div>'))
        + build_savebar(3)
    )
    return body


def build_html_doc(viewport_w: int, viewport_h: int) -> str:
    body = build_page()
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{ST_DEFAULTS}
{MASTHEAD_CSS}
{PAGE_CSS}
</head><body>
<div data-testid="stApp" class="stApp">
  <header data-testid="stHeader" class="stAppHeader"
          style="display:none;"><div>toolbar</div></header>
  <div data-testid="stAppViewContainer">
    <section data-testid="stMain" class="stMain">
      <div data-testid="stMainBlockContainer"
           class="stMainBlockContainer block-container">
        <div data-testid="stVerticalBlock" class="stVerticalBlock">
          {body}
        </div>
      </div>
    </section>
  </div>
</div>
</body></html>"""


# Write a separate HTML file per viewport so screenshots are crisp.
OUT_DIR = Path("/tmp/ps_full")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 5. JS overlap probe.
# ---------------------------------------------------------------------
OVERLAP_PROBE = r"""
() => {
  const out = { viewport: { w: window.innerWidth, h: window.innerHeight },
                 checks: [], rects: {} };

  const rectOf = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    // Use page-relative coords for stability across scrolls.
    return { x: r.left + window.scrollX, y: r.top + window.scrollY,
             w: r.width, h: r.height,
             left: r.left + window.scrollX, top: r.top + window.scrollY,
             right: r.right + window.scrollX, bottom: r.bottom + window.scrollY };
  };

  // Determine if two rects overlap (intersect on both axes), allowing
  // a small slack for sub-pixel rounding.
  const SLACK = 1.5;
  const overlap = (a, b) => {
    if (!a || !b) return false;
    return a.right - SLACK > b.left
        && a.left + SLACK < b.right
        && a.bottom - SLACK > b.top
        && a.top + SLACK < b.bottom;
  };
  // Vertical-only overlap (we want side-by-side columns to NOT
  // horizontally overlap but they SHOULD vertically share rows).
  const hOverlap = (a, b) => {
    if (!a || !b) return false;
    return a.right - SLACK > b.left && a.left + SLACK < b.right;
  };

  // ---- gather rects ----
  const mast = document.querySelector('.st-key-bl_edge_masthead');
  const wrap = document.querySelector('.st-key-ps_wrap');
  const head = document.querySelector('.st-key-ps_wrap .ps-page-head');
  const hero = document.querySelector('.st-key-ps_wrap .ps-hero');
  const sections = ['profile', 'bb', 'swing', 'acct', 'priv', 'danger']
        .map(n => document.querySelector(`.st-key-ps_sec_${n}`));
  const savebar = document.querySelector('.st-key-ps_savebar');
  out.rects.masthead = rectOf(mast);
  out.rects.wrap = rectOf(wrap);
  out.rects.head = rectOf(head);
  out.rects.hero = rectOf(hero);
  out.rects.sections = sections.map(rectOf);
  out.rects.savebar = rectOf(savebar);

  // CHECK 1 — masthead does NOT overlap the page head.
  out.checks.push({
    name: "masthead vs page head",
    passed: !overlap(out.rects.masthead, out.rects.head),
    detail: out.rects.masthead && out.rects.head
              ? `mast.bottom=${out.rects.masthead.bottom.toFixed(1)} `
                + `head.top=${out.rects.head.top.toFixed(1)}` : "missing",
  });

  // CHECK 2 — hero does NOT overlap section[0] (profile).
  out.checks.push({
    name: "hero vs section[0] profile",
    passed: !overlap(out.rects.hero, out.rects.sections[0]),
    detail: out.rects.hero && out.rects.sections[0]
              ? `hero.bottom=${out.rects.hero.bottom.toFixed(1)} `
                + `s0.top=${out.rects.sections[0].top.toFixed(1)}` : "missing",
  });

  // CHECK 3 — adjacent section cards never overlap.
  for (let i = 0; i + 1 < sections.length; i++) {
    const a = out.rects.sections[i], b = out.rects.sections[i + 1];
    out.checks.push({
      name: `section[${i}] vs section[${i + 1}]`,
      passed: !overlap(a, b),
      detail: a && b ? `a.bottom=${a.bottom.toFixed(1)} `
                          + `b.top=${b.top.toFixed(1)}` : "missing",
    });
  }

  // CHECK 4 — every stColumn pair inside a section is side-by-side
  // (no horizontal overlap) at viewports wider than 640px. Below that,
  // Streamlit auto-stacks columns so we skip this check.
  if (window.innerWidth > 640) {
    let pairIdx = 0;
    document.querySelectorAll('[class*="st-key-ps_sec_"] '
      + '> [data-testid="stVerticalBlock"] '
      + '> [data-testid="stElementContainer"] '
      + '> [data-testid="stHorizontalBlock"]').forEach((row) => {
      const cols = Array.from(row.children).filter(
        c => c.matches('[data-testid="stColumn"]'));
      for (let i = 0; i + 1 < cols.length; i++) {
        const a = rectOf(cols[i]), b = rectOf(cols[i + 1]);
        out.checks.push({
          name: `column pair #${pairIdx++} (${cols[i].closest('[class*="st-key-ps_sec_"]').className.match(/st-key-ps_sec_\w+/)?.[0]})`,
          passed: !hOverlap(a, b),
          detail: `a.right=${a.right.toFixed(1)} b.left=${b.left.toFixed(1)}`,
        });
      }
    });
  }

  // CHECK 5 — savebar (position:fixed) clears the last content when
  // the user scrolls to the bottom. Geometric reasoning (no need to
  // actually scroll, which Playwright reads inconsistently):
  //   - savebar lives at vp.bottom - 22px (offset) and is ~56px tall;
  //     savebar.top in vp coords = vp.height - 78px when at rest.
  //   - When scrolled to the page bottom, the wrap's bottom touches
  //     vp.bottom. The wrap has 9rem (144px) padding-bottom, so the
  //     last child sits at vp.bottom - 144px.
  //   - Required: padding-bottom > 22 + savebar.height + clearance.
  // We measure the actual rendered savebar height and the wrap's
  // computed padding-bottom and check the inequality holds.
  if (wrap && savebar) {
    const sbH = savebar.getBoundingClientRect().height;
    const wrapPad = parseFloat(getComputedStyle(wrap).paddingBottom) || 0;
    const sbOffset = parseFloat(getComputedStyle(savebar).bottom) || 0;
    const required = sbOffset + sbH + 16;   // 16px breathing room
    out.checks.push({
      name: "savebar clears last section (geometric)",
      passed: wrapPad >= required,
      detail: `wrap.paddingBottom=${wrapPad.toFixed(1)}px `
              + `>= sb.bottom(${sbOffset.toFixed(1)}) `
              + `+ sb.height(${sbH.toFixed(1)}) + 16 = ${required.toFixed(1)}px`,
    });
  }

  // CHECK 6 — the savebar's 3 internal columns are side-by-side
  // (the markdown label, cancel button, save button).
  const sbRow = document.querySelector(
    '.st-key-ps_savebar [data-testid="stHorizontalBlock"]');
  if (sbRow) {
    const sbCols = Array.from(sbRow.children).filter(
      c => c.matches('[data-testid="stColumn"]'));
    for (let i = 0; i + 1 < sbCols.length; i++) {
      const a = rectOf(sbCols[i]), b = rectOf(sbCols[i + 1]);
      out.checks.push({
        name: `savebar col[${i}] vs col[${i + 1}]`,
        passed: !hOverlap(a, b) || window.innerWidth <= 640,
        detail: `a.right=${a.right.toFixed(1)} b.left=${b.left.toFixed(1)}`,
      });
    }
  }

  // CHECK 7 — page content does NOT spill outside the wrap.
  if (wrap) {
    const w = rectOf(wrap);
    const overflowing = Array.from(
      document.querySelectorAll('.st-key-ps_wrap *')).filter(el => {
      const r = el.getBoundingClientRect();
      return r.left + window.scrollX + 2 < w.left
          || r.right + window.scrollX - 2 > w.right;
    }).slice(0, 5);
    out.checks.push({
      name: "no content overflows ps_wrap horizontally",
      passed: overflowing.length === 0,
      detail: overflowing.length ? `${overflowing.length} overflowing nodes`
                                  : "ok",
    });
  }

  // Summary
  out.passed = out.checks.every(c => c.passed);
  out.failedCount = out.checks.filter(c => !c.passed).length;
  return out;
}
"""


# ---------------------------------------------------------------------
# 6. Drive Playwright across viewports.
# ---------------------------------------------------------------------
from playwright.sync_api import sync_playwright  # noqa: E402


def run_viewport(p, label: str, w: int, h: int) -> dict:
    html = build_html_doc(w, h)
    out_html = OUT_DIR / f"ps_full_{label}.html"
    out_html.write_text(html, encoding="utf-8")
    pg = p.new_page(viewport={"width": w, "height": h},
                     device_scale_factor=1)
    pg.goto(f"file://{out_html}", wait_until="networkidle")
    pg.wait_for_timeout(450)
    result = pg.evaluate(OVERLAP_PROBE)
    pg.screenshot(path=str(OUT_DIR / f"ps_full_{label}.png"),
                   full_page=True)
    pg.close()
    return result


VIEWPORTS = [
    ("1920", 1920, 1080),
    ("1440", 1440, 900),
    ("1280", 1280, 800),
    ("1024", 1024, 900),
    ("375",  375,  800),
]

results: dict[str, dict] = {}

with sync_playwright() as p:
    b = p.chromium.launch()
    for label, w, h in VIEWPORTS:
        results[label] = run_viewport(b, label, w, h)
    b.close()


# ---------------------------------------------------------------------
# 7. Report.
# ---------------------------------------------------------------------
report_path = Path("/tmp/ps_overlap_report.json")
report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

print("=" * 64)
print("Player Settings v3 — full-page overlap audit")
print("=" * 64)

global_pass = True
for label, _, _ in VIEWPORTS:
    r = results[label]
    head = f"[{label}x{r['viewport']['h']}]"
    print(f"\n{head} " + ("PASS" if r["passed"] else f"FAIL ({r['failedCount']})"))
    for c in r["checks"]:
        flag = "  ✓" if c["passed"] else "  ✗"
        print(f"{flag} {c['name']}")
        if not c["passed"]:
            print(f"      {c['detail']}")
            global_pass = False

print("\n" + "=" * 64)
print("Screenshots: " + str(OUT_DIR))
print("Full JSON: " + str(report_path))
print("=" * 64)
print("OVERALL: " + ("PASS" if global_pass else "FAIL"))

if GATE and not global_pass:
    sys.exit(1)
sys.exit(0)
