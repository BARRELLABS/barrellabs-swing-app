# Phase 3 — Validation workflow

End-to-end tooling for comparing the v3 (legacy) and v4 (toe-tap-aware) phase
detectors against hand-labeled ground truth. Produces quantitative accuracy
metrics and a human-readable markdown report.

## Layout

```
validation/
├── manifest.json          ← list of swings + ground-truth labels (edit this)
├── results/               ← per-swing fingerprints (generated; gitignored ok)
└── reports/               ← timestamped markdown + JSON reports (generated)

scripts/validation/
├── manifest.py            ← schema + loader
├── batch.py               ← runs detect_phases.py on each video
├── compare.py             ← scores v3/v4 vs ground truth
├── report.py              ← writes the markdown report
└── run_validation.py      ← CLI entry point
```

## Quick start

```bash
# 0. Launch the visual labeling tool (frame-by-frame video review)
streamlit run scripts/validation/labeling_app.py

# 1. Validate the manifest schema
python -m scripts.validation.run_validation --check

# 2. Run the full pipeline: batch process + score + report
python -m scripts.validation.run_validation

# 3. Just score existing fingerprints (no batch processing)
python -m scripts.validation.run_validation --no-batch
```

Reports land in `validation/reports/<UTC-timestamp>-report.md` (human) and
`<UTC-timestamp>-summary.json` (machine).

## Labeling tool walkthrough

```bash
streamlit run scripts/validation/labeling_app.py
```

What you'll see:

- **Sidebar:** a `Labeled X / N` progress meter and a swing picker (defaults to
  showing only unlabeled swings; toggle to see everything).
- **Main panel:** the current frame, with the frame index + timestamp under it.
- **Navigation row:** −10 / −1 / type-frame / scrub-slider / +1 / +10 / End.
- **Capture buttons:** `📌 Set final_plant_frame = <current>` and matching
  buttons for `contact_frame` + `rotation_onset_frame`. These write to the
  form below.
- **Label form:** stride style radio, camera view radio, real-time checkbox,
  numeric inputs for the three frame markers, notes, labeled-by, labeled-at,
  and a **💾 SAVE LABELS** button that writes back to `validation/manifest.json`
  via an atomic rename (a crash mid-save can't corrupt the file).

### Labeling workflow per swing

1. Watch the swing once at normal speed to identify the stride pattern.
2. Choose `stride_style` (radio): `no_stride` / `standard_stride` / `toe_tap`
   / `leg_kick`.
3. Step backward from contact frame-by-frame (`−1`) until you find the moment
   the bat first touches the ball. Click `📌 Set contact_frame = <current>`.
4. Step backward again until the front foot has truly settled. **For toe-tap
   swings, scrub past the toe-tap touch — the final plant comes after the
   second lift.** Click `📌 Set final_plant_frame = <current>`.
5. (Optional) Mark `rotation_onset_frame` — the first frame where you can
   see the hips begin to fire.
6. Add a note if anything was ambiguous.
7. Click **💾 SAVE LABELS**. Confirmation balloons + green banner indicate the
   manifest was written.
8. Pick the next swing from the sidebar.

### What if a swing has no video yet?

The labeling tool only shows entries with a resolvable `video_path`. If you
need to add swings, edit `validation/manifest.json` directly:

```json
{
  "id": "my_swing_001",
  "video_path": "uploads_streamlit/my_swing_001.mp4",
  "handedness": "RIGHT",
  "ground_truth": {
    "stride_style": "toe_tap",
    "final_plant_frame": null,
    "contact_frame": null,
    "rotation_onset_frame": null,
    "camera_view": "profile",
    "real_time": true
  },
  "notes": "",
  "labeled_by": "",
  "labeled_at": ""
}
```

Then refresh the labeling tool — the new entry appears in the sidebar.

## Adding swings to the manifest

Open `validation/manifest.json` and append entries under `swings`:

```json
{
  "id": "your_swing_id",
  "video_path": "uploads/your_swing.mp4",     // optional, repo-relative
  "fingerprint_path": null,                   // optional, repo-relative
  "handedness": "RIGHT",                      // or "LEFT" or null (auto)
  "ground_truth": {
    "stride_style": "toe_tap",                // no_stride | standard_stride | toe_tap | leg_kick
    "final_plant_frame": 142,                 // **required** for scoring; null = unlabeled
    "contact_frame": 150,                     // **required** for scoring; null = unlabeled
    "rotation_onset_frame": null,             // optional
    "camera_view": "profile",                 // profile | three_quarter | front
    "real_time": true                         // false if slow-motion playback
  },
  "notes": "freeform — capture coach observations here",
  "labeled_by": "Coach Name",
  "labeled_at": "2026-05-20"
}
```

### Labeling protocol

To score the detectors, you need at minimum the **frame number of final foot
plant** and the **frame number of contact**, plus the **stride style**.

Recommended workflow:

1. Open the source video in a frame-stepping player (QuickTime supports
   single-frame nav via the arrow keys; VLC's `e` key advances one frame).
2. **Stride style:** classify the load pattern once per swing.
   - `no_stride`: front foot stays on the ground through contact
   - `standard_stride`: single lift → single plant
   - `toe_tap`: lift → brief touch → lift again → plant
   - `leg_kick`: large vertical lift (≥ ~50% of torso length)
3. **final_plant_frame:** the LAST frame where the front foot is on the ground
   *before rotation begins*. For toe-tap swings this is NOT the tap moment —
   it's the second/final plant.
4. **contact_frame:** the frame where the bat appears to meet the ball.
5. Record all three numbers in the manifest along with notes about anything
   ambiguous.

Until `final_plant_frame` is filled in, that swing will run through both
detectors but won't contribute to the accuracy metrics. Unlabeled swings
appear in the report with status `unlabeled`.

## What the report contains

The generated markdown report has these sections:

- **Executive summary** — headline accuracy numbers, v4-vs-v3 delta,
  head-to-head wins/losses, stride-style accuracy.
- **Per-detector metrics** — mean / median absolute error, % within ±3 / ±10
  frames, mean signed error (bias).
- **Stride-style classification** — confusion matrix and per-class accuracy
  for v4's phase_debug classifier.
- **v4 timing accuracy by stride style** — does v4 do better on toe-tap than
  no-stride? Per-class breakdown.
- **Per-swing detail** — one row per swing showing ground truth, v3/v4
  picks, errors, winner, v4 confidence.

## Cutover criteria for Phase 4

We should consider promoting v4 to the default detector when, across at least
30 labeled swings:

- **Stride-style accuracy ≥ 90%** overall, **≥ 80% per class**
- **v4 mean absolute foot-plant error < v3 mean absolute foot-plant error**
- **v4 wins or ties ≥ 75% of head-to-head comparisons**
- **No regression on `standard_stride`** — v4 must agree with v3 within ±3
  frames on swings where v3 was already correct

If those thresholds hold, Phase 4 (recalibration of scoring, drills, MLB
comparison) becomes the next workstream.

## Adding videos

The 17 entries in the seed manifest are the existing MLB reference clips.
Their fingerprints were produced by the broken v3 detector (no `analysis_debug`,
no `phases_frame_v4`), so until we have the source videos available **the
batch runner will reuse those v3-only fingerprints and v4 metrics will show
as `v4_unavailable`** in the report.

To get full v3-vs-v4 comparison on those references, set their `video_path`
to the source clip and re-run with `--no-batch=false` (the default).
