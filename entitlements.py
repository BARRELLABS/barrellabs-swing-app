"""
BarrelLabs SwingAI — Entitlements

Single source of truth for every "can this user do X?" question. Every
feature gate in the app should call into this module so we never end
up with inconsistent paywalls across pages.

Design rules:
  • Plan-level capabilities live in PLAN_CAPS (a flat dict-of-dicts).
  • Per-user state (which plan, usage counters) comes from
    subscription_storage.load_my_plan() — this module never talks to
    Supabase directly.
  • Every public function returns either a bool or an EntitlementResult
    so call sites can render meaningful upgrade prompts.

Usage:
    from entitlements import can_analyze_swing, can_save_drill_plan
    ok, reason, upgrade_to = can_analyze_swing()
    if not ok:
        show_paywall(reason, upgrade_to)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


FREE_PLAN_ID    = "free"
SOLO_PLAN_ID    = "solo_pro"
FAMILY_PLAN_ID  = "family_pro"
COACH_PLAN_ID   = "coach_pro"

PRO_PLANS = {SOLO_PLAN_ID, FAMILY_PLAN_ID, COACH_PLAN_ID}

# How many lifetime swings a Free user can run before hitting the wall.
FREE_SWING_LIMIT = 3


# --------------------------------------------------------------------
#  PLAN CAPABILITIES — the canonical capability table
# --------------------------------------------------------------------
# Every gated feature has a key here. Adding a new gate = adding a new
# key here + the corresponding can_X() function below.
#
# Keep this dict POD (plain old data) — no callables. The gating logic
# lives in can_X() so it's testable in isolation.
PLAN_CAPS = {
    FREE_PLAN_ID: {
        "swing_limit_lifetime":   FREE_SWING_LIMIT,   # int or None for unlimited
        "drill_plan":             False,
        "video_storage":          False,
        "development_tracker":    False,
        "rewards":                False,
        "pdf_export":             False,
        "compare_swings":         False,
        "mlb_comp_library":       "basic",            # 'basic' | 'full'
        "support_priority":       "standard",
    },
    SOLO_PLAN_ID: {
        "swing_limit_lifetime":   None,
        "drill_plan":             True,
        "video_storage":          True,
        "development_tracker":    True,
        "rewards":                True,
        "pdf_export":             True,
        "compare_swings":         True,
        "mlb_comp_library":       "full",
        "support_priority":       "standard",
    },
}
# Family + Coach share Solo's caps (just different seat counts on the sub).
PLAN_CAPS[FAMILY_PLAN_ID] = dict(PLAN_CAPS[SOLO_PLAN_ID])
PLAN_CAPS[COACH_PLAN_ID]  = dict(PLAN_CAPS[SOLO_PLAN_ID])


# --------------------------------------------------------------------
#  Result type
# --------------------------------------------------------------------
@dataclass
class EntitlementResult:
    """
    Returned from every can_X() check. The UI can use this directly
    to render either the feature or a paywall.

    allowed:        boolean — whether the user can use the feature
    reason:         human-readable reason if blocked (None if allowed)
    upgrade_to:     suggested plan id to upgrade to (None if no upgrade
                    helps, e.g. the user is already on the highest plan)
    remaining:      for limit-based gates, how many uses they have left
    """
    allowed:    bool
    reason:     Optional[str] = None
    upgrade_to: Optional[str] = None
    remaining:  Optional[int] = None

    def __bool__(self) -> bool:
        return self.allowed


# --------------------------------------------------------------------
#  Plan lookups
# --------------------------------------------------------------------
def _resolve_plan_via_family(user_id: str) -> str | None:
    """Look up plan_id via family membership.

    Returns 'family_pro' if the user is an ACTIVE member of a family
    with a non-cancelled Family Pro subscription. Returns None otherwise.

    Safe — wraps family_storage in try/except so a storage-layer
    failure can never break the entitlements pipeline.
    """
    try:
        import family_storage
        if family_storage.is_family_pro_member(user_id):
            return FAMILY_PLAN_ID
        return None
    except Exception:
        return None


def _resolve_plan_id(plan_snapshot: Optional[dict]) -> str:
    """Pick a plan id out of a v_my_plan row, defaulting to FREE.

    Falls back to family membership when the user has no direct
    subscription: a Family Pro member resolves to 'family_pro' even
    if they never bought a sub themselves. Direct subs always win.
    """
    if not plan_snapshot:
        return FREE_PLAN_ID
    pid = plan_snapshot.get("plan_id")
    if pid in PLAN_CAPS:
        return pid
    # No direct subscription — check family membership before falling back.
    user_id = plan_snapshot.get("user_id")
    if user_id:
        via_family = _resolve_plan_via_family(user_id)
        if via_family:
            return via_family
    return FREE_PLAN_ID


def caps_for(plan_id: str) -> dict:
    """Return the capability dict for a plan id (defaults to FREE)."""
    return PLAN_CAPS.get(plan_id) or PLAN_CAPS[FREE_PLAN_ID]


def is_pro(plan_snapshot: Optional[dict]) -> bool:
    """True if the user is on any paid plan (or beta-comp Pro)."""
    return _resolve_plan_id(plan_snapshot) in PRO_PLANS


def status_is_active(plan_snapshot: Optional[dict]) -> bool:
    """Whether the user's sub is in a non-terminal state."""
    if not plan_snapshot:
        return False
    return plan_snapshot.get("status") in ("active", "trialing", "comp")


# --------------------------------------------------------------------
#  Capability checks
# --------------------------------------------------------------------
def can_analyze_swing(plan_snapshot: Optional[dict]) -> EntitlementResult:
    """
    Free: hard-capped at FREE_SWING_LIMIT lifetime analyses.
    Any Pro plan: unlimited.
    """
    plan_id = _resolve_plan_id(plan_snapshot)
    caps    = caps_for(plan_id)
    limit   = caps.get("swing_limit_lifetime")

    if limit is None:
        return EntitlementResult(allowed=True)

    used = int((plan_snapshot or {}).get("free_swings_used") or 0)
    remaining = max(0, limit - used)
    if remaining <= 0:
        return EntitlementResult(
            allowed=False,
            reason=(
                f"You\u2019ve used all {limit} of your free swing analyses. "
                "Upgrade to Pro for unlimited swings, drill plans, "
                "video saving, and the full Development Tracker."
            ),
            upgrade_to=SOLO_PLAN_ID,
            remaining=0,
        )
    return EntitlementResult(allowed=True, remaining=remaining)


def _gate_pro_only(
    plan_snapshot: Optional[dict],
    cap_key: str,
    feature_label: str,
) -> EntitlementResult:
    """Shared helper for boolean Pro-only feature gates."""
    plan_id = _resolve_plan_id(plan_snapshot)
    caps    = caps_for(plan_id)
    if caps.get(cap_key):
        return EntitlementResult(allowed=True)
    return EntitlementResult(
        allowed=False,
        reason=(
            f"{feature_label} is a Pro feature. "
            "Upgrade to unlock it (or redeem a beta code)."
        ),
        upgrade_to=SOLO_PLAN_ID,
    )


def can_save_drill_plan(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(plan_snapshot, "drill_plan", "Personalized drill plans")


def can_save_video(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(plan_snapshot, "video_storage", "Swing video saving")


def can_access_development_tracker(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(
        plan_snapshot, "development_tracker", "The Development Tracker",
    )


def can_export_pdf(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(plan_snapshot, "pdf_export", "PDF report export")


def can_compare_swings(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(plan_snapshot, "compare_swings", "Swing comparisons")


def can_access_rewards(plan_snapshot: Optional[dict]) -> EntitlementResult:
    return _gate_pro_only(plan_snapshot, "rewards", "Streaks, XP, and rewards")


# --------------------------------------------------------------------
#  Display helpers — used by paywall / pricing screens
# --------------------------------------------------------------------
def plan_display_name(plan_id: str) -> str:
    return {
        FREE_PLAN_ID:    "Free",
        SOLO_PLAN_ID:    "Solo Pro",
        FAMILY_PLAN_ID:  "Family Pro",
        COACH_PLAN_ID:   "Coach Pro",
    }.get(plan_id, plan_id.title())


def plan_seat_count(plan_id: str) -> int:
    return {
        FREE_PLAN_ID:   1,
        SOLO_PLAN_ID:   1,
        FAMILY_PLAN_ID: 4,
        COACH_PLAN_ID:  20,
    }.get(plan_id, 1)


__all__ = [
    "FREE_PLAN_ID", "SOLO_PLAN_ID", "FAMILY_PLAN_ID", "COACH_PLAN_ID",
    "PRO_PLANS", "FREE_SWING_LIMIT",
    "PLAN_CAPS",
    "EntitlementResult",
    "caps_for", "is_pro", "status_is_active",
    "can_analyze_swing", "can_save_drill_plan", "can_save_video",
    "can_access_development_tracker", "can_export_pdf",
    "can_compare_swings", "can_access_rewards",
    "plan_display_name", "plan_seat_count",
]
