# biomech.py
"""Power Sequence biomech compute layer.

Computes the 3 derived metrics introduced in the Power Sequence redesign,
from per-frame signals already produced by detect_phases.py:

  - M1 sequencing_lag_ms     — hip-peak → shoulder-peak gap (kinematic chain)
  - M2 peak_hip_omega_deg_s  — peak hip angular velocity (rotational power)
  - M3 front_side_stability_pct — % shoulder rotation done at launch (fly-out)

Pure-numpy, no mediapipe/opencv deps — testable in isolation (same pattern
as phase_burst.py). detect_phases.py imports `compute_sequence` and writes
its output into a `sequence` block on every fingerprint.

Spec: docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def _smooth(arr: np.ndarray, window: int = 5) -> np.ndarray:
    """Same moving-average smooth() used by detect_phases.py and phase_burst.py."""
    arr = np.asarray(arr, dtype=float)
    out = np.copy(arr)
    half = window // 2
    for i in range(len(arr)):
        lo = max(0, i - half)
        hi = min(len(arr), i + half + 1)
        out[i] = np.mean(arr[lo:hi])
    return out


def _search_window(load_start: int, contact: int, fps: float, n: int) -> tuple[int, int]:
    """The interval inside which we look for hip / shoulder peaks.

    200ms before load_start through 50ms after contact. This excludes
    post-contact follow-through from dominating the shoulder peak.
    """
    lo = max(0, int(load_start) - int(round(0.20 * fps)))
    hi = min(int(n), int(contact) + int(round(0.05 * fps)))
    if hi <= lo:                       # malformed phases — fall back to whole clip
        return 0, int(n)
    return lo, hi


def compute_sequence(
    *,
    hip_vel: np.ndarray,
    shoulder_rotation: np.ndarray,
    load_start: int,
    launch: int,
    contact: int,
    fps: float,
) -> dict:
    """Compute the Power Sequence block from per-frame signals.

    See module docstring + the design spec for full algorithm rationale.
    """
    hip_vel = np.asarray(hip_vel, dtype=float)
    shoulder_rotation = np.asarray(shoulder_rotation, dtype=float)
    n = min(len(hip_vel), len(shoulder_rotation))
    if n == 0 or fps <= 0:
        return {
            "sequencing_lag_ms":         None,
            "peak_hip_omega_deg_s":      None,
            "front_side_stability_pct":  None,
            "hip_peak_frame":            None,
            "shoulder_peak_frame":       None,
            "rating": {"sequencing_lag": None,
                       "peak_hip_omega": None,
                       "front_side_stability": None},
        }

    lo, hi = _search_window(load_start, contact, fps, n)

    # M1 — sequencing lag
    # Use forward difference (diff with prepend) rather than np.gradient so
    # that the peak of d/dt(cumsum(gaussian(t0))) falls exactly at t0 instead
    # of being split symmetrically across t0-1 and t0 by central differences.
    shoulder_vel = _smooth(np.diff(shoulder_rotation, prepend=shoulder_rotation[0]), window=5)
    hip_window = np.abs(hip_vel[lo:hi])
    sho_window = np.abs(shoulder_vel[lo:hi])
    hip_peak_frame = int(lo + np.argmax(hip_window)) if len(hip_window) else None
    sho_peak_frame = int(lo + np.argmax(sho_window)) if len(sho_window) else None
    sequencing_lag_ms: Optional[float] = None
    if hip_peak_frame is not None and sho_peak_frame is not None:
        sequencing_lag_ms = (sho_peak_frame - hip_peak_frame) * 1000.0 / fps

    return {
        "sequencing_lag_ms":         sequencing_lag_ms,
        "peak_hip_omega_deg_s":      None,
        "front_side_stability_pct":  None,
        "hip_peak_frame":            hip_peak_frame,
        "shoulder_peak_frame":       sho_peak_frame,
        "rating": {"sequencing_lag": None,
                   "peak_hip_omega": None,
                   "front_side_stability": None},
    }
