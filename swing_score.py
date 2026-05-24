"""Independent, age-fair Swing Score — pure functions (no Streamlit/I-O).

Each pillar returns compliance in [0,1]; confidence is applied at aggregation.
Mirrors the pure-function style of biomech.py.
Spec: docs/superpowers/specs/2026-05-23-swing-score-and-mlb-match-design.md
"""
from __future__ import annotations
from typing import Optional

BRACKETS = ("8-10", "11-12", "13-14", "15-17")


def _ramp(x: float, good: float, bad: float) -> float:
    """1.0 at/over `good`, 0.0 at/under `bad`, linear between.
    Handles both 'higher is better' (good>bad) and 'lower is better' (good<bad)."""
    if good == bad:
        return 1.0 if x >= good else 0.0
    t = (x - bad) / (good - bad)
    return max(0.0, min(1.0, t))


_SEQ_WIDEN = {"8-10": 30.0, "11-12": 20.0, "13-14": 0.0, "15-17": 0.0}

def score_sequence(lag_ms: Optional[float], bracket: str) -> Optional[float]:
    """Hips-lead direction (good >= 0ms); ramps to the casting floor."""
    if lag_ms is None:
        return None
    widen = _SEQ_WIDEN.get(bracket, 0.0)
    return _ramp(lag_ms, good=0.0, bad=-100.0 - widen)


_STAB_WIDEN = {"8-10": 0.10, "11-12": 0.05, "13-14": 0.0, "15-17": 0.0}

def score_stability(total_drift_torso: Optional[float], bracket: str) -> Optional[float]:
    """Lower head drift = better. good <= 0.15T (+widen), ~0 by 0.6T."""
    if total_drift_torso is None:
        return None
    w = _STAB_WIDEN.get(bracket, 0.0)
    return _ramp(abs(total_drift_torso), good=0.15 + w, bad=0.60 + w)


def score_timing(load_ms, launch_to_contact_ms, bracket: str) -> Optional[float]:
    """Reward a real gather then a crisp fire (ratio), not absolute speed."""
    # Distinguish "not measured" (None → drop the pillar) from a genuine 0ms
    # gather (a real, poorly-timed swing that should score low, not vanish).
    if load_ms is None or launch_to_contact_ms is None or launch_to_contact_ms <= 0:
        return None
    ratio = load_ms / launch_to_contact_ms
    floor = {"8-10": 0.5, "11-12": 0.6, "13-14": 0.8, "15-17": 0.8}.get(bracket, 0.8)
    return _ramp(ratio, good=2.0, bad=floor)


_STRIDE_GOOD = {"8-10": 12.0, "11-12": 15.0, "13-14": 18.0, "15-17": 20.0}

def score_stride(knee_re_extension_deg, stride_toward_pitcher: bool, bracket: str) -> Optional[float]:
    """Front-leg brace (re-extension) gated by a sane forward stride."""
    if knee_re_extension_deg is None:
        return None
    if not stride_toward_pitcher:
        return 0.3
    return _ramp(knee_re_extension_deg, good=_STRIDE_GOOD.get(bracket, 18.0), bad=0.0)


def aggregate_score(pillars: dict) -> Optional[int]:
    """Confidence-weighted mean of compliance across pillars. Pillars that are
    unmeasurable (compliance is None) or have zero confidence drop out
    entirely. Returns None if nothing is measurable."""
    measurable = [p for p in pillars.values()
                  if p.get("compliance") is not None and p.get("confidence", 0) > 0]
    den = sum(p["confidence"] for p in measurable)
    if den <= 0:
        return None
    num = sum(p["compliance"] * p["confidence"] for p in measurable)
    return round(100.0 * num / den)
