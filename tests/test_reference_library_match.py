"""Tests for movement-based pro matching in reference_library.

The matcher used to rank references by handedness + camera-view delta +
rotation method (a flaw — it picked whoever was filmed from the same angle,
not whoever MOVED like the player). It now ranks by movement distance in
z-space (mlb_match), so two players with clearly different movement vectors
land on different pros.

These tests pin:
  - public signatures/return shapes of find_best_match / find_all_ranked,
  - movement-based discrimination (different vectors -> different pros),
  - handedness stays mirror-tolerant (a mismatched-handed pro can still win
    on movement),
  - locked-slug replay (load_reference returns the asked-for pro regardless
    of the player's movement — no recompute).
"""
import copy

import pytest

from reference_library import (
    find_all_ranked,
    find_best_match,
    load_reference,
)


# A synthetic player whose movement vector lands squarely on Aaron Judge:
# very long load relative to a short, crisp fire (Judge's signature tempo).
FP_JUDGE_LIKE = {
    "handedness": "RIGHT",
    "rotation_method": "2d_width_ratio",
    "camera_view": {"hip_to_torso_ratio_stance": 0.41},
    "timing_ms": {"load_duration": 730, "foot_plant_to_launch": 16,
                  "launch_to_contact": 83, "total_swing": 100},
    "rotation_deg": {"peak_separation": 7.8, "separation_at_contact": 7.8,
                     "peak_separation_t": 0.86, "peak_hip": -14.2,
                     "hip_at_foot_plant": 11},
    "phases_t": {"foot_plant": 0.76, "contact": 0.86},
    "knee_deg": {"at_foot_plant": 169.8, "min_during_load": 166.9,
                 "re_extension": 10.2},
    "head_movement_normalized_foot_plant_to_contact": {"total_drift_torso": 0.074},
}

# A clearly different player: compact, modest load, longer fire — lands on a
# different pro (a Cluster 0 contact hitter, NOT Judge).
FP_COMPACT_LIKE = {
    "handedness": "RIGHT",
    "rotation_method": "2d_width_ratio",
    "camera_view": {"hip_to_torso_ratio_stance": 0.41},
    "timing_ms": {"load_duration": 200, "foot_plant_to_launch": 40,
                  "launch_to_contact": 150, "total_swing": 390},
    "rotation_deg": {"peak_separation": 40, "separation_at_contact": 5,
                     "peak_separation_t": 0.55, "peak_hip": 50,
                     "hip_at_foot_plant": 5},
    "phases_t": {"foot_plant": 0.5, "contact": 0.8},
    "knee_deg": {"at_foot_plant": 150, "min_during_load": 130,
                 "re_extension": 25},
    "head_movement_normalized_foot_plant_to_contact": {"total_drift_torso": 0.05},
}


def test_find_best_match_signature_and_shape():
    slug, ref, reason = find_best_match(FP_JUDGE_LIKE)
    assert isinstance(slug, str) and slug
    assert isinstance(ref, dict)
    assert ref.get("player_name")
    assert isinstance(reason, str) and reason


def test_different_movement_vectors_pick_different_pros():
    slug_a, _, _ = find_best_match(FP_JUDGE_LIKE)
    slug_b, _, _ = find_best_match(FP_COMPACT_LIKE)
    assert slug_a != slug_b, (
        f"expected distinct pros for clearly different swings, "
        f"got {slug_a} for both"
    )


def test_judge_like_player_matches_judge():
    slug, ref, _ = find_best_match(FP_JUDGE_LIKE)
    assert slug == "aaron_judge"
    assert ref.get("player_name") == "Aaron Judge"


def test_find_all_ranked_shape_and_order():
    ranked = find_all_ranked(FP_JUDGE_LIKE)
    assert ranked, "library should not be empty"
    # 4-tuple shape preserved: (slug, ref_dict, score, breakdown)
    for slug, ref, score, breakdown in ranked:
        assert isinstance(slug, str)
        assert isinstance(ref, dict)
        assert isinstance(score, (int, float))
        assert isinstance(breakdown, dict)
    # best-first: scores are non-decreasing (lower == closer)
    scores = [t[2] for t in ranked]
    assert scores == sorted(scores)
    # The best-ranked entry agrees with find_best_match.
    best_slug, _, _ = find_best_match(FP_JUDGE_LIKE)
    assert ranked[0][0] == best_slug


def test_handedness_mirror_tolerant():
    # Same movement, opposite handedness from the matched pro (Judge is RIGHT).
    # Movement still wins — a mirrored-handed player should still match Judge,
    # because detect_phases mirror-normalizes the metrics before fingerprinting.
    lefty = copy.deepcopy(FP_JUDGE_LIKE)
    lefty["handedness"] = "LEFT"
    slug, ref, _ = find_best_match(lefty)
    assert slug == "aaron_judge", (
        "handedness mismatch must not block a movement match"
    )


def test_locked_slug_replays_without_recompute():
    # The locked-pro flow loads a specific reference by slug and must return
    # exactly that pro, independent of how the player actually moves.
    ref = load_reference("aaron_judge")
    assert ref is not None
    assert ref.get("player_name") == "Aaron Judge"
    # And a different lock returns a different pro.
    other = load_reference("mike_trout")
    assert other is not None
    assert other.get("player_name") == "Mike Trout"


def test_stats_cache_retries_after_failed_load(monkeypatch, tmp_path):
    """A failed stats load must NOT poison the module cache. The sentinel
    stays in place so a later (now-valid) load succeeds — otherwise a single
    transient I/O error would disable matching for the process lifetime."""
    import json as _json
    import reference_library as rl

    # Point at a missing file and reset the cache to the unset sentinel.
    monkeypatch.setattr(rl, "_STATS_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(rl, "_STATS_CACHE", rl._STATS_UNSET)

    assert rl._load_stats() is None
    # Cache must remain the sentinel (not poisoned to {}), so we can retry.
    assert rl._STATS_CACHE is rl._STATS_UNSET

    # Now make a valid file appear and confirm the retry loads it.
    good = {"means": [0.0], "stds": [1.0], "centroids": [[0.0]],
            "pros": [{"slug": "x", "name": "X", "z": [0.0], "cluster": 0}]}
    good_path = tmp_path / "stats.json"
    good_path.write_text(_json.dumps(good))
    monkeypatch.setattr(rl, "_STATS_PATH", str(good_path))

    assert rl._load_stats() == good
