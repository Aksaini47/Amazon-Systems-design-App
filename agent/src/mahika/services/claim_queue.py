"""Postgres-backed SAFE-T claim queue.

The queue sits between Phase 4 (refund detection) and Phase 5 (Playwright
filing). When a refund event is verified for an order in `pending_refund`
state, the order moves to `claim_queued` and a row is inserted into the
`claims` table.

Phase 5's Playwright worker `pop_next_claim()`s here, attempts to file via
Seller Central, and records the outcome.

Mandatory verifications before queueing (per `mahika.md §7.1`):
    1. Order must be in `pending_refund` state (refund detected but not filed)
    2. Composite evidence file must exist on disk
    3. SAFE-T window must still be open (≤ deadline_days from refund date)

The queue itself is FIFO by `queued_at`, with attempt-count backoff for
retries (filing might fail due to session expiry, slow Seller Central, etc.).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from mahika.config import settings
from mahika.db.connection import get_session
from mahika.utils.audit import audit

log = logging.getLogger(__name__)

# Amazon's SAFE-T window — claim must be filed within this many days of
# refund processing. Conservative default; real value is 60 days per Amazon's
# published SAFE-T policy but treat 50 as our hard cutoff to leave buffer.
SAFE_T_WINDOW_DAYS = 50


@dataclass(frozen=True)
class QueuedClaim:
    """Snapshot of a queued claim ready for filing."""

    claim_id: str          # internal UUID, not Amazon's claim ID
    order_id: str
    composite_path: str
    template_version: str
    queued_at: datetime
    attempt_count: int


# ─── Eligibility helpers ─────────────────────────────────────────────────


def composite_path_for(order_id: str) -> Path:
    """Where Phase 3 wrote the composite JPG."""
    return settings.orders_dir / order_id / f"{order_id}_compare.jpg"


def is_within_safe_t_window(refund_processed_at: datetime) -> bool:
    deadline = refund_processed_at + timedelta(days=SAFE_T_WINDOW_DAYS)
    return datetime.now(UTC) <= deadline


# ─── Queue API ───────────────────────────────────────────────────────────


def enqueue(
    order_id: str,
    *,
    refund_processed_at: datetime,
    refund_amount_paise: int,
    template_version: str = "v1",
) -> str | None:
    """Add an order to the claim queue if all pre-conditions are met.

    Returns the internal claim UUID on success, None on rejection.

    Pre-conditions (per `mahika.md §7.1`):
        - Order is in `pending_refund` state
        - Composite file exists at the canonical path
        - SAFE-T window is still open

    Records the queue action in audit_log either way.
    """
    composite = composite_path_for(order_id)

    # ── Verification gate ──────────────────────────────────────────────
    if not composite.exists():
        audit(
            "claim.queue_rejected",
            order_id=order_id,
            reason="composite evidence missing",
            payload={"composite_path": str(composite)},
            actor="mahika.claim_queue",
        )
        log.warning("claim_queue: composite missing for %s at %s", order_id, composite)
        return None

    if not is_within_safe_t_window(refund_processed_at):
        audit(
            "claim.queue_rejected",
            order_id=order_id,
            reason="SAFE-T window closed",
            payload={
                "refund_processed_at": refund_processed_at.isoformat(),
                "window_days": SAFE_T_WINDOW_DAYS,
            },
            actor="mahika.claim_queue",
        )
        log.warning("claim_queue: SAFE-T window expired for %s", order_id)
        return None

    # ── Idempotent insert ──────────────────────────────────────────────
    with get_session() as sess:
        existing = sess.execute(
            text(
                "SELECT id::text FROM claims "
                "WHERE order_id = :oid AND filed_at IS NULL "
                "ORDER BY queued_at DESC LIMIT 1"
            ),
            {"oid": order_id},
        ).first()
        if existing is not None:
            log.info("claim_queue: %s already queued (id=%s)", order_id, existing[0])
            return existing[0]

        row = sess.execute(
            text(
                """
                INSERT INTO claims (order_id, composite_path, template_version)
                VALUES (:oid, :cp, :tv)
                RETURNING id::text
                """
            ),
            {"oid": order_id, "cp": str(composite), "tv": template_version},
        ).first()

        # Mirror state on the order
        sess.execute(
            text(
                """
                UPDATE orders
                SET state = 'claim_queued',
                    refund_processed_at = :refund_at,
                    refund_amount_paise = :amount
                WHERE order_id = :oid
                """
            ),
            {"oid": order_id, "refund_at": refund_processed_at, "amount": refund_amount_paise},
        )

    claim_uuid = row[0] if row is not None else None

    audit(
        "claim.queued",
        order_id=order_id,
        state_before="pending_refund",
        state_after="claim_queued",
        reason="refund verified + composite present + SAFE-T window open",
        payload={
            "claim_id": claim_uuid,
            "composite_path": str(composite),
            "refund_amount_paise": refund_amount_paise,
            "template_version": template_version,
        },
        actor="mahika.claim_queue",
    )
    log.info("claim_queue: enqueued %s as %s", order_id, claim_uuid)
    return claim_uuid


def pop_next_claim() -> QueuedClaim | None:
    """Return the oldest unfiled claim, or None when the queue is empty.

    Does NOT actually lock or remove the row — Phase 5's Playwright worker
    calls `mark_attempt()` / `mark_filed()` to update state. The natural
    ordering by queued_at + attempt_count keeps the worker grabbing the
    least-recently-attempted item.
    """
    with get_session() as sess:
        row = sess.execute(
            text(
                """
                SELECT id::text, order_id, composite_path, template_version,
                       queued_at, attempt_count
                FROM claims
                WHERE filed_at IS NULL
                ORDER BY attempt_count ASC, queued_at ASC
                LIMIT 1
                """
            )
        ).first()
    if row is None:
        return None
    return QueuedClaim(
        claim_id=row[0],
        order_id=row[1],
        composite_path=row[2] or "",
        template_version=row[3],
        queued_at=row[4],
        attempt_count=row[5],
    )


def mark_attempt(claim_id: str, error: str | None = None) -> None:
    """Increment attempt counter (called by Phase 5 each time it tries)."""
    with get_session() as sess:
        sess.execute(
            text(
                """
                UPDATE claims
                SET attempt_count   = attempt_count + 1,
                    last_attempt_at = now(),
                    last_error      = :err
                WHERE id = :cid
                """
            ),
            {"cid": claim_id, "err": error},
        )
    audit(
        "claim.attempt_recorded",
        payload={"claim_id": claim_id, "error": error},
        actor="mahika.claim_queue",
    )


def mark_filed(
    claim_id: str,
    *,
    amazon_claim_id: str,
    submission_screenshot: str | None = None,
) -> None:
    """Mark a claim as successfully filed."""
    with get_session() as sess:
        sess.execute(
            text(
                """
                UPDATE claims
                SET filed_at = now(),
                    amazon_claim_id = :acid,
                    submission_screenshot = :ss
                WHERE id = :cid
                """
            ),
            {"cid": claim_id, "acid": amazon_claim_id, "ss": submission_screenshot},
        )
        # Mirror to orders
        sess.execute(
            text(
                """
                UPDATE orders o
                SET state          = 'claim_filed',
                    claim_id       = :acid,
                    claim_filed_at = now()
                FROM claims c
                WHERE c.id = :cid AND c.order_id = o.order_id
                """
            ),
            {"cid": claim_id, "acid": amazon_claim_id},
        )
    audit(
        "claim.filed",
        state_before="claim_queued",
        state_after="claim_filed",
        payload={
            "claim_id": claim_id,
            "amazon_claim_id": amazon_claim_id,
            "submission_screenshot": submission_screenshot,
        },
        screenshot_path=submission_screenshot,
        actor="mahika.claim_queue",
    )


# ─── Read-only helpers (cockpit + tests) ─────────────────────────────────


def queue_depth() -> int:
    """How many claims are awaiting filing?"""
    with get_session() as sess:
        result = sess.execute(
            text("SELECT count(*) FROM claims WHERE filed_at IS NULL")
        ).first()
    return int(result[0]) if result else 0


def pending_refund_count() -> int:
    """How many orders are in pending_refund state (waiting for Amazon)?"""
    with get_session() as sess:
        result = sess.execute(
            text("SELECT count(*) FROM orders WHERE state = 'pending_refund'")
        ).first()
    return int(result[0]) if result else 0
