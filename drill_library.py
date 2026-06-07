"""
BarrelLabs SwingAI — Drill Library

A browsable library of hitting drills, filtered by the training aids the
player actually has on hand. Plain-language, no jargon, organized by what
each group of drills fixes.

Design notes
------------
* Single source of drill content: drills.DRILL_DB (also used by the Training
  Plan prescriptions). Each drill carries an `equipment` list of aid keys;
  drills.EQUIPMENT maps each key to a human label.
* The equipment selection is stored PER PROFILE on players.training_aids
  (jsonb). On a Family/Coach plan each kid keeps their own kit — it is NOT
  shared across the account's profiles, because we key the read/write on the
  active player id (st.session_state["player"]/["user"]["id"]).
* Matches the editorial theme (bl_theme tokens) and the shared Edge masthead.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from bl_theme import inject_global_theme
from bl_edge_chrome import render_edge_masthead
from drills import DRILL_DB, EQUIPMENT


# A small icon per aid so the kit reads fast for kids/parents (accessible).
AID_ICON = {
    "tee":          "⚾",
    "net":          "🥅",
    "soft_toss":    "🤝",
    "wall":         "🧱",
    "towel":        "🧺",
    "band":         "➰",
    "weighted_bat": "🏏",
    "pvc":          "📏",
    "med_ball":     "🏐",
    "mirror":       "🪞",
}

# Plain-language, one-line "what this group fixes" — keeps the library
# understandable instead of throwing biomechanics jargon at people.
CATEGORY_GOAL = {
    "head_stability":          "Keep your eyes steady so you track the ball longer.",
    "hip_rotation":            "Use your lower half to unlock real power.",
    "hip_shoulder_separation": "Load up torque so the barrel whips through.",
    "knee_extension":          "Brace the front leg to turn momentum into bat speed.",
    "sequencing":              "Fire your body in the right order so nothing drags.",
    "rotational_speed":        "Train pure bat speed and exit velo.",
    "front_side_stability":    "Lock your front side so you stay on the ball.",
    "timing":                  "Be on time so good mechanics actually connect.",
}

# The aids offered in the kit selector. "none" (just a bat) is implied for
# every player, so it is never a toggle — bat-only drills always show.
KIT_AIDS = [k for k in EQUIPMENT.keys() if k != "none"]


_LOCAL_CSS = """
<style>
  .dl-page { max-width: 1120px; margin: 0 auto; padding: 0 4px 4rem; }

  /* ---- Hero ---- */
  .dl-hero { margin: 0.4rem 0 1.6rem; }
  .dl-eyebrow {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--gold-deep); margin-bottom: 0.5rem;
  }
  .dl-title {
    font-family: var(--serif); font-weight: 400; line-height: 0.98;
    font-size: clamp(2.4rem, 7vw, 4rem); color: var(--ink); margin: 0 0 0.6rem;
  }
  .dl-sub {
    font-family: var(--sans); font-size: 1rem; line-height: 1.55;
    color: var(--bone-faint); max-width: 60ch;
  }

  /* ---- Kit selector panel ---- */
  .dl-kit {
    background: var(--ink); border-radius: 18px; padding: 1.3rem 1.4rem 1.1rem;
    margin: 0 0 1.4rem; box-shadow: 0 18px 40px -28px rgba(10,11,14,.6);
  }
  .dl-kit-row { display:flex; align-items:baseline; gap:.6rem; flex-wrap:wrap; margin-bottom:.85rem; }
  .dl-kit-title {
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--gold);
  }
  .dl-kit-hint { font-family: var(--sans); font-size: 13px; color: var(--bone-dim); }

  /* Theme the native st.pills inside the dark kit panel. */
  .dl-kit-pills [data-baseweb="tag"],
  .dl-kit-pills button[kind] { font-family: var(--mono) !important; }
  .dl-kit-pills [role="button"],
  .dl-kit-pills button {
    font-family: var(--mono) !important; font-size: 12.5px !important;
    letter-spacing: 0.04em !important; border-radius: 999px !important;
  }

  /* ---- Count line ---- */
  .dl-count {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--bone-mute); margin: 0 2px 1.4rem;
  }
  .dl-count b { color: var(--gold-deep); }

  /* ---- Category sections ---- */
  .dl-cat { margin: 0 0 2.1rem; }
  .dl-cat-head {
    display:flex; align-items:flex-end; justify-content:space-between;
    gap:1rem; border-bottom: 1px solid rgba(10,11,14,.14);
    padding-bottom: .55rem; margin-bottom: 1rem;
  }
  .dl-cat-title {
    font-family: var(--serif); font-size: clamp(1.5rem, 4vw, 2rem);
    color: var(--ink); line-height: 1; margin: 0;
  }
  .dl-cat-goal {
    font-family: var(--sans); font-size: 13.5px; color: var(--bone-faint);
    margin-top: .25rem;
  }
  .dl-cat-n {
    font-family: var(--mono); font-size: 11px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--bone-mute); white-space: nowrap;
  }

  .dl-grid {
    display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px;
  }
  .dl-card {
    background: #fff; border: 1px solid rgba(10,11,14,.10); border-radius: 14px;
    padding: 1.05rem 1.1rem; display:flex; flex-direction:column; gap:.55rem;
  }
  .dl-card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.6rem; }
  .dl-card-name {
    font-family: var(--sans); font-weight: 600; font-size: 1.02rem;
    color: var(--ink); line-height: 1.2;
  }
  .dl-reps {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: .08em;
    text-transform: uppercase; color: var(--gold-deep);
    background: rgba(232,193,112,.16); border-radius: 999px;
    padding: 4px 9px; white-space: nowrap; flex-shrink: 0;
  }
  .dl-how { font-family: var(--sans); font-size: 13.5px; line-height: 1.5; color: var(--bone-faint); }
  .dl-tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:.15rem; }
  .dl-tag {
    font-family: var(--mono); font-size: 10px; letter-spacing: .06em;
    text-transform: uppercase; color: var(--bone-mute);
    border: 1px solid rgba(10,11,14,.14); border-radius: 6px; padding: 3px 7px;
  }
  .dl-tag--bat { color: var(--gold-deep); border-color: rgba(201,163,80,.5); }

  /* ---- Mobile ---- */
  @media (max-width: 720px) {
    .dl-grid { grid-template-columns: 1fr; }
    .dl-cat-head { flex-direction: column; align-items: flex-start; gap: .2rem; }
  }
</style>
"""


# --------------------------------------------------------------------
#  Per-profile persistence (players.training_aids)
# --------------------------------------------------------------------
def _cache_key(player_id: str) -> str:
    return f"_dl_aids_{player_id}"


def _load_aids(player_id: str) -> list:
    """Load this profile's saved kit. Cached per run; falls back to []."""
    ck = _cache_key(player_id)
    if ck in st.session_state:
        return st.session_state[ck]
    aids: list = []
    try:
        from supabase_client import get_client
        res = (
            get_client().table("players")
            .select("training_aids").eq("id", player_id).single().execute()
        )
        aids = (res.data or {}).get("training_aids") or []
    except Exception:
        aids = []
    if not isinstance(aids, list):
        aids = []
    # Only keep aids we still recognize (taxonomy can change).
    aids = [a for a in aids if a in EQUIPMENT and a != "none"]
    st.session_state[ck] = aids
    return aids


def _save_aids(player_id: str, aids: list) -> None:
    aids = [a for a in (aids or []) if a in EQUIPMENT and a != "none"]
    st.session_state[_cache_key(player_id)] = aids
    try:
        from supabase_client import get_client
        get_client().table("players").update(
            {"training_aids": aids}
        ).eq("id", player_id).execute()
    except Exception:
        # Persistence is best-effort; the in-session cache still works this run.
        pass


def _on_kit_change(player_id: str, widget_key: str) -> None:
    _save_aids(player_id, st.session_state.get(widget_key) or [])


# --------------------------------------------------------------------
#  Page
# --------------------------------------------------------------------
def _esc(s) -> str:
    return _html.escape(str(s or ""))


def _drill_available(drill: dict, have: set) -> bool:
    need = {a for a in drill.get("equipment", []) if a != "none"}
    return need.issubset(have)


def render_drill_library():
    inject_global_theme()
    render_edge_masthead(
        st.session_state.get("user") or {}, active_page="drill_library"
    )
    st.markdown(_LOCAL_CSS, unsafe_allow_html=True)
    st.markdown('<div class="dl-page">', unsafe_allow_html=True)

    # ---- Hero ----
    st.markdown(
        '<div class="dl-hero">'
        '<div class="dl-eyebrow">BarrelLabs Drill Library</div>'
        '<h1 class="dl-title">Find your next drill</h1>'
        '<div class="dl-sub">Tell us what you’ve got to work with and we’ll '
        'show you drills you can actually do today — grouped by what they fix. '
        'Everything works with just a bat; add gear to unlock more.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Active profile (per-profile kit). user is aliased to the active player.
    user = st.session_state.get("user") or st.session_state.get("player") or {}
    player_id = user.get("id")

    # ---- Kit selector ----
    saved = _load_aids(player_id) if player_id else []
    st.markdown('<div class="dl-kit">', unsafe_allow_html=True)
    st.markdown(
        '<div class="dl-kit-row">'
        '<span class="dl-kit-title">Your training kit</span>'
        '<span class="dl-kit-hint">Tap everything you have. We remember it for next time.</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="dl-kit-pills">', unsafe_allow_html=True)
    widget_key = f"dl_kit_{player_id or 'anon'}"
    selected = st.pills(
        "Your training kit",
        options=KIT_AIDS,
        selection_mode="multi",
        default=[a for a in saved if a in KIT_AIDS],
        format_func=lambda k: f"{AID_ICON.get(k,'')} {EQUIPMENT[k]}".strip(),
        key=widget_key,
        label_visibility="collapsed",
        on_change=_on_kit_change if player_id else None,
        args=(player_id, widget_key) if player_id else None,
    )
    st.markdown('</div></div>', unsafe_allow_html=True)

    have = {a for a in (selected or []) if a != "none"}

    # ---- Count + nudge ----
    total_available = sum(
        1 for cat in DRILL_DB.values()
        for d in cat["drills"] if _drill_available(d, have)
    )
    if not have:
        nudge = "Add your gear above to unlock more — showing every drill you can do with just a bat."
        st.markdown(
            f'<div class="dl-count"><b>{total_available}</b> bat-only drills ready &nbsp;·&nbsp; {nudge}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="dl-count"><b>{total_available}</b> drills ready with your kit</div>',
            unsafe_allow_html=True,
        )

    # ---- Categories ----
    for cat_key, cat in DRILL_DB.items():
        avail = [d for d in cat["drills"] if _drill_available(d, have)]
        if not avail:
            continue
        goal = CATEGORY_GOAL.get(cat_key, "")
        st.markdown(
            '<div class="dl-cat">'
            '<div class="dl-cat-head"><div>'
            f'<h2 class="dl-cat-title">{_esc(cat["title"])}</h2>'
            f'<div class="dl-cat-goal">{_esc(goal)}</div>'
            '</div>'
            f'<div class="dl-cat-n">{len(avail)} drill{"s" if len(avail)!=1 else ""}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        cards = ['<div class="dl-grid">']
        for d in avail:
            need = [a for a in d.get("equipment", []) if a != "none"]
            if need:
                tags = "".join(
                    f'<span class="dl-tag">{_esc(EQUIPMENT.get(a, a))}</span>'
                    for a in need
                )
            else:
                tags = '<span class="dl-tag dl-tag--bat">Just a bat</span>'
            cards.append(
                '<div class="dl-card">'
                '<div class="dl-card-top">'
                f'<div class="dl-card-name">{_esc(d["name"])}</div>'
                f'<div class="dl-reps">{_esc(d.get("reps",""))}</div>'
                '</div>'
                f'<div class="dl-how">{_esc(d.get("how",""))}</div>'
                f'<div class="dl-tags">{tags}</div>'
                '</div>'
            )
        cards.append('</div>')  # .dl-grid
        st.markdown("".join(cards), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)  # .dl-cat

    st.markdown('</div>', unsafe_allow_html=True)  # .dl-page
