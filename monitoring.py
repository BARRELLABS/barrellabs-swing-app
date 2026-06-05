"""Error monitoring — initializes Sentry if a DSN is configured, else a no-op.

Today the app could crash silently in production and nobody knew until a user
hit it. This wires up Sentry so unhandled errors get reported automatically.

To turn it on: add a DSN under `[sentry] dsn = "https://..."` in
`.streamlit/secrets.toml` (or set the `SENTRY_DSN` env var). Until you do, this
is a complete no-op — zero overhead, never raises, safe to ship now.
"""
from __future__ import annotations

import os

_initialized = False


def init_monitoring() -> None:
    """Initialize Sentry once per process if a DSN is configured. Safe no-op
    otherwise — never raises, never blocks app startup."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    dsn = None
    try:
        import streamlit as st
        dsn = (st.secrets.get("sentry", {}) or {}).get("dsn")
    except Exception:
        dsn = None
    dsn = dsn or os.environ.get("SENTRY_DSN")
    if not dsn:
        return  # not configured yet — stay a no-op

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            # Errors only — no performance tracing (keeps cost + overhead at 0).
            traces_sample_rate=0.0,
            # Don't ship user PII (emails, IPs) to a third party by default.
            send_default_pii=False,
            environment=os.environ.get("SENTRY_ENV", "production"),
        )
    except Exception:
        # sentry-sdk missing or init failed — never let monitoring break the app.
        pass


def capture(exc: BaseException, **context) -> None:
    """Manually report a caught exception (best-effort). Use in except blocks
    where the error is swallowed but you still want visibility."""
    try:
        import sentry_sdk
        if context:
            with sentry_sdk.push_scope() as scope:
                for k, v in context.items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass
