"""
Authentication facade.

Wraps Supabase sign_up / sign_in / sign_out so the rest of the app
never has to know which backend it's talking to. Returns the same
shape of profile dict the old file-based player_storage used, so
the UI code only needs a one-line swap.

Public API
----------
    sign_up(name, email, password, handedness, height_in=None, weight_lb=None)
        -> profile dict (after creating the auth user + players row)
    sign_in(email, password)
        -> profile dict (after fetching the players row for that user)
    sign_out()
        -> None
    current_profile()
        -> profile dict or None
"""

from datetime import datetime
from typing import Optional

import streamlit as st

from supabase_client import (
    get_client,
    store_session,
    clear_session,
    get_current_user,
)


# --------------------------------------------------------------------
#  Internal helpers
# --------------------------------------------------------------------
def _fetch_player_row(user_id: str) -> Optional[dict]:
    """Pull the players row for the given auth user. None if missing."""
    sb = get_client()
    try:
        resp = (
            sb.table("players")
              .select("*")
              .eq("user_id", user_id)
              .limit(1)
              .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as exc:
        st.error(f"Failed to load profile: {exc}")
        return None


def _profile_from_row(row: dict) -> dict:
    """
    Translate a Supabase players row into the legacy 'profile' dict
    shape the rest of the app already expects. The UI was built
    against this shape; keep it stable so we don't have to touch
    every read site.
    """
    if not row:
        return {}
    return {
        # Identity
        "id":          row.get("id"),           # players.id (uuid)
        "user_id":     row.get("user_id"),      # auth.users.id (uuid)
        "slug":        row.get("id"),           # back-compat alias used by the UI
        "name":        row.get("name"),
        "email":       row.get("email"),
        "handedness":  row.get("handedness"),

        # Body / metadata
        "height_in":   row.get("height_in"),
        "weight_lb":   row.get("weight_lb"),
        "team":        row.get("team"),
        "position":    row.get("position"),
        "throws":      row.get("throws"),
        "level":       row.get("level"),
        "primary_goal":row.get("primary_goal"),
        "profile_pic_path": row.get("profile_pic_path"),

        # MLB comp lock — slug of the reference this player is locked to,
        # set on first auto-picked swing so subsequent swings keep
        # comparing to the same MLB hitter instead of bouncing between
        # players (Trout one week, Judge the next).
        "locked_mlb_slug": row.get("locked_mlb_slug"),

        # Bookkeeping
        "created_at":  row.get("created_at"),
    }


# --------------------------------------------------------------------
#  Signup
# --------------------------------------------------------------------
def sign_up(
    name: str,
    email: str,
    password: str,
    handedness: str,
    height_in=None,
    weight_lb=None,
) -> dict:
    """
    Create a Supabase auth user and the matching players row.
    Raises ValueError on validation / duplicate-email errors so the
    UI can surface a clean st.error message.
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not name:
        raise ValueError("Please enter your name.")
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if handedness not in {"RIGHT", "LEFT"}:
        raise ValueError("Please choose right- or left-handed.")

    sb = get_client()

    # 1. Create the auth user.
    try:
        auth_resp = sb.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        msg = str(exc)
        if "already registered" in msg.lower() or "already exists" in msg.lower():
            raise ValueError("An account with this email already exists.") from exc
        raise ValueError(f"Signup failed: {msg}") from exc

    user = getattr(auth_resp, "user", None)
    session = getattr(auth_resp, "session", None)
    if not user:
        raise ValueError("Signup did not return a user. Try again in a minute.")

    # 2. Persist the session so the next DB call is authenticated.
    if session:
        store_session(session)

    # 3. Insert the players row. Re-fetch the client so the auth header
    #    picks up the new session above.
    sb = get_client()
    try:
        insert_resp = (
            sb.table("players")
              .insert({
                  "user_id":    user.id,
                  "name":       name,
                  "email":      email,
                  "handedness": handedness,
                  "height_in":  int(height_in) if height_in else None,
                  "weight_lb":  int(weight_lb) if weight_lb else None,
              })
              .execute()
        )
    except Exception as exc:
        raise ValueError(
            "Auth account created but profile row failed: "
            f"{exc}. You can try logging in — the profile may be created on next sign-in."
        ) from exc

    rows = insert_resp.data or []
    if not rows:
        raise ValueError("Profile row was not returned after insert.")

    profile = _profile_from_row(rows[0])
    st.session_state["player"] = profile
    return profile


# --------------------------------------------------------------------
#  Login
# --------------------------------------------------------------------
def sign_in(email: str, password: str) -> dict:
    """
    Log in with email + password. Returns the legacy-shaped profile dict.
    Raises ValueError on bad credentials.
    """
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        raise ValueError("Please enter your email and password.")

    sb = get_client()

    try:
        auth_resp = sb.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        msg = str(exc).lower()
        if "invalid" in msg or "credentials" in msg:
            raise ValueError("Incorrect email or password.") from exc
        raise ValueError(f"Login failed: {exc}") from exc

    user = getattr(auth_resp, "user", None)
    session = getattr(auth_resp, "session", None)
    if not user or not session:
        raise ValueError("Login did not return a session. Try again.")

    store_session(session)

    row = _fetch_player_row(user.id)
    if not row:
        # The auth account exists but no players row — auto-recover by
        # creating a minimal one. Name = local-part of email so they at
        # least see a sensible default until they fill in their profile.
        sb = get_client()
        fallback_name = email.split("@", 1)[0].replace(".", " ").title() or "Player"
        insert_resp = (
            sb.table("players")
              .insert({
                  "user_id":    user.id,
                  "name":       fallback_name,
                  "email":      email,
                  "handedness": "RIGHT",
              })
              .execute()
        )
        rows = insert_resp.data or []
        row = rows[0] if rows else None

    profile = _profile_from_row(row)
    st.session_state["player"] = profile
    return profile


# --------------------------------------------------------------------
#  Logout
# --------------------------------------------------------------------
def sign_out():
    clear_session()


# --------------------------------------------------------------------
#  Read current profile
# --------------------------------------------------------------------
def current_profile() -> Optional[dict]:
    """
    Return the cached profile dict if we have one, otherwise fetch
    it from the database. None if no user is logged in.
    """
    cached = st.session_state.get("player")
    if cached:
        return cached

    user = get_current_user()
    if not user:
        return None

    row = _fetch_player_row(user.id)
    if not row:
        return None

    profile = _profile_from_row(row)
    st.session_state["player"] = profile
    return profile


# --------------------------------------------------------------------
#  Update profile
# --------------------------------------------------------------------
ALLOWED_PROFILE_UPDATES = {
    "name", "handedness", "height_in", "weight_lb",
    "team", "position", "throws", "level", "primary_goal",
    "profile_pic_path",
    "locked_mlb_slug",
}


# --------------------------------------------------------------------
#  Password reset flow
# --------------------------------------------------------------------
def request_password_reset(email: str, redirect_to: Optional[str] = None) -> None:
    """
    Ask Supabase to send a password-reset email. The email contains
    a magic link that brings the user back to `redirect_to` with a
    recovery token in the URL.

    We always answer with a generic success message in the UI — even
    if the email doesn't exist — so attackers can't use this endpoint
    to enumerate registered emails. Errors that aren't "user not found"
    are surfaced.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")

    sb = get_client()
    try:
        kwargs = {}
        if redirect_to:
            kwargs["options"] = {"redirect_to": redirect_to}
        sb.auth.reset_password_for_email(email, **kwargs)
    except Exception as exc:
        msg = str(exc).lower()
        # Silently swallow "user not found" — see docstring.
        if "user not found" in msg or "not registered" in msg:
            return
        raise ValueError(f"Could not send reset email: {exc}") from exc


def update_password(new_password: str) -> None:
    """
    Set a new password for the CURRENTLY logged-in user. This is what
    the post-recovery-link screen calls after the user has been
    re-authenticated by the recovery token in the URL.
    """
    new_password = new_password or ""
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    sb = get_client()
    try:
        sb.auth.update_user({"password": new_password})
    except Exception as exc:
        raise ValueError(f"Could not update password: {exc}") from exc


def consume_recovery_url(access_token: str, refresh_token: str) -> bool:
    """
    Called when the app loads with a recovery token in the URL hash.
    Plants the tokens on the client so the next update_password() call
    is properly authenticated as the recovering user.
    """
    if not access_token or not refresh_token:
        return False
    try:
        sb = get_client()
        sb.auth.set_session(access_token, refresh_token)
        st.session_state["supabase_session"] = {
            "access_token":  access_token,
            "refresh_token": refresh_token,
        }
        return True
    except Exception:
        return False


def consume_recovery_token_hash(token_hash: str) -> bool:
    """
    Called when the app loads with `?token_hash=...&type=recovery` in
    the URL query string. This is the SSR-style recovery flow where the
    email link points directly at our app with a token_hash query
    param (cleaner than the implicit/hash-fragment flow because
    Streamlit can read query params natively, no JS shim needed).

    We call verify_otp to exchange the token_hash for a real session,
    then plant that session on the client.
    """
    if not token_hash:
        return False
    try:
        sb = get_client()
        # supabase-py accepts a dict for verify_otp; the dict shape
        # matches the JS SDK's VerifyTokenHashParams.
        resp = sb.auth.verify_otp({
            "token_hash": token_hash,
            "type":       "recovery",
        })
        sess = getattr(resp, "session", None)
        if not sess:
            return False
        at = getattr(sess, "access_token",  None)
        rt = getattr(sess, "refresh_token", None)
        if not at or not rt:
            return False
        sb.auth.set_session(at, rt)
        st.session_state["supabase_session"] = {
            "access_token":  at,
            "refresh_token": rt,
        }
        return True
    except Exception:
        return False


def update_profile(player_id: str, **fields) -> Optional[dict]:
    """
    Patch the current player's profile. Only fields in the whitelist
    are written.
    """
    safe = {k: v for k, v in fields.items() if k in ALLOWED_PROFILE_UPDATES}
    if not safe:
        return st.session_state.get("player")

    safe["updated_at"] = datetime.utcnow().isoformat()

    sb = get_client()
    resp = (
        sb.table("players")
          .update(safe)
          .eq("id", player_id)
          .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    profile = _profile_from_row(rows[0])
    st.session_state["player"] = profile
    return profile
