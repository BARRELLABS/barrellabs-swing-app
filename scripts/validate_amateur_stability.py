#!/usr/bin/env python3
"""Validate the re-anchored score_stability against real amateur/phone swings.

Runs pose on the labeled amateur clips in the validation manifest (Logan's own
phone swings: img_*, my_swing), computes head-drift with the FIXED ear-midpoint
metric at the verified plant/contact frames, and reports the resulting stability
score. Tells us where genuine amateur swings land — the validation we couldn't
do without a dedicated amateur-lurch clip.
"""
import csv, json, math, os, sys
import numpy as np
import cv2
import mediapipe as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from swing_score import score_stability

L_EAR, R_EAR, L_SHO, R_SHO, L_HIP, R_HIP = 7, 8, 11, 12, 23, 24


def _smooth(a, w=5):
    a = np.asarray(a, float)
    return np.convolve(a, np.ones(w) / w, mode="same") if len(a) >= w else a


def head_drift(video, plant, contact):
    cap = cv2.VideoCapture(os.path.expanduser(video))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pose = mp.solutions.pose.Pose(model_complexity=2, min_detection_confidence=0.5)
    em_x, em_y, sm_x, sm_y, hm_y = [], [], [], [], []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        res = pose.process(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            X = lambda i: lm[i].x * w; Y = lambda i: lm[i].y * h
            em_x.append((X(L_EAR) + X(R_EAR)) / 2); em_y.append((Y(L_EAR) + Y(R_EAR)) / 2)
            sm_x.append((X(L_SHO) + X(R_SHO)) / 2); sm_y.append((Y(L_SHO) + Y(R_SHO)) / 2)
            hm_y.append((Y(L_HIP) + Y(R_HIP)) / 2)
        else:
            for arr in (em_x, em_y, sm_x, sm_y, hm_y):
                arr.append(arr[-1] if arr else 0.0)
    cap.release(); pose.close()
    if plant >= len(em_x) or contact >= len(em_x):
        return None
    emx = _smooth(em_x) - _smooth(sm_x); emy = _smooth(em_y) - _smooth(sm_y)
    torso = np.abs(_smooth(hm_y) - _smooth(sm_y)); ref = float(np.percentile(torso, 95))
    if ref <= 1:
        return None
    dx = emx[contact] - emx[plant]; dy = emy[contact] - emy[plant]
    return math.hypot(dx, dy) / ref


def main():
    raw = json.load(open(os.path.join(ROOT, "validation/manifest.json")))["swings"]
    it = raw if isinstance(raw, list) else list(raw.values())
    targets = [s for s in it if (s["id"].startswith("img_") or s["id"] == "my_swing")
               and os.path.exists(os.path.expanduser(s.get("video_path", "") or ""))]
    print(f"{'clip':12} {'drift':>7} {'stability(13-14)':>18} {'stability(11-12)':>18}")
    drifts = []
    for s in targets:
        gt = s["ground_truth"]
        p, c = gt.get("final_plant_frame"), gt.get("contact_frame")
        if p is None or c is None:
            continue
        d = head_drift(s["video_path"], int(p), int(c))
        if d is None:
            print(f"{s['id']:12} (could not compute)"); continue
        drifts.append(d)
        print(f"{s['id']:12} {d:7.3f} {score_stability(d,'13-14'):18.2f} {score_stability(d,'11-12'):18.2f}")
    if drifts:
        print(f"\namateur head-drift: min={min(drifts):.3f} max={max(drifts):.3f} mean={np.mean(drifts):.3f}")
        print("(For reference: MLB pros sit 0.009-0.136; threshold good=0.07, bad=0.30.)")


if __name__ == "__main__":
    main()
