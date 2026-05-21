# BarrelLabs SwingAI — Session Handoff

**Date written:** 2026-05-19 ~01:35
**Branch:** `claude/nervous-proskuriakova` (git worktree at
`/Users/logancollins/barrellabs-swing-app/.claude/worktrees/nervous-proskuriakova`)
**Last commit:** `dae4743` — `fix(auth): nav is in-session st.button again`
**Live server:** Streamlit on `http://localhost:8501` (restart-required — see §3)

---

## 1. TL;DR — where things stand right now

We spent this session turning the BarrelLabs "Edge" UI into one seamless,
premium, sports-tech dashboard and chasing down a cascade of
**Streamlit-specific** layout/routing/auth bugs. The product logic
(scoring, analyzer, PDF, comparison math, Stripe, uploads) was **never
touched** and must stay that way.

**What is fixed and proven (tests + Playwright, deterministic):**

- The top masthead/nav renders flush at the very top of the page —
  **no slit, no dead band, no "big black box"** — proven against
  Streamlit 1.57's real default chrome.
- The masthead + page body are **one continuous `#0A0B0E` surface**
  (every layer forced to the same ink so no seam can show).
- The nav is now **auth-safe in-session `st.button`** navigation
  (the previous `<a href="?page=">` anchor nav was logging the user
  out on every click — root-caused and reverted).
- `Sessions` routes to the new dashboard-style Saved Reports page
  (the `?page=` URL bridge was running *after* the default-to-dashboard
  fallback — fixed by reordering).
- Login lands on Dashboard (no stale `?page=` redirect anymore).
- 18-test suite (`tests/test_nav_routing_smoke.py`) green, run 3×
  stable.

**What is NOT verified by me (needs the user's eyes — I cannot log in):**

- The **visual polish of the nav button-tabs on the authenticated
  pages**. I rebuilt the nav as Streamlit `st.button`s restyled into
  glass tabs via CSS. The mechanism (auth-safe) is proven; the exact
  pixel look on the live authed Dashboard/Sessions/Swing-Report pages
  has only been reasoned about, not screenshotted, because login is
  required and I have no credentials. **First task next session:
  user logs in, we screenshot-verify, iterate the scoped CSS if
  needed.**

---

## 2. Product / project context

- **App:** Streamlit app (`app.py` is a single ~5k-line top-to-bottom
  script). Python venv at `/Users/logancollins/barrellabs-swing-app/.venv`.
- **Streamlit version: 1.57.0** — this matters enormously (DOM testids
  changed across versions; see §3).
- **The "Edge" design system:** dark editorial sports-tech look —
  ink `#0A0B0E`, bone `#F4EFE6`, red `#E64530`, gold `#E8C170`;
  fonts Instrument Serif (italic display), Geist (sans), Geist Mono
  (labels). Tokens originate in `mock_dashboard_template.py` /
  `bl_theme.py`.
- **The Dashboard** is rendered as a big HTML string inside a
  Streamlit `components.html(...)` **iframe** (`dashboard_v3.py`
  pulls `DASHBOARD_HTML` from `mock_dashboard_template.py`).
- **Sessions / Saved Reports** = `saved_reports_dashboard.py`
  (`render_saved_reports_dashboard`) — the premium card list.
- **Individual Swing Report** = `swing_report_page.py`
  (`render_swing_report_page`) → delegates to
  `swing_report_dashboard_preview.py`
  (`render_swing_report_dashboard_preview`, `is_preview=False` in prod).
- **Shared masthead/nav** = `bl_edge_chrome.py`
  (`render_edge_masthead`) — the single nav component used by every
  authenticated page.

---

## 3. CRITICAL OPERATIONAL GOTCHAS — read this before doing anything

These are the hard-won lessons. Ignoring any one of them wastes hours.

### 3a. The Streamlit server is STALE until you restart it
`streamlit run app.py --server.headless true` **caches imported Python
modules in `sys.modules` for the life of the process.** Editing
`bl_edge_chrome.py` etc. does **NOT** hot-reload in headless mode.
This caused the user to repeatedly say "nothing changed" — the server
had been running since *before* an entire masthead rewrite.

**Every code change requires:**
```bash
lsof -ti :8501 | xargs -r kill -9; sleep 1
nohup /Users/logancollins/barrellabs-swing-app/.venv/bin/streamlit \
  run app.py --server.port 8501 --server.headless true >/tmp/sl.log 2>&1 &
# then poll until curl http://localhost:8501/ == 200
```
The restart **clears the Streamlit session → the user must re-login**.
Always tell them this when you restart.

### 3b. Auth lives ONLY in `st.session_state` — no durable persistence
Forensic trace of `auth.py` + `supabase_client.py`: the Supabase
session is stored solely in `st.session_state["supabase_session"]`.
There is **no cookie, file, keychain, or localStorage**, no
`.streamlit/config.toml`. Therefore:

- **A full browser navigation = a fresh Streamlit session = empty
  `st.session_state` = the user is logged out.** `current_profile()`
  has nothing to restore from.
- **Nav must be in-session** (`st.button` + `st.rerun()`), never
  `<a href="?page=">` anchors. This was the bug behind "clicking
  Dashboard kicks me out." Do not reintroduce anchor nav unless you
  also add durable token persistence (a much larger, security-
  sensitive change — Option B, not done).

### 3c. Streamlit 1.57 DOM testids (verified live via Playwright)
The chrome-kill CSS MUST use these exact selectors, **unscoped**,
`!important`, injected in the **last** stylesheet:

| Element | testid | Default that bites you |
|---|---|---|
| App root | `[data-testid="stApp"]` | bg differs per theme |
| Header bar | `[data-testid="stHeader"]` / `.stAppHeader` | **60px, position:absolute, z-index:999990** |
| Toolbar | `[data-testid="stToolbar"]` / `.stAppToolbar` | 60px |
| Main | `[data-testid="stMain"]` (NOT `section.main`) | — |
| Block container | `[data-testid="stMainBlockContainer"]` / `.block-container` | **padding-top: 96px (6rem)** |
| Vertical block | `[data-testid="stVerticalBlock"]` | **gap: 16px** flex |
| Element box | `[data-testid="stElementContainer"]` | margins |
| Button | `button[kind="primary"|"secondary"]` AND `button[data-testid="stBaseButton-primary"|"baseButton-primary"]` | Streamlit chrome |
| Keyed container | `.st-key-<key>` (from `st.container(key=...)`) | the reliable scoping hook |

**`section.main`, `.main`, `.st-key-*` on an unkeyed `st.markdown`
do NOT exist / match in 1.57.** Earlier CSS scoped to `section.main`
silently never matched → the 16px gap + 96px padding survived = the
"slit" and "dead band."

### 3d. I cannot authenticate — verification strategy
The authed pages (Dashboard/Sessions/Swing Report) only render after
Supabase login, and I have no credentials. So:

- **Logic correctness** is proven via the unit suite and runtime
  simulations (deterministic, no auth needed).
- **Seam/padding correctness** is proven via
  `scripts/visual_qa/verify_seam_fix.py` — it rebuilds Streamlit
  1.57's *exact default chrome* as a class stylesheet, injects the
  *real* `_EDGE_MASTHEAD_CSS` + masthead HTML, and Playwright-asserts
  `mast top == 0`, header hidden, all layers `rgb(10,11,14)`.
- **Live-DOM ground truth** was captured once via
  `scripts/visual_qa/probe_top_chrome.py` (Playwright against
  `localhost:8501` login page — top chrome is identical pre/post auth).
- **Static visual harness** (`scripts/visual_qa/render_full_app_static.py`)
  faithfully renders the masthead HTML + report HTML but **NOT
  Streamlit widget DOM** — so it could verify the *anchor* masthead
  but cannot show the *button-based* masthead. That's the current
  verification gap (§1).

### 3e. The Streamlit "markdown div can't wrap widgets" trap
`st.markdown("<div>")` does NOT wrap subsequent widgets — Streamlit
auto-closes it into an empty sibling. To group/scope widgets you must
use a real `st.container(key="...")` which yields a `.st-key-<key>`
class. Layout inside is done by making Streamlit's wrapper divs
`display:contents` so the real children become flex items of the
keyed container. This is how the current masthead lays out
(brand | navbar | chip) and how the nav buttons become glass tabs.

---

## 4. Architecture map

### Navigation flow (current, post-`dae4743`)
1. `render_edge_masthead(user, active_page=...)` in `bl_edge_chrome.py`
   renders: `st.container(key="bl_edge_masthead")` containing
   `st.markdown` brand → `st.container(key="bl_edge_navbar")` with
   **5 `st.button`s** (`key="_ble_nav_<page_key>"`,
   `type="primary"` when active) → `st.markdown` user chip.
2. Click handler (in-session): `st.session_state["page"] = page_key`;
   if `page_key != "swing_report"` it scrubs
   `view_swing_record/view_swing_path/view_swing_report_id/view`;
   then `st.rerun()`. **No URL change, no reload, auth preserved.**
3. `app.py` routing order (CRITICAL — must stay in this order):
   - auth gate (`~1524-1539`): restore/`render_auth_screen()`+`st.stop()`
   - **URL `?page=` bridge** (`~1653`, `_ALLOWED_PAGES_FROM_URL`):
     consumes a genuine deep-link `?page=`, scrubs stale open-report
     state for non-`swing_report` targets, `del st.query_params["page"]`.
   - **default-to-dashboard fallback** (`~1690`): only sets
     `page="dashboard"` if nothing else set it. **MUST run AFTER the
     bridge** (this ordering is the `973c6cb` fix; there is a
     regression-guard test `test_bridge_runs_before_dashboard_default`).
   - page dispatch: each `if st.session_state.get("page")=="X": ...
     st.stop()`. `saved_reports` → `render_saved_reports_dashboard`;
     `_should_open_report` (page==swing_report OR view_swing_* present)
     → `swing_report_page.render_swing_report_page` →
     `render_swing_report_dashboard_preview(..., is_preview=False)`.
4. The `?page=` bridge still exists **only for genuine deep-links**;
   the nav itself no longer uses it.

### The seamless-top CSS (in `_EDGE_MASTHEAD_CSS`, `bl_edge_chrome.py`)
Injected by `render_edge_masthead` on every authed page, last sheet,
all `!important`:
- Hide every chrome node (`stHeader/.stAppHeader/stToolbar/.stAppToolbar/
  stDecoration/stMainMenu/...`).
- Force one ink `#0A0B0E` on `html, body, stApp, stAppViewContainer,
  stMain, stMainBlockContainer, .block-container, iframe`.
- Zero `stMain` / `stMainBlockContainer` top padding+margin, zero
  `stVerticalBlock` gap, zero first element-container top margin.
- Masthead = full-bleed (`width:100vw; margin-left:-50vw`), solid
  `#0A0B0E`, no border, `z-index:10` above the `bl_theme` `::before`
  glow.
- Nav buttons restyled into glass tabs scoped to
  `.st-key-bl_edge_navbar button` (+ all 1.57 button-testid variants);
  active = `type=primary` with gold→red underline.

### Page renderers & seamless treatment (agents confirmed correct)
- `saved_reports_dashboard.render_saved_reports_dashboard`: calls
  `inject_global_theme()` → `render_edge_masthead(active_page="saved_reports")`
  → `render_edge_page_wrapper_open()` (phantom `.bl-edge-page` is
  `display:contents` = zero box) → `.srl-wrap` (max-width 1560, 40px
  gutter, tight top). Premium cards: score delta, MLB sim%, Personal
  Best badge, sparkline, Open Report / Download PDF / Delete.
- `swing_report_page.render_swing_report_page`: masthead +
  `render_swing_report_dashboard_preview(record, history,
  is_sample=False, is_preview=False)` → `.srd-wrap` (max-width 1560,
  40px gutter). `is_preview=False` ⇒ **no "PREVIEW ONLY" banner** in
  prod. Includes the Compare-This-Swing section with the dynamic
  executive summary.
- Both share the masthead's forced `#0A0B0E` (wins over `bl_theme`'s
  `#050505` because it's the later `!important` sheet).

---

## 5. Commit narrative (this session, newest first)

| Commit | What & why |
|---|---|
| `dae4743` | **Auth fix.** Anchor nav (`<a href="?page=">`) did full reloads → wiped session-only Supabase auth → logout on every click + stale `?page=` made re-login land on swing report. Reverted nav to in-session `st.container`+`st.button`+`st.rerun()`; kept glass-tab look via scoped CSS; scrub stale open-report state. Tests rewritten to the in-session contract. |
| `973c6cb` | **Routing fix.** `?page=` bridge ran *after* the default-to-dashboard block → fresh reload from a nav anchor got `page=dashboard`, dashboard route `st.stop()`'d before `saved_reports`. Moved bridge above the default; added stale-state scrub; runtime + source-order tests. |
| `9cd9176` | **The real slit/padding fix.** Chrome-kill CSS was scoped to non-existent `section.main`/`.main` → ST1.57's 16px `stVerticalBlock` gap + 96px `stMainBlockContainer` padding survived. Rewrote with correct unscoped 1.57 testids; forced one `#0A0B0E` ink on every layer; masthead solid + `z-index:10`, no border. Proven by `verify_seam_fix.py` (PASS). |
| `4010405` | Polish: seamless masthead→content, glass segmented nav, denser Sessions, gutter align (40px). |
| `69dee40` | Pure-HTML masthead (anchor nav — later found auth-unsafe, superseded by `dae4743`); harmonized page side-spacing. |
| `d4b9516` | Rebuilt masthead as a columnless flex row (nested `st.columns` were auto-stacking → tall wrapped "black box"). |
| `5af889c` | Single-page scroll + first premium-nav pass; `components.html(scrolling=False)` + auto-height bridge in `mock_dashboard_template.py` to kill the nested iframe scrollbar. |
| `e6a92ef` | `saved_reports._parse_date` bug: it sliced by the *format string* length, mangling ISO timestamps → Sessions cards showed `2026-05-18T14:23:00`. Now uses `fromisoformat` + correct fallbacks. |
| `873996f` | Official BarrelLabs logo installed (`static/`+`assets/barrellabs-logo.png`), hardened `_logo_data_uri` (PIL resize + underscore-root fallback); shared masthead added to Drills/Library/Compare; Compare executive summary; premium Sessions cards. |
| `2f7d1cc` | Promoted the dashboard-style swing report + Sessions page to production (Open Report → new renderer; Sessions → new `saved_reports_dashboard`). |
| `71bc1ee` | (pre-session) Top Priorities + Drills above the fold. |

`git log --oneline -16` for the full picture.

---

## 6. Verified vs unverified

**Deterministically verified (no auth needed):**
- 18/18 tests in `tests/test_nav_routing_smoke.py`, 3× stable.
- `verify_seam_fix.py` → masthead `top==0`, header hidden, all layers
  `#0A0B0E` against ST1.57 real defaults — **PASS**.
- `probe_top_chrome.py` captured live-DOM ground truth (96px pad,
  16px gap, 60px abs header) confirming the diagnosis.
- Server reboots clean on the nav URLs (Playwright HTTP 200, no
  exception) at commits `9cd9176`, `973c6cb`, `dae4743`.
- Routing simulation: fresh `?page=saved_reports` reload → resolves to
  `saved_reports`, scrubs stale state, `_should_open_report` False.

**NOT verified (needs user login):**
- The visual look of the **button-based glass tabs** on the live
  authed pages. The CSS uses `display:contents` to flatten Streamlit
  wrappers + scoped `.st-key-bl_edge_navbar button` styling. Selectors
  are based on the documented ST1.57 button DOM but the exact rendered
  result on Dashboard/Sessions/Swing-Report is unconfirmed.
- That clicking each nav tab on the live authed app navigates
  correctly **and keeps the user logged in** (logically proven; needs
  one real click-through to be 100%).
- The Compare-This-Swing dropdown interaction on the live Streamlit
  app (the static harness proved the default state only).

---

## 7. Open items / known risks / tech debt

1. **`components.html(height=5800, scrolling=False)`** in
   `dashboard_v3.py` (~2128) and `mock_dashboard_template.py` (~3287).
   The in-iframe `postMessage`/`setFrameHeight` auto-height bridge is
   **not actually honored by Streamlit `components.html`** (it's only
   for declared bidirectional components). So the iframe is a fixed
   5800px box: if the real dashboard content is shorter there is a
   silent empty region at the **bottom** of the dashboard (same ink so
   low-visibility, but it's there and makes the page very tall). The
   only robust fixes are (a) measure the template's true rendered
   height and hardcode it, or (b) build a real bidirectional component.
   Not urgent (user hasn't complained) but it's the last "not truly
   seamless" thing.
2. **Button-tab visual** (see §6) — top priority to confirm.
3. **`render_full_app_static.py`** can no longer faithfully preview
   the masthead (it stubs `st.button`). Either accept that the
   masthead is only verifiable live, or extend a harness that renders
   a real Streamlit `st.button` DOM skeleton (like `verify_seam_fix.py`
   does for chrome) so the button-tab CSS can be proven auth-free.
   Recommended: build `verify_nav_tabs.py` on the `verify_seam_fix.py`
   pattern.
4. **`scripts/visual_qa/`** now has several one-off probes
   (`probe_top_chrome.py`, `verify_seam_fix.py`,
   `render_full_app_static.py`, `render_saved_reports_static.py`,
   `render_swing_report_static.py`, `run_promotion_checks.py`). Keep
   `verify_seam_fix.py` + `probe_top_chrome.py` (genuinely useful for
   regression); the others can be pruned if they bitrot.
5. **`.streamlit/secrets.toml`** lives in the *main* repo
   (`/Users/logancollins/barrellabs-swing-app/.streamlit/secrets.toml`,
   Supabase project `xionpyhapspecsrjregt`). The worktree has none;
   the running server's cwd is the worktree but Streamlit/Supabase
   still resolve because the venv/secrets are found via the main repo.
   If auth ever fails to even reach the login form, check this.
6. **Two duplicate route guards** for `development_tracker` /
   `historical_charts` exist in `app.py` (early ~915 AND later
   ~5470). The early ones fire first; the later are dead code. Not
   harmful, but confusing — candidate cleanup.

---

## 8. The path forward (priority order)

1. **VERIFY THE NAV LIVE (do this first).** User logs in at
   `localhost:8501`. Confirm in order:
   - Lands on **Dashboard** (not swing report).
   - Click **Sessions** → premium Saved Reports list, **no logout**,
     masthead flush/seamless, glass tabs look premium.
   - Click **Dashboard / Compare / Drills / Library** → each
     navigates, **no logout**, identical masthead.
   - **Open Report** on a Sessions card → clean swing report (no
     PREVIEW banner), Back to Sessions works.
   - Screenshot each (read-tier Safari screenshot via computer-use, or
     the user pastes). Iterate the `.st-key-bl_edge_navbar` CSS if the
     tabs aren't pixel-clean.
2. **Build `scripts/visual_qa/verify_nav_tabs.py`** (on the
   `verify_seam_fix.py` pattern) so the button-tab styling is provable
   auth-free going forward — closes the verification gap permanently.
3. **Decide on the iframe bottom-void** (§7.1). If the user notices
   excess length on the Dashboard, measure the template's true height
   and set `components.html(height=...)` to it (delete the dead
   postMessage bridge or keep as harmless).
4. **Polish pass on the three pages once nav is confirmed:** ensure
   Sessions density, Swing Report spacing, Compare section, and the
   dashboard hero all read as one product. Use the static harnesses
   for the HTML parts; the user for the Streamlit-widget parts.
5. **Only after the user signs off visually:** consider a squash/PR
   of `claude/nervous-proskuriakova` → `main`. The branch is ~14
   commits ahead; the work is cohesive (UI/nav/routing/auth-safety,
   zero product-logic changes).

---

## 9. How to run / test / verify (commands)

```bash
cd /Users/logancollins/barrellabs-swing-app/.claude/worktrees/nervous-proskuriakova
PY=/Users/logancollins/barrellabs-swing-app/.venv/bin/python

# Restart the live server (REQUIRED after every code change — §3a)
lsof -ti :8501 | xargs -r kill -9; sleep 1
nohup /Users/logancollins/barrellabs-swing-app/.venv/bin/streamlit \
  run app.py --server.port 8501 --server.headless true >/tmp/sl.log 2>&1 &
# poll: curl -s -o /dev/null -w '%{http_code}' http://localhost:8501/  → 200

# Unit/integration suite (no auth needed) — must stay green
$PY -m unittest tests.test_nav_routing_smoke        # 18 tests

# Prove seam/padding against ST1.57 real defaults (no auth)
$PY scripts/visual_qa/verify_seam_fix.py            # expect VERDICT: PASS

# Capture live Streamlit DOM ground truth (login-page chrome == authed)
$PY scripts/visual_qa/probe_top_chrome.py           # JSON + /tmp/probe_top.png

# Static HTML previews (HTML-only; NOT Streamlit widgets)
$PY scripts/visual_qa/render_full_app_static.py     # /tmp/full_app_preview.html
# served on the Claude_Preview server (port 8502, /tmp/preview_root/index.html)

# AST sanity on the big file before restart
$PY -c "import ast; ast.parse(open('app.py').read()); print('ok')"
```

**Playwright** is installed in the venv (Chromium present). Use it to
script DOM forensics against `localhost:8501` — but remember the
authed pages need login, so Playwright can only see the **login page
chrome** (which is identical to authed for the top slit/padding) and
**cannot** drive the authed nav.

**Browser tiers for computer-use:** Safari is tier "read" (screenshot
only, no clicks/typing). The Claude-in-Chrome extension was **not
connected** this session (`list_connected_browsers` → `[]`). Ask the
user to connect it if you need to drive a real authed browser.

---

## 10. CONSTRAINTS — do NOT touch (hard rule, repeated all session)

No changes to: **scoring, analyzer logic, pose extraction, metric
calculations, upload flow, auth/Supabase, Stripe/billing,
entitlements, saved-report storage, PDF generation, swing-comparison
math.** Everything we did is UI / nav / routing / CSS only. Keep it
that way unless the user explicitly authorizes a data-layer change.

---

## 11. File reference (what each touched file is for)

| File | Role |
|---|---|
| `bl_edge_chrome.py` | **The shared masthead/nav.** `_EDGE_MASTHEAD_CSS` (chrome-kill + unified ink + glass-tab CSS), `render_edge_masthead` (st.container+st.button in-session nav), `_logo_data_uri`, `render_edge_page_wrapper_open/close` (phantom `.bl-edge-page` is `display:contents`). **Most-edited file; the nav lives here.** |
| `app.py` | Routing. The `?page=` bridge (`~1653`) MUST precede the default-to-dashboard block (`~1690`). Page dispatch + `_should_open_report` further down (~4246 saved_reports, ~4766 open-report). |
| `saved_reports_dashboard.py` | Sessions page — premium cards, filters, delta/PB/sparkline. Reuses `_parse_date`/`_fmt_short_date`/`_top_focus` from `saved_reports.py`. |
| `swing_report_page.py` | Individual report page wrapper; delegates to `render_swing_report_dashboard_preview(is_preview=False)`. |
| `swing_report_dashboard_preview.py` | The dashboard-style report renderer + Compare-This-Swing + dynamic executive summary + `SAMPLE_RECORD/SAMPLE_HISTORY`. |
| `mock_dashboard_template.py` | `DASHBOARD_HTML` (the iframe dashboard) + the auto-height `<script>` + `components.html(...,scrolling=False)`. `.app` gutter = 40px. |
| `dashboard_v3.py` | Extracts `DASHBOARD_HTML`, injects data, `components.html(height=5800, scrolling=False)`; `_render_v3_nav` → `render_edge_masthead`. |
| `bl_theme.py` | `inject_global_theme` (global tokens; sets `#050505` which the masthead CSS overrides to `#0A0B0E`; the `::before` radial glow at z-index:0). |
| `saved_reports.py` | Legacy list page (kept) + the shared `_parse_date`/helpers reused by the new Sessions page. `_parse_date` was the timestamp-format bug fix. |
| `tests/test_nav_routing_smoke.py` | The 18-test guard: masthead button contract, active state, Sessions in-session routing, bridge-before-default ordering + runtime sim, no-`?page=`-anchor invariant. **Run this every change.** |
| `scripts/visual_qa/verify_seam_fix.py` | Auth-free proof of seam/padding vs ST1.57 defaults. Keep. |
| `scripts/visual_qa/probe_top_chrome.py` | Live-DOM Playwright forensics. Keep. |

---

## 12. One-paragraph orientation for the next session

You are continuing a UI/nav hardening effort on a Streamlit 1.57 app.
The product logic is off-limits. The masthead/nav is in
`bl_edge_chrome.py` and is now in-session `st.button` nav (auth-safe —
do **not** revert to `<a href>` anchors, that logs users out because
auth is `st.session_state`-only). The seam/padding fix uses correct
ST1.57 testids unscoped+`!important`+last-sheet and forces one
`#0A0B0E` ink everywhere; it's proven by
`scripts/visual_qa/verify_seam_fix.py`. **Restart the Streamlit server
after every edit or the user sees nothing change.** Your first job is
to have the user log in and screenshot the live authed
Dashboard/Sessions/Swing-Report so we can confirm the glass nav-tabs
look premium and that navigation never logs them out — then iterate
the `.st-key-bl_edge_navbar` CSS if needed, and build
`verify_nav_tabs.py` so that's provable auth-free thereafter. Keep
`tests/test_nav_routing_smoke.py` green (18 tests). Last commit:
`dae4743`.
