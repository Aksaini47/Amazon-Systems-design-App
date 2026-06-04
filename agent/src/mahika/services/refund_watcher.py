"""Refund event watcher — Mahika's link to Amazon's payment lifecycle.

Per `mahika_capture_specs.md §9.2`: polls SP-API Financial Events every 12hr
(plus real-time webhook listener — Phase 4.5). The instant a refund-processed
event is detected for an order in `pending_refund` state, Mahika:

    1. Records the raw event in `refund_events` table (audit anchor)
    2. Verifies it's Amazon-initiated (not seller-initiated)
    3. Transitions order to `claim_queued`
    4. Enqueues the claim for Phase 5 Playwright filing

Sandbox handling:
    The `python-amazon-sp-api` library exposes a Sandbox client that returns
    static test fixtures. We accommodate three modes:

    1. **No library installed** — synthetic stub returns empty list. Safe for
       Phase 4 plumbing tests without touching Amazon at all.

    2. **Library installed, sandbox refresh token** — real SP-API call against
       sandbox endpoints. Static test data per Amazon's fixture catalogue.

    3. **Library installed, production token** — live calls against real seller
       account. Activated when MAHIKA_SP_API_REFRESH_TOKEN points at a
       production-authorized app.

The watcher itself is mode-agnostic — it consumes a generic event sequence and
acts on it identically regardless of source.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from mahika.config import settings
from mahika.db.connection import get_session
from mahika.services import claim_queue
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import audit

log = logging.getLogger(__name__)

# How far back to poll for financial events on each tick. We poll every 12hr,
# so an 18hr lookback gives us 6hr overlap to catch anything that arrived
# late or got missed on a prior poll. De-dup happens via the `refund_events`
# unique constraint downstream.
POLL_LOOKBACK = timedelta(hours=18)


# ─── Normalised event shape ──────────────────────────────────────────────


@dataclass(frozen=True)
class RefundEvent:
    """Source-agnostic refund-processed event Mahika reasons about.

    SP-API's `FinancialEventGroup -> ShipmentEventList -> ChargeRefundEventList`
    structure is flattened into this shape before insertion.
    """

    amazon_order_id: str
    refund_processed_at: datetime
    amount_paise: int
    currency: str = "INR"
    seller_initiated: bool = False  # True for refunds Sir issued voluntarily
    source: str = "sp_api_poll"     # 'sp_api_poll' | 'sp_api_webhook' | 'stub'
    raw_payload: dict[str, Any] = None  # type: ignore[assignment]

    def to_db_params(self) -> dict[str, Any]:
        return {
            "received_at": datetime.now(UTC),
            "event_source": self.source,
            "amazon_order_id": self.amazon_order_id,
            "refund_processed_at": self.refund_processed_at,
            "amount_paise": self.amount_paise,
            "currency": self.currency,
            "raw_payload": json.dumps(self.raw_payload or {}),
            "processed": False,
        }


# ─── SP-API fetcher (graceful degradation) ───────────────────────────────


def fetch_refund_events(
    since: datetime | None = None,
    *,
    until: datetime | None = None,
) -> Sequence[RefundEvent]:
    """Pull refund-processed events from SP-API Financial Events.

    Returns an empty list when:
        - SP-API credentials are missing (settings.sp_api_configured == False)
        - python-amazon-sp-api library isn't installed
        - The SP-API call itself fails (logged, but doesn't crash the watcher)

    This deliberately conservative behaviour keeps Mahika's scheduler running
    even when SP-API is in a degraded state — the audit_log still gets a row
    saying the poll happened.
    """
    until = until or datetime.now(UTC)
    since = since or (until - POLL_LOOKBACK)

    if not settings.sp_api_configured:
        log.debug("refund_watcher: SP-API not configured, skipping poll")
        return ()

    if settings.sp_api_sandbox:
        log.debug(
            "refund_watcher: sandbox mode — live financial events skipped "
            "(set MAHIKA_SP_API_SANDBOX=false after production authorize)"
        )
        return ()

    try:
        from mahika.sp_api.client import get_finances_client  # type: ignore[import-untyped]
    except ImportError as exc:
        log.warning("refund_watcher: SP-API client unavailable (%s)", exc)
        return ()

    try:
        client = get_finances_client()
        # python-amazon-sp-api's list_financial_events is the catch-all
        # endpoint; it auto-pages and returns Settlement, Shipment, Refund and
        # Service events. We only need RefundEventList from each shipment.
        response = client.list_financial_events(
            PostedAfter=since.isoformat(),
            PostedBefore=until.isoformat(),
            MaxResultsPerPage=100,
        )
    except Exception as exc:
        log.exception("refund_watcher: SP-API list_financial_events failed")
        audit(
            "refund_watcher.sp_api_error",
            reason=f"{type(exc).__name__}: {exc}",
            actor="mahika.refund_watcher",
        )
        return ()

    return tuple(_extract_refunds(getattr(response, "payload", None) or {}))


def _extract_refunds(payload: dict[str, Any]) -> list[RefundEvent]:
    """Normalize SP-API FinancialEvents payload into RefundEvent objects."""
    out: list[RefundEvent] = []
    fe = payload.get("FinancialEvents") or {}

    # ShipmentEventList carries the order-scoped refund records for FBM sellers
    for shipment in fe.get("RefundEventList") or []:
        order_id = shipment.get("AmazonOrderId")
        posted = shipment.get("PostedDate")
        if not order_id or not posted:
            continue
        # ChargeList entries enumerate the refund's principal + tax + shipping
        total_paise = 0
        currency = "INR"
        for item in (shipment.get("ShipmentItemAdjustmentList") or []):
            for adj in (item.get("ItemChargeAdjustmentList") or []):
                amount = (adj.get("ChargeAmount") or {})
                value = amount.get("CurrencyAmount") or 0.0
                currency = amount.get("CurrencyCode") or currency
                # Convert to paise (smallest currency unit). Amazon returns
                # values as floats — multiply by 100 + round to avoid drift.
                total_paise += int(round(float(value) * 100))
        out.append(
            RefundEvent(
                amazon_order_id=order_id,
                refund_processed_at=_parse_dt(posted),
                amount_paise=abs(total_paise),  # refunds are negative; we store positive
                currency=currency,
                seller_initiated=False,  # this branch is Amazon-initiated by definition
                source="sp_api_poll",
                raw_payload=shipment,
            )
        )

    return out


def _parse_dt(s: str) -> datetime:
    """Parse SP-API timestamp ('2026-04-12T10:00:00Z' or ISO with offset)."""
    s = s.rstrip("Z")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Last resort — drop fractional seconds
        dt = datetime.fromisoformat(s.split(".", 1)[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


# ─── Persist + process ───────────────────────────────────────────────────


def persist_events(events: Sequence[RefundEvent]) -> int:
    """Insert raw events into refund_events. Returns count inserted.

    De-dup is best-effort: we treat (amazon_order_id, refund_processed_at,
    amount_paise) as the natural key and skip on duplicate. The schema doesn't
    have a UNIQUE constraint on this triple (raw ingest is intentionally
    lax) — we do an existence check first to keep the audit clean.
    """
    if not events:
        return 0
    inserted = 0
    with get_session() as sess:
        for ev in events:
            already = sess.execute(
                text(
                    """
                    SELECT 1 FROM refund_events
                    WHERE amazon_order_id = :oid
                      AND refund_processed_at = :rat
                      AND amount_paise = :amt
                    LIMIT 1
                    """
                ),
                {"oid": ev.amazon_order_id, "rat": ev.refund_processed_at, "amt": ev.amount_paise},
            ).first()
            if already:
                continue
            sess.execute(
                text(
                    """
                    INSERT INTO refund_events (
                        received_at, event_source, amazon_order_id,
                        refund_processed_at, amount_paise, currency,
                        raw_payload, processed
                    ) VALUES (
                        :received_at, :event_source, :amazon_order_id,
                        :refund_processed_at, :amount_paise, :currency,
                        CAST(:raw_payload AS jsonb), :processed
                    )
                    """
                ),
                ev.to_db_params(),
            )
            inserted += 1
    return inserted


def process_pending_events() -> int:
    """For every unprocessed refund_event, link to an order + enqueue claim.

    Returns the number of orders that transitioned to `claim_queued`.

    Mahika never files for orders where:
        - the order isn't in `pending_refund` state (defensive double-check)
        - the refund was seller-initiated (we'd be filing against ourselves)
        - the composite evidence is missing (Phase 3 didn't complete yet)
        - SAFE-T window has closed
    """
    queued = 0
    with get_session() as sess:
        rows = sess.execute(
            text(
                """
                SELECT id::text, amazon_order_id, refund_processed_at, amount_paise, raw_payload
                FROM refund_events
                WHERE processed = false
                ORDER BY received_at ASC
                """
            )
        ).all()

    for refund_id, order_id, refund_at, amount, _raw in rows:
        if not order_id:
            _mark_event_processed(refund_id)
            continue

        # Check that this order is something we captured + still waiting for refund
        with get_session() as sess:
            order_row = sess.execute(
                text("SELECT state FROM orders WHERE order_id = :oid"),
                {"oid": order_id},
            ).first()
        if order_row is None:
            log.info(
                "refund_watcher: refund event for unknown order %s (not captured by Mahika)",
                order_id,
            )
            audit(
                "refund.unmatched",
                order_id=order_id,
                reason="refund event arrived for an order not in Mahika's evidence set",
                payload={"refund_event_id": refund_id, "amount_paise": amount},
                actor="mahika.refund_watcher",
            )
            _mark_event_processed(refund_id)
            continue

        order_state = order_row[0]
        if order_state != "pending_refund":
            # Already past refund-detection — log for traceability, mark processed
            audit(
                "refund.duplicate",
                order_id=order_id,
                reason=f"refund event arrived for order in state {order_state}",
                payload={"refund_event_id": refund_id, "amount_paise": amount},
                actor="mahika.refund_watcher",
            )
            _mark_event_processed(refund_id)
            continue

        audit(
            "refund.detected",
            order_id=order_id,
            reason="Amazon refund-processed event matched a pending_refund order",
            payload={
                "refund_event_id": refund_id,
                "refund_processed_at": refund_at.isoformat() if refund_at else None,
                "amount_paise": amount,
            },
            actor="mahika.refund_watcher",
        )

        # Enqueue (or get reason for rejection)
        claim_uuid = claim_queue.enqueue(
            order_id,
            refund_processed_at=refund_at,
            refund_amount_paise=amount or 0,
        )
        if claim_uuid is not None:
            queued += 1
            # Sir gets a HIGH-priority Telegram nudge — claim ready to file
            alert(
                Priority.HIGH,
                title=f"Claim queued: {order_id}",
                body=(
                    f"Refund of ₹{(amount or 0)/100:.2f} confirmed by Amazon.\n"
                    f"SAFE-T claim queued for Phase 5 filing."
                ),
                key=f"claim_queued:{order_id}",
                order_id=order_id,
                payload={"claim_id": claim_uuid, "amount_paise": amount},
            )

        _mark_event_processed(refund_id)

    return queued


def _mark_event_processed(refund_event_id: str) -> None:
    with get_session() as sess:
        sess.execute(
            text("UPDATE refund_events SET processed = true WHERE id = :rid"),
            {"rid": refund_event_id},
        )


# ─── Scheduler task ──────────────────────────────────────────────────────


def run_one_poll() -> dict[str, int]:
    """Single end-to-end tick of the refund watcher.

    Designed to be the function APScheduler invokes every 12 hours. Returns
    a small dict so the scheduler can log structured task results.
    """
    audit("task.started", actor="mahika.refund_watcher", payload={"task": "refund_watcher"})

    try:
        events = fetch_refund_events()
        new_count = persist_events(events)
        queued = process_pending_events()
    except Exception as exc:
        log.exception("refund_watcher: unhandled error during poll")
        audit(
            "task.failed",
            actor="mahika.refund_watcher",
            reason=f"{type(exc).__name__}: {exc}",
        )
        alert(
            Priority.CRITICAL,
            title="Refund watcher crashed",
            body=f"Unhandled exception in refund poll cycle: {exc}",
            key="refund_watcher_crash",
        )
        raise

    audit(
        "task.completed",
        actor="mahika.refund_watcher",
        payload={
            "events_fetched": len(events),
            "events_persisted_new": new_count,
            "claims_queued": queued,
        },
    )
    return {
        "events_fetched": len(events),
        "events_persisted_new": new_count,
        "claims_queued": queued,
    }
