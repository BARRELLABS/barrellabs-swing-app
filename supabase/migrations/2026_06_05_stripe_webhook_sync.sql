-- ============================================================
--  Stripe webhook -> subscriptions sync RPC. Date: 2026-06-05
--  Called ONLY by the stripe-webhook Edge Function (service role).
--  Schema VERIFIED live via Supabase MCP (project xionpyhapspecsrjregt).
--
--  Key facts that shape this RPC:
--   * v_my_plan resolves a user's plan THROUGH a subscription_seats row whose
--     subscription.status is active/trialing/past_due/comp. So writing a
--     subscriptions row is NOT enough — the OWNER SEAT must exist too, or a
--     paid checkout unlocks nothing. (Mirrors redeem_beta_code's owner seat.)
--   * Cancel just needs status='canceled' — the view's status filter drops it
--     to Free automatically (no need to rewrite plan_id).
--   * Upsert key = stripe_subscription_id (UNIQUE). owner_user_id has only a
--     PARTIAL unique (one ACTIVE sub per owner) so it's not a safe conflict key.
-- ============================================================

CREATE OR REPLACE FUNCTION public.apply_stripe_subscription(
  p_user_id                uuid,
  p_plan_id                text,
  p_status                 text,
  p_billing_interval       text,
  p_stripe_customer_id     text,
  p_stripe_subscription_id text,
  p_current_period_start   timestamptz,
  p_current_period_end     timestamptz,
  p_cancel_at_period_end   boolean
) RETURNS void AS $$
DECLARE
  v_sub_id uuid;
  v_canceled_at timestamptz := CASE WHEN p_status = 'canceled' THEN now() ELSE NULL END;
BEGIN
  IF p_user_id IS NULL THEN
    RAISE EXCEPTION 'apply_stripe_subscription: user_id required';
  END IF;
  IF p_stripe_subscription_id IS NULL THEN
    RAISE EXCEPTION 'apply_stripe_subscription: stripe_subscription_id required';
  END IF;

  -- Upsert the subscription keyed on the unique stripe_subscription_id.
  INSERT INTO public.subscriptions (
    owner_user_id, plan_id, status, billing_interval, source,
    stripe_customer_id, stripe_subscription_id,
    current_period_start, current_period_end, cancel_at_period_end, canceled_at
  ) VALUES (
    p_user_id, COALESCE(p_plan_id, 'free'), p_status, p_billing_interval, 'stripe',
    p_stripe_customer_id, p_stripe_subscription_id,
    p_current_period_start, p_current_period_end, COALESCE(p_cancel_at_period_end, false), v_canceled_at
  )
  ON CONFLICT (stripe_subscription_id) DO UPDATE SET
    plan_id              = COALESCE(EXCLUDED.plan_id, public.subscriptions.plan_id),
    status               = EXCLUDED.status,
    billing_interval     = COALESCE(EXCLUDED.billing_interval, public.subscriptions.billing_interval),
    stripe_customer_id   = COALESCE(EXCLUDED.stripe_customer_id, public.subscriptions.stripe_customer_id),
    current_period_start = EXCLUDED.current_period_start,
    current_period_end   = EXCLUDED.current_period_end,
    cancel_at_period_end = EXCLUDED.cancel_at_period_end,
    canceled_at          = COALESCE(EXCLUDED.canceled_at, public.subscriptions.canceled_at),
    updated_at           = now()
  RETURNING id INTO v_sub_id;

  -- Ensure the OWNER SEAT exists while the sub is live (v_my_plan needs it).
  -- Idempotent: subscription_seats has a (subscription_id, user_id) unique idx.
  IF p_status IN ('active', 'trialing', 'past_due', 'comp') THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.subscription_seats
       WHERE subscription_id = v_sub_id AND user_id = p_user_id
    ) THEN
      INSERT INTO public.subscription_seats (subscription_id, user_id, role, accepted_at)
      VALUES (v_sub_id, p_user_id, 'owner', now());
    END IF;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Only the service role (Edge Function) may call this — never anon/authenticated.
REVOKE EXECUTE ON FUNCTION public.apply_stripe_subscription(uuid,text,text,text,text,text,timestamptz,timestamptz,boolean) FROM anon, authenticated, public;
GRANT  EXECUTE ON FUNCTION public.apply_stripe_subscription(uuid,text,text,text,text,text,timestamptz,timestamptz,boolean) TO service_role;
