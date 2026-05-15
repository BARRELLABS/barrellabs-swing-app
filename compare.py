"""
Milestone 4: Compare a player's swing fingerprint to a reference (e.g., MLB hitter).

Reads a player fingerprint saved by detect_phases.py, picks the best-matching
MLB reference from references/ (or uses one the user specifies), and prints:
  - A side-by-side metrics report.
  - Per-metric gap analysis.
  - An overall similarity score (0-100).
  - Ranked focus areas (biggest gaps first).
  - Coaching narrative + drills.

Usage:
  python compare.py
      # Defaults: player = swing_fingerprint.json,
      #           reference = auto-picked from references/

  python compare.py my_swing_fingerprint.json
      # Custom player, auto-picked reference

  python compare.py my_swing_fingerprint.json --reference judge
      # Force-pick a specific MLB reference (slug or substring of player name)

  python compare.py my_swing_fingerprint.json --reference mookie_swing_fingerprint.json
      # Direct path to a fingerprint JSON (legacy / one-off references)

  python compare.py --list-references
      # Show every MLB reference currently in the library
"""

import argparse
import json
import math
import os
import sys

from drills import recommend_drills, narrate_top_gaps, classify_gap, TYPICAL_TORSO_INCHES
from reference_library import (
    list_references,
    load_reference,
    find_best_match,
)


def load_fp(path):
    with open(path) as f:
        return json.load(f)


def _print_library_listing():
    refs = list_references()
    if not refs:
        print("Reference library is empty.")
        print("Add an MLB clip with:")
        print("  python build_reference_library.py <video> --name '<Player Name>'")
        return
    print(f"MLB reference library — {len(refs)} player(s):")
    print("-" * 80)
    print(f"{'SLUG':<20}{'PLAYER':<22}{'HAND':<7}{'METHOD':<18}{'VIEW':<6}STYLE")
    print("-" * 80)
    for r in refs:
        style = r["swing_style"][:30] + ("…" if len(r["swing_style"]) > 30 else "")
        print(f"{r['slug']:<20}{r['player_name']:<22}{r['handedness']:<7}"
              f"{r['rotation_method']:<18}{r['camera_view_ratio']:<6.2f}{style}")


# ---- ARG PARSING ----
_parser = argparse.ArgumentParser(add_help=True)
_parser.add_argument("player", nargs="?", default="swing_fingerprint.json",
                     help="Player fingerprint JSON (default: swing_fingerprint.json)")
_parser.add_argument("--reference", "-r", default=None,
                     help="MLB reference: library slug, player name substring, or path to a fingerprint JSON")
_parser.add_argument("--list-references", action="store_true",
                     help="List MLB references in the library and exit")
_args = _parser.parse_args()

if _args.list_references:
    _print_library_listing()
    sys.exit(0)


# ---- LOAD PLAYER ----
PLAYER_FP = _args.player
if not os.path.isfile(PLAYER_FP):
    print(f"ERROR: player fingerprint not found: {PLAYER_FP}")
    print(f"Run detect_phases.py first to generate one.")
    sys.exit(1)
player = load_fp(PLAYER_FP)
PLAYER_NAME = player.get("video", "Player").replace(".mp4", "")


# ---- RESOLVE REFERENCE ----
# Three modes:
#   1. --reference points to a .json file path  → load directly (legacy)
#   2. --reference is a slug or name substring  → look up in library
#   3. no --reference                           → auto-pick best from library
reference = None
ref_source = None     # "file" | "library" | "auto"
auto_reason = None    # human-readable reason string when auto-picked

if _args.reference and os.path.isfile(_args.reference):
    reference = load_fp(_args.reference)
    ref_source = "file"
elif _args.reference:
    reference = load_reference(_args.reference)
    if reference is None:
        print(f"ERROR: no reference matching '{_args.reference}' in the library.")
        print("Run  python compare.py --list-references  to see what's available.")
        sys.exit(1)
    ref_source = "library"
else:
    slug, ref_data, reason = find_best_match(player)
    if ref_data is None:
        # Library empty — fall back to legacy mookie_swing_fingerprint.json
        # if it exists, so the script still works on a fresh clone.
        legacy = "mookie_swing_fingerprint.json"
        if os.path.isfile(legacy):
            reference = load_fp(legacy)
            ref_source = "file"
        else:
            print("ERROR: no MLB references available.")
            print("Add one with:")
            print("  python build_reference_library.py <video> --name '<Player Name>'")
            sys.exit(1)
    else:
        reference = ref_data
        ref_source = "auto"
        auto_reason = reason

# Player-facing reference name. Prefer player_name (library), fall back to
# video filename (legacy fingerprints).
REF_NAME = (
    reference.get("player_name")
    or reference.get("video", "Reference").replace(".mp4", "").replace("_swing", "").title()
)


# ---- METRIC DEFINITIONS ----
# (label, player_value, reference_value, "expected_typical_range" for similarity scoring,
#  units, "higher_is_better" or "lower_is_better" or None, slow_mo_caveat?)
def get(d, *keys, default=0.0):
    cur = d
    for k in keys:
        cur = cur.get(k, {})
    return cur if isinstance(cur, (int, float)) else default


# ---- TIMING SOURCE: prefer slow-mo-corrected values when present ----
# Fingerprints written by detect_phases.py >= the slow-mo-correction update
# include `timing_ms_corrected` (raw timing scaled by slow_mo_factor) and
# a top-level `slow_mo_factor`. We use the corrected values for comparison
# so a slow-mo MLB reference can be compared apples-to-apples against a
# real-time player clip. Older fingerprints without the corrected block
# fall back to the raw timing_ms (effectively slow_mo_factor = 1.0).
def _timing_source(fp):
    return fp.get("timing_ms_corrected") or fp.get("timing_ms", {})

player_timing = _timing_source(player)
ref_timing    = _timing_source(reference)

player_slow_mo = float(player.get("slow_mo_factor", 1.0))
ref_slow_mo    = float(reference.get("slow_mo_factor", 1.0))
any_slow_mo    = player_slow_mo > 1.05 or ref_slow_mo > 1.05


metrics = [
    # group, label, player_val, ref_val, range_for_score, units, direction, caveat
    ("Rotation",  "Peak hip-shoulder separation",
        get(player, "rotation_deg", "peak_separation"),
        get(reference, "rotation_deg", "peak_separation"),
        30.0, "°", "higher", False),
    ("Rotation",  "Hip rotation at foot plant",
        get(player, "rotation_deg", "hip_at_foot_plant"),
        get(reference, "rotation_deg", "hip_at_foot_plant"),
        45.0, "°", None, False),
    ("Rotation",  "Hip rotation at contact",
        get(player, "rotation_deg", "hip_at_contact"),
        get(reference, "rotation_deg", "hip_at_contact"),
        45.0, "°", None, False),
    ("Rotation",  "Separation at foot plant",
        get(player, "rotation_deg", "separation_at_foot_plant"),
        get(reference, "rotation_deg", "separation_at_foot_plant"),
        30.0, "°", "higher", False),

    # Timing values use the slow-mo-CORRECTED source where available, so
    # caveat=False — they're now scored normally. The slow-mo bullet in
    # the report just notes that correction was applied (informational).
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

    # Knee ANGLES are time-independent (degrees are degrees regardless of
    # playback speed), so they're scored normally now. Phase-detection
    # noise on slow-mo clips can shift WHICH frame the angle is read at,
    # but the magnitude of that error is small (a few degrees at most).
    ("Front Knee","Most bent (load)",
        get(player, "knee_deg", "min_during_load"),
        get(reference, "knee_deg", "min_during_load"),
        30.0, "°", None, False),
    ("Front Knee","Re-extension",
        get(player, "knee_deg", "re_extension"),
        get(reference, "knee_deg", "re_extension"),
        15.0, "°", "higher", False),

    ("Head",      "Head drift Δx (torso-rel)",
        get(player, "head_movement_normalized_foot_plant_to_contact", "dx_torso"),
        get(reference, "head_movement_normalized_foot_plant_to_contact", "dx_torso"),
        0.5, "T", "lower_abs", False),
    ("Head",      "Head drift Δy (torso-rel)",
        get(player, "head_movement_normalized_foot_plant_to_contact", "dy_torso"),
        get(reference, "head_movement_normalized_foot_plant_to_contact", "dy_torso"),
        0.5, "T", "lower_abs", False),
    ("Head",      "Total head drift (torso-rel)",
        get(player, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso"),
        get(reference, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso"),
        0.8, "T", "lower", False),
]


# ---- CAMERA-VIEW COMPARISON ----
# Each fingerprint records its rotation_method. Cases:
#   • both "3d_world"        → camera-invariant, trust regardless of view diff
#   • both "2d_width_ratio"  → depends on camera angle; flag if views differ
#   • mixed (one 3D, one 2D) → measurement systems aren't directly comparable,
#                              flag rotation metrics regardless of view
# detect_phases.py picks 3D for three-quarter views (hip/torso ≥ 0.6) and 2D
# for profile views, so a mixed pair is the common "user filmed three-quarter,
# reference is profile" case.
player_view = get(player, "camera_view", "hip_to_torso_ratio_stance")
ref_view    = get(reference, "camera_view", "hip_to_torso_ratio_stance")
have_view   = player_view > 0 and ref_view > 0
view_diff   = abs(player_view - ref_view) if have_view else 0.0
view_warning = have_view and view_diff > 0.15

player_rot_method = player.get("rotation_method", "2d_width_ratio")
ref_rot_method    = reference.get("rotation_method", "2d_width_ratio")
methods_match     = (player_rot_method == ref_rot_method)
both_3d           = (player_rot_method == "3d_world" and ref_rot_method == "3d_world")

if not methods_match:
    # Mixed methods — rotation values aren't directly comparable.
    rotation_view_sensitive = True
    rotation_flag_reason = "mixed_method"
elif both_3d:
    # Both 3D — camera-invariant, trust regardless of camera angle.
    rotation_view_sensitive = False
    rotation_flag_reason = None
else:
    # Both 2D — comparable only if camera angles roughly match.
    rotation_view_sensitive = view_warning
    rotation_flag_reason = "view_diff" if view_warning else None


def metric_similarity(p, r, span):
    """Return 0-1 similarity for a single metric (1 = identical, ~0 = far apart).
    Exponential decay: at diff = span, similarity ≈ 0.37; never hits 0 exactly,
    so even very different swings produce a meaningful (low) score instead of
    bottoming out at 0/100."""
    diff = abs(p - r)
    return math.exp(-diff / span) if span > 0 else 0.0


# Per-metric similarity (and gap)
results = []
for group, label, p, r, span, units, direction, caveat in metrics:
    sim = metric_similarity(p, r, span)
    gap = p - r
    # "Better/worse" judgment using direction
    judgment = ""
    if direction == "higher":
        judgment = "below ref" if gap < 0 else "at/above ref"
    elif direction == "lower":
        judgment = "longer/larger than ref" if gap > 0 else "at/below ref"
    elif direction == "lower_abs":
        # better = abs closer to zero
        judgment = "more drift than ref" if abs(p) > abs(r) else "less drift than ref"
    # Rotation metrics are camera-angle-sensitive when computed from 2D widths;
    # flag them when cameras differ. If both sides use 3D world landmarks the
    # rotation values are camera-invariant, so don't flag.
    view_sensitive = rotation_view_sensitive and group == "Rotation"
    results.append({
        "group": group, "label": label, "p": p, "r": r,
        "gap": gap, "sim": sim, "units": units,
        "judgment": judgment, "caveat": caveat,
        "view_sensitive": view_sensitive,
    })

# Overall similarity = average of metric similarities, excluding rotation
# metrics flagged because cameras differ enough that the methods don't match.
# Timing values are slow-mo-corrected upstream, so they're scored normally.
score_eligible = [r for r in results if not r["caveat"] and not r["view_sensitive"]]
if score_eligible:
    overall_sim = sum(r["sim"] for r in score_eligible) / len(score_eligible)
else:
    overall_sim = sum(r["sim"] for r in results) / len(results)
overall_score = int(round(overall_sim * 100))


# ---- PRINT REPORT ----
title = f"SWING COMPARISON:  {PLAYER_NAME}  vs  {REF_NAME}"
print()
print("=" * len(title))
print(title)
print("=" * len(title))
print()

# Reference attribution line. Tells the user which MLB hitter was used and
# why — auto-picked, library-pinned, or one-off file.
ref_team  = reference.get("team", "")
ref_pos   = reference.get("position", "")
ref_style = reference.get("swing_style", "")
attribution = f"Reference:  {REF_NAME}"
if ref_team or ref_pos:
    attribution += f"  ({ref_team}{', ' if ref_team and ref_pos else ''}{ref_pos})"
print(attribution)
if ref_style:
    print(f"  Style:    {ref_style}")
if ref_source == "auto":
    print(f"  Picked:   auto — {auto_reason}")
    print(f"  Override: python compare.py {PLAYER_FP} --reference <slug>")
elif ref_source == "library":
    print(f"  Picked:   manual override (--reference)")
elif ref_source == "file":
    print(f"  Picked:   direct file ({_args.reference or 'mookie_swing_fingerprint.json'})")
# Show 2-3 next-best alternatives so the user knows what else is available.
if ref_source in ("auto", "library"):
    refs_meta = list_references()
    if len(refs_meta) > 1:
        others = [r["player_name"] for r in refs_meta if r["player_name"] != REF_NAME][:3]
        if others:
            print(f"  Also in library: {', '.join(others)}")
print()

# Handedness line — saved by detect_phases.py in each fingerprint.
player_hand = player.get("handedness", "?")
ref_hand    = reference.get("handedness", "?")
print(f"Handedness:  {PLAYER_NAME} = {player_hand}-handed   |   {REF_NAME} = {ref_hand}-handed")
if player_hand != ref_hand and player_hand in ("LEFT", "RIGHT") and ref_hand in ("LEFT", "RIGHT"):
    print(f"  ✓  Mirrored swings — metrics use front/back side, so this comparison is still apples-to-apples.")
print()

print(f"Overall similarity score:  {overall_score}/100")
print(f"  (averaged over {len(score_eligible)} comparable metrics; flagged metrics excluded)")
print()

# Slow-motion correction note. detect_phases.py auto-detects slow-mo clips
# (any swing > 250ms) and writes a rescaled timing_ms_corrected block plus a
# slow_mo_factor. We compare the corrected values, so the user should know
# this happened — otherwise they'd see "Mookie's swing is 150ms" and not
# realize the source clip was 4× slow-mo.
if any_slow_mo:
    print("SLOW-MOTION CORRECTION")
    print("-" * 70)
    if player_slow_mo > 1.05:
        print(f"  {PLAYER_NAME[:11]:>11}  raw swing {player.get('timing_ms',{}).get('total_swing',0):.0f}ms  →  corrected to {player_timing.get('total_swing',0):.0f}ms  ({player_slow_mo:.1f}× slow-mo)")
    if ref_slow_mo > 1.05:
        print(f"  {REF_NAME[:11]:>11}  raw swing {reference.get('timing_ms',{}).get('total_swing',0):.0f}ms  →  corrected to {ref_timing.get('total_swing',0):.0f}ms  ({ref_slow_mo:.1f}× slow-mo)")
    print(f"  Timing metrics below use the real-time-equivalent values, so")
    print(f"  a slow-mo MLB clip can be compared against a real-time player clip.")
    print()

if have_view:
    print("CAMERA VIEW CHECK")
    print("-" * 70)
    print(f"  {PLAYER_NAME[:11]:>11} hip-width / torso-length (stance) : {player_view:.2f}  ({player_rot_method})")
    print(f"  {REF_NAME[:11]:>11} hip-width / torso-length (stance) : {ref_view:.2f}  ({ref_rot_method})")
    if rotation_flag_reason == "mixed_method":
        print(f"  ⚠  Different rotation methods — one clip is filmed three-quarter")
        print(f"     (3D world landmarks) and the other is filmed profile (2D width).")
        print(f"     The numbers aren't on the same scale, so rotation metrics get a †")
        print(f"     and are excluded from the score. Re-film from a similar angle")
        print(f"     to the reference for a direct rotation comparison.")
    elif rotation_flag_reason == "view_diff":
        print(f"  ⚠  Both clips use 2D width-ratio rotation but cameras differ in")
        print(f"     viewing angle (Δ={view_diff:.2f}). Rotation metrics get a † and")
        print(f"     are excluded from the score.")
    else:
        same_method = "3D world landmarks (camera-invariant)" if both_3d else "2D width-ratio"
        print(f"  ✓  Both clips use {same_method}; rotation comparison is valid.")
    print()

current_group = None
for r in results:
    if r["group"] != current_group:
        current_group = r["group"]
        print(f"\n{current_group.upper()}")
        print("-" * 70)
        print(f"{'Metric':<34}{PLAYER_NAME[:11]:>12}{REF_NAME[:11]:>12}{'Gap':>10}")

    if r['units'] == 'ms':
        p_str = f"{r['p']:.0f}{r['units']}"
        ref_str = f"{r['r']:.0f}{r['units']}"
        g_str = f"{r['gap']:+.0f}"
    elif r['units'] == 'T':
        p_str = f"{r['p']:+.2f}{r['units']}"
        ref_str = f"{r['r']:+.2f}{r['units']}"
        g_str = f"{r['gap']:+.2f}"
    else:
        p_str = f"{r['p']:+.1f}{r['units']}"
        ref_str = f"{r['r']:+.1f}{r['units']}"
        g_str = f"{r['gap']:+.1f}"
    if r['caveat']:
        flag = "*"
    elif r['view_sensitive']:
        flag = "\u2020"  # †
    else:
        flag = " "
    print(f"  {r['label']:<32}{p_str:>12}{ref_str:>12}{g_str:>9}{flag}")

print()
if rotation_flag_reason == "mixed_method":
    print("  \u2020  flagged: rotation metric — clips were filmed at different")
    print("     camera angles forcing different measurement methods (3D vs 2D).")
elif rotation_flag_reason == "view_diff":
    print("  \u2020  flagged: rotation metric — cameras at different angles, so")
    print("     this gap partly reflects viewpoint, not pure swing differences.")
print("  T  =  torso lengths (resolution-/distance-invariant unit).")
print()


# ---- BIGGEST GAPS / FOCUS AREAS ----
# Filter to non-caveated metrics, sort by similarity ascending (biggest gaps first)
gaps_ranked = sorted(
    [r for r in results if not r["caveat"] and not r["view_sensitive"]],
    key=lambda r: r["sim"]
)

# ---- DISPLAY HELPERS (used by multiple sections below) -----------------
_CATEGORY_LABELS = {
    "head_stability":          "Head stability",
    "hip_rotation":             "Hip rotation",
    "hip_shoulder_separation":  "Hip-shoulder separation",
    "knee_extension":           "Front-side firmness",
    "timing":                   "Timing & tempo",
}

def _friendly_label(label):
    """Friendlier sub-metric names used in nested bullets."""
    if "Δx" in label:
        return "forward/back drift"
    if "Δy" in label:
        return "up/down drift"
    if label.startswith("Total head drift"):
        return "total drift"
    return label

def _fmt_pair(r):
    """Return (player_str, ref_str) for a result row."""
    if r["units"] == "ms":
        return f"{r['p']:.0f}ms", f"{r['r']:.0f}ms"
    if r["units"] == "T":
        return (f"~{abs(r['p']) * TYPICAL_TORSO_INCHES:.0f} in",
                f"~{abs(r['r']) * TYPICAL_TORSO_INCHES:.0f} in")
    return f"{r['p']:+.1f}{r['units']}", f"{r['r']:+.1f}{r['units']}"


# ---- WHAT YOU'RE DOING WELL ----
# Highlight metrics where the player is close to the reference. Two tiers:
#   ✓ confirmed  — high sim, no flags. Trust this fully.
#   ≈ potential  — high sim but flagged (camera angle or slow-mo). Could be
#                  real, could be the recording. Worth knowing.
# Section is skipped entirely if neither tier has anything to show.
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
shown_strengths = []  # list of (tier, cat, result)
for r in confirmed_strengths:
    cat = classify_gap(r) or r["label"]
    if cat not in shown_cats:
        shown_cats.add(cat)
        shown_strengths.append(("confirmed", cat, r))
for r in potential_strengths:
    if len(shown_strengths) >= 3:
        break
    cat = classify_gap(r) or r["label"]
    if cat not in shown_cats:
        shown_cats.add(cat)
        shown_strengths.append(("potential", cat, r))

if shown_strengths:
    print("=" * 70)
    print("WHAT YOU'RE DOING WELL")
    print("=" * 70)
    for tier, cat, r in shown_strengths[:3]:
        p_str, ref_str = _fmt_pair(r)
        cat_label = _CATEGORY_LABELS.get(cat, r["label"])
        sim_pct = int(round(r["sim"] * 100))
        if tier == "confirmed":
            mark = "✓"
            note = f"{sim_pct}% match"
        else:
            mark = "≈"
            caveat_word = "camera-angle caveat" if r["view_sensitive"] else "slow-mo caveat"
            note = f"~{sim_pct}% match ({caveat_word})"
        print(f"  {mark}  {cat_label:<26}  player={p_str:<10}  ref={ref_str:<10}   {note}")
    print()


print("=" * 70)
print("BIGGEST COACHABLE GAPS  (ranked by similarity)")
print("=" * 70)

_seen = {}
_order = []
for r in gaps_ranked:
    cat = classify_gap(r) or r["label"]
    if cat not in _seen:
        _seen[cat] = []
        _order.append(cat)
    _seen[cat].append(r)

display_count = 0
for cat in _order:
    if display_count >= 5:
        break
    items = _seen[cat]
    primary = items[0]
    p_str, ref_str = _fmt_pair(primary)

    direction_note = ""
    if primary["judgment"] == "below ref":
        direction_note = " — player below reference"
    elif primary["judgment"] == "more drift than ref":
        direction_note = " — player has more drift"

    cat_label = _CATEGORY_LABELS.get(cat, primary["label"])
    display_count += 1
    print(f"  {display_count}. {cat_label}{direction_note}")

    # Sub-bullets for each metric in this category.
    for sub in items:
        sub_label = _friendly_label(sub["label"])
        sub_p, sub_r = _fmt_pair(sub)
        print(f"       • {sub_label:<22}  player={sub_p:<10}  ref={sub_r}")

print()


# ---- WHAT TO FIX (coach-style narrative diagnosis) ----
narrate_top_gaps(gaps_ranked, REF_NAME, top_n=2)


# ---- DRILL RECOMMENDATIONS (Milestone 5) ----
recommend_drills(gaps_ranked, top_n_categories=2)


# ---- OTHER OBSERVATIONS ----
# Flagged rotation metrics couldn't be reliably scored across mixed methods,
# but they're real measurements. Show them softly so the player isn't blind
# to them. Slow-mo timing is auto-corrected upstream and scored normally now,
# so it doesn't show up here anymore.
view_sensitive_results = [r for r in results if r["view_sensitive"]]

if view_sensitive_results:
    print("=" * 70)
    print("OTHER OBSERVATIONS")
    print("  (couldn't be reliably scored — take with a grain of salt)")
    print("=" * 70)
    print()

    if rotation_flag_reason == "mixed_method":
        print("  ⚠  Different camera angles forced different rotation methods")
        print("     (3D world for one clip, 2D width-ratio for the other), so")
        print("     these numbers aren't on the same scale. Re-film from the")
        print(f"     same side as the {REF_NAME} clip for a direct read:")
    else:
        print("  ⚠  Camera angles differ. These rotation gaps could be real,")
        print("     could just be the angle. Re-film from the same side as your")
        print("     reference video to lock these in:")
    for r in view_sensitive_results:
        p_str, ref_str = _fmt_pair(r)
        print(f"       • {r['label']:<35}  player={p_str:<10}  ref={ref_str}")
    print()


# ---- NEXT STEPS (closing message) ----
print("=" * 70)
print("NEXT STEPS")
print("=" * 70)
print(f"  1. Pick 1–2 drills from the plan above and commit to 10–15 min")
print(f"     a day. Pros work on ONE mechanical change at a time — that's")
print(f"     how it actually sticks.")
print(f"  2. Film yourself again in 2–3 weeks (same angle, same distance,")
print(f"     full speed) and re-run:  python compare.py")
print(f"  3. Watch the score climb and the top fix change. Each re-film")
print(f"     surfaces the next biggest priority — that's the workflow.")
print()
if rotation_view_sensitive:
    print(f"  Tip: for cleanest rotation comparison, film from the side")
    print(f"  (perpendicular to the pitcher) at full real-time speed. Same")
    print(f"  setup as the {REF_NAME} clip you're comparing to — that")
    print(f"  forces both clips onto the same measurement method.")
    print()
elif any_slow_mo:
    print(f"  Tip: timing values were auto-corrected from slow-mo footage,")
    print(f"  but real-time clips give the cleanest read. If you can grab a")
    print(f"  full-speed broadcast clip of {REF_NAME}, replace the reference.")
    print()
