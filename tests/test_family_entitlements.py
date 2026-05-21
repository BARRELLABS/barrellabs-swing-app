"""Family Pro entitlement propagation.

When a user is an active member of a family with an active Family
Pro subscription, they should resolve to 'family_pro' even if they
have no direct subscription of their own. A direct subscription
always wins over family membership.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


class TestFamilyEntitlementPropagation:
    def test_family_member_with_no_direct_sub_resolves_to_family_pro(self, monkeypatch):
        """A kid added to a Family Pro household sees family_pro plan,
        even though they didn't buy anything themselves."""
        import family_storage
        # Mock family_storage to say "yes, this user is in a Family Pro family"
        monkeypatch.setattr(family_storage, "is_family_pro_member",
                            lambda uid: True)
        # Now invoke the entitlements resolution — it should pick up family_pro
        # via the new helper. The exact function name depends on what we find.
        import entitlements
        # Try the common names; one of these should exist
        if hasattr(entitlements, "_resolve_plan_via_family"):
            assert entitlements._resolve_plan_via_family("kid-uuid") == "family_pro"
        else:
            pytest.fail("expected entitlements._resolve_plan_via_family helper")

    def test_non_member_falls_through_to_none(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "is_family_pro_member",
                            lambda uid: False)
        import entitlements
        if hasattr(entitlements, "_resolve_plan_via_family"):
            assert entitlements._resolve_plan_via_family("random-uuid") is None

    def test_helper_safe_when_family_storage_breaks(self, monkeypatch):
        """If family_storage raises an exception, the helper should return
        None gracefully — never break the entitlements pipeline."""
        import family_storage
        def boom(*a, **k):
            raise RuntimeError("storage layer crashed")
        monkeypatch.setattr(family_storage, "is_family_pro_member", boom)
        import entitlements
        if hasattr(entitlements, "_resolve_plan_via_family"):
            assert entitlements._resolve_plan_via_family("any-uuid") is None
