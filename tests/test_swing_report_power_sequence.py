"""Snapshot test: rendered swing report HTML contains the Power Sequence
section when a record has a sequence block."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
# Ensure project root is first on sys.path so our local modules take priority.
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

# Install a minimal streamlit stub before any project module imports it,
# so that swing_report.py (which does `import streamlit as st` at module
# level) doesn't fail when running alongside tests that install their own
# incompatible stub.
if "streamlit" not in sys.modules:
    _st_stub = types.ModuleType("streamlit")
    _st_stub.session_state = {}

    def _noop(*a, **kw):
        return None

    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _passthrough_decorator(*dargs, **dkwargs):
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        def inner(fn): return fn
        return inner

    for _attr in (
        "markdown", "write", "error", "warning", "caption", "rerun",
        "stop", "toast", "success", "info", "image", "code", "header",
        "subheader", "text", "title", "button", "checkbox", "selectbox",
        "text_input", "number_input", "slider", "columns", "expander",
        "sidebar", "spinner", "empty", "form", "form_submit_button",
        "set_page_config",
    ):
        setattr(_st_stub, _attr, _noop)

    _st_stub.cache_resource = _passthrough_decorator
    _st_stub.cache_data = _passthrough_decorator

    class _SessionState(dict):
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
        def __setattr__(self, k, v): self[k] = v

    _st_stub.session_state = _SessionState()
    sys.modules["streamlit"] = _st_stub

import swing_report_dashboard_preview as _srd  # noqa: E402


def test_power_sequence_section_renders_with_all_three_tiles():
    record = {
        "sequence": {
            "sequencing_lag_ms":        32.0,
            "peak_hip_omega_deg_s":     947.0,
            "front_side_stability_pct": 22.0,
            "rating": {
                "sequencing_lag":        "good",
                "peak_hip_omega":        "good",
                "front_side_stability":  "good",
            },
        },
    }
    html = _srd._render_power_sequence(record)
    assert "Power Sequence" in html
    assert "32" in html and "ms" in html
    assert "947" in html and "°/s" in html
    assert "22" in html and "%" in html
    assert "SEQUENCING" in html.upper()
    assert "PEAK HIP SPEED" in html.upper()
    assert "STAY CLOSED" in html.upper()


def test_power_sequence_section_empty_when_no_sequence_block():
    record = {}
    assert _srd._render_power_sequence(record) == ""


def test_power_sequence_section_skips_all_none_metrics():
    """When all 3 metrics are None, hide the section."""
    record = {
        "sequence": {
            "sequencing_lag_ms":        None,
            "peak_hip_omega_deg_s":     None,
            "front_side_stability_pct": None,
            "rating": {"sequencing_lag": None, "peak_hip_omega": None,
                        "front_side_stability": None},
        },
    }
    assert _srd._render_power_sequence(record) == ""


def test_power_sequence_poor_rating_shows_red_border_class():
    record = {
        "sequence": {
            "sequencing_lag_ms":        -10.0,
            "peak_hip_omega_deg_s":     400.0,
            "front_side_stability_pct": 60.0,
            "rating": {
                "sequencing_lag":        "poor",
                "peak_hip_omega":        "poor",
                "front_side_stability":  "poor",
            },
        },
    }
    html = _srd._render_power_sequence(record)
    assert html.count("srd-power-tile poor") == 3
