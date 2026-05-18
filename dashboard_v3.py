"""
BarrelLabs / SwingAI — Dashboard V3  (Edge mock, wired to real data)
=====================================================================

This module renders the "Edge" mock dashboard
(`mock_dashboard_template.py`) populated with the signed-in player's
real Supabase data. It exists alongside `dashboard.py` (v1) and
`dashboard_v2.py` (v2) — it does NOT replace either.

Activation:
    app.py reads st.session_state["use_dashboard_v3"] (default False).
    A `?v3=1` URL param can also toggle it. When True, the auth flow
    calls `render_dashboard_v3(user)` instead of v1 / v2.

Data sources:
    - player_storage.load_swing_history(player_slug) -> list[record]
    - dashboard._safe_history(user)                  -> normalized history
    - dashboard._similarity_pct(record)              -> overall sim 0..100
    - dashboard._pretty_player_name(slug)            -> "Mookie Betts"
    - dashboard._format_when(timestamp)              -> "Tuesday · 10:42 PM"
    - reference_library                              -> MLB reference data

Strategy (intentionally pragmatic for first integration pass):
    The mock's HTML payload is loaded from `mock_dashboard_template.py`
    as a single string. We do targeted str.replace() swaps to inject
    real values into the template, then render via components.html.
    Sections without a confirmed real-data source remain as the mock's
    placeholder values; each one is flagged with TODO comments below
    showing what's needed to wire it. This approach keeps the design
    100% faithful while making integration iterative.
"""
from __future__ import annotations

import os
import re
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

from dashboard import (
    _safe_history,
    _similarity_pct,
    _pretty_player_name,
    _format_when,
)


# ---------------------------------------------------------------------------
# Logo data URI (embedded so the components.html iframe doesn't need to
# fetch an external file). Cached per-process since the PNG never
# changes mid-session.
# ---------------------------------------------------------------------------

_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "barrellabs_logo.png",
)
_LOGO_DATA_URI_CACHE: Optional[str] = None


def _logo_data_uri() -> str:
    """Return a base64 PNG data URI for the BarrelLabs logo, resized to
    256×256 and PNG-optimized. Empty string if the file is missing — the
    template still renders; the masthead just shows a blank circle."""
    global _LOGO_DATA_URI_CACHE
    if _LOGO_DATA_URI_CACHE is not None:
        return _LOGO_DATA_URI_CACHE
    try:
        import base64
        import io
        from PIL import Image
        if not os.path.exists(_LOGO_PATH):
            _LOGO_DATA_URI_CACHE = ""
            return ""
        img = Image.open(_LOGO_PATH).convert("RGBA").resize((256, 256), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        _LOGO_DATA_URI_CACHE = "data:image/png;base64," + b64
        return _LOGO_DATA_URI_CACHE
    except Exception:
        _LOGO_DATA_URI_CACHE = ""
        return ""


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "mock_dashboard_template.py",
)
_TEMPLATE_CACHE: Optional[str] = None


def _load_template_html() -> str:
    """Extract the DASHBOARD_HTML raw string from mock_dashboard_template.py."""
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is not None:
        return _TEMPLATE_CACHE
    try:
        src = open(_TEMPLATE_PATH, "r", encoding="utf-8").read()
        m = re.search(r'DASHBOARD_HTML\s*=\s*r"""(.*?)"""', src, re.DOTALL)
        if not m:
            return ""
        _TEMPLATE_CACHE = m.group(1)
        return _TEMPLATE_CACHE
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def _all_metric_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten metric_table (dict-of-lists) into a single list of rows."""
    mt = record.get("metric_table") or {}
    rows: List[Dict[str, Any]] = []
    if isinstance(mt, dict):
        for group_rows in mt.values():
            if isinstance(group_rows, list):
                rows.extend([r for r in group_rows if isinstance(r, dict)])
    elif isinstance(mt, list):
        rows.extend([r for r in mt if isinstance(r, dict)])
    return rows


def _find_metric(record: Dict[str, Any], *keywords: str) -> Optional[Dict[str, Any]]:
    """Find the first metric row whose label contains all provided keywords."""
    needles = [k.lower() for k in keywords]
    for row in _all_metric_rows(record):
        label = (row.get("label") or "").lower()
        if all(n in label for n in needles):
            return row
    return None


def _metric_sim(record: Dict[str, Any], *keywords: str, default: int = 0) -> int:
    row = _find_metric(record, *keywords)
    if not row:
        return default
    try:
        return int(round(float(row.get("sim_pct") or 0)))
    except Exception:
        return default


def _compose_edge_score(record: Dict[str, Any]) -> int:
    """Composite 0..100 from average of per-metric similarity scores."""
    sims = [
        float(r.get("sim_pct") or 0)
        for r in _all_metric_rows(record)
        if isinstance(r.get("sim_pct"), (int, float))
    ]
    if not sims:
        return 50
    return int(round(sum(sims) / len(sims)))


def _tier_for(edge_score: int) -> Tuple[str, str, int]:
    """Return (tier_name, next_tier_name, points_to_next)."""
    if edge_score >= 92:
        return ("MLB", "MLB", 0)
    if edge_score >= 85:
        return ("Pro", "MLB", max(0, 92 - edge_score))
    if edge_score >= 72:
        return ("Elite", "Pro", max(0, 85 - edge_score))
    return ("Amateur", "Elite", max(0, 72 - edge_score))


def _streak_days(history: List[Dict[str, Any]]) -> int:
    """Count consecutive calendar days with at least one swing, ending today."""
    if not history:
        return 0
    dates = set()
    for r in history:
        ts = r.get("timestamp") or r.get("created_at")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = ts
            dates.add(dt.date())
        except Exception:
            pass
    if not dates:
        return 0
    today = datetime.now(timezone.utc).date()
    streak = 0
    cur = today
    while cur in dates:
        streak += 1
        cur -= timedelta(days=1)
    # If today doesn't have a session, also check from yesterday backwards.
    if streak == 0:
        cur = today - timedelta(days=1)
        while cur in dates:
            streak += 1
            cur -= timedelta(days=1)
    return streak


def _active_days(history: List[Dict[str, Any]], window_days: int = 84) -> int:
    """Count unique calendar days with at least one swing in the last N days."""
    if not history:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    dates = set()
    for r in history:
        ts = r.get("timestamp") or r.get("created_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt >= cutoff:
                dates.add(dt.date())
        except Exception:
            pass
    return len(dates)


def _total_swings(history: List[Dict[str, Any]], window_days: Optional[int] = None) -> int:
    """Approximate total swings analyzed. Uses record-level swing counts if
    present, otherwise counts records (1 record ≈ 1 analyzed clip)."""
    if window_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        records = []
        for r in history:
            ts = r.get("timestamp") or r.get("created_at")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
                if dt >= cutoff:
                    records.append(r)
            except Exception:
                pass
    else:
        records = history
    total = 0
    for r in records:
        n = r.get("swing_count") or r.get("num_swings") or 1
        try:
            total += int(n)
        except Exception:
            total += 1
    return total


# ---------------------------------------------------------------------------
# MLB reference metadata (used to populate the "you swing most like" bio)
# ---------------------------------------------------------------------------

_MLB_META: Dict[str, Dict[str, str]] = {
    "mookie_betts":      {"team": "LAD", "hand": "RHH", "height": "5'10\"", "weight": "180 lb", "tag": "4× All-Star"},
    "aaron_judge":       {"team": "NYY", "hand": "RHH", "height": "6'7\"",  "weight": "282 lb", "tag": "2× MVP"},
    "shohei_ohtani":     {"team": "LAD", "hand": "LHH", "height": "6'4\"",  "weight": "210 lb", "tag": "3× MVP"},
    "mike_trout":        {"team": "LAA", "hand": "RHH", "height": "6'2\"",  "weight": "235 lb", "tag": "3× MVP"},
    "juan_soto":         {"team": "NYM", "hand": "LHH", "height": "6'2\"",  "weight": "224 lb", "tag": "4× All-Star"},
    "ronald_acuna_jr":   {"team": "ATL", "hand": "RHH", "height": "6'0\"",  "weight": "205 lb", "tag": "MVP"},
    "freddie_freeman":   {"team": "LAD", "hand": "LHH", "height": "6'5\"",  "weight": "220 lb", "tag": "MVP"},
    "kyle_tucker":       {"team": "CHC", "hand": "LHH", "height": "6'4\"",  "weight": "199 lb", "tag": "3× All-Star"},
    "manny_machado":     {"team": "SD",  "hand": "RHH", "height": "6'3\"",  "weight": "218 lb", "tag": "6× All-Star"},
    "alex_bregman":      {"team": "HOU", "hand": "RHH", "height": "6'0\"",  "weight": "192 lb", "tag": "2× All-Star"},
    "jose_ramirez":      {"team": "CLE", "hand": "S",   "height": "5'9\"",  "weight": "190 lb", "tag": "6× All-Star"},
    "yandy_diaz":        {"team": "TB",  "hand": "RHH", "height": "6'2\"",  "weight": "215 lb", "tag": "All-Star"},
    "yordan_alvarez":    {"team": "HOU", "hand": "LHH", "height": "6'5\"",  "weight": "235 lb", "tag": "3× All-Star"},
    "kyle_schwarber":    {"team": "PHI", "hand": "LHH", "height": "6'0\"",  "weight": "229 lb", "tag": "2× All-Star"},
    "francisco_lindor":  {"team": "NYM", "hand": "S",   "height": "5'11\"", "weight": "190 lb", "tag": "4× All-Star"},
    "gunnar_henderson":  {"team": "BAL", "hand": "LHH", "height": "6'2\"",  "weight": "210 lb", "tag": "All-Star"},
    "spencer_torkelson": {"team": "DET", "hand": "RHH", "height": "6'1\"",  "weight": "220 lb", "tag": "Top prospect"},
}


def _ref_bio(slug: str) -> str:
    meta = _MLB_META.get(slug, {})
    parts = [
        meta.get("team", "—"),
        meta.get("hand", "RHH"),
        meta.get("height", ""),
        meta.get("weight", ""),
        meta.get("tag", ""),
    ]
    return " · ".join([p for p in parts if p])


# ---------------------------------------------------------------------------
# Six-axis DNA / Edge Score categorization. The mock has 6 axes that don't
# 1:1 with dashboard.py's _radar_from_record (which uses 5 different axes).
# Categorize metric_table rows into our six buckets by label keyword.
# ---------------------------------------------------------------------------
_AXIS_KEYS: Dict[str, List[List[str]]] = {
    # Each axis maps to a list of keyword sets — a row matches the axis if
    # any keyword set is fully present in its label.
    "match":     [["match"], ["overall"]],
    "rotation":  [["hip", "rotation"], ["separation"], ["sep"]],
    "knee":      [["knee"]],
    "head":      [["head"]],
    "timing":    [["launch"], ["contact", "ms"], ["foot plant"], ["timing"]],
    "tempo":     [["total"], ["duration"], ["load"], ["tempo"]],
}


def _six_axis_scores(record: Dict[str, Any]) -> Dict[str, int]:
    """Compute 0-100 scores for the six dashboard axes from metric_table."""
    rows = _all_metric_rows(record)
    overall = int(round(_similarity_pct(record) or 0))
    out: Dict[str, int] = {}
    for axis, keyword_sets in _AXIS_KEYS.items():
        sims: List[float] = []
        for r in rows:
            label = (r.get("label") or "").lower()
            for kws in keyword_sets:
                if all(kw in label for kw in kws):
                    try:
                        sims.append(float(r.get("sim_pct") or 0))
                    except Exception:
                        pass
                    break
        out[axis] = int(round(sum(sims) / len(sims))) if sims else overall
    return out


# ---------------------------------------------------------------------------
# Gamification (optional — falls back gracefully if unavailable)
# ---------------------------------------------------------------------------

def _gamification_state(user: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from gamification import compute_player_state  # type: ignore
        return compute_player_state(user, history) or {}
    except Exception:
        return {}


def _personal_records_count(history: List[Dict[str, Any]]) -> int:
    """Count PRs.

    Production records don't store an explicit `is_pr` flag, so we compute
    it: a record counts as a PR if its overall score set a new high-water
    mark vs every prior session (chronologically). The first record always
    counts as one PR (the first time you do anything is by definition a
    high-water mark).
    """
    n = 0
    high = -1.0
    for r in history:  # history is ordered oldest → newest
        if r.get("is_pr") or r.get("pr") or r.get("is_personal_record"):
            n += 1
            continue
        try:
            score = float(_similarity_pct(r) or 0)
        except Exception:
            score = 0.0
        if score > high:
            high = score
            n += 1
    return n


def _edge_score_series(history: List[Dict[str, Any]]) -> List[int]:
    return [_compose_edge_score(r) for r in history]


def _match_score_series(history: List[Dict[str, Any]]) -> List[int]:
    return [int(round(_similarity_pct(r) or 0)) for r in history]


def _grade_from_score(score: int) -> str:
    """Map a 0-100 score band to a letter grade."""
    if score >= 92: return "A+"
    if score >= 88: return "A"
    if score >= 82: return "A−"
    if score >= 75: return "B+"
    if score >= 68: return "B"
    if score >= 60: return "B−"
    if score >= 50: return "C"
    return "C−"


def _format_phase_offset_ms(record: Dict[str, Any], key: str, anchor_key: str = "contact") -> str:
    """Return signed ms offset of phase `key` relative to anchor (default: contact)."""
    pt = record.get("phases_t") or {}
    a = pt.get(anchor_key)
    v = pt.get(key)
    if not isinstance(a, (int, float)) or not isinstance(v, (int, float)):
        return "—"
    ms = int(round((v - a) * 1000))
    sign = "+" if ms >= 0 else "−"
    return f"{sign}{abs(ms)}"


# ---------------------------------------------------------------------------
# SVG path / chart geometry helpers
# ---------------------------------------------------------------------------

def _parse_numeric(s: Any) -> Optional[float]:
    """Extract leading numeric value from a string like '42°' or '184 ms'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.match(r'[-+]?\d*\.?\d+', str(s).strip())
    return float(m.group(0)) if m else None


def _metric_value_series(history: List[Dict[str, Any]], *keywords: str) -> List[float]:
    """Series of numeric values for a metric across history (None where missing)."""
    out: List[Optional[float]] = []
    for r in history:
        row = _find_metric(r, *keywords)
        if not row:
            out.append(None); continue
        out.append(_parse_numeric(row.get("player_str") or row.get("value")))
    # Forward-fill missing values so the chart doesn't break.
    filled: List[float] = []
    last = 0.0
    for v in out:
        if v is None:
            filled.append(last)
        else:
            filled.append(v); last = v
    return filled


def _scale_to_viewbox(values: List[float], width: int, height: int,
                      margin_top: int = 5, margin_bot: int = 5) -> List[Tuple[float, float]]:
    """Map a value series to (x, y) coords in a viewBox. Inverts Y."""
    if not values:
        return []
    n = len(values)
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vmax = vmin + 1
    yspan = height - margin_top - margin_bot
    pts: List[Tuple[float, float]] = []
    for i, v in enumerate(values):
        x = (i / max(1, n - 1)) * width if n > 1 else width / 2
        # invert: high value = low y
        y = margin_top + (1 - (v - vmin) / (vmax - vmin)) * yspan
        pts.append((round(x, 1), round(y, 1)))
    return pts


def _line_path(pts: List[Tuple[float, float]]) -> str:
    if not pts:
        return "M0,0"
    return "M" + " L".join(f"{x},{y}" for x, y in pts)


def _area_path(pts: List[Tuple[float, float]], width: int, height: int) -> str:
    if not pts:
        return f"M0,{height} L{width},{height} Z"
    line = _line_path(pts)
    return f"{line} L{width},{height} L0,{height} Z"


def _sparkline_svg(values: List[float], *,
                   accent: str = "#E8C170", stroke: str = "#F4EFE6",
                   fill_id: Optional[str] = None,
                   fill_color: str = "rgba(244,239,230,0.32)",
                   end_dot: bool = True) -> str:
    """Build a 200x40 area+line sparkline SVG block (replacement for the
    mock's scoreboard SVGs). When fill_id is None, line-only mode."""
    if not values:
        values = [50] * 16
    if len(values) > 16:
        values = values[-16:]
    pts = _scale_to_viewbox(values, width=200, height=40, margin_top=5, margin_bot=5)
    line_d = _line_path(pts)
    end_x, end_y = pts[-1]
    end_html = (
        f'<circle cx="{end_x}" cy="{end_y}" r="3" fill="{accent}"/>' if end_dot else ""
    )
    if fill_id:
        area_d = _area_path(pts, 200, 40)
        gradient = (
            f'<defs><linearGradient id="{fill_id}" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0%" stop-color="{fill_color}"/>'
            f'<stop offset="100%" stop-color="rgba(0,0,0,0)"/>'
            f'</linearGradient></defs>'
        )
        body = (
            f'{gradient}'
            f'<path d="{area_d}" fill="url(#{fill_id})"/>'
            f'<path d="{line_d}" fill="none" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round"/>'
            f'{end_html}'
        )
    else:
        body = (
            f'<path d="{line_d}" fill="none" stroke="{stroke}" stroke-width="1.4" stroke-linecap="round"/>'
            f'{end_html}'
        )
    return f'<svg class="spark" viewBox="0 0 200 40" preserveAspectRatio="none">{body}</svg>'


def _sparkline_bars_svg(values: List[float], accent: str = "#E8C170") -> str:
    """16-bar mini bar chart (last bar accent-colored)."""
    if not values:
        values = [12] * 16
    if len(values) > 16:
        values = values[-16:]
    if len(values) < 16:
        # left-pad with first value
        values = [values[0]] * (16 - len(values)) + values
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vmax = vmin + 1
    bars = []
    for i, v in enumerate(values):
        h = 4 + (v - vmin) / (vmax - vmin) * 26   # 4..30 px tall
        y = 30 - h + 5   # top edge so bottom is at y=35
        fill = accent if i == 15 else "rgba(244,239,230,0.85)"
        bars.append(f'<rect x="{2 + i*12}" y="{y:.1f}" width="8" height="{h:.1f}" fill="{fill}"/>')
    return (
        '<svg class="spark" viewBox="0 0 200 40" preserveAspectRatio="none">'
        '<g>' + "".join(bars) + '</g></svg>'
    )


def _radar_polygon_points(scores: Dict[str, int],
                          axis_order: List[str], max_radius: float = 118.0,
                          score_max: float = 100.0) -> str:
    """6-axis polygon points string. Axes plotted at -90, -30, 30, 90, 150, 210 degrees."""
    angles = [-90 + i * 60 for i in range(6)]
    pts = []
    for axis, deg in zip(axis_order, angles):
        score = max(0, min(score_max, scores.get(axis, 50)))
        r = (score / score_max) * max_radius
        rad = math.radians(deg)
        x = round(r * math.cos(rad), 1)
        y = round(r * math.sin(rad), 1)
        pts.append(f"{x},{y}")
    return " ".join(pts)


def _weekly_buckets(values: List[float], timestamps: List[Any], n_weeks: int = 8) -> List[Optional[float]]:
    """Bucket values into N most-recent calendar weeks; returns list of avg-per-week."""
    if not values or not timestamps:
        return [None] * n_weeks
    pairs = []
    for v, ts in zip(values, timestamps):
        if v is None or ts is None:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        pairs.append((v, dt))
    if not pairs:
        return [None] * n_weeks
    now = datetime.now(timezone.utc)
    buckets: List[List[float]] = [[] for _ in range(n_weeks)]
    for v, dt in pairs:
        delta_days = (now - dt).days
        week_idx = (n_weeks - 1) - (delta_days // 7)
        if 0 <= week_idx < n_weeks:
            buckets[week_idx].append(v)
    out: List[Optional[float]] = []
    last = None
    for b in buckets:
        if b:
            last = sum(b) / len(b)
            out.append(last)
        else:
            out.append(last)  # carry forward
    return out


def _ladder_data_points(history: List[Dict[str, Any]], max_n: int = 8) -> List[Tuple[float, str]]:
    """Return up to `max_n` (score, date_label) tuples from the most recent
    analyses, ordered oldest → newest. No placeholders — returns only what
    actually exists in the user's history. Empty list if no analyses."""
    if not history:
        return []
    recent = history[-max_n:]
    out: List[Tuple[float, str]] = []
    for r in recent:
        score = float(_similarity_pct(r) or 0)
        ts = r.get("timestamp") or r.get("created_at")
        lbl = "—"
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt:
                lbl = dt.strftime("%b %-d").upper()
        except Exception:
            pass
        out.append((score, lbl))
    return out


def _velocity_ladder_bars(history: List[Dict[str, Any]]) -> str:
    """Bars from real analyses only — no padding, no placeholders."""
    pts = _ladder_data_points(history, max_n=8)

    # Empty state — render a single full-width message inside the ladder slot
    # rather than a fake bar grid.
    if not pts:
        return (
            '<div class="ladder-vis" style="padding-bottom: 24px; align-items: center; '
            'grid-template-columns: 1fr; text-align: center;">\n'
            '  <div style="font-family: var(--mono); font-size: 11px; '
            'letter-spacing: 0.14em; text-transform: uppercase; color: var(--gray-1);">'
            'Upload a swing to start tracking your match-score progression</div>\n'
            '</div>'
        )

    vals = [p[0] for p in pts]
    peak_val = max(vals)
    n = len(pts)

    # Build a CSS grid that always shows columns proportional to actual analyses;
    # bars fill the available width even if there are fewer than 8.
    bars: List[str] = []
    for i, (v, lbl) in enumerate(pts):
        # Height as % of card; min 18% so the value label always reads.
        pct_height = max(18, int(round(v)))
        # Highlight the most recent bar AND any peak.
        is_last = (i == n - 1)
        is_peak = abs(v - peak_val) < 0.5
        peak_cls = " peak" if (is_last or is_peak) else ""
        bars.append(
            f'<div class="bar{peak_cls}" style="height: {pct_height}%;">'
            f'<span class="v">{int(round(v))}</span><span class="wk">{lbl}</span></div>'
        )
    grid_cols = f"repeat({n}, 1fr)"
    return (
        f'<div class="ladder-vis" style="padding-bottom: 24px; grid-template-columns: {grid_cols};">\n  '
        + "\n  ".join(bars) +
        '\n</div>'
    )


def _trend_chart_svg(*, edge_series: List[float], match_series: List[float],
                     pr_indices: List[int], x_labels: List[Tuple[float, str]],
                     width: int = 1280, height: int = 280) -> str:
    """12-week or 30-day trend chart: 2 lines + area fills + PR gold dots."""
    if not edge_series:
        edge_series = [50, 55, 60, 65, 70, 75, 80, 85]
    if not match_series:
        match_series = [50, 60, 65, 70, 75, 80, 85, 88]
    if len(edge_series) != len(match_series):
        # pad shorter to match
        n = max(len(edge_series), len(match_series))
        def _pad(xs):
            if len(xs) >= n: return xs
            return [xs[0]] * (n - len(xs)) + xs
        edge_series  = _pad(edge_series)
        match_series = _pad(match_series)
    e_pts = _scale_to_viewbox(edge_series,  width, height, margin_top=40, margin_bot=60)
    m_pts = _scale_to_viewbox(match_series, width, height, margin_top=40, margin_bot=60)
    e_line  = _line_path(e_pts)
    e_area  = _area_path(e_pts, width, height)
    m_line  = _line_path(m_pts)
    m_area  = _area_path(m_pts, width, height)

    # PR dots: place at corresponding e_pts indices
    pr_marks = []
    for idx in pr_indices:
        if 0 <= idx < len(e_pts):
            x, y = e_pts[idx]
            pr_marks.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#E8C170"/>')
    # Halo around the most-recent PR
    if pr_indices:
        last = pr_indices[-1]
        if 0 <= last < len(e_pts):
            x, y = e_pts[last]
            pr_marks.append(f'<circle cx="{x}" cy="{y}" r="11" fill="none" stroke="#E8C170" opacity="0.4"/>')

    # X-axis labels
    xlabel_g = "".join(
        f'<text x="{x}" y="{height - 8}" text-anchor="{anchor}" '
        f'font-family="Geist Mono, monospace" font-size="9.5" fill="#565A62" letter-spacing="0.10em">{lbl}</text>'
        for x, lbl, anchor in [
            (xl[0],         xl[1], "start" if i == 0 else ("end" if i == len(x_labels) - 1 else "middle"))
            for i, xl in enumerate(x_labels)
        ]
    )

    return f'''
<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
  <defs>
    <linearGradient id="edgeAreaGrad12" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"  stop-color="rgba(244,239,230,0.18)"/>
      <stop offset="100%" stop-color="rgba(244,239,230,0)"/>
    </linearGradient>
    <linearGradient id="matchAreaGrad12" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%"  stop-color="rgba(230,69,48,0.20)"/>
      <stop offset="100%" stop-color="rgba(230,69,48,0)"/>
    </linearGradient>
  </defs>
  <g stroke="rgba(244,239,230,0.05)" stroke-dasharray="2 4">
    <line x1="0" y1="40"  x2="{width}" y2="40"/>
    <line x1="0" y1="100" x2="{width}" y2="100"/>
    <line x1="0" y1="160" x2="{width}" y2="160"/>
    <line x1="0" y1="220" x2="{width}" y2="220"/>
  </g>
  <path d="{e_area}" fill="url(#edgeAreaGrad12)"/>
  <path d="{e_line}" fill="none" stroke="#F4EFE6" stroke-width="2"/>
  <path d="{m_area}" fill="url(#matchAreaGrad12)" opacity="0.7"/>
  <path d="{m_line}" fill="none" stroke="#E64530" stroke-width="2" opacity="0.92"/>
  {"".join(pr_marks)}
  {xlabel_g}
</svg>'''.strip()


# ---------------------------------------------------------------------------
# Narrative band + top-category helpers
# ---------------------------------------------------------------------------

# Match-score bands. Mirror dashboard.py's analyzer thresholds:
#   ≥75 -> strong, 55-74 -> decent, <55 -> building.
def _match_band(pct: int) -> str:
    if pct >= 75:  return "strong match"
    if pct >= 55:  return "decent match"
    return "building"


# Pretty names for the six DNA axes used in narratives.
_AXIS_PRETTY: Dict[str, str] = {
    "match":    "MLB match alignment",
    "rotation": "hip-shoulder separation",
    "knee":     "knee drive",
    "head":     "head stability",
    "timing":   "launch-to-contact timing",
    "tempo":    "overall tempo",
}


def _top_improvement(history: List[Dict[str, Any]]) -> Optional[str]:
    """Axis (pretty name) that improved the most from oldest → newest swing."""
    if len(history) < 2:
        return None
    first_sx = _six_axis_scores(history[0])
    last_sx  = _six_axis_scores(history[-1])
    deltas = {axis: last_sx.get(axis, 0) - first_sx.get(axis, 0) for axis in _AXIS_PRETTY}
    best_axis, best_delta = max(deltas.items(), key=lambda kv: kv[1])
    if best_delta <= 0:
        return None
    return _AXIS_PRETTY.get(best_axis)


def _next_lever(latest: Dict[str, Any]) -> Optional[str]:
    """Axis (pretty name) with the LOWEST sx score on the latest swing."""
    sx = _six_axis_scores(latest)
    if not sx:
        return None
    axis, _ = min(sx.items(), key=lambda kv: kv[1])
    return _AXIS_PRETTY.get(axis)


def _current_plan_id() -> str:
    """Resolve the signed-in user's plan id ("free" | "solo_pro" |
    "family_pro" | "coach_pro"). Falls back to "free" on any error."""
    try:
        from subscription_storage import load_my_plan
        from entitlements import _resolve_plan_id, FREE_PLAN_ID
        snap = load_my_plan() or {}
        return _resolve_plan_id(snap) or FREE_PLAN_ID
    except Exception:
        try:
            from entitlements import FREE_PLAN_ID
            return FREE_PLAN_ID
        except Exception:
            return "free"


def _upgrade_tier_ids(current_plan_id: str) -> List[str]:
    """Return the list of plan ids the user can still upgrade TO,
    in display order. Empty list means they're at the top tier."""
    order = ["solo_pro", "family_pro", "coach_pro"]
    if current_plan_id not in order:
        # Free or unknown — show everything
        return order
    idx = order.index(current_plan_id)
    return order[idx + 1:]


def _build_tier_card_html(plan_id: str, interval: str, *, featured: bool) -> str:
    """Single tier card HTML, populated directly from plan_pricing.
    `interval` is "monthly" or "annual". Tagline/seats/features all live
    inside the card; the toggle picks which `interval` set is visible."""
    from plan_pricing import (
        PLAN_PRICING, annual_savings_pct,
        annual_monthly_equivalent_cents, format_cents,
    )
    p = PLAN_PRICING.get(plan_id) or {}
    name    = p.get("name") or plan_id.replace("_", " ").title()
    tagline = p.get("tagline") or ""
    seats   = int(p.get("seats") or 1)
    seats_lbl = f"{seats} seat" + ("s" if seats != 1 else "")

    # sub_line_cls toggles between gold (value-pop) and muted gray (assurance)
    # so the two states aren't visually indistinguishable in the pricing band.
    if interval == "annual":
        num_disp = format_cents(p.get("annual_cents") or 0).replace("$", "").strip()
        per_lbl  = "/yr"
        save_pct = annual_savings_pct(plan_id)
        if save_pct > 0:
            sub_line = f"save {save_pct}% vs monthly"
            sub_line_cls = ""           # gold — actual savings is the value-pop
        else:
            sub_line = "billed annually · cancel anytime"
            sub_line_cls = " is-assurance"
    else:
        num_disp = format_cents(p.get("monthly_cents") or 0).replace("$", "").strip()
        per_lbl  = "/mo"
        sub_line = "billed monthly · cancel anytime"
        sub_line_cls = " is-assurance"

    # Feature lists — sourced from pricing.py for single-source-of-truth.
    try:
        from pricing import _FEATURES_BASE, _FEATURES_FAMILY_EXTRAS, _FEATURES_COACH_EXTRAS
    except Exception:
        _FEATURES_BASE = [
            "Unlimited swing analyses",
            "Full personalized drill plan",
            "Swing video saved to your history",
            "Full Development Tracker (XP, streaks, achievements)",
            "Rewards Roadmap (incl. limited-edition hoodie at 180d)",
            "PDF report export",
            "Side-by-side swing comparisons",
            "Full MLB comp library",
        ]
        _FEATURES_FAMILY_EXTRAS = ["Up to 4 family member accounts",
                                   "Each member gets their own swing history"]
        _FEATURES_COACH_EXTRAS  = ["Up to 20 player rosters",
                                   "Read-only views of each player's swings",
                                   "Priority support"]
    base_lis  = "".join(f'<li>{f}</li>' for f in _FEATURES_BASE)
    if plan_id == "family_pro":
        extra_lis = "".join(f'<li class="extra">{f}</li>' for f in _FEATURES_FAMILY_EXTRAS)
    elif plan_id == "coach_pro":
        extra_lis = "".join(f'<li class="extra">{f}</li>' for f in _FEATURES_COACH_EXTRAS)
    else:
        extra_lis = ""

    featured_cls = " featured" if featured else ""
    return f'''
<div class="tier-card{featured_cls}">
  <div class="tier-head">
    <div class="tier-name">{name}</div>
    <div class="tier-seats">{seats_lbl}</div>
  </div>
  <div class="tier-tagline">{tagline}</div>
  <div class="tier-price">
    <span class="dollar">$</span><span class="num">{num_disp}</span><span class="per">{per_lbl}</span>
  </div>
  <div class="tier-price-sub{sub_line_cls}">{sub_line}</div>
  <ul class="tier-features">{base_lis}{extra_lis}</ul>
  <a class="tier-cta" href="/?page=pricing">Upgrade now ↗</a>
</div>'''.strip()


def _build_pricing_band_html(current_plan_id: str) -> str:
    """Compose the entire pricing band, plan-aware.

    Cases:
      Free        → 3 cards (Solo / Family / Coach), Family featured
      Solo Pro    → 2 cards (Family / Coach),         Family featured
      Family Pro  → 1 card  (Coach only),              not featured
      Coach Pro   → top-tier closing card (no upsell)
    """
    from plan_pricing import annual_savings_pct
    from entitlements import (
        FREE_SWING_LIMIT, FREE_PLAN_ID, plan_display_name, plan_seat_count,
    )

    upgrade_ids = _upgrade_tier_ids(current_plan_id)
    is_free     = (current_plan_id == FREE_PLAN_ID)

    # ----- Top-tier state: no upgrades available -----
    if not upgrade_ids:
        cur_name  = plan_display_name(current_plan_id)
        cur_seats = plan_seat_count(current_plan_id)
        return f'''
<section class="pricing-band fade-in d12">
  <div class="pricing-head">
    <div class="pricing-head-meta">
      <div class="pricing-eyebrow">§ 13 · Edge Pro Upsell</div>
      <h2 class="pricing-title">You're at the <span class="ital">top tier.</span></h2>
      <p class="pricing-sub">Thanks for being on <span style="color:var(--gold)">{cur_name}</span> — you have access to every BarrelLabs feature, including the full {cur_seats}-seat roster.</p>
    </div>
  </div>
  <div class="free-strip" style="border-color: rgba(232,193,112,0.36);">
    <span class="lead">
      <span class="badge" style="background:var(--gold); color:var(--bg); border-color:var(--gold);">★ {cur_name}</span>
      <span>Top-tier subscriber · all features unlocked · {cur_seats} seats</span>
    </span>
    <a href="/?page=pricing" style="font-family: var(--mono); font-size:10px; letter-spacing:0.14em; text-transform:uppercase; color:var(--bone); text-decoration:none; padding-bottom:2px; border-bottom: 1px solid var(--red);">Manage subscription ↗</a>
  </div>
</section>'''.strip()

    # ----- Upgrade band -----
    save_pct = annual_savings_pct(upgrade_ids[0])

    # Top strip — only for Free users; paid subscribers see a "your plan" chip.
    if is_free:
        top_strip = f'''
<div class="free-strip">
  <span class="lead">
    <span class="badge">Start Free</span>
    <span><span class="v">{FREE_SWING_LIMIT}</span> swing analyses included · no card required</span>
  </span>
  <span class="trail">Upgrade anytime · keep your full swing history</span>
</div>'''.strip()
    else:
        cur_name = plan_display_name(current_plan_id)
        top_strip = f'''
<div class="free-strip">
  <span class="lead">
    <span class="badge">Your plan</span>
    <span><span class="v">{cur_name}</span> · ready to scale up</span>
  </span>
  <a href="/?page=pricing" style="font-family: var(--mono); font-size:10px; letter-spacing:0.14em; text-transform:uppercase; color:var(--gray-1); text-decoration:none;">Manage subscription ↗</a>
</div>'''.strip()

    # Title varies by audience.
    if is_free:
        title_html = 'Lock in your <span class="ital">edge.</span>'
        sub_text   = 'Three tiers. One source of truth. Pick the seat count that matches your household or roster — cancel any time.'
    elif current_plan_id == "solo_pro":
        title_html = 'Open up your <span class="ital">roster.</span>'
        sub_text   = 'Already on Solo Pro? Scale up to share BarrelLabs with your family — or take on a full coaching roster.'
    else:  # family_pro
        title_html = 'Coach a <span class="ital">full roster.</span>'
        sub_text   = 'Coach Pro gives you 20 player seats with read-only views of every swing — built for travel-team and academy coaches.'

    # Determine which card (if any) gets the gold "Most Popular" elevation.
    if "family_pro" in upgrade_ids:
        featured_id = "family_pro"
    elif len(upgrade_ids) == 1:
        # Only one option left — no need for featured emphasis.
        featured_id = None
    else:
        featured_id = upgrade_ids[0]

    n_cols = len(upgrade_ids)
    annual_cards  = "\n      ".join(
        _build_tier_card_html(pid, "annual",  featured=(pid == featured_id))
        for pid in upgrade_ids
    )
    monthly_cards = "\n      ".join(
        _build_tier_card_html(pid, "monthly", featured=(pid == featured_id))
        for pid in upgrade_ids
    )

    # Center single-card layouts.
    grid_style = (
        f"grid-template-columns: repeat({n_cols}, minmax(0, 1fr));"
        + (" max-width: 460px; margin: 0 auto;" if n_cols == 1 else "")
    )

    return f'''
<input type="radio" name="bill" id="bill-m" class="bill-radio">
<input type="radio" name="bill" id="bill-y" class="bill-radio" checked>
<section class="pricing-band fade-in d12">
  <div class="pricing-head">
    <div class="pricing-head-meta">
      <div class="pricing-eyebrow">§ 13 · Edge Pro Upsell</div>
      <h2 class="pricing-title">{title_html}</h2>
      <p class="pricing-sub">{sub_text}</p>
    </div>
  </div>

  {top_strip}

  <div class="pricing-toggle-row">
    <div class="tier-toggle">
      <label for="bill-m">Monthly</label>
      <label for="bill-y">Annual <span class="save-badge">save {save_pct}%</span></label>
    </div>
  </div>

  <div class="tiers-row tiers-annual" style="{grid_style}">
      {annual_cards}
  </div>
  <div class="tiers-row tiers-monthly" style="{grid_style}">
      {monthly_cards}
  </div>
</section>'''.strip()


def _swings_this_week(history: List[Dict[str, Any]]) -> int:
    """Count records timestamped in the last 7 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    n = 0
    for r in history:
        ts = r.get("timestamp") or r.get("created_at")
        if not ts: continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt and dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            if dt and dt >= cutoff: n += 1
        except Exception:
            pass
    return n


# ---------------------------------------------------------------------------
# Section HTML builders — generate dynamic blocks from real data.
# ---------------------------------------------------------------------------

def _build_velocity_narrative_html(history: List[Dict[str, Any]]) -> str:
    """Right side of the velocity ladder card — eyebrow + delta + body copy.

    Uses the SAME data points as the ladder bars (last ≤8 analyses) so the
    narrative numbers always match what the bars show. No weekly bucketing,
    no padded placeholders.
    """
    pts = _ladder_data_points(history, max_n=8)

    # Empty / single-analysis edge cases.
    if not pts:
        return (
            '<div class="ladder-narrative">\n'
            '  <div class="card-eyebrow">Match score · progression · vs MLB match</div>\n'
            '  <div class="num"><span class="ital">—</span></div>\n'
            '  <div class="label">no analyses yet</div>\n'
            '  <div class="body">Upload a swing to begin tracking how your MLB match '
            'score evolves session over session.</div>\n'
            '</div>'
        )
    if len(pts) == 1:
        v = int(round(pts[0][0]))
        return (
            f'<div class="ladder-narrative">\n'
            f'  <div class="card-eyebrow">Match score · first analysis · vs MLB match</div>\n'
            f'  <div class="num"><span class="ital">{v}</span> pts</div>\n'
            f'  <div class="label">your starting baseline</div>\n'
            f'  <div class="body">This is your first analyzed session. Once you upload '
            f'a second swing we\'ll start charting your progression here.</div>\n'
            f'</div>'
        )

    n = len(pts)
    start_pct = int(round(pts[0][0]))
    end_pct   = int(round(pts[-1][0]))
    delta     = end_pct - start_pct
    sign      = "+" if delta >= 0 else "−"

    # Eyebrow uses "N sessions" when not exactly 8, "8-session" otherwise.
    eyebrow_window = f"{n}-session progression"
    label_window   = f"composite change over {n} session" + ("s" if n != 1 else "")

    start_band = _match_band(start_pct)
    end_band   = _match_band(end_pct)
    if start_band == end_band:
        band_phrase = f'staying in the "{end_band}" band'
    elif (start_pct, end_pct) and end_pct > start_pct:
        band_phrase = f'a climb out of the "{start_band}" band into "{end_band}" territory'
    else:
        band_phrase = f'a dip from "{start_band}" into "{end_band}" territory'

    # Top-improvement + next-lever computed only on the SAME analysis window.
    window = history[-n:]
    top = _top_improvement(window)
    nxt = _next_lever(window[-1])
    if top and nxt and top != nxt:
        gain_phrase = (
            f' Biggest contributor: <span class="em">{top}</span>. '
            f'<span class="em">{nxt}</span> is your next lever.'
        )
    elif top:
        gain_phrase = f' Biggest contributor: <span class="em">{top}</span>.'
    elif nxt:
        gain_phrase = f' <span class="em">{nxt}</span> is your next lever.'
    else:
        gain_phrase = ""

    body = (
        f'You started this block at a <span class="em">{start_pct}%</span> match against '
        f'your MLB match; you sit at <span class="em">{end_pct}%</span> after your latest '
        f'session — {band_phrase}.{gain_phrase}'
    )

    return f'''
<div class="ladder-narrative">
  <div class="card-eyebrow">Match score · {eyebrow_window} · vs MLB match</div>
  <div class="num">{sign} <span class="ital">{abs(delta)}</span> pts</div>
  <div class="label">{label_window}</div>
  <div class="body">{body}</div>
</div>'''.strip()


def _build_hero_deck_html(latest: Dict[str, Any], history: List[Dict[str, Any]],
                         ref_name: str, sep_peak_val: str, match_pct: int) -> str:
    """Replaces the hardcoded hero <p class="hero-deck"> with computed copy."""
    n_swings = _swings_this_week(history) or len(history)

    # Compare current sep peak vs all-time best PRIOR to this session (honest PB).
    sep_now_n = _parse_numeric(sep_peak_val) or 0.0
    prior_sep_peaks = [
        _parse_numeric((_find_metric(r, "hip", "shoulder", "sep") or _find_metric(r, "separation") or {}).get("player_str"))
        for r in history[:-1]
    ]
    prior_max = max([v for v in prior_sep_peaks if v is not None], default=None)
    pb_phrase = ""
    if prior_max is not None and sep_now_n > prior_max:
        pb_delta = round(sep_now_n - prior_max, 1)
        if pb_delta >= 0.5:
            pb_phrase = f" — a personal best by {pb_delta:g}°"

    band  = _match_band(match_pct)
    band_phrase = (
        f'firmly in the "<span class="em">{band}</span>" band'
        if band == "strong match" else
        f'in the "<span class="em">{band}</span>" band'
    )

    return (
        f'<p class="hero-deck">Across {n_swings} swing'
        f'{"s" if n_swings != 1 else ""} this week, your peak hip-shoulder '
        f'separation reached <span class="em">{sep_peak_val}</span>{pb_phrase}. '
        f'Your overall match score against <span class="em">{ref_name}</span> is '
        f'<span class="em">{match_pct}%</span>, putting you {band_phrase}.</p>'
    )


def _build_drill_html(latest: Dict[str, Any], ref_last: str) -> str:
    """3 drill cards from latest['drill_plan']. Empty-safe."""
    drill_plan = latest.get("drill_plan") or {}
    drills: List[Dict[str, Any]] = []
    if isinstance(drill_plan, dict):
        for cat, items in drill_plan.items():
            if isinstance(items, list):
                for d in items:
                    if isinstance(d, dict):
                        d2 = dict(d); d2.setdefault("_category", cat); drills.append(d2)
                    elif isinstance(d, str):
                        drills.append({"name": d, "_category": cat})
    elif isinstance(drill_plan, list):
        for d in drill_plan:
            if isinstance(d, dict):
                drills.append(d)
            elif isinstance(d, str):
                drills.append({"name": d})
    drills = drills[:3]

    if not drills:
        return (
            '<div class="coach-grid"><div class="coach-card" style="grid-column:1 / -1; text-align:center;">'
            '<div class="why">▲ No drill prescription yet</div>'
            '<div class="drill">Upload a swing to unlock <span class="ital">today\'s prescription.</span></div>'
            '<p class="body">Once your next swing is analyzed, we\'ll generate a three-drill action plan tied to your top gap categories.</p>'
            '</div></div>'
        )

    cards = []
    for i, d in enumerate(drills, 1):
        name      = (d.get("name") or d.get("title") or "Drill").strip()
        cat       = (d.get("_category") or d.get("category") or "").replace("_", " ").title()
        reps      = (d.get("duration") or d.get("time") or d.get("reps") or "3 sets")
        body      = (d.get("description") or d.get("how_to") or d.get("body")
                     or "Personalized drill prescription from your latest swing analysis.")
        target    = d.get("target") or d.get("goal")
        target_html = (
            f'<div class="target">Target · <span class="v">{target}</span></div>'
            if target else ""
        )
        # split name into "main · ital" if it contains a clear preposition
        name_html = name
        for sep in [" — ", " – ", ": "]:
            if sep in name:
                a, b = name.split(sep, 1)
                name_html = f'{a} <span class="ital">{b}.</span>'
                break

        cards.append(f'''
        <div class="coach-card">
          <div class="num">{i:02d}</div>
          <div class="why">▲ {cat or "Focus area"}</div>
          <div class="drill">{name_html}</div>
          {target_html}
          <p class="body">{body}</p>
          <div class="cta-row">
            <a class="cta" href="#">Open drill →</a>
            <span class="reps">{reps}</span>
          </div>
        </div>'''.strip())

    return '<div class="coach-grid fade-in d11">\n  ' + "\n  ".join(cards) + "\n</div>"


def _build_ledger_html(history: List[Dict[str, Any]]) -> str:
    """5 most-recent session rows."""
    if not history:
        return (
            '<div style="padding:24px; text-align:center; font-family: var(--mono); '
            'font-size: 12px; letter-spacing: 0.10em; color: var(--gray-1);">'
            'No sessions yet · upload your first swing to populate the ledger.</div>'
        )

    # Pre-compute PR flags via high-water-mark walk over the full history.
    pr_ids: set = set()
    high = -1.0
    for r in history:  # oldest → newest
        score = float(_similarity_pct(r) or 0)
        if score > high:
            high = score
            pr_ids.add(id(r))

    rows = []
    for r in reversed(history[-5:]):
        ts = r.get("timestamp") or r.get("created_at")
        date_str = "—"
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = ts
            if dt:
                date_str = dt.strftime("%a · %b %-d")
        except Exception:
            pass

        sw_count = r.get("swing_count") or r.get("num_swings") or 1
        score    = int(round(_similarity_pct(r) or 0))
        grade    = _grade_from_score(score)
        sep_row  = _find_metric(r, "hip", "shoulder", "sep") or _find_metric(r, "separation")
        sep_val  = (sep_row or {}).get("player_str") or "—"
        is_pr    = (id(r) in pr_ids) or bool(r.get("is_pr") or r.get("pr"))
        pr_cls   = " pr" if is_pr else ""
        mood     = "🔥" if score >= 88 else ("⚡" if score >= 82 else ("💪" if score >= 75 else ("🟡" if score >= 65 else "👀")))

        rows.append(
            f'<div class="ledger-row{pr_cls}">'
            f'<span class="date">{date_str}</span>'
            f'<span class="swings">{sw_count} sw</span>'
            f'<span class="top-metric">Match <span class="v">{score}%</span> · sep peak <span class="v">{sep_val}</span></span>'
            f'<span class="grade">{grade}</span>'
            f'<span class="mood">{mood}</span>'
            f'</div>'
        )

    return '<div style="margin-top:4px;">\n  ' + "\n  ".join(rows) + "\n</div>"


def _build_swap_pairs(
    latest: Dict[str, Any],
    history: List[Dict[str, Any]],
    edge_score: int,
    match_pct: int,
    ref_last: str,
    streak: int,
) -> List[Tuple[str, str]]:
    """Build the long list of single-value swaps for the inline numerical updates."""
    pairs: List[Tuple[str, str]] = []

    # ----- Edge Score 6 sub-categories (mock has 91/94/86/89/92/91) -----
    sx = _six_axis_scores(latest)
    pairs += [
        ('<span>MLB match</span><span class="v peak">91</span>',
         f'<span>MLB match</span><span class="v{" peak" if sx["match"] >= 90 else ""}">{sx["match"]}</span>'),
        ('<span>Rotation</span><span class="v peak">94</span>',
         f'<span>Rotation</span><span class="v{" peak" if sx["rotation"] >= 90 else ""}">{sx["rotation"]}</span>'),
        ('<span>Knee drive</span><span class="v">86</span>',
         f'<span>Knee drive</span><span class="v{" peak" if sx["knee"] >= 90 else ""}">{sx["knee"]}</span>'),
        ('<span>Head stability</span><span class="v">89</span>',
         f'<span>Head stability</span><span class="v{" peak" if sx["head"] >= 90 else ""}">{sx["head"]}</span>'),
        ('<span>Timing</span><span class="v">92</span>',
         f'<span>Timing</span><span class="v{" peak" if sx["timing"] >= 90 else ""}">{sx["timing"]}</span>'),
        ('<span>Tempo</span><span class="v peak">91</span>',
         f'<span>Tempo</span><span class="v{" peak" if sx["tempo"] >= 90 else ""}">{sx["tempo"]}</span>'),
    ]

    # ----- Scoreboard 5 cells: real metric values -----
    hip_rot_row = _find_metric(latest, "hip", "rotation", "contact") or _find_metric(latest, "hip rotation")
    sep_row     = _find_metric(latest, "hip", "shoulder", "sep") or _find_metric(latest, "separation")
    launch_row  = _find_metric(latest, "launch") or _find_metric(latest, "contact", "ms")
    knee_row    = _find_metric(latest, "knee", "re-ext") or _find_metric(latest, "knee", "extension")

    if hip_rot_row:
        v = hip_rot_row.get("player_str") or "52°"
        pairs.append(('<div class="value">52° <span class="unit">avg</span></div>',
                      f'<div class="value">{v} <span class="unit">avg</span></div>'))
    if launch_row:
        v = launch_row.get("player_str") or "184 ms"
        # strip "ms" if present, the unit is appended in template
        num = re.sub(r'\s*ms\s*$', '', v.strip())
        pairs.append(('<div class="value">184 <span class="unit">ms</span></div>',
                      f'<div class="value">{num} <span class="unit">ms</span></div>'))
    if sep_row:
        v = sep_row.get("player_str") or "42°"
        pairs.append(('<div class="value">42° <span class="unit">peak</span></div>',
                      f'<div class="value">{v} <span class="unit">peak</span></div>'))
    if knee_row:
        v = knee_row.get("player_str") or "24°"
        pairs.append(('<div class="value">24° <span class="unit">avg</span></div>',
                      f'<div class="value">{v} <span class="unit">avg</span></div>'))

    # ----- Phase Clock numbers (1,124 ms total swing window, 96.9%) -----
    pt = latest.get("phases_t") or {}
    if isinstance(pt.get("load_start"), (int, float)) and isinstance(pt.get("finish"), (int, float)):
        total_ms = int(round((pt["finish"] - pt["load_start"]) * 1000))
        pairs.append(('<div class="v">1,124 ms</div>', f'<div class="v">{total_ms:,} ms</div>'))
        # alignment %  ≈ match score (it's the same underlying measure)
        pairs.append(('<div class="v">96.9%</div>', f'<div class="v">{match_pct}.0%</div>'))
        # The big inner number on the clock dial
        pairs.append(('font-size="22" letter-spacing="-0.02em">1,124</text>',
                      f'font-size="22" letter-spacing="-0.02em">{total_ms:,}</text>'))

    # ----- 12-week middle stats (PR count, deltas) -----
    pr_count   = _personal_records_count(history)
    edge_hist  = _edge_score_series(history)
    edge_delta = (edge_hist[-1] - edge_hist[0]) if len(edge_hist) >= 2 else 0
    match_hist = _match_score_series(history)
    match_delta = (match_hist[-1] - match_hist[0]) if len(match_hist) >= 2 else 0

    pairs += [
        ('<div class="num"><span class="gold">6</span></div>',
         f'<div class="num"><span class="gold">{pr_count}</span></div>'),
        ('<div class="num">+ <span class="gold">29</span></div>',
         f'<div class="num">{"+" if edge_delta >= 0 else "−"} <span class="gold">{abs(int(edge_delta))}</span></div>'),
        ('<div class="num">+ <span class="gold">17</span></div>',
         f'<div class="num">{"+" if match_delta >= 0 else "−"} <span class="gold">{abs(int(match_delta))}</span></div>'),
        # Sub-text under the deltas
        ('59 → 88 · ELITE tier',
         f'{edge_hist[0] if edge_hist else 0} → {edge_hist[-1] if edge_hist else 0}'),
        ('74% → 91% · Mookie Betts',
         f'{match_hist[0] if match_hist else 0}% → {match_hist[-1] if match_hist else 0}%'),
        ('2 unlocked this week',
         f'{streak}-day streak'),
    ]

    # ----- Phase ribbon ms offsets (Swing of the Week) -----
    if pt:
        pairs += [
            ('<span class="ms"><span class="sign">−</span>758</span><span class="name">Load</span>',
             f'<span class="ms">{_format_phase_offset_ms(latest, "load_start")}</span><span class="name">Load</span>'),
            ('<span class="ms"><span class="sign">−</span>262</span><span class="name">Foot plant</span>',
             f'<span class="ms">{_format_phase_offset_ms(latest, "foot_plant")}</span><span class="name">Foot plant</span>'),
            ('<span class="ms"><span class="sign">−</span>91</span><span class="name">Launch</span>',
             f'<span class="ms">{_format_phase_offset_ms(latest, "launch")}</span><span class="name">Launch</span>'),
            ('<span class="ms"><span class="sign">+</span>122</span><span class="name">Peak rot.</span>',
             f'<span class="ms">{_format_phase_offset_ms(latest, "peak_rotation")}</span><span class="name">Peak rot.</span>'),
            ('<span class="ms"><span class="sign">+</span>366</span><span class="name">Finish</span>',
             f'<span class="ms">{_format_phase_offset_ms(latest, "finish")}</span><span class="name">Finish</span>'),
        ]

    # ----- Swing of the Week composite grade -----
    grade = _grade_from_score(match_pct)
    pairs.append(('<div class="num">A−</div>',         f'<div class="num">{grade}</div>'))
    pairs.append(('<div class="card-eyebrow">Reference swing · A-</div>',
                  f'<div class="card-eyebrow">Reference swing · {grade}</div>'))

    # ----- Closest MLB Match: 6 comparable bars come from sx categories -----
    pairs += [
        ('<div class="match-bar-fill" style="width:94%"></div></div>\n          <span class="match-bar-val">94</span>',
         f'<div class="match-bar-fill" style="width:{sx["rotation"]}%"></div></div>\n          <span class="match-bar-val">{sx["rotation"]}</span>'),
        ('<div class="match-bar-fill" style="width:92%"></div></div>\n          <span class="match-bar-val">92</span>',
         f'<div class="match-bar-fill" style="width:{sx["tempo"]}%"></div></div>\n          <span class="match-bar-val">{sx["tempo"]}</span>'),
        ('<div class="match-bar-fill" style="width:88%"></div></div>\n          <span class="match-bar-val">88</span>',
         f'<div class="match-bar-fill" style="width:{sx["rotation"]}%"></div></div>\n          <span class="match-bar-val">{sx["rotation"]}</span>'),
        ('<div class="match-bar-fill" style="width:87%"></div></div>\n          <span class="match-bar-val">87</span>',
         f'<div class="match-bar-fill" style="width:{sx["timing"]}%"></div></div>\n          <span class="match-bar-val">{sx["timing"]}</span>'),
        ('<div class="match-bar-fill" style="width:86%"></div></div>\n          <span class="match-bar-val">86</span>',
         f'<div class="match-bar-fill" style="width:{sx["head"]}%"></div></div>\n          <span class="match-bar-val">{sx["head"]}</span>'),
        ('<div class="match-bar-fill" style="width:74%"></div></div>\n          <span class="match-bar-val">74</span>',
         f'<div class="match-bar-fill" style="width:{sx["knee"]}%"></div></div>\n          <span class="match-bar-val">{sx["knee"]}</span>'),
    ]

    # ----- Match stat pills at bottom of MLB card -----
    pairs.append(('<span>Match score <span class="v gold">91%</span></span>',
                  f'<span>Match score <span class="v gold">{match_pct}%</span></span>'))
    pairs.append(('<span>Considered <span class="v">17 references</span></span>',
                  f'<span>Considered <span class="v">{len(_MLB_META)} references</span></span>'))

    # ----- Form Quadrants 3×3 — 9 sub-metric similarity scores -----
    quads = {
        "SEP PEAK":   _metric_sim(latest, "hip", "shoulder", "sep") or _metric_sim(latest, "separation"),
        "SEP @ FP":   _metric_sim(latest, "sep", "fp") or _metric_sim(latest, "separation", "foot"),
        "SEP @ CON":  _metric_sim(latest, "sep", "contact"),
        "HIP @ FP":   _metric_sim(latest, "hip", "rotation", "fp") or _metric_sim(latest, "hip", "foot"),
        "HIP @ CON":  _metric_sim(latest, "hip", "rotation", "contact"),
        "HIP RANGE":  _metric_sim(latest, "hip", "range") or _metric_sim(latest, "rotation", "range"),
        "KNEE @ FP":  _metric_sim(latest, "knee", "fp") or _metric_sim(latest, "knee", "foot"),
        "KNEE MIN":   _metric_sim(latest, "knee", "min"),
        "RE-EXT":     _metric_sim(latest, "knee", "re-ext") or _metric_sim(latest, "knee", "extension"),
    }
    quad_mock_vals = ["94", "81", "89", "76", "88", "86", "62", "74", "91"]
    quad_keys      = ["SEP PEAK", "SEP @ FP", "SEP @ CON", "HIP @ FP", "HIP @ CON", "HIP RANGE",
                      "KNEE @ FP", "KNEE MIN", "RE-EXT"]
    for key, mock_val in zip(quad_keys, quad_mock_vals):
        new_val = quads[key]
        if new_val and new_val != int(mock_val):
            # Heat class by score
            heat_cls = "heat-3" if new_val >= 80 else "heat-2" if new_val >= 60 else "heat-1" if new_val >= 35 else "heat-0"
            old = f'<span class="n">{key}</span><span class="pct">{mock_val}</span>'
            new = f'<span class="n">{key}</span><span class="pct">{new_val}</span>'
            pairs.append((old, new))

    return pairs


# ---------------------------------------------------------------------------
# Empty state (when user has no swings yet)
# ---------------------------------------------------------------------------

def _render_empty() -> None:
    logo_uri = _logo_data_uri()
    logo_html = (
        f'<img src="{logo_uri}" alt="BarrelLabs" style="width:96px;height:96px;'
        'object-fit:contain;margin:0 auto 28px;display:block;'
        'filter:drop-shadow(0 4px 18px rgba(0,0,0,0.5));">'
        if logo_uri else
        '<div style="font-family:\'Instrument Serif\',Georgia,serif;font-style:italic;'
        'font-size:64px;line-height:1;color:#E8C170;margin-bottom:24px;">⌖</div>'
    )
    st.markdown(
        f"""
        <div style="
            max-width: 720px; margin: 14vh auto; text-align: center;
            font-family: 'Geist', system-ui, sans-serif; color: #F4EFE6;">
          {logo_html}
          <h1 style="font-family: 'Instrument Serif', Georgia, serif; font-weight: 400;
                     font-size: 48px; line-height: 1.05; letter-spacing: -0.02em; margin: 0 0 16px;">
            Your first swing<br><span style="font-style: italic; color: #E8C170;">unlocks everything.</span>
          </h1>
          <p style="font-family: 'Geist', system-ui, sans-serif; font-size: 16px;
                    line-height: 1.55; color: #C8C4BB; max-width: 480px; margin: 0 auto;">
            Drop a side-angle clip and we'll generate your Edge Score,
            closest MLB match, biomechanical radar, and a personalized
            drill plan in under a minute.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def render_dashboard_v3(user: Dict[str, Any]) -> None:
    """Render the Edge mock dashboard, populated with the user's real data."""
    # Hide Streamlit chrome so the page feels like a real app, not a notebook.
    st.markdown(
        """
        <style>
          header[data-testid="stHeader"], [data-testid="stSidebar"],
          [data-testid="stToolbar"], [data-testid="stDecoration"],
          footer { display: none !important; }
          [data-testid="stAppViewContainer"] > .main { padding: 0 !important; }
          .block-container { padding: 0 !important; max-width: 100% !important; }
          body, html, [data-testid="stAppViewContainer"] { background: #0A0B0E !important; }
          iframe { background: #0A0B0E !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    history = _safe_history(user) or []
    latest = history[-1] if history else None

    if not latest:
        _render_empty()
        return

    # ----- Compute real values from the user + latest swing -----
    name = (user.get("name") or "Player").strip()
    first = name.split()[0] if name else "Player"
    initial = (first[:1] or "P").upper()

    edge_score = _compose_edge_score(latest)
    tier_name, next_tier, pts_to_next = _tier_for(edge_score)
    match_pct = int(round(_similarity_pct(latest) or 0))
    streak = _streak_days(history)
    ref_slug = latest.get("picked_slug") or latest.get("reference_name") or "mookie_betts"
    ref_name = _pretty_player_name(ref_slug) or "Mookie Betts"
    ref_last = ref_name.split()[-1] if ref_name else "Betts"   # surname for solo refs
    ref_bio = _ref_bio(ref_slug)
    today_str = datetime.now().strftime("%A · %b %-d · %Y")

    # Optional user profile fields — fall back gracefully when missing.
    handedness   = (user.get("handedness") or user.get("hand") or "").upper() or "—"
    height_str   = user.get("height") or ""
    weight_str   = user.get("weight") or ""
    profile_bits = " · ".join([b for b in [handedness, height_str, weight_str] if b])
    if not profile_bits:
        profile_bits = "Player Report"

    # Real metric values (with safe fallbacks to mock numbers when missing).
    sep_peak_row    = _find_metric(latest, "hip", "shoulder", "sep") or _find_metric(latest, "separation")
    sep_peak_val    = (sep_peak_row or {}).get("player_str") or "42°"
    hip_rot_row     = _find_metric(latest, "hip", "rotation", "contact") or _find_metric(latest, "hip rotation")
    hip_rot_val     = (hip_rot_row or {}).get("player_str") or "52°"
    launch_row      = _find_metric(latest, "launch") or _find_metric(latest, "contact", "ms")
    launch_val      = (launch_row or {}).get("player_str") or "184 ms"
    knee_row        = _find_metric(latest, "knee", "re-ext") or _find_metric(latest, "knee", "extension")
    knee_val        = (knee_row or {}).get("player_str") or "24°"

    # 12-week summary numbers.
    total_swings_12w = _total_swings(history, window_days=84)
    active_days_12w  = _active_days(history, window_days=84)

    # ----- Load template + targeted swaps -----
    html = _load_template_html()
    if not html:
        st.error(
            "dashboard_v3: could not load mock_dashboard_template.py. "
            "Make sure the file exists alongside dashboard_v3.py."
        )
        return

    swaps: List[Tuple[str, str]] = [
        # Logo (real PNG, embedded as base64 data URI for iframe safety)
        ("{{LOGO_DATA_URI}}", _logo_data_uri()),

        # Identity / chrome
        ("Logan Collins", name),
        (">L<", f">{initial}<"),
        ("Sunday · May 17 · 2026", today_str),

        # Issue line metadata — neutralize fake profile until user has one.
        ("Right-handed · 5'11\" · 178 lb", profile_bits),
        # Avoid stale "Volume IV · Issue 23" — tie to streak so it feels real.
        ("Volume IV · Issue 23", f"Vol. {max(1, streak // 7) + 1} · Iss. {max(1, len(history))}"),

        # Solo MLB-surname references that "Mookie Betts" → ref_name doesn't cover.
        ("Betts's compact load",      f"{ref_last}'s compact load"),
        ("Betts's signature delay",   f"{ref_last}'s signature delay"),
        ("almost identical to Betts's signature delay",
                                      f"almost identical to {ref_last}'s signature delay"),
        ("Betts is the cleanest single match",
                                      f"{ref_last} is the cleanest single match"),

        # Hero headline (separation milestone)
        ("hit <span class=\"ital\">42°</span>", f"hit <span class=\"ital\">{sep_peak_val}</span>"),
        # Hero deck — first number reference (peak hip-shoulder sep)
        ("climbed to 42°", f"climbed to {sep_peak_val}"),
        # Streak chip
        (">17-day streak<", f">{streak}-day streak<" if streak else ">First-swing streak<"),

        # Edge Score number
        (">88</div>", f">{edge_score}</div>"),
        # Edge Score tier label
        (">ELITE tier</span>", f">{tier_name.upper()} tier</span>"),
        # Next-tier callout
        ("next tier <span class=\"gold\">Pro</span> at 92 · <span class=\"gold\">+ 4 pts</span>",
         f"next tier <span class=\"gold\">{next_tier}</span> · <span class=\"gold\">+ {pts_to_next} pts</span>"
         if pts_to_next > 0 else
         "<span class=\"gold\">MLB-tier hitter.</span>"),
        # Tier card subtitle
        ("You're 4 Edge points from promotion to PRO",
         (f"You're {pts_to_next} Edge points from promotion to {next_tier.upper()}"
          if pts_to_next > 0 else "Top tier — maintain your form")),
        # Tier card big italic name
        (">Elite</div>", f">{tier_name}</div>"),

        # Match score on hero pill / closest MLB ring
        (">91<span class=\"pct\">%</span>", f">{match_pct}<span class=\"pct\">%</span>"),
        ("91%", f"{match_pct}%"),  # ticker tape & stat pills

        # MLB reference name (multiple spots)
        ("Mookie<br>Betts", ref_name.replace(" ", "<br>", 1)),
        ("Mookie Betts", ref_name),
        ("LAD · RHH · 5'10\" · 180 lb · 4× All-Star", ref_bio or "MLB · 6'0\" · All-Star"),

        # 12 Weeks of Progress summary numerals
        (">214</div>", f">{total_swings_12w}</div>"),
        (">37</div>",  f">{active_days_12w}</div>"),
        (">17</span>", f">{streak}</span>"),

        # Methodology note: insert app-version + user slug for traceability.
        ("v 0.2 ·",
         f"v 0.3-wired · session {user.get('slug', '—')} ·"),
    ]

    # Align the 30-day chart legend with the 2-line generator output.
    swaps.append((
        '<div class="tag"><span class="swatch" style="background:#E8C170"></span>Hip-Sh sep (°)</div>',
        '',
    ))
    swaps.append((
        'Hip rotation (°)',
        'MLB Match (%)',
    ))
    swaps.append((
        'Match score (%)',
        'Edge Score',
    ))

    # Append the broad swap-pair builder — Edge Score categories,
    # scoreboard values, phase clock numbers, 12-week stats, phase ribbon
    # offsets, Closest MLB Match bars, Form Quadrants. All single-line
    # value substitutions that don't risk over-replacing.
    swaps += _build_swap_pairs(
        latest=latest,
        history=history,
        edge_score=edge_score,
        match_pct=match_pct,
        ref_last=ref_last,
        streak=streak,
    )

    for needle, replacement in swaps:
        html = html.replace(needle, replacement)

    # ----- Block-level replacements (multi-line HTML substitution) -----
    # Drill Prescription — replace the entire 3-card grid.
    drill_html = _build_drill_html(latest, ref_last)
    # The mock's drill grid starts at `<div class="coach-grid fade-in d11">`
    # and ends at the matching `</div>` after card #03. We do a regex
    # substitution to avoid having to mirror the entire mock block in code.
    html = re.sub(
        r'<div class="coach-grid fade-in d11">.*?</div>\s*</div>\s*</div>',
        drill_html,
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Session Ledger — the 5 rows inside the standalone ledger card.
    ledger_html = _build_ledger_html(history)
    html = re.sub(
        r'<div style="margin-top:4px;">\s*<div class="ledger-row pr">.*?</div>\s*</div>',
        ledger_html,
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Pricing band — plan-aware: filter tiers above current, swap whole
    # section. Also strips the two radio inputs that live OUTSIDE the
    # section so we re-inject the right pair in the new HTML.
    current_plan = _current_plan_id()
    pricing_html = _build_pricing_band_html(current_plan)
    html = re.sub(
        r'(?:<input[^>]+id="bill-[my]"[^>]*>\s*){0,2}<section class="pricing-band[^"]*"[^>]*>.*?</section>',
        pricing_html,
        html, count=1, flags=re.DOTALL,
    )

    # Hero deck — replace the hardcoded "personal best by 2°… within four
    # degrees of Mookie Betts's…" copy with computed real-data narrative.
    hero_deck_html = _build_hero_deck_html(
        latest=latest, history=history,
        ref_name=ref_name, sep_peak_val=sep_peak_val, match_pct=match_pct,
    )
    html = re.sub(
        r'<p class="hero-deck">Across 42 swings.*?</p>',
        hero_deck_html, html, count=1, flags=re.DOTALL,
    )

    # Velocity Ladder narrative — replace hardcoded "+29 pts / 62% → 91%"
    # copy with computed delta and band-aware phrasing.
    #
    # The regex consumes 3 trailing </div>s (close .body, close .ladder-narrative,
    # close .ladder). The replacement provides a full <div class="ladder-narrative">
    # (which closes itself) plus ONE manual </div> for .ladder. The .card
    # ladder-card close that originally followed in the template is left in place
    # by NOT including it in the match — it stays as the next character in the
    # document. Previously this added TWO manual </div>s, producing one extra
    # close that auto-closed .app and made every section §09-§14 escape .app's
    # padding gutter in production.
    velocity_narrative_html = _build_velocity_narrative_html(history)
    html = re.sub(
        r'<div class="ladder-narrative">.*?</div>\s*</div>\s*</div>',
        velocity_narrative_html + "\n    </div>",
        html, count=1, flags=re.DOTALL,
    )

    # ===== Chart geometry replacements (path generation from history) =====

    # 1) Scoreboard sparklines: 5 cells, each its own SVG. We identify each
    #    by the mock's distinctive endpoint coord/fill_id so the regex is
    #    unambiguous, then swap the entire <svg class="spark"> block.
    match_series   = [int(round(_similarity_pct(r) or 0)) for r in history]
    hip_rot_series = _metric_value_series(history, "hip", "rotation", "contact") or _metric_value_series(history, "hip rotation")
    launch_series  = _metric_value_series(history, "launch") or _metric_value_series(history, "contact", "ms")
    sep_series     = _metric_value_series(history, "hip", "shoulder", "sep") or _metric_value_series(history, "separation")
    knee_series    = _metric_value_series(history, "knee", "re-ext") or _metric_value_series(history, "knee", "extension")

    # Cell 1 — Match score (area + line)
    html = re.sub(
        r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp1".*?</svg>',
        _sparkline_svg(match_series, fill_id="sp1"),
        html, count=1, flags=re.DOTALL,
    )
    # Cell 2 — Hip rotation @ contact (line only)
    html = re.sub(
        r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<path d="M0,24.*?</svg>',
        _sparkline_svg(hip_rot_series, fill_id=None),
        html, count=1, flags=re.DOTALL,
    )
    # Cell 3 — Launch → contact (gold-tinted area + line)
    html = re.sub(
        r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp3".*?</svg>',
        _sparkline_svg(launch_series, fill_id="sp3", fill_color="rgba(232,193,112,0.20)"),
        html, count=1, flags=re.DOTALL,
    )
    # Cell 4 — Hip-Shoulder sep (area + line)
    html = re.sub(
        r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp4".*?</svg>',
        _sparkline_svg(sep_series, fill_id="sp4", fill_color="rgba(244,239,230,0.28)"),
        html, count=1, flags=re.DOTALL,
    )
    # Cell 5 — Knee re-extension (bar chart, last bar gold)
    html = re.sub(
        r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<g fill="rgba\(244,239,230,0\.85\)">.*?</svg>',
        _sparkline_bars_svg(knee_series),
        html, count=1, flags=re.DOTALL,
    )

    # 2) DNA Radar polygon — replace the "You · this wk" polygon (the bone
    #    filled one, not the dashed MLB / peak overlays).
    sx = _six_axis_scores(latest)
    radar_axes = ["rotation", "timing", "knee", "head", "tempo", "match"]
    you_points = _radar_polygon_points(sx, radar_axes, max_radius=118)
    html = re.sub(
        r'<polygon\s+points="0,-118 105,-60 109,63 0,109 -98,57 -106,-61"',
        f'<polygon points="{you_points}"',
        html, count=1,
    )
    # And the vertex dots: place at the same computed points
    dots_old_pattern = (
        r'<g fill="#F4EFE6">\s*'
        r'<circle cx="0"    cy="-118" r="3.5"/>\s*'
        r'<circle cx="105"  cy="-60"  r="3.5"/>\s*'
        r'<circle cx="109"  cy="63"   r="3.5"/>\s*'
        r'<circle cx="0"    cy="109"  r="3.5"/>\s*'
        r'<circle cx="-98"  cy="57"   r="3.5"/>\s*'
        r'<circle cx="-106" cy="-61"  r="3.5"/>\s*'
        r'</g>'
    )
    pts_list = you_points.split()
    dots_new = '<g fill="#F4EFE6">' + "".join(
        f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3.5"/>' for p in pts_list
    ) + '</g>'
    html = re.sub(dots_old_pattern, dots_new, html, count=1, flags=re.DOTALL)

    # 3) Velocity Ladder — replace the 8-bar grid with weekly buckets.
    ladder_html = _velocity_ladder_bars(history)
    html = re.sub(
        r'<div class="ladder-vis"[^>]*>.*?</div>\s*(?=<div class="ladder-narrative">)',
        ladder_html + "\n      ",
        html, count=1, flags=re.DOTALL,
    )

    # 4) Trend charts — both the 30-day "Thirty days in" chart (gradients
    #    named batAreaGrad/barAreaGrad in the template) and the 12-week
    #    progress chart (gradients edgeAreaGrad/matchAreaGrad). Each gets
    #    its own line geometry from history.
    edge_series_all = _edge_score_series(history)
    pr_idx_all: List[int] = []
    high = -1.0
    for i, r in enumerate(history):
        s = float(_similarity_pct(r) or 0)
        if s > high:
            high = s
            pr_idx_all.append(i)

    # 30-day chart: last 30 days only (filter history by timestamp)
    cutoff_30 = datetime.now(timezone.utc) - timedelta(days=30)
    hist_30: List[Dict[str, Any]] = []
    for r in history:
        ts = r.get("timestamp") or r.get("created_at")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt and dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            if dt and dt >= cutoff_30:
                hist_30.append(r)
        except Exception:
            pass
    if not hist_30: hist_30 = history[-10:] if history else []
    edge_30 = _edge_score_series(hist_30) if hist_30 else edge_series_all[-10:]
    match_30 = [int(round(_similarity_pct(r) or 0)) for r in hist_30] if hist_30 else match_series[-10:]
    pr_idx_30 = []; hi30 = -1.0
    for i, r in enumerate(hist_30):
        s = float(_similarity_pct(r) or 0)
        if s > hi30: hi30 = s; pr_idx_30.append(i)
    x_labels_30 = [
        (0,    (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%b %d").upper()),
        (320,  (datetime.now(timezone.utc) - timedelta(days=22)).strftime("%b %d").upper()),
        (640,  (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%b %d").upper()),
        (960,  (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%b %d").upper()),
        (1224, datetime.now(timezone.utc).strftime("%b %d").upper()),
    ]
    trend_30_svg = _trend_chart_svg(
        edge_series=edge_30, match_series=match_30,
        pr_indices=pr_idx_30, x_labels=x_labels_30,
    )
    # 30-day chart's distinctive marker: gradient id "batAreaGrad" inside <defs>
    html = re.sub(
        r'<svg viewBox="0 0 1280 280"[^>]*>\s*<defs>\s*<linearGradient id="batAreaGrad"[^"]*".*?</svg>',
        trend_30_svg,
        html, count=1, flags=re.DOTALL,
    )

    # 12-week chart: full history (or last 12 weeks if larger)
    cutoff_12 = datetime.now(timezone.utc) - timedelta(weeks=12)
    hist_12: List[Dict[str, Any]] = []
    for r in history:
        ts = r.get("timestamp") or r.get("created_at")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
            if dt and dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            if dt and dt >= cutoff_12: hist_12.append(r)
        except Exception:
            pass
    if not hist_12: hist_12 = history
    edge_12 = _edge_score_series(hist_12)
    match_12 = [int(round(_similarity_pct(r) or 0)) for r in hist_12]
    pr_idx_12 = []; hi12 = -1.0
    for i, r in enumerate(hist_12):
        s = float(_similarity_pct(r) or 0)
        if s > hi12: hi12 = s; pr_idx_12.append(i)
    now = datetime.now(timezone.utc)
    x_labels_12 = [
        (0,    (now - timedelta(weeks=12)).strftime("WK 1 · %b %d").upper()),
        (320,  (now - timedelta(weeks=9)).strftime("WK 4 · %b %d").upper()),
        (640,  (now - timedelta(weeks=6)).strftime("WK 7 · %b %d").upper()),
        (960,  (now - timedelta(weeks=3)).strftime("WK 10 · %b %d").upper()),
        (1224, now.strftime("WK 12 · %b %d").upper()),
    ]
    trend_12_svg = _trend_chart_svg(
        edge_series=edge_12, match_series=match_12,
        pr_indices=pr_idx_12, x_labels=x_labels_12,
    )
    html = re.sub(
        r'<svg viewBox="0 0 1280 280"[^>]*>\s*<defs>\s*<linearGradient id="edgeAreaGrad"[^"]*".*?</svg>',
        trend_12_svg,
        html, count=1, flags=re.DOTALL,
    )

    # Render — same height as the mock since structure is preserved.
    components.html(html, height=5800, scrolling=True)
