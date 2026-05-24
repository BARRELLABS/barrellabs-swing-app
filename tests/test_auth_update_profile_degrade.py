"""update_profile must degrade gracefully when an apply-gated column
(birth_year) is missing from the live schema: strip that column and retry
once, so a plain profile save still works before the migration has run
against prod. Regression guard for PR #23 review finding."""
import types

import auth


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    """Records each update payload; raises a PostgREST-style schema error
    while the payload still names birth_year, succeeds once it's stripped."""

    def __init__(self, recorder):
        self._recorder = recorder
        self._payload = None

    def update(self, payload):
        self._payload = payload
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        self._recorder.append(dict(self._payload))
        if "birth_year" in self._payload:
            raise RuntimeError(
                "Could not find the 'birth_year' column of 'players' "
                "in the schema cache"
            )
        return _Resp([{"id": "p1", "name": "Test", "handedness": "RIGHT"}])


class _FakeClient:
    def __init__(self, recorder):
        self._recorder = recorder

    def table(self, _name):
        return _FakeTable(self._recorder)


def _install(monkeypatch):
    recorder = []
    monkeypatch.setattr(auth, "get_client", lambda: _FakeClient(recorder))
    monkeypatch.setattr(auth, "st", types.SimpleNamespace(session_state={}))
    return recorder


def test_update_profile_retries_without_birth_year_on_schema_error(monkeypatch):
    recorder = _install(monkeypatch)

    prof = auth.update_profile(
        "p1", name="Test", handedness="RIGHT", birth_year=2014
    )

    # First attempt carries birth_year (and is rejected); retry strips it.
    assert len(recorder) == 2
    assert "birth_year" in recorder[0]
    assert "birth_year" not in recorder[1]
    # The rest of the profile still saved instead of the whole save crashing.
    assert prof is not None
    assert prof["name"] == "Test"


def test_update_profile_no_gated_column_saves_in_one_call(monkeypatch):
    recorder = _install(monkeypatch)

    prof = auth.update_profile("p1", name="Test", handedness="RIGHT")

    assert len(recorder) == 1
    assert prof is not None


def test_update_profile_reraises_non_schema_errors(monkeypatch):
    """A genuine failure (not a missing-column schema error) must propagate,
    not be silently swallowed by the retry path."""
    def _boom():
        class _T:
            def update(self, p): return self
            def eq(self, *a, **k): return self
            def execute(self): raise RuntimeError("network is unreachable")
        return types.SimpleNamespace(table=lambda _n: _T())

    monkeypatch.setattr(auth, "get_client", _boom)
    monkeypatch.setattr(auth, "st", types.SimpleNamespace(session_state={}))

    try:
        auth.update_profile("p1", name="Test", birth_year=2014)
    except RuntimeError as exc:
        assert "network is unreachable" in str(exc)
    else:
        raise AssertionError("expected non-schema error to propagate")
