"""Standalone Playwright preview of the pricing.py v2 editorial redesign.

The authed page can't be screenshot'd live without a Supabase login.
This harness builds a static HTML document that mirrors the exact
markup `render_pricing_page` emits, drops it in a tmp file, then
Playwright opens it and screenshots desktop + mobile.

Usage:
    PY=/Users/logancollins/barrellabs-swing-app/.venv/bin/python
    $PY scripts/visual_qa/preview_pricing.py

Output:
    /tmp/pricing_v2_desktop.png  (1440 wide)
    /tmp/pricing_v2_mobile.png   (430 wide)
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))


def _extract_css() -> str:
    """Pull the _PRICING_CSS block straight out of pricing.py — single
    source of truth. We snip from the start `<link rel="preconnect"` line
    through the closing `</style>` so we don't drift from production."""
    src = (PROJECT / "pricing.py").read_text()
    m = re.search(
        r'_PRICING_CSS\s*=\s*"""(.*?)"""',
        src, re.DOTALL,
    )
    if not m:
        raise RuntimeError("Couldn't find _PRICING_CSS in pricing.py")
    return m.group(1)


def _build_html(interval: str = "annual") -> str:
    """Assemble the static HTML mirror of render_pricing_page's output.
    Plan prices + features are hand-mirrored from PLAN_PRICING so the
    preview matches the live page byte-for-byte where possible.

    `interval` switches between "annual" (the default we ship as primary)
    and "monthly" so we can verify both states render cleanly."""
    css = _extract_css()

    # Card payloads — mirror what _render_plan_card produces. Solo Pro is
    # FEATURED (audit-driven) and sits in the MIDDLE column via family →
    # solo → coach order. Two parallel variants so we can verify the
    # Monthly state without spinning up Streamlit.
    if interval == "monthly":
        cards = [
            {
                "name":       "Family Pro",
                "eyebrow":    "Family · 4 seats",
                "seats_line": "Up to <strong>4 family members</strong>",
                "featured":   False,
                "price":      "$24.99",
                "period":     "/mo",
                "equiv":      "",
                "save":       "",
                "cta":        "Start with Family",
            },
            {
                "name":       "Solo Pro",
                "eyebrow":    "Solo · 1 seat",
                "seats_line": "For <strong>1 player</strong>",
                "featured":   True,
                "price":      "$14.99",
                "period":     "/mo",
                "equiv":      "",
                "save":       "",
                "cta":        "Start with Solo",
            },
            {
                "name":       "Coach Pro",
                "eyebrow":    "Coach · 20 seats",
                "seats_line": "Up to <strong>20 players</strong>",
                "featured":   False,
                "price":      "$79.99",
                "period":     "/mo",
                "equiv":      "",
                "save":       "",
                "cta":        "Start with Coach",
            },
        ]
    else:
        cards = [
            {
                "name":         "Family Pro",
                "eyebrow":      "Family · 4 seats",
                "seats_line":   "Up to <strong>4 family members</strong>",
                "featured":     False,
                "price":        "$199",
                "period":       "/yr",
                "equiv":        "$16.58/mo billed annually",
                "save":         "↗ Save 40% vs monthly",
                "cta":          "Start with Family",
            },
            {
                "name":         "Solo Pro",
                "eyebrow":      "Solo · 1 seat",
                "seats_line":   "For <strong>1 player</strong>",
                "featured":     True,
                "price":        "$99",
                "period":       "/yr",
                "equiv":        "$8.25/mo billed annually",
                "save":         "↗ Save 45% vs monthly",
                "cta":          "Start with Solo",
            },
            {
                "name":         "Coach Pro",
                "eyebrow":      "Coach · 20 seats",
                "seats_line":   "Up to <strong>20 players</strong>",
                "featured":     False,
                "price":        "$599",
                "period":       "/yr",
                "equiv":        "$49.92/mo billed annually",
                "save":         "↗ Save 38% vs monthly",
                "cta":          "Start with Coach",
            },
        ]
    # Toggle pill state mirrors the live UI: the selected interval gets
    # the bone fill, the other stays ghosted.
    monthly_active = (interval == "monthly")
    features = [
        "Unlimited swing analyses",
        "Personalized drill plan",
        "Swing video saved with every analysis",
        "Side-by-side swing comparison",
        "PDF report export",
        "Full Development Tracker (XP, streaks, achievements)",
        "Full MLB comp library",
        "Rewards Roadmap — incl. limited-edition hoodie at 180 days",
    ]
    extras_map = {
        "Family Pro": [
            "Up to 4 family member accounts",
            "Separate swing history per member",
        ],
        "Coach Pro": [
            "Up to 20 player rosters",
            "Read-only views of each player's swings",
            "Priority support",
        ],
    }

    def render_card(c: dict) -> str:
        feats = features + extras_map.get(c["name"], [])
        feat_html = "".join(f"<li>{f}</li>" for f in feats)
        badge = '<div class="pr-card-badge">Recommended</div>' if c["featured"] else ""
        cta_class = "pr-card-cta-wrap is-featured" if c["featured"] else "pr-card-cta-wrap"
        card_class = "pr-card is-featured" if c["featured"] else "pr-card"
        return f"""
        <div class="{card_class}">
          {badge}
          <div class="pr-card-eyebrow">{c['eyebrow']}</div>
          <div class="pr-card-name">{c['name']}</div>
          <div class="pr-card-seats">{c['seats_line']}</div>
          <div class="pr-price-row">
            <span class="pr-price-big">{c['price']}</span>
            <span class="pr-price-period">{c['period']}</span>
          </div>
          <div class="pr-price-equiv">{c['equiv']}</div>
          <div class="pr-price-save">{c['save']}</div>
          <ul class="pr-features">{feat_html}</ul>
          <div class="{cta_class}">
            <div data-testid="stButton">
              <button>{c['cta']}</button>
            </div>
          </div>
        </div>
        """

    cards_html = "".join(render_card(c) for c in cards)

    faqs = [
        ("What's the difference between Solo, Family, and Coach?",
         "Solo Pro is one player. Family Pro is the same Pro experience "
         "but with four separate accounts. Coach Pro lets a coach roster "
         "up to 20 players, each with private swing history."),
        ("Can I cancel anytime?",
         "Yes. Cancel from Account Settings → Subscription in two clicks. "
         "Your Pro access stays active through the end of your paid period."),
        ("Do you offer refunds?",
         "100% refund within 7 days of your first charge, no questions "
         "asked. After 7 days we pro-rate refunds case by case."),
        ("What equipment do I need?",
         "A smartphone or laptop camera. Film one swing from the side at "
         "30–60 fps, upload, get your report."),
        ("Is my swing data private?",
         "Yes, your data is private. Coach accounts can only see "
         "players who actively join their roster."),
        ("Do you offer team or program discounts?",
         "For larger rollouts (D1 programs, academies), drop us a line."),
    ]
    faq_html = "".join(
        f"<details><summary>{q}</summary><p>{a}</p></details>"
        for q, a in faqs
    )

    return textwrap.dedent(f"""
    <!doctype html>
    <html><head><meta charset="utf-8">
    <title>BarrelLabs Pricing — v2 preview</title>
    {css}
    <style>
      /* Page chrome stub so the preview looks like Streamlit's setup */
      body {{ margin: 0; background: var(--pr-bg); }}
    </style>
    </head><body>
    <div class="pr-bg"></div>
    <div class="pr-grain"></div>
    <div class="pr-wrap">
      <div class="pr-back-row">
        <div data-testid="stButton" style="display:inline-block;">
          <button style="background:transparent;color:#C8C4BB;border:none;
                         font-family:'Geist',sans-serif;font-size:0.92rem;
                         padding:8px 0;cursor:pointer;">
            ← Back to Dashboard
          </button>
        </div>
      </div>

      <div class="pr-hero">
        <div class="pr-hero-eyebrow">§ 03 · Pricing</div>
        <h1 class="pr-hero-title">BarrelLabs&nbsp;Pro. <span class="ital">Three sizes.</span></h1>
        <p class="pr-hero-sub">
          One product. Three seat counts. Built for serious hitters and the
          coaches who train them. Unlimited swings, personalized drills,
          the full MLB comp library — every Pro plan, every feature.
        </p>
      </div>

      <div style="display:flex;align-items:center;justify-content:center;gap:18px;margin:8px 0 44px 0;">
        <div data-testid="stRadio" style="background:var(--pr-bg-glass);border:1px solid var(--pr-line);
                                          border-radius:100px;padding:4px;display:inline-flex;">
          <label style="margin:0;padding:8px 18px;border-radius:100px;
                        background:{'var(--pr-bone)' if monthly_active else 'transparent'};
                        color:{'var(--pr-bg)' if monthly_active else 'var(--pr-bone-dim)'};
                        font-family:'Geist Mono',monospace;font-size:11px;font-weight:600;
                        letter-spacing:0.16em;text-transform:uppercase;cursor:pointer;">
            Monthly
          </label>
          <label style="margin:0;padding:8px 18px;border-radius:100px;
                        background:{'transparent' if monthly_active else 'var(--pr-bone)'};
                        color:{'var(--pr-bone-dim)' if monthly_active else 'var(--pr-bg)'};
                        font-family:'Geist Mono',monospace;font-size:11px;font-weight:600;
                        letter-spacing:0.16em;text-transform:uppercase;cursor:pointer;">
            Annual
          </label>
        </div>
        <span class="pr-save-pill">Save 45% · 2 months free</span>
      </div>

      <div class="pr-grid">
        {cards_html}
      </div>

      <div class="pr-reassure-rule">
        <p class="pr-reassure-line">
          Refund within 7 days. <em>Cancel in two clicks.</em>
          Your swings stay yours.
        </p>
      </div>

      <div class="pr-faq-wrap">
        <div class="pr-faq-eyebrow">§ 04 · Common questions</div>
        <h2 class="pr-faq-title">Before you <span class="ital">commit.</span></h2>
        {faq_html}
      </div>

      <div class="pr-beta">
        Got a <strong>BarrelLabs beta code</strong>? Redeem it in
        <em>Account Settings → Subscription</em> for 30 days of full Pro
        access — no card required.
      </div>
    </div>
    <script>
      // Mirror of the JS injected in pricing.py — so opening this
      // preview HTML in a browser actually exercises the hover tilt
      // and spotlight, not just the static layout.
      (function() {{
          const cards = document.querySelectorAll('.pr-card');
          cards.forEach(card => {{
              const isFeatured = card.classList.contains('is-featured');
              const baseScale  = isFeatured ? 1.025 : 1.0;
              const hoverY     = isFeatured ? -20 : -6;
              card.addEventListener('mouseenter', () => {{
                  card.classList.add('is-tilting');
              }});
              card.addEventListener('mousemove', (e) => {{
                  const r = card.getBoundingClientRect();
                  const localX = e.clientX - r.left;
                  const localY = e.clientY - r.top;
                  const px = localX / r.width;
                  const py = localY / r.height;
                  const ry = (px - 0.5) * 14;
                  const rx = (0.5 - py) * 10;
                  card.style.setProperty('--pr-mx', localX + 'px');
                  card.style.setProperty('--pr-my', localY + 'px');
                  card.style.transform =
                      'translateY(' + hoverY + 'px) ' +
                      'scale(' + baseScale + ') ' +
                      'perspective(1100px) ' +
                      'rotateX(' + rx.toFixed(2) + 'deg) ' +
                      'rotateY(' + ry.toFixed(2) + 'deg)';
              }});
              card.addEventListener('mouseleave', () => {{
                  card.classList.remove('is-tilting');
                  card.style.transform = '';
                  card.style.setProperty('--pr-mx', '50%');
                  card.style.setProperty('--pr-my', '-120px');
              }});
          }});
      }})();
    </script>
    </body></html>
    """).strip()


def main() -> int:
    from playwright.sync_api import sync_playwright

    # Two variants of the static HTML — one per interval — so we can
    # verify both states render cleanly without spinning up Streamlit.
    annual_html  = _build_html(interval="annual")
    monthly_html = _build_html(interval="monthly")

    out_annual  = Path("/tmp/pricing_v2_preview.html")
    out_monthly = Path("/tmp/pricing_v2_preview_monthly.html")
    out_annual.write_text(annual_html)
    out_monthly.write_text(monthly_html)

    targets = [
        (out_annual,  "/tmp/pricing_v2_desktop.png",         1440),
        (out_annual,  "/tmp/pricing_v2_mobile.png",          430),
        (out_monthly, "/tmp/pricing_v2_monthly_desktop.png", 1440),
        (out_monthly, "/tmp/pricing_v2_monthly_mobile.png",  430),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for source, out_png, width in targets:
            ctx = browser.new_context(viewport={"width": width, "height": 900})
            page = ctx.new_page()
            page.goto(f"file://{source}")
            page.wait_for_load_state("networkidle")
            # Let the webfonts settle so the screenshot captures Instrument
            # Serif and Geist, not Times fallback.
            page.wait_for_timeout(1500)
            page.screenshot(path=out_png, full_page=True)
            ctx.close()
        browser.close()

    print("Wrote:")
    for _, png, _ in targets:
        print(f"  {png}")
    print(f"Preview HTML (annual):  {out_annual}")
    print(f"Preview HTML (monthly): {out_monthly}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
