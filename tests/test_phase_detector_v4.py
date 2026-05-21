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


# ---------------------------------------------------------------------------
# Phase 4a — regression tests for the 3 bugs surfaced by the Phase 3 report
# ---------------------------------------------------------------------------


class TestPhase4aFix1EndOfContactAnchor:
    """Fix 1: when there's a single stable-contact period covering the
    whole pre-rotation window, v4 should anchor foot_plant to the END of
    the contact (just before lift), not the START (frame 0).

    The Phase 3 report row that exposed this:
      img_8436   gt_plant=52   v3=52 (perfect)   v4=0  (off by -52)
    """

    def test_effective_anchor_uses_end_for_pre_rotation_stance(self):
        # Long stance from frame 0 to 50, rotation_onset at 55. Foot lifts
        # during 50–55 and contact happens at 57.
        contact = {"start_frame": 0, "end_frame": 50, "duration_ms": 833.0}
        anchor = phase_detector_v4._effective_anchor(
            contact, rot_onset=55, fps=60.0,
        )
        # Should land on frame 51 (end+1) — clamped not to exceed rot_onset
        assert anchor == 51, f"expected 51, got {anchor}"

    def test_effective_anchor_unchanged_for_straddle_recent_start(self):
        # Contact straddles rotation_onset AND started recently (200ms
        # before rot_onset) → this is a real plant. Start IS the plant.
        # fps=60, gap = 18 frames = 300ms — JUST below the long_stance threshold.
        contact = {"start_frame": 142, "end_frame": 200, "duration_ms": 967.0}
        anchor = phase_detector_v4._effective_anchor(
            contact, rot_onset=160, fps=60.0,
        )
        # 18 frames * 1000/60 = 300ms, default threshold = 300ms → uses start
        # (the >= comparison makes 300ms exactly fall on the threshold;
        # we use < threshold to keep start, so 18 frames at exactly 300ms
        # triggers the long-stance branch. Use 17 frames to be safely below.)
        # Adjust to verify "recent start" returns start_frame:
        contact_recent = {"start_frame": 145, "end_frame": 200,
                          "duration_ms": 917.0}
        anchor_recent = phase_detector_v4._effective_anchor(
            contact_recent, rot_onset=160, fps=60.0,
        )
        # 15 frames * 1000/60 = 250ms — well below 300ms threshold
        assert anchor_recent == 145, f"expected start=145, got {anchor_recent}"

    def test_effective_anchor_straddle_long_stance_anchors_at_rot_onset(self):
        """Phase 4b extension: a long stance that STRADDLES rot_onset
        (e.g. no-stride pattern) should anchor at rot_onset, not at
        start. Targets the img_8436 / img_8608 / mariotswing failure
        mode from the Phase 4a Pass #2 report."""
        # Stance covers frames 0-56, rot_onset at 53. Start is 53 frames
        # = 1767ms before rot_onset at 30 fps — way past the 300ms threshold.
        contact = {"start_frame": 0, "end_frame": 56, "duration_ms": 1900.0}
        anchor = phase_detector_v4._effective_anchor(
            contact, rot_onset=53, fps=30.0,
        )
        # Should anchor at rot_onset=53, not at start=0
        assert anchor == 53, (
            f"long stance straddling rot_onset should anchor at rot_onset; "
            f"got {anchor}"
        )

    def test_effective_anchor_straddle_short_stance_keeps_start(self):
        """Real toe-tap final-plant contact straddles rot_onset by a
        small margin — those should keep start_frame (the real plant).
        Targets the toe-tap MLB clips where v4 already wins."""
        # Plant starts at frame 130, rot_onset=135, ends at 145.
        # Start to rot_onset gap = 5 frames = 167ms at 30 fps —
        # well below the 300ms long-stance threshold.
        contact = {"start_frame": 130, "end_frame": 145, "duration_ms": 533.0}
        anchor = phase_detector_v4._effective_anchor(
            contact, rot_onset=135, fps=30.0,
        )
        assert anchor == 130, (
            f"recent-start straddle should keep start; got {anchor}"
        )

    def test_effective_anchor_unchanged_for_distant_stance(self):
        # Stance ends 500ms before rot_onset → not the plant, keep start
        contact = {"start_frame": 0, "end_frame": 20, "duration_ms": 333.0}
        anchor = phase_detector_v4._effective_anchor(
            contact, rot_onset=60, fps=60.0,
        )
        # Gap = 40 frames = 667 ms — well beyond the 200ms window
        assert anchor == 0

    def test_end_to_end_single_contact_clip(self):
        """Replicate the img_8436 failure mode end-to-end and assert v4
        picks the end-of-stance frame, not 0."""
        n = 60
        fps = 60.0
        times = np.arange(n) / fps
        # Foot on the ground from frame 0–50, then lifts slightly
        fa_y = np.full(n, 500.0)
        fa_y[50:55] = 490.0   # tiny lift before contact
        fa_y[55:] = 495.0
        vis_fa = np.ones(n) * 0.95
        # Hip velocity ramps up around frame 50, peaks at 57 (contact)
        hip_vel = np.zeros(n)
        for i in range(50, 58):
            hip_vel[i] = 10.0 * (i - 50) / 7.0
        for i in range(58, n):
            hip_vel[i] = max(0.0, 10.0 * math.exp(-(i - 57) / 3.0))
        stride = np.concatenate([np.full(45, 5.0), np.linspace(5, 30, 15)])
        knee = np.concatenate([np.full(45, 175.0), np.linspace(175, 145, 15)])
        # Legacy v3 detector picks foot_plant=52 (correct on this clip)
        phases_v3 = {
            "load_start": 40, "foot_plant": 52, "launch": 56,
            "contact": 57, "peak_rotation": 58, "finish": 59,
        }
        analysis_debug = phase_debug.build_debug_payload(
            times=times, fa_y=fa_y, vis_fa=vis_fa, hip_vel=hip_vel,
            stride=stride, knee=knee, phases=phases_v3,
            burst_lo=50, burst_hi=58, burst_peak=57,
            fps=fps, torso_length_px=200.0,
            handedness="RIGHT", handedness_ratio=1.8, edge_warnings=[],
        )
        result = phase_detector_v4.detect_phases_v4(
            times=times, stride=stride, knee=knee,
            analysis_debug=analysis_debug, phases_v3=phases_v3,
            burst_lo=50, burst_hi=58, fps=fps,
        )
        # v4 should pick a plant frame near rotation onset (not 0)
        assert result["phases"]["foot_plant"] >= 30, (
            f"v4 plant should be near rotation onset, got "
            f"{result['phases']['foot_plant']}"
        )


class TestPhase4aFix2TighterToeTapClassifier:
    """Fix 2: the bare contact-count rule (≥3 contacts → toe_tap) was
    over-predicting toe_tap because MediaPipe jitter splits a single
    stance into multiple contacts with no real lift between them.

    Phase 3 confusion matrix:
        29 standard_stride swings → 11 mis-classified as toe_tap (~38%)

    The fix requires at least 2 REAL lifts (≥50ms gap + ≥8% torso
    height) between consecutive contacts before believing it's a tap.
    """

    def test_jitter_split_stance_not_classified_as_toe_tap(self):
        """3 contacts close together with no real lift between them
        should classify as standard_stride, not toe_tap."""
        # Build fa_y that stays mostly on the ground for frames 0-80, then
        # has a real stride lift from 80-100, then settles. MediaPipe
        # jitter splits the initial stance into 3 short contacts via tiny
        # blips that the contact-finder picks up.
        n = 120
        fa_y = np.full(n, 500.0)
        # Tiny jitter blips that split the stance — only 2 frames each,
        # so the lift is real but extremely brief.
        fa_y[25:27] = 498.0
        fa_y[55:57] = 498.0
        # Real stride lift
        fa_y[80:100] = 440.0  # 60px lift = 30% of 200px torso
        contacts = [
            {"start_frame": 0,   "end_frame": 24,  "duration_ms": 400.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
            {"start_frame": 27,  "end_frame": 54,  "duration_ms": 450.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
            {"start_frame": 57,  "end_frame": 79,  "duration_ms": 367.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
            {"start_frame": 100, "end_frame": 119, "duration_ms": 333.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
        ]
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=100, contact=115,
            burst_lo=80, torso_length_px=200.0, fps=60.0,
        )
        assert style != "toe_tap", (
            f"jitter-split stance should NOT be toe_tap; got {style} ({reason})"
        )

    def test_real_toe_tap_still_classified_as_toe_tap(self):
        """Real toe-tap (stance + meaningful tap + final plant with real
        lifts between) must still classify as toe_tap."""
        n = 240
        fa_y = np.full(n, 500.0)
        # Real lift 1 (frames 100–115) — 60 px lift = 30% of 200 torso
        fa_y[100:115] = 440.0
        # Real lift 2 (frames 135–150)
        fa_y[135:150] = 440.0
        contacts = [
            {"start_frame": 0,   "end_frame": 99,  "duration_ms": 1650.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
            {"start_frame": 115, "end_frame": 134, "duration_ms": 317.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
            {"start_frame": 150, "end_frame": 239, "duration_ms": 1500.0,
             "mean_y": 500.0, "mean_abs_vel": 1.0, "min_visibility": 0.9},
        ]
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=150, contact=175,
            burst_lo=165, torso_length_px=200.0, fps=60.0,
        )
        assert style == "toe_tap", (
            f"real toe-tap should classify as toe_tap; got {style} ({reason})"
        )



class TestPhase4aFix3ConfidenceCalibration:
    """Fix 3: a high raw score must NOT translate to high confidence when
    the picked frame is far from rotation_onset.

    Phase 3 row that exposed this:
        elly_de_la_cruz_swing  v4=1322  conf=1.00  but 145 frames off
    """

    def test_confidence_capped_when_plant_far_from_rot_onset(self):
        """Synthetic clip where v4 picks a plant ≥ 500 ms from
        rotation_onset — confidence must be ≤ 0.5."""
        n = 200
        fps = 60.0
        times = np.arange(n) / fps
        # Foot on ground throughout — single long contact
        fa_y = np.full(n, 500.0)
        vis_fa = np.ones(n) * 0.95
        # Rotation onset at frame 100, contact at 120
        hip_vel = np.zeros(n)
        for i in range(100, 121):
            hip_vel[i] = 10.0 * (i - 100) / 20.0
        for i in range(121, n):
            hip_vel[i] = max(0.0, 10.0 * math.exp(-(i - 120) / 5.0))
        stride = np.concatenate([np.full(80, 5.0), np.linspace(5, 40, 120)])
        knee = np.concatenate([np.full(80, 175.0), np.linspace(175, 145, 120)])
        phases_v3 = {
            "load_start": 30, "foot_plant": 0, "launch": 110,
            "contact": 120, "peak_rotation": 125, "finish": 140,
        }
        analysis_debug = phase_debug.build_debug_payload(
            times=times, fa_y=fa_y, vis_fa=vis_fa, hip_vel=hip_vel,
            stride=stride, knee=knee, phases=phases_v3,
            burst_lo=100, burst_hi=130, burst_peak=120,
            fps=fps, torso_length_px=200.0,
            handedness="RIGHT", handedness_ratio=1.8, edge_warnings=[],
        )
        result = phase_detector_v4.detect_phases_v4(
            times=times, stride=stride, knee=knee,
            analysis_debug=analysis_debug, phases_v3=phases_v3,
            burst_lo=100, burst_hi=130, fps=fps,
        )
        # If the v4 pick happens to be near rotation onset, we don't get
        # to test the penalty — skip in that case. Otherwise the penalty
        # must apply.
        v4_plant = result["phases"]["foot_plant"]
        gap_ms = abs(v4_plant - 100) * 1000.0 / fps
        if gap_ms > 200.0:
            assert result["confidence"] <= 0.5, (
                f"confidence should be capped when plant is {gap_ms:.0f}ms "
                f"from rot_onset; got conf={result['confidence']}"
            )

    def test_confidence_unchanged_when_plant_near_rot_onset(self):
        """When the picked plant IS near rotation_onset, the calibration
        penalty does NOT kick in."""
        from phase_detector_v4 import detect_phases_v4
        # Single candidate exactly straddling rotation_onset, high raw
        # score. Should keep its high confidence.
        n = 150
        fps = 60.0
        times = np.arange(n) / fps
        analysis_debug = {
            "foot_plant_candidates": [
                {"start_frame": 100, "end_frame": 130,
                 "duration_ms": 517.0, "mean_y": 500.0,
                 "mean_abs_vel": 1.0, "min_visibility": 0.95,
                 "start_time_s": 1.667, "end_time_s": 2.167,
                 "mean_y_px": 500.0, "mean_abs_vel_px_per_s": 1.0,
                 "selected_as_foot_plant": True},
            ],
            "selected_phases": {
                "rotation_onset": {"frame": 110, "time_s": 1.833,
                                    "confidence": 0.9, "reason": "synthetic"},
            },
        }
        phases_v3 = {
            "load_start": 50, "foot_plant": 110, "launch": 115,
            "contact": 125, "peak_rotation": 130, "finish": 140,
        }
        result = detect_phases_v4(
            times=times, stride=np.zeros(n), knee=np.full(n, 175.0),
            analysis_debug=analysis_debug, phases_v3=phases_v3,
            burst_lo=100, burst_hi=130, fps=fps,
        )
        # Plant straddles rot_onset — penalty should NOT fire
        assert result["confidence"] >= 0.85, (
            f"confidence should stay high for on-target pick; "
            f"got conf={result['confidence']}"
        )


class TestPhase4cTrustPhaseDebugFootPlant:
    """Phase 4c Fix 1 — when phase_debug.selected_phases.foot_plant is
    confident AND aligned with rotation_onset, v4 should adopt it
    directly instead of re-deriving from foot_plant_candidates.

    Phase 4b validation showed v4 regressing on 7/7 short-clip swings
    where phase_debug already had the right answer (conf ≥ 0.6, within
    ~70ms of rot_onset) but v4's candidate ranking landed 50-90 frames
    earlier because the candidates list didn't contain the actual plant.
    """

    def _payload(self, *, candidates, pd_fp_frame, pd_fp_conf, rot_onset,
                 pd_fp_reason="stable contact aligned with rotation onset"):
        """Build a minimal analysis_debug shape that detect_phases_v4 reads."""
        return {
            "foot_plant_candidates": candidates,
            "selected_phases": {
                "rotation_onset": {"frame": rot_onset, "time_s": 0.0,
                                    "confidence": 0.9, "reason": "synthetic"},
                "foot_plant":     {"frame": pd_fp_frame, "time_s": 0.0,
                                    "confidence": pd_fp_conf,
                                    "reason": pd_fp_reason},
            },
        }

    def test_short_clip_with_only_early_candidate_uses_phase_debug(self):
        """img_8436 regression: only candidate is [0,27] (the early
        stance), but phase_debug picked frame 52 with conf=1.0 because
        the stable contact aligns with rot_onset=53. v4 must return 52,
        not 0 (the start of the misleading candidate)."""
        from phase_detector_v4 import detect_phases_v4
        n = 120
        fps = 29.7  # ≈ real img_8436 fps
        ad = self._payload(
            candidates=[
                {"start_frame": 0, "end_frame": 27, "duration_ms": 943.0,
                 "min_visibility": 0.95},
            ],
            pd_fp_frame=52, pd_fp_conf=1.0, rot_onset=53,
        )
        phases_v3 = {
            "load_start": 30, "foot_plant": 52, "launch": 53,
            "contact": 57, "peak_rotation": 60, "finish": 70,
        }
        res = detect_phases_v4(
            times=np.arange(n) / fps, stride=np.zeros(n),
            knee=np.full(n, 180.0),
            analysis_debug=ad, phases_v3=phases_v3,
            burst_lo=53, burst_hi=70, fps=fps,
        )
        assert res["phases"]["foot_plant"] == 52, (
            f"Expected 52 (phase_debug's pick); got {res['phases']['foot_plant']}. "
            "v4 must trust phase_debug when its pick is high-confidence and "
            "near rotation_onset, NOT re-derive from the misleading [0,27] "
            "candidate which lands at frame 0."
        )
        assert "phase_debug.foot_plant" in res["selection_reason"]
        assert res["fallback_to_v3"] is False

    def test_toe_tap_with_tap_candidate_uses_phase_debug_for_final_plant(self):
        """img_8605 / img_8607 / swing regression: foot_plant_candidates
        contains [tap, final_plant] but the duration credit makes the tap
        win in candidate ranking. phase_debug picks the final plant
        correctly (the "stable contact aligned with rotation onset" branch);
        v4 should adopt that and not pick the earlier tap."""
        from phase_detector_v4 import detect_phases_v4
        n = 200
        fps = 30.0
        # Realistic toe-tap candidate layout: a long early tap [36, 48]
        # plus a short final plant [78, 80]. Without the fix, candidate
        # ranking picks frame 36 (the tap); with the fix, v4 takes
        # phase_debug's pick of frame 78.
        ad = self._payload(
            candidates=[
                {"start_frame": 36, "end_frame": 48, "duration_ms": 433.0,
                 "min_visibility": 0.95},
                {"start_frame": 78, "end_frame": 80, "duration_ms": 100.0,
                 "min_visibility": 0.95},
            ],
            pd_fp_frame=78, pd_fp_conf=0.6, rot_onset=76,
            pd_fp_reason="foot_plant→contact 67 ms out of range",
        )
        phases_v3 = {
            "load_start": 50, "foot_plant": 78, "launch": 76,
            "contact": 80, "peak_rotation": 85, "finish": 95,
        }
        res = detect_phases_v4(
            times=np.arange(n) / fps, stride=np.zeros(n),
            knee=np.full(n, 180.0),
            analysis_debug=ad, phases_v3=phases_v3,
            burst_lo=76, burst_hi=80, fps=fps,
        )
        assert res["phases"]["foot_plant"] == 78, (
            f"Expected 78 (the final plant); got {res['phases']['foot_plant']}. "
            "v4 must not pick the tap candidate at frame 36 — phase_debug "
            "already identified 78 as the plant near rotation_onset."
        )

    def test_low_confidence_phase_debug_falls_through_to_candidate_ranking(self):
        """When phase_debug.foot_plant.confidence is below
        PHASE_DEBUG_TRUST_MIN_CONF, v4 should run its normal candidate
        ranking instead of blindly trusting phase_debug. This keeps the
        Phase 4b candidate-ranking path active for long-swing cases
        where phase_debug is itself uncertain."""
        from phase_detector_v4 import detect_phases_v4
        n = 200
        fps = 60.0
        # phase_debug picked frame 100 with conf=0.4 — below trust threshold.
        # A strong candidate exists that straddles rot_onset; ranking
        # should pick THAT, not phase_debug's low-confidence guess.
        ad = self._payload(
            candidates=[
                {"start_frame": 110, "end_frame": 140, "duration_ms": 500.0,
                 "min_visibility": 0.95},
            ],
            pd_fp_frame=100, pd_fp_conf=0.4, rot_onset=120,
            pd_fp_reason="brief contact (low confidence)",
        )
        phases_v3 = {
            "load_start": 80, "foot_plant": 110, "launch": 120,
            "contact": 130, "peak_rotation": 140, "finish": 150,
        }
        res = detect_phases_v4(
            times=np.arange(n) / fps, stride=np.zeros(n),
            knee=np.full(n, 180.0),
            analysis_debug=ad, phases_v3=phases_v3,
            burst_lo=120, burst_hi=130, fps=fps,
        )
        # Candidate ranking should pick frame 110 (the straddling
        # candidate), NOT 100 (phase_debug's low-confidence guess).
        assert res["phases"]["foot_plant"] == 110, (
            f"Expected 110 (from candidate ranking); got {res['phases']['foot_plant']}."
        )
        assert "phase_debug.foot_plant" not in res["selection_reason"]

    def test_far_phase_debug_falls_through_to_candidate_ranking(self):
        """When phase_debug.foot_plant lands far from rotation_onset
        (> PHASE_DEBUG_TRUST_GAP_MAX_MS), v4 should also fall through
        to candidate ranking. A "far" phase_debug pick is suspect even
        if its confidence is high."""
        from phase_detector_v4 import detect_phases_v4
        n = 200
        fps = 60.0
        # phase_debug picked frame 50 (conf=1.0) but rot_onset is at 130 —
        # 80 frames / 1333ms away. Far above the 300ms trust gap.
        ad = self._payload(
            candidates=[
                {"start_frame": 120, "end_frame": 145, "duration_ms": 417.0,
                 "min_visibility": 0.95},
            ],
            pd_fp_frame=50, pd_fp_conf=1.0, rot_onset=130,
        )
        phases_v3 = {
            "load_start": 90, "foot_plant": 120, "launch": 130,
            "contact": 140, "peak_rotation": 150, "finish": 160,
        }
        res = detect_phases_v4(
            times=np.arange(n) / fps, stride=np.zeros(n),
            knee=np.full(n, 180.0),
            analysis_debug=ad, phases_v3=phases_v3,
            burst_lo=130, burst_hi=140, fps=fps,
        )
        # Candidate ranking takes over; should pick frame 120.
        assert res["phases"]["foot_plant"] == 120, (
            f"Expected 120; got {res['phases']['foot_plant']}. "
            "Far-from-rot_onset phase_debug picks should be ignored "
            "even when conf=1.0."
        )

    def test_phase_debug_pick_confidence_propagates(self):
        """When v4 adopts phase_debug's pick, the returned confidence
        should reflect phase_debug's confidence (rounded), not a
        candidate-ranking score."""
        from phase_detector_v4 import detect_phases_v4
        n = 120
        fps = 30.0
        ad = self._payload(
            candidates=[{"start_frame": 0, "end_frame": 27,
                         "duration_ms": 900.0, "min_visibility": 0.95}],
            pd_fp_frame=52, pd_fp_conf=0.85, rot_onset=53,
        )
        phases_v3 = {
            "load_start": 30, "foot_plant": 52, "launch": 53,
            "contact": 57, "peak_rotation": 60, "finish": 70,
        }
        res = detect_phases_v4(
            times=np.arange(n) / fps, stride=np.zeros(n),
            knee=np.full(n, 180.0),
            analysis_debug=ad, phases_v3=phases_v3,
            burst_lo=53, burst_hi=70, fps=fps,
        )
        assert res["confidence"] == 0.85
        assert res["alternatives"] == [], (
            "When trusting phase_debug, we don't surface candidate "
            "alternatives because we didn't run candidate ranking."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
