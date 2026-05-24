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


def test_power_sequence_renders_sequencing_only():
    """Only the sequencing-lag (kinetic-chain) read is surfaced, and
    CATEGORICALLY — not a precise ms. Peak hip speed + front-side stability are
    intentionally NOT shown (unreliable from a single phone video)."""
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
    assert "Kinetic Chain" in html
    assert "Hips lead" in html                       # categorical label, not "32 ms"
    assert "SEQUENCING" in html.upper()
    # The two unreliable metrics must NOT surface anywhere.
    assert "947" not in html and "°/s" not in html
    assert "PEAK HIP SPEED" not in html.upper()
    assert "STAY CLOSED" not in html.upper()


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


def test_power_sequence_poor_rating_single_tile():
    record = {
        "sequence": {
            "sequencing_lag_ms":        -80.0,
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
    # Single sequencing tile now — not three.
    assert html.count("srd-power-tile poor") == 1
    assert "Shoulders fire early" in html


def test_power_sequence_hidden_when_lag_unmeasured():
    """If sequencing couldn't be read (bad angle / not a clean swing), the whole
    section hides — even if the now-unused omega/flyout happen to have values."""
    record = {
        "sequence": {
            "sequencing_lag_ms":        None,
            "peak_hip_omega_deg_s":     900.0,
            "front_side_stability_pct": 20.0,
            "rating": {"sequencing_lag": None, "peak_hip_omega": "good",
                       "front_side_stability": "good"},
        },
    }
    assert _srd._render_power_sequence(record) == ""


# ───────────────────────── X-Factor timing tile ─────────────────────────
# Approved "Balanced" band: good <= -20ms (peaks before contact),
# marginal -20 < ms <= 10, poor ms > 10 (peaks after contact).

def test_xfactor_rating_band_boundaries():
    assert _srd._xfactor_rating(-45.0) == "good"
    assert _srd._xfactor_rating(-20.0) == "good"      # inclusive good edge
    assert _srd._xfactor_rating(-19.9) == "marginal"
    assert _srd._xfactor_rating(0.0) == "marginal"
    assert _srd._xfactor_rating(10.0) == "marginal"   # inclusive marginal edge
    assert _srd._xfactor_rating(10.1) == "poor"
    assert _srd._xfactor_rating(30.0) == "poor"
    assert _srd._xfactor_rating(None) is None


def test_xfactor_value_maps_sign_to_early_late():
    assert _srd._xfactor_value(-45.0) == ("45", "ms early")
    assert _srd._xfactor_value(15.0) == ("15", "ms late")
    assert _srd._xfactor_value(0.0) == ("0", "ms")
    assert _srd._xfactor_value(None) == ("—", "")


# ───────────────────────── Tempo (gather:fire) tile ─────────────────────
# Rating REUSES the Timing pillar so the tile can never contradict the bar.

def test_tempo_rating_tracks_timing_pillar():
    def rec(compliance, confidence=1.0):
        return {"pillars": {"timing": {"compliance": compliance,
                                       "confidence": confidence}}}
    assert _srd._tempo_rating(rec(0.90)) == "good"
    assert _srd._tempo_rating(rec(0.66)) == "good"     # inclusive good edge
    assert _srd._tempo_rating(rec(0.50)) == "marginal"
    assert _srd._tempo_rating(rec(0.33)) == "marginal"  # inclusive marginal edge
    assert _srd._tempo_rating(rec(0.10)) == "poor"


def test_tempo_rating_none_when_pillar_unmeasured():
    assert _srd._tempo_rating({}) is None
    assert _srd._tempo_rating({"pillars": {"timing": {"compliance": None,
                                                      "confidence": 1.0}}}) is None
    assert _srd._tempo_rating({"pillars": {"timing": {"compliance": 0.9,
                                                      "confidence": 0}}}) is None


# ───────────────────── render integration (all three tiles) ─────────────

def _full_record():
    return {
        "sequence": {"sequencing_lag_ms": 32.0,
                     "rating": {"sequencing_lag": "good"}},
        "tempo_ratio": 1.8,
        "pillars": {"timing": {"compliance": 0.9, "confidence": 1.0}},
        "xfactor_timing_ms": -45.0,
    }


def test_tempo_tile_renders_with_value_and_pillar_rating():
    html = _srd._render_power_sequence(_full_record())
    assert "TEMPO" in html.upper()
    assert "1.8" in html                      # the gather:fire value
    assert "A real gather" in html            # good coach copy
    # Pillar is good -> tempo tile carries the good class.
    assert "srd-power-tile good" in html


def test_xfactor_tile_renders_early_and_good():
    html = _srd._render_power_sequence(_full_record())
    assert "X-FACTOR" in html.upper()
    assert "45" in html and "ms early" in html
    assert "unwinds into the ball" in html    # good coach copy


def test_section_shows_with_tempo_only_no_sequencing():
    """Section is no longer all-or-nothing on sequencing: tempo alone shows it."""
    record = {"tempo_ratio": 1.8,
              "pillars": {"timing": {"compliance": 0.9, "confidence": 1.0}}}
    html = _srd._render_power_sequence(record)
    assert html != ""
    assert "TEMPO" in html.upper()
    assert "Hips lead" not in html            # sequencing tile absent


def test_three_tiles_render_without_fullwidth_span():
    html = _srd._render_power_sequence(_full_record())
    # Count actual tile <div>s (the class token is followed by a rating word),
    # not the sub-element classes (srd-power-tile-label, etc.).
    assert html.count('class="srd-power-tile ') == 3
    # With >=2 tiles they sit in the grid — no full-width override.
    assert "grid-column: 1 / -1" not in html


def test_single_sequencing_tile_keeps_fullwidth_span():
    record = {"sequence": {"sequencing_lag_ms": 32.0,
                           "rating": {"sequencing_lag": "good"}}}
    html = _srd._render_power_sequence(record)
    assert html.count('class="srd-power-tile ') == 1
    assert "grid-column: 1 / -1" in html


def test_two_tiles_use_two_column_modifier():
    """Two tiles should fill the row 50/50 (modifier class), not hug the left
    third of a 3-col grid."""
    record = {"sequence": {"sequencing_lag_ms": 20.0,
                           "rating": {"sequencing_lag": "marginal"}},
              "tempo_ratio": 2.1,
              "pillars": {"timing": {"compliance": 0.7, "confidence": 1.0}}}
    html = _srd._render_power_sequence(record)
    assert html.count('class="srd-power-tile ') == 2
    assert "srd-power-tiles--two" in html


def test_three_and_one_tile_omit_two_column_modifier():
    assert "srd-power-tiles--two" not in _srd._render_power_sequence(_full_record())
    one = {"sequence": {"sequencing_lag_ms": 32.0,
                        "rating": {"sequencing_lag": "good"}}}
    assert "srd-power-tiles--two" not in _srd._render_power_sequence(one)
