"""
Render validation results as a human-readable markdown report.

The report has three sections:

  1. Executive summary — headline numbers (v3 vs v4 mean error, % within
     tolerance, stride-style accuracy, head-to-head).
  2. Per-detector metrics — full timing accuracy block for each detector.
  3. Per-swing detail — one row per swing with ground truth, v3/v4
     outputs, errors, and winner.

Designed to be paired with a sibling `summary.json` file (produced by
`compare.summary_as_dict`) for downstream programmatic consumers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .compare import (
    Summary, SwingResult, DetectorMetrics,
    THRESHOLD_FRAMES_TIGHT, THRESHOLD_FRAMES_LOOSE,
)


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _fmt_signed(value: float | int | None, *, unit: str, decimals: int = 1) -> str:
    if value is None:
        return "—"
    fmt = f"{{:+.{decimals}f}}"
    return fmt.format(value) + unit


def _fmt_abs(value: float | int | None, *, unit: str, decimals: int = 1) -> str:
    if value is None:
        return "—"
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value) + unit


def _detector_block(name: str, m: DetectorMetrics) -> str:
    if m.n == 0:
        return f"### {name}\n\n_no scored swings_\n"
    lines = [
        f"### {name}",
        "",
        f"- Swings scored: **{m.n}**",
        f"- Mean absolute error: **{_fmt_abs(m.mean_abs_error_frames, unit=' frames', decimals=2)}** "
        f"({_fmt_abs(m.mean_abs_error_ms, unit=' ms', decimals=1)})",
        f"- Median absolute error: **{_fmt_abs(m.median_abs_error_frames, unit=' frames', decimals=1)}** "
        f"({_fmt_abs(m.median_abs_error_ms, unit=' ms', decimals=1)})",
        f"- Mean signed error: **{_fmt_signed(m.mean_signed_error_frames, unit=' frames', decimals=2)}** "
        f"(positive = picks too LATE)",
        f"- Within ±{THRESHOLD_FRAMES_TIGHT} frames: **{_fmt_pct(m.pct_within_tight)}**",
        f"- Within ±{THRESHOLD_FRAMES_LOOSE} frames: **{_fmt_pct(m.pct_within_loose)}**",
        "",
    ]
    return "\n".join(lines)


def _stride_style_block(summary: Summary) -> str:
    sm = summary.stride_style
    if sm.n_evaluated == 0:
        return "### Stride-style classification\n\n_no swings with stride_style available_\n"
    lines = [
        "### Stride-style classification (v4 / phase_debug)",
        "",
        f"- Swings evaluated: **{sm.n_evaluated}**",
        f"- Overall accuracy: **{_fmt_pct(sm.overall_accuracy)}** "
        f"({sm.n_correct}/{sm.n_evaluated})",
        "",
        "**Per-class accuracy:**",
        "",
    ]
    for cls, acc in sm.per_class_accuracy.items():
        lines.append(f"- `{cls}`: {_fmt_pct(acc)}")

    lines.append("")
    lines.append("**Confusion matrix** (rows = ground truth, columns = predicted):")
    lines.append("")
    classes = sorted({k for k in sm.confusion}
                     | {p for row in sm.confusion.values() for p in row})
    header = "| GT \\ Pred |" + "".join(f" {c} |" for c in classes)
    sep = "|" + "---|" * (len(classes) + 1)
    lines.append(header)
    lines.append(sep)
    for gt in sorted(sm.confusion):
        row = sm.confusion[gt]
        cells = [f" **{row.get(p, 0)}** |" if gt == p else f" {row.get(p, 0)} |"
                 for p in classes]
        lines.append(f"| **{gt}** |" + "".join(cells))
    lines.append("")
    return "\n".join(lines)


def _per_stride_style_block(summary: Summary) -> str:
    lines = ["### v4 timing accuracy by stride style", ""]
    lines.append("| Stride style | N | Mean abs error (frames) | "
                 "Mean abs error (ms) | Within ±3 frames |")
    lines.append("|---|---|---|---|---|")
    for cls, m in summary.per_stride_style.items():
        if m.n == 0:
            lines.append(f"| `{cls}` | 0 | — | — | — |")
            continue
        lines.append(
            f"| `{cls}` | {m.n} | "
            f"{_fmt_abs(m.mean_abs_error_frames, unit='', decimals=2)} | "
            f"{_fmt_abs(m.mean_abs_error_ms, unit='', decimals=1)} | "
            f"{_fmt_pct(m.pct_within_tight)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _per_swing_table(rows: Iterable[SwingResult]) -> str:
    headers = [
        "id", "stride", "status", "gt_plant", "v3", "v4",
        "v3 err (f)", "v4 err (f)", "v3-v4 Δ", "winner", "v4_conf",
    ]
    lines = ["### Per-swing detail", "", "| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        def cell(val, fmt=str, default="—"):
            if val is None:
                return default
            return fmt(val)

        winner = r.winner or "—"
        if winner == "v4":
            winner = "**v4**"
        elif winner == "v3":
            winner = "_v3_"

        lines.append("| " + " | ".join([
            r.id,
            cell(r.gt_stride_style),
            r.status,
            cell(r.gt_final_plant),
            cell(r.v3_foot_plant),
            cell(r.v4_foot_plant),
            cell(r.v3_error_frames, fmt=lambda x: f"{x:+d}"),
            cell(r.v4_error_frames, fmt=lambda x: f"{x:+d}"),
            cell(r.v3_v4_delta_frames, fmt=lambda x: f"{x:+d}"),
            winner,
            cell(r.v4_confidence, fmt=lambda x: f"{x:.2f}"),
        ]) + " |")
    lines.append("")
    return "\n".join(lines)


def _executive_summary(summary: Summary) -> str:
    v3 = summary.v3
    v4 = summary.v4
    h2h = summary.head_to_head
    sm = summary.stride_style

    lines = ["## Executive summary", ""]
    lines.append(f"- Total swings in manifest: **{summary.n_total}**")
    lines.append(f"- Swings fully scored: **{summary.n_scored}**")
    lines.append(f"- Swings skipped: **{summary.n_skipped}** "
                 + (f"({', '.join(f'{k}={v}' for k, v in summary.skipped_by_reason.items())})"
                    if summary.skipped_by_reason else ""))
    lines.append("")

    if v3.n > 0 and v4.n > 0:
        delta_mean_frames = v4.mean_abs_error_frames - v3.mean_abs_error_frames
        verdict = "✓ v4 IS more accurate" if delta_mean_frames < 0 else (
            "✗ v4 is LESS accurate" if delta_mean_frames > 0
            else "= no measurable difference"
        )
        lines.append("**Foot-plant accuracy headline:**")
        lines.append("")
        lines.append(
            f"- v3 mean absolute error: **{_fmt_abs(v3.mean_abs_error_frames, unit=' frames', decimals=2)}** "
            f"({_fmt_abs(v3.mean_abs_error_ms, unit=' ms', decimals=1)})"
        )
        lines.append(
            f"- v4 mean absolute error: **{_fmt_abs(v4.mean_abs_error_frames, unit=' frames', decimals=2)}** "
            f"({_fmt_abs(v4.mean_abs_error_ms, unit=' ms', decimals=1)})"
        )
        lines.append(f"- Improvement (v4 − v3): **{_fmt_signed(delta_mean_frames, unit=' frames')}** "
                     f"→ {verdict}")
        lines.append("")

    if h2h.n > 0:
        lines.append("**Head-to-head:**")
        lines.append("")
        lines.append(f"- v4 wins (closer to ground truth): **{h2h.v4_better}** ({_fmt_pct(h2h.pct_v4_better)})")
        lines.append(f"- v3 wins: **{h2h.v3_better}** ({_fmt_pct(h2h.pct_v3_better)})")
        lines.append(f"- Ties: **{h2h.tie}** ({_fmt_pct(h2h.pct_tie)})")
        lines.append("")

    if sm.n_evaluated > 0:
        lines.append(
            f"**Stride-style accuracy:** {_fmt_pct(sm.overall_accuracy)} "
            f"({sm.n_correct}/{sm.n_evaluated})"
        )
        lines.append("")

    return "\n".join(lines)


def render(
    rows: list[SwingResult],
    summary: Summary,
    *,
    manifest_path: str = "",
    generated_at: str | None = None,
) -> str:
    """Top-level: turn rows + summary into a complete markdown document."""
    generated_at = (
        generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    parts: list[str] = []
    parts.append("# Phase 3 validation report — v3 vs v4 phase detection")
    parts.append("")
    parts.append(f"_Generated {generated_at}._  _Manifest: `{manifest_path or '(in-memory)'}`._")
    parts.append("")
    parts.append(_executive_summary(summary))
    parts.append("## Per-detector metrics")
    parts.append("")
    parts.append(_detector_block("v3 (legacy)", summary.v3))
    parts.append(_detector_block("v4 (toe-tap-aware)", summary.v4))
    parts.append("## Stride-style + per-class breakdown")
    parts.append("")
    parts.append(_stride_style_block(summary))
    parts.append(_per_stride_style_block(summary))
    parts.append(_per_swing_table(rows))
    return "\n".join(parts)
