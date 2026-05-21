"""Debug what's actually in the iframe + what video URL it's trying to load."""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "validation" / "reports"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1800, "height": 1200})
    page = ctx.new_page()
    page.set_default_timeout(15000)

    # Capture network requests
    requests = []
    page.on("requestfailed", lambda r: requests.append(
        f"FAILED: {r.method} {r.url}  reason={r.failure}"
    ))
    page.on("response", lambda r: (
        requests.append(f"{r.status} {r.request.method} {r.url}")
        if "/static/" in r.url or "video" in r.url.lower() or r.status >= 400
        else None
    ))

    page.goto("http://localhost:8503/")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('section[data-testid="stMain"]', timeout=10000)
    time.sleep(5)

    # Print sidebar swing pick
    sidebar_text = page.locator('section[data-testid="stSidebar"]').inner_text() if page.locator('section[data-testid="stSidebar"]').count() else ""
    print("=== SIDEBAR TEXT (first 500 chars) ===")
    print(sidebar_text[:500])
    print()

    # Print main panel subheader (the swing id)
    subheaders = page.locator("h3").all_inner_texts()
    print(f"=== H3 SUBHEADERS ===")
    for h in subheaders:
        print(f"  - {h}")
    print()

    # Inspect the iframe
    for f in page.frames:
        if f == page.main_frame:
            continue
        try:
            html_snippet = f.evaluate("() => document.documentElement.outerHTML")
        except Exception:
            html_snippet = "(could not read)"
        if "vid" in html_snippet[:5000] or "<video" in html_snippet[:5000]:
            print("=== COMPONENT IFRAME (truncated to 2500 chars) ===")
            print(html_snippet[:2500])
            print()
            # Get the video src
            try:
                src = f.locator("#vid").get_attribute("src")
                print(f"video src attribute: {src!r}")
                # Get the resolved (absolute) URL
                abs_src = f.evaluate(
                    "() => document.getElementById('vid').src"
                )
                print(f"video src (resolved): {abs_src!r}")
                ready = f.evaluate(
                    "() => document.getElementById('vid').readyState"
                )
                err = f.evaluate(
                    "() => { const e = document.getElementById('vid').error; "
                    "return e ? {code: e.code, msg: e.message} : null; }"
                )
                print(f"video readyState: {ready}, error: {err}")
            except Exception as e:
                print(f"could not inspect video element: {e!r}")

    print()
    print("=== NETWORK REQUESTS (static / video / 4xx 5xx) ===")
    for r in requests[-30:]:
        print(f"  {r}")

    browser.close()
