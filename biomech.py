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


def _search_window(launch: int, contact: int, fps: float, n: int) -> tuple[int, int]:
    """The downswing interval inside which we look for hip / shoulder peaks.

    [launch - 50ms, contact + 100ms]. Anchoring to ``launch`` (the burst
    leading edge — when the hips fire) instead of ``load_start`` is the key
    robustness fix: ``load_start`` can sit ~1s before contact, so the old
    window swallowed pre-pitch waggle / leg-kick motion, and ``argmax`` then
    locked onto that noise on long broadcast clips (the calibration bug where
    pro clips returned −1000ms lags). The downswing is where hip and shoulder
    angular velocity actually peak. The small 50ms lead lets a genuine
    early-shoulder (out-of-sequence) peak register as interior rather than as a
    window-edge artifact; the 100ms trail covers shoulder peaks that lag the
    hips by up to the marginal band.
    """
    lo = max(0, int(launch) - int(round(0.05 * fps)))
    hi = min(int(n), int(contact) + int(round(0.10 * fps)))
    if hi - lo < 3:                    # malformed/too-short — fall back to clip
        return 0, int(n)
    return lo, hi


def _subframe_peak(arr: np.ndarray, k: int, lo: int, hi: int) -> float:
    """Parabolic sub-frame refinement of an integer ``argmax`` at index ``k``.

    Fits a parabola through (k-1, k, k+1) and returns the vertex position as a
    float frame index — removing the 1000/fps ms quantization that made the
    raw lag cluster on exact frame multiples. Falls back to ``k`` when the peak
    sits at the window boundary or the local curvature is flat/convex
    (no well-defined interior vertex).
    """
    if k <= lo or k >= hi - 1 or k <= 0 or k >= len(arr) - 1:
        return float(k)
    y0, y1, y2 = float(arr[k - 1]), float(arr[k]), float(arr[k + 1])
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-9:
        return float(k)
    delta = 0.5 * (y0 - y2) / denom
    if delta < -0.5 or delta > 0.5:    # not a concave-down peak here
        return float(k)
    return float(k) + delta


def rate_sequencing_lag(ms: Optional[float]) -> Optional[str]:
    """Categorical kinetic-chain rating, calibrated to the 2D-pose measurement.

    Textbook elite sequencing lag is ~20-60ms (pelvis leads torso), but a
    single-camera 2D estimate systematically compresses the magnitude toward
    zero. Calibrated on a pro-vs-amateur set, the reliable signal is the
    DIRECTION, not a precise millisecond: pros cluster at/above zero (hips
    lead), amateurs sit strongly negative (shoulders fire first = casting).
    So we rate directionally and surface it categorically — never as a
    false-precise ms. (When Barrel Lock sensors give a true ms, revert to the
    textbook bands.)
        good     — hips lead             (lag >= 0)
        marginal — nearly synced         (-50 <= lag < 0)
        poor     — shoulders fire early  (lag < -50)
    """
    if ms is None:
        return None
    if ms >= 0.0:
        return "good"
    if ms >= -50.0:
        return "marginal"
    return "poor"


def rate_peak_hip_omega(deg_s: Optional[float]) -> Optional[str]:
    """Good: >= 900 deg/s. Marginal: 600-900. Poor: < 600."""
    if deg_s is None:
        return None
    if deg_s >= 900.0:
        return "good"
    if deg_s >= 600.0:
        return "marginal"
    return "poor"


def rate_front_side_stability(pct: Optional[float]) -> Optional[str]:
    """Good: <= 25%. Marginal: 25-45%. Poor: >= 45%. Lower is better."""
    if pct is None:
        return None
    if pct <= 25.0:
        return "good"
    if pct < 45.0:
        return "marginal"
    return "poor"


def compute_sequence(
    *,
    hip_vel: np.ndarray,
    shoulder_rotation: np.ndarray,
    load_start: int,
    launch: int,
    contact: int,
    fps: float,
    slow_mo_factor: float = 1.0,
) -> dict:
    """Compute the Power Sequence block from per-frame signals.

    `slow_mo_factor` (>1 for high-capture-FPS slow-mo clips) divides the
    sequencing lag back to real-time-equivalent ms, consistent with
    timing_ms_corrected — otherwise a slow-mo clip's lag inflates ~Nx and the
    rating (thresholded at -50 ms) wrongly tanks the Sequence pillar.

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

    lo, hi = _search_window(launch, contact, fps, n)

    # M1 — sequencing lag (downswing window only)
    # Use forward difference (diff with prepend) rather than np.gradient so
    # that the peak of d/dt(cumsum(gaussian(t0))) falls exactly at t0 instead
    # of being split symmetrically across t0-1 and t0 by central differences.
    shoulder_vel = _smooth(np.diff(shoulder_rotation, prepend=shoulder_rotation[0]), window=5)
    hip_abs = np.abs(hip_vel)
    sho_abs = np.abs(shoulder_vel)
    hip_window = hip_abs[lo:hi]
    sho_window = sho_abs[lo:hi]
    hip_peak_frame = int(lo + np.argmax(hip_window)) if len(hip_window) else None
    sho_peak_frame = int(lo + np.argmax(sho_window)) if len(sho_window) else None
    sequencing_lag_ms: Optional[float] = None
    if hip_peak_frame is not None and sho_peak_frame is not None:
        # Sub-frame parabolic refinement removes the 1000/fps ms quantization
        # that made raw lags cluster on exact frame multiples.
        hip_pos = _subframe_peak(hip_abs, hip_peak_frame, lo, hi)
        sho_pos = _subframe_peak(sho_abs, sho_peak_frame, lo, hi)
        _sm = slow_mo_factor if slow_mo_factor and slow_mo_factor > 0 else 1.0
        sequencing_lag_ms = (sho_pos - hip_pos) * 1000.0 / fps / _sm

    # M2 — peak hip angular velocity (within the downswing window)
    if len(hip_window):
        peak_hip_omega_deg_s = float(np.max(hip_window)) * fps
    else:
        peak_hip_omega_deg_s = None

    # M3 — front-side stability (% shoulder rotation done at launch).
    # SUPPRESS (return None) rather than clamp when the value is implausible:
    # a result outside roughly [-20%, 120%] means the shoulder-rotation signal
    # is non-monotonic to contact (noise / mis-indexed contact frame), so we
    # genuinely can't characterize fly-out — emitting a pegged "150% / poor"
    # would be fabricating a reading. Better to show nothing.
    front_side_stability_pct: Optional[float] = None
    if 0 <= int(launch) < n and 0 <= int(contact) < n:
        total_to_contact = float(shoulder_rotation[int(contact)])
        done_at_launch = float(shoulder_rotation[int(launch)])
        if abs(total_to_contact) >= 5.0:
            raw_pct = 100.0 * done_at_launch / total_to_contact
            if -20.0 <= raw_pct <= 120.0:
                front_side_stability_pct = float(raw_pct)

    rating = {
        "sequencing_lag":        rate_sequencing_lag(sequencing_lag_ms),
        "peak_hip_omega":        rate_peak_hip_omega(peak_hip_omega_deg_s),
        "front_side_stability":  rate_front_side_stability(front_side_stability_pct),
    }

    return {
        "sequencing_lag_ms":         sequencing_lag_ms,
        "peak_hip_omega_deg_s":      peak_hip_omega_deg_s,
        "front_side_stability_pct":  front_side_stability_pct,
        "hip_peak_frame":            hip_peak_frame,
        "shoulder_peak_frame":       sho_peak_frame,
        "rating":                    rating,
    }


def stride_direction(front_ankle_x, back_ankle_x, stance_idx, foot_plant_idx,
                     torso_px, eps=0.04):
    """Did the front foot stride toward the pitcher?

    Pitcher side = sign(front − back ankle x at stance). A real stride moves
    the front foot further toward that side by foot plant. `dx_norm` is the
    signed forward displacement in torso lengths (positive = toward pitcher).
    Fail-soft to the lenient gate (toward_pitcher=True, dx_norm=0.0) on
    degenerate input so a bad camera read never unfairly punishes the brace.
    """
    n = len(front_ankle_x)
    if (n == 0 or len(back_ankle_x) != n or torso_px is None or torso_px <= 1.0
            or not (0 <= stance_idx < n) or not (0 <= foot_plant_idx < n)):
        return {"toward_pitcher": True, "dx_norm": 0.0}

    def _avg(arr, i, w=2):
        lo, hi = max(0, i - w), min(len(arr), i + w + 1)
        seg = arr[lo:hi]
        return float(sum(seg) / len(seg)) if seg else float(arr[i])

    fx_stance = _avg(front_ankle_x, stance_idx)
    bx_stance = _avg(back_ankle_x, stance_idx)
    fx_plant = _avg(front_ankle_x, foot_plant_idx)
    pitcher_side = 1.0 if (fx_stance - bx_stance) >= 0 else -1.0
    dx_norm = ((fx_plant - fx_stance) * pitcher_side) / torso_px
    return {"toward_pitcher": bool(dx_norm > eps), "dx_norm": float(dx_norm)}
