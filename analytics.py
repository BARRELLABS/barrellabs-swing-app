"""Product analytics (PostHog) — track the funnel so you can see what works.

Right now you can't tell how many people sign up, run a swing, or convert to
Pro. This wires up PostHog server-side event tracking to answer that.

To turn it on: add to `.streamlit/secrets.toml`:
    [posthog]
    api_key = "phc_..."          # Project API Key from posthog.com
    host    = "https://us.i.posthog.com"   # or https://eu.i.posthog.com

Until that's set, every call here is a complete no-op — zero overhead, never
raises, safe to ship now. Add the key later and events start flowing.

Usage:
    import analytics
    analytics.track("swing_analyzed", user_id, edge_score=82, bracket="13-14")
"""
from __future__ import annotations

import os

_client = None
_resolved = False


def _get_client():
    """Lazily build the PostHog client from secrets/env, or None if unconfigured."""
    global _client, _resolved
    if _resolved:
        return _client
    _resolved = True

    api_key = None
    host = "https://us.i.posthog.com"
    try:
        import streamlit as st
        cfg = st.secrets.get("posthog", {}) or {}
        api_key = cfg.get("api_key")
        host = cfg.get("host") or host
    except Exception:
        pass
    api_key = api_key or os.environ.get("POSTHOG_API_KEY")
    host = os.environ.get("POSTHOG_HOST") or host
    if not api_key:
        return None
    try:
        from posthog import Posthog
        _client = Posthog(project_api_key=api_key, host=host)
    except Exception:
        _client = None
    return _client


def track(event: str, user_id: str | None, **properties) -> None:
    """Record a product event (best-effort). No-op if PostHog isn't configured
    or anything goes wrong — never breaks the app flow."""
    try:
        client = _get_client()
        if client is None:
            return
        client.capture(
            distinct_id=str(user_id) if user_id else "anonymous",
            event=event,
            properties={k: v for k, v in properties.items() if v is not None},
        )
    except Exception:
        pass
