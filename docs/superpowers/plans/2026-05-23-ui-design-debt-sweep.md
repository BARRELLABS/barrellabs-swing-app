# UI Design-Debt Sweep — Audit + Plan

**Date:** 2026-05-23
**Status:** Proposal — awaiting go-ahead + two design decisions
**Scope audited:** `swing_report.py` (4,324 lines), `historical_charts.py`
(1,368), `bl_theme.py` (314), cross-checked against the editorial pages
(`family_dashboard.py`, `household_picker.py`).

## The core finding

There are **two token vocabularies** in the app and they disagree:

1. **Legacy "iOS-dark"** — `bl_theme.py` defines `--bl-*` tokens: Inter +
   JetBrains Mono, Apple red `#FF3B30`, `#050505` bg, `#fafafa` text. **No gold,
   no serif, no Geist.** Consumed by `historical_charts.py`, `swing_report.py`
   (via a hand-copied mirror), `dashboard*.py`, `saved_reports.py`,
   `development_tracker.py`.
2. **Editorial** — the household pages declare their own `:root`:
   `--bone #F4EFE6`, `--ink #0A0B0E`, `--gold #E8C170`, `--red #E64530`,
   `--fd-serif 'Instrument Serif'`, `--fd-sans 'Geist'`, `--fd-mono 'Geist Mono'`.

Note: `pricing.py` is on **neither** — it hardcodes Tailwind `#ef4444`/white/gray
literals. It is *not* a good reference (the audit briefs that called it
"gold-standard" were wrong; `family_dashboard.py` is the real reference).

Because the legacy pages render via `var(--bl-*)`, **updating `bl_theme.py` once
flips the entire legacy surface to editorial in a single change** — the highest-
leverage move available. The catch: pages that *also* hardcode literals
(`historical_charts.py` has both) would be half-converted, so the token swap
must be paired with a per-page literal sweep.

## Architectural decision (recommended)

Make **`bl_theme.py` the single canonical token source**:

1. Add the editorial canonical names to `:root` as the source of truth:
   `--bone`, `--ink`, `--gold`, `--gold-deep`, `--red`, `--serif`, `--sans`,
   `--mono` (values from `family_dashboard.py` above).
2. **Alias the legacy names to them** so existing pages keep working but now
   render editorial: `--bl-red: var(--red)`, `--bl-bg: var(--ink)`,
   `--bl-ink-100: var(--bone)`, `--bl-sans: var(--sans)`,
   `--bl-mono: var(--mono)`, add `--bl-gold: var(--gold)`,
   `--bl-serif: var(--serif)`.
3. Swap the Google Fonts `@import` from Inter + JetBrains Mono to
   **Geist + Geist Mono + Instrument Serif**.
4. **Export Python color constants** (`BL_RED = "#E64530"`, `BL_GOLD`, `BL_BONE`,
   `BL_INK`, font names) for code that *cannot* read CSS variables — Plotly
   (`historical_charts._style_plotly`), SVG (`swing_report._build_sparkline_svg`),
   and ReportLab PDFs. Kills the duplicated literals at the source.

This is one small file, high blast radius — do it first and visually QA every
page before touching the consumers.

## Two decisions needed from you

1. **Positive / "trending up" color.** The editorial palette has no green, but
   the charts/milestones use green for improvement. Options:
   (a) **gold for positive, red for negative** (tightest, most on-brand —
   recommended); (b) introduce one muted editorial green token. Baseball context
   = improvement is good, so gold reads well as "good."
2. **Plotly secondary trace** (the comparison-metric line). No editorial blue
   exists. Recommend **`--bone-dim #C8C4BB`** (recedes behind the red primary)
   rather than the current off-system `#6cc1ff`.

## The sweep (phased, each phase independently shippable)

### Phase 1 — `bl_theme.py` canonical tokens + Python constants
The architectural change above. Visually QA dashboard, training plan, saved
reports, historical charts, pricing after this lands. ~1–2 hrs.

### Phase 2 — `historical_charts.py`
- Replace the raw `st.dataframe` at line ~1365 ("View Raw Data Table") with a
  custom HTML table matching the existing `.hc-table-wrap` pattern (highest-
  effort single item, ~2 hrs).
- Sweep hardcoded literals → tokens/constants: `#FF3B30`→red, `#FFD479`→gold
  (`#E8C170`), `#46d160`→positive (per decision 1), `#6cc1ff`→secondary (per
  decision 2).
- `_style_plotly()` (line ~639) + trace colors (lines ~992–1058): swap
  hardcoded `"Inter"`/`"JetBrains Mono"` → Geist/Geist Mono via imported
  constants; recolor traces.
- `.hc-title` → `var(--bl-serif)` (Instrument Serif).
- Migrate `.stButton > button` selectors to the editorial `div[class*="st-key-..."]`
  pattern (assign `key=` to the back + quick-open buttons).
- Remove the duplicate routing guard (`app.py` dispatches `historical_charts`
  at both line ~918 and ~5372). ~5–6 hrs total.

### Phase 3 — `swing_report.py`
The CSS architecture (`.swr-*`, token-referencing) is already correct; the debt
is values + fonts + dead code.
- Replace the hand-copied palette mirror (~line 3155) with imports from
  `bl_theme` (the Python constants) — kills the drift risk.
- Sweep ~40 hardcoded semantic-state literals (`#34d399`/`#6ee7b7` green,
  `#fbbf24`/`#f59e0b` amber, `#ff6058`/`#c91e15` red, `rgba(255,59,48,…)`) →
  tokens/constants per decision 1.
- `_build_sparkline_svg()` (lines ~2429–2561): swap `font-family="Inter"`/
  `"JetBrains Mono"` → Geist/Geist Mono; recolor fills via constants.
- Replace the two `st.info()` empty states (lines ~1937, ~2603) with `_md()`
  editorial cards.
- **Delete dead code (~1,300 lines):** the v1 web render body (lines ~2994–3092,
  superseded by `swing_report_v2`), the v1 PDF body (lines ~3141–4324,
  superseded by `swing_report_v2_pdf`), and the orphaned `_render_vs_last()`
  (lines ~2050–2117). Verify against `swing_report_v2*.py` imports first — the
  *data helpers* (`coach_summary`, `swing_progress`, etc.) ARE imported and must
  stay. ~3–4 hrs.

## Sequencing & risk
- Phase 1 is the unlock and the riskiest (touches every page) — land + QA it
  alone before 2/3.
- Phases 2 and 3 are independent of each other.
- Dead-code deletion in Phase 3 should be its own commit, after a grep proves
  the v1 paths are unreachable (`USE_V2_REPORT`/`USE_V2_PDF` both hardcoded
  `True`) and `swing_report_v2*.py` imports only data helpers.
- Verification each phase: Playwright screenshots + the existing snapshot tests +
  visual QA via computer-use.

## Estimate
~12–15 focused hours total, naturally splittable across subagents by phase.
