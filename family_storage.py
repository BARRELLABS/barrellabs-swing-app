"""Household / Family Pro data layer.

Safe by design: every function falls back to None / empty / False
when the schema isn't yet migrated or the Supabase client isn't
configured. That lets the dashboard ship before the user has
applied the migration to their live database.

Public API:
  load_family_for_user(user_id)   → family dict or None
  list_members(family_id)         → list of family_members rows
  is_family_pro_member(user_id)   → bool
  add_member(family_id, email, ...) → {ok, error?, invite_token?}
  remove_member(family_member_id) → {ok, error?}
  claim_invite(token, user_id)    → {ok, family_id?, error?}
  get_member_summary(member, swings=None) → dashboard-ready dict

Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
"""

from __future__ import annotations

import datetime as _dt
import hashlib as _hashlib
import secrets as _secrets
from typing import Any, Optional

try:
    from supabase_client import get_client as _get_client  # type: ignore
except Exception:
    _get_client = None  # type: ignore


# ── Constants ──────────────────────────────────────────────────────
MAX_SEATS = 4
STALE_DAYS = 10
INVITE_EXPIRY_DAYS = 30

# Trend bands for verdict-line generation
_BIG_JUMP   = 5   # delta ≥ this → "Best swing"
_MED_JUMP   = 3   # ≥ this → "Trending up"
_BIG_DROP   = -3  # ≤ this → "Slipping"


# ── Supabase wrapper ───────────────────────────────────────────────
def _supabase_query_safe(table: str, query_fn) -> tuple[str, Any]:
    """Run a Supabase query, mapping schema-missing / connection errors
    to ('schema_missing', None) so callers can fall back gracefully."""
    if _get_client is None:
        return ("no_client", None)
    try:
        client = _get_client()
        result = query_fn(client.table(table))
        return ("ok", result)
    except Exception as exc:
        msg = str(exc).lower()
        if any(s in msg for s in ("does not exist", "relation", "schema",
                                   "not authenticated", "no client")):
            return ("schema_missing", None)
        return ("error", str(exc))


# ── Public API ─────────────────────────────────────────────────────
def load_family_for_user(user_id: str) -> Optional[dict]:
    """Return the family dict the user belongs to (as owner or
    active member). None if no family or schema not yet migrated."""
    if not user_id:
        return None
    status, result = _supabase_query_safe(
        "families",
        lambda t: t.select("*").eq("owner_user_id", user_id).limit(1).execute(),
    )
    if status != "ok":
        return None
    rows = (result.data if hasattr(result, "data") else result.get("data", []))
    if rows:
        return rows[0]
    # Fall through: user might be a member, not an owner
    status2, result2 = _supabase_query_safe(
        "family_members",
        lambda t: t.select("family_id").eq("player_user_id", user_id)
                   .eq("invite_status", "active").limit(1).execute(),
    )
    if status2 != "ok":
        return None
    mrows = (result2.data if hasattr(result2, "data") else result2.get("data", []))
    if not mrows:
        return None
    fid = mrows[0].get("family_id")
    if not fid:
        return None
    status3, result3 = _supabase_query_safe(
        "families",
        lambda t: t.select("*").eq("id", fid).limit(1).execute(),
    )
    if status3 != "ok":
        return None
    frows = (result3.data if hasattr(result3, "data") else result3.get("data", []))
    return frows[0] if frows else None


def list_members(family_id: str, include_removed: bool = False) -> list[dict]:
    """Return family_members rows for a family. Active+pending only by
    default; pass include_removed=True to see soft-deleted rows too."""
    if not family_id:
        return []
    statuses = (["active", "pending", "removed"]
                if include_removed else ["active", "pending"])
    status, result = _supabase_query_safe(
        "family_members",
        lambda t: t.select("*").eq("family_id", family_id)
                   .in_("invite_status", statuses)
                   .order("added_at", desc=False).execute(),
    )
    if status != "ok":
        return []
    rows = (result.data if hasattr(result, "data") else result.get("data", []))
    return rows or []


def is_family_pro_member(user_id: str) -> bool:
    """True iff the user is an active member of a family with an
    active Family Pro subscription. Backed by v_my_effective_plan."""
    if not user_id:
        return False
    status, result = _supabase_query_safe(
        "v_my_effective_plan",
        lambda t: t.select("plan_id,source").limit(1).execute(),
    )
    if status != "ok":
        return False
    rows = (result.data if hasattr(result, "data") else result.get("data", []))
    if not rows:
        return False
    row = rows[0]
    return (row.get("plan_id") == "family_pro"
            and row.get("source") == "family")


def add_member(
    family_id: str,
    email: str,
    role: str = "child",
    is_minor: bool = False,
    display_name: Optional[str] = None,
) -> dict:
    """Invite a new member by email. Generates a one-time token,
    stores its hash via the add_family_member RPC.

    Returns {ok: bool, invite_token?: str, error?: str}.
    The invite_token is returned so the caller can include it in an
    email (or display it inline pre-email-send-backend).
    """
    if not email or "@" not in email:
        return {"ok": False, "error": "Enter a valid email."}

    # Client-side seat-cap pre-check (the RPC is authoritative)
    active = [m for m in list_members(family_id)
              if m.get("invite_status") == "active"]
    if len(active) >= MAX_SEATS:
        return {"ok": False, "error": "Household is full — at the 4-seat cap."}

    token = _secrets.token_urlsafe(32)
    token_hash = _hashlib.sha256(token.encode()).hexdigest()

    if _get_client is None:
        # Pre-migration mode — return the invite token without inserting
        return {"ok": True, "invite_token": token, "mode": "stub"}

    try:
        client = _get_client()
        client.rpc("add_family_member", {
            "p_family_id":   family_id,
            "p_email":       email.lower().strip(),
            "p_role":        role,
            "p_is_minor":    is_minor,
            "p_display_name": display_name,
            "p_token_hash":  token_hash,
        }).execute()
        return {"ok": True, "invite_token": token}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def remove_member(family_member_id: str) -> dict:
    """Soft-delete: set invite_status='removed', removed_at=now()."""
    if not family_member_id:
        return {"ok": False, "error": "Missing family_member_id."}
    if _get_client is None:
        return {"ok": True, "mode": "stub"}
    try:
        client = _get_client()
        client.table("family_members").update({
            "invite_status": "removed",
            "removed_at":    _dt.datetime.utcnow().isoformat() + "Z",
        }).eq("id", family_member_id).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def claim_invite(token: str, user_id: str) -> dict:
    """Match token → flip status to active via the claim_family_invite RPC.

    The RPC is SECURITY DEFINER: it enforces the 30-day expiry AND the
    4-seat cap server-side, and claims the pending row atomically under a
    FOR UPDATE lock. We deliberately do NOT do the lookup/expiry/update
    as separate client calls — that was race-able (two invitees, or an
    invite + a seat fill, could interleave)."""
    if not token or not user_id:
        return {"ok": False, "error": "Missing token or user."}
    token_hash = _hashlib.sha256(token.encode()).hexdigest()

    if _get_client is None:
        return {"ok": False, "error": "Database not configured."}
    try:
        client = _get_client()
        res = client.rpc("claim_family_invite",
                         {"p_token_hash": token_hash}).execute()
        fam_id = res.data if hasattr(res, "data") else res.get("data")
        if not fam_id:
            return {"ok": False, "error": "Invite token invalid or expired."}
        # supabase-py returns the scalar directly for a uuid-returning RPC,
        # but normalize in case it's wrapped in a list.
        if isinstance(fam_id, (list, tuple)):
            fam_id = fam_id[0] if fam_id else None
        return {"ok": True, "family_id": fam_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_member_summary(member: dict, swings: list[dict] | None = None) -> dict:
    """Combine a family_members row with their recent swings into a
    card-ready dict. If swings is None and there's a real DB, fetches
    the member's last 30 swings."""
    out = dict(member)
    if swings is None and member.get("player_user_id") and _get_client is not None:
        status, result = _supabase_query_safe(
            "swings",
            lambda t: t.select("created_at,edge_score")
                       .eq("player_id", member["player_user_id"])
                       .order("created_at", desc=False).limit(30).execute(),
        )
        if status == "ok":
            rows = (result.data if hasattr(result, "data") else result.get("data", []))
            swings = rows or []
        else:
            swings = []
    elif swings is None:
        swings = []
    out.update(_compute_member_summary(swings))
    return out


def _compute_member_summary(
    swings: list[dict], *, today: Optional[str] = None,
) -> dict:
    """Pure function: derive verdict/score/trend/sparkline from
    a member's swing list. Sorted ascending by created_at; latest
    is last."""
    today_dt = (_dt.date.fromisoformat(today) if today
                else _dt.date.today())

    if not swings:
        return {
            "latest_score":     None,
            "latest_date":      None,
            "delta":            None,
            "days_since":       None,
            "is_stale":         True,
            "verdict_line":     "No swings yet.",
            "trend":            "unknown",
            "sparkline_points": [],
        }

    sorted_s = sorted(swings, key=lambda s: s.get("created_at", ""))
    scores = [float(s.get("edge_score") or 0) for s in sorted_s]
    latest = sorted_s[-1]
    latest_score = round(scores[-1])
    latest_date_iso = latest.get("created_at", "") or ""
    delta = round(scores[-1] - scores[-2]) if len(scores) >= 2 else 0

    # Staleness
    try:
        latest_date = _dt.date.fromisoformat(latest_date_iso[:10])
        days_since = (today_dt - latest_date).days
    except Exception:
        days_since = 999
    is_stale = days_since > STALE_DAYS

    # Verdict + trend
    if is_stale:
        verdict_line = f"Hasn't filmed in {days_since} days."
        trend = "stale"
    elif delta >= _BIG_JUMP:
        verdict_line = "Best swing this week."
        trend = "up"
    elif delta >= _MED_JUMP:
        verdict_line = f"Trending up — +{delta} since last."
        trend = "up"
    elif delta <= _BIG_DROP:
        prev = round(scores[-2]) if len(scores) >= 2 else latest_score
        verdict_line = f"Slipping — was {prev} last week."
        trend = "down"
    else:
        verdict_line = "Holding steady. Building up."
        trend = "flat"

    # Sparkline: last 10 scores
    last10 = [round(s) for s in scores[-10:]]

    return {
        "latest_score":     latest_score,
        "latest_date":      latest_date_iso,
        "delta":            delta,
        "days_since":       days_since,
        "is_stale":         is_stale,
        "verdict_line":     verdict_line,
        "trend":            trend,
        "sparkline_points": last10,
    }
