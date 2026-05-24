# Age + Stride-Direction Persistence — Design (#134)

**Date:** 2026-05-23
**Branch:** `claude/swing-engine` (folded into PR #23, making it a complete, shippable unit)
**Status:** APPROVED (pending user spec review)

## Problem

The Swing Score engine (PR #23) ships an age-fair scoring system and a front-leg
brace pillar, but two inputs never reach it in production:

1. **Age is not persisted.** `analyze()` reads `player.get("age")` from the
   fingerprint and `age_bracket()` maps it to one of `8-10 / 11-12 / 13-14 /
   15-17`. But age is only captured in Player Settings as a *session-state pref
   with no DB column*, so it's lost on logout / new device. Every real swing
   therefore defaults to the `13-14` bracket and the per-age threshold widening
   never engages.

2. **Stride direction is unknown.** `score_stride` needs `stride_toward_pitcher`
   to gate the front-leg-brace reward, but `detect_phases` only serializes stride
   *magnitude* (`stride_px = abs(...)`), so `analyzer.py` hardcodes the gate to
   `True`. A player who steps in the bucket / bails out is scored as if they
   strode forward.

## Goal

Make the age-fair bands actually vary and replace the hardcoded stride gate with
a real signal — without breaking older fingerprints or saved reports.

## Decisions

- **Store `birth_year` (4-digit), not raw age.** Age is computed at analysis time
  as `current_year − birth_year`, so it auto-advances every year with zero
  re-entry. A stored raw age would silently go stale.
- **Settings shows a "Birth year" field** with the computed age rendered beside it
  as a read-only hint (e.g. *"Birth year 2014 · Age 12"*).
- **`detect_phases` remains the sole author of the fingerprint.** Age is passed
  *in* to it (computed by `app.py` from the profile); it writes `age` + a `stride`
  block into the fingerprint JSON.
- **Age capture = soft nudge + honest label, never a hard gate.** Analysis is
  never blocked on a missing birth year. Instead, when a swing is scored without
  a known age, the report shows an honest note ("Scored on the 13–14 standard —
  add your birth year for an age-accurate score") that links to Settings. This
  matches the app's existing honesty cues (confidence badges, filming guide) and
  captures most users without a wall. The label disappears once a birth year is
  set.
- **Height & weight stay optional, unchanged.** The analysis never reads them
  (biomechanics are torso-normalized; the Score/Match use dimensionless ratios),
  so they remain context-only profile fields with no prompt or gate.

## Data flow

```
Settings (Birth year)  ──save (update_profile)──▶  players.birth_year  (Supabase)
                                                          │
                                            profile dict via _profile_from_row
                                                          │
                              app.py: age = current_year − birth_year (or None)
                                                          │  passed to subprocess
                                                          ▼
   detect_phases.py  ──writes──▶  *_fingerprint.json {
                                      "age": 12,
                                      "stride": { "toward_pitcher": true, "dx_norm": 0.18 }
                                    }
                                                          │
                              analyze(): age_bracket(age) + score_stride(reext, toward_pitcher, bracket)
```

## Components & changes

### 1. DB migration (DDL — gated on explicit user apply)
- Add `birth_year smallint` (nullable) to `public.players`.
- Written idempotently (`ADD COLUMN IF NOT EXISTS`). Additive + nullable →
  existing rows get `NULL` → default bracket until a birth year is entered.
- A migration file is committed; **applying it to the live DB is a separate,
  explicitly-authorized step** (mirrors the family / sub-accounts migration flow).

### 2. `auth.py`
- `_profile_from_row` returns `"birth_year": row.get("birth_year")`.
- Add `"birth_year"` to the profile-update whitelist (the `ALLOWED_*` set near
  line 389) so `update_profile` can persist it.
- `sign_up` is left unchanged (birth year is optional, set later in Settings).

### 3. `player_storage.py`
- Add `"birth_year"` to `ALLOWED_PROFILE_UPDATES` so the patch path accepts it.

### 4. `player_settings_page.py`
- Replace the session-state-only "Age" field with a **"Birth year"** field bound
  to the profile (`user.get("birth_year")`), dirty-tracked like height/weight,
  saved through the existing `update_profile` save path.
- Render the computed age beside it as a hint. Validate range (e.g. plausible
  4-digit year that yields age 5–19); blank is allowed (→ unknown).

### 5. `detect_phases.py`
- Accept an **optional age argument** (after the existing video + handedness
  args). When present and valid, write `fingerprint["age"] = int(age)`. When
  absent, omit the field (analyze falls back to the default bracket).
- Add a **pure helper** `stride_direction(front_ankle_x, back_ankle_x,
  stance_idx, foot_plant_idx, torso_px) -> {"toward_pitcher": bool, "dx_norm": float}`
  (both ankle args are per-frame x-series):
  - pitcher side = `sign(front_ankle_x[stance_idx] − back_ankle_x[stance_idx])`,
  - signed forward displacement = `(front_ankle_x[foot_plant_idx] − front_ankle_x[stance_idx]) * pitcher_side`,
  - `dx_norm` = that displacement / torso_px (scale-invariant, signed; + = toward pitcher),
  - `toward_pitcher` = `dx_norm > STRIDE_TOWARD_EPS` (small positive threshold).
- Write `fingerprint["stride"] = {"toward_pitcher": ..., "dx_norm": ...}`.

### 6. `app.py`
- At the `detect_phases.py` subprocess call site, compute the player's age from
  `user["birth_year"]` and pass it as the new optional arg. If birth_year is
  missing, pass nothing (current behavior preserved).

### 7. `analyzer.py`
- Read `stride_toward_pitcher` from `fingerprint["stride"]["toward_pitcher"]`,
  defaulting to `True` when the block is absent (back-compat). Feed it to
  `score_stride`. Age path is already wired (`player.get("age")`).
- Add `"age_known": bool` to the result — `True` when `player.get("age")`
  resolved to a usable int, `False` when the bracket was defaulted. The report
  uses this to decide whether to show the honest age label. (`age_bracket` is
  already returned.)

### 8. `swing_report_dashboard_preview.py` — honest age label (the soft nudge)
- On the score card, when `record.get("age_known")` is falsy, render a small,
  non-blocking note: *"Scored on the 13–14 standard — add your birth year for an
  age-accurate score."* with a link/affordance to Player Settings. When
  `age_known` is true, render nothing (or a quiet "Age-fair · 11–12" tag).
- Back-compat: legacy records without `age_known` are treated as unknown but the
  note is suppressed if the record predates the field entirely (no `swing_score`)
  so old saved reports don't sprout a nag. (i.e. only show on new-engine reports.)

## Error handling & back-compat

- **Old fingerprints / saved reports** lack `age` and `stride` → age defaults to
  `13-14`; stride gate defaults to `True`. Identical to today. No regression.
- **Missing/invalid birth_year** → age is `None` → default bracket. Never raises.
- **Degenerate stride geometry** (missing ankle visibility, zero torso) → helper
  returns `toward_pitcher=True, dx_norm=0.0` (fail-soft to the lenient gate so a
  bad camera read doesn't unfairly punish the brace pillar).

## Testing

- `stride_direction()` — pure unit tests: forward stride → `True` + positive
  `dx_norm`; step-in-the-bucket (front foot moves away from pitcher) → `False`;
  degenerate inputs → fail-soft.
- `age_from_birth_year()` — pure: `2014 @ 2026 → 12`; `None → None`; junk → `None`.
- `auth._profile_from_row` — a fake row with `birth_year` round-trips into the
  profile dict.
- `analyzer.analyze` — a fingerprint with `stride.toward_pitcher=False` gates the
  Stride pillar (lower compliance than the `True` case); a fingerprint with
  `age` resolves a non-default bracket.
- `player_settings_page` — wiring test: editing birth year marks dirty and the
  save path calls `update_profile(birth_year=...)`.
- `analyzer.analyze` — `age_known` is `True` when the fingerprint carries a valid
  `age`, `False` when absent.
- `swing_report_dashboard_preview` — the honest age note appears when
  `age_known` is falsy on a new-engine record, and is absent when `age_known` is
  true; a legacy record (no `swing_score`) shows no note.
- Full suite stays green (`pytest tests/ -q`).

## Out of scope (YAGNI)

- Full date-of-birth (year granularity is enough for the 4 brackets).
- Backfilling birth_year for existing players (they set it in Settings; until
  then, default bracket).
- Re-scoring historical saved swings with newly-known age.
