-- Account deletion currently leaves the auth.users row orphaned (the browser
-- anon-key client can't delete auth users), so a "deleted" account keeps its
-- email/PII in auth.users (a GDPR/retention gap). Every public table that
-- references auth.users is ON DELETE CASCADE (players, swings, training_logs,
-- subscriptions, facilities, usage_counters, beta_redemptions), so deleting the
-- auth row server-side wipes the whole account in one shot.
--
-- This SECURITY DEFINER RPC deletes ONLY the caller's own auth row
-- (auth.uid()), so a user can never delete anyone else. Authenticated-only.

CREATE OR REPLACE FUNCTION public.delete_own_auth_user()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  uid uuid := auth.uid();
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'not authenticated';
  END IF;
  -- Cascades to players / swings / training_logs / subscriptions / facilities /
  -- usage_counters / beta_redemptions and all auth-internal rows.
  DELETE FROM auth.users WHERE id = uid;
END;
$$;

REVOKE ALL ON FUNCTION public.delete_own_auth_user() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.delete_own_auth_user() TO authenticated;
