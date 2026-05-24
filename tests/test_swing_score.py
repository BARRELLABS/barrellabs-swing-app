import pytest
from swing_score import (score_sequence, score_stability, score_timing,
                         score_stride, aggregate_score)

def test_sequence_hips_lead_is_full():
    assert score_sequence(lag_ms=0.0, bracket="13-14") == pytest.approx(1.0, abs=0.01)
    assert score_sequence(lag_ms=20.0, bracket="13-14") == pytest.approx(1.0, abs=0.01)

def test_sequence_casting_is_low():
    assert score_sequence(lag_ms=-120.0, bracket="13-14") < 0.2

def test_sequence_marginal_midrange():
    v = score_sequence(lag_ms=-50.0, bracket="13-14")
    assert 0.45 < v < 0.75

def test_sequence_age_widens_for_young():
    assert score_sequence(-60.0, "8-10") > score_sequence(-60.0, "15-17")

def test_sequence_none_passthrough():
    assert score_sequence(None, "13-14") is None

def test_stability_quiet_head_full():
    # A genuinely quiet head (within the elite range) scores ~1.0.
    assert score_stability(total_drift_torso=0.03, bracket="13-14") == pytest.approx(1.0, abs=0.01)

def test_stability_mediocre_amateur_not_full():
    # Re-anchored: a mediocre amateur (0.12T drift) must NOT score a perfect
    # 1.0 the way the old good=0.15 threshold let it. The pillar has to
    # discriminate in the amateur range (every pro is below 0.09T).
    assert score_stability(0.12, "13-14") < 0.95

def test_stability_big_drift_low():
    assert score_stability(0.7, "13-14") < 0.2

def test_timing_balanced_tempo_high():
    assert score_timing(load_ms=400, launch_to_contact_ms=150, bracket="13-14") > 0.7

def test_timing_no_gather_low():
    assert score_timing(load_ms=40, launch_to_contact_ms=200, bracket="13-14") < 0.5

def test_timing_none_when_missing():
    assert score_timing(load_ms=0, launch_to_contact_ms=0, bracket="13-14") is None

def test_timing_implausible_downswing_dropped():
    # A sub-40ms launch->contact can't be a real downswing at phone frame
    # rates — it's a contact/launch mis-index. Drop the pillar (None) rather
    # than rewarding the artifact as elite tempo (the Machado 18ms case).
    assert score_timing(load_ms=488, launch_to_contact_ms=18, bracket="13-14") is None

def test_timing_zero_gather_scores_low_not_none():
    # A genuine 0ms gather is *measured* (a real, badly-timed swing) and must
    # score low — it should NOT vanish like an unmeasured signal.
    assert score_timing(load_ms=0, launch_to_contact_ms=200, bracket="13-14") == 0.0

def test_timing_none_load_drops_pillar():
    # Truly absent signal (None) → unmeasurable → drop the pillar.
    assert score_timing(load_ms=None, launch_to_contact_ms=200, bracket="13-14") is None

def test_stride_firm_front_side_high():
    assert score_stride(knee_re_extension_deg=20.0, stride_toward_pitcher=True, bracket="13-14") > 0.7

def test_stride_soft_front_side_low():
    assert score_stride(knee_re_extension_deg=0.0, stride_toward_pitcher=True, bracket="13-14") < 0.5

def test_stride_bad_direction_gated():
    assert score_stride(20.0, stride_toward_pitcher=False, bracket="13-14") < 0.5

def test_aggregate_confidence_weighted():
    pillars = {
        "sequence":  {"compliance": 1.0, "confidence": 1.0},
        "stability": {"compliance": 0.0, "confidence": 1.0},
        "timing":    {"compliance": 1.0, "confidence": 1.0},
        "stride":    {"compliance": 1.0, "confidence": 1.0},
    }
    assert aggregate_score(pillars) == 75

def test_aggregate_drops_zero_confidence():
    pillars = {
        "sequence":  {"compliance": 1.0, "confidence": 1.0},
        "stability": {"compliance": 0.0, "confidence": 0.0},
    }
    assert aggregate_score(pillars) == 100

def test_aggregate_none_when_nothing_measurable():
    assert aggregate_score({"sequence": {"compliance": 0.5, "confidence": 0.0}}) is None

def test_aggregate_drops_none_compliance_pillars():
    # A pillar with compliance=None is unmeasurable and must drop out, not crash.
    pillars = {
        "a": {"compliance": None, "confidence": 1.0},   # unmeasurable → drop
        "b": {"compliance": 0.8, "confidence": 1.0},
        "c": {"compliance": 0.6, "confidence": 1.0},
    }
    # Mean of the two measurable pillars = (0.8 + 0.6)/2 = 0.7 → 70
    assert aggregate_score(pillars) == 70

def test_aggregate_none_compliance_with_zero_conf_is_safe():
    # compliance=None with confidence=0 must not raise either.
    pillars = {
        "a": {"compliance": None, "confidence": 0.0},
        "b": {"compliance": 1.0, "confidence": 1.0},
    }
    assert aggregate_score(pillars) == 100

def test_aggregate_all_none_returns_none():
    pillars = {"a": {"compliance": None, "confidence": 1.0},
               "b": {"compliance": None, "confidence": 0.5}}
    assert aggregate_score(pillars) is None
