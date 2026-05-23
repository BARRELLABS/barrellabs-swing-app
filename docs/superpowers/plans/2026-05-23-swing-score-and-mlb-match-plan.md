# Swing Score + MLB Match (v1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pro-similarity scoring with an independent, age-fair **Swing Score** (4 principle pillars) that drives all diagnosis, and reframe the **MLB Match** as a movement-based, locked "who you swing like" hero (real pro name + quiet movement-match %).

**Architecture:** Two new pure-Python modules (`swing_score.py`, `mlb_match.py`) hold all the new logic and are unit-tested in isolation (same pattern as `biomech.py`). `analyzer.py` orchestrates: it computes the Swing Score (headline), resolves/locks the MLB Match, derives drill gaps **from the Score pillars only**, and returns new result fields. `drills.py`, `reference_library.py`, and the live report renderer `swing_report_dashboard_preview.py` are repointed to consume the new data. Everything degrades gracefully on low pose confidence (suppress, never fake).

**Tech Stack:** Python 3.11, pure-numpy/stdlib for the engines (no new deps), pytest, Streamlit for the report. Signals already on the fingerprint from `detect_phases.py`.

**Worktree:** `.claude/worktrees/swing-engine` (branch `claude/swing-engine`, off `main`).

**Spec:** `docs/superpowers/specs/2026-05-23-swing-score-and-mlb-match-design.md` (read it first).

**Baseline:** full suite is green before starting — run `/Users/logancollins/barrellabs-swing-app/.venv/bin/python -m pytest tests/ -q` and confirm pass.

---

## File structure

| File | Responsibility |
|---|---|
| `swing_score.py` (NEW) | Pure functions: 4 pillar compliance scorers, age-band widening, confidence weighting, 0-100 aggregation. No Streamlit, no I/O. |
| `mlb_match.py` (NEW) | Pure functions: scale-invariant movement feature vector, frozen pro z-stats + cluster centroids, nearest-pro-in-cluster, movement-match %. No I/O. |
| `tests/test_swing_score.py` (NEW) | Unit tests for every pillar curve + aggregation + confidence drop-out + age bands. |
| `tests/test_mlb_match.py` (NEW) | Unit tests: scale-invariance, cluster assignment, nearest pro, match %. |
| `analyzer.py` (MODIFY) | Orchestrate: compute swing_score, resolve+lock mlb_match, derive gaps from pillars, new result fields; stop using pro-similarity as the headline score. |
| `reference_library.py` (MODIFY) | Replace `_match_score` internals with `mlb_match` movement distance; keep `find_best_match`/`find_all_ranked` signatures + handedness mirror. |
| `drills.py` (MODIFY) | Source faults from Score pillars (not pro-diff), pillar→category map, pro-relative line, external-focus cues, plain-language copy. |
| `swing_report_dashboard_preview.py` (MODIFY) | New report order: Match reveal (name + gated %) → Swing Score + pillars + "what you did well" → reconciliation line → fixes → confidence badge → filming guide. |
| `scripts/build_match_stats.py` (NEW, one-shot) | Offline: compute z-stats + k=3 cluster centroids from the 17 references; write `mlb_match_stats.json` (frozen constants the engine loads). |

---

## Task 1: `swing_score.py` — pillar compliance scorers (pure, TDD)

**Files:**
- Create: `swing_score.py`
- Test: `tests/test_swing_score.py`

Each pillar is a pure function `(value, age_bracket) -> float in [0,1]`. Age bracket is one of `"8-10","11-12","13-14","15-17"`; younger brackets widen/lower-anchor the band.

- [ ] **Step 1: Write failing tests for the Sequence pillar**

```python
# tests/test_swing_score.py
import pytest
from swing_score import score_sequence, score_stability, score_timing, score_stride

def test_sequence_hips_lead_is_full():
    assert score_sequence(lag_ms=0.0, bracket="13-14") == pytest.approx(1.0, abs=0.01)
    assert score_sequence(lag_ms=20.0, bracket="13-14") == pytest.approx(1.0, abs=0.01)

def test_sequence_casting_is_low():
    assert score_sequence(lag_ms=-120.0, bracket="13-14") < 0.2

def test_sequence_marginal_midrange():
    v = score_sequence(lag_ms=-50.0, bracket="13-14")
    assert 0.45 < v < 0.75

def test_sequence_age_widens_for_young():
    # a -60ms lag is "casting" for a teen but more forgivable for 8-10
    assert score_sequence(-60.0, "8-10") > score_sequence(-60.0, "15-17")
```

- [ ] **Step 2: Run, expect failure** — `…/.venv/bin/python -m pytest tests/test_swing_score.py -q` → FAIL (module/functions missing).

- [ ] **Step 3: Implement Sequence + a shared soft-ramp helper**

```python
# swing_score.py
"""Independent, age-fair Swing Score — pure functions (no Streamlit/I-O).
Each pillar returns compliance in [0,1]; confidence is applied at aggregation.
Spec: docs/superpowers/specs/2026-05-23-swing-score-and-mlb-match-design.md
"""
from __future__ import annotations
from typing import Optional

BRACKETS = ("8-10", "11-12", "13-14", "15-17")

def _ramp(x: float, good: float, bad: float) -> float:
    """Linear ramp: 1.0 at/over `good`, 0.0 at/under `bad`, linear between.
    Works for both 'higher is better' (good>bad) and 'lower is better' (good<bad)."""
    if good == bad:
        return 1.0 if x >= good else 0.0
    t = (x - bad) / (good - bad)
    return max(0.0, min(1.0, t))

# Per-bracket leniency offset (ms) added to the casting floor for Sequence.
_SEQ_WIDEN = {"8-10": 30.0, "11-12": 20.0, "13-14": 0.0, "15-17": 0.0}

def score_sequence(lag_ms: Optional[float], bracket: str) -> Optional[float]:
    """Hips-lead direction. good >= 0ms; ramps down to the casting floor."""
    if lag_ms is None:
        return None
    widen = _SEQ_WIDEN.get(bracket, 0.0)
    # good at >=0, floor at -50 (teens), widened for younger brackets
    return _ramp(lag_ms, good=0.0, bad=-50.0 - widen)
```

- [ ] **Step 4: Run Sequence tests, expect PASS.**

- [ ] **Step 5: Add Stability, Timing, Stride tests**

```python
def test_stability_quiet_head_full():
    assert score_stability(total_drift_torso=0.10, bracket="13-14") == pytest.approx(1.0, abs=0.01)
def test_stability_big_drift_low():
    assert score_stability(0.7, "13-14") < 0.2
def test_timing_balanced_tempo_high():
    # load clearly longer than the explosive launch->contact
    assert score_timing(load_ms=400, launch_to_contact_ms=150, bracket="13-14") > 0.7
def test_timing_no_gather_low():
    assert score_timing(load_ms=40, launch_to_contact_ms=200, bracket="13-14") < 0.5
def test_stride_firm_front_side_high():
    assert score_stride(knee_re_extension_deg=20.0, stride_toward_pitcher=True, bracket="13-14") > 0.7
def test_stride_soft_front_side_low():
    assert score_stride(knee_re_extension_deg=0.0, stride_toward_pitcher=True, bracket="13-14") < 0.5
def test_stride_bad_direction_gated():
    assert score_stride(20.0, stride_toward_pitcher=False, bracket="13-14") < 0.5
```

- [ ] **Step 6: Run, expect failure (functions missing).**

- [ ] **Step 7: Implement Stability, Timing, Stride**

```python
_STAB_WIDEN = {"8-10": 0.10, "11-12": 0.05, "13-14": 0.0, "15-17": 0.0}
def score_stability(total_drift_torso: Optional[float], bracket: str) -> Optional[float]:
    """Lower drift = better. good <= 0.15T (+ widening), ~0 by 0.6T."""
    if total_drift_torso is None:
        return None
    w = _STAB_WIDEN.get(bracket, 0.0)
    return _ramp(abs(total_drift_torso), good=0.15 + w, bad=0.60 + w)

def score_timing(load_ms, launch_to_contact_ms, bracket: str) -> Optional[float]:
    """Reward a real gather then a crisp fire (ratio), not absolute speed."""
    if not load_ms or not launch_to_contact_ms or launch_to_contact_ms <= 0:
        return None
    ratio = load_ms / launch_to_contact_ms          # >1 = gather longer than fire (good)
    # good ratio ~2.0+, poor < ~0.8; younger brackets a touch more lenient
    floor = {"8-10": 0.5, "11-12": 0.6, "13-14": 0.8, "15-17": 0.8}.get(bracket, 0.8)
    return _ramp(ratio, good=2.0, bad=floor)

_STRIDE_GOOD = {"8-10": 12.0, "11-12": 15.0, "13-14": 18.0, "15-17": 20.0}
def score_stride(knee_re_extension_deg, stride_toward_pitcher: bool, bracket: str) -> Optional[float]:
    """Front-leg brace (re-extension) gated by a sane forward stride."""
    if knee_re_extension_deg is None:
        return None
    if not stride_toward_pitcher:
        return 0.3                                   # stride direction failed the sanity gate
    return _ramp(knee_re_extension_deg, good=_STRIDE_GOOD.get(bracket, 18.0), bad=0.0)
```

- [ ] **Step 8: Run all pillar tests, expect PASS.**

- [ ] **Step 9: Commit** — `git add swing_score.py tests/test_swing_score.py && git commit -m "feat(score): age-fair pillar compliance scorers"`

---

## Task 2: `swing_score.py` — aggregation with confidence drop-out (TDD)

**Files:** Modify `swing_score.py`; Test `tests/test_swing_score.py`

- [ ] **Step 1: Write failing tests**

```python
from swing_score import aggregate_score

def test_aggregate_confidence_weighted():
    pillars = {
        "sequence":  {"compliance": 1.0, "confidence": 1.0},
        "stability": {"compliance": 0.0, "confidence": 1.0},
        "timing":    {"compliance": 1.0, "confidence": 1.0},
        "stride":    {"compliance": 1.0, "confidence": 1.0},
    }
    assert aggregate_score(pillars) == 75   # (1+0+1+1)/4 * 100

def test_aggregate_drops_zero_confidence():
    pillars = {
        "sequence":  {"compliance": 1.0, "confidence": 1.0},
        "stability": {"compliance": 0.0, "confidence": 0.0},  # unmeasurable -> dropped
    }
    assert aggregate_score(pillars) == 100  # only the measurable pillar counts

def test_aggregate_none_when_nothing_measurable():
    assert aggregate_score({"sequence": {"compliance": 0.5, "confidence": 0.0}}) is None
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement**

```python
def aggregate_score(pillars: dict) -> Optional[int]:
    num = sum(p["compliance"] * p["confidence"] for p in pillars.values())
    den = sum(p["confidence"] for p in pillars.values())
    if den <= 0:
        return None
    return round(100.0 * num / den)
```

- [ ] **Step 4: Run, expect PASS. Step 5: Commit** — `git commit -am "feat(score): confidence-weighted aggregation"`

---

## Task 3: `mlb_match.py` — scale-invariant movement vector (TDD)

**Files:** Create `mlb_match.py`; Test `tests/test_mlb_match.py`

The vector uses dimensionless ratios so scaling a swing's size leaves it unchanged. Exact fingerprint field names MUST be confirmed against both player fingerprints and `references/*.json` during this task (see spec implementation note) — adjust accessors if a field differs.

- [ ] **Step 1: Write failing tests (scale-invariance is the key property)**

```python
# tests/test_mlb_match.py
import pytest
from mlb_match import movement_vector

_FP = {  # minimal fingerprint-shaped dict
  "timing_ms": {"load_duration": 400, "foot_plant_to_launch": 80,
                "launch_to_contact": 150, "total_swing": 230},
  "rotation_deg": {"peak_separation": 40, "separation_at_contact": 20,
                   "peak_separation_t": 0.6, "peak_hip": 45},
  "phases_t": {"foot_plant": 0.5, "contact": 0.8},
  "knee_deg": {"at_foot_plant": 150, "min_during_load": 130, "re_extension": 20},
  "head_movement_normalized_foot_plant_to_contact": {"total_drift_torso": 0.2},
}

def test_movement_vector_is_dimensionless_and_stable():
    v = movement_vector(_FP)
    assert isinstance(v, list) and len(v) == 8
    # all features are ratios/normalized -> finite, no raw degrees/ms leaking
    assert all(abs(x) < 100 for x in v)
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `movement_vector`** (defensive `.get` accessors; the 8 features from the spec). Each feature is a ratio; guard divide-by-zero with a small epsilon.

```python
# mlb_match.py
"""Scale-invariant movement match — pure functions. Spec §System 2."""
from __future__ import annotations
import json, math, os
from typing import Optional

_EPS = 1e-6
def _g(d, *path, default=0.0):
    for k in path:
        d = (d or {}).get(k)
        if d is None: return default
    return d

def movement_vector(fp: dict) -> list:
    t = fp.get("timing_ms") or {}
    total = (t.get("total_swing") or 0) or _EPS
    rot = fp.get("rotation_deg") or {}
    ph = fp.get("phases_t") or {}
    kn = fp.get("knee_deg") or {}
    plant_to_contact = ((ph.get("contact") or 0) - (ph.get("foot_plant") or 0)) or _EPS
    return [
        (t.get("load_duration") or 0) / total,
        (t.get("foot_plant_to_launch") or 0) / total,
        (t.get("launch_to_contact") or 0) / total,
        ((rot.get("peak_separation_t") or 0) - (ph.get("foot_plant") or 0)) / plant_to_contact,
        (rot.get("separation_at_contact") or 0) / ((rot.get("peak_separation") or 0) or _EPS),
        (rot.get("peak_hip") or 0) / (abs(rot.get("peak_separation") or 0) + _EPS),
        (kn.get("re_extension") or 0) / (((kn.get("at_foot_plant") or 0) - (kn.get("min_during_load") or 0)) + _EPS),
        _g(fp, "head_movement_normalized_foot_plant_to_contact", "total_drift_torso"),
    ]
```

- [ ] **Step 4: Run, expect PASS. Step 5: Commit** — `git commit -am "feat(match): scale-invariant movement vector"`

---

## Task 4: `scripts/build_match_stats.py` + `mlb_match` clustering & nearest-pro (TDD)

**Files:** Create `scripts/build_match_stats.py`; Modify `mlb_match.py`; Test `tests/test_mlb_match.py`

- [ ] **Step 1: Write the one-shot stats builder** — reads every `references/*.json`, computes each pro's `movement_vector`, then z-stats (mean/std per feature) and k=3 k-means centroids (use a tiny deterministic k-means with fixed seed; no sklearn dep — implement Lloyd's algo in ~30 lines), and writes `mlb_match_stats.json` = `{"means":[...], "stds":[...], "centroids":[[...]*3], "pros":[{"slug","name","z":[...],"cluster":int}, ...]}`.

- [ ] **Step 2: Run it** — `…/.venv/bin/python scripts/build_match_stats.py` → writes `mlb_match_stats.json`; print the 3 clusters + members so a human can sanity-check the archetypes.

- [ ] **Step 3: Write failing tests for matching**

```python
from mlb_match import match_pro

def test_match_returns_real_pro_name_and_pct():
    # a vector identical to a known pro should match that pro at ~100%
    import json; stats = json.load(open("mlb_match_stats.json"))
    pro = stats["pros"][0]
    res = match_pro(z_vector=pro["z"], stats=stats)
    assert res["slug"] == pro["slug"]
    assert res["name"]                      # real name surfaced
    assert 0 <= res["movement_match_pct"] <= 100
    assert res["movement_match_pct"] > 90
```

- [ ] **Step 4: Run, expect failure.**

- [ ] **Step 5: Implement `zscore` + `match_pro`** (assign nearest centroid, then nearest pro within that cluster; convert distance→% via `100 * exp(-dist / SCALE)` with SCALE tuned so an identical vector ≈100% and a far one ≈low).

```python
def zscore(vec, stats):
    return [(v - m) / (s or _EPS) for v, m, s in zip(vec, stats["means"], stats["stds"])]

def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

_MATCH_SCALE = 3.0
def match_pro(z_vector: list, stats: dict) -> dict:
    # nearest cluster, then nearest pro within it
    ci = min(range(len(stats["centroids"])),
             key=lambda i: _dist(z_vector, stats["centroids"][i]))
    in_cluster = [p for p in stats["pros"] if p["cluster"] == ci] or stats["pros"]
    best = min(in_cluster, key=lambda p: _dist(z_vector, p["z"]))
    pct = round(100.0 * math.exp(-_dist(z_vector, best["z"]) / _MATCH_SCALE))
    return {"slug": best["slug"], "name": best["name"],
            "movement_match_pct": max(0, min(100, pct)), "cluster": ci}
```

- [ ] **Step 6: Run, expect PASS. Step 7: Commit** — `git add scripts/build_match_stats.py mlb_match.py mlb_match_stats.json tests/test_mlb_match.py && git commit -m "feat(match): clustering + nearest-pro matching"`

---

## Task 5: `analyzer.py` — orchestrate Swing Score + Match into the result (TDD)

**Files:** Modify `analyzer.py` (the `analyze()` result assembly + `_synthesize_sequence_gaps`); Test `tests/test_analyzer_swing_score.py` (NEW)

Build the per-pillar dict (compliance from Task 1, confidence from existing `camera_view`/`view_diff`/`rotation_view_sensitive` + per-pillar visibility), aggregate to `swing_score`, resolve the locked Match via `reference_library` (Task 6), and add result fields: `swing_score`, `pillars`, `mlb_match` (`pro_name`, `slug`, `movement_match_pct`, `confident: bool`, `locked: bool`), `what_you_did_well`. Keep the old `score`/`reference` keys populated for backward-compat but make `swing_score` the headline.

- [ ] **Step 1: Write a failing integration test** that feeds a known fingerprint + age into `analyze()` and asserts `result["swing_score"]` is an int 0-100, `result["pillars"]` has the 4 keys each with `compliance`/`confidence`/`label`, `result["mlb_match"]["pro_name"]` is a real name, and `result["what_you_did_well"]` is a non-empty string. (Use an existing reference fingerprint from `references/` as the input so the pipeline is real.)

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement** — add an `age_bracket(age)` helper (8-10/11-12/13-14/15-17), a `_pillar_confidence(...)` helper reusing the existing view flags, a `_what_you_did_well(pillars)` (highest confident pillar → positive line; fallback to an effort/identity line tied to the Match), and assemble the new result fields. Pillar inputs come from the fingerprint: Sequence ← `sequence.sequencing_lag_ms`; Stability ← `head_movement_normalized_foot_plant_to_contact.total_drift_torso`; Timing ← `_timing_source(fp)`; Stride ← `knee_deg.re_extension` + stride direction.

- [ ] **Step 4: Run, expect PASS. Step 5: Commit** — `git commit -am "feat(analyzer): Swing Score + Match orchestration + result fields"`

---

## Task 6: `reference_library.py` — movement-based match + keep lock (TDD)

**Files:** Modify `reference_library.py` (`_match_score`/`find_best_match`); Test `tests/test_reference_library_match.py` (NEW)

- [ ] **Step 1: Failing test** — two synthetic fingerprints with clearly different movement vectors match different clusters/pros; handedness still mirror-normalized; `find_best_match` signature unchanged (returns a slug/ref).

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement** — inside `_match_score` (or a new `_movement_match`), compute `movement_vector` → `zscore` → `match_pro` (Task 4) and rank by movement distance instead of camera-view delta. Preserve `find_best_match`/`find_all_ranked` return shapes so `analyzer.py`/`app.py` callers are untouched. Lock: leave `players.locked_mlb_slug` handling in `app.py` as-is (compute once, replay) — verify by test that passing a locked slug bypasses re-matching.

- [ ] **Step 4: Run, expect PASS. Step 5: Commit** — `git commit -am "feat(match): reference_library uses movement match; lock preserved"`

---

## Task 7: `drills.py` — faults from pillars, pro-relative line, external cues, plain language (TDD)

**Files:** Modify `drills.py`; Test `tests/test_drills_from_pillars.py` (NEW)

- [ ] **Step 1: Failing tests** — (a) a `pillars` dict whose weakest *confident* pillar is `sequence` yields the `sequencing` drill category (not pro-diff); (b) a low-but-zero-confidence pillar is skipped; (c) each fix card contains exactly one pro-relative line using the locked pro name and the right pillar verb; (d) player-facing copy contains none of the banned jargon strings (`kinematic`, `X-Factor`, `re-extension`, `torso-relative`).

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement** — add `gaps_from_pillars(pillars) -> ranked list` (lowest confident compliance first) feeding the existing `classify_gap`/`build_drill_plan` via the pillar→category map (Sequence→sequencing[+hip_shoulder_separation/hip_rotation]; Stability→head_stability[+front_side_stability]; Timing→timing; Stride→knee_extension[+front_side_stability]). Drop `ref_name` from diagnosis copy. Add `pro_relative_line(pillar, pro_name)`. Rewrite the player-facing `_narrate_*` "what the fix feels like" lines to the external cues + swap jargon in `DRILL_DB.why_it_matters` to the plain-language forms (both from the spec tables).

- [ ] **Step 4: Run, expect PASS + run full suite. Step 5: Commit** — `git commit -am "feat(drills): pillar-sourced faults, external cues, plain language, pro-relative line"`

---

## Task 8: Report renderer + must-haves (`swing_report_dashboard_preview.py`) (TDD-snapshot)

**Files:** Modify `swing_report_dashboard_preview.py`; Test `tests/test_report_two_systems.py` (NEW, streamlit-stubbed snapshot like `tests/test_swing_report_power_sequence.py`)

- [ ] **Step 1: Failing snapshot tests** — render with a record carrying the new fields and assert, in order: (a) Match reveal contains the pro name; the movement-match % shows only when `mlb_match.confident` is true and is labeled "movement match" (never "/100"); (b) the reconciliation line text is present between Match and Score; (c) Swing Score card shows the 0-100 + the 4 pillar bars + the "what you did well" line BEFORE any fix; (d) a yellow/red confidence badge renders + the "Film it like this" block appears when any pillar confidence is low; (e) NO pro-similarity radar remains.

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement** — split `_build_hero` into `_build_match_reveal` + `_build_score`; add `_build_confidence_badge`, `_build_filming_guide`, the reconciliation caption, pillar bars from `result["pillars"]`, and thread `what_you_did_well`. Backward-compat: `swing_score = record.get("swing_score") or record.get("score")`; hide pillar bars if absent; Match card from legacy `reference` with `%` omitted when missing.

- [ ] **Step 4: Run, expect PASS. Step 5: Commit** — `git commit -am "feat(report): two-system layout, confidence badge, filming guide, what-you-did-well"`

---

## Task 9: End-to-end calibration + full suite + PR

**Files:** none (validation) + a short `docs/superpowers/specs/2026-05-23-swing-score-calibration.md` notes file.

- [ ] **Step 1:** Re-run the pro-vs-amateur cohort through `analyze()` (reuse the calibration harness pattern from `/tmp/calibrate_biomech.py`); confirm amateurs score lower on weak pillars and each held-out pro lands in a sensible cluster/match. Record the table in the notes file.
- [ ] **Step 2:** `…/.venv/bin/python -m pytest tests/ -q` — full suite green (fix any snapshot fallout in existing report tests).
- [ ] **Step 3:** Headless render check (reuse `scripts/visual_qa/render_swing_report_static.py` pattern) — eyeball the new report HTML for the two-system layout + badges.
- [ ] **Step 4: Commit + open PR** off `main`: `gh pr create --title "Swing Score + movement-based MLB Match (v1)" --body "…summary + risks from the spec…"`.

---

## Self-review notes
- **Spec coverage:** Score engine (T1-2), Match engine (T3-4-6), analyzer orchestration + result fields (T5), diagnosis/drills/cues/language (T7), report + must-haves (T8), calibration/tests/PR (T9). Age brackets, locked match, movement-% gating, "what you did well", confidence, filming guide all mapped. ✓
- **Deferred to v2 (explicitly NOT in this plan):** age **percentiles** (v1 is compliance-only), "The Climb" history view, pro-library expansion, you-vs-pro overlay polish.
- **Type consistency:** pillar dict shape `{compliance, confidence, label}`; `mlb_match` shape `{pro_name, slug, movement_match_pct, confident, locked, cluster}`; used identically across T5/T7/T8.
- **Known risk to verify in T3/T4:** exact fingerprint field names (`rotation_deg.peak_separation_t`, `separation_at_contact`, `knee_deg.*`) must exist on both player + reference JSONs; adjust accessors if not (the `movement_vector` uses defensive `.get`, so a missing field degrades rather than crashes, but the match quality depends on them — verify during T4 stats build).
