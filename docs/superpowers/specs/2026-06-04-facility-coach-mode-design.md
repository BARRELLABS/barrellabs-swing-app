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
- **Self-onboard, not coach-managed profiles.** A facility may have *hundreds
  or thousands* of kids. No coach hand-creates that many profiles. Instead the
  facility is an **org that kids/parents join via a code**; each kid owns their
  own account (data is portable — see §6). The coach gets a **read-mostly
  roster view** across everyone linked.
- **Facility sponsors everyone (Model B) — every rostered kid gets the FULL
  product**, co-branded with the academy logo, priced in flat roster-size
  brackets (§6). This is the decided business model; the facility is an
  *additive* B2B acquisition channel, not a cannibalization of consumer subs,
  and departing sponsored kids convert to full-price direct subs via account
  portability.
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
- Multi-site / League (1,000+) custom tier — quote-only, later.
- Weekly cohort digest email — nice retention loop, but v2 unless cheap.

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
- **The facility sponsors every rostered kid** (Model B, §6): a linked player
  is granted **full Pro-equivalent entitlement for as long as the membership is
  active**, regardless of whether they ever had their own sub. Billing is at the
  facility level by roster bracket — the family pays nothing while sponsored.
- **Entitlement resolution + portability:** a player's effective plan = the
  best of (their own sub) OR (facility-sponsored Pro). When the membership ends
  or the facility lapses, the sponsored grant is removed → the player falls back
  to their own sub or to Free **with full history retained** (§6 portability).
  This is a new entitlement state to add in `entitlements.py` (a sponsored
  grant), not a change to the membership model.

### Reuse vs. new
- **Reuse:** the roster card UI, sparkline, stale/nudge logic, and
  `get_member_summary()` from `family_dashboard.py` / `family_storage.py`. The
  family dashboard *is* a roster view; we generalize it from "household ≤4" to
  "facility ≤hundreds."
- **Reuse:** the swing report renderer (`swing_report_dashboard_preview.py`)
  for the branded + shareable report.
- **New:** the facility org entity + join-code self-onboard flow; the
  sponsored-Pro entitlement grant + portability; the coach roster page (scaled,
  searchable); facility-logo co-branding; facility checkout + bracket SKUs.

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

### 3.3 Co-branded report (every sponsored kid)
- Report header shows **BarrelLabs branding + the facility's logo** (light
  touch — not a reskin). Applies to every sponsored kid's report + MLB card,
  so every athlete who shares one is marketing the academy.
- Each kid already has their own login + parent-visible view (Model B), so a
  separate "send to parent" link is **optional polish, not load-bearing** —
  keep it if cheap (reuses the report renderer), else defer.
- Any public/shareable link must be read-only, single-report scoped, no auth,
  no cross-player data leak.

### 3.4 Facility checkout + sponsored entitlement (wire up the tier)
- Replace the unbuilt 20-seat `coach_pro` with the **roster-bracket facility
  tiers** (§6). v1 launch SKU = **Academy early-access $1,990/yr**.
- Checkout creates/activates the Facility; the facility's plan + roster ceiling
  drive a **sponsored Pro grant** on every linked player (§2 entitlement
  resolution). Reuse the existing Stripe Checkout flow; add the bracket SKUs to
  `plan_pricing.py`.

---

## 4. Data flow

1. **Coach onboards:** signs up / upgrades → creates Facility (name, logo) →
   gets join code. Coach Pro checkout via existing Stripe flow.
2. **Kid joins:** enters join code at signup or in settings → Membership row
   links player → facility. Player uses BarrelLabs normally (films, gets
   reports), owns their data.
3. **Coach reviews:** opens roster → sees all linked players' latest
   scores/trends/flags → opens any player's report for a lesson.
4. **Sponsored access:** while the membership is active, the player has full
   Pro-equivalent features (co-branded). Parent sees it via the kid's own
   login. If the facility lapses → grant removed, history retained, win-back
   offer (§6 portability).

---

## 5. Error handling & edge cases
- Backend not configured / query error → roster falls back to empty/safe
  states (follow the `family_storage` "safe by design" pattern — never crash).
- Invalid / expired join code → clear error, no partial link.
- **Facility lapses / membership ends** → remove the sponsored Pro grant; player
  falls back to their own sub or Free **with full history retained**; strip
  co-branding; surface the win-back offer (§6).
- **Roster ceiling reached** → block new joins with a clear "upgrade tier"
  prompt to the coach (don't silently exceed the bracket).
- **Kid linked to two facilities** → one account, linked to both rosters (both
  coaches see them); family is never double-charged (they pay nothing while
  sponsored). Counting against each facility's ceiling is acceptable for v1.
- Public report link → read-only, single-report scoped, no auth, no data leak
  across players.
- Large roster → pagination/lazy-load; no unbounded render.

---

## 6. Business model & pricing — MODEL B (research complete — 2026-06-04)

**Decision: the facility pays, and EVERY rostered kid gets the full product**
(equivalent to Solo/Family Pro), co-branded with the academy logo. This is the
"facility sponsors everyone" model. We do **NOT** ship the earlier "dashboard
only + families still hit a paywall" idea — that fights the facility buyer's
expectation, makes the coach look bad to his parents, and starves the branded
share loop. Every comparable org-SaaS (TeamBuildr, Hudl club-wide, Blast team,
CoachNow Academy) is org-pays-everyone-included.

### Pricing — flat roster-size brackets (NOT per-upload)
Billing meter = **enrolled roster slots in brackets**, not per-active-upload.
Bracket pricing is predictable (facility owners hate variable bills), survives
the Aug–Sep off-season, and never incentivizes the facility to suppress kid
usage. Anchored to TeamBuildr's public 50→1,000 athlete brackets. Annual = 10×
monthly (2 months free). **Push annual — it's the seasonality fix.**

| Tier | Roster ceiling | Full monthly | Full annual | ≈ $/athlete/mo | **Early-access annual** (founding, 33% off, locked 12 mo) |
|---|---|---|---|---|---|
| **Team** | ≤ 25 | $99 | $990 | $3.30 | **$690/yr** |
| **Academy** | ≤ 100 | $299 | $2,990 | $2.49 | **$1,990/yr** (≈$166/mo) ← cold-email anchor |
| **Academy Plus** | ≤ 250 | $549 | $5,490 | $1.83 | **$3,490/yr** |
| **Facility** | ≤ 500 | $899 | $8,990 | $1.50 | **$5,990/yr** |
| **Facility Pro** | ≤ 1,000 | $1,499 | $14,990 | $1.25 | **$9,990/yr** |
| **Multi-site / League** | 1,000+ | Custom (~$1.00–1.10/athlete/mo) | Custom | ≤$1.10 | Custom |

Per-athlete rate **declines $3.30 → $1.00** as the roster grows — that's the
answer to "a 1,000-kid academy can't pay 30¢/kid": they pay **$14,990/yr**, a
real number that's still trivial per kid. **Hold the ~$1.00/athlete/mo floor at
the top bracket — do not go below it** (see economics).

### What "the facility pays" unlocks
- **Every linked athlete:** full AI biomech breakdown, unlimited uploads, full
  MLB-match card (co-branded with the academy logo), drill plan + progress
  tracker, their own login + parent-visible view.
- **The coach/facility:** roster dashboard (sortable by score / last upload /
  flagged issue), co-branded reports, weekly cohort progress digest email.
  *(Drill assignment + multi-coach remain v2 — see non-goals.)*

### Account portability (the critical guardrail — turns Model B into a funnel)
The **parent/athlete owns the account and data; the facility only *sponsors*
it.** When a kid leaves the facility (or the facility stops paying), their
account **downgrades to Free with full swing history retained**, branding
stripped, and we immediately offer a direct Solo/Family plan ("you've already
got X swings of history"). So Model B isn't a giveaway — it's **paid customer
acquisition the facility funds**, with a built-in win-back to full-price direct
subs. This is also the COPPA-clean answer (parent consents/controls the minor's
data; the business never owns it).

### Unit economics (from `financial_model.md` COGS; ~60% of roster active/mo)
| Facility | Tier (annual) | Rev/mo | COGS/mo | Gross margin |
|---|---|---|---|---|
| 50 kids | Academy @ $2,990 | $249 | ~$49 | **80%** |
| 300 kids | Facility @ $8,990 | $749 | ~$294 | **61%** |
| 1,000 kids | Facility Pro @ $14,990 | $1,249 | ~$980 | **22%** |

Never loses money if the $1/athlete floor holds (worst case = 100%-active
1,000-kid tier is roughly breakeven; realistic 60%-active is healthily
positive). Margin is richest at the 50–300 kid facilities — exactly the
cold-email targets. The 1,000-kid tier is a trophy-logo + consumer-funnel play,
not a margin play.

### Cannibalization — net additive, not a loss
Facility buyers (academy owners, reached by cold B2B outbound) and direct
consumers (travel-ball parents, reached by Reels/ads) are **different channels,
different buyers**. Of a sponsored roster, only ~10–15% would ever have
converted to a paid direct sub on their own — and you weren't reaching them
(they're locked inside an academy). The facility *delivers the whole roster* to
you at near-zero CAC and absorbs support. The only real risk is a facility
buying a big tier and reselling cheap slots to families who'd otherwise pay
direct — prevented by the $1/athlete floor + roster-ceiling brackets +
co-branding being the actual value.

### Go-to-market
Lead the cold emails with **Academy ($2,990/yr) at the founding-facility launch
price $1,990/yr** — "**$166/mo to give every kid in your academy a pro-grade
AI swing report, co-branded to you, that they share on Instagram, plus a coach
dashboard.**" Make the launch offer **annual-only, founding-facility,
locked-rate** ("first 15 facilities lock 33% off for life if you stay annual")
— urgency + scarcity + the seasonality lock + cash up front. Land-and-expand is
built into the brackets (Academy → Academy Plus → Facility as they grow).

§3.4 checkout applies the **Academy early-access $1,990/yr** as the default
launch SKU; the bracket ladder above is the full price book.

---

## 7. Build sequence (high level — detailed plan comes next)
1. Facility org entity + join-code self-onboard (the new primitive).
2. Sponsored-Pro entitlement grant + portability in `entitlements.py`.
3. Generalize family dashboard → scalable searchable coach roster.
4. Facility-logo co-branding on reports + MLB card.
5. Wire facility checkout (Academy early-access $1,990/yr launch SKU) + bracket
   SKUs in `plan_pricing.py`.
6. (Parallel, not part of this feature) finish the engine/MLB-reference
   trust work — the gate on actually sending the cold emails.

---

## 8. Reused/affected files (initial map — confirm during planning)
- `family_storage.py` / `family_dashboard.py` — generalize household → facility
  roster; the new facility entity likely lives in a sibling
  `facility_storage.py` to keep concerns separate.
- `entitlements.py` — new **sponsored Pro grant** state + portability fallback;
  effective-plan = best-of(own sub, facility sponsorship). `plan_pricing.py` —
  replace 20-seat `coach_pro` with the roster-bracket SKUs.
- `swing_report_dashboard_preview.py` — facility-logo co-branding.
- `auth.py` — household-player helpers are the pattern for facility membership.
- `app.py` — routing for the new coach-roster + join-code pages.
- New: public shareable-report route (no-auth, single-report scoped).
