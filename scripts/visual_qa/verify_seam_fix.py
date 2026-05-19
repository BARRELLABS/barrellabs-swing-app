"""Rigorous, auth-free proof that the masthead sits FLUSH at top=0 with
zero slit, against Streamlit 1.57's REAL default chrome.

Builds a DOM skeleton identical to Streamlit 1.57 (stApp > stHeader
[abs 60px z999990] + stAppViewContainer > stMain[flex] >
stMainBlockContainer[.block-container, default padding 96px 16px 160px]
> stVerticalBlock[flex, default gap 16px] > stElementContainer*), with
those defaults applied via a CLASS stylesheet (exactly like Streamlit's
emotion CSS, NOT inline) so the real _EDGE_MASTHEAD_CSS !important
overrides behave precisely as in production. Then injects the REAL
_EDGE_MASTHEAD_CSS + the REAL render_edge_masthead() HTML, and asserts
via Playwright:
  * .ble-mast top == 0  (no padding/gap/header above)
  * stApp / stMain / stMainBlockContainer / body backgrounds all #0A0B0E
  * stHeader not visible
Exit code 0 only if ALL pass. Screenshot -> /tmp/seam_fix.png
"""
from __future__ import annotations
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# --- capture the REAL masthead html + css via a tiny streamlit stub ---
_CAP: list[str] = []
st = types.ModuleType("streamlit")
class _SS(dict):
    def __getattr__(s, k):
        try: return s[k]
        except KeyError as e: raise AttributeError(k) from e
    def __setattr__(s, k, v): s[k] = v
st.session_state = _SS()
class _QP(dict):
    def get(self, k, d=None): return super().get(k, d)
st.query_params = _QP()
class _C:
    def __enter__(self): return self
    def __exit__(self, *e): return False
st.markdown = lambda s, **k: _CAP.append(str(s))
st.container = lambda *a, **k: _C()
st.columns = lambda n, **k: [_C() for _ in range(n if isinstance(n, int) else len(n))]
for _n in ("button", "write", "error", "warning", "info", "caption",
           "image", "rerun", "stop", "toast"):
    setattr(st, _n, lambda *a, **k: None)
_c1 = types.ModuleType("streamlit.components.v1"); _c1.html = lambda *a, **k: None
_c0 = types.ModuleType("streamlit.components"); _c0.v1 = _c1; st.components = _c0
sys.modules["streamlit"] = st
sys.modules["streamlit.components"] = _c0
sys.modules["streamlit.components.v1"] = _c1

import importlib
bec = importlib.import_module("bl_edge_chrome")
_CAP.clear()
bec.render_edge_masthead({"name": "Mario Ricard",
                          "gamification": {"current_streak_days": 7}},
                         active_page="dashboard")
mast_blob = "\n".join(_CAP)  # contains the <style>…</style> + masthead HTML

# Streamlit 1.57 default chrome reproduced via a CLASS stylesheet
# (same mechanism as Streamlit's emotion CSS — no inline styles).
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
</style>
"""

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

PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{ST_DEFAULTS}
</head><body>
<div data-testid="stApp" class="stApp">
  <header data-testid="stHeader" class="stAppHeader"><div>toolbar</div></header>
  <div data-testid="stAppViewContainer">
    <section data-testid="stMain" class="stMain">
      <div data-testid="stMainBlockContainer" class="stMainBlockContainer block-container">
        <div data-testid="stVerticalBlock" class="stVerticalBlock">
          <div data-testid="stElementContainer">{mast_blob}</div>
          <div data-testid="stElementContainer">{DASH_BAND}</div>
        </div>
      </div>
    </section>
  </div>
</div>
</body></html>"""

OUT = Path("/tmp/seam_fix.html")
OUT.write_text(PAGE, encoding="utf-8")

from playwright.sync_api import sync_playwright

CHECK = r"""
() => {
  const bg = el => getComputedStyle(el).backgroundColor;
  const norm = c => c.replace(/\s+/g,'');
  const m = document.querySelector('.ble-mast');
  const r = m ? m.getBoundingClientRect() : null;
  const hdr = document.querySelector('[data-testid="stHeader"]');
  const hs = hdr ? getComputedStyle(hdr) : null;
  const ink = norm('rgb(10, 11, 14)'); // #0A0B0E
  const layers = ['[data-testid="stApp"]','[data-testid="stMain"]',
    '[data-testid="stMainBlockContainer"]'];
  const layerBg = {};
  layers.forEach(s=>{const e=document.querySelector(s);
    layerBg[s]= e? norm(bg(e)) : 'MISSING';});
  const bodyBg = norm(bg(document.body));
  return {
    mastTop: r ? Math.round(r.top) : 'NO .ble-mast',
    mastBg: m ? norm(bg(m)) : null,
    headerHidden: hs ? (hs.display==='none'||hs.visibility==='hidden') : 'no header',
    layerBg, bodyBg, ink,
    allInk: Object.values(layerBg).every(v=>v===ink) && bodyBg===ink,
    navGlass: (()=>{const n=document.querySelector('.ble-nav');
      if(!n)return null;const s=getComputedStyle(n);
      return {bg:s.backgroundColor, blur:s.backdropFilter,
              radius:s.borderRadius};})(),
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"file://{OUT}", wait_until="networkidle")
    pg.wait_for_timeout(700)
    res = pg.evaluate(CHECK)
    pg.screenshot(path="/tmp/seam_fix.png",
                  clip={"x": 0, "y": 0, "width": 1440, "height": 340})
    b.close()

import json
print(json.dumps(res, indent=2))

ok = (res["mastTop"] == 0
      and res["headerHidden"] is True
      and res["allInk"] is True)
print("\n=== VERDICT:", "PASS ✅" if ok else "FAIL ❌", "===")
sys.exit(0 if ok else 1)
