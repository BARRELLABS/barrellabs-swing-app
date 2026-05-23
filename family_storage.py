"""Household / Family Pro data layer.

Presents a "family"-shaped API over the household's player profiles so
the dashboard and settings don't need to know the underlying schema. A
"family" IS a household whose plan has more than one seat (>1 profile).

Safe by design: every function falls back to None / empty / False when
the backend isn't configured or a query errors, so the dashboard renders
its empty/upgrade states instead of crashing.

Public API (stable — callers depend on these shapes):
  load_family_for_user(user_id)     → family dict or None
  list_members(family_id)           → list of member dicts
  is_family_pro_member(user_id)     → bool
  add_member(family_id, ...)        → {ok, error?}
  remove_member(member_id)          → {ok, error?}
  get_member_summary(member, swings=None) → dashboard-ready dict

Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

try:
    from supabase_client import get_client as _get_client  # type: ignore
except Exception:
    _get_client = None  # type: ignore


# ── Constants ──────────────────────────────────────────────────────
STALE_DAYS = 10

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


# ── Public API ─────────────────────────────────────────────────────
def load_family_for_user(user_id: str) -> Optional[dict]:
    """Return the household ("family") the user belongs to, or None.

    A household exists only when the user's plan has more than one seat
    (multi-profile). Solo / free users get None → the dashboard shows
    the upgrade prompt.

    The returned dict's `id` is the user_id so callers can pass it
    straight to list_members()."""
    import auth
    if not user_id:
        return None
    try:
        seats = auth.current_household_seats()
    except Exception:
        seats = 1
    if seats <= 1:
        return None
    return {
        "id":              user_id,
        "subscription_id": user_id,
        "owner_user_id":   user_id,
        "max_seats":       seats,
        "plan_name":       "Household",
    }


def list_members(family_id: str, include_removed: bool = False) -> list[dict]:
    """Return member dicts for a household. `family_id` is the household
    owner's user_id. Each member maps to a player profile."""
    import auth
    profs = auth.list_household_players(family_id)
    members: list[dict] = []
    for i, p in enumerate(profs):
        members.append({
            "id":             p.get("id"),
            "player_user_id": p.get("id"),
            "display_name":   p.get("name") or "Player",
            "position":       p.get("position"),
            "handedness":     p.get("handedness"),
            "role":           "owner" if i == 0 else "member",
            "invite_status":  "active",
        })
    return members


def is_family_pro_member(user_id: str) -> bool:
    """True iff the user is in a live multi-seat household (>1 profile seat)."""
    import auth
    try:
        return bool(user_id) and auth.current_household_seats() > 1
    except Exception:
        return False


def add_member(
    family_id: str,
    name: str = "",
    role: str = "member",
    is_minor: bool = True,
    display_name: Optional[str] = None,
) -> dict:
    """Create a new player profile in the household."""
    import auth
    return auth.create_household_player(
        name or display_name or "", position=None, is_minor=is_minor
    )


def remove_member(member_id: str) -> dict:
    """Soft-remove a player profile from the household."""
    import auth
    return auth.remove_household_player(member_id)


def get_member_summary(member: dict, swings: list[dict] | None = None) -> dict:
    """Combine a member dict with their recent swings into a card-ready
    dict. If swings is None and there's a real DB, fetches the member's
    last 30 swings by player_id."""
    out = dict(member)
    pid = member.get("id")
    if swings is None and pid and _get_client is not None:
        status, result = _supabase_query_safe(
            "swings",
            lambda t: t.select("created_at,score").eq("player_id", pid)
                       .order("created_at", desc=False).limit(30).execute(),
        )
        if status == "ok":
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
