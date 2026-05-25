"""Unit tests for the Compare Swings page's pure data helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import compare_swings_page as cmp  # noqa: E402


def _rec(n, score, metrics=None, narr=None, ts="2026-05-12T13:00:00",
         swing_score=None, flagged=None):
    rows = []
    for k, v in (metrics or {}).items():
        row = {"label": k, "sim_pct": v}
        if flagged and k in flagged:
            row["flagged"] = True
        rows.append(row)
    rec = {"swing_number": n, "score": score, "timestamp": ts,
           "metric_table": {"Cat": rows},
           "narratives": [{"title": narr}] if narr else []}
    if swing_score is not None:
        rec["swing_score"] = swing_score
    return rec


class TestScoreOf:
    def test_prefers_swing_score(self):
        assert cmp.score_of({"swing_score": 80, "score": 60}) == 80.0

    def test_falls_back_to_legacy_score(self):
        assert cmp.score_of({"score": 60}) == 60.0

    def test_none_when_absent(self):
        assert cmp.score_of({}) is None

    def test_zero_is_valid(self):
        assert cmp.score_of({"swing_score": 0}) == 0.0


class TestMetricPcts:
    def test_extracts_label_to_pct(self):
        r = _rec(1, 70, {"Hip rotation": 80, "Head drift": 65})
        assert cmp.metric_pcts(r) == {"Hip rotation": 80, "Head drift": 65}

    def test_skips_flagged(self):
        r = _rec(1, 70, {"Hip rotation": 80, "Bad view": 90}, flagged={"Bad view"})
        assert cmp.metric_pcts(r) == {"Hip rotation": 80}

    def test_handles_missing_table(self):
        assert cmp.metric_pcts({}) == {}


class TestCompareMetricRows:
    def test_only_shared_labels_with_signed_delta(self):
        a = _rec(1, 70, {"Hip": 60, "Head": 50, "OnlyA": 99})
        b = _rec(2, 75, {"Hip": 72, "Head": 48, "OnlyB": 10})
        rows = cmp.compare_metric_rows(a, b)
        labels = {r["label"] for r in rows}
        assert labels == {"Hip", "Head"}
        hip = next(r for r in rows if r["label"] == "Hip")
        assert hip["a_pct"] == 60 and hip["b_pct"] == 72 and hip["delta"] == 12

    def test_sorted_by_abs_delta_desc(self):
        a = _rec(1, 70, {"Big": 20, "Small": 50})
        b = _rec(2, 75, {"Big": 60, "Small": 52})
        rows = cmp.compare_metric_rows(a, b)
        assert rows[0]["label"] == "Big"  # |+40| before |+2|


class TestKpiStats:
    def test_basic_rollup(self):
        hist = [_rec(1, 60), _rec(2, 70), _rec(3, 65)]
        k = cmp.kpi_stats(hist)
        assert k["first"] == 60 and k["latest"] == 65 and k["best"] == 70
        assert k["average"] == pytest.approx(65.0) and k["total"] == 3
        assert k["latest_is_pb"] is False

    def test_latest_is_pb(self):
        hist = [_rec(1, 60), _rec(2, 88)]
        assert cmp.kpi_stats(hist)["latest_is_pb"] is True

    def test_empty(self):
        k = cmp.kpi_stats([])
        assert k["total"] == 0 and k["best"] is None


class TestMisc:
    def test_delta_class(self):
        assert cmp.delta_class(5) == "up"
        assert cmp.delta_class(-5) == "down"
        assert cmp.delta_class(0) == "flat"
        assert cmp.delta_class(None) == "flat"

    def test_focus_area(self):
        assert cmp.focus_area(_rec(1, 70, narr="Hip Separation")) == "Hip Separation"
        assert cmp.focus_area(_rec(1, 70)) == "—"

    def test_summary_mentions_improved_and_score_move(self):
        a = _rec(1, 60, {"Hip": 50, "Head": 60})
        b = _rec(2, 72, {"Hip": 70, "Head": 55})
        text = cmp.summary_sentence(a, b, cmp.compare_metric_rows(a, b))
        assert "improved" in text.lower()
        assert "60 → 72" in text
        assert "Hip" in text  # biggest gain

    def test_summary_handles_no_shared_data(self):
        a = _rec(1, 60, {"OnlyA": 50})
        b = _rec(2, 72, {"OnlyB": 70})
        text = cmp.summary_sentence(a, b, cmp.compare_metric_rows(a, b))
        assert text  # non-empty, no crash
