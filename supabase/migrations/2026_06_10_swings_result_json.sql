-- Persist the full analyzer result on each swing so a reopened report is
-- identical to the live post-analyze report. Before this, only the legacy
-- `score`/`score_band_*` columns were saved, so swings reopened from Sessions
-- lost every new-engine field (swing_score, pillars, mlb_match,
-- what_you_did_well, confidence, ...) and fell back to a downgraded render.
--
-- The discrete columns (score, narratives, metric_table, ...) are kept for
-- querying; player_storage._swing_row_to_legacy uses result_json as the base
-- and overlays them. Additive + nullable, so older rows are unaffected.

ALTER TABLE public.swings
  ADD COLUMN IF NOT EXISTS result_json jsonb;
