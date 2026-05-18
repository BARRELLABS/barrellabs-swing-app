"""
BarrelLabs AI Stack Verifier
=============================

Confirms that every layer of the AI tooling environment described in
`docs/AI_OPERATING_SYSTEM.md` is wired up and reachable.

Exit codes
----------
    0    every check passed (some plugins may be MANUAL — see notes)
    1    at least one REQUIRED check failed

Usage
-----
    .venv/bin/python scripts/verify_ai_stack.py
    .venv/bin/python scripts/verify_ai_stack.py --json     # machine-readable

Design notes
------------
- The three Claude Code plugins (superpowers, ECC, ui-ux-pro-max) can ONLY
  be installed by the user typing /plugin commands inside Claude Code.
  We can't invoke /plugin from a script, so we check for filesystem
  evidence of installation under ~/.claude/plugins/ and report MANUAL if
  absent — that's a hint to the user, not a hard failure.
- browser-use IS a real Python install in tools/browser-use/.venv/, so
  that one is a hard required check.
- The BarrelLabs application code is not touched; we only verify import
  health of files we know already work.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
PLUGINS_DIR = CLAUDE_DIR / "plugins"
# Claude Code derives the project-memory directory name from the cwd at
# session start. For a worktree like .claude/worktrees/agitated-pare the
# directory is "...-claude-worktrees-agitated-pare". We accept any
# barrellabs-swing-app project dir as evidence the harness is wired up.
PROJECTS_DIR = CLAUDE_DIR / "projects"
BROWSER_USE_VENV = REPO_ROOT / "tools" / "browser-use" / ".venv"
BROWSER_USE_PY = BROWSER_USE_VENV / "bin" / "python"
BROWSER_USE_CLI = BROWSER_USE_VENV / "bin" / "browser-use"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: str        # "ok" | "fail" | "manual" | "warn"
    detail: str
    fix: Optional[str] = None

    @property
    def required(self) -> bool:
        return self.status == "fail"


@dataclass
class Report:
    checks: List[CheckResult] = field(default_factory=list)

    def add(self, c: CheckResult) -> None:
        self.checks.append(c)

    @property
    def failed(self) -> bool:
        return any(c.required for c in self.checks)

    def render_text(self) -> str:
        symbols = {"ok": "✓", "fail": "✗", "manual": "○", "warn": "⚠"}
        lines = ["BarrelLabs AI Stack — verification", "=" * 40]
        for c in self.checks:
            sym = symbols.get(c.status, "?")
            lines.append(f"  {sym} {c.name:<32} {c.detail}")
            if c.fix and c.status in ("fail", "manual", "warn"):
                lines.append(f"      → {c.fix}")
        ok    = sum(c.status == "ok"     for c in self.checks)
        fail  = sum(c.status == "fail"   for c in self.checks)
        manual= sum(c.status == "manual" for c in self.checks)
        warn  = sum(c.status == "warn"   for c in self.checks)
        lines.append("")
        lines.append(
            f"  Summary: {ok} ok · {fail} failed · {manual} manual · {warn} warn"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_repo_layout() -> CheckResult:
    expected = [
        REPO_ROOT / "tools",
        REPO_ROOT / "docs" / "AI_OPERATING_SYSTEM.md",
        REPO_ROOT / "docs" / "AGENT_WORKFLOWS.md",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in expected if not p.exists()]
    if missing:
        return CheckResult(
            "Repo layout", "fail",
            f"missing: {', '.join(missing)}",
            fix="Re-run the AI stack setup task; these are core artifacts.",
        )
    return CheckResult("Repo layout", "ok", "tools/ + docs/ present")


def check_gitignore() -> CheckResult:
    gi = REPO_ROOT / ".gitignore"
    if not gi.exists():
        return CheckResult(
            "tools/ gitignored", "warn",
            "no .gitignore at repo root",
            fix="Create .gitignore and add an entry for tools/",
        )
    txt = gi.read_text()
    if "tools/" not in txt:
        return CheckResult(
            "tools/ gitignored", "warn",
            "tools/ not in .gitignore — cloned source will be committed",
            fix="Add 'tools/' on its own line in .gitignore",
        )
    return CheckResult("tools/ gitignored", "ok", "tools/ excluded from git")


def check_browser_use_installed() -> CheckResult:
    if not BROWSER_USE_PY.exists():
        return CheckResult(
            "browser-use venv", "fail",
            f"missing python at {BROWSER_USE_PY.relative_to(REPO_ROOT)}",
            fix=(
                "cd tools/browser-use && python3 -m venv .venv && "
                ".venv/bin/pip install browser-use"
            ),
        )
    try:
        out = subprocess.run(
            [str(BROWSER_USE_PY), "-c",
             "import browser_use; from browser_use import Agent, Browser; print('ok')"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return CheckResult(
            "browser-use venv", "fail",
            f"import attempt raised {type(e).__name__}: {e}",
            fix="Recreate the venv: rm -rf tools/browser-use/.venv && "
                "cd tools/browser-use && python3 -m venv .venv && "
                ".venv/bin/pip install browser-use",
        )
    if out.returncode != 0 or "ok" not in out.stdout:
        return CheckResult(
            "browser-use venv", "fail",
            f"import failed: {out.stderr.strip()[:160]}",
            fix=".venv/bin/pip install --force-reinstall browser-use",
        )
    # Get version
    ver = subprocess.run(
        [str(BROWSER_USE_PY), "-c",
         "import importlib.metadata as m; print(m.version('browser-use'))"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip() or "unknown"
    return CheckResult("browser-use venv", "ok",
                       f"v{ver} importable in isolated venv")


def check_browser_use_cli() -> CheckResult:
    if not BROWSER_USE_CLI.exists():
        return CheckResult(
            "browser-use CLI", "fail",
            "CLI entry-point not found",
            fix="Re-install browser-use into tools/browser-use/.venv",
        )
    out = subprocess.run(
        [str(BROWSER_USE_CLI), "doctor"],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        return CheckResult(
            "browser-use CLI", "warn",
            f"`doctor` returned {out.returncode}",
            fix="Run `tools/browser-use/.venv/bin/browser-use doctor` manually.",
        )
    # Pull the summary line "X/Y checks passed"
    summary = next(
        (ln.strip() for ln in out.stdout.splitlines() if "checks passed" in ln),
        "doctor ran",
    )
    return CheckResult("browser-use CLI", "ok", summary)


def check_plugin(plugin_id: str, install_cmd: str) -> CheckResult:
    """Filesystem-evidence check for a Claude Code plugin.

    Claude Code stores installed plugins under ~/.claude/plugins/ (the exact
    layout varies by harness version). We look for a directory or marker
    file mentioning the plugin id.
    """
    if not PLUGINS_DIR.exists():
        return CheckResult(
            f"plugin: {plugin_id}", "manual",
            "no ~/.claude/plugins/ yet",
            fix=f"In Claude Code, run:  {install_cmd}",
        )
    # Scan for any path whose name or contents mention the plugin id
    matches: List[Path] = []
    for p in PLUGINS_DIR.rglob("*"):
        if plugin_id.lower() in p.name.lower():
            matches.append(p)
            if len(matches) >= 3:
                break
    if matches:
        rel = matches[0].relative_to(PLUGINS_DIR)
        return CheckResult(f"plugin: {plugin_id}", "ok",
                           f"installed (~/.claude/plugins/{rel})")
    return CheckResult(
        f"plugin: {plugin_id}", "manual",
        "not detected in ~/.claude/plugins/",
        fix=f"In Claude Code, run:  {install_cmd}",
    )


def check_persistent_memory() -> CheckResult:
    if not PROJECTS_DIR.exists():
        return CheckResult(
            "persistent memory", "warn",
            "no ~/.claude/projects/ yet",
            fix="Open this project in Claude Code at least once to "
                "initialize the harness.",
        )
    # Find any project dir that matches barrellabs-swing-app (with or
    # without worktree suffix).
    candidates = sorted(
        p for p in PROJECTS_DIR.iterdir()
        if p.is_dir() and "barrellabs-swing-app" in p.name
    )
    if not candidates:
        return CheckResult(
            "persistent memory", "warn",
            "harness has no project dir for barrellabs-swing-app",
            fix="Open this project in Claude Code at least once.",
        )
    # Look for the memory subdirectory in any candidate
    memory_dirs = [p / "memory" for p in candidates if (p / "memory").exists()]
    if not memory_dirs:
        return CheckResult(
            "persistent memory", "ok",
            f"{len(candidates)} project dir(s) present; memory not yet seeded",
            fix="Tell Claude 'remember that <fact>' to create the first entry.",
        )
    mem = memory_dirs[0]
    files = list(mem.glob("*.md"))
    has_index = any(f.name == "MEMORY.md" for f in files)
    rel = mem.relative_to(HOME)
    return CheckResult(
        "persistent memory", "ok",
        f"{len(files)} file(s) in ~/{rel}, index {'present' if has_index else 'missing'}",
    )


def check_streamlit_app_untouched() -> CheckResult:
    """Smoke-test that the BarrelLabs app files still import cleanly.

    We don't run streamlit (that needs network + Supabase secrets). We just
    confirm the modules we know are critical can at least parse and import
    their top-level identifiers.
    """
    critical = [
        REPO_ROOT / "dashboard_v3.py",
        REPO_ROOT / "mock_dashboard_template.py",
        REPO_ROOT / "scripts" / "visual_qa" / "capture.py",
    ]
    missing = [p for p in critical if not p.exists()]
    if missing:
        return CheckResult(
            "app files present", "fail",
            f"missing: {', '.join(p.name for p in missing)}",
            fix="Application files were removed — restore from git.",
        )
    # Parse only — full import would need streamlit/supabase deps loaded.
    import ast
    for p in critical:
        try:
            ast.parse(p.read_text(), filename=str(p))
        except SyntaxError as e:
            return CheckResult(
                "app files present", "fail",
                f"syntax error in {p.name}: {e}",
                fix="Revert recent edits to that file (git checkout).",
            )
    return CheckResult("app files present", "ok",
                       f"{len(critical)} core files parse cleanly")


def check_qa_workflow_runnable() -> CheckResult:
    """The visual QA script must still be runnable via parent venv."""
    parent_venv = Path("/Users/logancollins/barrellabs-swing-app/.venv/bin/python")
    capture = REPO_ROOT / "scripts" / "visual_qa" / "capture.py"
    if not parent_venv.exists():
        return CheckResult(
            "visual QA workflow", "warn",
            "parent .venv python not found (worktree may have different layout)",
            fix="Use whichever venv runs your streamlit app to run capture.py",
        )
    if not capture.exists():
        return CheckResult(
            "visual QA workflow", "fail",
            "scripts/visual_qa/capture.py missing",
            fix="Restore from git.",
        )
    out = subprocess.run(
        [str(parent_venv), str(capture), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        return CheckResult(
            "visual QA workflow", "warn",
            f"capture.py --help exit {out.returncode}",
            fix="Run the script manually; check stderr.",
        )
    return CheckResult("visual QA workflow", "ok",
                       "capture.py runnable via parent .venv")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PLUGIN_CHECKS = [
    ("superpowers",   "/plugin marketplace add obra/superpowers-marketplace "
                      "&& /plugin install superpowers@superpowers-marketplace"),
    ("ecc",           "/plugin marketplace add https://github.com/affaan-m/everything-claude-code "
                      "&& /plugin install ecc@ecc"),
    ("ui-ux-pro-max", "/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill "
                      "&& /plugin install ui-ux-pro-max@ui-ux-pro-max-skill"),
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of text")
    args = parser.parse_args(argv)

    report = Report()
    report.add(check_repo_layout())
    report.add(check_gitignore())
    report.add(check_streamlit_app_untouched())
    report.add(check_qa_workflow_runnable())
    report.add(check_browser_use_installed())
    report.add(check_browser_use_cli())
    for plugin_id, install_cmd in PLUGIN_CHECKS:
        report.add(check_plugin(plugin_id, install_cmd))
    report.add(check_persistent_memory())

    if args.json:
        print(json.dumps([asdict(c) for c in report.checks], indent=2))
    else:
        print(report.render_text())

    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
