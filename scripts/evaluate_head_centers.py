#!/usr/bin/env python3
"""Evaluate candidate head-center definitions for the head-drift fix.

Reads validation/head_probe/<slug>.csv (from head_center_probe.py) + the
verified plant/contact frames from validation/manifest.json, and computes
total_drift_torso under each candidate head-center — all relative to
shoulder-mid and normalized by 95th-pct torso length (matching detect_phases).

GOAL: find the head-center whose drift DROPS on the inflated broadcast clips
(lindor/mookie/schwarber/freeman/yandy) while staying ~unchanged on the
control clips (judge/tucker/yordan). That's the definition that measures head
TRANSLATION (stability) without the nose's rotation arc.
"""
import csv, json, math, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "validation", "head_probe")
MANIFEST = os.path.join(ROOT, "validation", "manifest.json")

INFLATED = {"francisco_lindor", "mookie_betts", "kyle_schwarber", "freddie_freeman", "yandy_diaz"}
CONTROL = {"aaron_judge", "kyle_tucker", "yordan_alvarez"}
# slug -> manifest id (where they differ)
MANIFEST_ID = {"aaron_judge": "judge_swing_copy", "mookie_betts": "mookie_swing",
               "mike_trout": "trout_swing", "shohei_ohtani": "shohei_swing"}


def _smooth(a, w=5):
    a = np.asarray(a, float)
    if len(a) < w:
        return a
    k = np.ones(w) / w
    return np.convolve(a, k, mode="same")


def _load_manifest_frames():
    raw = json.load(open(MANIFEST))["swings"]
    it = raw if isinstance(raw, list) else list(raw.values())
    out = {}
    for s in it:
        gt = s.get("ground_truth", {})
        out[s["id"]] = (gt.get("final_plant_frame"), gt.get("contact_frame"))
    return out


def _candidates(rows):
    """Return dict candidate_name -> (head_x_array, head_y_array) RAW image coords."""
    col = lambda k: np.array([r[k] for r in rows], float)
    nose = (col("nose_x"), col("nose_y"))
    learx, leary, learv = col("l_ear_x"), col("l_ear_y"), col("l_ear_v")
    rearx, reary, rearv = col("r_ear_x"), col("r_ear_y"), col("r_ear_v")
    leyex, leyey = col("l_eye_x"), col("l_eye_y")
    reyex, reyey = col("r_eye_x"), col("r_eye_y")
    ear_mid = ((learx + rearx) / 2, (leary + reary) / 2)
    eye_mid = ((leyex + reyex) / 2, (leyey + reyey) / 2)
    use_l = learv >= rearv
    near_ear = (np.where(use_l, learx, rearx), np.where(use_l, leary, reary))
    skull = ((learx + rearx + leyex + reyex) / 4, (leary + reary + leyey + reyey) / 4)
    # visibility-weighted ear midpoint (down-weight an occluded/hallucinated ear)
    wl = np.clip(learv, 1e-3, None); wr = np.clip(rearv, 1e-3, None)
    vwear = ((learx * wl + rearx * wr) / (wl + wr),
             (leary * wl + reary * wr) / (wl + wr))
    return {"nose": nose, "ear_mid": ear_mid, "eye_mid": eye_mid,
            "near_ear": near_ear, "skull4": skull, "vwear": vwear}


def _at(arr, idx, win=0):
    """Value at idx, optionally the median over [idx-win, idx+win] (glitch-robust)."""
    if win <= 0:
        return arr[idx]
    lo, hi = max(0, idx - win), min(len(arr), idx + win + 1)
    return float(np.median(arr[lo:hi]))


def _drift(head_xy, rows, plant, contact, anchor="sho", win=0):
    hx, hy = head_xy
    sho_x = np.array([r["sho_mid_x"] for r in rows], float)
    sho_y = np.array([r["sho_mid_y"] for r in rows], float)
    hip_x = np.array([r["hip_mid_x"] for r in rows], float)
    hip_y = np.array([r["hip_mid_y"] for r in rows], float)
    ax = sho_x if anchor == "sho" else hip_x
    ay = sho_y if anchor == "sho" else hip_y
    rel_x = _smooth(hx) - _smooth(ax)
    rel_y = _smooth(hy) - _smooth(ay)
    torso = np.abs(_smooth(hip_y) - _smooth(sho_y))
    ref_torso = float(np.percentile(torso, 95))
    if ref_torso <= 1 or plant is None or contact is None:
        return None
    dx = _at(rel_x, contact, win) - _at(rel_x, plant, win)
    dy = _at(rel_y, contact, win) - _at(rel_y, plant, win)
    return math.hypot(dx, dy) / ref_torso


def main():
    frames = _load_manifest_frames()
    # (label, head-center, anchor, median-window)
    variants = [
        ("nose",            "nose",    "sho", 0),
        ("ear_mid",         "ear_mid", "sho", 0),
        ("ear_mid+med5",    "ear_mid", "sho", 2),
        ("vwear+med5",      "vwear",   "sho", 2),
        ("ear_mid@hip+med5","ear_mid", "hip", 2),
        ("vwear@hip+med5",  "vwear",   "hip", 2),
    ]
    labels = [v[0] for v in variants]
    print(f"{'clip':18} {'grp':9} " + " ".join(f"{l:>15}" for l in labels))
    results = {l: {"inflated": [], "control": []} for l in labels}
    for fn in sorted(os.listdir(PROBE)):
        if not fn.endswith(".csv"):
            continue
        slug = fn[:-4]
        rows = list(csv.DictReader(open(os.path.join(PROBE, fn))))
        rows = [{k: float(v) for k, v in r.items()} for r in rows]
        mid = MANIFEST_ID.get(slug, slug + "_swing")
        plant, contact = frames.get(mid, (None, None))
        if plant is not None:
            plant, contact = int(plant), int(contact)
        cands = _candidates(rows)
        grp = "INFLATED" if slug in INFLATED else ("control" if slug in CONTROL else "?")
        vals = []
        for (label, hc, anchor, win) in variants:
            d = _drift(cands[hc], rows, plant, contact, anchor=anchor, win=win)
            vals.append(d)
            if d is not None and grp in ("INFLATED", "control"):
                results[label]["inflated" if slug in INFLATED else "control"].append(d)
        print(f"{slug:18} {grp:9} " + " ".join(
            (f"{v:15.3f}" if v is not None else f"{'—':>15}") for v in vals))

    print("\n=== group means (want INFLATED low AND control low) ===")
    print(f"{'variant':18} {'inflated_mean':>14} {'inflated_max':>13} {'control_mean':>14}")
    for l in labels:
        inf = results[l]["inflated"]; con = results[l]["control"]
        im = np.mean(inf) if inf else float("nan")
        ix = np.max(inf) if inf else float("nan")
        cm = np.mean(con) if con else float("nan")
        print(f"{l:18} {im:14.3f} {ix:13.3f} {cm:14.3f}")


if __name__ == "__main__":
    main()
