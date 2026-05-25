#!/usr/bin/env python3
"""
Rebuild the 17 MLB reference fingerprints from their source clips, anchored on
hand-verified ground-truth phase frames.

WHY: the live references were built by the auto-detector, which locked onto the
WRONG swing on these multi-event slow-mo broadcast clips (e.g. torkelson's
foot_plant landed 300+ frames into a second swing). This rebuild instead forces
detect_phases to use the validation manifest's verified foot_plant + contact
labels (via --swing-center/--foot-plant/--contact), so each reference is
computed at the correct swing. The match vector is ratio/spatial based, so it is
slow-mo invariant — the (often mis-detected) slow-mo factor doesn't affect it.

SAFETY: writes to references_rebuilt/ (staging) — does NOT touch the live
references/ until a human verifies the montages and promotes them. Emits one
verification montage per clip (forced foot_plant + contact frames) and a sanity
table (corrected swing duration should be ~120-300ms).

Usage:
  .venv/bin/python scripts/rebuild_references.py            # all 17
  .venv/bin/python scripts/rebuild_references.py aaron_judge mike_trout  # subset
"""
from __future__ import annotations
import json, os, subprocess, sys, glob, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(REPO, "references")
STAGE = os.path.join(REPO, "references_rebuilt")
VERIFY = os.path.join(STAGE, "_verify")
MANIFEST = os.path.join(REPO, "validation", "manifest.json")

# reference slug -> labeled manifest entry id (where names differ)
ALIAS = {"aaron_judge": "judge_swing_copy", "mike_trout": "trout_swing",
         "mookie_betts": "mookie_swing", "shohei_ohtani": "shohei_swing"}


def manifest_id(slug, byid):
    for c in [ALIAS.get(slug), f"{slug}_swing", slug, slug.replace("_jr", "") + "_swing"]:
        if c and c in byid:
            return c
    return None


def run_one(slug, ref_meta, gt, video, out_dir):
    """Run detect_phases anchored on the verified labels; return fingerprint dict."""
    plant, contact = gt["final_plant_frame"], gt["contact_frame"]
    hand = (ref_meta.get("handedness") or "AUTO").upper()
    base = os.path.splitext(os.path.basename(video))[0]
    cmd = [sys.executable, os.path.join(REPO, "detect_phases.py"), video]
    if hand in ("LEFT", "RIGHT"):
        cmd.append(hand)
    cmd += ["--swing-center", str(contact), "--foot-plant", str(plant), "--contact", str(contact)]
    subprocess.run(cmd, cwd=REPO, check=True, capture_output=True, text=True, timeout=600)
    fp_path = os.path.join(REPO, f"{base}_fingerprint.json")
    with open(fp_path) as f:
        fp = json.load(f)
    # clean detect_phases' stray outputs from the repo root
    for ext in ("_fingerprint.json", "_metrics.csv", "_phases.png",
                "_phases_debug.json", "_detector_v4.json"):
        p = os.path.join(REPO, f"{base}{ext}")
        if os.path.exists(p):
            os.remove(p)
    return fp


def montage(slug, video, fp):
    import cv2, numpy as np
    pf = fp["phases_frame"]
    cap = cv2.VideoCapture(video)
    marks = [("load", pf["load_start"]), ("PLANT", pf["foot_plant"]),
             ("launch", pf["launch"]), ("CONTACT", pf["contact"]),
             ("peak_rot", pf["peak_rotation"]), ("finish", pf["finish"])]
    tiles = []
    for lab, fr in marks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr); ok, img = cap.read()
        if not ok:
            continue
        img = cv2.resize(img, (260, 150))
        cv2.rectangle(img, (0, 0), (260, 18), (0, 0, 0), -1)
        cv2.putText(img, f"{lab} f{fr}", (4, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        tiles.append(img)
    cap.release()
    if not tiles:
        return
    grid = np.zeros((150, 260 * len(tiles), 3), dtype=np.uint8)
    for i, t in enumerate(tiles):
        grid[:, i * 260:(i + 1) * 260] = t
    cv2.imwrite(os.path.join(VERIFY, f"{slug}.jpg"), grid)


def main():
    os.makedirs(VERIFY, exist_ok=True)
    byid = {s["id"]: s for s in json.load(open(MANIFEST))["swings"]}
    want = sys.argv[1:] or [os.path.splitext(os.path.basename(p))[0]
                            for p in sorted(glob.glob(os.path.join(REFS, "*.json")))]
    rows = []
    for slug in want:
        ref_meta = json.load(open(os.path.join(REFS, f"{slug}.json")))
        mid = manifest_id(slug, byid)
        if not mid:
            print(f"  ✗ {slug}: no manifest label"); continue
        entry = byid[mid]; gt = entry["ground_truth"]; video = entry["video_path"]
        if not (video and os.path.exists(video)):
            print(f"  ✗ {slug}: source clip missing ({video})"); continue
        try:
            fp = run_one(slug, ref_meta, gt, video, STAGE)
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {slug}: detect_phases failed: {e.stderr[-300:] if e.stderr else e}")
            continue
        # preserve metadata, swap in the corrected fingerprint
        enriched = {k: ref_meta.get(k, "") for k in
                    ("player_name", "team", "position", "swing_style", "added_at", "source_clip")}
        enriched.update(fp)
        with open(os.path.join(STAGE, f"{slug}.json"), "w") as f:
            json.dump(enriched, f, indent=2)
        montage(slug, video, fp)
        pf = fp["phases_frame"]
        corr = (fp.get("timing_ms_corrected") or {}).get("total_swing")
        sane = "ok" if (corr and 110 <= corr <= 320) else "CHECK"
        rows.append((slug, pf["foot_plant"], pf["contact"], fp.get("slow_mo_factor"), corr, sane))
        print(f"  ✓ {slug:22} plant={pf['foot_plant']:>5} contact={pf['contact']:>5} "
              f"slowmo={fp.get('slow_mo_factor',0):.1f}x corrected_swing={corr:.0f}ms [{sane}]")
    print(f"\nStaged {len(rows)} references -> {STAGE}")
    print("Verify montages in", VERIFY, "then promote with: mv references_rebuilt/*.json references/")
    flagged = [r[0] for r in rows if r[5] != "ok"]
    if flagged:
        print("  ⚠ sanity-CHECK (corrected swing out of 110-320ms):", flagged)


if __name__ == "__main__":
    main()
