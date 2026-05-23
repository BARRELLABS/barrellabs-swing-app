"""Family Pro entitlement propagation.

The key architectural fact: the `v_my_plan` SQL view ALREADY resolves a
member's plan through their `subscription_seats` seat. So a seat on a
family_pro subscription arrives at `entitlements._resolve_plan_id` as a
snapshot with plan_id='family_pro' — no special-case code needed. These
tests lock in that pass-through behavior so nobody re-adds a redundant
family fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


class TestPlanResolutionPassThrough:
    def test_family_pro_snapshot_resolves_to_family_pro(self):
        """A member's v_my_plan row (resolved through their seat) carries
        plan_id='family_pro' → entitlements returns family_pro."""
        import entitlements
        snap = {"plan_id": "family_pro", "status": "active",
                "user_id": "kid-uuid"}
        assert entitlements._resolve_plan_id(snap) == "family_pro"

    def test_solo_pro_snapshot_resolves_to_solo_pro(self):
        import entitlements
        snap = {"plan_id": "solo_pro", "status": "active"}
        assert entitlements._resolve_plan_id(snap) == "solo_pro"

    def test_none_snapshot_resolves_to_free(self):
        import entitlements
        assert entitlements._resolve_plan_id(None) == entitlements.FREE_PLAN_ID

    def test_unknown_plan_resolves_to_free(self):
        import entitlements
        snap = {"plan_id": "nonsense_plan"}
        assert entitlements._resolve_plan_id(snap) == entitlements.FREE_PLAN_ID

    def test_no_redundant_family_helper_remains(self):
        """Guard against re-introducing the removed _resolve_plan_via_family
        fallback — v_my_plan is the single source of truth."""
        import entitlements
        assert not hasattr(entitlements, "_resolve_plan_via_family"), (
            "v_my_plan already resolves family seats; a separate helper "
            "creates a competing resolution path. Don't re-add it."
        )
