"""
Unit tests for the Phase 3 validation tooling.

Verifies that:
  - The manifest loader validates schema + rejects malformed entries
  - The comparator scores swings correctly against ground truth
  - Skipped-swing statuses are reported (unlabeled, missing fingerprint, etc.)
  - Aggregate metrics (mean / median error, head-to-head, confusion matrix)
    are computed correctly
  - The markdown report renders without exceptions and includes the
    expected sections
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validation.manifest import (
    Manifest, SwingEntry, GroundTruth,
    load_manifest, write_manifest, ManifestError, SCHEMA_VERSION,
)
from scripts.validation.compare import (
    evaluate_swing, evaluate_manifest, summarize,
    SwingResult, summary_as_dict, as_dicts,
)
from scripts.validation.report import render


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_fingerprint(
    *,
    v3_foot_plant: int,
    v4_foot_plant: int | None,
    stride_style: str | None = None,
    v4_confidence: float = 0.85,
    v4_fallback: bool = False,
    fps: float = 60.0,
) -> dict:
    """Build a synthetic fingerprint shaped like what detect_phases.py emits."""
    fp = {
        "video": "synth.mp4",
        "handedness": "RIGHT",
        "rotation_method": "2d_width_ratio",
        "fps": fps,
        "phases_frame": {
            "load_start": 50, "foot_plant": v3_foot_plant, "launch": 90,
            "contact": 100, "peak_rotation": 110, "finish": 120,
        },
        "phases_t": {
            "load_start": 50 / fps,
            "foot_plant": v3_foot_plant / fps,
            "launch": 90 / fps,
            "contact": 100 / fps,
            "peak_rotation": 110 / fps,
            "finish": 120 / fps,
        },
    }
    if stride_style is not None:
        fp["analysis_debug"] = {
            "schema_version": "phase_debug_v1",
            "stride_style": stride_style,
        }
    if v4_foot_plant is not None:
        fp["phases_frame_v4"] = {
            "load_start": 60, "foot_plant": v4_foot_plant, "launch": 90,
            "contact": 100, "peak_rotation": 110, "finish": 120,
        }
        fp["phases_t_v4"] = {
            k: v / fps for k, v in fp["phases_frame_v4"].items()
        }
        fp["detector_v4"] = {
            "phases": fp["phases_frame_v4"],
            "confidence": v4_confidence,
            "fallback_to_v3": v4_fallback,
            "selection_reason": "synthetic",
        }
    return fp


def _make_entry(
    *,
    swing_id: str,
    stride_style: str,
    final_plant: int | None,
    contact: int | None = 100,
) -> SwingEntry:
    return SwingEntry(
        id=swing_id,
        ground_truth=GroundTruth(
            stride_style=stride_style,
            final_plant_frame=final_plant,
            contact_frame=contact,
            camera_view="profile",
            real_time=True,
        ),
    )


# ---------------------------------------------------------------------------
# Manifest loader
# ---------------------------------------------------------------------------


class TestManifestLoader:
    def test_loads_valid_manifest(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [{
                "id": "swing_1",
                "handedness": "RIGHT",
                "ground_truth": {
                    "stride_style": "toe_tap",
                    "final_plant_frame": 142,
                    "contact_frame": 150,
                    "camera_view": "profile",
                    "real_time": True,
                },
            }],
        }))
        m = load_manifest(path)
        assert m.schema_version == SCHEMA_VERSION
        assert len(m.swings) == 1
        assert m.swings[0].id == "swing_1"
        assert m.swings[0].ground_truth.is_labeled is True

    def test_rejects_missing_schema_version(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"swings": []}))
        with pytest.raises(ManifestError, match="schema_version"):
            load_manifest(path)

    def test_rejects_wrong_schema_version(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({"schema_version": "v9000", "swings": []}))
        with pytest.raises(ManifestError, match="unsupported schema_version"):
            load_manifest(path)

    def test_rejects_invalid_stride_style(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [{
                "id": "x",
                "ground_truth": {
                    "stride_style": "nonsense",
                    "final_plant_frame": 1,
                    "contact_frame": 2,
                    "camera_view": "profile",
                    "real_time": True,
                },
            }],
        }))
        with pytest.raises(ManifestError, match="stride_style"):
            load_manifest(path)

    def test_rejects_invalid_camera_view(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [{
                "id": "x",
                "ground_truth": {
                    "stride_style": "toe_tap",
                    "final_plant_frame": 1,
                    "contact_frame": 2,
                    "camera_view": "moon",
                    "real_time": True,
                },
            }],
        }))
        with pytest.raises(ManifestError, match="camera_view"):
            load_manifest(path)

    def test_rejects_invalid_handedness(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [{
                "id": "x",
                "handedness": "SIDEWAYS",
                "ground_truth": {
                    "stride_style": "toe_tap",
                    "final_plant_frame": 1,
                    "contact_frame": 2,
                    "camera_view": "profile",
                    "real_time": True,
                },
            }],
        }))
        with pytest.raises(ManifestError, match="handedness"):
            load_manifest(path)

    def test_rejects_duplicate_ids(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [
                {"id": "dup", "ground_truth": {
                    "stride_style": "toe_tap", "final_plant_frame": 1,
                    "contact_frame": 2, "camera_view": "profile",
                    "real_time": True}},
                {"id": "dup", "ground_truth": {
                    "stride_style": "toe_tap", "final_plant_frame": 1,
                    "contact_frame": 2, "camera_view": "profile",
                    "real_time": True}},
            ],
        }))
        with pytest.raises(ManifestError, match="duplicate"):
            load_manifest(path)

    def test_null_final_plant_marked_unlabeled(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "swings": [{
                "id": "x",
                "ground_truth": {
                    "stride_style": "toe_tap",
                    "final_plant_frame": None,
                    "contact_frame": None,
                    "camera_view": "profile",
                    "real_time": True,
                },
            }],
        }))
        m = load_manifest(path)
        assert m.swings[0].ground_truth.is_labeled is False

    def test_real_manifest_loads(self):
        """Smoke test: the seeded manifest.json in the repo loads cleanly."""
        m = load_manifest(PROJECT_ROOT / "validation" / "manifest.json")
        assert len(m.swings) >= 5
        # Verify each swing has a usable ground_truth.stride_style
        for s in m.swings:
            assert s.ground_truth.stride_style in (
                "no_stride", "standard_stride", "toe_tap", "leg_kick"
            )

    def test_roundtrip_write_then_read(self, tmp_path):
        original = Manifest(
            schema_version=SCHEMA_VERSION,
            swings=[_make_entry(
                swing_id="rt",
                stride_style="toe_tap",
                final_plant=100,
                contact=110,
            )],
        )
        path = tmp_path / "m.json"
        write_manifest(original, path)
        loaded = load_manifest(path)
        assert loaded.swings[0].id == "rt"


# ---------------------------------------------------------------------------
# Per-swing scoring
# ---------------------------------------------------------------------------


class TestEvaluateSwing:
    def test_scored_when_labeled_and_both_detectors_present(self):
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=150, contact=170)
        fp = _make_fingerprint(
            v3_foot_plant=125, v4_foot_plant=152,
            stride_style="toe_tap", v4_confidence=0.88,
        )
        result = evaluate_swing(entry, fp)
        assert result.status == "scored"
        # v3 error: 125 - 150 = -25 (picks 25 frames too early)
        assert result.v3_error_frames == -25
        # v4 error: 152 - 150 = +2 (picks 2 frames too late)
        assert result.v4_error_frames == 2
        # v3-v4 delta
        assert result.v3_v4_delta_frames == 27
        assert result.stride_style_correct is True
        assert result.winner == "v4"
        assert result.v4_confidence == 0.88

    def test_unlabeled_swing_still_emits_v3_v4_delta(self):
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=None, contact=None)
        fp = _make_fingerprint(
            v3_foot_plant=125, v4_foot_plant=152, stride_style="toe_tap",
        )
        result = evaluate_swing(entry, fp)
        assert result.status == "unlabeled"
        assert result.v3_v4_delta_frames == 27
        # Error metrics not computed
        assert result.v3_error_frames is None
        assert result.v4_error_frames is None

    def test_missing_fingerprint_marked_skipped(self):
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=150)
        result = evaluate_swing(entry, fingerprint=None)
        assert result.status == "missing_fingerprint"

    def test_v3_only_fingerprint(self):
        """When DETECTOR_V4 wasn't enabled — only v3 phases present."""
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=150)
        fp = _make_fingerprint(v3_foot_plant=125, v4_foot_plant=None)
        result = evaluate_swing(entry, fp)
        assert result.status == "v4_unavailable"
        # v3 error still computed
        assert result.v3_error_frames == -25
        assert result.v4_error_frames is None

    def test_winner_tie(self):
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=150)
        fp = _make_fingerprint(
            v3_foot_plant=148, v4_foot_plant=152,
            stride_style="toe_tap",
        )
        # Both detectors are 2 frames off in opposite directions
        result = evaluate_swing(entry, fp)
        assert result.winner == "tie"

    def test_load_error_status(self):
        entry = _make_entry(swing_id="s", stride_style="toe_tap",
                             final_plant=150)
        result = evaluate_swing(entry, fingerprint=None, load_error="boom")
        assert result.status == "load_error"
        assert "boom" in result.notes


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


class TestSummarize:
    def test_empty_input(self):
        s = summarize([])
        assert s.n_total == 0
        assert s.v3.n == 0
        assert s.v4.n == 0
        assert s.head_to_head.n == 0

    def test_aggregates_correctly(self):
        rows = [
            SwingResult(
                id="a", status="scored",
                gt_stride_style="toe_tap",
                gt_final_plant=150, gt_contact=170,
                v3_foot_plant=125, v4_foot_plant=152,
                v4_stride_style="toe_tap",
                fps=60.0,
                v3_error_frames=-25, v4_error_frames=2,
                v3_error_ms=-25/60*1000, v4_error_ms=2/60*1000,
                v3_v4_delta_frames=27,
                stride_style_correct=True,
                winner="v4", v4_confidence=0.88,
            ),
            SwingResult(
                id="b", status="scored",
                gt_stride_style="standard_stride",
                gt_final_plant=100, gt_contact=120,
                v3_foot_plant=99, v4_foot_plant=99,
                v4_stride_style="standard_stride",
                fps=60.0,
                v3_error_frames=-1, v4_error_frames=-1,
                v3_error_ms=-1/60*1000, v4_error_ms=-1/60*1000,
                v3_v4_delta_frames=0,
                stride_style_correct=True,
                winner="tie", v4_confidence=0.85,
            ),
            SwingResult(
                id="c", status="missing_fingerprint",
                gt_stride_style="leg_kick",
            ),
        ]
        s = summarize(rows)
        assert s.n_total == 3
        assert s.n_scored == 2
        assert s.skipped_by_reason == {"missing_fingerprint": 1}
        # v3 mean absolute = mean(|-25|, |-1|) = 13
        assert s.v3.mean_abs_error_frames == 13.0
        # v4 mean absolute = mean(|2|, |-1|) = 1.5
        assert s.v4.mean_abs_error_frames == 1.5
        # v4 wins 1, ties 1, loses 0
        assert s.head_to_head.v4_better == 1
        assert s.head_to_head.tie == 1
        assert s.head_to_head.v3_better == 0
        assert s.head_to_head.pct_v4_better == 0.5
        # Stride style: 2/2 correct
        assert s.stride_style.n_evaluated == 2
        assert s.stride_style.overall_accuracy == 1.0

    def test_within_tolerance_thresholds(self):
        rows = [
            # 2 frames off — within ±3 ✓
            SwingResult(id="a", status="scored", gt_stride_style="toe_tap",
                         gt_final_plant=100,
                         v3_foot_plant=98, v4_foot_plant=100,
                         v3_error_frames=-2, v4_error_frames=0,
                         winner="v4", fps=60.0),
            # 5 frames off — within ±10 ✓, NOT within ±3
            SwingResult(id="b", status="scored", gt_stride_style="toe_tap",
                         gt_final_plant=100,
                         v3_foot_plant=95, v4_foot_plant=100,
                         v3_error_frames=-5, v4_error_frames=0,
                         winner="v4", fps=60.0),
            # 20 frames off — NOT within either
            SwingResult(id="c", status="scored", gt_stride_style="toe_tap",
                         gt_final_plant=100,
                         v3_foot_plant=80, v4_foot_plant=100,
                         v3_error_frames=-20, v4_error_frames=0,
                         winner="v4", fps=60.0),
        ]
        s = summarize(rows)
        # v3: 1/3 within tight, 2/3 within loose
        assert s.v3.pct_within_tight == pytest.approx(1/3)
        assert s.v3.pct_within_loose == pytest.approx(2/3)
        # v4: 3/3 within both
        assert s.v4.pct_within_tight == 1.0
        assert s.v4.pct_within_loose == 1.0


# ---------------------------------------------------------------------------
# evaluate_manifest end-to-end
# ---------------------------------------------------------------------------


class TestEvaluateManifest:
    def test_end_to_end_with_synthetic_fingerprints(self, tmp_path):
        # Write 3 swings of fingerprints to a directory
        fp_dir = tmp_path / "fps"
        fp_dir.mkdir()
        (fp_dir / "toe_tap_a_fingerprint.json").write_text(json.dumps(
            _make_fingerprint(v3_foot_plant=125, v4_foot_plant=152,
                              stride_style="toe_tap")
        ))
        (fp_dir / "standard_b_fingerprint.json").write_text(json.dumps(
            _make_fingerprint(v3_foot_plant=99, v4_foot_plant=99,
                              stride_style="standard_stride")
        ))
        (fp_dir / "leg_kick_c_fingerprint.json").write_text(json.dumps(
            _make_fingerprint(v3_foot_plant=110, v4_foot_plant=108,
                              stride_style="leg_kick")
        ))

        manifest = Manifest(schema_version=SCHEMA_VERSION, swings=[
            _make_entry(swing_id="toe_tap_a", stride_style="toe_tap",
                         final_plant=150),
            _make_entry(swing_id="standard_b", stride_style="standard_stride",
                         final_plant=100),
            _make_entry(swing_id="leg_kick_c", stride_style="leg_kick",
                         final_plant=110),
        ])

        rows, summary = evaluate_manifest(manifest, fingerprint_dir=fp_dir)
        assert summary.n_scored == 3
        assert summary.head_to_head.v4_better >= 1  # toe-tap and leg-kick favor v4
        assert summary.stride_style.overall_accuracy == 1.0


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


class TestReportRenderer:
    def test_renders_nonempty_markdown(self):
        rows = [
            SwingResult(
                id="a", status="scored",
                gt_stride_style="toe_tap",
                gt_final_plant=150, gt_contact=170,
                v3_foot_plant=125, v4_foot_plant=152,
                v4_stride_style="toe_tap",
                fps=60.0,
                v3_error_frames=-25, v4_error_frames=2,
                v3_error_ms=-25/60*1000, v4_error_ms=2/60*1000,
                v3_v4_delta_frames=27,
                stride_style_correct=True,
                winner="v4", v4_confidence=0.88,
            ),
        ]
        summary = summarize(rows)
        md = render(rows, summary, manifest_path="m.json",
                    generated_at="2026-01-01 00:00:00 UTC")
        assert "Phase 3 validation report" in md
        assert "Executive summary" in md
        assert "v3" in md.lower()
        assert "v4" in md.lower()
        assert "Per-swing detail" in md
        # The toe-tap entry should appear in the per-swing table
        assert "toe_tap" in md
        # Generated timestamp included
        assert "2026-01-01" in md

    def test_renders_when_only_unlabeled_swings(self):
        """Report shouldn't crash if every swing is unlabeled."""
        rows = [
            SwingResult(id="x", status="unlabeled",
                         gt_stride_style="toe_tap"),
            SwingResult(id="y", status="missing_fingerprint",
                         gt_stride_style="leg_kick"),
        ]
        summary = summarize(rows)
        md = render(rows, summary)
        assert "Phase 3 validation report" in md
        assert "no scored swings" in md

    def test_handles_empty_input(self):
        rows: list[SwingResult] = []
        summary = summarize(rows)
        md = render(rows, summary)
        assert "Phase 3 validation report" in md


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_summary_serializes_to_json(self):
        rows = [
            SwingResult(
                id="a", status="scored",
                gt_stride_style="toe_tap",
                gt_final_plant=100, gt_contact=110,
                v3_foot_plant=80, v4_foot_plant=98,
                v4_stride_style="toe_tap",
                fps=60.0,
                v3_error_frames=-20, v4_error_frames=-2,
                v3_v4_delta_frames=18, stride_style_correct=True,
                winner="v4",
            ),
        ]
        summary = summarize(rows)
        d = summary_as_dict(summary)
        # Must be json.dumps-able without errors
        s = json.dumps(d, indent=2)
        assert "v3" in s and "v4" in s and "stride_style" in s

    def test_rows_serialize_to_json(self):
        rows = [
            SwingResult(id="a", status="scored", gt_stride_style="toe_tap",
                         v3_foot_plant=80),
        ]
        d = as_dicts(rows)
        s = json.dumps(d, indent=2)
        assert "toe_tap" in s


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
