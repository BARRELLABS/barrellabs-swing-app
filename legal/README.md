# BarrelLabs Legal — Source of Truth

This directory contains the legal documents BarrelLabs users see in
the app and on the marketing site. **These files are the source of
truth.** Anywhere we display TOS or Privacy in the product, it
should render from these markdown files (or a published copy of
them), not be hand-maintained in HTML.

## Files

- `TERMS.md` — Terms of Service
- `PRIVACY.md` — Privacy Policy

## Before publishing

1. **Have an attorney review.** I (Claude, the AI assistant who
   drafted these) am not a lawyer. Both documents are clearly
   labeled as drafts at the top. An hour or two of paid legal
   review is well worth it before going live, especially for the
   Limitation of Liability, Indemnification, and Children's Privacy
   sections.

2. **Fill in the placeholders:**

   | Placeholder | Where | What to put |
   |---|---|---|
   | `[DATE — fill in on publish]` | Top of both files | Today's date, e.g. `2026-06-01` |
   | `[TO FILL — your business mailing address...]` | Bottom of both files | A real mailing address (PO box is fine — required for CAN-SPAM and CCPA notices) |

3. **Set up the four email addresses** referenced in the docs:
   - `support@barrellabs.com`
   - `privacy@barrellabs.com`
   - `disputes@barrellabs.com`
   - Plus the email on your `BarrelLabs` Stripe account

   You can forward them all to your personal inbox initially, but
   they need to be deliverable.

4. **Verify the entity statement.** Both documents identify the
   operator as "Arro AI Solutions LLC, d/b/a BarrelLabs". If you
   restructure (separate LLC for BarrelLabs, S-corp, etc.), update
   the entity statement in both files.

5. **Register the d/b/a if you haven't.** Operating BarrelLabs
   under your existing LLC (Arro AI Solutions) gives you
   personal-liability protection. Most states require you to file a
   "DBA" / "assumed name" / "fictitious name" registration to do
   business under a name other than your LLC's legal name.
   Michigan: ~$10, file with the Department of Licensing and
   Regulatory Affairs (LARA).

## What's wired in the app

**Currently**: nothing renders these docs in the app yet.

**To wire up** (one small follow-up commit):

- Add a `legal/` route to the Streamlit app that renders TERMS.md
  and PRIVACY.md (just `st.markdown(Path("legal/TERMS.md").read_text())`)
- Add footer links from the auth screen and pricing page
- Add a "I agree to the Terms and Privacy Policy" checkbox on
  signup (currently missing — required for enforceability)

## Updating

When you edit TERMS or PRIVACY:

1. Update the "Last updated" date at the top of the file
2. If the change is material (new data collection, new sharing,
   pricing structure changes, etc.), the Privacy Policy and Terms
   of Service both require you to notify active users by email at
   least 14 days before the new version takes effect
3. Commit with a clear message like `legal: TERMS.md — clarify
   refund policy for annual plans` so the git history is the
   version history

## Compliance summary (what these docs assume)

- **Entity**: Arro AI Solutions LLC, d/b/a BarrelLabs (Michigan)
- **Jurisdictions**: United States, with CCPA compliance for
  California residents
- **Not currently compliant with**: GDPR (EU), UK-GDPR, LGPD
  (Brazil), PIPEDA (Canada). The docs explicitly say so. If you
  start actively marketing outside the US, you'll need to revisit.
- **Age policy**: 13+ for self-signup, under 13 via Family Pro
  parent account (COPPA-compliant)
- **Refund**: 7-day full refund, after that pro-rated case by case
  (matches the pricing-page copy)
- **No data sale, no third-party trackers, no AI training for
  third parties** — strong privacy posture; if you ever add
  third-party trackers (e.g., Meta Pixel for ads), update PRIVACY.md
  first
