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

    Inputs are already-smoothed arrays from detect_phases.py:
      - hip_vel: smoothed gradient of hip_rotation (deg/frame)
      - shoulder_rotation: baselined shoulder rotation (deg)

    Returns a dict with the 3 metric values + their per-frame anchors +
    a rating sub-dict that classifies each into good / marginal / poor.

    Returns None values where the metric is undefined (e.g. negligible
    shoulder rotation makes stability % meaningless).
    """
    raise NotImplementedError("filled in next task")
