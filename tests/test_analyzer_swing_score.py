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
    # Uniform dict shape: every path (locked + auto-pick) carries `cluster`
    # so downstream readers never KeyError on one path but not the other.
    assert "cluster" in m


def test_match_stats_cache_retries_after_failed_load(monkeypatch, tmp_path):
    """A failed match-stats load must not poison analyzer's module cache —
    the sentinel stays so a later valid load succeeds (no permanent disable
    after a transient I/O error)."""
    import json as _json
    import analyzer as az

    monkeypatch.setattr(az, "_MATCH_STATS_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(az, "_MATCH_STATS_CACHE", az._MATCH_STATS_UNSET)

    assert az._load_match_stats() is None
    assert az._MATCH_STATS_CACHE is az._MATCH_STATS_UNSET  # not poisoned to {}

    good = {"means": [0.0], "stds": [1.0], "centroids": [[0.0]],
            "pros": [{"slug": "x", "name": "X", "z": [0.0], "cluster": 0}]}
    good_path = tmp_path / "stats.json"
    good_path.write_text(_json.dumps(good))
    monkeypatch.setattr(az, "_MATCH_STATS_PATH", str(good_path))

    assert az._load_match_stats() == good


def test_age_known_true_when_fingerprint_has_age(player_fp_path, tmp_path):
    import json
    fp = json.load(open(player_fp_path))
    fp["age"] = 11
    p = tmp_path / "fp_age.json"
    p.write_text(json.dumps(fp))
    result = analyze(str(p), "mike_trout")
    assert result["age_known"] is True
    assert result["age_bracket"] == "11-12"

def test_age_known_false_when_age_absent(player_fp_path, tmp_path):
    import json
    fp = json.load(open(player_fp_path))
    fp.pop("age", None)
    p = tmp_path / "fp_noage.json"
    p.write_text(json.dumps(fp))
    result = analyze(str(p), "mike_trout")
    assert result["age_known"] is False
    assert result["age_bracket"] == "13-14"  # default

def test_stride_gate_reads_fingerprint(player_fp_path, tmp_path):
    import json
    base = json.load(open(player_fp_path))
    base["knee_deg"] = dict(base.get("knee_deg") or {}, re_extension=18.0,
                            at_foot_plant=150.0, min_during_load=140.0)
    toward = dict(base); toward["stride"] = {"toward_pitcher": True, "dx_norm": 0.2}
    away = dict(base); away["stride"] = {"toward_pitcher": False, "dx_norm": -0.1}
    pa = tmp_path / "toward.json"; pa.write_text(json.dumps(toward))
    pb = tmp_path / "away.json"; pb.write_text(json.dumps(away))
    ra = analyze(str(pa), "mike_trout")
    rb = analyze(str(pb), "mike_trout")
    # Stride pillar compliance must be lower (or equal) when not striding to pitcher.
    assert rb["pillars"]["stride"]["compliance"] <= ra["pillars"]["stride"]["compliance"]


def test_pillar_reliability_ceiling_caps_noisy_pillars():
    from analyzer import _pillar_confidence, _PILLAR_RELIABILITY
    # Sequence & Stride are structurally capped below 1.0 on phone video.
    assert _PILLAR_RELIABILITY["sequence"] < 1.0
    assert _PILLAR_RELIABILITY["stride"] < 1.0
    assert _PILLAR_RELIABILITY["stability"] == 1.0
    assert _PILLAR_RELIABILITY["timing"] == 1.0
    # A clean signal for a capped pillar yields confidence == its ceiling
    # (no rotation/visibility penalty active).
    conf = _pillar_confidence(0.5, rotation_dependent=False,
                              rotation_view_sensitive=False, pose_visibility=1.0,
                              reliability_ceiling=_PILLAR_RELIABILITY["stride"])
    assert conf == _PILLAR_RELIABILITY["stride"]
    # None still drops out entirely.
    assert _pillar_confidence(None, rotation_dependent=False,
                              rotation_view_sensitive=False, pose_visibility=1.0,
                              reliability_ceiling=0.5) == 0.0


def test_noisy_pillar_zero_drags_less_than_before(player_fp_path, tmp_path):
    # A swing strong on Stability+Timing but zero on Sequence+Stride should now
    # score clearly above 50 (the trustworthy pillars dominate), not be dragged
    # to the midpoint by full-weight zero reads.
    import json
    fp = json.load(open(player_fp_path))
    fp["age"] = 13
    # Force the pillar inputs: strong stability (tiny head drift) + strong timing
    # (big gather, short fire), zero stride (no knee re-extension), casting seq.
    fp["head_movement_normalized_foot_plant_to_contact"] = {"total_drift_torso": 0.05, "dx_torso": 0.03, "dy_torso": 0.02}
    fp["timing_ms"] = dict(fp.get("timing_ms") or {}, load_duration=500.0, launch_to_contact=150.0)
    fp["timing_ms_corrected"] = dict(fp.get("timing_ms_corrected") or {}, load_duration=500.0, launch_to_contact=150.0)
    fp["knee_deg"] = dict(fp.get("knee_deg") or {}, re_extension=0.0, at_foot_plant=150.0, min_during_load=148.0)
    fp["sequence"] = dict(fp.get("sequence") or {}, sequencing_lag_ms=-200.0)
    p = tmp_path / "fp.json"; p.write_text(json.dumps(fp))
    r = analyze(str(p), "mike_trout")
    assert r["swing_score"] is not None and r["swing_score"] >= 55
