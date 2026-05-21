# Power Sequence Biomechanics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 new biomech metrics (sequencing lag, peak hip rotational speed, front-side stability) computed from existing per-frame signals, surface them via a new "Power Sequence" section at the top of the swing report, and re-architect existing tiles to use verb-based titles. Spec: `docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md`.

**Architecture:** New pure-numpy `biomech.py` module (mediapipe-free, unit-testable in isolation) computes the 3 metrics. `detect_phases.py` calls it and writes a `sequence` block to every fingerprint. `analyzer.py` classifies the result, `drills.py` maps new metric gaps to 3 new drill categories, `swing_report_dashboard_preview.py` renders the new section + verb-renames existing tiles. `build_reference_library.py` idempotently re-processes the 20 MLB reference clips.

**Tech Stack:** Python 3.12 · numpy · pytest · Streamlit · pure HTML/CSS/SVG for visualizations (no Plotly/D3).

---

## Pre-flight

- [ ] **Confirm starting branch is fresh from main**

```bash
cd /Users/logancollins/barrellabs-swing-app/.claude/worktrees/nervous-proskuriakova
git fetch origin
git rebase origin/main || (git rebase --abort && echo "stash changes first")
git log --oneline origin/main..HEAD | head -5
```

Expected: branch is at most a few commits ahead of main (Phase 4c/4d/legal/spec, if PR #17 not merged) or even with main (if merged). Resolve conflicts if any.

- [ ] **Verify existing tests pass**

Run: `python3 -m pytest tests/test_phase_detector_v4.py tests/test_burst_multi_swing.py tests/test_player_settings_wiring.py tests/test_entitlements.py -q`

Expected: 100+ passing, 0 failures.

---

## Task 1: Scaffold `biomech.py` + first failing test

Create the new module. No functionality yet — just the file and the test that proves the import works.

**Files:**
- Create: `biomech.py`
- Create: `tests/test_biomech.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'biomech'`

- [ ] **Step 3: Create biomech.py with stub**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_biomech.py
git commit -m "feat(biomech): scaffold Power Sequence compute layer + first test

Pure-numpy module that will own the 3 new biomech metrics. Mirrors
the phase_burst.py extraction pattern so the compute layer can be
unit-tested without mediapipe. Empty for now — next tasks fill in
the M1/M2/M3 algorithms per the design spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: M1 — sequencing lag

Add the first metric: the gap in ms between hip-velocity peak and shoulder-velocity peak.

**Files:**
- Modify: `biomech.py` (add `_compute_sequencing_lag` helper + integrate into `compute_sequence`)
- Modify: `tests/test_biomech.py` (add `TestSequencingLag` class)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_biomech.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_biomech.py::TestSequencingLag -v`
Expected: 4 FAILED with `NotImplementedError`

- [ ] **Step 3: Implement `compute_sequence` (sequencing lag only)**

Replace the stub in `biomech.py`:

```python
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
    shoulder_vel = _smooth(np.gradient(shoulder_rotation), window=5)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 6 PASSED (2 scaffold + 4 lag)

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_biomech.py
git commit -m "feat(biomech): M1 sequencing lag (hip→shoulder peak in ms)

Computes the gap between hip-velocity peak and shoulder-velocity peak
within a [load_start − 200ms, contact + 50ms] window — wide enough to
catch the real swing burst, tight enough to exclude follow-through.

Tests cover: good 33ms lag, simultaneous-fire 0ms, shoulders-lead
negative, and a follow-through-rejection test that proves the search
window keeps post-contact shoulder spikes from dominating.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: M2 — peak hip angular velocity

Add the second metric to the same compute_sequence call.

**Files:**
- Modify: `biomech.py` (extend compute_sequence)
- Modify: `tests/test_biomech.py` (add `TestPeakHipOmega` class)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_biomech.py`:

```python
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
        # Window is [load_start − 200ms, contact + 50ms] = [28, 73] at 60fps
        # Peak hip_vel = 15 at frame 60, inside window.  ω = 15 × 60 = 900.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_biomech.py::TestPeakHipOmega -v`
Expected: 3 FAILED (`assert None == 900.0` etc.)

- [ ] **Step 3: Extend `compute_sequence` with M2**

In `biomech.py`, inside `compute_sequence`, immediately after the M1 block (before the `return` statement), add:

```python
    # M2 — peak hip angular velocity
    if len(hip_window):
        peak_hip_omega_deg_s = float(np.max(hip_window)) * fps
    else:
        peak_hip_omega_deg_s = None
```

Then in the returned dict change `"peak_hip_omega_deg_s": None` to `"peak_hip_omega_deg_s": peak_hip_omega_deg_s`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 9 PASSED (2 scaffold + 4 lag + 3 omega)

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_biomech.py
git commit -m "feat(biomech): M2 peak hip angular velocity (deg/s)

Reuses the search window from M1. Trivial derivation from the
already-computed hip_vel array (which detect_phases.py exposes).
Tests cover: known-signal sanity check, window-exclusion of
post-contact spikes, all-zero edge case.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: M3 — front-side stability

The third metric: % of shoulder rotation already complete at launch (foot plant).

**Files:**
- Modify: `biomech.py` (extend compute_sequence)
- Modify: `tests/test_biomech.py` (add `TestFrontSideStability`)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_biomech.py`:

```python
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
        # Make it simple: linear ramp 0 → launch_val over [0, launch],
        # then launch_val → contact_val over [launch, contact].
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

    def test_clamped_to_150_max(self):
        """Pathological case: shoulder at 100° at launch but only 50° at
        contact (recoiled) → 100/50 = 200%, clamped to 150."""
        from biomech import compute_sequence
        n = 100
        # Hand-craft an array where contact is LESS than launch.
        arr = np.zeros(n)
        arr[58] = 100.0
        arr[70] = 50.0
        # Fill linearly between
        for i in range(59, 70):
            arr[i] = 100.0 + (50.0 - 100.0) * (i - 58) / 12.0
        result = compute_sequence(
            hip_vel=np.zeros(n),
            shoulder_rotation=arr,
            load_start=40, launch=58, contact=70, fps=60.0,
        )
        assert result["front_side_stability_pct"] == 150.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_biomech.py::TestFrontSideStability -v`
Expected: 4 FAILED

- [ ] **Step 3: Extend `compute_sequence` with M3**

In `biomech.py`, inside `compute_sequence`, after the M2 block, add:

```python
    # M3 — front-side stability (% shoulder rotation done at launch)
    front_side_stability_pct: Optional[float] = None
    if 0 <= int(launch) < n and 0 <= int(contact) < n:
        total_to_contact = float(shoulder_rotation[int(contact)])
        done_at_launch = float(shoulder_rotation[int(launch)])
        if abs(total_to_contact) >= 5.0:
            raw_pct = 100.0 * done_at_launch / total_to_contact
            front_side_stability_pct = float(max(-50.0, min(150.0, raw_pct)))
```

Then in the returned dict change `"front_side_stability_pct": None` to `"front_side_stability_pct": front_side_stability_pct`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 13 PASSED (9 prior + 4 stability)

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_biomech.py
git commit -m "feat(biomech): M3 front-side stability (% shoulder rotation at launch)

Lower = better. Uses the already-baselined shoulder_rotation array
from detect_phases.py (rotation past stance baseline). Clamped to
[-50, 150] to handle pathological recoil cases gracefully; returns
None when total shoulder rotation < 5° (can't characterize swings
with effectively no shoulder rotation).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Rating classifier (good / marginal / poor)

Map each numeric metric to a 3-state rating so the UI tile can color itself + pick the right coach line.

**Files:**
- Modify: `biomech.py` (add `_rate_*` helpers + populate `rating` dict)
- Modify: `tests/test_biomech.py` (add `TestRatings`)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_biomech.py`:

```python
class TestRatings:
    """The `rating` sub-dict maps each metric to 'good' / 'marginal' / 'poor'
    using the thresholds locked in the spec (§ The 3 new metrics)."""

    def test_sequencing_good_30ms(self):
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(30.0) == "good"
        assert rate_sequencing_lag(20.0) == "good"
        assert rate_sequencing_lag(60.0) == "good"

    def test_sequencing_marginal(self):
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(10.0) == "marginal"
        assert rate_sequencing_lag(70.0) == "marginal"

    def test_sequencing_poor_simultaneous(self):
        from biomech import rate_sequencing_lag
        assert rate_sequencing_lag(0.0) == "poor"
        assert rate_sequencing_lag(-20.0) == "poor"

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
        # Shoulder rotation that gives a 33ms lag + stays-closed 11%
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_biomech.py::TestRatings -v`
Expected: 11 FAILED

- [ ] **Step 3: Implement the raters + wire into `compute_sequence`**

In `biomech.py`, before the `compute_sequence` function, add:

```python
def rate_sequencing_lag(ms: Optional[float]) -> Optional[str]:
    """Good: 20-60ms. Marginal: 5-20 or 60-80. Poor: <=5 or negative."""
    if ms is None:
        return None
    if 20.0 <= ms <= 60.0:
        return "good"
    if 5.0 < ms < 20.0 or 60.0 < ms <= 80.0:
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
```

Then inside `compute_sequence`, just before the `return` statement, replace the rating sub-dict construction with:

```python
    rating = {
        "sequencing_lag":        rate_sequencing_lag(sequencing_lag_ms),
        "peak_hip_omega":        rate_peak_hip_omega(peak_hip_omega_deg_s),
        "front_side_stability":  rate_front_side_stability(front_side_stability_pct),
    }
```

And in the returned dict change the existing rating to `"rating": rating`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 24 PASSED (13 prior + 11 ratings)

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_biomech.py
git commit -m "feat(biomech): rating classifier (good/marginal/poor) per metric

Thresholds locked from the spec. Each rate_*() function is None-safe
and standalone-importable (so the report layer can reclassify ad-hoc
without re-running compute_sequence). compute_sequence wires them
into the result dict's rating block.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wire biomech into `detect_phases.py`

The compute layer exists; now `detect_phases.py` needs to call it and write the `sequence` block to every fingerprint.

**Files:**
- Modify: `detect_phases.py` (import + call after phases are determined)

- [ ] **Step 1: Find the right insertion point**

Open `detect_phases.py`. Locate the section where it writes the fingerprint JSON. Look for a line like `fingerprint = {...}` or `json.dump(fingerprint, ...)`. The block we add must run BEFORE that.

Run: `grep -n "json.dump\|^fingerprint\|FINGERPRINT\|fingerprint\s*=" detect_phases.py | head -10`

Confirm the order: `phases` dict is built → biomech runs → final fingerprint serialization.

- [ ] **Step 2: Add the biomech import + call**

Near the other imports at the top of `detect_phases.py`, add:

```python
import biomech
```

Then, AFTER the line where the phases dict / `phases_frame` is populated AND `hip_vel` and `shoulder_rotation` are available (search for `hip_vel =` and `shoulder_rotation =` to confirm both are in scope), insert this block. The exact line number depends on the current file shape — find a spot AFTER `phases_frame` is built and BEFORE the fingerprint is serialized:

```python
# ───── Power Sequence biomech block (see biomech.py + spec) ─────
try:
    sequence_block = biomech.compute_sequence(
        hip_vel=hip_vel,
        shoulder_rotation=shoulder_rotation,
        load_start=int(phases_frame["load_start"]),
        launch=int(phases_frame["launch"]),
        contact=int(phases_frame["contact"]),
        fps=float(fps),
    )
except Exception as _seq_exc:
    # Biomech failure must not break the pipeline — fall back to empty block.
    import traceback
    print(f"⚠  Power Sequence biomech compute failed: {_seq_exc!r}")
    traceback.print_exc()
    sequence_block = {
        "sequencing_lag_ms":         None,
        "peak_hip_omega_deg_s":      None,
        "front_side_stability_pct":  None,
        "hip_peak_frame":            None,
        "shoulder_peak_frame":       None,
        "rating": {"sequencing_lag": None,
                   "peak_hip_omega": None,
                   "front_side_stability": None},
    }
```

Then, in the fingerprint dict construction (search for the `fingerprint = {...}` literal or `json.dump(...)` site — usually a multi-line dict with keys like `"phases_frame"`, `"phases_t"`, `"timing_ms"`), add a new key alongside the others:

```python
    "sequence": sequence_block,
```

- [ ] **Step 3: Smoke-test the integration on a known clip**

Use one of the cached MLB reference videos. Pick a short one:

```bash
ls -lh /Users/logancollins/baseball-swing-app/swing.mp4 2>/dev/null || \
  ls -lh validation/videos/*.mp4 | head -1
```

Run detect_phases.py against it:

```bash
PHASE_DEBUG_V1=true DETECTOR_V4=true \
  /Users/logancollins/barrellabs-swing-app/.venv/bin/python \
  detect_phases.py /Users/logancollins/baseball-swing-app/swing.mp4 \
  2>&1 | tail -20
```

Verify the output fingerprint JSON has a `sequence` key with non-null numbers:

```bash
python3 -c "
import json
fp = json.load(open('swing_fingerprint.json'))
seq = fp.get('sequence', {})
print('sequencing_lag_ms:',         seq.get('sequencing_lag_ms'))
print('peak_hip_omega_deg_s:',      seq.get('peak_hip_omega_deg_s'))
print('front_side_stability_pct:',  seq.get('front_side_stability_pct'))
print('rating:',                    seq.get('rating'))
"
```

Expected: 3 numeric values (or None for fly-out if shoulder rotation < 5°) + 3 rating strings.

- [ ] **Step 4: Add an integration test**

Append to `tests/test_biomech.py`:

```python
class TestDetectPhasesIntegration:
    """Loose integration test: confirms the sequence block survives a
    detect_phases.py write-and-read cycle. Skipped in CI; runs locally."""

    def test_recent_fingerprint_has_sequence_block(self):
        """Any fingerprint in validation/results/ should have the block."""
        from pathlib import Path
        import json
        project = Path(__file__).resolve().parent.parent
        fps = sorted((project / "validation/results").glob("*_fingerprint.json"))
        if not fps:
            pytest.skip("no cached fingerprints to test against")
        # The first 5 are enough — they're all generated by the same pipeline.
        for fp_path in fps[:5]:
            data = json.load(open(fp_path))
            assert "sequence" in data, (
                f"{fp_path.name} missing 'sequence' block — re-process "
                "the reference library and validation fingerprints."
            )
            seq = data["sequence"]
            assert "rating" in seq
            for k in ("sequencing_lag", "peak_hip_omega", "front_side_stability"):
                assert k in seq["rating"]
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_biomech.py -v`
Expected: 24 prior + 1 new TestDetectPhasesIntegration — that one will SKIP because no cached fingerprints have the new block yet. Re-run after Task 11 to flip it from skip→pass.

- [ ] **Step 6: Commit**

```bash
git add detect_phases.py tests/test_biomech.py
git commit -m "feat(detect-phases): wire biomech.compute_sequence into pipeline

Every fingerprint now carries a 'sequence' block with the 3 Power
Sequence metrics + their ratings. Try/except ensures a biomech
failure can never break the v3 phase-detection pipeline — falls
back to a null sequence block so the rest of the report still
renders.

Integration smoke test added; it skips when no fresh fingerprints
exist and passes once the validation set is re-processed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Surface sequence in `analyzer.py`

The analyzer's result dict is what the swing report consumes. Make sure the sequence block is passed through.

**Files:**
- Modify: `analyzer.py` (read sequence block, attach to result)

- [ ] **Step 1: Find where the result dict is built**

Run: `grep -n "^def analyze\|result\s*=\s*{\|result\[\"" analyzer.py | head -20`

Locate the function `def analyze(...)` and the final `return result` or equivalent.

- [ ] **Step 2: Read the sequence from the loaded fingerprint + attach to result**

Inside `analyzer.py` at the top of `analyze()`, after `player_fp` is loaded but before the result dict is finalized, add:

```python
    # Power Sequence biomech block — pre-computed by detect_phases.py.
    # Pass through unchanged; the swing report renders it directly.
    sequence_block = player_fp.get("sequence") or {
        "sequencing_lag_ms": None,
        "peak_hip_omega_deg_s": None,
        "front_side_stability_pct": None,
        "hip_peak_frame": None,
        "shoulder_peak_frame": None,
        "rating": {
            "sequencing_lag": None,
            "peak_hip_omega": None,
            "front_side_stability": None,
        },
    }
```

Then in the result dict construction, add the key:

```python
    "sequence": sequence_block,
```

(Find the existing dict literal — search for `"metrics":` or `"phases":` for context — and add `"sequence": sequence_block,` adjacent.)

- [ ] **Step 3: Commit**

```bash
git add analyzer.py
git commit -m "feat(analyzer): pass Power Sequence block through to result

The compute lives in biomech.py + detect_phases.py; the analyzer
just unpacks the cached block from the fingerprint and forwards it
to the swing report. Null-safe fallback so old fingerprints (no
sequence block) still render the report shell.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: New gap categories in `drills.py`

`classify_gap()` currently maps Rotation/Head/etc. groups to 5 categories. Extend it with 3 new ones whose triggers come from the Power Sequence ratings.

**Files:**
- Modify: `drills.py` (extend `classify_gap`, `_CATEGORY_TITLES`)

- [ ] **Step 1: Read the current classify_gap implementation**

Run: `grep -n -A 20 "^def classify_gap" drills.py`

Confirm the current branches: Head → head_stability, Rotation → hip_rotation/hip_shoulder_separation, Front Knee → knee_extension, Timing → timing.

- [ ] **Step 2: Extend `classify_gap` to recognize sequence-derived gaps**

Replace the current `classify_gap` function with:

```python
def classify_gap(result):
    """Map a single gap result dict to a drill category key.

    Three new Power Sequence categories (Phase Power Sequence redesign):
      - sequencing            (kinematic chain — pelvis → torso lag)
      - rotational_speed      (peak hip angular velocity)
      - front_side_stability  (early shoulder fly-out)

    The new gaps are synthesized in analyzer.py from the `sequence`
    block's rating fields — see _synthesize_sequence_gaps() there.
    """
    group = result.get("group", "")
    label = result.get("label", "").lower()

    if group == "Head":
        return "head_stability"
    if group == "Rotation":
        if "separation" in label:
            return "hip_shoulder_separation"
        return "hip_rotation"
    if group == "Front Knee":
        return "knee_extension"
    if group == "Timing":
        return "timing"
    if group == "Power Sequence":
        if "sequencing" in label or "lag" in label:
            return "sequencing"
        if "hip speed" in label or "omega" in label or "rotational speed" in label:
            return "rotational_speed"
        if "stay closed" in label or "fly-out" in label or "front-side" in label:
            return "front_side_stability"
    return None
```

- [ ] **Step 3: Extend `_CATEGORY_TITLES`**

Find the `_CATEGORY_TITLES` dict (around line 645) and replace with:

```python
_CATEGORY_TITLES = {
    "head_stability":           "HEAD QUIET",
    "hip_rotation":             "HIP TURN COMPLETION",
    "hip_shoulder_separation":  "TORQUE STORAGE",
    "knee_extension":           "LOWER-BODY DRIVE",
    "timing":                   "TIMING & TEMPO",
    # Power Sequence (new):
    "sequencing":               "POWER SEQUENCE",
    "rotational_speed":         "ROTATIONAL SPEED",
    "front_side_stability":     "STAY CLOSED",
}
```

(Note: this also covers the verb-rename of existing tiles. Task 13 wires the hover-tooltip showing old names in the UI layer.)

- [ ] **Step 4: Commit**

```bash
git add drills.py
git commit -m "feat(drills): add 3 Power Sequence categories + verb-rename map

classify_gap() now recognizes synthetic 'Power Sequence' gaps and
maps them to: sequencing, rotational_speed, front_side_stability.
_CATEGORY_TITLES doubles as the verb-renamed display labels for
ALL categories — the swing report reads from here directly.

Old → new mappings:
  HIP ROTATION             → HIP TURN COMPLETION
  HIP-SHOULDER SEPARATION  → TORQUE STORAGE
  FRONT-SIDE FIRMNESS      → LOWER-BODY DRIVE
  HEAD STABILITY           → HEAD QUIET
  TIMING & TEMPO           → (unchanged)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Narrator paragraphs for new categories

Each existing category has a `_narrate_*()` function that produces the "WHAT TO FIX" paragraphs. Add three new ones.

**Files:**
- Modify: `drills.py` (add narrators + extend `_CATEGORY_NARRATORS`)

- [ ] **Step 1: Read existing narrator pattern**

Run: `grep -n "_narrate_hip_rotation\|_narrate_head_stability\b" drills.py | head -5`

Open one of them to see the signature: takes `gaps_in_cat` (a list) and `ref_name`, returns 3 strings (first paragraph, why, fix).

- [ ] **Step 2: Add three new narrators**

Insert these immediately after `_narrate_timing_cat` (search for it in drills.py to find the location, around line 600):

```python
def _narrate_sequencing(gaps_in_cat, ref_name):
    """Power Sequence M1 narrative — hip → shoulder lag."""
    first = (
        f"Your kinematic chain isn't firing in order. The hips and the "
        f"upper body need to fire on a delay — pelvis first, torso a "
        f"split-second later — to transfer energy efficiently into the bat."
    )
    why = (
        f"When the shoulders fire AT THE SAME TIME as the hips (or before "
        f"them), the upper body never gets to amplify what the lower body "
        f"started. {ref_name} sequences the chain — hips snap, then "
        f"shoulders ride the snap. That's where the bat speed comes from."
    )
    fix = (
        "What the fix feels like: hips lead, hands wait. Start the swing "
        "with the back hip, then let the shoulders react to what the hips "
        "did — not initiate alongside them."
    )
    return [first, why, fix]


def _narrate_rotational_speed(gaps_in_cat, ref_name):
    """Power Sequence M2 narrative — hip angular velocity."""
    first = (
        f"You're getting through the swing but not at top speed. The "
        f"hips are rotating, just not violently enough to drive elite "
        f"bat speed."
    )
    why = (
        f"Peak hip rotational speed is the rotational analog of how hard "
        f"you can throw a ball — it's a measurable physical quality you "
        f"train. {ref_name} pulls the trigger faster, which is why the "
        f"barrel arrives with the kind of speed defenses can't catch up to."
    )
    fix = (
        "What the fix feels like: short and violent, not long and smooth. "
        "Med-ball rotational throws teach the body to RECRUIT power into "
        "the rotation rather than glide through it."
    )
    return [first, why, fix]


def _narrate_front_side_stability(gaps_in_cat, ref_name):
    """Power Sequence M3 narrative — early shoulder fly-out."""
    first = (
        f"Your front shoulder is opening up too early — before the front "
        f"foot has finished planting. That kills the storage of torque "
        f"between hips and shoulders."
    )
    why = (
        f"When the shoulders pre-open, the entire upper-body \"slingshot\" "
        f"effect is gone — the hips and shoulders end up firing together "
        f"and the bat has to catch up to a swing that already happened. "
        f"{ref_name} keeps the front shoulder pointed at the pitcher "
        f"until AFTER the front foot is down."
    )
    fix = (
        "What the fix feels like: chin to back shoulder, chest pointed at "
        "the catcher until you can't help but turn. Closed-shoulder tee "
        "work with a noodle across the chest gives the body the cue."
    )
    return [first, why, fix]
```

- [ ] **Step 3: Wire new narrators into `_CATEGORY_NARRATORS`**

Find the `_CATEGORY_NARRATORS` dict (around line 637) and extend it:

```python
_CATEGORY_NARRATORS = {
    "head_stability":           _narrate_head_stability,
    "hip_rotation":             _narrate_hip_rotation,
    "hip_shoulder_separation":  _narrate_separation,
    "knee_extension":           _narrate_knee,
    "timing":                   _narrate_timing_cat,
    # Power Sequence (new):
    "sequencing":               _narrate_sequencing,
    "rotational_speed":         _narrate_rotational_speed,
    "front_side_stability":     _narrate_front_side_stability,
}
```

- [ ] **Step 4: Smoke-test**

Run: `python3 -c "import drills; print(drills._narrate_sequencing([], 'Mookie Betts')[0])"`

Expected: prints the first sentence of the sequencing narrative.

- [ ] **Step 5: Commit**

```bash
git add drills.py
git commit -m "feat(drills): coach narratives for 3 new Power Sequence categories

Each narrator returns the same (first, why, fix) tuple shape the
existing narrators do, so the report's WHAT-TO-FIX section renders
new categories with the same UX. Copy follows the established
voice — direct, second-person, ends with a 'what the fix feels
like' line.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: New drill content (6 drills — 2 per new category)

The drill plan builder reads from `_DRILL_LIBRARY` (find it in drills.py). Add 6 drills.

**Files:**
- Modify: `drills.py` (extend `_DRILL_LIBRARY`)

- [ ] **Step 1: Locate the drill library**

Run: `grep -n "_DRILL_LIBRARY\|DRILL_LIBRARY = \|drill_library" drills.py | head -10`

Open the library and confirm the schema — typically a dict keyed by category, value is a list of drill dicts with fields like `name`, `description`, `reps`, `instructions`, etc.

- [ ] **Step 2: Add 6 drills**

Inside the existing `_DRILL_LIBRARY` dict (or whatever it's called), add three new keys with 2 drills each. Match the existing schema exactly (don't invent fields). Sketch:

```python
"sequencing": [
    {
        "name": "Connection Ball Drill",
        "summary": "Force the hands to wait for the hips by squeezing a ball in the armpit.",
        "reps": "3 × 8",
        "instructions": (
            "1. Tuck a tennis ball or small connection ball under your lead "
            "armpit (the one closest to the pitcher).\n"
            "2. Take your normal swing — the ball must NOT drop until "
            "after contact.\n"
            "3. If the ball drops early, your arms are leaving the body "
            "before your hips have done their work. Slow the swing down "
            "and feel the hips lead.\n"
            "4. Build up to game speed over a set of 8 swings."
        ),
        "what_it_targets": "Sequencing — keeps the upper body waiting on the lower body.",
    },
    {
        "name": "Heavy-Bat Hip Turner",
        "summary": "A weighted bat slows the upper body and forces the lower body to lead.",
        "reps": "2 × 10",
        "instructions": (
            "1. Use a fungo or weighted training bat (2–4 lbs heavier "
            "than your gamer).\n"
            "2. Take 10 controlled swings focusing ONLY on the hip turn "
            "— let the upper body and arms feel slow and reactive.\n"
            "3. Switch back to your game bat for 5 swings. The bat will "
            "feel like a feather and the sequence will feel automatic."
        ),
        "what_it_targets": "Sequencing — exaggerates the lag so the body can feel it.",
    },
],
"rotational_speed": [
    {
        "name": "Med-Ball Rotational Throws",
        "summary": "Direct rotational power output — train the hip-snap.",
        "reps": "3 × 6",
        "instructions": (
            "1. Stand sideways to a wall, 5–8 feet away. Hold a 4–8 lb "
            "med ball at hip height.\n"
            "2. Load into your back hip (just like a swing), then EXPLODE "
            "rotationally and throw the ball into the wall as hard as "
            "you can.\n"
            "3. Catch the rebound, reset, and do it again — fast and "
            "hard. The goal is peak rotational velocity, not endurance.\n"
            "4. Two sides — 6 throws each."
        ),
        "what_it_targets": "Peak hip rotational speed — pure rotational power.",
    },
    {
        "name": "Sledgehammer to Tire",
        "summary": "Eccentric loading + violent rotation. Best power drill there is.",
        "reps": "2 × 8 per side",
        "instructions": (
            "1. Stand next to a tire (or stack of pads). Hold a 6–10 lb "
            "sledgehammer overhead with both hands.\n"
            "2. Drive the hammer DOWN into the tire by rotating through "
            "the hips — the arms just hold on, the rotation does the "
            "work.\n"
            "3. Both sides. The deceleration on contact teaches the body "
            "to brake the hips violently, which transfers to bat speed."
        ),
        "what_it_targets": "Peak hip rotational speed + rotational deceleration.",
    },
],
"front_side_stability": [
    {
        "name": "Noodle Across the Chest",
        "summary": "Train the front shoulder to STAY CLOSED through plant.",
        "reps": "3 × 10",
        "instructions": (
            "1. Have a partner (or use a pool noodle braced under your "
            "lead armpit) lay a noodle across your chest, pointed at "
            "the pitcher.\n"
            "2. Take swings. The noodle MUST stay pointed at the pitcher "
            "until your front foot is planted. If it rotates open early, "
            "you flew open.\n"
            "3. Slow the swing down until you can keep the noodle pointed "
            "forward through plant. Build up speed over 10 swings."
        ),
        "what_it_targets": "Front-side stability — keep the chest closed through plant.",
    },
    {
        "name": "Pause-at-Plant Tee",
        "summary": "A 1-second pause at foot plant forces the front side to set.",
        "reps": "3 × 8",
        "instructions": (
            "1. Set up off a tee. Take your normal load and stride.\n"
            "2. PAUSE for 1 full second at the moment the front foot "
            "plants — front shoulder closed, chin tucked, hips loaded.\n"
            "3. From the pause, drive the swing. The pause kills momentum "
            "in the upper body so the lower body has to initiate.\n"
            "4. Over time, shorten the pause to half a second, then "
            "to a 'feel' — the body remembers."
        ),
        "what_it_targets": "Front-side stability + sequencing initiation.",
    },
],
```

- [ ] **Step 3: Verify the library loads cleanly**

Run: `python3 -c "import drills; print(list(drills._DRILL_LIBRARY.keys()))"` (replace `_DRILL_LIBRARY` with the actual name if it differs).

Expected: 8 keys (5 old + 3 new).

- [ ] **Step 4: Commit**

```bash
git add drills.py
git commit -m "feat(drills): 6 new drills for Power Sequence categories

Two drills per new category (sequencing, rotational_speed,
front_side_stability), matching the existing drill-library schema.
Copy follows the established voice — numbered steps, plain
language, ends with what the drill targets.

The drills themselves are coaching-staples, not inventions:
  - Connection Ball Drill — DiamondKinetics / Driveline classic
  - Heavy-Bat Hip Turner — universal weighted-bat hip iso
  - Med-Ball Rotational Throws — every S&C program uses these
  - Sledgehammer to Tire — Driveline + most velocity programs
  - Noodle Across Chest — common cue with a physical anchor
  - Pause-at-Plant Tee — well-established sequencing drill

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Update GOAL_CATEGORY_BOOSTS

The drill-plan generator weights gaps by category and adds a small boost based on the player's stated `primary_goal`. Extend the boost map so new categories light up for the right goals.

**Files:**
- Modify: `drills.py` (extend `GOAL_CATEGORY_BOOSTS` per the spec)

- [ ] **Step 1: Locate the existing boost map**

Run: `grep -n "GOAL_CATEGORY_BOOSTS" drills.py`

- [ ] **Step 2: Update the dict**

Replace the existing `GOAL_CATEGORY_BOOSTS` definition with the spec-locked version:

```python
GOAL_CATEGORY_BOOSTS: dict[str, dict[str, int]] = {
    "More power": {
        "rotational_speed":          4,   # NEW — primary mapping
        "sequencing":                3,   # NEW — secondary
        "hip_rotation":              2,
        "hip_shoulder_separation":   2,
        "knee_extension":            1,
    },
    "Better contact": {
        "front_side_stability":      3,   # NEW — primary mapping
        "head_stability":            3,
        "sequencing":                2,   # NEW — secondary
        "timing":                    2,
    },
    "Better timing": {
        "sequencing":                4,   # NEW — exact match for "timing"
        "timing":                    3,
        "head_stability":            1,
    },
    "Fix timing": {                       # legacy label, alias the above
        "sequencing":                4,
        "timing":                    3,
        "head_stability":            1,
    },
    "Better consistency": {
        "front_side_stability":      2,   # NEW
        "head_stability":            2,
        "timing":                    2,
        "hip_rotation":              1,
    },
    "Improve bat path": {
        "front_side_stability":      3,   # NEW — bat path is tied to front side
        "hip_shoulder_separation":   3,
        "knee_extension":            2,
    },
    "Reduce strikeouts": {
        "timing":                    3,
        "head_stability":            2,
        "sequencing":                2,   # NEW
    },
    "Improve mechanics":     {},
    "Improve overall swing": {},
    "Find MLB comparison":   {},
}
```

- [ ] **Step 3: Smoke-test**

Run:

```bash
python3 -c "
from drills import GOAL_CATEGORY_BOOSTS as g
assert g['More power']['rotational_speed'] == 4
assert g['Better contact']['front_side_stability'] == 3
assert g['Better timing']['sequencing'] == 4
print('boost map looks right')
"
```

- [ ] **Step 4: Commit**

```bash
git add drills.py
git commit -m "feat(drills): goal-boost map now routes to Power Sequence categories

primary_goal=\"More power\" now boosts rotational_speed (+4) and
sequencing (+3). \"Better contact\" boosts front_side_stability and
head_stability (both +3). \"Better timing\" boosts sequencing (+4)
— the new metric is a better proxy for what the user actually
asked for than the old generic 'timing' category.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Synthesize Power Sequence gaps in `analyzer.py`

So far the sequence block is computed and stored, but the drill-plan generator only sees gaps from the metric-similarity loop. We need to inject synthetic "gap" entries into `gaps_ranked` for any Power Sequence rating that's `marginal` or `poor`.

**Files:**
- Modify: `analyzer.py` (new helper `_synthesize_sequence_gaps`, call it before `build_drill_plan`)

- [ ] **Step 1: Find where `gaps_ranked` is built**

Run: `grep -n "gaps_ranked\b" analyzer.py | head -10`

Locate where `gaps_ranked` is assembled and where `build_drill_plan(gaps_ranked, ...)` is called.

- [ ] **Step 2: Add the synthesizer helper**

Insert at the bottom of analyzer.py (or near the other helpers — look for `_friendly_label` for context):

```python
def _synthesize_sequence_gaps(sequence_block: dict) -> list[dict]:
    """Convert Power Sequence ratings into synthetic gap entries the
    drill-plan generator already understands.

    A marginal rating becomes a moderate gap; a poor rating becomes a
    large gap. The label string carries enough information for
    drills.classify_gap to route to the right category (sequencing,
    rotational_speed, front_side_stability).
    """
    gaps: list[dict] = []
    if not sequence_block:
        return gaps
    rating = (sequence_block.get("rating") or {})

    # Severity → similarity (lower similarity = bigger gap; the drill
    # generator sorts by similarity ascending).
    SEVERITY = {"poor": 25.0, "marginal": 55.0, "good": None}

    def _add(label: str, rating_key: str, value):
        sev = SEVERITY.get(rating.get(rating_key))
        if sev is None:
            return
        gaps.append({
            "group":      "Power Sequence",
            "label":      label,
            "player":     value,
            "reference":  None,           # no MLB comp for synthetic gaps
            "similarity": sev,            # drives the gap-ranking
            "synthetic":  True,
        })

    _add("Sequencing lag",        "sequencing_lag",        sequence_block.get("sequencing_lag_ms"))
    _add("Peak hip rotational speed", "peak_hip_omega",    sequence_block.get("peak_hip_omega_deg_s"))
    _add("Stay closed (front-side stability)", "front_side_stability",
         sequence_block.get("front_side_stability_pct"))
    return gaps
```

- [ ] **Step 3: Wire it into `analyze()` before `build_drill_plan` is called**

Find the line `drill_plan = build_drill_plan(gaps_ranked, ...)`. Immediately above it, add:

```python
    # Inject Power Sequence ratings into gaps_ranked so the drill
    # generator routes to the new categories alongside metric-similarity gaps.
    sequence_gaps = _synthesize_sequence_gaps(sequence_block)
    if sequence_gaps:
        gaps_ranked = gaps_ranked + sequence_gaps
        gaps_ranked.sort(key=lambda g: g.get("similarity", 100))
```

- [ ] **Step 4: Smoke-test**

Run analyze on a fingerprint (use any cached fingerprint that has a sequence block — Task 11's reference re-processing will produce these):

```bash
python3 -c "
import json
from analyzer import analyze
# Use the simplest reference clip.
fp = 'references/aaron_judge.json'
# fake out the reference lookup by passing the same path as both player and ref
r = analyze(fp, fp)
print('drill plan categories:', [c.get('category') for c in r.get('drill_plan', [])])
"
```

Expected: drill_plan contains at least one new category. If sequence block is null (Task 6 hasn't been re-run), only old categories will appear — that's fine pre-Task 11.

- [ ] **Step 5: Commit**

```bash
git add analyzer.py
git commit -m "feat(analyzer): synthesize Power Sequence gaps for drill routing

Marginal/poor sequence ratings now appear in gaps_ranked as
synthetic gap entries with group='Power Sequence'. classify_gap()
in drills.py already knows how to route those labels to the new
categories. Good ratings produce no gap — no drill needed.

Severity (poor=25 sim, marginal=55 sim) is chosen so a 'poor'
sequence rating outranks most low-priority metric-similarity gaps
but doesn't displace a glaring biomechanics issue.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Re-process the MLB reference library

`build_reference_library.py` re-runs detect_phases.py on each reference video. After our changes, references need to be re-processed so they all carry a `sequence` block (otherwise comparison logic in the future may complain).

**Files:**
- Modify: `build_reference_library.py` (add `--rebuild` flag, skip-if-present logic)

- [ ] **Step 1: Read the current build script**

Run: `grep -n "^def \|argparse\|for ref\|rebuild" build_reference_library.py | head -20`

Confirm the script's shape: it iterates over source clips and writes JSON output per ref.

- [ ] **Step 2: Add a rebuild flag + idempotent re-process**

At the top of `build_reference_library.py` (after the existing imports), ensure argparse is available, then wrap the build loop:

```python
import argparse


def needs_rebuild(ref_json_path: str) -> bool:
    """True if the reference JSON lacks a Power Sequence block."""
    import json
    try:
        d = json.load(open(ref_json_path))
    except Exception:
        return True  # missing/corrupt → rebuild
    return "sequence" not in d
```

Then around the main loop, gate the work on `needs_rebuild(ref_json_path) or args.rebuild`:

```python
parser = argparse.ArgumentParser()
parser.add_argument("--rebuild", action="store_true",
                    help="Force re-process every reference even if "
                         "the JSON already has a sequence block.")
args = parser.parse_args()
# ...
for ref_clip in references_to_build:
    out_json = os.path.join("references", f"{slug}.json")
    if not args.rebuild and os.path.exists(out_json) and not needs_rebuild(out_json):
        print(f"  ✓ skip {slug} (already has sequence block)")
        continue
    # ... existing build logic ...
```

(Adjust variable names to match the current file. The KEY behavior: skip refs that already have `sequence`, unless `--rebuild` is passed.)

- [ ] **Step 3: Run the re-process**

```bash
PHASE_DEBUG_V1=true DETECTOR_V4=true \
  /Users/logancollins/barrellabs-swing-app/.venv/bin/python \
  build_reference_library.py 2>&1 | tail -30
```

Expected: 20 references re-processed, each gets a `sequence` block.

Verify:

```bash
python3 -c "
import json, glob
files = sorted(glob.glob('references/*.json'))
ok, bad = 0, 0
for f in files:
    d = json.load(open(f))
    if 'sequence' in d:
        ok += 1
    else:
        bad += 1
        print('  missing sequence:', f)
print(f'  OK: {ok}/{len(files)}')
"
```

Expected: `OK: 20/20`.

- [ ] **Step 4: Re-run the biomech integration test (should now PASS, not skip)**

Run: `python3 -m pytest tests/test_biomech.py::TestDetectPhasesIntegration -v`
Expected: 1 PASSED (no longer skipping).

- [ ] **Step 5: Commit**

```bash
git add build_reference_library.py
git add references/*.json
git commit -m "feat(reference-library): re-process 20 MLB clips with Power Sequence

Idempotent --rebuild flag: skips references that already have a
'sequence' block unless explicitly told to redo them. After this
commit, every reference fingerprint has the new biomech block, so
future comparison logic against the library works end-to-end.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Power Sequence section in the swing report — CSS

The new section needs editorial-style CSS that matches the rest of the report (`Instrument Serif` headlines, `Geist Mono` eyebrows, bone-on-ink palette, gold accents).

**Files:**
- Modify: `swing_report_dashboard_preview.py` (extend the CSS block)

- [ ] **Step 1: Find the existing CSS injection block**

Run: `grep -n "_SR_CSS\|SRD_CSS\|<style>" swing_report_dashboard_preview.py | head -10`

Locate the multi-line string that holds the report's CSS (likely a `_RENDER_CSS` or similar constant).

- [ ] **Step 2: Append the Power Sequence styles**

Inside the CSS string, before the closing `</style>`, add:

```css
/* ───── Power Sequence section (new) ───── */
.srd-power-section {
    margin: 32px 0 40px 0;
    padding: 28px 32px 32px 32px;
    border: 1px solid var(--srd-line);
    border-radius: 16px;
    background:
      radial-gradient(120% 60% at 50% 0%, rgba(232,193,112,0.06), transparent 70%),
      var(--srd-bg-glass);
}
.srd-power-eyebrow {
    font-family: var(--srd-mono); font-size: 11px; font-weight: 600;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--srd-gold);
    margin: 0 0 8px 0;
}
.srd-power-title {
    font-family: var(--srd-serif); font-size: 2.4rem;
    line-height: 1.05; letter-spacing: -0.018em;
    color: var(--srd-bone); font-weight: 400; margin: 0 0 8px 0;
}
.srd-power-title .ital { font-style: italic; color: var(--srd-gold); }
.srd-power-verdict {
    font-family: var(--srd-sans); font-size: 1.05rem;
    line-height: 1.5; color: var(--srd-bone-dim); max-width: 60ch;
    margin: 0 0 22px 0;
}
.srd-power-tiles {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 16px; margin-top: 20px;
}
@media (max-width: 760px) {
    .srd-power-tiles { grid-template-columns: 1fr; }
}
.srd-power-tile {
    border: 1px solid var(--srd-line);
    border-radius: 12px;
    padding: 18px 22px;
    background: rgba(244,239,230,0.025);
}
.srd-power-tile.good   { border-color: rgba(232,193,112,0.42); }
.srd-power-tile.marginal { border-color: var(--srd-line-hi); }
.srd-power-tile.poor   { border-color: rgba(230,69,48,0.45); }
.srd-power-tile-label {
    font-family: var(--srd-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.20em; text-transform: uppercase;
    color: var(--srd-bone-dim); margin-bottom: 6px;
}
.srd-power-tile.good     .srd-power-tile-label { color: var(--srd-gold); }
.srd-power-tile.poor     .srd-power-tile-label { color: var(--srd-red); }
.srd-power-tile-value {
    font-family: var(--srd-serif); font-style: italic;
    font-size: 2.2rem; line-height: 1; letter-spacing: -0.02em;
    color: var(--srd-bone); margin: 4px 0 8px 0;
}
.srd-power-tile-unit {
    font-family: var(--srd-mono); font-size: 11px; font-weight: 500;
    color: var(--srd-bone-dim); letter-spacing: 0.12em;
    text-transform: lowercase; margin-left: 4px;
}
.srd-power-tile-coach {
    font-family: var(--srd-sans); font-size: 0.92rem;
    line-height: 1.45; color: var(--srd-bone-dim); max-width: 32ch;
}
```

(The CSS variable names — `--srd-line`, `--srd-bone`, etc. — should already be defined in the same CSS block; if they have a different prefix, swap accordingly.)

- [ ] **Step 3: Verify the file still parses**

Run: `python3 -c "import swing_report_dashboard_preview as s; print('module loads')"`
Expected: `module loads`.

- [ ] **Step 4: Commit**

```bash
git add swing_report_dashboard_preview.py
git commit -m "feat(swing-report): Power Sequence section CSS

Editorial styling matching the rest of the report — bone-on-ink,
gold-on-good, red-on-poor border accent. Mobile-stacks at 760px.
Tile values use Instrument Serif italic to match the price-tag
treatment in the pricing page.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Power Sequence section in the swing report — HTML

Wire the actual section markup into the renderer.

**Files:**
- Modify: `swing_report_dashboard_preview.py` (new `_render_power_sequence` + call it)

- [ ] **Step 1: Find the renderer entry point**

Run: `grep -n "^def render_swing_report_dashboard_preview\|^def _render_" swing_report_dashboard_preview.py | head -15`

Locate `render_swing_report_dashboard_preview(record, ...)` — the main entry. Identify where the existing top-of-report sections are rendered (hero, score ring, etc.).

- [ ] **Step 2: Add `_render_power_sequence`**

Insert near the other `_render_*` helpers:

```python
# Plain-language coach lines per rating (spec § Tile copy).
_POWER_COPY = {
    "sequencing_lag": {
        "good":     "Pelvis-then-torso, the way pros do it.",
        "marginal": "Hips and shoulders firing close together — small power leak.",
        "poor":     "Shoulders fired before the hips. Top fix.",
        None:       "Need a cleaner side angle to read this.",
    },
    "peak_hip_omega": {
        "good":     "Solid rotational power. Good HS / college-prep range.",
        "marginal": "Build hip speed — med-ball rotational throws.",
        "poor":     "Hips aren't yet generating elite rotational power.",
        None:       "Could not measure.",
    },
    "front_side_stability": {
        "good":     "Front side stayed shut through plant.",
        "marginal": "Front side opening earlier than ideal.",
        "poor":     "Front shoulder flew open early. #1 amateur fault.",
        None:       "Not enough shoulder rotation to characterize.",
    },
}


def _format_pwr_value(metric: str, value, rating):
    """Format the tile value + unit per metric."""
    if value is None:
        return ("—", "")
    if metric == "sequencing_lag":
        return (f"{value:.0f}", "ms")
    if metric == "peak_hip_omega":
        return (f"{value:.0f}", "°/s")
    if metric == "front_side_stability":
        return (f"{value:.0f}", "%")
    return (f"{value}", "")


def _render_power_sequence(record) -> str:
    """Return the HTML string for the Power Sequence section, or empty
    string if the record has no sequence block."""
    seq = (record.get("sequence") or {})
    rating = (seq.get("rating") or {})
    if not any(seq.get(k) is not None for k in (
        "sequencing_lag_ms", "peak_hip_omega_deg_s", "front_side_stability_pct"
    )):
        return ""

    def _tile(label, metric_key, value, unit, rating_val, coach):
        rating_class = rating_val or "marginal"
        return f"""
        <div class="srd-power-tile {rating_class}">
          <div class="srd-power-tile-label">{label}</div>
          <div class="srd-power-tile-value">{value}<span class="srd-power-tile-unit"> {unit}</span></div>
          <div class="srd-power-tile-coach">{coach}</div>
        </div>
        """

    # Pick a verdict line for the section header (driven by sequencing_lag).
    lag_rating = rating.get("sequencing_lag")
    verdict = {
        "good":     "Your chain fired in order. The numbers below show how well.",
        "marginal": "Your chain mostly fired in order. Tighten the sequence and the bat will jump.",
        "poor":     "Your chain isn't firing in order yet. This is the biggest unlock available to you.",
        None:       "How your body fired through the swing.",
    }[lag_rating]

    seq_val, seq_unit = _format_pwr_value(
        "sequencing_lag", seq.get("sequencing_lag_ms"), rating.get("sequencing_lag"))
    omega_val, omega_unit = _format_pwr_value(
        "peak_hip_omega", seq.get("peak_hip_omega_deg_s"), rating.get("peak_hip_omega"))
    stab_val, stab_unit = _format_pwr_value(
        "front_side_stability", seq.get("front_side_stability_pct"),
        rating.get("front_side_stability"))

    return f"""
    <div class="srd-power-section">
      <div class="srd-power-eyebrow">§ 01 · Power Sequence</div>
      <h2 class="srd-power-title">How your body <span class="ital">fired.</span></h2>
      <p class="srd-power-verdict">{verdict}</p>
      <div class="srd-power-tiles">
        {_tile("Sequencing", "sequencing_lag", seq_val, seq_unit,
                rating.get("sequencing_lag"),
                _POWER_COPY["sequencing_lag"].get(rating.get("sequencing_lag")))}
        {_tile("Peak Hip Speed", "peak_hip_omega", omega_val, omega_unit,
                rating.get("peak_hip_omega"),
                _POWER_COPY["peak_hip_omega"].get(rating.get("peak_hip_omega")))}
        {_tile("Stay Closed", "front_side_stability", stab_val, stab_unit,
                rating.get("front_side_stability"),
                _POWER_COPY["front_side_stability"].get(rating.get("front_side_stability")))}
      </div>
    </div>
    """
```

- [ ] **Step 3: Call `_render_power_sequence` from the main renderer**

Inside `render_swing_report_dashboard_preview`, immediately after the existing header / score-ring is rendered and BEFORE the "Top Priorities" section, inject:

```python
    power_html = _render_power_sequence(record)
    if power_html:
        st.markdown(power_html, unsafe_allow_html=True)
```

(Adjust the call site to match how other sections are appended — there may be a `sections = []` list pattern or direct st.markdown calls.)

- [ ] **Step 4: Smoke-test render**

Run: `python3 -c "
import swing_report_dashboard_preview as s
record = {
    'sequence': {
        'sequencing_lag_ms': 32.0,
        'peak_hip_omega_deg_s': 947.0,
        'front_side_stability_pct': 22.0,
        'rating': {
            'sequencing_lag': 'good',
            'peak_hip_omega': 'good',
            'front_side_stability': 'good',
        },
    },
}
html = s._render_power_sequence(record)
assert 'POWER SEQUENCE' in html.upper()
assert '32' in html
assert '947' in html
assert '22' in html
print('renderer OK')
"`

- [ ] **Step 5: Commit**

```bash
git add swing_report_dashboard_preview.py
git commit -m "feat(swing-report): Power Sequence section renderer

New _render_power_sequence() builds the three-tile section + the
verdict line driven by the sequencing rating. Wired in at the top
of the report, right under the score-ring header. Empty string
when no sequence block exists — old fingerprints render the rest
of the report unchanged.

Coach copy table (per metric × per rating) is the spec's locked
language. Tile colors come from CSS class names (good/marginal/poor).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: Verb-rename existing tiles (in the report)

`_CATEGORY_TITLES` in drills.py now contains the new verb-language names. The swing report should READ from there (or the report's own equivalent constants) instead of hard-coding the old labels.

**Files:**
- Modify: `swing_report_dashboard_preview.py` (replace any hard-coded tile labels)

- [ ] **Step 1: Find hard-coded category labels in the report**

Run: `grep -n "HIP ROTATION\|HIP-SHOULDER\|HEAD STABILITY\|FRONT-SIDE FIRMNESS" swing_report_dashboard_preview.py | head -20`

There may be 0-5 occurrences depending on how the existing report renders categories.

- [ ] **Step 2: Replace each occurrence with the new verb-rename**

For each hit, replace with the new title from the rename map:

| Old | New |
|---|---|
| `HIP ROTATION` | `HIP TURN COMPLETION` |
| `HIP-SHOULDER SEPARATION` | `TORQUE STORAGE` |
| `HEAD STABILITY` | `HEAD QUIET` |
| `FRONT-SIDE FIRMNESS` | `LOWER-BODY DRIVE` |
| `KNEE EXTENSION` (if present) | `LOWER-BODY DRIVE` |

For tiles rendered via a tag/title prop, the simplest fix is to map through `_CATEGORY_TITLES` from drills.py. If the report file currently has its own constants, update them in place.

- [ ] **Step 3: Add hover-tooltip with old name (for 60-day grace)**

For each renamed tile in the report markup, add a `title=` attribute with the old name:

```html
<div class="srd-metric-tile" title="Previously: HIP ROTATION">
  <h3>HIP TURN COMPLETION</h3>
  ...
</div>
```

This gives muscle-memory users a quick reminder without cluttering the UI.

- [ ] **Step 4: Smoke-test**

Run: `python3 -c "import swing_report_dashboard_preview; print('OK')"`

Then check the rendered HTML on a sample record:

```bash
python3 -c "
import swing_report_dashboard_preview as s, json
fp = json.load(open('references/aaron_judge.json'))
# Render whatever section uses category labels — depends on the file's API.
# Just confirm 'HIP TURN COMPLETION' appears somewhere in the output.
"
```

- [ ] **Step 5: Commit**

```bash
git add swing_report_dashboard_preview.py
git commit -m "feat(swing-report): verb-rename existing tiles + grace tooltips

Tile titles now match the spec's verb-based language: HIP ROTATION
→ HIP TURN COMPLETION, etc. Each renamed tile carries a title=
attribute showing the old name for 60 days so users with muscle
memory aren't disoriented. After 60 days the title= can be dropped
(separate commit, not in this PR).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: Snapshot test of the rendered report

Lock in the report HTML so future changes can't silently regress the Power Sequence section.

**Files:**
- Create: `tests/test_swing_report_power_sequence.py`

- [ ] **Step 1: Write the snapshot test**

```python
# tests/test_swing_report_power_sequence.py
"""Snapshot test: rendered swing report HTML contains the Power Sequence
section when a record has a sequence block."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def test_power_sequence_section_renders_with_all_three_tiles():
    import swing_report_dashboard_preview as s
    record = {
        "sequence": {
            "sequencing_lag_ms":        32.0,
            "peak_hip_omega_deg_s":     947.0,
            "front_side_stability_pct": 22.0,
            "rating": {
                "sequencing_lag":        "good",
                "peak_hip_omega":        "good",
                "front_side_stability":  "good",
            },
        },
    }
    html = s._render_power_sequence(record)
    # Section header
    assert "Power Sequence" in html
    # Each metric value
    assert "32" in html and "ms" in html
    assert "947" in html and "°/s" in html
    assert "22" in html and "%" in html
    # Each tile label
    assert "SEQUENCING" in html.upper()
    assert "PEAK HIP SPEED" in html.upper()
    assert "STAY CLOSED" in html.upper()


def test_power_sequence_section_empty_when_no_sequence_block():
    import swing_report_dashboard_preview as s
    record = {}
    assert s._render_power_sequence(record) == ""


def test_power_sequence_section_skips_none_metrics():
    """When all 3 metrics are None, the section should be empty (we'd
    rather hide it than show three placeholder dashes)."""
    import swing_report_dashboard_preview as s
    record = {
        "sequence": {
            "sequencing_lag_ms":        None,
            "peak_hip_omega_deg_s":     None,
            "front_side_stability_pct": None,
            "rating": {"sequencing_lag": None, "peak_hip_omega": None,
                        "front_side_stability": None},
        },
    }
    assert s._render_power_sequence(record) == ""


def test_power_sequence_poor_rating_shows_red_border_class():
    import swing_report_dashboard_preview as s
    record = {
        "sequence": {
            "sequencing_lag_ms":        -10.0,
            "peak_hip_omega_deg_s":     400.0,
            "front_side_stability_pct": 60.0,
            "rating": {
                "sequencing_lag":        "poor",
                "peak_hip_omega":        "poor",
                "front_side_stability":  "poor",
            },
        },
    }
    html = s._render_power_sequence(record)
    # Three "poor" CSS classes expected (one per tile).
    assert html.count("srd-power-tile poor") == 3
```

- [ ] **Step 2: Run the snapshot tests**

Run: `python3 -m pytest tests/test_swing_report_power_sequence.py -v`
Expected: 4 PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_swing_report_power_sequence.py
git commit -m "test(swing-report): snapshot tests for Power Sequence section

Locks in: section renders all 3 tiles with correct values, returns
empty string when no sequence block, returns empty string when all
3 metrics are None, applies the right CSS class per rating. These
are the surface-level invariants that protect us when the renderer
gets touched by other workstreams.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: Manual end-to-end validation on 3-5 real swings

Confirm the full pipeline works on real videos before opening the PR.

**Files:**
- None modified; this is a validation pass.

- [ ] **Step 1: Run detect_phases.py on 3 different swings**

Pick swings with varied stride styles and clip lengths:

```bash
PHASE_DEBUG_V1=true DETECTOR_V4=true \
  /Users/logancollins/barrellabs-swing-app/.venv/bin/python \
  detect_phases.py validation/videos/corey_seager_swing.mp4

PHASE_DEBUG_V1=true DETECTOR_V4=true \
  /Users/logancollins/barrellabs-swing-app/.venv/bin/python \
  detect_phases.py /Users/logancollins/baseball-swing-app/swing.mp4

# Pick a third — any short clip from validation/videos/
ls validation/videos/*.mp4 | head -1
```

For each: inspect the resulting `<basename>_fingerprint.json` and confirm:
- `sequence.sequencing_lag_ms` is a sensible number (within ±200ms of zero)
- `sequence.peak_hip_omega_deg_s` is > 0 and < 3000
- `sequence.front_side_stability_pct` is None OR in [-50, 150]
- `sequence.rating` has 3 string values (or 3 nulls if metrics are None)

- [ ] **Step 2: Run the full validation suite**

```bash
# Move backup fingerprints out of the way (already done in earlier session)
ls validation/results/.backup_pre_phase4d/*_fingerprint.json | wc -l
# 42 backups — these are pre-Phase 4c/4d AND pre-sequence-block.

# Run the validation pipeline (will re-process all 42 scored swings)
/Users/logancollins/barrellabs-swing-app/.venv/bin/python \
  -m scripts.validation.run_validation \
  --manifest validation/manifest.json \
  --results-dir validation/results \
  --report-dir validation/reports 2>&1 | tail -20
```

This will take ~25 min. While it runs, check that every scored swing's resulting fingerprint has a sequence block:

```bash
python3 -c "
import json, glob
files = glob.glob('validation/results/*_fingerprint.json')
have = sum(1 for f in files if 'sequence' in json.load(open(f)))
print(f'{have}/{len(files)} fingerprints have sequence block')
"
```

Expected: `42/42 fingerprints have sequence block` once the run completes.

- [ ] **Step 3: Spot-check 5 swings in the rendered report (Streamlit)**

```bash
cd /Users/logancollins/barrellabs-swing-app/.claude/worktrees/nervous-proskuriakova
/Users/logancollins/barrellabs-swing-app/.venv/bin/streamlit run app.py
```

Sign in, navigate to Sessions → open 5 different existing reports. For each one verify:
- Power Sequence section appears at the top, below the score ring
- All 3 tiles render with values
- Coach lines are correct for the rating
- Existing tiles below now show verb-renamed titles (`HIP TURN COMPLETION` not `HIP ROTATION`)
- Hovering a renamed tile shows the old name in the tooltip

- [ ] **Step 4: Run the full test suite**

```bash
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

Expected: all tests passing (existing + new biomech + new snapshot). If anything fails, fix it before opening the PR.

- [ ] **Step 5: Final commit (if anything was tweaked) + push + open PR**

```bash
# If any small fixes were needed during validation:
git add -A
git commit -m "chore: end-to-end validation tweaks"

git push origin <branch>

gh pr create --base main --head <branch> \
  --title "Power Sequence biomech redesign — Approach A" \
  --body "$(cat <<'EOF'
Implements the spec at \`docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md\`.

## Summary

Adds 3 new biomechanics metrics (sequencing lag, peak hip rotational
speed, front-side stability), surfaces them via a new Power Sequence
section at the top of the swing report, and verb-renames existing
tiles so every label is now a mechanism a player can train (verbs)
instead of a position they can measure (nouns).

All 3 new metrics are derived from per-frame signals
detect_phases.py already produces — no new sensor inputs.

## Test plan

- [x] biomech.py unit tests (24 passing)
- [x] swing report snapshot tests (4 passing)
- [x] manual end-to-end on 5 real swings
- [x] full validation pipeline re-ran on 42 scored swings, every
      fingerprint has the new sequence block
- [x] all existing tests still pass (160+)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- ✅ M1 sequencing lag: Tasks 2, 6, 12, 15, 17
- ✅ M2 peak hip omega: Tasks 3, 6, 12, 15, 17
- ✅ M3 front-side stability: Tasks 4, 6, 12, 15, 17
- ✅ Rating classifier: Task 5
- ✅ detect_phases.py integration: Task 6
- ✅ analyzer.py surfacing: Task 7
- ✅ drills.py categories + titles: Task 8
- ✅ Narrator paragraphs: Task 9
- ✅ Drill content (3 categories × 2 drills): Task 10
- ✅ GOAL_CATEGORY_BOOSTS update: Task 11
- ✅ Synthetic gap injection (the "wires the new metrics into the drill plan" piece): Task 12
- ✅ MLB reference re-processing: Task 13
- ✅ Power Sequence section CSS: Task 14
- ✅ Power Sequence section HTML: Task 15
- ✅ Verb-rename existing tiles: Task 16
- ✅ Snapshot tests: Task 17
- ✅ Manual end-to-end + PR: Task 18

**Placeholder scan:** No `TODO` / `TBD` / "implement later" in any step. Every code block is complete.

**Type consistency:** `compute_sequence` returns the same dict shape in every task. `rate_*` functions all take `Optional[<numeric>]` and return `Optional[str]`. The `sequence_block` dict shape is identical in analyzer.py, drills.py synthesis, and the renderer.

**Skipped on purpose (out of scope for this plan):**
- Power Sequence timeline SVG visualization — the spec describes it but the plan ships the 3 tiles first, leaves the timeline viz as a follow-up commit so the PR scope stays manageable. If we want it in this PR, it slots in between Task 15 and Task 16.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-biomechanics-power-sequence-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
