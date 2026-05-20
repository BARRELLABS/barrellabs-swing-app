"""Full-page Training Plan v3.1 preview — hero + level card + stats +
motivation chips + consistency strip + drill cards (with action row)
+ coach notes + re-test reminder.

The live authed Streamlit page can't be screenshot'd without a Supabase
login, so this harness composes a faithful static HTML version of the
authed has-data path by:

  1. Importing development_tracker under a Streamlit stub (so
     `_DT_LOCAL_CSS` is read directly from the module — single source
     of truth).
  2. Calling the same helper functions the live page calls
     (`_hero_metrics`, `_build_data_hero_html`, `_build_consistency_html`)
     with realistic fake data.
  3. Hand-writing the *static* HTML versions of the level card, stat
     strip, motivation chips, drill cards, and action row in the
     EXACT same DOM shape that `_render_level_card` /
     `_render_stat_strip` / the drill loop emit — but with bare-HTML
     standins for the Streamlit widgets (a `<label class="tp-fake-check">`
     for the checkbox, a `<input>` for the reps field). That way the CSS
     overrides in `_DT_LOCAL_CSS` light up correctly without needing a
     live Streamlit instance.

Usage:
    PY=/Users/logancollins/barrellabs-swing-app/.venv/bin/python
    $PY scripts/visual_qa/preview_training_plan_full.py

Output: /tmp/training_plan_full_desktop.png + _mobile.png
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


# ---------- Static HTML stand-ins for live-Streamlit blocks ----------
def _level_card_html() -> str:
    """Same DOM shape as `_render_level_card` emits."""
    return """
<div class="dt-level-card">
  <div class="dt-level-row">
    <div style="flex:1;min-width:0;">
      <div class="dt-level-eyebrow">Current Level</div>
      <div class="dt-level-name">All-Star</div>
      <div class="dt-level-tagline">Locked in</div>
    </div>
    <div class="dt-xp-pill">
      <span class="dt-xp-num">1,100</span>&nbsp;XP&nbsp;Total
    </div>
  </div>
  <div class="dt-xp-bar-wrap">
    <div class="dt-xp-bar"><div class="dt-xp-bar-fill" style="width:6%"></div></div>
    <div class="dt-xp-bar-foot">
      <span>Level Progress · 6%</span>
      <span class="dt-xp-foot-next">1,400 XP to MVP</span>
    </div>
  </div>
</div>
"""


def _stat_strip_html() -> str:
    return """
<div class="dt-stat-strip">
  <div class="dt-stat-pod">
    <div class="dt-stat-pod-num is-red">0</div>
    <div class="dt-stat-pod-label">Day Streak</div>
  </div>
  <div class="dt-stat-pod">
    <div class="dt-stat-pod-num">1</div>
    <div class="dt-stat-pod-label">Longest Streak</div>
  </div>
  <div class="dt-stat-pod">
    <div class="dt-stat-pod-num">7</div>
    <div class="dt-stat-pod-label">Swings Logged</div>
  </div>
  <div class="dt-stat-pod">
    <div class="dt-stat-pod-num">0</div>
    <div class="dt-stat-pod-label">Drills Done</div>
  </div>
  <div class="dt-stat-pod">
    <div class="dt-stat-pod-num">81</div>
    <div class="dt-stat-pod-label">Best Score</div>
  </div>
</div>
"""


def _motivation_strip_html() -> str:
    return """
<div class="dt-motivate-strip">
  <div class="dt-motivate-chip is-red">1 drill away from unlocking First Reps.</div>
  <div class="dt-motivate-chip">6 days until your Silver Streak Badge.</div>
  <div class="dt-motivate-chip">Only 1,400 XP until MVP.</div>
</div>
"""


def _category_header_html(priority: int, title: str, n_drills: int) -> str:
    return f"""
<div class="dt-cat-header">
  <span class="dt-cat-priority-pill">Priority {priority}</span>
  <span class="dt-cat-title">{title}</span>
  <span class="dt-cat-count">{n_drills} DRILL{'S' if n_drills != 1 else ''}</span>
</div>
"""


def _coach_note_html(body: str) -> str:
    return f"""
<div class="dt-coach">
  <div class="dt-coach-eyebrow">Coach Notes</div>
  <div class="dt-coach-body">{body}</div>
</div>
"""


def _drill_card_html(*, num: str, name: str, role: str, role_cls: str,
                     reps: str, how: str, done: bool, mastery: int = 0) -> str:
    status = "✓ COMPLETE" if done else "○ PENDING"
    done_cls = "is-done" if done else ""
    role_chip = f'<span class="dt-role {role_cls}">{role}</span>'
    mastery_chip = (f'<span class="tp-mastery">Mastered {mastery}×</span>'
                    if mastery >= 3 else '')
    reps_chip = f'<span class="dt-drill-reps">SUGGESTED · {reps}</span>'
    how_html = f'<div class="dt-drill-how">{how}</div>'
    card = f"""
<div class="dt-drill {done_cls}">
  <div class="dt-drill-row">
    <div class="dt-drill-num">{num}</div>
    <div class="dt-drill-meta">
      <div class="dt-drill-name">{name}{role_chip}{mastery_chip}</div>
      {reps_chip}
      {how_html}
    </div>
    <div class="dt-drill-status-pill">{status}</div>
  </div>
</div>
"""
    # Static action row mimicking the Streamlit checkbox + text input.
    # We hand-roll the bare DOM the CSS targets so the preview looks
    # the same as the live page.
    reps_value = "3×10" if done else ""
    check_attr = "checked" if done else ""
    actions = f"""
<div class="dt-actions-wrap">
  <div style="display:grid;grid-template-columns:1fr 2fr;gap:18px;align-items:end;">
    <div data-testid="stCheckbox">
      <label>
        <input type="checkbox" {check_attr} style="display:none;">
        <div data-baseweb="checkbox" {('aria-checked="true"' if done else '')}>
          <div style="display:inline-block;vertical-align:middle;"></div>
        </div>
        <span style="margin-left:8px;vertical-align:middle;">Mark done</span>
      </label>
    </div>
    <div data-testid="stTextInput">
      <label>Reps completed</label>
      <div data-baseweb="input">
        <input type="text" placeholder="e.g. 4×10" value="{reps_value}">
      </div>
    </div>
  </div>
</div>
"""
    return card + actions


def _retest_html() -> str:
    return """
<div class="dt-retest">
  <div class="dt-retest-icon">↻</div>
  <div>
    <div class="dt-retest-eyebrow">Re-Test Reminder</div>
    <div class="dt-retest-title">When to upload your next swing</div>
    <ul class="dt-retest-list">
      <li>Pick 2 drills from PRIORITY 1 — do them every practice session.</li>
      <li>Pick 1 drill from PRIORITY 2 — do it 3× per week.</li>
      <li>Re-film and re-run the comparison every 2–3 weeks. The goal is your similarity score climbing over time.</li>
    </ul>
  </div>
</div>
"""


def _progress_card_html() -> str:
    """Static stand-in for `_render_progress_card`."""
    circumference = 2 * 3.14159 * 70
    dash_offset = circumference * (1 - 0.25)
    return f"""
<div class="dt-progress-card">
  <div class="dt-ring">
    <svg viewBox="0 0 160 160">
      <circle class="dt-ring-track" cx="80" cy="80" r="70"></circle>
      <circle class="dt-ring-fill"  cx="80" cy="80" r="70"
              stroke-dasharray="{circumference:.2f}"
              stroke-dashoffset="{dash_offset:.2f}"></circle>
    </svg>
    <div class="dt-ring-center">
      <div><span class="dt-ring-pct">25</span><span class="dt-ring-pct-sym">%</span></div>
      <div class="dt-ring-tag">Warming Up</div>
    </div>
  </div>
  <div>
    <div class="dt-progress-meta-eyebrow">Session Progress</div>
    <div class="dt-progress-meta-title">Training plan for Mario Ricard</div>
    <div class="dt-progress-meta-line">
      Built from your latest report on <strong>May 16, 2026</strong>.
      Check off drills as you complete them — progress saves automatically.
    </div>
    <div class="dt-stat-row">
      <div class="dt-stat-item">
        <div class="dt-stat-num is-red">1</div>
        <div class="dt-stat-label">Completed</div>
      </div>
      <div class="dt-stat-item">
        <div class="dt-stat-num">3</div>
        <div class="dt-stat-label">Remaining</div>
      </div>
      <div class="dt-stat-item">
        <div class="dt-stat-num">4</div>
        <div class="dt-stat-label">Total Drills</div>
      </div>
    </div>
  </div>
</div>
"""


def main() -> None:
    sys.modules["streamlit"] = _streamlit_stub()
    sys.modules.pop("development_tracker", None)
    import development_tracker as dt

    # ---- Realistic mock data ----
    saved_swing = {
        "date": "May 16, 2026",
        "timestamp": "2026-05-16T18:20:00",
        "picked_slug": "mike_trout",
        "reference_name": "mike_trout",
        "drill_plan": {
            "categories": [
                {
                    "priority": 1,
                    "title": "Sharpen Timing & Quickness",
                    "drills": [
                        {"name": "Short-Toss Quick Hands", "reps": "3 sets of 10",
                         "how": "Partner soft-tosses from 8–10 feet away. Focus on the shortest, most direct path from load to contact. No wasted motion."},
                        {"name": "Tennis Ball Reactions", "reps": "3 sets of 10",
                         "how": "Partner randomly tosses tennis balls (different speeds, small intentional pauses). Forces you to read and react rather than time a rhythm."},
                        {"name": "One-Hand Top-Hand Tee", "reps": "3 sets of 8",
                         "how": "Take swings off a tee using only your top (back) hand. Forces a compact, quick path — no looping or dragging."},
                    ],
                },
                {
                    "priority": 2,
                    "title": "Quiet the Head",
                    "drills": [
                        {"name": "Eye on Tee", "reps": "3 sets of 5",
                         "how": "Keep eyes locked through contact."},
                    ],
                },
            ],
            "weekly_guide": [
                "Pick 2 drills from PRIORITY 1 — do them every practice session.",
                "Pick 1 drill from PRIORITY 2 — do it 3× per week.",
                "Re-film and re-run the comparison every 2–3 weeks. The goal is your similarity score climbing over time.",
            ],
        },
    }
    gm_state = {"current_streak_days": 0, "longest_streak_days": 1}
    history = [
        {"timestamp": "2026-05-16T18:20:00", "date": "2026-05-16"},
        {"timestamp": "2026-05-13T08:00:00", "date": "2026-05-13"},
    ]

    metrics = dt._hero_metrics(
        saved_swing=saved_swing,
        gm_state=gm_state,
        total_completed=1,
        total_drills=4,
    )
    hero = dt._build_data_hero_html(metrics, saved_swing["date"])
    cons = dt._build_consistency_html(history, metrics["today_pct"])
    css = dt._DT_LOCAL_CSS

    # ---- Compose the full page body in the same order the live page renders ----
    coach_note = (
        "A long, slow swing arrives late and leaves you guessing. Quick "
        "hands and a compact path let you wait longer on the pitch and "
        "still get the barrel there on time."
    )

    body = (
        hero
        + cons
        + _level_card_html()
        + _stat_strip_html()
        + _motivation_strip_html()
        + _progress_card_html()
        + _category_header_html(1, "Sharpen Timing & Quickness", 3)
        + _coach_note_html(coach_note)
        + _drill_card_html(
            num="01", name="Short-Toss Quick Hands",
            role="PRIMARY", role_cls="is-primary",
            reps="3 sets of 10",
            how="Partner soft-tosses from 8–10 feet away. Focus on the shortest, most direct path from load to contact. No wasted motion.",
            done=True, mastery=4,
        )
        + _drill_card_html(
            num="02", name="Tennis Ball Reactions",
            role="SUPPORTING", role_cls="is-supporting",
            reps="3 sets of 10",
            how="Partner randomly tosses tennis balls (different speeds, small intentional pauses). Forces you to read and react rather than time a rhythm.",
            done=False,
        )
        + _drill_card_html(
            num="03", name="One-Hand Top-Hand Tee",
            role="SUPPORTING", role_cls="is-supporting",
            reps="3 sets of 8",
            how="Take swings off a tee using only your top (back) hand. Forces a compact, quick path — no looping or dragging.",
            done=False,
        )
        + _category_header_html(2, "Quiet the Head", 1)
        + _coach_note_html(
            "Head drift adds variance to your contact point. Pinning it "
            "down stabilises everything downstream."
        )
        + _drill_card_html(
            num="04", name="Eye on Tee",
            role="CHALLENGE", role_cls="is-challenge",
            reps="3 sets of 5",
            how="Keep eyes locked through contact.",
            done=False,
        )
        + _retest_html()
    )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Training Plan v3.1 full preview</title>
{css}
<style>
body {{ background: #0A0B0E; margin: 0; padding: 40px 56px; }}
</style>
</head>
<body>
<div class="tp-shell bl-page">
{body}
</div>
</body></html>
"""
    out_html = Path("/tmp/training_plan_full.html")
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(out_html.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        out_desk = Path("/tmp/training_plan_full_desktop.png")
        page.screenshot(path=str(out_desk), full_page=True)
        print(f"wrote {out_desk}")

        ctx.close()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(out_html.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        out_mob = Path("/tmp/training_plan_full_mobile.png")
        page.screenshot(path=str(out_mob), full_page=True)
        print(f"wrote {out_mob}")
        b.close()


if __name__ == "__main__":
    main()
