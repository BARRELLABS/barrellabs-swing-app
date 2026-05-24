import pytest
from mlb_match import movement_vector, match_pro, zscore
import json

_FP = {
  "timing_ms": {"load_duration": 400, "foot_plant_to_launch": 80,
                "launch_to_contact": 150, "total_swing": 230},
  "rotation_deg": {"peak_separation": 40, "separation_at_contact": 20,
                   "peak_separation_t": 0.6, "peak_hip": 45},
  "phases_t": {"foot_plant": 0.5, "contact": 0.8},
  "knee_deg": {"at_foot_plant": 150, "min_during_load": 130, "re_extension": 20},
  "head_movement_normalized_foot_plant_to_contact": {"total_drift_torso": 0.2},
}

def test_movement_vector_len_and_finite():
    v = movement_vector(_FP)
    assert isinstance(v, list) and len(v) == 8
    assert all(isinstance(x, float) and abs(x) < 1000 for x in v)

def test_movement_vector_scale_invariant():
    # Scaling all *_torso/degree magnitudes does NOT change the ratio vector,
    # because every feature is a ratio. Doubling raw separation/hip together
    # keeps rotational_linear_lean stable; timing ratios unchanged.
    import copy
    fp2 = copy.deepcopy(_FP)
    fp2["rotation_deg"]["peak_separation"] *= 2
    fp2["rotation_deg"]["separation_at_contact"] *= 2
    fp2["rotation_deg"]["peak_hip"] *= 2
    v1, v2 = movement_vector(_FP), movement_vector(fp2)
    # sep_retention (idx 4) and timing ratios unchanged; lean (idx 5) unchanged
    assert v1[4] == pytest.approx(v2[4])
    assert v1[5] == pytest.approx(v2[5])
    assert v1[0] == pytest.approx(v2[0])


def test_match_identical_pro_is_high():
    stats = json.load(open("mlb_match_stats.json"))
    pro = stats["pros"][0]
    res = match_pro(z_vector=pro["z"], stats=stats)
    assert res["slug"] == pro["slug"]
    assert res["name"]
    assert 90 <= res["movement_match_pct"] <= 100


def test_match_pct_bounded():
    stats = json.load(open("mlb_match_stats.json"))
    far = [99.0]*len(stats["means"])
    res = match_pro(z_vector=far, stats=stats)
    assert 0 <= res["movement_match_pct"] <= 100
