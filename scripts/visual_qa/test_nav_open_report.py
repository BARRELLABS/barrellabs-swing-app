"""
Deterministic AppTest suite for the user-reported workflow:

  Dashboard  ->  Sessions  ->  Open Report  ->  Edge swing report

Acceptance criteria under test
------------------------------
  C1  Dashboard "Sessions" nav opens the Saved Reports page WITHOUT
      losing session state (the auth-wipe regression).
  C2  Opening a saved swing routes through the DEDICATED swing_report_page
      (NOT the old renderer, NOT the deprecated render_dashboard_v3
      force_record re-skin, NOT a dashboard fall-through).
  C3  render_dashboard_v3(force_record=...) — the function still supports
      the force_record kwarg — renders the forced swing in the Edge
      template, and it is THAT specific swing (not history[-1]).
  C4  app.py boots cleanly inside Streamlit (no import/runtime break).

No browser, no Supabase, no auth automation — Streamlit's official
AppTest drives the REAL shipped functions with the data seams stubbed.

Run:  .venv/bin/python scripts/visual_qa/test_nav_open_report.py
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "scripts" / "visual_qa" / "_nav_harness.py"
APP = REPO_ROOT / "app.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from streamlit.testing.v1 import AppTest

RUN_TIMEOUT = 90  # the Edge template is large; give it room.


# --------------------------------------------------------------------------
# Synthetic data — mirrors the production record shape used by
# scripts/visual_qa/capture.py::_mk_record (metric_table dict-of-lists etc).
# --------------------------------------------------------------------------
def _mk_record(score: float, days_ago: int, ref: str = "mookie_betts",
               sep: float = 42.0) -> Dict[str, Any]:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "score": score,
        "timestamp": ts,
        "reference_name": ref,
        "metric_table": {
            "Rotation": [
                {"label": "Peak hip-shoulder separation",
                 "sim_pct": score - 2, "player_str": f"{sep:g}deg", "ref_str": "44deg"},
                {"label": "Hip rotation at contact",
                 "sim_pct": score, "player_str": "52deg", "ref_str": "54deg"},
            ],
            "Timing": [
                {"label": "Launch to contact ms",
                 "sim_pct": score - 3, "player_str": "184 ms", "ref_str": "175 ms"},
            ],
            "Front Knee": [
                {"label": "Knee re-extension",
                 "sim_pct": score - 8, "player_str": "24deg", "ref_str": "28deg"},
            ],
            "Head": [
                {"label": "Head total drift",
                 "sim_pct": score - 6, "player_str": "0.18", "ref_str": "0.15"},
            ],
        },
        "drill_plan": {
            "hip_rotation": [{"name": "Walking stride hip-leads",
                              "duration": "3 x 6 reps", "target": ">= 42deg",
                              "description": "Stall at foot plant before launching."}],
        },
        "phases_t": {"load_start": 0.04, "foot_plant": 0.50, "launch": 0.71,
                     "contact": 0.80, "peak_rotation": 0.92, "finish": 1.16},
    }


def _history() -> List[Dict[str, Any]]:
    # 8-session climb, all vs mookie_betts (newest last). Index 2 will be
    # swapped to a mike_trout matchup to prove force_record selects it.
    h = [_mk_record(60 + i * 3, days_ago=(7 - i) * 5, sep=32 + i)
         for i in range(8)]
    return h


FAKE_USER = {"name": "Test Player", "slug": "test-player",
             "id": "test-player", "handedness": "RIGHT"}

PASSED: List[str] = []
FAILED: List[str] = []


def _check(name: str, fn) -> None:
    try:
        fn()
        PASSED.append(name)
        print(f"  PASS  {name}")
    except Exception as e:  # noqa: BLE001
        FAILED.append(name)
        print(f"  FAIL  {name}: {e}")
        traceback.print_exc()


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


# --------------------------------------------------------------------------
# C4 — app.py boots inside Streamlit without an uncaught exception.
# --------------------------------------------------------------------------
def test_app_boots():
    at = AppTest.from_file(str(APP))
    at.run(timeout=RUN_TIMEOUT)
    assert at.exception == [], f"app.py raised on boot: {at.exception}"


# --------------------------------------------------------------------------
# C1 — Sessions nav -> saved_reports, session state preserved.
# --------------------------------------------------------------------------
def test_sessions_nav_routes_and_preserves_state():
    at = AppTest.from_file(str(HARNESS))
    at.session_state["_user"] = FAKE_USER
    at.session_state["_hist"] = _history()
    # A stand-in for the Supabase auth token that the OLD hard-navigation
    # bug used to wipe. If the fixed native-button + st.rerun path works,
    # this survives the nav click.
    at.session_state["_authsentinel"] = "TOKEN-123"
    at.run(timeout=RUN_TIMEOUT)
    assert at.exception == [], f"dashboard render raised: {at.exception}"
    assert "V3_IFRAME_RENDERED" in _md(at), "Edge dashboard did not render"

    # Nav consolidation (merge 36f8c12) moved the nav into the editorial
    # masthead (bl_edge_chrome), renaming the keys _v3nav_* -> _ble_nav_*.
    nav = [b for b in at.button if b.key == "_ble_nav_saved_reports"]
    assert nav, f"Sessions nav button missing; keys={[b.key for b in at.button]}"
    nav[0].click()
    at.run(timeout=RUN_TIMEOUT)

    assert at.exception == [], f"raised after Sessions click: {at.exception}"
    assert at.session_state["page"] == "saved_reports", \
        f"page != saved_reports (got {at.session_state.get('page')!r})"
    assert "SAVED_REPORTS_REACHED" in _md(at), "did not reach saved reports page"
    assert at.session_state["_authsentinel"] == "TOKEN-123", \
        "session state was wiped by nav (auth-wipe regression present)"


# --------------------------------------------------------------------------
# C2 / C3 — force_record renders the Edge template for THAT swing.
# --------------------------------------------------------------------------
def _render_capture(force_idx, history):
    at = AppTest.from_file(str(HARNESS))
    at.session_state["_user"] = FAKE_USER
    at.session_state["_hist"] = history
    if force_idx is not None:
        at.session_state["_force_idx"] = force_idx
    at.run(timeout=RUN_TIMEOUT)
    assert at.exception == [], f"render raised: {at.exception}"
    try:
        html = at.session_state["_captured_html"]
    except (KeyError, AttributeError):
        html = ""
    return at, html


def test_default_render_is_edge_template():
    _at, html = _render_capture(None, _history())
    assert len(html) > 5000, f"rendered html too small ({len(html)}B) — not Edge"
    assert "comp-radar" in html, "Edge comp-radar section absent"
    assert "Test Player" in html, "real-data name swap absent (not Edge renderer)"


def test_force_record_renders_that_specific_swing():
    hist = _history()
    # Make a clearly different swing at index 2: a Mike Trout matchup.
    hist[2] = _mk_record(91, days_ago=99, ref="mike_trout", sep=48)

    _at_def, html_default = _render_capture(None, hist)   # latest = idx 7 (Betts)
    _at_for, html_forced = _render_capture(2, hist)       # forced = idx 2 (Trout)

    assert "Betts" in html_default, "default render should reflect history[-1] (Betts)"
    assert "Trout" in html_forced, \
        "forced render did not reflect the Mike Trout swing (force_record ignored)"
    assert html_forced != html_default, \
        "force_record produced identical output to history[-1] (not selecting that swing)"


# --------------------------------------------------------------------------
# C2 — app.py routing structurally sends Open Report to the DEDICATED
# swing_report_page, not the old renderer, not the deprecated
# render_dashboard_v3(force_record=...) re-skin, not a dashboard fall-through.
#
# The nav consolidation / Open-Report rework (merge 36f8c12) replaced the
# old "re-skin the whole dashboard with force_record" behavior with a
# focused swing_report_page. This mirrors the canonical contract locked by
# tests/test_nav_routing_smoke.py::AppRoutingTest.
# --------------------------------------------------------------------------
def test_apppy_routing_structure():
    src = APP.read_text()
    i = src.index("_should_open_report = (")
    # Slice from the guard definition through the dispatch block. The block
    # ends at the next top-level page section ("UPLOAD"); fall back to a
    # generous fixed slice if that marker ever moves.
    end = src.find("# ---------- UPLOAD", i)
    block = src[i:end] if end != -1 else src[i:i + 3200]

    assert "from swing_report_page import render_swing_report_page" in block, \
        "Open Report does not import the dedicated swing_report_page"
    assert "render_swing_report_page(user, saved_record, history=hist)" in block, \
        "Open Report does not route to render_swing_report_page(...)"
    assert "st.stop()" in block, "no st.stop() — risk of dashboard fall-through"

    # The deprecated force_record re-skin and the old renderer must NOT be
    # on the primary open-report path (only ever an except/legacy fallback).
    primary = block.split("except Exception")[0]
    assert "force_record=" not in primary, \
        "deprecated render_dashboard_v3(force_record=...) is on the PRIMARY path"
    assert "render_saved_swing_report" not in primary, \
        "old render_saved_swing_report is on the PRIMARY open-report path"


def main() -> int:
    print("nav / open-report AppTest suite")
    print("=" * 60)
    _check("C4 app.py boots", test_app_boots)
    _check("C1 Sessions nav + state preserved",
           test_sessions_nav_routes_and_preserves_state)
    _check("C3 default render is Edge template",
           test_default_render_is_edge_template)
    _check("C2/C3 force_record selects that swing",
           test_force_record_renders_that_specific_swing)
    _check("C2 app.py routing structure", test_apppy_routing_structure)
    print("=" * 60)
    print(f"PASSED {len(PASSED)}  FAILED {len(FAILED)}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
