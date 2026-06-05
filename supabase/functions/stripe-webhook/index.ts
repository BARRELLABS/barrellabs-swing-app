// Stripe webhook -> Supabase sync (Edge Function).
//
// WHY: BarrelLabs checkout (stripe_client.create_checkout_session) stamps
// bl_user_id / bl_plan_id / bl_interval into the Stripe subscription metadata
// expecting "the webhook" to write the subscriptions row. This is that webhook.
// Without it: checkouts never sync, cancellations/failed renewals never update
// the app, and revenue leaks silently.
//
// It verifies Stripe's signature (REQUIRED — never trust an unverified webhook),
// then calls one Postgres RPC (apply_stripe_subscription) so all schema coupling
// lives in SQL next to the table (see migrations/2026_06_05_stripe_webhook_sync.sql).
//
// Deploy:  supabase functions deploy stripe-webhook --no-verify-jwt
//   (--no-verify-jwt because Stripe calls it, not a logged-in user; auth IS the
//    Stripe signature check below.)
// Secrets: supabase secrets set STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=whsec_...
//   (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are injected automatically.)

import Stripe from "https://esm.sh/stripe@17?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2?target=deno";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
  apiVersion: "2026-04-22.dahlia",
});
const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET")!;
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const iso = (unixSeconds: number | null | undefined): string | null =>
  unixSeconds ? new Date(unixSeconds * 1000).toISOString() : null;

// Pull (user_id, plan_id) out of a subscription's metadata.
function ids(sub: Stripe.Subscription): { userId: string | null; planId: string | null } {
  const m = sub.metadata ?? {};
  return { userId: m.bl_user_id || null, planId: m.bl_plan_id || null };
}

// Upsert the subscriptions row (+ owner seat) from a Stripe subscription object.
// The RPC handles the cancel-downgrade (via status) and owner-seat creation.
async function syncSubscription(sub: Stripe.Subscription, statusOverride?: string) {
  const { userId, planId } = ids(sub);
  if (!userId) {
    console.warn(`sub ${sub.id}: no bl_user_id metadata — skipping`);
    return;
  }
  const s = sub as any; // period fields' TS types vary by API version
  const { error } = await supabase.rpc("apply_stripe_subscription", {
    p_user_id: userId,
    p_plan_id: planId,
    p_status: statusOverride ?? sub.status, // active|trialing|past_due|canceled|...
    p_billing_interval: sub.metadata?.bl_interval || null,
    p_stripe_customer_id: typeof sub.customer === "string" ? sub.customer : sub.customer?.id,
    p_stripe_subscription_id: sub.id,
    p_current_period_start: iso(s.current_period_start),
    p_current_period_end: iso(s.current_period_end),
    p_cancel_at_period_end: sub.cancel_at_period_end ?? false,
  });
  if (error) {
    console.error(`apply_stripe_subscription failed for ${sub.id}:`, error.message);
    throw error; // 500 -> Stripe retries
  }
  console.log(`synced sub ${sub.id} user=${userId} plan=${planId} status=${statusOverride ?? sub.status}`);
}

Deno.serve(async (req) => {
  const sig = req.headers.get("stripe-signature");
  if (!sig) return new Response("missing signature", { status: 400 });

  let event: Stripe.Event;
  try {
    // constructEventAsync is REQUIRED in Deno (signature crypto is async).
    const body = await req.text();
    event = await stripe.webhooks.constructEventAsync(body, sig, webhookSecret);
  } catch (err) {
    console.error("signature verification failed:", (err as Error).message);
    return new Response("invalid signature", { status: 400 });
  }

  try {
    switch (event.type) {
      case "customer.subscription.created":
      case "customer.subscription.updated":
        await syncSubscription(event.data.object as Stripe.Subscription);
        break;

      case "customer.subscription.deleted":
        // Subscription fully ended -> mark canceled (app downgrades to Free).
        await syncSubscription(event.data.object as Stripe.Subscription, "canceled");
        break;

      case "invoice.payment_failed": {
        // Card declined on a renewal -> reflect past_due so the app can prompt
        // an update. Stripe's smart retries continue; a later success re-syncs.
        const inv = event.data.object as Stripe.Invoice;
        const subId = (inv as any).subscription as string | null;
        if (subId) {
          const sub = await stripe.subscriptions.retrieve(subId);
          await syncSubscription(sub, "past_due");
        }
        break;
      }

      case "checkout.session.completed": {
        // Belt-and-suspenders: pull the freshly created subscription and sync
        // immediately (don't wait on subscription.created ordering).
        const cs = event.data.object as Stripe.Checkout.Session;
        if (cs.mode === "subscription" && cs.subscription) {
          const subId = typeof cs.subscription === "string" ? cs.subscription : cs.subscription.id;
          const sub = await stripe.subscriptions.retrieve(subId);
          await syncSubscription(sub);
        }
        break;
      }

      default:
        // Unhandled event types are fine — ack so Stripe doesn't retry.
        break;
    }
  } catch (_err) {
    // syncSubscription already logged; 500 makes Stripe retry with backoff.
    return new Response("handler error", { status: 500 });
  }

  return new Response(JSON.stringify({ received: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
});
