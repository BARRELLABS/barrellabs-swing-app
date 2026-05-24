"""run_subprocess must cap runtime so a hung child (mediapipe on a corrupt or
huge clip) can't block the Streamlit worker forever — a timeout returns a
non-zero rc the caller already surfaces, not an infinite hang."""
import sys

from proc_utils import run_subprocess


def test_success_returns_zero_and_stdout(tmp_path):
    rc, out, err = run_subprocess(
        [sys.executable, "-c", "print('hi')"], cwd=tmp_path)
    assert rc == 0
    assert "hi" in out


def test_nonzero_exit_propagates(tmp_path):
    rc, out, err = run_subprocess(
        [sys.executable, "-c", "import sys; sys.exit(3)"], cwd=tmp_path)
    assert rc == 3


def test_timeout_returns_error_not_hang(tmp_path):
    rc, out, err = run_subprocess(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path, timeout=1)
    assert rc != 0
    assert "timed out" in err.lower()
