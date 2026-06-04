"""Court-grade audit logger.

Every state transition + every action Mahika takes goes through `audit()`.
Writes a row to `audit_log` table (append-only, immutable by convention).

Per `mahika.md §9 forbidden behaviors`: Mahika MUST NEVER skip the audit_log
write for any action. If this function raises, the caller should NOT proceed —
log the failure to stderr and halt the operation.

The schema is wide enough to carry arbitrary action context via the `payload`
JSONB column, so most callers just need to supply `event_type` + `order_id`.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mahika.config import settings
from mahika.db.connection import get_session

log = logging.getLogger(__name__)

MAHIKA_VERSION = "0.1.0"  # bumped per release; mirrors pyproject.toml

_INSERT_SQL = text(
    """
    INSERT INTO audit_log (
        event_at, actor, runner_id, mahika_version,
        event_type, order_id,
        state_before, state_after, reason, screenshot_path,
        human_intervention, payload
    ) VALUES (
        :event_at, :actor, :runner_id, :mahika_version,
        :event_type, :order_id,
        CAST(:state_before AS order_state),
        CAST(:state_after  AS order_state),
        :reason, :screenshot_path,
        :human_intervention, CAST(:payload AS jsonb)
    )
    """
)


class AuditFailure(RuntimeError):
    """Raised when the audit_log write itself fails. Caller must halt operation."""


def audit(
    event_type: str,
    *,
    order_id: str | None = None,
    state_before: str | None = None,
    state_after: str | None = None,
    reason: str | None = None,
    screenshot_path: str | None = None,
    payload: dict[str, Any] | None = None,
    actor: str = "mahika.system",
    human_intervention: bool = False,
) -> None:
    """Append one row to audit_log.

    Parameters
    ----------
    event_type:      Short snake_case event name, e.g. 'order.captured',
                     'refund.detected', 'claim.queued', 'claim.filed',
                     'task.completed', 'task.failed', 'hard_stop.triggered'.
    order_id:        Optional. Order this event pertains to.
    state_before:    Optional. Order state before the action (must be a valid
                     `order_state` enum string).
    state_after:     Optional. Order state after the action.
    reason:          Free-text reason / description.
    screenshot_path: Path to a screenshot anchoring this audit entry (used by
                     Phase 5 Playwright steps).
    payload:         Arbitrary JSON-serialisable context. Stored as JSONB.
    actor:           Source attribution. Convention:
                       'mahika.{module}' for automated actions,
                       'sir.cockpit' for manual overrides.
    human_intervention: True when a human had to step in (OTP, manual fix).

    Raises
    ------
    AuditFailure when the DB write fails. Caller should treat this as a
    safety hard-stop — better to halt than to act un-audited.
    """
    params = {
        "event_at": datetime.now(UTC),
        "actor": actor,
        "runner_id": settings.runner_id,
        "mahika_version": MAHIKA_VERSION,
        "event_type": event_type,
        "order_id": order_id,
        "state_before": state_before,
        "state_after": state_after,
        "reason": reason,
        "screenshot_path": screenshot_path,
        "human_intervention": human_intervention,
        "payload": json.dumps(payload) if payload is not None else None,
    }
    try:
        with get_session() as sess:
            sess.execute(_INSERT_SQL, params)
    except SQLAlchemyError as exc:
        # Log to stderr too — Sir must see this if Postgres is down.
        print(
            f"!!! AUDIT FAILURE !!! event_type={event_type} order_id={order_id} "
            f"exc={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        log.exception("audit_log write failed for %s", event_type)
        raise AuditFailure(f"Could not write audit_log row: {exc}") from exc


def audit_safe(event_type: str, **kwargs: Any) -> bool:
    """Same as `audit()` but swallows failures.

    Returns True if the audit row was written, False otherwise. Use when the
    audit write itself shouldn't propagate (e.g. inside an exception handler
    that's already going to bubble a different error up). Caller should still
    log the False return value somewhere safe.
    """
    try:
        audit(event_type, **kwargs)
        return True
    except AuditFailure:
        return False
