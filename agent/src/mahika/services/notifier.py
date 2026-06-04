"""Telegram alert routing — Mahika's primary out-of-band channel to Sir.

Per `mahika_pipeline_protocol.md §6.2 / §6.3`:
    🔴 Critical — Telegram immediate (OTP needed, hard-stops, infra failure)
    🟠 High     — Telegram batched hourly
    🟡 Medium   — Daily summary only (no immediate Telegram)
    ⚪ Low      — Audit log only (never Telegram)

Anti-spam rule: same item key not alerted more than once per hour unless its
priority escalates.

Configuration via .env:
    MAHIKA_TELEGRAM_BOT_TOKEN   — set via @BotFather on Telegram
    MAHIKA_TELEGRAM_CHAT_ID     — Sir's chat ID (one-time via getUpdates)

When credentials are missing, the notifier degrades gracefully: alerts go to
stderr + audit_log only. This is intentional — Phase 4 can be exercised
end-to-end without Telegram set up.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Any

from mahika.config import settings
from mahika.utils.audit import audit_safe

log = logging.getLogger(__name__)


class Priority(IntEnum):
    """Priority levels. Higher value = more urgent. Mirrors audit_log.alert_priority."""

    INFO = 0          # ignored by Telegram, audit only
    LOW = 1           # audit log only
    MEDIUM = 2        # included in daily summary, not pushed
    HIGH = 3          # batched hourly
    CRITICAL = 4      # immediate push, bypass anti-spam if escalating


# ─── Anti-spam state (in-process; ephemeral across restarts on purpose) ──
@dataclass
class _SuppressionState:
    """Records the last alert per (key, priority) pair for anti-spam logic."""

    last_sent_at: dict[tuple[str, Priority], datetime]


_state_lock = threading.Lock()
_state = _SuppressionState(last_sent_at={})

# Anti-spam window — per protocol §6.3, "not more than once per hour for
# the same item unless priority escalates".
ANTI_SPAM_WINDOW = timedelta(hours=1)


# ─── Public API ──────────────────────────────────────────────────────────


def alert(
    priority: Priority,
    title: str,
    body: str,
    *,
    key: str | None = None,
    order_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Route an alert through the appropriate channel(s) for its priority.

    Parameters
    ----------
    priority:  Priority enum value. INFO/LOW go to audit only.
    title:     Single-line title shown in the Telegram preview.
    body:      Multi-line body. Markdown supported (Telegram parses MarkdownV2).
    key:       Stable identifier for anti-spam dedup (e.g. order_id or task
               name). Same key + same priority within 1hr is suppressed.
               If None, no suppression — used for one-shot alerts.
    order_id:  Optional. Recorded in the audit_log row for traceability.
    payload:   Optional. Extra context in audit_log.

    Returns
    -------
    True if an alert was actually pushed (Telegram or stderr), False if
    suppressed by anti-spam.
    """
    # Always write to audit log first (court-grade trail)
    audit_safe(
        "alert.emitted",
        order_id=order_id,
        reason=f"[{priority.name}] {title}",
        payload={
            "priority": priority.name,
            "title": title,
            "body": body,
            "key": key,
            **(payload or {}),
        },
        actor="mahika.notifier",
    )

    # LOW/INFO: stay in audit, don't push anywhere
    if priority <= Priority.LOW:
        return False

    # Anti-spam check
    if key is not None and not _should_send(key, priority):
        log.debug("Alert suppressed by anti-spam: key=%s priority=%s", key, priority.name)
        return False

    # MEDIUM: batched/daily — we just stage to audit_log here. The daily
    # summary task (in insights.py) aggregates these for Sir's morning brief.
    if priority == Priority.MEDIUM:
        if key is not None:
            _mark_sent(key, priority)
        return False  # not pushed, but staged for daily summary

    # HIGH/CRITICAL — actually push
    body_formatted = _format_message(priority, title, body, order_id=order_id)
    pushed = _push_to_telegram(body_formatted)
    if not pushed:
        # Fallback: stderr alert so Sir at least sees it on the runner console.
        print(f"\n[TELEGRAM FALLBACK / {priority.name}] {title}\n{body}\n", file=sys.stderr)

    if key is not None:
        _mark_sent(key, priority)
    return pushed


# ─── Suppression helpers ─────────────────────────────────────────────────


def _should_send(key: str, priority: Priority) -> bool:
    """True if we haven't sent (key, priority) within ANTI_SPAM_WINDOW.

    Per protocol §6.3, priority escalation bypasses the window: if we previously
    sent (key, HIGH) and now have (key, CRITICAL), CRITICAL goes through.
    """
    now = datetime.now(UTC)
    with _state_lock:
        # Find highest priority recently sent for this key
        recent_max: Priority | None = None
        for (existing_key, existing_prio), ts in _state.last_sent_at.items():
            if existing_key != key:
                continue
            if (now - ts) < ANTI_SPAM_WINDOW and (recent_max is None or existing_prio > recent_max):
                recent_max = existing_prio
        if recent_max is None:
            return True
        # Escalation bypasses window
        return priority > recent_max


def _mark_sent(key: str, priority: Priority) -> None:
    with _state_lock:
        _state.last_sent_at[(key, priority)] = datetime.now(UTC)


# ─── Telegram transport (best-effort, never raises) ──────────────────────


_OTP_NUDGE_FILE = settings.storage_root / "sessions" / ".telegram_otp_nudge_last"
OTP_NUDGE_MIN_INTERVAL_S = 60.0


def send_plain_message(text: str) -> bool:
    """Send plain text to Telegram without Markdown escaping. Never raises."""
    if not settings.telegram_configured:
        return False
    try:
        import httpx

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        r = httpx.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": text},
            timeout=15.0,
        )
        if r.status_code == 200:
            return True
        log.error("Telegram plain send HTTP %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as exc:
        log.error("Telegram plain send failed: %s: %s", type(exc).__name__, exc)
        return False


def send_otp_nudge(text: str, *, min_interval_s: float = OTP_NUDGE_MIN_INTERVAL_S) -> bool:
    """OTP reminder — max once per minute across all Mahika processes."""
    if not settings.telegram_configured:
        return False
    now = time.monotonic()
    try:
        _OTP_NUDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _OTP_NUDGE_FILE.exists():
            raw = _OTP_NUDGE_FILE.read_text(encoding="utf-8").strip()
            last = float(raw) if raw else 0.0
            if now - last < min_interval_s:
                log.debug("otp_nudge: suppressed (%.0fs since last)", now - last)
                return False
        _OTP_NUDGE_FILE.write_text(str(now), encoding="utf-8")
    except Exception as exc:
        log.warning("otp_nudge: throttle file failed (%s) — sending anyway", exc)
    return send_plain_message(text)


def _push_to_telegram(text: str) -> bool:
    """Send `text` to Sir's configured Telegram chat. Returns success bool.

    Uses the python-telegram-bot async API but blocks until delivery confirmed
    or times out. Never raises — failures are logged and reported as False.
    """
    if not settings.telegram_configured:
        return False

    try:
        # Lazy import keeps Phase 1–3 boot fast for users without Telegram.
        from telegram import Bot  # type: ignore[import-untyped]
        from telegram.constants import ParseMode  # type: ignore[import-untyped]
    except ImportError:
        log.warning("python-telegram-bot not installed; cannot push alert.")
        return False

    async def _send() -> None:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )

    try:
        asyncio.run(asyncio.wait_for(_send(), timeout=15.0))
        return True
    except Exception as exc:
        log.error("Telegram push failed: %s: %s", type(exc).__name__, exc)
        return False


def _format_message(
    priority: Priority,
    title: str,
    body: str,
    *,
    order_id: str | None = None,
) -> str:
    """Compose MarkdownV2 message with priority emoji + order context."""
    emoji = {
        Priority.CRITICAL: "🔴",
        Priority.HIGH: "🟠",
        Priority.MEDIUM: "🟡",
        Priority.LOW: "⚪",
        Priority.INFO: "ℹ️",
    }[priority]
    # Telegram MarkdownV2 reserves chars; do bare-minimum escape on the title.
    safe_title = _md_escape(title)
    safe_body = _md_escape(body)
    head = f"{emoji} *{safe_title}*"
    parts = [head, "", safe_body]
    if order_id:
        parts.append("")
        parts.append(f"_Order:_ `{_md_escape(order_id)}`")
    parts.append("")
    parts.append(f"_Mahika ❄️_  · runner `{_md_escape(settings.runner_id)}`")
    return "\n".join(parts)


_MD_SPECIAL = set("_*[]()~`>#+-=|{}.!\\")


def _md_escape(s: str) -> str:
    return "".join("\\" + c if c in _MD_SPECIAL else c for c in s)
