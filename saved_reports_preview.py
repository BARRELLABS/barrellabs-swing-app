"""
Saved Reports Preview — Phase 1 design approval page.

This is a PREVIEW-ONLY route. It does NOT replace the existing
saved_reports.py. It is reached at:

    /?page=saved_reports_preview

No dashboard buttons route here. Production navigation is unchanged.

Design intent: visual parity with the v3 Edge dashboard
(mock_dashboard_template.py) — Instrument Serif italic display type,
Geist sans body, Geist Mono labels, bone palette, editorial issue line,
sports-magazine card grid.

This file is the design preview only; once approved, the wire-up phase
will replace saved_reports.py's body with this template and route the
Sessions pill to it.
"""

from __future__ import annotations

import html
import textwrap
from datetime import datetime
from typing import Dict, Any, List, Optional

import streamlit as st

from bl_edge_chrome import (
    render_edge_masthead,
    render_edge_page_wrapper_open,
    render_edge_page_wrapper_close,
)

try:
    from player_storage import load_swing_history
except Exception:
    load_swing_history = None  # tolerated in design-preview mode


# =====================================================================
#  Shared Edge token CSS — mirrors mock_dashboard_template.py exactly
# =====================================================================
_EDGE_TOKENS_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:           #0A0B0E;
  --bg-elev:      #11141A;
  --bg-glass:     rgba(255, 255, 255, 0.025);
  --bg-glass-hi:  rgba(255, 255, 255, 0.045);
  --line:         rgba(244, 239, 230, 0.08);
  --line-hi:      rgba(244, 239, 230, 0.16);
  --line-lo:      rgba(244, 239, 230, 0.04);
  --bone:         #F4EFE6;
  --bone-dim:     #C8C4BB;
  --gray-1:       #8B8E94;
  --gray-2:       #565A62;
  --gray-3:       #2A2D33;
  --red:          #E64530;
  --red-deep:     #B83320;
  --red-soft:     rgba(230, 69, 48, 0.12);
  --red-glow:     rgba(230, 69, 48, 0.32);
  --gold:         #E8C170;
  --gold-deep:    #C9A350;
  --gold-soft:    rgba(232, 193, 112, 0.10);
  --green:        #4AE38C;
  --amber:        #FFB948;
  --serif:        'Instrument Serif', 'Fraunces', Georgia, serif;
  --serif-alt:    'Fraunces', 'Instrument Serif', Georgia, serif;
  --sans:         'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --mono:         'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;
  --radius-xs:    4px;
  --radius-sm:    8px;
  --radius:       14px;
  --radius-lg:    20px;
}
</style>
"""


_SRPREVIEW_CSS = """
<style>
/* ---------- ISSUE LINE ---------- */
.srp-issue-line {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 0 28px;
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--gray-2);
  border-bottom: 1px solid var(--line);
  margin-bottom: 36px;
}
.srp-issue-line .center { color: var(--bone-dim); }
.srp-issue-line .right  { color: var(--gray-2); }

/* ---------- HERO ---------- */
.srp-hero {
  display: grid; grid-template-columns: 1.4fr 1fr; gap: 60px;
  align-items: end;
  padding: 8px 0 56px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 48px;
}
.srp-hero-eyebrow {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--red); margin-bottom: 22px;
  display: inline-flex; align-items: center; gap: 10px;
}
.srp-hero-eyebrow .swatch {
  display: inline-block; width: 22px; height: 1px; background: var(--red);
}
.srp-hero-headline {
  font-family: var(--serif); font-weight: 400;
  font-size: 88px; line-height: 0.98; letter-spacing: -0.025em;
  color: var(--bone); margin: 0 0 22px;
}
.srp-hero-headline .ital {
  font-style: italic; color: var(--gold);
  padding: 0 0.04em;
}
.srp-hero-deck {
  font-family: var(--sans); font-weight: 300;
  font-size: 17px; line-height: 1.5; color: var(--bone-dim);
  max-width: 540px; margin: 0;
}

/* Hero stats panel (right column) */
.srp-stats {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 32px 40px;
  border-left: 1px solid var(--line);
  padding: 6px 0 6px 56px;
}
.srp-stat-label {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1); margin-bottom: 10px;
}
.srp-stat-value {
  font-family: var(--serif); font-size: 56px; font-weight: 400;
  letter-spacing: -0.025em; line-height: 0.9;
  color: var(--bone);
}
.srp-stat-value .pct,
.srp-stat-value .of {
  font-family: var(--mono); font-size: 14px;
  letter-spacing: 0.04em; color: var(--gray-1);
  margin-left: 4px; vertical-align: top;
}
.srp-stat-value.is-red  { color: var(--red); }
.srp-stat-value.is-gold { color: var(--gold); }
.srp-stat-meta {
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase;
  color: var(--gray-2); margin-top: 6px;
}

/* ---------- SECTION HEADERS (filter + grid) ---------- */
.srp-section-head {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 0 0 22px;
}
.srp-section-eyebrow {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: var(--red);
}
.srp-section-title {
  font-family: var(--serif); font-size: 30px; font-weight: 400;
  letter-spacing: -0.01em; color: var(--bone); margin: 6px 0 0;
}
.srp-section-title .ital { font-style: italic; }
.srp-section-counter {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-1);
}
.srp-section-counter strong { color: var(--bone); font-weight: 500; }

/* ---------- FILTER BAR ---------- */
.srp-filter-card {
  padding: 22px 26px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg-glass);
  margin-bottom: 14px;
}
.srp-filter-card [data-testid="stTextInput"] input,
.srp-filter-card [data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: rgba(255,255,255,0.025) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  color: var(--bone) !important;
  font-family: var(--sans) !important;
  font-size: 13px !important;
}
.srp-filter-card [data-testid="stTextInput"] input:focus {
  border-color: rgba(232,193,112,0.45) !important;
  box-shadow: 0 0 0 3px rgba(232,193,112,0.10) !important;
}
.srp-filter-card label, .srp-filter-card label p {
  font-family: var(--mono) !important;
  font-size: 9.5px !important;
  letter-spacing: 0.22em !important;
  color: var(--gray-1) !important;
  text-transform: uppercase !important;
  font-weight: 500 !important;
}

/* ---------- CARDS ---------- */
.srp-card {
  border: 1px solid var(--line); border-radius: var(--radius);
  background:
    radial-gradient(140% 90% at 0% 0%, rgba(230,69,48,0.04), transparent 60%),
    var(--bg-glass);
  padding: 24px 26px 22px;
  position: relative;
  margin-bottom: 14px;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.srp-card:hover {
  transform: translateY(-2px);
  border-color: var(--line-hi);
  box-shadow: 0 14px 40px rgba(0,0,0,0.45);
}
.srp-card-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 16px; margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}
.srp-card-num {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.20em; color: var(--red);
  padding: 5px 11px;
  border: 1px solid rgba(230,69,48,0.32);
  border-radius: 100px;
  background: var(--red-soft);
  text-transform: uppercase;
}
.srp-card-date {
  font-family: var(--mono); font-size: 10.5px;
  letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--gray-1);
}
.srp-card-body {
  display: grid; grid-template-columns: 130px 1fr; gap: 32px;
  align-items: center;
  margin-bottom: 18px;
}
.srp-card-score-wrap {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center;
}
.srp-card-score {
  font-family: var(--serif); font-size: 84px; font-weight: 400;
  line-height: 0.85; letter-spacing: -0.04em;
  color: var(--bone);
}
.srp-card-score .pct {
  font-family: var(--mono); font-size: 14px;
  letter-spacing: 0.04em; color: var(--gray-1);
  vertical-align: top; margin-left: 2px;
}
.srp-card-score-label {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--gray-1); margin-top: 10px;
}
.srp-card-info {
  display: grid; gap: 14px;
}
.srp-info-row {
  display: grid; grid-template-columns: 86px 1fr;
  align-items: baseline;
  gap: 18px;
}
.srp-info-label {
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: 0.20em; color: var(--gray-1);
  text-transform: uppercase;
}
.srp-info-value {
  font-family: var(--serif); font-size: 22px; font-style: italic;
  font-weight: 400; color: var(--bone); line-height: 1.05;
}
.srp-info-value.is-focus {
  font-family: var(--sans); font-style: normal;
  font-size: 14px; font-weight: 500;
  color: var(--bone-dim); line-height: 1.4;
}
.srp-info-value.is-file {
  font-family: var(--mono); font-style: normal;
  font-size: 11.5px; color: var(--gray-1);
  letter-spacing: 0.02em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.srp-card-focus-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 4px 11px;
  border-radius: 100px;
  background: rgba(74,227,140,0.10);
  border: 1px solid rgba(74,227,140,0.30);
  color: var(--green);
  font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.10em; text-transform: uppercase;
  white-space: nowrap;
}
.srp-card-focus-pill.is-red {
  background: var(--red-soft);
  border-color: rgba(230,69,48,0.30);
  color: var(--red);
}
.srp-card-focus-pill.is-gold {
  background: var(--gold-soft);
  border-color: rgba(232,193,112,0.30);
  color: var(--gold);
}

/* Action row styling — the Open Report button below the card */
.srp-card-actions {
  display: flex; justify-content: flex-end;
  margin-top: 8px;
}
/* Open Report buttons — keyed selector so styles actually apply.
   The key pattern is srpv_open_<id>; we target the prefix using
   attribute-starts-with matching on the .st-key-* class via [class*=].
*/
[class*="st-key-srpv_open_"] button {
  background: var(--bone) !important;
  color: var(--bg) !important;
  border: 1px solid var(--bone) !important;
  border-radius: 100px !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase !important;
  padding: 10px 22px !important;
  width: auto !important;
  min-height: 0 !important;
  box-shadow: none !important;
  transition: background 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease !important;
}
[class*="st-key-srpv_open_"] button:hover {
  background: #FFFFFF !important;
  border-color: #FFFFFF !important;
  box-shadow: 0 0 28px -8px rgba(244,239,230,0.55) !important;
  transform: translateY(-1px);
}

/* ---------- EMPTY STATE ---------- */
.srp-empty {
  padding: 88px 36px;
  text-align: center;
  border: 1px dashed var(--line-hi);
  border-radius: var(--radius);
  background: var(--bg-glass);
}
.srp-empty-icon {
  font-family: var(--serif); font-size: 56px; font-style: italic;
  color: var(--gold); opacity: 0.75; margin-bottom: 14px;
  line-height: 1;
}
.srp-empty-title {
  font-family: var(--serif); font-size: 30px; font-weight: 400;
  font-style: italic; color: var(--bone); margin-bottom: 12px;
}
.srp-empty-body {
  font-family: var(--sans); font-size: 14px; color: var(--bone-dim);
  line-height: 1.6; max-width: 460px; margin: 0 auto;
}

/* ---------- PREVIEW NOTICE BANNER ---------- */
.srp-preview-banner {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 22px; margin: 0 0 32px;
  background: rgba(232,193,112,0.06);
  border: 1px solid rgba(232,193,112,0.22);
  border-radius: var(--radius-sm);
}
.srp-preview-banner-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--gold);
  box-shadow: 0 0 12px var(--gold);
}
.srp-preview-banner-text {
  font-family: var(--mono); font-size: 11px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--gold);
}
.srp-preview-banner-text .em {
  font-family: var(--serif); font-style: italic;
  font-size: 13px; text-transform: none;
  letter-spacing: 0; color: var(--bone-dim);
  margin-left: 8px;
}

/* ---------- RESPONSIVE ---------- */
@media (max-width: 1100px) {
  .srp-hero { grid-template-columns: 1fr; gap: 36px; }
  .srp-stats { border-left: none; padding-left: 0; border-top: 1px solid var(--line); padding-top: 32px; }
  .srp-hero-headline { font-size: 64px; }
}
@media (max-width: 760px) {
  .srp-hero-headline { font-size: 48px; }
  .srp-issue-line { font-size: 9.5px; gap: 12px; flex-wrap: wrap; }
  .srp-card-body { grid-template-columns: 1fr; gap: 20px; }
  .srp-card-score-wrap { align-items: flex-start; }
  .srp-stats { grid-template-columns: 1fr; gap: 20px; }
  .srp-stat-value { font-size: 44px; }
  .srp-info-row { grid-template-columns: 80px 1fr; gap: 12px; }
  .srp-section-head { flex-direction: column; align-items: flex-start; gap: 8px; }
}
</style>
"""


# =====================================================================
#  Helpers — operate on real records returned by load_swing_history
# =====================================================================
def _fmt_short_date(rec: Dict[str, Any]) -> str:
    for key in ("timestamp", "created_at", "date"):
        v = rec.get(key)
        if not v:
            continue
        if isinstance(v, datetime):
            return v.strftime("%b %d · %Y")
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).strftime("%b %d · %Y")
            except Exception:
                return v[:10]
    return "—"


def _top_focus(rec: Dict[str, Any]) -> str:
    narratives = rec.get("narratives") or []
    if narratives and isinstance(narratives, list):
        n0 = narratives[0]
        if isinstance(n0, dict):
            return str(n0.get("title", "Top fix")).strip() or "Top fix"
    drill_plan = rec.get("drill_plan") or {}
    if isinstance(drill_plan, dict) and drill_plan:
        first_cat = next(iter(drill_plan.keys()))
        return str(first_cat).replace("_", " ").title()
    return "Mechanics review"


def _focus_pill_cls(focus: str) -> str:
    f = (focus or "").lower()
    if any(k in f for k in ("elite", "strong", "excellent", "great", "best")):
        return "is-gold"
    if any(k in f for k in ("urgent", "critical", "fix", "issue")):
        return "is-red"
    return ""


def _safe_int(v, default=None):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


def _avg_score(history: List[Dict[str, Any]]) -> Optional[float]:
    vals = []
    for r in history or []:
        s = r.get("score")
        if s is None:
            continue
        try:
            vals.append(float(s))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return sum(vals) / len(vals)


def _best_score(history: List[Dict[str, Any]]) -> Optional[float]:
    vals = [float(r["score"]) for r in (history or []) if r.get("score") is not None]
    return max(vals) if vals else None


def _filter_history(history, q, score_range, time_range):
    from datetime import timedelta
    q = (q or "").strip().lower()
    cutoff = None
    now = datetime.now()
    if time_range == "Last 7 days":
        cutoff = now - timedelta(days=7)
    elif time_range == "Last 30 days":
        cutoff = now - timedelta(days=30)
    elif time_range == "Last 90 days":
        cutoff = now - timedelta(days=90)
    out = []
    for rec in history:
        if q:
            hay = " ".join([
                str(rec.get("reference_name") or ""),
                str(rec.get("filename") or ""),
                _top_focus(rec),
                str(rec.get("swing_number") or ""),
            ]).lower()
            if q not in hay:
                continue
        s = rec.get("score") or 0
        try:
            s = float(s)
        except (TypeError, ValueError):
            s = 0
        if score_range == "80+ (Elite)" and s < 80:
            continue
        if score_range == "60–79 (Strong)" and not (60 <= s < 80):
            continue
        if score_range == "Below 60 (Building)" and s >= 60:
            continue
        if cutoff is not None:
            try:
                ts = rec.get("timestamp") or rec.get("created_at")
                if ts is None:
                    continue
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = ts
                if dt.replace(tzinfo=None) < cutoff:
                    continue
            except Exception:
                continue
        out.append(rec)
    return out


def _synthetic_history() -> List[Dict[str, Any]]:
    """Return a small synthetic dataset for preview when no real data
    is available. Clearly labelled as 'PREVIEW SAMPLE DATA' on screen
    so the user doesn't mistake it for their own swings."""
    base = datetime.now()
    return [
        {
            "id": "preview-3", "swing_number": 7,
            "score": 78,
            "timestamp": base.replace(hour=14, minute=22).isoformat(),
            "reference_name": "Mookie Betts",
            "filename": "tournament_round_3.mp4",
            "narratives": [{"title": "Hip rotation locked in"}],
        },
        {
            "id": "preview-2", "swing_number": 6,
            "score": 72,
            "timestamp": (base.replace(day=max(1, base.day-3))).isoformat(),
            "reference_name": "Juan Soto",
            "filename": "cage_session_thursday.mp4",
            "narratives": [{"title": "Hip-shoulder separation timing"}],
        },
        {
            "id": "preview-1", "swing_number": 5,
            "score": 64,
            "timestamp": (base.replace(day=max(1, base.day-7))).isoformat(),
            "reference_name": "Yandy Diaz",
            "filename": "first_BP_after_clinic.mp4",
            "narratives": [{"title": "Head drift through contact"}],
        },
    ]


# =====================================================================
#  Main renderer
# =====================================================================
def render_saved_reports_preview(user: Optional[Dict[str, Any]] = None) -> None:
    """Phase 1 preview-only Saved Reports page. Reachable at
    /?page=saved_reports_preview. No production behavior change."""
    render_edge_masthead(user or {}, active_page="saved_reports")
    render_edge_page_wrapper_open()
    st.markdown(_EDGE_TOKENS_CSS, unsafe_allow_html=True)
    st.markdown(_SRPREVIEW_CSS, unsafe_allow_html=True)

    # -- Issue line -----------------------------------------------------
    today = datetime.now().strftime("%A · %B %-d · %Y")
    player_name = (user or {}).get("name") or (user or {}).get("email") or "Player"
    handed = (user or {}).get("handedness") or "Right-handed"
    st.markdown(
        f"""
        <div class="srp-issue-line">
          <span>Volume IV · Issue 24</span>
          <span class="center">Sessions Archive · {html.escape(str(player_name))} · {html.escape(handed)}</span>
          <span class="right">{html.escape(today)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Load data ------------------------------------------------------
    player_id = (user or {}).get("slug") or (user or {}).get("id")
    history: List[Dict[str, Any]] = []
    is_sample = False
    if player_id and load_swing_history is not None:
        try:
            history = load_swing_history(player_id) or []
        except Exception:
            history = []
    if not history:
        history = _synthetic_history()
        is_sample = True

    # Newest first for display
    history_sorted = list(reversed(history))

    # -- Hero -----------------------------------------------------------
    total = len(history_sorted)
    avg = _avg_score(history_sorted)
    best = _best_score(history_sorted)
    streak = ((user or {}).get("gamification") or {}).get("current_streak_days") or 17

    st.markdown(
        f"""
        <section class="srp-hero">
          <div>
            <div class="srp-hero-eyebrow">
              <span class="swatch"></span>SESSIONS · COMPLETE ARCHIVE
            </div>
            <h1 class="srp-hero-headline">
              Every swing.<br>
              <span class="ital">One record book.</span>
            </h1>
            <p class="srp-hero-deck">
              Browse every analyzed swing, compare to past sessions, and
              re-open any report. Filter by score band, MLB comp, or
              date range. Open Report routes to the redesigned premium
              individual report page.
            </p>
          </div>
          <div class="srp-stats">
            <div>
              <div class="srp-stat-label">TOTAL SWINGS</div>
              <div class="srp-stat-value">{total}</div>
              <div class="srp-stat-meta">In your archive</div>
            </div>
            <div>
              <div class="srp-stat-label">AVERAGE SCORE</div>
              <div class="srp-stat-value">{_safe_int(avg) if avg is not None else '—'}<span class="of">/100</span></div>
              <div class="srp-stat-meta">Across all sessions</div>
            </div>
            <div>
              <div class="srp-stat-label">PERSONAL BEST</div>
              <div class="srp-stat-value is-gold">{_safe_int(best) if best is not None else '—'}<span class="of">/100</span></div>
              <div class="srp-stat-meta">Highest Edge score</div>
            </div>
            <div>
              <div class="srp-stat-label">CURRENT STREAK</div>
              <div class="srp-stat-value is-red">{streak}<span class="of">d</span></div>
              <div class="srp-stat-meta">Days analyzing</div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    # Preview-mode banner (only shown when previewing synthetic data)
    if is_sample:
        st.markdown(
            """
            <div class="srp-preview-banner">
              <div class="srp-preview-banner-dot"></div>
              <div class="srp-preview-banner-text">
                PREVIEW · SAMPLE DATA
                <span class="em">
                  Showing 3 example swings so the design is visible
                  before you upload your first clip. Your real history
                  will replace this once it loads.
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -- Section head: filter ------------------------------------------
    st.markdown(
        f"""
        <div class="srp-section-head">
          <div>
            <div class="srp-section-eyebrow">FILTER · SEARCH</div>
            <h2 class="srp-section-title">Find <span class="ital">a session.</span></h2>
          </div>
          <div class="srp-section-counter">
            SHOWING <strong>{total}</strong> OF <strong>{total}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Filter controls (Streamlit native, styled by .srp-filter-card)
    st.markdown('<div class="srp-filter-card">', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([2.4, 1, 1])
    with fc1:
        search_q = st.text_input(
            "Search reports",
            placeholder="Search by MLB comp, focus area, file name…",
            key="srpv_search",
        )
    with fc2:
        score_filter = st.selectbox(
            "Score band",
            ["All scores", "80+ (Elite)", "60–79 (Strong)", "Below 60 (Building)"],
            key="srpv_score",
        )
    with fc3:
        time_filter = st.selectbox(
            "Time range",
            ["All time", "Last 7 days", "Last 30 days", "Last 90 days"],
            key="srpv_time",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    filtered = _filter_history(history_sorted, search_q, score_filter, time_filter)

    if not filtered:
        st.markdown(
            """
            <div class="srp-empty">
              <div class="srp-empty-icon">◇</div>
              <div class="srp-empty-title">No sessions match those filters.</div>
              <div class="srp-empty-body">
                Try widening the score band, picking a longer time
                window, or clearing the search. Your full archive is
                still here — these filters are just a view on top.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_edge_page_wrapper_close()
        return

    # -- Section head: results -----------------------------------------
    st.markdown(
        f"""
        <div class="srp-section-head" style="margin-top: 8px;">
          <div>
            <div class="srp-section-eyebrow">ARCHIVE · ALL SWINGS</div>
            <h2 class="srp-section-title">
              <span class="ital">{len(filtered)}</span> session{"s" if len(filtered) != 1 else ""}
            </h2>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Cards ----------------------------------------------------------
    for idx, rec in enumerate(filtered):
        rec_id = rec.get("id") or rec.get("timestamp") or f"row{idx}"
        swing_num = rec.get("swing_number", "—")
        try:
            num_disp = f"SWING #{int(swing_num):02d}"
        except Exception:
            num_disp = f"SWING #{swing_num}"
        date_disp = _fmt_short_date(rec)
        score = rec.get("score")
        try:
            score_disp = f"{int(round(float(score)))}"
        except (TypeError, ValueError):
            score_disp = "—"
        ref = str(rec.get("reference_name") or "—")
        focus = _top_focus(rec)
        filename = str(rec.get("filename") or "—")
        pill_cls = _focus_pill_cls(focus)

        # Card body (visual only)
        st.markdown(
            f"""
            <div class="srp-card">
              <div class="srp-card-head">
                <span class="srp-card-num">{html.escape(num_disp)}</span>
                <span class="srp-card-date">{html.escape(date_disp)}</span>
              </div>
              <div class="srp-card-body">
                <div class="srp-card-score-wrap">
                  <div class="srp-card-score">{score_disp}<span class="pct">/100</span></div>
                  <div class="srp-card-score-label">Edge Score</div>
                </div>
                <div class="srp-card-info">
                  <div class="srp-info-row">
                    <span class="srp-info-label">MLB COMP</span>
                    <span class="srp-info-value">{html.escape(ref)}</span>
                  </div>
                  <div class="srp-info-row">
                    <span class="srp-info-label">FOCUS</span>
                    <span>
                      <span class="srp-card-focus-pill {pill_cls}">
                        {html.escape(focus)}
                      </span>
                    </span>
                  </div>
                  <div class="srp-info-row">
                    <span class="srp-info-label">FILE</span>
                    <span class="srp-info-value is-file">{html.escape(filename)}</span>
                  </div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Streamlit-native action row (Open Report)
        ac_l, ac_r = st.columns([4, 1])
        with ac_r:
            st.markdown('<div class="srp-open-btn">', unsafe_allow_html=True)
            if st.button(
                "Open Report →",
                key=f"srpv_open_{rec_id}",
            ):
                # Preview-only: stash the chosen record and route to the
                # swing_report_preview page. NO production routing change.
                st.session_state["preview_swing_record"] = rec
                st.session_state["preview_swing_record_id"] = str(rec_id)
                st.session_state["page"] = "swing_report_preview"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    render_edge_page_wrapper_close()
