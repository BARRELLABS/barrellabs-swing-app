"""
phase_detector_v4.py — toe-tap-aware phase detector (SHADOW MODE).

Phase 2 of the swing-analysis redesign. Runs ALONGSIDE the legacy v3
detector — never replaces it. The v3 outputs are unchanged; v4 emits a
parallel set of phases for comparison.

The key fix v4 makes over v3:

  v3:  foot_plant = argmax(fa_y[contact-0.6s:contact])
       → picks whichever frame has the highest front-ankle Y in a wide
         window, with no concept of stability. Toe-tap hitters get
         foot_plant anchored to the TAP instead of the final plant.

  v4:  foot_plant = best-scoring stable-contact period, ranked against
       rotation_onset and contact timing.
       → the final plant is the contact period the foot is in WHEN
         rotation begins.

Inputs: the analysis_debug payload produced by phase_debug.py, plus
the raw per-frame signals (so v4 can re-derive load_start, launch,
knee_min after picking a new foot_plant).

Outputs: a dict with `phases` (six-key dict mirroring v3's shape),
plus confidence, selection_reason, alternatives, and a diff against
v3 for side-by-side comparison.

Activated by env var DETECTOR_V4=true. When the flag is on,
PHASE_DEBUG_V1 is implicitly enabled (v4 cannot run without the
candidate list).
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Ranking weights — additive to a base of 0.0. Max possible raw score for a
# perfectly-aligned candidate ≈ 1.65 (rotation_onset_straddle + plant_timing +
# duration + visibility). We normalize to [0, 1] for confidence reporting.
RANK_STRADDLES_ROT_ONSET = 1.00
RANK_BEFORE_ROT_ONSET_NEAR = 0.70   # ends within 50 ms before rot_onset
RANK_BEFORE_ROT_ONSET_MID = 0.40    # ends within 150 ms before rot_onset
RANK_BEFORE_ROT_ONSET_FAR = 0.15    # ends within 500 ms before rot_onset
RANK_BEFORE_ROT_ONSET_STANCE = 0.02 # ends > 500 ms before rot_onset (likely stance)
RANK_AFTER_ROT_ONSET = 0.00         # starts after rot_onset (impossible-by-physics)

RANK_PLANT_TIMING_IN_RANGE = 0.30
RANK_PLANT_TIMING_NEAR_RANGE = 0.10

RANK_DURATION_LONG = 0.20   # >= 150 ms — typical final-plant duration
RANK_DURATION_OK = 0.10     # 80-150 ms

RANK_VISIBILITY_GOOD = 0.15  # min_visibility >= 0.75
RANK_VISIBILITY_OK = 0.05    # min_visibility >= 0.60

MAX_RAW_SCORE = (
    RANK_STRADDLES_ROT_ONSET + RANK_PLANT_TIMING_IN_RANGE
    + RANK_DURATION_LONG + RANK_VISIBILITY_GOOD
)  # ≈ 1.65

# Margin thresholds for confidence
MARGIN_STRONG = 0.50
MARGIN_MODERATE = 0.20

# Physiological foot_plant → contact range (matches phase_debug.py)
FOOT_PLANT_TO_CONTACT_MIN_MS = 80.0
FOOT_PLANT_TO_CONTACT_MAX_MS = 350.0
FOOT_PLANT_TO_CONTACT_NEAR_MIN_MS = 50.0
FOOT_PLANT_TO_CONTACT_NEAR_MAX_MS = 500.0


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled(env: Optional[dict] = None) -> bool:
    """Return True iff DETECTOR_V4 env var is set to a truthy value."""
    src = env if env is not None else os.environ
    raw = str(src.get("DETECTOR_V4", "")).strip().lower()
    return raw in _TRUTHY


# ---------------------------------------------------------------------------
# Candidate ranking
# ---------------------------------------------------------------------------


def score_candidate_as_final_plant(
    candidate: dict,
    *,
    rot_onset: int,
    contact: int,
    fps: float,
) -> tuple[float, list[str]]:
    """Score a single stable-contact candidate as a final-plant likelihood.

    Returns (score, reasons) where `score` is in [0, MAX_RAW_SCORE] and
    `reasons` is a list of one-line justifications for each component
    that contributed.
    """
    score = 0.0
    reasons: list[str] = []
    s = int(candidate["start_frame"])
    e = int(candidate["end_frame"])

    # ---- 1. Position relative to rotation_onset (dominant signal) ----
    if s <= rot_onset <= e:
        score += RANK_STRADDLES_ROT_ONSET
        reasons.append("contact straddles rotation_onset")
    elif e < rot_onset:
        gap_ms = (rot_onset - e) * 1000.0 / fps if fps > 0 else 0
        if gap_ms < 50.0:
            score += RANK_BEFORE_ROT_ONSET_NEAR
            reasons.append(f"ends {gap_ms:.0f}ms before rotation_onset")
        elif gap_ms < 150.0:
            score += RANK_BEFORE_ROT_ONSET_MID
            reasons.append(f"ends {gap_ms:.0f}ms before rotation_onset (mid)")
        elif gap_ms < 500.0:
            score += RANK_BEFORE_ROT_ONSET_FAR
            reasons.append(f"ends {gap_ms:.0f}ms before rotation_onset (far)")
        else:
            score += RANK_BEFORE_ROT_ONSET_STANCE
            reasons.append(f"ends {gap_ms:.0f}ms before rotation_onset (likely stance)")
    else:
        # s > rot_onset — candidate begins after rotation has already started.
        # Physically impossible to be the final plant, so the floor.
        score += RANK_AFTER_ROT_ONSET
        reasons.append("starts after rotation_onset (impossible as final plant)")

    # ---- 2. foot_plant → contact timing ----
    if fps > 0:
        fp_to_contact_ms = (contact - s) * 1000.0 / fps
        if FOOT_PLANT_TO_CONTACT_MIN_MS <= fp_to_contact_ms <= FOOT_PLANT_TO_CONTACT_MAX_MS:
            score += RANK_PLANT_TIMING_IN_RANGE
            reasons.append(f"plant→contact {fp_to_contact_ms:.0f}ms (in range)")
        elif (FOOT_PLANT_TO_CONTACT_NEAR_MIN_MS <= fp_to_contact_ms
              <= FOOT_PLANT_TO_CONTACT_NEAR_MAX_MS):
            score += RANK_PLANT_TIMING_NEAR_RANGE
            reasons.append(f"plant→contact {fp_to_contact_ms:.0f}ms (near range)")
        # else: 0 contribution

    # ---- 3. Duration ----
    duration_ms = float(candidate.get("duration_ms", 0.0))
    if duration_ms >= 150.0:
        score += RANK_DURATION_LONG
        reasons.append(f"duration {duration_ms:.0f}ms (long)")
    elif duration_ms >= 80.0:
        score += RANK_DURATION_OK
        reasons.append(f"duration {duration_ms:.0f}ms (ok)")

    # ---- 4. Visibility ----
    min_vis = candidate.get("min_visibility")
    if min_vis is not None:
        if min_vis >= 0.75:
            score += RANK_VISIBILITY_GOOD
            reasons.append(f"visibility ≥ {min_vis:.2f}")
        elif min_vis >= 0.60:
            score += RANK_VISIBILITY_OK
            reasons.append(f"visibility ≥ {min_vis:.2f} (marginal)")

    return (score, reasons)


def rank_candidates(
    candidates: Sequence[dict],
    *,
    rot_onset: int,
    contact: int,
    fps: float,
) -> list[dict]:
    """Score every candidate and return them sorted descending by score.

    Each returned dict includes the original candidate fields plus:
      - raw_score: float
      - reasons:   list[str]
      - rank:      0..N-1 (0 = best)
    """
    scored: list[dict] = []
    for c in candidates:
        score, reasons = score_candidate_as_final_plant(
            c, rot_onset=rot_onset, contact=contact, fps=fps,
        )
        scored.append({**c, "raw_score": float(score), "reasons": reasons})
    scored.sort(key=lambda r: r["raw_score"], reverse=True)
    for i, c in enumerate(scored):
        c["rank"] = i
    return scored


# ---------------------------------------------------------------------------
# Dependent-phase re-derivation
# ---------------------------------------------------------------------------


def _effective_anchor(
    candidate: dict,
    *,
    rot_onset: int,
    fps: float,
    near_window_ms: float = 200.0,
    long_stance_threshold_ms: float = 300.0,
) -> int:
    """Translate a candidate into the foot_plant frame we should report.

    For most candidates the candidate's ``start_frame`` IS the foot plant —
    it's the first frame the foot settled. But there are two cases where
    start_frame is the WRONG anchor:

    1. **Ends-before case** (Phase 4a Fix 1): candidate ends just before
       rotation_onset. Real on the no-stride pattern — foot stays on
       ground, lifts briefly, then contact. Anchor at end+1 (just before
       lift), not at start.

    2. **Straddle-long-stance case** (Phase 4b Fix 1 extension): candidate
       STRADDLES rotation_onset AND started ≥ ``long_stance_threshold_ms``
       before. This is the same no-stride pattern but the contact period
       happens to extend past rot_onset rather than ending just before it.
       Phase 3 → Phase 4a results showed this case wasn't being caught
       (img_8436 / img_8608 / mariotswing all still reporting frame=0).
       Anchor at rot_onset itself — that's the last on-ground frame
       before the swing begins.

    For normal toe-tap or standard-stride swings the candidate's start
    IS the plant — it's the first frame the foot settled after a real
    lift. Those candidates fall into neither remediation branch and the
    start frame is returned unchanged.
    """
    s = int(candidate["start_frame"])
    e = int(candidate["end_frame"])
    if s <= rot_onset <= e:
        # Straddle case — the contact spans rotation onset.
        # If the contact started a long time before rot_onset, it's a
        # stance that runs straight through the start of the swing —
        # anchor at rot_onset (Phase 4b Fix 1 extension).
        start_to_onset_ms = (
            (rot_onset - s) * 1000.0 / fps if fps > 0 else 0.0
        )
        if start_to_onset_ms >= long_stance_threshold_ms:
            return max(s, int(rot_onset))
        # Otherwise the contact started recently enough that start IS
        # plausibly the plant (e.g. a regular stride that landed right
        # before rotation onset).
        return s
    if s > rot_onset:
        # Starts after rotation_onset — unusual. Keep start as anchor.
        return s
    # Ends before rotation onset. If close (≤ near_window_ms), the
    # candidate is a stance that flowed straight into the swing — the
    # ANCHOR should be the last on-ground frame just before lift, not
    # the start of the stance period.
    gap_ms = (rot_onset - e) * 1000.0 / fps if fps > 0 else 0.0
    if gap_ms <= near_window_ms:
        return max(s, min(e + 1, int(rot_onset)))
    # Stance ends far before rotation_onset — the candidate is not the
    # plant at all (this case should fail scoring upstream). Keep start
    # as anchor for backwards compatibility.
    return s


def derive_load_start_v4(
    stride: np.ndarray,
    knee: np.ndarray,
    *,
    foot_plant_v4: int,
    fps: float,
    stride_delta: float = 5.0,
    knee_delta: float = 3.0,
) -> int:
    """Walk back from `foot_plant_v4` on stride + knee baseline.

    Mirrors v3's load_start algorithm exactly (detect_phases.py:617-630) —
    same percentile baselines, same delta thresholds, same search-floor of
    foot_plant - 1.0s. The only thing that differs is the anchor frame.
    """
    stride = np.asarray(stride, dtype=float)
    knee = np.asarray(knee, dtype=float)
    n = len(stride)
    if n == 0 or foot_plant_v4 <= 0 or foot_plant_v4 >= n:
        return max(0, foot_plant_v4 - 1)

    sk_end = max(5, foot_plant_v4 - int(fps * 0.5))
    if sk_end - 0 >= 5:
        stride_baseline = float(np.percentile(stride[:sk_end], 25))
        knee_baseline = float(np.percentile(knee[:sk_end], 75))
    else:
        fallback_hi = max(5, min(int(fps * 0.5), max(1, foot_plant_v4 - 2)))
        stride_baseline = (float(np.median(stride[:fallback_hi]))
                           if fallback_hi > 0 else 0.0)
        knee_baseline = (float(np.median(knee[:fallback_hi]))
                         if fallback_hi > 0 else 180.0)

    load_search_floor = max(0, foot_plant_v4 - int(fps * 1.0))
    load_start: Optional[int] = None
    for i in range(foot_plant_v4, load_search_floor - 1, -1):
        if (stride[i] - stride_baseline < stride_delta
                and knee_baseline - knee[i] < knee_delta):
            load_start = i + 1
            break
    if load_start is None or load_start >= foot_plant_v4:
        load_start = max(load_search_floor, foot_plant_v4 - int(fps * 0.5))
    return int(load_start)


def derive_launch_v4(
    *,
    foot_plant_v4: int,
    contact: int,
    burst_lo: int,
) -> int:
    """launch = max(foot_plant_v4 + 1, burst_lo), clamped below contact."""
    launch = max(int(foot_plant_v4) + 1, int(burst_lo))
    if contact > foot_plant_v4 + 1:
        launch = min(launch, int(contact) - 1)
    return int(launch)


def derive_knee_min_v4(
    knee: np.ndarray,
    *,
    load_start_v4: int,
    foot_plant_v4: int,
    peak_rotation: int,
    fps: float,
) -> int:
    """argmin(knee) over [max(load_start, foot_plant - 0.2s), peak_rotation+1]."""
    knee = np.asarray(knee, dtype=float)
    n = len(knee)
    knee_search_start = max(int(load_start_v4), int(foot_plant_v4) - int(fps * 0.2))
    knee_search_end = min(n, int(peak_rotation) + 1)
    if knee_search_end > knee_search_start:
        return int(knee_search_start
                   + int(np.argmin(knee[knee_search_start:knee_search_end])))
    return int(foot_plant_v4)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def detect_phases_v4(
    *,
    times: np.ndarray,
    stride: np.ndarray,
    knee: np.ndarray,
    analysis_debug: dict,
    phases_v3: dict,
    burst_lo: int,
    burst_hi: int,
    fps: float,
) -> dict:
    """Run v4 phase detection in shadow mode.

    Inputs:
      times, stride, knee  — same per-frame arrays detect_phases.py uses
      analysis_debug       — payload from phase_debug.build_debug_payload
      phases_v3            — the legacy v3 phases dict (used for comparison
                              + as fallback when v4 cannot pick a candidate)
      burst_lo, burst_hi   — swing burst window
      fps                  — frames per second

    Returns a dict shaped like:

      {
        "phases":           {load_start, foot_plant, launch, contact,
                              peak_rotation, finish},          # the 6 indices
        "phases_t":         {name: time_s},                    # mirror in seconds
        "confidence":       float in [0, 1],
        "selection_reason": str,                               # one-line summary
        "alternatives":     list[dict],                        # ranked alternatives
        "diff_from_v3":     {foot_plant_delta_frames,
                             foot_plant_delta_ms,
                             foot_plant_changed,               # bool
                             load_start_delta_frames,
                             launch_delta_frames},
        "fallback_to_v3":   bool,                              # true when v4
                                                                # couldn't pick
      }
    """
    candidates = analysis_debug.get("foot_plant_candidates", [])
    rot_onset = int(analysis_debug["selected_phases"]["rotation_onset"]["frame"])
    contact = int(phases_v3["contact"])
    peak_rotation = int(phases_v3["peak_rotation"])
    finish = int(phases_v3["finish"])

    # --- Pick the best candidate via ranked scoring ---
    if not candidates:
        # No stable contacts detected → fall back to v3 entirely.
        return _build_fallback_result(
            phases_v3=phases_v3, times=times, fps=fps,
            reason="no stable contact candidates available",
        )

    ranked = rank_candidates(
        candidates, rot_onset=rot_onset, contact=contact, fps=fps,
    )
    best = ranked[0]
    best_raw_score = best["raw_score"]

    # If even the best candidate scores at the absolute floor (no rotation
    # alignment, no timing in range, no duration credit) — that's a sign the
    # signals are too messy. Fall back to v3 and mark low confidence.
    if best_raw_score <= 0.05:
        return _build_fallback_result(
            phases_v3=phases_v3, times=times, fps=fps,
            reason=(f"best candidate scored only {best_raw_score:.2f} "
                    "— too low to trust"),
            ranked_alternatives=ranked,
        )

    # Phase 4a Fix 1: when the selected candidate ENDS just before
    # rotation begins (i.e. a stance period that runs straight into the
    # swing), use the frame just before rotation_onset as the anchor,
    # not the start of the contact period. This fixes the "frame-0 bug"
    # exposed by the Phase 3 validation report on real-time clips where
    # there's only one long stable contact spanning pre-rotation.
    foot_plant_v4 = _effective_anchor(
        best, rot_onset=rot_onset, fps=fps,
    )

    # --- Re-derive dependent phases with the new anchor ---
    load_start_v4 = derive_load_start_v4(
        stride, knee, foot_plant_v4=foot_plant_v4, fps=fps,
    )
    launch_v4 = derive_launch_v4(
        foot_plant_v4=foot_plant_v4, contact=contact, burst_lo=burst_lo,
    )
    knee_min_v4 = derive_knee_min_v4(
        knee, load_start_v4=load_start_v4, foot_plant_v4=foot_plant_v4,
        peak_rotation=peak_rotation, fps=fps,
    )

    # --- Confidence: normalized raw score, dampened by margin to next-best ---
    norm_score = min(1.0, best_raw_score / MAX_RAW_SCORE)
    confidence = norm_score
    margin_note = ""
    if len(ranked) >= 2:
        margin = best_raw_score - ranked[1]["raw_score"]
        if margin >= MARGIN_STRONG:
            margin_note = f"strong margin (Δ={margin:.2f}) over next candidate"
        elif margin >= MARGIN_MODERATE:
            confidence *= 0.90
            margin_note = f"moderate margin (Δ={margin:.2f}) over next candidate"
        else:
            confidence *= 0.75
            margin_note = (f"close call (Δ={margin:.2f}) "
                           "between top two candidates")
    else:
        margin_note = "single candidate available"

    # Phase 4a Fix 3: distance-to-rotation-onset penalty.
    # A high-confidence pick must actually be near where rotation begins.
    # On Phase 3 the elly_de_la_cruz_swing row showed confidence=1.00 but
    # the pick was 145 frames off — confidence should fall when the
    # picked frame is far from rot_onset regardless of raw score.
    gap_ms = (
        abs(foot_plant_v4 - rot_onset) * 1000.0 / fps if fps > 0 else 0.0
    )
    rot_distance_note = ""
    if gap_ms > 500.0:
        confidence *= 0.30
        rot_distance_note = (
            f"foot_plant {gap_ms:.0f} ms from rotation_onset — "
            "low confidence"
        )
    elif gap_ms > 200.0:
        confidence *= 0.50
        rot_distance_note = (
            f"foot_plant {gap_ms:.0f} ms from rotation_onset — "
            "reduced confidence"
        )

    selection_reason = "; ".join(
        best["reasons"] + [margin_note]
        + ([rot_distance_note] if rot_distance_note else [])
    )

    # --- Build phases dict ---
    phases_v4 = {
        "load_start":    int(load_start_v4),
        "foot_plant":    int(foot_plant_v4),
        "launch":        int(launch_v4),
        "contact":       int(contact),         # unchanged from v3
        "peak_rotation": int(peak_rotation),   # unchanged from v3
        "finish":        int(finish),          # unchanged from v3
    }

    # --- Diff vs v3 ---
    diff = _compute_diff(phases_v4, phases_v3, fps=fps)

    # --- Alternatives (excluding the selected one) ---
    alts_pub = [
        {
            "frame": int(c["start_frame"]),
            "time_s": _t(times, int(c["start_frame"])),
            "rank": c["rank"],
            "raw_score": float(c["raw_score"]),
            "duration_ms": float(c["duration_ms"]),
            "reasons": list(c["reasons"]),
        }
        for c in ranked[1:]
    ]

    return {
        "schema_version": "phase_detector_v4",
        "phases": phases_v4,
        "phases_t": {k: _t(times, v) for k, v in phases_v4.items()},
        "knee_min_frame": int(knee_min_v4),
        "confidence": float(round(confidence, 3)),
        "selection_reason": selection_reason,
        "alternatives": alts_pub,
        "diff_from_v3": diff,
        "fallback_to_v3": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _t(times: np.ndarray, frame: int) -> Optional[float]:
    if frame is None or frame < 0 or frame >= len(times):
        return None
    return float(times[frame])


def _compute_diff(phases_v4: dict, phases_v3: dict, *, fps: float) -> dict:
    """Compute v4-minus-v3 deltas for every shared phase."""
    out: dict = {}
    for name in phases_v4:
        if name not in phases_v3:
            continue
        delta_frames = int(phases_v4[name]) - int(phases_v3[name])
        out[f"{name}_delta_frames"] = delta_frames
        out[f"{name}_delta_ms"] = (delta_frames * 1000.0 / fps) if fps > 0 else 0.0
    out["foot_plant_changed"] = (
        int(phases_v4["foot_plant"]) != int(phases_v3["foot_plant"])
    )
    return out


def _build_fallback_result(
    *,
    phases_v3: dict,
    times: np.ndarray,
    fps: float,
    reason: str,
    ranked_alternatives: Optional[list[dict]] = None,
) -> dict:
    """v4 couldn't pick a candidate — fall back to v3 with low confidence."""
    alts_pub: list[dict] = []
    if ranked_alternatives:
        alts_pub = [
            {
                "frame": int(c["start_frame"]),
                "time_s": _t(times, int(c["start_frame"])),
                "rank": int(c.get("rank", i)),
                "raw_score": float(c["raw_score"]),
                "duration_ms": float(c["duration_ms"]),
                "reasons": list(c.get("reasons", [])),
            }
            for i, c in enumerate(ranked_alternatives)
        ]
    return {
        "schema_version": "phase_detector_v4",
        "phases": dict(phases_v3),
        "phases_t": {k: _t(times, v) for k, v in phases_v3.items()},
        "knee_min_frame": None,
        "confidence": 0.20,
        "selection_reason": f"fallback to v3: {reason}",
        "alternatives": alts_pub,
        "diff_from_v3": _compute_diff(dict(phases_v3), phases_v3, fps=fps),
        "fallback_to_v3": True,
    }


# ---------------------------------------------------------------------------
# Pretty-print summary
# ---------------------------------------------------------------------------


def format_v4_summary(v4_result: dict) -> str:
    """Human-readable summary of v4 output + diff vs v3."""
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("              DETECTOR V4 (shadow mode)")
    lines.append("=" * 60)
    if v4_result.get("fallback_to_v3"):
        lines.append(f"  ⚠  Fell back to v3 — {v4_result['selection_reason']}")
        lines.append("")
        return "\n".join(lines)

    p = v4_result["phases"]
    pt = v4_result["phases_t"]
    diff = v4_result["diff_from_v3"]
    conf = v4_result["confidence"]
    reason = v4_result["selection_reason"]

    lines.append(f"  Confidence            : {conf:.2f}")
    lines.append(f"  Selection reason      : {reason}")
    lines.append("")
    lines.append("  V4 PHASES vs V3 (Δ shown in ms; positive = v4 picked LATER frame)")
    lines.append("  " + "-" * 56)
    for name in ("load_start", "foot_plant", "launch",
                 "contact", "peak_rotation", "finish"):
        if name not in p:
            continue
        t = f"{pt[name]:5.2f}s" if pt[name] is not None else "  n/a "
        df = diff.get(f"{name}_delta_frames", 0)
        dms = diff.get(f"{name}_delta_ms", 0.0)
        flag = " ← changed" if df != 0 else ""
        lines.append(
            f"  {name:<14}  frame {p[name]:>4}  t={t}  "
            f"Δ={df:+d}f / {dms:+.0f}ms{flag}"
        )
    if v4_result.get("alternatives"):
        lines.append("")
        lines.append(f"  ALTERNATIVES ({len(v4_result['alternatives'])})")
        lines.append("  " + "-" * 56)
        for a in v4_result["alternatives"]:
            t = f"{a['time_s']:5.2f}s" if a["time_s"] is not None else "  n/a "
            lines.append(
                f"  rank {a['rank']}  frame {a['frame']:>4}  t={t}  "
                f"score={a['raw_score']:.2f}  dur={a['duration_ms']:.0f}ms"
            )
    lines.append("")
    return "\n".join(lines)
