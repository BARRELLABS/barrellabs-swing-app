# AI Operating System — BarrelLabs

This document describes the AI tooling layer installed around the BarrelLabs
codebase. Each tool is treated as a **separate concern** with its own install
path and runtime — none of them are pip-installed into the Streamlit app's
`.venv`, so production code keeps a clean dependency surface.

| Tier | Tool | Lives in | What it does |
|---|---|---|---|
| Plugin | Superpowers | `~/.claude/plugins/` | Methodology + skill bundle that upgrades how Claude Code plans, reviews, and tests work |
| Plugin | Everything Claude Code (ECC) | `~/.claude/plugins/` | Performance/optimization layer: hooks, security rules, memory tuning |
| Plugin | UI/UX Pro Max Skill | `~/.claude/plugins/` | Design-system intelligence — colors, type pairings, industry rules |
| Library | browser-use | `tools/browser-use/.venv/` | Headless browser agent for real-browser QA, scraping, and reproducer scripts |
| Built-in | Persistent memory | `~/.claude/projects/<proj>/memory/` | File-based memory the Claude Code harness already loads each session |

---

## Why this layout

- **`/tools/` is git-ignored.** Cloned source lives here for reference and
  customisation; nothing in it ships in PRs.
- **Plugins are user-scoped, not project-scoped.** Once installed they work
  across every repo you open with Claude Code. We document the exact install
  commands below — but you run them yourself in Claude Code (the harness
  doesn't let agents invoke `/plugin` for you).
- **browser-use gets its own venv.** It pulls in Playwright + multiple LLM
  SDKs; mixing those into `.venv` would force-upgrade `pydantic`, `httpx`,
  `anyio`, and likely break Streamlit and the Supabase client.

---

## 1. Superpowers — Methodology + skill bundle

**What it is:** Jesse Vincent's "complete software development methodology
for coding agents." It's a curated bundle of skills (planning, code review,
testing patterns) plus prompts that change how Claude Code approaches tasks.

**Install (run in Claude Code):**

```text
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Alternative (official Anthropic marketplace, simpler):

```text
/plugin install superpowers@claude-plugins-official
```

**How to use:**
- After install, Superpowers exposes new skills via the Skill tool — Claude
  picks them up automatically when a task matches.
- Look for `/superpowers:*` commands in `/help` once installed.
- The methodology emphasises **planning before coding, code review by a
  separate sub-agent, and explicit test plans**. Match BarrelLabs' existing
  worktree workflow (`claude/...` branches → PR → merge).

**Where to keep an eye on it:** if you ever see Superpowers' rules
contradicting our `mock_dashboard_template.py` style (single-source-of-truth
in `dashboard_v3.py`), prefer ours.

---

## 2. Everything Claude Code (ECC) — Performance & guardrails

**What it is:** A performance-optimization layer for agent harnesses: hooks,
security scanning, memory rules, production-readiness checklists. Hackathon
winner from Anthropic's internal hackathon.

**Install (run in Claude Code):**

```text
/plugin marketplace add https://github.com/affaan-m/everything-claude-code
/plugin install ecc@ecc
```

**Do NOT also run `./install.sh`** — ECC explicitly warns that stacking the
plugin install with the shell installer creates duplicate hooks and breaks
functionality. Pick one path. We chose the plugin path because it's
removable via `/plugin uninstall`.

**How to use:**
- Adds hooks under `~/.claude/hooks/` that run on tool calls (PreToolUse,
  PostToolUse, etc.). These are the harness's hooks, not application code.
- Adds rule files under `~/.claude/rules/ecc/` that Claude consults
  automatically when the matching tag triggers.
- Best paired with Superpowers — ECC is the *enforcement* layer (security,
  perf), Superpowers is the *methodology* layer (planning, review).

---

## 3. UI/UX Pro Max Skill — Design intelligence

**What it is:** A Claude Code skill that injects design-system reasoning:
67 UI styles, 161 color palettes, 57 font pairings, 161 industry rules.
Generates pre-delivery checklists tailored to product type (sports tech,
fintech, etc.).

**Install (run in Claude Code):**

```text
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

**How to use:**
- When you ask Claude to design a new screen or polish an existing one in
  `mock_dashboard_template.py` / `dashboard_v3.py`, the skill activates and
  suggests palettes / type pairings aligned to **sports analytics** as the
  industry vertical.
- It complements our existing visual QA workflow (`scripts/visual_qa/`) —
  UI/UX Pro Max suggests *what* to design, the QA script verifies *that it
  rendered* at four viewports.

**Industry tag to use in prompts:** `sports tech` or `sports analytics`
(maps to colour systems like ours: bone-white serif headlines, gold
accents, deep gray surfaces).

---

## 4. browser-use — Headless browser agent

**What it is:** A Python library + CLI (`browser-use`) that gives an LLM
agent control of a real Chromium browser via Playwright. Useful for:

- End-to-end testing flows the visual QA pipeline can't cover (login,
  Stripe checkout, Supabase magic-link auth)
- Reproducing user-reported bugs by replaying them in a browser
- Lightweight scraping of comp/reference data (MLB stats, etc.)

**Install (already done):**

```bash
# Already executed during setup:
cd tools/browser-use
python3 -m venv .venv
.venv/bin/pip install browser-use
```

The clone at `tools/browser-use/` is the upstream source — only the
`.venv/` inside it actually runs. Keep them in sync if you ever `git pull`.

**How to use — CLI (no Python needed):**

```bash
# Activate the dedicated venv
source tools/browser-use/.venv/bin/activate

# One-shot navigation
browser-use open https://barrellabs.streamlit.app

# Agent-driven task
browser-use --headed
# (then issue commands; session persists across browser-use calls)

# Sanity check installation
browser-use doctor
```

**How to use — as a library:**

```python
# Run from inside tools/browser-use/.venv
from browser_use import Agent, Browser
# … see tools/browser-use/README.md for examples
```

**Limitations:**
- Needs an LLM API key (Anthropic, OpenAI, Gemini, or local Ollama). Set
  `ANTHROPIC_API_KEY` or equivalent before running agent mode.
- `cloudflared` and `profile-use` are optional features and are NOT
  installed. Tunneling and named-profile management won't work until you
  install those.
- Do NOT add `browser-use` to BarrelLabs' top-level `.venv` — keep it
  isolated. If the Streamlit app ever needs browser automation in
  production, shell out to the CLI rather than importing.

---

## 5. Persistent memory — built-in, no install

The Claude Code harness already provides a file-based memory system at:

```
/Users/logancollins/.claude/projects/-Users-logancollins-barrellabs-swing-app/memory/
```

Files in here are loaded automatically each session via `MEMORY.md` (an
index of pointers to individual memory files). The system already
understands four memory types: **user**, **feedback**, **project**,
**reference**.

**You do not need a third-party "claude-mem" package** — and the one the
original task listed (`TheDotMac/claude-mem`) does not exist at that URL.

**How to use:**
- Tell Claude "remember that X" and it will write a memory file + add an
  index entry to `MEMORY.md`.
- Tell Claude "forget X" and it will remove it.
- Memories about repo structure, file paths, or git history are *not* saved
  — those are re-derivable from the code itself.

See **AGENT_WORKFLOWS.md → Persistent memory** for patterns.

---

## Dependency isolation summary

| Tool | Where deps live | Risk to BarrelLabs `.venv` |
|---|---|---|
| Superpowers | `~/.claude/plugins/` | None (no Python deps) |
| ECC | `~/.claude/plugins/` | None (no Python deps) |
| UI/UX Pro Max | `~/.claude/plugins/` | None (no Python deps) |
| browser-use | `tools/browser-use/.venv/` | None (separate venv) |
| Built-in memory | `~/.claude/projects/…/memory/` | None (filesystem only) |

The BarrelLabs application code in `dashboard_v3.py`, `mock_dashboard_template.py`,
`scripts/visual_qa/capture.py`, etc., is unchanged.

---

## Verifying everything is wired up

```bash
.venv/bin/python scripts/verify_ai_stack.py
```

The script exits 0 if every check passes, non-zero with a clear failure
message otherwise. See `scripts/verify_ai_stack.py` for what it checks.
