"""Seller Central session management — cookies + 2FA OTP coordination.

The browser context is rehydrated from saved cookies on every filing run. If
the cookies have expired (Amazon's session typically lasts 7–14 days), the
filer must:

    1. Detect the redirect-to-login (URL changes to /ap/signin or login form
       elements appear on the expected page)
    2. Push a CRITICAL Telegram alert to Sir
    3. Open a HEADED browser window so Sir can log in + enter OTP manually
    4. Wait for Sir to confirm via Telegram (`Mahika, OTP done`) or by
       reaching Seller Central home
    5. Save the new cookies + resume the filing operation

The cookie file lives at:
    {storage_root}/sessions/seller_central_cookies.json

It's gitignored at the project root, never logged, never sent to Telegram.
The file is per-machine (each runner refreshes its own copy when it takes
over the active lease).

Note on safety: per Anthropic's safety rules, this module NEVER stores or
transmits Sir's Amazon credentials. Only session cookies are persisted. The
login itself happens in a headed browser where Sir types credentials
directly into Amazon's official login page.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mahika.config import settings
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import audit

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext

log = logging.getLogger(__name__)


COOKIE_DIR = settings.storage_root / "sessions"
COOKIE_FILE = COOKIE_DIR / "seller_central_cookies.json"
HOME_LANDING_TIMEOUT_MS = 180_000  # 3 min — Telegram OTP auto-fill needs headroom


class NoSessionAvailable(RuntimeError):
    """First-boot state: no saved cookies AND we're not in live mode, so we
    refuse to pop a headed browser. Sir's launch-time codegen flow saves the
    initial cookies; until then the filer skips with an audit event."""


# ─── Persistence ─────────────────────────────────────────────────────────


def save_cookies(context: BrowserContext) -> None:
    """Persist the browser context cookies to COOKIE_FILE."""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    cookies = context.cookies()
    COOKIE_FILE.write_text(json.dumps({
        "saved_at": datetime.now(UTC).isoformat(),
        "cookies": cookies,
    }, indent=2), encoding="utf-8")
    log.info("session: saved %d cookies to %s", len(cookies), COOKIE_FILE)
    from mahika.utils.audit import audit_safe

    audit_safe(
        "session.cookies_saved",
        actor="mahika.session",
        payload={"cookie_count": len(cookies), "path": str(COOKIE_FILE)},
    )


CHROMIUM_PROFILE_DIR = COOKIE_DIR / "chromium_profile"
CHROMIUM_FRESH_PROFILE_DIR = COOKIE_DIR / "_pw_fresh_profile"


def clear_seller_cookies() -> bool:
    """Remove saved Seller Central cookies so the next login is a clean sign-in."""
    removed = False
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
        removed = True
        log.info("session: deleted %s", COOKIE_FILE)
    for stale in COOKIE_DIR.glob("seller_central_cookies*.json"):
        if stale != COOKIE_FILE:
            stale.unlink(missing_ok=True)
            removed = True
    if not removed:
        log.info("session: no cookie file to clear")
    return removed


def clear_all_seller_browser_state() -> None:
    """Cookies file + Playwright Chromium profile/cache (full clean sign-in)."""
    import shutil

    clear_seller_cookies()
    for profile_dir in (CHROMIUM_PROFILE_DIR, CHROMIUM_FRESH_PROFILE_DIR):
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
            log.info("session: removed Chromium profile %s", profile_dir)


def load_cookies(context: BrowserContext) -> bool:
    """Load cookies from COOKIE_FILE into the browser context.

    Returns True if cookies were loaded, False if the file doesn't exist or
    is empty/corrupt.
    """
    if not COOKIE_FILE.exists():
        log.info("session: no cookie file at %s — first run", COOKIE_FILE)
        return False
    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("session: cookie file corrupt (%s); ignoring", exc)
        return False
    if isinstance(data, list):
        cookies = data
    else:
        cookies = data.get("cookies", [])
    if not cookies:
        return False
    context.add_cookies(cookies)
    log.info("session: loaded %d cookies from %s", len(cookies), COOKIE_FILE)
    return True


# ─── Active-session detection ────────────────────────────────────────────


def session_is_authenticated(page) -> bool:  # type: ignore[no-untyped-def]
    """True when Seller Central looks logged in (URL + nav heuristics)."""
    url = page.url or ""
    if "/ap/signin" in url or "/ap/mfa" in url or "/ap/cvf" in url:
        return False
    if "/account-switcher" in url:
        return False
    if "/home" in url or "/safet-claims" in url:
        return True
    for sel in ("#sc-nav-brand", "#sp-cc-wrapper", "kat-nav", "[data-test-id='nav-bar']"):
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return is_logged_in(page)


def is_logged_in(page) -> bool:  # type: ignore[no-untyped-def]
    """True iff the current page shows the Seller Central home indicator.

    We don't navigate inside this function — call it after a navigation that
    expects an authenticated landing page.
    """
    from mahika.playwright.selectors import SELECTORS

    try:
        # Short timeout — we just want to know if the indicator is there NOW
        page.wait_for_selector(SELECTORS.login.home_indicator, timeout=3_000)
        return True
    except Exception:
        return False


# ─── Manual login flow (OTP coordination) ────────────────────────────────


class LoginAborted(RuntimeError):
    """Sir did not complete the manual login within HOME_LANDING_TIMEOUT_MS."""


def request_manual_login(
    context: BrowserContext,
    *,
    reason: str = "session expired",
) -> bool:
    """Pop a headed browser, alert Sir, and wait until login succeeds.

    Returns True on success (cookies were saved). Raises LoginAborted on
    timeout. The browser window stays open until login succeeds — Sir closes
    it manually after.

    This function is a no-op when cookies are already valid; callers should
    check `is_logged_in()` first and only call this when re-auth is needed.
    """
    audit(
        "session.manual_login_requested",
        actor="mahika.session",
        reason=reason,
    )

    alert(
        Priority.CRITICAL,
        title="Mahika needs Sir's Seller Central OTP",
        body=(
            f"Reason: {reason}\n"
            "\n"
            "A headed browser window has opened on the active runner. "
            "Log in to Seller Central there. Mahika will detect the home "
            "page automatically and save new cookies — no Telegram reply needed.\n"
            "\n"
            "If the window didn't open, check the active runner's display."
        ),
        key="session_otp_request",
    )

    from mahika.playwright.selectors import SELECTORS, URLs

    page = context.new_page()
    otp_watcher = None
    if settings.telegram_configured:
        try:
            from mahika.services.otp_watcher import TelegramOtpWatcher

            otp_watcher = TelegramOtpWatcher()
        except Exception as exc:
            log.warning("session: OTP watcher unavailable (%s)", exc)

    try:
        page.goto(URLs.LOGIN)
        deadline = time.monotonic() + HOME_LANDING_TIMEOUT_MS / 1000.0
        while time.monotonic() < deadline:
            if session_is_authenticated(page):
                save_cookies(context)
                audit(
                    "session.manual_login_completed",
                    actor="mahika.session",
                    reason="authenticated landing detected",
                )
                alert(
                    Priority.INFO,
                    title="Login successful — Mahika resuming",
                    body="Cookies saved. Filer will retry the queued claim now.",
                    key="session_otp_done",
                )
                return True

            if otp_watcher and page.locator(SELECTORS.login.otp_input).count() > 0:
                from mahika.playwright.seller_login import _trust_device

                _trust_device(page)
                otp_watcher.mark_otp_waiting(total_wait_s=600.0)
                otp = otp_watcher.wait_for_otp(
                    timeout_s=60.0,
                    log_every_s=60.0,
                    telegram_nudge=True,
                    telegram_nudge_interval_s=60.0,
                )
                if otp:
                    page.fill(SELECTORS.login.otp_input, otp)
                    page.locator(SELECTORS.login.otp_submit_button).click()
                    page.wait_for_timeout(3_000)
                    continue

            page.wait_for_timeout(2_000)
        raise LoginAborted(
            f"Sir did not complete login within "
            f"{HOME_LANDING_TIMEOUT_MS/1000:.0f} seconds"
        )
    finally:
        page.close()


# ─── Public context helper ───────────────────────────────────────────────


def get_authenticated_context(
    playwright,  # type: ignore[no-untyped-def]
    *,
    headless: bool = True,
) -> BrowserContext:
    """Return a Playwright context that's logged into Seller Central.

    Workflow:
        1. Launch a chromium browser (headless for production, headed for dev)
        2. Create a context + load saved cookies if available
        3. Navigate to Seller Central home; if not logged in:
             - LIVE mode: switch to headed browser + invoke request_manual_login()
             - Other modes (shadow/manual/paused) + no cookies: raise
               NoSessionAvailable so the filer skips cleanly. Stops smoke
               tests + first-boot from blocking on an interactive login.
        4. Return the authenticated context

    The caller owns the context lifecycle and must close it when done.
    """
    from mahika.playwright.selectors import URLs

    have_cookies = COOKIE_FILE.exists()
    if not have_cookies and settings.mode != "live":
        raise NoSessionAvailable(
            "No Seller Central cookies on disk and mode is not 'live'. "
            "Sir must run `scripts\\codegen_helper.bat` once + save cookies "
            "before the filer can drive shadow/manual mode."
        )

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    load_cookies(context)

    # Quick sanity check — navigate to home and see if we're logged in.
    probe = context.new_page()
    try:
        probe.goto(URLs.BASE, wait_until="domcontentloaded", timeout=30_000)
        ok = session_is_authenticated(probe)
    except Exception as exc:
        log.warning("session: home probe failed (%s); assuming logged out", exc)
        ok = False
    finally:
        probe.close()

    if ok:
        return context

    # Re-auth needed.
    context.close()
    browser.close()

    if settings.mode != "live":
        # Don't pop a headed browser outside live mode — propagate so the
        # filer logs a skip event and the scheduler tick completes cleanly.
        raise NoSessionAvailable(
            f"Cookies invalid and mode is {settings.mode!r}; refusing to open "
            "headed browser. Re-run codegen or flip MAHIKA_MODE=live to "
            "trigger interactive re-auth."
        )

    log.info("session: cookies invalid; switching to headed browser for manual login")
    headed_browser = playwright.chromium.launch(headless=False)
    headed_context = headed_browser.new_context()
    request_manual_login(headed_context, reason="cookies invalid or expired")
    return headed_context
