"""pose_coverage_confidence: a global pillar-confidence multiplier from the
fraction of frames a pose was detected. Low coverage (poor light / distance /
motion blur) is the cheapest signal that every metric is unreliable, so the
score should soften rather than present a confident grade built on noise."""
from analyzer import pose_coverage_confidence


def test_missing_or_nonnumeric_is_full_confidence():
    assert pose_coverage_confidence(None) == 1.0
    assert pose_coverage_confidence("x") == 1.0
    assert pose_coverage_confidence(True) == 1.0  # bool is not a coverage value


def test_high_coverage_no_penalty():
    assert pose_coverage_confidence(0.95) == 1.0
    assert pose_coverage_confidence(0.80) == 1.0


def test_low_coverage_hits_floor():
    assert pose_coverage_confidence(0.30) == 0.25
    assert pose_coverage_confidence(0.05) == 0.25


def test_mid_coverage_ramps():
    # midpoint 0.55 -> 0.25 + (0.25/0.50)*0.75 = 0.625
    assert abs(pose_coverage_confidence(0.55) - 0.625) < 1e-9


def test_monotonic_non_decreasing():
    vals = [pose_coverage_confidence(c) for c in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert vals == sorted(vals)
