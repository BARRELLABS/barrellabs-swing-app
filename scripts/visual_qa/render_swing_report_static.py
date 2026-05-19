"""Render the Dashboard-style Swing Report PREVIEW to a standalone HTML file.

Why this exists: the report is data-gated behind Supabase auth — there's
no URL-only preview route that bypasses login. When you want to *see* the
new dashboard-style polish without spinning up the app + login + upload
flow, run this script. It builds a synthetic record that exercises every
section and stitches the HTML by calling `build_dashboard_preview_html()`
in `swing_report_dashboard_preview.py`. Streamlit is stubbed so module
imports don't pull a real runtime.

    .venv/bin/python scripts/visual_qa/render_swing_report_static.py

Writes to /tmp/swing_report_preview.html (override via PREVIEW_OUT env var).
By default also auto-opens the HTML in the user's default browser.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

# Make the project root importable regardless of where this script runs from.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def render_to_html(out_path: Path) -> Path:
    # --- stub Streamlit BEFORE importing the renderer chain so the
    # module-level `import streamlit as st` doesn't reach for a real
    # runtime. ----------------------------------------------------------
    import types

    fake_st = types.ModuleType("streamlit")
    fake_st.session_state = {}

    def _noop(*a, **kw): return None
    def _ctx(*a, **kw):
        class _C:
            def __enter__(self): return self
            def __exit__(self, *e): return False
        return _C()

    fake_st.markdown = _noop
    fake_st.write = _noop
    fake_st.image = _noop
    fake_st.error = _noop
    fake_st.warning = _noop
    fake_st.info = _noop
    fake_st.expander = _ctx
    fake_st.columns = lambda n, **kw: [_ctx() for _ in range(
        n if isinstance(n, int) else len(n))]
    fake_st.container = _ctx
    fake_components_v1 = types.ModuleType("streamlit.components.v1")
    fake_components_v1.html = _noop
    fake_components = types.ModuleType("streamlit.components")
    fake_components.v1 = fake_components_v1
    fake_st.components = fake_components
    sys.modules["streamlit"] = fake_st
    sys.modules["streamlit.components"] = fake_components
    sys.modules["streamlit.components.v1"] = fake_components_v1

    # Now we can safely import the preview renderer.
    from swing_report_dashboard_preview import (  # noqa: E402
        SAMPLE_RECORD, SAMPLE_HISTORY, build_dashboard_preview_html,
    )

    body = build_dashboard_preview_html(
        SAMPLE_RECORD,
        history=SAMPLE_HISTORY,
        is_sample=True,
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard Swing Report — PREVIEW</title>
  <style>
    html, body {{
      margin: 0; padding: 0;
      background: #0A0B0E;
      color: #F4EFE6;
      font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    out = Path(os.environ.get("PREVIEW_OUT", "/tmp/swing_report_preview.html"))
    written = render_to_html(out)
    size = written.stat().st_size
    print(f"Wrote: {written}  ({size:,} bytes)")
    if os.environ.get("PREVIEW_NO_OPEN") != "1":
        url = f"file://{written.resolve()}"
        print(f"Opening: {url}")
        webbrowser.open(url)
