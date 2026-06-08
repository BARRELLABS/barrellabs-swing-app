"""Tests for facility_storage — the pure roster_summary logic + safe fallbacks.

The DB-touching functions are covered by their try/except → safe-default
contract (no backend in unit tests), not by mocking Supabase here.
"""
import facility_storage as fs


# --- pure roster summary -------------------------------------------

def test_summary_counts_active_and_attention():
    members = [
        {"player_id": "a", "swings": [{"created_at": "2026-06-03", "edge_score": 80}]},  # active
        {"player_id": "b", "swings": []},                                                # attention
        {"player_id": "c", "swings": [{"created_at": "2026-05-01", "edge_score": 70}]},  # stale
    ]
    s = fs.roster_summary(members, today="2026-06-04")
    assert s["total"] == 3
    assert s["active_this_week"] == 1
    assert s["needs_attention"] == 2   # b (no swings) + c (stale > 10 days)


def test_summary_empty_roster():
    s = fs.roster_summary([], today="2026-06-04")
    assert s == {"total": 0, "active_this_week": 0, "needs_attention": 0}


def test_summary_uses_latest_swing_for_recency():
    members = [{
        "player_id": "a",
        "swings": [
            {"created_at": "2026-05-01", "edge_score": 60},
            {"created_at": "2026-06-04", "edge_score": 84},  # latest → active
        ],
    }]
    s = fs.roster_summary(members, today="2026-06-04")
    assert s["active_this_week"] == 1
    assert s["needs_attention"] == 0


def test_summary_handles_malformed_dates():
    members = [{"player_id": "a", "swings": [{"created_at": "", "edge_score": 70}]}]
    s = fs.roster_summary(members, today="2026-06-04")
    # bad date → treated as very stale, not a crash
    assert s["needs_attention"] == 1


# --- safe fallbacks when no backend is configured ------------------

def test_load_facility_safe_without_backend(monkeypatch):
    monkeypatch.setattr(fs, "_get_client", None)
    assert fs.load_facility_for_owner("u1") is None
    assert fs.list_members("f1") == []
    assert fs.is_player_sponsored("p1") is False


def test_join_by_code_requires_code():
    res = fs.join_by_code("", "p1")
    assert res["ok"] is False and "join code" in res["error"].lower()
