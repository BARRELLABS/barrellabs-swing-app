"""Tests for facility sponsored-Pro grant + portability + tier helpers.

Spec: docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md §6
"""
import entitlements as ent


# --- sponsored grant + portability ---------------------------------

def test_sponsored_free_player_becomes_pro():
    snap = {"plan_id": "free", "free_swings_used": 9}
    eff = ent.resolve_effective_plan(snap, sponsored=True)
    assert eff == ent.SOLO_PLAN_ID
    assert ent.is_pro({"plan_id": eff})
    # the free-swing cap no longer bites a sponsored player
    assert ent.can_analyze_swing({"plan_id": eff}).allowed is True


def test_unsponsored_free_player_still_capped():
    snap = {"plan_id": "free", "free_swings_used": 9}
    eff = ent.resolve_effective_plan(snap, sponsored=False)
    assert eff == ent.FREE_PLAN_ID


def test_paid_sub_never_downgraded_by_losing_sponsorship():
    # Portability: a real paying customer keeps their plan when sponsorship ends.
    snap = {"plan_id": "solo_pro"}
    assert ent.resolve_effective_plan(snap, sponsored=False) == "solo_pro"
    assert ent.resolve_effective_plan(snap, sponsored=True) == "solo_pro"


def test_none_snapshot_defaults_free_unless_sponsored():
    assert ent.resolve_effective_plan(None, sponsored=False) == ent.FREE_PLAN_ID
    assert ent.resolve_effective_plan(None, sponsored=True) == ent.SOLO_PLAN_ID


# --- facility tier helpers -----------------------------------------

def test_tier_for_roster_picks_smallest_covering_bracket():
    assert ent.facility_tier_for_roster(10) == "team"
    assert ent.facility_tier_for_roster(25) == "team"
    assert ent.facility_tier_for_roster(26) == "academy"
    assert ent.facility_tier_for_roster(100) == "academy"
    assert ent.facility_tier_for_roster(250) == "academy_plus"
    assert ent.facility_tier_for_roster(800) == "facility_pro"
    assert ent.facility_tier_for_roster(5000) == "facility_pro"  # 1000+ → custom at checkout


def test_roster_ceiling_lookup_and_coach_pro_alias():
    assert ent.facility_roster_ceiling("academy") == 100
    assert ent.facility_roster_ceiling("facility_pro") == 1000
    # deprecated coach_pro maps onto the academy bracket
    assert ent.facility_roster_ceiling("coach_pro") == 100
