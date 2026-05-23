"""
BarrelLabs / SwingAI — shared swing metric helpers.

Pure-data helpers extracted from the (now-retired) v2 swing-report
renderer so live code can keep computing key-metric tiles without
depending on the dead renderer module.

Consumers:
    swing_report_dashboard_preview.py  (_flatten_metric_table,
        _find_metric_row, _compute_key_metrics)
    swing_report_v2_pdf.py             (_V2_TILES, _flatten_metric_table,
        _find_metric_row, _parse_value_from_str)

These functions take/return plain dicts and strings only — no Streamlit
or rendering dependencies.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any


def _sparkline_svg(values: List[float], direction: str = "match") -> str:
    """Tiny inline trend chart for a key-metric tile.

    `values` is oldest-→-newest. `direction` controls the line color hint
    (we use red for 'attention' trend, green for 'improving'). For Push 1
    we keep it simple and always red so it visually matches the mockup.
    """
    if not values or len(values) < 2:
        # Render a flat baseline so the tile doesn't look empty.
        return (
            '<svg class="bld2-km-spark" viewBox="0 0 100 28" '
            'preserveAspectRatio="none">'
            '<line x1="0" y1="18" x2="100" y2="18" '
            'stroke="rgba(255,255,255,0.08)" stroke-width="1.5" '
            'stroke-dasharray="2 3"/></svg>'
        )

    n = len(values)
    v_min = min(values)
    v_max = max(values)
    span = (v_max - v_min) or 1.0
    pts = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * 100.0
        # Invert y because SVG origin is top-left; pad 4 each side.
        y = 24 - ((v - v_min) / span) * 20
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    return (
        f'<svg class="bld2-km-spark" viewBox="0 0 100 28" '
        f'preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="#E64530" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{poly}"/>'
        f'</svg>'
    )


# =====================================================================
#                  KEY METRICS COMPUTATION (biomechanics)
# =====================================================================

# Map of (tile_label, [metric_label substrings to match], unit, direction)
# direction:
#   "match"        higher sim_pct = better (used when value itself is unitless)
#   "higher"       higher VALUE = better (more separation = better)
#   "lower"        lower VALUE = better (less drift, faster timing)
_V2_TILES = [
    # (label,                metric_label_match,                       unit,  direction)
    ("HIP ROTATION",         "Hip rotation at contact",                "°",   "match"),
    ("HIP-SHOULDER SEP",     "Peak hip-shoulder separation",           "°",   "higher"),
    ("BAT TIMING",           "Total swing duration",                    "ms",  "lower"),
    ("CONTACT TIMING",       "Launch → contact",                        "ms",  "lower"),
    ("KNEE RE-EXTENSION",    "Re-extension",                            "°",   "higher"),
    ("HEAD STABILITY",       "Total head drift",                        "",    "lower"),
]


def _flatten_metric_table(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten {group: [rows]} → [rows] for label-based lookup."""
    out = []
    mt = record.get("metric_table") or {}
    for group, rows in mt.items():
        for r in rows:
            r2 = dict(r)
            r2["__group"] = group
            out.append(r2)
    return out


def _find_metric_row(rows: List[Dict[str, Any]], needle: str) -> Optional[Dict[str, Any]]:
    needle = (needle or "").lower()
    for r in rows:
        if needle in str(r.get("label", "")).lower():
            return r
    return None


def _parse_value_from_str(s: str) -> Optional[float]:
    """Pull the leading number out of a formatted metric string like '58.3°',
    '152ms', '~3 in', '+1.5°', '-0.4T'. Returns None if no number."""
    if not s:
        return None
    s = str(s).strip().lstrip("+~").replace(",", "")
    # Find first contiguous number (allow leading sign)
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    n = ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            n += ch
        else:
            break
    try:
        return sign * float(n) if n else None
    except ValueError:
        return None


def _compute_key_metrics(record: Dict[str, Any],
                          history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Build the 6-tile key-metrics row. Each tile: {label, value, unit,
    delta_str, delta_class, ref_str, sparkline_svg}."""
    curr_rows = _flatten_metric_table(record)
    # Previous swing's metric_table for delta computation. We look at the
    # most-recent prior swing in history (history is sorted oldest→newest
    # in app.py's flow; defensive sort here just in case).
    prev_rows: List[Dict[str, Any]] = []
    # Also build a sorted-prior history (last 8 swings, current included)
    # so we can pull a per-metric series for the tile sparklines.
    series_records: List[Dict[str, Any]] = []
    if history:
        def _ts(r): return str(r.get("timestamp") or r.get("date") or "")
        sorted_hist = sorted(history, key=_ts)
        # Drop the current record from the tail if it's in history.
        curr_id = record.get("id")
        curr_ts = record.get("timestamp")
        prior = [r for r in sorted_hist
                 if not ((curr_id is not None and r.get("id") == curr_id)
                         or (curr_ts is not None and r.get("timestamp") == curr_ts))]
        if prior:
            prev_rec = prior[-1]
            prev_rows = _flatten_metric_table(prev_rec)
        # Last 7 historical + current = up to 8 points
        series_records = (prior[-7:] if prior else []) + [record]
    else:
        series_records = [record]

    out = []
    for (label, needle, unit_hint, direction) in _V2_TILES:
        curr_row = _find_metric_row(curr_rows, needle)
        if curr_row is None:
            out.append({
                "label": label, "value": "—", "unit": unit_hint,
                "delta_str": "", "delta_class": "flat",
                "ref_str": "", "tooltip": "Metric not available for this swing.",
                "sparkline_svg": _sparkline_svg([], direction),
            })
            continue

        # Sparkline series for this metric across recent history.
        series_vals: List[float] = []
        for rec in series_records:
            rec_rows = _flatten_metric_table(rec)
            rec_row = _find_metric_row(rec_rows, needle)
            if rec_row is None:
                continue
            v = _parse_value_from_str(rec_row.get("player_str", ""))
            if v is not None:
                series_vals.append(v)
        spark_svg = _sparkline_svg(series_vals, direction)

        # Value / ref strings come pre-formatted from analyzer.py — use as-is.
        p_str = str(curr_row.get("player_str") or "—")
        r_str = str(curr_row.get("ref_str") or "")
        # Some labels include the unit in the formatted string already
        # (e.g. "58.3°", "152ms"). For HEAD STABILITY we keep the inches
        # string ("~3 in") whole so we don't have to know the conversion.
        # We strip leading ~ for cleaner display.
        display_val = p_str.lstrip("~+").strip()
        # If the value already carries its unit (most do), don't double-print.
        # Heuristic: if any letter or ° appears in display_val, treat as
        # self-contained and blank the explicit unit chip.
        explicit_unit = ""
        if not any(c.isalpha() or c == "°" for c in display_val):
            explicit_unit = unit_hint

        # Delta vs previous swing
        delta_str = ""
        delta_class = "flat"
        if prev_rows:
            prev_row = _find_metric_row(prev_rows, needle)
            if prev_row is not None:
                p_val = _parse_value_from_str(curr_row.get("player_str", ""))
                v_prev = _parse_value_from_str(prev_row.get("player_str", ""))
                if p_val is not None and v_prev is not None:
                    raw = p_val - v_prev
                    # Tile-specific formatting
                    if abs(raw) < 0.05:
                        delta_str = "± 0"
                        delta_class = "flat"
                    else:
                        sign = "↑" if raw > 0 else "↓"
                        # Determine green/red based on direction
                        if direction == "higher":
                            delta_class = "up" if raw > 0 else "down"
                        elif direction == "lower":
                            delta_class = "up" if raw < 0 else "down"
                        else:  # "match" — use sim_pct trend instead
                            cur_sim = curr_row.get("sim_pct", 0) or 0
                            prv_sim = prev_row.get("sim_pct", 0) or 0
                            delta_class = "up" if cur_sim >= prv_sim else "down"
                        delta_str = f"{sign}{abs(raw):.1f}"

        # Reference subtitle so the player sees what they're tracking toward.
        ref_short = r_str.lstrip("~+").strip()
        ref_label = f"vs {ref_short}" if ref_short else ""

        out.append({
            "label": label,
            "value": display_val,
            "unit": explicit_unit,
            "delta_str": delta_str,
            "delta_class": delta_class,
            "ref_str": ref_label,
            "sparkline_svg": spark_svg,
        })

    return out
