-- Make the entitlement view honor the caller's RLS instead of running as its
-- owner (Supabase advisor 0010, ERROR). Applied to prod 2026-05-24 via MCP;
-- recorded here so the repo matches the live schema.
-- No live leak today (every CTE filters by auth.uid()), but as SECURITY DEFINER
-- RLS was not a backstop. Verified safe: the caller has SELECT on all four
-- underlying tables (plans=public; subscriptions=owner OR user_has_seat;
-- subscription_seats=self OR owner; usage_counters=self), so owners AND
-- household seat members still resolve their plan correctly.
alter view public.v_my_plan set (security_invoker = on);
