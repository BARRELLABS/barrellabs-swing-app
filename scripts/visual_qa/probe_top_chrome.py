"""Forensic probe of the LIVE Streamlit 1.57 DOM at localhost:8501.

The top-of-page chrome (stApp / stMain / stMainBlockContainer /
stVerticalBlock / stElementContainer + the .ble-mast masthead) is
identical whether logged in or on the login screen, so we can measure
the exact "slit" + "extra top padding" source without auth.

Usage:
    .venv/bin/python scripts/visual_qa/probe_top_chrome.py
Prints JSON: each top node's rect, key computed styles, and the
masthead's distance from viewport top. Saves a screenshot.
"""
from __future__ import annotations
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8501/"

JS = r"""
() => {
  const pick = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      testid: el.getAttribute('data-testid') || null,
      cls: (el.className && el.className.toString().slice(0,80)) || null,
      top: Math.round(r.top), bottom: Math.round(r.bottom),
      height: Math.round(r.height),
      mt: s.marginTop, mb: s.marginBottom,
      pt: s.paddingTop, pb: s.paddingBottom,
      gap: s.rowGap || s.gap,
      bg: (s.backgroundColor || '') + ' | ' +
          (s.backgroundImage || '').slice(0,60),
      pos: s.position, z: s.zIndex,
      borderTop: s.borderTopWidth + ' ' + s.borderTopColor,
      display: s.display,
    };
  };
  const q = (sel) => pick(document.querySelector(sel));
  const out = {
    viewport: {w: innerWidth, h: innerHeight},
    stApp: q('[data-testid="stApp"]'),
    stDecoration: q('[data-testid="stDecoration"]'),
    stHeader: q('[data-testid="stHeader"]'),
    stToolbar: q('[data-testid="stToolbar"]'),
    stMain: q('[data-testid="stMain"]'),
    stMainBlockContainer: q('[data-testid="stMainBlockContainer"]'),
  };
  // First vertical block + its first element container (where the
  // masthead lives) — the prime "extra top padding" suspects.
  const vb = document.querySelector(
    '[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]');
  out.firstVerticalBlock = pick(vb);
  const ec = vb ? vb.querySelector('[data-testid="stElementContainer"]') : null;
  out.firstElementContainer = pick(ec);
  out.bleMast = q('.ble-mast');
  out.bleNav  = q('.ble-nav');
  out.bleTabActive = q('.ble-tab.is-active');
  // What is literally at the pixel directly above the masthead?
  const m = document.querySelector('.ble-mast');
  if (m) {
    const r = m.getBoundingClientRect();
    const probeY = Math.max(0, r.top - 2);
    const elAbove = document.elementFromPoint(Math.round(r.left + r.width/2),
                                              Math.round(probeY));
    out.pixelAboveMast = pick(elAbove);
    out.mastTopGapPx = Math.round(r.top);
  }
  // body / html bg for seam analysis
  out.body = pick(document.body);
  out.html = pick(document.documentElement);
  return out;
}
"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(URL, wait_until="networkidle", timeout=45000)
        # Streamlit renders client-side; wait for the masthead or app root.
        try:
            pg.wait_for_selector('.ble-mast, [data-testid="stApp"]',
                                  timeout=30000)
        except Exception:
            pass
        pg.wait_for_timeout(2500)
        data = pg.evaluate(JS)
        print(json.dumps(data, indent=2))
        pg.screenshot(path="/tmp/probe_top.png", clip={
            "x": 0, "y": 0, "width": 1440, "height": 360})
        b.close()


if __name__ == "__main__":
    sys.exit(main())
