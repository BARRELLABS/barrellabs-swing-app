"""Render the dashboard-style Saved Reports / Sessions page to static HTML.

The real page (saved_reports_dashboard.render_saved_reports_dashboard)
relies on live Streamlit widgets (search box, score/time dropdowns,
Open Report / Download PDF / Delete buttons). For a no-auth visual
preview we stub Streamlit so:

  * st.markdown        -> captured into the page buffer
  * st.columns         -> a flex row; children flow into the buffer
  * st.text_input      -> a styled static input box
  * st.selectbox       -> a styled static dropdown
  * st.button          -> a styled static button
  * st.download_button -> a styled static button
  * Edge masthead/wrapper + global theme -> lightweight stand-ins

It feeds a synthetic saved-swing history (varied scores, MLB comps,
dates, filenames, narratives) so every card state is exercised.

    .venv/bin/python scripts/visual_qa/render_saved_reports_static.py

Writes /tmp/saved_reports_preview.html and auto-opens it.
"""

from __future__ import annotations

import os
import sys
import types
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Page buffer the stubs append HTML into, in render order.
_BUF: list[str] = []


def _make_streamlit_stub() -> types.ModuleType:
    st = types.ModuleType("streamlit")

    class _SS(dict):
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError as e:
                raise AttributeError(k) from e

        def __setattr__(self, k, v):
            self[k] = v

    st.session_state = _SS()

    class _QP(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    st.query_params = _QP()

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    def markdown(s, **kw):
        _BUF.append(str(s))

    def _col_spec_len(spec):
        if isinstance(spec, int):
            return spec
        try:
            return len(spec)
        except TypeError:
            return 1

    def columns(spec, **kw):
        # Render columns as a flex row. Each column is a context
        # manager; markdown emitted inside flows into the buffer in
        # order (good enough for a static visual mock).
        n = _col_spec_len(spec)
        _BUF.append('<div class="srl-mock-row">')
        cols = []
        for _ in range(n):
            cols.append(_Ctx())
        # Close the row at the end of the script (we add a sentinel
        # close after the last use isn't tracked precisely; instead we
        # close immediately since children append between markers).
        _BUF.append('</div>')
        return cols

    def text_input(label, **kw):
        ph = kw.get("placeholder", "")
        _BUF.append(
            f'<div class="srl-mock-field">'
            f'<label>{label}</label>'
            f'<div class="srl-mock-input">{ph or "&nbsp;"}</div></div>'
        )
        return ""

    def selectbox(label, options, **kw):
        first = options[0] if options else ""
        _BUF.append(
            f'<div class="srl-mock-field">'
            f'<label>{label}</label>'
            f'<div class="srl-mock-input srl-mock-select">'
            f'<span>{first}</span><span class="srl-mock-caret">▾</span></div></div>'
        )
        return first

    def button(label, **kw):
        cls = "srl-mock-btn"
        if "Open Report" in label:
            cls += " srl-mock-btn-primary"
        elif "Delete" in label:
            cls += " srl-mock-btn-ghost"
        _BUF.append(f'<button class="{cls}">{label}</button>')
        return False

    def download_button(label, **kw):
        _BUF.append(f'<button class="srl-mock-btn srl-mock-btn-dl">{label}</button>')
        return False

    st.markdown = markdown
    st.columns = columns
    st.text_input = text_input
    st.selectbox = selectbox
    st.button = button
    st.download_button = download_button
    st.container = lambda *a, **k: _Ctx()
    st.expander = lambda *a, **k: _Ctx()
    st.toast = lambda *a, **k: None
    st.caption = lambda *a, **k: _BUF.append(
        f'<div class="srl-mock-caption">{a[0] if a else ""}</div>')
    st.error = lambda *a, **k: None
    st.warning = lambda *a, **k: None
    st.info = lambda *a, **k: None
    st.rerun = lambda *a, **k: None
    st.stop = lambda *a, **k: None
    st.image = lambda *a, **k: None
    st.write = lambda *a, **k: _BUF.append(str(a[0]) if a else "")

    comp_v1 = types.ModuleType("streamlit.components.v1")
    comp_v1.html = lambda *a, **k: None
    comp = types.ModuleType("streamlit.components")
    comp.v1 = comp_v1
    st.components = comp
    sys.modules["streamlit.components"] = comp
    sys.modules["streamlit.components.v1"] = comp_v1
    return st


def _synthetic_history() -> list[dict]:
    """Saved-swing records shaped the way the page reads them:
    reference_name, score, swing_number, narratives[0].title,
    timestamp/date, filename, id.
    """
    rows = [
        (7, 72, "Ronald Acuña Jr.", "Hip Separation",
         "2026-05-18T14:23:00", "front_toss_0518.mp4"),
        (6, 70, "Ronald Acuña Jr.", "Head Stability",
         "2026-05-12T13:05:00", "cage_session_0512.mov"),
        (5, 71, "Mookie Betts", "Lower Body Sequence",
         "2026-05-05T12:20:00", "tee_work_0505.mp4"),
        (4, 69, "Mookie Betts", "Bat Path",
         "2026-04-28T15:55:00", "live_bp_0428.mp4"),
        (3, 64, "Yandy Díaz", "Stride Timing",
         "2026-04-20T14:10:00", "front_toss_0420.mov"),
        (2, 58, "Yandy Díaz", "Load Depth",
         "2026-04-12T17:00:00", "first_upload.mp4"),
    ]
    hist = []
    for num, score, ref, focus, ts, fn in rows:
        hist.append({
            "id": f"sample-{num}",
            "swing_number": num,
            "score": score,
            "reference_name": ref,
            "narratives": [{"title": focus, "paragraphs": []}],
            "timestamp": ts,
            "filename": fn,
            "_record_path": None,
        })
    # The page reverses history (newest first), so provide oldest-first.
    return list(reversed(hist))


def render_to_html(out_path: Path) -> Path:
    st = _make_streamlit_stub()
    sys.modules["streamlit"] = st

    # Lightweight stand-ins for the Edge chrome + heavy deps so the
    # page module imports and runs without a real runtime.
    bl_theme = types.ModuleType("bl_theme")
    bl_theme.inject_global_theme = lambda: None
    sys.modules["bl_theme"] = bl_theme

    bl_edge = types.ModuleType("bl_edge_chrome")
    bl_edge.render_edge_masthead = lambda *a, **k: _BUF.append(
        '<div class="srl-mock-masthead">'
        '<div class="srl-mock-brand">◆ BARRELLABS</div>'
        '<div class="srl-mock-nav">'
        '<span>Dashboard</span><span class="on">Sessions</span>'
        '<span>Compare</span><span>Drills</span><span>Library</span>'
        '</div><div class="srl-mock-chip">LC</div></div>')
    bl_edge.render_edge_page_wrapper_open = lambda *a, **k: _BUF.append(
        '<div class="srl-mock-pagewrap">')
    bl_edge.render_edge_page_wrapper_close = lambda *a, **k: _BUF.append(
        '</div>')
    sys.modules["bl_edge_chrome"] = bl_edge

    ps = types.ModuleType("player_storage")
    _HIST = _synthetic_history()
    ps.load_swing_history = lambda *a, **k: _HIST
    ps.delete_swing_record = lambda *a, **k: None
    sys.modules["player_storage"] = ps

    ent = types.ModuleType("entitlements")
    ent.can_export_pdf = lambda *a, **k: True
    sys.modules["entitlements"] = ent

    subs = types.ModuleType("subscription_storage")
    subs.load_my_plan = lambda *a, **k: {"plan": "pro"}
    sys.modules["subscription_storage"] = subs

    # saved_reports (the legacy module) imports streamlit + bl_theme +
    # player_storage + entitlements + subscription_storage at module
    # top — all stubbed above. Importing it is required because
    # saved_reports_dashboard pulls _filter_history et al from it.
    from saved_reports_dashboard import render_saved_reports_dashboard

    _BUF.clear()
    render_saved_reports_dashboard(
        {"slug": "preview-user", "id": "preview-user"},
        build_pdf_fn=lambda rec: b"%PDF-1.4 stub",
    )

    body = "".join(_BUF)

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saved Reports — Sessions (PREVIEW)</title>
<style>
  html,body{{margin:0;background:#0A0B0E;color:#F4EFE6;
    font-family:'Geist',-apple-system,system-ui,sans-serif;}}
  .srl-preview-note{{max-width:1280px;margin:0 auto;padding:10px 1.4rem 0;
    font-family:'Geist Mono',monospace;font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:rgba(232,193,112,.8);}}
  /* Edge chrome stand-ins */
  .srl-mock-masthead{{display:flex;align-items:center;gap:28px;
    padding:20px 56px;border-bottom:1px solid rgba(244,239,230,.08);
    background:#0A0B0E;}}
  .srl-mock-brand{{font-family:'Geist Mono',monospace;font-size:14px;
    letter-spacing:.22em;color:#F4EFE6;}}
  .srl-mock-nav{{display:flex;gap:22px;flex:1;font-size:13px;
    color:rgba(244,239,230,.55);}}
  .srl-mock-nav .on{{color:#F4EFE6;}}
  .srl-mock-chip{{width:32px;height:32px;border-radius:50%;
    background:rgba(232,193,112,.15);border:1px solid rgba(232,193,112,.3);
    display:flex;align-items:center;justify-content:center;
    font-family:'Instrument Serif',serif;font-style:italic;color:#E8C170;
    font-size:13px;}}
  .srl-mock-pagewrap{{padding-top:4px;}}
  /* Widget stand-ins */
  .srl-mock-row{{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;
    max-width:1280px;margin:0 auto;padding:0 1.4rem .4rem;}}
  .srl-mock-field{{flex:1;min-width:160px;}}
  .srl-mock-field label{{display:block;font-family:'Geist Mono',monospace;
    font-size:10px;letter-spacing:.18em;text-transform:uppercase;
    color:rgba(244,239,230,.55);margin-bottom:6px;}}
  .srl-mock-input{{background:#0F1115;border:1px solid rgba(244,239,230,.16);
    border-radius:14px;padding:.6rem .85rem;font-size:13px;
    color:rgba(244,239,230,.6);display:flex;justify-content:space-between;}}
  .srl-mock-caret{{color:rgba(244,239,230,.4);}}
  .srl-mock-btn{{appearance:none;border:1px solid rgba(244,239,230,.16);
    background:rgba(255,255,255,.045);color:#F4EFE6;border-radius:999px;
    padding:.55rem 1.1rem;font-size:13px;font-weight:500;cursor:default;
    font-family:'Geist',sans-serif;margin:.2rem .35rem .6rem 0;}}
  .srl-mock-btn-primary{{background:#E64530;border-color:rgba(255,255,255,.1);
    font-weight:600;box-shadow:0 8px 20px -10px rgba(230,69,48,.45);}}
  .srl-mock-btn-dl{{background:rgba(255,255,255,.06);}}
  .srl-mock-btn-ghost{{background:transparent;color:rgba(244,239,230,.55);}}
  .srl-mock-caption{{font-size:11px;color:rgba(244,239,230,.4);
    padding:0 1.4rem .4rem;max-width:1280px;margin:0 auto;}}
</style></head><body>
<div class="srl-preview-note">Preview · Sessions / Saved Reports · sample data · widgets shown as static stand-ins</div>
{body}
</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    out = Path(os.environ.get("SAVED_PREVIEW_OUT",
                              "/tmp/saved_reports_preview.html"))
    written = render_to_html(out)
    print(f"Wrote: {written}  ({written.stat().st_size:,} bytes)")
    if os.environ.get("PREVIEW_NO_OPEN") != "1":
        url = f"file://{written.resolve()}"
        print(f"Opening: {url}")
        webbrowser.open(url)
