"""
Structured analysis pipeline — same logic as compare.py, but returns a
dict instead of printing. Used by the Streamlit UI (app.py) to render the
report as nice visual cards. compare.py can keep using its own print logic
unchanged.

Public entry point:
    analyze(player_fingerprint_path, reference_arg=None) -> dict

Where reference_arg is one of:
    None                        → auto-pick best match from references/
    "<slug>" or "<substring>"   → look up in references/
    "<path>.json"               → direct file path to a fingerprint JSON
"""

import json
import math
import os
from typing import Optional

from drills import (
    DRILL_DB,
    TYPICAL_TORSO_INCHES,
    build_drill_plan,
    build_narratives,
    classify_gap,
    gaps_from_pillars,
    pro_relative_line,
)
from reference_library import find_best_match, list_references, load_reference
from swing_score import (
    aggregate_score,
    score_sequence,
    score_stability,
    score_stride,
    score_timing,
)
from mlb_match import match_pro, movement_vector, zscore


# ---- LOAD HELPERS ----
def _load_fp(path):
    with open(path) as f:
        return json.load(f)


def _get(d, *keys, default=0.0):
    cur = d
    for k in keys:
        cur = cur.get(k, {})
    return cur if isinstance(cur, (int, float)) else default


def _timing_source(fp):
    return fp.get("timing_ms_corrected") or fp.get("timing_ms", {})


def _metric_similarity(p, r, span):
    diff = abs(p - r)
    return math.exp(-diff / span) if span > 0 else 0.0


def _fmt_pair(r):
    """Player/ref formatted strings, matching compare.py for visual parity."""
    if r["units"] == "ms":
        return f"{r['p']:.0f}ms", f"{r['r']:.0f}ms"
    if r["units"] == "T":
        return (f"~{abs(r['p']) * TYPICAL_TORSO_INCHES:.0f} in",
                f"~{abs(r['r']) * TYPICAL_TORSO_INCHES:.0f} in")
    return f"{r['p']:+.1f}{r['units']}", f"{r['r']:+.1f}{r['units']}"


_CATEGORY_LABELS = {
    "head_stability":          "Head stability",
    "hip_rotation":             "Hip rotation",
    "hip_shoulder_separation":  "Hip-shoulder separation",
    "knee_extension":           "Front-side firmness",
    "timing":                   "Timing & tempo",
}


def _friendly_label(label):
    if "Δx" in label:
        return "forward/back drift"
    if "Δy" in label:
        return "up/down drift"
    if label.startswith("Total head drift"):
        return "total drift"
    return label


def _synthesize_sequence_gaps(sequence_block: dict) -> list:
    """Convert Power Sequence ratings into synthetic gap entries the
    drill-plan generator already understands.

    A marginal rating becomes a moderate gap; a poor rating becomes a
    large gap. The label string carries enough information for
    drills.classify_gap to route to the right category (sequencing,
    rotational_speed, front_side_stability).
    """
    gaps: list = []
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
            "reference":  None,
            "similarity": sev,
            "synthetic":  True,
        })

    _add("Sequencing lag",        "sequencing_lag",        sequence_block.get("sequencing_lag_ms"))
    # peak_hip_omega and front_side_stability are NOT surfaced as gaps: they
    # can't be measured reliably from a single-camera phone video (omega reads
    # backwards; flyout mostly can't be computed). They stay computed in the
    # sequence block for later (Barrel Lock sensors), but must not drive drills,
    # scoring, or report tiles. See biomech verification findings (2026-05-23).
    # _add("Peak hip rotational speed", "peak_hip_omega", sequence_block.get("peak_hip_omega_deg_s"))
    # _add("Stay closed (front-side stability)", "front_side_stability",
    #      sequence_block.get("front_side_stability_pct"))
    return gaps


# ---- SWING SCORE / MLB MATCH HELPERS ----

# Default age bracket when the player's age is genuinely unavailable. 13-14 is
# the middle of the supported range, so the age-fair ramps in swing_score.py
# neither over- nor under-reward an unknown-age player.
_DEFAULT_BRACKET = "13-14"

# The headline pillar order + display labels for the report.
_PILLAR_LABELS = {
    "sequence":  "Power Sequence",
    "stability": "Head Stability",
    "timing":    "Timing & Tempo",
    "stride":    "Front-Side Brace",
}

# Structural reliability ceilings per pillar. The app's input is always
# single-camera phone video, where hips-lead sequencing and front-leg-brace
# (knee re-extension) are intrinsically noisy (see biomech verification
# 2026-05-23). Cap their confidence so a low/zero read — which may be a
# measurement artifact rather than a real flaw — drags the Swing Score less.
# Head Stability and gross Timing are robust on phone video → no cap.
_PILLAR_RELIABILITY = {
    "sequence":  0.5,
    "stability": 1.0,
    "timing":    1.0,
    "stride":    0.5,
}


def age_from_birth_year(birth_year, today_year: Optional[int] = None) -> Optional[int]:
    """Compute a player's current age from a 4-digit birth year.

    Returns None for missing/blank/unparseable input, and for ages outside a
    plausible youth-baseball range (typo guard) so a bad value falls back to
    the default bracket rather than skewing the score.
    """
    import datetime
    if birth_year is None:
        return None
    try:
        by = int(str(birth_year).strip())
    except (TypeError, ValueError):
        return None
    yr = today_year if today_year is not None else datetime.date.today().year
    age = yr - by
    if age < 4 or age > 25:
        return None
    return age


# COPPA (Children's Online Privacy Protection Act) protects children UNDER 13.
# Anyone 13+ signs up normally; only an actual under-13 triggers the parental
# pathway. We gate on birth year (the only DOB granularity we collect).
COPPA_MIN_AGE = 13


def is_under_coppa_age(birth_year, today_year: Optional[int] = None):
    """True if the birth year implies the person is under 13 (COPPA threshold).

    Returns None when birth_year is missing/blank/unparseable — callers that
    enforce the age gate must REQUIRE a valid birth year first, so a None here
    means "can't tell", never "old enough".
    """
    import datetime
    if birth_year is None or str(birth_year).strip() == "":
        return None
    try:
        by = int(str(birth_year).strip())
    except (TypeError, ValueError):
        return None
    yr = today_year if today_year is not None else datetime.date.today().year
    return (yr - by) < COPPA_MIN_AGE


def parse_birth_year(value, today_year: Optional[int] = None) -> Optional[int]:
    """Validate a plausible 4-digit birth year for storage, else None.

    Bounds are generous (the last ~100 years) so both youth players and adult
    coaches validate; typos like 1500 / next year are rejected. Use this at
    every birth-year entry point (signup, add-player, settings) so the rule is
    consistent. age_from_birth_year() handles bracket fallback for ages that
    fall outside the scored 8-17 range.
    """
    import datetime
    if value is None:
        return None
    try:
        yr = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    cur = today_year if today_year is not None else datetime.date.today().year
    if yr < cur - 100 or yr > cur:
        return None
    return yr


def tempo_ratio(timing: dict) -> Optional[float]:
    """Gather:fire ratio = load_duration / launch_to_contact — the exact ratio
    the Timing pillar already grades internally, surfaced as a coach-legible
    number. Pass the slow-mo-CORRECTED timing dict. None when either component
    is missing or non-positive."""
    try:
        load = float((timing or {}).get("load_duration"))
        fire = float((timing or {}).get("launch_to_contact"))
    except (TypeError, ValueError):
        return None
    if load <= 0 or fire <= 0:
        return None
    return round(load / fire, 2)


def xfactor_timing_ms(player: dict) -> Optional[float]:
    """When peak hip-shoulder separation occurs relative to contact, in
    slow-mo-corrected milliseconds. Negative = separation peaks BEFORE contact
    (the elite "stretch then unwind" pattern); near-zero/positive = peaks at or
    after contact (stuck/late). None when inputs are missing.

    Uses the peak-separation TIME — a within-clip temporal landmark that is
    robust to camera viewpoint — rather than the separation magnitude (which is
    view-sensitive and only reported categorically)."""
    try:
        sep_t = float((player.get("rotation_deg") or {}).get("peak_separation_t"))
        contact_t = float((player.get("phases_t") or {}).get("contact"))
    except (TypeError, ValueError, AttributeError):
        return None
    slow_mo = float(player.get("slow_mo_factor", 1.0)) or 1.0
    return round((sep_t - contact_t) * 1000.0 / slow_mo, 1)


def pose_coverage_confidence(coverage) -> float:
    """Global confidence multiplier from pose-detection coverage (fraction of
    frames where a pose was found). Full confidence at >=0.8; ramps to a 0.25
    floor by 0.3. Missing/None/non-numeric -> 1.0 (no penalty — older
    fingerprints predate the field)."""
    if not isinstance(coverage, (int, float)) or isinstance(coverage, bool):
        return 1.0
    c = float(coverage)
    if c >= 0.8:
        return 1.0
    if c <= 0.3:
        return 0.25
    return 0.25 + (c - 0.3) / (0.8 - 0.3) * 0.75


# Above this stance hip-to-torso ratio a clip is too front-on for trustworthy
# 2D-width rotation (profile clips sit ~0.30-0.45). Tighter than the overall
# match's well_conditioned band because width-based rotation is the most
# viewpoint-sensitive signal.
_OFF_PROFILE_RATIO = 0.55
_VIEW_DIFF_MAX = 0.45


def rotation_view_flag(player_view, ref_view, player_method, ref_method):
    """Decide whether 2D-width rotation metrics are viewpoint-unreliable for
    this comparison. Returns (sensitive: bool, reason: Optional[str]).

    - mixed measurement methods (one 2D, one 3D) -> always sensitive
    - both 3D world -> trustworthy
    - both 2D-width -> sensitive when the player's OWN clip is off-profile
      (ABSOLUTE: ratio > _OFF_PROFILE_RATIO) or player/reference viewpoints
      differ a lot. The absolute check is what matters: the reference pool is
      all near-profile, so a relative diff alone never fires on a genuinely
      off-profile upload, leaving its unreliable rotation ungated."""
    have_view = (player_view or 0) > 0 and (ref_view or 0) > 0
    pm = player_method or "2d_width_ratio"
    rm = ref_method or "2d_width_ratio"
    if pm != rm:
        return True, "mixed_method"
    if pm == "3d_world" and rm == "3d_world":
        return False, None
    if have_view and player_view > _OFF_PROFILE_RATIO:
        return True, "off_profile"
    if have_view and abs(player_view - ref_view) > _VIEW_DIFF_MAX:
        return True, "view_diff"
    return False, None


def age_bracket(age) -> str:
    """Map a player's age (int-ish) to one of swing_score.BRACKETS.

    8-10 / 11-12 / 13-14 / 15-17. Ages below 8 fold into "8-10" and ages
    above 17 fold into "15-17" so the function always returns a valid bracket
    (never raises). Unknown/None age falls back to the middle bracket.
    """
    try:
        a = int(age)
    except (TypeError, ValueError):
        return _DEFAULT_BRACKET
    if a <= 10:
        return "8-10"
    if a <= 12:
        return "11-12"
    if a <= 14:
        return "13-14"
    return "15-17"


def _pose_visibility(player_fp: dict) -> float:
    """Mean lower-body landmark visibility across the player's pose frames, in
    [0,1]. Used to soften pillar confidence when the legs/feet are poorly
    tracked (the parts the brace + stability pillars lean on). Returns 1.0 when
    no pose frames are available (no penalty rather than a false one)."""
    # Preferred: the scalar detect_phases stamps onto the fingerprint. The live
    # upload path's fingerprint carries this (mean front-ankle visibility), not
    # raw per-frame pose_frames, so this is what actually gates real uploads.
    stamped = player_fp.get("lower_body_visibility")
    if isinstance(stamped, (int, float)) and not isinstance(stamped, bool):
        return max(0.0, min(1.0, float(stamped)))
    frames = player_fp.get("pose_frames") or []
    if not frames:
        return 1.0
    names = ((player_fp.get("pose_meta") or {}).get("lm_names")) or []
    lower = {"l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle",
             "l_heel", "r_heel", "l_foot_index", "r_foot_index"}
    idxs = [i for i, nm in enumerate(names) if nm in lower]
    if not idxs:
        return 1.0
    vis = []
    for fr in frames:
        kp = fr.get("kp") or []
        for i in idxs:
            if i < len(kp) and len(kp[i]) >= 3:
                vis.append(float(kp[i][2]))
    if not vis:
        return 1.0
    return max(0.0, min(1.0, sum(vis) / len(vis)))


# Movement-match stats are loaded once and cached (frozen file written by
# scripts/build_match_stats.py). Kept module-level so repeated analyze() calls
# don't re-read it.
_MATCH_STATS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_match_stats.json")
_MATCH_STATS_UNSET = object()  # sentinel: distinct from a failed/empty load
_MATCH_STATS_CACHE = _MATCH_STATS_UNSET


def _load_match_stats():
    """Load + cache the frozen movement-match stats. Returns None if missing.

    A failed load is NOT cached — we leave the sentinel in place so a later
    call retries, rather than permanently disabling the MLB match for the
    process lifetime after a single transient I/O error.
    """
    global _MATCH_STATS_CACHE
    if _MATCH_STATS_CACHE is _MATCH_STATS_UNSET:
        try:
            with open(_MATCH_STATS_PATH) as f:
                _MATCH_STATS_CACHE = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None  # leave cache unset → retry on the next call
    return _MATCH_STATS_CACHE or None


# Positive one-liners keyed by the strongest pillar.
_WELL_LINES = {
    "sequence":  "Your power sequence is already a strength — the hips are leading the way.",
    "stability": "Your head stays quiet through contact — that's real plate coverage.",
    "timing":    "Your timing is already a strength — a real gather into a crisp fire.",
    "stride":    "Your front-side brace is firm — you're letting that leg post up.",
}


def _build_what_you_did_well(pillars: dict, pro_name) -> str:
    """Return a non-empty positive one-liner.

    Anchored on the strongest CONFIDENT pillar (max compliance × confidence
    with confidence > 0). When nothing is confident, fall back to a line tied
    to the player's MLB movement match so the field is never empty.
    """
    scored = [
        (name, (p.get("compliance") or 0.0) * p.get("confidence", 0.0))
        for name, p in pillars.items()
        if p.get("confidence", 0.0) > 0 and p.get("compliance") is not None
    ]
    if scored:
        best_name = max(scored, key=lambda t: t[1])[0]
        return _WELL_LINES.get(best_name, "You've got a strong foundation to build on.")
    if pro_name:
        return f"Great base to build on — you already move like {pro_name}."
    return "Great base to build on."


def _pillar_confidence(signal, *, rotation_dependent: bool,
                       rotation_view_sensitive: bool,
                       pose_visibility: float,
                       reliability_ceiling: float = 1.0) -> float:
    """Per-pillar confidence in [0,1].

    Rules (kept deliberately simple but real, reusing the camera flags the
    analyzer already computes):
      - signal is None  → 0.0 (nothing measurable, pillar drops out).
      - else base 1.0.
      - halved for a rotation-dependent pillar (Sequence) when the rotation
        read is view-sensitive (mixed method or large camera-view delta).
      - scaled by lower-body pose visibility when that's poor (legs/feet not
        well tracked → less trust in the head/brace reads).
      - capped by reliability_ceiling: a structural ceiling per pillar that
        reflects how trustworthy a metric is on single-camera phone video.
        Sequence and Stride are intrinsically noisy on phone clips; their
        ceiling keeps a zero/low read from unfairly tanking the Swing Score.
    """
    if signal is None:
        return 0.0
    conf = 1.0
    if rotation_dependent and rotation_view_sensitive:
        conf *= 0.5
    # Only let visibility REDUCE confidence (>=0.8 visibility = no penalty);
    # below that, scale down proportionally so a half-tracked clip is trusted
    # roughly half as much.
    if pose_visibility < 0.8:
        conf *= max(0.25, pose_visibility / 0.8)
    conf *= reliability_ceiling
    return max(0.0, min(1.0, conf))


# ---- MAIN ENTRY POINT ----
def analyze(player_fp_path, reference_arg=None, *, preferred_goal=None):
    """Run the full comparison and return a structured result dict.

    The dict is consumed by app.py to render UI cards. Field shape is stable
    enough that a future iOS app could consume the same JSON.

    Parameters
    ----------
    player_fp_path
        Path to the player's fingerprint JSON.
    reference_arg
        Optional reference identifier (slug or file path). When the
        player has `locked_mlb_slug` set this is their locked MLB hitter.
    preferred_goal
        OPTIONAL — the player's `primary_goal` from the Player Settings
        page. Forwarded into `build_drill_plan` so drill recommendations
        weight categories that move the player's stated goal. Does NOT
        change scoring math, gap detection, or MLB comp selection — it
        only re-ranks roughly-tied drill categories.
    """
    # ----- LOAD PLAYER -----
    if not os.path.isfile(player_fp_path):
        raise FileNotFoundError(f"Player fingerprint not found: {player_fp_path}")
    player = _load_fp(player_fp_path)
    player_name = player.get("video", "Player").replace(".mp4", "")

    # Power Sequence biomech block — pre-computed by detect_phases.py.
    # Pass through unchanged; the swing report renders it directly.
    sequence_block = player.get("sequence") or {
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

    # ----- RESOLVE REFERENCE -----
    reference = None
    ref_source = None      # "file" | "library" | "auto"
    auto_reason = None
    ref_arg_for_override = None  # to display "Override: --reference <slug>"
    # picked_slug tracks which reference file was actually used. We surface
    # this in the result dict so callers (specifically the MLB comp lock
    # in app.py) can persist the slug to players.locked_mlb_slug after a
    # first-time auto-pick. None for ad-hoc file paths that have no slug.
    picked_slug = None

    if reference_arg and os.path.isfile(reference_arg):
        reference = _load_fp(reference_arg)
        ref_source = "file"
        ref_arg_for_override = reference_arg
    elif reference_arg:
        ref = load_reference(reference_arg)
        if ref is None:
            raise ValueError(f"No reference matching '{reference_arg}' in the library.")
        reference = ref
        ref_source = "library"
        ref_arg_for_override = reference_arg
        # When the caller passes a slug-like arg, that arg IS the slug.
        # (load_reference also accepts fuzzy name matches; in that case
        # this falls back to the raw input which is still useful for
        # locking — load_reference will resolve it again next time.)
        picked_slug = reference_arg
    else:
        slug, ref_data, reason = find_best_match(player)
        if ref_data is None:
            # Legacy fallback to mookie_swing_fingerprint.json if present.
            legacy = os.path.join(os.path.dirname(player_fp_path),
                                  "mookie_swing_fingerprint.json")
            if os.path.isfile(legacy):
                reference = _load_fp(legacy)
                ref_source = "file"
            else:
                raise RuntimeError("No MLB references available.")
        else:
            reference = ref_data
            ref_source = "auto"
            auto_reason = reason
            picked_slug = slug

    ref_name = (
        reference.get("player_name")
        or reference.get("video", "Reference").replace(".mp4", "")
                                              .replace("_swing", "").title()
    )

    # ----- TIMING SOURCE + SLOW-MO INFO -----
    player_timing = _timing_source(player)
    ref_timing    = _timing_source(reference)
    player_slow_mo = float(player.get("slow_mo_factor", 1.0))
    ref_slow_mo    = float(reference.get("slow_mo_factor", 1.0))
    any_slow_mo    = player_slow_mo > 1.05 or ref_slow_mo > 1.05

    # ----- METRIC DEFINITIONS -----
    # Same shape compare.py uses: (group, label, player_val, ref_val, span,
    # units, direction, caveat). caveat is always False now because timing is
    # slow-mo-corrected and knee angles are time-independent.
    metrics_raw = [
        ("Rotation",  "Peak hip-shoulder separation",
            _get(player, "rotation_deg", "peak_separation"),
            _get(reference, "rotation_deg", "peak_separation"),
            30.0, "°", "higher", False),
        ("Rotation",  "Hip rotation at foot plant",
            _get(player, "rotation_deg", "hip_at_foot_plant"),
            _get(reference, "rotation_deg", "hip_at_foot_plant"),
            45.0, "°", None, False),
        ("Rotation",  "Hip rotation at contact",
            _get(player, "rotation_deg", "hip_at_contact"),
            _get(reference, "rotation_deg", "hip_at_contact"),
            45.0, "°", None, False),
        ("Rotation",  "Separation at foot plant",
            _get(player, "rotation_deg", "separation_at_foot_plant"),
            _get(reference, "rotation_deg", "separation_at_foot_plant"),
            30.0, "°", "higher", False),

        ("Timing",    "Foot plant → launch",
            player_timing.get("foot_plant_to_launch", 0.0),
            ref_timing.get("foot_plant_to_launch", 0.0),
            100.0, "ms", "lower", False),
        ("Timing",    "Launch → contact",
            player_timing.get("launch_to_contact", 0.0),
            ref_timing.get("launch_to_contact", 0.0),
            80.0, "ms", "lower", False),
        ("Timing",    "Total swing duration",
            player_timing.get("total_swing", 0.0),
            ref_timing.get("total_swing", 0.0),
            100.0, "ms", "lower", False),

        ("Front Knee","Most bent (load)",
            _get(player, "knee_deg", "min_during_load"),
            _get(reference, "knee_deg", "min_during_load"),
            30.0, "°", None, False),
        ("Front Knee","Re-extension",
            _get(player, "knee_deg", "re_extension"),
            _get(reference, "knee_deg", "re_extension"),
            15.0, "°", "higher", False),

        ("Head",      "Head drift Δx (torso-rel)",
            _get(player, "head_movement_normalized_foot_plant_to_contact", "dx_torso"),
            _get(reference, "head_movement_normalized_foot_plant_to_contact", "dx_torso"),
            0.5, "T", "lower_abs", False),
        ("Head",      "Head drift Δy (torso-rel)",
            _get(player, "head_movement_normalized_foot_plant_to_contact", "dy_torso"),
            _get(reference, "head_movement_normalized_foot_plant_to_contact", "dy_torso"),
            0.5, "T", "lower_abs", False),
        ("Head",      "Total head drift (torso-rel)",
            _get(player, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso"),
            _get(reference, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso"),
            0.8, "T", "lower", False),
    ]

    # ----- CAMERA-VIEW / ROTATION-METHOD COMPARISON -----
    player_view = _get(player, "camera_view", "hip_to_torso_ratio_stance")
    ref_view    = _get(reference, "camera_view", "hip_to_torso_ratio_stance")
    have_view   = player_view > 0 and ref_view > 0
    view_diff   = abs(player_view - ref_view) if have_view else 0.0

    player_rot_method = player.get("rotation_method", "2d_width_ratio")
    ref_rot_method    = reference.get("rotation_method", "2d_width_ratio")
    both_3d           = (player_rot_method == "3d_world"
                         and ref_rot_method == "3d_world")

    # Flag 2D-width rotation as unreliable when the clip is off-profile
    # (absolute) or viewpoints differ — not just relative to the (near-zero-
    # variance) reference pool. Also gates the MLB match-% confidence below.
    rotation_view_sensitive, rotation_flag_reason = rotation_view_flag(
        player_view, ref_view, player_rot_method, ref_rot_method)

    # ----- BUILD METRIC RESULTS -----
    results = []
    for (group, label, p, r, span, units, direction, caveat) in metrics_raw:
        sim = _metric_similarity(p, r, span)
        gap = p - r
        judgment = ""
        if direction == "higher":
            judgment = "below ref" if gap < 0 else "at/above ref"
        elif direction == "lower":
            judgment = "longer/larger than ref" if gap > 0 else "at/below ref"
        elif direction == "lower_abs":
            judgment = "more drift than ref" if abs(p) > abs(r) else "less drift than ref"
        view_sensitive = rotation_view_sensitive and group == "Rotation"
        results.append({
            "group": group, "label": label, "p": p, "r": r,
            "gap": gap, "sim": sim, "units": units,
            "judgment": judgment, "caveat": caveat,
            "view_sensitive": view_sensitive,
            "direction": direction,
        })

    # ----- OVERALL SCORE -----
    score_eligible = [r for r in results
                      if not r["caveat"] and not r["view_sensitive"]]
    if score_eligible:
        overall_sim = sum(r["sim"] for r in score_eligible) / len(score_eligible)
    else:
        overall_sim = sum(r["sim"] for r in results) / len(results)
    overall_score = int(round(overall_sim * 100))

    if overall_score >= 75:
        score_band = ("green", "Strong match")
    elif overall_score >= 55:
        score_band = ("yellow", "Decent match — clear fixes available")
    else:
        score_band = ("red", "Big gaps to work on")

    # ----- STRENGTHS -----
    GOOD_SIM_THRESHOLD = 0.65
    confirmed_strengths = sorted(
        [r for r in results
         if not r["caveat"] and not r["view_sensitive"] and r["sim"] >= GOOD_SIM_THRESHOLD],
        key=lambda r: -r["sim"],
    )
    potential_strengths = sorted(
        [r for r in results
         if (r["caveat"] or r["view_sensitive"]) and r["sim"] >= GOOD_SIM_THRESHOLD],
        key=lambda r: -r["sim"],
    )
    shown_cats = set()
    strengths = []
    for r in confirmed_strengths:
        cat = classify_gap(r) or r["label"]
        if cat in shown_cats:
            continue
        shown_cats.add(cat)
        p_str, ref_str = _fmt_pair(r)
        strengths.append({
            "tier": "confirmed",
            "category": cat,
            "category_label": _CATEGORY_LABELS.get(cat, r["label"]),
            "sim_pct": int(round(r["sim"] * 100)),
            "player_str": p_str,
            "ref_str": ref_str,
            "label": r["label"],
        })
    for r in potential_strengths:
        if len(strengths) >= 3:
            break
        cat = classify_gap(r) or r["label"]
        if cat in shown_cats:
            continue
        shown_cats.add(cat)
        p_str, ref_str = _fmt_pair(r)
        strengths.append({
            "tier": "potential",
            "category": cat,
            "category_label": _CATEGORY_LABELS.get(cat, r["label"]),
            "sim_pct": int(round(r["sim"] * 100)),
            "player_str": p_str,
            "ref_str": ref_str,
            "label": r["label"],
            "caveat": "camera-angle" if r["view_sensitive"] else "slow-mo",
        })

    # ----- GAPS RANKED (grouped by category) -----
    gaps_ranked_raw = sorted(
        [r for r in results if not r["caveat"] and not r["view_sensitive"]],
        key=lambda r: r["sim"],
    )
    gaps_grouped = {}
    gaps_order   = []
    for r in gaps_ranked_raw:
        cat = classify_gap(r) or r["label"]
        if cat not in gaps_grouped:
            gaps_grouped[cat] = []
            gaps_order.append(cat)
        gaps_grouped[cat].append(r)

    gaps = []
    for rank, cat in enumerate(gaps_order[:5], 1):
        items = gaps_grouped[cat]
        primary = items[0]
        direction_note = ""
        if primary["judgment"] == "below ref":
            direction_note = "player below reference"
        elif primary["judgment"] == "more drift than ref":
            direction_note = "player has more drift"

        sub_metrics = []
        for sub in items:
            sp, sr = _fmt_pair(sub)
            sub_metrics.append({
                "label": _friendly_label(sub["label"]),
                "raw_label": sub["label"],
                "player_str": sp,
                "ref_str": sr,
                "sim_pct": int(round(sub["sim"] * 100)),
            })
        gaps.append({
            "rank": rank,
            "category": cat,
            "category_label": _CATEGORY_LABELS.get(cat, primary["label"]),
            "direction_note": direction_note,
            "sub_metrics": sub_metrics,
        })

    # ----- NARRATIVES + DRILL PLAN -----
    # `preferred_goal` is forwarded from app.py (the player's primary_goal
    # set on the Player Settings page) so the drill plan can boost
    # categories that move the player's stated goal. Gap-derived weights
    # still dominate — the goal just breaks ties between equally-ranked
    # categories.
    narratives = build_narratives(gaps_ranked_raw, ref_name, top_n=2)

    # Inject Power Sequence ratings into gaps_ranked_legacy so the legacy
    # path still works (e.g. strengths display). This is kept for back-compat
    # but the DRILL PLAN is now sourced from the Score pillars, not pro-difference.
    gaps_ranked_legacy = gaps_ranked_raw
    sequence_gaps = _synthesize_sequence_gaps(sequence_block)
    if sequence_gaps:
        gaps_ranked_legacy = gaps_ranked_raw + sequence_gaps
        gaps_ranked_legacy.sort(key=lambda g: g.get("similarity", g.get("sim", 100)))

    # ----- PILLAR-SOURCED DRILL PLAN (new) -----
    # The drill plan is now built from the Score pillars, not pro-difference gaps.
    # pillars is computed below in the SWING SCORE block, so we need to do a
    # two-pass approach: compute pillars first, then build the drill plan.
    # We defer to after the pillars block — the actual call is below.
    # (drill_plan is assigned after pillars are computed.)

    # ----- METRIC TABLE (for expanders) -----

    # ----- METRIC TABLE (for expanders) -----
    # Group metrics by group so the UI can show them in collapsible sections.
    metric_table = {}
    for r in results:
        g = r["group"]
        metric_table.setdefault(g, []).append({
            "label": r["label"],
            "player_str": _fmt_pair(r)[0],
            "ref_str":    _fmt_pair(r)[1],
            "gap": r["gap"],
            "sim_pct": int(round(r["sim"] * 100)),
            "units": r["units"],
            "flagged": r["view_sensitive"] or r["caveat"],
            "flag_reason": (
                "rotation method mismatch" if r["view_sensitive"]
                else ("slow-mo caveat" if r["caveat"] else None)
            ),
        })

    # ----- OTHER OBSERVATIONS (flagged rotation metrics) -----
    other_observations = [
        {
            "label": r["label"],
            "player_str": _fmt_pair(r)[0],
            "ref_str":    _fmt_pair(r)[1],
        }
        for r in results if r["view_sensitive"]
    ]

    # ----- REFERENCE ATTRIBUTION -----
    refs_meta = list_references()
    others_in_library = [
        r["player_name"] for r in refs_meta if r["player_name"] != ref_name
    ][:3]

    reference_attribution = {
        "name": ref_name,
        "team": reference.get("team", ""),
        "position": reference.get("position", ""),
        "style": reference.get("swing_style", ""),
        "source": ref_source,
        "auto_reason": auto_reason,
        "override_arg": ref_arg_for_override,
        "also_in_library": others_in_library,
        # Slug of the actual reference file used. Consumed by app.py's
        # MLB comp lock to remember which player was auto-picked on the
        # first swing so subsequent swings keep targeting the same hitter.
        "slug": picked_slug,
    }

    # ----- SWING SCORE (age-fair, independent of the MLB comparison) -----
    # The new HEADLINE score. Unlike `overall_score` above (which measures
    # similarity to the chosen MLB reference), the Swing Score grades the
    # player's swing on its own merits against age-appropriate biomechanical
    # targets. Both are returned; the report leads with swing_score and falls
    # back to `score` for older saved reports that predate this field.
    #
    # Age source: the player fingerprint's `age` field. detect_phases / app.py
    # can stamp it onto the fingerprint; when it's genuinely absent we fall
    # back to the middle "13-14" bracket (see age_bracket()).
    bracket = age_bracket(player.get("age"))
    # Did we resolve a real age, or fall back to the default bracket? Drives
    # the report's honest "set your birth year" nudge.
    def _age_is_known(_a) -> bool:
        try:
            int(_a)
            return True
        except (TypeError, ValueError):
            return False
    age_known = _age_is_known(player.get("age"))

    seq_lag = (sequence_block or {}).get("sequencing_lag_ms")
    total_drift = _get(player,
                       "head_movement_normalized_foot_plant_to_contact",
                       "total_drift_torso", default=None)
    load_ms = player_timing.get("load_duration")
    ltc_ms = player_timing.get("launch_to_contact")
    knee_reext = _get(player, "knee_deg", "re_extension", default=None)

    # Stride direction comes from the fingerprint (detect_phases serializes it
    # as `stride.toward_pitcher`). Default True for older fingerprints that
    # predate the field so they keep their prior (lenient) brace scoring.
    _stride_blk = player.get("stride") or {}
    stride_toward_pitcher = bool(_stride_blk.get("toward_pitcher", True))

    pose_vis = _pose_visibility(player)
    # Global gate: when few frames were tracked, soften every pillar rather than
    # presenting a confident grade built on sparse pose data.
    coverage_factor = pose_coverage_confidence(player.get("pose_coverage"))

    pillar_signals = {
        "sequence":  (score_sequence(seq_lag, bracket),                       True),
        "stability": (score_stability(total_drift, bracket),                 False),
        "timing":    (score_timing(load_ms, ltc_ms, bracket),               False),
        "stride":    (score_stride(knee_reext, stride_toward_pitcher, bracket), False),
    }

    pillars: dict = {}
    for name, (compliance, rotation_dependent) in pillar_signals.items():
        confidence = _pillar_confidence(
            compliance,
            rotation_dependent=rotation_dependent,
            rotation_view_sensitive=rotation_view_sensitive,
            pose_visibility=pose_vis,
            reliability_ceiling=_PILLAR_RELIABILITY.get(name, 1.0),
        )
        confidence *= coverage_factor
        pillars[name] = {
            "compliance": compliance,
            "confidence": confidence,
            "label": _PILLAR_LABELS[name],
        }

    swing_score = aggregate_score(pillars)

    # ----- MLB MOVEMENT MATCH -----
    # Locked-pro replay: when the caller resolved a specific reference (the
    # locked-slug flow from app.py, or a manual sidebar pick), the MLB match
    # REPLAYS that exact pro instead of recomputing a movement match — the
    # player is building toward one swing model. Otherwise compute the match
    # from the player's movement vector. `confident` gates whether the report
    # shows the %.
    locked = ref_source in ("library", "file") and picked_slug is not None

    try:
        _stats = _load_match_stats()
    except Exception:
        _stats = None

    # Camera quality gate for showing the match %: a well-conditioned (roughly
    # side-on) stance ratio AND a rotation read that isn't view-sensitive. Also
    # require the frozen stats to have loaded — otherwise match_pct stays 0 and
    # a True here would render a confident "0% movement match".
    stance_ratio = player_view  # camera_view.hip_to_torso_ratio_stance
    well_conditioned = 0.20 <= stance_ratio <= 0.70
    match_confident = bool(well_conditioned and not rotation_view_sensitive
                           and _stats is not None)

    if locked:
        # Replay the locked pro: the resolved `reference` IS that pro. Still
        # compute a movement_match_pct so the report can show how close the
        # player actually moves to their locked model.
        match_slug = picked_slug
        match_name = ref_name
        match_pct = 0
        if _stats is not None:
            try:
                z_player = zscore(movement_vector(player), _stats)
                z_ref = zscore(movement_vector(reference), _stats)
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(z_player, z_ref)))
                match_pct = max(0, min(100, round(100.0 * math.exp(-dist / 3.0))))
            except Exception:
                match_pct = 0
        mlb_match = {
            "pro_name": match_name,
            "slug": match_slug,
            "movement_match_pct": int(match_pct),
            "confident": match_confident,
            "locked": True,
            "cluster": None,  # uniform shape; replay path has no cluster read
        }
    else:
        # Auto-pick path: compute the closest-moving pro from the frozen stats.
        mlb_match = {
            "pro_name": ref_name,
            "slug": picked_slug or "",
            "movement_match_pct": 0,
            "confident": match_confident,
            "locked": False,
            "cluster": None,
        }
        if _stats is not None:
            try:
                z_player = zscore(movement_vector(player), _stats)
                m = match_pro(z_player, _stats)
                mlb_match = {
                    "pro_name": m["name"],
                    "slug": m["slug"],
                    "movement_match_pct": int(m["movement_match_pct"]),
                    "confident": match_confident,
                    "locked": False,
                    "cluster": m.get("cluster"),
                }
            except Exception:
                # Fail-soft to the reference attribution computed above.
                pass

    # ----- WHAT YOU DID WELL -----
    # A positive one-liner anchored on the player's strongest *confident*
    # pillar (highest compliance × confidence with confidence > 0). When no
    # pillar is confident, fall back to a line tied to their MLB match so the
    # field is never empty.
    what_you_did_well = _build_what_you_did_well(pillars, mlb_match["pro_name"])

    # ----- PILLAR-SOURCED DRILL PLAN -----
    # Build the drill plan from the Score pillars (weakest confident pillar
    # drives the top drill category). This replaces the former pro-difference
    # gap source. The legacy gap fields are still present on the result for
    # backward-compat but the drill plan is now pillar-sourced.
    pillar_gaps = gaps_from_pillars(pillars)
    drill_plan = build_drill_plan(
        pillar_gaps,
        top_n_categories=2,
        preferred_goal=preferred_goal,
    )
    # Inject the pro-relative motivation line into each fix card.
    # Each category maps back to a pillar via _PILLAR_TO_CATEGORY (inverted).
    _CAT_TO_PILLAR = {
        "sequencing":    "sequence",
        "head_stability": "stability",
        "timing":        "timing",
        "knee_extension": "stride",
        # secondary fold-in categories default to their closest pillar
        "hip_shoulder_separation": "sequence",
        "hip_rotation":             "sequence",
        "rotational_speed":         "sequence",
        "front_side_stability":     "stride",
    }
    for cat_entry in drill_plan.get("categories", []):
        pillar_key = _CAT_TO_PILLAR.get(cat_entry["category"], "sequence")
        cat_entry["pro_relative_line"] = pro_relative_line(
            pillar_key, mlb_match["pro_name"]
        )

    # ----- FINAL RESULT DICT -----
    return {
        "player_name": player_name,
        "player_handedness": player.get("handedness", "?"),
        "reference": reference_attribution,
        "reference_handedness": reference.get("handedness", "?"),
        "mirrored_handedness": (
            player.get("handedness") != reference.get("handedness")
            and player.get("handedness") in ("LEFT", "RIGHT")
            and reference.get("handedness") in ("LEFT", "RIGHT")
        ),
        "score": overall_score,
        "score_band_color": score_band[0],
        "score_band_label": score_band[1],
        "score_eligible_count": len(score_eligible),
        "slow_mo": {
            "any": any_slow_mo,
            "player_factor": player_slow_mo,
            "ref_factor": ref_slow_mo,
            "player_raw_swing_ms":       player.get("timing_ms", {}).get("total_swing", 0.0),
            "player_corrected_swing_ms": player_timing.get("total_swing", 0.0),
            "ref_raw_swing_ms":          reference.get("timing_ms", {}).get("total_swing", 0.0),
            "ref_corrected_swing_ms":    ref_timing.get("total_swing", 0.0),
        },
        # Accurate, phone-reliable insights derived from data already computed:
        # gather:fire tempo (the Timing pillar's own ratio) and when peak
        # hip-shoulder separation lands relative to contact.
        "tempo_ratio": tempo_ratio(player_timing),
        "xfactor_timing_ms": xfactor_timing_ms(player),
        "camera_view": {
            "have_view": have_view,
            "player_ratio": player_view,
            "ref_ratio": ref_view,
            "player_method": player_rot_method,
            "ref_method": ref_rot_method,
            "view_diff": view_diff,
            "rotation_view_sensitive": rotation_view_sensitive,
            "rotation_flag_reason": rotation_flag_reason,
            "both_3d": both_3d,
        },
        "strengths": strengths,
        "gaps": gaps,
        "narratives": narratives,
        "drill_plan": drill_plan,
        "metric_table": metric_table,
        "other_observations": other_observations,
        # Phase timestamps from the player fingerprint, surfaced so the
        # side-by-side comparison viewer can sync user playback to MLB
        # reference playback at foot plant. Safe to omit downstream —
        # callers that don't render the comparison ignore this field.
        "phases_t": player.get("phases_t", {}) or {},
        "sequence": sequence_block,

        # ----- NEW: Swing Score + movement Match (the new headline) -----
        # KEEP the legacy `score` + `reference` above for back-compat; the
        # report leads with these and falls back to the old fields for saved
        # reports that predate them.
        "swing_score": swing_score,        # int 0-100, or None if unmeasurable
        "age_bracket": bracket,            # which age-fair bracket was used
        "age_known": age_known,            # False → report shows the age nudge
        "pillars": pillars,                # {sequence|stability|timing|stride}
        "mlb_match": mlb_match,            # {pro_name, slug, movement_match_pct, confident, locked}
        "what_you_did_well": what_you_did_well,
    }
