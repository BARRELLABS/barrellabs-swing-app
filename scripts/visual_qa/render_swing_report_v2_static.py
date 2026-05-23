"""Render the LIVE swing report renderer (`swing_report_v2.py`) to a
standalone HTML file for visual QA of the editorial re-skin.

Unlike `render_swing_report_static.py` (which renders the *preview* module),
this harness drives the real production renderer `render_swing_report_v2()`.
Streamlit is stubbed so that `st.markdown(html, unsafe_allow_html=True)`
CAPTURES every HTML chunk into a list; all other `st.*` calls are no-ops or
context managers. The captured chunks are concatenated and wrapped in a
minimal HTML page on the ink background.

    .venv/bin/python scripts/visual_qa/render_swing_report_v2_static.py

Writes to /tmp/v2_report_editorial.html (override via V2_OUT env var).
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

# Make the project root importable regardless of where this script runs from.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# Module-level capture list so the stubbed st.markdown can append to it.
CAPTURED: list[str] = []


def _install_streamlit_stub() -> None:
    """Stub `streamlit` BEFORE importing the renderer chain. st.markdown
    captures its first positional arg into CAPTURED; everything else is a
    no-op or a context manager."""
    fake_st = types.ModuleType("streamlit")
    fake_st.session_state = {}

    def _noop(*a, **kw):
        return None

    def _ctx(*a, **kw):
        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False
        return _C()

    def _markdown(html_blob="", *a, **kw):
        # Capture every HTML chunk emitted by the renderer / _md wrapper.
        if isinstance(html_blob, str) and html_blob.strip():
            CAPTURED.append(html_blob)
        return None

    fake_st.markdown = _markdown
    fake_st.write = _noop
    fake_st.image = _noop
    fake_st.error = _noop
    fake_st.warning = _noop
    fake_st.info = _noop
    fake_st.success = _noop
    fake_st.caption = _noop
    fake_st.divider = _noop
    fake_st.expander = _ctx
    fake_st.container = _ctx
    fake_st.columns = lambda n, **kw: [
        _ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    fake_st.tabs = lambda labels, **kw: [_ctx() for _ in labels]
    fake_st.button = lambda *a, **kw: False
    fake_st.spinner = _ctx
    fake_st.empty = _ctx

    fake_components_v1 = types.ModuleType("streamlit.components.v1")
    fake_components_v1.html = _noop
    fake_components = types.ModuleType("streamlit.components")
    fake_components.v1 = fake_components_v1
    fake_st.components = fake_components

    sys.modules["streamlit"] = fake_st
    sys.modules["streamlit.components"] = fake_components
    sys.modules["streamlit.components.v1"] = fake_components_v1


def render_to_html(out_path: Path) -> Path:
    _install_streamlit_stub()

    # Import sample fixtures from the preview module and the LIVE renderer.
    from swing_report_dashboard_preview import (  # noqa: E402
        SAMPLE_RECORD, SAMPLE_HISTORY,
    )
    from swing_report_v2 import render_swing_report_v2  # noqa: E402

    CAPTURED.clear()
    render_swing_report_v2(
        SAMPLE_RECORD,
        history=SAMPLE_HISTORY,
        show_diagnostics=True,
    )

    body = "\n".join(CAPTURED)

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Swing Report v2 — EDITORIAL re-skin QA</title>
</head>
<body style="background:#0A0B0E; margin:0; padding:24px; color:#F4EFE6; \
font-family:'Geist',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;">
{body}
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    out = Path(os.environ.get("V2_OUT", "/tmp/v2_report_editorial.html"))
    written = render_to_html(out)
    size = written.stat().st_size
    print(f"Captured {len(CAPTURED)} HTML chunk(s).")
    print(f"Wrote: {written}  ({size:,} bytes)")
