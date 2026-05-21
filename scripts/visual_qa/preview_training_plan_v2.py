"""Standalone Playwright preview of the Training Plan v2 editorial layer.

The authed page can't be screenshot'd live without a Supabase login, so
this harness extracts the just-the-Edge-overlay CSS from
`development_tracker.py:_DT_LOCAL_CSS` and renders the helper functions
(`_build_hero_brand_html`, `_build_data_hero_html`,
`_build_consistency_html`) into a static HTML document the same way
they would compose on the live page. Then Playwright opens it and
screenshots desktop + mobile.

Usage:
    PY=/Users/logancollins/barrellabs-swing-app/.venv/bin/python
    $PY scripts/visual_qa/preview_training_plan_v2.py

Output: /tmp/training_plan_v2_desktop.png + /tmp/training_plan_v2_mobile.png
"""
from __future__ import annotations
import sys
import types
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))


def _streamlit_stub() -> types.ModuleType:
    """Minimum Streamlit stub the dev_tracker module needs at import."""
    stub = types.ModuleType("streamlit")
    stub.session_state = {}

    def _passthrough(*dargs, **dkwargs):
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def inner(fn):
            return fn

        return inner

    def _noop(*a, **k):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    stub.cache_resource = _passthrough
    stub.cache_data = _passthrough
    for name in ("markdown", "write", "error", "warning", "caption",
                 "rerun", "stop", "toast", "success", "info", "image",
                 "code", "header", "subheader", "title", "divider"):
        setattr(stub, name, _noop)
    stub.container = lambda *a, **k: _Ctx()
    stub.columns = lambda n, **k: [_Ctx() for _ in range(
        n if isinstance(n, int) else len(n))]
    stub.expander = lambda *a, **k: _Ctx()
    stub.spinner = lambda *a, **k: _Ctx()
    stub.form = lambda *a, **k: _Ctx()
    stub.form_submit_button = lambda *a, **k: False
    stub.button = lambda *a, **k: False
    stub.checkbox = lambda *a, **k: False
    stub.text_input = lambda *a, **k: ""
    stub.text_area = lambda *a, **k: ""
    stub.number_input = lambda *a, **k: 0
    stub.selectbox = lambda *a, **k: ""
    stub.radio = lambda *a, **k: ""
    stub.download_button = lambda *a, **k: None
    stub.file_uploader = lambda *a, **k: None
    stub.query_params = {}

    _c1 = types.ModuleType("streamlit.components.v1")
    _c1.html = _noop
    _c1.iframe = _noop
    _c0 = types.ModuleType("streamlit.components")
    _c0.v1 = _c1
    stub.components = _c0
    sys.modules["streamlit.components"] = _c0
    sys.modules["streamlit.components.v1"] = _c1
    return stub


def main() -> None:
    sys.modules["streamlit"] = _streamlit_stub()

    # Force-clear any cached import so we pick up our edits.
    for k in ("development_tracker",):
        sys.modules.pop(k, None)

    import development_tracker as dt

    # ---- Fake data: rich enough to exercise every visual branch ----
    saved_swing = {
        "date": "2026-05-19",
        "timestamp": "2026-05-19T18:20:00",
        "picked_slug": "mookie_betts",
        "reference_name": "mookie_betts",
        "drill_plan": {
            "categories": [
                {
                    "priority": 1,
                    "category": "separation",
                    "title": "Hip-Shoulder Separation",
                    "why_it_matters": (
                        "Hip-shoulder separation is the engine of your "
                        "swing. You're separating to ~38°, four degrees "
                        "short of Mookie Betts. Closing that gap is the "
                        "single highest-leverage change available to "
                        "you right now."
                    ),
                    "drills": [
                        {
                            "name": "Wall Tap Drill",
                            "reps": "3 sets of 10",
                            "how": ("Press your back hip into the wall, "
                                    "then sequence shoulders → hands → bat."),
                        },
                        {
                            "name": "Cross-Body Rotation",
                            "reps": "3 sets of 8",
                            "how": "Slow, controlled hip-leads-shoulders reps.",
                        },
                        {
                            "name": "Pause Sequence",
                            "reps": "2 sets of 6",
                            "how": "Pause at peak hip rotation for one second.",
                        },
                    ],
                },
                {
                    "priority": 2,
                    "category": "head_stability",
                    "title": "Quiet the Head",
                    "why_it_matters": (
                        "Head drift adds variance to your contact point. "
                        "Pinning it down stabilises everything downstream."
                    ),
                    "drills": [
                        {
                            "name": "Eye on Tee",
                            "reps": "3 sets of 5",
                            "how": "Keep eyes locked through contact.",
                        },
                    ],
                },
            ],
            "weekly_guide": [
                "Pick 2 drills from PRIORITY 1 — do them every practice session.",
                "Pick 1 drill from PRIORITY 2 — do it 3× per week.",
                ("Re-film and re-run the comparison every 2–3 weeks. The "
                 "goal is your similarity score climbing over time."),
            ],
        },
    }
    gm_state = {"current_streak_days": 12, "longest_streak_days": 18}
    history = [
        {"timestamp": "2026-05-19T18:20:00", "date": "2026-05-19"},
        {"timestamp": "2026-05-17T08:00:00", "date": "2026-05-17"},
        {"timestamp": "2026-05-16T08:00:00", "date": "2026-05-16"},
        {"timestamp": "2026-05-14T08:00:00", "date": "2026-05-14"},
    ]

    metrics = dt._hero_metrics(
        saved_swing=saved_swing,
        gm_state=gm_state,
        total_completed=2,
        total_drills=4,
    )
    hero = dt._build_data_hero_html(metrics, saved_swing["date"])
    cons = dt._build_consistency_html(history, metrics["today_pct"])

    css = dt._DT_LOCAL_CSS
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Training Plan v2 preview</title>
{css}
<style>
body {{ background: #0A0B0E; margin: 0; padding: 40px 56px; }}
</style>
</head>
<body>
<div class="tp-shell bl-page">
{hero}
{cons}
</div>
</body></html>
"""

    out_html = Path("/tmp/training_plan_v2.html")
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(out_html.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        out_desk = Path("/tmp/training_plan_v2_desktop.png")
        page.screenshot(path=str(out_desk), full_page=True)
        print(f"wrote {out_desk}")

        ctx.close()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(out_html.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        out_mob = Path("/tmp/training_plan_v2_mobile.png")
        page.screenshot(path=str(out_mob), full_page=True)
        print(f"wrote {out_mob}")
        b.close()


if __name__ == "__main__":
    main()
