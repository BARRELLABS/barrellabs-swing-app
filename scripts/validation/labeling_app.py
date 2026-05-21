"""
Streamlit labeling tool for the validation manifest.

Lets a hitting coach step through a video frame-by-frame and mark:
  - final_plant_frame   (the frame where the front foot finally settles
                         before rotation begins — NOT the toe-tap moment)
  - contact_frame       (the frame where the bat appears to meet the ball)
  - rotation_onset_frame (optional)
  - stride_style        (no_stride | standard_stride | toe_tap | leg_kick)
  - camera_view         (profile | three_quarter | front)
  - real_time           (false if this is slow-motion playback)

Saves directly back into `validation/manifest.json`. Atomic write to a
temp file followed by a rename, so a crash mid-save can't corrupt the
file.

Launch:
    streamlit run scripts/validation/labeling_app.py
"""

from __future__ import annotations

import sys
import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import cv2
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validation.manifest import (  # noqa: E402
    load_manifest, write_manifest, Manifest, SwingEntry, GroundTruth,
    VALID_STRIDE_STYLES, VALID_CAMERA_VIEWS,
)
from scripts.validation._text_utils import slugify  # noqa: E402
from scripts.validation._video_discovery import (  # noqa: E402
    ACCEPTED_VIDEO_EXTS,
    resolve_scan_dirs as _resolve_scan_dirs_impl,
    discover_videos as _discover_videos_impl,
    auto_import_videos as _auto_import_videos_impl,
)

MANIFEST_PATH = PROJECT_ROOT / "validation" / "manifest.json"
VIDEOS_DIR = PROJECT_ROOT / "validation" / "videos"

# Directories scanned at startup for videos to auto-import into the manifest.
# Order matters: earlier paths win on filename collisions.
#
# You can add custom paths by setting the LABELING_VIDEO_DIRS env var to a
# colon-separated list of absolute or repo-relative paths, e.g.:
#   LABELING_VIDEO_DIRS=~/Movies/swings:/tmp/clips python3 -m streamlit run ...
DEFAULT_SCAN_DIRS = [
    VIDEOS_DIR,
    PROJECT_ROOT / "uploads_streamlit",
]


def _resolve_scan_dirs() -> list[Path]:
    return _resolve_scan_dirs_impl(DEFAULT_SCAN_DIRS, project_root=PROJECT_ROOT)


def _auto_import_videos(manifest: Manifest, scan_dirs: list[Path]) -> int:
    return _auto_import_videos_impl(
        manifest, scan_dirs, project_root=PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------


def _try_transcode(src: Path, dst: Path) -> tuple[bool, str]:
    """Re-encode `src` to H.264 MP4 at `dst` using the system ffmpeg.

    Returns (success, message). On success, `dst` exists and contains a
    decodable MP4. On failure, the message tells the user what to do
    next (install ffmpeg, run manually, etc.).
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found on PATH. Install it (`brew install ffmpeg`)."
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [
                ffmpeg, "-y", "-i", str(src),
                "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",                # drop audio — we only need video frames
                str(dst),
            ],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out after 10 minutes."
    except Exception as e:  # noqa: BLE001
        return False, f"ffmpeg subprocess error: {e!r}"
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        tail = proc.stderr.strip().splitlines()[-5:] if proc.stderr else []
        return False, "ffmpeg failed:\n" + "\n".join(tail)
    return True, "ok"


@st.cache_resource(show_spinner=False)
def _open_video(path_str: str, _mtime: float = 0.0):
    """Open a video. Cached so reruns don't reopen the file.

    The `_mtime` arg is a cache buster — when the file at path_str is
    overwritten (e.g. the user re-uploads under the same id), the cache
    key changes and OpenCV reopens the new bytes.

    Returns (capture_handle, n_frames, fps) — or (None, 0, 0) on failure.
    """
    cap = cv2.VideoCapture(path_str)
    if not cap.isOpened():
        return None, 0, 0.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    return cap, n_frames, fps


def _read_frame(cap, frame_idx: int):
    """Seek + decode a single frame; return RGB numpy or None."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame_bgr = cap.read()
    if not ok or frame_bgr is None:
        return None
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def _resolve_video(rel_or_abs: Optional[str]) -> Optional[Path]:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p if p.exists() else None


def _save_manifest_atomic(manifest: Manifest, path: Path) -> None:
    """Write to a temp file in the same directory, then rename. Avoids
    corrupted manifests if the process is killed mid-save."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".manifest.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        write_manifest(manifest, tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


st.set_page_config(
    page_title="Swing Labeling Tool",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Swing Labeling Tool")
st.caption("Mark `final_plant_frame`, `contact_frame`, and `stride_style` on "
           "each swing in `validation/manifest.json`. Save persists directly "
           "to disk.")

# ---- Load manifest ----
if not MANIFEST_PATH.exists():
    st.error(f"Manifest not found at `{MANIFEST_PATH}`. Create it first.")
    st.stop()

try:
    manifest = load_manifest(MANIFEST_PATH)
except Exception as e:
    st.error(f"Failed to load manifest: {e!r}")
    st.stop()

# ---- Auto-discover + import videos sitting in scan paths ----
# Anything in validation/videos/ or uploads_streamlit/ (or in $LABELING_VIDEO_DIRS)
# that isn't yet bound to a manifest entry gets appended as a fresh entry on
# every app launch. Saves to disk atomically. Idempotent — re-running finds
# nothing new to import.
_scan_dirs = _resolve_scan_dirs()
try:
    _n_imported = _auto_import_videos(manifest, _scan_dirs)
    if _n_imported > 0:
        _save_manifest_atomic(manifest, MANIFEST_PATH)
        st.toast(f"Auto-imported {_n_imported} new video(s) from scan paths",
                 icon="🎬")
except Exception as e:
    st.warning(f"Auto-import failed (continuing anyway): {e!r}")

# Partition swings into "labelable" (has usable video) and "skipped"
labelable: list[tuple[SwingEntry, Path]] = []
without_video: list[SwingEntry] = []
for entry in manifest.swings:
    video = _resolve_video(entry.video_path)
    if video:
        labelable.append((entry, video))
    else:
        without_video.append(entry)


# ---- If no labelable swings, show the empty-state guide BEFORE the upload form ----
if not labelable:
    st.warning("No videos found in scan paths yet.")
    st.markdown(
        "**To start labeling, drop video files into any of these folders "
        "and refresh:**"
    )
    for d in _scan_dirs:
        exists = "✓ exists" if d.exists() else "✗ does not exist yet"
        rel = d
        try:
            rel = d.relative_to(PROJECT_ROOT)
        except ValueError:
            pass
        st.markdown(f"- `{rel}` ({exists})")
    st.caption(
        "Accepted formats: MP4, MOV, M4V, MKV. To add a custom scan path, "
        "restart with `LABELING_VIDEO_DIRS=/your/path python3 -m streamlit "
        "run scripts/validation/labeling_app.py`."
    )
    st.divider()


# ---- Upload form: in-UI video → manifest entry (FALLBACK) ----
# When videos are auto-discovered the scan workflow is preferred. This form
# stays available collapsed for one-off uploads from outside scan paths.
with st.expander(
    "➕ Or upload a single video from your machine",
    expanded=False,
):
    st.caption(
        "Upload an MP4/MOV. The video is saved under `validation/videos/` "
        "and a matching entry is appended to `validation/manifest.json`. "
        "If you reuse the ID of an existing unlabeled entry, the video is "
        "bound to that entry instead of creating a duplicate."
    )
    with st.form("upload_swing_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "Video file",
            type=None,  # accept any file — browser pickers can be flaky
                         # about uppercase extensions and Mac screen-recording
                         # MIME types. We validate the bytes after upload.
            help=(
                "Any video file (MP4, MOV, M4V, MKV, etc.). Streamlit's "
                "default upload size limit is 200 MB; for larger files, "
                "restart with `--server.maxUploadSize=4096` (MB). Or just "
                "drop videos straight into `validation/videos/` — no upload "
                "needed."
            ),
        )
        # Suggest a default id from the filename if one was uploaded
        default_id = ""
        if uploaded is not None:
            default_id = slugify(Path(uploaded.name).stem)
        cols_u = st.columns([2, 1])
        with cols_u[0]:
            new_id = st.text_input(
                "Swing ID",
                value=default_id,
                help=(
                    "Letters, numbers, underscores. Reusing an existing ID "
                    "binds the video to that entry. Otherwise creates a new entry."
                ),
            )
        with cols_u[1]:
            new_handedness = st.radio(
                "Handedness",
                ["AUTO", "RIGHT", "LEFT"],
                horizontal=True,
                help="AUTO lets detect_phases.py decide.",
            )
        cols_u2 = st.columns([1, 1, 1])
        with cols_u2[0]:
            new_stride_guess = st.radio(
                "Initial stride_style guess",
                VALID_STRIDE_STYLES,
                help="Refine while labeling. Just an initial value.",
            )
        with cols_u2[1]:
            new_camera_guess = st.radio(
                "Camera view", VALID_CAMERA_VIEWS,
            )
        with cols_u2[2]:
            new_realtime_guess = st.checkbox(
                "Real-time playback", value=True,
                help="Uncheck if this is a slow-motion clip.",
            )
        new_notes = st.text_area(
            "Notes (optional)", value="", height=68,
        )
        submitted = st.form_submit_button(
            "💾  Save video + add to manifest",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if uploaded is None:
            st.error("Pick a video file first.")
        elif not new_id.strip():
            st.error("Swing ID is required.")
        else:
            cleaned_id = slugify(new_id)
            ext = Path(uploaded.name).suffix.lstrip(".").lower() or "mp4"
            if ext not in ACCEPTED_VIDEO_EXTS:
                ext = "mp4"
            VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            target_video = VIDEOS_DIR / f"{cleaned_id}.{ext}"
            try:
                target_video.write_bytes(uploaded.getvalue())
            except Exception as e:
                st.error(f"Failed to save video bytes: {e!r}")
            else:
                rel_video_path = str(target_video.relative_to(PROJECT_ROOT))
                existing = next(
                    (s for s in manifest.swings if s.id == cleaned_id), None,
                )
                hand_to_save = (
                    None if new_handedness == "AUTO" else new_handedness
                )
                if existing is not None:
                    # Bind to existing entry; don't overwrite ground-truth frame
                    # numbers (those come from the labeling pass).
                    if _resolve_video(existing.video_path):
                        st.warning(
                            f"Swing `{cleaned_id}` already has a bound video at "
                            f"`{existing.video_path}`. Overwriting the file "
                            "but keeping the manifest entry."
                        )
                    existing.video_path = rel_video_path
                    existing.handedness = hand_to_save
                    existing.ground_truth.stride_style = new_stride_guess
                    existing.ground_truth.camera_view = new_camera_guess
                    existing.ground_truth.real_time = bool(new_realtime_guess)
                    if new_notes.strip():
                        existing.notes = new_notes
                    action = "bound video to existing"
                else:
                    new_entry = SwingEntry(
                        id=cleaned_id,
                        video_path=rel_video_path,
                        fingerprint_path=None,
                        handedness=hand_to_save,
                        ground_truth=GroundTruth(
                            stride_style=new_stride_guess,
                            final_plant_frame=None,
                            contact_frame=None,
                            rotation_onset_frame=None,
                            camera_view=new_camera_guess,
                            real_time=bool(new_realtime_guess),
                        ),
                        notes=new_notes,
                    )
                    manifest.swings.append(new_entry)
                    action = "added new"
                try:
                    _save_manifest_atomic(manifest, MANIFEST_PATH)
                    st.success(
                        f"✓ {action} swing `{cleaned_id}` — refreshing so you "
                        "can label it…"
                    )
                    st.session_state["_just_added_id"] = cleaned_id
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e!r}")


# Recompute labelable AFTER the form may have added one
labelable = []
without_video = []
for entry in manifest.swings:
    video = _resolve_video(entry.video_path)
    if video:
        labelable.append((entry, video))
    else:
        without_video.append(entry)


# If still no labelable swings, show a friendly empty state below the form
if not labelable:
    st.info(
        "No swings with bound videos yet. Use the **Add a swing** form above "
        "to upload your first clip and start labeling."
    )
    if without_video:
        with st.expander(
            f"Manifest contains {len(without_video)} entries awaiting a "
            "video binding (e.g. the seeded MLB references)"
        ):
            for e in without_video[:50]:
                st.write(f"- `{e.id}` ({e.ground_truth.stride_style})")
    st.stop()


# ---- Sidebar: progress + selection ----
with st.sidebar:
    st.header("Progress")
    n_total = len(manifest.swings)
    n_labeled = sum(1 for s in manifest.swings if s.ground_truth.is_labeled)
    st.metric("Labeled", f"{n_labeled} / {n_total}")
    st.progress(0 if n_total == 0 else n_labeled / n_total)

    st.divider()
    st.subheader("Swing selection")

    # Group labeled vs unlabeled in the dropdown
    labeled_options = [(i, e, v) for i, (e, v) in enumerate(labelable)
                       if e.ground_truth.is_labeled]
    unlabeled_options = [(i, e, v) for i, (e, v) in enumerate(labelable)
                         if not e.ground_truth.is_labeled]
    show_only_unlabeled = st.checkbox(
        "Show only unlabeled swings",
        value=bool(unlabeled_options),
    )
    pool = unlabeled_options if show_only_unlabeled else (
        unlabeled_options + labeled_options
    )
    if not pool:
        st.success("All swings in this filter are labeled.")
        st.stop()

    options_labels = [
        f"{'✓' if e.ground_truth.is_labeled else '○'} {e.id}"
        for _, e, _ in pool
    ]

    # If we just added a swing via the upload form, auto-select it so the
    # user lands directly on the new entry.
    default_pool_idx = 0
    just_added = st.session_state.pop("_just_added_id", None)
    if just_added:
        for i, (_, e, _) in enumerate(pool):
            if e.id == just_added:
                default_pool_idx = i
                break

    sel_pool_idx = st.selectbox(
        "Pick a swing",
        range(len(pool)),
        index=default_pool_idx,
        format_func=lambda i: options_labels[i],
    )
    _, entry, video_path = pool[sel_pool_idx]

    st.divider()
    st.write(f"**Source video:** `{video_path.name}`")
    st.write(f"**Manifest entry:** `{entry.id}`")
    if entry.handedness:
        st.write(f"**Handedness:** {entry.handedness}")


# ---- Open video ----
try:
    _mtime = video_path.stat().st_mtime
except OSError:
    _mtime = 0.0
cap, n_frames, fps = _open_video(str(video_path), _mtime)

# Decode-failure recovery: Mac screen recordings + many "convert to mp4"
# tools produce containers OpenCV's bundled ffmpeg can't read (ProRes,
# HEVC, etc). Surface a recoverable panel with a one-click transcode
# rather than st.stop().
if cap is None or n_frames <= 0:
    st.error(f"OpenCV couldn't decode `{video_path.name}`.")
    try:
        size_mb = video_path.stat().st_size / 1e6
    except OSError:
        size_mb = 0.0
    st.caption(
        f"Path: `{video_path}`  •  Size: {size_mb:.1f} MB  •  "
        "Common cause: ProRes / HEVC codec from a Mac screen recording "
        "that was renamed to .mp4 but not actually re-encoded."
    )

    transcoded_path = video_path.with_suffix(".transcoded.mp4")
    have_ffmpeg = shutil.which("ffmpeg") is not None

    # Case 1: a transcoded version already exists from a previous attempt
    if transcoded_path.exists():
        st.info(
            f"A previously-transcoded file exists at `{transcoded_path.name}`. "
            "Binding the manifest entry to it…"
        )
        entry.video_path = str(
            transcoded_path.relative_to(PROJECT_ROOT)
            if transcoded_path.is_relative_to(PROJECT_ROOT)
            else transcoded_path
        )
        _save_manifest_atomic(manifest, MANIFEST_PATH)
        st.rerun()

    # Case 2: ffmpeg is on PATH — offer an in-app one-click fix
    elif have_ffmpeg:
        st.markdown(
            "**Fix:** transcode to H.264 MP4 in place. Takes ~10–60 s for "
            "typical screen recordings. Click below — we'll write a "
            "`.transcoded.mp4` sibling file and re-point this manifest entry "
            "to it (the original file is left untouched)."
        )
        if st.button(
            "🔁  Auto-transcode to H.264 (one-time fix per file)",
            type="primary",
            use_container_width=True,
            key=f"transcode_{entry.id}",
        ):
            with st.spinner(f"Transcoding `{video_path.name}` → H.264…"):
                ok, msg = _try_transcode(video_path, transcoded_path)
            if ok:
                rel = (
                    transcoded_path.relative_to(PROJECT_ROOT)
                    if transcoded_path.is_relative_to(PROJECT_ROOT)
                    else transcoded_path
                )
                entry.video_path = str(rel)
                _save_manifest_atomic(manifest, MANIFEST_PATH)
                st.success("✓ Transcoded successfully. Reloading…")
                st.rerun()
            else:
                st.error(f"Auto-transcode failed: {msg}")

    # Case 3: ffmpeg isn't installed — show install + manual command
    else:
        st.warning(
            "ffmpeg isn't on your PATH. The easiest fix on macOS is "
            "`brew install ffmpeg`, then refresh this page."
        )
        st.markdown("**Or run this in your terminal right now:**")
        st.code(
            f'ffmpeg -y -i "{video_path}" -c:v libx264 -preset fast '
            f'-pix_fmt yuv420p -movflags +faststart -an '
            f'"{transcoded_path}"',
            language="bash",
        )
        st.caption(
            "After it finishes, refresh this page — the labeling app will "
            "auto-pick up the .transcoded.mp4 sibling."
        )

    # Offer to pick a different swing instead
    st.divider()
    st.info(
        "💡 Or pick a different swing in the sidebar while you sort this one out."
    )
    st.stop()

# ---- Per-swing session state ----
# Persist the current frame across reruns. Reset when the user switches swings.
frame_key = f"current_frame::{entry.id}"
if frame_key not in st.session_state:
    # Default to the existing final_plant_frame if labeled, else jump to
    # roughly 40% of the clip (the swing usually happens in the middle —
    # avoids landing on intro overlays / play-button thumbnails baked into
    # YouTube-style sources).
    if entry.ground_truth.final_plant_frame is not None:
        st.session_state[frame_key] = max(
            0, min(n_frames - 1, entry.ground_truth.final_plant_frame)
        )
    else:
        st.session_state[frame_key] = max(0, int(n_frames * 0.4))

# Slots that the "capture current frame" buttons fill
plant_key = f"plant::{entry.id}"
contact_key = f"contact::{entry.id}"
rot_key = f"rot::{entry.id}"
if plant_key not in st.session_state:
    st.session_state[plant_key] = entry.ground_truth.final_plant_frame
if contact_key not in st.session_state:
    st.session_state[contact_key] = entry.ground_truth.contact_frame
if rot_key not in st.session_state:
    st.session_state[rot_key] = entry.ground_truth.rotation_onset_frame


def _clamp_frame(idx: int) -> int:
    return max(0, min(n_frames - 1, int(idx)))


def _set_frame(idx: int) -> None:
    st.session_state[frame_key] = _clamp_frame(idx)


# ---- Header ----
st.subheader(entry.id)
status_chip = "✓ Labeled" if entry.ground_truth.is_labeled else "○ Not yet labeled"
st.caption(
    f"{status_chip}  •  `{video_path.name}`  •  "
    f"{n_frames} frames @ {fps:.1f} fps  •  duration {n_frames/fps:.2f}s"
)


# ---- Step A: playable preview (watch first) ----
with st.expander("▶ Watch the swing at normal speed (preview only — does NOT affect marking)", expanded=True):
    try:
        st.video(str(video_path))
    except Exception as e:  # noqa: BLE001
        st.warning(f"Preview unavailable: {e!r} — the frame stepper below still works.")
    st.caption(
        "Identify the foot-plant + contact moments here, then collapse this "
        "expander and use the frame stepper below to mark the exact frames."
    )

st.divider()
st.markdown("## ▼  Mark frames below  ▼")

# ---- Step B: precise frame view (mark here) ----
# OpenCV-decoded still frame + scrub slider. THIS is the surface the
# capture buttons read from — what you see here is what gets recorded
# as foot_plant_frame / contact_frame.
img = _read_frame(cap, st.session_state[frame_key])
if img is None:
    st.error(f"Could not decode frame {st.session_state[frame_key]}")
else:
    cur = st.session_state[frame_key]
    st.image(
        img,
        caption=f"Frame {cur}  •  t = {cur / fps:.3f}s  •  drag the slider below to scrub",
        use_container_width=True,
    )

# Big scrub slider, full width, right under the image — this is the
# primary navigation control.
scrub = st.slider(
    "▶ Scrub through the swing",
    min_value=0,
    max_value=max(0, n_frames - 1),
    value=st.session_state[frame_key],
    key=f"scrub_main_{entry.id}",
    label_visibility="collapsed",
)
if int(scrub) != st.session_state[frame_key]:
    st.session_state[frame_key] = int(scrub)
    st.rerun()


# ---- Frame nudge buttons (precision controls under the scrub slider) ----
nav_cols = st.columns([1, 1, 2, 1, 1])
with nav_cols[0]:
    if st.button("⏮ −10", use_container_width=True, key="back10"):
        _set_frame(st.session_state[frame_key] - 10)
        st.rerun()
with nav_cols[1]:
    if st.button("◀ −1", use_container_width=True, key="back1"):
        _set_frame(st.session_state[frame_key] - 1)
        st.rerun()
with nav_cols[2]:
    typed = st.number_input(
        "Jump to exact frame",
        min_value=0,
        max_value=max(0, n_frames - 1),
        value=st.session_state[frame_key],
        key=f"jump_input_{entry.id}",
    )
    if int(typed) != st.session_state[frame_key]:
        _set_frame(int(typed))
        st.rerun()
with nav_cols[3]:
    if st.button("+1 ▶", use_container_width=True, key="fwd1"):
        _set_frame(st.session_state[frame_key] + 1)
        st.rerun()
with nav_cols[4]:
    if st.button("+10 ⏭", use_container_width=True, key="fwd10"):
        _set_frame(st.session_state[frame_key] + 10)
        st.rerun()


# ---- Minimal label UI: 3 things per swing ----
#   1. Mark FOOT PLANT frame  (where front foot finally settles)
#   2. Mark CONTACT frame     (where bat meets ball)
#   3. Toe-tap? Yes / No
# Other fields (camera_view, real_time, rotation_onset, notes) are kept
# at sensible defaults so the user only sees what matters.
st.divider()
st.markdown("### Label this swing")

cur = st.session_state[frame_key]
plant_val = st.session_state[plant_key]
contact_val = st.session_state[contact_key]

cap_cols = st.columns(2)
with cap_cols[0]:
    st.markdown(
        f"**Step 1 · FOOT PLANT** — frame where the front foot finally "
        f"settles. For toe-tap swings: NOT the tap, the *final* plant."
    )
    if st.button(
        f"📌  Set foot plant = frame {cur}",
        type="primary",
        use_container_width=True,
        key="cap_plant",
    ):
        st.session_state[plant_key] = cur
        st.rerun()
    if plant_val is not None:
        st.success(f"✓ Foot plant marked at frame **{plant_val}**  "
                   f"(t = {plant_val / fps:.3f}s)")
    else:
        st.caption("Not marked yet")

with cap_cols[1]:
    st.markdown(
        "**Step 2 · CONTACT** — frame where the bat appears to meet the ball."
    )
    if st.button(
        f"📌  Set contact = frame {cur}",
        type="primary",
        use_container_width=True,
        key="cap_contact",
    ):
        st.session_state[contact_key] = cur
        st.rerun()
    if contact_val is not None:
        st.success(f"✓ Contact marked at frame **{contact_val}**  "
                   f"(t = {contact_val / fps:.3f}s)")
    else:
        st.caption("Not marked yet")

st.markdown("")
# Step 3: Toe-tap binary
existing_is_toe_tap = (entry.ground_truth.stride_style == "toe_tap")
is_toe_tap = st.radio(
    "**Step 3 · Is this a toe-tap?**",
    ["No — regular stride / leg-kick / no-stride",
     "Yes — front foot taps the ground before the final plant"],
    index=1 if existing_is_toe_tap else 0,
    horizontal=False,
)

st.markdown("")
# Save + auto-advance
save_clicked = st.button(
    "💾  SAVE + GO TO NEXT SWING  →",
    type="primary",
    use_container_width=True,
    key=f"save_{entry.id}",
)

if save_clicked:
    if plant_val is None or contact_val is None:
        st.error("⚠ Mark BOTH the foot plant and contact frames before saving.")
    elif int(contact_val) <= int(plant_val):
        st.error(
            f"⚠ Contact (frame {contact_val}) must come AFTER foot plant "
            f"(frame {plant_val}). Use the navigation to fix and re-mark."
        )
    else:
        # Mutate in place; commit to disk atomically
        entry.ground_truth.final_plant_frame = int(plant_val)
        entry.ground_truth.contact_frame = int(contact_val)
        entry.ground_truth.stride_style = (
            "toe_tap" if is_toe_tap.startswith("Yes") else "standard_stride"
        )
        # Defaults for fields we don't ask about in the simplified UI
        entry.ground_truth.camera_view = (
            entry.ground_truth.camera_view or "profile"
        )
        entry.ground_truth.real_time = (
            entry.ground_truth.real_time
            if entry.ground_truth.real_time is not None else True
        )
        if not entry.labeled_at:
            entry.labeled_at = str(date.today())
        try:
            _save_manifest_atomic(manifest, MANIFEST_PATH)
            # Auto-advance to next unlabeled swing
            next_unlabeled = next(
                (s for s in manifest.swings
                 if not s.ground_truth.is_labeled
                 and s.id != entry.id
                 and _resolve_video(s.video_path) is not None),
                None,
            )
            if next_unlabeled is not None:
                # Clear per-swing scratch state on the next swing so it
                # starts fresh
                for k in (
                    f"current_frame::{next_unlabeled.id}",
                    f"plant::{next_unlabeled.id}",
                    f"contact::{next_unlabeled.id}",
                    f"rot::{next_unlabeled.id}",
                ):
                    st.session_state.pop(k, None)
                st.session_state["_just_added_id"] = next_unlabeled.id
                st.toast(
                    f"✓ Saved `{entry.id}` — advancing to `{next_unlabeled.id}`",
                    icon="⏭️",
                )
                st.rerun()
            else:
                st.balloons()
                st.success(
                    f"✓ Saved `{entry.id}`. 🎉 All labelable swings are done — "
                    "run `python3 -m scripts.validation.run_validation` to "
                    "produce the v3-vs-v4 report."
                )
        except Exception as e:
            st.error(f"Save failed: {e!r}")


# ---- Footer: next-swing helper ----
st.divider()
st.caption(
    "Labeling protocol: see `validation/README.md`. When you've labeled a "
    "batch, run `python -m scripts.validation.run_validation` from the repo "
    "root to produce the v3-vs-v4 comparison report."
)
