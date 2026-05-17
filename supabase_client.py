"""
Supabase client singleton + session helpers.

The Supabase client is created once and cached so every module shares
the same auth state. The auth tokens for the currently logged-in user
are kept in st.session_state["supabase_session"] and re-applied to the
client on every Streamlit rerun (Streamlit reloads the whole script on
every interaction, so this matters).

Usage
-----
    from supabase_client import get_client, get_current_user

    sb = get_client()
    user = get_current_user()
    if user:
        rows = sb.table("players").select("*").eq("user_id", user.id).execute()
"""

import time

import streamlit as st

try:
    from supabase import create_client, Client
except ImportError as exc:
    # Surface a useful error inside the app instead of a confusing
    # ModuleNotFoundError stack trace.
    raise RuntimeError(
        "supabase-py is not installed. Run:\n"
        "    ./venv/bin/pip install supabase\n"
        "and restart the app."
    ) from exc


# --------------------------------------------------------------------
#  Singleton client
# --------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _build_client() -> "Client":
    """Build the Supabase client once per process."""
    cfg = st.secrets["supabase"]
    url = cfg["url"]
    # We support both the new "publishable_key" name and the legacy
    # "anon_key" name so existing deployments don't break.
    key = cfg.get("publishable_key") or cfg.get("anon_key")
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are missing. Add them to "
            ".streamlit/secrets.toml under [supabase]."
        )
    return create_client(url, key)


def _session_is_expired(session: dict, *, skew_seconds: int = 60) -> bool:
    """
    Return True if the cached session's access token is at/past its
    expiry (with a small skew so we refresh BEFORE Postgrest yells).
    A session without an expires_at falls through as "unknown" -> False
    so we don't refresh unnecessarily.
    """
    if not session:
        return False
    expires_at = session.get("expires_at")
    if expires_at is None:
        return False
    try:
        return time.time() >= (float(expires_at) - skew_seconds)
    except Exception:
        return False


def _refresh_stored_session(client) -> bool:
    """
    Try to mint a fresh access token from the stored refresh token.
    On success, overwrite st.session_state["supabase_session"] with the
    new tokens/expiry and return True. On failure, clear the session
    locally and return False (the next interaction will route the user
    back through the auth gate).
    """
    session = st.session_state.get("supabase_session")
    refresh_token = session.get("refresh_token") if session else None
    if not refresh_token:
        return False

    new_session = None
    # supabase-py's API has shifted across versions. Try the most
    # common signatures in order.
    for attempt in (
        lambda: client.auth.refresh_session(refresh_token),
        lambda: client.auth.refresh_session(refresh_token=refresh_token),
        lambda: client.auth.refresh_session(),
    ):
        try:
            resp = attempt()
            cand = getattr(resp, "session", None) or resp
            if cand and getattr(cand, "access_token", None):
                new_session = cand
                break
        except TypeError:
            continue
        except Exception:
            continue

    if not new_session:
        st.session_state.pop("supabase_session", None)
        st.session_state.pop("auth_user", None)
        return False

    user_obj = getattr(new_session, "user", None)
    st.session_state["supabase_session"] = {
        "access_token":  getattr(new_session, "access_token", None),
        "refresh_token": getattr(new_session, "refresh_token", refresh_token),
        "expires_at":    getattr(new_session, "expires_at", None),
        "user_id":       getattr(user_obj, "id", None) if user_obj else session.get("user_id"),
        "email":         getattr(user_obj, "email", None) if user_obj else session.get("email"),
    }
    # Invalidate the cached auth_user so the next get_current_user()
    # call picks up the refreshed identity.
    st.session_state.pop("auth_user", None)
    return True


def get_client() -> "Client":
    """
    Return the cached client with the current user's session re-applied.

    Streamlit reruns the script on every interaction, so the cached
    client may forget the user's auth tokens between runs. We persist
    the session in st.session_state and reattach it here. If the cached
    access token has already expired (Supabase's default TTL is 1 hour),
    we proactively swap it for a fresh one using the refresh token so
    PostgREST never sees a `JWT expired` error in the first place.
    """
    client = _build_client()

    session = st.session_state.get("supabase_session")
    if not session or not session.get("access_token") or not session.get("refresh_token"):
        return client

    # If the access token is already expired (or about to be), refresh
    # BEFORE planting it on the client.
    if _session_is_expired(session):
        if not _refresh_stored_session(client):
            # Refresh failed — the user is effectively logged out. The
            # next call to get_current_user() will return None and the
            # app will route to the auth gate.
            return client
        session = st.session_state.get("supabase_session") or {}

    try:
        client.auth.set_session(
            session["access_token"],
            session["refresh_token"],
        )
    except Exception:
        # set_session can throw if the access token is malformed or the
        # refresh token has been revoked. Try one refresh and one retry
        # before giving up.
        if _refresh_stored_session(client):
            session = st.session_state.get("supabase_session") or {}
            try:
                client.auth.set_session(
                    session["access_token"],
                    session["refresh_token"],
                )
            except Exception:
                st.session_state.pop("supabase_session", None)
                st.session_state.pop("auth_user", None)
        else:
            st.session_state.pop("supabase_session", None)
            st.session_state.pop("auth_user", None)
    return client


# --------------------------------------------------------------------
#  Session helpers
# --------------------------------------------------------------------
def store_session(session_obj):
    """Persist a Supabase Session (returned from sign_in / sign_up)
    into st.session_state so subsequent reruns stay logged in."""
    if not session_obj:
        return
    st.session_state["supabase_session"] = {
        "access_token":  session_obj.access_token,
        "refresh_token": session_obj.refresh_token,
        "expires_at":    getattr(session_obj, "expires_at", None),
        "user_id":       getattr(session_obj.user, "id", None) if getattr(session_obj, "user", None) else None,
        "email":         getattr(session_obj.user, "email", None) if getattr(session_obj, "user", None) else None,
    }


def clear_session():
    """Sign the user out — drop their tokens locally."""
    st.session_state.pop("supabase_session", None)
    st.session_state.pop("player", None)
    st.session_state.pop("auth_user", None)
    try:
        _build_client().auth.sign_out()
    except Exception:
        pass


def _is_auth_error(exc: Exception) -> bool:
    """Best-effort: is this exception an actual auth failure (vs. a
    transient network / 5xx hiccup)?

    Auth failures → clear the session and bounce to login.
    Transient errors → leave session intact, return the cached user
    if we have one, so a flaky network during a long upload doesn't
    kick a logged-in user to login with no warning.
    """
    msg = str(exc).lower()
    return (
        "jwt" in msg
        or "invalid_grant" in msg
        or "invalid token" in msg
        or "invalid refresh" in msg
        or "refresh token" in msg
        or "unauthor" in msg            # "unauthorized"
        or "user not found" in msg
        or "user_not_found" in msg
        or "session_not_found" in msg
        or "auth session missing" in msg
    )


def get_current_user():
    """
    Return the currently authenticated Supabase user object, or None.

    Pulls fresh user info from the API on first call per rerun, then
    caches it on st.session_state["auth_user"] for the rest of the run.

    Defensive: never clear the session on a transient error. A network
    blip during a 30-60s pose-detection upload was bouncing logged-in
    users straight back to login with no warning. Only clear when the
    error is unambiguously an auth failure.
    """
    if "auth_user" in st.session_state:
        cached = st.session_state["auth_user"]
        if cached:
            return cached
        # Cached value is None — fall through and try once more rather
        # than returning a stale "not logged in" answer.

    session = st.session_state.get("supabase_session")
    if not session:
        return None

    try:
        client = get_client()
        resp = client.auth.get_user()
        user = getattr(resp, "user", None)
        if user:
            # Only cache truthy users. Caching None creates a sticky
            # "logged out" state across reruns even if the very next
            # call would have succeeded.
            st.session_state["auth_user"] = user
        return user
    except Exception as exc:
        if _is_auth_error(exc):
            # Real auth failure — purge and bounce them back to login.
            clear_session()
            return None
        # Transient (network/5xx/etc): keep the session intact and
        # return whatever's cached. Worst case the user sees one stale
        # rerun, then the next call succeeds.
        return st.session_state.get("auth_user")


def is_logged_in() -> bool:
    return get_current_user() is not None
