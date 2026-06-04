"""Telegram OTP watcher — read 6-digit codes from Sir's bot chat.

Sir sends only the 6-digit Amazon OTP (or full SMS) to @mahika_arun_bot.
Playwright login polls getUpdates and fills Seller Central automatically.

See scripts/OTP_SETUP.md for chat ID setup.
"""
from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from mahika.config import settings
from mahika.services.notifier import send_otp_nudge

log = logging.getLogger(__name__)

# Amazon India SMS patterns (full SMS still accepted)
_OTP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:OTP|one.?time|verification|passcode)[^\d]{0,40}(\d{6})", re.I),
    re.compile(r"(\d{6})[^\d]{0,20}(?:OTP|one.?time|verification)", re.I),
    re.compile(r"\b(\d{6})\b"),
)

_OFFSET_FILE = settings.storage_root / "sessions" / ".telegram_update_offset"
_POLL_LOCK_FILE = settings.storage_root / "sessions" / ".telegram_poll.lock"

# Accept messages up to 3 minutes before mark_otp_waiting (clock / early SMS)
_GRACE_BEFORE_WAIT = timedelta(minutes=3)
REMINDER_INTERVAL_S = 60.0
LOG_INTERVAL_S = 60.0
_STATUS_FILE = settings.storage_root / "logs" / "seller_login_live.txt"


def _terminal_ping(message: str) -> None:
    """Visible line in the seller-login console (same window as python -m mahika.cli)."""
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[{ts}] Mahika OTP — {message}", flush=True)


def _load_offset() -> int:
    if not _OFFSET_FILE.exists():
        return 0
    try:
        data = json.loads(_OFFSET_FILE.read_text(encoding="utf-8"))
        return int(data.get("update_id", 0))
    except Exception:
        return 0


def _save_offset(update_id: int) -> None:
    _OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OFFSET_FILE.write_text(
        json.dumps({"update_id": update_id, "saved_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )


def _normalize_chat_id(chat_id: object) -> str:
    return str(chat_id).strip()


def extract_otp(text: str) -> str | None:
    """Return a 6-digit OTP from Telegram text (digits-only or SMS)."""
    if not text or not text.strip():
        return None

    stripped = text.strip()
    # "847291" or "OTP 847291" or "847291 is your OTP"
    digits_only = re.sub(r"\D", "", stripped)
    if len(digits_only) == 6 and digits_only.isdigit():
        return digits_only

    if stripped.isdigit() and len(stripped) == 6:
        return stripped

    lower = text.lower()
    amazonish = any(
        k in lower
        for k in ("amazon", "otp", "one time", "verification", "seller", "passcode")
    )
    for pattern in _OTP_PATTERNS[:2]:
        match = pattern.search(text)
        if match:
            code = match.group(1)
            if len(code) == 6 and code.isdigit():
                return code
    if amazonish:
        match = _OTP_PATTERNS[2].search(text)
        if match:
            code = match.group(1)
            if len(code) == 6 and code.isdigit():
                return code
    return None


@contextmanager
def _telegram_poll_lock():
    """Only one Mahika process may poll getUpdates (avoids stealing OTP updates)."""
    _POLL_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(_POLL_LOCK_FILE, "a+b")
    try:
        try:
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        except ImportError:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            try:
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except ImportError:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class TelegramOtpWatcher:
    """Poll Sir's Telegram chat for a fresh Amazon OTP."""

    def __init__(self) -> None:
        if not settings.telegram_configured:
            raise RuntimeError("Telegram not configured — see scripts/OTP_SETUP.md")
        self._offset = _load_offset()
        self._started_at: datetime | None = None
        self._used: set[str] = set()
        self._expected_chat = _normalize_chat_id(settings.telegram_chat_id)
        self._last_telegram_nudge: float = 0.0
        self._otp_wait_deadline: float | None = None
        self._otp_prompt_sent: bool = False

    def mark_start(self) -> None:
        """Legacy entry — prefer mark_otp_waiting() when OTP screen is visible."""
        self.mark_otp_waiting()

    def mark_otp_waiting(self, *, total_wait_s: float = 600.0) -> None:
        """Start accepting OTPs (clears used codes, grace window for early SMS)."""
        self._used.clear()
        self._started_at = datetime.now(UTC) - _GRACE_BEFORE_WAIT
        # Allow first Telegram nudge on the next log tick (not blocked for 60s).
        self._last_telegram_nudge = time.monotonic() - REMINDER_INTERVAL_S
        self._otp_wait_deadline = time.monotonic() + total_wait_s
        tail = self._expected_chat[-4:] if len(self._expected_chat) >= 4 else "????"
        log.info(
            "otp_watcher: waiting for 6-digit OTP (Telegram chat …%s)",
            tail,
        )
        self._write_live_status("OTP screen — send 6-digit code to bot")

    def _write_live_status(self, line: str) -> None:
        try:
            _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            left = 0
            if self._otp_wait_deadline is not None:
                left = max(0, int(self._otp_wait_deadline - time.monotonic()))
            _STATUS_FILE.write_text(
                f"{datetime.now(UTC).isoformat()} | {line} | {left}s left\n",
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("otp_watcher: status file write failed (%s)", exc)

    def wait_for_otp(
        self,
        *,
        timeout_s: float = 600.0,
        poll_s: float = 2.0,
        log_every_s: float = LOG_INTERVAL_S,
        telegram_nudge: bool = False,
        telegram_nudge_interval_s: float = REMINDER_INTERVAL_S,
    ) -> str | None:
        """Block until OTP arrives. Terminal + Telegram reminders at most every 60s."""
        if self._started_at is None:
            self.mark_otp_waiting(total_wait_s=timeout_s)
        elif self._otp_wait_deadline is None:
            self._otp_wait_deadline = time.monotonic() + timeout_s

        deadline = time.monotonic() + timeout_s
        next_log = time.monotonic()  # first terminal + Telegram tick immediately

        while True:
            now = time.monotonic()
            if now >= deadline:
                break

            otp = self._poll_once()
            if otp:
                self._write_live_status(f"OTP received: {otp[:2]}****")
                return otp

            if now >= next_log:
                if self._otp_wait_deadline is not None:
                    left = max(0, int(self._otp_wait_deadline - now))
                else:
                    left = max(0, int(deadline - now))
                msg = f"still waiting — send 6-digit OTP to bot ({left}s left)"
                log.info("otp_watcher: %s", msg)
                _terminal_ping(msg)
                self._write_live_status(f"waiting for 6-digit OTP ({left}s left)")
                if telegram_nudge and (
                    now - self._last_telegram_nudge >= telegram_nudge_interval_s
                ):
                    sent = send_otp_nudge(
                        f"Mahika: OTP chahiye — sirf 6 digit bhejo (~{left}s login wait)."
                    )
                    if sent:
                        log.info("otp_watcher: Telegram reminder sent")
                    self._last_telegram_nudge = now
                next_log = now + log_every_s

            time.sleep(poll_s)
        self._write_live_status("OTP wait timed out")
        return None

    def _poll_once(self) -> str | None:
        with _telegram_poll_lock():
            return self._poll_once_unlocked()

    def _poll_once_unlocked(self) -> str | None:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
        params: dict[str, int | str] = {"timeout": 0}
        if self._offset:
            params["offset"] = self._offset

        try:
            resp = httpx.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("otp_watcher: getUpdates failed: %s", exc)
            return None

        for item in data.get("result") or []:
            update_id = int(item.get("update_id", 0))
            self._offset = update_id + 1
            _save_offset(self._offset)

            msg = item.get("message") or item.get("edited_message") or {}
            chat = msg.get("chat") or {}
            chat_id = _normalize_chat_id(chat.get("id", ""))
            if chat_id != self._expected_chat:
                log.warning(
                    "otp_watcher: ignored message from chat %s (expected …%s) — "
                    "run: python -m mahika.cli telegram-chatid",
                    chat_id,
                    self._expected_chat[-4:],
                )
                continue

            ts = msg.get("date")
            if ts and self._started_at:
                msg_at = datetime.fromtimestamp(int(ts), tz=UTC)
                if msg_at < self._started_at:
                    log.debug(
                        "otp_watcher: skipped old message at %s (before wait window)",
                        msg_at.isoformat(),
                    )
                    continue

            text = (msg.get("text") or msg.get("caption") or "").strip()
            if not text:
                log.info("otp_watcher: message without text (photo/sticker?) — ignored")
                continue

            otp = extract_otp(text)
            if not otp:
                log.info(
                    "otp_watcher: no 6-digit code in message %r — send only OTP digits",
                    text[:40],
                )
                continue
            if otp in self._used:
                log.info("otp_watcher: duplicate OTP %s ignored — send fresh code", otp)
                continue

            self._used.add(otp)
            log.info("otp_watcher: OTP %s received via Telegram", otp)
            return otp
        return None
