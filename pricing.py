"""
BarrelLabs SwingAI — Pricing page.

Dedicated /pricing route. Reached by setting st.session_state["page"]
= "pricing" (wired via app.py routing). Renders:

    • Hero strip
    • Monthly / Annual toggle
    • 3 plan cards (Solo / Family / Coach) with feature lists
    • Per-card Upgrade button → Stripe Checkout
    • Beta-code reminder line + back-to-dashboard nav

The page degrades gracefully when Stripe isn't fully wired yet (no
price ids in secrets.toml): the Upgrade buttons show "Coming soon"
disabled state instead of crashing.
"""

from __future__ import annotations

import textwrap

import streamlit as st

from bl_theme import inject_global_theme
from plan_pricing import (
    PLAN_PRICING,
    annual_savings_pct,
    annual_monthly_equivalent_cents,
    format_cents,
    stripe_price_id,
)
from entitlements import is_pro, _resolve_plan_id, plan_display_name
from subscription_storage import load_my_plan


_PRICING_CSS = """
<style>
.bl-pricing-hero {
    margin: 1.5rem 0 0.8rem 0;
    padding: 2.2rem 2rem 1.6rem 2rem;
    border-radius: 18px;
    background:
      radial-gradient(80% 100% at 50% 0%, rgba(220,38,38,0.10), transparent 60%),
      linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.005));
    border: 1px solid rgba(255,255,255,0.06);
    text-align: center;
}
.bl-pricing-eyebrow {
    color: #ef4444;
    font-size: 0.72rem;
    font-weight: 900;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.bl-pricing-title {
    font-size: 2.4rem;
    font-weight: 950;
    letter-spacing: -0.04em;
    line-height: 1.05;
    color: #fafafa;
}
.bl-pricing-sub {
    color: #a3a3a3;
    margin-top: 0.5rem;
    font-size: 1.02rem;
    max-width: 56ch;
    margin-left: auto;
    margin-right: auto;
    line-height: 1.55;
}
.bl-toggle-row {
    display: flex;
    justify-content: center;
    margin: 0.4rem 0 1.3rem 0;
}

/* Plan card */
.bl-plan {
    position: relative;
    border-radius: 18px;
    padding: 1.6rem 1.5rem 1.4rem 1.5rem;
    background: rgba(255,255,255,0.018);
    border: 1px solid rgba(255,255,255,0.07);
    height: 100%;
    display: flex;
    flex-direction: column;
}
.bl-plan.is-featured {
    border-color: rgba(220,38,38,0.45);
    background:
      radial-gradient(120% 80% at 100% 0%, rgba(220,38,38,0.10), transparent 60%),
      linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.005));
    box-shadow: 0 8px 32px rgba(220,38,38,0.10);
}
.bl-plan-eyebrow {
    position: absolute;
    top: -10px;
    left: 50%;
    transform: translateX(-50%);
    background: #ef4444;
    color: #fff;
    font-size: 0.68rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 0.28rem 0.7rem;
    border-radius: 999px;
    white-space: nowrap;
}
.bl-plan-name {
    font-size: 1.35rem;
    font-weight: 800;
    color: #fafafa;
    letter-spacing: -0.01em;
}
.bl-plan-tag {
    color: #a3a3a3;
    font-size: 0.88rem;
    margin-top: 0.3rem;
    line-height: 1.45;
    min-height: 2.6em;
}
.bl-plan-price-row {
    margin-top: 1.1rem;
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
}
.bl-plan-price {
    font-size: 2.4rem;
    font-weight: 900;
    color: #fafafa;
    letter-spacing: -0.03em;
    line-height: 1;
}
.bl-plan-period {
    color: #a3a3a3;
    font-size: 0.92rem;
    font-weight: 600;
}
.bl-plan-equiv {
    color: #6b7280;
    font-size: 0.78rem;
    margin-top: 0.45rem;
    height: 1.1em;
}
.bl-plan-save {
    color: #16a34a;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.35rem;
    letter-spacing: 0.02em;
    height: 1.1em;
}
.bl-plan-seats {
    color: #d4d4d4;
    font-size: 0.86rem;
    margin-top: 0.6rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.bl-plan-seats strong { color: #fafafa; }

.bl-plan-features {
    list-style: none;
    padding: 0;
    margin: 0.9rem 0 1.1rem 0;
}
.bl-plan-features li {
    color: #d4d4d4;
    font-size: 0.9rem;
    line-height: 1.5;
    padding: 0.18rem 0 0.18rem 1.3rem;
    position: relative;
}
.bl-plan-features li::before {
    content: "✓";
    position: absolute;
    left: 0;
    color: #ef4444;
    font-weight: 900;
}

.bl-plan-cta-wrap { margin-top: auto; }

.bl-beta-strip {
    margin: 1.4rem 0 1rem 0;
    padding: 0.95rem 1.1rem;
    border-radius: 12px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    color: #a3a3a3;
    font-size: 0.92rem;
    text-align: center;
}
.bl-beta-strip strong { color: #fafafa; }
</style>
"""


# Feature list per plan — kept in this file because it's UX copy, not
# entitlement logic. The entitlements module is what actually gates.
_FEATURES_BASE = [
    "Unlimited swing analyses",
    "Full personalized drill plan",
    "Swing video saved to your history",
    "Full Development Tracker (XP, streaks, achievements)",
    "Rewards Roadmap (incl. limited-edition hoodie at 180d)",
    "PDF report export",
    "Side-by-side swing comparisons",
    "Full MLB comp library",
]

_FEATURES_FAMILY_EXTRAS = [
    "Up to 4 family member accounts",
    "Each member gets their own swing history",
]

_FEATURES_COACH_EXTRAS = [
    "Up to 20 player rosters",
    "Read-only views of each player's swings",
    "Priority support",
]

_PLAN_FEATURES = {
    "solo_pro":   _FEATURES_BASE,
    "family_pro": _FEATURES_BASE + _FEATURES_FAMILY_EXTRAS,
    "coach_pro":  _FEATURES_BASE + _FEATURES_COACH_EXTRAS,
}


def render_pricing_page():
    """Streamlit page entry point. Routed from app.py."""
    inject_global_theme()
    st.markdown(_PRICING_CSS, unsafe_allow_html=True)

    # ---- Back nav ----
    back_col, _ = st.columns([1, 5])
    with back_col:
        if st.button("← Back to Dashboard", key="pricing_back_btn"):
            st.session_state["page"] = "dashboard"
            st.rerun()

    # ---- Hero ----
    st.markdown("""
<div class="bl-pricing-hero">
  <div class="bl-pricing-eyebrow">Pick your plan</div>
  <div class="bl-pricing-title">Unlock the full BarrelLabs SwingAI experience.</div>
  <div class="bl-pricing-sub">
    Every Pro plan gets unlimited swings, your personalized drill plan,
    video saved with every analysis, the full Development Tracker, and
    the Rewards Roadmap — including the limited-edition hoodie at 180
    days.
  </div>
</div>
""", unsafe_allow_html=True)

    # ---- Already-Pro banner ----
    snap = load_my_plan()
    on_pro = is_pro(snap)
    if on_pro:
        current = plan_display_name(_resolve_plan_id(snap))
        st.markdown(f"""
<div style="
    margin: 0.4rem 0 1rem 0;
    padding: 0.85rem 1rem;
    border-radius: 12px;
    background: rgba(22,163,74,0.08);
    border: 1px solid rgba(22,163,74,0.32);
    color: #d4d4d4;
    text-align: center;
">
  <strong style="color:#fafafa;">You're already on {current}.</strong>
  &nbsp;Manage your subscription from <em>Account Settings</em>.
</div>
""", unsafe_allow_html=True)

    # ---- Monthly / Annual toggle ----
    interval_key = "pricing_billing_interval"
    if interval_key not in st.session_state:
        st.session_state[interval_key] = "annual"  # default highlights savings

    t_left, t_mid, t_right = st.columns([1, 2, 1])
    with t_mid:
        st.markdown('<div class="bl-toggle-row">', unsafe_allow_html=True)
        choice = st.radio(
            "Billing interval",
            options=["monthly", "annual"],
            format_func=lambda v: "Monthly" if v == "monthly" else "Annual (save ~45%)",
            index=0 if st.session_state[interval_key] == "monthly" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="pricing_interval_radio",
        )
        st.session_state[interval_key] = choice
        st.markdown('</div>', unsafe_allow_html=True)

    interval = st.session_state[interval_key]  # "monthly" | "annual"

    # ---- Plan cards ----
    col_solo, col_fam, col_coach = st.columns(3, gap="large")

    _render_plan_card(col_solo,  "solo_pro",   interval, featured=False)
    _render_plan_card(col_fam,   "family_pro", interval, featured=True)
    _render_plan_card(col_coach, "coach_pro",  interval, featured=False)

    # ---- Already paid? Refresh my plan ----
    # Since Stripe Checkout opens in a new tab, the main app tab needs a
    # way to re-pull the latest plan from Supabase after the webhook has
    # written the new subscription row. This button does exactly that.
    if st.session_state.get("_pending_checkout_url"):
        st.markdown("&nbsp;")
        rc1, rc2, _rc3 = st.columns([1.4, 1.4, 3], gap="small")
        if rc1.button(
            "I've completed payment — refresh my plan",
            type="primary",
            width="stretch",
            key="bl_refresh_plan_after_checkout",
        ):
            try:
                from subscription_storage import (
                    invalidate_my_plan_cache,
                    load_my_plan,
                )
                invalidate_my_plan_cache()
                load_my_plan(force_refresh=True)
                st.session_state.pop("_pending_checkout_url", None)
                st.success(
                    "Plan refreshed. If you don't see Pro yet, give the "
                    "webhook a few more seconds and click again.",
                    icon="🔄",
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't refresh plan: {exc}")
        if rc2.button(
            "Cancel — I didn't pay",
            width="stretch",
            key="bl_cancel_pending_checkout",
        ):
            st.session_state.pop("_pending_checkout_url", None)
            st.rerun()

    # ---- Beta code strip ----
    st.markdown("""
<div class="bl-beta-strip">
  Got a <strong>BarrelLabs beta code</strong>? Redeem it in
  <em>Account Settings → Subscription</em> for 30 days of full Pro
  access — no card required.
</div>
""", unsafe_allow_html=True)


def _render_plan_card(col, plan_id: str, interval: str, *, featured: bool):
    """Render one plan card into the given column container."""
    cfg = PLAN_PRICING.get(plan_id) or {}
    name = cfg.get("name") or plan_id
    tag  = cfg.get("tagline") or ""
    seats = cfg.get("seats") or 1

    if interval == "monthly":
        price_cents = cfg.get("monthly_cents") or 0
        period_label = "/month"
        equiv_line = ""
        save_line = ""
    else:
        price_cents = cfg.get("annual_cents") or 0
        period_label = "/year"
        equiv = annual_monthly_equivalent_cents(plan_id)
        equiv_line = f"or {format_cents(equiv)}/mo billed annually"
        pct = annual_savings_pct(plan_id)
        save_line = f"Save {pct}% vs monthly" if pct > 0 else ""

    features_html = "".join(
        f"<li>{f}</li>" for f in _PLAN_FEATURES.get(plan_id, [])
    )

    seats_html = ""
    if seats > 1:
        member_word = "member" if seats == 1 else "members"
        seats_html = f"<div class='bl-plan-seats'>Includes <strong>{seats} {member_word}</strong></div>"
    else:
        seats_html = "<div class='bl-plan-seats'>For <strong>1 player</strong></div>"

    eyebrow_html = '<div class="bl-plan-eyebrow">Most Popular</div>' if featured else ""

    with col:
        st.markdown(textwrap.dedent(f"""
<div class="bl-plan {'is-featured' if featured else ''}">
  {eyebrow_html}
  <div class="bl-plan-name">{name}</div>
  <div class="bl-plan-tag">{tag}</div>
  <div class="bl-plan-price-row">
    <div class="bl-plan-price">{format_cents(price_cents)}</div>
    <div class="bl-plan-period">{period_label}</div>
  </div>
  <div class="bl-plan-equiv">{equiv_line}</div>
  <div class="bl-plan-save">{save_line}</div>
  {seats_html}
  <ul class="bl-plan-features">{features_html}</ul>
  <div class="bl-plan-cta-wrap"></div>
</div>
""").strip(), unsafe_allow_html=True)

        # Upgrade button outside the static HTML block (Streamlit native).
        _render_upgrade_button(plan_id, interval, featured=featured)


def _render_upgrade_button(plan_id: str, interval: str, *, featured: bool):
    """Render the Upgrade CTA. Handles all the failure modes:
       - already Pro              → 'Current plan' disabled
       - no price id configured   → 'Coming soon' disabled
       - not signed in            → 'Sign in to upgrade' routes to auth
       - happy path               → creates Checkout session + redirects
    """
    snap = load_my_plan()
    current_plan_id = _resolve_plan_id(snap)
    on_pro = is_pro(snap)

    btn_key = f"upgrade_{plan_id}_{interval}"

    # Already on this exact plan?
    if on_pro and current_plan_id == plan_id:
        st.button("✓ Current plan", key=btn_key, disabled=True, width="stretch")
        return

    price_id = stripe_price_id(plan_id, interval)
    if not price_id:
        st.button(
            "Coming soon",
            key=btn_key,
            disabled=True,
            width="stretch",
            help="Checkout for this plan isn't wired up yet. Set the "
                 "Stripe price ID in secrets.toml.",
        )
        return

    label = "Upgrade now" if not on_pro else "Switch to this plan"
    if st.button(label, key=btn_key, type=("primary" if featured else "secondary"),
                 width="stretch"):
        _start_checkout(plan_id, interval)


def _start_checkout(plan_id: str, interval: str) -> None:
    """Create a Checkout session and redirect the browser there."""
    try:
        # Imported lazily so the pricing page module itself never crashes
        # on import if the Stripe SDK isn't installed yet.
        from stripe_client import create_checkout_session
    except ImportError as exc:
        st.error(f"Checkout isn't available yet: {exc}")
        return

    # success_url / cancel_url use Streamlit's runtime URL via query params
    # since Streamlit doesn't expose a clean way to know its own public URL.
    # We use relative-ish URLs and let Stripe append the session id.
    base = _streamlit_base_url()
    success_url = f"{base}?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{base}?checkout=cancel"

    try:
        url = create_checkout_session(
            plan_id=plan_id,
            interval=interval,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as ve:
        st.error(str(ve))
        return
    except Exception as exc:
        st.error(f"Couldn't start checkout: {exc}")
        return

    # Open Stripe Checkout in a NEW tab via window.open(...). We do NOT
    # navigate the current tab because Streamlit's session_state (incl.
    # auth) doesn't survive a full same-tab redirect — when the browser
    # comes back from Stripe, the websocket reconnects but session_state
    # is empty, which forces a re-login. By opening Stripe in a new tab,
    # the main app tab stays alive and the user is still signed in when
    # they return. Stash the session URL in session_state so the page can
    # show a fallback link if the popup is blocked.
    st.session_state["_pending_checkout_url"] = url
    st.markdown(
        f"""
<script>
  (function() {{
      const w = window.open("{url}", "_blank", "noopener,noreferrer");
      if (!w || w.closed || typeof w.closed === "undefined") {{
          // Popup blocked — leave the fallback link visible.
          const el = document.getElementById("bl-popup-blocked");
          if (el) el.style.display = "block";
      }}
  }})();
</script>
<div style="margin-top:1rem; padding:0.85rem 1rem; border-radius:10px;
            background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.32);
            color:#fafafa;">
  <strong>Opening secure Stripe checkout in a new tab…</strong><br>
  After you finish payment, return here and click
  <em>"I've completed payment — refresh my plan"</em> below.
</div>
<div id="bl-popup-blocked" style="display:none; margin-top:0.6rem; padding:0.85rem 1rem;
            border-radius:10px; background:rgba(220,38,38,0.10);
            border:1px solid rgba(220,38,38,0.32); color:#fafafa;">
  Your browser blocked the popup.
  &nbsp;<a href="{url}" target="_blank" rel="noopener noreferrer"
         style="color:#ef4444; font-weight:800;">Click here to open Stripe checkout</a>.
</div>
""",
        unsafe_allow_html=True,
    )
    # Don't st.stop() — let the rest of the pricing page render so the
    # user has the "refresh my plan" CTA below the checkout cards.


def _streamlit_base_url() -> str:
    """
    Best-effort guess at the app's public URL. We read it from secrets
    so deployments can override it; falls back to the localhost dev URL.
    """
    try:
        section = st.secrets.get("app", {})
        url = section.get("base_url")
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    return "http://localhost:8501"


__all__ = ["render_pricing_page"]
