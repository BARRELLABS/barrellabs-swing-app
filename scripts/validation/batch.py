"""
Batch-process the videos in a validation manifest.

For each manifest entry:
  1. If `fingerprint_path` is given and exists → use it as-is (skip processing).
  2. Else if `video_path` is given and exists → run `detect_phases.py` on the
     video with DETECTOR_V4=true (which also enables PHASE_DEBUG_V1) and
     drop the resulting fingerprint into `<results_dir>/<entry.id>_fingerprint.json`.
  3. Else → skip the swing; the comparator will mark it as missing_fingerprint.

Resilient: a failure on one swing logs the error and continues to the next.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .manifest import Manifest, SwingEntry


@dataclass
class BatchOutcome:
    """One row in the batch-runner report."""
    id: str
    status: str               # "reused" | "processed" | "no_source" | "process_failed"
    fingerprint_path: Optional[str] = None
    error: str = ""


def _resolve_repo_root(start: Path) -> Path:
    """Walk up until we find detect_phases.py (the worktree root)."""
    cur = start.resolve()
    for _ in range(8):
        if (cur / "detect_phases.py").exists():
            return cur
        cur = cur.parent
    raise FileNotFoundError(
        "could not locate detect_phases.py walking up from " + str(start)
    )


def _run_detect_phases(
    repo_root: Path,
    video_path: Path,
    handedness: Optional[str],
    *,
    results_dir: Path,
    swing_id: str,
    python_bin: str,
) -> Path:
    """Invoke `detect_phases.py` and move its outputs into results_dir.

    Returns the path to the moved fingerprint. Raises on subprocess error.
    """
    env = os.environ.copy()
    env["PHASE_DEBUG_V1"] = "true"
    env["DETECTOR_V4"] = "true"

    cmd = [python_bin, "detect_phases.py", str(video_path)]
    if handedness in ("LEFT", "RIGHT"):
        cmd.append(handedness)

    proc = subprocess.run(
        cmd, cwd=repo_root, env=env, capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"detect_phases.py failed (rc={proc.returncode}):\nstderr: {proc.stderr.strip()}"
        )

    # detect_phases.py writes its outputs to PROJECT_ROOT using the video's
    # basename. Move them into results_dir keyed on the swing id so they
    # don't clobber each other across batch entries.
    base = video_path.stem
    src_finger = repo_root / f"{base}_fingerprint.json"
    src_debug = repo_root / f"{base}_phases_debug.json"
    src_v4 = repo_root / f"{base}_detector_v4.json"
    src_chart = repo_root / f"{base}_phases.png"
    src_csv = repo_root / f"{base}_metrics.csv"

    if not src_finger.exists():
        raise RuntimeError(
            f"detect_phases.py did not produce a fingerprint at {src_finger}"
        )

    dst_finger = results_dir / f"{swing_id}_fingerprint.json"
    shutil.move(str(src_finger), str(dst_finger))
    for src, suffix in (
        (src_debug, "_phases_debug.json"),
        (src_v4, "_detector_v4.json"),
        (src_chart, "_phases.png"),
        (src_csv, "_metrics.csv"),
    ):
        if src.exists():
            shutil.move(str(src), str(results_dir / f"{swing_id}{suffix}"))
    return dst_finger


def process_entry(
    entry: SwingEntry,
    *,
    repo_root: Path,
    results_dir: Path,
    python_bin: str,
) -> BatchOutcome:
    """Process one manifest entry.

    Precedence: existing fingerprint_path > already-cached result > run video.
    """
    # 1. Existing fingerprint provided
    if entry.fingerprint_path:
        fp = Path(entry.fingerprint_path)
        if not fp.is_absolute():
            fp = repo_root / fp
        if fp.exists():
            return BatchOutcome(
                id=entry.id, status="reused", fingerprint_path=str(fp),
            )

    # 2. Already cached from a previous batch run
    cached = results_dir / f"{entry.id}_fingerprint.json"
    if cached.exists():
        return BatchOutcome(
            id=entry.id, status="reused", fingerprint_path=str(cached),
        )

    # 3. Process the video
    if entry.video_path:
        vp = Path(entry.video_path)
        if not vp.is_absolute():
            vp = repo_root / vp
        if not vp.exists():
            return BatchOutcome(
                id=entry.id, status="no_source",
                error=f"video_path does not exist: {vp}",
            )
        try:
            finger = _run_detect_phases(
                repo_root, vp, entry.handedness,
                results_dir=results_dir, swing_id=entry.id,
                python_bin=python_bin,
            )
            return BatchOutcome(
                id=entry.id, status="processed", fingerprint_path=str(finger),
            )
        except Exception as e:
            return BatchOutcome(
                id=entry.id, status="process_failed", error=str(e),
            )

    return BatchOutcome(
        id=entry.id, status="no_source",
        error="neither fingerprint_path nor video_path is set",
    )


def run_batch(
    manifest: Manifest,
    *,
    repo_root: Optional[Path] = None,
    results_dir: Optional[Path] = None,
    python_bin: Optional[str] = None,
) -> list[BatchOutcome]:
    """Process every swing in the manifest. Returns one BatchOutcome per entry."""
    if repo_root is None:
        repo_root = _resolve_repo_root(Path(__file__).parent)
    if results_dir is None:
        results_dir = repo_root / "validation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    if python_bin is None:
        python_bin = sys.executable

    outcomes: list[BatchOutcome] = []
    for entry in manifest.swings:
        outcome = process_entry(
            entry, repo_root=repo_root, results_dir=results_dir,
            python_bin=python_bin,
        )
        outcomes.append(outcome)
    return outcomes


def outcomes_summary(outcomes: list[BatchOutcome]) -> str:
    """Plaintext summary suitable for stdout."""
    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
    lines = [f"Batch run: {len(outcomes)} swings"]
    for status, count in sorted(by_status.items()):
        lines.append(f"  {status:<20} {count}")
    errors = [o for o in outcomes if o.status in ("process_failed", "no_source")]
    if errors:
        lines.append("")
        lines.append("Errors:")
        for e in errors:
            lines.append(f"  {e.id}: {e.status} — {e.error}")
    return "\n".join(lines)
