"""Reproduce the LIVE 3-chunk report render (NOT the one-blob static path).

The live app renders the report via render_swing_report_dashboard_preview(),
which emits multiple separate st.html() calls. Streamlit places each as a
sibling block in the DOM. This harness stubs Streamlit, captures every st.html
payload in order, and stitches them as siblings — exactly how the browser sees
them live — so we can screenshot the Compare + Next Session sections and confirm
they're styled (the :root-token + .srd-frame fix) instead of falling back to
broken defaults.

    .venv/bin/python scripts/visual_qa/render_report_live_chunks.py
Writes /tmp/report_live_chunks.html
"""
from __future__ import annotations
import sys, types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

chunks: list[str] = []

fake_st = types.ModuleType("streamlit")
fake_st.session_state = {}

def _noop(*a, **kw): return None
class _C:
    def __enter__(self): return self
    def __exit__(self, *e): return False
def _ctx(*a, **kw): return _C()

fake_st.markdown = _noop
fake_st.write = _noop
fake_st.image = _noop
fake_st.error = _noop
fake_st.warning = _noop
fake_st.info = _noop
fake_st.caption = _noop
fake_st.expander = _ctx
fake_st.container = _ctx
fake_st.columns = lambda n, **kw: [_ctx() for _ in range(n if isinstance(n, int) else len(n))]
fake_st.html = lambda h="", **kw: chunks.append(str(h))
def _selectbox(label, options=None, index=0, **kw):
    opts = options or []
    return opts[index] if opts else None
fake_st.selectbox = _selectbox

fc1 = types.ModuleType("streamlit.components.v1"); fc1.html = _noop
fc = types.ModuleType("streamlit.components"); fc.v1 = fc1
fake_st.components = fc
sys.modules["streamlit"] = fake_st
sys.modules["streamlit.components"] = fc
sys.modules["streamlit.components.v1"] = fc1

from swing_report_dashboard_preview import (  # noqa: E402
    SAMPLE_RECORD, SAMPLE_HISTORY, render_swing_report_dashboard_preview,
)

render_swing_report_dashboard_preview(
    SAMPLE_RECORD, SAMPLE_HISTORY, is_sample=True, is_preview=False,
)

# Stitch as SIBLINGS inside a dark page (the Edge theme bg behind the report),
# each chunk in its own block exactly like Streamlit's stHtml containers.
page = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Report LIVE chunks</title>"
    "<style>body{margin:0;background:#0A0B0E;}"
    ".stHtml{display:block;}</style></head><body>"
    + "".join(f"<div class='stHtml'>{c}</div>" for c in chunks)
    + "</body></html>"
)
out = Path("/tmp/report_live_chunks.html")
out.write_text(page, encoding="utf-8")
print(f"chunks captured: {len(chunks)}")
print(f"wrote {out} ({len(page):,} bytes)")
