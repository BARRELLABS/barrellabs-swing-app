"""
BarrelLabs / SwingAI — Global design system.

This module is the single source of truth for the app's visual language.
Any page (Dashboard, Upload, Saved Report, Development Tracker,
Performance Over Time, Compare Swings, Settings, Billing) should call
`inject_global_theme()` once near the top of its render flow so the
shared tokens and component classes are available.

EXPOSED TOKENS (CSS custom properties)
    --bl-red / --bl-red-hover / --bl-red-glow / --bl-red-soft
    --bl-bg
    --bl-surface-1 / --bl-surface-2
    --bl-line / --bl-line-hi
    --bl-ink-100 / --bl-ink-80 / --bl-ink-60 / --bl-ink-40
    --bl-radius-xl / --bl-radius-lg / --bl-radius-md / --bl-radius-sm
    --bl-space-2xs ... --bl-space-xl
    --bl-sans / --bl-mono

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bl-red:         #FF3B30;
    --bl-red-hover:   #ff4d43;
    --bl-red-glow:    rgba(255,59,48,0.28);
    --bl-red-soft:    rgba(255,59,48,0.08);

    --bl-bg:          #050505;
    --bl-surface-1:   rgba(255,255,255,0.02);
    --bl-surface-2:   rgba(255,255,255,0.035);

    --bl-line:        rgba(255,255,255,0.06);
    --bl-line-hi:     rgba(255,255,255,0.12);

    --bl-ink-100:     #fafafa;
    --bl-ink-80:      #d4d4d4;
    --bl-ink-60:      #8b8b8b;
    --bl-ink-40:      #5c5c5c;

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

    --bl-sans:  'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
    --bl-mono:  'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

    --bl-cta-shadow:  0 12px 30px -10px rgba(255,59,48,0.42);
}

/* ===========  GLOBAL BACKGROUND  =========== */
[data-testid="stAppViewContainer"] {
    background: #050505 !important;
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    top: -320px; left: 50%; transform: translateX(-50%);
    width: 1600px; height: 760px;
    background:
        radial-gradient(ellipse at 35% 50%,
            rgba(255,59,48,0.085) 0%,
            rgba(255,59,48,0.025) 30%,
            transparent 70%),
        radial-gradient(ellipse at 78% 40%,
            rgba(30,58,138,0.04) 0%,
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
</style>
"""


def inject_global_theme() -> None:
    """Inject the BarrelLabs global design system stylesheet.

    Safe to call from every page; Streamlit reruns the script on each
    interaction and CSS must be re-emitted each run. No-op beyond a
    single `st.markdown` call.
    """
    st.markdown(BL_GLOBAL_CSS, unsafe_allow_html=True)
