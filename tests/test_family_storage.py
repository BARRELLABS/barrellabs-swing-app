"""family_storage — Household / Family Pro data layer.

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
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.load_family_for_user("any-uuid") is None

    def test_list_members_returns_empty_when_unmigrated(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.list_members("any-family-id") == []

    def test_is_family_pro_member_false_when_unmigrated(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "_supabase_query_safe",
                            lambda *a, **k: ("schema_missing", None))
        assert family_storage.is_family_pro_member("any-uuid") is False

    def test_load_family_empty_user_id(self):
        import family_storage
        assert family_storage.load_family_for_user("") is None
        assert family_storage.load_family_for_user(None) is None


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
    """Adding a member: seat cap, email validation, token generation."""

    def test_invalid_email_rejected(self):
        import family_storage
        result = family_storage.add_member("f1", "")
        assert result["ok"] is False

        result = family_storage.add_member("f1", "no-at-sign")
        assert result["ok"] is False

    def test_seat_cap_enforced_client_side(self, monkeypatch):
        import family_storage
        # 4 active members already → adding 5th rejected
        fake_members = [{"player_user_id": f"u{i}", "invite_status": "active"}
                        for i in range(4)]
        monkeypatch.setattr(family_storage, "list_members",
                            lambda *a, **k: fake_members)
        result = family_storage.add_member("f1", "new@example.com")
        assert result["ok"] is False
        assert "full" in result["error"].lower() or "cap" in result["error"].lower()

    def test_under_cap_succeeds_in_stub_mode(self, monkeypatch):
        """With no Supabase client, add_member returns a stub success
        with the invite token (so the dashboard can show it inline)."""
        import family_storage
        monkeypatch.setattr(family_storage, "list_members", lambda *a, **k: [])
        monkeypatch.setattr(family_storage, "_get_client", None)
        result = family_storage.add_member("f1", "kid@example.com")
        assert result["ok"] is True
        assert len(result["invite_token"]) >= 32


class TestRemoveMember:
    def test_missing_id_returns_error(self):
        import family_storage
        result = family_storage.remove_member("")
        assert result["ok"] is False

    def test_stub_mode_success(self, monkeypatch):
        import family_storage
        monkeypatch.setattr(family_storage, "_get_client", None)
        result = family_storage.remove_member("fm1")
        assert result["ok"] is True


class TestClaimInvite:
    def test_missing_args_returns_error(self):
        import family_storage
        assert family_storage.claim_invite("", "uid")["ok"] is False
        assert family_storage.claim_invite("token", "")["ok"] is False

    def test_stub_mode_no_db_returns_error(self, monkeypatch):
        """Claim requires a real DB — stub mode is read-only error."""
        import family_storage
        monkeypatch.setattr(family_storage, "_get_client", None)
        result = family_storage.claim_invite("tok123", "user1")
        assert result["ok"] is False
