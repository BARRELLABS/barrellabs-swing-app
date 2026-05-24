"""Prune stale local files so a long-running single-process server doesn't fill
its disk. Uploaded videos + the per-swing analysis artifacts (fingerprint,
phase chart, etc.) are written to local disk; the durable copies live in
Supabase, so the local ones are safe to drop once they're not part of an
in-flight analysis.
"""
from __future__ import annotations

import time
from pathlib import Path

# Generated per-swing artifacts (named from the upload stem). Suffix-scoped so
# committed files (e.g. mlb_match_stats.json, references/*.json) are never hit.
_ARTIFACT_SUFFIXES = (
    "_fingerprint.json", "_phases.png", "_metrics.csv",
    "_signals.json", "_phases_debug.json", "_debug.json",
)


def prune_stale_files(upload_dir, project_root, max_age_hours: float = 2.0) -> int:
    """Delete stale upload videos (everything in ``upload_dir``) and generated
    artifacts (suffix-matched in ``project_root``) older than ``max_age_hours``.
    Files newer than the cutoff are left alone so an in-flight analysis is never
    disturbed. Returns the number removed. Never raises."""
    cutoff = time.time() - max_age_hours * 3600.0
    removed = 0

    def _sweep(directory: Path, match):
        nonlocal removed
        try:
            for p in directory.glob("*"):
                try:
                    if p.is_file() and match(p) and p.stat().st_mtime < cutoff:
                        p.unlink()
                        removed += 1
                except Exception:
                    pass
        except Exception:
            pass

    _sweep(Path(upload_dir), lambda p: True)
    _sweep(Path(project_root), lambda p: p.name.endswith(_ARTIFACT_SUFFIXES))
    return removed
