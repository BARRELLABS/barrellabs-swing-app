# Power Sequence Biomechanics — Verification Findings

**Date:** 2026-05-23
**Status:** ⚠️ Verification FAILED — metrics do not yet measure what they claim
**Relates to:** `docs/superpowers/specs/2026-05-21-biomechanics-power-sequence-design.md`
**Harness:** `/tmp/calibrate_biomech.py` → `/tmp/calib_results.json`
**Branch:** `claude/biomech-verify`

## What we tested

Re-processed a curated cohort through `detect_phases.py` (with the `sequence`
block wired into the fingerprint) to see whether the good/marginal/poor
thresholds discriminate pros from amateurs:

- **PRO (9 usable):** mookie, juan_soto, freddie_freeman, kyle_schwarber,
  manny_machado, jose_ramirez, marcus_semien, corey_seager, gunnar_henderson
  (steven_kwan timed out at 180s and was dropped)
- **AMA (8):** IMG_8436, IMG_8605, IMG_8607, IMG_8608, IMG_9005, MarioTSwing,
  My_swing, swing

## The result — no discrimination

| metric | PRO min / **med** / max | AMA min / **med** / max | "good" band | verdict |
|---|---|---|---|---|
| sequencing_lag (ms) | −1031 / **−17** / 26 | −509 / **−133** / 0 | 20–60 | weak, noisy, frame-quantized |
| peak_hip_omega (°/s) | 53 / **131** / 182 | 95 / **212** / 312 | ≥ 900 | **INVERTED** (amateurs higher) + 5× too low |
| front_side_stability (%) | 53 / 84 / 150 | 73 / 126 / 150 | ≤ 25 | no separation, pegged at clamp ceiling |

Only **one** swing (mookie, 26 ms) landed in any "good" band, and the evidence
below shows that was luck, not signal.

## Root causes (with evidence)

### 1. Reference clips are multi-swing / un-trimmed — the peak search spans the wrong region
The lag metric finds the argmax of `|hip_vel|` and `|shoulder_vel|` inside
`[load_start−200ms, contact+50ms]`. That window only means anything on a single
isolated swing. The pro clips are long broadcast segments:

| clip | fps | hip_peak_frame | sho_peak_frame | lag |
|---|---|---|---|---|
| corey_seager | 57 | **840** | **781** | −1031 ms |
| jose_ramirez | 57 | 802 | 802 | 0 (degenerate) |
| juan_soto | 58 | 297 | 297 | 0 (degenerate) |
| kyle_schwarber | 58 | 564 | 557 | −120 ms |
| mookie | 39 | **3** | **4** | 26 ms (window-edge artifact) |
| freddie | 59 | **4** | **3** | −17 ms (window-edge artifact) |

Peaks 800 frames deep, or pinned to the first 3–4 frames, are not swing events.
Three amateurs cluster at exactly −133.37 ms (≈ −4 frames at 30 fps) and three
swings read exactly 0.0 — both signatures of frame-quantized, degenerate peak
picking, not measurement.

### 2. `peak_hip_omega` from a 2D width-proxy is anti-discriminative
`hip_rotation = width_to_rotation_deg(hip_width)` — rotation is *inferred from
the apparent 2D width of the hips* (foreshortening). `omega = max(|d/dt hip_rotation|) × fps`.
This is dominated by camera angle, distance, zoom, and pose jitter:
- Pro broadcast clips (often oblique, far) show small width change → low omega
  (mookie, a pro, is the **lowest** of all at 53 °/s).
- Amateur phone clips (face-on, close, jittery) show large width swings → high
  omega (up to 312 °/s).
- Absolute values (53–312 °/s) are ~5× below real pelvis angular velocity
  (≈ 700–1000+ °/s), so the ≥ 900 "good" band is effectively unreachable.

A 2D width signal cannot carry this metric.

### 3. `front_side_stability` pegs at the clamp ceiling
`flyout = 100 × shoulder_rotation[launch] / shoulder_rotation[contact]`, clamped
to [−50, 150]. It pegs at 150 whenever `shoulder_rotation` is not monotonically
increasing to the `contact` index (noise, a wrong contact frame, or a
non-cumulative signal), so the launch value exceeds the contact value. Most
clips peg → no separation.

## Conclusion

This is **not a threshold-tuning problem.** Re-fitting the bands to make pros
pass would be fitting noise and shipping fake biomechanics to paying parents.
**Do not tune the current thresholds, and do not build the timeline
visualization or MLB comparison on these values** — they would be built on sand.

## Options

- **A — Deep fix (proper).** Re-derive all three metrics from 3D world-landmark
  kinematics (pelvis & thorax angular velocity), add robust single-swing
  isolation (reuse the existing burst detector), sub-frame parabolic peak
  interpolation, then re-calibrate against a *curated single-swing* pro/amateur
  set. Only path that makes omega + flyout real. Multi-day.
- **B — Salvage `sequencing_lag` only.** Keep the one physically-grounded metric;
  fix it with burst-window peak search + sub-frame interpolation + a validity
  gate; drop/hide omega and flyout until 3D lands. Re-calibrate lag on curated
  clips. Ships one credible metric.
- **C — Shelve Power Sequence** behind a flag in the user-facing report until the
  pose pipeline supports it. Zero risk of shipping fake data.
- **D — Cheap probe first.** Re-test on curated clean single-swing clips before
  any code change, to separate "bad clips" from "bad metric design." ~30 min,
  decisive for choosing A/B/C.

## Recommendation

**D → B**, with **A** on the roadmap and the whole Power Sequence section
**gated** so nothing displays until a metric passes validity. Suppress (return
`None`) instead of clamping/pegging. Keep the existing rating thresholds
untouched until we have a valid signal to calibrate against.

## Note on launch safety

Nothing here is in front of paying users yet (the v4 detector is not promoted to
production and the app cannot go live without ToS/Privacy), so there is no active
harm — but the gate must be in place before any launch.
