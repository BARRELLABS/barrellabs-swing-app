#!/usr/bin/env python3
"""
BarrelLabs SwingAI — Stripe products & prices setup CLI.

Run this ONCE per Stripe environment (test, then later live) to create
the products and prices for all three Pro plans on Stripe's side. The
script is idempotent: it uses Stripe `lookup_key`s to find existing
prices before creating new ones, so re-runs are safe.

It prints a ready-to-paste TOML block at the end with the price IDs you
need to drop into `.streamlit/secrets.toml`.

Setup
-----
1. Get your Stripe secret key from https://dashboard.stripe.com/test/apikeys
   (use the TEST key for now — flip to live later).

2. Either export it, or add it to `.streamlit/secrets.toml`:

       [stripe]
       secret_key = "sk_test_..."

3. Install stripe:
       ./venv/bin/pip install stripe

4. Run me:
       ./stripe_setup.py
       ./stripe_setup.py --dry-run     # preview, no API writes
       ./stripe_setup.py --mode live   # later, when ready for production

Pricing source of truth
-----------------------
The dollar amounts below match what we agreed on:
  * Solo Pro    — $14.99 / mo   $99 / yr
  * Family Pro  — $24.99 / mo   $179 / yr
  * Coach Pro   — $79.99 / mo   $599 / yr

If you change these, change them HERE — that keeps Stripe + the app in
sync. Then re-run me; the script will detect the mismatch and create
fresh prices (Stripe prices are immutable, so we never edit, only
add + deprecate).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional


# --------------------------------------------------------------------
#  Pricing — single source of truth (mirrors entitlements.py / SQL)
# --------------------------------------------------------------------
PRICING = [
    # (plan_id,       display_name,  description,                                  monthly_cents, annual_cents)
    ("solo_pro",      "Solo Pro",    "Unlimited swings, drills, video, PDFs.",     1499,           9900),
    ("family_pro",    "Family Pro",  "Solo Pro for up to 4 family members.",        2499,          17900),
    ("coach_pro",     "Coach Pro",   "Solo Pro for up to 20 players + roster.",     7999,          59900),
]


# --------------------------------------------------------------------
#  Credentials — env > secrets.toml
# --------------------------------------------------------------------
def _load_stripe_key(mode: str) -> str:
    """
    Load the Stripe secret key for the requested mode.

    Priority:
      1. STRIPE_SECRET_KEY env var (whatever mode it's for)
      2. [stripe].secret_key in secrets.toml (test mode default)
      3. [stripe].live_secret_key in secrets.toml (when --mode live)
    """
    env = os.environ.get("STRIPE_SECRET_KEY")
    if env:
        return env

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib   # type: ignore
        except ImportError:
            print(
                "ERROR: STRIPE_SECRET_KEY not set and tomllib not available.",
                file=sys.stderr,
            )
            sys.exit(2)

    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if not secrets_path.is_file():
        print(f"ERROR: No env var and no {secrets_path}.", file=sys.stderr)
        sys.exit(2)

    with open(secrets_path, "rb") as fh:
        cfg = tomllib.load(fh)
    section = cfg.get("stripe") or {}
    key = section.get("live_secret_key" if mode == "live" else "secret_key")
    if not key:
        print(
            f"ERROR: Missing [stripe].{'live_secret_key' if mode == 'live' else 'secret_key'} "
            f"in secrets.toml.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def _confirm_mode(key: str, mode: str) -> None:
    """Sanity check: the key prefix should match the requested mode."""
    if mode == "test" and not key.startswith("sk_test_"):
        print(
            "ERROR: --mode test was requested but the key doesn't start with "
            "'sk_test_'. Bailing to avoid hitting live Stripe by accident.",
            file=sys.stderr,
        )
        sys.exit(2)
    if mode == "live" and not key.startswith("sk_live_"):
        print(
            "ERROR: --mode live was requested but the key doesn't start with "
            "'sk_live_'.",
            file=sys.stderr,
        )
        sys.exit(2)


# --------------------------------------------------------------------
#  Lookup-key conventions
# --------------------------------------------------------------------
def _price_lookup_key(plan_id: str, interval: str) -> str:
    """e.g. bl_solo_pro_monthly_v1. Bump the suffix if you ever need to
    deprecate a price and ship a new one at a different amount."""
    return f"bl_{plan_id}_{interval}_v1"


# --------------------------------------------------------------------
#  Stripe API helpers
# --------------------------------------------------------------------
def _find_or_create_product(stripe, *, plan_id: str, name: str, description: str,
                             dry_run: bool) -> Optional[dict]:
    """
    Use the `metadata.bl_plan_id` field to find an existing product, or
    create a fresh one. Returns the product dict (or None in dry-run).
    """
    # Search by metadata is the cleanest way; Stripe supports it via the
    # search API.
    query = f"metadata['bl_plan_id']:'{plan_id}'"
    try:
        existing = stripe.Product.search(query=query, limit=1)
        if existing.data:
            prod = existing.data[0]
            print(f"  product OK       — {prod.id} ({prod.name})")
            return prod
    except Exception as exc:
        # Search API isn't enabled on every account; fall through to list.
        try:
            for prod in stripe.Product.list(limit=100).auto_paging_iter():
                if (prod.metadata or {}).get("bl_plan_id") == plan_id:
                    print(f"  product OK       — {prod.id} ({prod.name})")
                    return prod
        except Exception as inner:
            print(f"  WARN: product lookup failed: {inner}", file=sys.stderr)

    if dry_run:
        print(f"  product DRY-RUN  — would create {name!r}")
        return None

    prod = stripe.Product.create(
        name=name,
        description=description,
        metadata={"bl_plan_id": plan_id},
    )
    print(f"  product CREATED  — {prod.id}")
    return prod


def _find_or_create_price(stripe, *, product_id: str, plan_id: str,
                           interval: str, unit_amount_cents: int,
                           dry_run: bool) -> Optional[dict]:
    """
    Look up by lookup_key. If found AND the unit_amount matches, reuse.
    If found but amount mismatches, deactivate it and mint a new one
    with the same lookup_key (Stripe re-points the key automatically).
    """
    lkey = _price_lookup_key(plan_id, interval)

    # Stripe lets you fetch directly by lookup_keys.
    existing = stripe.Price.list(lookup_keys=[lkey], active=True, limit=1)
    if existing.data:
        price = existing.data[0]
        if price.unit_amount == unit_amount_cents and price.recurring \
                and price.recurring.interval == ("month" if interval == "monthly" else "year"):
            print(f"  price OK         — {price.id} (${unit_amount_cents/100:.2f}/{interval})")
            return price

        # Stale amount — deactivate + recreate.
        print(f"  price MISMATCH   — deactivating {price.id} "
              f"(was ${price.unit_amount/100:.2f}, want ${unit_amount_cents/100:.2f})")
        if not dry_run:
            stripe.Price.modify(price.id, active=False, lookup_key="")

    if dry_run:
        print(f"  price DRY-RUN    — would create {lkey} at ${unit_amount_cents/100:.2f}/{interval}")
        return None

    new_price = stripe.Price.create(
        product=product_id,
        currency="usd",
        unit_amount=unit_amount_cents,
        recurring={"interval": "month" if interval == "monthly" else "year"},
        lookup_key=lkey,
        transfer_lookup_key=True,
        metadata={"bl_plan_id": plan_id, "bl_interval": interval},
    )
    print(f"  price CREATED    — {new_price.id} ({lkey})")
    return new_price


# --------------------------------------------------------------------
#  Main
# --------------------------------------------------------------------
def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(
        description="Create / sync BarrelLabs Stripe products & prices.",
    )
    p.add_argument("--mode", choices=["test", "live"], default="test",
                   help="Which Stripe environment to operate on (default: test).")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would happen without writing anything.")
    args = p.parse_args(argv)

    try:
        import stripe  # type: ignore
    except ImportError:
        print(
            "ERROR: stripe SDK not installed. Run:\n"
            "    ./venv/bin/pip install stripe",
            file=sys.stderr,
        )
        return 2

    key = _load_stripe_key(args.mode)
    _confirm_mode(key, args.mode)
    stripe.api_key = key

    print(f"=== BarrelLabs Stripe Setup — mode={args.mode}{'  (DRY RUN)' if args.dry_run else ''} ===\n")

    results: list[dict] = []
    for plan_id, name, description, monthly, annual in PRICING:
        print(f"[{plan_id}] {name}")
        prod = _find_or_create_product(
            stripe,
            plan_id=plan_id,
            name=f"BarrelLabs SwingAI — {name}",
            description=description,
            dry_run=args.dry_run,
        )
        product_id = prod.id if prod else f"<would-create:{plan_id}>"

        monthly_price = _find_or_create_price(
            stripe,
            product_id=product_id,
            plan_id=plan_id,
            interval="monthly",
            unit_amount_cents=monthly,
            dry_run=args.dry_run,
        )
        annual_price = _find_or_create_price(
            stripe,
            product_id=product_id,
            plan_id=plan_id,
            interval="annual",
            unit_amount_cents=annual,
            dry_run=args.dry_run,
        )
        results.append({
            "plan_id":        plan_id,
            "product_id":     product_id,
            "monthly_id":     monthly_price.id if monthly_price else f"<would-create:{plan_id}-monthly>",
            "annual_id":      annual_price.id  if annual_price  else f"<would-create:{plan_id}-annual>",
        })
        print()

    # ---- TOML output to paste into secrets.toml ----
    suffix = "_live" if args.mode == "live" else ""
    print("=" * 64)
    print(f"Add this block to .streamlit/secrets.toml under [stripe]:\n")
    print("[stripe]")
    print(f'#  ^ keep any existing keys (secret_key, publishable_key, webhook_secret) above')
    for r in results:
        plan = r["plan_id"]
        print(f'price_{plan}_monthly{suffix} = "{r["monthly_id"]}"')
        print(f'price_{plan}_annual{suffix}  = "{r["annual_id"]}"')
    print("=" * 64)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
