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
    load_manifest, write_manifest, Manifest, SwingEntry,
    VALID_STRIDE_STYLES, VALID_CAMERA_VIEWS,
)

MANIFEST_PATH = PROJECT_ROOT / "validation" / "manifest.json"


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def _open_video(path_str: str):
    """Open a video. Cached so reruns don't reopen the file. Returns
    (capture_handle, n_frames, fps) — or (None, 0, 0) on failure."""
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

# Partition swings into "labelable" (has usable video) and "skipped"
labelable: list[tuple[SwingEntry, Path]] = []
without_video: list[SwingEntry] = []
for entry in manifest.swings:
    video = _resolve_video(entry.video_path)
    if video:
        labelable.append((entry, video))
    else:
        without_video.append(entry)


# ---- Sidebar: progress + selection ----
with st.sidebar:
    st.header("Progress")
    n_total = len(manifest.swings)
    n_labeled = sum(1 for s in manifest.swings if s.ground_truth.is_labeled)
    st.metric("Labeled", f"{n_labeled} / {n_total}")
    st.progress(0 if n_total == 0 else n_labeled / n_total)

    st.divider()
    st.subheader("Swing selection")

    if not labelable:
        st.warning(
            "No swings have a resolvable `video_path` yet.\n\n"
            "Set `video_path` on at least one entry in "
            "`validation/manifest.json` (relative to repo root or "
            "absolute), then refresh this page."
        )
        if without_video:
            st.write("Swings awaiting a video_path:")
            for e in without_video[:20]:
                st.write(f"- `{e.id}`")
        st.stop()

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
    sel_pool_idx = st.selectbox(
        "Pick a swing",
        range(len(pool)),
        format_func=lambda i: options_labels[i],
    )
    _, entry, video_path = pool[sel_pool_idx]

    st.divider()
    st.write(f"**Source video:** `{video_path.name}`")
    st.write(f"**Manifest entry:** `{entry.id}`")
    if entry.handedness:
        st.write(f"**Handedness:** {entry.handedness}")


# ---- Open video ----
cap, n_frames, fps = _open_video(str(video_path))
if cap is None:
    st.error(f"Failed to open video: `{video_path}`")
    st.stop()

if n_frames <= 0:
    st.error(
        f"Video has 0 frames (codec may be unsupported by OpenCV): `{video_path}`"
    )
    st.stop()

# ---- Per-swing session state ----
# Persist the current frame across reruns. Reset when the user switches swings.
frame_key = f"current_frame::{entry.id}"
if frame_key not in st.session_state:
    # Default to the existing final_plant_frame if labeled, else first frame
    if entry.ground_truth.final_plant_frame is not None:
        st.session_state[frame_key] = max(
            0, min(n_frames - 1, entry.ground_truth.final_plant_frame)
        )
    else:
        st.session_state[frame_key] = 0

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


# ---- Frame display ----
img = _read_frame(cap, st.session_state[frame_key])
if img is None:
    st.error(f"Could not decode frame {st.session_state[frame_key]}")
else:
    cur = st.session_state[frame_key]
    st.image(
        img,
        caption=f"Frame {cur}  •  t = {cur / fps:.3f}s",
        use_container_width=True,
    )


# ---- Frame navigation ----
st.divider()
st.markdown("### Navigation")
nav_cols = st.columns([1, 1, 1, 4, 1, 1, 1])
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
        "Jump",
        min_value=0,
        max_value=max(0, n_frames - 1),
        value=st.session_state[frame_key],
        key="jump_input",
        label_visibility="collapsed",
    )
    if int(typed) != st.session_state[frame_key]:
        _set_frame(int(typed))
        st.rerun()
with nav_cols[3]:
    slid = st.slider(
        "Scrub",
        min_value=0,
        max_value=max(0, n_frames - 1),
        value=st.session_state[frame_key],
        key=f"scrub_{entry.id}",
        label_visibility="collapsed",
    )
    if int(slid) != st.session_state[frame_key]:
        _set_frame(int(slid))
        st.rerun()
with nav_cols[4]:
    if st.button("+1 ▶", use_container_width=True, key="fwd1"):
        _set_frame(st.session_state[frame_key] + 1)
        st.rerun()
with nav_cols[5]:
    if st.button("+10 ⏭", use_container_width=True, key="fwd10"):
        _set_frame(st.session_state[frame_key] + 10)
        st.rerun()
with nav_cols[6]:
    if st.button("End ⏵⏵", use_container_width=True, key="end"):
        _set_frame(n_frames - 1)
        st.rerun()


# ---- Capture buttons (set the label slots to the current frame) ----
st.divider()
st.markdown("### Capture current frame as…")
cap_cols = st.columns(3)
cur = st.session_state[frame_key]
with cap_cols[0]:
    if st.button(
        f"📌 Set **final_plant_frame** = {cur}",
        type="primary",
        use_container_width=True,
        key="cap_plant",
    ):
        st.session_state[plant_key] = cur
with cap_cols[1]:
    if st.button(
        f"📌 Set **contact_frame** = {cur}",
        type="primary",
        use_container_width=True,
        key="cap_contact",
    ):
        st.session_state[contact_key] = cur
with cap_cols[2]:
    if st.button(
        f"📌 Set rotation_onset_frame = {cur}  (optional)",
        use_container_width=True,
        key="cap_rot",
    ):
        st.session_state[rot_key] = cur


# ---- Label form ----
st.divider()
st.markdown("### Labels")
with st.form(key=f"label_form_{entry.id}"):
    cols = st.columns(3)
    with cols[0]:
        new_stride_style = st.radio(
            "Stride style",
            VALID_STRIDE_STYLES,
            index=VALID_STRIDE_STYLES.index(entry.ground_truth.stride_style),
            help=(
                "no_stride: foot never leaves the ground\n\n"
                "standard_stride: single lift → single plant\n\n"
                "toe_tap: lift → brief touch → lift → plant\n\n"
                "leg_kick: large vertical lift (~50%+ of torso length)"
            ),
        )
    with cols[1]:
        try:
            cam_idx = VALID_CAMERA_VIEWS.index(entry.ground_truth.camera_view)
        except ValueError:
            cam_idx = 0
        new_camera_view = st.radio(
            "Camera view", VALID_CAMERA_VIEWS, index=cam_idx,
        )
    with cols[2]:
        new_real_time = st.checkbox(
            "Real-time playback",
            value=entry.ground_truth.real_time,
            help="Uncheck if this clip is slow-motion (e.g. 240fps "
                 "captured but played back at 30fps).",
        )

    cols2 = st.columns(3)
    with cols2[0]:
        new_plant = st.number_input(
            "final_plant_frame *",
            min_value=0, max_value=max(0, n_frames - 1),
            value=st.session_state[plant_key] if st.session_state[plant_key] is not None else 0,
            help="The frame where the front foot finally settles BEFORE "
                 "rotation begins. NOT the toe-tap moment for toe_tap swings.",
        )
    with cols2[1]:
        new_contact = st.number_input(
            "contact_frame *",
            min_value=0, max_value=max(0, n_frames - 1),
            value=st.session_state[contact_key] if st.session_state[contact_key] is not None else 0,
            help="The frame where the bat appears to meet the ball.",
        )
    with cols2[2]:
        rot_default = (
            st.session_state[rot_key] if st.session_state[rot_key] is not None else 0
        )
        new_rot = st.number_input(
            "rotation_onset_frame (optional)",
            min_value=0, max_value=max(0, n_frames - 1),
            value=rot_default,
        )

    new_notes = st.text_area("Notes", value=entry.notes, height=80)
    cols3 = st.columns([2, 1])
    with cols3[0]:
        new_labeled_by = st.text_input("Labeled by", value=entry.labeled_by)
    with cols3[1]:
        new_labeled_at = st.text_input(
            "Labeled at (YYYY-MM-DD)",
            value=entry.labeled_at or str(date.today()),
        )

    save_clicked = st.form_submit_button(
        "💾  SAVE LABELS",
        type="primary",
        use_container_width=True,
    )

if save_clicked:
    if new_plant <= 0 and new_contact <= 0:
        st.warning(
            "Both final_plant_frame and contact_frame are 0 — that's "
            "almost certainly a mistake. Capture them from the video first."
        )
    elif new_contact <= new_plant:
        st.error(
            f"contact_frame ({new_contact}) must come AFTER "
            f"final_plant_frame ({new_plant})."
        )
    else:
        # Mutate in place; manifest is the in-memory object the loader
        # returned.
        entry.ground_truth.stride_style = new_stride_style
        entry.ground_truth.camera_view = new_camera_view
        entry.ground_truth.real_time = bool(new_real_time)
        entry.ground_truth.final_plant_frame = int(new_plant)
        entry.ground_truth.contact_frame = int(new_contact)
        entry.ground_truth.rotation_onset_frame = (
            int(new_rot) if int(new_rot) > 0 else None
        )
        entry.notes = new_notes
        entry.labeled_by = new_labeled_by
        entry.labeled_at = new_labeled_at
        try:
            _save_manifest_atomic(manifest, MANIFEST_PATH)
            st.success(f"✓ Saved labels for `{entry.id}` → `{MANIFEST_PATH}`")
            st.balloons()
            # Update session-state slots so the form shows the saved values
            # immediately on the next interaction.
            st.session_state[plant_key] = int(new_plant)
            st.session_state[contact_key] = int(new_contact)
            st.session_state[rot_key] = (
                int(new_rot) if int(new_rot) > 0 else None
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
