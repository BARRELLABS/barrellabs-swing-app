"""Pure-Python text helpers for the validation tooling. No Streamlit
deps so it's importable from tests without side effects."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(raw: str) -> str:
    """Turn an arbitrary filename or label into a safe swing_id.

    Lowercases, replaces any run of non-alphanumeric chars with a single
    underscore, strips leading/trailing underscores. Falls back to
    ``"swing"`` for inputs that produce an empty result.
    """
    s = _SLUG_RE.sub("_", raw.strip().lower())
    s = s.strip("_")
    return s or "swing"
