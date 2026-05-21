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
        "VALID_STRIDE_STYLES", "VALID_CAMERA_VIEWS",
    ):
        assert required in src, f"labeling_app references missing symbol: {required}"


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
