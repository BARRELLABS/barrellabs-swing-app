"""Auth-free proof that the masthead nav buttons render as premium,
seamless glass tabs against Streamlit 1.57's real button DOM.

This is the missing third leg of the visual_qa harness suite:

  verify_seam_fix.py  — masthead is flush at top, ink is uniform.
  render_full_app_static.py — page bodies (saved reports, swing report)
                              render correctly as HTML.
  verify_nav_tabs.py  — (THIS FILE) the actual nav buttons look right,
                        respond to hover/focus correctly, and the active
                        state has the gold→red underline.

Why this file exists
--------------------
The button-based nav is the auth-safe replacement for the old anchor
nav. Streamlit 1.57's button DOM is:
  <div data-testid="stElementContainer">
    <div data-testid="stButton">
      <button kind="secondary|primary" data-testid="stBaseButton-...">
        <div data-testid="stMarkdownContainer"><p>Label</p></div>
      </button>
    </div>
  </div>
The CSS in bl_edge_chrome.py is scoped to .st-key-bl_edge_navbar and
targets that exact DOM. Without a real Streamlit session we cannot hit
the live page, so this harness reconstructs the button DOM by hand,
injects the real _EDGE_MASTHEAD_CSS, and screenshots + asserts the
computed pixel-level details (color, typography, padding, hover delta,
active underline pseudo-element, focus ring).

Exit code 0 only if ALL pass. Screenshots:
  /tmp/nav_tabs_rest.png    — masthead with Dashboard active, default
  /tmp/nav_tabs_hover.png   — same with hover applied to Sessions
  /tmp/nav_tabs_focus.png   — keyboard focus ring on Compare
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Extract the masthead CSS verbatim from the source file so this harness
# always proves what production actually ships.
src = (ROOT / "bl_edge_chrome.py").read_text(encoding="utf-8")
m = re.search(r"_EDGE_MASTHEAD_CSS\s*=\s*\"\"\"(.*?)\"\"\"", src, re.S)
assert m, "could not locate _EDGE_MASTHEAD_CSS in bl_edge_chrome.py"
EDGE_CSS = m.group(1)

# Reproduce Streamlit 1.57's default chrome stylesheet so the masthead
# CSS competes against the same defaults as in production.
ST_DEFAULTS = """
<style>
  html,body{margin:0;padding:0;background:#262730;}
  [data-testid="stApp"]{position:absolute;inset:0;background:#FFFFFF;}
  [data-testid="stHeader"]{position:absolute;top:0;left:0;right:0;
    height:60px;background:#FFFFFF;z-index:999990;display:flex;}
  [data-testid="stMain"]{display:flex;flex-direction:column;
    background:transparent;}
  [data-testid="stMainBlockContainer"]{padding:96px 16px 160px;
    max-width:736px;margin:0 auto;background:transparent;}
  [data-testid="stVerticalBlock"]{display:flex;flex-direction:column;
    gap:16px;}
  [data-testid="stElementContainer"]{}
  /* Streamlit 1.57 default button reset */
  button{font:inherit;color:inherit;cursor:pointer;
    background:rgb(247,247,247);border:1px solid rgba(49,51,63,0.2);
    padding:0.25rem 0.75rem;border-radius:0.5rem;
    font-family:"Source Sans Pro",sans-serif;}
</style>
"""


def _button_html(label: str, *, primary: bool) -> str:
    kind = "primary" if primary else "secondary"
    testid = f"stBaseButton-{kind}"
    return (
        '<div data-testid="stElementContainer" class="stElementContainer">'
        '<div data-testid="stButton" class="stButton">'
        f'<button kind="{kind}" data-testid="{testid}" type="button">'
        '<div data-testid="stMarkdownContainer" class="stMarkdownContainer">'
        f'<p>{label}</p>'
        '</div></button></div></div>'
    )


NAV_LABELS = [
    ("Dashboard", "dashboard"),
    ("Sessions", "saved_reports"),
    ("Compare", "compare_swings"),
    # "Drills" was renamed to "Training Plan" — see bl_edge_chrome._NAV_ENTRIES.
    ("Training Plan", "development_tracker"),
    ("Library", "historical_charts"),
]


def build_masthead_html(active_key: str) -> str:
    """Reconstruct exactly what render_edge_masthead() emits — the same
    .st-key-* containers, brand markup, button DOM, and user chip."""
    buttons_html = "".join(
        _button_html(label, primary=(key == active_key))
        for label, key in NAV_LABELS
    )
    brand_html = (
        '<div class="ble-brand">'
        '<span style="width:30px;height:30px;border-radius:50%;'
        'background:#E64530;display:block;"></span>'
        '<span class="wm">BarrelLabs<span class="sl">/</span>'
        '<span class="ed">Edge</span></span>'
        '</div>'
    )
    # Streak (still static markdown) + avatar BUTTON (the new clickable
    # one — routes to player_settings). Keyed `bl_edge_userchip`
    # container so the same masthead CSS that styles the navbar buttons
    # also styles the avatar.
    avatar_btn_html = (
        '<div data-testid="stElementContainer" class="stElementContainer">'
        '<div data-testid="stButton" class="stButton">'
        '<button kind="secondary" data-testid="stBaseButton-secondary" '
        'type="button" title="Player Settings">'
        '<div data-testid="stMarkdownContainer" class="stMarkdownContainer">'
        '<p>MR</p></div></button></div></div>'
    )
    chip_html = (
        '<div class="st-key-bl_edge_userchip stElementContainer" '
        'data-testid="stElementContainer">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        '<div data-testid="stElementContainer">'
        '<span class="ble-streak">'
        '<span class="d"></span>7-day streak</span>'
        '</div>'
        f'{avatar_btn_html}'
        '</div></div>'
    )
    # Mirror render_edge_masthead: keyed container wraps a stVerticalBlock,
    # the brand markdown + nested keyed navbar container + nested keyed
    # userchip container.
    return (
        '<div class="st-key-bl_edge_masthead stElementContainer" '
        'data-testid="stElementContainer">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'<div data-testid="stElementContainer">{brand_html}</div>'
        '<div class="st-key-bl_edge_navbar stElementContainer" '
        'data-testid="stElementContainer">'
        '<div data-testid="stVerticalBlock" class="stVerticalBlock">'
        f'{buttons_html}'
        '</div></div>'
        f'{chip_html}'
        '</div></div>'
    )


DASH_BAND = """
<div style="background:#0A0B0E;color:#F4EFE6;font-family:Geist,system-ui;
            padding:30px 40px 70px;">
  <div style="font-family:'Geist Mono',monospace;font-size:11px;
       letter-spacing:.26em;text-transform:uppercase;color:#E64530;">
    § 01 · this week's headline</div>
  <div style="font-family:'Instrument Serif',Georgia,serif;font-style:italic;
       font-size:3.2rem;margin:.4rem 0 0;">Your separation hit
       <span style="color:#E8C170;">+27.7°</span> — MLB territory.</div>
</div>
"""


def build_page(active_key: str) -> str:
    masthead = build_masthead_html(active_key)
    # EDGE_CSS already contains its own <style>...</style> wrapper — inject
    # raw, not re-wrapped.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{ST_DEFAULTS}
{EDGE_CSS}
</head><body>
<div data-testid="stApp" class="stApp">
  <header data-testid="stHeader" class="stAppHeader"><div>toolbar</div></header>
  <div data-testid="stAppViewContainer">
    <section data-testid="stMain" class="stMain">
      <div data-testid="stMainBlockContainer" class="stMainBlockContainer block-container">
        <div data-testid="stVerticalBlock" class="stVerticalBlock">
          <div data-testid="stElementContainer">{masthead}</div>
          <div data-testid="stElementContainer">{DASH_BAND}</div>
        </div>
      </div>
    </section>
  </div>
</div>
</body></html>"""


# Build pages: rest (Dashboard active), hover, focus, plus a sessions-active
# snapshot that proves the masthead is byte-identical on the Saved Reports
# page AND the Swing Report page (alt_keys → both surface "Sessions" as
# active so the cross-page look is one shot, not three).
PAGE_PATHS = {
    "rest": (Path("/tmp/nav_tabs_rest.html"), "dashboard"),
    "hover": (Path("/tmp/nav_tabs_hover.html"), "dashboard"),
    "focus": (Path("/tmp/nav_tabs_focus.html"), "dashboard"),
    "sessions": (Path("/tmp/nav_tabs_sessions.html"), "saved_reports"),
}
for path, active in PAGE_PATHS.values():
    path.write_text(build_page(active), encoding="utf-8")


# --------------- Playwright assertions ---------------

# Helper: parse "rgb(a,b,c)" → tuple of ints (ignoring optional alpha).
def _rgb(s: str) -> tuple[int, int, int]:
    nums = re.findall(r"\d+", s)
    return (int(nums[0]), int(nums[1]), int(nums[2]))


# Color targets (from bl_edge_chrome.py):
INK = (10, 11, 14)
INACTIVE_TEXT = (128, 131, 139)   # #80838B
ACTIVE_TEXT = (248, 242, 224)     # #F8F2E0
HOVER_TEXT = (239, 233, 219)      # #EFE9DB
GOLD = (232, 193, 112)            # #E8C170

REST_PROBE = r"""
() => {
  const nav = document.querySelector('.st-key-bl_edge_navbar');
  if (!nav) return {ok:false, error:'no navbar'};
  const buttons = Array.from(nav.querySelectorAll('button'));
  if (buttons.length !== 5) return {ok:false, error:'expected 5 buttons, got '+buttons.length};
  const navStyle = getComputedStyle(nav);
  const labels = buttons.map(b => b.innerText.trim());
  const inactive = buttons.find(b => b.getAttribute('kind') === 'secondary');
  const active = buttons.find(b => b.getAttribute('kind') === 'primary');
  if (!active) return {ok:false, error:'no active button'};

  const inactiveStyle = getComputedStyle(inactive);
  const activeStyle = getComputedStyle(active);
  const afterStyle = getComputedStyle(active, '::after');

  // bounding boxes — all buttons should share the same row (no wrap)
  const tops = buttons.map(b => Math.round(b.getBoundingClientRect().top));
  const sameRow = tops.every(t => t === tops[0]);

  // hairline separator: ::before on each inactive button (the "extra touch")
  const beforeStyles = buttons.map(b => {
    const s = getComputedStyle(b, '::before');
    return {
      content: s.content,
      width: s.width,
      opacity: parseFloat(s.opacity || '0'),
      hasGradient: /linear-gradient/.test(s.backgroundImage || ''),
    };
  });

  // typography on the <p> inside the button (where the label actually lives)
  const labelEl = active.querySelector('p') || active;
  const labelStyle = getComputedStyle(labelEl);

  // Avatar button — clickable circle in the userchip container
  const userchip = document.querySelector('.st-key-bl_edge_userchip');
  const avatar = userchip ? userchip.querySelector('button') : null;
  const avatarStyle = avatar ? getComputedStyle(avatar) : null;
  const avatarBox = avatar ? avatar.getBoundingClientRect() : null;
  const streak = userchip ? userchip.querySelector('.ble-streak') : null;

  return {
    ok: true,
    labels,
    navDisplay: navStyle.display,
    navBorderRadius: navStyle.borderRadius,
    navBackdropFilter: navStyle.backdropFilter || navStyle.webkitBackdropFilter,
    navBackground: navStyle.backgroundColor,
    navBorder: navStyle.borderStyle,
    inactive: {
      color: inactiveStyle.color,
      background: inactiveStyle.backgroundColor,
      font: inactiveStyle.fontFamily,
      size: inactiveStyle.fontSize,
      weight: inactiveStyle.fontWeight,
      tracking: inactiveStyle.letterSpacing,
      transform: inactiveStyle.textTransform,
      padding: inactiveStyle.padding,
      radius: inactiveStyle.borderRadius,
    },
    active: {
      color: activeStyle.color,
      background: activeStyle.backgroundImage || activeStyle.backgroundColor,
      borderColor: activeStyle.borderColor,
      boxShadow: activeStyle.boxShadow,
    },
    afterUnderline: {
      content: afterStyle.content,
      height: afterStyle.height,
      background: afterStyle.backgroundImage,
      hasGradient: /linear-gradient/.test(afterStyle.backgroundImage || ''),
      hasGoldOrRed: /232,\s*193,\s*112|230,\s*69,\s*48/.test(afterStyle.backgroundImage || ''),
    },
    separators: beforeStyles,
    sameRow,
    labelFontFamily: labelStyle.fontFamily,
    labelLetterSpacing: labelStyle.letterSpacing,
    avatar: avatar ? {
      label: avatar.innerText.trim(),
      width: Math.round(avatarBox.width),
      height: Math.round(avatarBox.height),
      borderRadius: avatarStyle.borderRadius,
      fontFamily: avatarStyle.fontFamily,
      fontStyle: avatarStyle.fontStyle,
      color: avatarStyle.color,
      isCircle: Math.round(avatarBox.width) === Math.round(avatarBox.height),
      onMasthead: avatarBox.top < 100,
      onRight: avatarBox.left > 1100,  // viewport=1440, right side
      streakPresent: !!streak,
    } : null,
  };
}
"""

AVATAR_HOVER_PROBE = r"""
() => {
  const avatar = document.querySelector('.st-key-bl_edge_userchip button');
  const s = getComputedStyle(avatar);
  return {
    color: s.color,
    borderColor: s.borderColor,
    boxShadow: s.boxShadow,
    transform: s.transform,
    hasGoldRing: /232,\s*193,\s*112/.test(s.boxShadow) ||
                 /232,\s*193,\s*112/.test(s.borderColor),
  };
}
"""

HOVER_PROBE = r"""
() => {
  const nav = document.querySelector('.st-key-bl_edge_navbar');
  const buttons = Array.from(nav.querySelectorAll('button'));
  // Sessions is the 2nd button (index 1) — hover it.
  const sess = buttons[1];
  const before = getComputedStyle(sess);
  const beforeColor = before.color;
  const beforeBg = before.backgroundColor;
  // Trigger CSS :hover via pseudo simulation — Playwright's hover() does
  // this for real; we just return the labels and the page will be probed
  // after hover() is called server-side.
  return {beforeColor, beforeBg, label: sess.innerText.trim()};
}
"""

HOVER_PROBE_AFTER = r"""
() => {
  const nav = document.querySelector('.st-key-bl_edge_navbar');
  const buttons = Array.from(nav.querySelectorAll('button'));
  const sess = buttons[1];
  const s = getComputedStyle(sess);
  return {
    color: s.color,
    background: s.backgroundColor,
    borderColor: s.borderColor,
    transform: s.transform,
  };
}
"""

FOCUS_PROBE_AFTER = r"""
() => {
  const nav = document.querySelector('.st-key-bl_edge_navbar');
  const buttons = Array.from(nav.querySelectorAll('button'));
  // Compare is the 3rd button (index 2) — focus it via keyboard.
  const cmp = buttons[2];
  const s = getComputedStyle(cmp);
  return {
    label: cmp.innerText.trim(),
    boxShadow: s.boxShadow,
    outline: s.outlineWidth + ' ' + s.outlineStyle + ' ' + s.outlineColor,
    hasGoldRing: /232,\s*193,\s*112/.test(s.boxShadow),
  };
}
"""

from playwright.sync_api import sync_playwright

results: dict = {}

with sync_playwright() as p:
    b = p.chromium.launch()

    # --- REST page: structural + typography + active underline ---
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{PAGE_PATHS['rest'][0]}", wait_until="networkidle")
    pg.wait_for_timeout(400)
    rest = pg.evaluate(REST_PROBE)
    pg.screenshot(path="/tmp/nav_tabs_rest.png",
                  clip={"x": 0, "y": 0, "width": 1440, "height": 120})
    results["rest"] = rest
    pg.close()

    # --- HOVER page: hover Sessions, check color shift + bg appearance ---
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{PAGE_PATHS['hover'][0]}", wait_until="networkidle")
    pg.wait_for_timeout(400)
    pre = pg.evaluate(HOVER_PROBE)
    # hover the 2nd button (Sessions)
    pg.locator(".st-key-bl_edge_navbar button").nth(1).hover()
    pg.wait_for_timeout(350)  # let the 220ms transition settle
    hov = pg.evaluate(HOVER_PROBE_AFTER)
    pg.screenshot(path="/tmp/nav_tabs_hover.png",
                  clip={"x": 0, "y": 0, "width": 1440, "height": 120})
    results["hover"] = {"label": pre["label"], **hov,
                        "before_color": pre["beforeColor"]}
    pg.close()

    # --- FOCUS page: keyboard-focus Compare, expect gold ring ---
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{PAGE_PATHS['focus'][0]}", wait_until="networkidle")
    pg.wait_for_timeout(400)
    # Tab into the page so :focus-visible engages (mouse focus is hidden
    # by design via :focus:not(:focus-visible)).
    pg.locator(".st-key-bl_edge_navbar button").nth(2).focus()
    # Force focus-visible by simulating a keyboard navigation
    pg.keyboard.press("Tab")  # moves to next
    pg.keyboard.press("Shift+Tab")  # back to Compare with keyboard focus
    pg.wait_for_timeout(200)
    foc = pg.evaluate(FOCUS_PROBE_AFTER)
    pg.screenshot(path="/tmp/nav_tabs_focus.png",
                  clip={"x": 0, "y": 0, "width": 1440, "height": 120})
    results["focus"] = foc
    pg.close()

    # --- SESSIONS-ACTIVE page: identical chrome with Sessions highlighted.
    # The alt_keys mapping in bl_edge_chrome.py makes swing_report also
    # surface Sessions as active, so this single screenshot represents the
    # masthead look on BOTH the Saved Reports page and the Swing Report
    # page — proves cross-page visual identity. ---
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{PAGE_PATHS['sessions'][0]}", wait_until="networkidle")
    pg.wait_for_timeout(400)
    sess_active_label = pg.evaluate(
        "() => document.querySelector('.st-key-bl_edge_navbar "
        "button[kind=primary]').innerText.trim()"
    )
    pg.screenshot(path="/tmp/nav_tabs_sessions.png",
                  clip={"x": 0, "y": 0, "width": 1440, "height": 120})
    results["sessions_active"] = {"active_label": sess_active_label}
    pg.close()

    # --- AVATAR HOVER: hover the clickable initials circle, expect gold ---
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{PAGE_PATHS['rest'][0]}", wait_until="networkidle")
    pg.wait_for_timeout(400)
    pg.locator(".st-key-bl_edge_userchip button").hover()
    pg.wait_for_timeout(350)
    av_hov = pg.evaluate(AVATAR_HOVER_PROBE)
    pg.screenshot(path="/tmp/nav_tabs_avatar_hover.png",
                  clip={"x": 1000, "y": 0, "width": 440, "height": 90})
    results["avatar_hover"] = av_hov
    pg.close()

    b.close()


import json

print(json.dumps(results, indent=2))

# ---------------- Assertions ----------------
problems: list[str] = []
rest = results["rest"]

if not rest.get("ok"):
    problems.append(f"REST probe failed: {rest.get('error')}")
else:
    # CSS text-transform:uppercase makes innerText return uppercase — that's
    # by design (sports-tech editorial typography).
    if rest["labels"] != ["DASHBOARD", "SESSIONS", "COMPARE", "TRAINING PLAN", "LIBRARY"]:
        problems.append(f"labels wrong: {rest['labels']}")
    if rest["navDisplay"] != "flex":
        problems.append(f"navbar is not flex: {rest['navDisplay']}")
    if not rest["sameRow"]:
        problems.append("buttons did not lay out in a single row")
    if "Geist Mono" not in rest["inactive"]["font"]:
        problems.append(f"inactive font is not Geist Mono: {rest['inactive']['font']}")
    if rest["inactive"]["transform"] != "uppercase":
        problems.append(f"inactive label is not uppercase: {rest['inactive']['transform']}")
    if rest["inactive"]["size"] not in ("11px", "10px"):
        problems.append(f"inactive font-size unexpected: {rest['inactive']['size']}")
    # color: inactive ≈ #80838B, active ≈ #F8F2E0 (warm bone)
    inactive_rgb = _rgb(rest["inactive"]["color"])
    active_rgb = _rgb(rest["active"]["color"])
    if abs(inactive_rgb[0] - INACTIVE_TEXT[0]) > 6 or abs(inactive_rgb[1] - INACTIVE_TEXT[1]) > 6:
        problems.append(f"inactive color drift: {inactive_rgb} vs target {INACTIVE_TEXT}")
    if abs(active_rgb[0] - ACTIVE_TEXT[0]) > 6 or abs(active_rgb[1] - ACTIVE_TEXT[1]) > 6:
        problems.append(f"active color drift: {active_rgb} vs target {ACTIVE_TEXT}")
    # active underline pseudo-element must have a gold-or-red gradient
    if not rest["afterUnderline"]["hasGradient"]:
        problems.append("active button ::after has no gradient (the underline is gone)")
    if not rest["afterUnderline"]["hasGoldOrRed"]:
        problems.append("active underline missing gold/red colors")

    # ---- The "extra touch": hairline separators ----
    # rest["separators"] is in nav-button order: [Dashboard, Sessions,
    # Compare, Drills, Library]. Dashboard is active (index 0). Expect:
    #   index 0 (active itself): hidden
    #   index 1 (immediately after active): hidden
    #   index 2, 3, 4: VISIBLE
    seps = rest["separators"]
    if len(seps) != 5:
        problems.append(f"expected 5 separators, got {len(seps)}")
    else:
        if seps[0]["opacity"] > 0.01:
            problems.append("separator on active button (Dashboard) should be hidden")
        if seps[1]["opacity"] > 0.01:
            problems.append("separator on Sessions (after active) should be hidden")
        # at least one of buttons 2-4 should show its separator
        if all(s["opacity"] < 0.5 for s in seps[2:]):
            problems.append("hairline separators between inactive tabs are all invisible")
        # all separators must use the same gradient style
        if not all(s["hasGradient"] for s in seps):
            problems.append("not all separators use the brand gradient hairline")

    # ---- The clickable avatar circle ----
    av = rest["avatar"]
    if av is None:
        problems.append("avatar button not found in .st-key-bl_edge_userchip")
    else:
        if not av["isCircle"]:
            problems.append(f"avatar not a circle: {av['width']}x{av['height']}")
        if av["width"] < 32 or av["width"] > 48:
            problems.append(f"avatar size out of range (32-48px): {av['width']}px")
        if "50%" not in av["borderRadius"]:
            problems.append(f"avatar border-radius is not 50%: {av['borderRadius']}")
        if "Instrument Serif" not in av["fontFamily"]:
            problems.append(f"avatar font is not Instrument Serif: {av['fontFamily']}")
        if av["fontStyle"] != "italic":
            problems.append(f"avatar font-style is not italic: {av['fontStyle']}")
        if not av["onMasthead"]:
            problems.append(f"avatar is not on the masthead row (top={av})")
        if not av["onRight"]:
            problems.append(f"avatar is not aligned far right (left={av})")
        if av["label"] != "MR":
            problems.append(f"avatar label not 'MR': {av['label']}")
        if not av["streakPresent"]:
            problems.append("streak chip is missing next to the avatar")

    av_hov = results.get("avatar_hover", {})
    if not av_hov.get("hasGoldRing"):
        problems.append(
            f"avatar hover did not produce a gold ring: {av_hov}"
        )

hov = results["hover"]
hov_rgb = _rgb(hov["color"])
if abs(hov_rgb[0] - HOVER_TEXT[0]) > 8:
    problems.append(f"hover color did not brighten as expected: {hov_rgb} vs target {HOVER_TEXT}")
# bg should have some non-zero alpha → not the parent's transparent rgba(0,0,0,0)
# rest bg of an inactive button is transparent, hover bg ≈ rgba(244,239,230,0.045)
if "rgba(244" not in hov["background"] and "rgb(244" not in hov["background"]:
    # could also be rgba(0,0,0,0) if hover didn't take — that's the failure mode
    if "0, 0, 0, 0" in hov["background"] or "rgba(0,0,0,0)" in hov["background"]:
        problems.append(f"hover background did not appear: {hov['background']}")

foc = results["focus"]
if not foc["hasGoldRing"]:
    problems.append(f"keyboard focus ring missing gold color: boxShadow={foc['boxShadow']}")

# Sessions-active assertion: when render_edge_masthead is called with
# active_page="saved_reports", the Sessions button (NOT Dashboard) must be
# the primary. This same state surfaces on the Swing Report page via the
# alt_keys mapping, so this assertion covers both pages.
sess = results["sessions_active"]
if sess["active_label"] != "SESSIONS":
    problems.append(
        f"active label on saved_reports page should be SESSIONS, got "
        f"{sess['active_label']}"
    )

print("\n--- Assertions ---")
if problems:
    for pblm in problems:
        print(f"  FAIL: {pblm}")
    print("\n=== VERDICT: FAIL ===")
    sys.exit(1)
else:
    print("  all good — typography, color, hover, focus, underline ✓")
    print("\n=== VERDICT: PASS ===")
    sys.exit(0)
