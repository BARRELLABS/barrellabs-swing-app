"""
Unit tests for entitlements.py — the source of truth for every "can this
user do X?" question in the app.

Why these tests matter
----------------------
Entitlements is the only thing between Free users and Pro features. A
silent regression here (e.g. `can_analyze_swing` always returning True,
or `is_pro` defaulting wrong) means we either give away unlimited Pro
features or lock paying customers out of what they bought. The functions
are pure (take a `plan_snapshot` dict, return EntitlementResult / bool)
so they're trivially unit-testable — there is no excuse for not having
this safety net.

These tests are deliberately exhaustive across the realistic plan_snapshot
shapes that `subscription_storage.load_my_plan` can return: None, {},
free-with-counter, paid-active, paid-canceled, paid-trialing, paid-comp,
and unknown-plan-id fallbacks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from entitlements import (  # noqa: E402
    # Constants
    FREE_PLAN_ID, SOLO_PLAN_ID, FAMILY_PLAN_ID, COACH_PLAN_ID,
    PRO_PLANS, FREE_SWING_LIMIT, PLAN_CAPS,
    # Result type
    EntitlementResult,
    # Helpers
    caps_for, is_pro, status_is_active,
    # Gates
    can_analyze_swing,
    can_save_drill_plan, can_save_video, can_access_development_tracker,
    can_export_pdf, can_compare_swings, can_access_rewards,
    # Display
    plan_display_name, plan_seat_count,
)
# _resolve_plan_id is private — import directly for completeness
from entitlements import _resolve_plan_id  # noqa: E402


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


class TestConstants:
    def test_free_swing_limit_is_three(self):
        # Pricing pages, swing-limit walls, and post-analysis nudges all
        # reference "3 free swings". A change here must be a deliberate
        # product decision, not a typo.
        assert FREE_SWING_LIMIT == 3

    def test_pro_plans_set_contents(self):
        # If somebody adds a new plan they must also add it to PRO_PLANS —
        # otherwise is_pro returns False for paying customers.
        assert PRO_PLANS == {SOLO_PLAN_ID, FAMILY_PLAN_ID, COACH_PLAN_ID}

    def test_plan_caps_has_every_plan_id(self):
        for pid in (FREE_PLAN_ID, SOLO_PLAN_ID, FAMILY_PLAN_ID, COACH_PLAN_ID):
            assert pid in PLAN_CAPS, f"missing PLAN_CAPS entry for {pid!r}"

    def test_free_plan_caps_are_all_blocked(self):
        """Every boolean cap on Free must be False. Adding a new
        capability and forgetting to set it on Free is a regression
        that silently grants Free users a Pro feature."""
        free = PLAN_CAPS[FREE_PLAN_ID]
        for key, val in free.items():
            if isinstance(val, bool):
                assert val is False, (
                    f"Free cap {key!r}={val!r} — should be False on Free"
                )

    def test_pro_plans_unlock_every_boolean_cap(self):
        """All Pro plans (solo/family/coach) must unlock every boolean
        capability. Pro tiers differ in seat count, not capabilities."""
        for pid in PRO_PLANS:
            caps = PLAN_CAPS[pid]
            for key, val in caps.items():
                if isinstance(val, bool):
                    assert val is True, (
                        f"{pid} cap {key!r}={val!r} — Pro plans should "
                        "unlock every boolean capability"
                    )


# ---------------------------------------------------------------------------
# _resolve_plan_id
# ---------------------------------------------------------------------------


class TestResolvePlanId:
    def test_none_resolves_to_free(self):
        assert _resolve_plan_id(None) == FREE_PLAN_ID

    def test_empty_dict_resolves_to_free(self):
        assert _resolve_plan_id({}) == FREE_PLAN_ID

    def test_known_plan_ids_pass_through(self):
        for pid in (FREE_PLAN_ID, SOLO_PLAN_ID, FAMILY_PLAN_ID, COACH_PLAN_ID):
            assert _resolve_plan_id({"plan_id": pid}) == pid

    def test_unknown_plan_id_falls_back_to_free(self):
        # If the DB ever returns a plan_id we don't recognize (e.g. an
        # in-progress migration, a typo), default to Free — NEVER grant
        # Pro capabilities to an unknown plan.
        assert _resolve_plan_id({"plan_id": "enterprise"}) == FREE_PLAN_ID
        assert _resolve_plan_id({"plan_id": "PRO"}) == FREE_PLAN_ID
        assert _resolve_plan_id({"plan_id": ""}) == FREE_PLAN_ID

    def test_extra_fields_ignored(self):
        # Real plan snapshots carry status, seat counts, free_swings_used.
        assert _resolve_plan_id({
            "plan_id": SOLO_PLAN_ID,
            "status": "active",
            "seat_count": 1,
            "free_swings_used": 0,
        }) == SOLO_PLAN_ID


# ---------------------------------------------------------------------------
# caps_for
# ---------------------------------------------------------------------------


class TestCapsFor:
    def test_known_plan_returns_its_caps(self):
        caps = caps_for(SOLO_PLAN_ID)
        assert caps["video_storage"] is True
        assert caps["pdf_export"] is True

    def test_unknown_plan_returns_free_caps(self):
        # Defensive default — same rationale as _resolve_plan_id.
        caps = caps_for("nonsense_plan")
        assert caps["pdf_export"] is False
        assert caps["video_storage"] is False

    def test_caps_for_returns_dict_not_none(self):
        # Some call sites do `caps_for(...).get(...)`. Returning None
        # would raise AttributeError.
        assert isinstance(caps_for("anything"), dict)
        assert isinstance(caps_for(FREE_PLAN_ID), dict)


# ---------------------------------------------------------------------------
# is_pro
# ---------------------------------------------------------------------------


class TestIsPro:
    def test_none_is_not_pro(self):
        assert is_pro(None) is False

    def test_empty_dict_is_not_pro(self):
        assert is_pro({}) is False

    def test_free_plan_is_not_pro(self):
        assert is_pro({"plan_id": FREE_PLAN_ID}) is False

    def test_solo_pro_is_pro(self):
        assert is_pro({"plan_id": SOLO_PLAN_ID}) is True

    def test_family_pro_is_pro(self):
        assert is_pro({"plan_id": FAMILY_PLAN_ID}) is True

    def test_coach_pro_is_pro(self):
        assert is_pro({"plan_id": COACH_PLAN_ID}) is True

    def test_unknown_plan_is_not_pro(self):
        assert is_pro({"plan_id": "enterprise"}) is False


# ---------------------------------------------------------------------------
# status_is_active
# ---------------------------------------------------------------------------


class TestStatusIsActive:
    @pytest.mark.parametrize("status", ["active", "trialing", "comp"])
    def test_active_statuses(self, status):
        assert status_is_active({"plan_id": SOLO_PLAN_ID, "status": status}) is True

    @pytest.mark.parametrize(
        "status",
        ["canceled", "incomplete", "incomplete_expired", "past_due",
         "unpaid", "paused", None, ""],
    )
    def test_inactive_statuses(self, status):
        assert status_is_active({"plan_id": SOLO_PLAN_ID, "status": status}) is False

    def test_none_snapshot(self):
        assert status_is_active(None) is False

    def test_empty_snapshot(self):
        assert status_is_active({}) is False


# ---------------------------------------------------------------------------
# can_analyze_swing — the headline gate
# ---------------------------------------------------------------------------


class TestCanAnalyzeSwing:
    """The single most important gate in the app. Bugs here either
    bleed paying users or give away unlimited free analyses."""

    def test_fresh_free_user_allowed(self):
        result = can_analyze_swing({"plan_id": FREE_PLAN_ID, "free_swings_used": 0})
        assert result.allowed is True
        assert result.remaining == FREE_SWING_LIMIT

    def test_free_user_with_one_swing_used(self):
        result = can_analyze_swing({"plan_id": FREE_PLAN_ID, "free_swings_used": 1})
        assert result.allowed is True
        assert result.remaining == FREE_SWING_LIMIT - 1

    def test_free_user_on_last_swing_still_allowed(self):
        # Used 2, limit is 3 → has 1 left → still allowed.
        result = can_analyze_swing(
            {"plan_id": FREE_PLAN_ID, "free_swings_used": FREE_SWING_LIMIT - 1}
        )
        assert result.allowed is True
        assert result.remaining == 1

    def test_free_user_at_limit_blocked(self):
        result = can_analyze_swing(
            {"plan_id": FREE_PLAN_ID, "free_swings_used": FREE_SWING_LIMIT}
        )
        assert result.allowed is False
        assert result.remaining == 0
        assert result.upgrade_to == SOLO_PLAN_ID
        assert result.reason and len(result.reason) > 10

    def test_free_user_overshoot_still_blocked(self):
        # Defensive: if free_swings_used somehow exceeds the limit
        # (race condition, manual DB edit, etc.) the user still gets
        # blocked, not silently allowed back in.
        result = can_analyze_swing(
            {"plan_id": FREE_PLAN_ID, "free_swings_used": FREE_SWING_LIMIT + 100}
        )
        assert result.allowed is False
        assert result.remaining == 0

    def test_solo_pro_is_unlimited(self):
        result = can_analyze_swing(
            {"plan_id": SOLO_PLAN_ID, "status": "active", "free_swings_used": 0}
        )
        assert result.allowed is True
        # remaining is None for unlimited plans (no counter to surface)
        assert result.remaining is None

    def test_family_pro_is_unlimited(self):
        assert can_analyze_swing({"plan_id": FAMILY_PLAN_ID}).allowed is True

    def test_coach_pro_is_unlimited(self):
        assert can_analyze_swing({"plan_id": COACH_PLAN_ID}).allowed is True

    def test_pro_user_ignores_free_swings_used_counter(self):
        # Even if the counter is high (e.g. user upgraded mid-flow),
        # Pro should be unlimited. The counter is a Free-only concept.
        result = can_analyze_swing(
            {"plan_id": SOLO_PLAN_ID, "free_swings_used": 999}
        )
        assert result.allowed is True

    def test_none_plan_treated_as_free(self):
        result = can_analyze_swing(None)
        assert result.allowed is True  # Free has 3 swings, used 0 → allowed
        assert result.remaining == FREE_SWING_LIMIT

    def test_missing_free_swings_used_treated_as_zero(self):
        # New free user with no counter yet — should be allowed.
        result = can_analyze_swing({"plan_id": FREE_PLAN_ID})
        assert result.allowed is True
        assert result.remaining == FREE_SWING_LIMIT

    def test_null_free_swings_used_treated_as_zero(self):
        # Supabase can return NULL for a missing column.
        result = can_analyze_swing(
            {"plan_id": FREE_PLAN_ID, "free_swings_used": None}
        )
        assert result.allowed is True
        assert result.remaining == FREE_SWING_LIMIT


# ---------------------------------------------------------------------------
# Generic Pro-only gates (can_export_pdf, can_save_video, etc.)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate_fn,cap_key",
    [
        (can_save_drill_plan,              "drill_plan"),
        (can_save_video,                   "video_storage"),
        (can_access_development_tracker,   "development_tracker"),
        (can_export_pdf,                   "pdf_export"),
        (can_compare_swings,               "compare_swings"),
        (can_access_rewards,               "rewards"),
    ],
)
class TestProOnlyGates:
    """One parametrized test class covering every Pro-only gate. Adding
    a new gate? Add it to the parametrize list above and these tests
    cover it automatically."""

    def test_blocks_none(self, gate_fn, cap_key):
        result = gate_fn(None)
        assert result.allowed is False
        assert result.upgrade_to == SOLO_PLAN_ID
        assert result.reason and "Pro feature" in result.reason

    def test_blocks_empty(self, gate_fn, cap_key):
        result = gate_fn({})
        assert result.allowed is False
        assert result.upgrade_to == SOLO_PLAN_ID

    def test_blocks_free(self, gate_fn, cap_key):
        result = gate_fn({"plan_id": FREE_PLAN_ID})
        assert result.allowed is False
        assert result.upgrade_to == SOLO_PLAN_ID

    def test_blocks_unknown_plan(self, gate_fn, cap_key):
        result = gate_fn({"plan_id": "enterprise"})
        assert result.allowed is False
        assert result.upgrade_to == SOLO_PLAN_ID

    def test_allows_solo_pro(self, gate_fn, cap_key):
        result = gate_fn({"plan_id": SOLO_PLAN_ID, "status": "active"})
        assert result.allowed is True
        assert result.reason is None
        assert result.upgrade_to is None

    def test_allows_family_pro(self, gate_fn, cap_key):
        result = gate_fn({"plan_id": FAMILY_PLAN_ID, "status": "active"})
        assert result.allowed is True

    def test_allows_coach_pro(self, gate_fn, cap_key):
        result = gate_fn({"plan_id": COACH_PLAN_ID, "status": "active"})
        assert result.allowed is True


# ---------------------------------------------------------------------------
# EntitlementResult — truthiness + shape
# ---------------------------------------------------------------------------


class TestEntitlementResult:
    def test_truthy_when_allowed(self):
        r = EntitlementResult(allowed=True)
        assert bool(r) is True
        if r:
            pass
        else:
            pytest.fail("allowed=True should evaluate truthy")

    def test_falsy_when_blocked(self):
        r = EntitlementResult(allowed=False, reason="nope", upgrade_to=SOLO_PLAN_ID)
        assert bool(r) is False
        if not r:
            pass
        else:
            pytest.fail("allowed=False should evaluate falsy")

    def test_fields_default_to_none(self):
        r = EntitlementResult(allowed=True)
        assert r.reason is None
        assert r.upgrade_to is None
        assert r.remaining is None


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


class TestPlanDisplayName:
    @pytest.mark.parametrize("plan_id,expected", [
        (FREE_PLAN_ID,    "Free"),
        (SOLO_PLAN_ID,    "Solo Pro"),
        (FAMILY_PLAN_ID,  "Family Pro"),
        (COACH_PLAN_ID,   "Coach Pro"),
    ])
    def test_known_plans(self, plan_id, expected):
        assert plan_display_name(plan_id) == expected

    def test_unknown_plan_titlecased(self):
        assert plan_display_name("enterprise") == "Enterprise"


class TestPlanSeatCount:
    @pytest.mark.parametrize("plan_id,expected", [
        (FREE_PLAN_ID,    1),
        (SOLO_PLAN_ID,    1),
        (FAMILY_PLAN_ID,  4),
        (COACH_PLAN_ID,   20),
    ])
    def test_known_plans(self, plan_id, expected):
        assert plan_seat_count(plan_id) == expected

    def test_unknown_plan_defaults_to_one(self):
        # Defensive: never multi-seat an unknown plan.
        assert plan_seat_count("nonsense") == 1


# ---------------------------------------------------------------------------
# Cross-cutting safety — "no gates leak across plans"
# ---------------------------------------------------------------------------


class TestCrossPlanSafety:
    """Sanity checks that catch the broad class of "I added a gate and
    forgot to update something" bugs."""

    def test_every_pro_gate_blocks_free(self):
        """If somebody adds a new Pro gate but forgets to add the cap
        to Free's PLAN_CAPS, the gate could silently allow Free users
        (because caps.get(cap_key) returns None which is falsy — wait,
        that's actually correct). Instead test the contract: every
        boolean cap MUST be present on every plan."""
        all_cap_keys = set()
        for caps in PLAN_CAPS.values():
            all_cap_keys.update(caps.keys())
        for plan_id, caps in PLAN_CAPS.items():
            for key in all_cap_keys:
                assert key in caps, (
                    f"plan {plan_id} is missing cap {key!r} — every plan "
                    "must explicitly set every cap, no implicit defaults"
                )

    def test_free_has_no_unlimited_swings(self):
        # If somebody flips Free's swing_limit_lifetime to None thinking
        # it means "no limit field needed", they'd give away unlimited
        # free swings. This guards against that.
        assert PLAN_CAPS[FREE_PLAN_ID]["swing_limit_lifetime"] is not None
        assert PLAN_CAPS[FREE_PLAN_ID]["swing_limit_lifetime"] > 0

    def test_every_pro_plan_has_unlimited_swings(self):
        for pid in PRO_PLANS:
            assert PLAN_CAPS[pid]["swing_limit_lifetime"] is None, (
                f"{pid} should have swing_limit_lifetime=None (unlimited)"
            )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
