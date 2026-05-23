-- ============================================================
--  Household sub-accounts: one auth login → many player profiles
--  Date: 2026-05-23
--  Spec: docs/superpowers/specs/2026-05-23-household-subaccounts-design.md
-- ============================================================

-- 1. Allow multiple players per auth user (was UNIQUE = one per login).
ALTER TABLE public.players DROP CONSTRAINT IF EXISTS players_user_id_key;

-- The UNIQUE constraint was also the only index on user_id; re-add a
-- plain index so household lookups stay fast.
CREATE INDEX IF NOT EXISTS players_user_id_idx ON public.players(user_id);

-- 2. Soft-remove column so removing a profile frees a seat but keeps swings.
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS removed_at timestamptz;

CREATE INDEX IF NOT EXISTS players_user_active_idx
  ON public.players(user_id)
  WHERE removed_at IS NULL;

-- 3. create_household_player — owner-only, seat cap from plans.seats,
--    counted under a lock so two concurrent creates can't both pass.
CREATE OR REPLACE FUNCTION public.create_household_player(
  p_name        text,
  p_handedness  text DEFAULT 'RIGHT',
  p_position    text DEFAULT NULL,
  p_is_minor    boolean DEFAULT true
) RETURNS public.players AS $$
DECLARE
  v_uid    uuid := auth.uid();
  v_seats  integer;
  v_active integer;
  result   public.players%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'create_household_player: not authenticated';
  END IF;
  IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
    RAISE EXCEPTION 'create_household_player: name required';
  END IF;
  IF p_handedness NOT IN ('RIGHT','LEFT') THEN
    RAISE EXCEPTION 'create_household_player: handedness must be RIGHT or LEFT';
  END IF;

  -- Seat cap from the household's plan (via v_my_plan, which already
  -- resolves the caller's plan). Lock the caller's existing rows so the
  -- count is stable for the duration of the insert.
  SELECT COALESCE(seats, 1) INTO v_seats
    FROM public.v_my_plan;
  IF v_seats IS NULL THEN v_seats := 1; END IF;

  PERFORM 1 FROM public.players
   WHERE user_id = v_uid AND removed_at IS NULL
   FOR UPDATE;

  SELECT count(*) INTO v_active
    FROM public.players
   WHERE user_id = v_uid AND removed_at IS NULL;

  IF v_active >= v_seats THEN
    RAISE EXCEPTION 'create_household_player: all % profile slots are in use', v_seats;
  END IF;

  INSERT INTO public.players (user_id, name, handedness, position)
  VALUES (v_uid, trim(p_name), p_handedness, p_position)
  RETURNING * INTO result;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.create_household_player(text, text, text, boolean) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.create_household_player(text, text, text, boolean) TO authenticated;
