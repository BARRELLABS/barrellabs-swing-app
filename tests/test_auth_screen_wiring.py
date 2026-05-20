"""Wiring tests for the premium split-screen auth_screen module.

These tests don't need live Streamlit / Supabase — they verify the
import-level contract:

  - auth_screen.render_auth_screen and render_recovery_screen exist
    and have the expected signatures.
  - app.py imports the two functions from auth_screen (and doesn't
    redefine them).
  - The recovery URL detection block in app.py is intact (JS shim +
    token_hash flow + access_token fallback).
  - player_storage.authenticate / create_account still exist with the
    legacy signatures the new forms call.

Run from project root:

    python3 -m unittest tests.test_auth_screen_wiring
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_streamlit_stub() -> types.ModuleType:
    stub = types.ModuleType("streamlit")
    stub.session_state = {}

    def _passthrough_decorator(*dargs, **dkwargs):
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def inner(fn):
            return fn

        return inner

    def _noop(*a, **k):
        return None

    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    stub.cache_resource = _passthrough_decorator
    stub.cache_data = _passthrough_decorator
    for name in (
        "markdown", "write", "error", "warning", "caption", "rerun",
        "stop", "toast", "success", "info", "image", "code", "header",
        "subheader", "title", "divider",
    ):
        setattr(stub, name, _noop)
    stub.container = lambda *a, **k: _Ctx()
    stub.columns = lambda n, **k: [_Ctx() for _ in range(
        n if isinstance(n, int) else len(n))]
    stub.expander = lambda *a, **k: _Ctx()
    stub.spinner = lambda *a, **k: _Ctx()
    stub.form = lambda *a, **k: _Ctx()
    stub.form_submit_button = lambda *a, **k: False
    stub.button = lambda *a, **k: False
    stub.checkbox = lambda *a, **k: False
    stub.text_input = lambda *a, **k: ""
    stub.number_input = lambda *a, **k: 0
    stub.selectbox = lambda *a, **k: ""
    stub.radio = lambda *a, **k: ""
    stub.download_button = lambda *a, **k: None
    stub.file_uploader = lambda *a, **k: None
    stub.query_params = {}

    _c1 = types.ModuleType("streamlit.components.v1")
    _c1.html = _noop
    _c1.iframe = _noop
    _c0 = types.ModuleType("streamlit.components")
    _c0.v1 = _c1
    stub.components = _c0
    sys.modules["streamlit.components"] = _c0
    sys.modules["streamlit.components.v1"] = _c1
    return stub


class AuthScreenModuleTest(unittest.TestCase):
    """The new module must expose both entry points and a non-empty CSS."""

    def test_imports_under_stub(self):
        stub = _make_streamlit_stub()
        prev = {
            k: sys.modules.get(k)
            for k in (
                "streamlit", "streamlit.components",
                "streamlit.components.v1",
            )
        }
        sys.modules["streamlit"] = stub
        try:
            mod = importlib.import_module("auth_screen")
            importlib.reload(mod)
            self.assertTrue(hasattr(mod, "render_auth_screen"))
            self.assertTrue(hasattr(mod, "render_recovery_screen"))
            # Both must be callable with zero positional args.
            sig_auth = inspect.signature(mod.render_auth_screen)
            sig_rec = inspect.signature(mod.render_recovery_screen)
            self.assertEqual(len(sig_auth.parameters), 0)
            self.assertEqual(len(sig_rec.parameters), 0)
            # CSS blob exists, non-trivial, and uses the keyed scope.
            self.assertIn("<style>", mod._AUTH_CSS)
            self.assertIn(".st-key-auth_root", mod._AUTH_CSS)
            self.assertIn(".st-key-auth_panel", mod._AUTH_CSS)
            self.assertIn(".st-key-auth_hero", mod._AUTH_CSS)
            # Hero copy must include the primary message verbatim.
            hero = mod._hero_html()
            self.assertIn("Find your", hero)
            self.assertIn("swing twin", hero)
            # Feature ladder has at least 4 rows (v2 tightened from 5
            # to 4 to make the hero stack denser; the 5th "Track your
            # progress" point folded into the testimonial meta).
            self.assertGreaterEqual(len(mod._FEATURE_ROWS), 4)
            self.assertLessEqual(len(mod._FEATURE_ROWS), 6)
        finally:
            for k, v in prev.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


class AppPyDelegatesAuthScreenTest(unittest.TestCase):
    """app.py must import the new functions from auth_screen and must
    not redefine them locally — otherwise the old code path could ship."""

    @classmethod
    def setUpClass(cls):
        cls.app_src = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    def test_imports_from_auth_screen(self):
        self.assertIn(
            "from auth_screen import",
            self.app_src,
            "app.py is not importing from auth_screen.",
        )
        # Both names must be present in the import.
        m = re.search(
            r"from auth_screen import\s*\(([^)]+)\)",
            self.app_src,
        )
        self.assertIsNotNone(
            m, "auth_screen import is not a parenthesized form."
        )
        names = m.group(1)
        self.assertIn("render_auth_screen", names)
        self.assertIn("render_recovery_screen", names)

    def test_no_local_redefinitions(self):
        """The legacy local defs must be gone — otherwise they'd shadow
        the import and the redesign would never appear."""
        # `def render_auth_screen(` / `def render_recovery_screen(` must
        # not appear at column 0 anywhere in app.py.
        for name in ("render_auth_screen", "render_recovery_screen"):
            self.assertIsNone(
                re.search(rf"^def {name}\(", self.app_src, re.M),
                f"app.py still defines {name}() locally — it would "
                "shadow the auth_screen import."
            )

    def test_recovery_url_detection_intact(self):
        """The recovery URL detection (JS shim + token_hash flow +
        access_token fallback) lives in app.py and must NOT have been
        deleted alongside the auth-renderer move."""
        # 1. JS shim that rewrites the hash fragment to query string.
        self.assertIn(
            "indexOf(\"access_token=\")",
            self.app_src,
            "Recovery JS shim was removed from app.py.",
        )
        # 2. token_hash flow.
        self.assertIn("consume_recovery_token_hash", self.app_src)
        # 3. access_token fallback.
        self.assertIn("consume_recovery_url", self.app_src)
        # 4. The `recovery_mode` session-state flag gate.
        self.assertIn('st.session_state.get("recovery_mode")', self.app_src)

    def test_call_sites_present(self):
        """Both entry points must still be called from the auth gate."""
        self.assertIn("render_auth_screen()", self.app_src)
        self.assertIn("render_recovery_screen()", self.app_src)


class PlayerStorageContractTest(unittest.TestCase):
    """auth_screen.py calls player_storage.authenticate(email, password)
    and player_storage.create_account(name, email, password, handedness,
    height_in, weight_lb). Both must still match those signatures."""

    @classmethod
    def setUpClass(cls):
        stub = _make_streamlit_stub()
        cls._real_st = sys.modules.get("streamlit")
        sys.modules["streamlit"] = stub
        try:
            cls.ps = importlib.import_module("player_storage")
            importlib.reload(cls.ps)
        finally:
            if cls._real_st is not None:
                sys.modules["streamlit"] = cls._real_st
            else:
                del sys.modules["streamlit"]

    def test_authenticate_signature(self):
        sig = inspect.signature(self.ps.authenticate)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["email", "password"])

    def test_create_account_signature(self):
        sig = inspect.signature(self.ps.create_account)
        params = list(sig.parameters.keys())
        # Must accept these in any order with these names — the form
        # calls them by keyword.
        for required in ("name", "email", "password", "handedness",
                         "height_in", "weight_lb"):
            self.assertIn(
                required, params,
                f"player_storage.create_account no longer accepts "
                f"{required!r}; the signup form will break."
            )


class AuthScreenCopyTest(unittest.TestCase):
    """User-facing copy must match the brief verbatim — these are easy
    to accidentally edit when polishing CSS."""

    @classmethod
    def setUpClass(cls):
        cls.src = (PROJECT_ROOT / "auth_screen.py").read_text(encoding="utf-8")

    def test_primary_message(self):
        self.assertIn("Find your", self.src)
        self.assertIn("swing twin", self.src)

    def test_button_copy_login(self):
        self.assertIn("Access your Performance Lab", self.src)

    def test_button_copy_signup(self):
        self.assertIn("Start your free analysis", self.src)

    def test_welcome_back_headline(self):
        self.assertIn("Welcome back", self.src)

    def test_create_account_headline(self):
        self.assertIn("Create your account", self.src)


if __name__ == "__main__":
    unittest.main()
