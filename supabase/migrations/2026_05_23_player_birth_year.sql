-- #134 — Persist player birth year for the age-fair Swing Score.
-- Additive + nullable: existing rows get NULL → analyzer defaults to the
-- 13-14 bracket until a birth year is set in Player Settings.
alter table public.players
  add column if not exists birth_year smallint;

comment on column public.players.birth_year is
  'Player birth year (4-digit). Age = current_year - birth_year, computed at '
  'analysis time so it never goes stale. Drives the age-fair Swing Score '
  'brackets (8-10 / 11-12 / 13-14 / 15-17). Nullable; null -> default bracket.';
