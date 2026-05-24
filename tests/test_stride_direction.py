"""Unit tests for biomech.stride_direction — is the front foot striding
toward the pitcher? Pure geometry on ankle x-series."""
from biomech import stride_direction


# Front foot starts to the RIGHT of the back foot (pitcher side = +x) and
# moves further right (toward pitcher) by foot plant → toward_pitcher True.
def test_forward_stride_toward_pitcher():
    front = [50, 52, 60, 75, 90]   # moves +x (toward pitcher side)
    back  = [10, 10, 11, 10, 10]   # stays put
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is True
    assert out["dx_norm"] > 0

# Step-in-the-bucket: front foot pulls BACK toward the back foot (away from
# pitcher) → toward_pitcher False, negative dx_norm.
def test_bail_out_not_toward_pitcher():
    front = [90, 85, 70, 55, 45]   # moves -x (away from pitcher side)
    back  = [10, 10, 10, 10, 10]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is False
    assert out["dx_norm"] < 0

# Pitcher on the LEFT (front foot left of back foot): a true stride moves -x.
def test_left_facing_forward_stride():
    front = [50, 40, 30, 20, 10]   # moves -x, but that's TOWARD pitcher here
    back  = [90, 90, 90, 90, 90]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is True
    assert out["dx_norm"] > 0

def test_no_stride_is_not_toward():
    front = [50, 50, 51, 50, 50]   # barely moves
    back  = [10, 10, 10, 10, 10]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is False

def test_degenerate_failsoft_lenient():
    # Empty / bad torso / out-of-range index → lenient fallback (True, 0.0)
    assert stride_direction([], [], 0, 0, 100.0) == {"toward_pitcher": True, "dx_norm": 0.0}
    assert stride_direction([1, 2], [1, 2], 0, 1, 0.0) == {"toward_pitcher": True, "dx_norm": 0.0}
    assert stride_direction([1, 2], [1, 2], 0, 9, 100.0) == {"toward_pitcher": True, "dx_norm": 0.0}
