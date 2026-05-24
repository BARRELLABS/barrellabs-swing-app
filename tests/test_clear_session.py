"""clear_session must drop the previous identity's cached profile, plan, and
swing-usage snapshot — not just the tokens — so a second login on a shared
device (a family iPad) never inherits the prior user's entitlements/state."""
import sys
import types


def _passthrough(*a, **k):
    if len(a) == 1 and callable(a[0]) and not k:
        return a[0]
    def inner(fn):
        return fn
    return inner


def _install(monkeypatch):
    ss = {}
    st_stub = types.SimpleNamespace(
        session_state=ss,
        cache_resource=_passthrough,
        cache_data=_passthrough,
        secrets={},
    )
    monkeypatch.setitem(sys.modules, "streamlit", st_stub)
    sys.modules.pop("supabase_client", None)
    import supabase_client
    monkeypatch.setattr(
        supabase_client, "_build_client",
        lambda: types.SimpleNamespace(
            auth=types.SimpleNamespace(sign_out=lambda: None)))
    return supabase_client, ss


def test_clear_session_drops_identity_and_plan_cache(monkeypatch):
    sc, ss = _install(monkeypatch)
    ss.update({
        "supabase_session": {"access_token": "x"},
        "player": {"id": "p1"},
        "user": {"id": "p1"},
        "_my_plan_snapshot": {"plan": "solo_pro", "free_swings_used": 2},
        "_session_expired": True,
        "_profile_picked": True,
        "page": "dashboard",  # unrelated UI state — must survive
    })

    sc.clear_session()

    for gone in ("supabase_session", "player", "user", "_my_plan_snapshot",
                 "_session_expired", "_profile_picked"):
        assert gone not in ss, f"{gone} should be cleared on logout"
    # Don't nuke unrelated navigation state.
    assert ss.get("page") == "dashboard"
