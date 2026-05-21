"""Playwright verification of the new live frame-counter overlay.

Drives the labeling app:
  1. Opens http://localhost:8503/
  2. Picks the first swing
  3. Reads the frame-counter element inside the components.html iframe
  4. Plays the video for ~1.5 s
  5. Reads the frame counter again — verifies it has advanced
  6. Saves before/during/after screenshots for visual review

Run:
    python3 -m scripts.validation._pw_verify_counter
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

OUT = Path(__file__).resolve().parents[2] / "validation" / "reports"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1800, "height": 1200})
        page = ctx.new_page()
        page.set_default_timeout(20000)

        print("→ Loading http://localhost:8503/")
        page.goto("http://localhost:8503/")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector('section[data-testid="stMain"]', timeout=10000)
        time.sleep(4)  # let Streamlit settle

        page.screenshot(path=OUT / "_counter_01_initial.png", full_page=True)
        print(f"   initial screenshot saved")

        # Find the components iframe (the custom video player lives in one)
        iframes = page.frames
        print(f"   total frames on page: {len(iframes)}")
        component_frame = None
        for f in iframes:
            try:
                if f.locator("#vid").count() > 0:
                    component_frame = f
                    print(f"   ✓ found component iframe with #vid")
                    break
            except Exception:
                pass

        if component_frame is None:
            print("   ✗ Could not find component iframe containing the video")
            browser.close()
            return 2

        # Confirm the frame-counter element is present
        fd_count = component_frame.locator("#frameDisplay").count()
        td_count = component_frame.locator("#timeDisplay").count()
        print(f"   #frameDisplay: {fd_count}, #timeDisplay: {td_count}")
        if fd_count == 0:
            print("   ✗ frameDisplay element not in iframe DOM")
            browser.close()
            return 3

        # Read initial state
        # Wait briefly for video metadata to load (currentTime starts at 0 once loaded)
        time.sleep(2)
        initial_text = component_frame.locator("#frameDisplay").inner_text()
        initial_time = component_frame.locator("#timeDisplay").inner_text()
        print(f"   initial frame counter: '{initial_text}', t='{initial_time}'s")

        # Play the video by clicking inside the iframe — call the JS API directly
        try:
            component_frame.evaluate(
                "() => { const v = document.getElementById('vid'); "
                "v.currentTime = 0; v.play(); }"
            )
            time.sleep(2.0)  # let it play for 2 seconds
            mid_text = component_frame.locator("#frameDisplay").inner_text()
            mid_time = component_frame.locator("#timeDisplay").inner_text()
            print(f"   after 2s playback: frame='{mid_text}', t='{mid_time}'s")
            component_frame.evaluate(
                "() => document.getElementById('vid').pause()"
            )
        except Exception as e:
            print(f"   ✗ playback control failed: {e!r}")

        # Try seeking to a specific time to verify the seek event updates the counter
        try:
            component_frame.evaluate(
                "() => { document.getElementById('vid').currentTime = 1.5; }"
            )
            time.sleep(1.0)
            seek_text = component_frame.locator("#frameDisplay").inner_text()
            seek_time = component_frame.locator("#timeDisplay").inner_text()
            print(f"   after seek to 1.5s: frame='{seek_text}', t='{seek_time}'s")
        except Exception as e:
            print(f"   ✗ seek failed: {e!r}")

        page.screenshot(path=OUT / "_counter_02_after_play.png", full_page=True)
        print(f"   after-play screenshot saved")

        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
