"""
CLI entry point for the Phase 3 validation workflow.

Usage:

    # Full pipeline: batch-process videos + score against ground truth + write report
    python -m scripts.validation.run_validation \\
        --manifest validation/manifest.json \\
        --results-dir validation/results \\
        --report-dir validation/reports

    # Just score existing fingerprints (skip batch processing)
    python -m scripts.validation.run_validation --no-batch

    # Validate the manifest schema and exit (no processing)
    python -m scripts.validation.run_validation --check

Outputs:
    validation/reports/<UTC-timestamp>-report.md      ← human-readable
    validation/reports/<UTC-timestamp>-summary.json   ← machine-readable aggregate
    validation/reports/<UTC-timestamp>-rows.json      ← per-swing detail
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Make `scripts.validation` importable when run as a module from the repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validation.manifest import load_manifest, ManifestError
from scripts.validation.batch import run_batch, outcomes_summary
from scripts.validation.compare import (
    evaluate_manifest, as_dicts, summary_as_dict,
)
from scripts.validation.report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--manifest", default="validation/manifest.json",
        help="path to manifest JSON (default: validation/manifest.json)",
    )
    parser.add_argument(
        "--results-dir", default="validation/results",
        help="where to store/find per-swing fingerprints",
    )
    parser.add_argument(
        "--report-dir", default="validation/reports",
        help="where to write the report files",
    )
    parser.add_argument(
        "--no-batch", action="store_true",
        help="skip batch video processing; only score existing fingerprints",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="validate the manifest schema and exit",
    )
    parser.add_argument(
        "--python-bin", default=sys.executable,
        help="Python interpreter to use for batch subprocess calls",
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    results_dir = Path(args.results_dir).resolve()
    report_dir = Path(args.report_dir).resolve()

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as e:
        print(f"✗ Manifest error: {e}", file=sys.stderr)
        return 2

    print(f"✓ Manifest loaded: {len(manifest.swings)} swings "
          f"(schema_version={manifest.schema_version})")

    if args.check:
        print("✓ Schema check passed.")
        return 0

    # ----- Step 1: batch process videos (optional) -----
    if not args.no_batch:
        print()
        print("=" * 60)
        print(" BATCH PROCESSING ")
        print("=" * 60)
        outcomes = run_batch(
            manifest,
            results_dir=results_dir,
            python_bin=args.python_bin,
        )
        print(outcomes_summary(outcomes))

    # ----- Step 2: evaluate against ground truth -----
    print()
    print("=" * 60)
    print(" EVALUATION ")
    print("=" * 60)
    rows, summary = evaluate_manifest(manifest, fingerprint_dir=results_dir)
    print(f"Scored {summary.n_scored}/{summary.n_total} swings "
          f"({summary.n_skipped} skipped)")

    # ----- Step 3: write report -----
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md_path = report_dir / f"{ts}-report.md"
    sum_path = report_dir / f"{ts}-summary.json"
    rows_path = report_dir / f"{ts}-rows.json"

    md = render(rows, summary, manifest_path=str(manifest_path))
    md_path.write_text(md + "\n")
    sum_path.write_text(json.dumps(summary_as_dict(summary), indent=2) + "\n")
    rows_path.write_text(json.dumps(as_dicts(rows), indent=2) + "\n")

    print()
    print(f"✓ Report:  {md_path}")
    print(f"✓ Summary: {sum_path}")
    print(f"✓ Rows:    {rows_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
