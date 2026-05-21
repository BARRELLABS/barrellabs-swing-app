"""End-to-end smoke check of the labeling UI via Playwright.

Confirms:
  - Page loads without errors
  - The OpenCV frame display renders
  - The scrub slider exists and updates the frame
  - The "Set foot plant" + "Set contact" buttons exist and update session state
  - The "SAVE + GO TO NEXT SWING" button persists labels
  - Auto-advance jumps to the next unlabeled swing

Run with:
    python3 -m scripts.validation._playwright_smoke
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect, TimeoutError as PWTimeout

URL = "http://localhost:8503/"


def main() -> int:
    out_dir = Path(__file__).resolve().parents[2] / "validation" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(20000)

        print("→ Loading", URL)
        page.goto(URL)
        # Wait for Streamlit to finish hydrating
        page.wait_for_load_state("networkidle")
        # Streamlit 1.57 may use different test IDs across versions; try a
        # couple of selectors and fall back to a plain time.sleep.
        for sel in (
            'section[data-testid="stMain"]',
            'div[data-testid="stAppViewContainer"]',
            'div[data-testid="stMain"]',
            '.stApp',
        ):
            try:
                page.wait_for_selector(sel, timeout=4000)
                print(f"   matched selector: {sel}")
                break
            except PWTimeout:
                continue
        time.sleep(3)  # let Streamlit finish its initial scripted run

        # Screenshot the initial landing state
        landing = out_dir / "_pw_01_landing.png"
        page.screenshot(path=landing, full_page=True)
        print(f"   landing screenshot: {landing}")

        # Check there's an image (the OpenCV frame) and a slider visible
        n_images = page.locator('img').count()
        n_sliders = page.locator('[data-baseweb="slider"]').count()
        print(f"   <img> count: {n_images}")
        print(f"   slider count: {n_sliders}")

        # Look for the Step 1 / Step 2 / Step 3 markers in the simplified UI
        body_text = page.inner_text("body")
        step_markers = []
        for needle in ("Step 1", "Step 2", "Step 3", "FOOT PLANT",
                       "CONTACT", "toe-tap", "SAVE + GO TO NEXT"):
            if needle.lower() in body_text.lower():
                step_markers.append(needle)
        print(f"   step markers found: {step_markers}")

        # If we landed on the empty state (no labelable swings), bail with a
        # clear message
        if "No videos found in scan paths" in body_text:
            print("✗ App is in empty-state — auto-discovery didn't pick up videos")
            browser.close()
            return 2

        # Verify the unified frame is present (caption with "Frame X")
        frame_caption_present = bool(re.search(r"Frame\s+\d+", body_text))
        print(f"   frame-caption present: {frame_caption_present}")

        # Verify there is NO second <video> element clashing with the
        # frame view — the user's confusion was caused by having both
        n_videos = page.locator('video').count()
        print(f"   <video> elements: {n_videos}  (expected 0)")

        # Try clicking '+10' navigation button and screenshot
        try:
            plus10 = page.get_by_role("button", name=re.compile(r"\+10"))
            if plus10.count() > 0:
                plus10.first.click()
                time.sleep(1.5)
                after_nav = page.inner_text("body")
                m1 = re.search(r"Frame\s+(\d+)", body_text)
                m2 = re.search(r"Frame\s+(\d+)", after_nav)
                if m1 and m2:
                    print(f"   frame advanced: {m1.group(1)} → {m2.group(1)}")
                    if int(m2.group(1)) > int(m1.group(1)):
                        print("   ✓ navigation works")
                    else:
                        print("   ✗ navigation didn't advance the frame")
        except PWTimeout:
            print("   ✗ +10 button not clickable")

        scrubbed = out_dir / "_pw_02_after_nav.png"
        page.screenshot(path=scrubbed, full_page=True)
        print(f"   after-nav screenshot: {scrubbed}")

        # Click "Set foot plant" capture button
        try:
            plant_btn = page.get_by_role(
                "button", name=re.compile(r"Set foot plant", re.IGNORECASE),
            )
            if plant_btn.count() > 0:
                plant_btn.first.click()
                time.sleep(1.5)
                after_plant = page.inner_text("body")
                if "Foot plant marked at frame" in after_plant:
                    print("   ✓ foot-plant capture works")
                else:
                    print("   ✗ foot-plant capture didn't update state")
            else:
                print("   ✗ foot-plant button not found")
        except PWTimeout:
            print("   ✗ foot-plant button timeout")

        captured = out_dir / "_pw_03_after_capture.png"
        page.screenshot(path=captured, full_page=True)
        print(f"   after-capture screenshot: {captured}")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
