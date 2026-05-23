"""Integration tests for the Swing Score + movement Match wired into
analyzer.analyze().

We feed a REAL MLB reference fingerprint (references/aaron_judge.json) in as
the *player* clip — it has every field a real player fingerprint has except
the player-only `sequence` block, which we add here with a plausible
sequencing_lag_ms (references genuinely lack it). We also tag an `age` so the
age bracket resolves to something other than the default.

Asserts the new result contract:
  - swing_score: int 0..100 or None
  - pillars: {sequence,stability,timing,stride} each with compliance/
             confidence/label
  - mlb_match.pro_name: a real name
  - what_you_did_well: non-empty
  - existing fields (score, reference) still present for back-compat.
"""
import json
import os

import pytest

from analyzer import analyze, age_bracket

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFS = os.path.join(ROOT, "references")


@pytest.fixture
def player_fp_path(tmp_path):
    """A realistic player fingerprint built from a real reference, plus the
    player-only `sequence` block and an `age`."""
    with open(os.path.join(REFS, "aaron_judge.json")) as f:
        fp = json.load(f)
    # References lack the player-only Power Sequence block — add a plausible
    # one (hips lead slightly = good sequencing).
    fp["sequence"] = {
        "sequencing_lag_ms": 15.0,
        "peak_hip_omega_deg_s": None,
        "front_side_stability_pct": None,
        "hip_peak_frame": None,
        "shoulder_peak_frame": None,
        "rating": {
            "sequencing_lag": "good",
            "peak_hip_omega": None,
            "front_side_stability": None,
        },
    }
    fp["age"] = 16  # → "15-17" bracket
    fp["video"] = "test_player.mp4"
    out = tmp_path / "player_fingerprint.json"
    out.write_text(json.dumps(fp))
    return str(out)


def test_age_bracket_mapping():
    assert age_bracket(9) == "8-10"
    assert age_bracket(11) == "11-12"
    assert age_bracket(13) == "13-14"
    assert age_bracket(16) == "15-17"
    # Out-of-range / unknown ages still resolve to a valid bracket.
    assert age_bracket(7) in ("8-10", "11-12", "13-14", "15-17")
    assert age_bracket(40) in ("8-10", "11-12", "13-14", "15-17")
    assert age_bracket(None) in ("8-10", "11-12", "13-14", "15-17")


def test_analyze_returns_swing_score(player_fp_path):
    # Use a DIFFERENT reference as the comparison target so the legacy
    # comparison path still exercises (any real slug works).
    result = analyze(player_fp_path, "mike_trout")

    # Headline Swing Score.
    ss = result["swing_score"]
    assert ss is None or (isinstance(ss, int) and 0 <= ss <= 100)


def test_analyze_pillars_shape(player_fp_path):
    result = analyze(player_fp_path, "mike_trout")
    pillars = result["pillars"]
    assert set(pillars.keys()) == {"sequence", "stability", "timing", "stride"}
    for name, p in pillars.items():
        assert "compliance" in p
        assert "confidence" in p
        assert "label" in p
        assert p["compliance"] is None or isinstance(p["compliance"], float)
        assert isinstance(p["confidence"], float)
        assert 0.0 <= p["confidence"] <= 1.0
        assert isinstance(p["label"], str) and p["label"]


def test_analyze_mlb_match(player_fp_path):
    result = analyze(player_fp_path, "mike_trout")
    m = result["mlb_match"]
    assert isinstance(m["pro_name"], str) and m["pro_name"]
    assert isinstance(m["slug"], str) and m["slug"]
    assert isinstance(m["movement_match_pct"], int)
    assert 0 <= m["movement_match_pct"] <= 100
    assert isinstance(m["confident"], bool)
    assert isinstance(m["locked"], bool)


def test_analyze_what_you_did_well_nonempty(player_fp_path):
    result = analyze(player_fp_path, "mike_trout")
    wd = result["what_you_did_well"]
    assert isinstance(wd, str) and wd.strip()


def test_analyze_keeps_backcompat_fields(player_fp_path):
    result = analyze(player_fp_path, "mike_trout")
    # Old contract still present so the report can fall back to it.
    assert "score" in result
    assert isinstance(result["score"], int)
    assert "reference" in result
    assert result["reference"].get("name")


def test_locked_match_replays_locked_pro(player_fp_path):
    # When a reference is passed in (the locked-pro flow in app.py), the MLB
    # match should REPLAY that pro, not recompute a movement match — and be
    # flagged locked.
    result = analyze(player_fp_path, "mookie_betts")
    m = result["mlb_match"]
    assert m["slug"] == "mookie_betts"
    assert m["pro_name"] == "Mookie Betts"
    assert m["locked"] is True
