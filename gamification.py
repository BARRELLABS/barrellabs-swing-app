"""
BarrelLabs SwingAI — Gamification engine.

Pure-Python game-state module. Owns:

  • LEVELS, ACHIEVEMENTS, REWARDS  — constants
  • level_for_xp(total_xp)         — total xp -> (level_index, level_dict, next_level_dict_or_None)
  • compute_player_state(...)      — single function that derives the
                                     full progress snapshot from raw inputs
  • update_streak(persisted, ...)  — idempotent "one qualifying day per
                                     calendar date" streak update
  • check_streak_break(persisted)  — reset current_streak to 0 if stale
  • determine_achievements(state)  — returns the list of achievements the
                                     player has now unlocked
  • determine_rewards(state)       — returns the list of rewards the player
                                     can now claim/has unlocked
  • evaluate_progress(...)         — convenience wrapper that runs the
                                     whole pipeline and returns a dict the
                                     UI can render directly

Persistence concerns (Supabase, training_logs row) live in player_storage —
this module is pure and unit-testable in isolation.

The persisted gamification dict shape stored under
training_logs.drill_state._gamification:

    {
        "current_streak_days":   int,
        "longest_streak_days":   int,
        "last_qualifying_date":  "YYYY-MM-DD" or None,
        "achievements_unlocked": { achievement_id: "YYYY-MM-DD", ... },
        "rewards_unlocked":      { reward_id: "YYYY-MM-DD", ... },
        "rewards_claimed":       { reward_id: "YYYY-MM-DD", ... },
    }

Totals (xp, level, swings, drills, scores) are NEVER persisted — they're
always re-derived from raw history + drill meta on every load so a) the
client can't tamper with them and b) re-runs are always consistent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Optional


# --------------------------------------------------------------------
#  LEVELS
# --------------------------------------------------------------------
LEVELS = [
    {"id": "rookie",           "name": "Rookie",           "min_xp": 0,     "tagline": "Start of the journey"},
    {"id": "prospect",         "name": "Prospect",         "min_xp": 250,   "tagline": "Reps add up"},
    {"id": "all_star",         "name": "All-Star",         "min_xp": 1000,  "tagline": "Locked in"},
    {"id": "mvp",              "name": "MVP",              "min_xp": 2500,  "tagline": "Top of the lineup"},
    {"id": "elite_hitter",     "name": "Elite Hitter",     "min_xp": 5000,  "tagline": "Plus bat speed"},
    {"id": "barrel_scientist", "name": "Barrel Scientist", "min_xp": 10000, "tagline": "Mastery of mechanics"},
    {"id": "lab_legend",       "name": "Lab Legend",       "min_xp": 25000, "tagline": "BarrelLabs immortal"},
]


def level_for_xp(total_xp: int):
    """
    Return (index, level_dict, next_level_or_None) for a given total XP.
    Levels are inclusive at their min_xp boundary — i.e. exactly 250 XP
    promotes you to Prospect.
    """
    total_xp = max(0, int(total_xp or 0))
    current_idx = 0
    for i, lvl in enumerate(LEVELS):
        if total_xp >= lvl["min_xp"]:
            current_idx = i
    current = LEVELS[current_idx]
    nxt = LEVELS[current_idx + 1] if current_idx + 1 < len(LEVELS) else None
    return current_idx, current, nxt


def level_progress(total_xp: int) -> dict:
    """
    Return a UI-friendly snapshot of where the player sits inside their
    current level: { level, next, xp_in_level, xp_needed_for_next, pct }.
    Max level returns pct=1.0 and xp_needed_for_next=0.
    """
    total_xp = max(0, int(total_xp or 0))
    _, current, nxt = level_for_xp(total_xp)
    if nxt is None:
        return {
            "level": current,
            "next":  None,
            "xp_total": total_xp,
            "xp_in_level": total_xp - current["min_xp"],
            "xp_needed_for_next": 0,
            "pct": 1.0,
        }
    span = max(1, nxt["min_xp"] - current["min_xp"])
    xp_in_level = total_xp - current["min_xp"]
    xp_to_next = max(0, nxt["min_xp"] - total_xp)
    pct = max(0.0, min(1.0, xp_in_level / span))
    return {
        "level": current,
        "next":  nxt,
        "xp_total": total_xp,
        "xp_in_level": xp_in_level,
        "xp_needed_for_next": xp_to_next,
        "pct": pct,
    }


# --------------------------------------------------------------------
#  ACHIEVEMENTS
# --------------------------------------------------------------------
# Each achievement records:
#   id            stable key (also used as session-state suffix)
#   category      "swing" | "drill" | "score" | "streak"
#   title         display name
#   description   one-line description
#   target        numeric threshold
#   metric        which state field to compare to (set by category)
ACHIEVEMENTS = [
    # Swing milestones
    {"id": "swing_1",   "category": "swing", "title": "First Cut",          "description": "Upload your first swing.",         "target": 1},
    {"id": "swing_5",   "category": "swing", "title": "Quick Study",        "description": "Analyze 5 swings.",                "target": 5},
    {"id": "swing_10",  "category": "swing", "title": "Working Class Hitter","description": "Analyze 10 swings.",              "target": 10},
    {"id": "swing_25",  "category": "swing", "title": "Filmstudy",          "description": "Analyze 25 swings.",               "target": 25},
    {"id": "swing_50",  "category": "swing", "title": "Cage Rat",           "description": "Analyze 50 swings.",               "target": 50},
    {"id": "swing_100", "category": "swing", "title": "Lab Rat",            "description": "Analyze 100 swings.",              "target": 100},

    # Drill milestones
    {"id": "drill_1",   "category": "drill", "title": "First Reps",         "description": "Complete your first drill.",       "target": 1},
    {"id": "drill_10",  "category": "drill", "title": "Practice Pays",      "description": "Complete 10 drills.",              "target": 10},
    {"id": "drill_50",  "category": "drill", "title": "Drill Sergeant",     "description": "Complete 50 drills.",              "target": 50},
    {"id": "drill_100", "category": "drill", "title": "Workhorse",          "description": "Complete 100 drills.",             "target": 100},

    # Improvement
    {"id": "improve_10","category": "improvement", "title": "Big Jump",     "description": "Improve a swing score by 10+ over a previous swing.", "target": 10},

    # Best-score thresholds
    {"id": "best_70",   "category": "score", "title": "Got Plus Tools",     "description": "Hit a swing score of 70 or higher.","target": 70},
    {"id": "best_80",   "category": "score", "title": "Pro Material",       "description": "Hit a swing score of 80 or higher.","target": 80},
    {"id": "best_90",   "category": "score", "title": "Elite Hitter",       "description": "Hit a swing score of 90 or higher.","target": 90},

    # Streak milestones
    {"id": "streak_3",   "category": "streak", "title": "Spark",            "description": "3-day training streak.",           "target": 3},
    {"id": "streak_7",   "category": "streak", "title": "On Fire",          "description": "7-day training streak.",           "target": 7},
    {"id": "streak_30",  "category": "streak", "title": "Locked In",        "description": "30-day training streak.",          "target": 30},
    {"id": "streak_90",  "category": "streak", "title": "Quarter Master",   "description": "90-day training streak.",          "target": 90},
    {"id": "streak_365", "category": "streak", "title": "Year One",         "description": "365-day training streak.",         "target": 365},
]


def _metric_for_category(state: dict, category: str) -> int:
    """Which derived stat in `state` corresponds to a given achievement category."""
    if category == "swing":
        return int(state.get("total_swings") or 0)
    if category == "drill":
        return int(state.get("total_drills_completed") or 0)
    if category == "improvement":
        return int(state.get("max_score_improvement") or 0)
    if category == "score":
        return int(state.get("best_score") or 0)
    if category == "streak":
        # Achievements unlock against the longest streak the player has
        # ever held — so a 30-day badge stays earned even if the user's
        # current streak resets to 0.
        return int(state.get("longest_streak_days") or 0)
    return 0


def determine_achievements(state: dict) -> list:
    """
    Walk the ACHIEVEMENTS table and return the ids whose criteria the
    player currently meets. Sorted in the canonical ACHIEVEMENTS order.
    """
    earned = []
    for a in ACHIEVEMENTS:
        metric_val = _metric_for_category(state, a["category"])
        if metric_val >= a["target"]:
            earned.append(a["id"])
    return earned


# --------------------------------------------------------------------
#  REWARDS — gated by streak days
# --------------------------------------------------------------------
# Premium athlete loyalty progression. ALL rewards are DIGITAL \u2014 no physical
# fulfillment, no shipping, no inventory cost. The progression peaks with an
# animated "Legend" card at 180d and the Hall of Fame legacy status at 365d.
# (We deliberately avoid physical merch like patches/hoodies: zero capital
# tied up, instant delivery, and digital collectibles still feel earned.)
#
# `kind` drives the type-badge color in the UI:
#   status | collectible | graphic | report | title | perk | legacy
REWARDS = [
    {"id": "r_silver_badge",    "title": "Silver Streak Badge",                "kind": "status",      "day_threshold": 7,
     "description": "Your first week of consistency. Unlocks a premium profile badge."},
    {"id": "r_milestone_patch", "title": "Digital Milestone Patch",            "kind": "collectible", "day_threshold": 14,
     "description": "A collectible achievement patch pinned to your in-app trophy case. Collect the full set."},
    {"id": "r_player_card",     "title": "Personalized Player Card",           "kind": "graphic",     "day_threshold": 30,
     "description": "Custom baseball-card style graphic with your best score, MLB comp, and strengths \u2014 yours to share."},
    {"id": "r_progress_report", "title": "Elite Progress Report",              "kind": "report",      "day_threshold": 60,
     "description": "Professional development report summarizing strengths, weaknesses, and biggest improvements."},
    {"id": "r_locker_title",    "title": "Locker Room Title",                  "kind": "title",       "day_threshold": 90,
     "description": "Earn an elite title such as \u201cCertified Grinder,\u201d \u201cBarrel Hunter,\u201d or \u201cLab Veteran.\u201d"},
    {"id": "r_legend_card",     "title": "Animated Legend Card",               "kind": "graphic",     "day_threshold": 180,
     "description": "A rare animated version of your player card \u2014 six months of consistency, immortalized. Earned, never bought."},
    {"id": "r_priority_access", "title": "Founding Athlete Access",            "kind": "perk",        "day_threshold": 270,
     "description": "Early access to new BarrelLabs features before anyone else, plus a permanent Founding Athlete flair."},
    {"id": "r_hall_of_fame",    "title": "Hall of Fame Status",                "kind": "legacy",      "day_threshold": 365,
     "description": "Permanent recognition as one of BarrelLabs\u2019 most dedicated athletes."},
]


def determine_rewards(state: dict) -> list:
    """
    Return the list of reward ids whose day_threshold the player's
    LONGEST streak meets. Once unlocked, a reward stays unlocked even if
    the current streak resets.
    """
    longest = int(state.get("longest_streak_days") or 0)
    return [r["id"] for r in REWARDS if longest >= r["day_threshold"]]


def next_reward(state: dict) -> Optional[dict]:
    """Return the next reward the player has NOT yet unlocked, or None."""
    longest = int(state.get("longest_streak_days") or 0)
    for r in REWARDS:
        if longest < r["day_threshold"]:
            # Include a derived `days_remaining` so the UI doesn't have
            # to re-do the subtraction.
            return {**r, "days_remaining": r["day_threshold"] - longest}
    return None


def next_achievement(state: dict, earned_ids: Iterable[str]) -> Optional[dict]:
    """
    Return the achievement with the smallest remaining gap that the
    player has NOT yet earned. Helpful for "X away from..." motivation
    text in the UI.
    """
    earned_set = set(earned_ids or [])
    best = None
    best_gap = None
    for a in ACHIEVEMENTS:
        if a["id"] in earned_set:
            continue
        metric_val = _metric_for_category(state, a["category"])
        gap = max(0, a["target"] - metric_val)
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = {**a, "gap": gap, "current": metric_val}
    return best


# --------------------------------------------------------------------
#  STREAK
# --------------------------------------------------------------------
def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    """Lenient date parser — accepts 'YYYY-MM-DD' or ISO datetime."""
    if not s:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def empty_persisted() -> dict:
    """Default persisted gamification dict for a brand-new player."""
    return {
        "current_streak_days":   0,
        "longest_streak_days":   0,
        "last_qualifying_date":  None,
        "achievements_unlocked": {},
        "rewards_unlocked":      {},
        "rewards_claimed":       {},
    }


def _coerce_persisted(persisted: Optional[dict]) -> dict:
    """Merge incoming persisted dict over the defaults, never trusting it."""
    out = empty_persisted()
    if not isinstance(persisted, dict):
        return out
    for k in out.keys():
        if k in persisted and persisted[k] is not None:
            out[k] = persisted[k]
    # Type cleanup
    out["current_streak_days"] = int(out["current_streak_days"] or 0)
    out["longest_streak_days"] = int(out["longest_streak_days"] or 0)
    if not isinstance(out["achievements_unlocked"], dict):
        out["achievements_unlocked"] = {}
    if not isinstance(out["rewards_unlocked"], dict):
        out["rewards_unlocked"] = {}
    if not isinstance(out["rewards_claimed"], dict):
        out["rewards_claimed"] = {}
    return out


def check_streak_break(persisted: dict, today_iso: Optional[str] = None) -> dict:
    """
    If the user's last qualifying activity was BEFORE yesterday, their
    current streak is broken (current_streak_days -> 0). Longest streak
    is never touched. Returns the same dict (mutated for convenience).
    """
    persisted = _coerce_persisted(persisted)
    today = _parse_iso_date(today_iso) or date.today()
    last = _parse_iso_date(persisted.get("last_qualifying_date"))
    if last is None:
        # No activity ever — already at 0.
        persisted["current_streak_days"] = 0
        return persisted
    delta = (today - last).days
    if delta > 1:
        # Skipped at least one full calendar day → streak broken.
        persisted["current_streak_days"] = 0
    return persisted


def update_streak(persisted: dict, today_iso: Optional[str] = None) -> dict:
    """
    Record a qualifying activity for `today_iso` (defaults to today).

    Rules (anti-abuse: at most one streak bump per calendar date):
      • If last_qualifying_date == today                → no-op
      • If last_qualifying_date == today - 1 day        → current_streak += 1
      • Otherwise (None or older than yesterday)        → current_streak = 1
      • longest_streak = max(longest_streak, current_streak)
      • last_qualifying_date = today
    """
    persisted = _coerce_persisted(persisted)
    today = _parse_iso_date(today_iso) or date.today()
    last = _parse_iso_date(persisted.get("last_qualifying_date"))

    if last == today:
        # Already counted today — anti-abuse.
        return persisted

    if last is not None and (today - last).days == 1:
        persisted["current_streak_days"] = int(persisted["current_streak_days"] or 0) + 1
    else:
        persisted["current_streak_days"] = 1

    if persisted["current_streak_days"] > int(persisted["longest_streak_days"] or 0):
        persisted["longest_streak_days"] = persisted["current_streak_days"]

    persisted["last_qualifying_date"] = today.isoformat()
    return persisted


# --------------------------------------------------------------------
#  XP DERIVATION (from raw history + drill meta)
# --------------------------------------------------------------------
# Single source of truth for award amounts — keep this in lockstep with
# the "Your XP" tooltip in the Development Tracker UI.
XP_AWARDS = {
    "swing_upload":       25,
    "drill_complete":     10,
    "score_improve_5":    50,   # >= 5 pt jump vs immediate previous swing
    "score_improve_10":  100,   # >= 10 pt jump replaces (does not add to) the +50
    "personal_best":      75,   # a swing whose score strictly exceeds all earlier ones
    "streak_week":       150,   # awarded for every COMPLETED 7-day block of longest streak
    "achievement":        50,
}


def _scores_from_history(history) -> list:
    """Extract a list of (score, created_at_iso) tuples, oldest first."""
    out = []
    for rec in history or []:
        s = rec.get("score")
        if s is None:
            continue
        try:
            out.append((float(s), rec.get("created_at") or rec.get("timestamp") or ""))
        except Exception:
            continue
    return out


def _drill_completion_count(drill_meta_map: dict) -> int:
    """
    Sum of "True" entries inside every swing's `drills_completed` map.
    drill_meta_map is { swing_id: { drills_completed: {drill_name: bool} } }
    """
    if not isinstance(drill_meta_map, dict):
        return 0
    total = 0
    for _swing_id, meta in drill_meta_map.items():
        completed = (meta or {}).get("drills_completed") or {}
        for _drill_name, done in completed.items():
            if bool(done):
                total += 1
    return total


def _score_improvement_xp(scores) -> tuple:
    """
    For each consecutive (prev, cur) pair, award +50 for >=5 pt jump,
    or +100 for >=10 pt jump (mutually exclusive — bigger replaces
    smaller, not stacks).
    Returns (xp, max_improvement_seen).
    """
    if not scores or len(scores) < 2:
        return 0, 0
    xp = 0
    max_jump = 0
    prev = scores[0][0]
    for cur, _ in scores[1:]:
        jump = cur - prev
        if jump > max_jump:
            max_jump = int(jump)
        if jump >= 10:
            xp += XP_AWARDS["score_improve_10"]
        elif jump >= 5:
            xp += XP_AWARDS["score_improve_5"]
        prev = cur
    return xp, max_jump


def _personal_best_xp(scores) -> int:
    """+75 each time a swing sets a new ceiling vs every earlier swing."""
    if not scores:
        return 0
    xp = 0
    best_so_far = -1.0
    for s, _ in scores:
        if s > best_so_far:
            # The very first swing also counts as a "PB" — that feels
            # fair because it's the player's first ceiling.
            xp += XP_AWARDS["personal_best"]
            best_so_far = s
    return xp


def _streak_week_xp(longest_streak_days: int) -> int:
    """+150 per completed 7-day block within the player's longest streak."""
    return (int(longest_streak_days or 0) // 7) * XP_AWARDS["streak_week"]


# --------------------------------------------------------------------
#  MOTIVATIONAL COPY
# --------------------------------------------------------------------
def motivational_messages(state: dict, persisted: dict) -> list:
    """
    Return up to 3 short, plain-text motivational lines for the
    Development Tracker hero. The UI is free to pick & render however.
    """
    msgs = []

    # Streak alive
    cs = int(state.get("current_streak_days") or 0)
    if cs >= 2:
        msgs.append(f"Your {cs}-day streak is alive — keep it going.")
    elif cs == 1:
        msgs.append("Streak started — come back tomorrow to make it two.")

    # Next achievement teaser
    nxt_a = state.get("next_achievement")
    if nxt_a and nxt_a.get("gap"):
        gap = nxt_a["gap"]
        unit = {
            "swing": "swing" if gap == 1 else "swings",
            "drill": "drill" if gap == 1 else "drills",
            "score": "point" if gap == 1 else "points",
            "streak": "day" if gap == 1 else "days",
            "improvement": "point" if gap == 1 else "points",
        }.get(nxt_a.get("category"), "to go")
        msgs.append(f"{gap} {unit} away from unlocking {nxt_a['title']}.")

    # Next reward teaser
    nxt_r = state.get("next_reward")
    if nxt_r and nxt_r.get("days_remaining"):
        d = nxt_r["days_remaining"]
        msgs.append(f"{d} day{'s' if d != 1 else ''} until your {nxt_r['title']}.")

    # Level teaser
    lp = state.get("level_progress") or {}
    if lp.get("next") and lp.get("xp_needed_for_next"):
        xp_to = lp["xp_needed_for_next"]
        msgs.append(f"Only {xp_to} XP until {lp['next']['name']}.")

    return msgs[:3]


# --------------------------------------------------------------------
#  TOP-LEVEL EVALUATION
# --------------------------------------------------------------------
def compute_player_state(
    history: list,
    drill_meta_map: Optional[dict],
    persisted: Optional[dict],
    today_iso: Optional[str] = None,
) -> dict:
    """
    Pure derivation of the full progress snapshot from raw inputs.
    Does NOT mutate `persisted` (returns a coerced copy inside the
    `persisted` key for convenience).
    """
    persisted = _coerce_persisted(persisted)
    persisted = check_streak_break(dict(persisted), today_iso=today_iso)

    history = history or []
    drill_meta_map = drill_meta_map or {}

    scores = _scores_from_history(history)
    total_swings = len(history)
    total_drills_completed = _drill_completion_count(drill_meta_map)
    best_score = int(max((s for s, _ in scores), default=0))
    score_improve_xp, max_improvement = _score_improvement_xp(scores)
    pb_xp = _personal_best_xp(scores)
    streak_xp = _streak_week_xp(persisted.get("longest_streak_days") or 0)

    upload_xp = XP_AWARDS["swing_upload"] * total_swings
    drill_xp = XP_AWARDS["drill_complete"] * total_drills_completed

    # We need to determine achievements BEFORE we can know how much
    # achievement XP to award — but achievement determination only reads
    # the raw stats below, not XP, so there's no circular dependency.
    interim_for_ach = {
        "total_swings":            total_swings,
        "total_drills_completed":  total_drills_completed,
        "best_score":              best_score,
        "max_score_improvement":   max_improvement,
        "current_streak_days":     int(persisted.get("current_streak_days") or 0),
        "longest_streak_days":     int(persisted.get("longest_streak_days") or 0),
    }
    earned_ids = determine_achievements(interim_for_ach)
    ach_xp = XP_AWARDS["achievement"] * len(earned_ids)

    total_xp = upload_xp + drill_xp + score_improve_xp + pb_xp + streak_xp + ach_xp
    lp = level_progress(total_xp)

    interim_state = {
        **interim_for_ach,
        "total_xp":                total_xp,
        "level_progress":          lp,
        "xp_breakdown": {
            "swing_uploads":     upload_xp,
            "drill_completes":   drill_xp,
            "score_improvement": score_improve_xp,
            "personal_bests":    pb_xp,
            "streak_weeks":      streak_xp,
            "achievements":      ach_xp,
        },
        "achievements_earned":     earned_ids,
    }

    earned_reward_ids = determine_rewards(interim_state)
    interim_state["rewards_earned"] = earned_reward_ids

    interim_state["next_achievement"] = next_achievement(interim_state, earned_ids)
    interim_state["next_reward"]      = next_reward(interim_state)

    # Persist any new achievement/reward unlock dates (caller will write back).
    today_str = (_parse_iso_date(today_iso) or date.today()).isoformat()
    a_map = dict(persisted.get("achievements_unlocked") or {})
    for aid in earned_ids:
        a_map.setdefault(aid, today_str)
    persisted["achievements_unlocked"] = a_map

    r_map = dict(persisted.get("rewards_unlocked") or {})
    for rid in earned_reward_ids:
        r_map.setdefault(rid, today_str)
    persisted["rewards_unlocked"] = r_map

    interim_state["persisted"] = persisted
    interim_state["motivational_messages"] = motivational_messages(interim_state, persisted)

    return interim_state


# --------------------------------------------------------------------
#  LOOKUP HELPERS (for UI)
# --------------------------------------------------------------------
def achievement_by_id(aid: str) -> Optional[dict]:
    for a in ACHIEVEMENTS:
        if a["id"] == aid:
            return a
    return None


def reward_by_id(rid: str) -> Optional[dict]:
    for r in REWARDS:
        if r["id"] == rid:
            return r
    return None


__all__ = [
    "LEVELS",
    "ACHIEVEMENTS",
    "REWARDS",
    "XP_AWARDS",
    "level_for_xp",
    "level_progress",
    "determine_achievements",
    "determine_rewards",
    "next_achievement",
    "next_reward",
    "empty_persisted",
    "check_streak_break",
    "update_streak",
    "compute_player_state",
    "motivational_messages",
    "achievement_by_id",
    "reward_by_id",
]
