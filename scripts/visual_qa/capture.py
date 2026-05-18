"""
BarrelLabs Visual QA · Capture (Role 1 of the QA workflow)
============================================================

Renders the v3 "Edge" dashboard to a static HTML file (using
dashboard_v3's own swap + block-replacement pipeline with synthetic
swing history), then Playwright-screenshots it at 4 standard widths.

This is the **Critic** half of the loop: it produces the evidence
(screenshots) the report writer reviews.

Usage
-----
    .venv/bin/python scripts/visual_qa/capture.py
    .venv/bin/python scripts/visual_qa/capture.py --plan free   # FREE-tier upsell
    .venv/bin/python scripts/visual_qa/capture.py --label after # tag the run

Output
------
    .visual_qa/screenshots/<YYYY-MM-DD-HHMM>-<label>/
        desktop_1600.png
        laptop_1280.png
        tablet_900.png
        mobile_430.png
        full_rendered.html         # the exact HTML that was screenshotted
        meta.json                  # viewport sizes, plan, timestamp
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

VIEWPORTS = [
    ("desktop", 1600, 900),
    ("laptop",  1280, 800),
    ("tablet",  900,  1100),
    ("mobile",  430,  900),
]


# ---------------------------------------------------------------------------
# Synthetic-but-realistic history so the dashboard renders fully populated.
# Mirrors the production record shape (`metric_table` as dict-of-lists,
# `phases_t`, `drill_plan`, etc.) — see player_storage._swing_row_to_legacy.
# ---------------------------------------------------------------------------

def _mk_record(score: float, days_ago: int, *,
               sep: float = 42.0, hip_rot: float = 52.0,
               launch_ms: float = 184.0, knee_ext: float = 24.0) -> Dict[str, Any]:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "score": score,
        "timestamp": ts,
        "reference_name": "mookie_betts",
        "metric_table": {
            "Rotation": [
                {"label": "Peak hip-shoulder separation",
                 "sim_pct": score - 2, "player_str": f"{sep:g}°", "ref_str": "44°"},
                {"label": "Hip rotation at contact",
                 "sim_pct": score,     "player_str": f"{hip_rot:g}°", "ref_str": "54°"},
                {"label": "Hip rotation at FP",
                 "sim_pct": score - 4, "player_str": f"{hip_rot - 16:g}°", "ref_str": "38°"},
            ],
            "Timing": [
                {"label": "Launch to contact ms",
                 "sim_pct": score - 3, "player_str": f"{launch_ms:g} ms", "ref_str": "175 ms"},
                {"label": "Total swing duration",
                 "sim_pct": score - 1, "player_str": "1,124 ms", "ref_str": "1,160 ms"},
            ],
            "Front Knee": [
                {"label": "Knee re-extension",
                 "sim_pct": score - 8, "player_str": f"{knee_ext:g}°", "ref_str": "28°"},
                {"label": "Knee angle at FP",
                 "sim_pct": score - 12, "player_str": "112°", "ref_str": "118°"},
                {"label": "Knee min angle",
                 "sim_pct": score - 10, "player_str": "88°",  "ref_str": "92°"},
            ],
            "Head": [
                {"label": "Head total drift",
                 "sim_pct": score - 6, "player_str": "0.18", "ref_str": "0.15"},
            ],
        },
        "drill_plan": {
            "hip_rotation": [{
                "name": "Walking stride hip-leads",
                "duration": "3 × 6 reps",
                "target": "≥ 42° for 5 of 8 reps",
                "description": ("Walk into a slow stride and stall at foot plant for "
                                "a half-second before launching."),
            }],
            "knee_drive": [{
                "name": "Overload / underload set",
                "duration": "3 full rounds",
                "target": "knee re-ext ≥ 90 by next session",
                "description": ("2 swings with a +6oz weighted bat, 2 with a −6oz "
                                "speed bat, 2 game bats."),
            }],
            "bat_path": [{
                "name": "Early hand-set tee work",
                "duration": "3 × 8 swings",
                "target": "barrel tips toward ball before front foot lands",
                "description": ("Set the tee middle-up. Cock your hands to "
                                "launch-position before the leg lift starts."),
            }],
        },
        "phases_t": {
            "load_start": 0.04, "foot_plant": 0.50, "launch": 0.71,
            "contact": 0.80, "peak_rotation": 0.92, "finish": 1.16,
        },
    }


def _synthetic_history(n: int = 16) -> List[Dict[str, Any]]:
    """16-session climb from a B− match score to A territory."""
    out = []
    for i in range(n):
        days = (n - 1 - i) * 5
        score = 60.0 + i * 2.0
        sep   = 32.0 + i * 0.7
        out.append(_mk_record(score, days, sep=sep))
    return out


# ---------------------------------------------------------------------------
# Render the dashboard via dashboard_v3's pipeline, save HTML to disk
# ---------------------------------------------------------------------------

def _render_static(plan_id: str, output_html: Path) -> None:
    """Drive dashboard_v3's swap pipeline into a static HTML file."""
    import dashboard_v3 as v3

    history = _synthetic_history()
    latest  = history[-1]
    name    = "Logan Collins"
    ref_last = "Betts"
    ref_name = "Mookie Betts"
    edge_score = v3._compose_edge_score(latest)
    match_pct  = int(round(v3._similarity_pct(latest) or 0))
    streak     = v3._streak_days(history)

    html = v3._load_template_html()

    # Single-value swaps (replicate render_dashboard_v3)
    today_str = datetime.now().strftime("%A · %b %-d · %Y")
    swaps = [
        ("{{LOGO_DATA_URI}}", v3._logo_data_uri()),
        ("Logan Collins", name),
        (">L<", f">{name[0].upper()}<"),
        ("Sunday · May 17 · 2026", today_str),
        ("Right-handed · 5'11\" · 178 lb", "Player Report"),
        ("Volume IV · Issue 23", f"Vol. 4 · Iss. {len(history)}"),
        ("Betts's compact load", f"{ref_last}'s compact load"),
        ("Betts's signature delay", f"{ref_last}'s signature delay"),
        ("Betts is the cleanest single match", f"{ref_last} is the cleanest single match"),
        (">17-day streak<", f">{streak}-day streak<"),
        (">88</div>", f">{edge_score}</div>"),
    ] + v3._build_swap_pairs(latest, history, edge_score, match_pct, ref_last, streak)

    for needle, replacement in swaps:
        html = html.replace(needle, replacement)

    # Block-level replacements (regex)
    html = re.sub(
        r'(?:<input[^>]+id="bill-[my]"[^>]*>\s*){0,2}<section class="pricing-band[^"]*"[^>]*>.*?</section>',
        v3._build_pricing_band_html(plan_id), html, count=1, flags=re.DOTALL,
    )
    html = re.sub(
        r'<p class="hero-deck">Across 42 swings.*?</p>',
        v3._build_hero_deck_html(latest, history, ref_name, "42°", match_pct),
        html, count=1, flags=re.DOTALL,
    )
    # Mirrors the fix in dashboard_v3.py: regex consumes close-body +
    # close-narrative + close-ladder; replacement provides a self-closed
    # narrative div + ONE manual </div> for .ladder. The .card close that
    # follows in the template remains in place. Two manual closes here would
    # auto-close .app and break the gutter for sections §09-§14.
    html = re.sub(
        r'<div class="ladder-narrative">.*?</div>\s*</div>\s*</div>',
        v3._build_velocity_narrative_html(history) + "\n    </div>",
        html, count=1, flags=re.DOTALL,
    )
    html = re.sub(
        r'<div class="coach-grid fade-in d11">.*?</div>\s*</div>\s*</div>',
        v3._build_drill_html(latest, ref_last), html, count=1, flags=re.DOTALL,
    )
    html = re.sub(
        r'<div style="margin-top:4px;">\s*<div class="ledger-row pr">.*?</div>\s*</div>',
        v3._build_ledger_html(history), html, count=1, flags=re.DOTALL,
    )

    # Chart geometry
    ms = [int(round(v3._similarity_pct(r) or 0)) for r in history]
    hr = v3._metric_value_series(history, "hip", "rotation", "contact")
    lc = v3._metric_value_series(history, "launch")
    sp = v3._metric_value_series(history, "hip", "shoulder", "sep")
    kn = v3._metric_value_series(history, "knee", "re-ext") or v3._metric_value_series(history, "knee", "extension")
    html = re.sub(r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp1".*?</svg>',
                  v3._sparkline_svg(ms, fill_id="sp1"), html, count=1, flags=re.DOTALL)
    html = re.sub(r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<path d="M0,24.*?</svg>',
                  v3._sparkline_svg(hr, fill_id=None), html, count=1, flags=re.DOTALL)
    html = re.sub(r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp3".*?</svg>',
                  v3._sparkline_svg(lc, fill_id="sp3", fill_color="rgba(232,193,112,0.20)"),
                  html, count=1, flags=re.DOTALL)
    html = re.sub(r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<defs><linearGradient id="sp4".*?</svg>',
                  v3._sparkline_svg(sp, fill_id="sp4", fill_color="rgba(244,239,230,0.28)"),
                  html, count=1, flags=re.DOTALL)
    html = re.sub(r'<svg class="spark" viewBox="0 0 200 40"[^>]*>\s*<g fill="rgba\(244,239,230,0\.85\)">.*?</svg>',
                  v3._sparkline_bars_svg(kn), html, count=1, flags=re.DOTALL)
    sx = v3._six_axis_scores(latest)
    pts = v3._radar_polygon_points(sx, ["rotation","timing","knee","head","tempo","match"], max_radius=118)
    html = re.sub(r'<polygon\s+points="0,-118 105,-60 109,63 0,109 -98,57 -106,-61"',
                  f'<polygon points="{pts}"', html, count=1)
    html = re.sub(r'<div class="ladder-vis"[^>]*>.*?</div>\s*(?=<div class="ladder-narrative">)',
                  v3._velocity_ladder_bars(history) + "\n      ",
                  html, count=1, flags=re.DOTALL)

    output_html.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Playwright capture
# ---------------------------------------------------------------------------

async def _capture_all(html_path: Path, out_dir: Path) -> List[Dict[str, Any]]:
    """Screenshot the page at each viewport.

    NOTE: We intentionally use device_scale_factor=1 (not 2). The combo of
    `full_page=True` + `device_scale_factor=2` produces a PNG that is 2x
    taller than the real rendered content — leaving a 50% blank tail on
    tall pages like ours. 1x DPR + full_page=True gives an accurate
    screenshot. The trade-off (less crisp text) is acceptable for layout
    QA where we care about composition, not pixel-perfect type rendering.
    """
    from playwright.async_api import async_playwright
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for name, w, h in VIEWPORTS:
            ctx = await browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=1,
            )
            page = await ctx.new_page()
            await page.goto(f"file://{html_path}", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            real_h = await page.evaluate(
                "() => Math.max(document.documentElement.scrollHeight, "
                "document.body.scrollHeight)"
            )
            out = out_dir / f"{name}_{w}.png"
            await page.screenshot(path=str(out), full_page=True)
            size = out.stat().st_size
            results.append({"viewport": name, "width": w, "height": h,
                            "rendered_height": int(real_h),
                            "file": out.name, "bytes": size})
            print(f"  ✓ {name:7s} {w}x{h} (rendered h={int(real_h)}): "
                  f"{out.name} ({size/1024:,.0f} KB)")
            await ctx.close()
        await browser.close()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", default="free",
                   choices=["free", "solo_pro", "family_pro", "coach_pro"],
                   help="Which subscription plan to simulate (affects the upsell band).")
    p.add_argument("--label", default="",
                   help="Suffix for the run directory name (e.g. 'before' or 'after-fix-N').")
    args = p.parse_args()

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    run_name = f"{stamp}-{args.label}" if args.label else stamp
    out_dir = REPO_ROOT / ".visual_qa" / "screenshots" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Visual QA capture · plan={args.plan} · run={run_name}")
    print(f"  → {out_dir}\n")

    html_path = out_dir / "full_rendered.html"
    print(f"  rendering static HTML → {html_path.name}")
    _render_static(args.plan, html_path)
    print(f"  rendered: {html_path.stat().st_size / 1024:,.0f} KB\n")

    print(f"  Playwright capturing {len(VIEWPORTS)} viewports:")
    results = asyncio.run(_capture_all(html_path, out_dir))

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan": args.plan,
        "label": args.label,
        "html_file": html_path.name,
        "viewports": results,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\n  meta.json saved\n  done.\n")
    print(f"Reviewer: open the PNGs and write findings into")
    print(f"  {REPO_ROOT / 'VISUAL_QA_REPORT.md'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
