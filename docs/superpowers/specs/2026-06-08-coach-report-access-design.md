# Coach Report Access (parent-opt-in) — Design

> Date: 2026-06-08
> Status: SPEC — not yet built. Blocked on Logan's COPPA/consent decision (§5).
> Related: [facility-coach-mode-design](2026-06-04-facility-coach-mode-design.md)

**Goal:** Let a facility owner (coach) open a rostered player's full swing
report from the roster dashboard — gated on explicit parent consent, scoped to
active members of an active facility, and revocable — without weakening the
player's ownership of their own account/data.

---

## 1. The gap today

The roster UI is already wired: every card has a "View [name]'s Report →"
button (`family_dashboard.py:848-855`) that sets `viewing_member_id` and routes
to the report page. It is a **no-op for a coach by design**, because:

- In a *family*, the parent account owns every child row (same `user_id`), so
  Supabase RLS lets the report page read them.
- In a *facility*, each rostered kid is a **separate auth user**. The coach is
  not the owner, so RLS blocks every read of that kid's swings/reports. The
  report renders empty.

So this is purely a **data-access + consent** problem. No new UI is required
beyond a consent control and a couple of empty/blocked states.

## 2. Principle: consent is the gate, not facility membership

Joining a facility grants **sponsorship** (the kid gets Pro). It must NOT, by
itself, grant the coach the right to read a minor's biometric swing data and
report. Those are separate grants:

- **Sponsorship** = facility pays → kid gets Pro. (already built)
- **Report visibility** = parent explicitly opts in → coach can read. (this spec)

A kid can be sponsored with report-sharing OFF. The coach still sees roster
presence + activity recency (already non-sensitive: name, last-active, score
trend), but NOT the report internals until the parent flips sharing on.

## 3. Data model

Add an explicit, per-membership consent flag rather than overloading anything:

```sql
ALTER TABLE public.facility_members
  ADD COLUMN report_sharing  boolean      NOT NULL DEFAULT false,
  ADD COLUMN sharing_set_by  uuid,            -- the parent/guardian auth user who toggled it
  ADD COLUMN sharing_set_at  timestamptz;
```

- Default **false** — fail closed. No silent exposure of a minor's report.
- The flag lives on the membership row, so leaving the facility (`left_at`) or
  re-joining naturally resets the relationship; a fresh join requires fresh
  consent.

## 4. Access path (SECURITY DEFINER RPC, not broad RLS)

Prefer a narrow RPC the report page calls for a non-owned player, over opening
new SELECT policies on the swings/reports tables (smaller blast radius, easier
to audit, no risk of leaking to sibling queries).

```sql
-- Returns a rostered player's report payload to the facility OWNER only,
-- and ONLY when consent + active sponsorship both hold.
CREATE OR REPLACE FUNCTION public.coach_get_player_report(p_player_id uuid)
RETURNS TABLE (...report columns...) AS $$
DECLARE v_uid uuid := auth.uid();
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM public.facility_members m
      JOIN public.facilities f ON f.id = m.facility_id
     WHERE m.player_id = p_player_id
       AND m.left_at IS NULL
       AND m.report_sharing = true          -- parent opted in
       AND f.owner_user_id = v_uid          -- caller owns the facility
       AND f.status = 'active'              -- facility is paid/active
  ) THEN
    RAISE EXCEPTION 'coach_get_player_report: not authorized';
  END IF;
  RETURN QUERY SELECT ... FROM <swing/report tables> WHERE player_id = p_player_id ...;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.coach_get_player_report(uuid) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.coach_get_player_report(uuid) TO authenticated;
```

All four conditions must hold on every read: membership active, consent on,
caller is the owner, facility active. Drop any one and the read fails closed.

A second RPC `set_report_sharing(p_member_id uuid, p_on boolean)` lets the
**parent** (the player's account owner) toggle consent, authorized by
`player_id IN (SELECT id FROM players WHERE user_id = auth.uid())`. The coach
can never set it.

## 5. OPEN DECISION (Logan) — the consent UX

This is the actual blocker. Pick the consent model:

**Option A — Parent toggle at/after join (recommended).** When a parent joins
their kid to a facility, show a clear opt-in: "Share [kid]'s reports with
[facility]'s coaches?" Default OFF. Editable anytime in player settings. Simple,
honest, COPPA-clean (verifiable parental consent, revocable).

**Option B — Facility-wide consent at join code entry.** One toggle when
entering the join code covers all the parent's kids. Fewer clicks, slightly less
granular.

**Option C — Coach requests, parent approves.** Coach taps a locked card →
"Request access" → parent gets a prompt → approves. Most explicit, most
friction, best paper trail.

Recommendation: **A**. It's the cleanest consent record per child, matches the
COPPA "guardian owns the account" model already shipped, and is the least
surprising to parents. Needs a lawyer eyeball on the consent copy before launch
(consistent with the open legal-review item on the COPPA work).

## 6. Report page wiring

In the report/sessions dispatch, when `viewing_member_id` is set and is **not**
an account the current user owns:
- Call `coach_get_player_report(viewing_member_id)`.
- On success → render the report read-only (no edit/delete controls; coach is a
  viewer, not the owner).
- On the authorization exception → render a "Report sharing is off for this
  player. Ask their parent to enable it in their BarrelLabs settings." state on
  the card / report shell (never a stack trace).

## 7. Out of scope (v1)

- Coach editing/annotating a player's report (view-only first).
- Coach-to-parent messaging beyond the existing "nudge."
- Per-report (vs per-membership) sharing granularity.

## 8. Build size

Once §5 is decided: ~1 migration (1 column-add + 2 RPCs), ~1 settings toggle
(parent side), ~1 report-page branch + blocked-state, plus tests locking the
four-condition gate and the fail-closed default. Roughly an afternoon. The
engineering is small; the decision and consent copy are the real work.
