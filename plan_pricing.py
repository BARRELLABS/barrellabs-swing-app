"""
BarrelLabs SwingAI — Plan pricing & Stripe price ID resolution.

Single source of truth for:
  • dollar amounts displayed on the pricing page
  • the mapping plan_id × interval -> Stripe price ID

The dollar amounts here MUST match what stripe_setup.py created, and what
the SQL migration's `plans` rows declare. If you change pricing, change
it in all three places (this file, stripe_setup.py PRICING, the SQL
migration's plans seed rows) and re-run stripe_setup.py.

Price IDs are read from `.streamlit/secrets.toml` so they can differ
between test & live mode without touching code.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


# --------------------------------------------------------------------
#  Display pricing (cents)
# --------------------------------------------------------------------
PLAN_PRICING = {
    "solo_pro": {
        "name":           "Solo Pro",
        "tagline":        "Everything you need to lock in your swing.",
        "monthly_cents":  1499,
        "annual_cents":   9900,
        "seats":          1,
    },
    "family_pro": {
        "name":           "Family Pro",
        "tagline":        "Solo Pro for up to 4 family members.",
        "monthly_cents":  2499,
        "annual_cents":   17900,
        "seats":          4,
    },
    "coach_pro": {
        "name":           "Coach Pro",
        "tagline":        "Solo Pro for up to 20 players + roster.",
        "monthly_cents":  7999,
        "annual_cents":   59900,
        "seats":          20,
    },
}


# --------------------------------------------------------------------
#  FACILITY / ACADEMY pricing — roster-size brackets (spec §6)
# --------------------------------------------------------------------
# License path: the facility pays, every rostered kid gets full Pro.
# Annual = ~2 months free vs monthly. `early_access_annual_cents` is the
# founding-facility launch price (locked 12 mo). Dollar amounts MUST match
# whatever stripe_setup.py creates + the SQL plans seed if these become
# real Stripe products.
FACILITY_PRICING = {
    "team": {
        "name": "Team", "roster_ceiling": 25,
        "monthly_cents": 9900,  "annual_cents": 99000,  "early_access_annual_cents": 69000,
    },
    "academy": {
        "name": "Academy", "roster_ceiling": 100,
        "monthly_cents": 29900, "annual_cents": 299000, "early_access_annual_cents": 199000,
    },
    "academy_plus": {
        "name": "Academy Plus", "roster_ceiling": 250,
        "monthly_cents": 54900, "annual_cents": 549000, "early_access_annual_cents": 349000,
    },
    "facility": {
        "name": "Facility", "roster_ceiling": 500,
        "monthly_cents": 89900, "annual_cents": 899000, "early_access_annual_cents": 599000,
    },
    "facility_pro": {
        "name": "Facility Pro", "roster_ceiling": 1000,
        "monthly_cents": 149900, "annual_cents": 1499000, "early_access_annual_cents": 999000,
    },
}

# Rev-share path: facility pays $0 upfront; parents pay the member rate
# through BarrelLabs; the facility earns the split. Setup fee filters
# tire-kickers (waived for founding facilities).
REVSHARE = {
    "member_monthly_cents": 1200,   # $12/mo per kid (discount off $14.99 retail)
    "platform_split":       0.70,   # BarrelLabs keeps 70%, facility earns 30%
    "setup_fee_cents":      40000,  # $400 one-time, waived for founders
}


def facility_stripe_price_id(tier: str, interval: str) -> Optional[str]:
    """Stripe price id for a facility tier × interval, from secrets.toml.
    Mirrors stripe_price_id(). interval ∈ {monthly, annual, early_access_annual}."""
    if tier not in FACILITY_PRICING:
        return None
    if interval not in ("monthly", "annual", "early_access_annual"):
        return None
    try:
        section = st.secrets.get("stripe", {})
    except Exception:
        return None
    suffix = "_live" if _live_mode() else ""
    key = f"price_facility_{tier}_{interval}{suffix}"
    val = section.get(key)
    return val.strip() if isinstance(val, str) and val.strip() else None


def annual_savings_pct(plan_id: str) -> int:
    """How much cheaper is annual vs 12 × monthly? Rounded to nearest int."""
    p = PLAN_PRICING.get(plan_id)
    if not p:
        return 0
    monthly_12 = p["monthly_cents"] * 12
    if monthly_12 <= 0:
        return 0
    savings = (monthly_12 - p["annual_cents"]) / monthly_12 * 100
    return max(0, round(savings))


def annual_monthly_equivalent_cents(plan_id: str) -> int:
    """For the 'or $8.25/mo billed annually' display line."""
    p = PLAN_PRICING.get(plan_id)
    if not p:
        return 0
    return round(p["annual_cents"] / 12)


def format_cents(cents: int) -> str:
    """149 → '$1.49', 1499 → '$14.99', 9900 → '$99'. Trims trailing .00."""
    dollars = cents / 100
    if abs(dollars - round(dollars)) < 0.005:
        return f"${int(round(dollars))}"
    return f"${dollars:,.2f}"


# --------------------------------------------------------------------
#  Stripe price ID resolution
# --------------------------------------------------------------------
def _live_mode() -> bool:
    """
    Is the Stripe integration pointing at live keys? Determined by the
    presence of [stripe].mode = "live" in secrets, falling back to
    inspecting the secret key prefix.
    """
    try:
        section = st.secrets.get("stripe", {})
    except Exception:
        return False
    mode = section.get("mode")
    if mode == "live":
        return True
    if mode == "test":
        return False
    # Fallback: look at the secret key prefix.
    key = section.get("secret_key", "") or ""
    return key.startswith("sk_live_")


def stripe_price_id(plan_id: str, interval: str) -> Optional[str]:
    """
    Look up the Stripe price ID for (plan, interval) from secrets.toml.

    Keys are expected in either of these shapes (test vs live):
        price_solo_pro_monthly        (test)
        price_solo_pro_annual         (test)
        price_solo_pro_monthly_live   (live)
        price_solo_pro_annual_live    (live)

    Returns None if the key isn't configured. The pricing page falls
    back to disabling the Upgrade button in that case (rather than
    sending users to a broken Stripe checkout).
    """
    if interval not in ("monthly", "annual"):
        return None
    try:
        section = st.secrets.get("stripe", {})
    except Exception:
        return None
    suffix = "_live" if _live_mode() else ""
    key = f"price_{plan_id}_{interval}{suffix}"
    val = section.get(key)
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def publishable_key() -> Optional[str]:
    """Stripe publishable key (pk_test_... or pk_live_...). Optional —
    we use Checkout's hosted page so the publishable key isn't strictly
    required, but it's handy if we ever embed Elements client-side."""
    try:
        section = st.secrets.get("stripe", {})
    except Exception:
        return None
    suffix = "_live" if _live_mode() else ""
    return section.get(f"publishable_key{suffix}") or section.get("publishable_key")


def stripe_secret_key() -> Optional[str]:
    """Server-side Stripe secret key. Required for Checkout/Portal sessions."""
    try:
        section = st.secrets.get("stripe", {})
    except Exception:
        return None
    if _live_mode():
        return section.get("live_secret_key") or section.get("secret_key")
    return section.get("secret_key")


__all__ = [
    "PLAN_PRICING",
    "FACILITY_PRICING",
    "REVSHARE",
    "annual_savings_pct",
    "annual_monthly_equivalent_cents",
    "format_cents",
    "stripe_price_id",
    "facility_stripe_price_id",
    "publishable_key",
    "stripe_secret_key",
]
