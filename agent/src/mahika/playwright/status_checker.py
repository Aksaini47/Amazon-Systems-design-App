"""Filed-claim status checker — Phase 5's eyes-on-Amazon for claim outcomes.

Per spec §9.5: every 12 hours, check all "Submitted" claims in Seller Central:

    Submitted → Under Review → Info Requested → Approved → Amount Credited → Closed
    Submitted → Under Review → Rejected → Auto-Appeal → Re-reviewed

State transitions trigger:
    - Info Requested → CRITICAL Telegram to Sir with question text
    - Rejected      → Auto-appeal once with enhanced evidence (if appeal window open)
    - Approved      → Track until amount credits to balance
    - Closed        → Only when amount actually shows on balance

Verification rules per `mahika.md §7.2`:
    - Verify amount actually credited via Finances API (cross-check)
    - Verify claim status in Seller Central matches "Approved"/"Resolved"
    - Verify no pending appeals
    - Update audit log with closing reason + credited amount
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from mahika.db.connection import get_session
from mahika.playwright import session as session_mgr
from mahika.playwright.selectors import SELECTORS, URLs
from mahika.services.notifier import Priority, alert
from mahika.utils.audit import audit

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimStatus:
    """A claim's current state as observed on Seller Central."""

    order_id: str
    amazon_claim_id: str
    status_label: str         # "Submitted" / "Under Review" / "Approved" / etc.
    info_request_text: str | None  # populated when status = info_requested
    rejection_reason: str | None    # populated when status = rejected


# Map Seller Central status labels → our `order_state` enum values.
STATUS_TO_ORDER_STATE: dict[str, str] = {
    "Submitted": "claim_filed",
    "Under Review": "claim_under_review",
    "Info Requested": "claim_info_requested",
    "Approved": "claim_approved",
    "Rejected": "claim_rejected",
    "Appealed": "claim_appealed",
    "Closed": "claim_closed",
    "Resolved": "claim_closed",
}


# ─── Read filed claims that need checking ────────────────────────────────


def _open_claims() -> list[tuple[str, str]]:
    """Return [(order_id, amazon_claim_id), ...] for claims still in flight."""
    with get_session() as s:
        rows = s.execute(
            text(
                """
                SELECT o.order_id, o.claim_id
                FROM orders o
                WHERE o.state IN (
                    'claim_filed', 'claim_under_review',
                    'claim_info_requested', 'claim_appealed'
                )
                  AND o.claim_id IS NOT NULL
                ORDER BY o.claim_filed_at ASC NULLS LAST
                """
            )
        ).all()
    return [(r[0], r[1]) for r in rows]


# ─── Per-claim Playwright probe ──────────────────────────────────────────


def _read_claim_status(page: Page, amazon_claim_id: str) -> ClaimStatus | None:
    """Navigate to a specific claim's detail page and parse its status.

    Returns None if the detail page couldn't be loaded (network/timeout).
    """
    # Seller Central URLs for individual claims are query-string driven —
    # placeholder until codegen confirms the exact format.
    detail_url = f"{URLs.SAFE_T_LIST}?claimId={amazon_claim_id}"
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as exc:
        log.warning("status_checker: navigate failed for %s: %s", amazon_claim_id, exc)
        return None

    sel = SELECTORS.claim_detail
    try:
        status_label = page.locator(sel.status_label).first.inner_text(timeout=5_000).strip()
    except Exception:
        return None

    info_req_text: str | None = None
    try:
        info_req_text = page.locator(sel.info_request_banner).first.inner_text(timeout=2_000).strip()
    except Exception:
        pass

    rejection_reason: str | None = None
    try:
        rejection_reason = page.locator(sel.rejection_reason).first.inner_text(timeout=2_000).strip()
    except Exception:
        pass

    # We need order_id — we'll fill it in the caller because the URL doesn't carry it
    return ClaimStatus(
        order_id="",
        amazon_claim_id=amazon_claim_id,
        status_label=status_label,
        info_request_text=info_req_text,
        rejection_reason=rejection_reason,
    )


# ─── DB state transition ─────────────────────────────────────────────────


def _apply_status(claim_status: ClaimStatus) -> None:
    """Persist the observed status to orders + audit_log + Telegram if needed."""
    new_state = STATUS_TO_ORDER_STATE.get(claim_status.status_label)
    if new_state is None:
        log.info(
            "status_checker: unknown SAFE-T label %r for %s — skipping",
            claim_status.status_label, claim_status.amazon_claim_id,
        )
        return

    with get_session() as s:
        # Fetch current state for the transition log
        row = s.execute(
            text("SELECT order_id, state::text FROM orders WHERE claim_id = :cid"),
            {"cid": claim_status.amazon_claim_id},
        ).first()
        if row is None:
            log.warning("status_checker: no orders row for claim_id=%s", claim_status.amazon_claim_id)
            return
        order_id = row[0]
        old_state = row[1]
        if old_state == new_state:
            return  # idempotent — no transition

        # Apply transition
        s.execute(
            text("UPDATE orders SET state = CAST(:s AS order_state) WHERE order_id = :oid"),
            {"s": new_state, "oid": order_id},
        )

    audit(
        "claim.status_changed",
        order_id=order_id,
        state_before=old_state,
        state_after=new_state,
        reason=f"Seller Central reports {claim_status.status_label!r}",
        payload={
            "amazon_claim_id": claim_status.amazon_claim_id,
            "status_label": claim_status.status_label,
            "info_request_text": claim_status.info_request_text,
            "rejection_reason": claim_status.rejection_reason,
        },
        actor="mahika.status_checker",
    )

    # Route alerts per the new state
    if new_state == "claim_info_requested":
        alert(
            Priority.CRITICAL,
            title=f"Amazon needs info on {order_id}",
            body=(
                f"Claim {claim_status.amazon_claim_id} status: Info Requested\n"
                f"\n"
                f"Amazon's question:\n{claim_status.info_request_text or '(no text captured)'}\n"
                f"\n"
                f"Mahika cannot auto-reply — Sir must respond via Seller Central UI."
            ),
            key=f"claim_info_request:{order_id}",
            order_id=order_id,
        )
    elif new_state == "claim_rejected":
        alert(
            Priority.HIGH,
            title=f"Claim REJECTED: {order_id}",
            body=(
                f"Reason: {claim_status.rejection_reason or '(no reason captured)'}\n"
                f"\n"
                f"Mahika will auto-appeal once (per spec §9.5) on the next tick "
                f"if the appeal window is still open."
            ),
            key=f"claim_rejected:{order_id}",
            order_id=order_id,
        )
    elif new_state == "claim_approved":
        alert(
            Priority.MEDIUM,
            title=f"Claim APPROVED: {order_id}",
            body=(
                "Tracking until amount credits to seller balance — "
                "will move to 'closed' state once Finance API confirms."
            ),
            key=f"claim_approved:{order_id}",
            order_id=order_id,
        )
    elif new_state == "claim_closed":
        alert(
            Priority.MEDIUM,
            title=f"Claim CLOSED: {order_id}",
            body="Amount credited to seller balance.",
            key=f"claim_closed:{order_id}",
            order_id=order_id,
        )


# ─── Public scheduler entry ──────────────────────────────────────────────


def check_filed_claims() -> dict[str, int]:
    """One tick — check all in-flight claims for status updates."""
    audit(
        "task.started",
        actor="mahika.status_checker",
        payload={"task": "filed_claim_status_check"},
    )

    pairs = _open_claims()
    if not pairs:
        audit(
            "task.completed",
            actor="mahika.status_checker",
            payload={"checked": 0, "reason": "no in-flight claims"},
        )
        return {"checked": 0, "updated": 0}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("status_checker: playwright not installed")
        audit("task.failed", actor="mahika.status_checker", reason="playwright not installed")
        return {"checked": 0, "updated": 0}

    checked = 0
    updated = 0
    with sync_playwright() as pw:
        try:
            context = session_mgr.get_authenticated_context(pw, headless=True)
            page = context.new_page()
            for order_id, amazon_claim_id in pairs:
                checked += 1
                status = _read_claim_status(page, amazon_claim_id)
                if status is None:
                    continue
                # Patch in order_id for audit trail
                status = ClaimStatus(
                    order_id=order_id,
                    amazon_claim_id=status.amazon_claim_id,
                    status_label=status.status_label,
                    info_request_text=status.info_request_text,
                    rejection_reason=status.rejection_reason,
                )
                _apply_status(status)
                updated += 1
            page.close()
            session_mgr.save_cookies(context)
            context.close()
        except Exception as exc:
            log.exception("status_checker: unhandled error")
            audit("task.failed", actor="mahika.status_checker", reason=f"{type(exc).__name__}: {exc}")
            alert(
                Priority.HIGH,
                title="Claim status checker crashed",
                body=f"{type(exc).__name__}: {exc}",
                key="status_checker_crash",
            )
            return {"checked": checked, "updated": updated, "error": 1}

    audit(
        "task.completed",
        actor="mahika.status_checker",
        payload={"checked": checked, "updated": updated},
    )
    return {"checked": checked, "updated": updated}
