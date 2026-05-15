"""
BarrelLabs SwingAI — Stripe client wrapper.

Centralises every server-side Stripe call so the rest of the app
doesn't have to know about the SDK directly. Currently exposes:

    create_checkout_session(plan_id, interval, success_url, cancel_url)
        → returns the hosted Checkout URL the user is redirected to.

    create_portal_session(return_url)
        → returns a Stripe Customer Portal URL for the current user to
          manage billing / cancel / update payment method.

    get_or_create_stripe_customer()
        → returns the Stripe customer id for the current Supabase user,
          creating one on Stripe's side if this is their first paid
          interaction.

Design notes
------------
* We store stripe_customer_id on the public.subscriptions row when one
  exists. For users with no subscription yet (first-time checkout), we
  pass customer_email to Checkout and let Stripe mint the customer
  during checkout completion — the webhook then writes the new
  customer_id back to subscriptions.
* All calls fail-loud with ValueError so the UI can show a clean banner
  rather than dumping a Stripe SDK traceback to the screen.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from plan_pricing import stripe_price_id, stripe_secret_key
from supabase_client import get_client, get_current_user
from subscription_storage import load_my_plan


# --------------------------------------------------------------------
#  SDK bootstrap
# --------------------------------------------------------------------
def _stripe_module():
    """
    Lazy-import + auth the Stripe SDK. We bootstrap on every call so
    secret-key swaps (test → live) take effect on the next request
    without a process restart.
    """
    try:
        import stripe   # type: ignore
    except ImportError as exc:
        raise ValueError(
            "Payments aren't fully set up yet (the stripe SDK isn't installed). "
            "Run `./venv/bin/pip install stripe` and restart the app."
        ) from exc

    key = stripe_secret_key()
    if not key:
        raise ValueError(
            "Stripe isn't configured for this environment. Add "
            "[stripe].secret_key to .streamlit/secrets.toml."
        )
    stripe.api_key = key
    return stripe


# --------------------------------------------------------------------
#  Customer helpers
# --------------------------------------------------------------------
def _current_user_email() -> Optional[str]:
    """Pull the email of the currently logged-in Supabase user."""
    user = get_current_user()
    if not user:
        return None
    return getattr(user, "email", None)


def _existing_stripe_customer_id() -> Optional[str]:
    """
    Return the Stripe customer ID we've already stored for this user, if any.
    Reads subscriptions directly — v_my_plan doesn't surface stripe_customer_id.
    """
    user = get_current_user()
    if not user:
        return None

    sb = get_client()
    # No try/except: we want a real error to surface in the UI rather than
    # collapsing to the misleading "no billing account" message. No
    # `.not_.is_(...)` filter either — we post-filter in Python so the
    # diagnostic is precise if the column is somehow unset.
    resp = (
        sb.table("subscriptions")
          .select("stripe_customer_id, source, status, created_at")
          .eq("owner_user_id", user.id)
          .order("created_at", desc=True)
          .limit(5)
          .execute()
    )
    rows = resp.data or []

    # Prefer an active Stripe row; fall back to any row with a customer id.
    for r in rows:
        if r.get("source") == "stripe" and r.get("stripe_customer_id"):
            return r["stripe_customer_id"]
    for r in rows:
        cid = r.get("stripe_customer_id")
        if cid:
            return cid
    return None


# --------------------------------------------------------------------
#  Checkout
# --------------------------------------------------------------------
def create_checkout_session(
    *,
    plan_id: str,
    interval: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Build a Stripe Checkout session for the given plan + interval and
    return the hosted URL. The caller redirects the browser there.

    Raises:
        ValueError — any of: not signed in / unknown plan / missing
        price id / Stripe API error. The UI is expected to show the
        message text directly.
    """
    if not _current_user_email():
        raise ValueError("Please sign in first to upgrade.")

    price_id = stripe_price_id(plan_id, interval)
    if not price_id:
        raise ValueError(
            f"This plan isn't available for checkout yet — the Stripe "
            f"price ID for {plan_id}/{interval} hasn't been configured. "
            f"Run stripe_setup.py and paste the IDs into secrets.toml."
        )

    stripe = _stripe_module()
    user = get_current_user()
    user_id = getattr(user, "id", None)
    email = _current_user_email()

    # Use an existing customer if we have one (so card on file / past
    # invoices stay linked); otherwise let Stripe mint one automatically
    # from customer_email (in subscription mode customer creation is
    # automatic — no explicit `customer_creation` flag needed).
    existing_customer = _existing_stripe_customer_id()

    kwargs: dict = {
        "mode":                "subscription",
        "line_items":          [{"price": price_id, "quantity": 1}],
        "success_url":         success_url,
        "cancel_url":          cancel_url,
        "allow_promotion_codes": True,
        # We carry the Supabase user id + the plan id all the way to
        # the webhook so it can write the right subscriptions row.
        "client_reference_id": user_id,
        "metadata": {
            "bl_user_id":   user_id or "",
            "bl_plan_id":   plan_id,
            "bl_interval":  interval,
        },
        "subscription_data": {
            "metadata": {
                "bl_user_id":  user_id or "",
                "bl_plan_id":  plan_id,
                "bl_interval": interval,
            },
        },
    }
    if existing_customer:
        kwargs["customer"] = existing_customer
    elif email:
        kwargs["customer_email"] = email

    try:
        session = stripe.checkout.Session.create(**kwargs)
    except Exception as exc:
        raise ValueError(f"Couldn't start checkout: {exc}") from exc

    if not session.url:
        raise ValueError("Stripe didn't return a checkout URL — please try again.")
    return session.url


# --------------------------------------------------------------------
#  Customer Portal
# --------------------------------------------------------------------
def create_portal_session(*, return_url: str) -> str:
    """
    Build a Stripe Customer Portal session for the current user and
    return the hosted URL. The Portal lets them update card, change
    plan, cancel, view invoices — all without us building that UI.

    Raises:
        ValueError — same convention as create_checkout_session.
    """
    if not _current_user_email():
        raise ValueError("Please sign in first.")

    customer_id = _existing_stripe_customer_id()
    if not customer_id:
        raise ValueError(
            "You don't have a billing account yet. Pick a plan on the "
            "pricing page to get started."
        )

    stripe = _stripe_module()
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
    except Exception as exc:
        raise ValueError(f"Couldn't open the billing portal: {exc}") from exc

    if not session.url:
        raise ValueError("Stripe didn't return a portal URL — please try again.")
    return session.url


__all__ = [
    "create_checkout_session",
    "create_portal_session",
]
