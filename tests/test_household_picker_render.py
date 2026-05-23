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
    assert "Who's training" in out or "Who's training" in out
    assert any("Dad" in b for b in _stub["button"])
    assert any("Tommy" in b for b in _stub["button"])
    assert any("Add a player" in b for b in _stub["button"])
