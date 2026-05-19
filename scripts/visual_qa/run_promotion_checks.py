"""Run end-to-end checks after the dashboard-style report promotion.

Verifies:
  1. AST parses cleanly for all changed files (no syntax errors).
  2. The static preview renderer imports + runs end-to-end.
  3. The Compare section appears in the rendered HTML and includes the
     expected "Master Hip Separation" wording (proves the wording tweak
     and the dynamic priority logic both fire).
  4. AppTest navigation smoke suite passes via pytest.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHANGED = [
    "swing_report_dashboard_preview.py",
    "saved_reports_dashboard.py",
    "swing_report_page.py",
    "app.py",
]

print("=" * 60)
print("1. AST PARSE CHECK")
print("=" * 60)
for f in CHANGED:
    path = ROOT / f
    src = path.read_text()
    try:
        ast.parse(src)
        print(f"  OK   {f}")
    except SyntaxError as e:
        print(f"  FAIL {f}: {e}")
        sys.exit(1)

print()
print("=" * 60)
print("2. STATIC RENDER (exercises all builders)")
print("=" * 60)
import os
os.environ["PREVIEW_NO_OPEN"] = "1"
from scripts.visual_qa.render_swing_report_static import render_to_html
out = render_to_html(Path("/tmp/swing_report_preview.html"))
html_size = out.stat().st_size
html_body = out.read_text()
print(f"  Rendered {html_size:,} bytes to {out}")

print()
print("=" * 60)
print("3. CONTENT ASSERTIONS")
print("=" * 60)
checks = [
    ("Compare This Swing", "Compare section header"),
    ("srd-cmp-pair",       "Compare cards (prev vs current)"),
    ("srd-cmp-delta-badge","Center delta badge"),
    ("Master Hip Separation", "Dynamic priority wording"),
    ("Comparison unlocks", None),  # text not expected when SAMPLE_HISTORY non-empty
]
for needle, label in checks:
    present = needle in html_body
    if label is None:
        status = "OK   (not present, as expected)" if not present else "WARN (present, expected absent)"
    else:
        status = "OK  " if present else "FAIL"
    print(f"  {status} '{needle}'  — {label or 'empty-state guard'}")
    if label is not None and not present:
        sys.exit(1)

print()
print("=" * 60)
print("4. APPTEST NAV SMOKE")
print("=" * 60)
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
    print(f"\nPYTEST EXIT: {result.returncode}")
    sys.exit(result.returncode)

print()
print("=" * 60)
print("ALL CHECKS PASSED")
print("=" * 60)
