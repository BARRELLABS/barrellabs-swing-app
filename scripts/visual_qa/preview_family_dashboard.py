"""Playwright preview harness for family_dashboard.py.

Extracts _FAMILY_CSS from family_dashboard.py and renders a static
HTML mock with 3 members (one trending up, one steady, one stale)
so we can visually QA the editorial styling without spinning up
Streamlit.

Usage:
    /Users/logancollins/barrellabs-swing-app/.venv/bin/python \
      scripts/visual_qa/preview_family_dashboard.py
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))


def _extract_css() -> str:
    """Pull the _FAMILY_CSS block straight out of family_dashboard.py."""
    src = (PROJECT / "family_dashboard.py").read_text()
    m = re.search(r'_FAMILY_CSS\s*=\s*"""(.*?)"""', src, re.DOTALL)
    if not m:
        raise RuntimeError("Couldn't find _FAMILY_CSS in family_dashboard.py")
    return m.group(1)


def _build_html() -> str:
    css = _extract_css()

    # State A mockup — 3 members (Jake active+up, Mia recent+flat, Owen stale)
    # HTML structure uses fd- prefixed class names that match family_dashboard.py.
    members_html = """
<div class="fd-context">
  <div class="fd-context-left">
    Viewing as <strong>Parent</strong>
  </div>
  <div class="fd-context-right">
    <span>Manage household in Settings</span>
  </div>
</div>

<div class="fd-hero">
  <div class="fd-hero-eyebrow">Your household</div>
  <h1 class="fd-hero-title">The whole family. <span class="ital">One lab.</span></h1>
  <p class="fd-hero-sub">
    A read-only view of every player in your household — latest score, this week's
    top fix, who's been quiet. You're keeping an eye, not steering the wheel —
    each player still owns their swings.
  </p>
</div>

<div class="fd-summary">
  <div class="fd-sum-cell">
    <div class="fd-sum-eyebrow">This week</div>
    <div class="fd-sum-val">12 swings</div>
    <div class="fd-sum-label">across 3 players</div>
  </div>
  <div class="fd-sum-cell">
    <div class="fd-sum-eyebrow">Top mover</div>
    <div class="fd-sum-val">Jake</div>
    <div class="fd-sum-label">household leader</div>
  </div>
  <div class="fd-sum-cell">
    <div class="fd-sum-eyebrow">Players</div>
    <div class="fd-sum-val">3 of 4</div>
    <div class="fd-sum-label">seats used</div>
  </div>
  <div class="fd-sum-cell">
    <div class="fd-sum-eyebrow">Avg score</div>
    <div class="fd-sum-val">82</div>
    <div class="fd-sum-label">household, last 7 days</div>
  </div>
</div>

<div class="fd-grid-eyebrow">Players</div>
<h2 class="fd-grid-title">In the <span class="ital">lab.</span></h2>

<div class="fd-grid">

  <!-- Card 1 — Jake, active, trending up -->
  <div class="fd-card">
    <div class="fd-card-top">
      <div class="fd-identity">
        <div class="fd-avatar">J</div>
        <div>
          <h3 class="fd-member-name">Jake</h3>
          <div class="fd-member-meta">
            <span>13</span><span class="dot">&middot;</span>
            <span>2B</span><span class="dot">&middot;</span>
            <span>R</span>
          </div>
        </div>
      </div>
      <div class="fd-badge active">&#9679; Today</div>
    </div>

    <div class="fd-verdict">
      Best week <span class="accent">this month.</span>
    </div>

    <div class="fd-latest">
      <div class="fd-score">87</div>
      <div class="fd-score-meta">
        <div class="fd-latest-eyebrow">Latest swing</div>
        <div class="fd-delta-line">
          <span class="fd-delta-date">May 21</span>
          <span class="fd-delta-val up">&#9650; +4</span>
        </div>
      </div>
    </div>

    <div class="fd-spark-wrap">
      <span class="fd-spark-tick top">90</span>
      <span class="fd-spark-tick bottom">60</span>
      <svg class="fd-spark" viewBox="0 0 240 36" preserveAspectRatio="none">
        <polyline fill="none" stroke="rgba(244,239,230,0.32)" stroke-width="1.5"
          points="0,32 24,28 48,30 72,22 96,18 120,20 144,16 168,14 192,12 216,8 240,6"/>
        <circle cx="240" cy="6" r="3.5" fill="#E8C170" stroke="#0A0B0E" stroke-width="2"/>
      </svg>
    </div>

    <div class="fd-topfix">
      <div class="fd-topfix-eyebrow">ASK&nbsp;HIM</div>
      <div class="fd-topfix-text">
        Ask Jake about <strong>keeping his front shoulder closed</strong> —
        he's been working on it all week.
      </div>
    </div>
  </div>

  <!-- Card 2 — Mia, recent, holding steady -->
  <div class="fd-card">
    <div class="fd-card-top">
      <div class="fd-identity">
        <div class="fd-avatar tint-warm">M</div>
        <div>
          <h3 class="fd-member-name">Mia</h3>
          <div class="fd-member-meta">
            <span>11</span><span class="dot">&middot;</span>
            <span>SS</span><span class="dot">&middot;</span>
            <span>L</span>
          </div>
        </div>
      </div>
      <div class="fd-badge recent">3 days</div>
    </div>

    <div class="fd-verdict mute">
      Holding steady. Building up.
    </div>

    <div class="fd-latest">
      <div class="fd-score">74</div>
      <div class="fd-score-meta">
        <div class="fd-latest-eyebrow">Latest swing</div>
        <div class="fd-delta-line">
          <span class="fd-delta-date">May 18</span>
          <span class="fd-delta-val flat">&#8212; +0</span>
        </div>
      </div>
    </div>

    <div class="fd-spark-wrap">
      <span class="fd-spark-tick top">90</span>
      <span class="fd-spark-tick bottom">60</span>
      <svg class="fd-spark" viewBox="0 0 240 36" preserveAspectRatio="none">
        <polyline fill="none" stroke="rgba(244,239,230,0.32)" stroke-width="1.5"
          points="0,20 24,22 48,24 72,20 96,18 120,20 144,18 168,16 192,18 216,20 240,18"/>
        <circle cx="240" cy="18" r="3.5" fill="#C8C4BB" stroke="#0A0B0E" stroke-width="2"/>
      </svg>
    </div>

    <div class="fd-topfix">
      <div class="fd-topfix-eyebrow">ASK&nbsp;HER</div>
      <div class="fd-topfix-text">
        Ask Mia how her <strong>hip-shoulder separation</strong> is feeling —
        she's getting close to a breakthrough.
      </div>
    </div>
  </div>

  <!-- Card 3 — Owen, STALE -->
  <div class="fd-card is-stale">
    <div class="fd-card-top">
      <div class="fd-identity">
        <div class="fd-avatar muted">O</div>
        <div>
          <h3 class="fd-member-name">Owen</h3>
          <div class="fd-member-meta">
            <span>15</span><span class="dot">&middot;</span>
            <span>OF</span><span class="dot">&middot;</span>
            <span>R</span>
          </div>
        </div>
      </div>
      <div class="fd-badge stale">12 days</div>
    </div>

    <div class="fd-verdict mute">
      Hasn't filmed since the 9th.
    </div>

    <div class="fd-latest">
      <div class="fd-score">85</div>
      <div class="fd-score-meta">
        <div class="fd-latest-eyebrow">Last swing</div>
        <div class="fd-delta-line">
          <span class="fd-delta-date">May 9</span>
          <span class="fd-delta-val down">&#9660; &minus;3</span>
        </div>
      </div>
    </div>

    <div class="fd-spark-wrap">
      <span class="fd-spark-tick top">90</span>
      <span class="fd-spark-tick bottom">60</span>
      <svg class="fd-spark" viewBox="0 0 240 36" preserveAspectRatio="none">
        <polyline fill="none" stroke="rgba(244,239,230,0.22)" stroke-width="1.5"
          points="0,10 24,12 48,10 72,14 96,12 120,16 144,14 168,18 192,20 216,22 240,24"/>
        <circle cx="240" cy="24" r="3.5" fill="rgba(244,239,230,0.42)" stroke="#0A0B0E" stroke-width="2"/>
      </svg>
    </div>

    <div class="fd-nudge">
      <div class="fd-nudge-text">
        <strong>Send him a soft nudge?</strong>
        We'll push a friendly reminder to his app.
      </div>
      <button style="background:rgba(230,69,48,0.15);color:#E64530;border:1px solid rgba(230,69,48,0.30);
                     border-radius:100px;padding:8px 16px;font-family:var(--fd-mono);font-size:10px;
                     font-weight:700;letter-spacing:0.18em;text-transform:uppercase;cursor:pointer;
                     white-space:nowrap;">Nudge Owen</button>
    </div>
  </div>

</div><!-- .fd-grid -->

<div class="fd-add-row">
  <div>
    <div class="fd-add-title">Add another <span class="accent">player</span> to your household.</div>
    <div class="fd-add-meta">3 of 4 seats used</div>
  </div>
  <button style="background:var(--bone);color:var(--ink);border:none;border-radius:100px;
                 padding:12px 28px;font-family:var(--fd-mono);font-size:10.5px;font-weight:700;
                 letter-spacing:0.20em;text-transform:uppercase;cursor:pointer;
                 box-shadow:0 12px 28px -16px rgba(244,239,230,0.40);">+ Invite Player</button>
</div>

<div class="fd-foot">
  Parents see what their kids see. Kids own their data.
</div>
"""

    return textwrap.dedent(f"""
    <!doctype html>
    <html><head><meta charset="utf-8">
    <title>BarrelLabs &middot; Family Dashboard preview</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    {css}
    <style>body {{ margin: 0; background: #0A0B0E; padding: 56px 32px; }}</style>
    </head><body>
    <div class="fd-wrap">
      <div class="fd-bg-fx"></div>
      {members_html}
    </div>
    </body></html>
    """).strip()


def main() -> int:
    from playwright.sync_api import sync_playwright

    html = _build_html()
    out_html = Path("/tmp/family_dashboard_preview.html")
    out_html.write_text(html)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for w, name in [(1440, "family_dashboard_desktop.png"),
                        (430,  "family_dashboard_mobile.png")]:
            ctx = browser.new_context(viewport={"width": w, "height": 900})
            page = ctx.new_page()
            page.goto(f"file://{out_html}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
            page.screenshot(path=f"/tmp/{name}", full_page=True)
            ctx.close()
        browser.close()
    print("Wrote /tmp/family_dashboard_desktop.png + mobile.png")
    print(f"Preview HTML: {out_html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
