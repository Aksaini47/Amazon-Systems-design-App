"""Create Seller / SP-API support case (Case Log) after Seller Central login.

Prerequisite: `mahika.cli seller-login` completed (cookies saved).

Entry paths (tried in order):
  D. Help Hub → Create new issue → My issue is not listed (primary)
  A. Seller Central → Develop Apps → Solution Provider Portal → Case Log
  B. developer.amazonservices.com/support
  C. Direct SPP /support/cases URL
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from mahika.config import settings
from mahika.playwright.account_switcher import (
    complete_account_switcher,
    is_account_switcher_page,
)
from mahika.playwright.seller_login import (
    ensure_seller_session,
    load_seller_credentials,
)
from mahika.playwright.session import (
    COOKIE_FILE,
    homepage_session_from_cookies,
    load_cookies,
    save_cookies,
    session_is_authenticated,
)
from mahika.services.notifier import send_plain_message

log = logging.getLogger(__name__)

INDIA_PAID = os.getenv(
    "AMAZON_INDIA_PAID_ACCOUNT_ID",
    "amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A",
).strip()
HOME_INDIA = f"https://sellercentral.amazon.in/home?mons_sel_dir_paid={INDIA_PAID}"
DEVELOP_APPS = f"https://sellercentral.amazon.in/apps/manage?mons_sel_dir_paid={INDIA_PAID}"
DEV_SUPPORT = "https://developer.amazonservices.com/support"
SPP_CASE_LOG = "https://solutionproviderportal.amazon.com/support/cases"

from mahika.playwright.support_case_text import (
    APP_ID,
    DEVELOPER_ID,
    get_case_text_variant,
)

_DEFAULT = get_case_text_variant()
DEFAULT_SUBJECT = _DEFAULT.subject
DEFAULT_BODY = _DEFAULT.help_with
DEFAULT_STEPS = _DEFAULT.steps_taken


@dataclass(frozen=True)
class SupportCaseDraft:
    subject: str
    help_with: str
    steps_taken: str
    developer_id: str
    app_id: str
    marketplace_label: str = "India"

    @property
    def body(self) -> str:
        """Alias for legacy fill helpers."""
        return self.help_with


def _goto_resilient(page: Page, url: str, *, timeout_ms: int = 90_000) -> None:
    """Navigate; Amazon often redirects (Help Hub) and interrupts goto."""
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except PlaywrightError as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "interrupted" not in msg and "navigation" not in msg:
                raise
            log.warning(
                "support_case: goto interrupted (attempt %s) — now at %s",
                attempt + 1,
                page.url,
            )
            page.wait_for_timeout(2_500)
    if last_exc:
        log.warning("support_case: goto gave up after retries — url=%s", page.url)


def _create_otp_watcher():
    """Telegram OTP watcher — mark_otp_waiting only when OTP screen is shown."""
    if not settings.telegram_configured:
        return None
    from mahika.services.otp_watcher import TelegramOtpWatcher

    return TelegramOtpWatcher()


def ensure_badeja_india_context(page: Page) -> bool:
    """S7 — Badeja Enterprises → India on Seller Central."""
    _goto_resilient(page, HOME_INDIA)
    page.wait_for_timeout(2_000)
    if is_account_switcher_page(page):
        return complete_account_switcher(page)
    body = ""
    try:
        body = page.inner_text("body", timeout=5_000)
    except Exception:
        pass
    if "Badeja" in body and "India" in body:
        log.info("support_case: Badeja India context already active")
        return True
    log.warning("support_case: Badeja/India not confirmed — url=%s", page.url)
    return complete_account_switcher(page)


def _click_text(page: Page, *labels: str) -> bool:
    for label in labels:
        loc = page.get_by_role("link", name=label)
        if loc.count():
            try:
                loc.first.click(timeout=10_000)
                return True
            except Exception:
                pass
        loc = page.get_by_text(label, exact=False)
        if loc.count():
            try:
                loc.first.click(timeout=10_000)
                return True
            except Exception:
                pass
    return False


def is_case_log_page(page: Page) -> bool:
    url = (page.url or "").lower()
    if "support/cases" in url or "caselog" in url:
        return True
    body = ""
    try:
        body = page.inner_text("body", timeout=5_000).lower()
    except Exception:
        pass
    return "case log" in body or "create a case" in body or "open a case" in body


def open_case_log(page: Page) -> str:
    """Navigate to Case Log / support case creation. Returns final URL."""
    log.info("support_case: path A — Develop Apps → Case Log")
    _goto_resilient(page, DEVELOP_APPS)
    page.wait_for_timeout(3_000)
    url = page.url
    log.info("support_case: after Develop Apps → %s", url)

    if "solutionproviderportal" in url:
        if _click_text(page, "Case Log", "Launch Case Log", "Support", "Create a case"):
            page.wait_for_timeout(2_500)
            return page.url
        _goto_resilient(page, SPP_CASE_LOG, timeout_ms=60_000)
        return page.url

    log.info("support_case: path B — developer.amazonservices.com/support")
    _goto_resilient(page, DEV_SUPPORT, timeout_ms=60_000)
    page.wait_for_timeout(2_000)
    if _click_text(
        page,
        "Create a case",
        "Need to open a case",
        "contact Developer Support",
        "Case Log",
    ):
        page.wait_for_timeout(2_500)
        return page.url

    log.info("support_case: path C — direct SPP Case Log URL")
    _goto_resilient(page, SPP_CASE_LOG, timeout_ms=60_000)
    return page.url


def fill_support_case_form(page: Page, draft: SupportCaseDraft, *, submit: bool) -> None:
    """Best-effort fill — Amazon forms vary by portal skin."""
    page.wait_for_timeout(2_000)
    for selector, value in (
        ("textarea", draft.help_with),
        ("input[type='text']", draft.subject),
    ):
        loc = page.locator(selector)
        if loc.count():
            try:
                loc.first.fill(value, timeout=8_000)
            except Exception:
                pass

    for label, text in (
        ("Developer", draft.developer_id),
        ("Application", draft.app_id),
        ("Marketplace", draft.marketplace_label),
        ("getOrders", "getOrders"),
    ):
        try:
            page.get_by_label(label).fill(text, timeout=4_000)
        except Exception:
            pass

    out = settings.storage_root / "logs" / "support_case_form.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out))
    log.info("support_case: screenshot %s", out)

    if not submit:
        log.info("support_case: form filled — review in browser (no submit)")
        return

    for btn in ("Submit", "Create case", "Send", "Continue", "Open case"):
        b = page.get_by_role("button", name=btn)
        if b.count():
            try:
                b.first.click(timeout=10_000)
                page.wait_for_timeout(5_000)
                log.info("support_case: clicked %s", btn)
                return
            except Exception:
                continue
    log.warning("support_case: submit button not found — manual submit needed")


def run_support_case_flow(
    *,
    headless: bool = False,
    submit: bool = False,
    review_wait_s: float = 120.0,
    draft: SupportCaseDraft | None = None,
    skip_login: bool = False,
) -> bool:
    """
    Full flow: login (if needed) → Badeja India → Case Log → fill form.

    Returns True when form reached and filled (submit optional).
    """
    if not COOKIE_FILE.exists() and skip_login:
        raise RuntimeError("No cookies — run: python -m mahika.cli seller-login")

    creds = load_seller_credentials()
    text = get_case_text_variant()
    case = draft or SupportCaseDraft(
        subject=text.subject,
        help_with=text.help_with,
        steps_taken=text.steps_taken,
        developer_id=DEVELOPER_ID,
        app_id=APP_ID,
    )

    send_plain_message(
        f"Mahika: Support case flow start ({creds.email}).\n"
        f"Submit={'yes' if submit else 'review only'}"
    )

    watcher = None
    if settings.telegram_configured and not skip_login:
        watcher = _create_otp_watcher()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "logs").mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()
        load_cookies(context)
        page = context.new_page()
        try:
            if skip_login:
                if not homepage_session_from_cookies(page):
                    send_plain_message(
                        "Mahika: support-case — cookies expired. Run seller-login."
                    )
                    return False
            elif not homepage_session_from_cookies(page):
                if not ensure_seller_session(page, creds, watcher):
                    send_plain_message("Mahika: Support case — login failed.")
                    return False

            if not session_is_authenticated(page) and not is_account_switcher_page(page):
                if not ensure_seller_session(page, creds, watcher):
                    return False

            ensure_badeja_india_context(page)

            from mahika.playwright.help_hub_case_flow import run_help_hub_case_path

            ok_path_d = run_help_hub_case_path(page, case, submit=submit)
            if not ok_path_d:
                log.error(
                    "support_case: path D (Help Hub) failed — "
                    "no Case Lobby / developer portal fallback"
                )
                out = settings.storage_root / "logs" / "support_case_form.png"
                try:
                    page.screenshot(path=str(out), full_page=True)
                except Exception:
                    pass
                send_plain_message("Mahika: Help Hub case failed — see support_case_form.png")
                return False
            elif not submit and not headless and review_wait_s > 0:
                log.info("support_case: browser open %.0fs for review", review_wait_s)
                page.wait_for_timeout(int(review_wait_s * 1000))

            send_plain_message(
                "Mahika: SP-API production case — "
                + ("submitted." if submit else "ready for review.")
                + f"\nURL: {page.url}"
            )
            save_cookies(context)
            return ok_path_d
        finally:
            page.close()
            context.close()
            browser.close()
