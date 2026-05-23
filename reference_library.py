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

from mlb_match import movement_vector, zscore, _dist

REFERENCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references")
_STATS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mlb_match_stats.json")

# Frozen movement-match stats (means/stds for z-scoring + precomputed pro
# z-vectors). Loaded once and cached. The matcher z-scores the player's
# movement vector against these means/stds and ranks references by Euclidean
# distance in that shared z-space — i.e. it picks the pro who MOVES like the
# player, not the pro who happened to be filmed from the same angle.
_STATS_CACHE: Optional[Dict[str, Any]] = None


def _load_stats() -> Optional[Dict[str, Any]]:
    global _STATS_CACHE
    if _STATS_CACHE is None:
        try:
            with open(_STATS_PATH) as f:
                _STATS_CACHE = json.load(f)
        except (OSError, json.JSONDecodeError):
            _STATS_CACHE = {}
    return _STATS_CACHE or None


def _pro_z_by_slug(stats: Dict[str, Any]) -> Dict[str, List[float]]:
    """slug -> precomputed z-vector for every pro in the frozen stats."""
    return {p["slug"]: p["z"] for p in (stats.get("pros") or [])}


def _player_z(player_fp: Dict[str, Any], stats: Dict[str, Any]) -> Optional[List[float]]:
    try:
        return zscore(movement_vector(player_fp), stats)
    except Exception:
        return None


def _reference_z(slug: str, reference: Dict[str, Any],
                 stats: Dict[str, Any],
                 pro_z: Dict[str, List[float]]) -> Optional[List[float]]:
    """z-vector for a reference. Prefer the frozen precomputed value (keyed by
    slug) so ranking matches how the stats were built; fall back to computing
    it from the reference fingerprint for any library file not in stats."""
    if slug in pro_z:
        return pro_z[slug]
    try:
        return zscore(movement_vector(reference), stats)
    except Exception:
        return None


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


# Tiny handedness tiebreaker. Movement distance dominates; this only breaks
# near-ties so a same-side pro edges out a mirrored one when they move almost
# identically. The metrics are mirror-normalized by detect_phases, so a
# mismatched-handed pro can — and should — still win on movement alone.
_HAND_TIEBREAK = 1e-3


def _match_score(player_fp: Dict[str, Any],
                 reference: Dict[str, Any],
                 *,
                 stats: Optional[Dict[str, Any]] = None,
                 pro_z: Optional[Dict[str, List[float]]] = None,
                 player_z: Optional[List[float]] = None,
                 ref_slug: Optional[str] = None) -> Tuple[float, Dict[str, Any]]:
    """Compute a matching score (0=perfect, larger=worse) and a breakdown.

    Score is the Euclidean distance between the player's movement vector and
    the reference's, both expressed in the shared z-space from
    mlb_match_stats.json. Smaller distance = more similar swing MOVEMENT.

    A negligible handedness tiebreaker is added so a same-side pro wins a true
    tie, but it can never flip a real movement difference. Handedness is NOT a
    gate — detect_phases mirror-normalizes the metrics, so mismatched-handed
    pros remain fair matches.

    `stats`/`pro_z`/`player_z` are optional precomputed caches so callers that
    rank the whole library don't recompute them per reference.
    """
    if stats is None:
        stats = _load_stats()
    p_hand = (player_fp.get("handedness") or "").upper()
    r_hand = (reference.get("handedness") or "").upper()
    handedness_pen = 0.0 if p_hand == r_hand else 1.0

    # No frozen stats available → degrade to a stable, deterministic fallback
    # (handedness only) rather than crashing. Should not happen in practice.
    if not stats:
        return handedness_pen, {
            "movement_distance": None,
            "handedness_pen": handedness_pen,
            "method": "handedness_fallback",
        }

    if pro_z is None:
        pro_z = _pro_z_by_slug(stats)
    if player_z is None:
        player_z = _player_z(player_fp, stats)
    if ref_slug is None:
        ref_slug = reference.get("slug")

    r_z = _reference_z(ref_slug or "", reference, stats, pro_z)
    if player_z is None or r_z is None:
        # Can't compute movement distance for this pair → push to the back but
        # keep handedness ordering stable.
        return 1e6 + handedness_pen, {
            "movement_distance": None,
            "handedness_pen": handedness_pen,
            "method": "movement_unavailable",
        }

    distance = _dist(player_z, r_z)
    score = distance + _HAND_TIEBREAK * handedness_pen
    return score, {
        "movement_distance": distance,
        "handedness_pen": handedness_pen,
        "method": "movement_zspace",
    }


def find_all_ranked(player_fp: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], float, Dict[str, Any]]]:
    """Return every reference in the library ranked best-first (lower score =
    closer movement match)."""
    out = []
    if not os.path.isdir(REFERENCES_DIR):
        return out
    # Compute the player z-vector + pro z-lookup once, then reuse per ref.
    stats = _load_stats()
    pro_z = _pro_z_by_slug(stats) if stats else {}
    player_z = _player_z(player_fp, stats) if stats else None
    for fname in sorted(os.listdir(REFERENCES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(REFERENCES_DIR, fname)
        data = _read_json(path)
        if data is None:
            continue
        slug = _slug_from_filename(fname)
        score, breakdown = _match_score(
            player_fp, data,
            stats=stats, pro_z=pro_z, player_z=player_z, ref_slug=slug,
        )
        out.append((slug, data, score, breakdown))
    out.sort(key=lambda t: t[2])
    return out


def find_best_match(player_fp: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
    """Return (slug, reference_dict, reason). reason is a short string
    explaining why this reference was chosen, suitable for printing in a
    CLI report. Selection is by movement similarity (see _match_score).
    """
    ranked = find_all_ranked(player_fp)
    if not ranked:
        return None, None, "no_references_available"

    slug, ref, score, br = ranked[0]
    name = ref.get("player_name", slug)

    bits = []
    dist = br.get("movement_distance")
    if dist is not None:
        # Same scale-invariant exp() mapping mlb_match uses for the headline %,
        # so the reason text agrees with the match % the report shows.
        import math
        pct = round(100.0 * math.exp(-dist / 3.0))
        pct = max(0, min(100, pct))
        bits.append(f"closest swing movement ({pct}% match)")
    else:
        bits.append("closest available swing")
    if br.get("handedness_pen") == 0.0:
        bits.append(f"same handedness ({player_fp.get('handedness','?')})")
    else:
        bits.append("mirrored handedness")

    reason = f"selected {name}: " + ", ".join(bits)
    if len(ranked) > 1:
        runner = ranked[1][1].get("player_name", ranked[1][0])
        reason += f". Next-best: {runner}."
    return slug, ref, reason
