"""Task 4: facility sponsorship layered onto the live plan read."""
import subscription_storage as ss
from entitlements import can_analyze_swing, is_pro


def test_apply_sponsorship_upgrades_free(monkeypatch):
    monkeypatch.setattr(ss, "_is_active_player_sponsored", lambda: True)
    snap = {"plan_id": "free", "status": "active", "free_swings_used": 3}
    eff = ss._apply_sponsorship(snap)
    assert eff["plan_id"] == "solo_pro"
    assert is_pro(eff) is True
    assert can_analyze_swing(eff).allowed is True   # unlimited despite 3 used
    assert eff.get("sponsored") is True


def test_apply_sponsorship_noop_when_not_sponsored(monkeypatch):
    monkeypatch.setattr(ss, "_is_active_player_sponsored", lambda: False)
    snap = {"plan_id": "free", "status": "active"}
    assert ss._apply_sponsorship(snap) is snap


def test_sponsorship_never_downgrades_payer(monkeypatch):
    monkeypatch.setattr(ss, "_is_active_player_sponsored", lambda: True)
    snap = {"plan_id": "family_pro", "status": "active"}
    eff = ss._apply_sponsorship(snap)
    assert eff["plan_id"] == "family_pro"
