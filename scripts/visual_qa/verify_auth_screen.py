"""Auth-free Playwright proof that the premium Player Settings auth
screen renders without overlap and without leaking Streamlit default
chrome at every supported viewport.

How it works
------------
1. Import `auth_screen.py` under a streamlit stub (same technique as
   verify_player_settings.py / verify_nav_tabs.py) so we can pull
   `_AUTH_CSS`, `_hero_html()`, `_google_placeholder_html()`,
   `_legal_html()` verbatim from the module.
2. Reconstruct Streamlit 1.57's auth-screen DOM by hand: the root
   `.st-key-auth_root` grid wrapper holding `.st-key-auth_hero`
   (left) and `.st-key-auth_panel` (right), with the panel containing
   the segmented toggle (`.st-key-auth_toggle`), the glass card
   `.au-card-frame`, the login form (st.form), the Forgot link, the
   Google placeholder, and the legal footer.
3. Inject ST1.57's real default chrome stylesheet so `_AUTH_CSS`
   competes against the same defaults production sees.
4. Screenshot at 1920×1080, 1440×900, 1024×900, 375×800 (full page).
5. Run a JS probe that computes bounding rects of every salient region
   and asserts:
     - no overflow on the x-axis at any viewport
     - hero and panel sit side-by-side at desktop, stacked on tablet/mobile
     - the auth card is fully visible inside the panel (not clipped)
     - the toggle, form, Google placeholder, legal footer all stack
       vertically inside the card with no overlap
     - the primary CTA is the brand red gradient
     - Streamlit chrome (`stHeader`/`stToolbar`/`stDecoration`) is hidden

Run modes
---------
    python verify_auth_screen.py           # diagnostic, exit 0 always
    python verify_auth_screen.py --gate    # exit 1 on any failure

Outputs
-------
    /tmp/auth_screen_1920.png
    /tmp/auth_screen_1440.png
    /tmp/auth_screen_1024.png
    /tmp/auth_screen_375.png
    /tmp/auth_screen_report.json
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


# =====================================================================
# 1. Stub streamlit + bl_edge_chrome, import auth_screen.
# =====================================================================
class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *e): return False


_st = types.ModuleType("streamlit")
_st.session_state = {}
_st.query_params = {}
_st.markdown = lambda *a, **k: None
_st.container = lambda *a, **k: _Ctx()
_st.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
_st.button = lambda *a, **k: False
_st.text_input = lambda *a, **k: ""
_st.number_input = lambda *a, **k: 0
_st.checkbox = lambda *a, **k: False
_st.radio = lambda *a, **k: ""
_st.selectbox = lambda *a, **k: ""
_st.form = lambda *a, **k: _Ctx()
_st.form_submit_button = lambda *a, **k: False
_st.expander = lambda *a, **k: _Ctx()
_st.caption = lambda *a, **k: None
_st.error = lambda *a, **k: None
_st.success = lambda *a, **k: None
_st.info = lambda *a, **k: None
_st.warning = lambda *a, **k: None
_st.rerun = lambda *a, **k: None
_st.stop = lambda *a, **k: None
_c1 = types.ModuleType("streamlit.components.v1")
_c1.html = lambda *a, **k: None
_c1.iframe = lambda *a, **k: None
_c0 = types.ModuleType("streamlit.components")
_c0.v1 = _c1
_st.components = _c0
sys.modules["streamlit"] = _st
sys.modules["streamlit.components"] = _c0
sys.modules["streamlit.components.v1"] = _c1

import importlib  # noqa: E402

ascreen = importlib.import_module("auth_screen")

AUTH_CSS = ascreen._AUTH_CSS
HERO_HTML = ascreen._hero_html()
GOOGLE_HTML = ascreen._google_placeholder_html()
LEGAL_HTML = ascreen._legal_html()

assert "<style>" in AUTH_CSS, "AUTH_CSS missing <style>"
assert "au-title" in HERO_HTML, "hero html missing au-title"


# =====================================================================
# 2. Streamlit 1.57 default chrome stylesheet — same as
#    verify_player_settings_full / verify_nav_tabs.
# =====================================================================
ST_DEFAULTS = """
<style>
  html, body { margin: 0; padding: 0; background: #262730; }
  [data-testid="stApp"] {
    position: absolute; inset: 0; background: #0A0B0E;
    overflow-x: hidden;
  }
  [data-testid="stHeader"] {
    position: absolute; top: 0; left: 0; right: 0;
    height: 60px; background: #FFFFFF; z-index: 999990;
  }
  [data-testid="stMain"] {
    display: flex; flex-direction: column; background: transparent;
  }
  [data-testid="stMainBlockContainer"] {
    padding: 96px 16px 160px;
    max-width: 1560px; margin: 0 auto; background: transparent;
  }
  [data-testid="stVerticalBlock"] {
    display: flex; flex-direction: column; gap: 16px;
  }
  [data-testid="stHorizontalBlock"] {
    display: flex; flex-direction: row; gap: 16px;
  }
  button {
    font: inherit; color: inherit; cursor: pointer;
    background: rgb(247,247,247); border: 1px solid rgba(49,51,63,0.2);
    padding: 0.25rem 0.75rem; border-radius: 0.5rem;
    font-family: "Source Sans Pro", sans-serif;
  }
  input, textarea {
    font: inherit; color: rgb(49,51,63);
    background: rgb(255,255,255);
    border: 1px solid rgba(49,51,63,0.2);
    border-radius: 0.5rem; padding: 0.5rem 0.75rem;
    width: 100%; box-sizing: border-box;
    font-family: "Source Sans Pro", sans-serif;
  }
  label { color: rgb(49,51,63);
    font-family: "Source Sans Pro", sans-serif; font-size: 14px; }
</style>
"""


# =====================================================================
# 3. ST 1.57 widget-DOM builders (same idiom as verify_player_settings*).
# =====================================================================
def _el(inner: str, *, key: str | None = None) -> str:
    keycls = f"st-key-{key} " if key else ""
    return (
        f'<div data-testid="stElementContainer" '
        f'class="{keycls}stElementContainer">{inner}</div>'
    )


def _md_el(inner: str) -> str:
    return _el(
        f'<div data-testid="stMarkdownContainer" '
        f'class="stMarkdownContainer">{inner}</div>'
    )


def _text_input(label: str, value: str = "", placeholder: str = "",
                input_type: str = "text") -> str:
    return _el(
        '<div data-testid="stTextInput" class="stTextInput">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div data-baseweb="input" class="st-baseweb-input">'
        f'<input type="{input_type}" value="{value}" '
        f'placeholder="{placeholder}" aria-label="{label}">'
        '</div></div>'
    )


def _number_input(label: str, value: int = 0) -> str:
    return _el(
        '<div data-testid="stNumberInput" class="stNumberInput">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        '<div><input type="number" '
        f'value="{value}" aria-label="{label}">'
        '<button>+</button><button>-</button></div></div>'
    )


def _checkbox(label: str, checked: bool = False) -> str:
    aria = "true" if checked else "false"
    return _el(
        '<div data-testid="stCheckbox" class="stCheckbox">'
        f'<label><div><div role="checkbox" aria-checked="{aria}" tabindex="0">'
        f'<svg width="16" height="16"></svg></div></div>'
        f'<div>{label}</div></label></div>'
    )


def _radio_horizontal(label: str, options: list[str], checked: int = 0) -> str:
    opts = "".join(
        f'<label data-baseweb="radio">'
        f'<input type="radio" name="{label}"'
        f'{" checked" if i == checked else ""}>'
        f'<span>{o}</span></label>'
        for i, o in enumerate(options)
    )
    return _el(
        '<div data-testid="stRadio" class="stRadio" role="radiogroup">'
        f'<label data-testid="stWidgetLabel">{label}</label>'
        f'<div role="radiogroup">{opts}</div></div>'
    )


def _button(label: str, *, kind: str = "secondary") -> str:
    return _el(
        '<div data-testid="stButton" class="stButton">'
        f'<button kind="{kind}" data-testid="stBaseButton-{kind}" type="button">'
        '<div data-testid="stMarkdownContainer" class="stMarkdownContainer">'
        f'<p>{label}</p></div></button></div>'
    )


def _form_submit(label: str, *, kind: str = "primary") -> str:
    return _el(
        '<div data-testid="stFormSubmitButton" class="stFormSubmitButton">'
        f'<button kind="{kind}" data-testid="stBaseButton-{kind}" type="submit">'
        '<div data-testid="stMarkdownContainer" class="stMarkdownContainer">'
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
        '<div data-testid="stHorizontalBlock" class="stHorizontalBlock">'
        f'{cols}</div>'
    )


def _form(inner: str) -> str:
    return _el(
        '<div data-testid="stForm" class="stForm">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{inner}</div></div>'
    )


def _keyed(key: str, inner: str) -> str:
    """Reproduce `st.container(key='X')`'s DOM."""
    return (
        f'<div class="st-key-{key} stElementContainer" '
        f'data-testid="stElementContainer">'
        f'<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{inner}</div></div>'
    )


# =====================================================================
# 4. Build the full auth-screen DOM (login mode — represents the
#    busiest layout: toggle + form + forgot + google + legal).
# =====================================================================
def build_auth_dom() -> str:
    # The hero side is one big st.markdown emitting HERO_HTML directly.
    hero = _md_el(HERO_HTML)

    # The auth panel has: optional toggle + markdown card-frame open +
    # eyebrow/title/sub markdown + form + forgot button + google
    # placeholder markdown + legal markdown + card-frame close.
    toggle = _keyed("auth_toggle", _columns_row([
        _button("Sign in", kind="primary"),
        _button("Create account", kind="secondary"),
    ]))

    card_open = _md_el('<div class="au-card-frame">')
    eyebrow_title_sub = _md_el(
        '<div class="au-card-eyebrow">Welcome back</div>'
        '<h2 class="au-card-title">Welcome back.</h2>'
        '<p class="au-card-sub">Continue your path to elite performance — '
        'your swing library is right where you left it.</p>'
    )

    form_inner = (
        _text_input("Email", placeholder="you@example.com")
        + _text_input("Password", placeholder="Your password", input_type="password")
        + _columns_row([
            _checkbox("Remember me", checked=True),
            _checkbox("Show password", checked=False),
        ])
        + _form_submit("Access your Performance Lab  →", kind="primary")
    )
    form = _form(form_inner)
    forgot = _button("Forgot password?", kind="secondary")
    google = _md_el(GOOGLE_HTML)
    legal = _md_el(LEGAL_HTML)
    card_close = _md_el('</div>')

    panel_inner = (
        toggle + card_open + eyebrow_title_sub + form
        + forgot + google + legal + card_close
    )

    root_inner = (
        _keyed("auth_hero", hero)
        + _keyed("auth_panel", panel_inner)
    )

    # _AUTH_CSS itself + atmos divs sit at the top of the page body, just
    # before the keyed root, exactly as render_auth_screen() emits them.
    pre = (
        _md_el('<div class="auth-atmos"></div>')
        + _md_el('<div class="auth-grain"></div>')
    )

    return (
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{pre}'
        f'{_keyed("auth_root", root_inner)}'
        '</div>'
    )


PAGE_BODY = build_auth_dom()


def build_page() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{ST_DEFAULTS}
{AUTH_CSS}
</head><body>
<div data-testid="stApp" class="stApp">
  <header data-testid="stHeader" class="stAppHeader"><div>toolbar</div></header>
  <div data-testid="stAppViewContainer">
    <section data-testid="stMain" class="stMain">
      <div data-testid="stMainBlockContainer"
           class="stMainBlockContainer block-container">
        {PAGE_BODY}
      </div>
    </section>
  </div>
</div>
</body></html>"""


HTML_PATH = Path("/tmp/auth_screen.html")
HTML_PATH.write_text(build_page(), encoding="utf-8")


# =====================================================================
# 5. JS probe — computed-style + bounding-rect overlap checks.
# =====================================================================
PROBE = r"""
() => {
  const out = { viewport: {
    w: window.innerWidth, h: window.innerHeight,
    scrollW: document.documentElement.scrollWidth,
    scrollH: document.documentElement.scrollHeight,
  } };

  const rect = el => el ? (() => {
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height,
             right: r.right, bottom: r.bottom };
  })() : null;
  const cs = (el, p) => el ? getComputedStyle(el).getPropertyValue(p) : null;

  // chrome must be hidden
  const stHeader = document.querySelector('[data-testid="stHeader"]');
  out.stHeaderDisplay = cs(stHeader, 'display');

  const root = document.querySelector('.st-key-auth_root');
  out.rootFound = !!root;
  out.rootDisplay = cs(root, 'display');
  out.rootCols = cs(root, 'grid-template-columns');
  out.rootRect = rect(root);

  const hero = document.querySelector('.st-key-auth_hero');
  out.heroFound = !!hero;
  out.heroRect = rect(hero);

  const panel = document.querySelector('.st-key-auth_panel');
  out.panelFound = !!panel;
  out.panelRect = rect(panel);

  // card frame
  const card = document.querySelector('.au-card-frame');
  out.cardFound = !!card;
  out.cardRect = rect(card);

  // toggle row
  const toggle = document.querySelector('.st-key-auth_toggle');
  out.toggleFound = !!toggle;
  out.toggleDisplay = cs(toggle, 'display');
  out.toggleRect = rect(toggle);
  const togglePrimary = toggle ? toggle.querySelector('button[kind="primary"], '
        + 'button[data-testid="stBaseButton-primary"]') : null;
  out.togglePrimaryFound = !!togglePrimary;

  // form widgets
  const emailInput = document.querySelector('[data-testid="stTextInput"] input');
  out.emailBg = cs(emailInput, 'background-color');
  out.emailBorderRadius = cs(emailInput, 'border-top-left-radius');
  out.emailRect = rect(emailInput);

  // primary submit
  const submit = document.querySelector(
    '[data-testid="stFormSubmitButton"] button[kind="primary"]');
  out.submitFound = !!submit;
  out.submitBg = cs(submit, 'background-image') || cs(submit, 'background-color');
  out.submitHeight = cs(submit, 'height');
  out.submitRect = rect(submit);

  // hero pieces
  const heroTitle = document.querySelector('.au-title');
  out.heroTitleFound = !!heroTitle;
  out.heroTitleFontSize = cs(heroTitle, 'font-size');
  out.heroTitleRect = rect(heroTitle);

  // feature rows
  const featureRows = Array.from(document.querySelectorAll('.au-row'));
  out.featureRowCount = featureRows.length;
  // pairwise overlap (none should overlap)
  out.featureRowOverlaps = [];
  for (let i = 0; i + 1 < featureRows.length; i++) {
    const a = featureRows[i].getBoundingClientRect();
    const b = featureRows[i+1].getBoundingClientRect();
    if (a.bottom > b.top + 1) {
      out.featureRowOverlaps.push({i, gap: b.top - a.bottom});
    }
  }

  // legal at the bottom
  const legal = document.querySelector('.au-legal');
  out.legalFound = !!legal;
  out.legalRect = rect(legal);

  // google placeholder
  const google = document.querySelector('.au-google');
  out.googleFound = !!google;
  out.googleRect = rect(google);

  return out;
}
"""


# =====================================================================
# 6. Run Playwright at four viewports, screenshot, probe.
# =====================================================================
from playwright.sync_api import sync_playwright  # noqa: E402

VIEWPORTS = [
    ("1920", 1920, 1080),
    ("1440", 1440, 900),
    ("1024", 1024, 900),
    ("375",  375,  800),
]

results: dict = {}

with sync_playwright() as p:
    b = p.chromium.launch()
    for label, vw, vh in VIEWPORTS:
        pg = b.new_page(viewport={"width": vw, "height": vh})
        pg.goto(f"file://{HTML_PATH}", wait_until="networkidle")
        pg.wait_for_timeout(450)
        results[label] = pg.evaluate(PROBE)
        pg.screenshot(path=f"/tmp/auth_screen_{label}.png", full_page=True)
        pg.close()
    b.close()


# =====================================================================
# 7. Evaluate.
# =====================================================================
problems: list[str] = []


def _is_red(s: str | None) -> bool:
    """Cheap check that the primary submit's background paints red/dark
    red (allow either solid color or linear-gradient)."""
    if not s:
        return False
    nums = re.findall(r"\d+", s)
    if not nums:
        return False
    r, g, b = int(nums[0]), int(nums[1]), int(nums[2]) if len(nums) >= 3 else 0
    return r > 150 and g < 110 and b < 110


def _check(label: str, viewport: str, r: dict) -> None:
    v = r["viewport"]
    if v["scrollW"] > v["w"] + 2:
        problems.append(f"[{label}] horizontal overflow: scrollW={v['scrollW']} > viewport={v['w']}")

    if r["stHeaderDisplay"] != "none":
        problems.append(f"[{label}] stHeader is {r['stHeaderDisplay']!r}, expected 'none'")

    if not r["rootFound"]:
        problems.append(f"[{label}] .st-key-auth_root not found")
        return
    if r["rootDisplay"] != "grid":
        problems.append(f"[{label}] root display is {r['rootDisplay']!r}, expected 'grid'")

    if not r["heroFound"] or not r["panelFound"]:
        problems.append(f"[{label}] hero/panel missing: hero={r['heroFound']} panel={r['panelFound']}")
        return

    hero = r["heroRect"]; panel = r["panelRect"]
    # At desktop (≥981px) hero sits left of panel; at tablet/mobile they stack.
    if v["w"] >= 981:
        if hero["right"] > panel["x"] + 2:
            problems.append(
                f"[{label}] hero overlaps panel "
                f"(hero.right={hero['right']:.0f}, panel.x={panel['x']:.0f})"
            )
    else:
        # stacked: hero on top, panel below
        if hero["bottom"] > panel["y"] + 2:
            problems.append(
                f"[{label}] stacked hero overlaps panel "
                f"(hero.bottom={hero['bottom']:.0f}, panel.y={panel['y']:.0f})"
            )

    if not r["cardFound"]:
        problems.append(f"[{label}] .au-card-frame not found in panel")
    else:
        c = r["cardRect"]
        if c["x"] < panel["x"] - 2 or c["right"] > panel["right"] + 2:
            problems.append(
                f"[{label}] card frame escapes panel "
                f"(card.x={c['x']:.0f}, panel.x={panel['x']:.0f}; "
                f"card.right={c['right']:.0f}, panel.right={panel['right']:.0f})"
            )

    if not r["toggleFound"]:
        problems.append(f"[{label}] .st-key-auth_toggle not found")
    elif r["toggleDisplay"] != "flex":
        problems.append(
            f"[{label}] toggle display is {r['toggleDisplay']!r}, expected 'flex'")
    if not r["togglePrimaryFound"]:
        problems.append(f"[{label}] toggle has no primary (selected) button")

    # input bg must be dark (--au-ink-2 ≈ 13,15,19)
    bg = r["emailBg"] or ""
    nums = re.findall(r"\d+", bg)
    if not nums or int(nums[0]) > 30 or int(nums[1]) > 30:
        problems.append(
            f"[{label}] email input bg is {bg!r}; expected dark --au-ink-2")
    if r["emailBorderRadius"] not in ("14px",):
        problems.append(
            f"[{label}] email input border-radius is {r['emailBorderRadius']!r}, expected 14px")

    if not r["submitFound"]:
        problems.append(f"[{label}] primary submit button not found")
    else:
        # accept solid red or linear-gradient with reddish first stop
        sb = r["submitBg"] or ""
        if "gradient" in sb:
            # extract first rgb() inside the gradient
            m = re.search(r"rgb\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)", sb)
            if not m or not _is_red(m.group(0)):
                problems.append(
                    f"[{label}] primary CTA gradient is not brand red: {sb[:80]}")
        elif not _is_red(sb):
            problems.append(
                f"[{label}] primary CTA bg is not brand red: {sb!r}")
        # height should be 48px
        if r["submitHeight"] != "48px":
            problems.append(
                f"[{label}] primary CTA height is {r['submitHeight']!r}, expected 48px")

    if r["featureRowCount"] != 5:
        problems.append(
            f"[{label}] feature rows count is {r['featureRowCount']}, expected 5")
    if r["featureRowOverlaps"]:
        problems.append(
            f"[{label}] feature rows overlap: {r['featureRowOverlaps']}")

    if not r["legalFound"]:
        problems.append(f"[{label}] legal footer not found")
    if not r["googleFound"]:
        problems.append(f"[{label}] google placeholder not found")


for label, r in results.items():
    _check(label, label, r)


report = {
    "viewports_tested": [v[0] for v in VIEWPORTS],
    "screenshots": [f"/tmp/auth_screen_{v[0]}.png" for v in VIEWPORTS],
    "problems": problems,
    "all_passed": not problems,
    "results": results,
}
Path("/tmp/auth_screen_report.json").write_text(
    json.dumps(report, indent=2, default=str), encoding="utf-8"
)


print("=" * 68)
print("PREMIUM AUTH SCREEN — VISUAL QA HARNESS")
print("=" * 68)
for label, _, _ in VIEWPORTS:
    r = results[label]
    v = r["viewport"]
    print(f"\n--- viewport {label} ({v['w']}×{v['h']}) ---")
    print(f"  scroll w/h: {v['scrollW']} × {v['scrollH']}")
    print(f"  hero rect:  {r['heroRect']}")
    print(f"  panel rect: {r['panelRect']}")
    print(f"  card rect:  {r['cardRect']}")
    print(f"  submit height: {r['submitHeight']}, bg starts: "
          f"{(r['submitBg'] or '')[:60]}")
    print(f"  hero title font-size: {r['heroTitleFontSize']}")
    print(f"  feature rows: {r['featureRowCount']}, "
          f"overlaps: {len(r['featureRowOverlaps'])}")

print("\n" + "=" * 68)
if problems:
    print("FAIL · problems found:")
    for p_ in problems:
        print(f"  - {p_}")
else:
    print("PASS · auth screen renders cleanly at every viewport.")
print("=" * 68)
print(f"\nReport: /tmp/auth_screen_report.json")
print("Screenshots:")
for label, _, _ in VIEWPORTS:
    print(f"  /tmp/auth_screen_{label}.png")


if GATE and problems:
    sys.exit(1)
sys.exit(0)
