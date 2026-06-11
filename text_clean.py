"""App-wide em-dash scrubber.

We never want em dashes in user-facing copy ("the ai dashes"). They're scattered
through generated headlines, narratives, drill copy, trend insights, etc., across
many render paths, and most literal "—" in the source is in code/CSS comments
(which must NOT be touched). So rather than edit source strings, we scrub at the
RENDER boundary: wrap st.markdown / st.html / components.html once so every bit of
copy that actually reaches the page gets cleaned. Comments are gone by then, so
they're never affected.

Only the SPACED pattern " — " (prose punctuation) is replaced with ", ". The bare
"—" glyph is left alone because it's used as an empty-value placeholder in tables
and tiles. Idempotent, so double-scrubbing (e.g. the report already scrubs its own
body) is harmless.

Install once, early, from app.py:  from text_clean import install_em_dash_scrubber
                                    install_em_dash_scrubber()
"""

from __future__ import annotations


def scrub_em_dashes(s):
    """Replace the spaced em dash (prose) with a comma. Non-str / no-match
    values pass through unchanged."""
    if isinstance(s, str) and " — " in s:
        return s.replace(" — ", ", ")
    return s


_installed = False


def install_em_dash_scrubber() -> None:
    """Monkeypatch the Streamlit HTML render entry points so any copy reaching
    the page is em-dash-free. Safe to call multiple times (no-ops after first)."""
    global _installed
    if _installed:
        return
    _installed = True

    try:
        import streamlit as st
    except Exception:
        return

    def _wrap_first_arg(orig, argname):
        def _wrapped(*args, **kwargs):
            if args:
                args = (scrub_em_dashes(args[0]),) + args[1:]
            elif argname in kwargs:
                kwargs[argname] = scrub_em_dashes(kwargs[argname])
            return orig(*args, **kwargs)
        return _wrapped

    # st.markdown(body, ...) and st.html(body) — the bulk of inline copy.
    try:
        st.markdown = _wrap_first_arg(st.markdown, "body")
    except Exception:
        pass
    try:
        if hasattr(st, "html"):
            st.html = _wrap_first_arg(st.html, "body")
    except Exception:
        pass

    # components.html(html, ...) — the iframe surfaces (dashboard, report, etc.).
    try:
        import streamlit.components.v1 as components
        components.html = _wrap_first_arg(components.html, "html")
    except Exception:
        pass
