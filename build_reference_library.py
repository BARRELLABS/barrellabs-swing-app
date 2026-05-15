"""
Ingest a new MLB hitter video into the reference library.

What it does:
  1. Runs detect_phases.py on the input video (as a subprocess) to produce
     a fingerprint JSON with all the phase / rotation / head metrics.
  2. Adds reference-library metadata (player_name, team, position,
     swing_style, source_clip, added_at).
  3. Writes the result to references/<slug>.json.

After this, compare.py will automatically discover the new reference and
auto-pick it for player clips that share its handedness and camera angle.

Usage:
    python build_reference_library.py <video> --name "<Player Name>"
                                              [--handedness LEFT|RIGHT]
                                              [--team "<Team>"]
                                              [--position "<Position>"]
                                              [--style "<Swing style note>"]
                                              [--slug <override_slug>]

Examples:
    python build_reference_library.py judge_swing.mp4 \\
        --name "Aaron Judge" --team "Yankees" --position "OF" \\
        --style "Long levers, plus power, vertical bat path"

    python build_reference_library.py soto_swing.mp4 \\
        --name "Juan Soto" --handedness LEFT --team "Yankees" \\
        --style "Patient, picks his pitch, plus contact, plus power"

To list everything currently in the library:
    python build_reference_library.py --list
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

from reference_library import REFERENCES_DIR, list_references


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "reference"


def run_detect_phases(video_path: str, handedness: str = "AUTO") -> str:
    """Run detect_phases.py on the video. Returns the path to the produced
    fingerprint JSON. Raises RuntimeError on failure.
    """
    if not os.path.isfile(video_path):
        raise RuntimeError(f"Video not found: {video_path}")

    # detect_phases.py writes outputs into the current working directory,
    # using the video's basename as the prefix. Run it from a tmp dir so we
    # don't pollute the project root with intermediate CSVs / charts.
    here = os.path.dirname(os.path.abspath(__file__))
    detect_script = os.path.join(here, "detect_phases.py")
    if not os.path.isfile(detect_script):
        raise RuntimeError(f"detect_phases.py not found at {detect_script}")

    base = os.path.splitext(os.path.basename(video_path))[0]
    fingerprint_path = os.path.join(here, f"{base}_fingerprint.json")

    cmd = [sys.executable, detect_script, video_path]
    if handedness in ("LEFT", "RIGHT"):
        cmd.append(handedness)

    print(f"  Running: {' '.join(cmd)}")
    try:
        # Show output live so the user can see pose-extraction progress.
        result = subprocess.run(cmd, cwd=here, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"detect_phases.py failed (exit {e.returncode})")

    if not os.path.isfile(fingerprint_path):
        raise RuntimeError(
            f"Expected fingerprint not found: {fingerprint_path}"
        )
    return fingerprint_path


def list_command():
    refs = list_references()
    if not refs:
        print("Reference library is empty.")
        print(f"Add a clip with:  python {os.path.basename(__file__)} <video> --name '<Player Name>'")
        return
    print(f"Reference library — {len(refs)} player(s):")
    print("-" * 80)
    print(f"{'SLUG':<22}{'PLAYER':<22}{'HAND':<8}{'METHOD':<18}{'VIEW':<8}STYLE")
    print("-" * 80)
    for r in refs:
        style = r["swing_style"][:30] + ("…" if len(r["swing_style"]) > 30 else "")
        print(f"{r['slug']:<22}{r['player_name']:<22}{r['handedness']:<8}"
              f"{r['rotation_method']:<18}{r['camera_view_ratio']:<8.2f}{style}")


def build_command(args):
    if not args.name:
        print("ERROR: --name is required (e.g. --name 'Aaron Judge')")
        sys.exit(1)

    slug = args.slug or slugify(args.name)
    out_path = os.path.join(REFERENCES_DIR, f"{slug}.json")
    os.makedirs(REFERENCES_DIR, exist_ok=True)

    if os.path.isfile(out_path) and not args.overwrite:
        print(f"ERROR: {out_path} already exists. Use --overwrite to replace it.")
        sys.exit(1)

    print(f"Adding {args.name} ({slug}) to the reference library...")
    fingerprint_path = run_detect_phases(args.video, args.handedness or "AUTO")

    with open(fingerprint_path) as f:
        fp = json.load(f)

    # Sanity warnings — surface issues that would make this a bad reference.
    fps = fp.get("fps", 0)
    total_swing = fp.get("timing_ms", {}).get("total_swing", 0)
    slow_mo_factor = fp.get("slow_mo_factor", 1.0)
    corrected_swing = fp.get("timing_ms_corrected", {}).get("total_swing", total_swing)
    if slow_mo_factor > 1.0:
        print(f"  ⚙  Slow-motion detected ({slow_mo_factor:.1f}× playback). Timing")
        print(f"     values will be auto-corrected to real-time equivalents")
        print(f"     (raw {total_swing:.0f}ms → corrected ~{corrected_swing:.0f}ms swing).")
    rot_method = fp.get("rotation_method", "?")
    print(f"  Detected handedness:  {fp.get('handedness','?')}")
    print(f"  Rotation method:      {rot_method}")
    print(f"  Camera view ratio:    {fp.get('camera_view',{}).get('hip_to_torso_ratio_stance',0):.2f}")
    if slow_mo_factor > 1.0:
        print(f"  Swing duration:       raw {total_swing:.0f}ms → corrected {corrected_swing:.0f}ms (slow_mo={slow_mo_factor:.1f}×)")
    else:
        print(f"  FPS / swing duration: {fps:.1f} / {total_swing:.0f}ms (real-time)")

    # Build the reference record. Reference JSONs intentionally keep the
    # fingerprint's keys at the top level (so compare.py loads them
    # unchanged); the metadata is just additional fields.
    enriched = {
        "player_name":  args.name,
        "team":         args.team or "",
        "position":     args.position or "",
        "swing_style":  args.style or "",
        "added_at":     datetime.date.today().isoformat(),
        "source_clip":  os.path.basename(args.video),
    }
    enriched.update(fp)

    with open(out_path, "w") as f:
        json.dump(enriched, f, indent=2)

    print(f"\n  ✓  Saved reference → {out_path}")
    print(f"\n  compare.py will now auto-pick {args.name} when filming angle matches.")
    print(f"  Force-pick with:  python compare.py <player_fp.json> --reference {slug}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a video into the MLB reference library, or list current references."
    )
    parser.add_argument("video", nargs="?", help="Path to MLB hitter video clip")
    parser.add_argument("--name", help="Player display name, e.g. 'Aaron Judge'")
    parser.add_argument("--handedness", choices=["LEFT", "RIGHT", "AUTO"],
                        default="AUTO", help="Override auto-detect")
    parser.add_argument("--team", help="Team name (optional metadata)")
    parser.add_argument("--position", help="Position (optional metadata)")
    parser.add_argument("--style", help="Brief swing style description")
    parser.add_argument("--slug", help="Override the auto-derived slug (default: slugified player name)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace an existing reference with the same slug")
    parser.add_argument("--list", action="store_true",
                        help="List all references currently in the library")
    args = parser.parse_args()

    if args.list:
        list_command()
        return

    if not args.video:
        parser.print_help()
        sys.exit(1)

    build_command(args)


if __name__ == "__main__":
    main()
