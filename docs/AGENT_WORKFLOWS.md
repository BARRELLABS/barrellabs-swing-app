# Agent Workflows — BarrelLabs

Concrete, repeatable patterns for using the AI Operating System (see
`AI_OPERATING_SYSTEM.md`) to do real BarrelLabs work. Each workflow names
the tools it depends on and is written as a prompt you can paste.

---

## 1. UI/UX design review

**Tools:** UI/UX Pro Max Skill · visual QA workflow · (optional) Superpowers
review skill

### When to run
- Before merging any change to `mock_dashboard_template.py` or
  `dashboard_v3.py` that affects layout, type scale, colour, or section
  composition.
- When prototyping a new dashboard section.

### Workflow

```
1. Capture baseline screenshots:
   .venv/bin/python scripts/visual_qa/capture.py --label before-<topic>

2. Prompt Claude:
   "Run a UI/UX design review against industry 'sports analytics'.
    Look at the latest screenshots under
    .visual_qa/screenshots/<latest>/ and the rendered HTML in the same
    folder. Flag any conflicts with our design system (bone serif
    headlines, gold accents, mono labels) and propose CSS-only fixes."

3. Apply fixes — CSS-only patches in mock_dashboard_template.py only.
   Never restructure markup unless the task explicitly requires it.

4. Re-capture and confirm:
   .venv/bin/python scripts/visual_qa/capture.py --label after-<topic>

5. Add a new PASS section to VISUAL_QA_REPORT.md with before/after
   dimensions and resolved/deferred findings.
```

### Gotchas
- The UI/UX Pro Max skill suggests palettes — but our palette is already
  fixed (`--bone`, `--gold`, `--gray-1`, etc. in
  `mock_dashboard_template.py:75-85`). Use the skill for *spacing rhythm,
  type pairings, and section composition*, not for colour overrides.
- Screenshot files in `.visual_qa/screenshots/` are gitignored — only the
  `VISUAL_QA_REPORT.md` ships in commits.

---

## 2. Automated QA

**Tools:** visual QA capture script · browser-use · `scripts/verify_ai_stack.py`

### Visual QA (already built)

```bash
.venv/bin/python scripts/visual_qa/capture.py --label <label>
```

Renders the v3 dashboard to a static HTML file (via dashboard_v3's swap +
block-replacement pipeline with synthetic swing history) and screenshots it
at 4 widths (1600 / 1280 / 900 / 430). See `scripts/visual_qa/README.md`.

### End-to-end QA (when needed)

For flows the visual QA script can't simulate — auth, Stripe checkout,
Supabase magic-link, multi-step nav — use browser-use:

```bash
source tools/browser-use/.venv/bin/activate

# Manual repro
browser-use open https://barrellabs.streamlit.app/?page=pricing
browser-use click "Family Pro · Upgrade"
browser-use screenshot

# Agent-driven
ANTHROPIC_API_KEY=… browser-use --headed
> "Open the BarrelLabs dashboard, log in with the magic link from
>  test@barrellabs.test, navigate to the pricing band, and confirm the
>  annual sub-line shows 'save 45% vs monthly' in gold while the monthly
>  sub-line shows 'billed monthly · cancel anytime' in muted gray."
```

### Stack-health QA

```bash
.venv/bin/python scripts/verify_ai_stack.py
```

Run after any change to the tool layer (new plugin, browser-use upgrade,
venv rebuild). Exits non-zero if anything is broken.

---

## 3. Coding and refactoring

**Tools:** Superpowers (planning + review) · ECC (security/perf rules) ·
built-in Claude Code tools (Edit, Read, Glob, Grep)

### Pattern: small fix

```
1. Read the affected file directly. Do not "explore" first — go straight
   to the file once you know its name.
2. Make the minimal Edit. No drive-by cleanup.
3. Verify (run the test, capture a screenshot, re-render the HTML).
4. Commit with a message that names the user-visible change.
```

### Pattern: non-trivial change (Superpowers' planning skill should fire)

```
1. Ask Claude to enter plan mode for the change. Superpowers' planning
   skill will produce a step-by-step plan with file paths and trade-offs.
2. Approve or edit the plan. (Plan mode blocks file writes.)
3. Exit plan mode → execute step-by-step, marking tasks complete one at
   a time.
4. After the implementation, prompt Claude to "Run a code review on the
   diff" — Superpowers' review skill spawns a subagent that re-reads the
   diff with fresh eyes. This catches the "I wrote it so it must be
   right" bias.
5. Address review feedback, re-run tests, commit.
```

### Pattern: refactoring across many files

```
1. Use Grep to enumerate every call site.
2. Spawn a Plan subagent with the full list. Plan mode produces the
   sequence of edits.
3. Apply edits one file at a time, NOT in bulk. After each file:
   - run the relevant test (or render the dashboard)
   - commit
4. ECC's security rules will flag risky patterns (eval, dynamic SQL,
   exec) automatically; respect those rather than skipping.
```

### What NOT to do (carried over from existing project feedback)
- Don't add docstrings/comments/type-annotations to code you didn't change.
- Don't add error handling, fallbacks, or validation for impossible cases.
- Don't refactor for "future flexibility" — three similar lines beats a
  premature abstraction.
- Don't bypass safety checks (`--no-verify`, etc.) — investigate the root
  cause.

---

## 4. Persistent memory

**Tools:** Built-in Claude Code memory (no plugin needed)

### The four memory types

| Type | Save when… | Example |
|---|---|---|
| `user` | You learn about Logan's role, preferences, expertise | "Logan is the founder of BarrelLabs; full-stack Python/Streamlit; prefers minimal/no comments unless logic is non-obvious" |
| `feedback` | Logan corrects an approach OR confirms a non-obvious one worked | "Pricing band sub-lines must visually distinguish savings (gold) from assurance (muted) — confirmed PASS 3" |
| `project` | You learn about goals, deadlines, or stakeholders not visible in code | "v3 'Edge' dashboard is the default; v1 and v2 are URL-fallbacks only" |
| `reference` | You learn where info lives in external systems | "Synthetic swing history for QA is generated inline by `dashboard_v3.py`" |

### Workflow

**Save:** "Remember that we always do CSS-only patches in
`mock_dashboard_template.py` for layout polish — never markup changes
unless the task requires it." → Claude writes
`~/.claude/projects/.../memory/feedback_css_only_polish.md` and adds it to
`MEMORY.md`.

**Recall:** "What do you remember about how we approach dashboard polish?"
→ Claude reads `MEMORY.md`, opens any matching feedback files, and answers.

**Forget:** "Forget what we said about pricing tier widths." → Claude
removes the relevant file and updates `MEMORY.md`.

### What NOT to save

- Code patterns, conventions, file paths, project structure → re-derivable
  from the code.
- Git history / who-changed-what → `git log` / `git blame` are authoritative.
- Debugging fix recipes → the fix is in the code; commit message has context.
- Ephemeral task state → use the TodoWrite tool instead.

### Verifying memory state

```bash
ls ~/.claude/projects/-Users-logancollins-barrellabs-swing-app/memory/
cat ~/.claude/projects/-Users-logancollins-barrellabs-swing-app/memory/MEMORY.md
```

`MEMORY.md` is an index, not a memory — keep entries to one line each,
under ~150 chars.

---

## Combining workflows: a worked example

**Scenario:** "Polish the highlight reel on the dashboard."

```
1. [Coding/refactoring · Pattern: non-trivial]
   Enter plan mode. Plan: read .highlight-reel CSS + markup in
   mock_dashboard_template.py, identify polish opportunities.

2. [UI/UX design review]
   Capture before screenshots.
   UI/UX Pro Max suggests: 16:9 aspect lock, hover lift on tiles,
   gold play-button accent.

3. [Coding/refactoring]
   Apply CSS-only patches.

4. [UI/UX design review]
   Capture after screenshots.
   Document in VISUAL_QA_REPORT.md as PASS N.

5. [Automated QA]
   .venv/bin/python scripts/visual_qa/capture.py
   .venv/bin/python scripts/verify_ai_stack.py

6. [Persistent memory]
   "Remember that highlight reel polish uses a 16:9 aspect lock with
    a gold play-button accent." → saves as feedback memory.

7. Commit. PR. Merge.
```
