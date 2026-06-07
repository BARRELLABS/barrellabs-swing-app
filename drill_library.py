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
* DARK editorial theme (bl_theme tokens) to match the rest of the app: bone
  text on ink, translucent --bl-surface cards (no stark white boxes).
* The training-kit chips are custom st.buttons (not st.pills) laid out the
  same way the Edge masthead lays out its nav — so we get full control of the
  look: line-art icons that tint via CSS mask, and a gold "selected" state.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from bl_theme import inject_global_theme
from bl_edge_chrome import render_edge_masthead
from drills import DRILL_DB, EQUIPMENT


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
    text-transform: uppercase; color: var(--gold); margin-bottom: 0.5rem;
  }
  .dl-title {
    font-family: var(--serif); font-weight: 400; line-height: 0.98;
    font-size: clamp(2.4rem, 7vw, 4rem); color: var(--bone); margin: 0 0 0.6rem;
  }
  .dl-sub {
    font-family: var(--sans); font-size: 1rem; line-height: 1.55;
    color: var(--bone-mute); max-width: 60ch;
  }

  /* ---- Kit selector panel (a real st.container so it wraps the widgets) ---- */
  .st-key-dl_kit_panel {
    background: rgba(244,239,230,0.03); border: 1px solid var(--bl-line);
    border-radius: 18px; padding: 1.25rem 1.35rem 1.3rem; margin: 0 0 1.3rem;
    backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  }
  .dl-kit-row { display:flex; align-items:baseline; gap:.6rem; flex-wrap:wrap; margin-bottom:.95rem; }
  .dl-kit-title {
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--gold);
  }
  .dl-kit-hint { font-family: var(--sans); font-size: 13px; color: var(--bone-mute); }

  /* Lay the chip st.buttons out as a wrapping row (same trick the masthead
     uses for its nav). */
  .st-key-dl_kit_chips {
    display:flex !important; flex-direction:row !important; flex-wrap:wrap !important;
    gap:8px !important; align-items:flex-start !important;
  }
  .st-key-dl_kit_chips > div,
  .st-key-dl_kit_chips > div > div[data-testid="stVerticalBlock"] { display:contents !important; }
  .st-key-dl_kit_chips [data-testid="stElementContainer"],
  .st-key-dl_kit_chips [data-testid="stButton"] {
    flex:0 0 auto !important; width:auto !important; margin:0 !important;
  }
  /* Chip base (idle) */
  .st-key-dl_kit_chips button {
    position: relative !important;
    background: rgba(244,239,230,0.04) !important;
    border: 1px solid var(--bl-line) !important;
    color: var(--bone-dim) !important;
    font-family: var(--mono) !important; font-size: 11.5px !important;
    font-weight: 500 !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    padding: 9px 16px !important; border-radius: 999px !important;
    min-height: 0 !important; height: auto !important; line-height: 1.1 !important;
    box-shadow: none !important;
    transition: color .2s ease, background-color .2s ease, border-color .2s ease, transform .2s ease;
  }
  .st-key-dl_kit_chips button p { font: inherit !important; color: inherit !important; margin: 0 !important; letter-spacing: inherit !important; }
  .st-key-dl_kit_chips button:hover {
    color: var(--bone) !important; border-color: var(--bl-line-hi) !important;
    transform: translateY(-1px);
  }

  /* ---- Count line ---- */
  .dl-count {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--bone-mute); margin: 0 2px 1.5rem;
  }
  .dl-count b { color: var(--gold); }

  /* ---- Category sections ---- */
  .dl-cat { margin: 1.7rem 0 1.1rem; }
  .dl-cat-head {
    display:flex; align-items:flex-end; justify-content:space-between;
    gap:1rem; border-bottom: 1px solid var(--bl-line);
    padding-bottom: .55rem; margin-bottom: 1.1rem;
  }
  .dl-cat-title {
    font-family: var(--serif); font-size: clamp(1.5rem, 4vw, 2rem);
    color: var(--bone); line-height: 1; margin: 0;
  }
  .dl-cat-goal {
    font-family: var(--sans); font-size: 13.5px; color: var(--bone-mute);
    margin-top: .3rem;
  }
  .dl-cat-n {
    font-family: var(--mono); font-size: 11px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--bone-faint); white-space: nowrap;
  }

  /* Each drill is a real st.container so the "I did this" button lives
     INSIDE the card (no overlap). Styled as the card surface. */
  [class*="st-key-dlcard_"] {
    background: rgba(244,239,230,0.035) !important; border: 1px solid var(--bl-line) !important;
    border-radius: 16px !important; padding: 1.05rem 1.15rem 1.1rem !important;
    margin-bottom: 14px !important; gap: 0.6rem !important;
    transition: border-color .22s ease, background .22s ease;
  }
  [class*="st-key-dlcard_"]:hover {
    border-color: var(--bl-line-hi) !important; background: rgba(244,239,230,0.055) !important;
  }
  .dl-card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.6rem; }
  .dl-card-name {
    font-family: var(--sans); font-weight: 600; font-size: 1.02rem;
    color: var(--bone); line-height: 1.2;
  }
  .dl-reps {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: .08em;
    text-transform: uppercase; color: var(--gold);
    background: rgba(232,193,112,0.14); border: 1px solid rgba(232,193,112,0.26);
    border-radius: 999px; padding: 4px 9px; white-space: nowrap; flex-shrink: 0;
  }
  .dl-how { font-family: var(--sans); font-size: 13.5px; line-height: 1.5; color: var(--bone-dim); }
  .dl-tags { display:flex; flex-wrap:wrap; gap:6px; margin-top:.15rem; }
  .dl-tag {
    font-family: var(--mono); font-size: 10px; letter-spacing: .06em;
    text-transform: uppercase; color: var(--bone-mute);
    border: 1px solid var(--bl-line); border-radius: 6px; padding: 3px 7px;
  }
  .dl-tag--bat { color: var(--gold); border-color: rgba(232,193,112,0.4); }

  /* ---- "I did this" action + logged state (inside the card) ---- */
  [class*="st-key-dldone_"] button {
    background: rgba(232,193,112,0.10) !important;
    border: 1px solid rgba(232,193,112,0.38) !important;
    color: var(--gold) !important;
    font-family: var(--mono) !important; font-size: 10px !important;
    font-weight: 600 !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important; border-radius: 9px !important;
    padding: 8px 14px !important; min-height: 0 !important; height: auto !important;
    width: auto !important; box-shadow: none !important;
    transition: background .18s ease;
  }
  [class*="st-key-dldone_"] button p { font: inherit !important; color: inherit !important; margin: 0 !important; letter-spacing: inherit !important; }
  [class*="st-key-dldone_"] button:hover { background: rgba(232,193,112,0.18) !important; }
  .dl-done {
    font-family: var(--mono); font-size: 10px; font-weight: 600;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: #6FBF8B; border: 1px solid rgba(111,191,139,0.32);
    background: rgba(111,191,139,0.10); border-radius: 9px;
    padding: 8px 14px; display: inline-block;
  }

  /* ---- Mobile ---- */
  @media (max-width: 720px) {
    .dl-grid { grid-template-columns: 1fr; }
    .dl-cat-head { flex-direction: column; align-items: flex-start; gap: .25rem; }
  }
</style>
"""


# --------------------------------------------------------------------
#  Per-profile persistence (players.training_aids)
# --------------------------------------------------------------------
def _cache_key(player_id) -> str:
    return f"_dl_aids_{player_id}"


def _load_aids(player_id) -> list:
    """Load this profile's saved kit. Cached per run; falls back to []."""
    ck = _cache_key(player_id)
    if ck in st.session_state:
        return st.session_state[ck]
    aids: list = []
    if player_id:
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
    aids = [a for a in aids if a in EQUIPMENT and a != "none"]
    st.session_state[ck] = aids
    return aids


def _save_aids(player_id, aids: list) -> None:
    aids = [a for a in (aids or []) if a in EQUIPMENT and a != "none"]
    st.session_state[_cache_key(player_id)] = aids
    if not player_id:
        return
    try:
        from supabase_client import get_client
        get_client().table("players").update(
            {"training_aids": aids}
        ).eq("id", player_id).execute()
    except Exception:
        # Persistence is best-effort; the in-session cache still works this run.
        pass


# --------------------------------------------------------------------
#  Page
# --------------------------------------------------------------------
def _esc(s) -> str:
    return _html.escape(str(s or ""))


def _drill_available(drill: dict, have: set) -> bool:
    need = {a for a in drill.get("equipment", []) if a != "none"}
    return need.issubset(have)


# --------------------------------------------------------------------
#  Training log — "I did this" writes to the SAME per-player training_logs
#  store + _completion_events history the Training Plan uses, with the same
#  drill_id format ("{category title}::{drill name}"). So library reps feed
#  the same drill-mastery counts. (Gamification XP is computed from a
#  separate swing-meta store, so logging here does not grant XP — it records
#  the rep in the training log, which is what we want.)
# --------------------------------------------------------------------
def _load_log(player_id):
    """Load the player's training log once per run (session-cached)."""
    ck = f"_dl_log_{player_id}"
    if ck in st.session_state:
        return st.session_state[ck]
    log = {"drills": {}, "session_notes": []}
    if player_id:
        try:
            from player_storage import load_training_log
            log = load_training_log(player_id) or log
        except Exception:
            pass
    st.session_state[ck] = log
    return log


def _logged_today(log: dict, drill_id: str) -> bool:
    """True if this exact drill was logged earlier today (any source)."""
    from datetime import datetime as _dt
    today = _dt.now().date().isoformat()
    events = ((log or {}).get("drills") or {}).get("_completion_events") or []
    for e in events:
        if e.get("drill_id") == drill_id and (e.get("completed_at") or "")[:10] == today:
            return True
    return False


def _log_drill_done(player_id, cat_title: str, drill: dict) -> None:
    """Record a library drill completion in the player's training log.

    Two stores (both inside training_logs, no schema migration):
      1. _completion_events + drill_log[drill_id] -> drill MASTERY, matching
         the Training Plan's "{category}::{drill}" id so counts reconcile.
      2. The gamification _swing_meta bucket under a synthetic "library"
         swing id -> feeds total_drills_completed (XP) AND bumps the streak
         (save_swing_meta fires _on_qualifying_activity on a new completion).
    """
    from datetime import datetime as _dt
    drill_name = drill.get("name", "")
    drill_id = f"{cat_title}::{drill_name}"
    now = _dt.now().isoformat(timespec="seconds")

    # 1) mastery + history
    log = _load_log(player_id)
    drill_log = log.setdefault("drills", {})
    drill_log[drill_id] = {
        "completed": True,
        "reps_done": drill.get("reps", ""),
        "last_updated": now,
    }
    drill_log.setdefault("_completion_events", []).append({
        "drill_id": drill_id,
        "drill_name": drill_name,
        "completed_at": now,
        "source_swing_date": None,
        "reps_done": drill.get("reps", ""),
        "source": "library",
    })
    st.session_state[f"_dl_log_{player_id}"] = log  # keep run cache fresh
    if not player_id:
        return
    try:
        from player_storage import (
            save_training_log, load_swing_meta, save_swing_meta,
        )
        save_training_log(player_id, log)
        # 2) XP + streak: count this drill in the gamification bucket.
        done = load_swing_meta(player_id, "library").get("drills_completed", {}) or {}
        done[drill_name] = True
        save_swing_meta(player_id, "library", drills_completed=done)
    except Exception:
        pass


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
    saved = set(_load_aids(player_id))
    with st.container(key="dl_kit_panel"):
        st.markdown(
            '<div class="dl-kit-row">'
            '<span class="dl-kit-title">Your training kit</span>'
            '<span class="dl-kit-hint">Tap everything you have. We remember it for next time.</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        with st.container(key="dl_kit_chips"):
            for aid in KIT_AIDS:
                if st.button(EQUIPMENT[aid], key=f"dlk_{aid}"):
                    new = set(saved)
                    new.symmetric_difference_update({aid})
                    _save_aids(player_id, sorted(new))
                    st.rerun()
    # Gold "selected" override for the chips currently in the kit.
    if saved:
        sel = "".join(
            f'.st-key-dlk_{a} button{{'
            f'background:rgba(232,193,112,0.16)!important;'
            f'border-color:rgba(232,193,112,0.55)!important;'
            f'color:var(--gold)!important;}}'
            for a in saved
        )
        st.markdown(f"<style>{sel}</style>", unsafe_allow_html=True)

    have = saved
    log = _load_log(player_id)

    # ---- Count + nudge ----
    total_available = sum(
        1 for cat in DRILL_DB.values()
        for d in cat["drills"] if _drill_available(d, have)
    )
    if not have:
        st.markdown(
            f'<div class="dl-count"><b>{total_available}</b> bat-only drills ready '
            '&nbsp;·&nbsp; add your gear above to unlock more</div>',
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
        # Float the drills that USE your gear to the top of each category, so
        # adding equipment visibly surfaces new drills first; bat-only after.
        avail.sort(key=lambda d: 0 if [a for a in d.get("equipment", []) if a != "none"] else 1)

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

        # Two-up rows. Each drill is one st.container styled as a card, with
        # the "I did this" button INSIDE it. st.columns stacks on mobile.
        for row in range(0, len(avail), 2):
            cols = st.columns(2, gap="small")
            for ci, d in enumerate(avail[row:row + 2]):
                with cols[ci]:
                    with st.container(key=f"dlcard_{cat_key}_{row + ci}"):
                        need = [a for a in d.get("equipment", []) if a != "none"]
                        if need:
                            tags = "".join(
                                f'<span class="dl-tag">{_esc(EQUIPMENT.get(a, a))}</span>'
                                for a in need
                            )
                        else:
                            tags = '<span class="dl-tag dl-tag--bat">Just a bat</span>'
                        st.markdown(
                            '<div class="dl-card-top">'
                            f'<div class="dl-card-name">{_esc(d["name"])}</div>'
                            f'<div class="dl-reps">{_esc(d.get("reps",""))}</div>'
                            '</div>'
                            f'<div class="dl-how">{_esc(d.get("how",""))}</div>'
                            f'<div class="dl-tags">{tags}</div>',
                            unsafe_allow_html=True,
                        )
                        drill_id = f'{cat["title"]}::{d["name"]}'
                        done = (
                            st.session_state.get(f"_dl_doneflag_{drill_id}")
                            or _logged_today(log, drill_id)
                        )
                        if done:
                            st.markdown(
                                '<div class="dl-done">✓ Logged today</div>',
                                unsafe_allow_html=True,
                            )
                        elif st.button("✓ I did this", key=f"dldone_{cat_key}_{row + ci}"):
                            _log_drill_done(player_id, cat["title"], d)
                            st.session_state[f"_dl_doneflag_{drill_id}"] = True
                            try:
                                st.toast(f"+10 XP · {d['name']} logged", icon="⚡")
                            except Exception:
                                pass
                            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)  # .dl-cat

    st.markdown('</div>', unsafe_allow_html=True)  # .dl-page
