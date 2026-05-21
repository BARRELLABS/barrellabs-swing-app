"""
phase_debug.py — PHASE_DEBUG_V1 instrumentation for swing phase detection.

OBSERVABILITY-ONLY MODULE. This module does NOT modify any phase indices,
metric values, or scoring produced by `detect_phases.py`. It computes a
parallel set of observations:

  - All stable-contact periods of the front foot (not just the one the
    legacy detector picked)
  - A "rotation_onset" frame, derived independently from hip velocity
  - Stride-style classification: no_stride / standard_stride / toe_tap /
    leg_kick / uncertain
  - Per-phase confidence scores with one-line "reason" strings
  - Alternatives[] for foot_plant — other plausible plant candidates
  - Warnings[] for known failure modes (multiple contacts, low confidence,
    contact too soon after foot plant, poor pose visibility, toe-tap
    suspected, low handedness confidence, edge-of-video phases)

Activated by setting the environment variable PHASE_DEBUG_V1 to one of
{1, true, yes, on} (case-insensitive). When off, this module is not
imported and detect_phases.py runs exactly as before.

See the Phase 1 implementation plan for the long-form rationale.
"""

from __future__ import annotations

import math
import os
from typing import Iterable, Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

STRIDE_STYLES = ("no_stride", "standard_stride", "toe_tap", "leg_kick", "uncertain")

# Stable-contact period thresholds
STABLE_CONTACT_MIN_MS = 80.0
GROUND_PERCENTILE = 80          # higher Y in image coords = ankle on ground
GROUND_EPS_MAD_MULT = 1.5
VELOCITY_EPS_MAD_MULT = 2.0

# Rotation onset
ROTATION_ONSET_THRESHOLD = 0.15  # fraction of peak |hip_vel|
ROTATION_ONSET_MAX_BACK_MS = 400.0

# Stride-style classification heuristics
LEG_KICK_LIFT_TORSO_FRAC = 0.55
NO_STRIDE_LIFT_TORSO_FRAC = 0.05

# Temporal sanity checks
FOOT_PLANT_TO_CONTACT_MIN_MS = 80.0
FOOT_PLANT_TO_CONTACT_MAX_MS = 350.0

# Visibility thresholds (lm.visibility is in [0, 1])
LOW_VISIBILITY_THRESHOLD = 0.6
MARGINAL_VISIBILITY_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled(env: Optional[dict] = None) -> bool:
    """Return True iff PHASE_DEBUG_V1 env var is set to a truthy value."""
    src = env if env is not None else os.environ
    raw = str(src.get("PHASE_DEBUG_V1", "")).strip().lower()
    return raw in _TRUTHY


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mad(arr: np.ndarray) -> float:
    """Median absolute deviation. Robust analogue of std deviation."""
    if len(arr) == 0:
        return 0.0
    med = float(np.median(arr))
    return float(np.median(np.abs(np.asarray(arr, dtype=float) - med)))


def _time_at(times: np.ndarray, frame: int) -> Optional[float]:
    if frame is None or frame < 0 or frame >= len(times):
        return None
    return float(times[frame])


def _close_short_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Fill stretches of False of length <= `max_gap` that are bounded on
    both sides by True. Used to smooth single-frame landmark jitter inside
    an otherwise-stable foot-contact period.
    """
    if max_gap <= 0 or len(mask) == 0:
        return mask
    out = np.asarray(mask, dtype=bool).copy()
    L = len(out)
    i = 0
    while i < L:
        if out[i]:
            i += 1
            continue
        j = i
        while j < L and not out[j]:
            j += 1
        gap_len = j - i
        if i > 0 and j < L and gap_len <= max_gap:
            out[i:j] = True
        i = j
    return out


# ---------------------------------------------------------------------------
# Candidate enumeration
# ---------------------------------------------------------------------------


def find_stable_contact_periods(
    fa_y: np.ndarray,
    fa_y_vel: np.ndarray,
    vis_fa: Optional[np.ndarray],
    *,
    ground_floor: float,
    ground_eps: float,
    velocity_eps: float,
    lo: int,
    hi: int,
    fps: float,
    min_duration_ms: float = STABLE_CONTACT_MIN_MS,
) -> list[dict]:
    """Return contiguous frame runs where the front ankle satisfies all of:

        fa_y >= ground_floor - ground_eps
        |fa_y_vel| <= velocity_eps
        visibility >= LOW_VISIBILITY_THRESHOLD (when visibility is provided)

    AND the run is at least `min_duration_ms` long.

    Each returned dict contains: start_frame, end_frame (inclusive),
    duration_ms, mean_y, mean_abs_vel, min_visibility (or None).
    """
    fa_y = np.asarray(fa_y, dtype=float)
    fa_y_vel = np.asarray(fa_y_vel, dtype=float)
    n = len(fa_y)
    lo = max(0, int(lo))
    hi = min(n, int(hi))
    if hi <= lo or fps <= 0:
        return []

    min_frames = max(1, int(round(fps * (min_duration_ms / 1000.0))))

    on_ground = fa_y[lo:hi] >= (ground_floor - ground_eps)
    quiet = np.abs(fa_y_vel[lo:hi]) <= velocity_eps
    if vis_fa is not None:
        vis_arr = np.asarray(vis_fa, dtype=float)
        vis_ok = vis_arr[lo:hi] >= LOW_VISIBILITY_THRESHOLD
    else:
        vis_ok = np.ones_like(on_ground, dtype=bool)
    mask = on_ground & quiet & vis_ok

    # Close 1-2 frame false gaps inside otherwise-stable runs. MediaPipe
    # landmark jitter can cause single-frame velocity spikes inside a real
    # foot-down period; without this we'd shatter one true contact into
    # several short ones below the min-duration cutoff.
    mask = _close_short_gaps(mask, max_gap=2)

    runs: list[dict] = []
    i = 0
    L = len(mask)
    while i < L:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < L and mask[j]:
            j += 1
        # local indices [i, j) → global frame range [start, end] inclusive
        dur_frames = j - i
        if dur_frames >= min_frames:
            start = lo + i
            end = lo + j - 1
            mean_y = float(np.mean(fa_y[start:end + 1]))
            mean_abs_vel = float(np.mean(np.abs(fa_y_vel[start:end + 1])))
            min_vis: Optional[float] = None
            if vis_fa is not None:
                min_vis = float(np.min(np.asarray(vis_fa)[start:end + 1]))
            runs.append({
                "start_frame": int(start),
                "end_frame": int(end),
                "duration_ms": float(dur_frames * 1000.0 / fps),
                "mean_y": mean_y,
                "mean_abs_vel": mean_abs_vel,
                "min_visibility": min_vis,
            })
        i = j
    return runs


def rotation_onset_frame(
    hip_vel: np.ndarray,
    *,
    contact: int,
    burst_lo: int,
    fps: float,
    threshold_ratio: float = ROTATION_ONSET_THRESHOLD,
    max_back_ms: float = ROTATION_ONSET_MAX_BACK_MS,
) -> int:
    """Walk backward from `contact` until |hip_vel| first drops below
    `threshold_ratio * |hip_vel[contact]|`. Bounded by `burst_lo` and
    `contact - fps * max_back_ms/1000`. Returns a frame index.

    Independent of foot-plant. Observational only.
    """
    hip_vel = np.asarray(hip_vel, dtype=float)
    n = len(hip_vel)
    if n == 0 or contact < 0:
        return max(0, contact)
    contact = min(contact, n - 1)
    peak_vel = abs(float(hip_vel[contact]))
    if peak_vel <= 0:
        return contact
    threshold = peak_vel * threshold_ratio
    floor = max(int(burst_lo), int(contact - round(fps * (max_back_ms / 1000.0))), 0)
    onset = contact
    while onset > floor and abs(float(hip_vel[onset - 1])) >= threshold:
        onset -= 1
    return int(onset)


# ---------------------------------------------------------------------------
# Stride-style classification
# ---------------------------------------------------------------------------


def classify_stride_style(
    contacts: Sequence[dict],
    *,
    fa_y: np.ndarray,
    foot_plant: int,
    contact: int,
    burst_lo: int,
    torso_length_px: float,
    fps: float,
) -> tuple[str, str]:
    """Classify the swing's stride pattern. Returns (style, reason).

    Rules (in priority order):
      1. leg_kick — front ankle lifted >= LEG_KICK_LIFT_TORSO_FRAC of torso
         length during the load window. (Wins even if a brief contact
         happened earlier — leg-kicks can include a momentary plant.)
      2. toe_tap — at least one stable contact starts more than ~50 ms before
         foot_plant.
      3. no_stride — total front-ankle lift < NO_STRIDE_LIFT_TORSO_FRAC of
         torso length.
      4. standard_stride — at least one stable contact present, moderate lift.
      5. uncertain — none of the above can be determined reliably.
    """
    fa_y = np.asarray(fa_y, dtype=float)
    if torso_length_px <= 0:
        return ("uncertain", "torso_length unavailable")
    lo = max(0, int(burst_lo - fps * 1.0))
    hi = min(len(fa_y), int(contact) + 1)
    if hi <= lo:
        return ("uncertain", "empty load window")
    window = fa_y[lo:hi]
    ground_y = float(np.percentile(window, GROUND_PERCENTILE))
    min_y = float(np.min(window))
    lift_px = max(0.0, ground_y - min_y)
    lift_frac = lift_px / torso_length_px if torso_length_px > 0 else 0.0
    n_contacts = len(contacts)

    # Leg-kick wins on lift magnitude — even a leg-kick can include a brief
    # plant before the kick, so contact count is not the discriminator here.
    if lift_frac >= LEG_KICK_LIFT_TORSO_FRAC:
        return ("leg_kick",
                f"front ankle lift = {lift_frac:.2f}× torso "
                f"(>= {LEG_KICK_LIFT_TORSO_FRAC})")

    # Three or more stable contacts in the load window = stance + tap + plant
    # (and possibly more). Two = stance + plant (standard). One = continuous
    # contact (no-stride).
    #
    # Phase 4a Fix 2: the bare contact-count rule over-predicts toe_tap on
    # standard strides because MediaPipe jitter often splits a single stance
    # into 2–4 contacts with no real lift between them. Before believing
    # "3 contacts = toe_tap" we verify there are at least TWO real lifts
    # (gaps where the foot meaningfully left the ground) interspersed.
    #
    # Phase 4b note: I tried loosening to 1 real lift + 5% torso threshold
    # to catch the user-labeled toe-taps but it re-introduced false
    # positives — a jitter-split stance + ONE stride lift is indistinguishable
    # from a real toe-tap under a 1-lift rule. Reverted to 2-lifts +
    # 8% torso. The 0/10 toe-tap accuracy issue requires a more thoughtful
    # rewrite (likely needing a richer per-contact feature set rather than
    # just gap-and-lift counting) and is left for Phase 4c.
    if n_contacts >= 3:
        contacts_sorted = sorted(contacts, key=lambda c: c["start_frame"])
        real_lifts = 0
        for i in range(len(contacts_sorted) - 1):
            a = contacts_sorted[i]
            b = contacts_sorted[i + 1]
            gap_start = int(a["end_frame"]) + 1
            gap_end = int(b["start_frame"])
            if gap_end <= gap_start:
                continue
            gap_ms = (gap_end - gap_start) * 1000.0 / fps if fps > 0 else 0.0
            if gap_ms < 50.0:
                continue
            between_y = fa_y[gap_start:gap_end]
            if len(between_y) == 0:
                continue
            lift_during_gap = ground_y - float(np.min(between_y))
            if lift_during_gap / torso_length_px >= 0.08:
                real_lifts += 1
        if real_lifts >= 2:
            return ("toe_tap",
                    f"{n_contacts} stable contacts with {real_lifts} real "
                    "lifts between them (stance + tap(s) + final plant)")
        # Multiple contacts but no real lifts → jitter/noise. Fall through
        # to the standard-stride logic below rather than calling it toe_tap.
    if n_contacts == 2:
        return ("standard_stride",
                f"2 stable contacts (stance + plant), lift {lift_frac:.2f}× torso")
    if n_contacts == 1 and lift_frac < NO_STRIDE_LIFT_TORSO_FRAC:
        return ("no_stride",
                f"1 continuous contact, lift {lift_frac:.2f}× torso "
                f"(< {NO_STRIDE_LIFT_TORSO_FRAC})")
    if n_contacts == 1:
        return ("standard_stride",
                f"1 contact spanning foot_plant, lift {lift_frac:.2f}× torso")
    return ("uncertain",
            f"no stable contact found (lift = {lift_frac:.2f}× torso)")


# ---------------------------------------------------------------------------
# Per-phase confidence scorers
# ---------------------------------------------------------------------------


def score_foot_plant_confidence(
    plant_run: Optional[dict],
    contacts: Sequence[dict],
    *,
    velocity_eps: float,
    rot_onset: int,
    contact: int,
    foot_plant: int,
    fps: float,
) -> tuple[float, str]:
    """Confidence score in [0, 1] for the selected foot_plant frame.

    Penalties (subtractive from base=1.0):
      - duration < 60 ms                       -0.40
      - duration < 100 ms                      -0.15
      - mean |fa_y_vel| > 2 × velocity_eps     -0.30
      - min visibility < 0.6                   -0.50
      - min visibility < 0.75                  -0.20
      - each additional contact within ~100 ms
        of rotation_onset                      -0.20
      - foot_plant→contact outside [80, 350]ms -0.40
    """
    if plant_run is None:
        return (0.30, "selected foot_plant lies outside any stable-contact period")
    base = 1.0
    reasons: list[str] = []

    duration_ms = float(plant_run.get("duration_ms", 0.0))
    if duration_ms < 60.0:
        base -= 0.40
        reasons.append(f"short contact ({duration_ms:.0f} ms)")
    elif duration_ms < 100.0:
        base -= 0.15
        reasons.append(f"brief contact ({duration_ms:.0f} ms)")

    mean_abs_vel = float(plant_run.get("mean_abs_vel", 0.0))
    if velocity_eps > 0 and mean_abs_vel > 2.0 * velocity_eps:
        base -= 0.30
        reasons.append(f"unstable vertical velocity (|v|={mean_abs_vel:.1f})")

    min_vis = plant_run.get("min_visibility")
    if min_vis is not None:
        if min_vis < LOW_VISIBILITY_THRESHOLD:
            base -= 0.50
            reasons.append(f"ankle visibility low ({min_vis:.2f})")
        elif min_vis < MARGINAL_VISIBILITY_THRESHOLD:
            base -= 0.20
            reasons.append(f"ankle visibility marginal ({min_vis:.2f})")

    ambiguous = 0
    for c in contacts:
        if c is plant_run:
            continue
        if abs(int(c["start_frame"]) - int(rot_onset)) < max(1, int(fps * 0.1)):
            ambiguous += 1
    if ambiguous:
        base -= 0.20 * ambiguous
        reasons.append(f"{ambiguous} ambiguous contact(s) near rotation onset")

    if fps > 0:
        fp_to_contact_ms = (contact - foot_plant) * 1000.0 / fps
        if not (FOOT_PLANT_TO_CONTACT_MIN_MS <= fp_to_contact_ms
                <= FOOT_PLANT_TO_CONTACT_MAX_MS):
            base -= 0.40
            reasons.append(
                f"foot_plant→contact {fp_to_contact_ms:.0f} ms out of range "
                f"[{FOOT_PLANT_TO_CONTACT_MIN_MS:.0f}, {FOOT_PLANT_TO_CONTACT_MAX_MS:.0f}]"
            )

    confidence = max(0.0, min(1.0, base))
    reason = "; ".join(reasons) if reasons else "stable contact aligned with rotation onset"
    return (confidence, reason)


def score_contact_confidence(
    hip_vel: np.ndarray,
    *,
    contact: int,
    burst_lo: int,
    burst_hi: int,
) -> tuple[float, str]:
    """Confidence based on prominence of |hip_vel| peak at contact."""
    hip_vel = np.asarray(hip_vel, dtype=float)
    n = len(hip_vel)
    if n == 0 or contact < 0 or contact >= n:
        return (0.0, "contact frame out of bounds")
    peak_vel = abs(float(hip_vel[contact]))
    if peak_vel <= 0:
        return (0.20, "zero peak hip velocity")
    lo = max(0, int(burst_lo) - 1)
    hi = min(n, int(burst_hi) + 2)
    if hi - lo <= 1:
        return (0.50, "burst window too narrow to assess prominence")
    window = np.abs(hip_vel[lo:hi])
    background = float(np.median(window))
    prominence = (peak_vel - background) / peak_vel if peak_vel > 0 else 0.0
    if prominence >= 0.7:
        return (0.95, f"sharp peak (prominence={prominence:.2f})")
    if prominence >= 0.5:
        return (0.85, f"clear peak (prominence={prominence:.2f})")
    if prominence >= 0.3:
        return (0.65, f"moderate peak (prominence={prominence:.2f})")
    return (0.40, f"low-prominence peak (prominence={prominence:.2f})")


def score_launch_confidence(
    *,
    burst_lo: int,
    burst_hi: int,
    foot_plant: int,
    contact: int,
    launch: int,
) -> tuple[float, str]:
    """Confidence based on burst clarity and temporal ordering."""
    if not (foot_plant <= launch <= contact):
        return (0.30, "launch frame violates ordering")
    burst_width = max(1, int(burst_hi) - int(burst_lo))
    if burst_width < 3:
        return (0.40, f"burst window very narrow ({burst_width} frames)")
    return (0.85, f"burst width {burst_width} frames; launch in [foot_plant, contact]")


def score_load_start_confidence(
    stride: np.ndarray,
    knee: np.ndarray,
    *,
    load_start: int,
    foot_plant: int,
    fps: float,
) -> tuple[float, str]:
    """Confidence based on baseline separation between pre-load and load."""
    stride = np.asarray(stride, dtype=float)
    knee = np.asarray(knee, dtype=float)
    n = len(stride)
    if not (0 <= int(load_start) <= int(foot_plant) < n):
        return (0.20, "load_start violates ordering")
    pre_end = max(5, int(foot_plant) - int(fps * 0.5))
    if pre_end <= 5:
        return (0.40, "pre-load window too short")
    stride_baseline = float(np.percentile(stride[:pre_end], 25))
    knee_baseline = float(np.percentile(knee[:pre_end], 75))
    stride_delta = float(stride[int(foot_plant)]) - stride_baseline
    knee_delta = knee_baseline - float(knee[int(foot_plant)])
    score = 0.5
    if stride_delta > 20.0:
        score += 0.25
    elif stride_delta > 10.0:
        score += 0.10
    if knee_delta > 15.0:
        score += 0.25
    elif knee_delta > 5.0:
        score += 0.10
    return (max(0.0, min(1.0, score)),
            f"stride Δ={stride_delta:.1f}px, knee Δ={knee_delta:.1f}°")


def score_rotation_onset_confidence(
    hip_vel: np.ndarray,
    *,
    rot_onset: int,
    contact: int,
) -> tuple[float, str]:
    hip_vel = np.asarray(hip_vel, dtype=float)
    n = len(hip_vel)
    if not (0 <= int(rot_onset) <= int(contact) < n):
        return (0.30, "rotation_onset violates ordering")
    peak_vel = abs(float(hip_vel[int(contact)]))
    if peak_vel <= 0:
        return (0.20, "zero peak hip velocity")
    onset_vel = abs(float(hip_vel[int(rot_onset)]))
    ratio = onset_vel / peak_vel
    if ratio <= 0.20:
        return (0.90, f"clean threshold crossing at {ratio:.2f}× peak")
    if ratio <= 0.35:
        return (0.70, f"acceptable crossing at {ratio:.2f}× peak")
    return (0.50, f"slow drop to threshold ({ratio:.2f}× peak)")


def score_stride_style_confidence(
    style: str,
    contacts: Sequence[dict],
    *,
    foot_plant: int,
    fps: float,
) -> tuple[float, str]:
    """Confidence in the stride-style classification itself."""
    if style == "uncertain":
        return (0.20, "could not classify with available signals")
    if style == "no_stride":
        if len(contacts) >= 1:
            return (0.80, "minimal lift, stable contact persists")
        return (0.50, "minimal lift but no stable contact period")
    if style == "toe_tap":
        if len(contacts) >= 3 and all(c["duration_ms"] >= 80.0 for c in contacts):
            return (0.90, f"{len(contacts)} stable contacts, all >= 80 ms")
        if len(contacts) >= 3:
            return (0.75, f"{len(contacts)} stable contacts (some brief)")
        return (0.55, "stable contacts present but ambiguous")
    if style == "leg_kick":
        return (0.80, "large vertical lift detected")
    if style == "standard_stride":
        if len(contacts) == 2:
            return (0.85, "exactly two stable contacts (stance + plant)")
        if len(contacts) == 1:
            return (0.70, "single stable contact spanning foot_plant")
        return (0.55, "stride pattern present but contact count unusual")
    return (0.0, "unknown style label")


# ---------------------------------------------------------------------------
# Alternatives + warnings
# ---------------------------------------------------------------------------


def build_alternatives(
    contacts: Sequence[dict],
    *,
    selected_foot_plant: int,
    times: np.ndarray,
    rot_onset: int,
    fps: float,
    top_k: int = 3,
) -> list[dict]:
    """Return up to `top_k` alternative foot-plant candidates (other than the
    one the legacy detector picked), ranked by closeness to rotation onset.
    """
    times = np.asarray(times)
    n = len(times)
    ranked: list[dict] = []
    for c in contacts:
        if int(c["start_frame"]) == int(selected_foot_plant):
            continue
        s = int(c["start_frame"])
        e = int(c["end_frame"])
        if s <= rot_onset <= e:
            closeness = 1.0
            label = "alternative_final_plant"
        elif e < rot_onset:
            label = "toe_tap_candidate"
            span = max(1, int(fps * 0.3))
            closeness = max(0.0, 1.0 - (rot_onset - e) / span)
        else:
            label = "post_rotation_contact"
            closeness = 0.0
        ranked.append({
            "frame": s,
            "time_s": float(times[s]) if 0 <= s < n else None,
            "duration_ms": float(c["duration_ms"]),
            "confidence": float(round(closeness, 3)),
            "label": label,
            "reason": (f"stable contact start={s} end={e} "
                       f"dur={c['duration_ms']:.0f}ms"),
        })
    ranked.sort(key=lambda r: r["confidence"], reverse=True)
    return ranked[:top_k]


def build_warnings(
    *,
    stride_style: str,
    foot_plant_conf: float,
    contacts: Sequence[dict],
    foot_plant: int,
    contact: int,
    fps: float,
    fa_visibility_window_min: Optional[float],
    handedness_ratio: Optional[float],
    edge_warnings: Iterable[str],
) -> list[dict]:
    """Return list of {code, severity, message} warnings.

    Severities:
      - "info"  → informational (e.g. toe-tap suspected)
      - "warn"  → likely measurement issue
      - "error" → strong evidence the result cannot be trusted
    """
    out: list[dict] = []

    # Multiple stable contacts in the candidate window — either the legacy
    # detector picked the tap (real plant is LATER), or it picked the plant
    # correctly and a tap exists EARLIER. Both are diagnostic.
    if len(contacts) >= 2:
        margin = int(fps * 0.05)
        before = sum(1 for c in contacts if c["end_frame"] < foot_plant - margin)
        after = sum(1 for c in contacts if c["start_frame"] > foot_plant + margin)
        out.append({
            "code": "multiple_foot_contacts",
            "severity": "warn",
            "message": (f"{len(contacts)} stable foot-contact periods detected "
                        f"({before} before / {after} after the selected foot_plant) "
                        "— may indicate a toe-tap stride."),
        })

    if foot_plant_conf < 0.5:
        out.append({
            "code": "low_foot_plant_confidence",
            "severity": "warn" if foot_plant_conf >= 0.3 else "error",
            "message": f"Foot plant confidence is {foot_plant_conf:.2f}.",
        })

    if fps > 0:
        fp_to_contact_ms = (contact - foot_plant) * 1000.0 / fps
        if fp_to_contact_ms < FOOT_PLANT_TO_CONTACT_MIN_MS:
            out.append({
                "code": "contact_too_soon_after_foot_plant",
                "severity": "warn",
                "message": (f"Contact is only {fp_to_contact_ms:.0f} ms after "
                            f"foot_plant (< {FOOT_PLANT_TO_CONTACT_MIN_MS:.0f} ms)."),
            })
        elif fp_to_contact_ms > FOOT_PLANT_TO_CONTACT_MAX_MS:
            out.append({
                "code": "foot_plant_to_contact_too_long",
                "severity": "warn",
                "message": (f"Foot plant → contact is {fp_to_contact_ms:.0f} ms "
                            f"(> {FOOT_PLANT_TO_CONTACT_MAX_MS:.0f} ms). "
                            "Possible slow-motion clip or mis-detection."),
            })

    if fa_visibility_window_min is not None and fa_visibility_window_min < LOW_VISIBILITY_THRESHOLD:
        out.append({
            "code": "poor_pose_visibility",
            "severity": "warn",
            "message": (f"Front-ankle visibility dropped to "
                        f"{fa_visibility_window_min:.2f} during the plant window."),
        })

    if stride_style == "toe_tap":
        out.append({
            "code": "toe_tap_suspected",
            "severity": "info",
            "message": ("Toe-tap stride pattern suspected. The legacy detector "
                        "may anchor foot_plant to the tap rather than the final "
                        "plant; treat phase-anchored metrics with caution until "
                        "the Phase 2 detector ships."),
        })

    if handedness_ratio is not None and handedness_ratio < 1.3:
        out.append({
            "code": "low_handedness_confidence",
            "severity": "info",
            "message": (f"Handedness auto-detection ratio = {handedness_ratio:.2f} "
                        "(< 1.3). Both feet moved similarly in the early window."),
        })

    for w in edge_warnings:
        msg = str(w).strip()
        if msg:
            out.append({
                "code": "phase_at_video_edge",
                "severity": "warn",
                "message": msg,
            })

    return out


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def build_debug_payload(
    *,
    times: np.ndarray,
    fa_y: np.ndarray,
    vis_fa: Optional[np.ndarray],
    hip_vel: np.ndarray,
    stride: np.ndarray,
    knee: np.ndarray,
    phases: dict,
    burst_lo: int,
    burst_hi: int,
    burst_peak: int,
    fps: float,
    torso_length_px: float,
    handedness: str,
    handedness_ratio: Optional[float],
    edge_warnings: Iterable[str],
) -> dict:
    """Compute the full analysis_debug payload.

    All inputs come straight from `detect_phases.py` AFTER the existing
    detector has run. Nothing here mutates any of those inputs.
    """
    times = np.asarray(times)
    fa_y = np.asarray(fa_y, dtype=float)
    hip_vel = np.asarray(hip_vel, dtype=float)
    stride = np.asarray(stride, dtype=float)
    knee = np.asarray(knee, dtype=float)
    if vis_fa is not None:
        vis_fa = np.asarray(vis_fa, dtype=float)
    n = len(times)

    foot_plant = int(phases["foot_plant"])
    contact = int(phases["contact"])
    launch = int(phases["launch"])
    load_start = int(phases["load_start"])

    # --- Front-ankle vertical velocity (pixels/sec) ---
    if n >= 2 and fps > 0:
        fa_y_vel = np.gradient(fa_y) * float(fps)
    else:
        fa_y_vel = np.zeros(n)

    # --- Learn "ground" + epsilons from pre-burst posture ---
    pre_lo = max(0, int(burst_lo - fps * 1.5))
    pre_hi = max(pre_lo + 5, int(burst_lo - fps * 0.1))
    pre_hi = min(pre_hi, n)
    if pre_hi - pre_lo >= 5:
        pre_y = fa_y[pre_lo:pre_hi]
        pre_v = fa_y_vel[pre_lo:pre_hi]
        ground_floor = float(np.percentile(pre_y, GROUND_PERCENTILE))
        ground_eps = max(1.0, _mad(pre_y) * GROUND_EPS_MAD_MULT)
        velocity_eps = max(1.0, _mad(pre_v) * VELOCITY_EPS_MAD_MULT)
    else:
        ground_floor = float(np.percentile(fa_y, GROUND_PERCENTILE)) if n > 0 else 0.0
        ground_eps = max(1.0, _mad(fa_y) * GROUND_EPS_MAD_MULT)
        velocity_eps = max(1.0, _mad(fa_y_vel) * VELOCITY_EPS_MAD_MULT)

    # --- Enumerate stable-contact periods in the candidate window ---
    # Window: 2.0 s before the swing burst through contact. Wide enough to
    # capture initial stance (which is the cleanest contact period in most
    # clips) on top of any toe-tap touches inside the load phase.
    cand_lo = max(0, int(burst_lo - fps * 2.0))
    cand_hi = min(n, contact + 1)
    contacts = find_stable_contact_periods(
        fa_y, fa_y_vel, vis_fa,
        ground_floor=ground_floor,
        ground_eps=ground_eps,
        velocity_eps=velocity_eps,
        lo=cand_lo,
        hi=cand_hi,
        fps=float(fps),
    )

    # --- Locate the stable-contact period containing the legacy foot_plant.
    # Fall back to nearest if foot_plant lies outside any stable period (this
    # is the case the toe-tap bug typically produces).
    plant_run: Optional[dict] = None
    for c in contacts:
        if c["start_frame"] <= foot_plant <= c["end_frame"]:
            plant_run = c
            break
    if plant_run is None and contacts:
        plant_run = min(contacts, key=lambda c: abs(c["start_frame"] - foot_plant))

    # --- Rotation onset (observational, independent of foot_plant) ---
    rot_onset = rotation_onset_frame(
        hip_vel, contact=contact, burst_lo=burst_lo, fps=float(fps),
    )

    # --- Stride-style classification ---
    stride_style, style_reason = classify_stride_style(
        contacts,
        fa_y=fa_y,
        foot_plant=foot_plant,
        contact=contact,
        burst_lo=burst_lo,
        torso_length_px=float(torso_length_px),
        fps=float(fps),
    )
    style_conf, style_conf_reason = score_stride_style_confidence(
        stride_style, contacts, foot_plant=foot_plant, fps=float(fps),
    )

    # --- Per-phase confidence ---
    fp_conf, fp_reason = score_foot_plant_confidence(
        plant_run, contacts,
        velocity_eps=velocity_eps,
        rot_onset=rot_onset,
        contact=contact,
        foot_plant=foot_plant,
        fps=float(fps),
    )
    ct_conf, ct_reason = score_contact_confidence(
        hip_vel, contact=contact, burst_lo=burst_lo, burst_hi=burst_hi,
    )
    ln_conf, ln_reason = score_launch_confidence(
        burst_lo=burst_lo, burst_hi=burst_hi,
        foot_plant=foot_plant, contact=contact, launch=launch,
    )
    ls_conf, ls_reason = score_load_start_confidence(
        stride, knee, load_start=load_start, foot_plant=foot_plant, fps=float(fps),
    )
    ro_conf, ro_reason = score_rotation_onset_confidence(
        hip_vel, rot_onset=rot_onset, contact=contact,
    )

    # --- Alternatives ---
    alternatives = build_alternatives(
        contacts,
        selected_foot_plant=foot_plant,
        times=times,
        rot_onset=rot_onset,
        fps=float(fps),
    )

    # --- Visibility in the plant window (for warnings) ---
    fa_vis_window_min: Optional[float] = None
    if vis_fa is not None and plant_run is not None:
        s = int(plant_run["start_frame"])
        e = int(plant_run["end_frame"])
        if 0 <= s <= e < len(vis_fa):
            fa_vis_window_min = float(np.min(vis_fa[s:e + 1]))

    # --- Warnings ---
    warnings = build_warnings(
        stride_style=stride_style,
        foot_plant_conf=fp_conf,
        contacts=contacts,
        foot_plant=foot_plant,
        contact=contact,
        fps=float(fps),
        fa_visibility_window_min=fa_vis_window_min,
        handedness_ratio=handedness_ratio,
        edge_warnings=edge_warnings,
    )

    # --- Public-facing contact list (add start_time_s; no private fields) ---
    contacts_pub: list[dict] = []
    for c in contacts:
        s = int(c["start_frame"])
        e = int(c["end_frame"])
        contacts_pub.append({
            "start_frame": s,
            "end_frame": e,
            "start_time_s": _time_at(times, s),
            "end_time_s": _time_at(times, e),
            "duration_ms": float(c["duration_ms"]),
            "mean_y_px": float(c["mean_y"]),
            "mean_abs_vel_px_per_s": float(c["mean_abs_vel"]),
            "min_visibility": c.get("min_visibility"),
            "selected_as_foot_plant": (s <= foot_plant <= e),
        })

    return {
        "schema_version": "phase_debug_v1",
        "feature_flag": "PHASE_DEBUG_V1",
        "stride_style": stride_style,
        "stride_style_reason": style_reason,
        "stride_style_confidence": float(round(style_conf, 3)),
        "stride_style_confidence_reason": style_conf_reason,
        "selected_phases": {
            "load_start": {
                "frame": load_start,
                "time_s": _time_at(times, load_start),
                "confidence": float(round(ls_conf, 3)),
                "reason": ls_reason,
            },
            "foot_plant": {
                "frame": foot_plant,
                "time_s": _time_at(times, foot_plant),
                "confidence": float(round(fp_conf, 3)),
                "reason": fp_reason,
            },
            "launch": {
                "frame": launch,
                "time_s": _time_at(times, launch),
                "confidence": float(round(ln_conf, 3)),
                "reason": ln_reason,
            },
            "contact": {
                "frame": contact,
                "time_s": _time_at(times, contact),
                "confidence": float(round(ct_conf, 3)),
                "reason": ct_reason,
            },
            "rotation_onset": {
                "frame": int(rot_onset),
                "time_s": _time_at(times, int(rot_onset)),
                "confidence": float(round(ro_conf, 3)),
                "reason": ro_reason,
            },
        },
        "foot_plant_candidates": contacts_pub,
        "alternatives": alternatives,
        "ground_model": {
            "ground_floor_y_px": float(ground_floor),
            "ground_eps_px": float(ground_eps),
            "velocity_eps_px_per_s": float(velocity_eps),
            "pre_burst_window_frames": [int(pre_lo), int(pre_hi)],
            "candidate_window_frames": [int(cand_lo), int(cand_hi)],
        },
        "burst": {
            "lo_frame": int(burst_lo),
            "hi_frame": int(burst_hi),
            "peak_frame": int(burst_peak),
        },
        "handedness": {
            "label": handedness,
            "auto_confidence_ratio": (float(handedness_ratio)
                                       if handedness_ratio is not None else None),
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Pretty-print summary for stdout
# ---------------------------------------------------------------------------


def format_debug_summary(payload: dict) -> str:
    """Human-readable rendering of the debug payload for the detect_phases
    stdout log. Returns a multi-line string."""
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("              PHASE DEBUG V1 (observability)")
    lines.append("=" * 60)
    lines.append(f"  Stride style          : {payload['stride_style']} "
                 f"(conf {payload['stride_style_confidence']:.2f}) — "
                 f"{payload['stride_style_reason']}")
    lines.append("")
    lines.append("  PER-PHASE CONFIDENCE")
    lines.append("  " + "-" * 56)
    for name, p in payload["selected_phases"].items():
        t = f"{p['time_s']:5.2f}s" if p["time_s"] is not None else "  n/a "
        lines.append(f"  {name:<16}  frame {p['frame']:>4}  t={t}  "
                     f"conf={p['confidence']:.2f}  — {p['reason']}")
    lines.append("")
    cands = payload["foot_plant_candidates"]
    lines.append(f"  FOOT-PLANT CANDIDATES (n={len(cands)})")
    lines.append("  " + "-" * 56)
    for c in cands:
        sel = "★" if c["selected_as_foot_plant"] else " "
        vis = (f"vis≥{c['min_visibility']:.2f}"
               if c["min_visibility"] is not None else "vis n/a")
        lines.append(f"  {sel} frame {c['start_frame']:>4}–{c['end_frame']:<4}  "
                     f"dur={c['duration_ms']:5.0f}ms  meanY={c['mean_y_px']:6.1f}px  "
                     f"|vel|={c['mean_abs_vel_px_per_s']:5.1f}  {vis}")
    lines.append("")
    alts = payload["alternatives"]
    if alts:
        lines.append(f"  ALTERNATIVES FOR FOOT-PLANT (top {len(alts)})")
        lines.append("  " + "-" * 56)
        for a in alts:
            t = f"{a['time_s']:5.2f}s" if a["time_s"] is not None else "  n/a "
            lines.append(f"  frame {a['frame']:>4}  t={t}  conf={a['confidence']:.2f}  "
                         f"label={a['label']}  — {a['reason']}")
        lines.append("")
    warns = payload["warnings"]
    if warns:
        lines.append(f"  WARNINGS ({len(warns)})")
        lines.append("  " + "-" * 56)
        for w in warns:
            sev = w["severity"].upper().ljust(5)
            lines.append(f"  [{sev}] {w['code']}: {w['message']}")
        lines.append("")
    return "\n".join(lines)
