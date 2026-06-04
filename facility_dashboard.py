"""Coach / Facility roster dashboard — Streamlit page.

Generalizes the household (≤4) view to a facility roster (up to hundreds),
adding a name filter + pagination so a big roster doesn't render as one
giant column wall. Reuses family_dashboard's card + sparkline + CSS so it
reads as one product (import-reuse, no modification to the live family page).

Routed from app.py via st.session_state['page'] = 'facility' (in-session nav
only — auth is session-state-only; never use <a href> anchors).

Spec: docs/superpowers/specs/2026-06-04-facility-coach-mode-design.md §3.2
Plan: docs/superpowers/plans/2026-06-04-facility-coach-mode.md  (Task 6)
"""
from __future__ import annotations

import html as _html
import math
from typing import Optional

import streamlit as st


PAGE_SIZE = 30   # cards per page; keeps a few-hundred roster responsive


# ── Pure helpers (unit-tested without Streamlit) ───────────────────
def filter_members(members: list[dict], query: str) -> list[dict]:
    """Case-insensitive name filter. Empty query → all."""
    q = (query or "").strip().lower()
    if not q:
        return list(members)
    return [m for m in members
            if q in str(m.get("display_name", "")).lower()]


def paginate(members: list[dict], page: int, size: int = PAGE_SIZE) -> dict:
    """Slice a member list into a page. Returns
    {items, page, n_pages, total}. `page` is 0-based and clamped in-range."""
    total = len(members)
    n_pages = max(1, math.ceil(total / size))
    page = max(0, min(page, n_pages - 1))
    start = page * size
    return {
        "items": members[start:start + size],
        "page": page,
        "n_pages": n_pages,
        "total": total,
    }


# ── Page entry point ───────────────────────────────────────────────
def render_facility_dashboard() -> None:
    """Streamlit entry. Coach-only: shows the roster of the facility this
    user owns. Falls back to an empty/onboard state when there's no
    facility or no members (safe-by-design — never crashes)."""
    import facility_storage
    try:
        import auth
        profile = (auth.current_profile() or {}) if hasattr(auth, "current_profile") else {}
    except Exception:
        profile = {}

    # Reuse the family dashboard's locked design system + card renderer.
    try:
        from family_dashboard import _FAMILY_CSS, _render_member_card
    except Exception:
        _FAMILY_CSS, _render_member_card = "", None

    st.markdown(_FAMILY_CSS, unsafe_allow_html=True)
    st.markdown('<div class="fd-wrap"><div class="fd-bg-fx"></div>', unsafe_allow_html=True)

    user_id = profile.get("user_id") or profile.get("id") or ""
    facility = facility_storage.load_facility_for_owner(user_id) if user_id else None

    if not facility:
        _render_no_facility_state()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    members = facility_storage.list_members(facility["id"])
    # attach swing summaries (reuse family_storage's per-member fetch shape)
    summaries = _hydrate_member_summaries(members)
    summary = facility_storage.roster_summary(summaries)

    _render_header(facility, summary)
    _render_roster(facility, summaries, _render_member_card)

    st.markdown('</div>', unsafe_allow_html=True)


def _hydrate_member_summaries(members: list[dict]) -> list[dict]:
    """Combine each member with their swing history into a card-ready dict.
    Reuses family_storage.get_member_summary so the card renders identically."""
    try:
        import family_storage
    except Exception:
        return members
    out = []
    for m in members:
        # family_storage.get_member_summary keys off member['id']==player_id
        card = dict(m)
        card.setdefault("id", m.get("player_id"))
        try:
            card.update(family_storage.get_member_summary({"id": card["id"], **m}))
        except Exception:
            pass
        # also carry a 'swings' shim so roster_summary can read recency
        out.append(card)
    return out


def _render_header(facility: dict, summary: dict) -> None:
    name = _html.escape(str(facility.get("name") or "Your Facility"))
    st.markdown(f"""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Facility roster</div>
      <h1 class="fd-hero-title">{name}'s <span class="ital">lab.</span></h1>
      <p class="fd-hero-sub">
        Every hitter who's joined your facility — latest score, who's trending,
        who's gone quiet. Tap any card to pull up their report in a lesson.
      </p>
    </div>
    <div class="fd-summary">
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Roster</div>
        <div class="fd-sum-val">{summary['total']}</div>
        <div class="fd-sum-label">hitters joined</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Active</div>
        <div class="fd-sum-val">{summary['active_this_week']}</div>
        <div class="fd-sum-label">filmed this week</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Needs attention</div>
        <div class="fd-sum-val">{summary['needs_attention']}</div>
        <div class="fd-sum-label">quiet / no swings</div>
      </div>
      <div class="fd-sum-cell">
        <div class="fd-sum-eyebrow">Join code</div>
        <div class="fd-sum-val accent">{_html.escape(str(facility.get('join_code') or '—'))}</div>
        <div class="fd-sum-label">share to add hitters</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_roster(facility: dict, summaries: list[dict], render_card) -> None:
    # name filter
    query = st.text_input("Search hitters", key="_fac_search",
                          placeholder="Filter by name…", label_visibility="collapsed")
    filtered = filter_members(summaries, query)

    page = int(st.session_state.get("_fac_page", 0))
    pg = paginate(filtered, page)
    st.session_state["_fac_page"] = pg["page"]

    if pg["total"] == 0:
        st.markdown("""
        <div class="fd-household-full">No hitters match — share your join code to add players.</div>
        """, unsafe_allow_html=True)
        return

    items = pg["items"]
    cols_per_row = 3
    for row_start in range(0, len(items), cols_per_row):
        row = items[row_start:row_start + cols_per_row]
        cols = st.columns(len(row), gap="medium")
        for col, summary in zip(cols, row):
            with col:
                if render_card:
                    render_card(summary, is_self=False)

    if pg["n_pages"] > 1:
        _render_pager(pg)


def _render_pager(pg: dict) -> None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("← Prev", key="_fac_prev", disabled=pg["page"] <= 0,
                     use_container_width=True):
            st.session_state["_fac_page"] = pg["page"] - 1
            st.rerun()
    with c2:
        st.markdown(
            f"<div style='text-align:center;font-family:var(--fd-mono);"
            f"font-size:11px;letter-spacing:.14em;color:var(--bone-mute);"
            f"padding-top:10px;'>PAGE {pg['page']+1} OF {pg['n_pages']} · "
            f"{pg['total']} HITTERS</div>", unsafe_allow_html=True)
    with c3:
        if st.button("Next →", key="_fac_next", disabled=pg["page"] >= pg["n_pages"] - 1,
                     use_container_width=True):
            st.session_state["_fac_page"] = pg["page"] + 1
            st.rerun()


def _render_no_facility_state() -> None:
    st.markdown("""
    <div class="fd-hero">
      <div class="fd-hero-eyebrow">Facility</div>
      <h1 class="fd-hero-title">Run your academy <span class="ital">on BarrelLabs.</span></h1>
      <p class="fd-hero-sub">
        Give every hitter in your facility a pro-grade AI swing report — co-branded
        to you — and see your whole roster's progress in one place.
      </p>
    </div>
    <div class="fd-empty">
      <div class="fd-empty-art">§</div>
      <h2 class="fd-empty-title">No facility <span class="ital">yet.</span></h2>
      <p class="fd-empty-sub">
        Set up your facility to get a join code your hitters use to link in.
      </p>
    </div>
    """, unsafe_allow_html=True)
    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("See facility plans →", key="_fac_upgrade",
                     type="primary", use_container_width=True):
            st.session_state["page"] = "pricing"
            st.rerun()
