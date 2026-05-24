"""Subprocess helper with a hard timeout.

The pose-detection step runs detect_phases.py as a child process. Without a
timeout a corrupt/huge/odd-codec clip can make mediapipe or cv2 hang, blocking
the synchronous Streamlit worker indefinitely behind a spinner with no
recovery. Capping it and returning a non-zero return code lets the existing
"Pose detection failed" path surface a real error instead.
"""
from __future__ import annotations

import subprocess

# Pose detection is advertised as ~30-60s; 180s leaves generous headroom for a
# slow clip while still bounding a genuine hang.
DEFAULT_TIMEOUT_S = 180

# Conventional shell exit code for a timed-out command.
_TIMEOUT_RC = 124


def run_subprocess(args, cwd, timeout: int = DEFAULT_TIMEOUT_S):
    """Run ``args`` in ``cwd``, capturing output. Returns
    ``(returncode, stdout, stderr)``. On timeout, returns a non-zero code and
    an explanatory stderr rather than hanging."""
    try:
        proc = subprocess.run(
            args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stderr or exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        return _TIMEOUT_RC, "", f"Timed out after {timeout}s.\n{partial}"
    return proc.returncode, proc.stdout, proc.stderr
