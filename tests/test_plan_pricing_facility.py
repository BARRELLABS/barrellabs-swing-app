"""Tests for facility bracket pricing + rev-share config (spec §6).

These assert the price BOOK (dollar amounts), independent of Stripe secrets.
"""
import plan_pricing as pp
import entitlements as ent


def test_facility_brackets_match_spec():
    assert pp.FACILITY_PRICING["academy"]["annual_cents"] == 299000          # $2,990
    assert pp.FACILITY_PRICING["academy"]["monthly_cents"] == 29900          # $299
    assert pp.FACILITY_PRICING["academy"]["early_access_annual_cents"] == 199000  # $1,990
    assert pp.FACILITY_PRICING["academy"]["roster_ceiling"] == 100
    assert pp.FACILITY_PRICING["facility_pro"]["annual_cents"] == 1499000     # $14,990


def test_every_tier_has_required_keys():
    for tier, cfg in pp.FACILITY_PRICING.items():
        for k in ("name", "roster_ceiling", "monthly_cents", "annual_cents", "early_access_annual_cents"):
            assert k in cfg, f"{tier} missing {k}"
        # annual should beat 12x monthly (the "2 months free" nudge)
        assert cfg["annual_cents"] < cfg["monthly_cents"] * 12
        # early access is a discount on the full annual
        assert cfg["early_access_annual_cents"] < cfg["annual_cents"]


def test_pricing_tiers_match_entitlement_ceilings():
    # the price book and the entitlement ceilings must agree
    for tier, cfg in pp.FACILITY_PRICING.items():
        assert cfg["roster_ceiling"] == ent.FACILITY_TIERS[tier]["roster_ceiling"]


def test_revshare_config():
    assert pp.REVSHARE["member_monthly_cents"] == 1200    # $12/mo
    assert pp.REVSHARE["platform_split"] == 0.70          # 70/30
    assert pp.REVSHARE["setup_fee_cents"] == 40000        # $400


def test_facility_stripe_price_id_unknown_returns_none():
    # No secrets configured in test → graceful None, never a broken checkout.
    assert pp.facility_stripe_price_id("nonsense_tier", "annual") is None
    assert pp.facility_stripe_price_id("academy", "bogus_interval") is None
