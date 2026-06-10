"""
Shared pose-extraction helper used by both the user-swing pipeline (app.py)
and the MLB-reference ingestion pipeline (build_reference_library.py).

Reads a video, runs MediaPipe Pose on every frame, returns the 33-keypoint
arrays + metadata. Coords are normalized 0..1 so the data is resolution-
independent — the renderer multiplies by canvas size at draw time.

The output schema is the same one already on every MLB reference JSON, so
the side-by-side skeleton overlay can treat user swings and reference
swings identically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

import cv2
import mediapipe as mp


# 33 MediaPipe pose landmarks — human-readable names so the data is
# self-documenting if anyone opens the JSON.
LM_NAMES: List[str] = [
    "nose", "l_eye_inner", "l_eye", "l_eye_outer",
    "r_eye_inner", "r_eye", "r_eye_outer",
    "l_ear", "r_ear", "mouth_l", "mouth_r",
    "l_shoulder", "r_shoulder", "l_elbow", "r_elbow",
    "l_wrist", "r_wrist", "l_pinky", "r_pinky",
    "l_index", "r_index", "l_thumb", "r_thumb",
    "l_hip", "r_hip", "l_knee", "r_knee",
    "l_ankle", "r_ankle", "l_heel", "r_heel",
    "l_foot_index", "r_foot_index",
]


def extract_pose_frames(video_path: Union[str, Path]) -> Dict:
    """Run MediaPipe Pose on every frame of the video.

    Returns a dict with:
      - fps                : float (from the video container)
      - width, height      : int (video frame dims in pixels)
      - n_frames_total     : int (frames read)
      - n_frames_with_pose : int (frames where pose was detected)
      - frames             : list of {f, t, kp} per frame with pose
                              where kp = [[x, y, visibility], ... × 33]
                              coords normalized 0..1

    Raises RuntimeError if the video can't be opened.
    """
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frames: List[Dict] = []
    frame_idx = 0
    detected = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            detected += 1
            kp = []
            for lm in results.pose_landmarks.landmark:
                kp.append([
                    round(float(lm.x), 4),
                    round(float(lm.y), 4),
                    round(float(lm.visibility), 3),
                ])
            frames.append({
                "f": frame_idx,
                "t": round(frame_idx / fps, 4),
                "kp": kp,
            })
        frame_idx += 1

    cap.release()
    pose.close()

    return {
        "fps": fps,
        "width": width,
        "height": height,
        "n_frames_total": frame_idx,
        "n_frames_with_pose": detected,
        "frames": frames,
    }


def extract_key_frames(video_path: Union[str, Path],
                       phases_t: Dict,
                       keys=("foot_plant", "contact", "finish"),
                       max_width: int = 480,
                       jpeg_quality: int = 80) -> Dict[str, bytes]:
    """Grab one still JPEG at each requested swing-phase moment.

    `phases_t` maps phase name -> seconds into the clip (the same dict
    detect_phases surfaces). For each key we seek to that timestamp and keep
    a single frame, downsized to `max_width` (aspect ratio preserved, so the
    report's pose overlay still aligns) and JPEG-encoded.

    Returns {key: jpeg_bytes} for every key that resolved to a readable frame.
    Keys with no timestamp or an unreadable seek are simply omitted. Returns
    an empty dict (never raises) if the video can't be opened, so the caller
    can stay fail-soft: a missing frame just drops that panel from the report.
    """
    if not phases_t:
        return {}
    cap = cv2.VideoCapture(str(Path(video_path)))
    if not cap.isOpened():
        return {}
    out: Dict[str, bytes] = {}
    try:
        for key in keys:
            t = phases_t.get(key)
            if t is None:
                continue
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            h, w = frame.shape[:2]
            if w > max_width and w > 0:
                new_h = max(1, int(round(h * max_width / w)))
                frame = cv2.resize(frame, (max_width, new_h),
                                   interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
            if ok:
                out[key] = buf.tobytes()
    finally:
        cap.release()
    return out


def build_pose_meta(pose_data: Dict) -> Dict:
    """Format the metadata block that gets stored alongside `frames`.

    Kept in a separate helper so callers (both reference-builder and the
    user-swing pipeline) can use the same schema.
    """
    return {
        "fps":                pose_data["fps"],
        "video_width":        pose_data["width"],
        "video_height":       pose_data["height"],
        "n_frames_total":     pose_data["n_frames_total"],
        "n_frames_with_pose": pose_data["n_frames_with_pose"],
        "lm_count":           33,
        "lm_names":           LM_NAMES,
        "coord_space":        "normalized_0_1",
        "model":              "mediapipe.pose",
        "model_complexity":   2,
    }
