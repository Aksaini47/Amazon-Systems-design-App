"""Amazon Ads console login — MANUAL OTP flow (no Telegram relay).

Same pattern as seller_login_manual_otp.py but targets
advertising.amazon.in instead of sellercentral.amazon.in. Fills
email+password (reusing advance_signin_until_otp_or_home, which is
domain-agnostic Amazon sign-in handling), then WAITS for Sir to type the
OTP himself in the visible window, then saves Playwright storage_state to
ads_auth_state.json (the format stage2/3-style Ads workers expect).

Run in BACKGROUND (Bash run_in_background=true) - blocks up to 10 min on
manual input.
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

from mahika.playwright.amazon_signin_flow import (
    advance_signin_until_otp_or_home,
    is_otp_delivery_picker,
    is_otp_entry_screen,
    submit_otp_delivery_picker,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

ADS_HOME = "https://advertising.amazon.in/campaign-manager/all-campaigns?entityId=ENTITY37NJTG1VOHVTB"
# Must live under the persistent MAHIKA_STORAGE_ROOT (same dir as
# seller_central_cookies.json / agent_browser_sc_state.json), NOT a Claude
# Code session-scoped temp scratchpad - that path changes every new session,
# which was silently forcing a fresh OTP login on almost every session.
STATE_OUT = Path(os.getenv("MAHIKA_STORAGE_ROOT", str(Path(__file__).resolve().parents[2] / "data" / "mahika"))) / "sessions" / "ads_auth_state.json"
STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
MANUAL_OTP_WAIT_S = 600
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
    if not page.get_by_text("Switch accounts", exact=True).count():
        return False
    row = page.get_by_text(email, exact=False)
    if row.count():
        row.first.click(timeout=5000, force=True)
        page.wait_for_timeout(1500)
        log("clicked account row on 'Switch accounts' screen")
        return True
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


def is_ads_authenticated(page) -> bool:
    u = page.url or ""
    if "signin" in u.lower() or "/ap/" in u:
        return False
    return "advertising.amazon.in" in u


def main() -> int:
    email, password = creds()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1300, "height": 900})
        page = context.new_page()
        page.goto(ADS_HOME, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)

        if is_ads_authenticated(page):
            log("already authenticated — saving state")
            context.storage_state(path=str(STATE_OUT))
            context.close()
            browser.close()
            return 0

        for _ in range(3):
            if not dismiss_switch_accounts_screen(page, email):
                break
            page.wait_for_timeout(1000)

        log("advancing sign-in")
        state = advance_signin_until_otp_or_home(page, email, password=password, fresh=False)
        log(f"signin state -> {state}")

        if state == "stuck":
            if dismiss_switch_accounts_screen(page, email):
                state = advance_signin_until_otp_or_home(page, email, password=password, fresh=False)
                log(f"signin state (retry) -> {state}")
            if is_otp_delivery_picker(page) and not is_otp_entry_screen(page):
                submit_otp_delivery_picker(page, use_call=False)
                page.wait_for_timeout(1_500)
                state = "otp" if is_otp_entry_screen(page) else "stuck"

        if state == "home" or is_ads_authenticated(page):
            log("already authenticated after signin")
        elif state == "otp" or is_otp_entry_screen(page):
            tick_trust_device(page)
            log(f"OTP screen up — AAP KHUD OTP DALO ({MANUAL_OTP_WAIT_S}s wait budget)")
        else:
            log(f"unexpected state '{state}' — will still poll for manual completion")

        deadline = time.time() + MANUAL_OTP_WAIT_S
        done = False
        last_note = 0.0
        while time.time() < deadline:
            try:
                if is_ads_authenticated(page):
                    done = True
                    break
            except Exception:
                pass
            if time.time() - last_note > 30:
                log(f"waiting for manual completion… ({int(deadline - time.time())}s left, url={page.url[:90]})")
                last_note = time.time()
            page.wait_for_timeout(POLL_S * 1000)

        if not done:
            log("TIMEOUT — login not completed in time")
            page.screenshot(path=str(STATE_OUT.parent / "ads_login_timeout.png"))
            context.close()
            browser.close()
            return 1

        page.wait_for_timeout(1500)
        context.storage_state(path=str(STATE_OUT))
        log(f"LOGIN COMPLETE — storage state saved to {STATE_OUT}")
        context.close()
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
