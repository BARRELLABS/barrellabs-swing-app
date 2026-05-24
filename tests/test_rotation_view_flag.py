"""rotation_view_flag: decide when 2D-width rotation metrics are viewpoint-
unreliable. The key fix — flag a player whose OWN clip is off-profile, even
against a profile reference, because the reference pool has ~no viewpoint
variance so a relative diff alone never fires on a real off-profile upload."""
from analyzer import rotation_view_flag


def test_both_profile_2d_is_trustworthy():
    s, r = rotation_view_flag(0.40, 0.40, "2d_width_ratio", "2d_width_ratio")
    assert s is False and r is None


def test_player_off_profile_flagged_vs_profile_ref():
    # Front-on player (0.62) vs profile ref (0.40): relative diff is only 0.22
    # (under the old 0.45 gate) but the clip itself is off-profile -> flag.
    s, r = rotation_view_flag(0.62, 0.40, "2d_width_ratio", "2d_width_ratio")
    assert s is True and r == "off_profile"


def test_mixed_method_is_sensitive():
    s, r = rotation_view_flag(0.40, 0.40, "3d_world", "2d_width_ratio")
    assert s is True and r == "mixed_method"


def test_both_3d_world_is_trustworthy():
    s, r = rotation_view_flag(0.65, 0.65, "3d_world", "3d_world")
    assert s is False and r is None


def test_large_relative_view_diff_still_flagged():
    # player in-band (0.52 < 0.55) but very different from ref -> view_diff.
    s, r = rotation_view_flag(0.52, 0.04, "2d_width_ratio", "2d_width_ratio")
    assert s is True and r == "view_diff"
