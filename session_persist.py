"""Durable login — keep the user signed in across page reloads and new tabs.

The app's Supabase session normally lives only in st.session_state (in-memory),
so any full page reload (a refresh, or returning from Stripe Checkout in a new
tab) logs the user out. This module persists the Supabase *refresh token* in a
browser cookie so the session can be silently restored on the next load.

SAFE BY DESIGN: every function swallows its own errors. If cookie persistence
fails for ANY reason, the app simply falls back to today's in-session-only
behavior (the user signs in again). Nothing here can break the existing auth.

Security note: the refresh token is stored in a JS-readable cookie (httpOnly
cannot be set from client JS). This is the same trade-off the official
supabase-js client makes (it persists the session in localStorage). SameSite=Lax
limits cross-site sending; the token is only useful if the app has an XSS hole.
The cookie holds ONLY the refresh token — never the user's password or PII.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

_COOKIE = "bl_session"
_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def read_refresh_token() -> str | None:
    """Refresh token the browser sent with this request, or None.
    Read-only (server-side) — no component render needed."""
    try:
        val = st.context.cookies.get(_COOKIE)
        return val or None
    except Exception:
        return None


# The cookie holds a sensitive credential, so it gets `Secure` on HTTPS. We
# gate it on the live protocol (in JS) rather than hardcoding it, so the cookie
# still works on http://localhost during development. SameSite=Lax keeps it sent
# on the top-level return from Stripe while limiting cross-site exposure.
_SECURE_JS = "var s=(location.protocol==='https:')?'; Secure':'';"


def write_refresh_token(refresh_token: str | None) -> None:
    """Persist the refresh token to a browser cookie (best-effort, invisible)."""
    if not refresh_token:
        return
    try:
        # json.dumps → a safe JS string literal; replace </ so a token can never
        # break out of the <script> tag (defense-in-depth — tokens are URL-safe).
        val = json.dumps(refresh_token).replace("</", "<\\/")
        components.html(
            "<script>" + _SECURE_JS
            + "document.cookie='" + _COOKIE + "='+" + val
            + "+'; max-age=" + str(_MAX_AGE) + "; path=/; SameSite=Lax'+s;</script>",
            height=0,
            width=0,
        )
    except Exception:
        pass


def clear_refresh_token() -> None:
    """Delete the persisted cookie (on sign-out, or when a token is rejected)."""
    try:
        components.html(
            "<script>" + _SECURE_JS
            + "document.cookie='" + _COOKIE
            + "=; max-age=0; path=/; SameSite=Lax'+s;</script>",
            height=0,
            width=0,
        )
    except Exception:
        pass
