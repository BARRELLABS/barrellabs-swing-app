# BarrelLabs SwingAI — State of the App + Roadmap

**Date:** 2026-06-05
**Purpose:** An honest, comprehensive audit of where the product stands, and a roadmap to turning it into a *real downloadable app*.

---

## TL;DR (read this first)

You have a **working, paid, premium web product** — most "AI baseball" companies are still in pitch decks; you're shipping. As of today the scary foundations are done and live: the AI engine is trustworthy, payments actually work, and users stay logged in like a real app.

**But "downloadable app" is a real fork in the road.** Your app is built on **Streamlit, a web framework — it cannot be exported to an App Store app.** Getting to a real download means either (a) making the web app installable (PWA), (b) wrapping it in a native shell (risky with Apple), or (c) rebuilding the front-end natively while keeping your Python AI as a backend. The honest recommendation + tradeoffs are in **§4** (informed by dedicated research).

**The most important strategic point:** don't build the native app yet. Validate that people *pay and stick* on the web product first (Hitz, a few facilities, a consumer trickle), *then* invest in native. Native is a 2-4 month project; demand-validation is a 2-4 week one.

---

## 1. Where you are today — honest current state

### What's genuinely strong
- **A working AI pipeline that ships.** Phone video → MediaPipe pose extraction → biomechanics (`detect_phases.py`, `analyzer.py`) → a premium swing report (Edge Score, MLB-hitter comparison, drills). This is the moat.
- **A premium, consistent design system** ("Edge" — dark editorial, Instrument Serif + Geist, gold/red). Most Streamlit apps look like Streamlit; yours doesn't.
- **Real billing.** Supabase + Stripe with working subscriptions, and (as of today) the webhook that actually syncs payments.
- **Trustworthy MLB engine** (as of today — see §2).
- **17-player MLB reference library** with similarity scoring — the foundation of the viral "who's your kid's MLB twin?" hook.

### Architecture (so you know what you're working with)
- **Front + back end:** one ~4,900-line Python **Streamlit** app (`app.py`) plus ~50k lines of supporting Python. Server-rendered, runs on **Streamlit Community Cloud**, used in a browser.
- **Data/auth/storage:** **Supabase** (Postgres + RLS + auth + `subscriptions`/`players`/`subscription_seats` schema).
- **Payments:** **Stripe** Checkout + a **Supabase Edge Function** webhook (deployed today).
- **AI:** Python — MediaPipe + OpenCV + NumPy. Runs server-side on each uploaded video.
- **Marketing site:** a **separate** Next.js project at `~/barrellabs-website` ("The Pull" direction) — built, not deployed.

### Known tech debt / fragilities (be aware, not alarmed)
- **`app.py` is a 4,900-line god file** and `development_tracker.py` is **6,900 lines**. Slows iteration; a refactor target, not urgent.
- **Streamlit's model is the root of several UX quirks** you hit today: in-session-only nav, the awkward (now-fixed) checkout tab dance, logout-on-refresh (now fixed via durable login). These are *framework* limitations — relevant to the "downloadable app" decision (§4).
- **The supabase client is a shared singleton** with per-rerun session re-application — works, but has theoretical multi-user race edges.
- **The MLB head-drift metric** has a documented residual limitation on broadcast clips (bounded by the score threshold) — see [[mlb-reference-corruption]] memory.

---

## 2. What today's session actually shipped (so you remember)

All **live on `main` / deployed** unless noted:
- ✅ **MLB engine fixed + trustworthy:** re-labeled + rebuilt the 17 references on verified contacts; fixed the head-drift metric (nose→ear-midpoint); re-anchored the stability score. Validated on your own phone swings.
- ✅ **Stripe webhook** — the missing piece of checkout. Built, **deployed to Supabase**, and **proven on a real test purchase** (synced to active Family Pro). ⚠️ *Its source code lives on branch `feat/stripe-webhook` — not merged to `main`. Merge it so the repo matches what's live.*
- ✅ **Durable login** — stay signed in across reloads/tabs (fixes the post-checkout re-sign-in). Tested.
- ✅ **Pricing page** — was rendering raw CSS as text; fixed (the `<link>`-before-`<style>` bug).
- ✅ **Checkout** — real clickable link + a clean "Payment received" return screen.
- ✅ **Startup crash** fixed (a dead video symlink).
- ✅ **Error monitoring (Sentry)** + **product analytics (PostHog)** wired (PostHog key baked in; Sentry needs a DSN).

---

## 3. What's built but NOT merged/live (decide on each)

| Branch | What it is | Action |
|---|---|---|
| `feat/stripe-webhook` | The webhook source (edge function + SQL). **The webhook is LIVE** (deployed via Supabase), but the code isn't in `main`. | **Merge it** — make the repo match production. |
| `feat/facility-coach-mode` (7 commits) | Facility/Academy tier: full spec + plan + prod-safe foundation (schema migration *file*, entitlements sponsored-grant, pricing brackets, storage, roster dashboard) + a themed pitch mockup. | Hold until you validate facility demand (Hitz). Then finish + merge. |

---

## 4. The big question: "a real downloadable app"

### The honest constraint
**Streamlit cannot become a native app — and it's not a tooling gap, it's architectural.** Your Python runs on a *server*, and the browser holds a live WebSocket to it, re-running the whole script on every click. A native app ships compiled code that runs *on the phone*. There's nothing to "compile to a phone" — the app *is* the server. There's no "build for iOS," no React-Native/Flutter renderer, no Capacitor adapter for Streamlit. The "native app for Streamlit" beta tools you'll find are just **webview wrappers** (Path B). So "native" means either wrapping the hosted web app in a shell, or rebuilding the UI in a real mobile framework while keeping your Python AI as a backend.

### The realistic paths

| Path | What it is | Effort | UX | App Store? | Verdict |
|---|---|---|---|---|---|
| **A — PWA** | Make the web app installable (home-screen icon, full-screen, iOS web push). | ~1–2 wks, ~$0 | 6/10 | No | Cheapest legitimacy bump. Good *interim*. |
| **B — Webview wrapper** (Capacitor/Median) | Native shell loading your web app + native camera/push. | 2–4 wks | 6.5/10 | Yes | **Skip it** — worst fit for Streamlit (you'd dress up your weakest layer + risk Apple's "thin wrapper" rejection). |
| **C — Native rewrite** (React Native/Expo + Python AI as an API) | Real native UI; extract `detect_phases`/`analyzer` behind a FastAPI service. | **2–4 months** | 9/10 | Yes | **The destination.** Don't start before demand is proven. |
| **D — Stay web + PWA** | Polished mobile-web, defer native. | (= A) | 6/10 | No | **Genuinely enough to validate paying retention**, since your core flow is just "upload clip → get report." |

**On Path C's AI:** keep pose detection **server-side first** (phone uploads clip → FastAPI runs MediaPipe → returns report — reuses your existing Python directly). The marquee upgrade later is **on-device MediaPipe** — it has first-class native iOS/Android Pose Landmarker SDKs that run in real time on the phone. The sweet spot: **extract landmarks on-device, send the tiny landmark arrays (not the video) to your Python API for the Edge Score / MLB comparison.** Kills upload latency, cuts compute cost, keeps your scoring IP server-side, and enables live "you're in frame" feedback.

### ⚠️ The biggest gotcha: Apple's in-app-purchase rules (and they just shifted your way)
Historically, selling a digital subscription in an iOS app forced Apple's IAP (30%, or 15% small-biz) — and a Stripe-subscription app got *rejected* for it. **As of the 2025 Epic v. Apple ruling (upheld in part Dec 2025), US apps can link out to external web checkout (your Stripe flow) and Apple currently can't take a commission on it (0%, pending a court-set fee).** But the rules are strict: (1) the purchase must happen on **web checkout you link out to** — you may *not* embed a native Stripe form; (2) the link should **open the real browser, not an in-app webview**; (3) most non-"reader" apps must *also* still offer Apple IAP alongside — SwingAI isn't a reader app, so plan for this. This area is **legally in flux** — re-check before you submit.

**Other gotchas:** webview wrappers get rejected under Guideline 4.2 unless they add real native value (push, camera, offline); mobile-web is fine for *uploading* a clip but unreliable for *live in-app camera* on iOS Safari; iOS PWA push works but only after the user *manually* adds to home screen (build that into onboarding).

### ✅ Good news: the one blocker for the PWA path is already fixed
The research flagged that your **session-only auth (logout on every reload) would make a PWA log users out constantly** — which is true, and it's the *exact* thing I fixed today with **durable login**. So the PWA path is now unblocked.

### Recommendation (sequenced, not either/or)
**Don't rewrite native yet.** Sequence:
1. **Now (1–2 wks):** front the Streamlit app with a thin HTML wrapper page that owns the manifest/icon/name + service worker; add iOS web push ("your report is ready"). Cheap, gets you home-screen install + push + a real "app" feel. (Durable login already handled the auth blocker.)
2. **Trigger to go native:** once you have evidence of *paying retention* (a few dozen paying coaches/parents, repeat uploads).
3. **Then (2–4 mo):** React Native/Expo UI + FastAPI-extracted Python pipeline, with **on-device MediaPipe** as the headline upgrade.

**One line:** *PWA-fronted mobile web now → prove people pay and come back → React Native + on-device MediaPipe later.*

---

## 5. The roadmap (phased)

### Phase 0 — Finish the web product (1–2 weeks)
The web app is the thing you demo and validate with *now*. Close the launch gaps:
1. **Merge `feat/stripe-webhook`** (repo = reality).
2. **The report-focus overlap** (you reported it; needs you to describe what overlaps, or I find it with a real swing on file).
3. **COPPA / parental consent** — you collect *minors'* videos. Legal must-have, urgent the moment a facility puts kids on it.
4. **Password-reset email** + basic transactional email (welcome, payment-failed).
5. **Add the Sentry DSN** (you have PostHog; add Sentry to stop flying blind).
6. **Verify end-to-end on the live app** with a real swing upload.

### Phase 1 — Validate demand (2–4 weeks, overlaps Phase 0)
Don't build native before someone pays and sticks.
1. **Hitz meeting** — demo the working app + the facility mockup; find out if facilities pay.
2. **Cold-email 10–20 facilities** (the founding-facility discount; only after the engine's proven — it is now).
3. **Consumer trickle** — the marketing site's waitlist; a few real parent users.
4. **Watch the funnel** (PostHog now tracks signup → swing → checkout) — measure where people drop.

### Phase 2 — The architecture pivot for a real app (timing per §4 research)
Only after Phase 1 shows real demand:
1. **Extract the AI pipeline behind an API** (decouple the Python biomechanics from the UI). This is the prerequisite for *any* native path and also makes the web app cleaner.
2. **Build the native front-end** (path per §4) — camera capture, push notifications, smooth UX.
3. **Resolve the Apple in-app-purchase question** (see §4 — Stripe-in-a-webview can violate Apple's IAP policy; this materially affects the plan).

### Phase 3 — Launch & scale
- App Store / Play Store submission, COPPA-compliant, analytics-instrumented, webhook-solid.
- Facility product live (the rev-share / bracket model already designed).
- The viral MLB-match share card as a 1-click PNG (top consumer-growth lever from your strategic audit).

---

## 6. Gaps & risks checklist (from the strategic audit + today)

| Item | Status |
|---|---|
| Payments sync (webhook) | ✅ Done + proven |
| Durable login | ✅ Done |
| Error tracking (Sentry) | ⚙️ Wired — **add a DSN** |
| Product analytics (PostHog) | ✅ Wired + key in |
| MLB engine trustworthy | ✅ Done |
| COPPA / parental consent | ❌ **Gap — legal, do before scaling to minors** |
| Password reset / transactional email | ❌ Gap |
| Shareable MLB-match PNG (viral lever) | ❌ Not built |
| Public/shareable swing-report URL | ❌ Not built |
| Facility/coach product | 🟡 Foundation built (branch) — finish on demand |
| `app.py` god-file refactor | 🟡 Tech debt, not urgent |
| Report-focus + any remaining overlaps | 🟡 Minor, needs a real swing to see |

---

## 7. If I were you, the next two weeks
1. **Merge the webhook branch**, add the Sentry DSN, run one real swing on the live app (proves it + surfaces the report overlap).
2. **Take the working app + facility mockup to Hitz.** Find out if facilities pay. This decides everything downstream.
3. **Read §4** and decide the app path — but **don't start native until Hitz/cold-emails say "yes."**
4. Knock out **COPPA consent** (I can build most of it) — it's the one gap that becomes a real problem the moment a facility onboards kids.

**You are closer to a real business than the day-to-day bugs made it feel.** The product works, it's paid, and the engine is honest. The "downloadable app" is a real next chapter — but it's chapter 2, and chapter 1 (validate that people pay) isn't finished yet.
