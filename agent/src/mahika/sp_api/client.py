"""SP-API client factory + LWA auth wrapper.

Wraps the `python-amazon-sp-api` library with our credential layout.
Phase 4 modules (refund watcher, return scanner) import factory funcs
from here — never instantiate the underlying client directly.

Credentials live in .env (see config.Settings). Mahika supports multiple
seller accounts by checking which one has valid creds at runtime — for
now we only have Sir's friend's account; Sir's reactivated account is
future scope.

NOTE: SP-API India operates from the EU region (eu-west-1) per Amazon's
SP-API regional routing for IN/UK/DE marketplaces. The marketplace ID
for amazon.in is A21TJRUUN4KGV.

Sandbox vs production:
    Sandbox refresh tokens only work against sandbox endpoints. Set
    MAHIKA_SP_API_SANDBOX=true (default) until production is approved.
    The library switches endpoints via AWS_ENV=SANDBOX (set in config.py
    before sp_api is imported).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mahika.config import settings

# Amazon static sandbox fixture for Orders API v0 (US marketplace).
_SANDBOX_ORDERS_CREATED_AFTER = "TEST_CASE_200"
_SANDBOX_ORDERS_MARKETPLACE_ID = "ATVPDKIKX0DER"


class SPAPINotConfiguredError(RuntimeError):
    """Raised when SP-API credentials are missing — Sir hasn't completed
    `scripts/sp_api_registration_checklist.md` yet."""


@dataclass(frozen=True)
class SPAPIStatus:
    """Result of a connectivity probe — surfaced in doctor + status CLI."""

    configured: bool
    sandbox_mode: bool
    lwa_ok: bool
    api_reachable: bool
    detail: str


def _credentials() -> dict[str, str]:
    """Build the credentials dict the sp_api library expects."""
    if not settings.sp_api_configured:
        raise SPAPINotConfiguredError(
            "SP-API credentials missing in .env. See "
            "scripts/sp_api_registration_checklist.md for setup."
        )
    creds: dict[str, str] = {
        "refresh_token": settings.sp_api_refresh_token,
        "lwa_app_id": settings.sp_api_lwa_client_id,
        "lwa_client_secret": settings.sp_api_lwa_client_secret,
    }
    if settings.sp_api_role_arn:
        creds["role_arn"] = settings.sp_api_role_arn
    return creds


def _marketplace() -> Any:
    """Resolve Marketplaces enum — IN for production, US for sandbox static tests."""
    from sp_api.base import Marketplaces  # type: ignore[import-not-found]

    if settings.sp_api_sandbox:
        return Marketplaces.US
    return Marketplaces.IN


def get_orders_client() -> Any:
    """Return an Orders SP-API client."""
    from sp_api.api import Orders  # type: ignore[import-not-found]

    return Orders(credentials=_credentials(), marketplace=_marketplace())


def get_reports_client() -> Any:
    """Return a Reports SP-API client."""
    from sp_api.api import Reports  # type: ignore[import-not-found]

    return Reports(credentials=_credentials(), marketplace=_marketplace())


def get_finances_client() -> Any:
    """Return a Finances SP-API client."""
    from sp_api.api import Finances  # type: ignore[import-not-found]

    return Finances(credentials=_credentials(), marketplace=_marketplace())


def ping() -> bool:
    """Smoke test — does our SP-API token work on the configured endpoint?"""
    return check_status().api_reachable


def check_status() -> SPAPIStatus:
    """Probe LWA + SP-API for doctor/status — does not raise."""
    if not settings.sp_api_configured:
        return SPAPIStatus(
            configured=False,
            sandbox_mode=settings.sp_api_sandbox,
            lwa_ok=False,
            api_reachable=False,
            detail="credentials missing in .env",
        )

    lwa_ok = _lwa_token_ok()
    if not lwa_ok:
        return SPAPIStatus(
            configured=True,
            sandbox_mode=settings.sp_api_sandbox,
            lwa_ok=False,
            api_reachable=False,
            detail="LWA token exchange failed",
        )

    if settings.sp_api_sandbox:
        api_ok, detail = _sandbox_orders_ok()
    else:
        api_ok, detail = _production_orders_ok()

    return SPAPIStatus(
        configured=True,
        sandbox_mode=settings.sp_api_sandbox,
        lwa_ok=True,
        api_reachable=api_ok,
        detail=detail,
    )


def _lwa_token_ok() -> bool:
    try:
        import httpx

        r = httpx.post(
            "https://api.amazon.com/auth/o2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": settings.sp_api_refresh_token,
                "client_id": settings.sp_api_lwa_client_id,
                "client_secret": settings.sp_api_lwa_client_secret,
            },
            timeout=20,
        )
        return r.status_code == 200 and bool(r.json().get("access_token"))
    except Exception:
        return False


def _sandbox_orders_ok() -> tuple[bool, str]:
    try:
        client = get_orders_client()
        resp = client.get_orders(
            CreatedAfter=_SANDBOX_ORDERS_CREATED_AFTER,
            MarketplaceIds=[_SANDBOX_ORDERS_MARKETPLACE_ID],
        )
        orders = (getattr(resp, "payload", None) or {}).get("Orders") or []
        return True, f"sandbox OK — {len(orders)} mock order(s)"
    except Exception as exc:
        return False, f"sandbox orders failed: {type(exc).__name__}: {exc}"


def _production_orders_ok() -> tuple[bool, str]:
    try:
        from datetime import UTC, datetime, timedelta

        client = get_orders_client()
        end = datetime.now(UTC)
        start = end - timedelta(days=7)
        resp = client.get_orders(
            CreatedAfter=start.isoformat(),
            CreatedBefore=end.isoformat(),
            MarketplaceIds=[settings.sp_api_marketplace_id],
        )
        payload = getattr(resp, "payload", None)
        if payload is None:
            return False, "production orders: empty payload"
        count = len(payload.get("Orders") or [])
        return True, f"production OK — {count} order(s) in last 7d"
    except Exception as exc:
        return False, f"production orders failed: {type(exc).__name__}: {exc}"
