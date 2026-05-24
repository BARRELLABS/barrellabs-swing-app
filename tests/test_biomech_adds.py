"""Two accurate, phone-reliable additions derived from data the pipeline
already produces:
  - tempo_ratio: the gather:fire ratio the Timing pillar already grades,
    surfaced as a coach-legible number.
  - xfactor_timing_ms: WHEN peak hip-shoulder separation occurs relative to
    contact (a within-clip temporal landmark — robust to viewpoint, unlike the
    separation magnitude). Negative = peaks before contact (the elite pattern).
"""
from analyzer import tempo_ratio, xfactor_timing_ms


def test_tempo_ratio_basic():
    assert tempo_ratio({"load_duration": 400, "launch_to_contact": 200}) == 2.0


def test_tempo_ratio_missing_or_zero_is_none():
    assert tempo_ratio({}) is None
    assert tempo_ratio({"load_duration": 400, "launch_to_contact": 0}) is None
    assert tempo_ratio({"load_duration": None, "launch_to_contact": 200}) is None


def test_xfactor_timing_peak_before_contact_is_negative():
    p = {"rotation_deg": {"peak_separation_t": 1.00},
         "phases_t": {"contact": 1.05}, "slow_mo_factor": 1.0}
    # peak 50 ms before contact -> -50.0
    assert xfactor_timing_ms(p) == -50.0


def test_xfactor_timing_is_slow_mo_corrected():
    p = {"rotation_deg": {"peak_separation_t": 1.00},
         "phases_t": {"contact": 1.15}, "slow_mo_factor": 3.0}
    # raw -150 ms at 3x slow-mo -> -50.0 real-time-equivalent
    assert xfactor_timing_ms(p) == -50.0


def test_xfactor_timing_missing_inputs_none():
    assert xfactor_timing_ms({}) is None
    assert xfactor_timing_ms({"rotation_deg": {}, "phases_t": {}}) is None
