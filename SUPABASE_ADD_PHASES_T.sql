-- =====================================================================
-- Push 1.3 — add phases_t column to swings table
-- =====================================================================
--
-- Why: the side-by-side swing comparison viewer needs the user's
-- per-phase timestamps (load_start, foot_plant, launch, contact,
-- peak_rotation, finish) to synchronize playback against the MLB
-- reference at foot plant.
--
-- Until this column exists, save_swing_record() will detect the missing
-- column and silently retry without phases_t — newly saved swings won't
-- have foot-plant sync. The viewer falls back to lockstep playback so
-- nothing breaks visually, but the experience is noticeably worse.
--
-- After running this:
--   - All NEW swings save phases_t to the row.
--   - The comparison viewer pulls phases_t from the row first; falls
--     back to the pose JSON (which already carries it for backwards
--     compatibility) for any swings saved before the column existed.
--
-- Safe to re-run: IF NOT EXISTS guard makes this idempotent.
-- =====================================================================

ALTER TABLE swings
  ADD COLUMN IF NOT EXISTS phases_t JSONB DEFAULT '{}'::jsonb;

-- Backfill: for older swings, leave phases_t as {} — the viewer will
-- look inside the pose JSON for the timestamps as a fallback path.

COMMENT ON COLUMN swings.phases_t IS
  'Phase timestamps in seconds (load_start, foot_plant, launch, contact, peak_rotation, finish) for the user video. Drives side-by-side swing comparison sync.';
