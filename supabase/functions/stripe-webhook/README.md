# Stripe webhook — deploy runbook

This closes the gap where checkout stamped `bl_user_id`/`bl_plan_id` into the
subscription expecting a webhook to write the `subscriptions` row — but the
webhook never existed. Until it's live, real Stripe checkouts may not sync, and
cancellations / failed renewals never update the app.

Two files:
- `index.ts` — the Edge Function (verifies Stripe's signature, calls the RPC).
- `../../migrations/2026_06_05_stripe_webhook_sync.sql` — the `apply_stripe_subscription` RPC.

## Step 0 — CONFIRM the schema (the one thing that could be wrong)
The `subscriptions` table was hand-created (not in migration history), so **open
the migration and check the column names match your real table** (`owner_user_id`,
`plan_id`, `status`, `stripe_customer_id`, `stripe_subscription_id`,
`current_period_end`, `cancel_at_period_end`). If any differ, fix them in the SQL
only — the Edge Function is generic and won't need changes.

> Easiest way to confirm: in Supabase SQL editor run
> `select column_name from information_schema.columns where table_name='subscriptions';`
> (or ask me to do it via the Supabase MCP once it's connected).

## Step 1 — Apply the RPC migration
Via the Supabase MCP (how prod migrations are applied here) or the SQL editor:
paste `2026_06_05_stripe_webhook_sync.sql` and run it.

## Step 2 — Deploy the Edge Function
```bash
supabase functions deploy stripe-webhook --no-verify-jwt
# --no-verify-jwt: Stripe (not a logged-in user) calls this; auth IS the
#                  signature check inside the function.
```
Note the function URL:
`https://<your-project-ref>.supabase.co/functions/v1/stripe-webhook`

## Step 3 — Set the function's secrets
```bash
supabase secrets set \
  STRIPE_SECRET_KEY=sk_live_...           # or a restricted key with read access
  STRIPE_WEBHOOK_SECRET=whsec_...          # from Step 4
# SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are injected automatically.
```
(Best practice: use a **restricted** Stripe key (`rk_`) scoped to read
subscriptions/invoices, not a full secret key.)

## Step 4 — Register the endpoint in Stripe + get the signing secret
Stripe Dashboard → Developers → Webhooks → **Add endpoint**:
- URL: the function URL from Step 2
- Events to send:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
- Copy the **Signing secret** (`whsec_...`) → that's `STRIPE_WEBHOOK_SECRET` in Step 3.

Do this in **test mode first**, then repeat for live mode (separate endpoint +
separate `whsec_`).

## Step 5 — Test before trusting it
```bash
stripe login
stripe listen --forward-to https://<project-ref>.supabase.co/functions/v1/stripe-webhook
stripe trigger checkout.session.completed
stripe trigger customer.subscription.deleted
```
Then confirm the `subscriptions` row updated (status/plan flipped) in Supabase.
Run a real test-mode checkout end-to-end and verify the app shows Pro, then
cancel from the Customer Portal and verify it drops to Free.

## What it does once live
| Stripe event | Effect on `subscriptions` |
|---|---|
| checkout.session.completed / subscription.created/updated | upsert: plan + status=active/trialing + stripe ids + period end |
| invoice.payment_failed | status → `past_due` (keep access during Stripe's retry window; prompt "update card") |
| customer.subscription.deleted | status → `canceled` **and plan → free** (access revoked) |

## Follow-ups (not required to ship the sync)
- "Payment failed — update your card" email on `past_due` (needs a transactional
  email pipeline — separate task).
- The app already expects `webhook_secret` in `.streamlit/secrets.toml`
  (stripe_setup.py mentions it) — the app itself doesn't need it; only the Edge
  Function does. No app change required.
