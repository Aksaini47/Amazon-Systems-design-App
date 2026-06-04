"""APScheduler wiring — the Mahika daemon's orchestration spine.

Starts a BlockingScheduler with the polling cadence from
`mahika_capture_specs.md §11`:

    Heartbeat ping              every 60s
    Refund event watcher        every 12 hours
    Returns scanner             every 4 hours
    Filed-claim status check    every 12 hours    (Phase 4.5 — placeholder)
    Weekly audit + Insights     Sunday 23:00 IST
    Mode/heartbeat health check every 5 minutes

Every task is wrapped in `_protected()`:
    1. Skip if not the active runner (heartbeat dead → another machine took over)
    2. Skip if MAHIKA_MODE == 'paused'
    3. In 'shadow' / 'manual' modes, still polling runs — only side-effects on
       Seller Central are gated (Phase 5). Phase 4 tasks always observe.
    4. Catch + audit + alert on exceptions; never let one task crash the daemon

Run via:
    python -m mahika.cli start            # default — blocks until SIGINT
    python -m mahika.cli start --once     # run all tasks once + exit (testing)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from mahika.config import settings
from mahika.playwright import safe_t_filer, status_checker
from mahika.runner.heartbeat import HeartbeatService, am_i_active, claim_active
from mahika.services import insights, refund_watcher, returns_scanner
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import AuditFailure, audit

log = logging.getLogger(__name__)


# ─── Task wrapper ─────────────────────────────────────────────────────────


def _protected(name: str, fn: Callable[[], dict]) -> Callable[[], None]:
    """Wrap a polling function with heartbeat/mode guards + error handling."""

    def wrapper() -> None:
        # Mode gate
        if settings.mode == "paused":
            log.debug("scheduler: skipping %s — Mahika is paused", name)
            return

        # Active-runner gate (only the machine with the NVMe + heartbeat acts)
        if not am_i_active():
            log.debug("scheduler: skipping %s — not the active runner", name)
            return

        log.info("scheduler: running task %s", name)
        try:
            result = fn()
            log.info("scheduler: %s completed: %s", name, result)
        except AuditFailure as exc:
            # The audit log itself is broken — bail loud and skip downstream work.
            log.critical("scheduler: %s failed to audit (%s) — HARD STOP", name, exc)
            alert(
                Priority.CRITICAL,
                title="Audit log unreachable",
                body=f"Task {name} could not write to audit_log. Mahika cannot "
                "proceed un-audited. Investigate Postgres.",
                key="hard_stop:audit_failure",
            )
        except Exception as exc:
            log.exception("scheduler: %s crashed", name)
            try:
                audit(
                    "task.crashed",
                    actor=f"mahika.{name}",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            except AuditFailure:
                pass
            alert(
                Priority.HIGH,
                title=f"Task crashed: {name}",
                body=f"{type(exc).__name__}: {exc}",
                key=f"task_crash:{name}",
            )

    return wrapper


# ─── Phase 5 task wrappers ────────────────────────────────────────────────


def filed_claim_status_check() -> dict:
    """Phase 5 status checker — polls in-flight claims on Seller Central."""
    return status_checker.check_filed_claims()


def file_queued_claims() -> dict:
    """Phase 5 SAFE-T filer — drains the claim queue (up to 5 per tick).

    Returns a structured summary the audit_log can latch onto.
    """
    results = safe_t_filer.file_queued_batch(max_claims=5)
    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)
    return {
        "attempted": len(results),
        "success": success_count,
        "failed": fail_count,
        "mode": settings.mode,
    }


# ─── Builder ──────────────────────────────────────────────────────────────


def build_scheduler() -> BlockingScheduler:
    """Create + populate the scheduler. Caller starts it (or run_once())."""
    sched = BlockingScheduler(timezone="UTC")

    # Refund event watcher — every 12 hours (spec §11)
    sched.add_job(
        _protected("refund_watcher", refund_watcher.run_one_poll),
        IntervalTrigger(hours=12),
        id="refund_watcher",
        name="SP-API refund event poll",
        replace_existing=True,
        next_run_time=datetime.now(UTC),  # run immediately on boot
    )

    # Returns scanner — every 4 hours
    sched.add_job(
        _protected("returns_scanner", returns_scanner.run_one_poll),
        IntervalTrigger(hours=4),
        id="returns_scanner",
        name="SP-API returns initiation poll",
        replace_existing=True,
    )

    # Filed-claim status check — every 12 hours (Phase 5)
    sched.add_job(
        _protected("claim_status_check", filed_claim_status_check),
        IntervalTrigger(hours=12),
        id="claim_status_check",
        name="Seller Central claim status check (Phase 5)",
        replace_existing=True,
    )

    # File queued SAFE-T claims — every 30 minutes (Phase 5)
    # Tight cadence so newly-queued claims hit Seller Central fast — but
    # the queue is naturally rate-limited (5 per tick + max attempt backoff).
    sched.add_job(
        _protected("file_queued_claims", file_queued_claims),
        IntervalTrigger(minutes=30),
        id="file_queued_claims",
        name="SAFE-T queued-claim filer (Phase 5)",
        replace_existing=True,
    )

    # Weekly audit + Insights — Sunday 23:00 UTC (close to 11 PM Mumbai per spec §11)
    sched.add_job(
        _protected("insights_weekly", insights.run_weekly_audit),
        CronTrigger(day_of_week="sun", hour=23, minute=0),
        id="insights_weekly",
        name="Weekly Insights Engine audit",
        replace_existing=True,
    )

    # Heartbeat protection — every 60s (matches HeartbeatService.refresh_interval)
    # The HeartbeatService below also writes its own heartbeat in a daemon
    # thread — this APScheduler job is a belt-and-braces ping that also
    # surfaces heartbeat drops in the audit log.
    sched.add_job(
        _protected("heartbeat_keepalive", lambda: {"claimed": claim_active(notes="scheduler keepalive")}),
        IntervalTrigger(seconds=60),
        id="heartbeat_keepalive",
        name="Active-runner heartbeat",
        replace_existing=True,
    )

    return sched


# ─── Lifecycle ────────────────────────────────────────────────────────────


_active_heartbeat: HeartbeatService | None = None


def _claim_runner_lease() -> bool:
    """Acquire the active-runner role at startup. Returns True on success."""
    claimed = claim_active(notes="scheduler boot")
    if not claimed:
        alert(
            Priority.HIGH,
            title="Another runner is active",
            body=(
                "Mahika tried to start on this machine but another runner "
                "already holds the active heartbeat. This instance will not "
                "schedule any tasks. Either stop the other runner or move "
                "the NVMe before retrying."
            ),
            key="hard_stop:runner_conflict",
        )
        return False
    return True


def run_forever() -> int:
    """Start the daemon and block until SIGINT/SIGTERM."""
    global _active_heartbeat
    if not _claim_runner_lease():
        return 1

    audit(
        "scheduler.started",
        actor="mahika.scheduler",
        payload={
            "mode": settings.mode,
            "runner_id": settings.runner_id,
        },
    )

    # HeartbeatService writes heartbeat every 60s from a daemon thread —
    # protects against scheduler hangs (the APScheduler ping wouldn't fire
    # if the scheduler loop is wedged).
    _active_heartbeat = HeartbeatService(notes="scheduler runtime")
    _active_heartbeat.start()

    sched = build_scheduler()
    try:
        log.info(
            "Mahika scheduler online — runner=%s mode=%s",
            settings.runner_id,
            settings.mode,
        )
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler: shutdown signal received")
    finally:
        if _active_heartbeat is not None:
            _active_heartbeat.stop()
        try:
            audit("scheduler.stopped", actor="mahika.scheduler")
        except AuditFailure:
            pass
    return 0


def run_once() -> dict[str, dict]:
    """Run every task exactly once, then exit. Useful for smoke testing.

    Skips heartbeat keepalive (it's run continuously, not on-demand). Order
    matches typical real-time flow: returns first (so order state moves
    captured→pending_refund), then refund watcher (pending_refund→claim_queued),
    then insights (read-only).
    """
    if not _claim_runner_lease():
        return {}
    results: dict[str, dict] = {}
    for name, fn in (
        ("returns_scanner", returns_scanner.run_one_poll),
        ("refund_watcher", refund_watcher.run_one_poll),
        ("file_queued_claims", file_queued_claims),
        ("claim_status_check", filed_claim_status_check),
        ("insights_weekly", insights.run_weekly_audit),
    ):
        try:
            results[name] = fn()
        except Exception as exc:
            results[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return results
