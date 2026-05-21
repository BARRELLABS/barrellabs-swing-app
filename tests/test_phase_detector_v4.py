"""
Unit tests for phase_detector_v4.py — the toe-tap-aware shadow detector.

Tests verify that:
  - The ranking function prefers contacts straddling rotation_onset
  - foot_plant_v4 differs from foot_plant_v3 on the canonical toe-tap case
  - load_start / launch are re-derived consistently with the new anchor
  - Fallback fires when no candidates exist
  - All-or-nothing: v4 never mutates the v3 phases dict it's given
  - Feature flag respects the same truthy set as PHASE_DEBUG_V1
  - The diff_from_v3 metadata is correct
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import phase_debug          # noqa: E402
import phase_detector_v4    # noqa: E402

# Reuse the synthetic toe-tap fixture from the Phase 1 tests
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from test_phase_debug import (  # noqa: E402
    _make_fa_y_toe_tap, _make_fa_y_standard_stride, _smooth,
)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_is_enabled_truthy(self):
        for v in ("1", "true", "TRUE", "yes", "Yes", "on", "ON"):
            assert phase_detector_v4.is_enabled({"DETECTOR_V4": v}) is True

    def test_is_enabled_falsy(self):
        for v in ("", "0", "false", "no", "off"):
            assert phase_detector_v4.is_enabled({"DETECTOR_V4": v}) is False

    def test_is_enabled_missing(self):
        assert phase_detector_v4.is_enabled({}) is False


# ---------------------------------------------------------------------------
# score_candidate_as_final_plant
# ---------------------------------------------------------------------------


def _make_candidate(start_frame, end_frame, *, duration_ms=None,
                    min_visibility=0.95, mean_y=500.0, mean_abs_vel=3.0):
    if duration_ms is None:
        # Assume 60 fps for synthetic fixtures
        duration_ms = (end_frame - start_frame + 1) * 1000.0 / 60.0
    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "duration_ms": duration_ms,
        "mean_y": mean_y,
        "mean_abs_vel": mean_abs_vel,
        "min_visibility": min_visibility,
    }


class TestScoreCandidateAsFinalPlant:
    def test_straddling_rotation_onset_scores_highest(self):
        # foot_plant=120, contact=140 → 333ms (in [80, 350] range)
        c = _make_candidate(start_frame=120, end_frame=140)
        score, reasons = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=140, fps=60.0,
        )
        # 1.00 (straddle) + 0.30 (in-range) + 0.20 (long) + 0.15 (vis) ≈ 1.65
        assert score >= 1.55, f"score={score} reasons={reasons}"
        assert any("straddles" in r for r in reasons)

    def test_ends_just_before_rot_onset(self):
        # Candidate ends 5 frames before rot_onset (83ms — mid bucket).
        # contact=145 → 750ms timing → out of near range, no timing credit.
        c = _make_candidate(start_frame=100, end_frame=125)
        score, reasons = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=145, fps=60.0,
        )
        # 0.40 (mid-before) + 0.20 (long dur) + 0.15 (vis) = 0.75
        assert 0.65 <= score <= 0.90, f"score={score}"
        assert any("before rotation_onset" in r for r in reasons)

    def test_stance_candidate_scores_floor(self):
        c = _make_candidate(start_frame=10, end_frame=60, duration_ms=833.0)
        score, _ = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=145, fps=60.0,
        )
        # Ends 70 frames (1167ms) before rot_onset → stance bucket = 0.02
        # No timing credit (contact - 10 = 2250ms — out of range)
        # +0.20 (long) +0.15 (vis) → ≈ 0.37
        assert score <= 0.45

    def test_starts_after_rot_onset_scores_zero_rotation_component(self):
        c = _make_candidate(start_frame=140, end_frame=160)
        score, reasons = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=200, fps=60.0,
        )
        # No rotation alignment credit; gets +0.20 dur +0.15 vis = ~0.35
        # Timing (200-140)=60 frames = 1000ms → no in-range credit either
        assert any("starts after rotation_onset" in r for r in reasons)

    def test_zero_visibility_no_credit(self):
        c = _make_candidate(start_frame=120, end_frame=140, min_visibility=0.3)
        score, _ = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=145, fps=60.0,
        )
        # No visibility credit → 1.0 + 0.30 + 0.20 = 1.50
        assert score <= 1.50 + 0.001

    def test_unknown_visibility_no_credit(self):
        c = _make_candidate(start_frame=120, end_frame=140, min_visibility=None)
        score, reasons = phase_detector_v4.score_candidate_as_final_plant(
            c, rot_onset=130, contact=145, fps=60.0,
        )
        assert score <= 1.50 + 0.001
        assert not any("visibility" in r for r in reasons)


# ---------------------------------------------------------------------------
# rank_candidates
# ---------------------------------------------------------------------------


class TestRankCandidates:
    def test_returns_sorted_descending(self):
        # 3 candidates with distinct expected ranks:
        #   stance (10-60): far before rot_onset → ~0.37
        #   mid-tap (100-120): ends 10 frames before rot_onset → ~0.40+0.20+0.15 = 0.75
        #   straddle (120-140): straddles rot_onset → ~1.45+
        candidates = [
            _make_candidate(10, 60),    # stance — should rank LAST
            _make_candidate(120, 140),  # straddle — should rank FIRST
            _make_candidate(100, 120),  # mid-tap — should rank MIDDLE
        ]
        ranked = phase_detector_v4.rank_candidates(
            candidates, rot_onset=130, contact=140, fps=60.0,
        )
        assert ranked[0]["start_frame"] == 120, "straddle should rank highest"
        assert ranked[0]["rank"] == 0
        assert ranked[-1]["start_frame"] == 10, "stance should rank lowest"
        assert ranked[-1]["rank"] == len(ranked) - 1

    def test_empty_input(self):
        assert phase_detector_v4.rank_candidates(
            [], rot_onset=100, contact=120, fps=60.0,
        ) == []


# ---------------------------------------------------------------------------
# derive_load_start_v4
# ---------------------------------------------------------------------------


class TestDeriveLoadStart:
    def test_walks_back_to_baseline_break(self):
        # Pre-load: stride flat at 5px; loading starts at frame 60.
        stride = np.concatenate([np.full(60, 5.0), np.linspace(5, 50, 60)])
        # Knee flat at 175°, bends from frame 60 onwards.
        knee = np.concatenate([np.full(60, 175.0), np.linspace(175, 140, 60)])
        load_start = phase_detector_v4.derive_load_start_v4(
            stride, knee, foot_plant_v4=110, fps=60.0,
        )
        # Should land somewhere right around frame 60 (where load begins)
        assert 55 <= load_start <= 75

    def test_handles_short_pre_window(self):
        stride = np.full(15, 5.0)
        knee = np.full(15, 175.0)
        load_start = phase_detector_v4.derive_load_start_v4(
            stride, knee, foot_plant_v4=10, fps=60.0,
        )
        # Pre-window is very short — falls back to defaults
        assert 0 <= load_start <= 10


# ---------------------------------------------------------------------------
# derive_launch_v4
# ---------------------------------------------------------------------------


class TestDeriveLaunch:
    def test_uses_burst_lo_when_after_foot_plant(self):
        launch = phase_detector_v4.derive_launch_v4(
            foot_plant_v4=100, contact=140, burst_lo=125,
        )
        assert launch == 125

    def test_clamps_below_contact(self):
        launch = phase_detector_v4.derive_launch_v4(
            foot_plant_v4=100, contact=140, burst_lo=200,
        )
        assert launch == 139

    def test_minimum_foot_plant_plus_one(self):
        launch = phase_detector_v4.derive_launch_v4(
            foot_plant_v4=100, contact=140, burst_lo=50,
        )
        assert launch == 101


# ---------------------------------------------------------------------------
# detect_phases_v4 — end-to-end on the canonical toe-tap case
# ---------------------------------------------------------------------------


def _build_analysis_debug_for_toe_tap():
    """Run phase_debug on the synthetic toe-tap fixture exactly as
    detect_phases.py does, so v4 receives realistic instrumentation."""
    n = 240
    fps = 60.0
    times = np.arange(n) / fps
    fa_y = _make_fa_y_toe_tap(n=n)
    vis_fa = np.ones(n) * 0.95
    hip_vel = np.zeros(n)
    for i in range(160, 176):
        hip_vel[i] = 10.0 * (i - 160) / 15.0
    for i in range(176, n):
        hip_vel[i] = max(0.0, 10.0 * math.exp(-(i - 175) / 8.0))
    stride = np.concatenate([np.full(100, 5.0),
                              np.linspace(5, 40, 60),
                              np.full(80, 40.0)])
    knee = np.concatenate([np.full(100, 175.0),
                            np.linspace(175, 145, 60),
                            np.full(80, 145.0)])
    # Legacy v3 detector mis-picks the tap as foot_plant
    phases_v3 = {
        "load_start": 90,
        "foot_plant": 125,   # ← tap (the bug)
        "launch":     165,
        "contact":    175,
        "peak_rotation": 185,
        "finish":     215,
    }
    analysis_debug = phase_debug.build_debug_payload(
        times=times, fa_y=fa_y, vis_fa=vis_fa, hip_vel=hip_vel,
        stride=stride, knee=knee, phases=phases_v3,
        burst_lo=165, burst_hi=195, burst_peak=175,
        fps=fps, torso_length_px=200.0,
        handedness="RIGHT", handedness_ratio=1.8, edge_warnings=[],
    )
    return {
        "times": times, "stride": stride, "knee": knee,
        "phases_v3": phases_v3, "analysis_debug": analysis_debug,
        "burst_lo": 165, "burst_hi": 195, "fps": fps,
    }


class TestDetectPhasesV4ToeTap:
    """The headline test — v4 must pick the real plant on a toe-tap swing."""

    def test_v4_foot_plant_differs_from_v3(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        v3_fp = ctx["phases_v3"]["foot_plant"]
        v4_fp = result["phases"]["foot_plant"]
        assert v4_fp != v3_fp, (
            f"v4 foot_plant ({v4_fp}) should differ from v3 ({v3_fp})"
        )
        # The real plant period starts at frame ~150
        assert v4_fp >= 140, f"v4 should pick the LATER (real) plant; got {v4_fp}"

    def test_v4_foot_plant_close_to_rotation_onset(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        rot_onset = ctx["analysis_debug"]["selected_phases"]["rotation_onset"]["frame"]
        # Real plant should straddle or be just before rotation_onset
        v4_fp = result["phases"]["foot_plant"]
        # Foot plant should start within ~250 ms of rotation_onset
        delta_ms = abs(v4_fp - rot_onset) * 1000.0 / ctx["fps"]
        assert delta_ms <= 250.0, (
            f"v4 foot_plant frame {v4_fp} is {delta_ms:.0f}ms from rot_onset {rot_onset}"
        )

    def test_v4_diff_metadata(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        diff = result["diff_from_v3"]
        assert diff["foot_plant_changed"] is True
        # v4 picks a LATER frame → positive delta
        assert diff["foot_plant_delta_frames"] > 0
        assert diff["foot_plant_delta_ms"] > 0
        # Contact / peak_rotation / finish never change in v4
        assert diff["contact_delta_frames"] == 0
        assert diff["peak_rotation_delta_frames"] == 0
        assert diff["finish_delta_frames"] == 0

    def test_v4_contact_unchanged(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        assert result["phases"]["contact"] == ctx["phases_v3"]["contact"]
        assert result["phases"]["peak_rotation"] == ctx["phases_v3"]["peak_rotation"]
        assert result["phases"]["finish"] == ctx["phases_v3"]["finish"]

    def test_v4_load_start_re_derived(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        # load_start_v4 should be reasonable for the new (later) foot_plant_v4
        assert 0 <= result["phases"]["load_start"] < result["phases"]["foot_plant"]

    def test_v4_launch_clamped(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        p = result["phases"]
        assert p["foot_plant"] < p["launch"] < p["contact"]

    def test_v4_confidence_high(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        assert result["confidence"] >= 0.6, (
            f"Expected confident pick on canonical toe-tap; got {result['confidence']}"
        )

    def test_v4_emits_alternatives(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        # Toe-tap signal has 3 candidates → 2 alternatives
        assert len(result["alternatives"]) >= 1


# ---------------------------------------------------------------------------
# Standard-stride should produce NO change
# ---------------------------------------------------------------------------


class TestDetectPhasesV4StandardStride:
    """For a standard stride, v3 already picks the right frame.
    v4 should agree (or near-agree) on foot_plant."""

    def _build(self):
        n = 120
        fps = 60.0
        times = np.arange(n) / fps
        fa_y = _make_fa_y_standard_stride(n=n)
        vis_fa = np.ones(n) * 0.95
        hip_vel = np.zeros(n)
        for i in range(85, 101):
            hip_vel[i] = 10.0 * (i - 85) / 15.0
        for i in range(101, n):
            hip_vel[i] = max(0.0, 10.0 * math.exp(-(i - 100) / 8.0))
        stride = np.concatenate([np.full(40, 5.0),
                                  np.linspace(5, 40, 40),
                                  np.full(40, 40.0)])
        knee = np.concatenate([np.full(40, 175.0),
                                np.linspace(175, 145, 40),
                                np.full(40, 145.0)])
        # v3 picks the post-lift final plant (frame ~85)
        phases_v3 = {
            "load_start": 40, "foot_plant": 85, "launch": 90,
            "contact": 100, "peak_rotation": 110, "finish": 119,
        }
        analysis_debug = phase_debug.build_debug_payload(
            times=times, fa_y=fa_y, vis_fa=vis_fa, hip_vel=hip_vel,
            stride=stride, knee=knee, phases=phases_v3,
            burst_lo=90, burst_hi=115, burst_peak=100,
            fps=fps, torso_length_px=200.0,
            handedness="RIGHT", handedness_ratio=1.8, edge_warnings=[],
        )
        return {
            "times": times, "stride": stride, "knee": knee,
            "phases_v3": phases_v3, "analysis_debug": analysis_debug,
            "burst_lo": 90, "burst_hi": 115, "fps": fps,
        }

    def test_v4_agrees_with_v3_on_standard_stride(self):
        ctx = self._build()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        # Allow up to 3-frame disagreement (smoothing edge effects)
        assert abs(result["phases"]["foot_plant"]
                   - ctx["phases_v3"]["foot_plant"]) <= 3


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


class TestFallbackToV3:
    def test_no_candidates_falls_back(self):
        n = 120
        times = np.arange(n) / 60.0
        # Empty analysis_debug
        analysis_debug = {
            "foot_plant_candidates": [],
            "selected_phases": {
                "rotation_onset": {"frame": 80, "time_s": 1.33, "confidence": 0.5,
                                    "reason": "synthetic"},
            },
        }
        phases_v3 = {
            "load_start": 40, "foot_plant": 85, "launch": 90,
            "contact": 100, "peak_rotation": 110, "finish": 119,
        }
        result = phase_detector_v4.detect_phases_v4(
            times=times, stride=np.zeros(n), knee=np.full(n, 175.0),
            analysis_debug=analysis_debug, phases_v3=phases_v3,
            burst_lo=90, burst_hi=115, fps=60.0,
        )
        assert result["fallback_to_v3"] is True
        assert result["phases"] == phases_v3
        assert "fallback" in result["selection_reason"].lower()
        assert result["confidence"] <= 0.30

    def test_phases_v3_not_mutated(self):
        n = 120
        times = np.arange(n) / 60.0
        phases_v3 = {
            "load_start": 40, "foot_plant": 85, "launch": 90,
            "contact": 100, "peak_rotation": 110, "finish": 119,
        }
        phases_v3_copy = dict(phases_v3)
        analysis_debug = {
            "foot_plant_candidates": [],
            "selected_phases": {
                "rotation_onset": {"frame": 80, "time_s": 1.33, "confidence": 0.5,
                                    "reason": "synthetic"},
            },
        }
        phase_detector_v4.detect_phases_v4(
            times=times, stride=np.zeros(n), knee=np.full(n, 175.0),
            analysis_debug=analysis_debug, phases_v3=phases_v3,
            burst_lo=90, burst_hi=115, fps=60.0,
        )
        # v4 must NEVER mutate the v3 phases it was passed
        assert phases_v3 == phases_v3_copy


# ---------------------------------------------------------------------------
# Pretty-print summary
# ---------------------------------------------------------------------------


class TestFormatSummary:
    def test_summary_nonempty_for_normal_pick(self):
        ctx = _build_analysis_debug_for_toe_tap()
        result = phase_detector_v4.detect_phases_v4(
            times=ctx["times"], stride=ctx["stride"], knee=ctx["knee"],
            analysis_debug=ctx["analysis_debug"],
            phases_v3=ctx["phases_v3"],
            burst_lo=ctx["burst_lo"], burst_hi=ctx["burst_hi"], fps=ctx["fps"],
        )
        s = phase_detector_v4.format_v4_summary(result)
        assert "DETECTOR V4" in s
        assert "foot_plant" in s
        assert "Δ=" in s
        assert "ALTERNATIVES" in s

    def test_summary_flags_fallback(self):
        n = 120
        times = np.arange(n) / 60.0
        result = phase_detector_v4.detect_phases_v4(
            times=times, stride=np.zeros(n), knee=np.full(n, 175.0),
            analysis_debug={
                "foot_plant_candidates": [],
                "selected_phases": {"rotation_onset":
                                     {"frame": 80, "time_s": 1.33,
                                      "confidence": 0.5, "reason": "x"}},
            },
            phases_v3={"load_start": 40, "foot_plant": 85, "launch": 90,
                       "contact": 100, "peak_rotation": 110, "finish": 119},
            burst_lo=90, burst_hi=115, fps=60.0,
        )
        s = phase_detector_v4.format_v4_summary(result)
        assert "Fell back to v3" in s


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
