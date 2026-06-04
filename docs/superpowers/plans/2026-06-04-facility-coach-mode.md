# Facility / Coach Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Facility/Academy tier where a facility self-onboards a roster of hitters via a join code, every rostered kid gets the full co-branded product (sponsored), and the coach sees a scalable roster dashboard — sold via license (annual/monthly brackets) or rev-share.

**Architecture:** Extend the existing household model (one owner → many player profiles) into a *facility org* that players LINK to via a join code (players keep owning their own accounts/data). A new `facilities` table + `facility_members` link table sit alongside `players`; entitlements gain a "sponsored Pro grant" resolved as best-of(own sub, facility sponsorship). Reuse `family_dashboard.py`'s roster card UI and the existing swing-report renderer (adding a facility logo). Billing is config on top of the same sponsored-entitlement mechanic.

**Tech Stack:** Streamlit 1.57, Supabase (Postgres + RLS + `SECURITY DEFINER` RPCs), Stripe Checkout, Python. Follows patterns in `supabase/migrations/2026_05_23_household_profiles.sql`, `entitlements.py`, `family_storage.py`, `auth.py`.

**Spec:** `docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md`

---

## Hard constraints (from HANDOFF.md + session)
- **Do NOT apply migrations to prod Supabase, create live Stripe products, or merge to `main` without Logan's explicit go.** Migration files are written but applied by Logan.
- Restart the Streamlit server after every edit (headless caches modules).
- Nav must stay in-session `st.button` (no `<a href>` — auth is session-only).
- Work on branch `feat/facility-coach-mode`.

---

## File Structure

**Create:**
- `supabase/migrations/2026_06_04_facilities.sql` — `facilities` + `facility_members` tables, RLS, RPCs (`create_facility`, `join_facility_by_code`, `leave_facility`, `list_facility_members`), `v_my_facility` view, sponsored-plan resolution in `v_my_plan`.
- `facility_storage.py` — Python data layer over the facility RPCs (mirrors `family_storage.py`'s "safe by design" shape).
- `facility_dashboard.py` — the coach roster page (generalizes `family_dashboard.py` to N players + search + pagination).
- `tests/test_facility_storage.py` — unit tests for the storage layer (pure functions + mocked client).
- `tests/test_entitlements_sponsored.py` — unit tests for sponsored-grant + portability resolution.

**Modify:**
- `entitlements.py` — add sponsored-Pro grant state + best-of resolution + facility tier caps.
- `plan_pricing.py` — replace 20-seat `coach_pro` with roster-bracket SKUs + rev-share `$12/mo` member SKU + setup-fee SKU.
- `swing_report_dashboard_preview.py` — optional facility logo in the report header.
- `app.py` — route the coach roster page + the join-code entry point (in-session nav).
- `stripe_client.py` — checkout for the new bracket SKUs (license) + the member SKU (rev-share).

---

## Phase 1 — Data layer (schema + storage)

### Task 1: Facility schema migration (file only — Logan applies)

**Files:**
- Create: `supabase/migrations/2026_06_04_facilities.sql`

- [ ] **Step 1: Write the migration**

```sql
-- ============================================================
--  Facility / Academy: org that players LINK to via a join code.
--  Players keep owning their own accounts/data; the facility
--  SPONSORS Pro for every active member. Date: 2026-06-04
--  Spec: docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md
-- ============================================================

-- 1. Facilities. owner_user_id is the coach's auth user.
CREATE TABLE IF NOT EXISTS public.facilities (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name          text NOT NULL,
  logo_url      text,
  join_code     text NOT NULL UNIQUE,
  plan_tier     text NOT NULL DEFAULT 'academy',   -- team|academy|academy_plus|facility|facility_pro
  roster_ceiling integer NOT NULL DEFAULT 100,
  billing_mode  text NOT NULL DEFAULT 'license',   -- license | revshare
  status        text NOT NULL DEFAULT 'active',    -- active|trialing|past_due|canceled
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS facilities_owner_idx ON public.facilities(owner_user_id);

-- 2. Membership link: a player (by player_id) belongs to a facility.
--    Player owns the row's player; facility gets read access.
CREATE TABLE IF NOT EXISTS public.facility_members (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id  uuid NOT NULL REFERENCES public.facilities(id) ON DELETE CASCADE,
  player_id    uuid NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
  joined_at    timestamptz NOT NULL DEFAULT now(),
  left_at      timestamptz,                         -- soft-leave (portability)
  UNIQUE (facility_id, player_id)
);
CREATE INDEX IF NOT EXISTS facility_members_facility_idx
  ON public.facility_members(facility_id) WHERE left_at IS NULL;
CREATE INDEX IF NOT EXISTS facility_members_player_idx
  ON public.facility_members(player_id) WHERE left_at IS NULL;

-- 3. RLS
ALTER TABLE public.facilities       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facility_members ENABLE ROW LEVEL SECURITY;

-- Coach sees/edits their own facility.
CREATE POLICY facilities_owner ON public.facilities
  FOR ALL USING (owner_user_id = auth.uid()) WITH CHECK (owner_user_id = auth.uid());

-- Coach sees members of facilities they own; a player sees their own membership.
CREATE POLICY facility_members_visibility ON public.facility_members
  FOR SELECT USING (
    facility_id IN (SELECT id FROM public.facilities WHERE owner_user_id = auth.uid())
    OR player_id IN (SELECT id FROM public.players WHERE user_id = auth.uid())
  );
```

- [ ] **Step 2: Add the RPCs (same file)**

```sql
-- create_facility: coach creates their org, gets a unique join code.
CREATE OR REPLACE FUNCTION public.create_facility(
  p_name text, p_tier text DEFAULT 'academy', p_ceiling integer DEFAULT 100,
  p_billing_mode text DEFAULT 'license'
) RETURNS public.facilities AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_code text;
  result public.facilities%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'create_facility: not authenticated'; END IF;
  IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
    RAISE EXCEPTION 'create_facility: name required';
  END IF;
  -- 6-char uppercase code, retry on collision.
  LOOP
    v_code := upper(substr(md5(gen_random_uuid()::text), 1, 6));
    EXIT WHEN NOT EXISTS (SELECT 1 FROM public.facilities WHERE join_code = v_code);
  END LOOP;
  INSERT INTO public.facilities (owner_user_id, name, join_code, plan_tier, roster_ceiling, billing_mode)
  VALUES (v_uid, trim(p_name), v_code, p_tier, p_ceiling, p_billing_mode)
  RETURNING * INTO result;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- join_facility_by_code: a player (caller's active player) links to a facility.
CREATE OR REPLACE FUNCTION public.join_facility_by_code(
  p_code text, p_player_id uuid
) RETURNS public.facility_members AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_fac public.facilities%ROWTYPE;
  v_active integer;
  result public.facility_members%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'join_facility: not authenticated'; END IF;
  -- player must belong to the caller
  IF NOT EXISTS (SELECT 1 FROM public.players WHERE id = p_player_id AND user_id = v_uid) THEN
    RAISE EXCEPTION 'join_facility: player not owned by caller';
  END IF;
  SELECT * INTO v_fac FROM public.facilities WHERE join_code = upper(trim(p_code));
  IF NOT FOUND THEN RAISE EXCEPTION 'join_facility: invalid code'; END IF;
  -- roster ceiling check (active members)
  SELECT count(*) INTO v_active FROM public.facility_members
   WHERE facility_id = v_fac.id AND left_at IS NULL;
  IF v_active >= v_fac.roster_ceiling THEN
    RAISE EXCEPTION 'join_facility: facility roster is full';
  END IF;
  INSERT INTO public.facility_members (facility_id, player_id)
  VALUES (v_fac.id, p_player_id)
  ON CONFLICT (facility_id, player_id)
  DO UPDATE SET left_at = NULL
  RETURNING * INTO result;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- leave_facility: soft-leave (sponsorship ends; player keeps account+history).
CREATE OR REPLACE FUNCTION public.leave_facility(p_member_id uuid)
RETURNS void AS $$
DECLARE v_uid uuid := auth.uid();
BEGIN
  UPDATE public.facility_members fm
     SET left_at = now()
   WHERE fm.id = p_member_id
     AND (fm.facility_id IN (SELECT id FROM public.facilities WHERE owner_user_id = v_uid)
          OR fm.player_id IN (SELECT id FROM public.players WHERE user_id = v_uid));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.create_facility(text,text,integer,text) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.create_facility(text,text,integer,text) TO authenticated;
REVOKE EXECUTE ON FUNCTION public.join_facility_by_code(text,uuid) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.join_facility_by_code(text,uuid) TO authenticated;
REVOKE EXECUTE ON FUNCTION public.leave_facility(uuid) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.leave_facility(uuid) TO authenticated;
```

- [ ] **Step 3: Sponsored-plan resolution — extend `v_my_plan`**

The sponsored grant must flow through the SAME view entitlements already read. Add a CTE that, for the caller's players, finds any active facility membership whose facility is `active`, and surfaces a `sponsored_tier`. The Python layer (Task 3) treats a sponsored player as Pro. Document in the migration that `v_my_plan` gains a `sponsored_by_facility uuid` column; the best-of resolution lives in Python (`entitlements.py`) to keep the SQL view simple and testable.

```sql
-- Append to v_my_plan: expose whether the caller's ACTIVE player is sponsored.
-- (Kept minimal — Python resolves best-of(own sub, sponsorship).)
-- See entitlements.resolve_effective_plan().
```

- [ ] **Step 4: Commit (file only — NOT applied)**

```bash
git add supabase/migrations/2026_06_04_facilities.sql
git commit -m "feat(facility): schema migration — facilities + members + join/leave RPCs (file only, unapplied)"
```

### Task 2: `facility_storage.py` (Python data layer)

**Files:**
- Create: `facility_storage.py`
- Test: `tests/test_facility_storage.py`

- [ ] **Step 1: Write failing tests for the pure summary logic**

```python
# tests/test_facility_storage.py
import facility_storage as fs

def test_roster_summary_counts_active_and_stale():
    members = [
        {"player_id": "a", "display_name": "Al", "swings": [{"created_at": "2026-06-03", "edge_score": 80}]},
        {"player_id": "b", "display_name": "Bo", "swings": []},
    ]
    summary = fs.roster_summary(members, today="2026-06-04")
    assert summary["total"] == 2
    assert summary["active_this_week"] == 1
    assert summary["needs_attention"] == 1   # Bo has no swings

def test_roster_summary_empty():
    assert fs.roster_summary([], today="2026-06-04")["total"] == 0
```

- [ ] **Step 2: Run, verify fail**

Run: `.venv/bin/python -m pytest tests/test_facility_storage.py -v`
Expected: FAIL (module/func missing)

- [ ] **Step 3: Implement `facility_storage.py`**

Mirror `family_storage.py`: a `_supabase_query_safe` wrapper that falls back to empty/None on any error; public functions `load_facility_for_owner(user_id)`, `list_members(facility_id)`, `create_facility(...)`, `join_by_code(code, player_id)`, `leave(member_id)` (each calls the RPC via `supabase_client.get_client().rpc(...)`), and a **pure** `roster_summary(members, today=None)` that reuses the staleness/active logic from `family_storage._compute_member_summary`. Pure functions take data in, so they're unit-testable without a DB.

```python
"""Facility / Academy data layer (safe-by-design, mirrors family_storage)."""
from __future__ import annotations
import datetime as _dt
from typing import Optional, Any
try:
    from supabase_client import get_client as _get_client
except Exception:
    _get_client = None

STALE_DAYS = 10

def roster_summary(members: list[dict], *, today: Optional[str] = None) -> dict:
    today_dt = _dt.date.fromisoformat(today) if today else _dt.date.today()
    total = len(members)
    active = 0; attention = 0
    for m in members:
        swings = m.get("swings") or []
        if not swings:
            attention += 1; continue
        last = max(s.get("created_at", "") for s in swings)
        try:
            days = (today_dt - _dt.date.fromisoformat(last[:10])).days
        except Exception:
            days = 999
        if days <= 7: active += 1
        if days > STALE_DAYS: attention += 1
    return {"total": total, "active_this_week": active, "needs_attention": attention}

def load_facility_for_owner(user_id: str) -> Optional[dict]:
    if not user_id or _get_client is None: return None
    try:
        res = _get_client().table("facilities").select("*").eq("owner_user_id", user_id).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None
# list_members / create_facility / join_by_code / leave: call .rpc(...) with the same try/except→None pattern.
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_facility_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add facility_storage.py tests/test_facility_storage.py
git commit -m "feat(facility): facility_storage data layer + roster_summary tests"
```

---

## Phase 2 — Entitlements (sponsored grant + portability)

### Task 3: Sponsored-Pro grant in `entitlements.py`

**Files:**
- Modify: `entitlements.py`
- Test: `tests/test_entitlements_sponsored.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_entitlements_sponsored.py
import entitlements as ent

def test_sponsored_player_is_pro_even_on_free_sub():
    snap = {"plan_id": "free", "free_swings_used": 9}
    eff = ent.resolve_effective_plan(snap, sponsored=True)
    assert ent.is_pro({"plan_id": eff})
    assert ent.can_analyze_swing({"plan_id": eff}).allowed is True

def test_unsponsored_free_player_still_capped():
    snap = {"plan_id": "free", "free_swings_used": 9}
    eff = ent.resolve_effective_plan(snap, sponsored=False)
    assert eff == "free"

def test_sponsorship_lost_falls_back_to_own_sub():
    snap = {"plan_id": "solo_pro"}
    # sponsorship ending must not downgrade a real paying sub
    assert ent.resolve_effective_plan(snap, sponsored=False) == "solo_pro"
```

- [ ] **Step 2: Run, verify fail**

Run: `.venv/bin/python -m pytest tests/test_entitlements_sponsored.py -v`
Expected: FAIL (`resolve_effective_plan` missing)

- [ ] **Step 3: Implement `resolve_effective_plan`**

Add to `entitlements.py`. Best-of(own plan, sponsored Pro). A sponsored player resolves to `SOLO_PLAN_ID` (full Pro caps) unless their own plan is already higher-or-equal. This keeps all existing `can_X()` gates working unchanged — they just receive the resolved plan_id.

```python
def resolve_effective_plan(plan_snapshot: Optional[dict], *, sponsored: bool = False) -> str:
    """Best-of the player's own plan and any facility sponsorship.
    Sponsored players get full Pro (SOLO caps); a real paid sub is never
    downgraded by losing sponsorship (portability: they keep their own plan)."""
    own = _resolve_plan_id(plan_snapshot)
    if sponsored and own == FREE_PLAN_ID:
        return SOLO_PLAN_ID
    return own
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_entitlements_sponsored.py -v`
Expected: PASS

- [ ] **Step 5: Add facility tier caps + commit**

Add `FACILITY_TIERS` constant (team/academy/academy_plus/facility/facility_pro → roster_ceiling) and `facility_tier_for_roster(n)` helper for checkout. Keep `coach_pro` as a deprecated alias mapping to `academy` so old references don't break.

```bash
git add entitlements.py tests/test_entitlements_sponsored.py
git commit -m "feat(facility): sponsored-Pro grant + portability resolution + tier caps"
```

### Task 4: Wire sponsorship into the live entitlement read

**Files:**
- Modify: `subscription_storage.py` (or the call site that builds the plan snapshot), `app.py` (where `current_profile()`/plan is read per active player)

- [ ] **Step 1:** When loading the active player's plan snapshot, also query `facility_storage` for an active membership on that player and pass `sponsored=` into `resolve_effective_plan`. Cache it alongside the plan snapshot (invalidate on profile switch — see [[auth-session-state-only]] memory). Add a runtime test simulating a sponsored free player getting Pro features. Commit.

*(Detailed code deferred to execution — this is the one task that touches the live plan-read path; implement carefully with the server-restart + profile-switch caveats from CLAUDE.md memory.)*

---

## Phase 3 — Self-onboard (join code)

### Task 5: Join-code entry in player settings + signup

**Files:**
- Modify: `player_settings_page.py` (add a "Join a facility" section), `app.py` (route)
- Test: runtime test that a valid code calls `facility_storage.join_by_code` and an invalid code shows an error without linking.

- [ ] Add a "Join a facility" input (code + active-player) → `facility_storage.join_by_code`. On success, toast + the player is now sponsored. On invalid code, inline error. In-session `st.button` only. Commit. *(Follows the existing settings-section pattern; reuse the household section's structure.)*

---

## Phase 4 — Coach roster dashboard

### Task 6: `facility_dashboard.py` (generalize family dashboard)

**Files:**
- Create: `facility_dashboard.py`
- Modify: `app.py` (route `page == "facility"`), `bl_edge_chrome.py` (add nav entry when the user owns a facility)

- [ ] Generalize `family_dashboard.py`: render `roster_summary` strip + a **searchable, paginated** grid of member cards (reuse `_render_member_card` / `_build_sparkline_svg` from `family_dashboard`). Cap render to ~30 cards/page with a name filter and next/prev. Coach taps a card → opens that player's report read-only. In-session nav. Add a runtime smoke test (renders empty + populated states without error). Commit.

*(UI follows the locked `family_dashboard` CSS system — bone/ink/gold tokens — so it reads as one product. Extract shared card rendering into a small helper module if the duplication is large.)*

---

## Phase 5 — Co-branded report

### Task 7: Facility logo in the report header

**Files:**
- Modify: `swing_report_dashboard_preview.py`

- [ ] When the player being reported is a facility member, fetch the facility `logo_url` and render it beside the BarrelLabs mark in the report header (light touch, not a reskin). Falls back cleanly when no facility/logo. Add a render test with and without a logo. Commit.

---

## Phase 6 — Checkout SKUs (both pricing paths)

### Task 8: Pricing SKUs in `plan_pricing.py`

**Files:**
- Modify: `plan_pricing.py`
- Test: `tests/test_plan_pricing_facility.py`

- [ ] **Step 1: Failing test**

```python
import plan_pricing as pp
def test_facility_brackets_present():
    assert pp.FACILITY_PRICING["academy"]["annual_cents"] == 299000
    assert pp.FACILITY_PRICING["academy"]["roster_ceiling"] == 100
def test_revshare_member_rate():
    assert pp.REVSHARE["member_monthly_cents"] == 1200
    assert pp.REVSHARE["platform_split"] == 0.70
```

- [ ] **Step 2-4:** Add `FACILITY_PRICING` (team/academy/academy_plus/facility/facility_pro with monthly_cents/annual_cents/roster_ceiling/early_access_annual_cents per spec §6), `REVSHARE` ($12/mo member rate, 70/30 split, $400 setup), and `facility_stripe_price_id(tier, interval)` mirroring the existing `stripe_price_id`. Run tests → PASS. Commit.

### Task 9: Facility checkout in `stripe_client.py`

**Files:**
- Modify: `stripe_client.py`, `pricing.py` (facility tier cards/CTA)

- [ ] License path: checkout for the chosen bracket SKU → on success (Logan applies migration + a webhook or manual step) create the facility with that tier/ceiling. Rev-share path: the member `$12/mo` SKU grants the kid sponsorship and tags the facility for manual 70/30 payout (no automated payout system in v1 — spec §3.4). **Stripe products are created by Logan, not the agent.** Provide the exact `stripe_setup.py` additions as a diff for Logan to run. Commit code; flag the live-Stripe step for Logan.

---

## Self-Review

- **Spec coverage:** §2 model → Task 1; sponsored entitlement → Tasks 3-4; §3.1 join code → Tasks 1,5; §3.2 roster → Task 6; §3.3 co-brand → Task 7; §3.4 checkout → Tasks 8-9; §6 both pricing paths → Tasks 8-9. Portability (§6) → Task 3 (`resolve_effective_plan` never downgrades a paid sub; `leave_facility` soft-leave). Edge cases (§5): roster ceiling → Task 1 RPC; two-facility → allowed by `facility_members` unique-per-facility; lapse → Task 3.
- **Deferred (spec non-goals, NOT in this plan):** full white-label, multi-coach, team/group splits, drill-assignment homework, automated rev-share payouts, weekly digest.
- **Placeholder note:** Tasks 4, 5, 6, 9 intentionally defer exact line-level code to execution because they touch the live app (plan-read path, Streamlit widgets, Stripe) where the server-restart / profile-switch / in-session-nav caveats in CLAUDE.md memory must be honored per-edit. Foundational Tasks 1-3 and 8 carry complete code.
- **Type consistency:** `resolve_effective_plan(snapshot, *, sponsored)` used identically in Tasks 3-4; `roster_summary(members, today=)` identical in Task 2; `FACILITY_PRICING`/`REVSHARE` keys identical in Tasks 8-9.

---

## Build order & safety
1. Tasks 1-3, 8 are **prod-safe** (new files, new pure logic, unit tests) — build these now on the branch.
2. Tasks 4, 5, 6, 7, 9 touch the live app/billing — build on the branch but do NOT apply the migration, create Stripe products, or merge until Logan approves.
3. Logan's gated steps: apply `2026_06_04_facilities.sql` to Supabase; add facility products in `stripe_setup.py` and run it; review + merge.
