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

from drills import (
    DRILL_DB,
    TYPICAL_TORSO_INCHES,
    build_drill_plan,
    build_narratives,
    classify_gap,
)
from reference_library import find_best_match, list_references, load_reference


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


# ---- MAIN ENTRY POINT ----
def analyze(player_fp_path, reference_arg=None):
    """Run the full comparison and return a structured result dict.

    The dict is consumed by app.py to render UI cards. Field shape is stable
    enough that a future iOS app could consume the same JSON.
    """
    # ----- LOAD PLAYER -----
    if not os.path.isfile(player_fp_path):
        raise FileNotFoundError(f"Player fingerprint not found: {player_fp_path}")
    player = _load_fp(player_fp_path)
    player_name = player.get("video", "Player").replace(".mp4", "")

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
    view_warning = have_view and view_diff > 0.45

    player_rot_method = player.get("rotation_method", "2d_width_ratio")
    ref_rot_method    = reference.get("rotation_method", "2d_width_ratio")
    methods_match     = (player_rot_method == ref_rot_method)
    both_3d           = (player_rot_method == "3d_world"
                         and ref_rot_method == "3d_world")

    if not methods_match:
        rotation_view_sensitive = True
        rotation_flag_reason = "mixed_method"
    elif both_3d:
        rotation_view_sensitive = False
        rotation_flag_reason = None
    else:
        rotation_view_sensitive = view_warning
        rotation_flag_reason = "view_diff" if view_warning else None

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
    narratives = build_narratives(gaps_ranked_raw, ref_name, top_n=2)
    drill_plan = build_drill_plan(gaps_ranked_raw, top_n_categories=2)

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
    }
