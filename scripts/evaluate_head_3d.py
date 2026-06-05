#!/usr/bin/env python3
"""Evaluate 3D-world-landmark head-drift candidates (rotation/camera-invariant).

MediaPipe world landmarks are metric (meters), hip-centered, camera-invariant.
The ear-midpoint sits near the spine axis, so in 3D it should barely move during
rotation while still capturing genuine head translation relative to the body —
the cleanest fix for the residual shoulder-anchor-slide artifact (freeman/
schwarber/mookie still read ~0.13 in 2D).

Reads validation/head_probe/<slug>.csv (must include w_* 3D columns), uses the
verified plant/contact from the manifest. Compares 3D variants against the 2D
ear-mid baseline. WANT: inflated clips drop toward control levels.
"""
import csv, json, math, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "validation", "head_probe")
MANIFEST = os.path.join(ROOT, "validation", "manifest.json")
INFLATED = {"francisco_lindor", "mookie_betts", "kyle_schwarber", "freddie_freeman", "yandy_diaz"}
CONTROL = {"aaron_judge", "kyle_tucker", "yordan_alvarez"}
MANIFEST_ID = {"aaron_judge": "judge_swing_copy", "mookie_betts": "mookie_swing",
               "mike_trout": "trout_swing", "shohei_ohtani": "shohei_swing"}


def _smooth(a, w=5):
    a = np.asarray(a, float)
    return np.convolve(a, np.ones(w) / w, mode="same") if len(a) >= w else a


def _frames():
    raw = json.load(open(MANIFEST))["swings"]
    it = raw if isinstance(raw, list) else list(raw.values())
    return {s["id"]: (s["ground_truth"].get("final_plant_frame"),
                      s["ground_truth"].get("contact_frame")) for s in it}


def main():
    frames = _frames()
    variants = ["2d_ear_sho", "3d_ear_hip", "3d_ear_hip_xy", "3d_ear_sho", "3d_ear_sho_xy"]
    print(f"{'clip':18} {'grp':9} " + " ".join(f"{v:>14}" for v in variants))
    agg = {v: {"inflated": [], "control": []} for v in variants}
    for fn in sorted(os.listdir(PROBE)):
        if not fn.endswith(".csv"):
            continue
        slug = fn[:-4]
        rows = list(csv.DictReader(open(os.path.join(PROBE, fn))))
        if "w_l_ear_x" not in rows[0]:
            print(f"{slug}: no 3D columns — re-run head_center_probe.py"); return
        col = lambda k: _smooth([float(r[k]) for r in rows])
        mid = MANIFEST_ID.get(slug, slug + "_swing")
        p, ct = frames.get(mid, (None, None))
        if p is None:
            continue
        p, ct = int(p), int(ct)

        # 2D baseline (ear-mid rel shoulder-mid)
        emx = (col("l_ear_x") + col("r_ear_x")) / 2; emy = (col("l_ear_y") + col("r_ear_y")) / 2
        smx = col("sho_mid_x"); smy = col("sho_mid_y"); hmy = col("hip_mid_y")
        tor2d = float(np.percentile(np.abs(hmy - smy), 95))

        # 3D world (meters, hip-centered)
        wex = (col("w_l_ear_x") + col("w_r_ear_x")) / 2
        wey = (col("w_l_ear_y") + col("w_r_ear_y")) / 2
        wez = (col("w_l_ear_z") + col("w_r_ear_z")) / 2
        wsx = (col("w_l_sho_x") + col("w_r_sho_x")) / 2
        wsy = (col("w_l_sho_y") + col("w_r_sho_y")) / 2
        wsz = (col("w_l_sho_z") + col("w_r_sho_z")) / 2
        whx = (col("w_l_hip_x") + col("w_r_hip_x")) / 2
        why = (col("w_l_hip_y") + col("w_r_hip_y")) / 2
        whz = (col("w_l_hip_z") + col("w_r_hip_z")) / 2
        tor3d = float(np.percentile(np.sqrt((wsx - whx)**2 + (wsy - why)**2 + (wsz - whz)**2), 95))

        def d2(hx, hy, ax, ay, tor):
            dx = (hx[ct] - ax[ct]) - (hx[p] - ax[p]); dy = (hy[ct] - ay[ct]) - (hy[p] - ay[p])
            return math.hypot(dx, dy) / tor

        def d3(ax, ay, az, xy_only=False):
            dx = (wex[ct] - ax[ct]) - (wex[p] - ax[p])
            dy = (wey[ct] - ay[ct]) - (wey[p] - ay[p])
            dz = 0 if xy_only else (wez[ct] - az[ct]) - (wez[p] - az[p])
            return math.sqrt(dx*dx + dy*dy + dz*dz) / tor3d

        vals = {
            "2d_ear_sho":    d2(emx, emy, smx, smy, tor2d),
            "3d_ear_hip":    d3(whx, why, whz),
            "3d_ear_hip_xy": d3(whx, why, whz, xy_only=True),
            "3d_ear_sho":    d3(wsx, wsy, wsz),
            "3d_ear_sho_xy": d3(wsx, wsy, wsz, xy_only=True),
        }
        grp = "INFLATED" if slug in INFLATED else ("control" if slug in CONTROL else "?")
        for v in variants:
            if grp in ("INFLATED", "control"):
                agg[v]["inflated" if slug in INFLATED else "control"].append(vals[v])
        print(f"{slug:18} {grp:9} " + " ".join(f"{vals[v]:14.3f}" for v in variants))

    print("\n=== group means (want INFLATED low, control low) ===")
    print(f"{'variant':16} {'inflated_mean':>14} {'inflated_max':>13} {'control_mean':>14}")
    for v in variants:
        inf, con = agg[v]["inflated"], agg[v]["control"]
        print(f"{v:16} {np.mean(inf):14.3f} {np.max(inf):13.3f} {np.mean(con):14.3f}")


if __name__ == "__main__":
    main()
