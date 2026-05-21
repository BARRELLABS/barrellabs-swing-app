"""
Generate a SAMPLE validation report from synthetic fingerprints.

Produces `validation/reports/SAMPLE-report.md` and its JSON siblings so
the user can see exactly what a labeled validation run looks like
before they invest in hand-labeling real videos.

Run with:
    python -m scripts.validation.demo_report

The synthetic data is constructed to be plausible — v4 reliably wins
on toe_tap and leg_kick, agrees with v3 on standard_stride, and the
stride-style classifier is mostly correct with one deliberate miss
so the confusion matrix is non-trivial.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validation.compare import evaluate_manifest, summary_as_dict, as_dicts
from scripts.validation.manifest import (
    Manifest, SwingEntry, GroundTruth, SCHEMA_VERSION,
)
from scripts.validation.report import render


@dataclass
class _Synth:
    id: str
    stride_style: str
    gt_plant: int
    gt_contact: int
    v3_pick: int
    v4_pick: int
    v4_stride_pred: str
    v4_conf: float
    fps: float = 60.0


def _fingerprint(s: _Synth) -> dict:
    return {
        "video": f"{s.id}.mp4",
        "handedness": "RIGHT",
        "rotation_method": "2d_width_ratio",
        "fps": s.fps,
        "phases_frame": {
            "load_start": max(0, s.v3_pick - 30),
            "foot_plant": s.v3_pick,
            "launch": s.gt_contact - 10,
            "contact": s.gt_contact,
            "peak_rotation": s.gt_contact + 10,
            "finish": s.gt_contact + 30,
        },
        "phases_t": {
            "load_start": max(0, s.v3_pick - 30) / s.fps,
            "foot_plant": s.v3_pick / s.fps,
            "launch": (s.gt_contact - 10) / s.fps,
            "contact": s.gt_contact / s.fps,
            "peak_rotation": (s.gt_contact + 10) / s.fps,
            "finish": (s.gt_contact + 30) / s.fps,
        },
        "phases_frame_v4": {
            "load_start": max(0, s.v4_pick - 30),
            "foot_plant": s.v4_pick,
            "launch": s.gt_contact - 10,
            "contact": s.gt_contact,
            "peak_rotation": s.gt_contact + 10,
            "finish": s.gt_contact + 30,
        },
        "phases_t_v4": {
            "load_start": max(0, s.v4_pick - 30) / s.fps,
            "foot_plant": s.v4_pick / s.fps,
            "launch": (s.gt_contact - 10) / s.fps,
            "contact": s.gt_contact / s.fps,
            "peak_rotation": (s.gt_contact + 10) / s.fps,
            "finish": (s.gt_contact + 30) / s.fps,
        },
        "detector_v4": {
            "phases": {},  # filled in synthetic — comparator only reads
                            # confidence + fallback_to_v3
            "confidence": s.v4_conf,
            "fallback_to_v3": False,
            "selection_reason": "synthetic demo",
        },
        "analysis_debug": {
            "schema_version": "phase_debug_v1",
            "stride_style": s.v4_stride_pred,
        },
    }


# Constructed dataset:
#   - 3 toe_tap: v3 lands on the tap (~30f early); v4 lands on real plant ±1-2f
#   - 2 leg_kick: v3 misses by ~10f; v4 lands within 2f
#   - 4 standard_stride: v3 and v4 agree within 1-2f (no toe-tap bug)
#   - 1 no_stride: both detectors land within 1f
#   - 1 deliberate stride-style mis-classification (toe_tap mistaken as
#     standard_stride) to give the confusion matrix something interesting
_DEMO = [
    _Synth("toe_tap_001",      "toe_tap",         150, 165, 122, 151, "toe_tap",         0.88),
    _Synth("toe_tap_002",      "toe_tap",         142, 158, 118, 144, "toe_tap",         0.84),
    _Synth("toe_tap_003",      "toe_tap",         160, 175, 130, 162, "toe_tap",         0.82),
    _Synth("leg_kick_001",     "leg_kick",        148, 165, 138, 150, "leg_kick",        0.81),
    _Synth("leg_kick_002",     "leg_kick",        155, 170, 142, 154, "leg_kick",        0.78),
    _Synth("standard_001",     "standard_stride", 138, 152, 137, 138, "standard_stride", 0.86),
    _Synth("standard_002",     "standard_stride", 145, 160, 146, 145, "standard_stride", 0.84),
    _Synth("standard_003",     "standard_stride", 130, 145, 131, 131, "standard_stride", 0.85),
    _Synth("standard_004",     "standard_stride", 152, 168, 151, 152, "standard_stride", 0.87),
    _Synth("no_stride_001",    "no_stride",       145, 161, 144, 145, "no_stride",       0.80),
    # Deliberate stride-style miss — toe-tap clip whose tap was too brief
    # for the classifier (drops below 80ms cutoff) so v4 labels it as
    # standard_stride. v4 still picks the right foot_plant frame.
    _Synth("toe_tap_004_miss", "toe_tap",         165, 180, 138, 166, "standard_stride", 0.62),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        fp_dir = Path(td)
        for s in _DEMO:
            (fp_dir / f"{s.id}_fingerprint.json").write_text(
                json.dumps(_fingerprint(s), indent=2)
            )
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            swings=[
                SwingEntry(
                    id=s.id,
                    ground_truth=GroundTruth(
                        stride_style=s.stride_style,
                        final_plant_frame=s.gt_plant,
                        contact_frame=s.gt_contact,
                        camera_view="profile",
                        real_time=True,
                    ),
                    notes="synthetic demo data",
                )
                for s in _DEMO
            ],
        )
        rows, summary = evaluate_manifest(manifest, fingerprint_dir=fp_dir)

    out_dir = PROJECT_ROOT / "validation" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "SAMPLE-report.md"
    sum_path = out_dir / "SAMPLE-summary.json"
    rows_path = out_dir / "SAMPLE-rows.json"
    md_path.write_text(
        render(rows, summary,
               manifest_path="(synthetic demo)",
               generated_at="(SAMPLE — synthetic data)") + "\n"
    )
    sum_path.write_text(json.dumps(summary_as_dict(summary), indent=2) + "\n")
    rows_path.write_text(json.dumps(as_dicts(rows), indent=2) + "\n")

    print(f"Wrote SAMPLE report:  {md_path}")
    print(f"Wrote SAMPLE summary: {sum_path}")
    print(f"Wrote SAMPLE rows:    {rows_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
