# Visual QA & UI Polish Workflow

Two-role internal loop for catching layout regressions in the v3
"Edge" dashboard without anyone having to scroll-and-screenshot manually.

## Roles

### Role 1 · Critic
Captures the evidence. Renders the dashboard via `dashboard_v3`'s own
swap pipeline (with realistic synthetic history), then
Playwright-screenshots it at **desktop / laptop / tablet / mobile**.

```bash
.venv/bin/python scripts/visual_qa/capture.py
.venv/bin/python scripts/visual_qa/capture.py --plan free       # free-tier upsell
.venv/bin/python scripts/visual_qa/capture.py --label before    # tag the run
```

Output lands at:
```
.visual_qa/screenshots/<YYYY-MM-DD-HHMMSS>[-label]/
    desktop_1600.png       # 1600 × 900,  device scale 2
    laptop_1280.png        # 1280 × 800,  device scale 2
    tablet_900.png         # 900  × 1100, device scale 2
    mobile_430.png         # 430  × 900,  device scale 2
    full_rendered.html     # exact HTML that was screenshotted
    meta.json
```

The reviewer (human or LLM) then opens the screenshots and writes
findings to **`VISUAL_QA_REPORT.md`** at the repo root using the
template documented in that file's header.

### Role 2 · Fixer
Reads `VISUAL_QA_REPORT.md`, applies targeted CSS/markup fixes to
`mock_dashboard_template.py` and/or `dashboard_v3.py`, then:

1. Re-runs the Critic step with `--label after-pass-N`
2. Updates `VISUAL_QA_REPORT.md`: marks resolved issues, records new
   ones, includes the new screenshot references.

The Fixer is bound by these rules (do not redesign):
- Spacing / alignment / responsiveness / numbering / clipping only
- Preserve the current design language (color, typography, layout
  concept, card structure, content hierarchy)
- Production dashboards (`dashboard.py`, `dashboard_v2.py`) untouched
- No data wiring changes

## Why static render?

The live dashboard requires Supabase auth and signed-in state. A
static render via `dashboard_v3._load_template_html()` + the swap
pipeline produces the same HTML the live page would, populated with
realistic synthetic swing history — so screenshots are deterministic
and reproducible across runs.

## Repeatable loop

```bash
# 1. Critic: baseline
python scripts/visual_qa/capture.py --label before
# 2. Reviewer fills in VISUAL_QA_REPORT.md
# 3. Fixer edits mock_dashboard_template.py / dashboard_v3.py
# 4. Critic: after
python scripts/visual_qa/capture.py --label after-pass-1
# 5. Reviewer compares before/after, updates VISUAL_QA_REPORT.md
# 6. Repeat 3–5 until clean
```

The `.visual_qa/` directory is gitignored — screenshots are local
artifacts; only `VISUAL_QA_REPORT.md` ships in commits.
