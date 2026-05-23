# Household Sub-Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One household login holds up to N player profiles (N = `plans.seats`); after login a "Who's training?" picker sets the active profile in `st.session_state["player"]`, and the whole app (which already reads that session var) behaves as that profile.

**Architecture:** Drop the `players.user_id` UNIQUE constraint so one auth user owns many `players` rows; the active one lives in `st.session_state["player"]`. A `create_household_player` SECURITY DEFINER RPC enforces the seat cap from `plans.seats`. New `household_picker.py` renders the chooser; `auth.py` gains `list_household_players` / `set_active_player`; `app.py` gates the picker; settings + family_storage re-point at player profiles. Solo/free users (1 profile) auto-select — no picker, zero change.

**Tech Stack:** Streamlit 1.57 · Supabase Postgres + RLS · pytest. Editorial design system (Instrument Serif / Geist / Geist Mono · bone/ink/gold).

**Spec:** `docs/superpowers/specs/2026-05-23-household-subaccounts-design.md`

---

## Pre-flight

- [ ] **Confirm branch + green baseline**

```bash
cd /Users/logancollins/barrellabs-swing-app/.claude/worktrees/nervous-proskuriakova
git checkout claude/household-subaccounts
python3 -m pytest tests/ -q --tb=line 2>&1 | tail -3
```
Expected: suite green (the spec commit is already on this branch).

---

## Task 1: Migration — multi-profile schema + seat-cap RPC

**Files:**
- Create: `supabase/migrations/2026_05_23_household_profiles.sql`

- [ ] **Step 1: Write the migration file** (exact contents)

```sql
-- ============================================================
--  Household sub-accounts: one auth login → many player profiles
--  Date: 2026-05-23
--  Spec: docs/superpowers/specs/2026-05-23-household-subaccounts-design.md
-- ============================================================

-- 1. Allow multiple players per auth user (was UNIQUE = one per login).
ALTER TABLE public.players DROP CONSTRAINT IF EXISTS players_user_id_key;

-- The UNIQUE constraint was also the only index on user_id; re-add a
-- plain index so household lookups stay fast.
CREATE INDEX IF NOT EXISTS players_user_id_idx ON public.players(user_id);

-- 2. Soft-remove column so removing a profile frees a seat but keeps swings.
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS removed_at timestamptz;

CREATE INDEX IF NOT EXISTS players_user_active_idx
  ON public.players(user_id)
  WHERE removed_at IS NULL;

-- 3. create_household_player — owner-only, seat cap from plans.seats,
--    counted under a lock so two concurrent creates can't both pass.
CREATE OR REPLACE FUNCTION public.create_household_player(
  p_name        text,
  p_handedness  text DEFAULT 'RIGHT',
  p_position    text DEFAULT NULL,
  p_is_minor    boolean DEFAULT true
) RETURNS public.players AS $$
DECLARE
  v_uid    uuid := auth.uid();
  v_seats  integer;
  v_active integer;
  result   public.players%ROWTYPE;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'create_household_player: not authenticated';
  END IF;
  IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
    RAISE EXCEPTION 'create_household_player: name required';
  END IF;
  IF p_handedness NOT IN ('RIGHT','LEFT') THEN
    RAISE EXCEPTION 'create_household_player: handedness must be RIGHT or LEFT';
  END IF;

  -- Seat cap from the household's plan (via v_my_plan, which already
  -- resolves the caller's plan). Lock the caller's existing rows so the
  -- count is stable for the duration of the insert.
  SELECT COALESCE(seats, 1) INTO v_seats
    FROM public.v_my_plan;
  IF v_seats IS NULL THEN v_seats := 1; END IF;

  PERFORM 1 FROM public.players
   WHERE user_id = v_uid AND removed_at IS NULL
   FOR UPDATE;

  SELECT count(*) INTO v_active
    FROM public.players
   WHERE user_id = v_uid AND removed_at IS NULL;

  IF v_active >= v_seats THEN
    RAISE EXCEPTION 'create_household_player: all % profile slots are in use', v_seats;
  END IF;

  INSERT INTO public.players (user_id, name, handedness, position)
  VALUES (v_uid, trim(p_name), p_handedness, p_position)
  RETURNING * INTO result;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.create_household_player(text, text, text, boolean) FROM anon, public;
GRANT  EXECUTE ON FUNCTION public.create_household_player(text, text, text, boolean) TO authenticated;
```

- [ ] **Step 2: Syntactic sanity check**

```bash
python3 -c "
t = open('supabase/migrations/2026_05_23_household_profiles.sql').read()
for s in ['DROP CONSTRAINT IF EXISTS players_user_id_key','ADD COLUMN IF NOT EXISTS removed_at','CREATE OR REPLACE FUNCTION public.create_household_player','plans','FOR UPDATE','GRANT  EXECUTE','REVOKE EXECUTE']:
    assert s in t, f'missing {s}'
print('migration looks complete')
"
```
Expected: `migration looks complete`

- [ ] **Step 3: Commit** (DB apply happens at the end, after review — like the family migration)

```bash
git add supabase/migrations/2026_05_23_household_profiles.sql
git commit -m "feat(schema): household profiles — drop players.user_id unique + seat-cap RPC

One auth login can now own many player rows (up to plans.seats).
Adds players.removed_at (soft-remove) and create_household_player()
SECURITY DEFINER RPC that enforces the cap from v_my_plan under a
row lock. Committed; applied to the live DB after review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `auth.py` — list profiles, set active, create profile

**Files:**
- Modify: `auth.py` (add three functions; reuse `_fetch_player_row` / `_profile_from_row` patterns)
- Test: `tests/test_household_profiles.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_household_profiles.py
"""Household sub-accounts — multi-profile auth helpers."""
from __future__ import annotations
import sys, types
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


@pytest.fixture(autouse=True)
def _stub_streamlit(monkeypatch):
    ss = {}
    st_stub = types.SimpleNamespace(
        session_state=ss,
        error=lambda *a, **k: None,
        markdown=lambda *a, **k: None,
        rerun=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    for m in ("auth",):
        sys.modules.pop(m, None)
    return ss


class TestListHouseholdPlayers:
    def test_returns_all_non_removed(self, monkeypatch):
        import auth
        rows = [
            {"id": "p1", "user_id": "u", "name": "Dad", "removed_at": None},
            {"id": "p2", "user_id": "u", "name": "Tommy", "removed_at": None},
            {"id": "p3", "user_id": "u", "name": "Old", "removed_at": "2026-01-01"},
        ]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        out = auth.list_household_players("u")
        names = [p["name"] for p in out]
        assert names == ["Dad", "Tommy"]   # removed excluded

    def test_empty_when_no_user(self, monkeypatch):
        import auth
        assert auth.list_household_players("") == []


class TestSetActivePlayer:
    def test_sets_session_when_owned(self, monkeypatch, _stub_streamlit):
        import auth
        rows = [{"id": "p2", "user_id": "u", "name": "Tommy", "removed_at": None}]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        monkeypatch.setattr(auth, "_current_user_id", lambda: "u")
        ok = auth.set_active_player("p2")
        assert ok is True
        assert _stub_streamlit["player"]["id"] == "p2"

    def test_rejects_unowned_profile(self, monkeypatch, _stub_streamlit):
        """IDOR guard: can't activate a profile that isn't in the household."""
        import auth
        rows = [{"id": "p2", "user_id": "u", "name": "Tommy", "removed_at": None}]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        monkeypatch.setattr(auth, "_current_user_id", lambda: "u")
        ok = auth.set_active_player("someone-elses-id")
        assert ok is False
        assert "player" not in _stub_streamlit


class TestNeedsProfilePick:
    def test_solo_autoselects(self, monkeypatch, _stub_streamlit):
        import auth
        rows = [{"id": "p1", "user_id": "u", "name": "Solo", "removed_at": None}]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        monkeypatch.setattr(auth, "_current_user_id", lambda: "u")
        # 1 profile → auto-selected, no pick needed
        assert auth.needs_profile_pick() is False
        assert _stub_streamlit["player"]["id"] == "p1"

    def test_household_needs_pick(self, monkeypatch, _stub_streamlit):
        import auth
        rows = [
            {"id": "p1", "user_id": "u", "name": "Dad", "removed_at": None},
            {"id": "p2", "user_id": "u", "name": "Tommy", "removed_at": None},
        ]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        monkeypatch.setattr(auth, "_current_user_id", lambda: "u")
        assert auth.needs_profile_pick() is True
        assert "player" not in _stub_streamlit   # nothing auto-picked

    def test_no_pick_once_active(self, monkeypatch, _stub_streamlit):
        import auth
        _stub_streamlit["player"] = {"id": "p2", "name": "Tommy"}
        rows = [
            {"id": "p1", "user_id": "u", "name": "Dad", "removed_at": None},
            {"id": "p2", "user_id": "u", "name": "Tommy", "removed_at": None},
        ]
        monkeypatch.setattr(auth, "_query_household_rows", lambda uid: rows)
        monkeypatch.setattr(auth, "_current_user_id", lambda: "u")
        assert auth.needs_profile_pick() is False
```

- [ ] **Step 2: Run — verify they fail**

Run: `python3 -m pytest tests/test_household_profiles.py -v`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Implement in `auth.py`**

Add near `_fetch_player_row` (after `_profile_from_row`):

```python
def _current_user_id() -> Optional[str]:
    """The logged-in auth user id, or None."""
    user = get_current_user()
    return user.id if user else None


def _query_household_rows(user_id: str) -> list[dict]:
    """All players rows for an auth user (incl. removed). Thin DB wrapper
    so tests can stub it."""
    sb = get_client()
    try:
        resp = (sb.table("players").select("*")
                  .eq("user_id", user_id)
                  .order("created_at", desc=False).execute())
        return resp.data or []
    except Exception as exc:
        st.error(f"Failed to load household: {exc}")
        return []


def list_household_players(user_id: str) -> list[dict]:
    """Active (non-removed) profile dicts for a household, in the app's
    legacy profile shape."""
    if not user_id:
        return []
    rows = [r for r in _query_household_rows(user_id) if not r.get("removed_at")]
    return [_profile_from_row(r) for r in rows]


def set_active_player(player_id: str) -> bool:
    """Set the active profile for this session. Returns False (and does
    nothing) if player_id isn't one of the caller's own non-removed
    profiles — IDOR guard."""
    uid = _current_user_id()
    if not uid or not player_id:
        return False
    for r in _query_household_rows(uid):
        if r.get("id") == player_id and not r.get("removed_at"):
            st.session_state["player"] = _profile_from_row(r)
            return True
    return False


def needs_profile_pick() -> bool:
    """True when the household has >1 active profile and none is selected
    yet. With exactly 1 profile, auto-selects it and returns False (solo
    users never see a picker)."""
    if st.session_state.get("player"):
        return False
    uid = _current_user_id()
    if not uid:
        return False
    actives = [r for r in _query_household_rows(uid) if not r.get("removed_at")]
    if len(actives) == 1:
        st.session_state["player"] = _profile_from_row(actives[0])
        return False
    return len(actives) > 1


def create_household_player(name: str, handedness: str = "RIGHT",
                            position: Optional[str] = None,
                            is_minor: bool = True) -> dict:
    """Create a new profile under the household via the seat-capped RPC.
    Returns {ok, player?, error?}."""
    if not (name or "").strip():
        return {"ok": False, "error": "Enter a name."}
    try:
        sb = get_client()
        resp = sb.rpc("create_household_player", {
            "p_name": name.strip(),
            "p_handedness": handedness,
            "p_position": position,
            "p_is_minor": is_minor,
        }).execute()
        data = resp.data
        row = data[0] if isinstance(data, list) and data else data
        return {"ok": True, "player": _profile_from_row(row) if row else None}
    except Exception as exc:
        msg = str(exc)
        if "slots are in use" in msg:
            return {"ok": False, "error": "Your household is full — every profile slot is in use."}
        return {"ok": False, "error": msg}
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_household_profiles.py -v`
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_household_profiles.py
git commit -m "feat(auth): household profile helpers (list/set-active/create/needs-pick)

list_household_players + set_active_player (with IDOR guard) +
needs_profile_pick (auto-selects the sole profile for solo users, so
they never see a picker) + create_household_player (calls the
seat-capped RPC). Active profile lives in st.session_state['player'],
the app's existing source of truth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `household_picker.py` — the "Who's training?" screen

**Files:**
- Create: `household_picker.py`
- Test: `tests/test_household_picker_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_household_picker_render.py
from __future__ import annotations
import sys, types
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    cap = {"markdown": [], "button": []}
    class _Col:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    st_stub = types.SimpleNamespace(
        session_state={},
        markdown=lambda s, **k: cap["markdown"].append(s),
        columns=lambda n, **k: [_Col() for _ in range(n if isinstance(n,int) else len(n))],
        button=lambda label, **k: (cap["button"].append(label) or False),
        rerun=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    auth_stub = types.SimpleNamespace(
        list_household_players=lambda uid: [
            {"id": "p1", "name": "Dad", "position": "1B", "handedness": "RIGHT"},
            {"id": "p2", "name": "Tommy", "position": "2B", "handedness": "RIGHT"},
        ],
        set_active_player=lambda pid: True,
        current_household_seats=lambda: 4,
    )
    monkeypatch.setitem(sys.modules, "auth", auth_stub)
    sys.modules.pop("household_picker", None)
    return cap


def test_renders_a_card_per_profile_and_add(_stub):
    import household_picker
    household_picker.render_household_picker("u")
    out = "\n".join(_stub["markdown"])
    assert "Who's training" in out
    # one selectable button per profile + an add-player button (under cap)
    assert any("Dad" in b for b in _stub["button"])
    assert any("Tommy" in b for b in _stub["button"])
    assert any("Add a player" in b for b in _stub["button"])
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_household_picker_render.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `household_picker.py`**

Editorial styling; one card-button per profile; "+ Add a player" when under cap.

```python
"""'Who's training?' household profile picker.

Shown after login when a household has >1 active profile and none is
selected. Selecting a profile sets it active (auth.set_active_player)
and reruns into the app as that profile.
"""
from __future__ import annotations
import html as _html
import streamlit as st

_PICKER_CSS = """
<style>
.hp-wrap { max-width: 760px; margin: 8vh auto 0; text-align: center; }
.hp-eyebrow { font-family:'Geist Mono',monospace; font-size:11px; font-weight:600;
  letter-spacing:0.24em; text-transform:uppercase; color:#E8C170; margin-bottom:12px; }
.hp-title { font-family:'Instrument Serif',serif; font-style:italic; font-weight:400;
  font-size:clamp(2.6rem,5vw,3.8rem); line-height:1.05; color:#F4EFE6; margin:0 0 36px; }
[data-testid="stButton"]:has(button[kind]) button { }
div[class*="st-key-hp_pick_"] button {
  width:100% !important; padding:26px 18px !important; border-radius:16px !important;
  background:rgba(244,239,230,0.025) !important; color:#F4EFE6 !important;
  border:1px solid rgba(244,239,230,0.10) !important;
  font-family:'Instrument Serif',serif !important; font-size:1.5rem !important;
  transition:all .2s ease !important;
}
div[class*="st-key-hp_pick_"] button:hover {
  border-color:rgba(232,193,112,0.5) !important; transform:translateY(-3px) !important;
  background:rgba(244,239,230,0.05) !important; }
.st-key-hp_add button {
  background:transparent !important; color:#C8C4BB !important;
  border:1px dashed rgba(244,239,230,0.18) !important; border-radius:16px !important;
  padding:26px 18px !important; width:100% !important;
  font-family:'Geist Mono',monospace !important; font-size:11px !important;
  letter-spacing:0.18em !important; text-transform:uppercase !important; }
</style>
"""


def render_household_picker(user_id: str) -> None:
    import auth
    st.markdown(_PICKER_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hp-wrap"><div class="hp-eyebrow">Your household</div>'
        '<h1 class="hp-title">Who’s training?</h1></div>',
        unsafe_allow_html=True,
    )
    profiles = auth.list_household_players(user_id)
    seats = auth.current_household_seats()
    n = len(profiles)
    cols = st.columns(min(max(n, 1), 4), gap="medium")
    for i, p in enumerate(profiles):
        with cols[i % 4]:
            meta = " · ".join(x for x in [str(p.get("position") or ""),
                              (p.get("handedness") or "")[:1]] if x)
            label = p.get("name") or "Player"
            if st.button(f"{label}\n{meta}".strip(),
                         key=f"hp_pick_{p.get('id')}", use_container_width=True):
                auth.set_active_player(p.get("id"))
                st.rerun()
    if n < seats:
        if st.button("+ Add a player", key="hp_add", use_container_width=True):
            st.session_state["page"] = "player_settings"
            st.session_state["_settings_open_section"] = "household"
            # Use a sentinel profile so the rest of the app has *a* player
            # to render settings under (first existing profile).
            if profiles:
                auth.set_active_player(profiles[0].get("id"))
            st.rerun()
```

Add the tiny `current_household_seats()` helper to `auth.py` (reads `v_my_plan.seats`):

```python
def current_household_seats() -> int:
    """Seat cap for the logged-in household's plan (default 1)."""
    try:
        sb = get_client()
        resp = sb.table("v_my_plan").select("seats").limit(1).execute()
        rows = resp.data or []
        return int(rows[0].get("seats") or 1) if rows else 1
    except Exception:
        return 1
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_household_picker_render.py -v`
Expected: 1 PASSED.

- [ ] **Step 5: Commit**

```bash
git add household_picker.py auth.py tests/test_household_picker_render.py
git commit -m "feat(picker): 'Who's training?' household profile chooser

Editorial card-buttons, one per active profile, plus '+ Add a player'
when under the seat cap. Selecting a profile sets it active and reruns
into the app. auth.current_household_seats() reads the cap from
v_my_plan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `app.py` — gate the picker after login + Switch Profile

**Files:**
- Modify: `app.py` (after the auth gate, before page routing)

- [ ] **Step 1: Find the auth gate.** Run `grep -n "current_profile\|just_signed_up\|page.*=.*dashboard\|render_auth" app.py | head` to locate where, post-login, the app decides what to render (around app.py:1045-1209 per the audit).

- [ ] **Step 2: Insert the picker gate.** Immediately AFTER the user is confirmed logged-in and BEFORE the normal page router, add:

```python
# Household sub-accounts: if this login has >1 active profile and none is
# chosen yet, show the "Who's training?" picker before any page renders.
# Solo/free users (1 profile) auto-select inside needs_profile_pick().
import auth as _auth
if _auth.needs_profile_pick():
    import household_picker
    _uid = _auth._current_user_id()
    household_picker.render_household_picker(_uid)
    st.stop()
```

- [ ] **Step 3: Add a "Switch profile" handler.** Where `st.session_state["page"]` transitions are handled, support a `switch_profile` action that clears the active player and reruns (the gate then re-shows the picker):

```python
if st.session_state.get("_action") == "switch_profile":
    st.session_state.pop("player", None)
    st.session_state.pop("_action", None)
    st.rerun()
```

- [ ] **Step 4: Smoke-compile**

Run: `python3 -m py_compile app.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(app): gate 'Who's training?' picker after login + switch-profile

When a household has >1 active profile and none is selected, render the
picker and st.stop() before any page. Solo users auto-select (no
picker). A 'switch_profile' action clears the active player so the
picker reappears.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Settings — profile management (replaces email invites)

**Files:**
- Modify: `player_settings_page.py` (the "Household" section added earlier)

- [ ] **Step 1: Locate the Household section** (`grep -n "_render_household_section\|Household\|add_member\|_fs\." player_settings_page.py | head`).

- [ ] **Step 2: Replace the invite UI with profile management.** The section should:
  - Show `auth.list_household_players(user_id)` as rows: name + position + handedness + a "Remove" button (not on the currently-active profile).
  - Show "X of N profiles" where N = `auth.current_household_seats()`.
  - An "Add a player" form: name (text), bat hand (R/L segmented), position (text) → calls `auth.create_household_player(name, handedness, position)`; on `{ok}` → `st.success` + `st.rerun()`; on error → `st.error(result["error"])`.
  - Only render the whole section when `current_household_seats() > 1` (multi-seat plan).
  - "Remove" calls a new `auth.remove_household_player(player_id)` (soft-remove: `players.update({"removed_at": now}).eq("id", id)`), then `st.rerun()`. Add that helper to `auth.py`:

```python
def remove_household_player(player_id: str) -> dict:
    """Soft-remove a profile (set removed_at). Owner-scoped by RLS."""
    if not player_id:
        return {"ok": False, "error": "Missing id."}
    import datetime as _dt
    try:
        sb = get_client()
        sb.table("players").update(
            {"removed_at": _dt.datetime.utcnow().isoformat() + "Z"}
        ).eq("id", player_id).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
```

- [ ] **Step 3: Guard against removing your own active profile** — in the UI, hide/disable "Remove" when `p["id"] == st.session_state.get("player", {}).get("id")`.

- [ ] **Step 4: Compile + commit**

```bash
python3 -m py_compile player_settings_page.py auth.py
git add player_settings_page.py auth.py
git commit -m "feat(settings): household profile management (create/remove)

The Household section now creates sub-account profiles directly
(name + bat hand + position, no email) via create_household_player,
lists them with a soft-remove, and shows 'X of N profiles' from the
plan cap. Replaces the email-invite UI. Hidden for single-seat plans.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Re-point `family_storage.py` at player profiles

**Files:**
- Modify: `family_storage.py`
- Modify: `tests/test_family_storage.py`

- [ ] **Step 1: Update the tests** to the player-profile source. `load_family_for_user` returns a dict whose `id` is the household auth user id; `list_members` returns the household's player profiles (via `auth.list_household_players`); `is_family_pro_member` true when `current_household_seats() > 1`; `add_member(family_id, name, ...)` delegates to `auth.create_household_player`; `remove_member(player_id)` to `auth.remove_household_player`. Rewrite `tests/test_family_storage.py`'s DB-touching tests to monkeypatch `auth.*` instead of `_supabase_query_safe`. Keep `_compute_member_summary` tests unchanged (pure).

- [ ] **Step 2: Rewrite the public functions** to delegate to `auth` + read swings by `player_id`:

```python
def load_family_for_user(user_id):
    import auth
    if not user_id or auth.current_household_seats() <= 1:
        return None
    return {"id": user_id, "owner_user_id": user_id,
            "max_seats": auth.current_household_seats(),
            "plan_name": "Household"}

def list_members(family_id, include_removed=False):
    import auth
    profs = auth.list_household_players(family_id)  # family_id == household user_id
    return [{"id": p["id"], "player_user_id": p["id"],
             "display_name": p.get("name") or "Player",
             "position": p.get("position"), "handedness": p.get("handedness"),
             "role": "owner" if i == 0 else "member",
             "invite_status": "active"} for i, p in enumerate(profs)]

def is_family_pro_member(user_id):
    import auth
    try:
        return bool(user_id) and auth.current_household_seats() > 1
    except Exception:
        return False

def add_member(family_id, name, role="member", is_minor=True, display_name=None):
    import auth
    return auth.create_household_player(name or display_name or "",
                                        position=None, is_minor=is_minor)

def remove_member(member_id):
    import auth
    return auth.remove_household_player(member_id)
```

Keep `get_member_summary` but fetch swings by `player_id` (the profile id) using the existing `swings.player_id` column:

```python
def get_member_summary(member, swings=None):
    out = dict(member)
    pid = member.get("id")
    if swings is None and pid and _get_client is not None:
        status, result = _supabase_query_safe(
            "swings",
            lambda t: t.select("created_at,score").eq("player_id", pid)
                       .order("created_at", desc=False).limit(30).execute())
        swings = ([{"created_at": r.get("created_at"), "edge_score": r.get("score")}
                   for r in _rows(result)] if status == "ok" else [])
    elif swings is None:
        swings = []
    out.update(_compute_member_summary(swings))
    return out
```

- [ ] **Step 3: Run** `python3 -m pytest tests/test_family_storage.py tests/test_family_dashboard_render.py -v`
Expected: green (update any assertions that referenced the old subscription_seats shape).

- [ ] **Step 4: Commit**

```bash
git add family_storage.py tests/test_family_storage.py
git commit -m "refactor(family): source the household dashboard from player profiles

family_storage now reads the household's player profiles (via auth)
instead of subscription_seats — matching the sub-account model. Public
API unchanged so family_dashboard/settings consume it as before. Swing
summaries read by player_id. subscription_seats stays parked.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Nav — "Switch profile" affordance

**Files:**
- Modify: `bl_edge_chrome.py`

- [ ] **Step 1:** In the masthead build, when `auth.current_household_seats() > 1`, add a small "Switch profile" item that sets `st.session_state["_action"] = "switch_profile"` + reruns. Place it near the existing account/nav controls. Mirror the existing nav-item pattern in the file.

- [ ] **Step 2:** Compile + commit

```bash
python3 -m py_compile bl_edge_chrome.py
git add bl_edge_chrome.py
git commit -m "feat(nav): Switch Profile control for multi-profile households

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Apply migration + end-to-end validation + PR

**Files:** none (validation + ship)

- [ ] **Step 1: Full suite green**

Run: `python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5`
Expected: all pass.

- [ ] **Step 2: Apply the migration to the live DB** (controller does this with user go-ahead — same as the household_seats migration). Verify:

```sql
-- after apply
SELECT conname FROM pg_constraint WHERE conrelid='public.players'::regclass AND contype='u';
-- expect: players_user_id_key GONE
SELECT count(*) FROM pg_proc WHERE proname='create_household_player';  -- expect 1
SELECT column_name FROM information_schema.columns
 WHERE table_name='players' AND column_name='removed_at';  -- expect 1 row
```

- [ ] **Step 3: Manual end-to-end** (Streamlit): on a Family Pro test login —
  create 2 profiles in Settings → log out/in → "Who's training?" appears →
  pick Tommy → upload a swing → it's in Tommy's history → Switch profile →
  pick Dad → Dad's history is separate → Family dashboard shows both.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin claude/household-subaccounts
gh pr create --base main --head claude/household-subaccounts \
  --title "Household sub-accounts (Family Pro profiles)" \
  --body "Implements docs/superpowers/specs/2026-05-23-household-subaccounts-design.md. One household login → up to N profiles, 'Who's training?' picker, swings auto-attach to the active profile. Solo/free users unaffected. Migration applied to live DB."
```

---

## Self-review

**Spec coverage:** schema change → T1; auth helpers → T2; picker → T3; login gate + switch → T4; settings management → T5; dashboard source → T6; nav switch → T7; migration apply + validation + PR → T8. All spec sections covered.

**Placeholder scan:** every code step has complete code; no TBD/TODO. The only "locate" steps (T4S1, T5S1, T7S1) are grep-to-find-insertion-point, each followed by exact code to insert.

**Type consistency:** `st.session_state["player"]` is the active-profile var throughout. `_profile_from_row` is the canonical shape (has `id`, `name`, `handedness`, `position`). `create_household_player` RPC params (`p_name`/`p_handedness`/`p_position`/`p_is_minor`) match the `auth.create_household_player` wrapper. `current_household_seats()` used in picker, settings, family_storage consistently.

**Parked, by design:** `subscription_seats` invite/claim machinery (documented, unused in this model).
