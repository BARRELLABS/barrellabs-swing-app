"""
Smoke tests for the Streamlit labeling tool.

Streamlit modules can't be fully unit-tested without a live server, but we
can catch import errors, syntax errors, and verify the helper functions
that don't depend on st.session_state.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_labeling_module():
    """Import labeling_app.py without executing its Streamlit body.

    The module is intended to be run with `streamlit run …`, which sets
    up a Streamlit script-run context. Importing it bare would execute
    every st.* call against a stub context. To smoke-test it we load the
    source, parse it, and verify the helper definitions resolve.
    """
    spec = importlib.util.spec_from_file_location(
        "labeling_app",
        PROJECT_ROOT / "scripts" / "validation" / "labeling_app.py",
    )
    return spec  # we don't actually exec — see test_parses below


def test_module_parses():
    """labeling_app.py must be syntactically valid Python."""
    import ast
    src = (PROJECT_ROOT / "scripts" / "validation" / "labeling_app.py").read_text()
    ast.parse(src)


def test_module_imports_required_symbols():
    """The module references symbols that must exist in our own packages."""
    src = (PROJECT_ROOT / "scripts" / "validation" / "labeling_app.py").read_text()
    # Symbols we depend on from scripts.validation.manifest
    for required in (
        "load_manifest", "write_manifest", "Manifest", "SwingEntry",
        "GroundTruth", "VALID_STRIDE_STYLES", "VALID_CAMERA_VIEWS",
    ):
        assert required in src, f"labeling_app references missing symbol: {required}"


def test_slugify_normalizes_filenames():
    """slugify() must produce safe, deterministic swing_ids from arbitrary input."""
    from scripts.validation._text_utils import slugify
    assert slugify("Mookie Betts!") == "mookie_betts"
    assert slugify("  ---HELLO---  ") == "hello"
    assert slugify("swing 001.mp4") == "swing_001_mp4"
    assert slugify("/path/with/slashes") == "path_with_slashes"
    assert slugify("") == "swing"           # fallback for empty input
    assert slugify("---") == "swing"         # fallback for all-separators


def test_auto_discovery_imports_new_videos(tmp_path):
    """Drop a video file → auto_import_videos must add a fresh manifest entry."""
    from scripts.validation.manifest import (
        Manifest, SCHEMA_VERSION, SwingEntry, GroundTruth,
    )
    from scripts.validation._video_discovery import (
        discover_videos, auto_import_videos,
    )
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "user_clip_42.mp4").write_bytes(b"\x00" * 256)

    discovered = discover_videos([videos_dir])
    assert len(discovered) == 1
    assert discovered[0].name == "user_clip_42.mp4"

    manifest = Manifest(schema_version=SCHEMA_VERSION, swings=[])
    n_added = auto_import_videos(manifest, [videos_dir], project_root=tmp_path)
    assert n_added == 1
    assert len(manifest.swings) == 1

    entry = manifest.swings[0]
    assert entry.id == "user_clip_42"
    assert entry.video_path == "videos/user_clip_42.mp4"
    assert entry.ground_truth.stride_style == "standard_stride"
    assert entry.ground_truth.final_plant_frame is None
    assert entry.ground_truth.contact_frame is None
    assert "auto-imported" in entry.notes


def test_auto_discovery_is_idempotent(tmp_path):
    """Running auto-import twice in a row must not create duplicates."""
    from scripts.validation.manifest import Manifest, SCHEMA_VERSION
    from scripts.validation._video_discovery import auto_import_videos

    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "swing_A.mp4").write_bytes(b"\x00" * 256)
    (videos_dir / "swing_B.mov").write_bytes(b"\x00" * 256)

    manifest = Manifest(schema_version=SCHEMA_VERSION, swings=[])
    first = auto_import_videos(manifest, [videos_dir], project_root=tmp_path)
    assert first == 2
    second = auto_import_videos(manifest, [videos_dir], project_root=tmp_path)
    assert second == 0
    assert len(manifest.swings) == 2


def test_auto_discovery_dedupes_existing_video_bindings(tmp_path):
    """If a manifest entry already points at a video, don't re-import it."""
    from scripts.validation.manifest import (
        Manifest, SCHEMA_VERSION, SwingEntry, GroundTruth,
    )
    from scripts.validation._video_discovery import auto_import_videos

    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    existing_video = videos_dir / "already_bound.mp4"
    existing_video.write_bytes(b"\x00" * 256)
    new_video = videos_dir / "needs_import.mp4"
    new_video.write_bytes(b"\x00" * 256)

    manifest = Manifest(schema_version=SCHEMA_VERSION, swings=[
        SwingEntry(
            id="already_bound",
            video_path=str(existing_video.relative_to(tmp_path)),
            ground_truth=GroundTruth(
                stride_style="toe_tap", final_plant_frame=42,
                contact_frame=50, camera_view="profile", real_time=True,
            ),
        ),
    ])
    n = auto_import_videos(manifest, [videos_dir], project_root=tmp_path)
    assert n == 1  # Only `needs_import.mp4` is new
    assert len(manifest.swings) == 2
    bound = next(s for s in manifest.swings if s.id == "already_bound")
    assert bound.ground_truth.final_plant_frame == 42  # not mutated


def test_resolve_scan_dirs_honors_env_var(tmp_path):
    """LABELING_VIDEO_DIRS env var should add extra scan paths."""
    from scripts.validation._video_discovery import resolve_scan_dirs

    extra1 = tmp_path / "extra1"
    extra2 = tmp_path / "extra2"
    extra1.mkdir()
    extra2.mkdir()
    default = tmp_path / "default"
    default.mkdir()

    dirs = resolve_scan_dirs(
        [default],
        project_root=tmp_path,
        env={"LABELING_VIDEO_DIRS": f"{extra1}:{extra2}"},
    )
    resolved = [d.resolve() for d in dirs]
    assert default.resolve() in resolved
    assert extra1.resolve() in resolved
    assert extra2.resolve() in resolved


def test_resolve_scan_dirs_dedupes(tmp_path):
    """Same path appearing twice (defaults + env) should produce one entry."""
    from scripts.validation._video_discovery import resolve_scan_dirs

    d = tmp_path / "scan"
    d.mkdir()
    dirs = resolve_scan_dirs(
        [d],
        project_root=tmp_path,
        env={"LABELING_VIDEO_DIRS": str(d)},
    )
    # Even though the same dir is mentioned twice, only one entry returned
    resolved = [p.resolve() for p in dirs]
    assert resolved.count(d.resolve()) == 1


def test_manifest_symbols_actually_exist():
    """The symbols labeling_app pulls from manifest.py must be exported."""
    from scripts.validation import manifest as m
    for required in (
        "load_manifest", "write_manifest", "Manifest", "SwingEntry",
        "VALID_STRIDE_STYLES", "VALID_CAMERA_VIEWS",
    ):
        assert hasattr(m, required), (
            f"scripts.validation.manifest missing: {required}"
        )


def test_atomic_save_helper_logic():
    """Pull the atomic-save logic out of the module and exercise it
    independently. We simulate it manually since the helper uses st.* nowhere."""
    from scripts.validation.manifest import (
        Manifest, SwingEntry, GroundTruth, SCHEMA_VERSION,
        write_manifest, load_manifest,
    )
    # Replicate the atomic-save behavior (this is what _save_manifest_atomic does)
    import os
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "manifest.json"
        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            swings=[
                SwingEntry(
                    id="t1",
                    ground_truth=GroundTruth(
                        stride_style="toe_tap",
                        final_plant_frame=100,
                        contact_frame=115,
                        camera_view="profile",
                        real_time=True,
                    ),
                ),
            ],
        )
        # Simulate atomic write
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".m.", suffix=".tmp")
        os.close(fd)
        tmp_path = Path(tmp)
        write_manifest(manifest, tmp_path)
        os.replace(tmp_path, target)
        # Verify round-trips
        loaded = load_manifest(target)
        assert loaded.swings[0].id == "t1"
        assert loaded.swings[0].ground_truth.final_plant_frame == 100


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
