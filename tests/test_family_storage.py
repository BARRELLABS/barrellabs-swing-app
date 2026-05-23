"""family_storage — Household / Family Pro data layer.

These tests run without a real Supabase connection. The module must
fall back to None / empty / False when auth is unavailable or when the
user is on a single-seat plan — that's the v1 contract that lets us
ship the dashboard before the migration is applied.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def _make_auth_stub(seats=1, players=None):
    """Build a minimal auth stub for monkeypatching."""
    return types.SimpleNamespace(
        current_household_seats=lambda: seats,
        list_household_players=lambda uid: players or [],
        create_household_player=lambda name, handedness="RIGHT", position=None, is_minor=True: {
            "ok": True, "player": {"id": "new-p", "name": name}
        },
        remove_household_player=lambda pid: {"ok": True},
    )


class TestSafeFallback:
    """Single-seat plans and empty user IDs return None / empty / False."""

    def test_load_family_for_user_returns_none_for_single_seat(self, monkeypatch):
        import family_storage
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=1))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        assert family_storage.load_family_for_user("any-uuid") is None

    def test_load_family_for_user_returns_dict_for_multi_seat(self, monkeypatch):
        import family_storage
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=4))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        result = family_storage.load_family_for_user("uid-123")
        assert result is not None
        assert result["max_seats"] == 4
        assert result["id"] == "uid-123"

    def test_load_family_empty_user_id(self):
        import family_storage
        assert family_storage.load_family_for_user("") is None
        assert family_storage.load_family_for_user(None) is None

    def test_is_family_pro_member_false_when_single_seat(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=1))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        assert family_storage.is_family_pro_member("any-uuid") is False

    def test_is_family_pro_member_true_when_multi_seat(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=4))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        assert family_storage.is_family_pro_member("uid-123") is True

    def test_list_members_maps_profiles_to_member_dicts(self, monkeypatch):
        players = [
            {"id": "p1", "name": "Jake", "position": "SS", "handedness": "RIGHT"},
            {"id": "p2", "name": "Mia", "position": "CF", "handedness": "LEFT"},
        ]
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=4, players=players))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        members = family_storage.list_members("uid-123")
        assert len(members) == 2
        # First profile is owner
        assert members[0]["role"] == "owner"
        assert members[1]["role"] == "member"
        assert members[0]["display_name"] == "Jake"
        assert members[1]["display_name"] == "Mia"
        assert members[0]["invite_status"] == "active"

    def test_list_members_returns_empty_when_no_profiles(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "auth", _make_auth_stub(seats=4, players=[]))
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        assert family_storage.list_members("uid-123") == []


class TestComputeMemberSummary:
    """Pure-function tests for the verdict + sparkline derivation."""

    def test_trending_up_big_jump(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([
            {"edge_score": 78, "created_at": "2026-05-14"},
            {"edge_score": 81, "created_at": "2026-05-17"},
            {"edge_score": 87, "created_at": "2026-05-21"},  # +6 vs last
        ], today="2026-05-21")
        assert s["latest_score"] == 87
        assert s["delta"] == 6
        assert s["trend"] == "up"
        assert "best" in s["verdict_line"].lower()

    def test_trending_up_medium_jump(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([
            {"edge_score": 80, "created_at": "2026-05-17"},
            {"edge_score": 83, "created_at": "2026-05-21"},  # +3
        ], today="2026-05-21")
        assert s["delta"] == 3
        assert s["trend"] == "up"
        assert "trending up" in s["verdict_line"].lower()

    def test_holding_steady(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([
            {"edge_score": 74, "created_at": "2026-05-17"},
            {"edge_score": 74, "created_at": "2026-05-21"},
        ], today="2026-05-21")
        assert s["delta"] == 0
        assert s["trend"] == "flat"
        assert ("steady" in s["verdict_line"].lower()
                or "holding" in s["verdict_line"].lower())

    def test_slipping(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([
            {"edge_score": 90, "created_at": "2026-05-17"},
            {"edge_score": 85, "created_at": "2026-05-21"},  # -5
        ], today="2026-05-21")
        assert s["delta"] == -5
        assert s["trend"] == "down"
        assert "slipping" in s["verdict_line"].lower()
        assert "90" in s["verdict_line"]

    def test_stale_when_no_recent_swing(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary(
            [{"edge_score": 85, "created_at": "2026-05-01"}],
            today="2026-05-21",
        )
        assert s["is_stale"] is True
        assert s["days_since"] == 20
        assert "20 days" in s["verdict_line"]
        assert s["trend"] == "stale"

    def test_empty_swings_no_crash(self):
        from family_storage import _compute_member_summary
        s = _compute_member_summary([])
        assert s["latest_score"] is None
        assert s["is_stale"] is True
        assert s["sparkline_points"] == []
        assert s["trend"] == "unknown"

    def test_sparkline_last_10_points(self):
        from family_storage import _compute_member_summary
        swings = [{"edge_score": i, "created_at": f"2026-05-{i:02d}"}
                  for i in range(1, 16)]  # 15 swings, ascending
        s = _compute_member_summary(swings, today="2026-05-15")
        assert len(s["sparkline_points"]) == 10
        assert s["sparkline_points"][0] == 6   # last 10 starts at swing #6
        assert s["sparkline_points"][-1] == 15


class TestAddMember:
    """Adding a member delegates to auth.create_household_player."""

    def test_add_member_delegates_to_auth(self, monkeypatch):
        called = {}

        def _create(name, handedness="RIGHT", position=None, is_minor=True):
            called["name"] = name
            called["is_minor"] = is_minor
            return {"ok": True, "player": {"id": "new-p", "name": name}}

        auth_stub = types.SimpleNamespace(
            current_household_seats=lambda: 4,
            list_household_players=lambda uid: [],
            create_household_player=_create,
            remove_household_player=lambda pid: {"ok": True},
        )
        monkeypatch.setitem(sys.modules, "auth", auth_stub)
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        result = family_storage.add_member("uid-123", name="Jake", is_minor=True)
        assert result["ok"] is True
        assert called["name"] == "Jake"
        assert called["is_minor"] is True

    def test_add_member_uses_display_name_when_name_empty(self, monkeypatch):
        called = {}

        def _create(name, handedness="RIGHT", position=None, is_minor=True):
            called["name"] = name
            return {"ok": True}

        auth_stub = types.SimpleNamespace(
            current_household_seats=lambda: 4,
            list_household_players=lambda uid: [],
            create_household_player=_create,
            remove_household_player=lambda pid: {"ok": True},
        )
        monkeypatch.setitem(sys.modules, "auth", auth_stub)
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        family_storage.add_member("uid-123", name="", display_name="Mia")
        assert called["name"] == "Mia"


class TestRemoveMember:
    def test_remove_member_delegates_to_auth(self, monkeypatch):
        called = {}

        def _remove(pid):
            called["pid"] = pid
            return {"ok": True}

        auth_stub = types.SimpleNamespace(
            current_household_seats=lambda: 4,
            list_household_players=lambda uid: [],
            create_household_player=lambda *a, **k: {"ok": True},
            remove_household_player=_remove,
        )
        monkeypatch.setitem(sys.modules, "auth", auth_stub)
        if "family_storage" in sys.modules:
            del sys.modules["family_storage"]
        import family_storage
        result = family_storage.remove_member("p-abc")
        assert result["ok"] is True
        assert called["pid"] == "p-abc"
