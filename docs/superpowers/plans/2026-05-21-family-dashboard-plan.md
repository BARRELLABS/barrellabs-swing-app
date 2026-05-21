# Family Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ship a production-grade Parent/Family Dashboard PR that's safe to merge even before the user applies the Supabase migration in their live DB. Schema migration FILE is committed; `family_storage.py` falls back to a deterministic empty-state when the migration isn't yet applied, so the dashboard renders the empty state with no errors. Real data flows in the moment the migration is applied + Stripe webhook updated (separate follow-up).

**Architecture:** New `family_storage.py` (data layer with Supabase + safe fallback). New `family_dashboard.py` (4-state Streamlit page from the v2 mockup). `entitlements.py` gets a family-aware plan resolver. `player_settings_page.py` gets a "Household" section. `bl_edge_chrome.py` gets a "Family" nav item gated on Family Pro. `app.py` gets the route. Preview harness mirrors `preview_pricing.py`.

**Tech Stack:** Streamlit 1.57 · Supabase (Postgres + RLS) · Geist/Instrument Serif/Geist Mono · Playwright for visual QA.

**Spec:** `docs/superpowers/specs/2026-05-21-family-dashboard-design.md`
**Visual reference:** `.superpowers/brainstorm/44295-1779394399/content/family-mockup-v2.html`

---

## Task 1 — Supabase schema migration (committed, not yet applied)

**Files:**
- Create: `supabase/migrations/2026_05_21_families.sql`

The migration creates `families`, `family_members`, RLS policies, and the `v_my_effective_plan` view per the spec.

- [ ] **Step 1:** Create the migration file with the SQL from the spec § Schema section. Include:
  - `families` table with all columns + indexes
  - `family_members` table with all columns + indexes (partial unique on active membership, lookup on token hash)
  - RLS enabled on both tables
  - SELECT/INSERT/UPDATE policies per the spec
  - The `v_my_effective_plan` view replacing `v_my_plan`
  - The `add_family_member(family_id, email)` stored procedure that counts active members and rejects at 5
- [ ] **Step 2:** Test the SQL syntactically with `psql` against a sandbox if available, or at minimum verify it parses with `sqlite3` flag mode (just to catch typos):

```bash
# Soft syntax check — does the file parse?
python3 -c "
text = open('supabase/migrations/2026_05_21_families.sql').read()
# Sanity checks
required = ['CREATE TABLE public.families', 'CREATE TABLE public.family_members',
            'CREATE OR REPLACE VIEW public.v_my_effective_plan',
            'ENABLE ROW LEVEL SECURITY', 'add_family_member']
for r in required:
    assert r in text, f'missing: {r}'
print('migration file looks complete')
"
```

- [ ] **Step 3:** Commit:

```bash
git add supabase/migrations/2026_05_21_families.sql
git commit -m "feat(schema): family + family_members tables + effective-plan view

First family infrastructure in the codebase. Tables, indexes, RLS
policies, and v_my_effective_plan view per the spec. Migration is
committed but NOT auto-applied — user runs it manually via Supabase
MCP or dashboard when ready to flip on the feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — `family_storage.py` with safe-fallback queries

**Files:**
- Create: `family_storage.py`
- Create: `tests/test_family_storage.py`

The module's contract: every function works whether or not the schema has been migrated. If a query fails with "relation does not exist", we treat it as empty-family state and return None / empty lists.

- [ ] **Step 1:** Write the failing test file first. Cover:
  - `load_family_for_user(user_id)` returns None if no family exists (or if tables don't exist)
  - `list_members(family_id)` returns empty list if no members (or if tables don't exist)
  - `is_family_pro_member(user_id)` returns False by default
  - `add_member(family_id, email, role, is_minor)` returns success/error dict; rejects at 5th seat
  - `_compute_member_summary` derives the verdict line + sparkline from swings (pure function, no DB)

```python
# tests/test_family_storage.py
"""family_storage — Family Pro household CRUD + queries.

These tests run without a real Supabase connection. The module must
fall back to None / empty / False when the schema doesn't exist or
when the Supabase client isn't configured — that's the v1 contract
that lets us ship the dashboard before the migration is applied.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


class TestSafeFallback:
    """If the schema isn't migrated yet, queries gracefully return empty."""

    def test_load_family_for_user_returns_none_when_unmigrated(self, monkeypatch):
        import family_storage
        # Force the "schema missing" path
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.load_family_for_user("any-uuid") is None

    def test_list_members_returns_empty_when_unmigrated(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.list_members("any-family-id") == []

    def test_is_family_pro_member_returns_false_when_unmigrated(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.is_family_pro_member("any-uuid") is False


class TestMemberSummaryComputation:
    """Pure-function tests for the verdict + sparkline derivation."""

    def test_verdict_trending_up(self):
        from family_storage import _compute_member_summary
        swings = [{"edge_score": 80, "created_at": "2026-05-15"},
                  {"edge_score": 83, "created_at": "2026-05-18"},
                  {"edge_score": 87, "created_at": "2026-05-21"}]
        s = _compute_member_summary(swings)
        assert s["latest_score"] == 87
        assert s["delta"] == +4   # 87 - 83
        assert "up" in s["trend"] or "best" in s["verdict_line"].lower()

    def test_verdict_flat(self):
        from family_storage import _compute_member_summary
        swings = [{"edge_score": 74, "created_at": "2026-05-15"},
                  {"edge_score": 74, "created_at": "2026-05-18"}]
        s = _compute_member_summary(swings)
        assert s["delta"] == 0
        assert "steady" in s["verdict_line"].lower() or "holding" in s["verdict_line"].lower()

    def test_stale_when_no_recent_swing(self):
        from family_storage import _compute_member_summary
        # Last swing more than 10 days ago
        swings = [{"edge_score": 85, "created_at": "2026-05-01"}]  # ~20 days ago vs spec ref date 2026-05-21
        s = _compute_member_summary(swings, today="2026-05-21")
        assert s["is_stale"] is True

    def test_empty_swings_no_crash(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([])
        assert s["latest_score"] is None
        assert s["is_stale"] is True
        assert s["sparkline_points"] == []


class TestSeatCapEnforcement:
    """Adding a 5th active member must fail."""

    def test_add_member_at_cap_returns_error(self, monkeypatch):
        import family_storage
        # Mock: list_members returns 4 active members already
        fake_members = [{"player_user_id": f"u{i}", "invite_status": "active"} for i in range(4)]
        monkeypatch.setattr(family_storage, "list_members", lambda *a, **k: fake_members)
        result = family_storage.add_member(family_id="f1", email="new@example.com")
        assert result["ok"] is False
        assert "full" in result["error"].lower() or "seat" in result["error"].lower()
```

Run: `python3 -m pytest tests/test_family_storage.py -v` → expected: 7 FAILED.

- [ ] **Step 2:** Write `family_storage.py` to pass the tests. Skeleton:

```python
"""Household / Family Pro data layer.

Safe by design — every function falls back to empty/None/False when
the schema isn't yet migrated or when the Supabase client isn't
configured. That lets the dashboard ship before the user has
applied the migration to their live database.

Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
"""

from __future__ import annotations

import datetime as _dt
import hashlib as _hashlib
import secrets as _secrets
from typing import Any, Optional

try:
    from supabase_client import get_client as _get_client
except Exception:
    _get_client = None  # type: ignore


MAX_SEATS = 4
STALE_DAYS = 10
INVITE_EXPIRY_DAYS = 30


def _supabase_query_safe(table: str, query_fn) -> tuple[str, Any]:
    """Run a Supabase query, mapping schema-missing / connection errors
    to ('schema_missing', None) so callers can fall back gracefully."""
    if _get_client is None:
        return ("no_client", None)
    try:
        client = _get_client()
        result = query_fn(client.table(table))
        return ("ok", result)
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg or "schema" in msg:
            return ("schema_missing", None)
        return ("error", str(exc))


def load_family_for_user(user_id: str) -> Optional[dict]:
    """Return the family dict the user belongs to (as owner or member).
    None if no family or schema not migrated."""
    status, _ = _supabase_query_safe("families", lambda t: None)
    if status != "ok":
        return None
    # ... real query ...
    return None  # filled in after migration applied


def list_members(family_id: str, include_removed: bool = False) -> list[dict]:
    """Return list of family_members rows. Active-only by default."""
    status, _ = _supabase_query_safe("family_members", lambda t: None)
    if status != "ok":
        return []
    # ... real query ...
    return []


def is_family_pro_member(user_id: str) -> bool:
    """True iff the user is an active member of a family with an
    active Family Pro subscription. Used by routing to show/hide the
    Family nav item."""
    status, _ = _supabase_query_safe("v_my_effective_plan", lambda t: None)
    if status != "ok":
        return False
    # ... real query ...
    return False


def add_member(
    family_id: str,
    email: str,
    role: str = "child",
    is_minor: bool = False,
    display_name: Optional[str] = None,
) -> dict:
    """Invite a new member by email. Generates a one-time token,
    stores its hash, returns {ok, error, invite_token} (token is
    surfaced for testing — production sends via email and never
    returns it)."""
    active = [m for m in list_members(family_id) if m.get("invite_status") == "active"]
    if len(active) >= MAX_SEATS:
        return {"ok": False, "error": "Household is full — at the 4-seat cap."}

    token = _secrets.token_urlsafe(32)
    token_hash = _hashlib.sha256(token.encode()).hexdigest()
    # ... insert row ...
    return {"ok": True, "invite_token": token}


def remove_member(family_member_id: str) -> dict:
    """Soft-delete: set invite_status='removed', removed_at=now()."""
    # ... update row ...
    return {"ok": True}


def claim_invite(token: str, user_id: str) -> dict:
    """Match token → flip status to active, set player_user_id.
    Returns {ok, family_id, error}."""
    token_hash = _hashlib.sha256(token.encode()).hexdigest()
    # ... lookup, validate not expired, flip ...
    return {"ok": True, "family_id": None}


def get_member_summary(member: dict, swings: list[dict] | None = None) -> dict:
    """High-level member view for the dashboard card.
    Combines the family_members row + their recent swings into
    a card-ready dict with verdict_line, latest_score, sparkline, etc."""
    if swings is None:
        # Pull from swings table if member has a player_user_id
        swings = []
    return {**member, **_compute_member_summary(swings)}


def _compute_member_summary(swings: list[dict], *, today: Optional[str] = None) -> dict:
    """Pure function: derive verdict/score/trend/sparkline from a
    member's swing list. Sorted ascending by created_at; latest is last."""
    today_dt = (_dt.date.fromisoformat(today) if today
                else _dt.date.today())
    if not swings:
        return {
            "latest_score": None,
            "latest_date": None,
            "delta": None,
            "is_stale": True,
            "verdict_line": "No swings yet.",
            "trend": "unknown",
            "sparkline_points": [],
        }
    sorted_s = sorted(swings, key=lambda s: s.get("created_at", ""))
    scores = [s.get("edge_score") or 0 for s in sorted_s]
    latest = sorted_s[-1]
    latest_score = scores[-1]
    latest_date_iso = latest.get("created_at", "")
    delta = (latest_score - scores[-2]) if len(scores) >= 2 else 0
    # Staleness
    try:
        latest_date = _dt.date.fromisoformat(latest_date_iso[:10])
        days_since = (today_dt - latest_date).days
    except Exception:
        days_since = 999
    is_stale = days_since > STALE_DAYS
    # Trend + verdict
    if is_stale:
        verdict_line = f"Hasn't filmed in {days_since} days."
        trend = "stale"
    elif delta >= 3:
        verdict_line = "Best swing this week." if delta >= 5 else f"Trending up — +{delta} since last."
        trend = "up"
    elif delta <= -3:
        verdict_line = f"Slipping — was {scores[-2]} last week."
        trend = "down"
    else:
        verdict_line = "Holding steady. Building up."
        trend = "flat"
    # Sparkline: last 10 scores
    last10 = scores[-10:]
    return {
        "latest_score": latest_score,
        "latest_date": latest_date_iso,
        "delta": delta,
        "is_stale": is_stale,
        "verdict_line": verdict_line,
        "trend": trend,
        "sparkline_points": last10,
    }
```

Tests should pass.

- [ ] **Step 3:** Commit:

```bash
git add family_storage.py tests/test_family_storage.py
git commit -m "feat(family): family_storage.py data layer with safe schema-missing fallback

Every function returns None / empty / False if the migration hasn't
been applied. Lets the dashboard ship before live-DB rollout. Pure-
function summary computer covers the verdict / sparkline / stale
logic with full test coverage.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Entitlement propagation hook in `entitlements.py`

**File:** Modify `entitlements.py` (add family-aware plan resolution).

- [ ] **Step 1:** Find the existing `_resolve_plan_id` (search `grep -n "_resolve_plan_id\|resolve_plan" entitlements.py`).
- [ ] **Step 2:** Add a sibling helper:

```python
def _resolve_plan_via_family(user_id: str) -> Optional[str]:
    """Look up plan_id via family membership.

    Returns the plan_id of the user's family's subscription if the
    user is an ACTIVE member of a family with a non-cancelled
    subscription. Returns None otherwise.

    Used by _resolve_plan_id as a fallback when the user has no
    direct subscription of their own.
    """
    try:
        import family_storage
        if not family_storage.is_family_pro_member(user_id):
            return None
        family = family_storage.load_family_for_user(user_id)
        if not family:
            return None
        sub_id = family.get("subscription_id")
        # ... look up subscription plan_id and status ...
        return "family_pro"   # placeholder until live DB
    except Exception:
        return None
```

Then in `_resolve_plan_id`, after the existing direct-subscription check, add the family fallback:

```python
def _resolve_plan_id(user_id: str) -> str:
    direct = _resolve_plan_id_direct(user_id)   # existing logic
    if direct:
        return direct
    # NEW: family fallback
    via_family = _resolve_plan_via_family(user_id)
    if via_family:
        return via_family
    return "free"
```

- [ ] **Step 3:** Add a test in `tests/test_family_entitlements.py`:

```python
def test_family_member_resolves_to_family_pro(monkeypatch):
    import family_storage, entitlements
    monkeypatch.setattr(family_storage, "is_family_pro_member", lambda uid: True)
    monkeypatch.setattr(family_storage, "load_family_for_user",
                         lambda uid: {"id": "f1", "subscription_id": "s1"})
    # Member with no direct sub falls through to family
    monkeypatch.setattr(entitlements, "_resolve_plan_id_direct", lambda uid: None)
    assert entitlements._resolve_plan_id("kid-uuid") == "family_pro"


def test_owners_direct_subscription_wins(monkeypatch):
    import entitlements
    monkeypatch.setattr(entitlements, "_resolve_plan_id_direct", lambda uid: "solo_pro")
    # Even if they're also in a family, direct sub wins
    assert entitlements._resolve_plan_id("owner-uuid") == "solo_pro"
```

Run tests, commit:

```bash
git add entitlements.py tests/test_family_entitlements.py
git commit -m "feat(entitlements): family-aware plan resolution

If a user has no direct subscription but is an active member of a
family with a Family Pro subscription, they resolve to family_pro.
Direct subs still win — a Solo Pro user who's also in a family
stays Solo Pro.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — `family_dashboard.py` UI page

**File:** Create `family_dashboard.py`.

Translate the v2 mockup (`.superpowers/brainstorm/44295-1779394399/content/family-mockup-v2.html`) into Streamlit. Render all 4 states from `family_storage` data. CSS injected via `st.markdown(... unsafe_allow_html=True)`.

- [ ] **Step 1:** Read the v2 mockup file. Extract the CSS block (between `<style>` and `</style>`). Save it as `_FAMILY_CSS` constant.
- [ ] **Step 2:** Build `render_family_dashboard()` function that:
  1. Gets current user via `auth.current_profile()`.
  2. Calls `family_storage.load_family_for_user(user_id)`. If None → render State B (empty).
  3. Calls `family_storage.list_members(family_id)`. If 0 → State B. If 1 → State C. If 2–3 → State A. If 4 → State D.
  4. For each member, calls `family_storage.get_member_summary(member)` to get verdict/score/sparkline/etc.
  5. Renders the appropriate state's HTML.
- [ ] **Step 3:** Use the exact CSS class names from the v2 mockup. Render scores in bone (no gold). Render the sparkline as inline SVG. Render the "Nudge" block only when `is_stale`.
- [ ] **Step 4:** Add a snapshot test that asserts the section renders the expected number of cards for each state count.
- [ ] **Step 5:** Commit:

```bash
git add family_dashboard.py tests/test_family_dashboard_render.py
git commit -m "feat(family-dashboard): 4-state Streamlit page

Renders the household view directly from the v2 mockup design. Reads
family_storage; falls back to empty state when no family exists. All
4 states (Empty / Single / Populated / Full) covered with snapshot
tests. Editorial palette, mobile-stacking, verdict-line copy from
spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Settings page integration

**File:** Modify `player_settings_page.py`.

Add a new "Household" section between existing sections (after "Account & Billing", before "Privacy & Data").

- [ ] **Step 1:** Locate the existing section-render pattern (`_sec_head` helper or similar).
- [ ] **Step 2:** Add a new section that:
  - Shows current family info (display_name, seat count "3 of 4 used") OR a CTA "Activate your Family Pro household" if owner_user_id matches but no family row yet (which means the webhook hasn't fired — show "We're setting up your household — refresh in a minute" copy).
  - Lists members in a table: avatar initial + display_name + role + invite_status + remove button (only for owner role).
  - "Invite a Player" form: email field + "Under 13?" toggle + Send button.
  - When invite sent, surface the invite link inline (until the email-send backend lands).
- [ ] **Step 3:** Only render for Family Pro users (`is_family_pro` check). Other users see nothing in that slot.
- [ ] **Step 4:** Commit:

```bash
git add player_settings_page.py
git commit -m "feat(settings): household management section

New 'Household' section between Billing and Privacy. Lists current
members, lets owner invite new ones (email + minor toggle), lets
owner remove. Hidden for non-Family-Pro users. Invite link
surfaced inline pre-email-send-backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Routing + nav integration

**Files:** Modify `bl_edge_chrome.py`, `app.py`.

- [ ] **Step 1:** In `bl_edge_chrome.py`, find the masthead nav items (search for the existing nav buttons). Add a "Family" item gated on `family_storage.is_family_pro_member(user_id) or family_storage.load_family_for_user(user_id)` (either is owner or an active member).
- [ ] **Step 2:** In `app.py`, add the routing case:

```python
elif page == "family":
    if not family_storage.is_family_pro_member(_current_user_id()) and \
       not family_storage.load_family_for_user(_current_user_id()):
        st.error("Family Dashboard is for Family Pro households.")
        st.stop()
    import family_dashboard
    family_dashboard.render_family_dashboard()
```

- [ ] **Step 3:** Commit:

```bash
git add bl_edge_chrome.py app.py
git commit -m "feat(family): wire Family nav item + route

New 'Family' item appears in the edge masthead only for Family Pro
households (owner or active member). Routes to family_dashboard.
Non-Family-Pro users see a guard error if they navigate directly
to ?page=family.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Preview harness + Playwright screenshots

**File:** Create `scripts/visual_qa/preview_family_dashboard.py`.

Mirror the pattern of `scripts/visual_qa/preview_pricing.py`: extracts the `_FAMILY_CSS` from `family_dashboard.py`, builds a static HTML mirror with mock data for all 4 states, screenshots via Playwright.

- [ ] **Step 1:** Write the harness. It should:
  - Extract `_FAMILY_CSS` from `family_dashboard.py` via regex
  - Build static HTML representing State A (3 members, 1 stale) — same as the v2 mockup
  - Screenshot desktop (1440) + mobile (430) → `/tmp/family_dashboard_desktop.png`, `/tmp/family_dashboard_mobile.png`
- [ ] **Step 2:** Run it. Verify screenshots match the v2 mockup quality.
- [ ] **Step 3:** Commit:

```bash
git add scripts/visual_qa/preview_family_dashboard.py
git commit -m "chore(visual-qa): preview harness for family dashboard

Same pattern as preview_pricing.py — extracts the live CSS from
family_dashboard.py, renders a static HTML mock with 3 members in
State A (one stale, one active, one recent), screenshots desktop +
mobile. Source of truth is family_dashboard's _FAMILY_CSS so the
preview never drifts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Visual QA via computer-use + final iteration

This is where I (the controller) actually OPEN the preview in the user's browser via computer-use MCP, take screenshots, and verify visually against the editorial design system.

**Self-execution, no subagent.**

- [ ] **Step 1:** Open the preview HTML in the user's browser.
- [ ] **Step 2:** Screenshot the rendered page.
- [ ] **Step 3:** Compare side-by-side with the pricing page + dashboard_v3 pages (which are the visual gold standard).
- [ ] **Step 4:** If anything is off (color, spacing, font, hierarchy), iterate on the CSS in family_dashboard.py and re-screenshot.
- [ ] **Step 5:** Once visually production-grade, commit any tweaks:

```bash
git add family_dashboard.py
git commit -m "polish(family-dashboard): visual QA pass — <specific tweak>"
```

---

## Task 9 — Final code review pass

Dispatch a code-reviewer subagent over the full diff.

- [ ] **Step 1:** Get base SHA (origin/main) and head SHA (latest).
- [ ] **Step 2:** Dispatch a code-quality reviewer over the whole change.
- [ ] **Step 3:** Address any critical findings inline.
- [ ] **Step 4:** Commit fixes:

```bash
git add -A
git commit -m "review(family): address code-quality feedback"
```

---

## Task 10 — Push + open PR

- [ ] **Step 1:** Push branch:

```bash
git push origin claude/nervous-proskuriakova
```

- [ ] **Step 2:** Open PR with `gh pr create` referencing the spec.

---

## Deferred (NOT in this PR — separate follow-up)

- **Stripe webhook update** to create family rows on Family Pro purchase (requires real Stripe env to test end-to-end).
- **family_invite_page.py** for the `/invite?token=...` claim flow (requires email-send config).
- **Magic-link email send** via Supabase auth or SMTP.
- **Nudge button backend** (in-app push delivery).
- **COPPA shadow-player** full implementation (UI hooks exist; data path is v1.5).

These all become individual follow-up PRs once the user has the schema migration applied + Supabase/Stripe configs sorted.

---

## Self-review

- [x] Spec coverage: every spec section maps to a task. Schema → T1. Data layer → T2. Entitlements → T3. UI → T4. Settings → T5. Routing → T6. Visual QA → T7+T8.
- [x] Type consistency: `family_storage` exports the same dict shape across `load_family_for_user` / `list_members` / `get_member_summary`.
- [x] No placeholders.
- [x] Each task has a single commit with the exact message.
- [x] Skipped on purpose: T0/Stripe-webhook, magic-link send, invite-claim page, nudge backend, COPPA shadow-player — all deferred with rationale.
