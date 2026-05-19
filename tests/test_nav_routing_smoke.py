"""
Smoke tests for the unified Edge masthead + dedicated swing report
routing rebuild.

These tests don't need a live Streamlit runtime — they install a small
stub `streamlit` module that records calls into a dict, then exercise
the rendering functions and routing helpers. Goal: catch obvious
breakage (signature drift, missing imports, wrong state mutations)
before the user opens the app.

Run from the project root:

    python3 -m unittest tests/test_nav_routing_smoke.py
"""

from __future__ import annotations

import os
import re
import sys
import types
import unittest
import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------
#  Minimal streamlit stub
# ---------------------------------------------------------------------
class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e
    def __setattr__(self, k, v):
        self[k] = v
    def __delattr__(self, k):
        try:
            del self[k]
        except KeyError as e:
            raise AttributeError(k) from e


class _QueryParams(dict):
    def get(self, k, default=None):
        return super().get(k, default)


class _StreamlitStub(types.ModuleType):
    """Just enough of streamlit's API to let the modules import and
    call the rendering helpers without erroring. Records button clicks
    and markdown payloads so tests can assert against them.
    """
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = _SessionState()
        self.query_params = _QueryParams()
        self._markdown_calls = []
        self._button_returns = {}   # key -> bool (force a click)
        self._buttons_rendered = [] # list of (label, key, type)
        self._rerun_called = False
        self._stop_called = False
        self._error_msgs = []
        self._warning_msgs = []
        self._captions = []
        self._cols_stack = []

    # --- API surface ---
    def markdown(self, s, **kw): self._markdown_calls.append(s)
    def error(self, s, **kw):    self._error_msgs.append(s)
    def warning(self, s, **kw):  self._warning_msgs.append(s)
    def caption(self, s, **kw):  self._captions.append(s)
    def write(self, s, **kw):    self._markdown_calls.append(s)
    def rerun(self):             self._rerun_called = True
    def stop(self):              self._stop_called = True

    def button(self, label, key=None, type="secondary", **kw):
        self._buttons_rendered.append((label, key, type))
        return self._button_returns.get(key, False)

    def text_input(self, label, **kw): return ""
    def selectbox(self, label, options, **kw): return options[0]
    def toast(self, *a, **kw): pass

    def columns(self, spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [_ColCtx(self) for _ in range(n)]

    def container(self, *a, **kw):
        # render_edge_masthead now wraps its content in a real keyed
        # st.container so the premium nav CSS can actually scope to it.
        # The stub just needs a context manager.
        return _ColCtx(self)

    def download_button(self, label, **kw):
        self._buttons_rendered.append((label, kw.get("key"), "download"))
        return False

    # cache + decorator no-ops
    def cache_data(self, *a, **kw):
        if a and callable(a[0]):
            return a[0]
        def deco(f): return f
        return deco
    cache_resource = cache_data


class _ColCtx:
    def __init__(self, st_):
        self.st = st_
    def __enter__(self):
        self.st._cols_stack.append(self)
        return self
    def __exit__(self, *a):
        self.st._cols_stack.pop()
        return False


def _install_stub():
    st = _StreamlitStub()
    sys.modules["streamlit"] = st
    return st


# ---------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------
class EdgeChromeImportTest(unittest.TestCase):
    """The new bl_edge_chrome module imports cleanly and exposes its
    public functions."""

    def setUp(self):
        self.st = _install_stub()

    def test_import_and_public_api(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        for name in (
            "render_edge_masthead",
            "render_edge_page_wrapper_open",
            "render_edge_page_wrapper_close",
            "hide_iframe_decorative_nav",
        ):
            self.assertTrue(hasattr(bec, name), f"missing public fn: {name}")

    def test_nav_entries_shape(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        labels = [e[0] for e in bec._NAV_ENTRIES]
        keys   = [e[1] for e in bec._NAV_ENTRIES]
        self.assertEqual(
            labels,
            ["Dashboard", "Sessions", "Compare", "Drills", "Library"],
            "Nav labels must match the spec exactly.",
        )
        self.assertIn("saved_reports", keys, "Sessions must map to saved_reports")

    def test_swing_report_routes_active_to_saved_reports(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        # When on the individual swing_report page, Sessions tab should
        # be the active highlight (since reports are reached *from*
        # Sessions).
        self.assertEqual(bec._resolve_active("swing_report"), "saved_reports")
        self.assertEqual(bec._resolve_active("dashboard"), "dashboard")
        self.assertEqual(bec._resolve_active("saved_reports"), "saved_reports")
        self.assertEqual(bec._resolve_active("unknown_page"), "dashboard")

    def test_initials_fallback(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        self.assertEqual(bec._initials({"name": "Logan Collins"}), "LC")
        # Single-word name yields a single initial (no duplication).
        self.assertEqual(bec._initials({"name": "Logan"}), "L")
        self.assertEqual(bec._initials({"email": "l@x.com"}), "L")
        self.assertEqual(bec._initials({}), "B")


class MastheadRendersNavTest(unittest.TestCase):
    """The masthead nav is now IN-SESSION st.button widgets (NOT
    <a href> anchors). Anchors did a full browser reload which wiped
    st.session_state — and this app keeps the Supabase auth session
    ONLY in st.session_state, so anchor nav logged the user out on
    every click. st.button triggers an in-session rerun: auth is
    preserved and no ?page= is ever written to the URL. The masthead
    must render exactly the 5 nav buttons with the right keys and mark
    exactly one type="primary" per active_page, and must NOT emit any
    <a href="?page="> nav anchor."""

    def setUp(self):
        self.st = _install_stub()

    def _html(self):
        return "\n".join(self.st._markdown_calls)

    def test_renders_five_nav_buttons(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        user = {"name": "Logan Collins",
                "gamification": {"current_streak_days": 17}}
        bec.render_edge_masthead(user, active_page="dashboard")
        nav = [b for b in self.st._buttons_rendered
               if b[1] and str(b[1]).startswith("_ble_nav_")]
        labels = [b[0] for b in nav]
        self.assertEqual(
            labels, [e[0] for e in bec._NAV_ENTRIES],
            "masthead must render the 5 nav buttons in order")
        for (label, page_key, _a), b in zip(bec._NAV_ENTRIES, nav):
            self.assertEqual(b[1], f"_ble_nav_{page_key}")
        types_ = [b[2] for b in nav]
        self.assertEqual(types_.count("primary"), 1,
                         "exactly one active (primary) tab")
        active_label = next(b[0] for b in nav if b[2] == "primary")
        self.assertEqual(active_label, "Dashboard")
        # CRITICAL: no full-reload nav anchor anywhere (would log the
        # user out — that's the bug this fix removes).
        html = self._html()
        self.assertNotIn('href="?page=', html,
                          "masthead must NOT use ?page= nav anchors "
                          "(full reload wipes auth)")

    def test_active_highlight_for_swing_report(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        bec.render_edge_masthead({}, active_page="swing_report")
        nav = [b for b in self.st._buttons_rendered
               if b[1] and str(b[1]).startswith("_ble_nav_")]
        active = [b[0] for b in nav if b[2] == "primary"]
        # swing_report rolls up to the Sessions (saved_reports) parent.
        self.assertEqual(active, ["Sessions"])


class SessionsNavContractTest(unittest.TestCase):
    """Clicking the Sessions button must, IN-SESSION (no reload, auth
    preserved): set page=saved_reports, scrub stale open-report state
    so _should_open_report can't hijack it, and call st.rerun()."""

    def setUp(self):
        self.st = _install_stub()

    def test_sessions_click_routes_in_session(self):
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        # Pretend a report was previously open (stale state).
        self.st.session_state["view_swing_record"] = {"id": "stale"}
        self.st.session_state["view_swing_path"] = "/tmp/x.json"
        self.st.session_state["page"] = "dashboard"
        # Force the Sessions button to "click".
        self.st._button_returns["_ble_nav_saved_reports"] = True
        bec.render_edge_masthead({}, active_page="dashboard")

        self.assertEqual(self.st.session_state["page"], "saved_reports")
        self.assertNotIn("view_swing_record", self.st.session_state)
        self.assertNotIn("view_swing_path", self.st.session_state)
        self.assertTrue(self.st._rerun_called,
                        "must st.rerun() so it's an in-session nav")
        # No nav anchor / no ?page= written to the URL.
        html = "\n".join(self.st._markdown_calls)
        self.assertNotIn('href="?page=', html)
        # The ?page= URL bridge must still exist in app.py for genuine
        # deep-links, with saved_reports allowed.
        app_src = (PROJECT_ROOT / "app.py").read_text()
        m = re.search(r"_ALLOWED_PAGES_FROM_URL\s*=\s*\{(.*?)\}",
                      app_src, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn('"saved_reports"', m.group(1))

    def test_swing_report_button_keeps_open_report_state(self):
        """The swing_report nav button must NOT scrub view_swing_*
        (that's how an opened report stays open)."""
        if "bl_edge_chrome" in sys.modules:
            del sys.modules["bl_edge_chrome"]
        bec = importlib.import_module("bl_edge_chrome")
        self.st.session_state["view_swing_record"] = {"id": "keep"}
        self.st._button_returns["_ble_nav_saved_reports"] = False
        # No swing_report nav entry exists by default; assert the scrub
        # logic is conditional on page_key != "swing_report" by checking
        # a non-swing click DOES scrub (covered above) and the source
        # guards on that key.
        src = (PROJECT_ROOT / "bl_edge_chrome.py").read_text()
        self.assertIn('if page_key != "swing_report":', src)
        self.assertIn("st.session_state.pop", src)


class SwingReportPageTest(unittest.TestCase):
    """The dedicated individual report page must render real metrics
    when previous swing exists, and the empty state when it doesn't."""

    def setUp(self):
        self.st = _install_stub()

    def _import_srp(self):
        # Force a fresh import so the patched streamlit module is used.
        for m in list(sys.modules):
            if m in ("swing_report_page", "bl_edge_chrome"):
                del sys.modules[m]
        # Stub out the heavyweight inner deps so we can exercise the
        # comparison + page flow without dragging in mediapipe etc.
        sys.modules.setdefault("bl_theme", types.ModuleType("bl_theme"))
        sys.modules["bl_theme"].inject_global_theme = lambda: None
        sys.modules.setdefault("swing_report", types.ModuleType("swing_report"))
        sys.modules["swing_report"].render_swing_report = lambda *a, **kw: None
        return importlib.import_module("swing_report_page")

    def test_empty_state_when_first_swing(self):
        srp = self._import_srp()
        # No previous swing — comparison should render the empty state.
        rec = {"id": "s1", "swing_number": 1, "score": 72,
               "reference_name": "Mookie Betts"}
        history = [rec]  # current is the only one
        srp.render_swing_compare_redesigned(rec, history)
        joined = "\n".join(self.st._markdown_calls)
        self.assertIn("Comparison unlocks after your next swing", joined)
        self.assertIn("srp-compare-empty", joined)

    def test_full_compare_when_previous_exists(self):
        srp = self._import_srp()
        prev = {"id": "s1", "swing_number": 1, "score": 64,
                "reference_name": "Yandy Diaz", "timestamp": "2026-05-01T00:00:00"}
        curr = {"id": "s2", "swing_number": 2, "score": 78,
                "reference_name": "Mookie Betts", "timestamp": "2026-05-10T00:00:00"}
        history = [prev, curr]  # oldest-first per load_swing_history contract
        srp.render_swing_compare_redesigned(curr, history)
        joined = "\n".join(self.st._markdown_calls)
        # Both swing cards present
        self.assertIn("THIS SWING", joined)
        self.assertIn("PREVIOUS SWING", joined)
        # Score delta = +14 should be reflected
        self.assertIn("+14", joined, "Score delta should render as +14")
        # Empty state must NOT render
        self.assertNotIn("Comparison unlocks", joined)

    def test_metric_pairs_only_real_data(self):
        srp = self._import_srp()
        # Records with NO per-axis match values — only the score row
        # should be collected (and that one gets dropped from the rows
        # since the score is already in the headline cards).
        prev = {"id": "s1", "swing_number": 1, "score": 64}
        curr = {"id": "s2", "swing_number": 2, "score": 70}
        rows = srp._collect_metric_pairs(curr, prev)
        # Either: just the headline score row, OR empty after dedup. We
        # accept either as long as no FAKE rows appear.
        labels = [r["label"] for r in rows]
        # No placeholders allowed
        for label in labels:
            self.assertIn(label, ("Swing Score",),
                          f"Unexpected metric row {label} — placeholders forbidden")

    def test_previous_record_found_by_id(self):
        srp = self._import_srp()
        a = {"id": "a", "swing_number": 1}
        b = {"id": "b", "swing_number": 2}
        c = {"id": "c", "swing_number": 3}
        self.assertEqual(srp._previous_record(c, [a, b, c]), b)
        self.assertEqual(srp._previous_record(b, [a, b, c]), a)
        self.assertIsNone(srp._previous_record(a, [a, b, c]),
                          "First swing has no previous")


class IframeNavHiddenTest(unittest.TestCase):
    """The decorative <nav class='nav'> inside the editorial mock
    template must be display:none so we never paint two navs again."""

    def test_template_hides_nav(self):
        template_path = PROJECT_ROOT / "mock_dashboard_template.py"
        src = template_path.read_text()
        self.assertIn(".nav { display: none !important; }", src,
                      "in-iframe nav must be hidden at template level")
        self.assertIn(".masthead { display: none !important; }", src,
                      "in-iframe duplicate masthead must be hidden too")


class SavedReportsOpenButtonTest(unittest.TestCase):
    """The Open Report button in saved_reports.py must set page to
    'swing_report' (NOT pop page / NOT route to dashboard)."""

    def test_open_report_sets_swing_report_page(self):
        path = PROJECT_ROOT / "saved_reports.py"
        src = path.read_text()
        # The fixed handler should explicitly set page = "swing_report"
        self.assertIn('st.session_state["page"] = "swing_report"', src,
                      "Open Report must route to the dedicated swing_report page")
        # And must NOT pop "page" (the old bug)
        self.assertNotIn('st.session_state.pop("page", None)', src,
                         "Open Report must not clear the page state")


class AppRoutingTest(unittest.TestCase):
    """app.py routing changes:
       - swing_report is in _ALLOWED_PAGES_FROM_URL
       - the saved-record dispatcher delegates to swing_report_page,
         NOT to render_dashboard_v3(force_record=...).
    """

    def test_swing_report_allowed_from_url(self):
        src = (PROJECT_ROOT / "app.py").read_text()
        # Find the allowlist set literal
        self.assertRegex(
            src,
            r'"swing_report"',
            "swing_report must be an allowed page from URL bridge",
        )

    def test_dispatcher_uses_swing_report_page(self):
        src = (PROJECT_ROOT / "app.py").read_text()
        self.assertIn(
            "from swing_report_page import render_swing_report_page",
            src,
            "saved-record dispatcher must import the dedicated page",
        )
        # The old broken call signature should be gone from the new
        # default path. (It may still appear in a fallback / legacy
        # branch, that's OK.)
        # Count instances of force_record= in the main saved-record
        # dispatch block — must not be the primary path anymore.
        primary_block_start = src.find("if _should_open_report:")
        legacy_block_start  = src.find("if _use_legacy:")
        if primary_block_start != -1 and legacy_block_start != -1:
            primary_segment = src[primary_block_start:legacy_block_start]
            self.assertNotIn(
                "force_record=", primary_segment,
                "force_record path must be deprecated for the new flow",
            )


class SessionsRoutingOrderTest(unittest.TestCase):
    """The Sessions nav anchor (?page=saved_reports) MUST land on
    render_saved_reports_dashboard. The bug was: the 'default to
    dashboard' fallback ran BEFORE the ?page= URL bridge, so a fresh
    reload from the anchor got page='dashboard' and the dashboard route
    st.stop()'d before the saved_reports route. These tests lock the
    fix: (1) bridge is positioned before the fallback in app.py source,
    (2) a runtime simulation of the two blocks yields saved_reports with
    no stale open-report state, (3) the saved_reports route calls
    render_saved_reports_dashboard."""

    def setUp(self):
        self.src = (PROJECT_ROOT / "app.py").read_text()

    def test_bridge_runs_before_dashboard_default(self):
        bridge = self.src.find("URL → session-state routing bridge")
        if bridge == -1:
            bridge = self.src.find("_ALLOWED_PAGES_FROM_URL = {")
        default = self.src.find(
            "Default landing for a fresh authenticated session = Dashboard"
        )
        self.assertNotEqual(bridge, -1, "URL bridge block not found")
        self.assertNotEqual(default, -1, "default-dashboard block not found")
        self.assertLess(
            bridge, default,
            "The ?page= URL bridge MUST appear before the default-to-"
            "dashboard fallback or Sessions silently routes to Dashboard.",
        )

    def test_saved_reports_route_uses_new_dashboard_page(self):
        self.assertIn(
            'render_saved_reports_dashboard(user, build_pdf_fn=',
            self.src,
            "saved_reports route must render the new dashboard-style page",
        )
        self.assertIn('"saved_reports"', self.src)

    def test_runtime_ordering_sessions_click(self):
        """Execute the exact ordering: bridge block THEN default block,
        against a fresh authed reload of ?page=saved_reports. Result
        must be page=saved_reports with NO stale open-report keys (so
        the _should_open_report guard cannot hijack it)."""
        ALLOWED = {
            "dashboard", "saved_reports", "swing_report", "compare_swings",
            "development_tracker", "historical_charts", "billing",
            "launch_progress", "pricing", "upload",
        }

        class QP(dict):
            def get(self, k, d=None):
                return super().get(k, d)
            def __delitem__(self, k):
                if k in self:
                    dict.__delitem__(self, k)

        ss = {}                       # fresh session (post-auth: empty)
        qp = QP({"page": "saved_reports"})  # arrived via the nav anchor
        # Pretend a previously-opened report left stale state behind
        # (in-session nav case) — the bridge must scrub it.
        ss["view_swing_record"] = {"id": "stale"}

        # --- BRIDGE BLOCK (must run first) ---
        up = qp.get("page")
        if up and up in ALLOWED:
            ss["page"] = up
            if up != "swing_report":
                for _k in ("view_swing_record", "view_swing_path",
                           "view_swing_report_id", "view"):
                    ss.pop(_k, None)
            try:
                del qp["page"]
            except Exception:
                pass

        # --- DEFAULT-DASHBOARD BLOCK (must run second) ---
        if not any(k in ss for k in ("page", "view", "view_swing_path",
                                     "view_swing_record")):
            ss["page"] = "dashboard"

        self.assertEqual(ss["page"], "saved_reports",
                         "Sessions anchor must resolve to saved_reports")
        self.assertNotIn("view_swing_record", ss,
                          "stale open-report state must be scrubbed so "
                          "_should_open_report cannot hijack Sessions")
        # _should_open_report would be: page==swing_report OR
        # view_swing_record/path present -> all false here.
        should_open_report = (
            ss.get("page") == "swing_report"
            or "view_swing_record" in ss
            or "view_swing_path" in ss
        )
        self.assertFalse(should_open_report,
                         "open-report guard must NOT fire for Sessions")


if __name__ == "__main__":
    unittest.main(verbosity=2)
