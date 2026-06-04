"""Automated Seller Central login — credentials + Telegram OTP + cookie save.

Three OTP scenarios (see ``run_otp_phase``):
  1. Ideal — email → password → delivery picker (default) → 3×60s Telegram wait
  2. Busy — after 3 waits: Didn't receive → Call …711 → Send OTP → 3×60s again
  3. Shortcut — already on OTP picker → Call …711 → Send OTP → 3×60s wait

Always ticks "Don't ask for codes on this device" on the OTP entry screen.

Run: python -m mahika.cli seller-login
Optional test flag: --fresh (clears cookies/cache — not for normal runs)
Uses Playwright Chromium (not Cursor IDE browser — separate cookie jar).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

from mahika.config import settings
from mahika.playwright.amazon_signin_flow import (
    advance_signin_until_otp_or_home,
    is_otp_delivery_picker,
    is_otp_entry_screen,
    is_otp_rate_limited,
    submit_otp_delivery_picker,
    wait_amazon_otp_cooldown,
)
from mahika.playwright.selectors import SELECTORS, URLs
from mahika.playwright.session import (
    CHROMIUM_FRESH_PROFILE_DIR,
    LoginAborted,
    clear_all_seller_browser_state,
    load_cookies,
    save_cookies,
    session_is_authenticated,
)
from mahika.services.notifier import send_plain_message

log = logging.getLogger(__name__)

S = SELECTORS.login
SIGNIN_ENTRY = (
    "https://sellercentral.amazon.in/signin"
    "?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect"
)
DEFAULT_TIMEOUT_S = 600
OTP_TELEGRAM_ATTEMPTS = 3
OTP_TELEGRAM_WAIT_S = 60
OTP_CALL_PHONE_SUFFIX = os.getenv("AMAZON_OTP_PHONE_SUFFIX", "711").strip() or "711"
# Scenario 2 — Call …711: submit → 120s → resubmit → 300s Telegram poll (×2 rounds max)
CALL_711_POST_SUBMIT_WAIT_S = 120
CALL_711_AFTER_RESUBMIT_WAIT_S = 300
CALL_711_MAX_ROUNDS = 2
LOGIN_FAILURE_LOG = settings.storage_root / "logs" / "seller_login_failure.log"


@dataclass(frozen=True)
class SellerCredentials:
    email: str
    password: str


def load_seller_credentials() -> SellerCredentials:
    load_dotenv(".env", override=True)
    email = os.getenv("AMAZON_SELLER_EMAIL", "").strip()
    password = os.getenv("AMAZON_SELLER_PASSWORD", "").strip()
    if not email or not password:
        raise RuntimeError(
            "AMAZON_SELLER_EMAIL and AMAZON_SELLER_PASSWORD missing in agent/.env"
        )
    return SellerCredentials(email=email, password=password)


def _trust_device(page: Page) -> None:
    """Always tick 'Don't ask for codes on this device' when OTP box is shown."""
    for sel in (
        "#auth-mfa-remember-device",
        "input[name='rememberDevice']",
        "input[type='checkbox'][name*='remember']",
    ):
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            if not loc.is_checked():
                loc.check(force=True)
            log.info("seller_login: Don't ask for codes on this device — ticked")
            return
        except Exception:
            continue


def _click_first_visible(page: Page, selectors: tuple[str, ...], *, label: str) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            if loc.first.is_visible():
                loc.first.click(force=True, timeout=8_000)
                page.wait_for_timeout(2_000)
                log.info("seller_login: %s (%s)", label, sel)
                return True
        except Exception:
            continue
    return False


def _wait_for_otp_input(page: Page, *, timeout_s: float = 20.0) -> bool:
    try:
        page.wait_for_selector(S.otp_input, timeout=int(timeout_s * 1000))
        return page.locator(S.otp_input).count() > 0
    except Exception:
        return page.locator(S.otp_input).count() > 0


def _telegram_wait_round(
    watcher, *, round_label: str, reset_prompt: bool = False
) -> str | None:
    """3×60s Telegram poll; log + nudge every 60s."""
    from mahika.services.notifier import send_otp_nudge

    if reset_prompt:
        watcher._otp_prompt_sent = False
        watcher._used.clear()

    watcher.mark_otp_waiting(
        total_wait_s=OTP_TELEGRAM_ATTEMPTS * OTP_TELEGRAM_WAIT_S + 60
    )
    if not watcher._otp_prompt_sent:
        send_otp_nudge(
            f"Mahika [{round_label}]: OTP screen — sirf 6-digit bhejo "
            f"(@mahika_arun_bot). {OTP_TELEGRAM_ATTEMPTS}×{OTP_TELEGRAM_WAIT_S}s wait."
        )
        watcher._otp_prompt_sent = True

    for attempt in range(1, OTP_TELEGRAM_ATTEMPTS + 1):
        log.info(
            "seller_login: [%s] Telegram wait %d/%d (60s)",
            round_label,
            attempt,
            OTP_TELEGRAM_ATTEMPTS,
        )
        watcher._write_live_status(
            f"[{round_label}] attempt {attempt}/{OTP_TELEGRAM_ATTEMPTS} — waiting OTP"
        )
        send_otp_nudge(
            f"Mahika [{round_label}]: attempt {attempt}/{OTP_TELEGRAM_ATTEMPTS} — "
            f"sirf 6-digit OTP @mahika_arun_bot"
        )
        otp = watcher.wait_for_otp(
            timeout_s=float(OTP_TELEGRAM_WAIT_S),
            poll_s=2.0,
            log_every_s=60.0,
            telegram_nudge=True,
            telegram_nudge_interval_s=60.0,
        )
        if otp:
            return otp
    return None


def _wait_fixed_seconds(page: Page, seconds: float, *, label: str) -> None:
    """Terminal ping every 60s while waiting (Call 711 / Amazon voice delay)."""
    from mahika.services.otp_watcher import _terminal_ping

    log.info("seller_login: fixed wait %ss — %s", int(seconds), label)
    deadline = time.monotonic() + seconds
    next_ping = time.monotonic()
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_ping:
            left = max(0, int(deadline - now))
            _terminal_ping(f"{label} — {left}s left")
            next_ping = now + 60.0
        page.wait_for_timeout(2_000)


def _submit_call_711(page: Page) -> bool:
    """Trigger Call …711 + Send OTP (picker or didn't-receive path)."""
    if is_otp_delivery_picker(page):
        return submit_otp_delivery_picker(page, use_call=True)
    if _scenario2_busy_recovery(page):
        page.wait_for_timeout(2_000)
        if is_otp_delivery_picker(page):
            return submit_otp_delivery_picker(page, use_call=True)
    return False


def _run_call_711_sequence(page: Page, watcher) -> str | None:
    """
    Call 711 submitted → wait 120s → resubmit 711 → wait 300s (Telegram poll).
    Up to CALL_711_MAX_ROUNDS (2) rounds.
    """
    from mahika.services.notifier import send_otp_nudge

    for round_n in range(1, CALL_711_MAX_ROUNDS + 1):
        log.info(
            "seller_login: Call …%s round %d/%d — submit",
            OTP_CALL_PHONE_SUFFIX,
            round_n,
            CALL_711_MAX_ROUNDS,
        )
        send_otp_nudge(
            f"Mahika: Call …{OTP_CALL_PHONE_SUFFIX} round {round_n} — phone suno, "
            f"phir 6-digit @mahika_arun_bot"
        )
        if not _submit_call_711(page):
            log.warning("seller_login: Call 711 submit failed (round %d)", round_n)

        _wait_fixed_seconds(
            page, CALL_711_POST_SUBMIT_WAIT_S, label=f"call-711-r{round_n}-after-submit-120s"
        )

        log.info("seller_login: resubmit Call …%s (round %d)", OTP_CALL_PHONE_SUFFIX, round_n)
        _submit_call_711(page)

        _wait_fixed_seconds(
            page,
            CALL_711_AFTER_RESUBMIT_WAIT_S,
            label=f"call-711-r{round_n}-after-resubmit-300s",
        )

        if not _wait_for_otp_input(page, timeout_s=5.0):
            continue
        _trust_device(page)
        watcher.mark_otp_waiting(total_wait_s=CALL_711_AFTER_RESUBMIT_WAIT_S + 30)
        otp = watcher.wait_for_otp(
            timeout_s=float(CALL_711_AFTER_RESUBMIT_WAIT_S),
            poll_s=2.0,
            log_every_s=60.0,
            telegram_nudge=True,
            telegram_nudge_interval_s=60.0,
        )
        if otp:
            log.info("seller_login: OTP received during Call 711 round %d", round_n)
            return otp

    return None


def _fail_login_close(page: Page, reason: str) -> None:
    """Save screenshot + failure log, notify Telegram, stop login."""
    _save_debug_screenshot(page, "login_failed_final")
    try:
        LOGIN_FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
        from datetime import UTC, datetime

        line = (
            f"{datetime.now(UTC).isoformat()} | FAILED | {reason} | url={page.url}\n"
        )
        with LOGIN_FAILURE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line)
        log.error("seller_login: %s — log appended %s", reason, LOGIN_FAILURE_LOG)
    except Exception as exc:
        log.warning("seller_login: failure log write failed (%s)", exc)
    send_plain_message(f"Mahika: login band — {reason}")


def _scenario2_busy_recovery(page: Page) -> bool:
    """Didn't receive OTP → Call …711 → Send OTP."""
    from mahika.services.notifier import send_otp_nudge

    log.info("seller_login: SCENARIO 2 — Didn't receive → Call …%s → Send OTP", OTP_CALL_PHONE_SUFFIX)
    send_otp_nudge(
        f"Mahika: 5 min wait over — Call …{OTP_CALL_PHONE_SUFFIX} trigger ho raha hai."
    )

    if page.locator(S.otp_input).count() > 0:
        _click_first_visible(
            page,
            (
                S.otp_didnt_receive_link,
                "a:has-text('Didn't receive the OTP')",
                "a:has-text('Did not receive the OTP')",
                "a:has-text('Didn't receive')",
            ),
            label="didnt_receive_otp",
        )
        page.wait_for_timeout(2_500)

    if is_otp_delivery_picker(page):
        return submit_otp_delivery_picker(page, use_call=True)

    return _click_first_visible(
        page,
        (
            f"a:has-text('Call me at my number ending in {OTP_CALL_PHONE_SUFFIX}')",
            f"label:has-text('{OTP_CALL_PHONE_SUFFIX}')",
            S.otp_voice_call_link,
        ),
        label="call_711_direct",
    ) and _click_first_visible(
        page,
        (S.otp_delivery_send_button, "button:has-text('Send OTP')"),
        label="send_otp_after_call",
    )


def _submit_otp_code(page: Page, otp: str) -> bool:
    from mahika.playwright.account_switcher import (
        complete_account_switcher,
        is_account_switcher_page,
    )

    page.fill(S.otp_input, "")
    page.fill(S.otp_input, otp)
    page.locator(S.otp_submit_button).click()
    log.info("seller_login: OTP submitted")
    page.wait_for_timeout(4_000)

    if is_account_switcher_page(page):
        log.info("seller_login: post-OTP — account switcher (Badeja → India)")
        complete_account_switcher(page)
        page.wait_for_timeout(2_000)

    ok = session_is_authenticated(page)
    if ok:
        log.info("seller_login: login complete (home / authenticated)")
    else:
        log.warning(
            "seller_login: OTP submitted but not home yet — url=%s",
            page.url,
        )
    return ok


def run_otp_phase(page: Page, watcher, *, scenario: int) -> bool:
    """
    Complete OTP after delivery method chosen.

    scenario 1: ideal (already sent default Send OTP)
    scenario 2: N/A here — use after failed round 1
    scenario 3: shortcut (already sent Call …711)
    """
    if watcher is None:
        send_plain_message("Mahika: OTP chahiye — 6 digit @mahika_arun_bot par bhejo.")
        return False

    if is_otp_entry_screen(page):
        log.info("seller_login: S4 OTP entry — skip picker (R3, no re-Send OTP)")
    elif is_otp_rate_limited(page):
        log.warning("seller_login: Amazon rate limit — wait 60s before retry")
        wait_amazon_otp_cooldown(page, reason="run_otp_phase-rate-limit")
    elif not _wait_for_otp_input(page):
        if is_otp_delivery_picker(page):
            use_call = scenario == 3
            submit_otp_delivery_picker(page, use_call=use_call)
            _wait_for_otp_input(page, timeout_s=90.0)
        if not _wait_for_otp_input(page):
            _save_debug_screenshot(page, "otp_input_missing")
            return False

    _trust_device(page)

    otp = _telegram_wait_round(watcher, round_label=f"scenario-{scenario}")
    if otp and _submit_otp_code(page, otp):
        return True

    if scenario == 1:
        log.info("seller_login: SCENARIO 2 — Call …711 (120s → resubmit → 300s ×2)")
        otp = _run_call_711_sequence(page, watcher)
        if otp and _submit_otp_code(page, otp):
            return True
        _fail_login_close(
            page,
            f"Call …{OTP_CALL_PHONE_SUFFIX} ×{CALL_711_MAX_ROUNDS} failed (120s+300s waits)",
        )
        return False

    _save_debug_screenshot(page, "otp_failed")
    _fail_login_close(page, "OTP phase failed")
    return False


def _at_otp_phase_already(page: Page) -> bool:
    """Scenario 3: browser reopened straight to OTP picker / entry."""
    if is_otp_delivery_picker(page):
        return True
    if page.locator(S.otp_input).count() > 0:
        try:
            return page.locator(S.otp_input).first.is_visible()
        except Exception:
            return True
    return False


def ensure_seller_session(
    page: Page,
    creds: SellerCredentials,
    watcher,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    fresh: bool = False,
) -> bool:
    if fresh:
        log.info("seller_login: fresh sign-in URL")
        page.goto(SIGNIN_ENTRY, wait_until="domcontentloaded", timeout=60_000)
    else:
        page.goto(URLs.BASE, wait_until="domcontentloaded", timeout=60_000)
        if session_is_authenticated(page):
            return True
        from mahika.playwright.account_switcher import (
            complete_account_switcher,
            is_account_switcher_page,
        )

        if is_account_switcher_page(page):
            log.info("seller_login: shortcut — account switcher (cookies session)")
            complete_account_switcher(page)
            if session_is_authenticated(page):
                return True
        page.goto(SIGNIN_ENTRY, wait_until="domcontentloaded", timeout=60_000)

    deadline = time.monotonic() + timeout_s

    if _at_otp_phase_already(page):
        log.info("seller_login: SCENARIO 3 — already on OTP options (shortcut)")
        if is_otp_delivery_picker(page):
            submit_otp_delivery_picker(page, use_call=True)
        return run_otp_phase(page, watcher, scenario=3)

    while time.monotonic() < deadline:
        if session_is_authenticated(page):
            return True

        if _at_otp_phase_already(page):
            log.info("seller_login: SCENARIO 3 — OTP phase detected in loop")
            if is_otp_delivery_picker(page):
                submit_otp_delivery_picker(page, use_call=True)
            return run_otp_phase(page, watcher, scenario=3)

        state = advance_signin_until_otp_or_home(
            page, creds.email, password=creds.password, fresh=fresh
        )
        log.info("seller_login: signin state → %s", state)

        if state == "home":
            return True

        if state == "otp" or is_otp_entry_screen(page):
            log.info("seller_login: SCENARIO 1 — ideal (OTP entry or post-password)")
            if is_otp_delivery_picker(page) and not is_otp_entry_screen(page):
                submit_otp_delivery_picker(page, use_call=False)
            return run_otp_phase(page, watcher, scenario=1)

        if state == "stuck":
            if is_otp_rate_limited(page):
                wait_amazon_otp_cooldown(page, reason="stuck-rate-limit")
                if is_otp_entry_screen(page):
                    return run_otp_phase(page, watcher, scenario=1)
            if is_otp_delivery_picker(page) or "/ap/mfa/new-otp" in page.url:
                if is_otp_entry_screen(page):
                    return run_otp_phase(page, watcher, scenario=1)
                log.info(
                    "seller_login: stuck was MFA picker — SCENARIO 1 (default Send OTP)"
                )
                submit_otp_delivery_picker(page, use_call=False)
                return run_otp_phase(page, watcher, scenario=1)
            _save_debug_screenshot(page, "signin_stuck")
            page.wait_for_timeout(2_000)
            continue

        page.wait_for_timeout(1_500)

    _save_debug_screenshot(page, "signin_timeout")
    return False


def _save_debug_screenshot(page: Page, name: str) -> None:
    try:
        out = settings.storage_root / "logs" / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out))
        log.info("seller_login: screenshot %s", out)
    except Exception as exc:
        log.warning("seller_login: screenshot failed (%s)", exc)


def run_seller_login(
    *, headless: bool = False, timeout_s: int = DEFAULT_TIMEOUT_S, fresh: bool = False
) -> bool:
    if fresh:
        clear_all_seller_browser_state()

    creds = load_seller_credentials()
    watcher = None
    if settings.telegram_configured:
        from mahika.services.otp_watcher import TelegramOtpWatcher

        watcher = TelegramOtpWatcher()
    else:
        log.warning("seller_login: Telegram not configured")

    send_plain_message(
        "Mahika login (Playwright):\n"
        "S1 email→pass→OTP picker→3×60s wait\n"
        "S2 busy: Didn't receive→Call …711\n"
        "S3: direct OTP picker→Call …711\n"
        "Sirf 6-digit OTP bhejo."
    )

    signout = (
        "https://www.amazon.in/ap/signin?openid.pape.max_auth_age=0"
        "&openid.return_to=https://sellercentral.amazon.in/"
    )

    with sync_playwright() as pw:
        browser = None
        context = None
        try:
            if fresh:
                CHROMIUM_FRESH_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                context = pw.chromium.launch_persistent_context(
                    str(CHROMIUM_FRESH_PROFILE_DIR),
                    headless=headless,
                    locale="en-IN",
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(signout, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(1_500)
                log.info("seller_login: fresh Chromium profile cleared")
            else:
                if not headless:
                    log.info(
                        "seller_login: opening Playwright Chromium (separate window — NOT Cursor browser)"
                    )
                browser = pw.chromium.launch(
                    headless=headless,
                    args=[] if headless else ["--start-maximized"],
                )
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                load_cookies(context)
                page = context.new_page()

            if ensure_seller_session(
                page, creds, watcher, timeout_s=timeout_s, fresh=fresh
            ):
                save_cookies(context)
                send_plain_message(
                    "Mahika: Seller Central login OK — Badeja India + cookies saved."
                )
                return True
            raise LoginAborted(f"Login not completed within {timeout_s}s")
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
