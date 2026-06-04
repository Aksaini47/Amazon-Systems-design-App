"""Post-OTP account switcher — Badeja Enterprises → India → Select account."""
from __future__ import annotations

import logging
import os
import re

from playwright.sync_api import Page

log = logging.getLogger(__name__)

ACCOUNT_NAME = os.getenv("AMAZON_SELLER_ACCOUNT_NAME", "Badeja Enterprises").strip()
MARKETPLACE_NAME = os.getenv("AMAZON_SELLER_MARKETPLACE", "India").strip()


def _body_text(page: Page) -> str:
    try:
        return page.inner_text("body", timeout=5_000)
    except Exception:
        return ""


def is_account_switcher_page(page: Page) -> bool:
    url = (page.url or "").lower()
    if "/account-switcher" in url:
        return True
    body = _body_text(page).lower()
    if "badeja" in body and ("select account" in body or "merchantmarketplace" in url):
        return True
    if ACCOUNT_NAME.lower() in body and "select account" in body:
        return True
    return False


def _click_text(page: Page, pattern: str | re.Pattern[str], *, label: str) -> bool:
    try:
        loc = page.get_by_text(pattern)
        if loc.count() == 0:
            return False
        loc.first.scroll_into_view_if_needed(timeout=5_000)
        loc.first.click(force=True, timeout=10_000)
        page.wait_for_timeout(1_500)
        log.info("account_switcher: clicked %s", label)
        return True
    except Exception as exc:
        log.debug("account_switcher: %s click failed (%s)", label, exc)
        return False


def _click_select_account(page: Page) -> bool:
    selectors = (
        "button:has-text('Select account')",
        "input[type='submit']:has-text('Select account')",
        "kat-button:has-text('Select account')",
        "a:has-text('Select account')",
    )
    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            btn = loc.first
            if btn.is_disabled():
                log.debug("account_switcher: Select account disabled — waiting")
                page.wait_for_timeout(1_000)
                continue
            btn.click(force=True, timeout=10_000)
            page.wait_for_timeout(2_500)
            log.info("account_switcher: Select account (%s)", sel)
            return True
        except Exception:
            continue

    try:
        page.get_by_role("button", name=re.compile(r"select account", re.I)).first.click(
            force=True, timeout=10_000
        )
        page.wait_for_timeout(2_500)
        log.info("account_switcher: Select account (role=button)")
        return True
    except Exception as exc:
        log.warning("account_switcher: Select account not found (%s)", exc)
        return False


def complete_account_switcher(page: Page, *, timeout_s: float = 45.0) -> bool:
    """
    S7: After valid OTP — Badeja Enterprises → India → Select account / Continue.
    Returns True if switcher was completed or not shown.
    """
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not is_account_switcher_page(page):
            from mahika.playwright.session import session_is_authenticated

            if session_is_authenticated(page):
                log.info("account_switcher: already on home — skip")
                return True
            page.wait_for_timeout(1_500)
            continue

        log.info(
            "account_switcher: S7 — %s → %s → Select account",
            ACCOUNT_NAME,
            MARKETPLACE_NAME,
        )

        if ACCOUNT_NAME:
            _click_text(
                page,
                re.compile(re.escape(ACCOUNT_NAME), re.I),
                label=ACCOUNT_NAME,
            )

        _click_text(
            page,
            re.compile(rf"^{re.escape(MARKETPLACE_NAME)}$", re.I),
            label=MARKETPLACE_NAME,
        )

        if not _click_select_account(page):
            _click_text(page, re.compile(r"^Continue$", re.I), label="Continue")

        page.wait_for_timeout(3_000)
        if not is_account_switcher_page(page):
            log.info("account_switcher: switcher done — url=%s", page.url)
            return True

        page.wait_for_timeout(1_500)

    log.warning("account_switcher: timeout on switcher screen")
    return False
