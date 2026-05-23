"""Household / Family Pro data layer.

Built on the EXISTING seat model that already lives in the database:

  subscriptions       = the household container (owner_user_id, plan_id)
  subscription_seats  = the members (subscription_id, user_id, invite_*,
                        accepted_at, role, display_name, is_minor)
  plans.seats         = the per-plan seat cap (free=1, solo=1, family=4,
                        coach=20)
  v_my_plan           = already resolves a member's plan THROUGH their
                        seat, so Family-Pro entitlement propagation needs
                        no extra code — a seat on a family_pro sub already
                        resolves the member to family_pro.

This module presents a "family"-shaped API over those tables so the
dashboard / settings don't need to know the underlying schema. A
"family" IS a subscription whose plan has more than one seat.

Safe by design: every function falls back to None / empty / False when
the Supabase client isn't configured or a query errors, so the dashboard
renders its empty/upgrade states instead of crashing.

Public API (stable — callers depend on these shapes):
  load_family_for_user(user_id)   → family dict or None
  list_members(family_id)         → list of member dicts
  is_family_pro_member(user_id)   → bool
  add_member(family_id, email, ...) → {ok, error?, invite_token?}
  remove_member(seat_id)          → {ok, error?}
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
STALE_DAYS = 10
INVITE_EXPIRY_DAYS = 30

# Subscription statuses that count as "the plan is live".
_LIVE_STATUSES = ("active", "trialing", "past_due", "comp")

# Trend bands for verdict-line generation
_BIG_JUMP   = 5   # delta ≥ this → "Best swing"
_MED_JUMP   = 3   # ≥ this → "Trending up"
_BIG_DROP   = -3  # ≤ this → "Slipping"


# ── Supabase wrapper ───────────────────────────────────────────────
def _supabase_query_safe(table: str, query_fn) -> tuple[str, Any]:
    """Run a Supabase query, mapping connection / schema errors to a
    non-'ok' status so callers can fall back gracefully."""
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


def _rows(result) -> list[dict]:
    """Normalize a supabase-py response into a list of row dicts."""
    if result is None:
        return []
    data = result.data if hasattr(result, "data") else result.get("data", [])
    return data or []


# ── Internal: subscription + plan lookup ───────────────────────────
def _subscription_for_user(user_id: str) -> Optional[dict]:
    """Find the live subscription the user belongs to — either as the
    owner, or via a seat they hold. Returns the joined subscription+plan
    dict (with max_seats) or None."""
    if not user_id:
        return None

    # 1. A seat the user holds (covers both owner-seat and invited member).
    status, result = _supabase_query_safe(
        "subscription_seats",
        lambda t: t.select("subscription_id")
                   .eq("user_id", user_id)
                   .is_("removed_at", "null")
                   .limit(1).execute(),
    )
    sub_id = None
    if status == "ok":
        seats = _rows(result)
        if seats:
            sub_id = seats[0].get("subscription_id")

    # 2. Fallback: the user directly owns a subscription (no seat row yet).
    if sub_id is None:
        status_o, result_o = _supabase_query_safe(
            "subscriptions",
            lambda t: t.select("id").eq("owner_user_id", user_id)
                       .in_("status", list(_LIVE_STATUSES))
                       .limit(1).execute(),
        )
        if status_o == "ok":
            owned = _rows(result_o)
            if owned:
                sub_id = owned[0].get("id")

    if not sub_id:
        return None

    # Load the subscription row.
    status_s, result_s = _supabase_query_safe(
        "subscriptions",
        lambda t: t.select("*").eq("id", sub_id).limit(1).execute(),
    )
    if status_s != "ok":
        return None
    subs = _rows(result_s)
    if not subs:
        return None
    sub = subs[0]
    if sub.get("status") not in _LIVE_STATUSES:
        return None

    # Join the plan for seat-count + display name.
    plan = {}
    status_p, result_p = _supabase_query_safe(
        "plans",
        lambda t: t.select("id,name,seats").eq("id", sub.get("plan_id"))
                   .limit(1).execute(),
    )
    if status_p == "ok":
        prows = _rows(result_p)
        if prows:
            plan = prows[0]

    sub["_plan_name"] = plan.get("name")
    sub["_max_seats"] = int(plan.get("seats") or 1)
    return sub


# ── Public API ─────────────────────────────────────────────────────
def load_family_for_user(user_id: str) -> Optional[dict]:
    """Return the household ("family") the user belongs to, or None.

    A household exists only when the user's live subscription has a
    multi-seat plan (family_pro / coach_pro). Solo / free users get
    None → the dashboard shows the upgrade prompt.

    The returned dict's `id` is the subscription_id so callers can pass
    it straight to list_members()."""
    sub = _subscription_for_user(user_id)
    if not sub:
        return None
    if int(sub.get("_max_seats") or 1) <= 1:
        return None  # solo / free — no household
    return {
        "id":             sub["id"],
        "subscription_id": sub["id"],
        "owner_user_id":  sub.get("owner_user_id"),
        "plan_id":        sub.get("plan_id"),
        "plan_name":      sub.get("_plan_name"),
        "max_seats":      int(sub.get("_max_seats") or 1),
        "status":         sub.get("status"),
    }


def list_members(family_id: str, include_removed: bool = False) -> list[dict]:
    """Return member dicts for a household (subscription_id). Active +
    pending seats by default. Each member is enriched with the player's
    profile (name / position / handedness) where they have an account."""
    if not family_id:
        return []

    def _q(t):
        q = t.select("*").eq("subscription_id", family_id)
        if not include_removed:
            q = q.is_("removed_at", "null")
        return q.order("invited_at", desc=False).execute()

    status, result = _supabase_query_safe("subscription_seats", _q)
    if status != "ok":
        return []
    seats = _rows(result)
    if not seats:
        return []

    # Batch-fetch player profiles for seats that have an account.
    user_ids = [s["user_id"] for s in seats if s.get("user_id")]
    players_by_uid: dict[str, dict] = {}
    if user_ids:
        status_p, result_p = _supabase_query_safe(
            "players",
            lambda t: t.select("user_id,name,position,handedness")
                       .in_("user_id", user_ids).execute(),
        )
        if status_p == "ok":
            for p in _rows(result_p):
                players_by_uid[p.get("user_id")] = p

    members: list[dict] = []
    for s in seats:
        prof = players_by_uid.get(s.get("user_id"), {})
        if s.get("removed_at"):
            invite_status = "removed"
        elif s.get("accepted_at"):
            invite_status = "active"
        else:
            invite_status = "pending"
        members.append({
            "id":             s.get("id"),
            "player_user_id": s.get("user_id"),
            "display_name":   s.get("display_name") or prof.get("name")
                              or s.get("invite_email") or "Player",
            "position":       prof.get("position"),
            "handedness":     prof.get("handedness"),
            "role":           s.get("role"),
            "is_minor":       bool(s.get("is_minor")),
            "invite_status":  invite_status,
            "invite_email":   s.get("invite_email"),
        })
    return members


def is_family_pro_member(user_id: str) -> bool:
    """True iff the user is in a live multi-seat household (family_pro /
    coach_pro), as owner or accepted member. Gates the Family nav item
    and the dashboard route."""
    sub = _subscription_for_user(user_id)
    if not sub:
        return False
    return int(sub.get("_max_seats") or 1) > 1


def add_member(
    family_id: str,
    email: str,
    role: str = "member",
    is_minor: bool = False,
    display_name: Optional[str] = None,
) -> dict:
    """Invite a member to the household via the invite_subscription_seat
    RPC. Generates a single-use token, stores only its sha256 hash; the
    plaintext token is returned so the caller can build the invite link
    (email-send backend is a follow-up). Seat cap is enforced server-side
    from plans.seats.

    Returns {ok, invite_token?, error?}."""
    if not email or "@" not in email:
        return {"ok": False, "error": "Enter a valid email."}

    token = _secrets.token_urlsafe(32)
    token_hash = _hashlib.sha256(token.encode()).hexdigest()

    if _get_client is None:
        # Pre-DB mode — return the token so the UI can still show the link.
        return {"ok": True, "invite_token": token, "mode": "stub"}

    try:
        client = _get_client()
        client.rpc("invite_subscription_seat", {
            "p_subscription_id": family_id,
            "p_email":           email.lower().strip(),
            "p_is_minor":        is_minor,
            "p_display_name":    display_name,
            "p_token_hash":      token_hash,
        }).execute()
        return {"ok": True, "invite_token": token}
    except Exception as exc:
        # Surface the server-side seat-cap / ownership errors verbatim-ish.
        msg = str(exc)
        if "seats are in use" in msg:
            return {"ok": False, "error": "Household is full — every seat is in use."}
        if "not the subscription owner" in msg:
            return {"ok": False, "error": "Only the household owner can invite players."}
        return {"ok": False, "error": msg}


def remove_member(seat_id: str) -> dict:
    """Soft-delete a seat (set removed_at). Owner-only via RLS
    (seats_owner_writes)."""
    if not seat_id:
        return {"ok": False, "error": "Missing seat id."}
    if _get_client is None:
        return {"ok": True, "mode": "stub"}
    try:
        client = _get_client()
        client.table("subscription_seats").update({
            "removed_at": _dt.datetime.utcnow().isoformat() + "Z",
        }).eq("id", seat_id).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def claim_invite(token: str, user_id: str) -> dict:
    """Accept a seat invite via the claim_subscription_seat RPC.

    The RPC is SECURITY DEFINER: it enforces the 30-day expiry AND the
    plan seat cap server-side, and claims the pending seat atomically
    under a FOR UPDATE lock."""
    if not token or not user_id:
        return {"ok": False, "error": "Missing token or user."}
    token_hash = _hashlib.sha256(token.encode()).hexdigest()

    if _get_client is None:
        return {"ok": False, "error": "Database not configured."}
    try:
        client = _get_client()
        res = client.rpc("claim_subscription_seat",
                         {"p_token_hash": token_hash}).execute()
        fam_id = res.data if hasattr(res, "data") else res.get("data")
        if not fam_id:
            return {"ok": False, "error": "Invite token invalid or expired."}
        if isinstance(fam_id, (list, tuple)):
            fam_id = fam_id[0] if fam_id else None
        return {"ok": True, "family_id": fam_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_member_summary(member: dict, swings: list[dict] | None = None) -> dict:
    """Combine a member dict with their recent swings into a card-ready
    dict. If swings is None and there's a real DB, fetches the member's
    last 30 swings (by auth user_id, since swings.user_id → auth.users)."""
    out = dict(member)
    uid = member.get("player_user_id")
    if swings is None and uid and _get_client is not None:
        status, result = _supabase_query_safe(
            "swings",
            lambda t: t.select("created_at,score")
                       .eq("user_id", uid)
                       .order("created_at", desc=False).limit(30).execute(),
        )
        if status == "ok":
            # Normalize the swings table's `score` column to the
            # `edge_score` key _compute_member_summary expects.
            swings = [{"created_at": r.get("created_at"),
                       "edge_score": r.get("score")} for r in _rows(result)]
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
