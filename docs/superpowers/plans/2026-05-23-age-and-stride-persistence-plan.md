# Age + Stride-Direction Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Swing Score's age-fair brackets and the Stride pillar's brace gate work on real swings by persisting a player's birth year and serializing stride direction into the fingerprint.

**Architecture:** Store `birth_year` on the `players` row (new nullable column). `app.py` computes age (`current_year − birth_year`) and passes it to `detect_phases.py`, which writes `age` plus a `stride` direction block into the fingerprint JSON. `analyzer.py` reads both (age already wired; stride gate replaces a hardcoded `True`) and flags `age_known` so the report can show an honest "set your birth year" nudge when age is missing. Two new pure helpers (`age_from_birth_year`, `stride_direction`) are unit-tested in isolation.

**Tech Stack:** Python, Streamlit, Supabase (Postgres), MediaPipe (existing `detect_phases.py`), pytest.

**Working dir:** `/Users/logancollins/barrellabs-swing-app/.claude/worktrees/swing-engine` (branch `claude/swing-engine`, folded into PR #23). Run python as `../../../.venv/bin/python` from the worktree, or `.venv/bin/python` from repo root.

**Spec:** `docs/superpowers/specs/2026-05-23-age-and-stride-persistence-design.md`

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `analyzer.py` | `age_from_birth_year()` helper; consume stride gate; emit `age_known` | modify |
| `biomech.py` | `stride_direction()` pure helper | modify |
| `supabase/migrations/2026_05_23_player_birth_year.sql` | add `players.birth_year` | create |
| `auth.py` | profile dict carries `birth_year`; whitelist it for update | modify |
| `detect_phases.py` | parse `--age`; write `age` + `stride` into fingerprint | modify |
| `app.py` | compute age, pass `--age` to detect_phases | modify |
| `player_settings_page.py` | "Birth year" field bound to profile + saved | modify |
| `swing_report_dashboard_preview.py` | honest age label when `age_known` falsy | modify |
| `tests/test_age_birth_year.py` | unit tests for `age_from_birth_year` | create |
| `tests/test_stride_direction.py` | unit tests for `stride_direction` | create |
| `tests/test_auth_birth_year.py` | `_profile_from_row` carries birth_year | create |
| `tests/test_analyzer_swing_score.py` | age_known + stride gate integration | modify |
| `tests/test_report_two_systems.py` | honest age label | modify |
| `tests/test_player_settings_wiring.py` | birth_year save wiring | modify |

---

## Task 1: `age_from_birth_year()` pure helper (analyzer.py)

**Files:**
- Modify: `analyzer.py` (add helper next to `age_bracket`, ~line 150)
- Test: `tests/test_age_birth_year.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_age_birth_year.py`:

```python
"""Unit tests for analyzer.age_from_birth_year — birth year → current age."""
import pytest

from analyzer import age_from_birth_year


def test_typical_birth_year():
    assert age_from_birth_year(2014, today_year=2026) == 12

def test_uses_current_year_by_default():
    # Just assert it returns a plausible int, not the exact value (clock-dependent).
    out = age_from_birth_year(2010)
    assert isinstance(out, int) and 5 <= out <= 30

def test_none_returns_none():
    assert age_from_birth_year(None, today_year=2026) is None

def test_blank_string_returns_none():
    assert age_from_birth_year("", today_year=2026) is None

def test_numeric_string_ok():
    assert age_from_birth_year("2015", today_year=2026) == 11

def test_junk_returns_none():
    assert age_from_birth_year("banana", today_year=2026) is None

def test_implausible_year_returns_none():
    # A 4-digit year that yields an absurd age is rejected (typo guard).
    assert age_from_birth_year(1500, today_year=2026) is None
    assert age_from_birth_year(2030, today_year=2026) is None  # future
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/bin/python -m pytest tests/test_age_birth_year.py -q`
Expected: FAIL with `ImportError: cannot import name 'age_from_birth_year'`.

- [ ] **Step 3: Implement the helper**

In `analyzer.py`, find `def age_bracket(age) -> str:` (~line 150). Immediately ABOVE it, add:

```python
def age_from_birth_year(birth_year, today_year: Optional[int] = None) -> Optional[int]:
    """Compute a player's current age from a 4-digit birth year.

    Returns None for missing/blank/unparseable input, and for ages outside a
    plausible youth-baseball range (typo guard) so a bad value falls back to
    the default bracket rather than skewing the score.
    """
    import datetime
    if birth_year is None:
        return None
    try:
        by = int(str(birth_year).strip())
    except (TypeError, ValueError):
        return None
    yr = today_year if today_year is not None else datetime.date.today().year
    age = yr - by
    if age < 4 or age > 25:
        return None
    return age
```

Confirm `Optional` is imported in `analyzer.py` (it is — used in existing signatures).

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/bin/python -m pytest tests/test_age_birth_year.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add analyzer.py tests/test_age_birth_year.py
git commit -m "feat(age): age_from_birth_year helper (#134)"
```

---

## Task 2: `stride_direction()` pure helper (biomech.py)

**Files:**
- Modify: `biomech.py` (add pure function; import-safe module already used by `detect_phases.py`)
- Test: `tests/test_stride_direction.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_stride_direction.py`:

```python
"""Unit tests for biomech.stride_direction — is the front foot striding
toward the pitcher? Pure geometry on ankle x-series."""
from biomech import stride_direction


# Front foot starts to the RIGHT of the back foot (pitcher side = +x) and
# moves further right (toward pitcher) by foot plant → toward_pitcher True.
def test_forward_stride_toward_pitcher():
    front = [50, 52, 60, 75, 90]   # moves +x (toward pitcher side)
    back  = [10, 10, 11, 10, 10]   # stays put
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is True
    assert out["dx_norm"] > 0

# Step-in-the-bucket: front foot pulls BACK toward the back foot (away from
# pitcher) → toward_pitcher False, negative dx_norm.
def test_bail_out_not_toward_pitcher():
    front = [90, 85, 70, 55, 45]   # moves -x (away from pitcher side)
    back  = [10, 10, 10, 10, 10]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is False
    assert out["dx_norm"] < 0

# Pitcher on the LEFT (front foot left of back foot): a true stride moves -x.
def test_left_facing_forward_stride():
    front = [50, 40, 30, 20, 10]   # moves -x, but that's TOWARD pitcher here
    back  = [90, 90, 90, 90, 90]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is True
    assert out["dx_norm"] > 0

def test_no_stride_is_not_toward():
    front = [50, 50, 51, 50, 50]   # barely moves
    back  = [10, 10, 10, 10, 10]
    out = stride_direction(front, back, stance_idx=0, foot_plant_idx=4, torso_px=100.0)
    assert out["toward_pitcher"] is False

def test_degenerate_failsoft_lenient():
    # Empty / bad torso / out-of-range index → lenient fallback (True, 0.0)
    assert stride_direction([], [], 0, 0, 100.0) == {"toward_pitcher": True, "dx_norm": 0.0}
    assert stride_direction([1, 2], [1, 2], 0, 1, 0.0) == {"toward_pitcher": True, "dx_norm": 0.0}
    assert stride_direction([1, 2], [1, 2], 0, 9, 100.0) == {"toward_pitcher": True, "dx_norm": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/bin/python -m pytest tests/test_stride_direction.py -q`
Expected: FAIL with `ImportError: cannot import name 'stride_direction'`.

- [ ] **Step 3: Implement the helper**

Append to `biomech.py`:

```python
def stride_direction(front_ankle_x, back_ankle_x, stance_idx, foot_plant_idx,
                     torso_px, eps=0.04):
    """Did the front foot stride toward the pitcher?

    Pitcher side = sign(front − back ankle x at stance). A real stride moves
    the front foot further toward that side by foot plant. `dx_norm` is the
    signed forward displacement in torso lengths (positive = toward pitcher).
    Fail-soft to the lenient gate (toward_pitcher=True, dx_norm=0.0) on
    degenerate input so a bad camera read never unfairly punishes the brace.
    """
    n = len(front_ankle_x)
    if (n == 0 or len(back_ankle_x) != n or torso_px is None or torso_px <= 1.0
            or not (0 <= stance_idx < n) or not (0 <= foot_plant_idx < n)):
        return {"toward_pitcher": True, "dx_norm": 0.0}

    def _avg(arr, i, w=2):
        lo, hi = max(0, i - w), min(len(arr), i + w + 1)
        seg = arr[lo:hi]
        return float(sum(seg) / len(seg)) if seg else float(arr[i])

    fx_stance = _avg(front_ankle_x, stance_idx)
    bx_stance = _avg(back_ankle_x, stance_idx)
    fx_plant = _avg(front_ankle_x, foot_plant_idx)
    pitcher_side = 1.0 if (fx_stance - bx_stance) >= 0 else -1.0
    dx_norm = ((fx_plant - fx_stance) * pitcher_side) / torso_px
    return {"toward_pitcher": bool(dx_norm > eps), "dx_norm": float(dx_norm)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/bin/python -m pytest tests/test_stride_direction.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add biomech.py tests/test_stride_direction.py
git commit -m "feat(stride): stride_direction pure helper (#134)"
```

---

## Task 3: DB migration — `players.birth_year`

**Files:**
- Create: `supabase/migrations/2026_05_23_player_birth_year.sql`

> **Note:** This task only WRITES the migration file. Applying it to the live DB is a gated step in Task 10 (requires explicit user authorization). Tests never touch the real DB.

- [ ] **Step 1: Write the migration file**

Create `supabase/migrations/2026_05_23_player_birth_year.sql`:

```sql
-- #134 — Persist player birth year for the age-fair Swing Score.
-- Additive + nullable: existing rows get NULL → analyzer defaults to the
-- 13-14 bracket until a birth year is set in Player Settings.
alter table public.players
  add column if not exists birth_year smallint;

comment on column public.players.birth_year is
  'Player birth year (4-digit). Age = current_year - birth_year, computed at '
  'analysis time so it never goes stale. Drives the age-fair Swing Score '
  'brackets (8-10 / 11-12 / 13-14 / 15-17). Nullable; null -> default bracket.';
```

- [ ] **Step 2: Sanity-check the SQL syntax locally (no DB)**

Run: `grep -c "add column if not exists birth_year" supabase/migrations/2026_05_23_player_birth_year.sql`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/2026_05_23_player_birth_year.sql
git commit -m "feat(db): migration to add players.birth_year (#134, apply gated)"
```

---

## Task 4: `auth.py` — profile carries + persists birth_year

**Files:**
- Modify: `auth.py` — `_profile_from_row` (~line 66) and `ALLOWED_PROFILE_UPDATES` (~line 388)
- Test: `tests/test_auth_birth_year.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_birth_year.py`:

```python
"""birth_year round-trips through the profile mapping + is update-whitelisted."""
import auth


def test_profile_from_row_includes_birth_year():
    row = {"id": "p1", "user_id": "u1", "name": "Test", "handedness": "RIGHT",
           "birth_year": 2014}
    prof = auth._profile_from_row(row)
    assert prof["birth_year"] == 2014

def test_profile_from_row_birth_year_absent_is_none():
    prof = auth._profile_from_row({"id": "p1", "name": "Test"})
    assert prof.get("birth_year") is None

def test_birth_year_is_update_whitelisted():
    assert "birth_year" in auth.ALLOWED_PROFILE_UPDATES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/bin/python -m pytest tests/test_auth_birth_year.py -q`
Expected: FAIL (`KeyError`/`assert None == 2014` and `birth_year not in ALLOWED_PROFILE_UPDATES`).

- [ ] **Step 3: Implement**

In `auth.py` `_profile_from_row`, in the "Body / metadata" block (after `"weight_lb": row.get("weight_lb"),`, ~line 77), add:

```python
        "birth_year":  row.get("birth_year"),
```

In `ALLOWED_PROFILE_UPDATES` (~line 388), add `"birth_year"`:

```python
ALLOWED_PROFILE_UPDATES = {
    "name", "handedness", "height_in", "weight_lb", "birth_year",
    "team", "position", "throws", "level", "primary_goal",
    "profile_pic_path",
    "locked_mlb_slug",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/bin/python -m pytest tests/test_auth_birth_year.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth_birth_year.py
git commit -m "feat(auth): birth_year in profile dict + update whitelist (#134)"
```

---

## Task 5: `detect_phases.py` — write `age` + `stride` into the fingerprint

**Files:**
- Modify: `detect_phases.py` — CLI arg parse (~line 31) and fingerprint dict (~line 1047)

> No unit test here (it's a top-level script that needs a video to run). The pure logic it relies on is covered by Task 2; end-to-end is verified in Task 10. Keep the change minimal and additive.

- [ ] **Step 1: Parse the optional `--age` flag**

In `detect_phases.py`, just after the `HANDEDNESS = ...` line (~line 31), add:

```python
# Optional player age (years), passed by app.py as "--age N". Written into the
# fingerprint so analyzer.age_bracket() can pick an age-fair band. Absent →
# fingerprint omits `age` → analyzer falls back to the default bracket.
PLAYER_AGE = None
if "--age" in sys.argv:
    try:
        PLAYER_AGE = int(sys.argv[sys.argv.index("--age") + 1])
    except (ValueError, IndexError):
        PLAYER_AGE = None
```

- [ ] **Step 2: Build the stride block + add both fields to the fingerprint**

In `detect_phases.py`, immediately BEFORE the `fingerprint = {` line (~line 1047), add:

```python
# ---------- STRIDE DIRECTION (front foot toward the pitcher?) ----------
# Pre-load stance window ends ~0.5s before foot plant (see stride_baseline
# above); use its start as the stance reference. ref_torso_len is the 95th-pct
# torso length used elsewhere for scale-invariant normalization.
_stance_ref = max(0, min(sk_start, len(records) - 1))
_front_ax = [r["front_ankle_x"] for r in records]
_back_ax = [r[f"{back_side}_ankle_x"] for r in records]
stride_block = biomech.stride_direction(
    _front_ax, _back_ax, _stance_ref, int(phases["foot_plant"]), ref_torso_len,
)
```

Then inside the `fingerprint = { ... }` dict literal, add a `"stride"` entry after the `"camera_view": {...},` block (~line 1096):

```python
    "stride": stride_block,
```

Finally, after the fingerprint dict is constructed but BEFORE `with open(OUTPUT_FINGERPRINT...)` (~line 1116), add:

```python
# Player age (optional) — additive; absent when not supplied.
if PLAYER_AGE is not None:
    fingerprint["age"] = int(PLAYER_AGE)
```

- [ ] **Step 3: Byte-compile to catch syntax errors (no video run needed)**

Run: `../../../.venv/bin/python -c "import py_compile; py_compile.compile('detect_phases.py', doraise=True); print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add detect_phases.py
git commit -m "feat(detect): write age + stride direction into fingerprint (#134)"
```

---

## Task 6: `app.py` — compute age, pass `--age` to detect_phases

**Files:**
- Modify: `app.py` — imports (top, where `from analyzer import analyze` is) and the detect_phases subprocess call (~line 4338)

- [ ] **Step 1: Import the helper**

Find the existing analyzer import in `app.py` (search `from analyzer import`). Extend it to include `age_from_birth_year`. Example (match the actual existing line):

```python
from analyzer import analyze, age_from_birth_year
```

(If `analyze` is imported differently, just add `age_from_birth_year` to that import.)

- [ ] **Step 2: Build the command with the optional age arg**

Replace the subprocess call at ~line 4338:

```python
    rc, out, err = run_subprocess(
        [PY, "detect_phases.py", str(video_path), HAND_MAP[hand_override]],
        cwd=PROJECT_ROOT,
    )
```

with:

```python
    _detect_cmd = [PY, "detect_phases.py", str(video_path),
                   HAND_MAP[hand_override]]
    _player_age = age_from_birth_year((user or {}).get("birth_year"))
    if _player_age is not None:
        _detect_cmd += ["--age", str(_player_age)]
    rc, out, err = run_subprocess(_detect_cmd, cwd=PROJECT_ROOT)
```

- [ ] **Step 3: Byte-compile to catch syntax errors**

Run: `../../../.venv/bin/python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(app): pass player age to detect_phases from birth_year (#134)"
```

---

## Task 7: `analyzer.py` — use the real stride gate + emit `age_known`

**Files:**
- Modify: `analyzer.py` — stride gate (~line 681), result dict (~line 873)
- Test: `tests/test_analyzer_swing_score.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_analyzer_swing_score.py`:

```python
def test_age_known_true_when_fingerprint_has_age(player_fp_path, tmp_path):
    import json
    fp = json.load(open(player_fp_path))
    fp["age"] = 11
    p = tmp_path / "fp_age.json"
    p.write_text(json.dumps(fp))
    result = analyze(str(p), "mike_trout")
    assert result["age_known"] is True
    assert result["age_bracket"] == "11-12"

def test_age_known_false_when_age_absent(player_fp_path, tmp_path):
    import json
    fp = json.load(open(player_fp_path))
    fp.pop("age", None)
    p = tmp_path / "fp_noage.json"
    p.write_text(json.dumps(fp))
    result = analyze(str(p), "mike_trout")
    assert result["age_known"] is False
    assert result["age_bracket"] == "13-14"  # default

def test_stride_gate_reads_fingerprint(player_fp_path, tmp_path):
    import json
    base = json.load(open(player_fp_path))
    base["knee_deg"] = dict(base.get("knee_deg") or {}, re_extension=18.0,
                            at_foot_plant=150.0, min_during_load=140.0)
    # toward_pitcher True → full brace credit possible
    toward = dict(base); toward["stride"] = {"toward_pitcher": True, "dx_norm": 0.2}
    away = dict(base); away["stride"] = {"toward_pitcher": False, "dx_norm": -0.1}
    pa = tmp_path / "toward.json"; pa.write_text(json.dumps(toward))
    pb = tmp_path / "away.json"; pb.write_text(json.dumps(away))
    ra = analyze(str(pa), "mike_trout")
    rb = analyze(str(pb), "mike_trout")
    # The stride pillar compliance must be lower when not striding to pitcher.
    assert rb["pillars"]["stride"]["compliance"] <= ra["pillars"]["stride"]["compliance"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/bin/python -m pytest tests/test_analyzer_swing_score.py -q -k "age_known or stride_gate"`
Expected: FAIL (`KeyError: 'age_known'`, and stride gate equal because it's hardcoded True).

- [ ] **Step 3: Implement the stride gate read**

In `analyzer.py`, find the hardcoded stride gate (~line 681):

```python
    stride_toward_pitcher = True
```

Replace with:

```python
    # Stride direction comes from the fingerprint (detect_phases serializes it
    # as `stride.toward_pitcher`). Default True for older fingerprints that
    # predate the field so they keep their prior (lenient) brace scoring.
    _stride_blk = player.get("stride") or {}
    stride_toward_pitcher = bool(_stride_blk.get("toward_pitcher", True))
```

- [ ] **Step 4: Implement `age_known`**

In `analyzer.py`, just after `bracket = age_bracket(player.get("age"))` (~line 664), add:

```python
    # Did we resolve a real age, or fall back to the default bracket? Drives
    # the report's honest "set your birth year" nudge.
    def _age_is_known(_a) -> bool:
        try:
            int(_a)
            return True
        except (TypeError, ValueError):
            return False
    age_known = _age_is_known(player.get("age"))
```

Then in the result dict, after `"age_bracket": bracket,` (~line 873), add:

```python
        "age_known": age_known,            # False → report shows the age nudge
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/bin/python -m pytest tests/test_analyzer_swing_score.py -q`
Expected: PASS (all, including the 3 new).

- [ ] **Step 6: Commit**

```bash
git add analyzer.py tests/test_analyzer_swing_score.py
git commit -m "feat(analyzer): real stride gate + age_known flag (#134)"
```

---

## Task 8: `player_settings_page.py` — "Birth year" field bound to the profile

**Files:**
- Modify: `player_settings_page.py` — `WK` (~line 148), `_saved_defaults` (~line 352), dirty list (~line 389), field list (~line 405), render (~line 1508), `_do_save` (~line 1923 & 1939)
- Test: `tests/test_player_settings_wiring.py` (extend)

- [ ] **Step 1: Write the failing test**

First inspect the existing wiring test to match its harness style:

Run: `sed -n '1,60p' tests/test_player_settings_wiring.py`

Then append a test that asserts the save path forwards `birth_year` to `update_profile`. Use the existing test's mocking pattern; the assertion shape is:

```python
def test_birth_year_persists_via_update_profile(monkeypatch):
    """Saving Settings forwards an int birth_year to auth.update_profile."""
    import player_settings_page as ps

    captured = {}
    def _fake_update(slug, **fields):
        captured.update(fields)
        return {"slug": slug, **fields}
    monkeypatch.setattr("auth.update_profile", _fake_update)

    user = {"slug": "p1", "name": "Test", "handedness": "RIGHT",
            "height_in": 60, "weight_lb": 120, "birth_year": None}

    # Simulate the user having typed a birth year in the widget.
    monkeypatch.setattr(ps, "_current_field_values",
                        lambda _u: dict(ps._saved_defaults(user), birth_year="2014"))
    ps._do_save(user)
    assert captured.get("birth_year") == 2014
```

> If `_do_save` references Streamlit session/flash state that errors under test, wrap only the `update_profile` assertion: the test's goal is that `birth_year=2014` reaches `update_profile`. Adjust mocks to the existing file's conventions (check how other fields are asserted in this test module first).

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/bin/python -m pytest tests/test_player_settings_wiring.py -q -k birth_year`
Expected: FAIL (`birth_year` not forwarded; it's currently an `_extras_set("age", ...)`).

- [ ] **Step 3: Rename the widget key**

In `WK` (~line 148), replace:

```python
    "age":      "ps_age",
```
with:
```python
    "birth_year": "ps_birth_year",
```

- [ ] **Step 4: Bind the saved default to the profile (not extras)**

In `_saved_defaults` (~line 352), replace:

```python
        "age":     str(extras.get("age", "") or ""),
```
with:
```python
        "birth_year": str(user.get("birth_year") or ""),
```

- [ ] **Step 5: Update the dirty-tracked field list**

In the loop near line 389, replace the tuple member `"age"` with `"birth_year"`:

```python
    for s in ("first", "last", "display", "birth_year", "grad", "team"):
```

- [ ] **Step 6: Update the field label list**

Near line 405, replace:

```python
    ("age",     "Age"),
```
with:
```python
    ("birth_year", "Birth year"),
```

- [ ] **Step 7: Render a "Birth year" input with an age hint**

Replace the render block at ~line 1508:

```python
            with c5:
                st.text_input("Age", value=saved["age"],
                               placeholder="e.g. 16", key=WK["age"])
```
with:
```python
            with c5:
                st.text_input("Birth year", value=saved["birth_year"],
                               placeholder="e.g. 2014", key=WK["birth_year"],
                               help="Used for an age-accurate Swing Score. "
                                    "Updates automatically each year.")
                from analyzer import age_from_birth_year as _afby
                _age_hint = _afby(st.session_state.get(WK["birth_year"])
                                  or saved["birth_year"])
                if _age_hint is not None:
                    st.caption(f"Age {_age_hint}")
```

- [ ] **Step 8: Persist birth_year through update_profile + drop the extras write**

In `_do_save` (~line 1923), add `birth_year` to the `update_profile(...)` call (alongside `weight_lb=...`):

```python
        weight_lb=int(cur["wt"]),
        birth_year=_parse_birth_year(cur["birth_year"]),
```

Add a parse helper near the top of `_do_save` (just under `cur = _current_field_values(user)`):

```python
    def _parse_birth_year(v):
        try:
            y = int(str(v).strip())
            return y if 1990 <= y <= 2025 else None
        except (TypeError, ValueError):
            return None
```

Then DELETE the now-stale extras line at ~line 1939:

```python
        _extras_set("age", (cur["age"] or "").strip())
```

- [ ] **Step 9: Run the test + the settings suite**

Run: `../../../.venv/bin/python -m pytest tests/test_player_settings_wiring.py -q`
Expected: PASS (existing + new).

- [ ] **Step 10: Byte-compile (catches any stray `cur["age"]` / `WK["age"]` reference)**

Run: `../../../.venv/bin/python -c "import py_compile; py_compile.compile('player_settings_page.py', doraise=True); print('OK')"`
Then grep for stragglers: `grep -n '\["age"\]\|WK\["age"\]\|saved\["age"\]\|cur\["age"\]' player_settings_page.py` — Expected: no output.

- [ ] **Step 11: Commit**

```bash
git add player_settings_page.py tests/test_player_settings_wiring.py
git commit -m "feat(settings): Birth year field persisted to profile (#134)"
```

---

## Task 9: `swing_report_dashboard_preview.py` — honest age nudge

**Files:**
- Modify: `swing_report_dashboard_preview.py` — `_build_score_card` (~line 1729)
- Test: `tests/test_report_two_systems.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_report_two_systems.py` (inside the score-card test class, matching its style):

```python
    def test_age_nudge_shown_when_age_unknown(self):
        """New-engine report with age_known False shows the birth-year nudge."""
        rec = _make_record(swing_score=72)
        rec["age_known"] = False
        html = _srd._build_score_card(rec, history=None)
        assert "birth year" in html.lower()

    def test_age_nudge_absent_when_age_known(self):
        rec = _make_record(swing_score=72)
        rec["age_known"] = True
        html = _srd._build_score_card(rec, history=None)
        assert "birth year" not in html.lower()

    def test_age_nudge_absent_on_legacy_record(self):
        """Legacy record (no swing_score) must not sprout the nudge."""
        rec = _make_legacy_record(score=65)
        html = _srd._build_score_card(rec, history=None)
        assert "birth year" not in html.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/bin/python -m pytest tests/test_report_two_systems.py -q -k age_nudge`
Expected: FAIL (nudge text not present).

- [ ] **Step 3: Implement the nudge**

In `_build_score_card` in `swing_report_dashboard_preview.py`, after the band label is computed (after the `band_label = ...` block, ~line 1745), build the nudge HTML:

```python
    # Honest age nudge (#134): only on new-engine reports (those with a
    # swing_score) where age was unknown, so the score used the default band.
    _is_new_engine = record.get("swing_score") is not None
    _age_unknown = not record.get("age_known", False)
    age_nudge_html = ""
    if _is_new_engine and _age_unknown:
        age_nudge_html = (
            '<div class="srd-age-nudge">Scored on the 13–14 standard — '
            'add your birth year in Settings for an age-accurate score.</div>'
        )
```

Then inject `age_nudge_html` into the card's returned markup. Find the `return` of `_build_score_card` and place `{age_nudge_html}` directly beneath the band label / score header (where it reads as a caption under the number). Match the existing f-string structure — e.g. if the card returns a block containing the band label, add `{age_nudge_html}` immediately after that label element.

- [ ] **Step 4: Add minimal CSS for the nudge**

Find the `srd-*` CSS block in `swing_report_dashboard_preview.py` (search `.srd-pillars` or `srd-` style string) and add:

```css
.srd-age-nudge { margin-top:8px; font-size:12px; line-height:1.4;
  color:rgba(244,239,230,0.62); font-style:italic; }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/bin/python -m pytest tests/test_report_two_systems.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add swing_report_dashboard_preview.py tests/test_report_two_systems.py
git commit -m "feat(report): honest birth-year nudge when age unknown (#134)"
```

---

## Task 10: End-to-end validation + full suite + (gated) migration apply + PR

**Files:** none (validation) — plus the gated DB apply.

- [ ] **Step 1: Full suite green**

Run: `../../../.venv/bin/python -m pytest tests/ -q`
Expected: all pass, 1 skipped (the pre-existing skip). No new failures.

- [ ] **Step 2: End-to-end fingerprint smoke (if a sample video exists)**

If a sample swing video is present (check `validation/videos/` or repo root for `*.mp4`/`*.mov`), run:

```bash
../../../.venv/bin/python detect_phases.py <sample_video> RIGHT --age 11
../../../.venv/bin/python -c "import json,glob; fp=json.load(open(sorted(glob.glob('*_fingerprint.json'))[-1])); print('age=', fp.get('age'), 'stride=', fp.get('stride'))"
```

Expected: prints `age= 11 stride= {'toward_pitcher': ..., 'dx_norm': ...}`. If no sample video is available, skip this step and note it.

- [ ] **Step 3: Confirm back-compat — an age-less, stride-less fingerprint still analyzes**

Run:
```bash
../../../.venv/bin/python -c "
import json, glob
from analyzer import analyze
# use a reference JSON as a stand-in player fingerprint (no age/stride block)
import os
ref = 'references/mike_trout.json'
r = analyze(ref, 'mookie_betts')
print('age_known=', r['age_known'], 'bracket=', r['age_bracket'], 'stride_compliance=', r['pillars']['stride']['compliance'])
"
```
Expected: `age_known= False bracket= 13-14` and a numeric stride compliance (no crash).

- [ ] **Step 4: Gated DB migration apply (ask the user first)**

STOP and ask the user for explicit authorization to apply
`supabase/migrations/2026_05_23_player_birth_year.sql` to the live database.
Only after they confirm, apply it via the Supabase MCP `apply_migration`
(name: `player_birth_year`) or have the user run it. Do NOT apply unprompted.
Until applied, the feature is inert in prod (birth_year reads/writes no-op or
error-soft), which is fine for merging the code.

- [ ] **Step 5: Update PR #23**

```bash
git push
```
Then add a PR comment summarizing the #134 addition (age persistence + stride
direction) so the PR description reflects the now-complete, age-fair build.

---

## Self-review notes

- **Spec coverage:** birth_year column (T3), profile load/save (T4), Settings field (T8), detect_phases age+stride write (T5), app.py age pass (T6), analyzer stride gate + age_known (T7), honest nudge (T9), pure helpers (T1, T2), validation + gated apply (T10). Height/weight untouched (spec: unchanged). ✓
- **Type consistency:** `age_from_birth_year(birth_year, today_year=None) -> Optional[int]` used identically in T1/T6/T8. `stride_direction(...) -> {"toward_pitcher": bool, "dx_norm": float}` used in T2/T5. Fingerprint keys `age` (int) and `stride.toward_pitcher` consumed in T7 exactly as written in T5. `age_known` (bool) emitted in T7, read in T9. ✓
- **Back-compat:** old fingerprints (no `age`/`stride`) → default bracket + lenient stride gate (T7 defaults); legacy reports (no `swing_score`) → no nudge (T9). Migration additive + nullable (T3). ✓
- **Deferred (YAGNI):** full DOB, backfill, historical re-scoring (per spec Out of Scope).
