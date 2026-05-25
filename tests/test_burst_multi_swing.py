"""Phase 4d — tests for `_find_burst_and_baseline` multi-swing handling.

`detect_phases._find_burst_and_baseline` decides which "burst" of high
hip-rotational velocity is the swing the user wants analyzed. On clips
with one swing it uses argmax — same as before. On clips long enough
to plausibly contain multiple distinct swings (warmup take + real
take, multiple cuts) it now prefers the FIRST distinct burst over the
strongest one. That fixes validation failures on 5 long clips where
the labeler marked swing #1's plant but the detector cascaded from
swing #N's contact.

This module tests the burst-selection logic in isolation against
synthetic rate-of-change signals.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from phase_burst import (
    find_burst_and_baseline as _find_burst_and_baseline,
    _find_distinct_burst_peaks,
    MULTI_SWING_MIN_DURATION_S,
    MULTI_SWING_MIN_DISTANCE_S,
    MULTI_SWING_HEIGHT_RATIO,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic burst signals
# ---------------------------------------------------------------------------


def _gaussian_burst(n: int, center: int, width: int, amplitude: float) -> np.ndarray:
    """Build a smoothed gaussian-shaped peak centered at `center`."""
    x = np.arange(n, dtype=float)
    return amplitude * np.exp(-((x - center) ** 2) / (2.0 * width ** 2))


def _two_burst_signal(
    *, n: int, peak_a: int, peak_b: int,
    amp_a: float, amp_b: float, width: int = 6,
) -> np.ndarray:
    """Two gaussian bursts at peak_a and peak_b, amplitudes amp_a / amp_b."""
    return (_gaussian_burst(n, peak_a, width, amp_a)
            + _gaussian_burst(n, peak_b, width, amp_b))


# ---------------------------------------------------------------------------
# _find_distinct_burst_peaks
# ---------------------------------------------------------------------------


class TestFindDistinctBurstPeaks:
    def test_single_clean_burst_returns_one_peak(self):
        sig = _gaussian_burst(300, center=150, width=8, amplitude=10.0)
        peaks = _find_distinct_burst_peaks(
            sig, min_height=5.0, min_distance_frames=30,
        )
        assert peaks == [150]

    def test_two_distinct_bursts_returned_in_order(self):
        sig = _two_burst_signal(
            n=600, peak_a=150, peak_b=450, amp_a=8.0, amp_b=10.0,
        )
        peaks = _find_distinct_burst_peaks(
            sig, min_height=5.0, min_distance_frames=60,
        )
        assert peaks == [150, 450]

    def test_secondary_peak_below_threshold_ignored(self):
        sig = _two_burst_signal(
            n=600, peak_a=150, peak_b=450,
            amp_a=2.0, amp_b=10.0,   # tiny first peak
        )
        peaks = _find_distinct_burst_peaks(
            sig, min_height=5.0, min_distance_frames=60,
        )
        # Tiny first peak is below threshold — only the big one remains
        assert peaks == [450]

    def test_close_peaks_collapsed_by_distance_filter(self):
        # Two peaks 20 frames apart — closer than min_distance — second one
        # should be filtered out, leaving only the first.
        sig = _two_burst_signal(
            n=400, peak_a=100, peak_b=120, amp_a=10.0, amp_b=9.5,
        )
        peaks = _find_distinct_burst_peaks(
            sig, min_height=5.0, min_distance_frames=30,
        )
        # Note: the two gaussians overlap — depending on width this may
        # actually merge into a single peak. Verify at least: not BOTH
        # picked, and the result is in valid range.
        assert len(peaks) == 1
        assert 95 <= peaks[0] <= 125

    def test_short_signal_returns_empty(self):
        assert _find_distinct_burst_peaks(
            np.array([1.0, 2.0]), min_height=0.5, min_distance_frames=1,
        ) == []

    def test_flat_signal_returns_empty(self):
        sig = np.ones(200)
        peaks = _find_distinct_burst_peaks(
            sig, min_height=0.5, min_distance_frames=10,
        )
        # No local maxima in a flat signal
        assert peaks == []


# ---------------------------------------------------------------------------
# _find_burst_and_baseline — multi-swing handling
# ---------------------------------------------------------------------------


class TestFindBurstAndBaselineMultiSwing:
    """The wider entry point. We care about which `burst_peak_idx`
    gets returned for short clips vs long ones, and single vs
    multi-burst signals."""

    def test_short_clip_uses_global_argmax(self):
        """A 3-second clip is below MULTI_SWING_MIN_DURATION_S — even if
        there are two peaks, behavior matches the pre-Phase-4d code:
        the burst peak is the global argmax."""
        fps = 60.0
        n = int(fps * 3.0)  # 3 seconds
        sig = _two_burst_signal(
            n=n, peak_a=40, peak_b=120, amp_a=8.0, amp_b=10.0,
        )
        # Wide window for the smooth() pass — exaggerated amplitudes so
        # smoothing doesn't tank them below the rate-min floor.
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0,
        )
        # Short clip → no multi-swing override → global argmax → peak_b
        assert 110 <= burst_peak_ <= 130

    def test_long_clip_single_burst_uses_global_argmax(self):
        """Long clip but only ONE distinct burst — current behavior
        preserved (peaks list has 1 element → fall through to argmax)."""
        fps = 60.0
        n = int(fps * 10.0)  # 10 seconds
        sig = _gaussian_burst(n, center=300, width=8, amplitude=10.0)
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0,
        )
        assert 290 <= burst_peak_ <= 310

    def test_long_clip_two_distinct_bursts_picks_first(self):
        """The headline Phase 4d case: long clip with two distinct
        significant peaks → pick the FIRST (the "intended" swing,
        not the strongest)."""
        fps = 60.0
        n = int(fps * 12.0)  # 12 seconds — well above MULTI_SWING_MIN_DURATION_S
        # Real swing at frame 200, warmup-or-second-swing at frame 600.
        # The second one is taller (the labeler-friendly case: real
        # swing is the strongest, but we want the first because in
        # validation the labeler marked the first).
        sig = _two_burst_signal(
            n=n, peak_a=200, peak_b=600, amp_a=8.0, amp_b=12.0,
        )
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0,
        )
        # First burst is picked
        assert 190 <= burst_peak_ <= 210, (
            f"Expected first burst (~200); got {burst_peak_}. "
            "Multi-swing detection should prefer the first significant burst."
        )

    def test_long_clip_with_weak_secondary_uses_strongest(self):
        """Long clip where the secondary peak is below the height ratio
        threshold — strongest still wins (it's the only "real" swing)."""
        fps = 60.0
        n = int(fps * 12.0)
        # Secondary at 0.3x amplitude of primary — below the 0.55 ratio
        sig = _two_burst_signal(
            n=n, peak_a=200, peak_b=600, amp_a=3.0, amp_b=10.0,
        )
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0,
        )
        # Primary peak (the 10.0 amplitude one) wins
        assert 590 <= burst_peak_ <= 610

    def test_three_bursts_picks_first(self):
        """Three distinct bursts — first still wins."""
        fps = 60.0
        n = int(fps * 18.0)
        sig = (
            _gaussian_burst(n, center=200, width=8, amplitude=8.0)
            + _gaussian_burst(n, center=600, width=8, amplitude=10.0)
            + _gaussian_burst(n, center=1000, width=8, amplitude=9.0)
        )
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0,
        )
        assert 190 <= burst_peak_ <= 210

    def test_prefer_first_burst_false_falls_back_to_argmax(self):
        """The flag is opt-out — passing False restores pre-4d behavior."""
        fps = 60.0
        n = int(fps * 12.0)
        sig = _two_burst_signal(
            n=n, peak_a=200, peak_b=600, amp_a=8.0, amp_b=12.0,
        )
        _, _, burst_peak_, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0, prefer_first_burst=False,
        )
        # Second burst (the strongest) wins
        assert 590 <= burst_peak_ <= 610


class TestCenterHint:
    """`center_hint` constrains burst-peak selection to a window around a given
    frame — used by the reference rebuild to lock onto the ground-truth swing on
    multi-event broadcast clips. Default None = unchanged behavior."""

    def test_hint_selects_burst_near_the_hint(self):
        fps = 60.0
        n = int(fps * 12.0)
        # First burst is the LOUDER one; default prefer-first would pick it.
        sig = _two_burst_signal(n=n, peak_a=200, peak_b=600, amp_a=12.0, amp_b=8.0)
        _, _, bp_default, _, _, _ = _find_burst_and_baseline(sig, fps, n, min_rate=0.0)
        assert 190 <= bp_default <= 210
        # Hint near the SECOND burst → pick it instead.
        _, _, bp_hint, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0, center_hint=600)
        assert 590 <= bp_hint <= 610

    def test_hint_ignores_louder_burst_outside_window(self):
        fps = 60.0
        n = int(fps * 12.0)
        # Intended swing is the SMALLER burst; a louder distractor sits far off.
        sig = _two_burst_signal(n=n, peak_a=300, peak_b=650, amp_a=6.0, amp_b=12.0)
        _, _, bp, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0, center_hint=300)
        assert 290 <= bp <= 310

    def test_hint_none_matches_default(self):
        fps = 60.0
        n = int(fps * 12.0)
        sig = _two_burst_signal(n=n, peak_a=200, peak_b=600, amp_a=8.0, amp_b=12.0)
        a = _find_burst_and_baseline(sig, fps, n, min_rate=0.0)
        b = _find_burst_and_baseline(sig, fps, n, min_rate=0.0, center_hint=None)
        assert a == b

    def test_hint_clamped_into_range(self):
        fps = 60.0
        n = int(fps * 12.0)
        sig = _gaussian_burst(n, center=300, width=8, amplitude=10.0)
        # An out-of-range hint shouldn't crash; clamps and still finds the burst.
        _, _, bp, _, _, _ = _find_burst_and_baseline(
            sig, fps, n, min_rate=0.0, center_hint=99999)
        assert 0 <= bp < n


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
