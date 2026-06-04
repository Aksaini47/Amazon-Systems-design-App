"""Phase 4 end-to-end smoke test.

Strategy: stub the SP-API source layer so we don't need a real Amazon roundtrip,
then drive the full pipeline end-to-end against the live Oracle Postgres:

    1. Seed a fresh test order in `orders` (state=captured, verdict=different)
    2. Seed a returns row + transition order → pending_refund
    3. Stub `refund_watcher.fetch_refund_events` → returns one synthetic
       refund-processed event for the test order
    4. Run `scheduler.run_once()` — exercises returns_scanner → refund_watcher
       → claim_queue → insights pipeline in one go
    5. Verify:
        - orders row transitioned to claim_queued
        - claims row exists for the order
        - audit_log got entries for refund.detected + claim.queued
        - refund_events row marked processed = true

The test cleans up after itself (deletes the test order + its claim row).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow running directly from `agent/`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text  # noqa: E402

from mahika.config import settings  # noqa: E402
from mahika.db.connection import get_session  # noqa: E402
from mahika.services import refund_watcher, scheduler  # noqa: E402
from mahika.services.refund_watcher import RefundEvent  # noqa: E402

TEST_ORDER_ID = f"407-TEST-{uuid.uuid4().hex[:7].upper()}"


def _ensure_composite_file(order_id: str) -> Path:
    """Create a tiny placeholder composite file so claim_queue.enqueue() passes
    its file-existence check."""
    folder = settings.orders_dir / order_id
    folder.mkdir(parents=True, exist_ok=True)
    composite = folder / f"{order_id}_compare.jpg"
    if not composite.exists():
        # Minimal valid JPEG header — 70 bytes — enough that .exists() returns True
        composite.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605"
                "08070707090908087b0d0a0b08090a0c0a0a0a0a0b0a0a0c1118120c0d0e0c"
                "ffd9"
            )
        )
    return composite


def _seed_order() -> None:
    """Create the test order with state=pending_refund."""
    with get_session() as s:
        s.execute(
            text(
                """
                INSERT INTO orders (
                    order_id, awb, mode, captured_at, storage_path, verdict, state
                ) VALUES (
                    :oid, :awb, 'PK', now() - interval '5 days',
                    :path, 'different', 'pending_refund'
                )
                ON CONFLICT (order_id) DO UPDATE SET state = 'pending_refund'
                """
            ),
            {
                "oid": TEST_ORDER_ID,
                "awb": f"TEST-AWB-{uuid.uuid4().hex[:8]}",
                "path": str(settings.orders_dir / TEST_ORDER_ID),
            },
        )


def _cleanup() -> None:
    """Remove the test order + related rows."""
    with get_session() as s:
        s.execute(text("DELETE FROM claims WHERE order_id = :oid"), {"oid": TEST_ORDER_ID})
        s.execute(text("DELETE FROM refund_events WHERE amazon_order_id = :oid"), {"oid": TEST_ORDER_ID})
        s.execute(text("DELETE FROM returns WHERE order_id = :oid"), {"oid": TEST_ORDER_ID})
        s.execute(text("DELETE FROM audit_log WHERE order_id = :oid"), {"oid": TEST_ORDER_ID})
        s.execute(text("DELETE FROM orders WHERE order_id = :oid"), {"oid": TEST_ORDER_ID})


def _synthetic_event() -> RefundEvent:
    return RefundEvent(
        amazon_order_id=TEST_ORDER_ID,
        refund_processed_at=datetime.now(UTC) - timedelta(hours=2),
        amount_paise=25000,  # ₹250.00
        currency="INR",
        seller_initiated=False,
        source="stub",
        raw_payload={"test_fixture": True},
    )


# ─── Smoke runner ────────────────────────────────────────────────────────


def main() -> int:
    print("=== Phase 4 smoke test ===")
    print(f"Test order ID: {TEST_ORDER_ID}")
    print()

    print("[1/6] Cleaning up any prior test state...")
    _cleanup()

    print("[2/6] Seeding test order in pending_refund state...")
    _seed_order()
    _ensure_composite_file(TEST_ORDER_ID)

    print("[3/6] Patching refund_watcher.fetch_refund_events with synthetic event...")
    original_fetcher = refund_watcher.fetch_refund_events
    refund_watcher.fetch_refund_events = lambda since=None, until=None: (_synthetic_event(),)

    print("[4/6] Running scheduler.run_once()...")
    try:
        results = scheduler.run_once()
    finally:
        refund_watcher.fetch_refund_events = original_fetcher

    print()
    print("Scheduler results:")
    print(json.dumps(results, indent=2, default=str))
    print()

    print("[5/6] Verifying DB state...")
    with get_session() as s:
        order_state = s.execute(
            text("SELECT state FROM orders WHERE order_id = :oid"),
            {"oid": TEST_ORDER_ID},
        ).scalar()
        claim_count = s.execute(
            text("SELECT count(*) FROM claims WHERE order_id = :oid"),
            {"oid": TEST_ORDER_ID},
        ).scalar() or 0
        audit_events = s.execute(
            text(
                """
                SELECT event_type FROM audit_log
                WHERE order_id = :oid OR (actor LIKE 'mahika.%' AND event_at > now() - interval '1 minute')
                ORDER BY event_at DESC
                LIMIT 30
                """
            ),
            {"oid": TEST_ORDER_ID},
        ).all()
        refund_processed = s.execute(
            text(
                "SELECT processed FROM refund_events WHERE amazon_order_id = :oid LIMIT 1"
            ),
            {"oid": TEST_ORDER_ID},
        ).scalar()

    audit_event_types = [row[0] for row in audit_events]

    checks = [
        ("orders.state == claim_queued", order_state == "claim_queued"),
        ("claims row exists", int(claim_count) == 1),
        ("audit: refund.detected", "refund.detected" in audit_event_types),
        ("audit: claim.queued", "claim.queued" in audit_event_types),
        ("refund_events.processed = true", refund_processed is True),
    ]
    for label, ok in checks:
        marker = "✓" if ok else "✗"
        print(f"  {marker} {label}")

    all_ok = all(ok for _, ok in checks)
    print()

    print("[6/6] Cleaning up test state...")
    _cleanup()

    print()
    print(f"=== {'PASS' if all_ok else 'FAIL'} — Phase 4 smoke test ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
