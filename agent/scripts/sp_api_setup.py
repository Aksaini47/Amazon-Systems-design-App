"""One-shot SP-API credential harvest from Solution Provider Portal.

Logs in as admin, opens Developer Central under profile A8C5XXFI7YLLM,
creates/opens sandbox app, copies LWA creds + refresh token into root .env.

Usage (from agent/):
    .venv\\Scripts\\python.exe scripts\\sp_api_setup.py
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT / "src"))
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SPP_SIGNIN = "https://solutionproviderportal.amazon.com/"
DEV_CONSOLE = (
    "https://solutionproviderportal.amazon.com/sellingpartner/developerconsole"
    "?mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A"
)
APP_FORM = "https://solutionproviderportal.amazon.com/sellingpartner/developerconsole/application"
PROFILE_LABEL = "A8C5XXFI7YLLM"
APP_NAME = "Mahika v1"


def _admin_creds() -> tuple[str, str]:
    email = os.getenv("AMAZON_ADMIN_EMAIL", "").strip()
    password = os.getenv("AMAZON_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        raise RuntimeError("AMAZON_ADMIN_EMAIL/PASSWORD missing in root .env")
    return email, password


def _otp_watcher():
    from mahika.services.otp_watcher import TelegramOtpWatcher

    w = TelegramOtpWatcher()
    w.mark_start()
    return w


def _sign_in(page: Page, email: str, password: str) -> None:
    page.goto(SPP_SIGNIN, wait_until="domcontentloaded", timeout=60_000)
    time.sleep(2)
    if "signin" not in page.url and "ap/signin" not in page.url:
        log.info("Already signed in to SPP (%s)", page.url)
        return
    if page.locator("#ap_email, input[name='email']").count() == 0:
        log.info("No sign-in form — assuming session active")
        return
    page.wait_for_selector("#ap_email, input[name='email']", timeout=30_000)
    page.fill("#ap_email, input[name='email']", email)
    page.locator("#continue, input#continue, button:has-text('Continue')").first.click()
    page.wait_for_selector("#ap_password, input[name='password']", timeout=30_000)
    page.fill("#ap_password, input[name='password']", password)
    page.locator("#signInSubmit, input[type='submit']").first.click()
    page.wait_for_timeout(3_000)
    if page.locator("#auth-mfa-otpcode, input[name='otpCode']").count():
        watcher = _otp_watcher()
        log.info("OTP required — send 6-digit code to Telegram bot")
        watcher.mark_otp_waiting()
        otp = watcher.wait_for_otp(timeout_s=180.0, log_every_s=60.0, telegram_nudge=False)
        if not otp:
            raise RuntimeError("OTP timeout — send 6-digit code to Telegram and retry")
        page.fill("#auth-mfa-otpcode, input[name='otpCode']", otp)
        page.locator("#auth-signin-button, input[type='submit']").first.click()
        page.wait_for_timeout(4_000)


def _select_profile(page: Page) -> None:
    page.goto(
        "https://solutionproviderportal.amazon.com/account-switcher/default/merchantMarketplace"
        "?returnTo=%2Fsellingpartner%2Fdeveloperconsole",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    page.wait_for_timeout(2_000)
    btn = page.locator(f"button:has-text('{PROFILE_LABEL}')")
    if btn.count() == 0:
        page.wait_for_timeout(3_000)
    btn.first.click(timeout=15_000)
    page.locator("kat-button:has-text('Select account'), button:has-text('Select account')").first.click(
        force=True
    )
    page.wait_for_timeout(3_000)


def _create_sandbox_app(page: Page) -> None:
    page.goto(DEV_CONSOLE, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(3_000)
    if page.locator(f"text={APP_NAME}").count():
        log.info("App %s already listed", APP_NAME)
        page.locator(f"text={APP_NAME}").first.click()
        return
    add = page.locator("text=Add new app client")
    if add.count() == 0:
        page.goto(APP_FORM, wait_until="domcontentloaded")
    else:
        add.first.click()
    page.wait_for_timeout(2_000)
    page.fill("input[name='appName'], input[type='text']", APP_NAME)
    page.locator("kat-dropdown").click()
    page.locator("kat-option:has-text('SP API'), text=SP API").first.click()
    page.locator("button:has-text('Save and exit'), kat-button:has-text('Save and exit')").first.click(
        force=True
    )
    page.wait_for_timeout(2_000)
    sandbox = page.locator("input[type='radio'], kat-radiobutton").filter(has_text="Sandbox")
    if sandbox.count():
        sandbox.first.click(force=True)
    page.locator("button:has-text('Save and exit'), kat-button:has-text('Save and exit')").first.click(
        force=True
    )
    page.wait_for_timeout(4_000)
    page.goto(DEV_CONSOLE, wait_until="domcontentloaded")
    page.wait_for_timeout(2_000)
    if page.locator(f"text={APP_NAME}").count():
        page.locator(f"text={APP_NAME}").first.click()
    page.wait_for_timeout(3_000)


def _scrape_lwa(page: Page) -> tuple[str, str]:
    html = page.content()
    ids = re.findall(r"(amzn1\.application-oa2-client\.[A-Za-z0-9]+)", html)
    secrets = re.findall(
        r"(?:LWA Client Secret|Client Secret)[^A-Za-z0-9|]*([A-Za-z0-9]{20,})",
        html,
        re.I,
    )
    if not ids:
        # try visible text blocks
        body = page.inner_text("body")
        ids = re.findall(r"(amzn1\.application-oa2-client\.[A-Za-z0-9]+)", body)
        secrets = re.findall(r"Client Secret\s*\n?\s*([A-Za-z0-9]{20,})", body, re.I)
    if not ids:
        raise RuntimeError("LWA Client ID not found on app page — migration may still be running")
    client_id = ids[0]
    client_secret = secrets[0] if secrets else ""
    if not client_secret:
        # click View / Show if present
        show = page.locator("button:has-text('View'), button:has-text('Show'), text=View")
        if show.count():
            show.first.click()
            page.wait_for_timeout(1_000)
            body = page.inner_text("body")
            secrets = re.findall(r"Client Secret\s*\n?\s*([A-Za-z0-9]{20,})", body, re.I)
            client_secret = secrets[0] if secrets else ""
    if not client_secret:
        raise RuntimeError("LWA Client Secret not found — copy manually from SPP app page")
    return client_id, client_secret


def _authorize_refresh_token(page: Page) -> str:
    auth = page.locator(
        "button:has-text('Authorize'), a:has-text('Authorize'), text=Authorize app"
    )
    if auth.count():
        auth.first.click()
        page.wait_for_timeout(5_000)
    body = page.content()
    tokens = re.findall(r"(Atzr\|[A-Za-z0-9/_+=.-]+)", body)
    if tokens:
        return tokens[0]
    # Seller Central authorize flow in popup
    if len(page.context.pages) > 1:
        popup = page.context.pages[-1]
        popup.wait_for_load_state("domcontentloaded")
        popup.wait_for_timeout(3_000)
        tokens = re.findall(r"(Atzr\|[A-Za-z0-9/_+=.-]+)", popup.content())
        if tokens:
            return tokens[0]
    return ""


def _patch_env(client_id: str, client_secret: str, refresh_token: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8")
    replacements = {
        "MAHIKA_SP_API_LWA_CLIENT_ID": client_id,
        "MAHIKA_SP_API_LWA_CLIENT_SECRET": client_secret,
        "MAHIKA_SP_API_REFRESH_TOKEN": refresh_token,
        "BACKEND_AMAZON_CLIENT_ID": client_id,
        "BACKEND_AMAZON_CLIENT_SECRET": client_secret,
        "BACKEND_AMAZON_REFRESH_TOKEN": refresh_token,
    }

    for key, val in replacements.items():
        if not val:
            continue
        pattern = rf"^{re.escape(key)}=.*$"
        line = f"{key}={val}"
        if re.search(pattern, text, re.M):
            text = re.sub(pattern, line, text, count=1, flags=re.M)
        else:
            text += f"\n{line}\n"

    ENV_PATH.write_text(text, encoding="utf-8")
    log.info("Updated %s", ENV_PATH)


def main() -> int:
    email, password = _admin_creds()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        try:
            _sign_in(page, email, password)
            _select_profile(page)
            _create_sandbox_app(page)
            client_id, client_secret = _scrape_lwa(page)
            log.info("LWA Client ID: %s...", client_id[:40])
            refresh = _authorize_refresh_token(page)
            if refresh:
                log.info("Refresh token captured")
            else:
                log.warning("Refresh token not auto-captured — authorize app manually on Seller Central")
            _patch_env(client_id, client_secret, refresh)
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
