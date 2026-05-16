"""
Player storage — Supabase edition.

This is a drop-in replacement for the original file-based player_storage.
The function names and shapes match the old API so the rest of the app
(app.py, development_tracker.py, historical_charts.py) keeps working
with one-line swaps.

Behind the scenes:
  - Profiles  -> public.players      (one row per auth.users account)
  - Swings    -> public.swings       (one row per saved analysis)
  - Auth      -> Supabase auth.users (email + password)

The old players/<slug>/ JSON tree is kept on disk as a local cache /
migration source only — see migrate_local_to_supabase.py.

NOTE on "slug": the rest of the UI passes around `user["slug"]` as the
identifier for a player. We map slug -> players.id (uuid) at the auth
layer, so any function in this module that takes `player_slug` is
actually receiving the players.id UUID.
"""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from supabase_client import get_client
from auth import (
    sign_up as _sign_up,
    sign_in as _sign_in,
    sign_out as _sign_out,
    current_profile as _current_profile,
    update_profile as _update_profile_remote,
    ALLOWED_PROFILE_UPDATES,
)


PROJECT_ROOT = Path(__file__).parent.resolve()
LEGACY_PLAYERS_DIR = PROJECT_ROOT / "players"  # kept for read-only migration
STORAGE_BUCKET = "swing-media"


# --------------------------------------------------------------------
#  Tiny helpers retained from the old module
# --------------------------------------------------------------------
def slugify(name: str) -> str:
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "player"


def _email_normalize(email: str) -> str:
    return (email or "").strip().lower()


# --------------------------------------------------------------------
#  Public index (kept for legacy callers, e.g. anything that listed
#  every player). For Supabase, every logged-in user only sees their
#  own player thanks to RLS, so this returns just the current profile
#  in a list-of-one shape.
# --------------------------------------------------------------------
def load_player_index() -> list:
    profile = _current_profile()
    if not profile:
        return []
    return [{
        "slug":       profile.get("id") or profile.get("slug"),
        "name":       profile.get("name"),
        "email":      profile.get("email"),
        "created_at": profile.get("created_at"),
    }]


def find_player_by_email(email: str) -> Optional[dict]:
    """
    Look up a public index entry for an email. With Supabase + RLS we
    can only see our own row, so this only returns a value when the
    currently logged-in user matches.
    """
    email_norm = _email_normalize(email)
    profile = _current_profile()
    if profile and _email_normalize(profile.get("email", "")) == email_norm:
        return {
            "slug":       profile.get("id"),
            "name":       profile.get("name"),
            "email":      profile.get("email"),
            "created_at": profile.get("created_at"),
        }
    return None


# --------------------------------------------------------------------
#  Profile (a logged-in user can only see their own row)
# --------------------------------------------------------------------
def load_profile(slug: str) -> Optional[dict]:
    """Return the profile for the given players.id (slug). RLS will
    refuse if it isn't owned by the current user, which is the point."""
    profile = _current_profile()
    if not profile:
        return None
    if str(profile.get("id")) == str(slug) or str(profile.get("slug")) == str(slug):
        return profile
    # Fallback: try a direct fetch (RLS will block foreign rows).
    sb = get_client()
    try:
        resp = sb.table("players").select("*").eq("id", slug).limit(1).execute()
        rows = resp.data or []
        if rows:
            from auth import _profile_from_row  # local import to avoid cycle
            return _profile_from_row(rows[0])
    except Exception:
        return None
    return None


# --------------------------------------------------------------------
#  Auth (thin facade — real work happens in auth.py)
# --------------------------------------------------------------------
def create_account(
    name: str,
    email: str,
    password: str,
    handedness: str,
    height_in=None,
    weight_lb=None,
) -> dict:
    """Legacy-compatible signup. Wraps auth.sign_up()."""
    return _sign_up(
        name=name,
        email=email,
        password=password,
        handedness=handedness,
        height_in=height_in,
        weight_lb=weight_lb,
    )


def authenticate(email: str, password: str) -> Optional[dict]:
    """Legacy-compatible login. Returns the profile dict or None."""
    try:
        return _sign_in(email, password)
    except ValueError:
        return None
    except Exception:
        return None


def update_profile(slug: str, **fields) -> Optional[dict]:
    """
    Patch fields on the players row. Whitelisted via ALLOWED_PROFILE_UPDATES
    upstream in auth.update_profile().
    """
    return _update_profile_remote(slug, **fields)


# --------------------------------------------------------------------
#  Swing records
# --------------------------------------------------------------------
def _upload_phase_chart(player_id: str, timestamp: str, safe_name: str,
                        local_path: Path) -> Optional[str]:
    """
    Upload the phase chart PNG into Supabase Storage under
    <user_uid>/<player_id>/<timestamp>_<name>.png so RLS lets only
    the owner read it. Returns the storage path, or None on failure.
    """
    sb = get_client()
    user = sb.auth.get_user()
    user_obj = getattr(user, "user", None)
    if not user_obj:
        return None
    uid = user_obj.id

    object_path = f"{uid}/{player_id}/{timestamp}_{safe_name}.png"
    try:
        with open(local_path, "rb") as fh:
            sb.storage.from_(STORAGE_BUCKET).upload(
                path=object_path,
                file=fh.read(),
                file_options={"content-type": "image/png", "upsert": "true"},
            )
        return object_path
    except Exception:
        return None


_VIDEO_CONTENT_TYPES = {
    "mp4":  "video/mp4",
    "mov":  "video/quicktime",
    "m4v":  "video/x-m4v",
    "webm": "video/webm",
    "avi":  "video/x-msvideo",
    "mkv":  "video/x-matroska",
}


def _upload_swing_video(player_id: str, timestamp: str, safe_name: str,
                        local_path: Path) -> Optional[str]:
    """
    Upload the raw swing video into Supabase Storage under
    <user_uid>/<player_id>/<timestamp>_<name>.<ext> so RLS lets only
    the owner read it. Returns the storage path, or None on failure.

    Entitlement: video persistence is a Pro-only feature. For Free users
    the analysis still saves (so the report renders and counts toward
    the lifetime cap), but the video itself isn't uploaded — video_path
    stays NULL. This degrades gracefully on the saved-report view, which
    already handles missing videos.
    """
    # Pro-only gate — silently skip the upload for Free users. We import
    # locally to avoid pulling subscription_storage at module import time
    # (keeps player_storage usable in standalone scripts / migrations).
    try:
        from entitlements import can_save_video
        from subscription_storage import load_my_plan
        if not can_save_video(load_my_plan()):
            return None
    except Exception:
        # If anything in the entitlement chain blows up, fail closed
        # (don't upload). The swing row still saves.
        return None

    sb = get_client()
    user = sb.auth.get_user()
    user_obj = getattr(user, "user", None)
    if not user_obj:
        return None
    uid = user_obj.id

    ext = (Path(local_path).suffix or ".mp4").lstrip(".").lower() or "mp4"
    content_type = _VIDEO_CONTENT_TYPES.get(ext, "video/mp4")

    object_path = f"{uid}/{player_id}/{timestamp}_{safe_name}.{ext}"
    try:
        with open(local_path, "rb") as fh:
            sb.storage.from_(STORAGE_BUCKET).upload(
                path=object_path,
                file=fh.read(),
                file_options={"content-type": content_type, "upsert": "true"},
            )
        return object_path
    except Exception:
        return None


def _upload_swing_pose_json(player_id: str, timestamp: str, safe_name: str,
                            pose_payload: dict) -> Optional[str]:
    """
    Upload the per-frame pose JSON (pose_frames + pose_meta) for a single
    swing into Supabase Storage under
    <user_uid>/<player_id>/<timestamp>_<name>.pose.json so RLS lets only
    the owner read it. Returns the storage path, or None on failure.

    Stored as a separate Storage object (not inline in the swings row) so
    the dashboard's recent-swing list stays light — pose JSON is only
    fetched when a specific swing report is opened.

    Entitlement: pose persistence is a Pro-only feature. Free users get
    the analysis numbers and their 1-3 free swings, but the side-by-side
    skeleton overlay is gated behind Pro. We mirror the video-upload
    pattern: silently skip for Free, swing row still saves (pose_path
    stays NULL), report falls back to "Upgrade to see overlay" CTA.
    """
    # Pro-only gate — mirror the video-upload pattern. Local imports keep
    # this module usable in standalone scripts that don't load entitlements.
    try:
        from entitlements import can_save_video
        from subscription_storage import load_my_plan
        if not can_save_video(load_my_plan()):
            return None
    except Exception:
        # Fail closed — if anything in the entitlement chain blows up,
        # skip the pose upload. The swing row still saves without it.
        return None

    sb = get_client()
    user = sb.auth.get_user()
    user_obj = getattr(user, "user", None)
    if not user_obj:
        return None
    uid = user_obj.id

    import json as _json
    try:
        body = _json.dumps(pose_payload).encode("utf-8")
    except Exception:
        return None

    object_path = f"{uid}/{player_id}/{timestamp}_{safe_name}.pose.json"
    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=object_path,
            file=body,
            file_options={"content-type": "application/json", "upsert": "true"},
        )
        return object_path
    except Exception:
        return None


def get_swing_pose_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    """Return a short-lived signed URL for a pose JSON object in
    Supabase Storage. Returns None if storage_path is empty or the URL
    can't be minted.
    """
    if not storage_path:
        return None
    try:
        sb = get_client()
        resp = sb.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, expires_in)
        return (resp or {}).get("signedURL") or (resp or {}).get("signed_url")
    except Exception:
        return None


def save_swing_record(player: dict, upload_name: str, result: dict,
                      phase_chart_path: Optional[str] = None,
                      video_path: Optional[str] = None,
                      pose_payload: Optional[dict] = None) -> dict:
    """
    Insert a swings row tied to the current player + auth user. Returns
    the inserted row (with the same key names the rest of the app
    already reads).
    """
    sb = get_client()
    user_resp = sb.auth.get_user()
    user_obj = getattr(user_resp, "user", None)
    if not user_obj:
        raise RuntimeError("Not logged in — cannot save swing.")

    player_id = player.get("id") or player.get("slug")
    if not player_id:
        raise RuntimeError("No player_id available — cannot save swing.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = slugify(Path(upload_name).stem)

    chart_path = None
    if phase_chart_path and Path(phase_chart_path).is_file():
        chart_path = _upload_phase_chart(
            player_id=player_id,
            timestamp=timestamp,
            safe_name=safe_name,
            local_path=Path(phase_chart_path),
        )

    video_storage_path = None
    if video_path and Path(video_path).is_file():
        video_storage_path = _upload_swing_video(
            player_id=player_id,
            timestamp=timestamp,
            safe_name=safe_name,
            local_path=Path(video_path),
        )

    pose_storage_path = None
    if pose_payload:
        pose_storage_path = _upload_swing_pose_json(
            player_id=player_id,
            timestamp=timestamp,
            safe_name=safe_name,
            pose_payload=pose_payload,
        )

    row = {
        "player_id":          player_id,
        "user_id":            user_obj.id,
        "timestamp_str":      timestamp,
        "date_str":           datetime.now().strftime("%b %d, %Y"),
        "filename":           upload_name,
        "score":              result.get("score"),
        "score_band_color":   result.get("score_band_color"),
        "score_band_label":   result.get("score_band_label"),
        "reference_name":     result.get("reference", {}).get("name"),
        "player_handedness":  result.get("player_handedness"),
        "swing_duration_ms":  result.get("slow_mo", {}).get("player_corrected_swing_ms"),
        "narratives":         result.get("narratives", []) or [],
        "strengths":          result.get("strengths", []) or [],
        "other_observations": result.get("other_observations", []) or [],
        "drill_plan":         result.get("drill_plan", {}) or {},
        "metric_table":       result.get("metric_table", {}) or {},
        "camera_view":        result.get("camera_view", {}) or {},
        "slow_mo":            result.get("slow_mo", {}) or {},
        "phase_chart_path":   chart_path,
        "video_path":         video_storage_path,
        "pose_path":          pose_storage_path,
    }

    # Tolerate older deployments where the swings table doesn't yet have
    # the `video_path` or `pose_path` columns — drop the offending column
    # and retry rather than failing the whole save. Each retry only fires
    # if the corresponding column genuinely doesn't exist server-side.
    def _do_insert(r):
        return sb.table("swings").insert(r).execute()

    try:
        resp = _do_insert(row)
    except Exception as exc:
        msg = str(exc).lower()
        retried = False
        if "pose_path" in msg and "pose_path" in row:
            row.pop("pose_path", None)
            retried = True
        if "video_path" in msg and "video_path" in row:
            row.pop("video_path", None)
            retried = True
        if retried:
            resp = _do_insert(row)
        else:
            raise
    inserted = (resp.data or [{}])[0]

    # Uploading a swing counts as a qualifying activity for streaks.
    # Soft-fail: never let gamification bookkeeping bork the save itself.
    try:
        _on_qualifying_activity(player_id)
    except Exception:
        pass

    # Reshape into the dict the UI used to receive (with legacy keys
    # for backward compatibility).
    return _swing_row_to_legacy(inserted)


def _swing_row_to_legacy(row: dict) -> dict:
    """
    Convert a swings row into the legacy record shape the UI reads.
    Adds a synthetic `timestamp` + `date` + `_phase_chart_path` so old
    code keeps working.
    """
    if not row:
        return {}
    return {
        # Legacy keys
        "id":                row.get("id"),
        "timestamp":         row.get("timestamp_str"),
        "date":              row.get("date_str"),
        "filename":          row.get("filename"),
        "score":             row.get("score"),
        "score_band_color":  row.get("score_band_color"),
        "score_band_label":  row.get("score_band_label"),
        "reference_name":    row.get("reference_name"),
        "player_handedness": row.get("player_handedness"),
        "swing_duration_ms": row.get("swing_duration_ms"),
        "narratives":        row.get("narratives") or [],
        "strengths":         row.get("strengths") or [],
        "other_observations":row.get("other_observations") or [],
        "drill_plan":        row.get("drill_plan") or {},
        "metric_table":      row.get("metric_table") or {},
        "camera_view":       row.get("camera_view") or {},
        "slow_mo":           row.get("slow_mo") or {},
        # New-world keys
        "player_id":         row.get("player_id"),
        "user_id":           row.get("user_id"),
        "created_at":        row.get("created_at"),
        # Phase chart pointer — UI just needs *something* truthy
        "_phase_chart_path": row.get("phase_chart_path"),
        # Raw swing video pointer (may be None for older swings)
        "_video_path":       row.get("video_path"),
        # Per-frame pose JSON pointer (may be None for Free users or older swings)
        "_pose_path":        row.get("pose_path"),
        "_record_path":      None,  # no longer a local file
    }


def _is_jwt_expired_error(exc: Exception) -> bool:
    """Heuristic — supabase-py surfaces JWT-expired as a PostgrestError
    whose stringified form contains either 'JWT expired' or 'PGRST303'."""
    msg = str(exc).lower()
    return ("jwt expired" in msg) or ("pgrst303" in msg)


def _flag_session_expired() -> None:
    """Set a single, deduplicated session-state flag so the UI can show
    a clean 'please log back in' banner once per rerun instead of dumping
    raw Postgrest errors on every call site."""
    try:
        st.session_state["_session_expired"] = True
    except Exception:
        pass


def load_swing_history(player_slug: str) -> list:
    """
    Return all swings for the given player_id (passed as `player_slug`
    for back-compat), oldest first, with a 1-based swing_number injected.

    JWT-expired errors are treated as a soft logged-out state: we silently
    return an empty list and flag st.session_state["_session_expired"] so
    the page header can render a single, clean 'please log back in' banner.
    """
    sb = get_client()
    try:
        resp = (
            sb.table("swings")
              .select("*")
              .eq("player_id", player_slug)
              .order("created_at", desc=False)
              .execute()
        )
    except Exception as exc:
        if _is_jwt_expired_error(exc):
            _flag_session_expired()
            return []
        # Any other error is still worth surfacing once (real bug, not auth).
        st.error(f"Failed to load swing history: {exc}")
        return []

    rows = resp.data or []
    records = [_swing_row_to_legacy(r) for r in rows]
    for i, rec in enumerate(records, 1):
        rec["swing_number"] = i
    return records


def delete_swing_record(swing_id: str) -> bool:
    """Delete a single swing by id (RLS still enforces ownership)."""
    sb = get_client()
    try:
        sb.table("swings").delete().eq("id", swing_id).execute()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------
#  Training log (development tracker)
# --------------------------------------------------------------------
def load_training_log(player_id: str) -> dict:
    """Return { drills: {...}, session_notes: [...] }. Empty defaults
    if no row exists yet."""
    sb = get_client()
    try:
        resp = (
            sb.table("training_logs")
              .select("*")
              .eq("player_id", player_id)
              .limit(1)
              .execute()
        )
    except Exception as exc:
        if _is_jwt_expired_error(exc):
            _flag_session_expired()
        return {"drills": {}, "session_notes": []}
    rows = resp.data or []
    if not rows:
        return {"drills": {}, "session_notes": []}
    row = rows[0]
    return {
        "drills":        row.get("drill_state") or {},
        "session_notes": row.get("session_notes") or [],
    }


def save_training_log(player_id: str, data: dict) -> None:
    """Upsert the training log for this player."""
    sb = get_client()
    user_resp = sb.auth.get_user()
    user_obj = getattr(user_resp, "user", None)
    if not user_obj:
        return

    payload = {
        "player_id":     player_id,
        "user_id":       user_obj.id,
        "drill_state":   data.get("drills") or {},
        "session_notes": data.get("session_notes") or [],
        "updated_at":    datetime.utcnow().isoformat(),
    }
    try:
        sb.table("training_logs").upsert(payload, on_conflict="player_id").execute()
    except Exception as exc:
        if _is_jwt_expired_error(exc):
            _flag_session_expired()
            return
        st.error(f"Failed to save training log: {exc}")


# --------------------------------------------------------------------
#  Profile picture (optional — kept simple, writes to Supabase Storage)
# --------------------------------------------------------------------
def save_profile_pic(player_id: str, file_bytes: bytes,
                     content_type: str = "image/png") -> Optional[str]:
    """Upload a profile pic and return the storage path stored on the
    players row."""
    sb = get_client()
    user_resp = sb.auth.get_user()
    user_obj = getattr(user_resp, "user", None)
    if not user_obj:
        return None
    object_path = f"{user_obj.id}/{player_id}/profile.png"
    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=object_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception:
        return None
    _update_profile_remote(player_id, profile_pic_path=object_path)
    return object_path


def get_profile_pic_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    """Return a temporary signed URL for a profile pic / phase chart."""
    if not storage_path:
        return None
    sb = get_client()
    try:
        resp = sb.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, expires_in)
        return resp.get("signedURL") or resp.get("signed_url")
    except Exception:
        return None


def get_swing_video_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    """Return a temporary signed URL for a raw swing video stored in
    Supabase Storage. Returns None if storage_path is empty or the URL
    can't be created."""
    if not storage_path:
        return None
    sb = get_client()
    try:
        resp = sb.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, expires_in)
        return resp.get("signedURL") or resp.get("signed_url")
    except Exception:
        return None


# --------------------------------------------------------------------
#  Per-swing meta (notes + drill completion). Piggybacks on the
#  existing training_logs row so we don't need a schema migration.
# --------------------------------------------------------------------
def _ensure_swing_meta_bucket(drills: dict) -> dict:
    """Return drills with a `_swing_meta` sub-dict guaranteed to exist."""
    if not isinstance(drills, dict):
        drills = {}
    if not isinstance(drills.get("_swing_meta"), dict):
        drills["_swing_meta"] = {}
    return drills


def load_swing_meta(player_id: str, swing_id: str) -> dict:
    """
    Return { notes: str, drills_completed: {drill_name: bool, ...} } for
    a single swing. Empty defaults if no meta has been saved yet.
    """
    if not player_id or not swing_id:
        return {"notes": "", "drills_completed": {}}
    log = load_training_log(player_id)
    drills = log.get("drills") or {}
    meta_bucket = drills.get("_swing_meta") or {}
    entry = meta_bucket.get(str(swing_id)) or {}
    return {
        "notes":            entry.get("notes", "") or "",
        "drills_completed": entry.get("drills_completed", {}) or {},
    }


def save_swing_meta(player_id: str, swing_id: str,
                    notes: Optional[str] = None,
                    drills_completed: Optional[dict] = None) -> dict:
    """
    Upsert per-swing meta inside training_logs.drill_state._swing_meta.
    Returns the merged meta entry that was written. Pass None for a
    field to leave it unchanged.
    """
    if not player_id or not swing_id:
        return {"notes": "", "drills_completed": {}}

    log = load_training_log(player_id)
    drills = _ensure_swing_meta_bucket(log.get("drills") or {})
    meta_bucket = drills["_swing_meta"]

    existing = meta_bucket.get(str(swing_id)) or {}
    prev_completed = existing.get("drills_completed", {}) or {}
    next_completed = prev_completed if drills_completed is None else (drills_completed or {})

    new_entry = {
        "notes":            existing.get("notes", "") if notes is None else (notes or ""),
        "drills_completed": next_completed,
        "updated_at":       datetime.utcnow().isoformat(),
    }
    meta_bucket[str(swing_id)] = new_entry
    drills["_swing_meta"] = meta_bucket

    save_training_log(player_id, {
        "drills":        drills,
        "session_notes": log.get("session_notes") or [],
    })

    # Streak hook: marking a NEW drill complete (i.e. flipping a False/missing
    # key to True) counts as a qualifying activity. Pure flipping a drill
    # OFF does not. Soft-fail so streak bookkeeping can't break the save.
    try:
        newly_completed = any(
            bool(v) and not bool(prev_completed.get(k))
            for k, v in (next_completed or {}).items()
        )
        if newly_completed:
            _on_qualifying_activity(player_id)
    except Exception:
        pass

    return new_entry


# --------------------------------------------------------------------
#  Gamification persistence (Milestones / XP / Streaks / Rewards)
#  Piggybacks on training_logs.drill_state._gamification so we don't
#  need a schema migration. Totals (XP, level, swings, drills, scores)
#  are NEVER stored here — they are derived from raw history on load.
# --------------------------------------------------------------------
def load_all_swing_meta(player_id: str) -> dict:
    """
    Return the full { swing_id: {notes, drills_completed, ...} } bucket.
    Used by the gamification engine to count total drills completed
    across every swing the player has ever logged.
    """
    if not player_id:
        return {}
    log = load_training_log(player_id)
    drills = log.get("drills") or {}
    meta = drills.get("_swing_meta") or {}
    return meta if isinstance(meta, dict) else {}


def load_player_progress(player_id: str) -> dict:
    """
    Return the persisted gamification dict for the player. Shape:
        {
            "current_streak_days":   int,
            "longest_streak_days":   int,
            "last_qualifying_date":  "YYYY-MM-DD" or None,
            "achievements_unlocked": { id: "YYYY-MM-DD", ... },
            "rewards_unlocked":      { id: "YYYY-MM-DD", ... },
            "rewards_claimed":       { id: "YYYY-MM-DD", ... },
        }
    """
    from gamification import empty_persisted, _coerce_persisted
    if not player_id:
        return empty_persisted()
    log = load_training_log(player_id)
    drills = log.get("drills") or {}
    persisted = drills.get("_gamification") if isinstance(drills, dict) else None
    return _coerce_persisted(persisted)


def save_player_progress(player_id: str, persisted: dict) -> dict:
    """
    Persist the gamification dict under training_logs.drill_state._gamification
    without disturbing real drill keys or _swing_meta. Returns the dict
    that was written.
    """
    from gamification import _coerce_persisted
    if not player_id:
        return _coerce_persisted(persisted)

    coerced = _coerce_persisted(persisted)
    log = load_training_log(player_id)
    drills = log.get("drills") or {}
    if not isinstance(drills, dict):
        drills = {}
    drills["_gamification"] = coerced

    save_training_log(player_id, {
        "drills":        drills,
        "session_notes": log.get("session_notes") or [],
    })
    return coerced


def _on_qualifying_activity(player_id: str) -> dict:
    """
    Bump the streak for `player_id` for today's calendar date.
    Idempotent: calling this twice on the same date is a no-op.
    Returns the updated persisted dict (or an empty one on failure).
    """
    from gamification import update_streak
    if not player_id:
        return {}
    persisted = load_player_progress(player_id)
    updated = update_streak(persisted)  # uses today's date
    # Only write if the streak actually changed — avoids redundant writes.
    if updated != persisted:
        save_player_progress(player_id, updated)
    return updated


# --------------------------------------------------------------------
#  Backwards-compat re-exports — some call sites import these directly
# --------------------------------------------------------------------
__all__ = [
    "slugify",
    "load_player_index",
    "find_player_by_email",
    "load_profile",
    "create_account",
    "authenticate",
    "update_profile",
    "save_swing_record",
    "load_swing_history",
    "delete_swing_record",
    "load_training_log",
    "save_training_log",
    "save_profile_pic",
    "get_profile_pic_signed_url",
    "get_swing_video_signed_url",
    "load_swing_meta",
    "save_swing_meta",
    "load_all_swing_meta",
    "load_player_progress",
    "save_player_progress",
    "ALLOWED_PROFILE_UPDATES",
]
