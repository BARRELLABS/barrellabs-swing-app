# tests/test_biomech.py
"""Power Sequence biomech compute layer — pure-numpy, no mediapipe dep.

Tests for the 3 new metrics introduced in the Power Sequence redesign:

  - M1 sequencing_lag_ms     (hip-peak → shoulder-peak in ms)
  - M2 peak_hip_omega_deg_s  (peak hip angular velocity)
  - M3 front_side_stability_pct  (% shoulder rotation done at launch)

See docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md
for the algorithms and rationale.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


class TestBiomechModuleExists:
    def test_module_imports(self):
        import biomech  # noqa: F401

    def test_exports_compute_sequence(self):
        from biomech import compute_sequence
        assert callable(compute_sequence)


class TestSequencingLag:
    """M1: hip-peak → shoulder-peak gap in milliseconds.

    Good band: 20-60 ms (pelvis leads, torso follows).
    Marginal: 5-20 ms or 60-80 ms.
    Poor: <= 5 ms (simultaneous) or negative (shoulders lead).
    """

    def _make_signals(self, *, n: int, hip_peak: int, shoulder_peak: int):
        """Build synthetic hip_vel + shoulder_rotation arrays.

        hip_vel: gaussian peak at hip_peak frame.
        shoulder_rotation: linearly rising to contact, but with the
          inflection (max gradient) at shoulder_peak frame.
        """
        x = np.arange(n, dtype=float)
        hip_vel = 10.0 * np.exp(-((x - hip_peak) ** 2) / (2.0 * 4.0 ** 2))
        # Cumulative sum of a gaussian peaked at shoulder_peak gives an
        # S-curve whose gradient peaks at shoulder_peak — exactly what we
        # need to test argmax(|gradient(shoulder_rotation)|).
        shoulder_pulse = np.exp(-((x - shoulder_peak) ** 2) / (2.0 * 4.0 ** 2))
        shoulder_rotation = np.cumsum(shoulder_pulse) * 5.0  # arbitrary deg scale
        return hip_vel, shoulder_rotation

    def test_good_lag_30ms_at_60fps(self):
        """Hip peak at 60, shoulder peak at 62 → 2 frames = 33.3 ms at 60fps."""
        from biomech import compute_sequence
        n = 200
        hip_vel, shoulder_rotation = self._make_signals(
            n=n, hip_peak=60, shoulder_peak=62,
        )
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 28.0 <= result["sequencing_lag_ms"] <= 38.0, (
            f"Expected ~33ms; got {result['sequencing_lag_ms']}"
        )

    def test_simultaneous_fire_zero_lag(self):
        """Hip + shoulder peak on same frame → ~0ms."""
        from biomech import compute_sequence
        n = 200
        hip_vel, shoulder_rotation = self._make_signals(
            n=n, hip_peak=60, shoulder_peak=60,
        )
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert abs(result["sequencing_lag_ms"]) <= 3.0

    def test_shoulders_lead_negative_lag(self):
        """Shoulder peak BEFORE hip peak → negative lag."""
        from biomech import compute_sequence
        n = 200
        hip_vel, shoulder_rotation = self._make_signals(
            n=n, hip_peak=62, shoulder_peak=58,
        )
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["sequencing_lag_ms"] < 0, (
            f"Expected negative; got {result['sequencing_lag_ms']}"
        )

    def test_search_window_ignores_followthrough(self):
        """A huge post-contact shoulder spike must NOT win — it's outside the
        downswing [launch - 50ms, contact + 100ms] window."""
        from biomech import compute_sequence
        n = 300
        x = np.arange(n, dtype=float)
        # Real hip peak at 60, real shoulder peak at 63 (32ms lag good).
        hip_vel = 10.0 * np.exp(-((x - 60) ** 2) / (2.0 * 4.0 ** 2))
        real_pulse = np.exp(-((x - 63) ** 2) / (2.0 * 4.0 ** 2))
        # MASSIVE follow-through shoulder pulse at frame 200, way after contact.
        followthrough_pulse = 100.0 * np.exp(-((x - 200) ** 2) / (2.0 * 4.0 ** 2))
        shoulder_rotation = np.cumsum(real_pulse + followthrough_pulse)
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        # If the search window worked, lag ≈ +50ms (3 frames at 60fps);
        # if it failed, lag would be huge (~140 frames = 2333ms).
        assert -100 <= result["sequencing_lag_ms"] <= 100, (
            f"search window leaked; got {result['sequencing_lag_ms']}ms"
        )

    def test_downswing_window_excludes_prepitch_noise(self):
        """A big pre-pitch hip-vel spike (waggle / leg-kick) BEFORE launch must
        not be picked as the hip peak — only the downswing counts. This is the
        long-broadcast-clip failure mode from calibration, where load_start sat
        far before contact and argmax locked onto pre-swing motion."""
        from biomech import compute_sequence
        n = 200
        x = np.arange(n, dtype=float)
        # Real downswing hip peak at 60 ...
        hip_vel = 8.0 * np.exp(-((x - 60) ** 2) / 32.0)
        # ... but a BIGGER pre-pitch spike at frame 35 (after load_start=40's
        # old window edge, before launch=58). The old [load_start-200ms, ...]
        # window included frame ~28+, so it would have picked 35.
        hip_vel += 20.0 * np.exp(-((x - 35) ** 2) / 32.0)
        shoulder_rotation = np.cumsum(np.exp(-((x - 63) ** 2) / 32.0)) * 5.0
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 56 <= result["hip_peak_frame"] <= 64, (
            f"pre-pitch noise leaked into hip peak; got {result['hip_peak_frame']}"
        )

    def test_subframe_interpolation_resolves_between_frames(self):
        """Lag resolution is finer than one frame thanks to parabolic
        sub-frame refinement: a true 1.5-frame gap (25ms at 60fps) should not
        snap to 1 or 2 whole frames (16.7 / 33.3 ms)."""
        from biomech import compute_sequence
        n = 200
        x = np.arange(n, dtype=float)
        hip_vel = 10.0 * np.exp(-((x - 60.0) ** 2) / 32.0)
        shoulder_pulse = np.exp(-((x - 61.5) ** 2) / 32.0)
        shoulder_rotation = np.cumsum(shoulder_pulse) * 5.0
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 19.0 <= result["sequencing_lag_ms"] <= 31.0, (
            f"expected ~25ms (sub-frame); got {result['sequencing_lag_ms']}"
        )


class TestPeakHipOmega:
    """M2: peak |hip_vel| × fps, in deg/s.

    Good band: ≥ 900 °/s.  Marginal: 600–900.  Poor: < 600.
    """

    def test_known_signal_yields_known_omega(self):
        """If hip_vel maxes at 15 deg/frame at 60 fps, peak_omega = 900 deg/s."""
        from biomech import compute_sequence
        n = 200
        x = np.arange(n, dtype=float)
        hip_vel = 15.0 * np.exp(-((x - 60) ** 2) / (2.0 * 4.0 ** 2))
        shoulder_rotation = np.cumsum(np.exp(-((x - 63) ** 2) / 32.0)) * 5.0
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 890.0 <= result["peak_hip_omega_deg_s"] <= 910.0

    def test_omega_uses_search_window(self):
        """Spike OUTSIDE the search window must not be picked."""
        from biomech import compute_sequence
        n = 300
        x = np.arange(n, dtype=float)
        # Real swing burst (10 deg/frame at 60 fps → 600 deg/s)
        hip_vel = 10.0 * np.exp(-((x - 60) ** 2) / 32.0)
        # MASSIVE post-contact spike (50 deg/frame → 3000 deg/s) — must be ignored
        hip_vel += 50.0 * np.exp(-((x - 200) ** 2) / 32.0)
        shoulder_rotation = np.cumsum(np.exp(-((x - 63) ** 2) / 32.0)) * 5.0
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        # If window works, omega ~600. If it leaks, omega ~3000.
        assert result["peak_hip_omega_deg_s"] <= 700.0

    def test_omega_zero_when_no_signal(self):
        """All-zero hip_vel → 0 deg/s."""
        from biomech import compute_sequence
        n = 200
        hip_vel = np.zeros(n)
        shoulder_rotation = np.zeros(n)
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=shoulder_rotation,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["peak_hip_omega_deg_s"] == 0.0


class TestFrontSideStability:
    """M3: % of shoulder rotation already complete at launch frame.

    Good: ≤ 25%.  Marginal: 25-45%.  Poor: ≥ 45%.
    Returns None when total shoulder rotation is < 5° (can't characterize).
    """

    def _shoulder_rot(self, *, n: int, launch_val: float, contact_val: float):
        """Linear ramp from 0 → launch_val at the launch frame,
        then launch_val → contact_val at the contact frame.
        """
        arr = np.zeros(n)
        launch, contact = 58, 70
        for i in range(n):
            if i <= launch:
                arr[i] = launch_val * (i / launch) if launch > 0 else 0
            elif i <= contact:
                arr[i] = launch_val + (contact_val - launch_val) * (i - launch) / (contact - launch)
            else:
                arr[i] = contact_val
        return arr

    def test_stays_closed_low_pct(self):
        """Shoulders barely moved at launch (10°), then opened to 90° at contact
        → 10/90 = 11%, good."""
        from biomech import compute_sequence
        n = 100
        result = compute_sequence(
            hip_vel=np.zeros(n),
            shoulder_rotation=self._shoulder_rot(n=n, launch_val=10.0, contact_val=90.0),
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 8.0 <= result["front_side_stability_pct"] <= 14.0

    def test_fly_out_high_pct(self):
        """Shoulders already at 50° at launch, only get to 80° by contact
        → 50/80 = 62%, poor."""
        from biomech import compute_sequence
        n = 100
        result = compute_sequence(
            hip_vel=np.zeros(n),
            shoulder_rotation=self._shoulder_rot(n=n, launch_val=50.0, contact_val=80.0),
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert 58.0 <= result["front_side_stability_pct"] <= 68.0

    def test_negligible_rotation_returns_none(self):
        """|shoulder_rotation[contact]| < 5° → None."""
        from biomech import compute_sequence
        n = 100
        result = compute_sequence(
            hip_vel=np.zeros(n),
            shoulder_rotation=self._shoulder_rot(n=n, launch_val=1.0, contact_val=3.0),
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["front_side_stability_pct"] is None

    def test_recoil_suppressed_returns_none(self):
        """Pathological case: shoulder at 100° at launch but only 50° at
        contact (recoiled) → 100/50 = 200%. The signal is non-monotonic to
        contact, so we can't characterize fly-out — suppress (None) rather
        than emit a fabricated pegged value."""
        from biomech import compute_sequence
        n = 100
        arr = np.zeros(n)
        arr[58] = 100.0
        arr[70] = 50.0
        for i in range(59, 70):
            arr[i] = 100.0 + (50.0 - 100.0) * (i - 58) / 12.0
        result = compute_sequence(
            hip_vel=np.zeros(n),
            shoulder_rotation=arr,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["front_side_stability_pct"] is None


class TestRatings:
    """The `rating` sub-dict maps each metric to 'good' / 'marginal' / 'poor'
    using the thresholds locked in the spec (§ The 3 new metrics)."""

    def test_sequencing_good_hips_lead(self):
        # Calibrated to 2D pose: non-negative lag = hips lead = good.
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(30.0) == "good"
        assert rate_sequencing_lag(0.0) == "good"
        assert rate_sequencing_lag(5.0) == "good"

    def test_sequencing_marginal_nearly_synced(self):
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(-10.0) == "marginal"
        assert rate_sequencing_lag(-49.0) == "marginal"

    def test_sequencing_poor_casting(self):
        # Strongly negative = shoulders fired first (casting).
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(-60.0) == "poor"
        assert rate_sequencing_lag(-120.0) == "poor"

    def test_sequencing_none_passes_through(self):
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(None) is None

    def test_omega_good_900plus(self):
        from biomech import rate_peak_hip_omega
        assert rate_peak_hip_omega(1000.0) == "good"
        assert rate_peak_hip_omega(900.0) == "good"

    def test_omega_marginal_600_to_900(self):
        from biomech import rate_peak_hip_omega
        assert rate_peak_hip_omega(750.0) == "marginal"

    def test_omega_poor_below_600(self):
        from biomech import rate_peak_hip_omega
        assert rate_peak_hip_omega(500.0) == "poor"

    def test_stability_good_under_25(self):
        from biomech import rate_front_side_stability
        assert rate_front_side_stability(15.0) == "good"
        assert rate_front_side_stability(25.0) == "good"

    def test_stability_marginal_25_to_45(self):
        from biomech import rate_front_side_stability
        assert rate_front_side_stability(35.0) == "marginal"

    def test_stability_poor_45plus(self):
        from biomech import rate_front_side_stability
        assert rate_front_side_stability(60.0) == "poor"

    def test_compute_sequence_populates_rating_dict(self):
        """End-to-end: feed real-shaped inputs, verify rating dict is filled."""
        from biomech import compute_sequence
        n = 200
        x = np.arange(n, dtype=float)
        hip_vel = 15.0 * np.exp(-((x - 60) ** 2) / 32.0)
        rot = np.zeros(n)
        for i in range(n):
            if i <= 58: rot[i] = 10.0 * (i / 58)
            elif i <= 70: rot[i] = 10.0 + 80.0 * (i - 58) / 12.0
            else: rot[i] = 90.0
        result = compute_sequence(
            hip_vel=hip_vel, shoulder_rotation=rot,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["rating"]["sequencing_lag"] in {"good", "marginal", "poor"}
        assert result["rating"]["peak_hip_omega"] in {"good", "marginal", "poor"}
        assert result["rating"]["front_side_stability"] in {"good", "marginal", "poor"}


class TestDetectPhasesIntegration:
    """Loose integration test: confirms the sequence block survives a
    detect_phases.py write-and-read cycle. Skipped when no cached
    fingerprints exist."""

    def test_recent_fingerprint_has_sequence_block(self):
        """Any fingerprint in validation/results/ should have the block."""
        from pathlib import Path
        import json
        project = Path(__file__).resolve().parent.parent
        fps = sorted((project / "validation/results").glob("*_fingerprint.json"))
        if not fps:
            pytest.skip("no cached fingerprints to test against")
        for fp_path in fps[:5]:
            data = json.load(open(fp_path))
            if "sequence" not in data:
                pytest.skip(f"{fp_path.name} pre-dates Power Sequence — "
                             "re-run detect_phases.py to refresh")
            seq = data["sequence"]
            assert "rating" in seq
            for k in ("sequencing_lag", "peak_hip_omega", "front_side_stability"):
                assert k in seq["rating"]
