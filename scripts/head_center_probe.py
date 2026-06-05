#!/usr/bin/env python3
"""Probe head-center landmark candidates for the head-drift metric fix.

WHY: the live head-drift metric uses the NOSE relative to shoulder-mid. The
nose projects forward of the skull, so it sweeps a large arc as the batter
ROTATES — counting rotation as "head drift" and over-penalizing hard rotators
(lindor 0.26, mookie 0.15 post-rebuild). This probe re-extracts candidate
head-center landmarks (nose / ear-midpoint / eye-midpoint) per frame so we can
evaluate which definition measures head TRANSLATION (stability) without the
rotation arc.

Matches detect_phases pose config (model_complexity=2, min_det=0.5).
Writes validation/head_probe/<slug>.csv. Run standalone (slow — re-runs pose).
"""
import csv, math, os, sys

import cv2
import mediapipe as mp

# MediaPipe Pose landmark indices
NOSE = 0
L_EYE, R_EYE = 2, 5
L_EAR, R_EAR = 7, 8
L_SHO, R_SHO = 11, 12
L_HIP, R_HIP = 23, 24

CLIPS = {
    # inflated (high-slow-mo broadcast)
    "francisco_lindor": "francisco_lindor_swing.mp4",
    "mookie_betts":     "mookie_swing.mp4",
    "kyle_schwarber":   "kyle_schwarber_swing.mp4",
    "freddie_freeman":  "freddie_freeman_swing.mp4",
    "yandy_diaz":       "yandy_diaz_swing.mp4",
    # controls (stayed low / went down)
    "aaron_judge":      "judge_swing copy.mp4",
    "kyle_tucker":      "kyle_tucker_swing.mp4",
    "yordan_alvarez":   "yordan_alvarez_swing.mp4",
}
VIDEO_DIR = os.path.expanduser("~/baseball-swing-app")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "validation", "head_probe")


def probe(slug, fname):
    path = os.path.join(VIDEO_DIR, fname)
    if not os.path.exists(path):
        print(f"  ✗ {slug}: missing {path}"); return
    cap = cv2.VideoCapture(path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=2,
                                  enable_segmentation=False, min_detection_confidence=0.5)
    rows = []
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        res = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            def x(i): return lm[i].x * w
            def y(i): return lm[i].y * h
            def v(i): return lm[i].visibility
            rows.append({
                "frame": fi,
                "nose_x": x(NOSE), "nose_y": y(NOSE),
                "l_ear_x": x(L_EAR), "l_ear_y": y(L_EAR), "l_ear_v": v(L_EAR),
                "r_ear_x": x(R_EAR), "r_ear_y": y(R_EAR), "r_ear_v": v(R_EAR),
                "l_eye_x": x(L_EYE), "l_eye_y": y(L_EYE), "l_eye_v": v(L_EYE),
                "r_eye_x": x(R_EYE), "r_eye_y": y(R_EYE), "r_eye_v": v(R_EYE),
                "sho_mid_x": (x(L_SHO) + x(R_SHO)) / 2.0,
                "sho_mid_y": (y(L_SHO) + y(R_SHO)) / 2.0,
                "hip_mid_x": (x(L_HIP) + x(R_HIP)) / 2.0,
                "hip_mid_y": (y(L_HIP) + y(R_HIP)) / 2.0,
            })
        fi += 1
    cap.release(); pose.close()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{slug}.csv")
    if rows:
        with open(out, "w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wtr.writeheader(); wtr.writerows(rows)
    print(f"  ✓ {slug}: {len(rows)} frames -> {out}")


if __name__ == "__main__":
    print(f"Probing {len(CLIPS)} clips for head-center candidates...")
    for slug, fname in CLIPS.items():
        probe(slug, fname)
    print("done.")
