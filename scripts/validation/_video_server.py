"""Standalone HTTP file server for serving validation videos.

Streamlit's enableStaticServing doesn't reliably work in 1.57 for our use
case (paths get shadowed by the SPA shell), so we run a dedicated HTTP
server on a separate port that just streams the files in
`static/videos/` with proper MIME types and Range support.

Started as a daemon thread from labeling_app.py on import. Idempotent —
if the port is already in use we assume another instance is serving.

Usage from labeling_app.py:
    from scripts.validation._video_server import ensure_running, port
    ensure_running()
    video_url = f"http://localhost:{port()}/videos/<filename>.mp4"
"""

from __future__ import annotations

import http.server
import os
import socket
import socketserver
import threading
from pathlib import Path
from typing import Optional


VIDEO_SERVER_PORT = 8504
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"


_lock = threading.Lock()
_started = False


class _StreamingHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that serves from STATIC_DIR with CORS
    headers + Range support (built into SimpleHTTPRequestHandler in
    Python 3.7+) so the browser can seek inside <video>."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        # Permit the Streamlit app (which runs on a different port) to
        # embed our videos in a <video> tag via CORS.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers",
                         "Content-Length, Content-Range")
        super().end_headers()

    def log_message(self, format, *args):
        # Silence the access log — Streamlit's logs are noisy enough
        return


def _port_in_use(host: str, port_: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port_))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def port() -> int:
    return VIDEO_SERVER_PORT


def ensure_running() -> None:
    """Start the video-file server in a background thread if it's not
    already running. Safe to call repeatedly."""
    global _started
    with _lock:
        if _started:
            return
        # If something is already listening on our port (e.g. another
        # Streamlit session started one), assume it's our server.
        if _port_in_use("127.0.0.1", VIDEO_SERVER_PORT):
            _started = True
            return
        STATIC_DIR.mkdir(parents=True, exist_ok=True)

        class _ReusableTCP(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        httpd = _ReusableTCP(("127.0.0.1", VIDEO_SERVER_PORT), _StreamingHandler)
        t = threading.Thread(
            target=httpd.serve_forever, daemon=True, name="video-server",
        )
        t.start()
        _started = True


if __name__ == "__main__":
    ensure_running()
    print(f"Serving {STATIC_DIR}/ at http://localhost:{VIDEO_SERVER_PORT}/")
    print("Press Ctrl+C to stop.")
    import time as _t
    while True:
        _t.sleep(3600)
