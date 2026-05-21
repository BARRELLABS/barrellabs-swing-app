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
