# Facility Founding Payment Links (LIVE)

> Created 2026-06-08. These are **live** Stripe links on account BARRELLABS
> (`acct_1TWQTV2e5mjNxoPy`). Real money. Each is a **recurring annual** subscription
> at the 33%-off founding rate, quantity locked to 1 license.
> Founding rate is the cold-outreach price for the discounted (non-comped) facilities.
> The 3 free founders onboard via the founder access code instead — they don't use these.

| Tier | Roster ≤ | Founding annual | Payment link |
|---|---|---|---|
| Team | 25 | $690/yr | https://buy.stripe.com/4gM8wI4kC0uD9Wv2TO8N207 |
| Academy | 100 | $1,990/yr | https://buy.stripe.com/eVq8wIdVcfpx1pZ1PK8N208 |
| Academy Plus | 250 | $3,490/yr | https://buy.stripe.com/14A9AM8AS1yHb0z2TO8N209 |
| Facility | 500 | $5,990/yr | https://buy.stripe.com/8x228kg3kdhp2u3eCw8N20a |
| Facility Pro | 1,000 | $9,990/yr | https://buy.stripe.com/eVq00cdVc2CL4Cbamg8N20b |

Academy ($1,990) is the cold-email anchor — send that one unless the facility is
clearly bigger/smaller.

## Stripe object IDs (for reference)

| Tier | Product | Price |
|---|---|---|
| Team | prod_UfUi1J4gAh1tfI | price_1Tg9qL2e5mjNxoPyuYaj9b6e |
| Academy | prod_UfUitxgNRwi0uJ | price_1Tg9kq2e5mjNxoPyH56114j5 |
| Academy Plus | prod_UfUiAD07irvN4s | price_1Tg9lI2e5mjNxoPyc7Vey33F |
| Facility | prod_UfUj5di67FjBE2 | price_1Tg9ld2e5mjNxoPyNDtaMdac |
| Facility Pro | prod_UfUjQasJel9FK3 | price_1Tg9lu2e5mjNxoPya5ezO7sK |

Each price + link carries metadata: `tier`, `roster_ceiling`, `plan=facility`, `founding=true`.

## ⚠ No webhook yet — activation is manual (v1)

Paying via one of these links does NOT auto-activate a facility. There's no
checkout webhook built yet (deferred Task 9). The manual flow per paid facility:

1. Facility owner creates their facility in-app (it's born `status='pending'` now —
   sponsors nobody until you activate).
2. They pay via the matching link above.
3. You see the payment land in the Stripe dashboard, then activate them:
   `UPDATE public.facilities SET status='active', plan_tier='<tier>', roster_ceiling=<n> WHERE id='<theirs>';`
   (a prod write — needs explicit authorization to run via the agent.)

Fine for the first handful of deals. Automate with a checkout webhook once volume
justifies it.

## Adjusting / retiring
- Deactivate a link: set the payment link `active=false` (links never delete).
- Cohort two (post-testimonials): make full-price annual prices ($990 / $2,990 /
  $5,490 / $8,990 / $14,990) and retire these founding links.
