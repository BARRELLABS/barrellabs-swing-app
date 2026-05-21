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
        """A huge post-contact shoulder spike must NOT win — it's
        outside the [load_start - 200ms, contact + 50ms] window."""
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
