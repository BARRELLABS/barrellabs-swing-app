-- ============================================================
--  Stripe webhook -> subscriptions sync RPC. Date: 2026-06-05
--  Called ONLY by the stripe-webhook Edge Function (service role).
--  All schema coupling for the webhook lives here, next to the table.
--
--  ⚠ NOT YET APPLIED. Apply via the Supabase MCP / SQL editor after
--    CONFIRMING the column names below match the live `subscriptions`
--    table (it was created by hand, not in migration history). If a
--    column differs, change it here only — the Edge Function is generic.
--
--  Assumed `public.subscriptions` columns (CONFIRM THESE):
--    owner_user_id            uuid     (the Supabase auth user)
--    plan_id                  text     (free|solo_pro|family_pro|coach_pro)
--    status                   text     (active|trialing|past_due|canceled)
--    stripe_customer_id       text
--    stripe_subscription_id   text
--    current_period_end       timestamptz
--    cancel_at_period_end     boolean
--    updated_at               timestamptz   (optional)
-- ============================================================

CREATE OR REPLACE FUNCTION public.apply_stripe_subscription(
  p_user_id                uuid,
  p_plan_id                text,
  p_status                 text,
  p_stripe_customer_id     text,
  p_stripe_subscription_id text,
  p_current_period_end     timestamptz,
  p_cancel_at_period_end   boolean
) RETURNS void AS $$
DECLARE
  v_plan text := p_plan_id;
BEGIN
  IF p_user_id IS NULL THEN
    RAISE EXCEPTION 'apply_stripe_subscription: user_id required';
  END IF;

  -- On a fully-canceled subscription, downgrade to free so the user loses Pro
  -- regardless of whether v_my_plan filters on status. (past_due keeps the plan
  -- during Stripe's smart-retry grace window — only `deleted` sends 'canceled'.)
  IF p_status = 'canceled' THEN
    v_plan := 'free';
  END IF;

  -- Upsert the owner's single subscription row WITHOUT relying on a specific
  -- unique constraint (the table was hand-created; constraints are unknown).
  UPDATE public.subscriptions
     SET plan_id                = COALESCE(v_plan, plan_id),
         status                 = p_status,
         stripe_customer_id     = COALESCE(p_stripe_customer_id, stripe_customer_id),
         stripe_subscription_id = COALESCE(p_stripe_subscription_id, stripe_subscription_id),
         current_period_end     = p_current_period_end,
         cancel_at_period_end   = COALESCE(p_cancel_at_period_end, false),
         updated_at             = now()
   WHERE owner_user_id = p_user_id;

  IF NOT FOUND THEN
    INSERT INTO public.subscriptions (
      owner_user_id, plan_id, status, stripe_customer_id,
      stripe_subscription_id, current_period_end, cancel_at_period_end
    ) VALUES (
      p_user_id, COALESCE(v_plan, 'free'), p_status, p_stripe_customer_id,
      p_stripe_subscription_id, p_current_period_end, COALESCE(p_cancel_at_period_end, false)
    );
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Only the service role (Edge Function) may call this — never anon/authenticated.
REVOKE EXECUTE ON FUNCTION public.apply_stripe_subscription(uuid,text,text,text,text,timestamptz,boolean) FROM anon, authenticated, public;
GRANT  EXECUTE ON FUNCTION public.apply_stripe_subscription(uuid,text,text,text,text,timestamptz,boolean) TO service_role;
