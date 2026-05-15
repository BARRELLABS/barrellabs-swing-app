"""
MLB reference library — load cached swing fingerprints for MLB hitters and
pick the best match for a given player clip.

Each reference is a JSON file in ./references/ that extends a normal
fingerprint (the kind detect_phases.py produces) with a few extra fields:

    {
      "player_name":  "Mookie Betts",
      "team":         "Dodgers",
      "position":     "OF",
      "swing_style":  "Compact, level path, plus barrel control",
      "added_at":     "2026-05-09",
      "source_clip":  "mookie_swing.mp4",

      # ... all normal fingerprint keys (handedness, fps, phases_t, etc.) ...
    }

The matcher prefers references that:
  1. Match handedness (LEFT vs RIGHT). Mismatched handedness is acceptable
     because the metrics are mirrored by detect_phases.py — but a same-side
     reference is preferred when available.
  2. Have the closest camera_view.hip_to_torso_ratio_stance (so a profile
     player clip pairs with a profile reference, three-quarter with
     three-quarter, etc.). This is what kills the "mixed_method" rotation
     warning.
  3. Use the same rotation_method (3d_world vs 2d_width_ratio). When the
     methods match the rotation comparison is apples-to-apples.

Public API:
  list_references()              → list of dicts (lightweight metadata only)
  load_reference(slug)           → full reference dict (or None)
  find_best_match(player_fp)     → (slug, reference_dict, reason_str) or
                                   (None, None, "no_references_available")
  find_all_ranked(player_fp)     → list of (slug, reference_dict, score)
                                   sorted best-first
"""

import json
import os
from typing import Optional, Tuple, List, Dict, Any

REFERENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references")


def _slug_from_filename(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_references() -> List[Dict[str, Any]]:
    """Return lightweight metadata for every reference in the library.

    Each entry has: slug, player_name, handedness, rotation_method,
    camera_view_ratio, swing_style. Useful for `--list` style CLI output.
    """
    if not os.path.isdir(REFERENCES_DIR):
        return []
    out = []
    for fname in sorted(os.listdir(REFERENCES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(REFERENCES_DIR, fname)
        data = _read_json(path)
        if data is None:
            continue
        out.append({
            "slug": _slug_from_filename(fname),
            "player_name": data.get("player_name", _slug_from_filename(fname)),
            "handedness": data.get("handedness", "?"),
            "rotation_method": data.get("rotation_method", "?"),
            "camera_view_ratio": (
                data.get("camera_view", {}).get("hip_to_torso_ratio_stance", 0.0)
            ),
            "swing_style": data.get("swing_style", ""),
            "team": data.get("team", ""),
            "position": data.get("position", ""),
        })
    return out


def load_reference(slug_or_name: str) -> Optional[Dict[str, Any]]:
    """Load a reference by slug ("mookie_betts") or fuzzy name ("betts",
    "mookie", "Mookie Betts"). Case-insensitive substring match on slug or
    player_name. Returns None if no unique match.
    """
    if not slug_or_name:
        return None

    # Direct slug hit (with or without .json)
    candidates = [slug_or_name, slug_or_name.lower(),
                  slug_or_name.replace(" ", "_").lower()]
    for c in candidates:
        path = os.path.join(REFERENCES_DIR, c if c.endswith(".json") else c + ".json")
        if os.path.isfile(path):
            data = _read_json(path)
            if data is not None:
                return data

    # Fuzzy match on slug or player_name substring.
    needle = slug_or_name.lower().strip()
    matches = []
    for entry in list_references():
        slug = entry["slug"].lower()
        name = entry["player_name"].lower()
        if needle in slug or needle in name:
            matches.append(entry["slug"])

    if len(matches) == 1:
        return _read_json(os.path.join(REFERENCES_DIR, matches[0] + ".json"))
    return None


def _match_score(player_fp: Dict[str, Any],
                 reference: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Compute a matching score (0=perfect, larger=worse) and a breakdown.

    Components (lower is better):
      - handedness penalty: 0 if same side, 1.0 if mirrored
      - camera-view delta:  abs(hip/torso ratio_stance difference); 0..1ish
      - rotation-method penalty: 0 if same method, 1.0 if mixed
    """
    p_hand = (player_fp.get("handedness") or "").upper()
    r_hand = (reference.get("handedness") or "").upper()
    handedness_pen = 0.0 if p_hand == r_hand else 1.0

    p_view = float(player_fp.get("camera_view", {}).get("hip_to_torso_ratio_stance", 0.0))
    r_view = float(reference.get("camera_view", {}).get("hip_to_torso_ratio_stance", 0.0))
    view_delta = abs(p_view - r_view)

    p_method = player_fp.get("rotation_method", "")
    r_method = reference.get("rotation_method", "")
    method_pen = 0.0 if p_method == r_method else 1.0

    # Weighting: rotation method is the biggest unlock for fair scoring,
    # then camera-view proximity (which is what drives method selection),
    # then handedness (mirroring keeps it apples-to-apples but same-side
    # is still preferred because the user can SEE the same view).
    score = (3.0 * method_pen) + (2.0 * view_delta) + (1.0 * handedness_pen)
    return score, {
        "handedness_pen": handedness_pen,
        "view_delta": view_delta,
        "method_pen": method_pen,
        "p_view": p_view,
        "r_view": r_view,
        "p_method": p_method,
        "r_method": r_method,
    }


def find_all_ranked(player_fp: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], float, Dict[str, Any]]]:
    """Return every reference in the library ranked best-first."""
    out = []
    if not os.path.isdir(REFERENCES_DIR):
        return out
    for fname in os.listdir(REFERENCES_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(REFERENCES_DIR, fname)
        data = _read_json(path)
        if data is None:
            continue
        score, breakdown = _match_score(player_fp, data)
        out.append((_slug_from_filename(fname), data, score, breakdown))
    out.sort(key=lambda t: t[2])
    return out


def find_best_match(player_fp: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
    """Return (slug, reference_dict, reason). reason is a short string
    explaining why this reference was chosen, suitable for printing in a
    CLI report.
    """
    ranked = find_all_ranked(player_fp)
    if not ranked:
        return None, None, "no_references_available"

    slug, ref, score, br = ranked[0]
    name = ref.get("player_name", slug)

    bits = []
    if br["method_pen"] == 0.0:
        bits.append(f"matching rotation method ({br['p_method']})")
    else:
        bits.append("closest available rotation method")
    if br["handedness_pen"] == 0.0:
        bits.append(f"same handedness ({player_fp.get('handedness','?')})")
    else:
        bits.append("mirrored handedness")
    bits.append(f"camera-view Δ={br['view_delta']:.2f}")

    reason = f"selected {name}: " + ", ".join(bits)
    if len(ranked) > 1:
        runner = ranked[1][1].get("player_name", ranked[1][0])
        reason += f". Next-best: {runner}."
    return slug, ref, reason
