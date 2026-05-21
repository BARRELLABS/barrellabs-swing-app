"""Swing-burst detection — pure numpy, no mediapipe / opencv deps.

Extracted from detect_phases.py so the burst-selection logic is
testable in isolation (detect_phases.py imports mediapipe at module
level, which makes unit-testing the helper functions painful).

The functions here decide WHICH frame range of the clip is "the swing"
— used by detect_phases.py (v3 pipeline) and indirectly by
phase_detector_v4 (which inherits the resulting rotation_onset,
contact, foot_plant frames from v3).

Phase 4d (2026-05-21) added multi-swing-aware peak selection: long
clips with multiple distinct rotation bursts now prefer the FIRST
significant burst over the strongest one. See the docstring on
`_find_burst_and_baseline` for the rationale.
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Smoothing — same window=5 moving average used by detect_phases.py
# ---------------------------------------------------------------------------


def smooth(arr, window: int = 5) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    out = np.copy(arr)
    half = window // 2
    for i in range(len(arr)):
        lo = max(0, i - half)
        hi = min(len(arr), i + half + 1)
        out[i] = np.mean(arr[lo:hi])
    return out


# ---------------------------------------------------------------------------
# Burst peak detection — multi-swing-aware (Phase 4d)
# ---------------------------------------------------------------------------


# Phase 4d: when a clip is long enough that it might contain multiple
# swings (e.g. warmup take + real take), prefer the FIRST distinct burst
# over the global argmax. Bounded by MIN_DURATION so short, clean clips
# fall through to the unchanged single-argmax behavior.
MULTI_SWING_MIN_DURATION_S = 5.0
MULTI_SWING_MIN_DISTANCE_S = 1.5
MULTI_SWING_HEIGHT_RATIO = 0.55


def _find_distinct_burst_peaks(
    rate_smooth: np.ndarray,
    *,
    min_height: float,
    min_distance_frames: int,
) -> list[int]:
    """Find indices of local maxima in `rate_smooth` that are >= min_height
    and at least min_distance_frames apart.

    Pure-numpy / no scipy dep. Greedy left-to-right enforcement of the
    distance constraint: we walk all local maxima, then keep only those
    whose predecessor in the output is far enough back.

    Used by `_find_burst_and_baseline` to spot multi-swing clips — when
    multiple distinct peaks are returned, the burst detector prefers the
    FIRST one (the "swing the user uploaded") rather than the strongest.
    """
    n = len(rate_smooth)
    if n < 3:
        return []
    # Local maxima (>= both neighbors, > at least one to break ties).
    candidates: list[int] = []
    for i in range(1, n - 1):
        v = rate_smooth[i]
        if v >= min_height and v > rate_smooth[i - 1] and v >= rate_smooth[i + 1]:
            candidates.append(i)
    # Greedy distance filter from the left.
    out: list[int] = []
    last_picked = -10 ** 9
    for c in candidates:
        if c - last_picked >= min_distance_frames:
            out.append(c)
            last_picked = c
    return out


def find_burst_and_baseline(
    rate_arr,
    fps_: float,
    n_: int,
    *,
    min_rate: float = 1.0,
    prefer_first_burst: bool = True,
):
    """Find the swing burst window in a rate-of-change signal.

    Returns (burst_lo, burst_hi, burst_peak_idx, peak_rate,
             base_start, base_end).

    Phase 4d — multi-swing-aware burst peak selection:

    On a single-swing clip, the global ``argmax`` of the smoothed rate
    is the swing's burst peak. But on multi-swing clips (warmup take +
    real take, multiple cuts, etc.), ``argmax`` lands on whichever swing
    is most violent — typically the LAST. Validation showed 5 long
    clips where the labeler marked swing #1's plant but every downstream
    phase (contact, rotation_onset, foot_plant) cascaded from the
    detector's pick of a later swing's burst.

    Fix: when ``prefer_first_burst`` is True (default) AND the clip is
    long enough that multi-swing content is plausible
    (>= MULTI_SWING_MIN_DURATION_S seconds), call
    `_find_distinct_burst_peaks` to enumerate all peaks >=
    MULTI_SWING_HEIGHT_RATIO of the global peak that are at least
    MULTI_SWING_MIN_DISTANCE_S apart. If two or more distinct peaks are
    returned, anchor the burst on the FIRST one.

    Short clips (< 5s) are untouched — keeps single-swing v3 behavior
    bit-identical for typical user uploads.
    """
    rate_smooth_ = smooth(rate_arr, window=5)
    global_peak_idx = int(np.argmax(rate_smooth_))
    global_peak_val = float(rate_smooth_[global_peak_idx])

    if (prefer_first_burst
            and global_peak_val > 0
            and n_ >= int(fps_ * MULTI_SWING_MIN_DURATION_S)):
        min_dist_frames = max(2, int(fps_ * MULTI_SWING_MIN_DISTANCE_S))
        min_height = global_peak_val * MULTI_SWING_HEIGHT_RATIO
        peaks = _find_distinct_burst_peaks(
            rate_smooth_, min_height=min_height,
            min_distance_frames=min_dist_frames,
        )
        if len(peaks) >= 2:
            # Multi-swing clip detected — prefer the first.
            burst_peak_ = int(peaks[0])
        else:
            burst_peak_ = global_peak_idx
    else:
        burst_peak_ = global_peak_idx

    peak_rate_ = float(rate_smooth_[burst_peak_])
    threshold_ = max(peak_rate_ * 0.3, min_rate)
    lo_ = burst_peak_
    while lo_ > 0 and rate_smooth_[lo_ - 1] >= threshold_:
        lo_ -= 1
    hi_ = burst_peak_
    while hi_ < n_ - 1 and rate_smooth_[hi_ + 1] >= threshold_:
        hi_ += 1
    burst_lo_ = max(0, lo_ - int(fps_ * 0.15))
    burst_hi_ = min(n_ - 1, hi_ + int(fps_ * 0.30))
    pre_gap_ = int(fps_ * 0.05)
    base_end_ = max(5, burst_lo_ - pre_gap_)
    base_start_ = max(0, base_end_ - int(fps_ * 1.0))
    if base_end_ - base_start_ < 5:
        base_start_, base_end_ = 0, max(5, min(n_, int(fps_ * 0.5)))
    return burst_lo_, burst_hi_, burst_peak_, peak_rate_, base_start_, base_end_
