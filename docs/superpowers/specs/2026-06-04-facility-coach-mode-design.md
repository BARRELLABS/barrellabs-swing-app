# Facility / Coach Mode — Design Spec

**Date:** 2026-06-04
**Status:** Approved design → ready for implementation plan
**Author:** Logan + Claude (brainstorming session)

---

## 1. Why we're building this

Logan wants to cold-email ~10–20 youth baseball/softball hitting facilities
offering a discounted "early access" price, and to walk into facility
conversations (e.g. Hitz) with a real product, not vapor. The existing
`coach_pro` plan ($79.99/mo, 20 seats) is **sold but unbuilt** — there is no
roster, no branding, no facility onboarding behind it. This spec defines the
v1 "Facility / Coach Mode" that makes that tier real.

### Strategic frame (the decisions behind the design)
- **Not white-label (for v1).** The BarrelLabs-branded report is the growth
  engine (the viral MLB-comp card, the consumer flywheel). White-label is
  offered later as a *paid custom add-on* to facilities that ask, not as the
  default. Default reports stay BarrelLabs-branded with the facility's logo
  added.
- **BarrelLabs is complementary to HitTrax, not competitive.** HitTrax = the
  *outcome* (exit velo, launch angle). BarrelLabs = the *cause* (body
  mechanics, sequencing, what to fix). The pitch is "the *why* behind your
  HitTrax numbers."
- **Self-onboard, not coach-managed profiles.** A facility may eventually have
  *hundreds* of kids. No coach hand-creates 300 profiles, and BarrelLabs
  should not own 300 coach-managed seats (support + COPPA burden). Instead the
  facility is an **org that kids/parents join via a code**; each kid owns their
  own account (and is therefore also a consumer user feeding the flywheel). The
  coach gets a **read-mostly roster view** across everyone linked to the
  facility.
- **Engine-first sequencing.** Facility owners are hitting experts who will
  spot a bad analysis instantly. The MLB-reference rebuild (already in flight)
  and single-swing accuracy must be trustworthy **before** the cold-email
  campaign. This feature is built in parallel but the outreach is gated on the
  engine being credible.

### Non-goals (explicitly deferred to v2+)
- Full white-label (custom domain/colors) — paid custom add-on, later.
- Multi-coach hierarchy / sub-coach permissions within one facility.
- Team/group splits inside a facility roster.
- Drill *assignment as homework* + completion tracking.
- Hundreds-scale billing optimization (bulk seat sponsorship math).
- Parent self-serve dashboards (parents get a shareable report link in v1; the
  existing Family Pro flow can be bolted on later if a facility asks).

---

## 2. The model (data + relationships)

```
FACILITY (org)
  ├─ id, name, logo, join_code, owner_user_id (the coach), plan/billing
  └─ MEMBERSHIPS (kid ↔ facility links)
        ├─ player A  (player owns their own BarrelLabs account + data)
        ├─ player B
        └─ player C  ... (scales to hundreds)

COACH (facility owner login)
  └─ Roster view: read-mostly across all linked players
```

- A **Facility** is a new org entity: `id`, `name`, `logo_url`, `join_code`
  (short shareable code/link), `owner_user_id`, plan/billing fields.
- A **Membership** links a player's existing user/player profile to a facility.
  The player **owns their own account and swing data** — the facility link
  grants the coach a roster view, not ownership.
- The **coach** is the facility `owner_user_id`. v1 = single coach per facility
  (multi-coach is v2).
- **Billing is decoupled from the link.** Whether the family pays their own
  consumer sub, the facility sponsors seats, or both, is a billing-layer
  decision (see §6) and does NOT change the membership model. v1 ships with a
  single, simple billing path (TBD by pricing research — see §6); the model
  supports either without rework.

### Reuse vs. new
- **Reuse:** the roster card UI, sparkline, stale/nudge logic, and
  `get_member_summary()` from `family_dashboard.py` / `family_storage.py`. The
  family dashboard *is* a roster view; we generalize it from "household ≤4" to
  "facility ≤hundreds."
- **Reuse:** the swing report renderer (`swing_report_dashboard_preview.py`)
  for the branded + shareable report.
- **New:** the facility org entity + join-code self-onboard flow; the coach
  roster page (scaled, searchable); facility-logo branding in the report
  header; the shareable "send to parent" report link; Coach Pro checkout
  wiring.

---

## 3. Components (v1 scope)

### 3.1 Facility account + join code
- A coach can create/own a **Facility** (name + logo upload).
- The facility has a **join code / link** the coach shares.
- A kid/parent enters the code (at signup or in settings) → a **Membership**
  links them to the facility. They keep their own login and data.
- COPPA: unchanged from the existing minor-account handling — the player's
  account follows the existing consumer/household consent path; the facility
  link adds no new minor-data ownership by BarrelLabs.

### 3.2 Coach roster dashboard
- Generalize the family dashboard to a facility roster: **N players** (not ≤4),
  **searchable / filterable** (by name; active vs. quiet).
- Per-player card: latest score, trend, "needs attention" (stale) flag,
  sparkline — reusing existing card components.
- Coach can open any linked player's report (read-only) to use in a lesson.
- Performance: the roster must paginate / lazy-load so a few hundred players
  don't render as one giant column wall (the family grid currently caps at 4
  cols — needs a scalable layout + pagination).

### 3.3 Branded + shareable report
- Report header shows **BarrelLabs branding + the facility's logo** (light
  touch — not a reskin).
- Every report gets a **"Send to parent" shareable link** (public, read-only
  URL) and/or PDF. This is the retention deliverable — the parent sees the
  report at home, which is the facility's reason-to-re-enroll.
- The public link must not require login and must not leak other players' data.

### 3.4 Coach Pro checkout (wire up the existing tier)
- The `coach_pro` tier exists in `entitlements.py` / `plan_pricing.py` but has
  no real product or validated price. Wire its checkout to create/activate a
  Facility, applying the **early-access discount price** (final numbers from
  the pricing-research agent — see §6).

---

## 4. Data flow

1. **Coach onboards:** signs up / upgrades → creates Facility (name, logo) →
   gets join code. Coach Pro checkout via existing Stripe flow.
2. **Kid joins:** enters join code at signup or in settings → Membership row
   links player → facility. Player uses BarrelLabs normally (films, gets
   reports), owns their data.
3. **Coach reviews:** opens roster → sees all linked players' latest
   scores/trends/flags → opens any player's report for a lesson.
4. **Parent retention loop:** coach (or the player) taps "Send to parent" on a
   report → parent opens the public branded link at home.

---

## 5. Error handling & edge cases
- Backend not configured / query error → roster falls back to empty/safe
  states (follow the `family_storage` "safe by design" pattern — never crash).
- Invalid / expired join code → clear error, no partial link.
- A player linked to a facility who later cancels their own sub → still appears
  on the roster but flagged appropriately (billing edge — final behavior tied
  to §6 billing decision).
- Public report link → read-only, single-report scoped, no auth, no data leak
  across players.
- Large roster → pagination/lazy-load; no unbounded render.

---

## 6. Open item: pricing & billing (research in flight)
A background research agent is determining:
- **Early-access (launch discount)** facility price
- **Full** facility price
- The **model** (per-location flat vs. per-athlete/seat vs. tiered by roster
  size; monthly vs annual)
- Whether families pay their own consumer subs, the facility sponsors seats, or
  both.

The membership model in §2 is deliberately billing-agnostic so either outcome
slots in without rework. Final numbers + model get folded into §3.4 and the
implementation plan before build.

---

## 7. Build sequence (high level — detailed plan comes next)
1. Facility org entity + join-code self-onboard (the new primitive).
2. Generalize family dashboard → scalable searchable coach roster.
3. Facility-logo branding + public shareable report link.
4. Wire Coach Pro checkout to the early-access price (pending §6).
5. (Parallel, not part of this feature) finish the engine/MLB-reference
   trust work — the gate on actually sending the cold emails.

---

## 8. Reused/affected files (initial map — confirm during planning)
- `family_storage.py` / `family_dashboard.py` — generalize household → facility
  roster; the new facility entity likely lives in a sibling
  `facility_storage.py` to keep concerns separate.
- `entitlements.py` / `plan_pricing.py` — Coach Pro caps + early-access price.
- `swing_report_dashboard_preview.py` — logo branding + shareable-link entry.
- `auth.py` — household-player helpers are the pattern for facility membership.
- `app.py` — routing for the new coach-roster + join-code pages.
- New: public shareable-report route (no-auth, single-report scoped).
