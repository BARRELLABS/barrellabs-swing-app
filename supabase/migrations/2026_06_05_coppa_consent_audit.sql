-- COPPA consent audit trail on players.
--
-- account_terms_agreed_at : when the ACCOUNT OWNER (13+) agreed to Terms/Privacy
--   and affirmed their age at signup (set on the owner's own player row).
-- guardian_consent_*       : when the account owner affirmed parent/guardian
--   consent for a MINOR household player (set on the child's player row).
--
-- Applied to prod 2026-06-05 via the Supabase MCP; this file version-controls it.
alter table public.players
  add column if not exists account_terms_agreed_at timestamptz,
  add column if not exists guardian_consent_at      timestamptz,
  add column if not exists guardian_consent_by       uuid,
  add column if not exists guardian_consent_method   text;

comment on column public.players.account_terms_agreed_at is
  'When this account owner agreed to Terms/Privacy + affirmed 13+ at signup.';
comment on column public.players.guardian_consent_at is
  'When a parent/guardian consented to data collection for this minor player.';
comment on column public.players.guardian_consent_by is
  'auth.users.id of the consenting parent/guardian (the household owner).';
comment on column public.players.guardian_consent_method is
  'How consent was captured: authenticated_account | phone | email_plus.';
