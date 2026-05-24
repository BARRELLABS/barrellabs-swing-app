"""Per-upload filename namespacing.

Streamlit serves every user from one process and one working directory, and
the upload pipeline derives every artifact (`*_fingerprint.json`,
`*_phases.png`, …) from the uploaded video's stem. If two users (or two
tabs) upload the same filename — and phone exports collide constantly
("IMG_1234.mov", "swing.mp4") — they overwrite each other's video and
fingerprint mid-analysis, so one user can get a report built from another's
swing. Giving the saved upload a collision-resistant, sanitized name
isolates the whole chain in one place (and drops any path-traversal in the
client-supplied filename).
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

# Components are restricted to a strict alphabet — no dots, so "../" can't
# survive as a traversal sequence. The extension is handled separately.
_UNSAFE = re.compile(r"[^A-Za-z0-9-]+")
_UNSAFE_EXT = re.compile(r"[^a-z0-9]+")


def _clean(value: str | None, fallback: str, maxlen: int) -> str:
    out = _UNSAFE.sub("-", value or "").strip("-")
    return out[:maxlen] or fallback


def unique_upload_name(original_name: str, *, owner: str | None = None,
                       token: str | None = None) -> str:
    """Return a collision-resistant on-disk filename for a user upload.

    Format: ``<owner>_<token>_<stem-hint><.ext>``. The owner tag and a random
    per-call token guarantee uniqueness across users and tabs; the sanitized
    stem hint keeps the name debuggable. ``token`` is injectable for tests.
    """
    p = Path(original_name or "swing")
    ext = _UNSAFE_EXT.sub("", p.suffix.lower().lstrip("."))[:8] or "mp4"
    stem_hint = _clean(p.stem, "swing", 40)
    owner_tag = _clean(owner, "anon", 24)
    tok = token or uuid.uuid4().hex
    return f"{owner_tag}_{tok}_{stem_hint}.{ext}"
