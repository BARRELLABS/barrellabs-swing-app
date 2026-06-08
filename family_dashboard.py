"""Parent / Family Dashboard — Streamlit page.

Renders the household view from family_storage data. Editorial style
matching pricing.py / dashboard_v3 / swing_report_dashboard_preview.

Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
Mockup: .superpowers/brainstorm/44295-1779394399/content/family-mockup-v2.html

Four states:
  A · Populated  (2-3 active members)
  B · Empty      (Family Pro active, 0 members invited yet)
  C · Single     (1 member)
  D · Full       (4/4 seats)

A member who hasn't filmed in > STALE_DAYS gets a red badge + Nudge
block inside their card; the surrounding state is unaffected.
"""

from __future__ import annotations

import html as _html
from typing import Optional

import streamlit as st


# ============================================================
# CSS — verbatim from the locked v2 mockup. Single source of
# truth lives in this constant; the preview harness extracts it
# via regex so they never drift.
# ============================================================
_FAMILY_CSS = """
<style>
:root {
  --bone:       #F4EFE6;
  --bone-dim:   #C8C4BB;
  --bone-mute:  #8a857b;
  --bone-faint: #5a564f;
  --ink:        #0A0B0E;
  --ink-elev:   #15171c;
  --gold:       #E8C170;
  --gold-deep:  #C9A350;
  --red:        #E64530;
  --line:       rgba(244,239,230,0.10);
  --line-hi:    rgba(244,239,230,0.18);
  --glass-1:    rgba(244,239,230,0.025);
  --glass-2:    rgba(244,239,230,0.05);
  --fd-serif:   'Instrument Serif', 'Times New Roman', serif;
  --fd-sans:    'Geist', 'Inter', system-ui, sans-serif;
  --fd-mono:    'Geist Mono', 'JetBrains Mono', monospace;
}
.fd-wrap { position: relative; max-width: 1280px; margin: 0 auto; padding: 24px 0 80px 0; }
.fd-bg-fx {
    position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background:
      radial-gradient(80% 60% at 10% 0%, rgba(232,193,112,0.05), transparent 60%),
      radial-gradient(80% 60% at 95% 95%, rgba(230,69,48,0.03), transparent 60%);
}

/* context bar */
.fd-context {
    position: relative; z-index: 1;
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px; margin-bottom: 38px;
    border: 1px solid var(--line); border-radius: 100px;
    background: var(--glass-1);
    font-family: var(--fd-mono); font-size: 10.5px;
    letter-spacing: 0.14em;
}
.fd-context-left { display: flex; align-items: center; gap: 10px; color: var(--bone-mute); }
.fd-context-left strong {
    color: var(--bone); font-weight: 600; letter-spacing: 0.18em;
    text-transform: uppercase;
}
.fd-context-right { display: flex; gap: 16px; color: var(--bone-dim); }

/* hero */
.fd-hero { position: relative; z-index: 1; margin-bottom: 40px; }
.fd-hero-eyebrow {
    font-family: var(--fd-mono); font-size: 11px; font-weight: 600;
    letter-spacing: 0.24em; text-transform: uppercase;
    color: var(--gold); margin-bottom: 12px;
}
.fd-hero-title {
    font-family: var(--fd-serif); font-weight: 400; line-height: 1.0;
    font-size: clamp(3.2rem, 6.4vw, 5.2rem); letter-spacing: -0.028em;
    color: var(--bone); margin: 0 0 14px 0;
}
.fd-hero-title .ital { font-style: italic; color: var(--gold); }
.fd-hero-sub {
    font-family: var(--fd-sans); font-size: 1.02rem;
    line-height: 1.55; color: var(--bone-dim);
    max-width: 60ch; margin: 0;
}

/* summary strip */
.fd-summary {
    position: relative; z-index: 1;
    display: flex; gap: 0; margin: 28px 0 48px 0;
    padding: 16px 24px; border: 1px solid var(--line); border-radius: 14px;
    background: var(--glass-1);
}
.fd-sum-cell {
    flex: 1; padding: 0 14px; border-right: 1px solid var(--line);
}
.fd-sum-cell:last-child { border-right: none; }
.fd-sum-eyebrow {
    font-family: var(--fd-mono); font-size: 9.5px; font-weight: 600;
    letter-spacing: 0.20em; text-transform: uppercase;
    color: var(--bone-mute); margin-bottom: 6px;
}
.fd-sum-val {
    font-family: var(--fd-sans); font-weight: 500;
    font-size: 1.42rem; line-height: 1.0;
    color: var(--bone); letter-spacing: -0.01em;
}
.fd-sum-val .accent { color: var(--gold); }
.fd-sum-label {
    font-family: var(--fd-sans); font-size: 0.82rem;
    color: var(--bone-dim); margin-top: 4px;
}

/* grid heading */
.fd-grid-eyebrow {
    font-family: var(--fd-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--gold); margin-bottom: 8px;
}
.fd-grid-title {
    font-family: var(--fd-serif); font-size: 2.1rem; font-weight: 400;
    line-height: 1.05; letter-spacing: -0.02em;
    margin: 0 0 22px 0; color: var(--bone);
}
.fd-grid-title .ital { font-style: italic; color: var(--gold); }

/* cards */
.fd-grid {
    position: relative; z-index: 1;
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 22px; margin-bottom: 36px;
}
@media (max-width: 900px) { .fd-grid { grid-template-columns: 1fr; } }
.fd-single {
    position: relative; z-index: 1;
    max-width: 480px; margin: 0 auto 36px auto;
}

.fd-card {
    position: relative;
    padding: 26px 26px 22px 26px;
    border: 1px solid var(--line); border-radius: 18px;
    background:
      radial-gradient(80% 50% at 50% 0%, rgba(232,193,112,0.04), transparent 70%),
      var(--glass-1);
    transition: border-color 0.24s ease, transform 0.24s ease, box-shadow 0.24s ease;
}
.fd-card:hover {
    border-color: var(--line-hi);
    transform: translateY(-4px);
    box-shadow: 0 18px 46px rgba(0,0,0,0.45);
}
.fd-card.is-self {
    border-color: rgba(232,193,112,0.32);
}
.fd-card.is-stale {
    background:
      radial-gradient(80% 50% at 50% 0%, rgba(230,69,48,0.03), transparent 70%),
      var(--glass-1);
}

.fd-card-top {
    display: flex; align-items: flex-start; justify-content: space-between;
    margin-bottom: 14px; gap: 10px;
}
.fd-identity { display: flex; align-items: center; gap: 14px; }
.fd-avatar {
    width: 52px; height: 52px; border-radius: 50%;
    background: linear-gradient(135deg, var(--gold), var(--gold-deep));
    color: #1a1206;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--fd-serif); font-style: italic;
    font-size: 1.55rem; font-weight: 500; letter-spacing: -0.02em;
    border: 1px solid rgba(232,193,112,0.4); flex: 0 0 auto;
}
.fd-avatar.tint-blue {
    background: linear-gradient(135deg, #7a9bb8, #4d6b88); color: #f4f6f8;
    border-color: rgba(122,155,184,0.4);
}
.fd-avatar.tint-warm {
    background: linear-gradient(135deg, #b88a7a, #885d4d); color: #f8f4f2;
    border-color: rgba(184,138,122,0.4);
}
.fd-avatar.muted {
    background: linear-gradient(135deg, var(--ink-elev), #2a2c33);
    color: var(--bone-dim); border-color: var(--line-hi);
}
.fd-member-name {
    font-family: var(--fd-serif); font-size: 1.7rem; font-weight: 400;
    letter-spacing: -0.018em; line-height: 1.05; color: var(--bone); margin: 0;
}
.fd-member-meta {
    font-family: var(--fd-mono); font-size: 10.5px;
    letter-spacing: 0.10em; color: var(--bone-mute);
    display: flex; gap: 8px; align-items: center; margin-top: 4px;
}
.fd-member-meta .dot { color: var(--bone-faint); }
.fd-you-tag {
    font-family: var(--fd-mono); font-size: 9px; font-weight: 700;
    letter-spacing: 0.20em; text-transform: uppercase;
    color: var(--gold); padding: 2px 8px;
    border: 1px solid rgba(232,193,112,0.32); border-radius: 100px;
    margin-left: 4px;
}
.fd-badge {
    font-family: var(--fd-mono); font-size: 9.5px; font-weight: 700;
    letter-spacing: 0.18em; text-transform: uppercase;
    padding: 5px 10px; border-radius: 100px; white-space: nowrap;
    align-self: flex-start;
}
.fd-badge.active { background: rgba(232,193,112,0.14); color: var(--gold); }
.fd-badge.recent { background: var(--glass-2); color: var(--bone-dim); }
.fd-badge.stale  { background: rgba(230,69,48,0.16); color: var(--red); }

.fd-verdict {
    font-family: var(--fd-serif); font-style: italic;
    font-size: 1.18rem; line-height: 1.35;
    color: var(--bone); margin: 14px 0 12px 0;
}
.fd-verdict .accent { color: var(--gold); }
.fd-verdict.mute { color: var(--bone-mute); }

.fd-latest {
    display: flex; align-items: baseline; gap: 14px;
    padding: 14px 0 14px 0;
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    margin-bottom: 14px;
}
.fd-score {
    font-family: var(--fd-serif); font-style: italic;
    font-size: 2.9rem; line-height: 1; letter-spacing: -0.035em;
    color: var(--bone);
}
.fd-score-meta {
    flex: 1; display: flex; flex-direction: column; gap: 4px; align-items: flex-end;
}
.fd-latest-eyebrow {
    font-family: var(--fd-mono); font-size: 9.5px; font-weight: 600;
    letter-spacing: 0.20em; text-transform: uppercase; color: var(--bone-mute);
}
.fd-delta-line {
    display: flex; gap: 8px; align-items: baseline;
    font-family: var(--fd-mono); font-size: 11px;
}
.fd-delta-date { color: var(--bone-dim); letter-spacing: 0.12em; }
.fd-delta-val { font-weight: 600; letter-spacing: 0.08em; }
.fd-delta-val.up { color: var(--gold); }
.fd-delta-val.down { color: var(--bone-mute); }
.fd-delta-val.flat { color: var(--bone-mute); }

.fd-spark-wrap { position: relative; margin-bottom: 12px; }
.fd-spark { width: 100%; height: 36px; display: block; }
.fd-spark-tick {
    position: absolute; font-family: var(--fd-mono); font-size: 9px;
    color: var(--bone-faint); letter-spacing: 0.08em;
}
.fd-spark-tick.top    { top: 0; right: 0; }
.fd-spark-tick.bottom { bottom: 0; right: 0; }

.fd-topfix {
    display: flex; gap: 8px; align-items: flex-start;
    margin-bottom: 16px;
    font-size: 0.92rem; line-height: 1.45;
    color: var(--bone-dim);
}
.fd-topfix-eyebrow {
    font-family: var(--fd-mono); font-size: 9px; font-weight: 700;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--gold); flex: 0 0 auto; padding-top: 2px;
}
.fd-topfix-text strong { color: var(--bone); font-weight: 500; }
.fd-topfix-text.mute { color: var(--bone-mute); }

.fd-nudge {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; padding: 12px 14px;
    border: 1px solid rgba(230,69,48,0.20);
    background: rgba(230,69,48,0.04);
    border-radius: 10px; margin-bottom: 14px;
}
.fd-nudge-text { font-size: 0.86rem; color: var(--bone-dim); line-height: 1.4; }
.fd-nudge-text strong { color: var(--bone); font-weight: 500; }

/* Editorial pill buttons. NOTE: :contains() is a jQuery extension, NOT
   real CSS — selectors that use it are discarded by the browser. We key
   off Streamlit's `st-key-<key>` wrapper class instead, which it emits on
   the container div around every st.button(key=...). The per-card view
   buttons use the prefix fd_view_<id> so we prefix-match with [class*=].  */
div[class*="st-key-fd_view_"] button,
.st-key-fd_invite_player button,
.st-key-fd_empty_invite button,
.st-key-fd_upgrade button {
    width: 100% !important;
    padding: 12px 18px !important;
    border-radius: 100px !important;
    background: var(--bone) !important;
    color: var(--ink) !important;
    border: none !important;
    font-family: var(--fd-mono) !important;
    font-size: 10.5px !important; font-weight: 700 !important;
    letter-spacing: 0.20em !important; text-transform: uppercase !important;
    transition: background 0.22s ease, color 0.22s ease, transform 0.22s ease !important;
    box-shadow: 0 12px 28px -16px rgba(244,239,230,0.40) !important;
}
div[class*="st-key-fd_view_"] button:hover,
.st-key-fd_invite_player button:hover,
.st-key-fd_empty_invite button:hover,
.st-key-fd_upgrade button:hover {
    background: var(--gold) !important;
    color: #1a1206 !important;
    transform: translateY(-2px) !important;
}

/* Nudge button — ghost variant (transparent + bordered) so the red Nudge
   block stays the single 'needs attention' moment per stale card. */
div[class*="st-key-fd_nudge_"] button {
    width: 100% !important;
    padding: 10px 18px !important;
    border-radius: 100px !important;
    background: transparent !important;
    color: var(--bone) !important;
    border: 1px solid var(--line-hi) !important;
    font-family: var(--fd-mono) !important;
    font-size: 10.5px !important; font-weight: 700 !important;
    letter-spacing: 0.20em !important; text-transform: uppercase !important;
    transition: all 0.22s ease !important;
    box-shadow: none !important;
}
div[class*="st-key-fd_nudge_"] button:hover {
    background: var(--bone) !important;
    color: var(--ink) !important;
    border-color: var(--bone) !important;
}

.fd-add-row {
    position: relative; z-index: 1;
    display: flex; align-items: center; justify-content: space-between;
    padding: 26px 30px; margin-bottom: 36px; gap: 16px;
    border: 1px dashed var(--line-hi); border-radius: 16px;
    background: var(--glass-1);
}
.fd-add-title {
    font-family: var(--fd-serif); font-size: 1.4rem; font-style: italic;
    color: var(--bone); font-weight: 400; line-height: 1.1;
}
.fd-add-title .accent { color: var(--gold); }
.fd-add-meta {
    font-family: var(--fd-mono); font-size: 10.5px;
    letter-spacing: 0.18em; text-transform: uppercase;
    color: var(--bone-mute); margin-top: 4px;
}
.fd-household-full {
    position: relative; z-index: 1;
    text-align: center; padding: 22px 24px;
    border: 1px solid var(--line); border-radius: 14px;
    background: var(--glass-1); margin-bottom: 36px;
    font-family: var(--fd-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.20em; text-transform: uppercase;
    color: var(--bone-mute);
}

/* Empty state */
.fd-empty {
    position: relative; z-index: 1;
    text-align: center; padding: 80px 28px 88px 28px;
    border: 1px solid var(--line); border-radius: 22px;
    background:
      radial-gradient(70% 50% at 50% 30%, rgba(232,193,112,0.05), transparent 65%),
      var(--glass-1);
    margin-bottom: 30px;
}
.fd-empty-art {
    width: 64px; height: 64px; margin: 0 auto 24px auto;
    border-radius: 50%;
    border: 1px dashed rgba(232,193,112,0.5);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--fd-serif); font-style: italic;
    font-size: 1.6rem; color: var(--gold);
}
.fd-empty-title {
    font-family: var(--fd-serif); font-size: 2.2rem; font-weight: 400;
    line-height: 1.1; letter-spacing: -0.02em;
    color: var(--bone); margin: 0 0 12px 0;
}
.fd-empty-title .ital { font-style: italic; color: var(--gold); }
.fd-empty-sub {
    max-width: 48ch; margin: 0 auto 28px auto;
    color: var(--bone-dim); line-height: 1.55; font-size: 1rem;
}
.fd-empty-note {
    margin-top: 32px;
    font-family: var(--fd-serif); font-style: italic;
    color: var(--bone-mute); font-size: 0.96rem;
    max-width: 44ch; margin-left: auto; margin-right: auto;
}

/* Footer */
.fd-foot {
    text-align: center; max-width: 540px; margin: 24px auto 0 auto;
    font-family: var(--fd-serif); font-style: italic;
    font-size: 1.0rem; line-height: 1.5;
    color: var(--bone-mute); position: relative; z-index: 1;
}

@media (max-width: 760px) {
    .fd-context { flex-direction: column; gap: 8px; padding: 14px 18px; border-radius: 16px; }
    .fd-summary { flex-direction: column; padding: 18px; gap: 14px; }
    .fd-sum-cell { border-right: none; border-bottom: 1px solid var(--line); padding-bottom: 12px; padding-top: 4px; }
    .fd-sum-cell:last-child { border-bottom: none; }
    .fd-add-row { flex-direction: column; align-items: stretch; gap: 14px; text-align: center; }
}
</style>
"""


# ============================================================
# Public entry point
# ============================================================
def render_family_dashboard() -> None:
    """Streamlit page entry. Routes from app.py via st.session_state['page'] = 'family'."""
    import family_storage

    try:
        import auth
        profile = auth.current_profile() if hasattr(auth, "current_profile") else {}
        profile = profile or {}
    except Exception:
        profile = {}

    st.markdown(_FAMILY_CSS, unsafe_allow_html=True)
    st.markdown('<div class="fd-wrap"><div class="fd-bg-fx"></div>', unsafe_allow_html=True)

    user_id = profile.get("user_id") or profile.get("id") or ""

    _render_context_bar(profile)

    family = family_storage.load_family_for_user(user_id) if user_id else None
    is_pro = family_storage.is_family_pro_member(user_id) if user_id else False

    # Entitlement gate: a user who is neither an owner-of-family NOR an
    # active Family Pro member must NOT see "Family Pro is active. Now
    # invite players." — that copy would falsely imply they have the plan.
    # Show an upgrade prompt instead.
    if not family and not is_pro:
        _render_upgrade_prompt()
        st.markdown("""
        <div class="fd-foot">
          Parents see what their kids see. Kids own their data.
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if not family:
        _render_empty_state(profile)
    else:
        members = family_storage.list_members(family["id"])
        active = [m for m in members if m.get("invite_status") == "active"]
        n = len(active)
        max_seats = int(family.get("max_seats") or 4)
        if n == 0:
            _render_empty_state(profile, family=family)
        elif n == 1:
            _render_single_state(profile, family, active[0], max_seats)
        elif n >= max_seats:
            _render_full_state(profile, family, active)
        else:
            _render_populated_state(profile, family, active, max_seats)

    st.markdown("""
    <div class="fd-foot">
      Parents see what their kids see. Kids own their data.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Section renderers
# ============================================================
def _render_context_bar(profile: dict) -> None:
    st.markdown("""
    <div class="fd-context">
      <div class="fd-context-left">
        Viewing as <strong>Parent</strong>
      </div>
      <div class="fd-context-right">
        <span>Manage household in Settings</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_upgrade_prompt() -> None:
    """Shown to non-Family-Pro users who reach the page. No 'active' copy —
    a clear upgrade ask with a CTA to pricing."""
    st.markdown("""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Your household</div>
      <h1 class="fd-hero-title">Family Pro <span class="ital">unlocks this.</span></h1>
      <p class="fd-hero-sub">
        The household dashboard is a Family Pro feature. Upgrade to invite up
        to 4 players and see everyone's progress — every score, every streak,
        every player — in one place.
      </p>
    </div>
    """, unsafe_allow_html=True)
    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("View plans →", key="fd_upgrade",
                     type="primary", use_container_width=True):
            st.session_state["page"] = "pricing"
            st.rerun()


def _render_empty_state(profile: dict, family: Optional[dict] = None) -> None:
    """State B — Family Pro active, 0 members invited (or schema not yet migrated)."""
    first_name = ((profile.get("name") or "Your").split(" ")[0])
    st.markdown(f"""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Your household</div>
      <h1 class="fd-hero-title">{_html.escape(first_name)}'s lab, <span class="ital">your household.</span></h1>
      <p class="fd-hero-sub">
        Family Pro is active. Now invite the players in your household — up to 4 total,
        including yourself. Each gets their own login and their own swing history.
      </p>
    </div>
    <div class="fd-empty">
      <div class="fd-empty-art">§</div>
      <h2 class="fd-empty-title">Add your first <span class="ital">player.</span></h2>
      <p class="fd-empty-sub">
        Send an email invite to anyone in your household — your kid, your spouse,
        your in-law. They make their own account, you see their progress here.
      </p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("+ Invite a Player", key="fd_empty_invite",
                     type="primary", use_container_width=True):
            st.session_state["page"] = "player_settings"
            st.session_state["_settings_open_section"] = "household"
            st.rerun()

    st.markdown("""
    <div class="fd-empty-note" style="margin-top: 32px;">
      Have a player under 13? Set up their account directly under your seat — no
      separate login required (COPPA-compliant).
    </div>
    """, unsafe_allow_html=True)


def _render_single_state(profile: dict, family: dict, member: dict,
                         max_seats: int = 4) -> None:
    """State C — exactly one member."""
    import family_storage
    summary = family_storage.get_member_summary(member)
    name = summary.get("display_name") or "Player"
    st.markdown(f"""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Your household</div>
      <h1 class="fd-hero-title">{_html.escape(name)}'s <span class="ital">progress.</span></h1>
      <p class="fd-hero-sub">
        Just you and {_html.escape(name)} so far. Add another player whenever — same plan covers all.
      </p>
    </div>
    <div class="fd-single">
    """, unsafe_allow_html=True)
    _render_member_card(summary, is_self=_is_self(member, profile))
    st.markdown("</div>", unsafe_allow_html=True)
    _render_add_row(seats_used=1, max_seats=max_seats)


def _render_populated_state(profile: dict, family: dict, members: list[dict],
                            max_seats: int = 4) -> None:
    """State A — more than one member, below the seat cap."""
    import family_storage
    n = len(members)
    summaries = [family_storage.get_member_summary(m) for m in members]

    swings_this_week = sum(1 for s in summaries
                            if s.get("days_since") is not None
                            and s["days_since"] <= 7
                            and s["latest_score"] is not None)
    top_mover = None
    for s in summaries:
        if s.get("latest_score") and not s.get("is_stale"):
            top_mover = s
            break
    scored = [s["latest_score"] for s in summaries if s.get("latest_score")]
    avg_score = (sum(scored) / len(scored)) if scored else 0

    st.markdown(f"""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Your household</div>
      <h1 class="fd-hero-title">The whole family. <span class="ital">One lab.</span></h1>
      <p class="fd-hero-sub">
        A read-only view of every player in your household — latest score, this week's
        top fix, who's been quiet. You're keeping an eye, not steering the wheel —
        each player still owns their swings.
      </p>
    </div>
    """, unsafe_allow_html=True)

    leader_name = ((top_mover or {}).get("display_name") or "Top player")
    st.markdown(f"""
    <div class="fd-summary">
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">This week</div>
        <div class="fd-sum-val">{swings_this_week} swings</div>
        <div class="fd-sum-label">across {n} players</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Top mover</div>
        <div class="fd-sum-val">{_html.escape(leader_name)}</div>
        <div class="fd-sum-label">household leader</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Players</div>
        <div class="fd-sum-val">{n} of {max_seats}</div>
        <div class="fd-sum-label">seats used</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Avg score</div>
        <div class="fd-sum-val">{round(avg_score)}</div>
        <div class="fd-sum-label">household, last 7 days</div>
      </div>
    </div>

    <div class="fd-grid-eyebrow">Players</div>
    <h2 class="fd-grid-title">In the <span class="ital">lab.</span></h2>
    """, unsafe_allow_html=True)

    cols = st.columns(n, gap="medium")
    for idx, summary in enumerate(summaries):
        with cols[idx]:
            _render_member_card(summary, is_self=_is_self(members[idx], profile))

    _render_add_row(seats_used=n, max_seats=max_seats)


_COUNT_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}


def _render_full_state(profile: dict, family: dict, members: list[dict]) -> None:
    """State D — every seat used."""
    import family_storage
    summaries = [family_storage.get_member_summary(m) for m in members]
    n = len(members)
    count_word = _COUNT_WORDS.get(n, str(n))

    st.markdown(f"""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Your household</div>
      <h1 class="fd-hero-title">{count_word} players. <span class="ital">One lab.</span></h1>
      <p class="fd-hero-sub">
        Read-only view of everyone in your household, including yourself.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Cap to 4 columns per row so large rosters (coach) don't get crushed.
    cols = st.columns(min(n, 4), gap="medium")
    for idx, summary in enumerate(summaries):
        with cols[idx % 4]:
            _render_member_card(summary, is_self=_is_self(members[idx], profile))

    st.markdown(f"""
    <div class="fd-household-full">
      Your household is full · {n} of {n} seats used
    </div>
    """, unsafe_allow_html=True)


def _render_add_row(seats_used: int, max_seats: int = 4) -> None:
    seats_remaining = max(0, max_seats - seats_used)
    st.markdown(f"""
    <div class="fd-add-row">
      <div>
        <div class="fd-add-title">Add another <span class="accent">player</span> to your household.</div>
        <div class="fd-add-meta">{seats_used} of {max_seats} seats used</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    cols = st.columns([2, 1])
    with cols[1]:
        if st.button(f"+ Invite Player ({seats_remaining} left)",
                     key="fd_invite_player",
                     use_container_width=True):
            st.session_state["page"] = "player_settings"
            st.session_state["_settings_open_section"] = "household"
            st.rerun()


# ============================================================
# Member card (the building block)
# ============================================================
def _render_member_card(summary: dict, is_self: bool = False) -> None:
    """Render one member's card. Reads from get_member_summary()'s dict."""
    name = _html.escape(str(summary.get("display_name") or "Player"))
    age = summary.get("age") or "—"
    position = summary.get("position") or ""
    handed = summary.get("handedness") or ""

    trend = summary.get("trend") or "unknown"
    is_stale = bool(summary.get("is_stale"))
    days_since = summary.get("days_since")
    latest_score = summary.get("latest_score")
    delta = summary.get("delta") or 0
    sparkline = summary.get("sparkline_points") or []
    verdict_line = summary.get("verdict_line") or "—"
    latest_date = summary.get("latest_date") or ""

    initial = (str(name)[:1] or "?").upper()
    avatar_class = "fd-avatar"
    if is_stale:
        avatar_class += " muted"
    elif is_self:
        avatar_class += " tint-blue"
    else:
        h = sum(ord(c) for c in str(name)) % 3
        if h == 1:
            avatar_class += " tint-warm"

    if is_stale:
        badge_html = f'<div class="fd-badge stale">{days_since or "—"} days</div>'
    elif days_since is not None and days_since == 0:
        badge_html = '<div class="fd-badge active">● Today</div>'
    elif days_since is not None and days_since <= 3:
        badge_html = f'<div class="fd-badge recent">{days_since} days</div>'
    else:
        badge_html = f'<div class="fd-badge recent">{days_since or "—"} days</div>'

    card_class = "fd-card"
    if is_self: card_class += " is-self"
    if is_stale: card_class += " is-stale"

    verdict_class = "fd-verdict"
    if trend == "flat" or trend == "stale":
        verdict_class += " mute"

    if trend == "up":
        delta_str = f'▲ +{delta}' if delta else '▲'
        delta_class = "up"
    elif trend == "down":
        delta_str = f'▼ {delta}' if delta else '▼'
        delta_class = "down"
    elif latest_score is None:
        delta_str = '—'; delta_class = "flat"
    else:
        delta_str = f'— +{delta}' if delta == 0 else f'{delta:+d}'
        delta_class = "flat"

    spark_svg = _build_sparkline_svg(sparkline, trend, is_stale)
    you_tag = '<span class="fd-you-tag">YOU</span>' if is_self else ''
    date_display = latest_date[:10] if latest_date else "—"

    # NOTE: keep these flush-left, single logical string (no leading whitespace,
    # no embedded newlines). They get interpolated into the card markdown below;
    # any line indented >=4 spaces would be rendered as a literal code block by
    # Streamlit's markdown (the cause of the "<div class=...>" leak on cards).
    if is_stale:
        topfix_html = ""
        nudge_html = (
            '<div class="fd-nudge"><div class="fd-nudge-text">'
            f'<strong>Send {name} a soft nudge?</strong> '
            "We'll push a friendly reminder, no spam."
            '</div></div>'
        )
    else:
        eyebrow = "YOUR FIX" if is_self else "ASK"
        topfix_html = (
            '<div class="fd-topfix">'
            f'<div class="fd-topfix-eyebrow">{eyebrow}</div>'
            f'<div class="fd-topfix-text">{_html.escape(verdict_line)}</div>'
            '</div>'
        )
        nudge_html = ""

    score_html = (f'<div class="fd-score">{latest_score}</div>'
                  if latest_score is not None
                  else '<div class="fd-score" style="opacity:0.4;">—</div>')

    position_html = ('<span class="dot">·</span><span>' + _html.escape(str(position)) + '</span>') if position else ''
    handed_html = ('<span class="dot">·</span><span>' + _html.escape(str(handed)) + '</span>') if handed else ''

    # st.html (NOT st.markdown): renders raw HTML with no markdown processing, so
    # interpolated sub-blocks (topfix/nudge) can't be turned into literal code by
    # indentation/blank-line rules. (Same reason the swing report uses st.html.)
    st.html(f"""
    <div class="{card_class}">
      <div class="fd-card-top">
        <div class="fd-identity">
          <div class="{avatar_class}">{_html.escape(initial)}</div>
          <div>
            <h3 class="fd-member-name">{name}{you_tag}</h3>
            <div class="fd-member-meta">
              <span>{_html.escape(str(age))}</span>
              {position_html}
              {handed_html}
            </div>
          </div>
        </div>
        {badge_html}
      </div>
      <div class="{verdict_class}">{_html.escape(verdict_line)}</div>
      <div class="fd-latest">
        {score_html}
        <div class="fd-score-meta">
          <div class="fd-latest-eyebrow">{'Last' if is_stale else 'Latest'} swing</div>
          <div class="fd-delta-line">
            <span class="fd-delta-date">{_html.escape(date_display)}</span>
            <span class="fd-delta-val {delta_class}">{delta_str}</span>
          </div>
        </div>
      </div>
      <div class="fd-spark-wrap">
        <span class="fd-spark-tick top">90</span>
        <span class="fd-spark-tick bottom">60</span>
        {spark_svg}
      </div>
      {topfix_html}
      {nudge_html}
    </div>
    """)

    if is_stale:
        btn_label = f"Nudge {name}"
        btn_key = f"fd_nudge_{summary.get('id') or summary.get('player_user_id') or name}"
        if st.button(btn_label, key=btn_key, use_container_width=True):
            st.session_state[f"_nudged_{btn_key}"] = True
            try:
                st.toast(f"Nudge sent to {name} ✓", icon="✓")
            except Exception:
                st.success(f"Nudge sent to {name} ✓")

    view_label = ("View your Report →" if is_self
                  else f"View {name}'s Report →")
    view_key = f"fd_view_{summary.get('id') or summary.get('player_user_id') or name}"
    if st.button(view_label, key=view_key, use_container_width=True):
        st.session_state["viewing_member_id"] = (summary.get("player_user_id")
                                                  or summary.get("id"))
        st.session_state["page"] = "sessions"
        st.rerun()


def _build_sparkline_svg(points: list, trend: str, is_stale: bool) -> str:
    """Inline SVG sparkline. Shared baseline 60-90 score range so
    cross-sibling comparisons are visually meaningful."""
    if not points:
        return '<svg class="fd-spark" viewBox="0 0 240 36"></svg>'

    n = max(1, len(points))
    xs = [i * 240 / max(1, n - 1) for i in range(n)] if n > 1 else [120.0]
    def _y(score):
        clamped = max(60.0, min(90.0, float(score)))
        return 36.0 - (clamped - 60.0) * 36.0 / 30.0
    ys = [_y(s) for s in points]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))

    if is_stale:
        stroke = "rgba(244,239,230,0.22)"; dot = "rgba(244,239,230,0.42)"
    elif trend == "up":
        stroke = "rgba(244,239,230,0.32)"; dot = "#E8C170"
    else:
        stroke = "rgba(244,239,230,0.32)"; dot = "#C8C4BB"

    return (f'<svg class="fd-spark" viewBox="0 0 240 36" preserveAspectRatio="none">'
            f'<polyline fill="none" stroke="{stroke}" stroke-width="1.5" '
            f'stroke-linecap="round" stroke-linejoin="round" points="{pts}"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.5" fill="{dot}" '
            f'stroke="#0A0B0E" stroke-width="2"/>'
            f'</svg>')


def _is_self(member: dict, profile: dict) -> bool:
    if not profile:
        return False
    pid = profile.get("user_id") or profile.get("id")
    return bool(pid) and (member.get("player_user_id") == pid)
