#!/usr/bin/env python3
"""
One-time migration: import the legacy file-based players/<slug>/ tree
into Supabase under a single target user.

Why not migrate auth automatically?
-----------------------------------
The old profile.json files only contain PBKDF2 password *hashes* —
plaintext passwords are not recoverable. So we don't try. You sign
up fresh in the new app, then run this script to bring your swing
history + training logs over to your new account.

Usage
-----
    1. Sign up in the new app with the email you want to be your
       primary account. Note the user_id (we print it for you on
       the dashboard once logged in, or pull from Supabase
       Authentication tab).

    2. Get the SERVICE-ROLE key from your Supabase project (Settings ->
       API Keys -> Secret keys). DO NOT commit this key. We use it
       because the migration needs to bypass RLS to write rows.

    3. Run:

           SUPABASE_URL="https://xxxxx.supabase.co" \\
           SUPABASE_SERVICE_KEY="sb_secret_..." \\
           TARGET_USER_ID="<your-auth-user-id>" \\
           TARGET_PLAYER_SLUG="mario-ricard"  \\        # optional: only this folder
           ./venv/bin/python migrate_local_to_supabase.py

    4. The script is idempotent — it skips swings that already
       exist (matched by timestamp_str).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase-py is not installed. Run:\n"
          "    ./venv/bin/pip install supabase")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).parent.resolve()
PLAYERS_DIR  = PROJECT_ROOT / "players"
STORAGE_BUCKET = "swing-media"


def must_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f"ERROR: ${name} environment variable is required.")
        sys.exit(1)
    return v


def main():
    supabase_url     = must_env("SUPABASE_URL")
    service_key      = must_env("SUPABASE_SERVICE_KEY")
    target_user_id   = must_env("TARGET_USER_ID")
    target_slug_only = os.environ.get("TARGET_PLAYER_SLUG")

    sb = create_client(supabase_url, service_key)

    if not PLAYERS_DIR.exists():
        print(f"No legacy players/ directory at {PLAYERS_DIR} — nothing to migrate.")
        return

    player_dirs = [
        p for p in sorted(PLAYERS_DIR.iterdir())
        if p.is_dir() and (p / "profile.json").exists()
    ]
    if target_slug_only:
        player_dirs = [p for p in player_dirs if p.name == target_slug_only]

    if not player_dirs:
        print("No matching player folders found.")
        return

    # We collapse every legacy player folder into the single target
    # auth user. If you want multiple players per account later, the
    # schema already supports it — just relax the unique(user_id)
    # constraint on public.players and tweak the insert below.
    primary_dir = player_dirs[0]
    primary_profile = json.loads((primary_dir / "profile.json").read_text())

    # ---- 1. Ensure a players row exists for the target user ----
    existing = (
        sb.table("players")
          .select("*")
          .eq("user_id", target_user_id)
          .limit(1)
          .execute()
    )
    if existing.data:
        player_row = existing.data[0]
        print(f"Found existing players row {player_row['id']}.")
    else:
        ins = sb.table("players").insert({
            "user_id":   target_user_id,
            "name":      primary_profile.get("name") or "Player",
            "email":     primary_profile.get("email") or "migrated@example.com",
            "handedness":primary_profile.get("handedness") or "RIGHT",
            "height_in": primary_profile.get("height_in"),
            "weight_lb": primary_profile.get("weight_lb"),
            "team":      primary_profile.get("team"),
            "position":  primary_profile.get("position"),
            "throws":    primary_profile.get("throws"),
            "level":     primary_profile.get("level"),
            "primary_goal": primary_profile.get("primary_goal"),
        }).execute()
        player_row = ins.data[0]
        print(f"Created players row {player_row['id']} for user {target_user_id}.")

    player_id = player_row["id"]

    # ---- 2. Migrate every swing in every selected folder ----
    existing_swings = (
        sb.table("swings")
          .select("timestamp_str")
          .eq("player_id", player_id)
          .execute()
    )
    seen_ts = {r["timestamp_str"] for r in (existing_swings.data or []) if r.get("timestamp_str")}

    total_new = 0
    for pdir in player_dirs:
        swings_dir = pdir / "swings"
        if not swings_dir.exists():
            continue
        for swing_path in sorted(swings_dir.glob("*.json")):
            try:
                swing = json.loads(swing_path.read_text())
            except Exception as e:
                print(f"  skip {swing_path.name}: {e}")
                continue

            ts = swing.get("timestamp")
            if ts and ts in seen_ts:
                continue

            # Upload the phase chart if present
            phase_chart_storage = None
            chart_local = swing_path.with_suffix(".png")
            if chart_local.exists():
                object_path = f"{target_user_id}/{player_id}/{ts}_{swing_path.stem}.png"
                try:
                    sb.storage.from_(STORAGE_BUCKET).upload(
                        path=object_path,
                        file=chart_local.read_bytes(),
                        file_options={"content-type": "image/png", "upsert": "true"},
                    )
                    phase_chart_storage = object_path
                except Exception as e:
                    print(f"  phase chart upload failed for {chart_local.name}: {e}")

            sb.table("swings").insert({
                "player_id":          player_id,
                "user_id":            target_user_id,
                "timestamp_str":      swing.get("timestamp"),
                "date_str":           swing.get("date"),
                "filename":           swing.get("filename"),
                "score":              swing.get("score"),
                "score_band_color":   swing.get("score_band_color"),
                "score_band_label":   swing.get("score_band_label"),
                "reference_name":     swing.get("reference_name"),
                "player_handedness":  swing.get("player_handedness"),
                "swing_duration_ms":  swing.get("swing_duration_ms"),
                "narratives":         swing.get("narratives") or [],
                "strengths":          swing.get("strengths") or [],
                "other_observations": swing.get("other_observations") or [],
                "drill_plan":         swing.get("drill_plan") or {},
                "metric_table":       swing.get("metric_table") or {},
                "camera_view":        swing.get("camera_view") or {},
                "slow_mo":            swing.get("slow_mo") or {},
                "phase_chart_path":   phase_chart_storage,
            }).execute()
            total_new += 1
            print(f"  + {pdir.name}/{swing_path.name}")

    print(f"\nImported {total_new} new swings.")

    # ---- 3. Migrate training logs (merge if any) ----
    merged = {"drills": {}, "session_notes": []}
    for pdir in player_dirs:
        log_path = pdir / "training_log.json"
        if log_path.exists():
            try:
                data = json.loads(log_path.read_text())
                merged["drills"].update(data.get("drills", {}))
                merged["session_notes"].extend(data.get("session_notes", []))
            except Exception as e:
                print(f"  training_log skip {pdir.name}: {e}")
    if merged["drills"] or merged["session_notes"]:
        sb.table("training_logs").upsert({
            "player_id":     player_id,
            "user_id":       target_user_id,
            "drill_state":   merged["drills"],
            "session_notes": merged["session_notes"],
            "updated_at":    datetime.utcnow().isoformat(),
        }, on_conflict="player_id").execute()
        print(f"Imported training log "
              f"({len(merged['drills'])} drills, "
              f"{len(merged['session_notes'])} notes).")

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
