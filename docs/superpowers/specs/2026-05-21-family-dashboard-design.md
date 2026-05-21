# Parent / Family Dashboard — Design Spec

**Date:** 2026-05-21
**Status:** Draft, locked after multi-agent design critique pass
**Workstream:** Family Pro UX — first ever family infrastructure in the codebase

> ⚠️ Prior audit confirmed: **zero family infrastructure exists**. No `families` table, no parent-child links, no seat enforcement. Family Pro today grants Pro only to the buyer. This spec is foundational.

## Problem

BarrelLabs sells a **$24.99/mo Family Pro** plan that advertises *"Up to 4 family member accounts."* But:

- No `families` table in Supabase.
- The Stripe webhook never creates a family group.
- Entitlements only check the buyer's row → kids who try to use the app get the free experience.
- The marketing page is selling something the product can't deliver.

Parents are paying for invisible seats. That's a fraud-adjacent state.

## Goal

Build the first end-to-end Family Pro experience:

1. **Schema** that supports families, members, roles, and pending invites.
2. **Entitlement propagation** so a Pro family's members see Pro features.
3. **Invite flow** so a parent can add up to 4 players to their household.
4. **Parent dashboard** (new page) showing every member's progress at a glance.
5. **Settings integration** for managing the household (add, remove, resend invite).
6. **Routing model** that's clear about parent-vs-kid mode.

## Non-goals (deferred)

- **COPPA shadow-player** (under-13 with no auth account) — design hooks exist, full implementation in v1.5.
- **Cross-household kid** (divorced parents, kid in two families) — single-household assumption.
- **Coach Pro roster view** — same shape but separate spec; this PR doesn't touch coach plans.
- **Nudge notifications** — the dashboard shows a "Nudge Owen" button but actual push/SMS/email delivery is stubbed (TODO marker). Visual + UX shipped; backend in follow-up.
- **Privacy controls / kid revoke parent visibility** — v1 ships "Parents see what kids see"; granular kid-side toggles are v2.
- **Family display name customization** — uses default "<Owner's name>'s Household."

## The 4 states the dashboard must handle

Locked from the v2 mockup (`.superpowers/brainstorm/.../family-mockup-v2.html`):

| State | When | UI shape |
|---|---|---|
| **A · Populated** | 2–4 active members | 3-col grid of cards; summary strip up top; add-row if seats remaining |
| **B · Empty** | Family Pro active, 0 members invited | Centered "Add your first player" CTA card; onboarding copy |
| **C · Single player** | 1 member | Single centered card (no grid); add-row prominent |
| **D · Full** | 4/4 seats | Grid; no add-row, instead "Household full · Manage" link |

Stale state (any active member who hasn't filmed in >10 days) gets red-accent badge + Nudge button INSIDE their card. Lives at the card level, applies to any of the 4 states.

## Schema

### `families` table

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `default gen_random_uuid()` |
| `owner_user_id` | `uuid` FK → `auth.users.id` | UNIQUE — one family per buyer in v1 |
| `subscription_id` | `uuid` FK → `subscriptions.id` | NULL until Stripe webhook fires |
| `display_name` | `text` | Default: "<Owner's first name>'s Household" |
| `created_at` | `timestamptz` | `default now()` |
| `updated_at` | `timestamptz` | trigger to maintain |

**Indexes:** `owner_user_id` UNIQUE, `subscription_id`.

### `family_members` table

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `default gen_random_uuid()` |
| `family_id` | `uuid` FK → `families.id` | ON DELETE CASCADE |
| `player_user_id` | `uuid` FK → `auth.users.id` | NULL until invite accepted |
| `role` | `text` CHECK in `('owner','parent','child')` | `owner` is the payer; `parent` is an adult sub-account; `child` is a minor |
| `invite_email` | `text` | citext lowercased; non-null for `invite_status='pending'` |
| `invite_token_hash` | `text` | sha256 of one-time token; NULL after acceptance |
| `invite_status` | `text` CHECK in `('pending','active','removed')` | |
| `is_minor` | `boolean` | drives COPPA path; v1 just an attestation flag |
| `display_name` | `text` | Used on the card before/while user fills profile |
| `added_at` | `timestamptz` | `default now()` |
| `removed_at` | `timestamptz` | NULL until removal; soft-delete |

**Indexes:**
- `(family_id, invite_status='active')` partial unique on `player_user_id` (one active membership per user)
- `(family_id)` for listing members
- `(invite_token_hash)` for invite-claim lookup
- `(invite_email) WHERE invite_status='pending'` for "resend invite" UX

### Row Level Security

```
families:
  SELECT  : user is owner OR active member of this family_id
  UPDATE  : user is owner only
  INSERT  : Stripe webhook (service role) only
  DELETE  : owner only (rare; v1 doesn't expose UI)

family_members:
  SELECT  : user is in the same family_id (any role)
  INSERT  : user is owner of family_id, AND total active members < 4
  UPDATE  : (a) user is owner of family_id, OR
            (b) user is updating their own row's `display_name`/`is_minor` only
  DELETE  : never; use UPDATE to set invite_status='removed' (soft delete)
```

Seat enforcement is a **DB-level check** via a row-level CHECK on insert or a stored procedure `add_family_member()` that COUNTs first. Either works; spec leaves implementation choice to the engineer.

### `v_my_effective_plan` view

Replaces `v_my_plan`. Returns the plan resolution honoring family membership:

```sql
CREATE OR REPLACE VIEW public.v_my_effective_plan AS
SELECT
  auth.uid()                                  AS user_id,
  COALESCE(
    -- Direct subscription wins (the user paid)
    (SELECT s.plan_id FROM subscriptions s
       WHERE s.owner_user_id = auth.uid()
         AND s.status IN ('active', 'trialing', 'past_due')
       LIMIT 1),
    -- Otherwise: are they an active member of a family with an active Family Pro sub?
    (SELECT s.plan_id FROM family_members fm
       JOIN families f ON f.id = fm.family_id
       JOIN subscriptions s ON s.id = f.subscription_id
      WHERE fm.player_user_id = auth.uid()
        AND fm.invite_status = 'active'
        AND s.status IN ('active', 'trialing', 'past_due')
      LIMIT 1)
  ) AS plan_id,
  ...
;
```

`past_due` keeps Pro for the dunning grace window; Stripe will downgrade status to `canceled` after 3 retries.

## Entitlement propagation

| Event | Effect |
|---|---|
| Parent buys Family Pro | Stripe webhook (`checkout.session.completed`) creates `subscriptions` row AND a `families` row with `owner_user_id=buyer`, plus a `family_members` row with `role='owner', player_user_id=buyer, invite_status='active'`. |
| Parent invites kid by email | New `family_members` row with `invite_status='pending'`, `invite_token_hash=sha256(token)`, `invite_email=lowercase(email)`. Magic-link email sent. |
| Kid clicks invite link | Lands on `/invite?token=...`. If unauthenticated → sign up. After auth, server validates token → flips `invite_status='active'`, sets `player_user_id=auth.uid()`. |
| Parent removes kid | UI sets `invite_status='removed'`, `removed_at=now()`. RLS no longer matches; kid's `v_my_effective_plan` returns NULL plan → Free tier. Their swing history STAYS on their `players` row. |
| Parent cancels Family Pro | Stripe webhook sets `subscriptions.status='canceled'`. `v_my_effective_plan` no longer joins. All members drop to Free on next render. |
| Subscription goes past_due | Members keep Pro for the dunning window (Stripe default 3 retries / ~10 days). |

## Invite flow (13+)

1. Parent enters email on settings page → POST to `add_family_member(family_id, email)`.
2. Server checks: caller is owner, family has < 4 active members.
3. Server: generates random 32-byte token, hashes with sha256, stores hash. Sends email via Supabase auth or SMTP with link `https://barrellabs.com/invite?token=<token>`.
4. Recipient clicks link:
   - **Already has account, logged in**: server matches token, flips `invite_status='active'`, sets `player_user_id`. UI: "You've joined the <Family> household." Redirect to dashboard.
   - **Already has account, logged out**: prompts sign-in, then same as above.
   - **No account**: sign-up flow inherits `invite_token`; on successful signup, server claims the invite atomically.
5. Token is single-use; cleared after claim. Expires after 30 days.

### Under-13 / COPPA path (v1.5 scaffolding)

Settings page UI has a toggle: "Is this player under 13?" → `is_minor=true`, no email field, parent enters display name + handedness. v1 just creates the row with `is_minor=true` and `player_user_id=NULL`; the kid never logs in separately. Swing uploads on this row are stamped with the parent's `auth.uid()` (audit). Full COPPA-shadow-player behavior is v1.5.

## UI

### Routing model

- **New nav item: "Family"** (visible only if `is_family_pro(user)`).
- When a Family Pro user logs in: still defaults to their own `/dashboard`. They opt into the family view via the nav. (Spec discussed defaulting parents to Family — rejected because parents who hit themselves also want their own dashboard.)
- The **context bar** atop the Family page shows "Viewing as Parent" with a "Switch to my own swings" link back to `/dashboard`.
- The **"View Jake's Report →"** CTA per card sets a session-scoped flag `viewing_as_member_id=<jake>` and routes to `/swing-report`. The report renders read-only with a persistent "Back to Family" bar at the top. Kids see no "Back to Family" bar when they view their own report normally.

### File map

| File | Purpose |
|---|---|
| `family_storage.py` | New. CRUD + queries: `load_family_for_user`, `list_members`, `add_member`, `claim_invite`, `remove_member`, `get_member_summary`. |
| `family_dashboard.py` | New. Streamlit page rendering the 4 states. Reads from `family_storage`. |
| `family_invite_page.py` | New. The `/invite?token=...` landing page. |
| `entitlements.py` | Modify. Add `_resolve_plan_id_via_family()` helper that hits `v_my_effective_plan`. |
| `subscription_storage.py` | Modify. Repoint `load_my_plan()` at `v_my_effective_plan` instead of `v_my_plan`. |
| `stripe_client.py` | Modify. Webhook handler creates `families` row when Family Pro purchased. |
| `player_settings_page.py` | Modify. New "Household" section: list members, invite form, remove. |
| `bl_edge_chrome.py` | Modify. Add "Family" nav item gated on `is_family_pro`. |
| `app.py` | Modify. Route `page == "family"` → `family_dashboard.render()`. Route `page == "family_invite"` → `family_invite_page.render()`. Honor `viewing_as_member_id` flag in swing-report routing. |
| `supabase/migrations/2026_05_21_families.sql` | New. Schema + RLS + view. |

### Detailed UI per state (from v2 mockup)

See `.superpowers/brainstorm/44295-1779394399/content/family-mockup-v2.html` — the design is locked there. Key decisions:

- **Hero copy varies by state.** State A: "The whole family. *One lab.*" State B: "Your lab, *your household.*" State C: "<Kid's name>'s *progress.*" State D: "Four players. *One lab.*"
- **Summary strip** (4 cells: This week, Top streak, Combined XP, Avg score) only renders in State A (2+ members). State C uses no strip — single card carries the story.
- **All scores in bone** (no gold). Gold is reserved for the single italic word in the hero + accent emphasis in verdict lines + delta arrows.
- **Verdict line** is `Instrument Serif italic` above the score: "Best week this month." / "Holding steady." / "Hasn't filmed since the 9th."
- **Sparklines** share a baseline (60-90 score range), tick labels in mono on the right edge. Stroke `rgba(244,239,230,0.32)`, end-dot color reflects rating (gold for up, bone-dim for flat, bone-mute for stale).
- **Stale state**: badge `12 days` in red, soft-red card-tint, dedicated "Send him a soft nudge?" block ABOVE the View Report CTA with a `Nudge <name>` button.
- **Top fix copy is parent-facing**: "ASK HIM" / "ASK HER" eyebrow, plain-English: "Ask Jake about keeping his front shoulder closed — he's been working on it all week."
- **Self-as-player card**: `.card.is-self` with subtle gold border tint + "YOU" pill next to the name. Top fix says "YOUR FIX" not "ASK".

## Tests

### Schema/RLS tests (`tests/test_family_rls.py`)

- Parent can SELECT own family.
- Parent CANNOT SELECT other family.
- Active member can SELECT own family.
- Removed member CANNOT SELECT family they were removed from.
- Sibling A can see sibling B's `display_name` (same family) — yes, this is intentional, the dashboard shows the whole household.
- Sibling A CANNOT modify sibling B's profile.
- Non-owner CANNOT add a member.
- Adding a 5th active member to a 4-seat family fails (CHECK).

### Backend tests (`tests/test_family_storage.py`)

- `load_family_for_user` returns owner's family.
- `load_family_for_user` returns member's family.
- `list_members` returns active members only by default; `include_removed=True` opts in.
- `add_member` enforces seat cap (returns error at 5th).
- `add_member` rejects duplicate emails for same family.
- `claim_invite` flips status only when token matches.
- `claim_invite` rejects expired tokens (>30 days).
- `remove_member` is soft-delete; row stays for audit.

### Entitlement tests (`tests/test_family_entitlements.py`)

- Member of active Family Pro family resolves to `family_pro` plan.
- Member of `canceled` Family Pro resolves to NULL (Free).
- Owner's own subscription wins over family membership (a Solo Pro buyer who's also in a family stays Solo Pro).
- Past-due Family Pro: members keep Pro.
- Removed member: NULL plan.

### Dashboard render tests (`tests/test_family_dashboard_render.py`)

- State A (3 members) renders 3 cards + summary strip.
- State B (0 members) renders empty state with CTA.
- State C (1 member) renders single centered card, no strip.
- State D (4 members) renders 4-card grid + "household full" line, no add-row.
- Stale member renders red badge + nudge block.
- Self-as-player card renders YOU pill.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| RLS matrix bug — kid sees another family's data | Test harness covers the matrix explicitly. Manual review of every RLS policy before applying migration. |
| Stripe webhook fails to create `families` row | Webhook handler is idempotent (lookup-or-create). Add a backfill helper `provision_family_for_subscription(sub_id)` runnable from the Streamlit admin panel. |
| Existing Family Pro buyers (if any) don't get a family row | Backfill SQL: for every active Family Pro `subscriptions` row, create a matching `families` row + `family_members` owner row. |
| Invite link forwarded to wrong person | Token is single-use and stored as hash; even if forwarded, the right person sees their email in the claim screen and can choose not to accept. |
| Member removed → swing history orphaned | History stays on `players` row; member's plan reverts to Free which caps NEW uploads but preserves history. |
| Parent revokes Pro mid-session → kid still has Pro UI | Plan resolution happens server-side every render via the view; kid's NEXT request returns Free. Mid-session is acceptable (worst case: the kid finishes the one swing they're analyzing). |
| Display-name collisions ("Jake" twice) | UI shows age + position to disambiguate; we don't enforce unique names. |
| "Nudge Owen" button has no backend in v1 | Render the button + show a "Nudge sent ✓" success state but log to telemetry only. Real push delivery in v1.1. |

## Effort estimate

| Phase | Hours | Notes |
|---|---|---|
| Schema migration + RLS policies + view | 3 | Includes test harness |
| `family_storage.py` + tests | 4 | CRUD + queries |
| Entitlement propagation in `_resolve_plan_id` + tests | 2 | |
| Stripe webhook update + idempotency | 2 | |
| `family_dashboard.py` (4 states) | 4 | Translate v2 HTML to Streamlit |
| `family_invite_page.py` | 2 | Includes email send via Supabase auth |
| Settings page integration | 2 | List members + add-member form + remove |
| Routing + nav | 1 | bl_edge_chrome.py + app.py routes |
| Preview harness + Playwright | 1 | Same pattern as preview_pricing.py |
| Visual QA pass + iteration | 2 | |
| Final code review + fixes | 2 | |
| **Total** | **~25 hours** | Single engineer end-to-end |

## Open questions — resolved (all locked)

| Q | Decision |
|---|---|
| Default page for Family Pro parent on login? | Their own `/dashboard`. Family is opt-in via nav. |
| Display name format? | "<Owner's first name>'s Household" |
| Maximum seats? | Hard-coded 4 in plan_pricing.py. Enforced at DB layer. |
| Stale threshold? | >10 days without a swing |
| Magic link expiry? | 30 days |
| Single-use invite token? | Yes — hashed, cleared on claim |
| Show ALL household swings in summary strip, or only player-tagged? | All household |
| Nudge button — push or email or both? | v1: log to telemetry, show "Sent ✓". v1.1: in-app push (no email/SMS). |
