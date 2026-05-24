"""pitcher_sign: shared image-x orientation so 'toward the pitcher = positive'
is consistent across stride direction AND head drift. Without it, head Δx (raw
image-x) was labeled 'toward pitcher' but read backwards for one handedness,
so the drill copy told half of hitters the wrong drift direction."""
from biomech import pitcher_sign


def test_front_ankle_right_of_back_is_positive():
    assert pitcher_sign(0.62, 0.40) == 1.0


def test_front_ankle_left_of_back_is_negative():
    assert pitcher_sign(0.40, 0.62) == -1.0


def test_equal_defaults_positive():
    assert pitcher_sign(0.50, 0.50) == 1.0
