"""TDD tests for pillar-sourced drill recommendations.

Requirements:
1. gaps_from_pillars(pillars) -> list  in drills.py
   - rank weakest CONFIDENT first (lowest compliance among confidence > 0)
   - skip pillars with confidence == 0 or compliance is None
   - returned entries shaped so classify_gap / build_drill_plan consume them
   - pillar → category mapping per spec:
       sequence  → sequencing
       stability → head_stability
       timing    → timing
       stride    → knee_extension

2. Wire in analyzer.py: drill plan from gaps_from_pillars(pillars), not pro-difference gaps.

3. pro_relative_line(pillar, pro_name) -> str
   Template: "This one tightens the move that gets you closer to how {pro} {verb}."
   Verbs: sequence→"sequences", stability→"stays quiet on the ball",
          timing→"stays on time", stride→"lands and braces"
   NEVER phrased as a fault ("you don't ... like {pro}" is banned).

4. External-focus cues in _narrate_* player-facing "what the fix feels like" lines.

5. Plain language — no jargon in player-facing copy:
   - "kinematic" (kinematic sequence / kinematic chain)
   - "X-Factor" or "X-factor"
   - "re-extension" (in player-facing copy)
   - "torso-relative" (in player-facing copy)
"""

from __future__ import annotations

import sys
import os

import pytest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from drills import (
    gaps_from_pillars,
    pro_relative_line,
    build_drill_plan,
    DRILL_DB,
    _narrate_head_stability,
    _narrate_sequencing,
    _narrate_knee,
    _narrate_timing_cat,
    _narrate_front_side_stability,
)


# ---- gaps_from_pillars ----

def test_gaps_from_pillars_weakest_first():
    """Weakest confident pillar (sequence, compliance=0.2) should rank first."""
    pillars = {
        "sequence":  {"compliance": 0.2, "confidence": 0.9, "label": "Power Sequence"},
        "stability": {"compliance": 0.8, "confidence": 0.8, "label": "Head Stability"},
        "timing":    {"compliance": 0.7, "confidence": 0.7, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.6, "confidence": 0.6, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    assert len(gaps) > 0
    # The first gap should map to "sequencing" (weakest pillar)
    from drills import classify_gap
    top_cat = classify_gap(gaps[0])
    assert top_cat == "sequencing"


def test_gaps_from_pillars_zero_confidence_skipped():
    """A pillar with confidence=0 must be skipped even if compliance is low."""
    pillars = {
        "sequence":  {"compliance": 0.05, "confidence": 0.0, "label": "Power Sequence"},  # skip
        "stability": {"compliance": 0.4,  "confidence": 0.8, "label": "Head Stability"},
        "timing":    {"compliance": 0.9,  "confidence": 0.7, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.9,  "confidence": 0.6, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    # sequence should not appear (confidence=0 skipped)
    from drills import classify_gap
    cats = [classify_gap(g) for g in gaps]
    assert "sequencing" not in cats
    # stability should be first (weakest among confident pillars)
    assert cats[0] == "head_stability"


def test_gaps_from_pillars_none_compliance_skipped():
    """A pillar with compliance=None must be skipped."""
    pillars = {
        "sequence":  {"compliance": None, "confidence": 0.9, "label": "Power Sequence"},
        "stability": {"compliance": 0.5,  "confidence": 0.8, "label": "Head Stability"},
        "timing":    {"compliance": 0.9,  "confidence": 0.7, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.9,  "confidence": 0.6, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    from drills import classify_gap
    cats = [classify_gap(g) for g in gaps]
    assert "sequencing" not in cats


def test_gaps_from_pillars_pillar_to_category_mapping():
    """Each pillar maps to the correct drill category per spec."""
    pillars = {
        "sequence":  {"compliance": 0.4, "confidence": 0.9, "label": "Power Sequence"},
        "stability": {"compliance": 0.5, "confidence": 0.9, "label": "Head Stability"},
        "timing":    {"compliance": 0.6, "confidence": 0.9, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.7, "confidence": 0.9, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    from drills import classify_gap
    cats = [classify_gap(g) for g in gaps]
    # All four should map to their expected categories
    assert "sequencing" in cats
    assert "head_stability" in cats
    assert "timing" in cats
    assert "knee_extension" in cats


def test_gaps_from_pillars_ordered_by_compliance():
    """Gaps should be ordered weakest compliance first (ascending)."""
    pillars = {
        "sequence":  {"compliance": 0.3, "confidence": 0.9, "label": "Power Sequence"},
        "stability": {"compliance": 0.1, "confidence": 0.9, "label": "Head Stability"},
        "timing":    {"compliance": 0.8, "confidence": 0.9, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.6, "confidence": 0.9, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    from drills import classify_gap
    cats = [classify_gap(g) for g in gaps]
    # stability (0.1) should come before sequence (0.3)
    assert cats.index("head_stability") < cats.index("sequencing")


def test_gaps_from_pillars_empty_when_all_zero_confidence():
    """No confident pillars → empty list."""
    pillars = {
        "sequence":  {"compliance": 0.1, "confidence": 0.0, "label": "Power Sequence"},
        "stability": {"compliance": 0.1, "confidence": 0.0, "label": "Head Stability"},
    }
    gaps = gaps_from_pillars(pillars)
    assert gaps == []


def test_gaps_from_pillars_feeds_build_drill_plan():
    """gaps_from_pillars output should work with build_drill_plan."""
    pillars = {
        "sequence":  {"compliance": 0.2, "confidence": 0.9, "label": "Power Sequence"},
        "stability": {"compliance": 0.8, "confidence": 0.8, "label": "Head Stability"},
        "timing":    {"compliance": 0.7, "confidence": 0.7, "label": "Timing & Tempo"},
        "stride":    {"compliance": 0.6, "confidence": 0.6, "label": "Front-Side Brace"},
    }
    gaps = gaps_from_pillars(pillars)
    plan = build_drill_plan(gaps, top_n_categories=2)
    assert len(plan["categories"]) > 0
    # Top category should be sequencing (sequence = weakest pillar)
    assert plan["categories"][0]["category"] == "sequencing"


# ---- pro_relative_line ----

def test_pro_relative_line_sequence_verb():
    """sequence pillar uses verb 'sequences'."""
    line = pro_relative_line("sequence", "Juan Soto")
    assert "Juan Soto" in line
    assert "sequences" in line
    # Must match the template structure
    assert "tightens" in line or "closer to how" in line


def test_pro_relative_line_stability_verb():
    """stability pillar uses verb 'stays quiet on the ball'."""
    line = pro_relative_line("stability", "Mookie Betts")
    assert "Mookie Betts" in line
    assert "stays quiet on the ball" in line


def test_pro_relative_line_timing_verb():
    """timing pillar uses verb 'stays on time'."""
    line = pro_relative_line("timing", "Ronald Acuna")
    assert "Ronald Acuna" in line
    assert "stays on time" in line


def test_pro_relative_line_stride_verb():
    """stride pillar uses verb 'lands and braces'."""
    line = pro_relative_line("stride", "Aaron Judge")
    assert "Aaron Judge" in line
    assert "lands and braces" in line


def test_pro_relative_line_never_phrased_as_fault():
    """The pro-relative line must NEVER be phrased as a fault."""
    for pillar in ("sequence", "stability", "timing", "stride"):
        line = pro_relative_line(pillar, "Mike Trout")
        lower = line.lower()
        # Banned fault patterns
        assert "you don't" not in lower
        assert "you do not" not in lower
        assert "unlike" not in lower
        assert "fail" not in lower
        assert "can't" not in lower
        assert "cannot" not in lower


def test_pro_relative_line_template_structure():
    """Line must follow the spec template."""
    line = pro_relative_line("sequence", "Bryce Harper")
    # Template: "This one tightens the move that gets you closer to how {pro} {verb}."
    assert line.startswith("This one tightens")
    assert "Bryce Harper" in line
    assert line.endswith(".")


# ---- External-focus cues (player-facing "what the fix feels like") ----

def test_external_cue_sequencing_no_internal_cues():
    """Sequencing narrate: player-facing fix line uses external cue (bat stays back / whip)."""
    paragraphs = _narrate_sequencing([], "Any Pro")
    # The fix paragraph should be external cue: casting/sequence cue per spec
    fix_para = paragraphs[-1]  # last paragraph is the fix
    lower = fix_para.lower()
    # External cue keywords from spec table
    assert (
        "bat" in lower or "barrel" in lower or "back" in lower
    ), f"Expected external cue in: {fix_para}"


def test_external_cue_head_stability_no_internal_cues():
    """Head stability fix should use external cue: 'eyes glued to the contact spot'."""
    # Build a minimal head gap
    gaps = [{"label": "Total head drift (torso-rel)", "group": "Head",
             "p": 0.4, "r": 0.1, "units": "T"}]
    paragraphs = _narrate_head_stability(gaps, "Any Pro")
    fix_para = paragraphs[-1]
    lower = fix_para.lower()
    # External cue per spec: "Keep your eyes glued to the contact spot"
    assert "eyes" in lower or "contact spot" in lower or "glued" in lower, \
        f"Expected external cue in: {fix_para}"


def test_external_cue_front_side_stability():
    """Front-side stability fix should use external cue: shoulder/pitcher/barrel."""
    paragraphs = _narrate_front_side_stability([], "Any Pro")
    fix_para = paragraphs[-1]
    lower = fix_para.lower()
    # External cue per spec: "Keep your front shoulder pointed at the pitcher until..."
    assert ("shoulder" in lower or "pitcher" in lower or "barrel" in lower), \
        f"Expected external cue in: {fix_para}"


# ---- Plain language — no jargon in player-facing copy ----

JARGON_TERMS = [
    "kinematic",
    "kinetic chain",
    "X-Factor",
    "X-factor",
    "re-extension",
    "torso-relative",
]


def _collect_player_facing_copy():
    """Collect all player-facing copy from DRILL_DB why_it_matters + narrate functions."""
    texts = []

    # DRILL_DB why_it_matters strings
    for cat, info in DRILL_DB.items():
        texts.append(("DRILL_DB.{}.why_it_matters".format(cat), info["why_it_matters"]))

    # _narrate_* output (paragraphs)
    dummy_gap = {"label": "Total head drift (torso-rel)", "group": "Head",
                 "p": 0.4, "r": 0.1, "units": "T"}
    for para in _narrate_head_stability([dummy_gap], "TestPro"):
        texts.append(("_narrate_head_stability", para))

    for para in _narrate_sequencing([], "TestPro"):
        texts.append(("_narrate_sequencing", para))

    for para in _narrate_front_side_stability([], "TestPro"):
        texts.append(("_narrate_front_side_stability", para))

    dummy_knee_gap = {"label": "Re-extension", "group": "Front Knee",
                      "p": 5.0, "r": 15.0, "units": "°"}
    for para in _narrate_knee([dummy_knee_gap], "TestPro"):
        texts.append(("_narrate_knee", para))

    dummy_timing_gap = {"label": "Foot plant → launch", "group": "Timing",
                        "p": 120.0, "r": 100.0, "units": "ms"}
    for para in _narrate_timing_cat([dummy_timing_gap], "TestPro"):
        texts.append(("_narrate_timing_cat", para))

    return texts


@pytest.mark.parametrize("jargon", JARGON_TERMS)
def test_no_jargon_in_player_facing_copy(jargon):
    """Player-facing copy must not contain banned jargon terms."""
    texts = _collect_player_facing_copy()
    violations = []
    for source, text in texts:
        if jargon.lower() in text.lower():
            violations.append(f"  [{source}]: ...{text[:120]}...")
    assert not violations, (
        f"Jargon '{jargon}' found in player-facing copy:\n" + "\n".join(violations)
    )


# ---- Integration: analyzer wires drill plan from pillars ----

def test_analyzer_drill_plan_from_pillars(tmp_path):
    """analyzer.analyze() drill plan must come from pillars, not pro-difference."""
    import json
    import os

    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    REFS = os.path.join(ROOT, "references")

    with open(os.path.join(REFS, "aaron_judge.json")) as f:
        fp = json.load(f)

    # Give a VERY weak sequence pillar (sequencing_lag_ms strongly negative = casting)
    fp["sequence"] = {
        "sequencing_lag_ms": -120.0,  # strong casting → worst pillar
        "peak_hip_omega_deg_s": None,
        "front_side_stability_pct": None,
        "hip_peak_frame": None,
        "shoulder_peak_frame": None,
        "rating": {
            "sequencing_lag": "poor",
            "peak_hip_omega": None,
            "front_side_stability": None,
        },
    }
    fp["age"] = 14
    fp["video"] = "test_pillar_drill.mp4"

    out = tmp_path / "test_pillar_drill.json"
    out.write_text(json.dumps(fp))

    from analyzer import analyze
    result = analyze(str(out), "mike_trout")
    plan = result["drill_plan"]

    # Should have categories
    assert len(plan["categories"]) > 0

    # The top drill category should be sequencing (weakest pillar = sequence with -120ms lag)
    top_cat = plan["categories"][0]["category"]
    assert top_cat == "sequencing", f"Expected 'sequencing' as top category, got '{top_cat}'"


def test_analyzer_drill_plan_contains_pro_relative_line(tmp_path):
    """Each fix card in the drill plan should contain a pro-relative line."""
    import json
    import os

    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    REFS = os.path.join(ROOT, "references")

    with open(os.path.join(REFS, "mookie_betts.json")) as f:
        fp = json.load(f)

    fp["sequence"] = {
        "sequencing_lag_ms": -80.0,
        "peak_hip_omega_deg_s": None,
        "front_side_stability_pct": None,
        "hip_peak_frame": None,
        "shoulder_peak_frame": None,
        "rating": {
            "sequencing_lag": "poor",
            "peak_hip_omega": None,
            "front_side_stability": None,
        },
    }
    fp["age"] = 13
    fp["video"] = "test_pro_line.mp4"

    out = tmp_path / "test_pro_line.json"
    out.write_text(json.dumps(fp))

    from analyzer import analyze
    result = analyze(str(out), "mookie_betts")
    plan = result["drill_plan"]
    pro_name = result["mlb_match"]["pro_name"]

    # Each category should have a pro_relative_line containing the pro name
    for cat in plan["categories"]:
        assert "pro_relative_line" in cat, \
            f"Missing pro_relative_line in category {cat['category']}"
        prl = cat["pro_relative_line"]
        assert pro_name in prl, \
            f"pro_relative_line '{prl}' doesn't contain pro name '{pro_name}'"
        # Never phrased as a fault
        lower = prl.lower()
        assert "you don't" not in lower
        assert "unlike" not in lower
