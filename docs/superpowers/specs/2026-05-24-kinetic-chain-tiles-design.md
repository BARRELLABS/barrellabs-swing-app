# Surface X-Factor timing + tempo in the report UI

**Date:** 2026-05-24
**Status:** Approved (design)
**Scope:** On-screen live swing report only. PDF (`swing_report_v2_pdf`) is out of scope.

## Problem

The analyzer already computes two accurate, phone-reliable insights and puts
them in the result dict, but nothing in the report UI shows them:

- `record["tempo_ratio"]` — gather:fire ratio (`load_duration / launch_to_contact`),
  the exact ratio the Timing pillar grades internally (`analyzer.tempo_ratio`).
- `record["xfactor_timing_ms"]` — ms of peak hip-shoulder separation relative to
  contact; **negative = peaks before contact** (elite stretch-then-unwind)
  (`analyzer.xfactor_timing_ms`).

This is the last "safe, no-real-video" item from the 2026-05-24 biomech audit.

## Where

`_render_power_sequence(record)` in `swing_report_dashboard_preview.py` — the
live report's "How your body fired" / **Kinetic Chain** section. This file is
the production renderer (called by `swing_report_page.py:753` with
`is_preview=False`), not just the preview.

The section's CSS grid is **already** `1fr 1fr 1fr` with an unused
`.srd-power-tile-unit` class; only the sequencing tile (spanning all 3 columns)
was ever filled in. We complete the grid with two more tiles.

## Design

Three independent tiles, each: label, value(+unit), good/marginal/poor rating
(border color + coach copy).

### Tile 1 — Sequencing (unchanged behavior)
Existing categorical "Hips lead / Nearly synced / Shoulders fire early".

### Tile 2 — Tempo (gather:fire)
- **Value:** `record["tempo_ratio"]`, e.g. `1.8 : 1`.
- **Rating: reuse the Timing pillar.** Derive good/marginal/poor from
  `record["pillars"]["timing"]` compliance (≥0.66 good, ≥0.33 marginal, else
  poor; confidence ≤ 0 or compliance None → unrated). The pillar already grades
  this exact ratio (good at ratio ≥ 2.0, bracket-dependent floor), so the tile
  can never contradict the Timing bar shown elsewhere in the report.
- **Coach copy** (`_POWER_COPY["tempo_ratio"]`):
  - good: "A real gather into a crisp fire — pro tempo."
  - marginal: "Lengthen the gather (or sharpen the fire) and the barrel jumps."
  - poor: "Rushed — not enough gather before you fire."
  - None: "Need a cleaner side angle to read this."

### Tile 3 — X-Factor Timing
- **Value:** `record["xfactor_timing_ms"]`, shown legibly as `"45 ms early"` /
  `"12 ms late"` (sign mapped to early/late), not a raw signed number.
- **Rating band (Balanced — approved):**
  - good: `ms <= -20` (peaks clearly before contact → unwinds into the ball)
  - marginal: `-20 < ms <= 10` (peaks ~at contact)
  - poor: `ms > 10` (peaks after contact → stuck/late)
  - None → unrated.
- **Coach copy** (`_POWER_COPY["xfactor_timing"]`):
  - good: "Stretch holds, then unwinds into the ball — elite."
  - marginal: "Separation peaks right around contact — a hair earlier adds power."
  - poor: "Separation peaks after contact — you're unwinding late."
  - None: "Need a cleaner side angle to read this."

### Layout / degradation rule
- Collect the tiles that have data (sequencing rating present; `tempo_ratio`
  present; `xfactor_timing_ms` present).
- **0 tiles → return `""`** (section hidden — unchanged today's behavior).
- **1 tile → render it full-width** (`grid-column: 1 / -1`), preserving the
  exact current look for old/sequencing-only records.
- **≥2 tiles → render in the 3-column grid.**
- The bottom **verdict line stays driven by sequencing** (rendered only when
  sequencing is present).

This keeps the "never show a number we can't stand behind" principle: a tile
with no data is omitted, not faked.

## Testing

Extend `tests/test_swing_report_power_sequence.py`:
- Tempo + X-Factor tiles render with correct rating class for representative
  values; Tempo tile rating matches the Timing pillar.
- X-Factor band boundaries (−20 / +10) map to good/marginal/poor.
- X-Factor value formats sign → "early"/"late".
- Section shows with tempo/x-factor present even if sequencing is None.
- Existing five tests stay green (they never set `tempo_ratio`/`xfactor_timing_ms`,
  so behavior there is unchanged).

## Out of scope / follow-up

- PDF export (`swing_report_v2_pdf`) — separate renderer/layout.
- Any change to scoring numerics or frozen-ref comparisons (this is display-only).
