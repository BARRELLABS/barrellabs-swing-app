"""Take a full-page screenshot at high resolution to see the entire labeling
UI top-to-bottom."""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "validation" / "reports"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1800, "height": 1100},
                              device_scale_factor=1)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    page.goto("http://localhost:8503/")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('section[data-testid="stMain"]', timeout=10000)
    time.sleep(4)

    # Collapse the video expander so we can see the marking surface
    # directly underneath. The "Watch the swing" expander has a header
    # button.
    try:
        page.get_by_text("Watch the swing").first.click(timeout=3000)
        time.sleep(2)
    except Exception as e:
        print(f"(could not collapse expander: {e})")

    full = OUT / "_pw_full_collapsed.png"
    page.screenshot(path=full, full_page=True)
    print(f"saved: {full}")
    print(f"page height: {page.evaluate('document.body.scrollHeight')}px")

    # And one with the expander still open
    try:
        page.get_by_text("Watch the swing").first.click(timeout=3000)
        time.sleep(2)
    except Exception:
        pass
    full_open = OUT / "_pw_full_open.png"
    page.screenshot(path=full_open, full_page=True)
    print(f"saved: {full_open}")

    browser.close()
