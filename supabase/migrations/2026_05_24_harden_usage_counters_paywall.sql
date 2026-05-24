-- Harden the free-swing paywall (applied to prod 2026-05-24 via MCP; recorded
-- here so the repo matches the live schema).
-- usage_counters.free_swings_used is the entire free-tier cap, but its RLS
-- policy was cmd=ALL (auth.uid() = user_id) and anon/authenticated held full
-- DML grants — so a Free user could PATCH/DELETE their own row via the public
-- Data API and reset the cap. The only legitimate writer is the SECURITY
-- DEFINER increment_free_swing_usage() RPC (runs as the function owner, does
-- INSERT ... ON CONFLICT itself), unaffected by the revoke below.
drop policy if exists usage_counters_self on public.usage_counters;

create policy usage_counters_select_self
  on public.usage_counters
  for select
  using ((select auth.uid()) = user_id);

revoke insert, update, delete, truncate
  on public.usage_counters from anon, authenticated;
