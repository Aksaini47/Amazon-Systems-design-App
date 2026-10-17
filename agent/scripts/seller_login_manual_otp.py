"""Seller Central login — MANUAL OTP flow (no Telegram relay).

Reuses the proven `advance_signin_until_otp_or_home()` state machine (same
one `mahika.cli seller-login` uses) so the account-picker / "Switch
accounts" screen, email, and password steps are all handled exactly like
the tested flow. The ONLY thing this script does differently: once the OTP
entry screen appears, it does NOT relay via Telegram — it just waits,
polling the DOM, for Sir to type the 6-digit code himself in the visible
window and submit it, then finishes the Badeja > India account switcher
and saves cookies.

Run in BACKGROUND (Bash run_in_background=true) — it blocks for up to
MANUAL_OTP_WAIT_S waiting on manual input, and must never block the
assistant's turn.
"""
from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from mahika.playwright.account_switcher import (
    complete_account_switcher,
    is_account_switcher_page,
)
from mahika.playwright.amazon_signin_flow import (
    advance_signin_until_otp_or_home,
    is_otp_delivery_picker,
    is_otp_entry_screen,
    submit_otp_delivery_picker,
)
from mahika.playwright.selectors import URLs
from mahika.playwright.session import load_cookies, save_cookies, session_is_authenticated

SIGNIN_URL = (
    "https://sellercentral.amazon.in/signin"
    "?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect"
)
MANUAL_OTP_WAIT_S = 600  # 10 min for Sir to type the OTP himself
POLL_S = 2


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def creds() -> tuple[str, str]:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
    email = os.getenv("AMAZON_SELLER_EMAIL", "").strip()
    password = os.getenv("AMAZON_SELLER_PASSWORD", "").strip()
    if not email or not password:
        raise SystemExit("AMAZON_SELLER_EMAIL / AMAZON_SELLER_PASSWORD missing in agent/.env")
    return email, password


def dismiss_switch_accounts_screen(page, email: str) -> bool:
    """The 'Switch accounts' picker (heading + account row + 'Add account')
    isn't recognized by amazon_signin_flow's `_already_logged_in_screen`
    detector for this UI variant — click the account row directly so the
    state machine doesn't stall here."""
    if not page.get_by_text("Switch accounts", exact=True).count():
        return False
    row = page.get_by_text(email, exact=False)
    if row.count():
        row.first.click(timeout=5000, force=True)
        page.wait_for_timeout(1500)
        log("clicked account row on 'Switch accounts' screen")
        return True
    # fallback: click by visible name text near the email if email text itself isn't clickable
    name_link = page.locator("a", has_text="@").first
    if name_link.count():
        name_link.click(timeout=5000, force=True)
        page.wait_for_timeout(1500)
        log("clicked account link (fallback) on 'Switch accounts' screen")
        return True
    return False


def tick_trust_device(page) -> None:
    for sel in ("#auth-mfa-remember-device", 'input[name="rememberDevice"]'):
        loc = page.locator(sel)
        if loc.count():
            try:
                if not loc.first.is_checked():
                    loc.first.check(force=True)
                log("trust-device ticked")
                return
            except Exception:
                continue


def main() -> int:
    email, password = creds()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        load_cookies(context)
        page = context.new_page()
        page.goto(SIGNIN_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_000)

        if session_is_authenticated(page):
            log("already authenticated — saving cookies")
            save_cookies(context)
            context.close()
            browser.close()
            return 0

        # this Amazon UI variant's picker isn't recognized by the shared
        # state machine — clear it explicitly before handing off
        for _ in range(3):
            if not dismiss_switch_accounts_screen(page, email):
                break
            page.wait_for_timeout(1000)

        log("advancing sign-in (handles email / password / most pickers automatically)")
        state = advance_signin_until_otp_or_home(page, email, password=password, fresh=False)
        log(f"signin state -> {state}")

        if state == "stuck":
            if dismiss_switch_accounts_screen(page, email):
                log("re-hit Switch-accounts mid-flow — retrying state machine")
                state = advance_signin_until_otp_or_home(page, email, password=password, fresh=False)
                log(f"signin state (retry) -> {state}")
            # one more nudge: if it's really the OTP delivery picker, submit default
            if is_otp_delivery_picker(page) and not is_otp_entry_screen(page):
                log("stuck on delivery picker -> submitting default Send OTP")
                submit_otp_delivery_picker(page, use_call=False)
                page.wait_for_timeout(1_500)
                state = "otp" if is_otp_entry_screen(page) else "stuck"

        if state == "home":
            log("already home after signin")
        elif state == "otp" or is_otp_entry_screen(page):
            tick_trust_device(page)
            log(f"OTP screen up — AAP KHUD OTP DALO ({MANUAL_OTP_WAIT_S}s wait budget)")
        elif state != "home":
            log(f"unexpected state '{state}' — will still wait/poll for manual completion")

        # Poll for manual completion regardless of exact state above —
        # Sir may be mid-interaction on the real window.
        deadline = time.time() + MANUAL_OTP_WAIT_S
        done = False
        last_note = 0.0
        while time.time() < deadline:
            try:
                if is_account_switcher_page(page):
                    log("account switcher detected — selecting Badeja > India")
                    complete_account_switcher(page)
                    page.wait_for_timeout(2_000)
                if session_is_authenticated(page):
                    done = True
                    break
            except Exception:
                pass
            if time.time() - last_note > 30:
                log(f"waiting for manual completion… ({int(deadline - time.time())}s left, url={page.url[:80]})")
                last_note = time.time()
            page.wait_for_timeout(POLL_S * 1000)

        if not done:
            log("TIMEOUT — login not completed in time")
            page.screenshot(path=str(Path(__file__).resolve().parents[1] / "manual_login_timeout.png"))
            context.close()
            browser.close()
            return 1

        save_cookies(context)
        log("LOGIN COMPLETE — cookies saved")
        page.wait_for_timeout(1_500)
        context.close()
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
