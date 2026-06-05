"""BarrelLabs · Player Settings page (v3 — single-column, bulletproof).

Open question this rebuild answers: how do we make a beautiful settings
page that DOES NOT overlap itself across viewports, with a clear "Save
changes" CTA and an unsaved-changes prompt that fires when the user
tries to navigate away?

Design choices vs the v2 attempt
--------------------------------
v2 used a 2-column CSS grid (`ps_grid`) with `display: contents`
flattening of Streamlit's auto wrappers (stVerticalBlock,
stHorizontalBlock, stColumn). That worked in theory but in practice
every nested layer of flattening introduced a new way for siblings to
overlap once the user's viewport, font scaling, or accessibility zoom
slid the math off. The rail was `position: sticky; top: 200px;` —
also a recipe for overlap on short scrolls.

v3 drops all of that:

- **Single column** layout, max-width 1080px, centered.
- **Hero identity banner** at the top is one full-width card with the
  avatar, name+email, plan pill, and quick stats laid out by a single
  CSS grid inside ONE st.markdown call (no widgets — no flattening).
- **6 section cards** below, each in its own `st.container(key="...")`.
  Each card uses st.columns(2) ONCE at its top-level — no nested
  columns, no display:contents flattening at all.
- **Native widgets** wherever possible: `st.segmented_control`
  replaces the custom `_segmented` button row; `st.pills` replaces the
  `_pill_grid_select` button grid. Both are first-class Streamlit
  widgets in 1.57 with stable DOM and built-in mobile responsiveness.
- **Save bar** is `position: fixed; bottom: 24px;` centered. Its
  internal layout is a simple 3-column st.columns inside a keyed
  container — NO display:contents tricks. The bar shows ONLY when
  `ps_is_dirty` is True. It NEVER co-exists with the leave dialog.
- **Leave-page prompt** is `st.dialog` — a real centered modal with
  proper z-index handling and a built-in dismiss-on-overlay-click.
  No more bottom-fixed "leave band" stacking on top of the save bar.

Dirty-state semantics (CRITICAL — fixes a v2 stale-state bug)
-------------------------------------------------------------
v2 computed `ps_is_dirty` at the BOTTOM of the page render, AFTER the
masthead had already read it and decided whether to intercept nav.
That meant the masthead saw the PREVIOUS rerun's dirty state — if you
typed a character and immediately clicked Sessions, the nav went
through without prompting because the dirty bit hadn't been refreshed.

v3 computes `ps_is_dirty` at the TOP of the page render — BEFORE the
masthead — by reading the CURRENT values from `st.session_state` (which
Streamlit refreshes between reruns from each widget's stored value).
This is correct because:

- After each user interaction, Streamlit sets `session_state[widget_key]
  = new_value` BEFORE re-running the script.
- So at the top of any rerun, session_state already has the user's
  most recent input.
- We read those values, compare to the saved DB record, and set
  `ps_is_dirty` for the masthead to read.

The masthead intercept (in `bl_edge_chrome.py`) just sets
`ps_pending_nav_to` whenever the user is on player_settings and clicks
a nav tab — no `is_dirty` gate at the masthead. The Player Settings
page itself decides whether to show the leave dialog (only if dirty)
or just nav immediately (if not).

ARCHITECTURE NOTE — Streamlit 1.57 markdown-div trap
----------------------------------------------------
`st.markdown("<div class='x'>", unsafe_allow_html=True)` does NOT wrap
the widgets rendered after it. Use `st.container(key="x")` whenever
the wrapper needs to actually contain widgets. We use `st.markdown`
ONLY for self-contained decorative HTML (the identity banner, footer,
flash messages) — never for structural wrappers around widgets.
"""

from __future__ import annotations

import html
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

from bl_edge_chrome import (
    render_edge_masthead,
    render_edge_page_wrapper_open,
    render_edge_page_wrapper_close,
)
from bl_theme import inject_global_theme


# ---------------------------------------------------------------------
# Static option lists  (kept identical to v2 so save logic stays compatible)
# ---------------------------------------------------------------------
POSITIONS = [
    ("ss",  "Shortstop · SS"),
    ("2b",  "Second base · 2B"),
    ("3b",  "Third base · 3B"),
    ("1b",  "First base · 1B"),
    ("c",   "Catcher · C"),
    ("cf",  "Center field · CF"),
    ("lf",  "Left field · LF"),
    ("rf",  "Right field · RF"),
    ("p",   "Pitcher · P"),
    ("dh",  "Designated hitter · DH"),
    ("util", "Utility"),
    ("",    "Not set"),
]
SECONDARY_POSITIONS = [
    ("",    "None"),
    ("2b",  "Second base · 2B"),
    ("3b",  "Third base · 3B"),
    ("ss",  "Shortstop · SS"),
    ("1b",  "First base · 1B"),
    ("of",  "Outfield · OF"),
    ("c",   "Catcher · C"),
    ("p",   "Pitcher · P"),
    ("dh",  "Designated hitter · DH"),
]
LEVELS = ["Youth", "Travel", "High School", "College", "Pro", "Adult/Rec"]
GOAL_OPTIONS = [
    "Improve mechanics",
    "More power",
    "Better contact",
    "Better timing",
    "Better consistency",
    "Reduce strikeouts",
    "Improve bat path",
    "Improve overall swing",
]
SWING_VIEWS = [
    "Side angle (1B / 3B line)",
    "Pitcher-side",
    "Catcher-side",
    "Tracking camera",
]
MLB_HAND_PREFS = ["Match mine", "Right", "Left"]
REPORT_FOCUS = ["Simple summary", "Full biomechanical", "Coach-style"]
BATS_OPTIONS = ["Right", "Left", "Switch"]
THROWS_OPTIONS = ["Right", "Left"]

# Widget keys — kept in one place so _dirty/_save/_wipe all agree.
WK = {
    "first":    "ps_first",
    "last":     "ps_last",
    "display":  "ps_display",
    "pos":      "ps_pos",         # selectbox value (label)
    "pos_sec":  "ps_pos_sec",
    "bats":     "ps_bats",        # segmented_control value
    "throws":   "ps_throws",
    "birth_year": "ps_birth_year",
    "ft":       "ps_ft",
    "in":       "ps_in",
    "wt":       "ps_wt",
    "grad":     "ps_grad",
    "team":     "ps_team",
    "level":    "ps_level",       # pills
    "view":     "ps_view",        # selectbox
    "hand":     "ps_hand",        # segmented_control
    "goal":     "ps_goal",        # pills
    "focus":    "ps_focus",       # segmented_control
    "priv_anon":      "ps_priv_anon",
    "priv_coach":     "ps_priv_coach",
    "priv_email_prod":"ps_priv_email_prod",
    "priv_email_perf":"ps_priv_email_perf",
    "new_email":      "ps_new_email",
}

EXTRAS_KEY = "player_settings_extras"


# ---------------------------------------------------------------------
# Extras (session-state-backed prefs without their own DB column yet)
# ---------------------------------------------------------------------
def _extras() -> Dict[str, Any]:
    extras = st.session_state.get(EXTRAS_KEY)
    if not isinstance(extras, dict):
        extras = {}
        st.session_state[EXTRAS_KEY] = extras
    return extras


def _extras_set(key: str, value: Any) -> None:
    e = _extras()
    e[key] = value
    st.session_state[EXTRAS_KEY] = e


def _extras_get(key: str, default: Any = None) -> Any:
    return _extras().get(key, default)


# ---------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------
def _initials(name: str, email: str = "") -> str:
    name = (name or "").strip()
    if name:
        parts = [p for p in name.split() if p]
        if parts:
            return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    if email:
        return email[:1].upper()
    return "B"


def _split_name(full: str) -> Tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _join_name(first: str, last: str) -> str:
    return " ".join([s for s in [(first or "").strip(), (last or "").strip()] if s])


def _height_to_ft_in(height_in: Optional[int]) -> Tuple[int, int]:
    try:
        h = int(height_in or 0)
    except (TypeError, ValueError):
        h = 0
    if h <= 0:
        h = 70
    return h // 12, h % 12


def _fmt_date_short(s: Optional[str]) -> str:
    if not s:
        return "—"
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).strftime("%b %Y")
    except Exception:
        return str(s)[:7]


def _quick_stats(user: Dict[str, Any]) -> Dict[str, str]:
    swings = 0
    best = "—"
    streak = "—"
    member = _fmt_date_short(user.get("created_at"))
    try:
        from player_storage import load_swing_history
        hist = load_swing_history(user.get("slug") or user.get("id")) or []
        swings = len(hist)
        scores = [r.get("score") for r in hist if r.get("score") is not None]
        if scores:
            best = str(int(round(max(float(s) for s in scores))))
    except Exception:
        pass
    streak_val = ((user.get("gamification") or {}).get("current_streak_days")
                   if isinstance(user.get("gamification"), dict)
                   else user.get("current_streak_days"))
    if streak_val:
        try:
            streak = str(int(streak_val))
        except Exception:
            pass
    return {"swings": str(swings), "best": best, "streak": streak, "member": member}


def _plan_summary() -> Dict[str, Any]:
    info: Dict[str, Any] = {"plan": "Free", "status": "Free tier",
                            "price": "—", "next_billing": "—",
                            "has_stripe": False}
    try:
        from subscription_storage import load_my_plan
        plan = load_my_plan() or {}
        name = plan.get("plan_name") or plan.get("name") or plan.get("plan")
        if name:
            info["plan"] = str(name).title() if str(name).islower() else str(name)
        status = plan.get("status") or plan.get("state")
        if status:
            info["status"] = str(status).title()
        price = plan.get("price") or plan.get("display_price")
        if price:
            info["price"] = str(price)
        renewal = plan.get("renewal_date") or plan.get("current_period_end")
        if renewal:
            info["next_billing"] = _fmt_date_short(renewal)
    except Exception:
        pass
    try:
        from stripe_client import _existing_stripe_customer_id
        info["has_stripe"] = bool(_existing_stripe_customer_id())
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------
# Default-value resolution — single source of truth.
# Each field's saved default is what `_compute_dirty` compares against,
# and what the widget falls back to on first render.
# ---------------------------------------------------------------------
def _saved_defaults(user: Dict[str, Any]) -> Dict[str, Any]:
    extras = _extras()
    cur_first, cur_last = _split_name(user.get("name", ""))
    cur_ft, cur_in = _height_to_ft_in(user.get("height_in"))

    bats_db = (user.get("handedness") or "RIGHT").upper()
    bats_label = {"RIGHT": "Right", "LEFT": "Left",
                   "SWITCH": "Switch"}.get(bats_db, "Right")
    throws_label = user.get("throws") or "Right"
    if throws_label not in THROWS_OPTIONS:
        throws_label = "Right"

    level = user.get("level") or "High School"
    if level not in LEVELS:
        level = "High School"

    # Position label resolution from extras (slug) -> POSITIONS lookup;
    # otherwise from the DB string match.
    pos_slug = extras.get("position_slug")
    if not pos_slug:
        existing = (user.get("position") or "").strip().lower()
        pos_slug = next(
            (s for s, lbl in POSITIONS
             if s == existing or lbl.lower().startswith(existing)),
            "",
        )
    pos_label = next((lbl for s, lbl in POSITIONS if s == pos_slug), "Not set")

    sec_slug = extras.get("secondary_position_slug", "")
    sec_label = next((lbl for s, lbl in SECONDARY_POSITIONS if s == sec_slug),
                      "None")

    goal = user.get("primary_goal") or "Improve mechanics"
    if goal not in GOAL_OPTIONS:
        goal = "Improve mechanics"

    view = extras.get("default_swing_view", SWING_VIEWS[0])
    if view not in SWING_VIEWS:
        view = SWING_VIEWS[0]

    hand = extras.get("mlb_hand_pref", MLB_HAND_PREFS[0])
    if hand not in MLB_HAND_PREFS:
        hand = MLB_HAND_PREFS[0]

    focus = extras.get("default_report_focus", REPORT_FOCUS[1])
    if focus not in REPORT_FOCUS:
        focus = REPORT_FOCUS[1]

    return {
        "first":   cur_first,
        "last":    cur_last,
        "display": extras.get("display_name", user.get("name") or ""),
        "pos":     pos_label,
        "pos_sec": sec_label,
        "bats":    bats_label,
        "throws":  throws_label,
        "birth_year": str(user.get("birth_year") or ""),
        "ft":      int(cur_ft) if cur_ft else 5,
        "in":      int(cur_in) if cur_in is not None else 10,
        "wt":      int(user.get("weight_lb") or 160),
        "grad":    str(extras.get("graduation_year", "") or ""),
        "team":    user.get("team", "") or "",
        "level":   level,
        "view":    view,
        "hand":    hand,
        "goal":    goal,
        "focus":   focus,
        "priv_anon":       bool(extras.get("privacy_anon", True)),
        "priv_coach":      bool(extras.get("privacy_coach", False)),
        "priv_email_prod": bool(extras.get("privacy_email_prod", True)),
        "priv_email_perf": bool(extras.get("privacy_email_perf", True)),
    }


def _current_field_values(user: Dict[str, Any]) -> Dict[str, Any]:
    """Read the user's most recent edits from session_state, with
    fallback to the saved defaults if a widget hasn't rendered yet.
    Called BEFORE the masthead to populate ps_is_dirty correctly."""
    d = _saved_defaults(user)
    out: Dict[str, Any] = {}
    for fkey, default_v in d.items():
        skey = WK.get(fkey)
        if skey and skey in st.session_state:
            out[fkey] = st.session_state[skey]
        else:
            out[fkey] = default_v
    # Type-normalize the numeric fields so dirty compares are stable.
    for n in ("ft", "in", "wt"):
        try:
            out[n] = int(out[n] or 0)
        except (TypeError, ValueError):
            out[n] = 0
    # String fields
    for s in ("first", "last", "display", "birth_year", "grad", "team"):
        out[s] = (str(out[s] or "")).strip()
    return out


# Fields that count toward dirty state. Privacy toggles auto-save on
# change so they're NOT in this list (changes are persisted to extras
# on every render — no Save button needed).
_DIRTY_FIELDS: List[Tuple[str, str]] = [
    ("first",   "First name"),
    ("last",    "Last name"),
    ("display", "Display name"),
    ("pos",     "Primary position"),
    ("pos_sec", "Secondary position"),
    ("bats",    "Bats"),
    ("throws",  "Throws"),
    ("birth_year", "Birth year"),
    ("ft",      "Height · ft"),
    ("in",      "Height · in"),
    ("wt",      "Weight"),
    ("grad",    "Graduation year"),
    ("team",    "Team"),
    ("level",   "Competition level"),
    ("view",    "Default swing view"),
    ("hand",    "MLB-comp handedness"),
    ("goal",    "Training goal"),
    ("focus",   "Default report focus"),
]


def _compute_dirty(user: Dict[str, Any]) -> Tuple[bool, List[str]]:
    cur = _current_field_values(user)
    saved = _saved_defaults(user)
    dirty: List[str] = []
    for fkey, label in _DIRTY_FIELDS:
        if cur.get(fkey) != saved.get(fkey):
            dirty.append(label)
    return bool(dirty), dirty


def _wipe_form_widget_state() -> None:
    """Discard all unsaved widget state so a fresh render reflects the
    DB-saved values. Used by the leave dialog's Discard button."""
    for k in list(st.session_state.keys()):
        if k in WK.values() or k.startswith("ps_"):
            if k in ("ps_is_dirty", "ps_pending_nav_to",
                      "ps_account_deleted", "ps_delete_armed",
                      "ps_flash_ok", "ps_flash_err", "ps_flash_info",
                      EXTRAS_KEY):
                continue
            st.session_state.pop(k, None)


# ---------------------------------------------------------------------
# CSS — short, scoped, and free of display:contents flattening.
# Layout is a simple max-width column. Every widget reskins itself by
# its native data-testid; no nested-keyed-container grid hacks.
# ---------------------------------------------------------------------
_PAGE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

:root {
  --ps-ink: #0A0B0E;
  --ps-ink-2: #0D0F13;
  --ps-ink-3: #14171C;
  --ps-bone: #F4EFE6;
  --ps-bone-warm: #F8F2E0;
  --ps-bone-80: rgba(244,239,230,0.82);
  --ps-bone-60: rgba(244,239,230,0.60);
  --ps-bone-40: rgba(244,239,230,0.36);
  --ps-glass-1: rgba(255,255,255,0.025);
  --ps-glass-2: rgba(255,255,255,0.045);
  --ps-line: rgba(244,239,230,0.08);
  --ps-line-hi: rgba(244,239,230,0.16);
  --ps-line-hi-2: rgba(244,239,230,0.24);
  --ps-red: #E64530;
  --ps-red-deep: #C53620;
  --ps-red-soft: rgba(230,69,48,0.14);
  --ps-red-line: rgba(230,69,48,0.32);
  --ps-gold: #E8C170;
  --ps-gold-soft: rgba(232,193,112,0.14);
  --ps-gold-line: rgba(232,193,112,0.32);
  --ps-green: #4AE38C;
  --ps-green-soft: rgba(74,227,140,0.14);
  --ps-green-line: rgba(74,227,140,0.32);
  --ps-serif: 'Instrument Serif', 'Fraunces', Georgia, serif;
  --ps-sans:  'Geist', -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  --ps-mono:  'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --ps-r-pill: 999px;
  --ps-r-card: 18px;
  --ps-r-mid: 12px;
  --ps-r-sm: 8px;
  --ps-ease-soft: cubic-bezier(.32,.72,0,1);
  --ps-ease-snap: cubic-bezier(.34,1.4,.64,1);
}

/* ============================================================
   .st-key-ps_wrap — single-column page wrapper. Max-width keeps
   long forms readable; padding-bottom reserves space for the
   sticky save bar so the last card never sits underneath it.
   ============================================================ */
.st-key-ps_wrap {
  position: relative;
  z-index: 3;
  max-width: 1080px;
  margin: 0 auto;
  padding: 1.6rem 32px 9rem;
  color: var(--ps-bone);
  font-family: var(--ps-sans);
}

/* Atmosphere — a fixed, decorative radial wash. Pointer-events:none
   so it never intercepts clicks. */
.ps-atmos {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(900px 600px at 12% -8%, rgba(232,193,112,0.04), transparent 60%),
    radial-gradient(700px 500px at 92% 110%, rgba(230,69,48,0.025), transparent 60%);
}

/* ============================================================
   Page header (eyebrow + title + sub)
   ============================================================ */
.ps-page-head { padding: 0.2rem 0 1.4rem; margin-bottom: 1.4rem;
  border-bottom: 1px solid var(--ps-line); }
.ps-eyebrow {
  font-family: var(--ps-mono); font-size: 10.5px;
  letter-spacing: 0.26em; text-transform: uppercase;
  color: var(--ps-red); font-weight: 600;
  display: inline-flex; align-items: center; gap: 8px;
}
.ps-eyebrow::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--ps-red); box-shadow: 0 0 8px var(--ps-red);
}
.ps-title {
  font-family: var(--ps-serif); font-style: italic;
  font-size: 2.4rem; line-height: 1.0;
  letter-spacing: -0.018em;
  color: var(--ps-bone);
  margin: 0.5rem 0 0.4rem;
}
.ps-sub {
  color: var(--ps-bone-60);
  font-size: 14px; line-height: 1.55;
  max-width: 620px; margin: 0;
}

/* ============================================================
   Hero identity banner — one full-width card laid out by a CSS
   grid inside ONE st.markdown. NO widgets inside (so there's no
   way for Streamlit's auto-wrappers to break the layout).
   Grid: avatar (auto) · name+meta (1fr) · stats (auto)
   ============================================================ */
.ps-hero {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 1.6rem;
  align-items: center;
  background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012));
  border: 1px solid var(--ps-line-hi);
  border-radius: var(--ps-r-card);
  padding: 1.3rem 1.5rem;
  margin-bottom: 1.6rem;
}
.ps-hero-av {
  width: 76px; height: 76px; border-radius: 50%;
  background: radial-gradient(120% 80% at 30% 20%, #2B2F37 0%, #14171C 60%, #0B0D11 100%);
  border: 1px solid var(--ps-line-hi);
  color: var(--ps-bone-warm);
  font-family: var(--ps-serif); font-style: italic;
  font-size: 2.0rem; line-height: 1;
  display: flex; align-items: center; justify-content: center;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    inset 0 -2px 0 rgba(0,0,0,0.35),
    0 6px 18px -8px rgba(0,0,0,0.7);
  flex-shrink: 0;
}
.ps-hero-meta { min-width: 0; }
.ps-hero-name {
  font-family: var(--ps-serif); font-style: italic;
  font-size: 1.6rem; line-height: 1.05;
  letter-spacing: -0.015em; color: var(--ps-bone);
  margin: 0 0 0.3rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ps-hero-email {
  font-family: var(--ps-mono); font-size: 11.5px;
  letter-spacing: 0.04em; color: var(--ps-bone-60);
  margin: 0 0 0.7rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ps-plan-pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--ps-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--ps-gold);
  background: var(--ps-gold-soft);
  border: 1px solid var(--ps-gold-line);
  padding: 5px 11px; border-radius: var(--ps-r-pill);
}
.ps-plan-pill::before {
  content: "★"; font-size: 9px; line-height: 1; transform: translateY(-1px);
}
.ps-plan-pill.free {
  color: var(--ps-bone-60); background: rgba(244,239,230,0.06);
  border-color: var(--ps-line);
}
.ps-plan-pill.free::before { content: "·"; }

.ps-hero-stats {
  display: grid; grid-template-columns: repeat(4, auto); gap: 0 1.5rem;
  align-items: end;
  flex-shrink: 0;
}
.ps-hero-stat-label {
  font-family: var(--ps-mono); font-size: 9px;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--ps-bone-40); margin-bottom: 3px;
}
.ps-hero-stat-val {
  font-family: var(--ps-serif); font-style: italic;
  font-size: 1.5rem; line-height: 1; color: var(--ps-bone);
  letter-spacing: -0.01em;
}
.ps-hero-stat-val .u {
  font-family: var(--ps-mono); font-style: normal; font-size: 9px;
  letter-spacing: 0.14em; color: var(--ps-bone-60);
  margin-left: 3px; text-transform: uppercase;
}

/* ============================================================
   Section card — each section lives in st.container(key="ps_sec_X")
   so its widgets are real descendants. Card chrome wraps them.
   ============================================================ */
[class*="st-key-ps_sec_"] {
  background: var(--ps-glass-1);
  border: 1px solid var(--ps-line);
  border-radius: var(--ps-r-card);
  padding: 1.4rem 1.5rem 1.6rem;
  margin-bottom: 1.4rem;
  transition: border-color .2s ease, background .2s ease;
}
[class*="st-key-ps_sec_"]:hover { border-color: var(--ps-line-hi); }
.st-key-ps_sec_danger {
  border-color: var(--ps-red-line) !important;
  border-style: dashed !important;
  background: rgba(230,69,48,0.04) !important;
}

.ps-sec-head {
  margin: 0 0 1.2rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px solid var(--ps-line);
}
.ps-sec-title {
  font-family: var(--ps-serif); font-style: italic;
  font-size: 1.4rem; line-height: 1.05;
  letter-spacing: -0.012em; color: var(--ps-bone);
  margin: 0.4rem 0 0.3rem;
}
.ps-sec-desc {
  color: var(--ps-bone-60); font-size: 13px; line-height: 1.55;
  max-width: 620px; margin: 0;
}

/* ============================================================
   Widget reskins — every selector is scoped under .st-key-ps_wrap
   so the masthead and outside-page widgets are not affected.
   No display:contents tricks. Targets natural Streamlit testids.
   ============================================================ */

/* Text + number + textarea + email inputs */
.st-key-ps_wrap [data-testid="stTextInput"] input,
.st-key-ps_wrap [data-testid="stNumberInput"] input,
.st-key-ps_wrap [data-testid="stTextArea"] textarea {
  background: var(--ps-ink-2) !important;
  border: 1px solid var(--ps-line-hi) !important;
  border-radius: var(--ps-r-mid) !important;
  color: var(--ps-bone) !important;
  font-family: var(--ps-sans) !important;
  font-size: 14px !important;
  padding: 0.55rem 0.85rem !important;
  transition: border-color .18s ease;
}
.st-key-ps_wrap [data-testid="stTextInput"] input:focus,
.st-key-ps_wrap [data-testid="stNumberInput"] input:focus,
.st-key-ps_wrap [data-testid="stTextArea"] textarea:focus {
  border-color: var(--ps-gold-line) !important;
  box-shadow: 0 0 0 3px rgba(232,193,112,0.12) !important;
  outline: none !important;
}
.st-key-ps_wrap [data-testid="stTextInput"] input[disabled],
.st-key-ps_wrap [data-testid="stTextInput"] input:read-only {
  color: var(--ps-bone-60) !important;
  background: var(--ps-ink) !important;
}

/* hide number-input native spinners */
.st-key-ps_wrap [data-testid="stNumberInput"] button { display: none !important; }

/* Selectbox */
.st-key-ps_wrap [data-testid="stSelectbox"] > div > div,
.st-key-ps_wrap [data-baseweb="select"] > div {
  background: var(--ps-ink-2) !important;
  border: 1px solid var(--ps-line-hi) !important;
  border-radius: var(--ps-r-mid) !important;
  color: var(--ps-bone) !important;
  min-height: 40px !important;
}
.st-key-ps_wrap [data-baseweb="select"] [role="combobox"] {
  color: var(--ps-bone) !important;
  font-family: var(--ps-sans) !important;
  font-size: 14px !important;
}

/* All widget labels — uppercase mono tags */
.st-key-ps_wrap [data-testid="stTextInput"] label,
.st-key-ps_wrap [data-testid="stNumberInput"] label,
.st-key-ps_wrap [data-testid="stSelectbox"] label,
.st-key-ps_wrap [data-testid="stTextArea"] label,
.st-key-ps_wrap [data-testid="stSegmentedControl"] label,
.st-key-ps_wrap [data-testid="stPills"] label,
.st-key-ps_wrap [data-testid="stRadio"] label[data-testid="stWidgetLabel"] {
  font-family: var(--ps-mono) !important;
  font-size: 9.5px !important;
  letter-spacing: 0.20em !important;
  text-transform: uppercase !important;
  color: var(--ps-bone-60) !important;
  font-weight: 500 !important;
  padding-bottom: 6px !important;
}

/* Toggle (st.toggle) — gold thumb when on, brand colors. */
.st-key-ps_wrap [data-testid="stCheckbox"] label,
.st-key-ps_wrap [data-testid="stCheckbox"] p {
  font-family: var(--ps-sans) !important;
  font-size: 13.5px !important;
  color: var(--ps-bone) !important;
  font-weight: 500 !important;
}

/* Segmented control (native st.segmented_control) */
.st-key-ps_wrap [data-testid="stSegmentedControl"] {
  width: 100%;
}
.st-key-ps_wrap [data-testid="stSegmentedControl"] > div[role="radiogroup"],
.st-key-ps_wrap [data-testid="stSegmentedControl"] > div {
  background: var(--ps-ink-2);
  border: 1px solid var(--ps-line-hi);
  border-radius: var(--ps-r-mid);
  padding: 3px;
  gap: 2px;
}
.st-key-ps_wrap [data-testid="stSegmentedControl"] button {
  flex: 1 1 0 !important;
  background: transparent !important;
  border: 1px solid transparent !important;
  border-radius: var(--ps-r-sm) !important;
  color: var(--ps-bone-60) !important;
  font-family: var(--ps-mono) !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  padding: 0.5rem 0.6rem !important;
  min-height: 36px !important;
  box-shadow: none !important;
  transition: color .14s ease, background .14s ease, border-color .14s ease;
}
.st-key-ps_wrap [data-testid="stSegmentedControl"] button:hover {
  color: var(--ps-bone) !important;
  background: var(--ps-glass-1) !important;
}
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[aria-checked="true"],
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[aria-pressed="true"],
.st-key-ps_wrap [data-testid="stSegmentedControl"] [data-checked="true"] button,
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[kind="primary"] {
  background: linear-gradient(180deg, rgba(244,239,230,0.10), rgba(244,239,230,0.04)) !important;
  color: var(--ps-bone-warm) !important;
  border-color: rgba(244,239,230,0.14) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.10),
    inset 0 -1px 0 rgba(0,0,0,0.18) !important;
  position: relative;
}
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[aria-checked="true"]::after,
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[aria-pressed="true"]::after,
.st-key-ps_wrap [data-testid="stSegmentedControl"] button[kind="primary"]::after {
  content: ""; position: absolute;
  left: 14px; right: 14px; bottom: 3px;
  height: 1.5px; border-radius: 1px;
  background: linear-gradient(90deg,
    rgba(232,193,112,0) 0%, var(--ps-gold) 30%, var(--ps-red) 70%, rgba(230,69,48,0) 100%);
  box-shadow: 0 0 10px -1px rgba(232,193,112,0.5);
}

/* Pills (native st.pills) — bigger card-like options for level/goal. */
.st-key-ps_wrap [data-testid="stPills"] {
  width: 100%;
}
.st-key-ps_wrap [data-testid="stPills"] > div[role="radiogroup"],
.st-key-ps_wrap [data-testid="stPills"] > div {
  background: transparent;
  display: flex; flex-wrap: wrap; gap: 8px;
}
.st-key-ps_wrap [data-testid="stPills"] button {
  background: var(--ps-glass-1) !important;
  border: 1px solid var(--ps-line) !important;
  border-radius: var(--ps-r-pill) !important;
  color: var(--ps-bone-80) !important;
  font-family: var(--ps-sans) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  letter-spacing: -0.005em !important;
  padding: 0.55rem 0.95rem !important;
  min-height: 38px !important;
  transition: color .14s ease, background .14s ease, border-color .14s ease;
  box-shadow: none !important;
}
.st-key-ps_wrap [data-testid="stPills"] button:hover {
  border-color: var(--ps-line-hi) !important;
  background: var(--ps-glass-2) !important;
}
.st-key-ps_wrap [data-testid="stPills"] button[aria-checked="true"],
.st-key-ps_wrap [data-testid="stPills"] button[aria-pressed="true"],
.st-key-ps_wrap [data-testid="stPills"] button[kind="primary"] {
  background: linear-gradient(180deg, rgba(232,193,112,0.12), rgba(232,193,112,0.04)) !important;
  color: var(--ps-bone-warm) !important;
  border-color: rgba(232,193,112,0.55) !important;
  font-weight: 600 !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.06),
    0 0 16px -8px rgba(232,193,112,0.45) !important;
}

/* Action buttons — base reset for ALL stButton inside ps_wrap. */
.st-key-ps_wrap [data-testid="stButton"] button,
.st-key-ps_wrap [data-testid="stDownloadButton"] button {
  font-family: var(--ps-sans) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  border-radius: var(--ps-r-pill) !important;
  padding: 0.55rem 1.2rem !important;
  background: var(--ps-glass-1) !important;
  color: var(--ps-bone) !important;
  border: 1px solid var(--ps-line-hi) !important;
  transition: transform .18s ease, border-color .18s ease,
              background .18s ease, color .18s ease,
              box-shadow .18s ease;
  min-height: 0 !important; height: auto !important; line-height: 1.2 !important;
}
.st-key-ps_wrap [data-testid="stButton"] button:hover,
.st-key-ps_wrap [data-testid="stDownloadButton"] button:hover {
  border-color: var(--ps-line-hi-2) !important;
  background: var(--ps-glass-2) !important;
}
.st-key-ps_wrap [data-testid="stButton"] button[kind="primary"] {
  background: var(--ps-red) !important;
  color: #FFFAF2 !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  font-weight: 600 !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.18),
    0 8px 22px -8px rgba(230,69,48,0.5) !important;
}
.st-key-ps_wrap [data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-1px);
}

/* Flash banners */
.ps-flash {
  font-family: var(--ps-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.55rem 0.9rem;
  border-radius: var(--ps-r-mid);
  margin-bottom: 1rem;
  display: inline-flex; align-items: center; gap: 8px;
}
.ps-flash.ok {
  color: var(--ps-green); background: var(--ps-green-soft);
  border: 1px solid var(--ps-green-line);
}
.ps-flash.err {
  color: var(--ps-red); background: var(--ps-red-soft);
  border: 1px solid var(--ps-red-line);
}
.ps-flash.info {
  color: var(--ps-gold); background: var(--ps-gold-soft);
  border: 1px solid var(--ps-gold-line);
}

/* Plan row inside account section */
.ps-plan-row {
  display: grid; grid-template-columns: auto 1fr auto;
  gap: 1.2rem; align-items: center;
  padding: 1rem 1.1rem;
  background: var(--ps-ink-2);
  border: 1px solid var(--ps-line);
  border-radius: var(--ps-r-mid);
  margin-bottom: 1rem;
}
.ps-plan-name {
  font-family: var(--ps-serif); font-style: italic;
  font-size: 1.3rem; color: var(--ps-bone); line-height: 1;
  display: flex; align-items: center; gap: 0.7rem;
}
.ps-plan-name em { color: var(--ps-gold); font-style: italic; }
.ps-plan-meta {
  font-family: var(--ps-mono); font-size: 10.5px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ps-bone-60); margin-top: 0.5rem;
  display: flex; gap: 1rem; flex-wrap: wrap;
}
.ps-plan-meta .price { color: var(--ps-bone); }
.ps-status-active {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--ps-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ps-green);
  background: var(--ps-green-soft);
  border: 1px solid var(--ps-green-line);
  padding: 5px 10px; border-radius: var(--ps-r-pill);
  margin-left: 0.5rem;
}
.ps-status-active::before {
  content: ""; width: 5px; height: 5px; border-radius: 50%;
  background: var(--ps-green); box-shadow: 0 0 6px var(--ps-green);
}

/* Danger zone inner */
.ps-danger-warn {
  padding: 1rem 1.1rem;
  border: 1px dashed var(--ps-red-line);
  border-radius: var(--ps-r-mid);
  background: rgba(230,69,48,0.06);
  margin-bottom: 1rem;
}
.ps-danger-label {
  font-family: var(--ps-mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.24em; text-transform: uppercase;
  color: var(--ps-red); margin-bottom: 6px;
}
.ps-danger-text {
  color: var(--ps-bone-60); font-size: 12.5px; line-height: 1.55;
  max-width: 520px;
}

/* Helper line ("Active: Better timing · drills aligned...") */
.ps-helper {
  font-family: var(--ps-mono); font-size: 10px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--ps-bone-40); margin-top: 0.7rem;
}
.ps-helper .gold { color: var(--ps-gold); text-transform: uppercase; }

/* Footer */
.ps-foot {
  margin-top: 0.6rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--ps-line);
  font-family: var(--ps-mono); font-size: 10px;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ps-bone-40);
  display: flex; justify-content: space-between;
}

/* ============================================================
   BOTTOM-STICKY SAVE BAR. Outside of ps_wrap (own keyed container)
   so its position:fixed escapes the ps_wrap content stacking.
   ONLY visible when ps_is_dirty is True. Plain flex layout: pill +
   descr (left) | Cancel + Save (right). NO display:contents.
   ============================================================ */
.st-key-ps_savebar {
  position: fixed !important;
  left: 50% !important;
  bottom: 22px !important;
  transform: translateX(-50%) !important;
  width: calc(100% - 48px) !important;
  max-width: 980px !important;
  z-index: 100 !important;
  background: linear-gradient(180deg,
    rgba(20,23,28,0.86) 0%,
    rgba(13,15,19,0.96) 100%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(1.2);
  backdrop-filter: blur(20px) saturate(1.2);
  border: 1px solid var(--ps-line-hi) !important;
  border-radius: 999px !important;
  padding: 0.55rem 0.65rem 0.55rem 1.2rem !important;
  box-shadow:
    0 -8px 28px -8px rgba(232,193,112,0.18),
    0 18px 40px -20px rgba(0,0,0,0.8),
    inset 0 1px 0 rgba(255,255,255,0.04) !important;
  animation: ps-slideup 380ms var(--ps-ease-snap);
}
@keyframes ps-slideup {
  from { transform: translate(-50%, 110%); opacity: 0; }
  to   { transform: translate(-50%, 0);    opacity: 1; }
}

/* The bar's internal stVerticalBlock holds ONE stHorizontalBlock
   with 3 columns: pill text (col), Cancel (col), Save (col).
   We don't flatten — we just style the inner block as a row. */
.st-key-ps_savebar > div[data-testid="stVerticalBlock"] {
  gap: 0 !important;
}
.st-key-ps_savebar [data-testid="stHorizontalBlock"] {
  align-items: center !important;
  gap: 14px !important;
}
.st-key-ps_savebar [data-testid="stColumn"] {
  align-items: center !important;
}
.st-key-ps_savebar [data-testid="stElementContainer"] {
  margin: 0 !important;
}

/* The unsaved label inside the bar */
.ps-savebar-label {
  display: flex; align-items: center; gap: 12px;
  min-width: 0;
}
.ps-unsaved-pill {
  font-family: var(--ps-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--ps-gold);
  background: var(--ps-gold-soft);
  border: 1px solid var(--ps-gold-line);
  padding: 6px 11px; border-radius: var(--ps-r-pill);
  display: inline-flex; align-items: center; gap: 7px;
  white-space: nowrap;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.04),
    0 0 16px -6px rgba(232,193,112,0.45);
}
.ps-unsaved-pill .d {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--ps-gold);
  box-shadow: 0 0 8px var(--ps-gold);
  animation: ps-brand-pulse 2.4s ease-in-out infinite;
}
@keyframes ps-brand-pulse {
  0%, 100% { opacity: 1;    box-shadow: 0 0 8px var(--ps-gold); }
  50%      { opacity: 0.55; box-shadow: 0 0 2px var(--ps-gold); }
}
.ps-savebar-text {
  font-family: var(--ps-sans); font-size: 13px;
  color: var(--ps-bone-60); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.ps-savebar-text em {
  font-family: var(--ps-serif); font-style: italic;
  color: var(--ps-bone); font-weight: 400;
}

/* The two action buttons inside the bar — slightly taller and pill */
.st-key-ps_savebar [data-testid="stButton"] button {
  width: 100% !important;
  height: 40px !important;
  white-space: nowrap !important;
}
.st-key-ps_savebar [data-testid="stButton"] button[kind="primary"] {
  background: linear-gradient(180deg, var(--ps-red) 0%, var(--ps-red-deep) 100%) !important;
  color: #FFFAF2 !important;
  font-weight: 600 !important;
  border: 1px solid rgba(0,0,0,0.25) !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.55),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    0 6px 18px -6px rgba(230,69,48,0.55) !important;
}
.st-key-ps_savebar [data-testid="stButton"] button[kind="primary"]:hover {
  transform: translateY(-1px) !important;
  box-shadow:
    inset 0 1px 0 rgba(232,193,112,0.75),
    inset 0 -1px 0 rgba(0,0,0,0.35),
    0 10px 26px -6px rgba(230,69,48,0.65) !important;
}

/* ============================================================
   Dialog — st.dialog renders an overlay. Style its body to match
   the editorial Edge look. The dialog escapes the page DOM via
   a portal so we can't scope its CSS under .st-key-ps_wrap; we
   target the global stDialog testid instead.
   ============================================================ */
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] h1,
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] h2 {
  font-family: var(--ps-serif) !important; font-style: italic !important;
  color: var(--ps-bone) !important;
}
div[data-testid="stDialog"] [data-testid="stButton"] button {
  border-radius: var(--ps-r-pill) !important;
  font-family: var(--ps-sans) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
}
div[data-testid="stDialog"] [data-testid="stButton"] button[kind="primary"] {
  background: linear-gradient(180deg, var(--ps-red) 0%, var(--ps-red-deep) 100%) !important;
  color: #FFFAF2 !important; border: 1px solid rgba(0,0,0,0.25) !important;
  font-weight: 600 !important;
}

/* ============================================================
   RESPONSIVE — only two breakpoints. The hero collapses to
   stacked at <=720px; the savebar tightens.
   ============================================================ */
@media (max-width: 980px) {
  .st-key-ps_wrap { padding: 1.4rem 20px 9rem; }
  .ps-hero { grid-template-columns: auto minmax(0, 1fr); }
  .ps-hero-stats {
    grid-column: 1 / -1;
    grid-template-columns: repeat(4, 1fr);
    border-top: 1px solid var(--ps-line);
    padding-top: 0.9rem;
    margin-top: 0.4rem;
    gap: 0 0.8rem;
  }
}
@media (max-width: 640px) {
  .st-key-ps_wrap { padding: 1.2rem 16px 8.5rem; }
  .ps-title { font-size: 2rem; }
  .ps-hero {
    grid-template-columns: 1fr;
    text-align: left;
    padding: 1.1rem 1.2rem;
    gap: 1rem;
  }
  .ps-hero-av { width: 60px; height: 60px; font-size: 1.6rem; }
  .ps-hero-stats {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem 0.8rem;
  }
  [class*="st-key-ps_sec_"] { padding: 1.15rem 1.1rem 1.3rem; }
  .ps-sec-title { font-size: 1.25rem; }
  .ps-plan-row { grid-template-columns: 1fr; }

  .st-key-ps_savebar {
    width: calc(100% - 20px) !important;
    bottom: 12px !important;
    padding: 0.5rem 0.5rem 0.5rem 0.9rem !important;
  }
  .ps-savebar-text { display: none !important; }
}
</style>
"""


# ---------------------------------------------------------------------
# Household section helper
# ---------------------------------------------------------------------
def _render_household_section(profile: Dict[str, Any]) -> None:
    """Render the 'Household' settings section (between Billing and Privacy).

    Shows profile management (create/remove sub-account player profiles).
    Hidden for single-seat plans. Lazy-imports auth so the settings page
    stays usable before the household schema is fully migrated.
    """
    import auth as _auth

    user_id = (profile or {}).get("user_id") or (profile or {}).get("id") or ""
    if not user_id:
        return

    # Single-seat plans get no household section at all.
    try:
        seats = _auth.current_household_seats()
    except Exception:
        seats = 1
    if seats <= 1:
        return

    try:
        profiles = _auth.list_household_players(user_id)
    except Exception:
        profiles = []

    family_name = "My Household"
    num_profiles = len(profiles)

    with st.container(key="ps_sec_household"):
        _sec_head("04b", "Household", "Manage your household",
                  "Add player profiles for each member of your household.")

        # Header: family name + profile count
        st.markdown(
            f'<div class="ps-plan-row">'
            f'  <div>'
            f'    <div class="ps-plan-name">{html.escape(family_name)}'
            f'      <span style="font-family:var(--ps-mono);font-size:10px;'
            f'      letter-spacing:0.16em;text-transform:uppercase;'
            f'      color:var(--ps-bone-60);margin-left:10px;font-style:normal;">'
            f'      {num_profiles} of {seats} profiles</span>'
            f'    </div>'
            f'  </div>'
            f'  <div></div><div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Profile list
        if profiles:
            st.markdown(
                '<div style="font-family:var(--ps-mono); font-size:9.5px; '
                'letter-spacing:0.20em; text-transform:uppercase; '
                'color:var(--ps-bone-60); padding:0.8rem 0 0.4rem;">Profiles</div>',
                unsafe_allow_html=True,
            )
            active_player_id = st.session_state.get("player", {}).get("id")
            for p in profiles:
                pid = p.get("id", "")
                pname = p.get("name") or pid
                ppos = p.get("position") or ""
                phand = p.get("handedness") or ""
                is_active = (pid == active_player_id)
                meta_parts = [x for x in [ppos, phand] if x]
                meta_str = " · ".join(meta_parts) if meta_parts else ""
                row_col, btn_col = st.columns([4, 1])
                with row_col:
                    st.markdown(
                        f'<div style="padding:6px 0 2px 0; font-size:13px; '
                        f'color:var(--ps-bone);">'
                        f'{html.escape(str(pname))}'
                        + (f'<span style="font-family:var(--ps-mono);font-size:10px;'
                           f'letter-spacing:0.12em;color:var(--ps-bone-60);margin-left:8px;">'
                           f'{html.escape(meta_str)}'
                           + (' · active' if is_active else '')
                           + '</span>' if (meta_str or is_active) else "")
                        + '</div>',
                        unsafe_allow_html=True,
                    )
                with btn_col:
                    # Hide Remove for the currently-active profile
                    if not is_active and pid:
                        if st.button("Remove", key=f"ps_hh_remove_{pid}",
                                     type="secondary"):
                            try:
                                _auth.remove_household_player(pid)
                            except Exception:
                                pass
                            st.rerun()

        # Add a player form (only when under seat cap)
        if num_profiles < seats:
            st.markdown(
                '<div style="height:1px; margin:1.2rem 0; '
                'background:var(--ps-line);"></div>'
                '<div style="font-family:var(--ps-mono); font-size:9.5px; '
                'letter-spacing:0.20em; text-transform:uppercase; '
                'color:var(--ps-bone-60); padding-bottom:6px;">Add a Player</div>',
                unsafe_allow_html=True,
            )
            add_name = st.text_input(
                "Name",
                value="",
                placeholder="Player name",
                key="ps_hh_add_name",
            )
            add_hand = st.radio(
                "Bat hand",
                options=["Right", "Left"],
                horizontal=True,
                key="ps_hh_add_hand",
            )
            add_position = st.text_input(
                "Position (optional)",
                value="",
                placeholder="e.g. SS, 2B, CF",
                key="ps_hh_add_position",
            )
            add_birth_year = st.text_input(
                "Birth year",
                value="",
                placeholder="e.g. 2014 — required for players under 13",
                key="ps_hh_add_birth_year",
            )
            # COPPA: a player under 13 may only be added by their parent/guardian,
            # who must consent to the child's data being collected. We record this
            # affirmation (who/when) on the new player row.
            add_consent = st.checkbox(
                "I'm this player's parent or legal guardian and I consent to "
                "BarrelLabs collecting their swing videos and related data to "
                "provide swing analysis.",
                key="ps_hh_add_consent",
            )
            if st.button("Add player", key="ps_hh_add_submit"):
                raw_name = (add_name or "").strip()
                from analyzer import parse_birth_year as _pby, is_under_coppa_age as _uca
                _add_by = _pby(add_birth_year)
                if not raw_name:
                    st.session_state["ps_flash_err"] = "Enter a player name."
                    st.rerun()
                elif _add_by is None:
                    st.error(
                        "Please enter the player's birth year (e.g. 2014) — it "
                        "sets the age-fair score and the under-13 protections."
                    )
                elif _uca(_add_by) and not add_consent:
                    # Under 13 needs the guardian affirmation, full stop.
                    st.error(
                        "Players under 13 can only be added by a parent or "
                        "guardian — please check the consent box above."
                    )
                else:
                    handedness = "RIGHT" if (add_hand or "Right") == "Right" else "LEFT"
                    position = (add_position or "").strip() or None
                    try:
                        result = _auth.create_household_player(
                            raw_name, handedness, position,
                            birth_year=add_birth_year,
                            guardian_consent=bool(add_consent),
                        )
                        if result.get("ok"):
                            st.success("Added " + raw_name)
                            st.rerun()
                        else:
                            st.error(result.get("error") or "Could not add player.")
                    except Exception as exc:
                        st.error(str(exc))
        elif num_profiles >= seats:
            st.markdown(
                '<div style="font-size:13px; color:var(--ps-bone-60); '
                'padding:0.8rem 0 0.4rem;">Household is full — all profiles in use.</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------
# Tiny render helpers
# ---------------------------------------------------------------------
def _flash(level: str, msg: str) -> None:
    icon = {"ok": "✓", "err": "!", "info": "·"}.get(level, "·")
    st.markdown(
        f'<div class="ps-flash {level}"><span>{icon}</span>{html.escape(msg)}</div>',
        unsafe_allow_html=True,
    )


def _sec_head(num: str, eyebrow: str, title: str, desc: str = "") -> None:
    st.markdown(
        '<div class="ps-sec-head">'
        f'<span class="ps-eyebrow">{html.escape(num)} · {html.escape(eyebrow)}</span>'
        f'<h2 class="ps-sec-title">{html.escape(title)}</h2>'
        + (f'<p class="ps-sec-desc">{html.escape(desc)}</p>' if desc else "")
        + '</div>',
        unsafe_allow_html=True,
    )


# Friendly page-label lookup for the leave dialog ("…continuing to X?").
_PAGE_LABELS = {
    "dashboard": "Dashboard",
    "saved_reports": "Sessions",
    "compare_swings": "Compare",
    "development_tracker": "Drills",
    "historical_charts": "Library",
    "swing_report": "Swing Report",
    "billing": "Billing",
}


def _page_label_for(page_key: str) -> str:
    return _PAGE_LABELS.get(page_key or "", "the next page")


# ---------------------------------------------------------------------
# THE RENDER FUNCTION
# ---------------------------------------------------------------------
def render_player_settings_page(
    user: Dict[str, Any],
    build_pdf_fn: Optional[Callable[[Dict[str, Any]], bytes]] = None,
) -> None:
    """Render the Player Settings page. Called from app.py route dispatch."""
    del build_pdf_fn  # accepted for parity, unused

    # If a previous interaction set the "account deleted" flag, render the
    # goodbye screen BEFORE any chrome and stop.
    if st.session_state.get("ps_account_deleted"):
        status = st.session_state.pop("ps_account_deleted")
        _render_goodbye(status)
        st.stop()

    # CRITICAL: compute dirty state from session_state BEFORE the masthead.
    # The masthead's nav intercept reads `ps_is_dirty` at the top of the
    # rerun — if we computed dirty at the bottom (as v2 did) the masthead
    # would see stale state and let nav clicks through.
    if user:
        is_dirty, dirty_fields = _compute_dirty(user)
    else:
        is_dirty, dirty_fields = False, []
    st.session_state["ps_is_dirty"] = is_dirty

    inject_global_theme()
    render_edge_masthead(user, active_page="player_settings")
    render_edge_page_wrapper_open()

    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="ps-atmos"></div>', unsafe_allow_html=True)

    if not user:
        with st.container(key="ps_wrap"):
            st.markdown(
                '<div class="ps-page-head">'
                '<span class="ps-eyebrow">Profile · Account</span>'
                '<h1 class="ps-title">Player Settings</h1>'
                '<p class="ps-sub">Sign in to manage your profile.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        render_edge_page_wrapper_close()
        return

    # If the masthead set pending_nav AND user has NO unsaved changes,
    # navigate immediately. Only show the dialog when there's something
    # to save.
    pending_nav = st.session_state.get("ps_pending_nav_to")
    if pending_nav and not is_dirty:
        st.session_state["page"] = pending_nav
        st.session_state.pop("ps_pending_nav_to", None)
        for _k in ("view_swing_record", "view_swing_path",
                    "view_swing_report_id", "view"):
            st.session_state.pop(_k, None)
        st.rerun()

    # Sync newly-confirmed email if the user just clicked a confirmation link.
    try:
        from auth import sync_email_after_confirm
        synced = sync_email_after_confirm()
        if synced:
            user = st.session_state.get("player") or user
            st.session_state["ps_flash_ok"] = (
                f"Email change confirmed — your login is now {synced}."
            )
    except Exception:
        pass

    saved = _saved_defaults(user)
    name_disp = user.get("name") or "Player"
    email_disp = user.get("email") or ""
    initials = _initials(user.get("name", ""), email_disp)
    stats = _quick_stats(user)
    plan = _plan_summary()
    plan_class = "" if (plan["plan"] and plan["plan"].lower() != "free") else " free"
    plan_text = (f'BarrelLabs {plan["plan"]}' if plan["plan"].lower() != "free"
                  else "Free")

    # ===================================================================
    # MAIN PAGE WRAP — every widget lives inside this keyed container so
    # the .st-key-ps_wrap-scoped CSS reskins them.
    # ===================================================================
    with st.container(key="ps_wrap"):

        # Page header
        st.markdown(
            '<div class="ps-page-head">'
            '<span class="ps-eyebrow">Profile · Account</span>'
            '<h1 class="ps-title">Player Settings</h1>'
            '<p class="ps-sub">Manage your player profile, swing '
            'preferences, and account settings. Edits surface in a save '
            'bar at the bottom of the page — click <em>Save changes</em> '
            'there to commit.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Flash messages
        for level in ("ok", "err", "info"):
            msg = st.session_state.pop(f"ps_flash_{level}", None)
            if msg:
                _flash(level, msg)

        # ============== HERO IDENTITY BANNER ==============
        # Pure HTML in ONE st.markdown call. No widgets inside, so
        # Streamlit can't break the layout with its auto-wrappers.
        st.markdown(
            f'<div class="ps-hero">'
            f'  <div class="ps-hero-av">{html.escape(initials)}</div>'
            f'  <div class="ps-hero-meta">'
            f'    <div class="ps-hero-name">{html.escape(name_disp)}</div>'
            f'    <div class="ps-hero-email">{html.escape(email_disp)}</div>'
            f'    <span class="ps-plan-pill{plan_class}">{html.escape(plan_text)}</span>'
            f'  </div>'
            f'  <div class="ps-hero-stats">'
            f'    <div><div class="ps-hero-stat-label">Swings</div>'
            f'      <div class="ps-hero-stat-val">{html.escape(stats["swings"])}</div></div>'
            f'    <div><div class="ps-hero-stat-label">Best</div>'
            f'      <div class="ps-hero-stat-val">{html.escape(stats["best"])}<span class="u">/100</span></div></div>'
            f'    <div><div class="ps-hero-stat-label">Streak</div>'
            f'      <div class="ps-hero-stat-val">{html.escape(stats["streak"])}<span class="u">d</span></div></div>'
            f'    <div><div class="ps-hero-stat-label">Member</div>'
            f'      <div class="ps-hero-stat-val" style="font-size:1.05rem;">{html.escape(stats["member"])}</div></div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ============== SECTION 01 — IDENTITY ==============
        with st.container(key="ps_sec_profile"):
            _sec_head("01", "Identity", "Your player card",
                      "The basics — your name shows on every swing report.")
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("First name", value=saved["first"], key=WK["first"])
            with c2:
                st.text_input("Last name", value=saved["last"], key=WK["last"])
            c3, c4 = st.columns(2)
            with c3:
                st.text_input("Display name", value=saved["display"],
                               placeholder="How you appear on shared reports",
                               key=WK["display"])
            with c4:
                st.text_input("Email · login id", value=email_disp,
                               disabled=True, key="ps_email_display")

        # ============== SECTION 02 — BASEBALL ==============
        with st.container(key="ps_sec_bb"):
            _sec_head("02", "Diamond", "Baseball profile",
                      "Optional, but the more we know, the sharper "
                      "your MLB-comparison match.")

            pos_labels = [lbl for _s, lbl in POSITIONS]
            sec_labels = [lbl for _s, lbl in SECONDARY_POSITIONS]
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Primary position", pos_labels,
                              index=pos_labels.index(saved["pos"])
                              if saved["pos"] in pos_labels else 0,
                              key=WK["pos"])
            with c2:
                st.selectbox("Secondary position", sec_labels,
                              index=sec_labels.index(saved["pos_sec"])
                              if saved["pos_sec"] in sec_labels else 0,
                              key=WK["pos_sec"])

            c3, c4 = st.columns(2)
            with c3:
                st.segmented_control("Bats", BATS_OPTIONS,
                                       selection_mode="single",
                                       default=saved["bats"], key=WK["bats"])
            with c4:
                st.segmented_control("Throws", THROWS_OPTIONS,
                                       selection_mode="single",
                                       default=saved["throws"], key=WK["throws"])

            c5, c6 = st.columns(2)
            with c5:
                st.text_input("Birth year", value=saved["birth_year"],
                               placeholder="e.g. 2014", key=WK["birth_year"],
                               help="Used for an age-accurate Swing Score. "
                                    "Updates automatically each year.")
                from analyzer import age_from_birth_year as _afby
                _age_hint = _afby(st.session_state.get(WK["birth_year"])
                                  or saved["birth_year"])
                if _age_hint is not None:
                    st.caption(f"Age {_age_hint}")
            with c6:
                h1, h2 = st.columns(2)
                with h1:
                    st.number_input("Height · ft",
                                     min_value=3, max_value=8,
                                     value=int(saved["ft"]),
                                     step=1, key=WK["ft"])
                with h2:
                    st.number_input("Height · in",
                                     min_value=0, max_value=11,
                                     value=int(saved["in"]),
                                     step=1, key=WK["in"])

            c7, c8 = st.columns(2)
            with c7:
                st.number_input("Weight · lb",
                                  min_value=50, max_value=400,
                                  value=int(saved["wt"]),
                                  step=1, key=WK["wt"])
            with c8:
                st.text_input("Graduation year", value=saved["grad"],
                                placeholder="e.g. 2027", key=WK["grad"])

            st.text_input("Team · school · organization",
                            value=saved["team"],
                            placeholder="e.g. 16U Tigers · Riverside HS",
                            key=WK["team"])

            # Competition level — native st.pills (single-select)
            st.pills("Competition level", LEVELS,
                       selection_mode="single",
                       default=saved["level"], key=WK["level"])

        # ============== SECTION 03 — SWING PREFERENCES ==============
        with st.container(key="ps_sec_swing"):
            _sec_head("03", "Lab", "Swing preferences",
                      "Tune how the analyzer frames your reports. "
                      "The training goal directly weights your drill plan.")

            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Default swing view", SWING_VIEWS,
                              index=SWING_VIEWS.index(saved["view"]),
                              key=WK["view"])
            with c2:
                st.segmented_control("MLB comparison handedness",
                                       MLB_HAND_PREFS,
                                       selection_mode="single",
                                       default=saved["hand"], key=WK["hand"])

            st.pills("Primary training goal · drives drill plan",
                       GOAL_OPTIONS,
                       selection_mode="single",
                       default=saved["goal"], key=WK["goal"])

            active_goal = st.session_state.get(WK["goal"]) or saved["goal"]
            st.markdown(
                '<div class="ps-helper">Active: '
                f'<span class="gold">{html.escape(active_goal)}</span> · '
                'drills aligned with this goal get a small boost in the plan.'
                '</div>',
                unsafe_allow_html=True,
            )

            st.segmented_control("Default report focus",
                                   REPORT_FOCUS,
                                   selection_mode="single",
                                   default=saved["focus"], key=WK["focus"])

        # ============== SECTION 04 — ACCOUNT & BILLING ==============
        with st.container(key="ps_sec_acct"):
            _sec_head("04", "Account", "Plan & access",
                      "Billing runs through Stripe — manage payment "
                      "methods, invoices, and cancel from the portal.")

            plan_label = plan.get("plan", "Free")
            plan_status_html = (
                '<span class="ps-status-active">Active</span>'
                if plan_label and plan_label.lower() != "free" else ''
            )
            plan_meta_bits = []
            if plan.get("price") and plan["price"] != "—":
                plan_meta_bits.append(
                    f'<span class="price">{html.escape(plan["price"])}</span>'
                )
            if plan.get("next_billing") and plan["next_billing"] != "—":
                plan_meta_bits.append(
                    f'Next billing · {html.escape(plan["next_billing"])}'
                )
            if plan_label.lower() == "free":
                plan_meta_bits.append("No active subscription")
            meta_html = " · ".join(plan_meta_bits) if plan_meta_bits else ""

            st.markdown(
                f'<div class="ps-plan-row">'
                f'  <div>'
                f'    <div class="ps-plan-name">BarrelLabs <em>{html.escape(plan_label)}</em>{plan_status_html}</div>'
                f'    <div class="ps-plan-meta">{meta_html}</div>'
                f'  </div>'
                f'  <div></div><div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if plan.get("has_stripe"):
                if st.button("Manage billing  →", key="ps_billing_portal"):
                    try:
                        from stripe_client import create_portal_session
                        origin = (
                            (st.context.headers.get("Origin")
                             if hasattr(st, "context") else "")
                            or "http://localhost:8501"
                        )
                        url = create_portal_session(
                            return_url=f"{origin}/?page=player_settings"
                        )
                        st.markdown(
                            f'<meta http-equiv="refresh" '
                            f'content="0;url={html.escape(url)}">',
                            unsafe_allow_html=True,
                        )
                        st.session_state["ps_flash_info"] = (
                            "Redirecting to the Stripe billing portal…"
                        )
                    except Exception as exc:
                        st.session_state["ps_flash_err"] = str(exc)
                        st.rerun()
            else:
                if st.button("Choose a plan  →", key="ps_choose_plan"):
                    st.session_state["page"] = "billing"
                    st.rerun()

            # Email change row — vertical stack, no st.columns hack.
            st.text_input("Change email", value="",
                            placeholder="new@email.com",
                            help="Supabase sends a confirmation link to your "
                                 "current email. The change takes effect "
                                 "after you click that link.",
                            key=WK["new_email"])
            if st.button("Send verification email", key="ps_send_email_change"):
                try:
                    from auth import request_email_change
                    note = request_email_change(
                        st.session_state.get(WK["new_email"], "")
                    )
                    st.session_state["ps_flash_info"] = note
                except ValueError as exc:
                    st.session_state["ps_flash_err"] = str(exc)
                except Exception as exc:
                    st.session_state["ps_flash_err"] = (
                        f"Could not start email change: {exc}"
                    )
                st.rerun()

            st.markdown(
                '<div style="height:1px; margin:1.2rem 0; '
                'background:var(--ps-line);"></div>'
                '<div style="font-family:var(--ps-mono); font-size:9.5px; '
                'letter-spacing:0.20em; text-transform:uppercase; '
                'color:var(--ps-bone-60); padding-bottom:6px;">Password</div>'
                '<div style="font-size:13px; color:var(--ps-bone-60); '
                'padding-bottom:0.8rem;">We don\'t store passwords — '
                'Supabase handles auth. Reset via a one-time email link.'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Send password reset email", key="ps_send_reset_email"):
                try:
                    from auth import request_password_reset
                    request_password_reset(email_disp)
                    st.session_state["ps_flash_info"] = (
                        f"Password-reset link sent to {email_disp} "
                        "if that account exists."
                    )
                except Exception as exc:
                    st.session_state["ps_flash_err"] = str(exc)
                st.rerun()

            st.markdown(
                '<div style="height:1px; margin:1.2rem 0; '
                'background:var(--ps-line);"></div>'
                '<div style="color:var(--ps-bone-60); font-size:13px; '
                'padding-bottom:0.6rem;">'
                f'Signed in as <em style="font-family:var(--ps-serif); '
                f'font-style:italic; color:var(--ps-bone);">'
                f'{html.escape(email_disp)}</em> — sign out of this device.'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Log out", key="ps_logout"):
                try:
                    from auth import sign_out
                    sign_out()
                    for _k in ("player", "user", "page", "view",
                                "view_swing_record", "view_swing_path",
                                "view_swing_report_id"):
                        st.session_state.pop(_k, None)
                except Exception:
                    pass
                st.rerun()

        # ============== SECTION 04b — HOUSEHOLD ==============
        _render_household_section(user)

        # ============== SECTION 05 — PRIVACY & DATA ==============
        with st.container(key="ps_sec_priv"):
            _sec_head("05", "Privacy", "Your data",
                      "Control how your swing data is used and shared. "
                      "These toggles save instantly.")

            pv_anon = st.toggle(
                "Improve BarrelLabs's models with my swings  ·  "
                "anonymized only",
                value=saved["priv_anon"],
                key=WK["priv_anon"],
            )
            pv_coach = st.toggle(
                "Allow shareable coach links for my swing reports",
                value=saved["priv_coach"],
                key=WK["priv_coach"],
            )
            pv_email_prod = st.toggle(
                "Product update emails  ·  under one a month",
                value=saved["priv_email_prod"],
                key=WK["priv_email_prod"],
            )
            pv_email_perf = st.toggle(
                "Weekly performance summary emails",
                value=saved["priv_email_perf"],
                key=WK["priv_email_perf"],
            )
            # Persist toggles instantly to extras (auto-save).
            _extras_set("privacy_anon", bool(pv_anon))
            _extras_set("privacy_coach", bool(pv_coach))
            _extras_set("privacy_email_prod", bool(pv_email_prod))
            _extras_set("privacy_email_perf", bool(pv_email_perf))

            st.markdown(
                '<div style="height:1px; margin:1.2rem 0; '
                'background:var(--ps-line);"></div>'
                '<div style="font-family:var(--ps-mono); font-size:9.5px; '
                'letter-spacing:0.20em; text-transform:uppercase; '
                'color:var(--ps-bone-60);">Export my data</div>'
                '<div style="font-size:13px; color:var(--ps-bone-60); '
                'padding:0.4rem 0 0.8rem; max-width:520px;">'
                'Download a JSON archive of every swing you\'ve uploaded, '
                'every report you\'ve generated, and your profile metadata.'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Export archive", key="ps_export"):
                try:
                    import json as _json
                    import datetime as _dt
                    from player_storage import load_swing_history
                    history = load_swing_history(
                        user.get("slug") or user.get("id")
                    ) or []
                    archive = {
                        "exported_at": _dt.datetime.utcnow().isoformat() + "Z",
                        "player": {k: v for k, v in user.items()
                                    if k != "gamification"},
                        "swings": history,
                        "preferences": _extras(),
                    }
                    st.download_button(
                        "↓ Download barrellabs_archive.json",
                        data=_json.dumps(archive, indent=2, default=str
                                          ).encode("utf-8"),
                        file_name="barrellabs_archive.json",
                        mime="application/json",
                        key="ps_export_dl",
                    )
                except Exception as exc:
                    st.session_state["ps_flash_err"] = (
                        f"Could not build archive: {exc}"
                    )
                    st.rerun()

        # ============== SECTION 06 — DANGER ZONE ==============
        with st.container(key="ps_sec_danger"):
            _sec_head("06", "Danger zone", "Delete account")
            st.markdown(
                '<div class="ps-danger-warn">'
                '<div class="ps-danger-label">Permanent · Cannot be undone</div>'
                '<div class="ps-danger-text">Deleting your account erases '
                'every swing, every report, and cancels your subscription. '
                'We can\'t recover deleted accounts — even with proof of '
                'identity. If you\'re between seasons, pause your '
                'subscription from the billing portal instead.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            confirm_armed = st.session_state.get("ps_delete_armed", False)
            if not confirm_armed:
                if st.button("Delete account", key="ps_delete_arm"):
                    st.session_state["ps_delete_armed"] = True
                    st.rerun()
            else:
                st.markdown(
                    '<div style="margin:0.4rem 0 0.6rem; '
                    'font-family:var(--ps-mono); font-size:11px; '
                    'letter-spacing:0.18em; text-transform:uppercase; '
                    'color:var(--ps-red);">'
                    'Are you sure? Click below to permanently delete '
                    'your account.</div>',
                    unsafe_allow_html=True,
                )
                cf1, cf2 = st.columns([1, 1])
                with cf1:
                    if st.button("Cancel", key="ps_delete_cancel"):
                        st.session_state.pop("ps_delete_armed", None)
                        st.rerun()
                with cf2:
                    if st.button("Yes — delete everything",
                                   key="ps_delete_confirm", type="primary"):
                        from auth import delete_account
                        status = delete_account()
                        st.session_state.pop("ps_delete_armed", None)
                        st.session_state["ps_account_deleted"] = status
                        st.rerun()

        # Footer
        st.markdown(
            f'<div class="ps-foot">'
            f'<span>§ End · BarrelLabs Edge</span>'
            f'<span>Member since {html.escape(stats["member"])}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ===================================================================
    # BOTTOM-STICKY SAVE BAR — its OWN keyed container, OUTSIDE ps_wrap.
    # position:fixed escapes whatever stacking context ps_wrap is in.
    # Only renders when dirty.
    # ===================================================================
    save_clicked = False
    cancel_clicked = False
    if is_dirty:
        n = len(dirty_fields)
        word = "field" if n == 1 else "fields"
        with st.container(key="ps_savebar"):
            label_col, cancel_col, save_col = st.columns([3, 1, 1])
            with label_col:
                st.markdown(
                    f'<div class="ps-savebar-label">'
                    f'<span class="ps-unsaved-pill">'
                    f'<span class="d"></span>Unsaved · {n} {word}</span>'
                    f'<span class="ps-savebar-text">'
                    f'Edits to <em>{html.escape(name_disp)}</em>\'s profile '
                    f'aren\'t saved yet.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with cancel_col:
                cancel_clicked = st.button("Discard", key="ps_cancel_bar",
                                              use_container_width=True)
            with save_col:
                save_clicked = st.button("Save changes", key="ps_save_bar",
                                           type="primary",
                                           use_container_width=True)

    # ===================================================================
    # LEAVE-PAGE DIALOG — st.dialog, opens when nav was attempted AND
    # there are unsaved changes. Centered overlay; auto-handles z-index
    # and dismiss-on-overlay-click.
    # ===================================================================
    if pending_nav and is_dirty:
        _show_leave_dialog(
            target_key=pending_nav,
            n=len(dirty_fields),
            user=user,
        )

    # ===================================================================
    # HANDLERS — these fire AFTER the wrap closes so the next rerun
    # starts cleanly from the top.
    # ===================================================================
    if save_clicked:
        _do_save(user)
        st.rerun()

    if cancel_clicked:
        # "Discard" — wipe widget state, then the next rerun will read
        # saved DB values and is_dirty becomes False.
        _wipe_form_widget_state()
        st.session_state["ps_flash_info"] = "Edits discarded."
        st.rerun()

    render_edge_page_wrapper_close()


# ---------------------------------------------------------------------
# Save logic (unchanged from v2 — same auth.update_profile contract)
# ---------------------------------------------------------------------
def _do_save(user: Dict[str, Any]) -> bool:
    from auth import update_profile
    cur = _current_field_values(user)

    def _parse_birth_year(v):
        # Shared validation so signup, add-player, and settings agree.
        from analyzer import parse_birth_year
        return parse_birth_year(v)

    db_bats = {"Right": "RIGHT", "Left": "LEFT",
                "Switch": "SWITCH"}.get(cur["bats"], "RIGHT")
    # Resolve pos label back to slug, then to a clean DB string.
    pos_slug = next((s for s, lbl in POSITIONS if lbl == cur["pos"]), "")
    sec_slug = next((s for s, lbl in SECONDARY_POSITIONS
                       if lbl == cur["pos_sec"]), "")
    pos_label_clean = next(
        (lbl for s, lbl in POSITIONS if s == pos_slug), ""
    )
    if "·" in pos_label_clean:
        pos_db = pos_label_clean.split("·", 1)[1].strip()
    else:
        pos_db = pos_label_clean.strip()

    updated = update_profile(
        user["slug"],
        name=_join_name(cur["first"], cur["last"]) or user.get("name"),
        handedness=db_bats,
        height_in=int(cur["ft"]) * 12 + int(cur["in"]),
        weight_lb=int(cur["wt"]),
        birth_year=_parse_birth_year(cur["birth_year"]),
        team=(cur["team"] or "").strip(),
        position=pos_db,
        throws=cur["throws"],
        level=cur["level"],
        primary_goal=cur["goal"],
    )
    if updated:
        _extras_set("display_name", (cur["display"] or "").strip())
        _extras_set("position_slug", pos_slug)
        _extras_set("secondary_position_slug", sec_slug)
        _extras_set("graduation_year", (cur["grad"] or "").strip())
        _extras_set("default_swing_view", cur["view"])
        _extras_set("mlb_hand_pref", cur["hand"])
        _extras_set("default_report_focus", cur["focus"])
        st.session_state["ps_flash_ok"] = (
            f"Profile saved. New drill plans will reflect "
            f"your goal: {cur['goal']}."
        )
        # Also clear pending_nav if a nav was queued; the dialog flow
        # handles the follow-on nav itself.
        return True

    st.session_state["ps_flash_err"] = (
        "Could not save profile. Please try again, or check your network."
    )
    return False


# ---------------------------------------------------------------------
# Leave-page dialog (uses st.dialog — first-class modal)
# ---------------------------------------------------------------------
@st.dialog("Unsaved changes")
def _leave_dialog_impl(target_key: str, n: int, user: Dict[str, Any]) -> None:
    word = "field" if n == 1 else "fields"
    target_label = _page_label_for(target_key)
    st.markdown(
        '<span style="font-family:\'Geist Mono\',monospace; font-size:9.5px; '
        'font-weight:600; letter-spacing:0.24em; text-transform:uppercase; '
        'color:#E64530;">· Unsaved edits</span>'
        f'<h3 style="font-family:\'Instrument Serif\',serif; font-style:italic; '
        f'font-size:1.55rem; color:#F4EFE6; line-height:1.1; '
        f'margin:0.5rem 0 0.4rem;">You have <em style="color:#E8C170;">'
        f'{n} unsaved {word}</em>.</h3>'
        f'<p style="font-size:13.5px; color:rgba(244,239,230,0.6); '
        f'line-height:1.55; margin:0 0 0.8rem;">'
        f'Save before continuing to {html.escape(target_label)}? '
        f'Discarded edits can\'t be recovered.</p>',
        unsafe_allow_html=True,
    )
    cs, cd, cv = st.columns([1, 1, 1])
    with cs:
        if st.button("Stay on page", key="ps_dlg_stay",
                       use_container_width=True):
            st.session_state.pop("ps_pending_nav_to", None)
            st.rerun()
    with cd:
        if st.button("Discard", key="ps_dlg_discard",
                       use_container_width=True):
            target = st.session_state.pop("ps_pending_nav_to", None) or "dashboard"
            _wipe_form_widget_state()
            st.session_state["page"] = target
            for _k in ("view_swing_record", "view_swing_path",
                        "view_swing_report_id", "view"):
                st.session_state.pop(_k, None)
            st.rerun()
    with cv:
        if st.button("Save & continue", key="ps_dlg_save",
                       type="primary", use_container_width=True):
            target = st.session_state.pop("ps_pending_nav_to", None) or "dashboard"
            if _do_save(user):
                st.session_state["page"] = target
                for _k in ("view_swing_record", "view_swing_path",
                            "view_swing_report_id", "view"):
                    st.session_state.pop(_k, None)
            st.rerun()


def _show_leave_dialog(*, target_key: str, n: int, user: Dict[str, Any]) -> None:
    """Open the leave-page dialog once per pending_nav cycle. The dialog
    is responsible for clearing pending_nav (via Stay/Discard/Save)."""
    _leave_dialog_impl(target_key, n, user)


# ---------------------------------------------------------------------
# Goodbye screen (rendered standalone after account deletion)
# ---------------------------------------------------------------------
def _render_goodbye(status: Dict[str, Any]) -> None:
    st.markdown(
        f'<div style="max-width:560px; margin:6rem auto; '
        f'text-align:center; color:#F4EFE6; '
        f'font-family:Geist,system-ui;">'
        f'<div style="font-family:\'Geist Mono\',monospace; '
        f'font-size:10.5px; letter-spacing:0.26em; '
        f'text-transform:uppercase; color:#E64530;">'
        f'· Account deleted</div>'
        f'<h1 style="font-family:\'Instrument Serif\',serif; '
        f'font-style:italic; font-size:2.4rem; line-height:1.05; '
        f'margin:0.8rem 0 0.8rem;">Your data has been removed.</h1>'
        f'<p style="color:rgba(244,239,230,0.6); font-size:14.5px; '
        f'line-height:1.55;">'
        f'{status.get("swings_deleted", 0)} swings, your profile, and '
        f'{"your active subscription " if status.get("stripe_cancelled") else ""}'
        f'have been wiped from BarrelLabs. Thanks for being part of the lab — '
        f'come back anytime.</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
