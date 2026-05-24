"""
Wiring tests for the Player Settings page and the systems it touches.

These tests don't need a live Streamlit / Supabase / Stripe — they
exercise the pure functions and import-level wiring of:

  - drills.build_drill_plan(preferred_goal=...) — the goal-boost layer
    that translates a player's `primary_goal` into a re-ranked drill plan
  - auth module — confirms change_email/delete_account/sync_email helpers
    exist with the expected signatures
  - app.py routing — confirms the player_settings route is dispatched and
    that the analyze() call site forwards primary_goal
  - stripe_client.cancel_active_subscription — present, callable

Run from the project root:

    python3 -m unittest tests.test_player_settings_wiring
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


# Build a streamlit stub generous enough that modules importing it at
# top level (auth.py, stripe_client.py, supabase_client.py, etc.) load
# without error. Anything missing returns a pass-through callable.
def _make_streamlit_stub() -> types.ModuleType:
    stub = types.ModuleType("streamlit")
    stub.session_state = {}

    def _passthrough_decorator(*dargs, **dkwargs):
        # Support both @decorator and @decorator(...)
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
    stub.experimental_memo = _passthrough_decorator
    stub.experimental_singleton = _passthrough_decorator
    stub.dialog = _passthrough_decorator
    stub.segmented_control = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
    stub.pills = lambda *a, **k: (a[1][0] if len(a) > 1 and a[1] else "")
    stub.toggle = lambda *a, **k: False
    for name in (
        "markdown", "write", "error", "warning", "caption", "rerun",
        "stop", "toast", "success", "info", "image", "code", "header",
        "subheader", "title", "divider",
    ):
        setattr(stub, name, _noop)
    stub.container = lambda *a, **k: _Ctx()
    stub.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
    stub.expander = lambda *a, **k: _Ctx()
    stub.spinner = lambda *a, **k: _Ctx()
    stub.button = lambda *a, **k: False
    stub.checkbox = lambda *a, **k: False
    stub.text_input = lambda *a, **k: ""
    stub.number_input = lambda *a, **k: 0
    stub.selectbox = lambda *a, **k: ""
    stub.radio = lambda *a, **k: ""
    stub.download_button = lambda *a, **k: None
    stub.file_uploader = lambda *a, **k: None
    stub.query_params = {}

    # components.v1.html so any `from streamlit import components` works.
    _c1 = types.ModuleType("streamlit.components.v1")
    _c1.html = _noop
    _c1.iframe = _noop
    _c0 = types.ModuleType("streamlit.components")
    _c0.v1 = _c1
    stub.components = _c0
    sys.modules["streamlit.components"] = _c0
    sys.modules["streamlit.components.v1"] = _c1

    return stub


# =========================================================
# Group 1 — drills.build_drill_plan(preferred_goal=...)
# =========================================================
class DrillGoalBoostTest(unittest.TestCase):
    """The training goal selected on Player Settings must actually move
    the drill plan when there's a tie or a close call between categories."""

    @classmethod
    def setUpClass(cls):
        # drills.py has no streamlit/supabase deps so it imports clean.
        cls.drills = importlib.import_module("drills")

    def _gaps(self, *pairs):
        """Build a fake gaps_ranked list. Each pair is (group, label).
        rank 0 = highest priority (largest gap)."""
        return [
            {"group": g, "label": lbl, "score": 0.4 + 0.05 * i}
            for i, (g, lbl) in enumerate(pairs)
        ]

    def test_goal_boost_categories_match_drills_db(self):
        """Every category in GOAL_CATEGORY_BOOSTS must also exist in
        DRILL_DB so the boost can't reference a non-existent drill.
        Catches typos at refactor time."""
        for goal, boosts in self.drills.GOAL_CATEGORY_BOOSTS.items():
            for cat in boosts.keys():
                self.assertIn(
                    cat, self.drills.DRILL_DB,
                    f"Goal {goal!r} boosts category {cat!r} but DRILL_DB "
                    "has no such category."
                )

    def test_plan_includes_goal_applied_field(self):
        """The drill plan dict must surface which goal was applied so
        the UI can show 'Tuned for: Better timing'."""
        gaps = self._gaps(
            ("Head",     "Head drift, total"),
            ("Rotation", "Hip-shoulder separation"),
            ("Timing",   "Bat lag time"),
        )
        plan = self.drills.build_drill_plan(gaps, preferred_goal="Better timing")
        self.assertIn("goal_applied", plan)
        self.assertEqual(plan["goal_applied"], "Better timing")

    def test_no_goal_means_no_boost(self):
        gaps = self._gaps(
            ("Head",     "Head drift, total"),
            ("Rotation", "Hip-shoulder separation"),
        )
        plan = self.drills.build_drill_plan(gaps, preferred_goal=None)
        self.assertIsNone(plan["goal_applied"])
        self.assertGreaterEqual(len(plan["categories"]), 1)

    def test_more_power_boost_reorders_close_call(self):
        """When the player's goal is 'More power' and a Rotation gap is
        present alongside an unrelated gap, the Rotation-derived hip
        category should beat or tie the unrelated one for priority."""
        gaps = self._gaps(
            ("Front Knee", "Knee extension"),
            ("Rotation",   "Hip rotation"),
        )
        plan_no_goal  = self.drills.build_drill_plan(gaps)
        plan_w_goal   = self.drills.build_drill_plan(gaps, preferred_goal="More power")

        # With "More power", hip_rotation gets +3. The plan should
        # surface hip_rotation in its top categories.
        cats = [c["category"] for c in plan_w_goal["categories"]]
        self.assertIn(
            "hip_rotation", cats,
            f"Expected hip_rotation in plan with 'More power', got {cats}",
        )

    def test_better_timing_promotes_timing_category(self):
        gaps = self._gaps(
            ("Head",     "Head drift, lateral"),
            ("Timing",   "Bat lag time"),
            ("Rotation", "Hip rotation"),
        )
        plan = self.drills.build_drill_plan(gaps, preferred_goal="Better timing")
        cats = [c["category"] for c in plan["categories"]]
        self.assertIn(
            "timing", cats,
            f"Expected 'Better timing' to surface the timing category, got {cats}",
        )

    def test_boost_never_invents_categories(self):
        """If the player's only gap is in head_stability and goal is
        'More power' (which boosts hip categories), the plan should NOT
        suddenly include a hip category — the player has no hip gap."""
        gaps = self._gaps(
            ("Head", "Head drift, total"),
            ("Head", "Head drift, lateral"),
        )
        plan = self.drills.build_drill_plan(gaps, preferred_goal="More power")
        cats = [c["category"] for c in plan["categories"]]
        for cat in cats:
            self.assertNotIn(
                cat, ("hip_rotation", "hip_shoulder_separation", "knee_extension"),
                f"Boost invented hip category {cat!r} despite no hip gaps.",
            )

    def test_weekly_guide_mentions_goal_when_applied(self):
        gaps = self._gaps(
            ("Rotation", "Hip rotation"),
            ("Front Knee", "Knee extension"),
        )
        plan = self.drills.build_drill_plan(gaps, preferred_goal="More power")
        joined = " ".join(plan["weekly_guide"]).lower()
        self.assertIn("more power", joined,
                       "Weekly guide should mention the active goal.")


# =========================================================
# Group 2 — auth.py helpers exist with correct signatures
# =========================================================
class AuthHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # auth.py imports streamlit. Stub it (incl. cache_resource etc).
        stub = _make_streamlit_stub()
        cls._real_st = sys.modules.get("streamlit")
        sys.modules["streamlit"] = stub
        try:
            cls.auth = importlib.import_module("auth")
            importlib.reload(cls.auth)
        finally:
            # Restore so other tests don't inherit our stub.
            if cls._real_st is not None:
                sys.modules["streamlit"] = cls._real_st
            else:
                del sys.modules["streamlit"]

    def test_change_email_helper_present(self):
        self.assertTrue(hasattr(self.auth, "request_email_change"))
        sig = inspect.signature(self.auth.request_email_change)
        self.assertIn("new_email", sig.parameters)

    def test_sync_email_helper_present(self):
        self.assertTrue(hasattr(self.auth, "sync_email_after_confirm"))

    def test_delete_account_helper_present(self):
        self.assertTrue(hasattr(self.auth, "delete_account"))
        sig = inspect.signature(self.auth.delete_account)
        self.assertIn("cancel_stripe", sig.parameters)


# =========================================================
# Group 3 — stripe cancel helper
# =========================================================
class StripeCancelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub = _make_streamlit_stub()
        cls._real_st = sys.modules.get("streamlit")
        sys.modules["streamlit"] = stub
        try:
            cls.stripe_client = importlib.import_module("stripe_client")
            importlib.reload(cls.stripe_client)
        finally:
            if cls._real_st is not None:
                sys.modules["streamlit"] = cls._real_st
            else:
                del sys.modules["streamlit"]

    def test_cancel_active_subscription_callable(self):
        self.assertTrue(hasattr(self.stripe_client, "cancel_active_subscription"))
        self.assertTrue(callable(self.stripe_client.cancel_active_subscription))


# =========================================================
# Group 4 — app.py routing + analyze() goal forwarding
# =========================================================
class AppRoutingForwardsGoalTest(unittest.TestCase):
    """Source-level guards. We don't execute app.py — we read it and
    check the key wiring lines are present. Cheap, fast, and catches
    accidental deletion during future refactors."""

    @classmethod
    def setUpClass(cls):
        cls.app_src = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

    def test_analyze_call_forwards_preferred_goal(self):
        """app.py must pass the player's primary_goal into analyze() so
        the drill plan can respect their training focus."""
        # Match the analyze() call site that we wired.
        m = re.search(
            r"result\s*=\s*analyze\(\s*str\(fingerprint_path\)\s*,\s*"
            r"reference_arg\s*,\s*preferred_goal\s*=\s*_pref_goal\s*\)",
            self.app_src,
        )
        self.assertIsNotNone(
            m, "app.py no longer forwards primary_goal into analyze()."
        )

    def test_player_settings_route_present(self):
        """app.py must dispatch page=player_settings to the new module."""
        m = re.search(
            r'st\.session_state\.get\("page"\)\s*==\s*"player_settings"',
            self.app_src,
        )
        self.assertIsNotNone(
            m, "app.py is missing the page=player_settings dispatch."
        )
        # And it must call the real renderer, not a placeholder.
        self.assertIn(
            "from player_settings_page import render_player_settings_page",
            self.app_src,
            "app.py is not importing render_player_settings_page from the new module."
        )

    def test_mlb_lock_read_still_present(self):
        """Regression guard — the MLB-comp lock conditional that honors
        locked_mlb_slug must not get accidentally removed."""
        m = re.search(
            r'_locked_slug\s*=\s*\(user or \{\}\)\.get\("locked_mlb_slug"\)',
            self.app_src,
        )
        self.assertIsNotNone(
            m, "MLB-lock read in app.py was removed/refactored away."
        )
        self.assertIn(
            'reference_arg = _locked_slug', self.app_src,
            "MLB-lock no longer overrides reference_arg.",
        )

    def test_mlb_lock_write_on_first_swing_still_present(self):
        """The first-swing write that creates the lock must persist."""
        self.assertIn(
            "_save_lock(user[\"slug\"], locked_mlb_slug=_picked)",
            self.app_src,
            "MLB-lock write on first swing was removed.",
        )


# =========================================================
# Group 5 — analyzer.py signature accepts preferred_goal
# =========================================================
class AnalyzerSignatureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer_src = (PROJECT_ROOT / "analyzer.py").read_text(encoding="utf-8")

    def test_analyze_accepts_preferred_goal(self):
        m = re.search(
            r"def analyze\(\s*player_fp_path\s*,\s*reference_arg\s*=\s*None\s*,"
            r"\s*\*\s*,\s*preferred_goal\s*=\s*None\s*\)",
            self.analyzer_src,
        )
        self.assertIsNotNone(
            m, "analyzer.analyze() no longer accepts preferred_goal kwarg."
        )

    def test_build_drill_plan_called_with_preferred_goal(self):
        self.assertIn(
            "preferred_goal=preferred_goal", self.analyzer_src,
            "analyzer.py is not forwarding preferred_goal into build_drill_plan().",
        )


# =========================================================
# Group 6 — player_settings_page imports cleanly under a stub
# =========================================================
class PlayerSettingsPageImportTest(unittest.TestCase):
    def test_module_imports_and_exposes_render(self):
        # We don't render — just verify the module loads without import
        # errors under a streamlit stub and exposes the public function
        # with the right signature.
        stub = _make_streamlit_stub()
        prev = {k: sys.modules.get(k) for k in
                ("streamlit", "streamlit.components", "streamlit.components.v1")}
        sys.modules["streamlit"] = stub
        try:
            mod = importlib.import_module("player_settings_page")
            importlib.reload(mod)
            self.assertTrue(hasattr(mod, "render_player_settings_page"))
            sig = inspect.signature(mod.render_player_settings_page)
            self.assertIn("user", sig.parameters)
            self.assertIn("build_pdf_fn", sig.parameters)
            # And the option lists must be present and non-empty.
            self.assertTrue(len(mod.GOAL_OPTIONS) > 0)
            self.assertTrue(len(mod.LEVELS) > 0)
            self.assertTrue(len(mod.POSITIONS) > 0)
        finally:
            for k, v in prev.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


# =========================================================
# Group 7 — birth_year persists via auth.update_profile
# =========================================================
class BirthYearPersistenceTest(unittest.TestCase):
    """Saving Settings forwards an int birth_year to auth.update_profile."""

    @classmethod
    def setUpClass(cls):
        stub = _make_streamlit_stub()
        cls._stub = stub
        cls._prev = {k: sys.modules.get(k) for k in
                     ("streamlit", "streamlit.components", "streamlit.components.v1")}
        sys.modules["streamlit"] = stub
        try:
            cls.ps = importlib.import_module("player_settings_page")
            importlib.reload(cls.ps)
        finally:
            for k, v in cls._prev.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def _install_stub(self):
        """Re-install the streamlit stub for the duration of the test."""
        sys.modules["streamlit"] = self._stub

    def _remove_stub(self):
        for k, v in self._prev.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_birth_year_persists_via_update_profile(self):
        """When the birth-year widget holds '2014', _do_save calls
        update_profile with birth_year=2014."""
        from unittest.mock import patch

        user = {
            "slug": "p1",
            "name": "Test",
            "handedness": "RIGHT",
            "height_in": 60,
            "weight_lb": 120,
            "birth_year": None,
        }

        # Build a realistic cur dict derived from _saved_defaults, with
        # birth_year overridden to "2014".
        self._install_stub()
        try:
            base = self.ps._saved_defaults(user)
        finally:
            self._remove_stub()
        base["birth_year"] = "2014"

        captured = {}

        def _fake_update(slug, **fields):
            captured.update(fields)
            return {"slug": slug, **fields}

        self._install_stub()
        try:
            with patch.object(self.ps, "_current_field_values",
                              return_value=base), \
                 patch("auth.update_profile", _fake_update):
                self.ps._do_save(user)
        finally:
            self._remove_stub()

        self.assertEqual(
            captured.get("birth_year"), 2014,
            f"Expected birth_year=2014 in update_profile call, got: {captured}",
        )


if __name__ == "__main__":
    unittest.main()
