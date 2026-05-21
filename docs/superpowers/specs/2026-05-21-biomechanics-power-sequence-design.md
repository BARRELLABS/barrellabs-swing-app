# Biomechanics — "Power Sequence" Redesign

**Date:** 2026-05-21
**Status:** Draft, awaiting user approval
**Workstream:** Approach A — Story-first redesign (3-4 days est.)

## Problem

The current swing report shows **positions** (`hip at 45°`, `separation peak 38°`,
`launch→contact 138 ms`). Positions are endpoints — a player can't train to
"have 45° of hip rotation at contact." They train **mechanisms**: rotate
faster, lag the shoulders, stay closed at launch, drive off the back side.
The report is a position-snapshot dashboard wearing the costume of a
biomechanics analyzer.

Three concrete consequences from the audit:

1. **`shoulder_rotation` and `hip_accel` are computed every frame and thrown
   away.** The signals exist; the report doesn't use them.
2. **`peak_separation_t`** (timestamp of peak separation) **is in the
   fingerprint but never displayed.** This is the single best sequencing
   proxy already on disk and we bury it.
3. **The drill plan maps a low-separation gap to wall-touch hip-turners.**
   That's a range-of-motion drill. But a player with normal range whose
   problem is *timing* won't be helped — and the report can't currently
   distinguish those cases.

## Goal

Rebuild the swing report around a **Power Sequence** story: how the body
fires (pelvis → torso → contact), how fast, and whether the front side
stays closed. Add three new metrics that are derivable from existing
per-frame signals, surface them in a hero visualization at the top of the
report, and rebadge existing tiles with verb-based language. Extend the
drill plan with new categories that match the new metrics. Re-process the
20-clip MLB reference library so comparisons work for the new metrics.

## Non-goals

- **No new sensor inputs.** No bat tracking, no wearables — everything
  derived from existing MediaPipe pose output.
- **No video-level features.** No timeline scrubber, no frame-by-frame
  marker overlay (that's a separate visual workstream).
- **No mobile-first restructure.** Existing report already mobile-aware;
  this redesign preserves that responsiveness but doesn't reinvent it.
- **No automated MLB comp regeneration.** The 20 reference clips get
  re-processed once via `build_reference_library.py`; we don't add
  scrape-from-MLB automation.

## The 3 new metrics

Each one derives from per-frame signals already computed in
`detect_phases.py` — no new pose tracking required.

### M1. Sequencing lag (`sequencing_lag_ms`)

`detect_phases.py` already computes `hip_vel = smooth(np.gradient(hip_rotation), window=5)`. We add the shoulder analog with the same smoothing.

```python
# Search window — 200ms before load_start through 50ms after contact.
# Avoids post-contact follow-through dominating the shoulder peak.
search_lo = max(0, load_start - int(0.20 * fps))
search_hi = min(n_frames, contact + int(0.05 * fps))

shoulder_vel       = smooth(np.gradient(shoulder_rotation), window=5)
hip_peak_frame     = search_lo + int(np.argmax(np.abs(hip_vel[search_lo:search_hi])))
shoulder_peak_frame= search_lo + int(np.argmax(np.abs(shoulder_vel[search_lo:search_hi])))
sequencing_lag_ms  = (shoulder_peak_frame - hip_peak_frame) * 1000.0 / fps
```

- **What it tells us**: whether the kinematic chain fires bottom-up
  (good) or fires simultaneously / shoulders-first (bad — "casting", or
  "leak").
- **Good band**: 20–60 ms (pelvis leads, torso follows, both crisp).
- **Marginal**: 5–20 ms or 60–80 ms.
- **Poor**: ≤ 5 ms (simultaneous fire) or negative (shoulders lead — the
  classic "early shoulder fly-out" signature).

### M2. Peak hip angular velocity (`peak_hip_omega_deg_s`)

```python
# Reuses the search_lo / search_hi window from M1.
peak_hip_omega_deg_s = float(np.max(np.abs(hip_vel[search_lo:search_hi]))) * fps
```

- **What it tells us**: rotational power output. Not how much hips turn,
  but how *fast* they turn.
- **Good band**: ≥ 900 °/s (varsity / advanced HS), ≥ 1100 °/s (collegiate /
  pro).
- **Marginal**: 600–900 °/s.
- **Poor**: < 600 °/s.
- **Caveat**: 2D-width-ratio rotation is camera-angle sensitive. We'll
  display a `(profile)` / `(3/4)` suffix and use *separate* comparison
  bands per rotation method when comparing to MLB references.

### M3. Front-side stability — early fly-out percentage (`front_side_stability_pct`)

`detect_phases.py` already baselines `shoulder_rotation` against stance (line ~524: `sho_rel_2d = shoulder_rotation_unsigned - sho_baseline_2d`), so `shoulder_rotation[i]` is degrees of rotation past stance — no extra baseline subtraction needed.

```python
total_to_contact = shoulder_rotation[contact]            # baseline already subtracted
done_at_launch   = shoulder_rotation[launch]             # same
if abs(total_to_contact) < 5.0:        # negligible total rotation → can't characterize
    front_side_stability_pct = None
else:
    raw_pct = 100.0 * done_at_launch / total_to_contact
    front_side_stability_pct = float(max(-50.0, min(150.0, raw_pct)))   # clamped
```

- **What it tells us**: what percentage of shoulder rotation is *already
  complete* at launch (foot_plant). Lower = stayed closed longer = better.
- **Good band**: ≤ 25 % (front shoulder stayed closed through launch).
- **Marginal**: 25–45 %.
- **Poor**: ≥ 45 % ("front shoulder flying open early" — the most common
  amateur fault).
- **Edge case**: when `|total_to_contact|` ≤ 5°, return `None` and skip the
  tile — we can't characterize stability from a swing with almost no
  shoulder rotation. The Power Sequence section still renders the other
  two tiles; the third shows a "Not enough data — re-film from the side"
  placeholder.

## Architecture

### Signal-flow changes

```
detect_phases.py
   │
   ├──► phase_burst.py     (existing: burst detection)
   │
   ├──► biomech.py         (NEW — pure-numpy compute layer)
   │      ├── compute_sequencing_lag(...)
   │      ├── compute_peak_hip_omega(...)
   │      └── compute_front_side_stability(...)
   │
   └──► writes fingerprint JSON with new "sequence" block:
        {
          ...
          "sequence": {
            "sequencing_lag_ms":          32.4,
            "peak_hip_omega_deg_s":       947.2,
            "front_side_stability_pct":   24.1,
            "hip_peak_frame":             58,
            "shoulder_peak_frame":        61,
            "rating": {                # added by classifier
              "sequencing_lag":          "good",     // good/marginal/poor
              "peak_hip_omega":          "marginal",
              "front_side_stability":    "good"
            }
          }
        }

analyzer.py
   └──► loads fingerprint, generates Power Sequence narrative paragraph,
        passes to swing_report renderer.

drills.py
   ├── New gap categories: "sequencing", "rotational_speed", "front_side_stability"
   ├── New _CATEGORY_NARRATORS entries
   ├── New _CATEGORY_TITLES: "POWER SEQUENCE", "ROTATIONAL SPEED", "STAY CLOSED"
   ├── GOAL_CATEGORY_BOOSTS extended (especially "More power" → rotational_speed +3)
   └── Drill library: 3 new drill blocks (≥ 2 drills per new category)

compare.py
   └── Score new metric gaps with the existing similarity-percent logic,
       feeding the radar + drill plan.

swing_report_dashboard_preview.py
   └── Adds the Power Sequence section at the top + 3 new KPI tiles +
       verb-renames existing tiles + extends the metric-breakdown rows.

reference_library.py + build_reference_library.py
   └── Re-process the 20 MLB reference clips so each gets a "sequence"
       block. Re-process script is idempotent (skips refs that already
       have it).
```

### Why a separate `biomech.py` module

The compute functions are pure-numpy and trivially unit-testable.
`detect_phases.py` already pulls heavy mediapipe + opencv imports at module
load, which is why we needed `phase_burst.py` for Phase 4d. Same pattern
here. Compute layer in `biomech.py`; `detect_phases.py` imports and writes
results to the fingerprint.

## Report UI shape

```
┌─────────────────────────────────────────────────────────────────┐
│ EXISTING HEADER (back nav + breadcrumb + score ring + MLB comp) │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ § 01 · POWER SEQUENCE                          (eyebrow gold)   │
│                                                                 │
│ This is how your body fired.                                    │
│ (italic Instrument Serif headline, plain-language coach line)   │
│                                                                 │
│ ┌───── Power Sequence timeline visualization ─────────────────┐ │
│ │  LOAD     PLANT    HIP PEAK     SHO PEAK     CONTACT        │ │
│ │ ━━━━━━┯━━━━━━━━┯━━━━━━━━┯━━━━━━━━━┯━━━━━━━━┯━━━━━━━ time   │ │
│ │       │        │        │←  32ms →│        │                │ │
│ │       │        │        │   lag   │        │                │ │
│ └───────────────────────────────────────────────────────────── ┘ │
│                                                                 │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│ │ SEQUENCING   │ │ PEAK HIP     │ │ STAY CLOSED  │              │
│ │              │ │ SPEED        │ │              │              │
│ │ 32 ms ✓      │ │ 947 °/s      │ │ 24 % ✓       │              │
│ │              │ │ (marginal)   │ │              │              │
│ │ Pelvis-then- │ │ Trains with  │ │ Front side   │              │
│ │ torso, the   │ │ rotational   │ │ stayed shut  │              │
│ │ way pros do  │ │ med-ball     │ │ through plant│              │
│ └──────────────┘ └──────────────┘ └──────────────┘              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ § 02 · TOP PRIORITIES   (existing 3 fix cards — drill plan)     │
├─────────────────────────────────────────────────────────────────┤
│ § 03 · YOUR SWING DNA                                           │
│   - 5-axis radar (now driven partly by new metrics)             │
├─────────────────────────────────────────────────────────────────┤
│ § 04 · METRIC BREAKDOWN  (verb-renamed tiles)                   │
│   HIP TURN COMPLETION    (was: HIP ROTATION)                    │
│   TORQUE STORAGE         (was: HIP-SHOULDER SEPARATION)         │
│   LOWER-BODY DRIVE       (was: FRONT-SIDE FIRMNESS / knee)      │
│   HEAD QUIET             (was: HEAD STABILITY)                  │
│   TIMING & TEMPO         (unchanged)                            │
├─────────────────────────────────────────────────────────────────┤
│ § 05 · DRILL PLAN  (existing, now mapped from new categories)   │
│ § 06 · COMPARE / PROGRESS / NEXT SESSION  (existing)            │
└─────────────────────────────────────────────────────────────────┘
```

### Power Sequence visualization

A horizontal timeline rendered as inline SVG inside the Streamlit
`unsafe_allow_html` block (same pattern the rest of the editorial system
uses — no Plotly, no external libs). Markers:

- Faint vertical ticks at `load_start`, `foot_plant`, `launch`, `contact`
- Bold gold tick at `hip_peak_frame`
- Bold tick (red or bone) at `shoulder_peak_frame`
- Annotated arc showing the lag with `32 ms` label centered
- Color of the arc: gold if good band, bone if marginal, red if poor
- Below the timeline, a one-line plain verdict:
  `"Pelvis-then-torso, the way pros do it."` (good)
  `"Hips and shoulders fired together — power leak."` (poor)
  `"Shoulders fired before the hips — early fly-out."` (very poor)

Width is responsive; on mobile (< 720 px) the timeline becomes a vertical
stack with the same beats.

### Tile copy (plain-language, 12-year-old-and-parent-friendly)

| Tile | Value | Coach line |
|---|---|---|
| SEQUENCING | `32 ms` ✓ | "Pelvis-then-torso, the way pros do it." |
| SEQUENCING | `8 ms` ⚠ | "Hips and shoulders fired together — power leak." |
| SEQUENCING | `-12 ms` ✗ | "Shoulders fired before the hips. Top fix." |
| PEAK HIP SPEED | `947 °/s` | "Solid rotational power. Good HS / college-prep range." |
| PEAK HIP SPEED | `630 °/s` ⚠ | "Build hip speed — med-ball rotational throws." |
| STAY CLOSED | `24 %` ✓ | "Front side stayed shut through plant." |
| STAY CLOSED | `52 %` ✗ | "Front shoulder flew open early. #1 amateur fault." |

Each tile has a small `(?)` icon that opens a one-sentence tooltip
explaining the metric without jargon.

### Verb-rename map for existing tiles

| Old title | New title | Why |
|---|---|---|
| HIP ROTATION | HIP TURN COMPLETION | "Rotation" sounds like physics; "turn completion" is what coaches say |
| HIP-SHOULDER SEPARATION | TORQUE STORAGE | The actual mechanism — storing torque between hips and shoulders before release |
| FRONT-SIDE FIRMNESS / KNEE EXTENSION | LOWER-BODY DRIVE | "Drive" is what coaches yell |
| HEAD STABILITY | HEAD QUIET | What players are told ("quiet head") |
| TIMING & TEMPO | (unchanged) | Already verb-leaning |

## Drill plan extensions

Three new gap categories. Each maps to ≥ 2 drills. Drills live in the
existing drill-library structure (no new file format).

### `sequencing` (M1 → bad lag)

- **Connection ball / step-behind drill** — physically delays the hands so
  the player has to feel the hips lead.
- **Heavy bat hip-turner** — slows the swing down so the player can sense
  the chain firing in order.

### `rotational_speed` (M2 → low °/s)

- **Med-ball rotational throws** — direct rotational power output.
- **Sledgehammer to tire** — eccentric loading + rotational deceleration.

### `front_side_stability` (M3 → high fly-out %)

- **Closed-shoulder tee work** — partner / coach holds a noodle across
  player's front shoulder; player swings without dislodging it.
- **Pause-at-plant tee** — pause for 1 sec at foot plant before
  initiating, forcing the front side to set before firing.

### `GOAL_CATEGORY_BOOSTS` updates

```python
GOAL_CATEGORY_BOOSTS = {
    "More power": {
        "rotational_speed":          4,    # NEW — primary mapping
        "sequencing":                3,    # NEW — secondary
        "hip_rotation":              2,
        "hip_shoulder_separation":   2,
        "knee_extension":            1,
    },
    "Better contact": {
        "front_side_stability":      3,    # NEW — primary mapping
        "head_stability":            3,
        "sequencing":                2,    # NEW — secondary
        "timing":                    2,
    },
    "Better timing": {
        "sequencing":                4,    # NEW — exact match
        "timing":                    3,
        "head_stability":            1,
    },
    ...
}
```

## MLB reference library re-processing

`build_reference_library.py` already exists. Modify it to:

1. **Skip-if-present**: if a reference's fingerprint already has a
   `sequence` block, skip (idempotent re-runs).
2. **Re-process otherwise**: load the source video, run the updated
   `detect_phases.py`, write the new fingerprint.
3. **Print a summary**: how many refs were re-processed, how many
   skipped, how many failed.

Once done, every reference has the new `sequence` block. Comparisons
work automatically.

For development: the user can run this manually once
(`python build_reference_library.py --rebuild`) before the redesign goes
live. We **don't** auto-trigger from CI.

## Testing

### Unit tests (no mediapipe required — `biomech.py` is pure numpy)

- `test_sequencing_lag_good_pattern` — synthetic hip_vel and
  shoulder_rotation arrays where pelvis peak precedes shoulder peak by
  ~30 ms; assert lag matches.
- `test_sequencing_lag_simultaneous` — both peaks at the same frame;
  assert lag is 0 and rating is "poor".
- `test_sequencing_lag_reversed` — shoulder peak before hip peak; assert
  negative lag, "poor" rating.
- `test_sequencing_lag_search_window_ignores_followthrough` — large
  post-contact shoulder peak; assert it's not selected because it's
  outside the window.
- `test_peak_hip_omega_units` — known gradient signal; assert °/s matches.
- `test_front_side_stability_normal` — shoulder rotates 0° at plant,
  90° at contact; assert 0 %.
- `test_front_side_stability_fly_out` — shoulder already at 45° at
  plant, 90° at contact; assert 50 %.
- `test_front_side_stability_negligible_rotation` — total shoulder
  rotation < 5°; assert `None`.

### Snapshot test for swing-report HTML

- `test_swing_report_renders_power_sequence_section` — render the
  preview report with a synthetic fingerprint that includes the new
  `sequence` block; assert the section header, the three tile values,
  and the verdict line appear in the output HTML.

### Regression: existing tests must still pass

- `tests/test_phase_detector_v4.py` (44)
- `tests/test_burst_multi_swing.py` (12)
- `tests/test_player_settings_wiring.py`
- `tests/test_entitlements.py`

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| 2D-width-ratio fps gives unreliable `°/s` numbers across cameras | Display `(profile)` / `(3/4)` suffix; compare to method-matched MLB refs only; in the worst case, fall through to "your value" only |
| `peak_separation_t` style edge cases (very short clips, no foot_plant detected) | Compute layer returns `None`; renderer falls back to "Not enough data — re-film from the side" copy |
| MLB reference re-processing fails on one or two clips | Idempotent script logs failures; the failed refs are just dropped from comparison until re-processed manually |
| New drill categories without drills don't break the drill-plan generator | Defensive fallback in `drills.py` — if a category has no drills, skip it (current code does this for any missing category) |
| Verb-rename confuses existing users who memorized old titles | Hover-tip on each renamed tile shows the old name in small caps for the first 60 days; after that, drop |
| Compute is wrong because pose detection lost the front shoulder for a few frames | `biomech.py` uses median-of-neighbors fallback over short visibility dropouts; if dropout > 30 % of the window, return `None` |

## Effort estimate

| Phase | Work | Est. |
|---|---|---|
| 1 | `biomech.py` compute layer + unit tests | 0.5 day |
| 2 | `detect_phases.py` integration + fingerprint write | 0.5 day |
| 3 | `compare.py` + `drills.py` extensions | 0.5 day |
| 4 | New drill content (3 categories × 2 drills) + narrator paragraphs | 0.5 day |
| 5 | `swing_report_dashboard_preview.py` — Power Sequence section + viz + tile copy | 1 day |
| 6 | Verb-rename existing tiles + tooltip-on-hover for old-name reference | 0.25 day |
| 7 | MLB reference re-processing script + run | 0.25 day |
| 8 | Snapshot test + manual validation on 3-5 real swings | 0.5 day |
| **Total** | | **~4 days** |

## Open questions

None — all decisions made, all defaults chosen. The next step is user
review of this spec; if approved, the writing-plans skill turns this
into a sequenced implementation plan with commit boundaries.

---

## Appendix: file inventory

**Files created**:
- `biomech.py` (new pure-numpy compute layer)
- `tests/test_biomech.py` (new unit tests)
- `docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md` (this doc)

**Files modified**:
- `detect_phases.py` (import + call biomech.py, write `sequence` block to fingerprint)
- `analyzer.py` (load `sequence` block, generate narrative)
- `compare.py` (score new metric gaps)
- `drills.py` (3 new categories + narrators + titles + boost-map updates + drill content)
- `swing_report_dashboard_preview.py` (Power Sequence section + verb-renames)
- `reference_library.py` / `build_reference_library.py` (idempotent re-process)
- `tests/test_phase_detector_v4.py` (no changes; regression check)

**Files NOT touched**:
- `phase_detector_v4.py` (orthogonal — foot_plant selection, not biomech derivation)
- `phase_burst.py` (orthogonal)
- `swing_report.py` (legacy renderer; touched in the design-debt workstream, not here)
- `pricing.py`, `auth_screen.py`, `dashboard_v3.py` (out of scope)

**MLB reference files**: 20 JSON files in `references/` get a `sequence`
block appended via re-processing. No file-format change.
