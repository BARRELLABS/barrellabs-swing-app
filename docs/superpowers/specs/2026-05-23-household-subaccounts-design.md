# Household Sub-Accounts (Family Pro Profiles) — Design Spec

**Date:** 2026-05-23
**Status:** Draft, design approved verbally; awaiting spec review
**Workstream:** Family Pro — turn "one login = one player" into "one household login = up to N player profiles, pick at session start"

## Problem

Family Pro advertises "up to 4 family member accounts," and we shipped the
seat plumbing + dashboard. But the join model we built (email invites →
each kid makes their own login) is wrong for the audience: most buyers are
parents of 8–12-year-olds who **have no email**, and a per-swing "who is
this for?" picker would scramble swing reports.

The right model (user-chosen): **one household login → up to N sub-account
profiles → pick which one you are at session start → swings auto-attach to
the active profile.** Netflix/Disney+ households.

## Goal

One household login can hold up to **N player profiles** (N = the plan's
`seats`: free 1, solo 1, family 4, coach 20). After login, a **"Who's
training?"** picker selects the active profile for that session/device.
Every page already keys off `st.session_state["player"]`, so once the
picker sets it, the whole app behaves as that profile. A **"Switch
profile"** control changes it. Swings, reports, drill plans, progress,
streaks are all isolated per profile.

## Key architectural fact (why this is bounded)

The app **already** centralizes "the current player" in a single place:

- `st.session_state["player"]` holds the active player dict.
- Every page reads it via `auth.current_profile()` (auth.py:240) or
  `st.session_state.get("player")`.
- Today `current_profile()` fetches *the* player row for the auth user
  (`_fetch_player_row(user.id)` → `players` where `user_id = auth.uid()`,
  `limit 1`).

So the change is concentrated: make the login/restore flow aware that a
household can have **multiple** player rows, set `st.session_state["player"]`
to the chosen one via a picker, and add a switch control. **Pages that
already read `st.session_state["player"]` need no changes.**

## Non-goals (parked / deferred)

- **Email-invite + claim flow** (`subscription_seats` invite_token/claim
  RPCs already in the DB): unused in this model. Left dormant — harmless,
  and available later for an optional "teen with their own login" feature.
- **Per-profile passwords / PINs**: v1 is one shared household login. A
  per-profile PIN ("kid mode" lock) is a future option, not now.
- **Coach Pro roster (20)**: the schema supports it (cap from plans.seats),
  but the coach-specific UX (rosters, read-only roll-ups) is its own spec.
- **Cross-household profile transfer / emancipation to own login**: future.

## Data model

### The one schema change

Today `players.user_id` is **UNIQUE** (one player per auth account). That's
the only thing blocking multiple profiles per household. We:

1. **Drop the unique constraint** on `players.user_id` (keep a plain index
   for query perf — the FK already provides one).
2. All of a household's profiles share `user_id = <household auth id>`.
   They're distinguished by `players.id`. The **active** profile is a
   session choice (`st.session_state["player"]` = that row).
3. **Seat cap** = `count(players WHERE user_id = auth.uid()) <= plans.seats`
   for the household's subscription plan. Enforced by a SECURITY DEFINER
   RPC `create_household_player(...)` (mirrors `invite_subscription_seat`):
   it reads the caller's plan via `v_my_plan`, counts existing profiles,
   rejects past the cap, inserts the new profile under `auth.uid()`.

### Why this is clean

- **RLS unchanged.** Existing `players`/`swings`/`training_logs` policies
  scope by `user_id = auth.uid()`. Since all a household's profiles share
  the household `user_id`, the household login already has correct access to
  every profile's data — no new policies.
- **Swings unchanged.** `swings.player_id` already points at a specific
  player; `swings.user_id` is the household auth id. A swing saved while
  profile = Tommy gets `player_id = Tommy.id`. Isolated history, free.
- **Existing solo/free users unaffected.** They have exactly 1 player row;
  `current_profile()` auto-selects it; no picker shown. Zero UX change for
  non-family users.

### What does NOT change

- `subscriptions` (owner_user_id = household auth id) — already the household.
- `subscription_seats` — parked; not read by this model.
- `v_my_plan` — already resolves the household's plan; we read `seats` from it.

## Components

| File | Change |
|---|---|
| `supabase/migrations/2026_05_23_household_profiles.sql` | NEW. Drop `players.user_id` unique; add `create_household_player` RPC (seat cap from plans.seats); SECURITY DEFINER, authenticated-only. |
| `auth.py` | Add `list_household_players(user_id) -> list[dict]` and `set_active_player(player_id)`. Change login/restore so that with >1 profile and none chosen, it does NOT auto-pick — it signals "needs profile pick". Solo (1 profile) auto-picks as today. `create_household_player()` wrapper calling the RPC. |
| `app.py` | After auth, if the household has >1 profile and `st.session_state["player"]` is unset → route to the "Who's training?" picker before any page renders. Add a "Switch profile" action that clears the active player and re-shows the picker. |
| `household_picker.py` | NEW. The "Who's training?" screen — editorial profile cards (avatar + name + last-active), plus "+ Add a player" if under the cap. Selecting one sets the active player and reruns. |
| `player_settings_page.py` | "Household" section becomes **profile management**: list profiles, "Add a player" (name + bat hand + position, no email), edit, remove. Replaces the email-invite UI. Hidden for non-multi-seat plans. |
| `family_dashboard.py` | `family_storage` already returns "members"; re-point its source to the household's player profiles (see below). UI unchanged. |
| `family_storage.py` | Repoint internals to `players WHERE user_id = household auth id`. Public API stays (load_family_for_user / list_members / add_member / remove_member / get_member_summary). `add_member` → `create_household_player`. Drop the invite-token path from the family-profile flow (parked). |
| `bl_edge_chrome.py` | Add a small "Switch profile" affordance (only when household has >1 profile). |

## Flows

### First-time setup (parent just bought Family Pro)
1. Parent logs in (household login). They have 1 profile (their own, from signup).
2. Settings → Household → "Add a player" → name + bat hand + position → repeat up to 4 total.
3. Done. No emails, no invites.

### Daily use (any device)
1. Sign in with the household login.
2. **"Who's training?"** picker: tap a profile (Dad / Tommy / Mia / Owen).
3. App now behaves entirely as that profile — upload a swing → saves to that
   profile's history; reports/training plan/dashboard all that profile's.
4. "Switch profile" → back to the picker.

### Family dashboard
Any profile can open it (it's a household view). Shows a card per profile
with latest score, trend, "what to ask them about." Tapping a card switches
the active profile to that player and opens their report.

### Solo / Free user (unchanged)
1 profile → auto-selected at login → no picker, no household section. Exactly
as today.

## Seat cap — exactly N, no more no less
- `create_household_player` RPC counts `players WHERE user_id = auth.uid()`
  and rejects when `>= plans.seats`. family_pro = 4. The parent's own profile
  (created at signup) is profile #1, so family = parent + 3 = 4.
- Removing a profile is a **soft-remove**: set `players.removed_at`. Swing
  history is never destroyed, the slot frees immediately, and removed
  profiles drop out of the picker/dashboard and stop counting toward the cap.

## Migration / backfill
- Drop unique on `players.user_id`. Existing rows: each user has 1 player →
  still valid (no dupes to worry about).
- Add `players.removed_at timestamptz NULL`.
- No data backfill needed. Existing 2 solo players keep working untouched.
- Additive + safe; apply via Supabase MCP after review.

## Testing
- `tests/test_household_profiles.py` (pure/mocked):
  - `list_household_players` returns all non-removed profiles for a user.
  - `create_household_player` rejects past the plan cap (mock plan seats).
  - `set_active_player` sets session correctly; ignores a profile id not in
    the household (security: can't activate someone else's profile).
  - solo user (1 profile) → auto-active, no picker.
  - household (>1) with none active → needs-pick signal.
  - removed profile excluded from list + cap count.
- `tests/test_household_picker_render.py` (streamlit-stubbed snapshot):
  picker renders one card per profile + add-player when under cap.
- Regression: existing `tests/test_family_*` updated to the player-profile
  source; full suite stays green.
- Manual: 2-profile household end-to-end (login → pick → upload → switch →
  second profile has its own report).

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Dropping the unique constraint could let a bug create stray dupes for solo users | `create_household_player` is the only insert path for extra profiles; signup still creates exactly 1; cap RPC guards count |
| A profile activates that isn't in the household (IDOR) | `set_active_player` verifies the chosen `player.id` belongs to `user_id = auth.uid()` before setting session |
| Pages that read the player BEFORE the picker runs | app.py gates the picker before any page render when household >1 and none active; solo path unchanged |
| Active profile leaking across devices | active profile lives in `st.session_state` (per-session/device), never persisted globally — each device picks its own |
| Removing a profile orphans its swings | soft-remove (`removed_at`); swings retained; slot frees |
| Existing family_storage/subscription_seats code now dead | repoint family_storage to players; leave subscription_seats parked + documented |

## Open questions — resolved
| Q | Decision |
|---|---|
| Multiple players per login — how linked? | Shared `user_id` = household auth id; distinguished by player.id |
| Where is "active profile" stored? | `st.session_state["player"]` (already the app's source of truth) |
| Remove = hard or soft delete? | Soft (`players.removed_at`) — preserve swing history, free the seat |
| Seat cap source? | `plans.seats` via `v_my_plan` (4 for family) |
| Picker every login or remembered? | Shown when household >1 and no active profile in this session; "Switch profile" re-shows it |
| Solo/free users see a picker? | No — 1 profile auto-selects, household UI hidden |
