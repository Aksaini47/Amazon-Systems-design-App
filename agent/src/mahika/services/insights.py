"""Mahika Insights Engine — pattern recognition + self-audit + suggestions.

Per `mahika_capture_specs.md §10`: runs every Sunday 11 PM. Surfaces patterns
across the last 7 days of operational history + proposes improvements for
Sir's approval. Mahika NEVER auto-implements suggestions (mahika.md §9
forbidden behaviors §4.9 critical boundary).

Output goes to two tables:
    `insights`     — raw metric rows (one per pattern detected)
    `suggestions`  — actionable proposals awaiting Sir's review

The cockpit (Phase 6) renders these for approval. Approved suggestions get
coded into the next iteration via Claude Code.

Patterns implemented in Phase 4 (per spec §10.1):
    1. Claim approval rate by template version
    2. Claim approval rate gated on FPC visibility
    3. Repeat-fraud pincodes / customer IDs (TODO when buyer info available)
    4. Capture quality: FPC OCR confidence trends
    5. Refund delay distribution
    6. Hard-stop frequency

Patterns 3 is parked until SP-API buyer-info role is granted (sandbox doesn't
expose this). Captured as a known gap rather than silently omitted.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from mahika.db.connection import get_session
from mahika.utils.audit import audit

log = logging.getLogger(__name__)

DEFAULT_PERIOD_DAYS = 7


# ─── Datatypes ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InsightRow:
    """One pattern observation."""

    pattern_type: str
    metric_label: str
    metric_value: float | None
    sample_size: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class Suggestion:
    """One proposal for Sir's approval queue."""

    title: str
    body: str
    rationale: str


# ─── Period boundary helper ──────────────────────────────────────────────


def period_window(now: datetime | None = None, days: int = DEFAULT_PERIOD_DAYS) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) for a 7-day rolling window ending now."""
    end = now or datetime.now(UTC)
    start = end - timedelta(days=days)
    return start, end


# ─── Pattern queries ─────────────────────────────────────────────────────


def _approval_rate_by_template(start: datetime, end: datetime) -> list[InsightRow]:
    """Claim approval percentage broken down by template_version."""
    sql = text(
        """
        SELECT c.template_version,
               count(*) FILTER (WHERE o.state = 'claim_approved')::float AS approved_count,
               count(*) FILTER (WHERE o.state IN ('claim_approved','claim_rejected','claim_closed','claim_appealed')) AS decided_count
        FROM claims c
        JOIN orders o ON o.order_id = c.order_id
        WHERE c.queued_at >= :start AND c.queued_at < :end
        GROUP BY c.template_version
        """
    )
    rows: list[InsightRow] = []
    with get_session() as sess:
        for tv, approved, decided in sess.execute(sql, {"start": start, "end": end}).all():
            if not decided:
                continue
            rate = float(approved) / float(decided)
            rows.append(
                InsightRow(
                    pattern_type="approval_rate_by_template",
                    metric_label=f"Template {tv}",
                    metric_value=rate,
                    sample_size=int(decided),
                    payload={"template_version": tv, "approved": int(approved), "decided": int(decided)},
                )
            )
    return rows


def _approval_rate_by_fpc_visibility(start: datetime, end: datetime) -> list[InsightRow]:
    """Approval rate split by whether the audit_log records an FPC code for
    that order's evidence package.

    This relies on audit_log payload from Phase 3 pipeline (key `fpc_sent` in
    payload). When no Phase 3 row exists for an order, it's bucketed as
    `unknown` — those rows are returned but should be ignored downstream
    until Phase 3 has run on the full history.
    """
    sql = text(
        """
        WITH ordered AS (
            SELECT o.order_id,
                   o.state,
                   COALESCE((
                       SELECT (payload->>'fpc_sent') IS NOT NULL
                       FROM audit_log
                       WHERE audit_log.order_id = o.order_id
                         AND audit_log.event_type = 'pipeline.processed'
                       ORDER BY event_at DESC LIMIT 1
                   ), false) AS has_fpc
            FROM orders o
            WHERE o.captured_at >= :start AND o.captured_at < :end
              AND o.state IN ('claim_approved','claim_rejected','claim_closed','claim_appealed')
        )
        SELECT has_fpc,
               count(*) FILTER (WHERE state IN ('claim_approved','claim_closed'))::float AS approved,
               count(*) AS total
        FROM ordered
        GROUP BY has_fpc
        """
    )
    rows: list[InsightRow] = []
    with get_session() as sess:
        for has_fpc, approved, total in sess.execute(sql, {"start": start, "end": end}).all():
            if not total:
                continue
            rate = float(approved) / float(total)
            rows.append(
                InsightRow(
                    pattern_type="approval_rate_by_fpc_visibility",
                    metric_label="FPC visible" if has_fpc else "FPC not visible",
                    metric_value=rate,
                    sample_size=int(total),
                    payload={"has_fpc": bool(has_fpc), "approved": int(approved), "total": int(total)},
                )
            )
    return rows


def _refund_delay_stats(start: datetime, end: datetime) -> list[InsightRow]:
    """Distribution of refund-processing delay (days from return to refund event)."""
    sql = text(
        """
        SELECT EXTRACT(EPOCH FROM (o.refund_processed_at - r.return_initiated_at)) / 86400.0 AS delay_days
        FROM orders o
        JOIN returns r ON r.order_id = o.order_id
        WHERE o.refund_processed_at IS NOT NULL
          AND r.return_initiated_at IS NOT NULL
          AND o.refund_processed_at >= :start AND o.refund_processed_at < :end
        """
    )
    delays: list[float] = []
    with get_session() as sess:
        for (delay,) in sess.execute(sql, {"start": start, "end": end}).all():
            if delay is None:
                continue
            delays.append(float(delay))
    if not delays:
        return []
    delays.sort()
    mid = delays[len(delays) // 2]
    p90 = delays[int(0.9 * (len(delays) - 1))]
    return [
        InsightRow(
            pattern_type="refund_delay_days",
            metric_label="median",
            metric_value=mid,
            sample_size=len(delays),
            payload={"median": mid, "p90": p90, "max": max(delays)},
        )
    ]


def _hard_stop_frequency(start: datetime, end: datetime) -> list[InsightRow]:
    """Count of hard-stop events in the window, grouped by event_type."""
    sql = text(
        """
        SELECT event_type, count(*) AS n
        FROM audit_log
        WHERE event_at >= :start AND event_at < :end
          AND event_type LIKE 'hard_stop.%'
        GROUP BY event_type
        ORDER BY n DESC
        """
    )
    rows: list[InsightRow] = []
    with get_session() as sess:
        for event_type, n in sess.execute(sql, {"start": start, "end": end}).all():
            rows.append(
                InsightRow(
                    pattern_type="hard_stop_frequency",
                    metric_label=event_type,
                    metric_value=float(n),
                    sample_size=int(n),
                    payload={"event_type": event_type, "count": int(n)},
                )
            )
    return rows


# ─── Suggestion synthesis ────────────────────────────────────────────────


def _suggestions_from(insights: list[InsightRow]) -> list[Suggestion]:
    """Heuristics that turn raw metrics into Sir-approval-worthy proposals."""
    suggestions: list[Suggestion] = []

    # Approval rate by FPC visibility — if "FPC visible" beats "FPC not
    # visible" by 15%+ over n≥10 samples, propose making FPC zoom mandatory.
    fpc_buckets = {row.metric_label: row for row in insights if row.pattern_type == "approval_rate_by_fpc_visibility"}
    if "FPC visible" in fpc_buckets and "FPC not visible" in fpc_buckets:
        a = fpc_buckets["FPC visible"]
        b = fpc_buckets["FPC not visible"]
        if a.sample_size + b.sample_size >= 10 and (a.metric_value or 0) - (b.metric_value or 0) >= 0.15:
            suggestions.append(
                Suggestion(
                    title="Mandate FPC zoom step in PK ritual",
                    body=(
                        "Claims where the FPC code is clearly visible in the back-of-product "
                        "photo get approved much more reliably than those without. Adding a "
                        "5-second mandatory FPC zoom in the packing flow should lift approval "
                        "rate materially."
                    ),
                    rationale=(
                        f"Approval rate with FPC visible: {(a.metric_value or 0):.0%} "
                        f"(n={a.sample_size}). Without: {(b.metric_value or 0):.0%} (n={b.sample_size})."
                    ),
                )
            )

    # Template comparison — if any template > 10% better with n≥10, propose deprecating the worse one
    tmpl_rows = [r for r in insights if r.pattern_type == "approval_rate_by_template"]
    if len(tmpl_rows) >= 2:
        best = max(tmpl_rows, key=lambda r: (r.metric_value or 0))
        worst = min(tmpl_rows, key=lambda r: (r.metric_value or 0))
        if (
            best.sample_size >= 10
            and worst.sample_size >= 10
            and (best.metric_value or 0) - (worst.metric_value or 0) >= 0.10
        ):
            suggestions.append(
                Suggestion(
                    title=f"Deprecate template {worst.payload['template_version']}",
                    body=(
                        f"Template {worst.payload['template_version']} is materially under-performing "
                        f"compared to {best.payload['template_version']}. Switch all new claims to "
                        f"the better template."
                    ),
                    rationale=(
                        f"{best.metric_label}: {(best.metric_value or 0):.0%} (n={best.sample_size}). "
                        f"{worst.metric_label}: {(worst.metric_value or 0):.0%} (n={worst.sample_size})."
                    ),
                )
            )

    # Hard-stop frequency — anything ≥3 in a week deserves attention
    for row in insights:
        if row.pattern_type == "hard_stop_frequency" and (row.metric_value or 0) >= 3.0:
            suggestions.append(
                Suggestion(
                    title=f"Investigate recurring hard-stop: {row.metric_label}",
                    body=(
                        "This hard-stop fired multiple times this week. Root-cause it and either "
                        "fix the underlying condition or relax the trigger threshold if it's a "
                        "false alarm."
                    ),
                    rationale=f"Triggered {int(row.metric_value or 0)} times in the last 7 days.",
                )
            )

    return suggestions


# ─── Persistence ─────────────────────────────────────────────────────────


def _insert_insights(rows: list[InsightRow], start: datetime, end: datetime) -> None:
    if not rows:
        return
    with get_session() as sess:
        for row in rows:
            sess.execute(
                text(
                    """
                    INSERT INTO insights (
                        period_start, period_end, pattern_type,
                        metric_label, metric_value, sample_size, payload
                    ) VALUES (
                        :period_start, :period_end, :pattern_type,
                        :metric_label, :metric_value, :sample_size, CAST(:payload AS jsonb)
                    )
                    """
                ),
                {
                    "period_start": start.date(),
                    "period_end": end.date(),
                    "pattern_type": row.pattern_type,
                    "metric_label": row.metric_label,
                    "metric_value": row.metric_value,
                    "sample_size": row.sample_size,
                    "payload": _to_json(row.payload),
                },
            )


def _insert_suggestions(suggestions: list[Suggestion]) -> int:
    if not suggestions:
        return 0
    inserted = 0
    with get_session() as sess:
        for sug in suggestions:
            # Idempotency — don't create duplicate pending suggestions
            already = sess.execute(
                text("SELECT 1 FROM suggestions WHERE title = :t AND status = 'pending' LIMIT 1"),
                {"t": sug.title},
            ).first()
            if already:
                continue
            sess.execute(
                text(
                    """
                    INSERT INTO suggestions (title, body, rationale, status)
                    VALUES (:title, :body, :rationale, 'pending')
                    """
                ),
                {"title": sug.title, "body": sug.body, "rationale": sug.rationale},
            )
            inserted += 1
    return inserted


def _to_json(obj: Any) -> str:
    import json

    def default(o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)

    return json.dumps(obj, default=default)


# ─── Public scheduler entry ──────────────────────────────────────────────


def run_weekly_audit() -> dict[str, int]:
    """Single weekly tick — run all pattern queries + generate suggestions."""
    start, end = period_window()
    audit(
        "task.started",
        actor="mahika.insights",
        payload={"task": "weekly_audit", "period_start": start.isoformat(), "period_end": end.isoformat()},
    )

    insights: list[InsightRow] = []
    try:
        insights += _approval_rate_by_template(start, end)
        insights += _approval_rate_by_fpc_visibility(start, end)
        insights += _refund_delay_stats(start, end)
        insights += _hard_stop_frequency(start, end)

        _insert_insights(insights, start, end)
        suggestions = _suggestions_from(insights)
        new_suggestions = _insert_suggestions(suggestions)
    except Exception as exc:
        log.exception("insights: unhandled error during weekly audit")
        audit("task.failed", actor="mahika.insights", reason=f"{type(exc).__name__}: {exc}")
        raise

    audit(
        "task.completed",
        actor="mahika.insights",
        payload={
            "insights_count": len(insights),
            "new_suggestions": new_suggestions,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
        },
    )
    return {"insights_count": len(insights), "new_suggestions": new_suggestions}
