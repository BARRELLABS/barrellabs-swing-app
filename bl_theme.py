"""
BarrelLabs / SwingAI — Global design system.

This module is the single source of truth for the app's visual language.
Any page (Dashboard, Upload, Saved Report, Development Tracker,
Performance Over Time, Compare Swings, Settings, Billing) should call
`inject_global_theme()` once near the top of its render flow so the
shared tokens and component classes are available.

EDITORIAL CANONICAL TOKENS (source of truth)
    --bone / --bone-dim / --bone-mute / --bone-faint
    --ink / --ink-elev
    --gold / --gold-deep
    --red / --red-hover
    --serif / --sans / --mono

LEGACY ALIASES (point at the canonical tokens above)
    --bl-red / --bl-red-hover / --bl-red-glow / --bl-red-soft
    --bl-gold / --bl-serif
    --bl-bg
    --bl-surface-1 / --bl-surface-2
    --bl-line / --bl-line-hi
    --bl-ink-100 / --bl-ink-80 / --bl-ink-60 / --bl-ink-40
    --bl-radius-xl / --bl-radius-lg / --bl-radius-md / --bl-radius-sm
    --bl-space-2xs ... --bl-space-xl
    --bl-sans / --bl-mono

PYTHON CONSTANTS (for Plotly / SVG / PDF — no CSS vars there)
    BL_INK / BL_BONE / BL_GOLD / BL_RED / BL_POSITIVE / BL_SECONDARY / ...
    BL_FONT_SANS / BL_FONT_MONO / BL_FONT_SERIF

REUSABLE COMPONENT CLASSES
    .bl-page              top-level page wrapper (z-index lifted above bg)
    .bl-section           vertical spacing slot
    .bl-section-header    eyebrow + title + subline trio
    .bl-section-eyebrow   mono red uppercase label
    .bl-section-title     large display headline
    .bl-section-sub       muted supporting line under a section title
    .bl-card              translucent card surface w/ hairline, blur, hover lift
    .bl-card-eyebrow      small mono uppercase label inside a card
    .bl-card-title        card heading (1.1rem, -0.02em)
    .bl-card-value        the numeric/big readout value inside a card
    .bl-card-sub          muted supporting text under a title/value
    .bl-cta               wrap a `st.button` to render it as a red pill CTA
    .bl-divider           subtle hairline separator

USAGE
    from bl_theme import inject_global_theme
    inject_global_theme()
    st.markdown('<div class="bl-page">', unsafe_allow_html=True)
    ... render with .bl-card / .bl-section-header / etc ...
    st.markdown('</div>', unsafe_allow_html=True)
"""

from __future__ import annotations

import streamlit as st


BL_GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');

:root {
    /* ===========  EDITORIAL CANONICAL TOKENS (source of truth)  ===========
       Matches the household / training-plan pages (family_dashboard.py et al).
       Everything else (the --bl-* names below) is aliased to these so legacy
       pages inherit the editorial palette without per-page edits. */
    --bone:        #F4EFE6;
    --bone-dim:    #C8C4BB;
    --bone-mute:   #8a857b;
    --bone-faint:  #5a564f;
    --ink:         #0A0B0E;
    --ink-elev:    #15171c;
    --gold:        #E8C170;
    --gold-deep:   #C9A350;
    --red:         #E64530;
    --red-hover:   #f0563f;

    --serif:  'Instrument Serif', 'Times New Roman', Georgia, serif;
    --sans:   'Geist', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --mono:   'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

    /* ===========  LEGACY ALIASES (→ editorial canonical above)  ===========
       Existing pages reference these names; pointing them at the editorial
       tokens flips the whole legacy surface to editorial in one place. */
    --bl-red:         var(--red);
    --bl-red-hover:   var(--red-hover);
    --bl-red-glow:    rgba(230,69,48,0.28);
    --bl-red-soft:    rgba(230,69,48,0.08);

    --bl-gold:        var(--gold);
    --bl-serif:       var(--serif);

    --bl-bg:          var(--ink);
    --bl-surface-1:   rgba(244,239,230,0.02);
    --bl-surface-2:   rgba(244,239,230,0.04);

    --bl-line:        rgba(244,239,230,0.10);
    --bl-line-hi:     rgba(244,239,230,0.18);

    --bl-ink-100:     var(--bone);
    --bl-ink-80:      var(--bone-dim);
    --bl-ink-60:      var(--bone-mute);
    --bl-ink-40:      var(--bone-faint);

    --bl-radius-xl:   28px;
    --bl-radius-lg:   24px;
    --bl-radius-md:   16px;
    --bl-radius-sm:   12px;

    --bl-space-2xs:   .35rem;
    --bl-space-xs:    .6rem;
    --bl-space-sm:    .9rem;
    --bl-space-md:    1.4rem;
    --bl-space-lg:    2rem;
    --bl-space-xl:    2.8rem;

    --bl-sans:  var(--sans);
    --bl-mono:  var(--mono);

    --bl-cta-shadow:  0 12px 30px -10px rgba(230,69,48,0.42);
}

/* ===========  LEFT SIDEBAR — REMOVED  ===========
   The app collapsed to a single navigation system (the top Edge
   masthead). The legacy left st.sidebar is gone; hide the Streamlit
   sidebar element AND its collapsed-state expand arrow so no empty
   rail or stray collapse control ever paints. */
section[data-testid="stSidebar"],
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* ===========  GLOBAL BACKGROUND  =========== */
[data-testid="stAppViewContainer"] {
    background: var(--ink) !important;
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    top: -320px; left: 50%; transform: translateX(-50%);
    width: 1600px; height: 760px;
    background:
        radial-gradient(ellipse at 35% 50%,
            rgba(230,69,48,0.075) 0%,
            rgba(230,69,48,0.020) 30%,
            transparent 70%),
        radial-gradient(ellipse at 78% 40%,
            rgba(232,193,112,0.035) 0%,
            transparent 70%);
    pointer-events: none;
    z-index: 0;
    filter: blur(8px);
}

/* ===========  GLOBAL PAGE CONTAINER  =========== */
section.main > div.block-container,
section.main .block-container,
[data-testid="stMainBlockContainer"] {
    max-width: 1280px !important;
    padding-top: 0.4rem !important;
    padding-bottom: 4rem !important;
    padding-left: 2.4rem !important;
    padding-right: 2.4rem !important;
}
@media (max-width: 720px) {
    section.main > div.block-container,
    section.main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        padding-top: 0.3rem !important;
    }
}

/* Hide Streamlit's top chrome (header, toolbar, decoration) so the
   page content can start flush with the top of the viewport. */
header[data-testid="stHeader"],
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
    height: 0 !important;
    visibility: hidden !important;
}
.stAppDeployButton, .stDeployButton { display: none !important; }
.stApp > header { display: none !important; }

/* ===========  TYPOGRAPHY DEFAULTS  =========== */
html, body, [data-testid="stAppViewContainer"] {
    font-family: var(--bl-sans);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* ===========  PAGE WRAPPER  =========== */
.bl-page {
    position: relative;
    z-index: 1;
    font-family: var(--bl-sans);
}
.bl-section {
    margin-bottom: var(--bl-space-lg);
}
.bl-divider {
    height: 1px;
    background: var(--bl-line);
    margin: 1.8rem 0;
    border: none;
}

/* ===========  SECTION HEADER  =========== */
.bl-section-header {
    margin-bottom: 1.6rem;
    padding-bottom: 1.6rem;
    border-bottom: 1px solid var(--bl-line);
}
.bl-section-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.7rem;
    color: var(--bl-red);
    letter-spacing: 0.24em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 0.85rem;
}
.bl-section-title {
    font-family: var(--bl-sans);
    font-size: 3rem;
    font-weight: 700;
    letter-spacing: -0.045em;
    color: var(--bl-ink-100);
    margin: 0;
    line-height: 1.04;
}
.bl-section-sub {
    margin-top: 0.85rem;
    color: var(--bl-ink-60);
    font-size: 1rem;
    max-width: 580px;
    line-height: 1.55;
    font-weight: 400;
}

/* ===========  CARD  =========== */
.bl-card {
    position: relative;
    background: var(--bl-surface-1);
    border: 1px solid var(--bl-line);
    border-radius: var(--bl-radius-lg);
    padding: 1.8rem;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    overflow: hidden;
    height: 100%;
    box-shadow:
        0 1px 0 rgba(255,255,255,0.03) inset,
        0 20px 50px -30px rgba(0,0,0,0.7);
    transition:
        transform .26s cubic-bezier(.2,.7,.2,1),
        border-color .26s ease,
        background .26s ease,
        box-shadow .26s ease;
    font-family: var(--bl-sans);
}
.bl-card:hover {
    border-color: var(--bl-line-hi);
    background: var(--bl-surface-2);
    transform: translateY(-2px);
    box-shadow:
        0 1px 0 rgba(255,255,255,0.04) inset,
        0 26px 60px -28px rgba(0,0,0,0.8);
}
.bl-card-eyebrow {
    font-family: var(--bl-mono);
    font-size: 0.62rem;
    letter-spacing: 0.22em;
    font-weight: 600;
    color: var(--bl-ink-60);
    text-transform: uppercase;
}
.bl-card-title {
    font-family: var(--bl-sans);
    font-size: 1.1rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--bl-ink-100);
    margin-top: 0.55rem;
}
.bl-card-value {
    font-family: var(--bl-sans);
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.035em;
    color: var(--bl-ink-100);
    line-height: 1;
    margin-top: 0.7rem;
}
.bl-card-sub {
    color: var(--bl-ink-60);
    font-size: 0.88rem;
    margin-top: 0.7rem;
    line-height: 1.5;
}

/* ===========  CTA PILL  =========== */
.bl-cta div.stButton > button {
    background: var(--bl-red) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    box-shadow:
        var(--bl-cta-shadow),
        inset 0 1px 0 rgba(255,255,255,0.14) !important;
    border-radius: 999px !important;
    color: white !important;
    font-family: var(--bl-sans) !important;
    font-weight: 600 !important;
    font-size: 0.96rem !important;
    letter-spacing: -0.005em !important;
    padding: 0.95rem 2rem !important;
    transition: all .22s cubic-bezier(.2,.7,.2,1) !important;
}
.bl-cta div.stButton > button:hover {
    transform: translateY(-2px);
    background: var(--bl-red-hover) !important;
    box-shadow:
        0 18px 40px -10px rgba(255,59,48,0.5),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
.bl-cta div.stButton > button:active {
    transform: translateY(0);
}

/* Secondary, ghost-style button wrapper (for less-emphasized actions). */
.bl-ghost div.stButton > button {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bl-ink-80) !important;
    border-radius: 999px !important;
    font-weight: 500 !important;
    padding: 0.7rem 1.4rem !important;
    transition: all .2s ease !important;
}
.bl-ghost div.stButton > button:hover {
    background: rgba(255,255,255,0.05) !important;
    border-color: var(--bl-line-hi) !important;
    color: var(--bl-ink-100) !important;
}

/* ===========  GLOBAL DEFAULT BUTTON LOOK  ===========
   Generic st.button / st.download_button that isn't a nav tab, an action
   button, or a .bl-cta/.bl-ghost wrapper would otherwise show raw Streamlit
   chrome (the "basic buttons" look). Give them the Edge default.
   CRITICAL: NO !important here. The nav (.st-key-bl_edge_navbar button) and the
   action-button rules below are all !important, so they win over this and stay
   exactly as designed. This rule only "fills in" everything those don't cover.
   That's why this is safe for the nav, unlike the old !important global theme. */
div.stButton > button,
div.stDownloadButton > button,
div[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--bl-line);
    color: var(--bl-ink-100);
    border-radius: 10px;
    font-family: var(--bl-sans);
    font-weight: 600;
    letter-spacing: 0.005em;
    transition: background .18s ease, border-color .18s ease, transform .18s ease;
}
div.stButton > button:hover,
div.stDownloadButton > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
    background: rgba(232,193,112,0.08);
    border-color: rgba(232,193,112,0.45);
    transform: translateY(-1px);
}
div.stButton > button:active,
div.stDownloadButton > button:active { transform: translateY(0); }

/* ===========  ACTION BUTTONS -> match the Edge nav button look  ===========
   Ghost / mono / uppercase, same language as the top nav. SCOPED to specific
   widget-key prefixes ONLY (sessions open/download/delete, swing-report,
   progress, analyze) so this never touches the nav (.st-key-bl_edge_navbar)
   or any other button. */
[class*="st-key-srl_"] button,
[class*="st-key-sr_"] button,
[class*="st-key-srp_"] button,
[class*="st-key-hc_quick_"] button,
.st-key-hc_progress_pdf button,
.st-key-analyze_swing_btn button {
    background: transparent !important;
    border: 1px solid rgba(244,239,230,0.12) !important;
    color: #A6A9B0 !important;
    font-family: 'Geist Mono', ui-monospace, SFMono-Regular, monospace !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.13em !important;
    text-transform: uppercase !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    transition: color .22s, background-color .22s, border-color .22s, transform .22s !important;
}
[class*="st-key-srl_"] button p, [class*="st-key-srl_"] button div, [class*="st-key-srl_"] button span,
[class*="st-key-sr_"] button p, [class*="st-key-sr_"] button div, [class*="st-key-sr_"] button span,
[class*="st-key-srp_"] button p, [class*="st-key-srp_"] button div, [class*="st-key-srp_"] button span,
[class*="st-key-hc_quick_"] button p, [class*="st-key-hc_quick_"] button div, [class*="st-key-hc_quick_"] button span,
.st-key-hc_progress_pdf button p, .st-key-hc_progress_pdf button div, .st-key-hc_progress_pdf button span,
.st-key-analyze_swing_btn button p, .st-key-analyze_swing_btn button div, .st-key-analyze_swing_btn button span {
    font: inherit !important; letter-spacing: inherit !important; color: inherit !important; margin: 0 !important;
}
[class*="st-key-srl_"] button:hover,
[class*="st-key-sr_"] button:hover,
[class*="st-key-srp_"] button:hover,
[class*="st-key-hc_quick_"] button:hover,
.st-key-hc_progress_pdf button:hover,
.st-key-analyze_swing_btn button:hover {
    color: #EFE9DB !important;
    background: rgba(244,239,230,0.045) !important;
    border-color: rgba(244,239,230,0.14) !important;
    transform: translateY(-0.5px);
}
/* Analyze = the primary action: same nav language but the nav-primary elevated
   fill so it reads as the main CTA. */
.st-key-analyze_swing_btn button {
    color: #F8F2E0 !important;
    background: linear-gradient(180deg, rgba(244,239,230,0.095), rgba(244,239,230,0.035)) !important;
    border-color: rgba(244,239,230,0.14) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10), 0 0 16px -6px rgba(232,193,112,0.45) !important;
}
</style>
"""


# ===========================================================================
#  PYTHON-ACCESSIBLE CONSTANTS
#  For code that cannot read CSS custom properties — Plotly figures, inline
#  SVG (sparklines), and ReportLab PDFs. Keep these in sync with the editorial
#  canonical tokens in :root above.
# ===========================================================================
BL_INK        = "#0A0B0E"
BL_INK_ELEV   = "#15171C"
BL_BONE       = "#F4EFE6"
BL_BONE_DIM   = "#C8C4BB"
BL_BONE_MUTE  = "#8A857B"
BL_BONE_FAINT = "#5A564F"
BL_GOLD       = "#E8C170"
BL_GOLD_DEEP  = "#C9A350"
BL_RED        = "#E64530"

# Semantic chart roles (no green exists in the editorial palette):
#   positive / "trending up" → gold;  negative → red;  secondary trace → bone-dim.
BL_POSITIVE   = BL_GOLD
BL_NEGATIVE   = BL_RED
BL_SECONDARY  = BL_BONE_DIM

# Font stacks (Plotly / SVG take plain strings, not CSS variables).
BL_FONT_SANS  = "Geist, Inter, system-ui, sans-serif"
BL_FONT_MONO  = "Geist Mono, JetBrains Mono, monospace"
BL_FONT_SERIF = "Instrument Serif, Georgia, serif"


def inject_global_theme() -> None:
    """Inject the BarrelLabs global design system stylesheet.

    Safe to call from every page; Streamlit reruns the script on each
    interaction and CSS must be re-emitted each run. No-op beyond a
    single `st.markdown` call.
    """
    st.markdown(BL_GLOBAL_CSS, unsafe_allow_html=True)
