"""
Unit tests for phase_debug.py — the PHASE_DEBUG_V1 instrumentation module.

These tests verify the instrumentation's behavior on synthetic signals
designed to mimic the four stride patterns the redesign needs to handle:
no_stride, standard_stride, toe_tap, leg_kick. They do NOT exercise
detect_phases.py end-to-end — for that, see the manual test instructions
in the Phase 1 hand-off.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import phase_debug  # noqa: E402


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_is_enabled_truthy(self):
        for v in ("1", "true", "TRUE", "yes", "Yes", "on", "ON"):
            assert phase_debug.is_enabled({"PHASE_DEBUG_V1": v}) is True

    def test_is_enabled_falsy(self):
        for v in ("", "0", "false", "no", "off", "maybe"):
            assert phase_debug.is_enabled({"PHASE_DEBUG_V1": v}) is False

    def test_is_enabled_missing(self):
        assert phase_debug.is_enabled({}) is False


# ---------------------------------------------------------------------------
# find_stable_contact_periods
# ---------------------------------------------------------------------------


def _smooth(arr, window=5):
    """5-frame centered moving average — matches detect_phases.py:smooth()."""
    arr = np.asarray(arr, dtype=float)
    out = np.copy(arr)
    half = window // 2
    for i in range(len(arr)):
        lo = max(0, i - half)
        hi = min(len(arr), i + half + 1)
        out[i] = np.mean(arr[lo:hi])
    return out


def _make_fa_y_no_stride(n=120, ground=500.0, noise=0.4):
    """Front-ankle stays on the ground the whole clip."""
    rng = np.random.default_rng(42)
    return _smooth(ground + rng.normal(0, noise, n))


def _make_fa_y_standard_stride(n=120, ground=500.0, lift_start=40, lift_end=80,
                                lift_depth=60.0, noise=0.4):
    """One single lift then return to ground. Two stable-contact periods:
    stance (0..lift_start-1) and final plant (lift_end..n-1).
    """
    rng = np.random.default_rng(42)
    y = ground + rng.normal(0, noise, n)
    for i in range(lift_start, lift_end):
        y[i] = ground - lift_depth
    return _smooth(y)


def _make_fa_y_toe_tap(n=240, ground=500.0, lift_depth=80.0, noise=0.4):
    """Realistic toe-tap pattern, positioned for burst_lo ~= 165:

      Frame   0–99    stance        (on ground, ~1.7 s at 60 fps)
      Frame 100–114   lift 1        (off ground)
      Frame 115–134   tap touch     (on ground, 333 ms — survives smoothing)
      Frame 135–149   lift 2        (off ground — real stride)
      Frame 150–239   final plant   (on ground through contact)

    Tap touch is intentionally generous (20 frames) so a 5-frame moving
    average still leaves enough pure-ground frames in the middle to clear
    the 80 ms minimum-duration cutoff.
    """
    rng = np.random.default_rng(42)
    y = ground + rng.normal(0, noise, n)
    for i in range(100, 115):
        y[i] = ground - lift_depth
    for i in range(135, 150):
        y[i] = ground - lift_depth
    return _smooth(y)


def _make_fa_y_leg_kick(n=140, ground=500.0,
                        lift_start=30, lift_end=90,
                        lift_depth=180.0, noise=0.4):
    rng = np.random.default_rng(42)
    y = ground + rng.normal(0, noise, n)
    for i in range(lift_start, lift_end):
        y[i] = ground - lift_depth
    return _smooth(y)


class TestStableContactPeriods:
    def test_no_stride_one_long_contact(self):
        fa_y = _make_fa_y_no_stride()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=50.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        assert len(contacts) >= 1
        # One contact should span most of the window
        longest = max(contacts, key=lambda c: c["duration_ms"])
        assert longest["duration_ms"] > 1500.0

    def test_standard_stride_split_contacts(self):
        fa_y = _make_fa_y_standard_stride()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=50.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        # Pre-lift and post-lift should each show up
        assert len(contacts) == 2
        # Lifted frames should NOT appear in any contact
        for c in contacts:
            assert not (45 <= c["start_frame"] <= 75)

    def test_toe_tap_produces_multiple_contacts(self):
        fa_y = _make_fa_y_toe_tap()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=80.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        # Expect three: stance, tap touch, final plant
        assert len(contacts) == 3, (
            f"Toe-tap should produce 3 contacts, got {len(contacts)}: {contacts}"
        )

    def test_visibility_gates_out_contact(self):
        fa_y = _make_fa_y_no_stride()
        vel = np.gradient(fa_y) * 60.0
        vis = np.ones_like(fa_y) * 0.95
        # Mark a chunk as poorly visible
        vis[30:60] = 0.2
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, vis,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=50.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        # The contiguous on-ground run should be broken into two
        assert len(contacts) >= 2
        # No contact should include the poorly-visible range
        for c in contacts:
            for f in range(c["start_frame"], c["end_frame"] + 1):
                assert vis[f] >= phase_debug.LOW_VISIBILITY_THRESHOLD

    def test_min_duration_filters_brief_touches(self):
        # Single 30 ms touch at 60 fps = ~2 frames, below the 80 ms (5-frame) cutoff
        n = 60
        fa_y = np.full(n, 100.0)
        fa_y[10:35] = 200.0  # "lifted"
        fa_y[20:22] = 100.0  # brief touch within the lift
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=100.0, ground_eps=5.0, velocity_eps=100.0,
            lo=0, hi=n, fps=60.0,
        )
        # The 2-frame touch should NOT make it past the 80 ms min duration
        for c in contacts:
            assert not (c["start_frame"] == 20 and c["end_frame"] == 21)


# ---------------------------------------------------------------------------
# rotation_onset_frame
# ---------------------------------------------------------------------------


class TestRotationOnset:
    def _make_hip_vel(self, n=120, onset=80, peak=95, peak_val=10.0):
        v = np.zeros(n)
        # Linear ramp from onset to peak
        for i in range(onset, peak + 1):
            v[i] = peak_val * (i - onset) / (peak - onset)
        # Decay after peak
        for i in range(peak + 1, n):
            v[i] = max(0.0, v[peak] * math.exp(-(i - peak) / 5.0))
        return v

    def test_walks_back_to_threshold(self):
        v = self._make_hip_vel()
        onset = phase_debug.rotation_onset_frame(
            v, contact=95, burst_lo=70, fps=60.0,
        )
        # At onset, |v| should be ~ 0.15 * peak (= 1.5)
        assert 80 <= onset <= 85, f"Expected onset near 82, got {onset}"
        assert abs(v[onset]) <= 0.15 * v[95] + 0.5

    def test_bounded_by_burst_lo(self):
        v = self._make_hip_vel(n=120, onset=10, peak=95, peak_val=10.0)
        # If burst_lo is high, onset shouldn't go below it
        onset = phase_debug.rotation_onset_frame(
            v, contact=95, burst_lo=50, fps=60.0,
        )
        assert onset >= 50

    def test_zero_peak_returns_contact(self):
        v = np.zeros(60)
        onset = phase_debug.rotation_onset_frame(
            v, contact=40, burst_lo=20, fps=60.0,
        )
        assert onset == 40


# ---------------------------------------------------------------------------
# Stride-style classification
# ---------------------------------------------------------------------------


class TestStrideStyleClassification:
    """Each test simulates a complete contact list and fa_y for a given stride."""

    def test_no_stride(self):
        fa_y = _make_fa_y_no_stride()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=50.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=100, contact=110,
            burst_lo=80, torso_length_px=200.0, fps=60.0,
        )
        assert style == "no_stride", f"Got {style} ({reason})"

    def test_standard_stride(self):
        fa_y = _make_fa_y_standard_stride()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=50.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        # foot_plant inside the post-lift contact (~frame 80 onwards)
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=85, contact=110,
            burst_lo=80, torso_length_px=200.0, fps=60.0,
        )
        assert style == "standard_stride", f"Got {style} ({reason})"

    def test_toe_tap(self):
        fa_y = _make_fa_y_toe_tap()
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=80.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=160, contact=175,
            burst_lo=165, torso_length_px=200.0, fps=60.0,
        )
        assert style == "toe_tap", f"Got {style} ({reason})"

    def test_leg_kick(self):
        fa_y = _make_fa_y_leg_kick(lift_depth=180.0)
        vel = np.gradient(fa_y) * 60.0
        contacts = phase_debug.find_stable_contact_periods(
            fa_y, vel, None,
            ground_floor=500.0, ground_eps=2.0, velocity_eps=80.0,
            lo=0, hi=len(fa_y), fps=60.0,
        )
        # torso ≈ 200 px → 180 lift / 200 torso = 0.90 ≥ 0.55 leg-kick threshold
        style, reason = phase_debug.classify_stride_style(
            contacts, fa_y=fa_y, foot_plant=100, contact=120,
            burst_lo=80, torso_length_px=200.0, fps=60.0,
        )
        assert style == "leg_kick", f"Got {style} ({reason})"

    def test_uncertain_when_torso_unknown(self):
        style, _ = phase_debug.classify_stride_style(
            [], fa_y=np.zeros(60),
            foot_plant=30, contact=40, burst_lo=20,
            torso_length_px=0.0, fps=60.0,
        )
        assert style == "uncertain"


# ---------------------------------------------------------------------------
# Confidence scorers
# ---------------------------------------------------------------------------


class TestFootPlantConfidence:
    def test_clean_plant_high_confidence(self):
        # foot_plant=80, contact=92 → 200 ms apart at 60 fps (well within range)
        plant = {
            "start_frame": 80, "end_frame": 95,
            "duration_ms": 250.0,
            "mean_y": 500.0, "mean_abs_vel": 5.0,
            "min_visibility": 0.95,
        }
        conf, reason = phase_debug.score_foot_plant_confidence(
            plant, [plant],
            velocity_eps=50.0, rot_onset=82, contact=92,
            foot_plant=80, fps=60.0,
        )
        assert conf >= 0.85, f"conf={conf} reason={reason}"

    def test_short_contact_reduces_confidence(self):
        plant = {
            "start_frame": 80, "end_frame": 82,
            "duration_ms": 50.0,
            "mean_y": 500.0, "mean_abs_vel": 5.0,
            "min_visibility": 0.95,
        }
        conf, _ = phase_debug.score_foot_plant_confidence(
            plant, [plant],
            velocity_eps=50.0, rot_onset=82, contact=110,
            foot_plant=80, fps=60.0,
        )
        assert conf <= 0.65

    def test_no_matching_run_returns_floor(self):
        conf, reason = phase_debug.score_foot_plant_confidence(
            None, [],
            velocity_eps=50.0, rot_onset=82, contact=110,
            foot_plant=80, fps=60.0,
        )
        assert conf <= 0.40
        assert "outside" in reason.lower()

    def test_low_visibility_penalizes(self):
        plant = {
            "start_frame": 80, "end_frame": 95, "duration_ms": 250.0,
            "mean_y": 500.0, "mean_abs_vel": 5.0,
            "min_visibility": 0.4,
        }
        conf, _ = phase_debug.score_foot_plant_confidence(
            plant, [plant],
            velocity_eps=50.0, rot_onset=82, contact=110,
            foot_plant=80, fps=60.0,
        )
        assert conf <= 0.55

    def test_out_of_range_timing_penalizes(self):
        # foot_plant=0, contact=40 → 667 ms at 60 fps (>> 350 ms range max).
        # This is exactly the toe-tap blast-radius case: legacy detector
        # picks an early frame and foot_plant→contact balloons.
        plant = {
            "start_frame": 0, "end_frame": 20, "duration_ms": 350.0,
            "mean_y": 500.0, "mean_abs_vel": 5.0, "min_visibility": 0.95,
        }
        conf, reason = phase_debug.score_foot_plant_confidence(
            plant, [plant],
            velocity_eps=50.0, rot_onset=5, contact=40,
            foot_plant=0, fps=60.0,
        )
        assert conf <= 0.65, f"expected <=0.65 (out-of-range penalty), got conf={conf} reason={reason}"
        assert "out of range" in reason


class TestOtherConfidenceScorers:
    def test_contact_confidence_sharp_peak(self):
        v = np.zeros(60)
        v[30] = 10.0  # single sharp peak
        v[20:40] = np.linspace(0, 0, 20)
        v[30] = 10.0
        conf, _ = phase_debug.score_contact_confidence(
            v, contact=30, burst_lo=20, burst_hi=40,
        )
        assert conf >= 0.85

    def test_contact_confidence_low_prominence(self):
        v = np.full(60, 8.0)
        v[30] = 9.0
        conf, _ = phase_debug.score_contact_confidence(
            v, contact=30, burst_lo=20, burst_hi=40,
        )
        assert conf <= 0.50

    def test_launch_confidence_ordering_violation(self):
        conf, _ = phase_debug.score_launch_confidence(
            burst_lo=20, burst_hi=40,
            foot_plant=50, contact=60, launch=10,  # launch < foot_plant
        )
        assert conf < 0.5

    def test_load_start_confidence_clear_load(self):
        stride = np.concatenate([np.full(40, 5.0), np.linspace(5, 50, 40)])
        knee = np.concatenate([np.full(40, 175.0), np.linspace(175, 140, 40)])
        conf, _ = phase_debug.score_load_start_confidence(
            stride, knee, load_start=40, foot_plant=78, fps=60.0,
        )
        assert conf >= 0.85

    def test_rotation_onset_confidence_clean(self):
        v = np.zeros(60)
        for i in range(40, 51):
            v[i] = 10.0 * (i - 40) / 10
        conf, _ = phase_debug.score_rotation_onset_confidence(
            v, rot_onset=42, contact=50,
        )
        assert conf >= 0.70


# ---------------------------------------------------------------------------
# Alternatives + warnings
# ---------------------------------------------------------------------------


class TestAlternativesAndWarnings:
    def test_alternatives_ranks_by_closeness_to_onset(self):
        times = np.linspace(0, 2.0, 120)
        contacts = [
            {"start_frame": 20, "end_frame": 30, "duration_ms": 167.0,
             "mean_y": 500.0, "mean_abs_vel": 5.0, "min_visibility": 0.9},
            {"start_frame": 80, "end_frame": 100, "duration_ms": 333.0,
             "mean_y": 500.0, "mean_abs_vel": 3.0, "min_visibility": 0.9},
        ]
        # Selected foot_plant=20 (toe-tap); real plant at 80; rot_onset=90
        alts = phase_debug.build_alternatives(
            contacts, selected_foot_plant=20, times=times,
            rot_onset=90, fps=60.0,
        )
        assert len(alts) == 1
        assert alts[0]["frame"] == 80
        # Real-plant contact straddles rot_onset → confidence == 1.0
        assert alts[0]["confidence"] >= 0.9
        assert alts[0]["label"] == "alternative_final_plant"

    def test_warnings_fire_for_toe_tap_with_multiple_contacts(self):
        contacts = [
            {"start_frame": 20, "end_frame": 30, "duration_ms": 167.0,
             "mean_y": 500.0, "mean_abs_vel": 5.0, "min_visibility": 0.9},
            {"start_frame": 80, "end_frame": 100, "duration_ms": 333.0,
             "mean_y": 500.0, "mean_abs_vel": 3.0, "min_visibility": 0.9},
        ]
        # Simulate the legacy detector picking the tap as foot_plant
        warns = phase_debug.build_warnings(
            stride_style="toe_tap",
            foot_plant_conf=0.30,
            contacts=contacts,
            foot_plant=20,
            contact=110,
            fps=60.0,
            fa_visibility_window_min=0.85,
            handedness_ratio=1.5,
            edge_warnings=[],
        )
        codes = {w["code"] for w in warns}
        assert "multiple_foot_contacts" in codes
        assert "low_foot_plant_confidence" in codes
        assert "foot_plant_to_contact_too_long" in codes
        assert "toe_tap_suspected" in codes

    def test_warnings_fire_for_low_visibility(self):
        warns = phase_debug.build_warnings(
            stride_style="standard_stride",
            foot_plant_conf=0.8, contacts=[],
            foot_plant=50, contact=70, fps=60.0,
            fa_visibility_window_min=0.4,
            handedness_ratio=None, edge_warnings=[],
        )
        assert any(w["code"] == "poor_pose_visibility" for w in warns)

    def test_warnings_fire_for_contact_too_soon(self):
        warns = phase_debug.build_warnings(
            stride_style="standard_stride",
            foot_plant_conf=0.8, contacts=[],
            foot_plant=68, contact=70, fps=60.0,
            fa_visibility_window_min=0.9,
            handedness_ratio=None, edge_warnings=[],
        )
        codes = {w["code"] for w in warns}
        assert "contact_too_soon_after_foot_plant" in codes

    def test_handedness_warning(self):
        warns = phase_debug.build_warnings(
            stride_style="standard_stride",
            foot_plant_conf=0.9, contacts=[],
            foot_plant=50, contact=70, fps=60.0,
            fa_visibility_window_min=0.9,
            handedness_ratio=1.1,
            edge_warnings=[],
        )
        assert any(w["code"] == "low_handedness_confidence" for w in warns)

    def test_edge_warnings_passthrough(self):
        warns = phase_debug.build_warnings(
            stride_style="standard_stride",
            foot_plant_conf=0.9, contacts=[],
            foot_plant=50, contact=70, fps=60.0,
            fa_visibility_window_min=0.9,
            handedness_ratio=None,
            edge_warnings=["  ⚠  load_start at frame 1 (edge of video)  "],
        )
        edge = [w for w in warns if w["code"] == "phase_at_video_edge"]
        assert len(edge) == 1
        assert "load_start" in edge[0]["message"]


# ---------------------------------------------------------------------------
# Top-level build_debug_payload
# ---------------------------------------------------------------------------


class TestBuildDebugPayload:
    """End-to-end smoke test on a synthetic toe-tap swing."""

    def _build_payload_for_toe_tap(self):
        # Synthetic toe-tap swing — see _make_fa_y_toe_tap for frame layout.
        # Real foot plant is at frame 150; we simulate the legacy bug
        # locking foot_plant onto the tap touch (~frame 125) instead.
        n = 240
        fps = 60.0
        times = np.arange(n) / fps
        fa_y = _make_fa_y_toe_tap(n=n)
        vis_fa = np.ones(n) * 0.95
        # Hip velocity ramps up through the swing, peaks at contact=175
        hip_vel = np.zeros(n)
        for i in range(160, 176):
            hip_vel[i] = 10.0 * (i - 160) / 15.0
        for i in range(176, n):
            hip_vel[i] = max(0.0, 10.0 * math.exp(-(i - 175) / 8.0))
        # Stride extends through the load; knee loads from frame ~100 onwards
        stride = np.concatenate([np.full(100, 5.0),
                                  np.linspace(5, 40, 60),
                                  np.full(80, 40.0)])
        knee = np.concatenate([np.full(100, 175.0),
                                np.linspace(175, 145, 60),
                                np.full(80, 145.0)])
        # Legacy bug: foot_plant locked onto the tap touch (mid frame 115-134),
        # not the real final plant at frame 150+.
        phases = {
            "load_start": 90,
            "foot_plant": 125,    # ← legacy bug: tap mistaken for final plant
            "launch":     165,
            "contact":    175,
            "peak_rotation": 185,
            "finish":     215,
        }
        return phase_debug.build_debug_payload(
            times=times, fa_y=fa_y, vis_fa=vis_fa,
            hip_vel=hip_vel, stride=stride, knee=knee,
            phases=phases,
            burst_lo=165, burst_hi=195, burst_peak=175,
            fps=fps, torso_length_px=200.0,
            handedness="RIGHT", handedness_ratio=1.8,
            edge_warnings=[],
        )

    def test_returns_required_top_level_keys(self):
        p = self._build_payload_for_toe_tap()
        for key in (
            "schema_version", "feature_flag", "stride_style",
            "stride_style_confidence", "selected_phases",
            "foot_plant_candidates", "alternatives", "ground_model",
            "burst", "handedness", "warnings",
        ):
            assert key in p, f"missing key {key}"
        assert p["schema_version"] == "phase_debug_v1"
        assert p["feature_flag"] == "PHASE_DEBUG_V1"

    def test_classifies_toe_tap(self):
        p = self._build_payload_for_toe_tap()
        assert p["stride_style"] == "toe_tap", (
            f"Expected toe_tap, got {p['stride_style']} ({p['stride_style_reason']})"
        )

    def test_emits_per_phase_confidence(self):
        p = self._build_payload_for_toe_tap()
        for name in ("load_start", "foot_plant", "launch",
                     "contact", "rotation_onset"):
            assert name in p["selected_phases"]
            entry = p["selected_phases"][name]
            assert "frame" in entry and "time_s" in entry
            assert 0.0 <= entry["confidence"] <= 1.0
            assert isinstance(entry["reason"], str) and entry["reason"]

    def test_warns_about_toe_tap_and_long_contact(self):
        p = self._build_payload_for_toe_tap()
        codes = {w["code"] for w in p["warnings"]}
        # Legacy bug parks foot_plant on the tap → 750 ms to contact (>> 350)
        # and 3 stable contacts in the candidate window.
        assert "multiple_foot_contacts" in codes
        assert "toe_tap_suspected" in codes
        assert "foot_plant_to_contact_too_long" in codes

    def test_alternatives_surface_real_plant(self):
        p = self._build_payload_for_toe_tap()
        # The real plant (frame 150+) should appear as the top alternative
        assert len(p["alternatives"]) >= 1
        assert p["alternatives"][0]["frame"] > 125, (
            f"top alternative frame={p['alternatives'][0]['frame']} "
            "should be later than the mis-selected foot_plant=125"
        )

    def test_format_summary_is_nonempty(self):
        p = self._build_payload_for_toe_tap()
        s = phase_debug.format_debug_summary(p)
        assert "PHASE DEBUG V1" in s
        assert "stride_style" not in s.lower() or "toe_tap" in s.lower()
        assert "WARNINGS" in s


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
