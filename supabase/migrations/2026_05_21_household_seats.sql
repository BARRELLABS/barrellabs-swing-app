-- ============================================================
--  Household / Family Pro — built on the EXISTING seat model
--  Date: 2026-05-21
--  Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
--
--  IMPORTANT: the database already models seats correctly:
--    subscriptions      = the household container (owner_user_id, plan_id)
--    subscription_seats = the members (subscription_id, user_id, invite_*,
--                         accepted_at, role)
--    v_my_plan          = ALREADY resolves a member's plan through their
--                         seat → so Family Pro entitlement propagation
--                         needs ZERO new code.
--    plans.seats        = seat cap per plan (free=1, solo=1, family=4,
--                         coach=20)
--
--  So this migration does NOT create families/family_members. It only:
--    1. Adds the few columns the dashboard + invite flow need.
--    2. Adds an owner-only invite RPC that enforces the seat cap from
--       plans.seats under a row lock (closes the over-invite TOCTOU).
--    3. Adds a claim RPC the invitee calls to accept their seat.
--  Everything is additive + idempotent.
-- ============================================================

-- 1. Columns the household dashboard + invite flow need ----------------
ALTER TABLE public.subscription_seats
  ADD COLUMN IF NOT EXISTS display_name      text,
  ADD COLUMN IF NOT EXISTS is_minor          boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS invite_token_hash text,
  ADD COLUMN IF NOT EXISTS removed_at        timestamptz;

CREATE INDEX IF NOT EXISTS subscription_seats_token_hash_idx
  ON public.subscription_seats(invite_token_hash)
  WHERE invite_token_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS subscription_seats_sub_active_idx
  ON public.subscription_seats(subscription_id)
  WHERE removed_at IS NULL;


-- 2. invite_subscription_seat ----------------------------------------
--  Owner-only. Seat cap read from plans.seats. Subscription row locked
--  FOR UPDATE so two concurrent invites can't both pass the count.
--  SECURITY DEFINER so it can insert past the (owner-scoped) RLS write
--  policy while still enforcing ownership itself.
CREATE OR REPLACE FUNCTION public.invite_subscription_seat(
  p_subscription_id uuid,
  p_email           text,
  p_is_minor        boolean DEFAULT false,
  p_display_name    text    DEFAULT NULL,
  p_token_hash      text    DEFAULT NULL
) RETURNS public.subscription_seats AS $$
DECLARE
  v_owner  uuid;
  v_plan   text;
  v_max    integer;
  v_active integer;
  result   public.subscription_seats%ROWTYPE;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'invite_subscription_seat: not authenticated';
  END IF;
  IF p_email IS NULL OR position('@' in p_email) = 0 THEN
    RAISE EXCEPTION 'invite_subscription_seat: invalid email';
  END IF;

  -- Lock the subscription row to serialize seat-cap checks.
  SELECT s.owner_user_id, s.plan_id INTO v_owner, v_plan
    FROM public.subscriptions s
   WHERE s.id = p_subscription_id
   FOR UPDATE;

  IF v_owner IS NULL OR v_owner <> auth.uid() THEN
    RAISE EXCEPTION 'invite_subscription_seat: caller is not the subscription owner';
  END IF;

  SELECT seats INTO v_max FROM public.plans WHERE id = v_plan;
  v_max := COALESCE(v_max, 1);

  -- All non-removed seats (incl. owner + pending invites) count against cap.
  SELECT count(*) INTO v_active
    FROM public.subscription_seats
   WHERE subscription_id = p_subscription_id
     AND removed_at IS NULL;

  IF v_active >= v_max THEN
    RAISE EXCEPTION 'invite_subscription_seat: all % seats are in use', v_max;
  END IF;

  INSERT INTO public.subscription_seats
    (subscription_id, invite_email, invite_token_hash, role, is_minor,
     display_name, invited_at)
  VALUES
    (p_subscription_id, lower(p_email), p_token_hash,
     CASE WHEN p_is_minor THEN 'child' ELSE 'member' END,
     p_is_minor, LEFT(trim(coalesce(p_display_name, '')), 60), now())
  RETURNING * INTO result;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;


-- 3. claim_subscription_seat -----------------------------------------
--  The invitee calls this with sha256(token). Enforces 30-day expiry +
--  seat cap in SQL, atomically under a row lock. SECURITY DEFINER so the
--  invitee (not yet a seat member) can flip their own pending row.
CREATE OR REPLACE FUNCTION public.claim_subscription_seat(
  p_token_hash text
) RETURNS uuid AS $$
DECLARE
  v_row  public.subscription_seats%ROWTYPE;
  v_plan text;
  v_max  integer;
  v_active integer;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'claim_subscription_seat: not authenticated';
  END IF;

  SELECT * INTO v_row
    FROM public.subscription_seats
   WHERE invite_token_hash = p_token_hash
     AND accepted_at IS NULL
     AND removed_at IS NULL
     AND invited_at > now() - interval '30 days'
   FOR UPDATE;

  IF v_row.id IS NULL THEN
    RAISE EXCEPTION 'claim_subscription_seat: invalid or expired invite';
  END IF;

  -- Seat cap recheck (a seat could have filled between invite + claim).
  SELECT s.plan_id INTO v_plan
    FROM public.subscriptions s WHERE s.id = v_row.subscription_id;
  SELECT seats INTO v_max FROM public.plans WHERE id = v_plan;
  v_max := COALESCE(v_max, 1);

  SELECT count(*) INTO v_active
    FROM public.subscription_seats
   WHERE subscription_id = v_row.subscription_id
     AND removed_at IS NULL
     AND accepted_at IS NOT NULL;

  IF v_active >= v_max THEN
    RAISE EXCEPTION 'claim_subscription_seat: household is full';
  END IF;

  UPDATE public.subscription_seats
     SET user_id           = auth.uid(),
         accepted_at       = now(),
         invite_token      = NULL,
         invite_token_hash = NULL
   WHERE id = v_row.id;

  RETURN v_row.subscription_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;


-- 4. Grants -----------------------------------------------------------
GRANT EXECUTE ON FUNCTION public.invite_subscription_seat TO authenticated;
GRANT EXECUTE ON FUNCTION public.claim_subscription_seat  TO authenticated;
