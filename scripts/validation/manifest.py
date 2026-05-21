"""
Validation manifest schema + loader.

A manifest is a JSON file at validation/manifest.json (default path,
configurable). It describes a set of swings with ground-truth labels
that downstream tooling uses to score the v3 and v4 detectors.

Schema:

    {
      "schema_version": "validation_v1",
      "swings": [
        {
          "id": "mookie_betts_001",                 # unique identifier
          "video_path": "uploads/mookie.mp4",       # optional, relative to repo
          "fingerprint_path": "results/m.json",     # optional, used if video missing
          "handedness": "RIGHT" | "LEFT" | null,    # null = auto-detect
          "ground_truth": {
            "stride_style": "no_stride|standard_stride|toe_tap|leg_kick",
            "final_plant_frame": 142,               # required (null = unlabeled)
            "contact_frame": 150,                   # required (null = unlabeled)
            "rotation_onset_frame": null,           # optional
            "camera_view": "profile|three_quarter|front",
            "real_time": true                       # false = slow-motion playback
          },
          "notes": "freeform string",
          "labeled_by": "Coach Name",
          "labeled_at": "2026-05-20"
        }
      ]
    }

The contract for `final_plant_frame`:
  - **null**     → swing is unlabeled. It will run through the detectors
                   but no accuracy metrics will be computed.
  - **int**      → ground-truth frame index from frame-by-frame review.
                   The validator scores both detectors against this number.

A manifest is loaded once at the start of a validation run; the loader
validates the schema and raises if anything is malformed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = "validation_v1"

VALID_STRIDE_STYLES = ("no_stride", "standard_stride", "toe_tap", "leg_kick")
VALID_CAMERA_VIEWS = ("profile", "three_quarter", "front")
VALID_HANDEDNESS = ("LEFT", "RIGHT", None)


@dataclass
class GroundTruth:
    """Hand-labeled per-swing facts. Populated by a hitting coach via
    frame-by-frame video review."""
    stride_style: str
    final_plant_frame: Optional[int]
    contact_frame: Optional[int]
    camera_view: str
    real_time: bool
    rotation_onset_frame: Optional[int] = None

    @property
    def is_labeled(self) -> bool:
        """True iff the swing has enough labels to score the detectors."""
        return (self.final_plant_frame is not None
                and self.contact_frame is not None)


@dataclass
class SwingEntry:
    """One row in the validation manifest."""
    id: str
    ground_truth: GroundTruth
    video_path: Optional[str] = None
    fingerprint_path: Optional[str] = None
    handedness: Optional[str] = None
    notes: str = ""
    labeled_by: str = ""
    labeled_at: str = ""

    def has_source(self) -> bool:
        """True iff there is at least one input (video or fingerprint) we can use."""
        return bool(self.video_path or self.fingerprint_path)


@dataclass
class Manifest:
    """Full manifest — schema version + list of swings."""
    schema_version: str
    swings: list[SwingEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


class ManifestError(ValueError):
    """Raised when a manifest fails schema validation."""


def _require(d: dict, key: str, context: str):
    if key not in d:
        raise ManifestError(f"missing required field '{key}' in {context}")
    return d[key]


def _validate_ground_truth(gt: dict, swing_id: str) -> GroundTruth:
    if not isinstance(gt, dict):
        raise ManifestError(f"swing {swing_id!r}: ground_truth must be an object")
    stride_style = _require(gt, "stride_style", f"swing {swing_id!r}.ground_truth")
    if stride_style not in VALID_STRIDE_STYLES:
        raise ManifestError(
            f"swing {swing_id!r}: stride_style must be one of {VALID_STRIDE_STYLES}, "
            f"got {stride_style!r}"
        )
    camera_view = _require(gt, "camera_view", f"swing {swing_id!r}.ground_truth")
    if camera_view not in VALID_CAMERA_VIEWS:
        raise ManifestError(
            f"swing {swing_id!r}: camera_view must be one of {VALID_CAMERA_VIEWS}, "
            f"got {camera_view!r}"
        )
    real_time = _require(gt, "real_time", f"swing {swing_id!r}.ground_truth")
    if not isinstance(real_time, bool):
        raise ManifestError(
            f"swing {swing_id!r}: real_time must be bool, got {type(real_time).__name__}"
        )

    final_plant_frame = gt.get("final_plant_frame")
    if final_plant_frame is not None and not isinstance(final_plant_frame, int):
        raise ManifestError(
            f"swing {swing_id!r}: final_plant_frame must be int or null"
        )
    contact_frame = gt.get("contact_frame")
    if contact_frame is not None and not isinstance(contact_frame, int):
        raise ManifestError(
            f"swing {swing_id!r}: contact_frame must be int or null"
        )
    rotation_onset_frame = gt.get("rotation_onset_frame")
    if (rotation_onset_frame is not None
            and not isinstance(rotation_onset_frame, int)):
        raise ManifestError(
            f"swing {swing_id!r}: rotation_onset_frame must be int or null"
        )

    return GroundTruth(
        stride_style=stride_style,
        final_plant_frame=final_plant_frame,
        contact_frame=contact_frame,
        rotation_onset_frame=rotation_onset_frame,
        camera_view=camera_view,
        real_time=real_time,
    )


def _validate_swing(s: dict, idx: int) -> SwingEntry:
    if not isinstance(s, dict):
        raise ManifestError(f"swings[{idx}] must be an object")
    swing_id = _require(s, "id", f"swings[{idx}]")
    if not isinstance(swing_id, str) or not swing_id.strip():
        raise ManifestError(f"swings[{idx}].id must be a non-empty string")

    handedness = s.get("handedness")
    if handedness not in VALID_HANDEDNESS:
        raise ManifestError(
            f"swing {swing_id!r}: handedness must be one of {VALID_HANDEDNESS}, "
            f"got {handedness!r}"
        )

    gt = _validate_ground_truth(
        _require(s, "ground_truth", f"swings[{idx}]"),
        swing_id=swing_id,
    )
    return SwingEntry(
        id=swing_id,
        ground_truth=gt,
        video_path=s.get("video_path"),
        fingerprint_path=s.get("fingerprint_path"),
        handedness=handedness,
        notes=s.get("notes", ""),
        labeled_by=s.get("labeled_by", ""),
        labeled_at=s.get("labeled_at", ""),
    )


def load_manifest(path: str | Path) -> Manifest:
    """Load and validate a manifest. Raises ManifestError on schema problems."""
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"manifest file not found: {path}")
    with open(path) as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestError(f"manifest is not valid JSON: {e}") from e
    if not isinstance(raw, dict):
        raise ManifestError("manifest root must be an object")

    schema_version = _require(raw, "schema_version", "manifest root")
    if schema_version != SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version {schema_version!r}; expected {SCHEMA_VERSION!r}"
        )

    swings_raw = _require(raw, "swings", "manifest root")
    if not isinstance(swings_raw, list):
        raise ManifestError("manifest.swings must be a list")

    swings: list[SwingEntry] = []
    seen_ids: set[str] = set()
    for idx, s in enumerate(swings_raw):
        entry = _validate_swing(s, idx)
        if entry.id in seen_ids:
            raise ManifestError(f"duplicate swing id {entry.id!r}")
        seen_ids.add(entry.id)
        swings.append(entry)

    return Manifest(schema_version=schema_version, swings=swings)


def write_manifest(manifest: Manifest, path: str | Path) -> None:
    """Serialize a manifest to JSON."""
    out = {
        "schema_version": manifest.schema_version,
        "swings": [asdict(s) for s in manifest.swings],
    }
    Path(path).write_text(json.dumps(out, indent=2) + "\n")
