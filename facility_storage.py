"""Facility / Academy data layer — safe by design.

Mirrors family_storage.py: every function falls back to None/empty/False
when the backend isn't configured or a query errors, so the dashboard
renders its empty/safe states instead of crashing.

A "facility" is an org a player LINKS to via a join code. The player keeps
owning their own account/data; the facility gets a read roster view and
SPONSORS full Pro for every active member (see
entitlements.resolve_effective_plan).

Public API (stable — callers depend on these shapes):
  load_facility_for_owner(user_id)    → facility dict or None
  list_members(facility_id)           → list of member dicts (active)
  create_facility(name, tier, ...)    → {ok, facility?, error?}
  join_by_code(code, player_id)       → {ok, error?}
  leave(member_id)                    → {ok, error?}
  roster_summary(members, today=None) → dashboard-ready dict (PURE)

Spec: docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md
Plan: docs/superpowers/plans/2026-06-04-facility-coach-mode.md
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

try:
    from supabase_client import get_client as _get_client  # type: ignore
except Exception:
    _get_client = None  # type: ignore


# A member is "needs attention" / stale if no swing in this many days.
STALE_DAYS = 10


# ── Pure summary logic (unit-tested without a DB) ──────────────────
def roster_summary(members: list[dict], *, today: Optional[str] = None) -> dict:
    """Derive the coach's roster headline numbers from member dicts.

    Each member may carry a `swings` list of {created_at, edge_score}. Pure:
    takes data in, returns the summary — no DB, fully testable.
    """
    today_dt = _dt.date.fromisoformat(today) if today else _dt.date.today()
    total = len(members)
    active_this_week = 0
    needs_attention = 0
    for m in members:
        swings = m.get("swings") or []
        if not swings:
            needs_attention += 1
            continue
        last_iso = max((s.get("created_at", "") or "") for s in swings)
        try:
            days = (today_dt - _dt.date.fromisoformat(last_iso[:10])).days
        except Exception:
            days = 999
        if days <= 7:
            active_this_week += 1
        if days > STALE_DAYS:
            needs_attention += 1
    return {
        "total": total,
        "active_this_week": active_this_week,
        "needs_attention": needs_attention,
    }


# ── Supabase wrappers (safe) ───────────────────────────────────────
def _rows(result) -> list[dict]:
    if result is None:
        return []
    data = result.data if hasattr(result, "data") else result.get("data", [])
    return data or []


def load_facility_for_owner(user_id: str) -> Optional[dict]:
    """The facility this user owns (coach), or None."""
    if not user_id or _get_client is None:
        return None
    try:
        res = (_get_client().table("facilities")
               .select("*").eq("owner_user_id", user_id).limit(1).execute())
        rows = _rows(res)
        return rows[0] if rows else None
    except Exception:
        return None


def list_members(facility_id: str) -> list[dict]:
    """Active members of a facility (left_at IS NULL). Each dict carries the
    player profile fields the roster card needs. Empty list on any error."""
    if not facility_id or _get_client is None:
        return []
    try:
        res = (_get_client().table("facility_members")
               .select("id, player_id, joined_at, players(name, position, handedness)")
               .eq("facility_id", facility_id).is_("left_at", "null").execute())
        out: list[dict] = []
        for r in _rows(res):
            p = r.get("players") or {}
            out.append({
                "member_id": r.get("id"),
                "player_id": r.get("player_id"),
                "display_name": p.get("name") or "Player",
                "position": p.get("position"),
                "handedness": p.get("handedness"),
                "joined_at": r.get("joined_at"),
            })
        return out
    except Exception:
        return []


def create_facility(name: str, tier: str = "academy", ceiling: int = 100,
                    billing_mode: str = "license") -> dict:
    """Coach creates their facility. Returns {ok, facility?, error?}."""
    if _get_client is None:
        return {"ok": False, "error": "backend not configured"}
    try:
        res = _get_client().rpc("create_facility", {
            "p_name": name, "p_tier": tier, "p_ceiling": ceiling,
            "p_billing_mode": billing_mode,
        }).execute()
        rows = _rows(res)
        return {"ok": True, "facility": rows[0] if rows else res.data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def join_by_code(code: str, player_id: str) -> dict:
    """Link one of the caller's players to a facility. {ok, error?}."""
    if _get_client is None:
        return {"ok": False, "error": "backend not configured"}
    if not (code or "").strip():
        return {"ok": False, "error": "Enter a join code."}
    try:
        _get_client().rpc("join_facility_by_code", {
            "p_code": code.strip().upper(), "p_player_id": player_id,
        }).execute()
        return {"ok": True}
    except Exception as exc:
        msg = str(exc)
        if "invalid code" in msg:
            return {"ok": False, "error": "That join code isn't valid."}
        if "roster is full" in msg:
            return {"ok": False, "error": "This facility's roster is full."}
        return {"ok": False, "error": msg}


def leave(member_id: str) -> dict:
    """Soft-leave a facility (sponsorship ends; data kept). {ok, error?}."""
    if _get_client is None:
        return {"ok": False, "error": "backend not configured"}
    try:
        _get_client().rpc("leave_facility", {"p_member_id": member_id}).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def is_player_sponsored(player_id: str) -> bool:
    """True iff the player has an active membership in an active facility.
    Drives entitlements.resolve_effective_plan(sponsored=...). False on error."""
    if not player_id or _get_client is None:
        return False
    try:
        res = (_get_client().table("facility_members")
               .select("id, facilities(status)")
               .eq("player_id", player_id).is_("left_at", "null").execute())
        for r in _rows(res):
            fac = r.get("facilities") or {}
            if fac.get("status") == "active":
                return True
        return False
    except Exception:
        return False


def get_facility_for_player(player_id: str) -> Optional[dict]:
    """Return the ACTIVE sponsoring facility (id, name, logo_url) for a player,
    or None. Used to co-brand the player's report with their academy's logo.
    None on error (safe — the report just stays BarrelLabs-only)."""
    if not player_id or _get_client is None:
        return None
    try:
        res = (_get_client().table("facility_members")
               .select("facilities(id,name,logo_url,status)")
               .eq("player_id", player_id).is_("left_at", "null").execute())
        for r in _rows(res):
            fac = r.get("facilities") or {}
            if fac.get("status") == "active":
                return fac
        return None
    except Exception:
        return None


def set_facility_logo(facility_id: str, logo_url: str) -> dict:
    """Owner-only (RLS) update of a facility's logo. logo_url is a small PNG
    data-URI so it renders in reports with no signed-URL expiry."""
    if not facility_id or _get_client is None:
        return {"ok": False, "error": "backend not configured"}
    try:
        _get_client().table("facilities").update(
            {"logo_url": logo_url}).eq("id", facility_id).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
