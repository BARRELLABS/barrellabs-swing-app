"""
Regression test: rendered preview pages must NOT contain literal HTML
markup as visible text.

This is a LIVE Playwright test that boots the preview harness Streamlit
app and asserts no `<div class=`, `<span class=`, etc. leak into the
rendered DOM text. Catches markdown-code-block escapes (the bug that
broke Phase 1) before they reach the user.

Run from repo root (requires streamlit + playwright + chromium):
    python3 -m unittest tests.test_preview_html_leaks -v

Skipped automatically when streamlit / playwright aren't installed or
the harness can't bind to a free port.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Leak needles — any of these appearing in visible page text means
# Streamlit escaped our HTML or CSS instead of rendering it.
LEAK_NEEDLES = [
    "<div class=",
    "<span class=",
    "<section class=",
    "<header class=",
    "<h3 class=",
    "<p class=",
    "</div>",
    "</span>",
    "</section>",
    # CSS injection leaks — these mean a st.markdown() call that
    # rendered our CSS tokens forgot to pass unsafe_allow_html=True.
    "<link rel=",
    "<style>",
    "</style>",
    ":root {",
]

PAGES_TO_CHECK = [
    "saved_reports_preview",
    "swing_report_preview",
]

PORT = 8771  # different from capture script's port to avoid clashes


def _streamlit_available() -> bool:
    try:
        subprocess.run(
            ["streamlit", "--version"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_streamlit_available(), "streamlit not on PATH")
@unittest.skipUnless(_playwright_available(), "playwright not installed")
class PreviewHtmlLeakTest(unittest.TestCase):
    """End-to-end leak detection on the live preview pages."""

    @classmethod
    def setUpClass(cls):
        # Boot the preview harness in the background.
        cls._proc = subprocess.Popen(
            [
                "streamlit", "run",
                str(REPO_ROOT / "scripts" / "visual_qa" / "preview_harness.py"),
                "--server.port", str(PORT),
                "--server.headless", "true",
                "--server.runOnSave", "false",
                "--browser.gatherUsageStats", "false",
                "--server.fileWatcherType", "none",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            text=True,
        )
        # Wait until healthy.
        import urllib.request
        deadline = time.time() + 30
        cls._healthy = False
        while time.time() < deadline:
            try:
                r = urllib.request.urlopen(
                    f"http://localhost:{PORT}/_stcore/health", timeout=1,
                )
                if r.status == 200:
                    cls._healthy = True
                    break
            except Exception:
                time.sleep(0.3)
        if not cls._healthy:
            cls._teardown_proc()
            raise unittest.SkipTest(
                f"Streamlit harness did not become healthy on port {PORT}"
            )

    @classmethod
    def tearDownClass(cls):
        cls._teardown_proc()

    @classmethod
    def _teardown_proc(cls):
        if not hasattr(cls, "_proc") or cls._proc is None:
            return
        try:
            cls._proc.send_signal(signal.SIGTERM)
            cls._proc.wait(timeout=5)
        except Exception:
            try:
                cls._proc.kill()
            except Exception:
                pass

    def _check_page(self, page_name: str):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1600, "height": 1100},
                device_scale_factor=1,
            )
            pg = ctx.new_page()
            pg.goto(
                f"http://localhost:{PORT}/?page={page_name}",
                wait_until="domcontentloaded", timeout=30000,
            )
            try:
                pg.wait_for_selector("text=Volume IV", timeout=15000)
            except Exception:
                pass
            pg.wait_for_timeout(2500)
            visible_text = pg.evaluate("document.body.innerText")
            ctx.close()
            browser.close()

        # Assert NO leak needle appears in visible text
        leaks = []
        for needle in LEAK_NEEDLES:
            if needle in visible_text:
                idx = visible_text.find(needle)
                ctx = visible_text[max(0, idx - 80):idx + 200]
                leaks.append((needle, ctx))

        if leaks:
            msg = [f"\n❌ {page_name}: HTML leaked into visible text:"]
            for needle, ctx in leaks[:3]:
                msg.append(f"  needle={needle!r}")
                msg.append(f"  context: ...{ctx!r}...")
            self.fail("\n".join(msg))

    def test_saved_reports_preview_no_html_leak(self):
        self._check_page("saved_reports_preview")

    def test_swing_report_preview_no_html_leak(self):
        self._check_page("swing_report_preview")


if __name__ == "__main__":
    unittest.main(verbosity=2)
