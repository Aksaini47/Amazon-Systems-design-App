"""Returns-initiation scanner — Mahika's view into incoming returns.

Per spec §11: poll SP-API `getReturns` every 4 hours. The agent learns about
NEW return-initiation events from Amazon's side, so it can:

    1. Pre-warn Sir via Telegram before the package physically arrives
    2. Cross-reference against the local `orders` table to flag any return
       that *doesn't* have a corresponding capture bundle (mis-sync alarm)
    3. Record return expected-delivery dates so the runner knows when an
       RT bundle is incoming

This watcher only INSERTS into the `returns` table. The actual RT-evidence
capture happens on the mobile app + sync flow — outside Phase 4.

Sandbox handling mirrors `refund_watcher`: missing SP-API library or empty
credentials → empty event sequence, watcher still logs the task.run.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text

from mahika.config import settings
from mahika.db.connection import get_session
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import audit

log = logging.getLogger(__name__)

POLL_LOOKBACK = timedelta(days=7)  # SP-API returns endpoint accepts a window


# ─── Normalised return event ─────────────────────────────────────────────


@dataclass(frozen=True)
class ReturnEvent:
    """One return-initiation entry as Mahika understands it."""

    amazon_order_id: str
    return_reason: str | None
    return_initiated_at: datetime | None
    expected_delivery: datetime | None
    return_carrier: str | None
    return_awb: str | None


# ─── SP-API fetcher ──────────────────────────────────────────────────────


def fetch_returns(since: datetime | None = None) -> Sequence[ReturnEvent]:
    """Pull return events from SP-API. Returns empty tuple on any failure.

    The `python-amazon-sp-api` library doesn't expose a `getReturns` shortcut
    on the high-level client — returns data is available via the Reports API
    (`GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE`). For Phase 4 sandbox we just
    log the poll + return empty; Phase 4.5 plugs in the report request flow.
    """
    if not settings.sp_api_configured:
        log.debug("returns_scanner: SP-API not configured, skipping poll")
        return ()

    if settings.sp_api_sandbox:
        log.debug("returns_scanner: sandbox mode — live returns report skipped")
        return ()

    # Production wiring deferred. Document the intent so future Mahika
    # implementers know exactly where to hook in.
    log.info(
        "returns_scanner: live SP-API Reports API request not wired yet "
        "(Phase 4.5). Returning empty event set for this tick."
    )
    return ()


# ─── Persist + cross-reference ───────────────────────────────────────────


def persist_returns(events: Sequence[ReturnEvent]) -> int:
    """Insert return-initiation rows; skip duplicates by (order_id, awb)."""
    if not events:
        return 0
    inserted = 0
    with get_session() as sess:
        for ev in events:
            # Skip if we already have this return event recorded
            existing = sess.execute(
                text(
                    """
                    SELECT 1 FROM returns
                    WHERE order_id = :oid
                      AND COALESCE(return_awb, '') = COALESCE(:awb, '')
                    LIMIT 1
                    """
                ),
                {"oid": ev.amazon_order_id, "awb": ev.return_awb},
            ).first()
            if existing:
                continue

            # Verify the order is in our orders table (else this is an
            # unmatched return — alarm-worthy because evidence is missing)
            order = sess.execute(
                text("SELECT state FROM orders WHERE order_id = :oid"),
                {"oid": ev.amazon_order_id},
            ).first()
            if order is None:
                audit(
                    "return.unmatched",
                    order_id=ev.amazon_order_id,
                    reason="return-initiation event with no matching order capture",
                    payload={"return_carrier": ev.return_carrier, "awb": ev.return_awb},
                    actor="mahika.returns_scanner",
                )
                alert(
                    Priority.HIGH,
                    title=f"Return with no capture: {ev.amazon_order_id}",
                    body=(
                        "Amazon flagged a return for an order Mahika has no PK "
                        "bundle for. Either evidence wasn't captured at dispatch "
                        "or the order folder didn't sync to the runner. Verify "
                        "before the package physically arrives."
                    ),
                    key=f"return_unmatched:{ev.amazon_order_id}",
                    order_id=ev.amazon_order_id,
                )
                # Still record the return — we want the audit trail
            sess.execute(
                text(
                    """
                    INSERT INTO returns (
                        order_id, return_reason, return_initiated_at,
                        expected_delivery, return_carrier, return_awb
                    ) VALUES (
                        :oid, :reason, :init_at, :expected, :carrier, :awb
                    )
                    """
                ),
                {
                    "oid": ev.amazon_order_id,
                    "reason": ev.return_reason,
                    "init_at": ev.return_initiated_at,
                    "expected": ev.expected_delivery.date() if ev.expected_delivery else None,
                    "carrier": ev.return_carrier,
                    "awb": ev.return_awb,
                },
            )
            inserted += 1
            audit(
                "return.initiated",
                order_id=ev.amazon_order_id,
                reason=f"Amazon-side return event recorded ({ev.return_reason or 'no reason'})",
                payload={
                    "carrier": ev.return_carrier,
                    "awb": ev.return_awb,
                    "expected_delivery": ev.expected_delivery.isoformat() if ev.expected_delivery else None,
                },
                actor="mahika.returns_scanner",
            )
    return inserted


def transition_to_pending_refund() -> int:
    """Move orders from `captured` → `pending_refund` once a return-event lands.

    A captured order is sitting on disk with PK + RT bundles. When Amazon
    confirms the return is initiated (which we discovered via getReturns), we
    move the order to `pending_refund` so the refund watcher knows to wait
    for Amazon to actually process the refund.
    """
    moved = 0
    with get_session() as sess:
        rows = sess.execute(
            text(
                """
                SELECT DISTINCT r.order_id
                FROM returns r
                JOIN orders o ON o.order_id = r.order_id
                WHERE o.state = 'captured'
                  AND o.verdict IN ('damaged', 'different', 'damaged_different')
                """
            )
        ).all()
        for (order_id,) in rows:
            sess.execute(
                text("UPDATE orders SET state = 'pending_refund' WHERE order_id = :oid"),
                {"oid": order_id},
            )
            moved += 1
            audit(
                "order.pending_refund",
                order_id=order_id,
                state_before="captured",
                state_after="pending_refund",
                reason="return initiation confirmed; awaiting Amazon refund event",
                actor="mahika.returns_scanner",
            )
    return moved


# ─── Scheduler task ──────────────────────────────────────────────────────


def run_one_poll() -> dict[str, int]:
    """One tick. Fetch → persist → transition. Idempotent."""
    audit("task.started", actor="mahika.returns_scanner", payload={"task": "returns_scanner"})
    try:
        events = fetch_returns()
        inserted = persist_returns(events)
        moved = transition_to_pending_refund()
    except Exception as exc:
        log.exception("returns_scanner: unhandled error")
        audit("task.failed", actor="mahika.returns_scanner", reason=f"{type(exc).__name__}: {exc}")
        alert(
            Priority.CRITICAL,
            title="Returns scanner crashed",
            body=f"Unhandled exception in returns poll cycle: {exc}",
            key="returns_scanner_crash",
        )
        raise
    audit(
        "task.completed",
        actor="mahika.returns_scanner",
        payload={"events_fetched": len(events), "events_inserted": inserted, "orders_to_pending_refund": moved},
    )
    return {
        "events_fetched": len(events),
        "events_inserted": inserted,
        "orders_to_pending_refund": moved,
    }
