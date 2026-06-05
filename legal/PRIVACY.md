# Privacy Policy

**Effective: [DATE — fill in on publish]**
**Last updated: [DATE — fill in on publish]**

> ⚠️ **Before publishing**: this is a first-pass draft. A licensed
> attorney should review it before going live, especially the
> Children's Privacy (§7) and California Residents (§8) sections.

---

## 1. Who we are

BarrelLabs is operated by **Arro AI Solutions LLC**, a Michigan
limited liability company doing business as BarrelLabs ("BarrelLabs",
"we", "us", "our").

This policy explains what data we collect, how we use it, who we
share it with, and what control you have over it.

For privacy questions: **privacy@barrellabs.com**

## 2. What we collect

### Data you give us directly

- **Account**: email address, optional display name, password
  (which is hashed by our auth provider Supabase — we never see or
  store your plain-text password)
- **Profile** (optional): handedness, age range, primary swing goal,
  position
- **Swing videos**: the videos you upload for analysis
- **Coaching context** (Coach Pro): your roster of players who have
  affirmatively joined
- **Communications**: emails or messages you send us for support

### Data Stripe collects on our behalf

We use **Stripe, Inc.** to process all payments. Stripe collects and
stores your payment card details, billing address, and transaction
history. We receive only:

- A Stripe customer ID
- Your current subscription status (active, past_due, canceled, etc.)
- The last 4 digits of your payment card (for display)

We do NOT store your full payment card number, security code, or
billing address — Stripe does that under their own privacy policy
(stripe.com/privacy).

### Data we collect automatically

- **Usage data**: which features you use, when, on what device
  (browser, OS, screen size, IP-derived approximate region)
- **Session cookies**: a Streamlit session cookie to keep you logged
  in (essential — no marketing/tracking cookies)
- **Error logs**: technical logs of bugs and crashes. These do NOT
  contain personal data unless you submit a bug report including
  personal information voluntarily.

### Data we derive from your videos

When you upload a video, we run it through:

- **Pose extraction** (using MediaPipe, processed on our servers).
  The raw pose keypoints from the video are computed and then used
  to derive metrics. Intermediate pose keypoints are not persisted
  long-term beyond what's needed to render your analysis.
- **Biomechanics analysis**: stride length, hip-shoulder separation,
  knee extension, head movement, contact timing, etc.
- **MLB comp comparison**: we compare your derived metrics to a
  library of MLB hitter fingerprints we maintain. The comparison
  happens locally to your account — we do not share your data with
  MLB or any league/team.

The DERIVED metrics (numbers, not the video) are stored with your
account so we can show your progress over time.

## 3. How we use your data

We use your data to:

- **Run the service** — process videos, generate analyses, build
  personalized drill plans, show your progress
- **Process payments** — via Stripe; for the rest see §2
- **Send service emails** — account confirmations, billing receipts,
  subscription changes, security notifications. We do NOT send
  marketing emails without your explicit opt-in.
- **Improve the service** — we may use **aggregated, de-identified**
  insights (e.g., "users with toe-tap strides show 18% more variance
  in foot-plant timing") for product research and improvement. This
  data is anonymized and cannot be traced back to you.
- **Detect abuse** — investigate violations of our Terms of Service
  or unlawful activity
- **Comply with law** — respond to lawful requests (subpoenas, court
  orders)

## 4. Who we share with

We share data with these categories of recipients:

### Service providers (processors acting on our behalf)

- **Supabase** — auth, database, and video file hosting. Their
  privacy policy: supabase.com/privacy
- **Stripe** — payment processing. Their policy: stripe.com/privacy
- **Hosting / infrastructure** — Streamlit Cloud and the underlying
  cloud provider, for running the application
- **Email delivery** (transactional) — if/when we send transactional
  emails (receipts, password resets), they go through a delivery
  provider

These service providers process data on our behalf, under contractual
restrictions, and only for the purposes we tell them to.

### Within your authorized circle

- **Family Pro**: The paying member's account can see usage and
  billing information for their family group. Each family member's
  individual swing data remains private to that family member's
  profile.
- **Coach Pro**: Coaches see a read-only roll-up view of swings
  from players who have **affirmatively joined** their roster.
  Players can leave a roster at any time.

### Legal & safety

- When required by valid legal process (subpoena, court order,
  warrant)
- To protect the rights, property, or safety of BarrelLabs, our
  users, or others
- In connection with a business transfer (merger, acquisition,
  asset sale) — with notice to you

### What we DON'T do

- We do NOT **sell** your personal data to anyone.
- We do NOT **share your individual videos** with advertisers, data
  brokers, MLB, teams, scouts, or any third party.
- We do NOT use your data to **train third-party AI models** or
  models that benefit anyone outside our service.
- We do NOT embed third-party advertising or tracking SDKs.

## 5. Where data lives, and for how long

- **Account, profile, derived metrics**: stored in Supabase (Postgres
  database), US-hosted
- **Video files**: stored in Supabase Storage, US-hosted
- **Backups**: encrypted backups maintained by our hosting providers
- **Logs**: error and security logs, US-hosted, retained up to 12
  months

**Retention**:

- While your account is active: we keep your data so you can use the
  service
- After you delete your account: we delete your videos, analyses,
  drill history, and account data within **30 days**. Some logs and
  records (e.g., financial transaction records, abuse-investigation
  records) may persist longer where required by law.
- Aggregated, de-identified data may persist indefinitely (it can't
  be traced back to you)

## 6. Your rights

You have the right to:

- **Access** — view all data we hold about you. Use
  **Account Settings → My Data Export** to download a JSON file of
  your account data, profile, and analysis history.
- **Correction** — update profile fields anytime from Account Settings.
- **Deletion** — delete your account from **Account Settings →
  Account → Delete Account**. This removes your data and cancels
  any active subscription.
- **Withdraw consent** — for any opt-in feature, you can withdraw
  consent anytime by toggling it off in Account Settings.
- **Object to certain processing** — email privacy@barrellabs.com
  if you want to object to specific processing (e.g., aggregated
  analytics).
- **Portability** — your data export (above) is in standard JSON
  format, suitable for moving to another service.

To exercise any right not available in-app, email
**privacy@barrellabs.com**. We'll respond within 30 days.

## 7. Children's Privacy (COPPA — under 13)

We do not knowingly collect personal information directly from
children under 13.

Children under 13 may only use BarrelLabs as a profile within a
**Family Pro** account, where:

- The parent or legal guardian creates and verifies the Family Pro
  account
- The parent provides COPPA consent on the child's behalf — captured as
  an explicit affirmation at the moment the parent adds the child as a
  player, and recorded with a timestamp. (A direct under-13 signup is
  blocked; only a parent/guardian can create the child's profile.)
- Where heightened verification is required (for example, when a child's
  data may be viewed by a coach or facility), we use a phone-based
  verification step — never a credit card
- The child's data (profile, videos, analyses) is held under the
  parent's authority
- The parent can view, edit, or delete the child's profile and data
  at any time from **Family Settings**

**What we collect about under-13 users (only via parent consent)**:

- Display name (parent chooses; not required to be the child's real
  name)
- Handedness, age range, primary goal (optional)
- Swing videos uploaded by the parent or by the child with parent's
  supervision
- Derived biomechanics metrics

**What we do NOT collect about under-13 users**:

- Direct contact information (email, phone, address)
- Geolocation
- Photos or videos beyond the swing videos uploaded for analysis

**Parental control**: A parent can email privacy@barrellabs.com to:

- Review the data we've collected about their child
- Request deletion of their child's data
- Refuse further collection

If you believe a child under 13 has created an account without
parental consent, please email **privacy@barrellabs.com** and we'll
delete it promptly.

## 8. California Residents (CCPA / CPRA)

If you're a California resident, you have additional rights:

- **Right to know**: what personal information we've collected, the
  sources, the purposes, and who we've shared it with (see §2-§4)
- **Right to delete**: see §6 ("Deletion")
- **Right to correct**: see §6 ("Correction")
- **Right to opt out of "sale" or "sharing"**: We don't sell or
  "share" personal information for cross-context behavioral
  advertising (as those terms are defined under the CCPA), so there's
  nothing to opt out of.
- **Right to limit use of sensitive personal information**: We don't
  collect sensitive personal information for the purposes that
  trigger this right.
- **Right to non-discrimination**: We won't deny service, charge you
  more, or provide a lesser experience because you exercised any of
  these rights.

To exercise any CCPA right, email **privacy@barrellabs.com**. We may
need to verify your identity (typically by confirming you can
respond from the email on your account).

We do not use "financial incentives" or loyalty programs in the
CCPA sense.

## 9. International users

BarrelLabs is operated from and intended for users in the **United
States**. We do not currently market or actively offer the service
in the European Union, the United Kingdom, or other jurisdictions
outside the US.

If you access BarrelLabs from outside the US:

- You acknowledge that your data will be transferred to and processed
  in the United States, which has different data-protection laws than
  your home country
- We will honor reasonable deletion and access requests from
  international users
- We do NOT claim full GDPR or UK-GDPR compliance — if you require
  full GDPR compliance, please don't use the service

If you believe we should expand our jurisdictional coverage, let us
know at privacy@barrellabs.com.

## 10. Security

We protect your data with industry-standard practices:

- All data in transit is encrypted with TLS (HTTPS)
- Passwords are hashed by Supabase using bcrypt/Argon2 — we never
  see or store plain-text passwords
- Database backups are encrypted at rest
- Access to production data is limited to authorized personnel
  (currently: the founder) and logged
- Payment data is processed by Stripe under PCI-DSS Level 1
  compliance

No system is 100% secure. If we discover a security breach that
affects your personal data, we'll notify you within 72 hours of
discovery (or sooner where required by law), with a description of
what happened, what data was affected, and what steps we're taking.

## 11. Cookies & tracking

We use:

- **Essential session cookies** (Streamlit) to keep you logged in
- **Stripe cookies** (only on payment pages) for fraud prevention

We do NOT use:

- Google Analytics, Meta Pixel, TikTok Pixel, or any other third-party
  analytics or advertising trackers
- Cross-site tracking pixels
- "Do Not Track" signals are honored by default — we don't track
  cross-site behavior anyway.

If we add analytics or marketing trackers in the future, we'll update
this policy first and provide a way to opt out.

## 12. Changes to this policy

We may update this Privacy Policy from time to time. If we make
material changes, we'll notify active users by email at least 14
days before the change takes effect. The "Last updated" date at the
top of this document will always reflect the current version.

Material changes include: new categories of data collection, new
data sharing with third parties, new uses of existing data, and any
expansion of data we share or sell.

## 13. Contact

- Privacy questions: **privacy@barrellabs.com**
- General support: **support@barrellabs.com**
- Operator: **Arro AI Solutions LLC**, d/b/a BarrelLabs
- State of formation: Michigan, USA
- Mailing address: [TO FILL — your business mailing address]
