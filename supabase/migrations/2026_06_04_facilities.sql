-- ============================================================
--  Facility / Academy: an org that players LINK to via a join code.
--  Players keep owning their own accounts/data; the facility
--  SPONSORS Pro for every active member. Date: 2026-06-04
--  Spec: docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md
--  Plan: docs/superpowers/plans/2026-06-04-facility-coach-mode.md
--
--  ⚠ NOT YET APPLIED TO PROD. Logan applies this after review.
-- ============================================================

-- 1. Facilities. owner_user_id is the coach's auth user.
CREATE TABLE IF NOT EXISTS public.facilities (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id  uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name           text NOT NULL,
  logo_url       text,
  join_code      text NOT NULL UNIQUE,
  plan_tier      text NOT NULL DEFAULT 'academy',   -- team|academy|academy_plus|facility|facility_pro
  roster_ceiling integer NOT NULL DEFAULT 100,
  billing_mode   text NOT NULL DEFAULT 'license',   -- license | revshare
  status         text NOT NULL DEFAULT 'active',    -- active|trialing|past_due|canceled
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS facilities_owner_idx ON public.facilities(owner_user_id);

-- 2. Membership link: a player (by players.id) belongs to a facility.
--    The player owns their account/data; the facility gets read access.
CREATE TABLE IF NOT EXISTS public.facility_members (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id uuid NOT NULL REFERENCES public.facilities(id) ON DELETE CASCADE,
  player_id   uuid NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
  joined_at   timestamptz NOT NULL DEFAULT now(),
  left_at     timestamptz,                          -- soft-leave (portability)
  UNIQUE (facility_id, player_id)
);
CREATE INDEX IF NOT EXISTS facility_members_facility_idx
  ON public.facility_members(facility_id) WHERE left_at IS NULL;
CREATE INDEX IF NOT EXISTS facility_members_player_idx
  ON public.facility_members(player_id) WHERE left_at IS NULL;

-- 3. RLS
ALTER TABLE public.facilities       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facility_members ENABLE ROW LEVEL SECURITY;

-- Coach sees/edits their own facility.
DROP POLICY IF EXISTS facilities_owner ON public.facilities;
CREATE POLICY facilities_owner ON public.facilities
  FOR ALL USING (owner_user_id = auth.uid()) WITH CHECK (owner_user_id = auth.uid());

-- Coach sees members of facilities they own; a player sees their own membership.
DROP POLICY IF EXISTS facility_members_visibility ON public.facility_members;
CREATE POLICY facility_members_visibility ON public.facility_members
  FOR SELECT USING (
    facility_id IN (SELECT id FROM public.facilities WHERE owner_user_id = auth.uid())
    OR player_id IN (SELECT id FROM public.players WHERE user_id = auth.uid())
  );

-- ============================================================
--  RPCs (SECURITY DEFINER — same pattern as create_household_player)
-- ============================================================

-- create_facility: coach creates their org, gets a unique join code.
CREATE OR REPLACE FUNCTION public.create_facility(
  p_name         text,
  p_tier         text    DEFAULT 'academy',
  p_ceiling      integer DEFAULT 100,
  p_billing_mode text    DEFAULT 'license'
) RETURNS public.facilities AS $$
DECLARE
  v_uid  uuid := auth.uid();
  v_code text;
  result public.facilities%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'create_facility: not authenticated'; END IF;
  IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
    RAISE EXCEPTION 'create_facility: name required';
  END IF;
  IF p_billing_mode NOT IN ('license','revshare') THEN
    RAISE EXCEPTION 'create_facility: billing_mode must be license or revshare';
  END IF;
  -- 6-char uppercase code, retry on collision.
  LOOP
    v_code := upper(substr(md5(gen_random_uuid()::text), 1, 6));
    EXIT WHEN NOT EXISTS (SELECT 1 FROM public.facilities WHERE join_code = v_code);
  END LOOP;
  INSERT INTO public.facilities (owner_user_id, name, join_code, plan_tier, roster_ceiling, billing_mode)
  VALUES (v_uid, trim(p_name), v_code, p_tier, p_ceiling, p_billing_mode)
  RETURNING * INTO result;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- join_facility_by_code: link one of the caller's players to a facility.
CREATE OR REPLACE FUNCTION public.join_facility_by_code(
  p_code text, p_player_id uuid
) RETURNS public.facility_members AS $$
DECLARE
  v_uid    uuid := auth.uid();
  v_fac    public.facilities%ROWTYPE;
  v_active integer;
  result   public.facility_members%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'join_facility: not authenticated'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.players WHERE id = p_player_id AND user_id = v_uid) THEN
    RAISE EXCEPTION 'join_facility: player not owned by caller';
  END IF;
  SELECT * INTO v_fac FROM public.facilities WHERE join_code = upper(trim(p_code));
  IF NOT FOUND THEN RAISE EXCEPTION 'join_facility: invalid code'; END IF;
  -- Lock the facility's member rows so two concurrent joins can't both pass the cap.
  PERFORM 1 FROM public.facility_members
   WHERE facility_id = v_fac.id AND left_at IS NULL FOR UPDATE;
  SELECT count(*) INTO v_active FROM public.facility_members
   WHERE facility_id = v_fac.id AND left_at IS NULL;
  IF v_active >= v_fac.roster_ceiling THEN
    RAISE EXCEPTION 'join_facility: facility roster is full (% of %)', v_active, v_fac.roster_ceiling;
  END IF;
  INSERT INTO public.facility_members (facility_id, player_id)
  VALUES (v_fac.id, p_player_id)
  ON CONFLICT (facility_id, player_id)
  DO UPDATE SET left_at = NULL
  RETURNING * INTO result;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- leave_facility: soft-leave. Sponsorship ends; player keeps account + history.
CREATE OR REPLACE FUNCTION public.leave_facility(p_member_id uuid)
RETURNS void AS $$
DECLARE v_uid uuid := auth.uid();
BEGIN
  UPDATE public.facility_members fm
     SET left_at = now()
   WHERE fm.id = p_member_id
     AND (fm.facility_id IN (SELECT id FROM public.facilities WHERE owner_user_id = v_uid)
          OR fm.player_id IN (SELECT id FROM public.players WHERE user_id = v_uid));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.create_facility(text,text,integer,text)  FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.create_facility(text,text,integer,text)  TO authenticated;
REVOKE EXECUTE ON FUNCTION public.join_facility_by_code(text,uuid)         FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.join_facility_by_code(text,uuid)         TO authenticated;
REVOKE EXECUTE ON FUNCTION public.leave_facility(uuid)                     FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.leave_facility(uuid)                     TO authenticated;

-- ------------------------------------------------------------
--  Sponsorship resolution note
-- ------------------------------------------------------------
-- The best-of(own sub, facility sponsorship) resolution lives in Python
-- (entitlements.resolve_effective_plan) to keep this view simple and unit-
-- testable. The app reads an active player's facility membership via
-- facility_storage and passes sponsored=True into resolve_effective_plan.
-- A player is "sponsored" iff they have a facility_members row with
-- left_at IS NULL whose facility.status = 'active'.
