#!/usr/bin/env python3
"""
Minimal keyboard-driven re-labeler for the 17 MLB reference clips.

Opens each clip's video in an OpenCV window. Scrub with keys, mark contact +
foot_plant, save, auto-advance. Writes back to validation/manifest.json
(atomic rename).

Run:
    .venv/bin/python scripts/validation/relabel_refs.py

Keys (shown on the overlay too):
    .  / ,   +1 / -1 frame
    >  / <   +10 / -10 frames    (Shift + . / ,)
    ]  / [   +30 / -30 frames
    /        jump to a frame (type number + Enter)
    c        mark current frame as CONTACT
    p        mark current frame as foot_PLANT
    s        SAVE this clip + advance to the next
    n        skip this clip WITHOUT saving
    b        go BACK one clip (re-open the previous)
    r        RESET marks to the values currently in manifest.json
    h        HELP overlay on/off
    q        quit (no save of the current clip)

Notes:
- The window opens at the current saved contact frame so you see the existing
  label first; adjust by scrubbing.
- Contact = bat in the hitting zone (arms extended toward pitcher); NOT
  follow-through (bat wrapped around).
- foot_plant = last frame the front foot is on the ground BEFORE rotation
  begins.
- Save is atomic: writes manifest.json.tmp, then os.rename.
"""
from __future__ import annotations
import json, os, sys
import cv2

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANIFEST = os.path.join(REPO, "validation", "manifest.json")
REFS_DIR = os.path.join(REPO, "references")
ALIAS = {"aaron_judge": "judge_swing_copy", "mike_trout": "trout_swing",
         "mookie_betts": "mookie_swing", "shohei_ohtani": "shohei_swing"}


def manifest_id(slug, byid):
    for c in [ALIAS.get(slug), f"{slug}_swing", slug, slug.replace("_jr", "") + "_swing"]:
        if c and c in byid:
            return c
    return None


def load_manifest():
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(m):
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f, indent=2)
    os.rename(tmp, MANIFEST)


def ref_slugs():
    import glob
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(REFS_DIR, "*.json")))


def draw_overlay(img, *, clip_no, total, slug, vid_name, frame, n_frames,
                 plant, contact, marked_plant, marked_contact, show_help):
    h, w = img.shape[:2]
    bar_h = 90
    img = img.copy()
    cv2.rectangle(img, (0, 0), (w, bar_h), (0, 0, 0), -1)
    cv2.putText(img, f"[{clip_no:>2}/{total}] {slug}  ({vid_name})",
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, f"frame  {frame:>5} / {n_frames}",
                (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
    p_str = f"PLANT  saved={plant}  marked={marked_plant if marked_plant is not None else '-'}"
    c_str = f"CONTACT  saved={contact}  marked={marked_contact if marked_contact is not None else '-'}"
    cv2.putText(img, p_str, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (180, 220, 255) if marked_plant is None else (140, 255, 140), 1, cv2.LINE_AA)
    cv2.putText(img, c_str, (380, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (180, 220, 255) if marked_contact is None else (140, 255, 140), 1, cv2.LINE_AA)
    if show_help:
        help_lines = [
            ".  ,  +/-1 frame    > <  +/-10    ] [  +/-30    /  jump-to",
            "c  mark contact     p  mark plant",
            "s  save & next      n  skip       b  back-clip   r  reset",
            "h  toggle help      q  quit",
        ]
        hh = 20 * len(help_lines) + 12
        cv2.rectangle(img, (0, h - hh), (w, h), (0, 0, 0), -1)
        for i, ln in enumerate(help_lines):
            cv2.putText(img, ln, (10, h - hh + 18 + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    return img


def prompt_jump(window, n_frames):
    """Modal-ish: read digits into a buffer until Enter; show on overlay."""
    buf = ""
    while True:
        k = cv2.waitKey(0) & 0xFF
        if k in (13, 10):  # Enter
            try:
                return max(0, min(n_frames - 1, int(buf)))
            except ValueError:
                return None
        if k == 27 or k == ord("q"):  # Esc / q cancels
            return None
        if k == 8 or k == 127:  # Backspace / DEL
            buf = buf[:-1]
        elif chr(k).isdigit():
            buf += chr(k)
        # Re-render with the in-progress buffer in the title bar
        try:
            cv2.setWindowTitle(window, f"jump to frame: {buf}_  (Enter=go, Esc=cancel)")
        except cv2.error:
            pass


def label_clip(slug, entry, clip_no, total):
    vp = entry["video_path"]
    if not (vp and os.path.exists(vp)):
        print(f"  ✗ {slug}: video missing ({vp})")
        return None  # caller skips
    cap = cv2.VideoCapture(vp)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    gt = entry["ground_truth"]
    saved_plant, saved_contact = gt["final_plant_frame"], gt["contact_frame"]
    marked_plant = None
    marked_contact = None
    frame = max(0, min(int(saved_contact or 0), n_frames - 1))
    window = "relabel_refs"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 760)
    show_help = True
    vid_name = os.path.basename(vp)
    action = None   # 'save', 'skip', 'back', 'quit'

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, img = cap.read()
        if not ok:
            # End of file or unreadable frame — step back
            frame = max(0, frame - 1); continue
        try:
            cv2.setWindowTitle(window, f"{slug}  ({clip_no}/{total})")
        except cv2.error:
            pass
        disp = draw_overlay(img, clip_no=clip_no, total=total, slug=slug,
                            vid_name=vid_name, frame=frame, n_frames=n_frames,
                            plant=saved_plant, contact=saved_contact,
                            marked_plant=marked_plant, marked_contact=marked_contact,
                            show_help=show_help)
        cv2.imshow(window, disp)
        k = cv2.waitKey(0) & 0xFF
        ch = chr(k) if 32 <= k < 127 else ""
        if ch == ".":   frame = min(n_frames - 1, frame + 1)
        elif ch == ",": frame = max(0, frame - 1)
        elif ch == ">": frame = min(n_frames - 1, frame + 10)
        elif ch == "<": frame = max(0, frame - 10)
        elif ch == "]": frame = min(n_frames - 1, frame + 30)
        elif ch == "[": frame = max(0, frame - 30)
        elif ch == "/":
            tgt = prompt_jump(window, n_frames)
            if tgt is not None:
                frame = tgt
        elif ch == "c": marked_contact = frame
        elif ch == "p": marked_plant = frame
        elif ch == "r":
            marked_plant = None
            marked_contact = None
        elif ch == "h": show_help = not show_help
        elif ch == "s": action = "save"; break
        elif ch == "n": action = "skip"; break
        elif ch == "b": action = "back"; break
        elif ch == "q": action = "quit"; break
        # else: ignore (keeps the window responsive)

    cap.release()
    return {
        "action": action,
        "plant": marked_plant if marked_plant is not None else saved_plant,
        "contact": marked_contact if marked_contact is not None else saved_contact,
        "changed_plant": marked_plant is not None,
        "changed_contact": marked_contact is not None,
    }


def main():
    m = load_manifest()
    byid = {s["id"]: s for s in m["swings"]}
    slugs = ref_slugs()
    if len(sys.argv) > 1:
        # Optional: limit to specific slugs from CLI
        wanted = set(sys.argv[1:])
        slugs = [s for s in slugs if s in wanted]

    # Map ref-slug -> manifest entry for the labeled clip
    work = []
    for slug in slugs:
        mid = manifest_id(slug, byid)
        if not mid:
            print(f"  ✗ {slug}: no manifest entry"); continue
        work.append((slug, byid[mid]))
    if not work:
        print("nothing to label"); return

    print(f"Re-labeling {len(work)} reference clips. Window opens for each;")
    print("close it (or press 'q') to quit. Hit 'h' in-window to toggle help.\n")

    i = 0
    while 0 <= i < len(work):
        slug, entry = work[i]
        print(f"[{i+1}/{len(work)}] {slug}  -> {entry['video_path']}")
        result = label_clip(slug, entry, clip_no=i + 1, total=len(work))
        if result is None:
            i += 1; continue
        if result["action"] == "save":
            entry["ground_truth"]["final_plant_frame"] = int(result["plant"])
            entry["ground_truth"]["contact_frame"] = int(result["contact"])
            entry["labeled_by"] = entry.get("labeled_by") or "logan (re-labeled 2026-05-26)"
            entry["labeled_at"] = "2026-05-26"
            save_manifest(m)
            print(f"  ✓ saved: plant={result['plant']} contact={result['contact']}"
                  + (" [plant changed]" if result["changed_plant"] else "")
                  + (" [contact changed]" if result["changed_contact"] else ""))
            i += 1
        elif result["action"] == "skip":
            print("  · skipped (no save)")
            i += 1
        elif result["action"] == "back":
            i = max(0, i - 1)
        elif result["action"] == "quit":
            print("\nquit; progress saved on each 's'."); break
    cv2.destroyAllWindows()
    print("\ndone.")


if __name__ == "__main__":
    main()
