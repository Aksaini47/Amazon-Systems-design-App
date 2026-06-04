"""Amazon / Seller Central sign-in — advance through picker until OTP or home.

When cookies exist, Amazon often shows "already logged in" account picker instead
of email form. Automation must click Continue / pick account until OTP screen.
"""
from __future__ import annotations

import logging
import os
import re
import time

from playwright.sync_api import Page

from mahika.playwright.selectors import SELECTORS
from mahika.playwright.session import session_is_authenticated

log = logging.getLogger(__name__)

S = SELECTORS.login
_OTP_PHONE_SUFFIX = os.getenv("AMAZON_OTP_PHONE_SUFFIX", "711").strip() or "711"
# Amazon blocks repeat Send OTP — "wait at least one minute" (see screenshot in rules).
POST_OTP_ACTION_COOLDOWN_S = 60

_CONTINUE_SELECTORS = (
    "input#continue",
    "#continue",
    "button:has-text('Continue')",
    "input[type='submit'][aria-labelledby*='continue']",
    "kat-button:has-text('Continue')",
)
_SIGN_IN_SELECTORS = (
    "input#signInSubmit",
    "#signInSubmit",
    "button:has-text('Sign in')",
    "input[type='submit'][id*='signIn']",
)


def _body_text(page: Page) -> str:
    try:
        return page.inner_text("body", timeout=3_000)
    except Exception:
        return ""


def _click_first(page: Page, selectors: tuple[str, ...]) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            if loc.first.is_visible():
                loc.first.click(force=True, timeout=5_000)
                page.wait_for_timeout(1_500)
                return True
        except Exception:
            continue
    return False


def _click_account_for_email(page: Page, email: str) -> bool:
    """Pick saved account row matching seller email."""
    email_l = email.lower().strip()
    # Link or button containing full or local part of email
    local = email_l.split("@")[0]
    for pattern in (email_l, local):
        for role in ("link", "button"):
            loc = page.get_by_role(role, name=re.compile(re.escape(pattern), re.I))
            if loc.count():
                try:
                    loc.first.click(timeout=5_000)
                    page.wait_for_timeout(1_500)
                    log.info("signin_flow: clicked account %s", pattern)
                    return True
                except Exception:
                    pass
        loc = page.get_by_text(re.compile(pattern, re.I))
        if loc.count():
            try:
                loc.first.click(timeout=5_000)
                page.wait_for_timeout(1_500)
                log.info("signin_flow: clicked text %s", pattern)
                return True
            except Exception:
                pass
    return False


def _click_picker_row(page: Page, email: str) -> bool:
    """Click account tile in Amazon 'pick account' UI."""
    local = email.split("@")[0].lower()
    for sel in (
        f"a:has-text('{email}')",
        f"div:has-text('{email}')",
        f"span:has-text('{local}')",
        ".cvf-account-switcher-additional-info",
        ".a-button-primary input",
    ):
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            loc.first.click(force=True, timeout=5_000)
            page.wait_for_timeout(1_500)
            log.info("signin_flow: picker row %s", sel)
            return True
        except Exception:
            continue
    return False


def _body_has_delivery_picker(body: str) -> bool:
    lower = body.lower()
    return (
        "choose where to receive" in lower
        or ("two-step verification" in lower and "send otp" in lower)
        or (
            "call me at my number ending in" in lower
            and _OTP_PHONE_SUFFIX in lower
        )
        or (
            "whatsapp me at my number ending in" in lower
            and "send otp" in lower
        )
    )


def _is_mfa_new_otp_url(page: Page) -> bool:
    return "/ap/mfa/new-otp" in page.url


def is_otp_delivery_picker(page: Page) -> bool:
    """Amazon 'Choose where to receive OTP' screen (radios + Send OTP)."""
    if page.locator(S.otp_input).count() > 0:
        return False
    if _is_mfa_new_otp_url(page):
        return True
    body = _body_text(page)
    if not _body_has_delivery_picker(body):
        return False
    return not _body_is_recovery_trap(body)


def _body_is_recovery_trap(body: str) -> bool:
    lower = body.lower()
    # SMS-unavailable banner appears ON the delivery picker — not the recovery page.
    if "two-step verification" in lower and "send otp" in lower:
        if any(
            m in lower
            for m in (
                "whatsapp me",
                "call me at my number",
                "text me at my number",
                "choose where to receive",
            )
        ):
            return False
    traps = (
        "didn't receive the code",
        "did not receive the code",
        "two-step verification account recovery",
        "verification account recovery",
    )
    if any(t in lower for t in traps):
        return True
    if "unable to send" in lower and "send otp" not in lower:
        return True
    if "didn't receive" in lower and "choose where to receive" not in lower:
        return True
    return False


def is_otp_didnt_receive_trap(page: Page) -> bool:
    """Recovery / 'Didn't receive code' page — NOT the delivery picker or OTP box."""
    if page.locator(S.otp_input).count() > 0:
        try:
            if page.locator(S.otp_input).first.is_visible():
                return False
        except Exception:
            pass
    if _body_has_delivery_picker(_body_text(page)):
        return False
    return _body_is_recovery_trap(_body_text(page))


def escape_didnt_receive_trap(page: Page) -> bool:
    """Back out of recovery trap → return to delivery picker or OTP entry."""
    log.warning("signin_flow: 'Didn't receive' / recovery trap — clicking Back")
    if not _click_first(page, ("button:has-text('Back')", "a:has-text('Back')")):
        return False
    page.wait_for_timeout(2_500)
    return True


def handle_post_password_mfa(page: Page) -> str | None:
    """After Sign-in: Scenario 1 — delivery picker (default option) → OTP box."""
    page.wait_for_timeout(2_000)

    if is_otp_didnt_receive_trap(page):
        if escape_didnt_receive_trap(page):
            page.wait_for_timeout(2_000)
        if is_otp_didnt_receive_trap(page):
            log.warning("signin_flow: recovery trap after Back")
            return "stuck"

    if is_otp_delivery_picker(page):
        log.info("signin_flow: post-password — delivery picker (default + Send OTP)")
        if submit_otp_delivery_picker(page, use_call=False):
            page.wait_for_timeout(3_000)
        else:
            return "stuck"

    if page.locator(S.otp_input).count() > 0:
        log.info("signin_flow: post-password — OTP entry screen")
        return "otp"

    return None


def is_otp_rate_limited(page: Page) -> bool:
    """Red banner: wait at least one minute before requesting another OTP."""
    lower = _body_text(page).lower()
    return (
        "wait at least one minute" in lower
        or "before requesting another otp" in lower
        or (
            "there was a problem" in lower
            and "otp" in lower
            and "minute" in lower
        )
    )


def is_otp_entry_screen(page: Page) -> bool:
    """S4 — OTP typed here; do not open picker / re-Send OTP."""
    loc = page.locator(S.otp_input)
    if loc.count() == 0:
        return False
    try:
        return loc.first.is_visible()
    except Exception:
        return True


def wait_amazon_otp_cooldown(page: Page, *, reason: str) -> None:
    """Wait 60s after radio change or Send OTP — avoids rate-limit loop."""
    log.info(
        "signin_flow: Amazon OTP cooldown %ss (%s)",
        POST_OTP_ACTION_COOLDOWN_S,
        reason,
    )
    deadline = time.monotonic() + POST_OTP_ACTION_COOLDOWN_S
    while time.monotonic() < deadline:
        if is_otp_entry_screen(page):
            log.info("signin_flow: OTP entry visible — cooldown done early")
            return
        if is_otp_rate_limited(page):
            left = max(0, int(deadline - time.monotonic()))
            if left % 15 == 0 or left <= 5:
                log.info(
                    "signin_flow: rate-limit banner — %ss left (do not click Send OTP)",
                    left,
                )
        page.wait_for_timeout(2_000)
    page.wait_for_timeout(500)


def _click_send_otp_on_picker(page: Page) -> bool:
    send_selectors = (
        S.otp_delivery_send_button,
        "input[type='submit']:has-text('Send OTP')",
        "button:has-text('Send OTP')",
        "input.a-button-input:has-text('Send OTP')",
    )
    if not _click_first(page, send_selectors):
        try:
            page.get_by_role("button", name=re.compile(r"^Send OTP$", re.I)).first.click(
                force=True, timeout=8_000
            )
        except Exception as exc:
            log.warning("signin_flow: Send OTP button not found (%s)", exc)
            return False
    return True


def submit_otp_delivery_picker(
    page: Page, *, use_call: bool = False, phone_suffix: str | None = None
) -> bool:
    """OTP delivery screen: default/Send OTP first; Call …711 only when ``use_call``."""
    if is_otp_entry_screen(page):
        log.info("signin_flow: already on OTP entry — skip picker / Send OTP")
        return True

    if is_otp_rate_limited(page):
        log.warning("signin_flow: rate limited before Send OTP — cooling down")
        wait_amazon_otp_cooldown(page, reason="rate-limit-before-send")
        if is_otp_entry_screen(page):
            return True
        if is_otp_rate_limited(page):
            log.warning("signin_flow: still rate limited — not clicking Send OTP again")
            return False

    suffix = (phone_suffix or _OTP_PHONE_SUFFIX).strip()

    if use_call:
        log.info("signin_flow: picker — select Call …%s then Send OTP", suffix)
        call_patterns = (
            re.compile(rf"Call me at my number ending in\s*{re.escape(suffix)}", re.I),
            re.compile(rf"Call me.*ending in\s*{re.escape(suffix)}", re.I),
        )
        selected = False
        for pattern in call_patterns:
            loc = page.get_by_text(pattern)
            if loc.count() == 0:
                continue
            try:
                loc.first.scroll_into_view_if_needed(timeout=3_000)
                loc.first.click(force=True, timeout=8_000)
                page.wait_for_timeout(1_000)
                log.info("signin_flow: selected call delivery …%s", suffix)
                selected = True
                break
            except Exception as exc:
                log.debug("signin_flow: call label click failed (%s)", exc)
        if not selected:
            radios = page.locator("input[type='radio']")
            if radios.count() >= 2:
                try:
                    radios.nth(1).check(force=True)
                    selected = True
                except Exception:
                    pass
        if not selected:
            log.warning("signin_flow: could not select Call …%s", suffix)
            return False
        wait_amazon_otp_cooldown(page, reason="after-call-radio-711")
    else:
        log.info(
            "signin_flow: picker — Send OTP on default option (Telegram wait pehle, call baad mein)"
        )

    if is_otp_rate_limited(page):
        wait_amazon_otp_cooldown(page, reason="rate-limit-before-send-otp-click")
        if is_otp_entry_screen(page):
            return True

    if not _click_send_otp_on_picker(page):
        return False

    wait_amazon_otp_cooldown(page, reason="after-send-otp-click")
    log.info("signin_flow: Send OTP done — cooldown finished, expect OTP input")
    return True


def select_call_delivery_and_send_otp(
    page: Page, *, phone_suffix: str | None = None
) -> bool:
    """Call …711 + Send OTP (used after Telegram wait fails)."""
    return submit_otp_delivery_picker(
        page, use_call=True, phone_suffix=phone_suffix
    )


def _password_visible(page: Page) -> bool:
    loc = page.locator(S.password_input)
    if loc.count() == 0:
        return False
    try:
        return loc.first.is_visible()
    except Exception:
        return False


def _submit_password(page: Page, password: str) -> bool:
    if not _password_visible(page):
        return False
    page.fill(S.password_input, password)
    clicked = _click_first(page, _SIGN_IN_SELECTORS)
    log.info("signin_flow: password filled, sign-in clicked=%s", clicked)
    try:
        page.wait_for_selector(
            S.password_input, state="hidden", timeout=12_000
        )
    except Exception:
        page.wait_for_timeout(2_500)
    return True


def _click_switch_account(page: Page) -> bool:
    """Force full sign-in (email + password) instead of saved-account loop."""
    for sel in (
        "a:has-text('Not you')",
        "a:has-text('Not You')",
        "a:has-text('Switch account')",
        "a:has-text('Use another account')",
        "#ap_switch_account_link",
    ):
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        try:
            if loc.first.is_visible():
                loc.first.click(force=True, timeout=5_000)
                page.wait_for_timeout(2_000)
                log.info("signin_flow: clicked switch account (%s)", sel)
                return True
        except Exception:
            continue
    return False


def _already_logged_in_screen(page: Page, email: str) -> bool:
    """Saved-account / welcome-back picker — NOT the password or OTP screen."""
    if session_is_authenticated(page):
        return False
    if _password_visible(page):
        return False
    if page.locator(S.otp_input).count() > 0:
        return False
    body = _body_text(page).lower()
    markers = (
        "not you",
        "switch account",
        "choose an account",
        "pick an account",
        "welcome back",
        "who is shopping",
    )
    if sum(1 for m in markers if m in body) >= 1:
        return True
    if email.lower() in body and "#ap_email" not in page.url:
        if page.locator(S.email_input).count() == 0:
            return True
        try:
            if not page.locator(S.email_input).first.is_visible():
                return True
        except Exception:
            return True
    return False


def advance_signin_until_otp_or_home(
    page: Page,
    email: str,
    *,
    password: str | None = None,
    max_steps: int = 40,
    step_pause_ms: int = 1_500,
    fresh: bool = False,
) -> str:
    """Click through Amazon sign-in UI until OTP, home, or stuck.

    Returns:
        ``home`` — Seller Central authenticated
        ``otp`` — OTP input visible (SMS should be sent / forward to Telegram)
        ``password_needed`` — password field visible but not filled
        ``stuck`` — no progress
    """
    account_row_clicked = False
    picker_stall = 0

    for step in range(max_steps):
        if session_is_authenticated(page):
            log.info("signin_flow: authenticated (step %d)", step)
            return "home"

        if fresh and step == 0 and _click_switch_account(page):
            continue

        if password and _submit_password(page, password):
            picker_stall = 0
            post = handle_post_password_mfa(page)
            if post == "otp":
                return "otp"
            if post == "stuck":
                return "stuck"
            continue

        if is_otp_didnt_receive_trap(page):
            log.info("signin_flow: recovery trap (step %d)", step)
            if escape_didnt_receive_trap(page):
                post = handle_post_password_mfa(page)
                if post == "otp":
                    return "otp"
                continue
            return "stuck"

        if is_otp_delivery_picker(page):
            log.info("signin_flow: OTP delivery picker (step %d)", step)
            if submit_otp_delivery_picker(page, use_call=False):
                page.wait_for_timeout(2_000)
                continue
            return "stuck"

        if page.locator(S.otp_input).count() > 0:
            log.info("signin_flow: OTP screen (step %d)", step)
            return "otp"

        if _already_logged_in_screen(page, email):
            log.info("signin_flow: saved account / picker (step %d)", step)
            picker_stall += 1
            if picker_stall > 8:
                log.warning("signin_flow: picker loop — trying Switch account")
                if _click_switch_account(page):
                    picker_stall = 0
                    continue
                return "stuck"
            # Continue advances pre-selected account → password screen
            if _click_first(page, _CONTINUE_SELECTORS):
                picker_stall = 0
                continue
            if not account_row_clicked:
                if _click_account_for_email(page, email) or _click_picker_row(
                    page, email
                ):
                    account_row_clicked = True
                    continue
            if _click_first(page, _CONTINUE_SELECTORS):
                picker_stall = 0
                continue
            continue

        picker_stall = 0

        if page.locator(S.email_input).count() > 0:
            try:
                if page.locator(S.email_input).first.is_visible():
                    page.fill(S.email_input, email)
                    _click_first(page, _CONTINUE_SELECTORS)
                    page.wait_for_timeout(2_000)
                    continue
            except Exception:
                pass

        if _click_first(page, _CONTINUE_SELECTORS):
            log.info("signin_flow: Continue (step %d)", step)
            continue

        if _click_first(page, _SIGN_IN_SELECTORS):
            log.info("signin_flow: Sign in (step %d)", step)
            continue

        # Generic consent / proceed
        for label in ("Yes", "Proceed", "Accept", "Done"):
            loc = page.get_by_role("button", name=label)
            if loc.count() and "cookie" in body.lower():
                try:
                    loc.first.click(timeout=3_000)
                    page.wait_for_timeout(1_000)
                    break
                except Exception:
                    pass

        page.wait_for_timeout(step_pause_ms)

    log.warning("signin_flow: stuck after %d steps url=%s", max_steps, page.url)
    return "stuck"
