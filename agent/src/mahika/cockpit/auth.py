"""Cockpit auth — single-user token + signed session cookie.

Strictly local. The token comes from `MAHIKA_COCKPIT_TOKEN` (.env). On a
correct paste, we set a signed cookie `mahika_session=ok` with HMAC integrity
via `itsdangerous`. Subsequent requests check the cookie signature.

Sessions don't expire on the server side (no DB-backed sessions), but the
cookie's HMAC depends on `cockpit_session_secret` so rotating that secret
invalidates all outstanding sessions.

Per the safety rules, this auth is for keeping casual eyes off Sir's
dashboard, not a hardened access-control system. The cockpit binds 127.0.0.1
by default — never expose this publicly without rebuilding the auth layer.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer

from mahika.config import settings

log = logging.getLogger(__name__)

SESSION_COOKIE = "mahika_session"
SESSION_VALUE = "ok"  # the only valid payload — the cookie's job is just attestation


def _ensure_secret() -> str:
    """Return the session-secret, generating one in-process if Sir didn't set one.

    The generated secret is NOT persisted — restarting the cockpit rotates it
    and forces re-login. That's fine for a single-user local dashboard.
    """
    secret = settings.cockpit_session_secret
    if not secret:
        secret = secrets.token_urlsafe(32)
        # Stash on the settings object so subsequent calls return the same one
        # within the lifetime of this process.
        object.__setattr__(settings, "cockpit_session_secret", secret)
        log.info("cockpit: generated ephemeral session secret (set MAHIKA_COCKPIT_SESSION_SECRET to persist)")
    return secret


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(_ensure_secret(), salt="mahika-cockpit")


def issue_session_cookie() -> str:
    """Return the value to set on Set-Cookie."""
    return _serializer().dumps(SESSION_VALUE)


def verify_session_cookie(cookie_value: str | None) -> bool:
    if not cookie_value:
        return False
    try:
        decoded = _serializer().loads(cookie_value)
    except BadSignature:
        return False
    return decoded == SESSION_VALUE


def check_token(submitted: str) -> bool:
    """Constant-time comparison against `settings.cockpit_token`."""
    expected = settings.cockpit_token or ""
    if not expected:
        # Refuse to authenticate when no token is configured — Sir must set
        # MAHIKA_COCKPIT_TOKEN before the cockpit is usable. This prevents an
        # empty-token bypass.
        return False
    return secrets.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


def require_session(request: Request) -> None:
    """FastAPI dependency — raises 302→/login when session cookie is invalid."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if not verify_session_cookie(cookie):
        # Redirect to login. FastAPI converts HTTPException(303) with `Location`
        # header into a proper browser redirect.
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
