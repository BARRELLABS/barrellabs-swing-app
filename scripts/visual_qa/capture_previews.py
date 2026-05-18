"""
Playwright capture script for the Phase 1 preview pages.

Launches the preview_harness Streamlit app on a local port, navigates
to each preview route at desktop + mobile widths, and saves screenshots.

Output:
    .visual_qa/preview_screenshots/<timestamp>/
        saved_reports_preview-desktop.png
        saved_reports_preview-mobile.png
        swing_report_preview-desktop.png
        swing_report_preview-mobile.png
        meta.json

Usage:
    python3 scripts/visual_qa/capture_previews.py
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

PORT = int(os.environ.get("BL_PREVIEW_PORT", "8765"))
OUT_ROOT = REPO_ROOT / ".visual_qa" / "preview_screenshots"

VIEWPORTS = [
    ("desktop", 1600, 1100),
    ("mobile",  430,  900),
]

PAGES = [
    "saved_reports_preview",
    "swing_report_preview",
]


def _start_streamlit() -> subprocess.Popen:
    env = os.environ.copy()
    cmd = [
        "streamlit", "run",
        str(REPO_ROOT / "scripts" / "visual_qa" / "preview_harness.py"),
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--server.runOnSave", "false",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
    ]
    print(f"[harness] starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        text=True,
    )
    return proc


def _wait_for_streamlit(timeout_s: int = 30) -> bool:
    import urllib.request
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=1)
            if r.status == 200:
                # Wait a touch more so JS finishes hydrating
                time.sleep(1.0)
                return True
        except Exception:
            time.sleep(0.3)
    return False


def _capture():
    from playwright.sync_api import sync_playwright

    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out_dir = OUT_ROOT / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "timestamp": ts,
        "port": PORT,
        "viewports": VIEWPORTS,
        "pages": PAGES,
        "shots": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for page_name in PAGES:
                for vp_label, w, h in VIEWPORTS:
                    print(f"[capture] {page_name} @ {vp_label} ({w}x{h})")
                    context = browser.new_context(
                        viewport={"width": w, "height": h},
                        device_scale_factor=2,
                    )
                    page = context.new_page()
                    url = f"http://localhost:{PORT}/?page={page_name}"
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Streamlit hydrates async — wait for the editorial
                    # issue line marker to appear, then a beat more.
                    try:
                        page.wait_for_selector("text=Volume IV", timeout=15000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)
                    shot = out_dir / f"{page_name}-{vp_label}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    meta["shots"].append({
                        "page": page_name, "viewport": vp_label,
                        "width": w, "height": h,
                        "file": shot.name,
                    })
                    context.close()
        finally:
            browser.close()

    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\n[done] screenshots → {out_dir}")
    return out_dir


def main() -> int:
    proc = _start_streamlit()
    try:
        if not _wait_for_streamlit():
            print("[error] streamlit did not become healthy within timeout")
            try:
                # Drain any pending output to help diagnose
                proc.terminate()
                out, _ = proc.communicate(timeout=5)
                print("--- streamlit stdout/stderr ---")
                print(out[-4000:] if out else "(no output)")
            except Exception:
                pass
            return 1
        out_dir = _capture()
        print(f"[ok] captured into {out_dir.relative_to(REPO_ROOT)}")
        return 0
    finally:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
