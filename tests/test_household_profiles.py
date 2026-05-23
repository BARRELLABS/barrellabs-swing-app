# tests/test_household_profiles.py
"""Household sub-accounts — multi-profile auth helpers."""
from __future__ import annotations
import sys, types
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def _passthrough_decorator(*dargs, **dkwargs):
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return dargs[0]
    def inner(fn):
        return fn
    return inner


@pytest.fixture(autouse=True)
def _stub_streamlit(monkeypatch):
    ss = {}
    st_stub = types.SimpleNamespace(
        session_state=ss,
        error=lambda *a, **k: None,
        markdown=lambda *a, **k: None,
        rerun=lambda: None,
        cache_resource=_passthrough_decorator,
        cache_data=_passthrough_decorator,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    # Also stub supabase_client so auth.py can be imported without a live DB
    sc_stub = types.ModuleType("supabase_client")
    sc_stub.get_client = lambda: None
    sc_stub.store_session = lambda *a, **k: None
    sc_stub.clear_session = lambda *a, **k: None
    sc_stub.get_current_user = lambda: None
    monkeypatch.setitem(sys.modules, "supabase_client", sc_stub)
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
