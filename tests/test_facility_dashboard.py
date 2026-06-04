"""Tests for facility_dashboard pure helpers (filter + paginate).

The Streamlit render path needs a server + auth (not unit-tested here); these
cover the pure logic that decides what shows on each page.
"""
import facility_dashboard as fd


def _members(n):
    return [{"display_name": f"Player {i}", "player_id": str(i)} for i in range(n)]


def test_filter_empty_query_returns_all():
    ms = _members(5)
    assert len(fd.filter_members(ms, "")) == 5
    assert len(fd.filter_members(ms, "   ")) == 5


def test_filter_is_case_insensitive_substring():
    ms = [{"display_name": "Johnny Ramirez"}, {"display_name": "Maria Lopez"}]
    assert len(fd.filter_members(ms, "ram")) == 1
    assert fd.filter_members(ms, "RAM")[0]["display_name"] == "Johnny Ramirez"
    assert fd.filter_members(ms, "z") == ms or len(fd.filter_members(ms, "z")) == 2


def test_paginate_basic():
    ms = _members(70)
    p0 = fd.paginate(ms, 0, size=30)
    assert p0["total"] == 70 and p0["n_pages"] == 3
    assert len(p0["items"]) == 30 and p0["page"] == 0
    p2 = fd.paginate(ms, 2, size=30)
    assert len(p2["items"]) == 10   # 70 - 60


def test_paginate_clamps_out_of_range_page():
    ms = _members(10)
    p = fd.paginate(ms, 99, size=30)
    assert p["page"] == 0 and p["n_pages"] == 1 and len(p["items"]) == 10


def test_paginate_empty():
    p = fd.paginate([], 0)
    assert p["total"] == 0 and p["n_pages"] == 1 and p["items"] == []


def test_module_imports():
    # guards against syntax/import errors in the page module
    assert hasattr(fd, "render_facility_dashboard")
