"""Auto-discovery of video files for the validation labeling tool.

Pure-Python helpers — no Streamlit deps so they're importable from tests
without side effects. The labeling app re-exports them.

The scan-and-import pattern: rather than making the user manually upload
each video, drop video files into one of the scan directories and the
labeling tool auto-creates a manifest entry on launch.
"""

from __future__ import annotations

import os
from pathlib import Path

from scripts.validation.manifest import Manifest, SwingEntry, GroundTruth
from scripts.validation._text_utils import slugify


# Extensions we'll auto-discover. Mac screen recordings sometimes land as
# .mov, .qt, or even .MP4 with uppercase suffix — be generous, OpenCV +
# the labeling tool's auto-transcode handle codec problems downstream.
ACCEPTED_VIDEO_EXTS = (
    "mp4", "mov", "m4v", "mkv", "webm", "avi", "qt", "mts", "ts",
)


def resolve_scan_dirs(
    default_dirs: list[Path],
    *,
    project_root: Path,
    env_var: str = "LABELING_VIDEO_DIRS",
    env: dict | None = None,
) -> list[Path]:
    """Return absolute paths to every directory that should be scanned for
    videos. Honors the given env var (colon-separated paths) in addition
    to ``default_dirs``. Order is preserved; later duplicates dropped."""
    env = env if env is not None else os.environ
    paths = list(default_dirs)
    extra = str(env.get(env_var, "")).strip()
    if extra:
        for p in extra.split(":"):
            p = p.strip()
            if not p:
                continue
            pp = Path(p).expanduser()
            if not pp.is_absolute():
                pp = (project_root / pp).resolve()
            paths.append(pp)
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            rp = p.resolve()
        except OSError:
            continue
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def discover_videos(scan_dirs: list[Path]) -> list[Path]:
    """Find all video files in scan_dirs. Returns absolute paths, sorted."""
    found: list[Path] = []
    seen: set[Path] = set()
    for d in scan_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for ext in ACCEPTED_VIDEO_EXTS:
            for pattern in (f"*.{ext}", f"*.{ext.upper()}"):
                for p in d.glob(pattern):
                    if not p.is_file():
                        continue
                    rp = p.resolve()
                    if rp in seen:
                        continue
                    seen.add(rp)
                    found.append(rp)
    return sorted(found)


def auto_import_videos(
    manifest: Manifest,
    scan_dirs: list[Path],
    *,
    project_root: Path,
) -> int:
    """For every discovered video not already bound to a manifest entry,
    append a fresh entry with sensible defaults. Returns number of new
    entries added.

    Defaults for a freshly-imported entry:
      - stride_style: "standard_stride"  (refine while labeling)
      - camera_view:  "profile"
      - real_time:    True
      - handedness:   None (auto-detect at analysis time)
      - final_plant_frame / contact_frame: None (awaiting label)

    Existing manifest entries are never mutated. If a discovered video is
    already pointed at by some entry's video_path, it's skipped.
    """
    bound: set[Path] = set()
    for s in manifest.swings:
        if not s.video_path:
            continue
        p = Path(s.video_path)
        if not p.is_absolute():
            p = project_root / p
        if p.exists():
            try:
                bound.add(p.resolve())
            except OSError:
                pass

    used_ids = {s.id for s in manifest.swings}
    n_added = 0
    for video in discover_videos(scan_dirs):
        if video in bound:
            continue
        base_id = slugify(video.stem)
        sid = base_id
        i = 2
        while sid in used_ids:
            sid = f"{base_id}_{i}"
            i += 1
        used_ids.add(sid)
        # Store relative paths when the video lives inside the repo
        try:
            rel = video.relative_to(project_root)
            video_path_str = str(rel)
        except ValueError:
            video_path_str = str(video)
        manifest.swings.append(SwingEntry(
            id=sid,
            video_path=video_path_str,
            fingerprint_path=None,
            handedness=None,
            ground_truth=GroundTruth(
                stride_style="standard_stride",
                final_plant_frame=None,
                contact_frame=None,
                rotation_onset_frame=None,
                camera_view="profile",
                real_time=True,
            ),
            notes=f"auto-imported from {video.parent.name}/",
        ))
        n_added += 1
    return n_added
