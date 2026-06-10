"""Unit tests for compare_video_view pure builders."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compare_video_view import (
    shared_phase_marks,
    build_compare_video_html,
    _seam_svg,
    watch_cards,
    build_watch_breakdown_html,
)


PA = {"load_start": 0.0, "foot_plant": 0.5, "launch": 0.9, "contact": 1.0, "finish": 1.4}
PB = {"load_start": 0.0, "foot_plant": 0.7, "launch": 1.2, "contact": 1.35, "finish": 1.9}


def test_shared_marks_intersection_and_order():
    marks = shared_phase_marks(PA, PB)
    assert [m["key"] for m in marks] == [
        "load_start", "foot_plant", "launch", "contact", "finish"]
    # evenly spaced fracs 0..1
    assert marks[0]["frac"] == 0.0
    assert marks[-1]["frac"] == 1.0
    assert abs(marks[1]["frac"] - 0.25) < 1e-9
    # per-side seconds preserved
    assert marks[3]["ta"] == 1.0 and marks[3]["tb"] == 1.35


def test_shared_marks_only_common_phases():
    a = {"foot_plant": 0.4, "contact": 0.9}          # 2 shared
    b = {"foot_plant": 0.5, "contact": 1.0, "finish": 1.3}
    marks = shared_phase_marks(a, b)
    assert [m["key"] for m in marks] == ["foot_plant", "contact"]
    assert marks[0]["frac"] == 0.0 and marks[1]["frac"] == 1.0


def test_shared_marks_too_few_returns_empty():
    assert shared_phase_marks({"contact": 1.0}, {"contact": 1.1}) == []
    assert shared_phase_marks({}, {}) == []
    assert shared_phase_marks(None, None) == []


def test_shared_marks_ignores_unparseable():
    a = {"foot_plant": "oops", "contact": 1.0, "finish": 1.4}
    b = {"foot_plant": 0.5, "contact": 1.0, "finish": 1.4}
    marks = shared_phase_marks(a, b)
    assert [m["key"] for m in marks] == ["contact", "finish"]


def test_build_html_empty_on_missing_inputs():
    marks = shared_phase_marks(PA, PB)
    assert build_compare_video_html(None, "u", marks, {}, {}) == ""
    assert build_compare_video_html("u", None, marks, {}, {}) == ""
    assert build_compare_video_html("u", "u", [], {}, {}) == ""
    assert build_compare_video_html("u", "u", marks[:1], {}, {}) == ""


def test_build_html_includes_sources_and_labels():
    marks = shared_phase_marks(PA, PB)
    doc = build_compare_video_html(
        "https://x/a.mov", "https://x/b.mov", marks,
        {"role": "Swing A", "date": "May 1", "score": 58},
        {"role": "Swing B", "date": "Jun 1", "score": 62})
    assert 'src="https://x/a.mov"' in doc
    assert 'src="https://x/b.mov"' in doc
    for label in ("Load", "Foot plant", "Launch", "Contact", "Finish"):
        assert label in doc
    # nudge controls + seam present
    assert "Nudge A" in doc and "Nudge B" in doc
    assert "cvv-seam-svg" in doc


def test_seam_svg_is_static_string_with_stitches():
    svg = _seam_svg(height=120)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # red stitches present
    assert svg.count("#E64530") > 4


# --- plain-language watch breakdown ---------------------------------------
ROWS = [
    {"label": "Re-extension", "a_pct": 27, "b_pct": 60, "delta": 33},          # big up
    {"label": "Hip rotation at contact", "a_pct": 70, "b_pct": 53, "delta": -17},  # down
    {"label": "Total head drift (torso-rel)", "a_pct": 95, "b_pct": 97, "delta": 2},  # held
    {"label": "Some unmapped metric", "a_pct": 10, "b_pct": 90, "delta": 80},   # ignored
]


def test_watch_cards_maps_ranks_and_tags():
    cards = watch_cards(ROWS, limit=3)
    # unmapped metric is dropped; mapped ones ranked by |delta|
    titles = [c["title"] for c in cards]
    assert titles[0] == "Front-leg brace"      # |33|
    assert titles[1] == "Hip rotation"         # |-17|
    assert "Head stability" in titles          # |2|
    assert cards[0]["trend"] == "up" and cards[0]["tag"] == "Sharper"
    assert cards[1]["trend"] == "down" and cards[1]["tag"] == "Slipped"
    # each card carries a phase to scrub to + a watch cue
    assert cards[0]["phase"] == "Contact" and cards[0]["watch"]


def test_watch_cards_dedupes_by_friendly_group():
    rows = [
        {"label": "Head drift Δx (torso-rel)", "a_pct": 90, "b_pct": 80, "delta": -10},
        {"label": "Total head drift (torso-rel)", "a_pct": 95, "b_pct": 99, "delta": 4},
    ]
    cards = watch_cards(rows)
    # both map to "Head stability"; keep the bigger absolute move only
    assert [c["title"] for c in cards] == ["Head stability"]
    assert cards[0]["delta"] == -10


def test_watch_cards_empty_when_nothing_maps():
    assert watch_cards([{"label": "xyz", "a_pct": 1, "b_pct": 2, "delta": 1}]) == []
    assert watch_cards([]) == []


def test_build_watch_breakdown_html():
    assert build_watch_breakdown_html([]) == ""
    doc = build_watch_breakdown_html(watch_cards(ROWS))
    assert "What changed, and where to watch" in doc
    assert "Front-leg brace" in doc and "Look for it at" in doc
