"""_pose_visibility must use the scalar lower_body_visibility that detect_phases
stamps onto the fingerprint (the live upload path carries this, not raw
pose_frames). Without it the pillar-confidence softening for poorly-tracked
legs/feet never fires on real uploads."""
from analyzer import _pose_visibility


def test_uses_stamped_scalar():
    assert _pose_visibility({"lower_body_visibility": 0.3}) == 0.3


def test_clamps_out_of_range():
    assert _pose_visibility({"lower_body_visibility": 1.5}) == 1.0
    assert _pose_visibility({"lower_body_visibility": -0.2}) == 0.0


def test_absent_visibility_is_full_no_penalty():
    assert _pose_visibility({}) == 1.0


def test_bool_is_not_treated_as_a_scalar():
    # A stray True/False must not be read as a visibility value.
    assert _pose_visibility({"lower_body_visibility": True}) == 1.0
