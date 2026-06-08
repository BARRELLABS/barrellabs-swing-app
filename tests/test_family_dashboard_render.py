"""Snapshot tests for family_dashboard.py — verify the 4 states
render via the right helpers and produce the expected number of
cards / markers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


@pytest.fixture(autouse=True)
def _stub_streamlit(monkeypatch):
    """Replace streamlit with a thin spy + stub auth so we can capture
    markdown calls and drive the dashboard's render branches."""
    captured = {"markdown": [], "button": [], "session_state": {}}

    class _Col:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _markdown(s, **kw): captured["markdown"].append(s)
    def _columns(n, gap=None, **kw):
        count = n if isinstance(n, int) else len(n)
        return [_Col() for _ in range(count)]
    def _button(label, **kw):
        captured["button"].append(label); return False
    def _rerun(): pass
    def _toast(*a, **k): pass
    def _success(*a, **k): pass

    st_stub = types.SimpleNamespace(
        markdown=_markdown,
        html=_markdown,  # family cards now render via st.html; capture it too
        columns=_columns,
        button=_button,
        rerun=_rerun,
        toast=_toast,
        success=_success,
        session_state=captured["session_state"],
    )
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)

    # Stub auth.current_profile so the dashboard has a user_id to route on.
    auth_stub = types.SimpleNamespace(
        current_profile=lambda: {"user_id": "u_parent", "name": "Dave"},
    )
    monkeypatch.setitem(sys.modules, "auth", auth_stub)

    # Force fresh import each test so the stub is used
    for mod_name in ("family_dashboard",):
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    return captured


def _make_member(name, **overrides):
    base = {
        "id":              f"m_{name}",
        "player_user_id":  f"u_{name}",
        "display_name":    name,
        "age":             13,
        "position":        "2B",
        "handedness":      "R",
        "invite_status":   "active",
    }
    base.update(overrides)
    return base


def _make_summary(name, **overrides):
    base = {
        **_make_member(name),
        "latest_score":     80,
        "delta":            0,
        "days_since":       1,
        "is_stale":         False,
        "trend":            "flat",
        "verdict_line":     "Holding steady.",
        "sparkline_points": [78, 79, 80],
        "latest_date":      "2026-05-21",
    }
    base.update(overrides)
    return base


class TestUpgradeGate:
    def test_non_pro_user_sees_upgrade_prompt_not_empty_state(self, _stub_streamlit, monkeypatch):
        """A free-tier user with no family must NOT see 'Family Pro is
        active' copy — they get an upgrade prompt."""
        import family_storage
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: None)
        monkeypatch.setattr(family_storage, "is_family_pro_member", lambda uid: False)
        import family_dashboard
        family_dashboard.render_family_dashboard()
        out = "\n".join(_stub_streamlit["markdown"])
        assert "Family Pro" in out and "unlocks this" in out
        assert "Family Pro is active" not in out
        assert "View plans →" in _stub_streamlit["button"]


class TestEmptyState:
    def test_empty_state_renders_invite_cta(self, _stub_streamlit, monkeypatch):
        import family_storage
        # No family yet, but the user IS a Family Pro member (e.g. webhook
        # just created their sub; family row provisioning lagging) — they
        # should see the onboarding empty state, not the upgrade prompt.
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: None)
        monkeypatch.setattr(family_storage, "is_family_pro_member", lambda uid: True)
        import family_dashboard
        family_dashboard.render_family_dashboard()
        out = "\n".join(_stub_streamlit["markdown"])
        assert "Add your first" in out
        assert "+ Invite a Player" in _stub_streamlit["button"]


class TestSingleState:
    def test_single_state_renders_one_card_centered(self, _stub_streamlit, monkeypatch):
        import family_storage
        family = {"id": "f1", "owner_user_id": "u_owner"}
        member = _make_member("Jake")
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: family)
        monkeypatch.setattr(family_storage, "list_members", lambda fid: [member])
        monkeypatch.setattr(family_storage, "get_member_summary",
                            lambda m, **k: _make_summary("Jake", latest_score=87, delta=4,
                                                          trend="up", days_since=0,
                                                          verdict_line="Best week."))
        import family_dashboard
        family_dashboard.render_family_dashboard()
        out = "\n".join(_stub_streamlit["markdown"])
        assert "Jake" in out and "progress" in out
        assert "fd-single" in out


class TestPopulatedState:
    def test_renders_3_cards(self, _stub_streamlit, monkeypatch):
        import family_storage
        family = {"id": "f1", "owner_user_id": "u_owner"}
        members = [_make_member(n) for n in ("Jake", "Mia", "Owen")]
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: family)
        monkeypatch.setattr(family_storage, "list_members", lambda fid: members)
        monkeypatch.setattr(family_storage, "get_member_summary",
                            lambda m, **k: _make_summary(m["display_name"]))
        import family_dashboard
        family_dashboard.render_family_dashboard()
        out = "\n".join(_stub_streamlit["markdown"])
        assert "The whole family" in out
        # 3 cards rendered
        assert out.count("fd-card") >= 3


class TestStaleMember:
    def test_stale_member_renders_nudge_button(self, _stub_streamlit, monkeypatch):
        import family_storage
        family = {"id": "f1", "owner_user_id": "u_owner"}
        members = [_make_member("Owen")]
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: family)
        monkeypatch.setattr(family_storage, "list_members", lambda fid: members)
        monkeypatch.setattr(family_storage, "get_member_summary",
                            lambda m, **k: _make_summary("Owen",
                                                          is_stale=True,
                                                          trend="stale",
                                                          days_since=12,
                                                          verdict_line="Hasn't filmed in 12 days.",
                                                          latest_score=85,
                                                          delta=-3,
                                                          latest_date="2026-05-09"))
        import family_dashboard
        family_dashboard.render_family_dashboard()
        # Owen is single state — only one member — but the stale info should
        # still render. Nudge button gets pushed.
        assert any("Nudge Owen" in b for b in _stub_streamlit["button"])


class TestFullState:
    def test_renders_4_cards_and_household_full(self, _stub_streamlit, monkeypatch):
        import family_storage
        family = {"id": "f1", "owner_user_id": "u_owner"}
        members = [_make_member(n) for n in ("Dave", "Jake", "Mia", "Owen")]
        monkeypatch.setattr(family_storage, "load_family_for_user", lambda uid: family)
        monkeypatch.setattr(family_storage, "list_members", lambda fid: members)
        monkeypatch.setattr(family_storage, "get_member_summary",
                            lambda m, **k: _make_summary(m["display_name"]))
        import family_dashboard
        family_dashboard.render_family_dashboard()
        out = "\n".join(_stub_streamlit["markdown"])
        assert "Four players" in out
        assert "household is full" in out.lower()
        assert out.count("fd-card") >= 4
