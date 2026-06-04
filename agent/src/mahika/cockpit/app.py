"""FastAPI app + routes for the Mahika cockpit.

One-file structure on purpose — the cockpit is intentionally small. Each
route is short, Jinja-rendered, and queries Postgres for read-only data
(the only write path is suggestion approve/reject).

Run via:
    python -m mahika.cli cockpit
or:
    uvicorn mahika.cockpit.app:app --port 8765 --host 127.0.0.1
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from mahika.cockpit.auth import (
    SESSION_COOKIE,
    check_token,
    issue_session_cookie,
    require_session,
    verify_session_cookie,
)
from mahika.config import settings
from mahika.db.connection import get_session
from mahika.services.claim_queue import SAFE_T_WINDOW_DAYS

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ─── Common context injected into every render ───────────────────────────


def _ctx(request: Request, **kwargs: Any) -> dict[str, Any]:
    ctx = {
        "request": request,
        "runner_id": settings.runner_id,
        "mode": settings.mode,
        "active": kwargs.pop("active", ""),
    }
    ctx.update(kwargs)
    return ctx


# ─── Date formatting helpers (Jinja can't format datetimes pretty) ──────


def _fmt_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_short(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%m-%d %H:%M")


# ─── State → urgency pill mapping ────────────────────────────────────────


_STATE_PILLS: dict[str, str] = {
    "captured": "info",
    "pending_refund": "caution",
    "claim_queued": "info",
    "claim_filed": "info",
    "claim_under_review": "info",
    "claim_info_requested": "warn",
    "claim_approved": "good",
    "claim_rejected": "warn",
    "claim_appealed": "caution",
    "claim_closed": "good",
    "claim_ineligible": "muted",
}


def _state_pill(state: str | None) -> str:
    return _STATE_PILLS.get(state or "", "muted")


# ─── App ─────────────────────────────────────────────────────────────────


app = FastAPI(
    title="Mahika cockpit",
    description="Project Alpha solo-operator triage dashboard.",
    docs_url=None,            # no swagger — single-user local UI doesn't need it
    redoc_url=None,
    openapi_url=None,
)


# ─── Login / logout ──────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    # If already logged in, bounce to dashboard
    if verify_session_cookie(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)  # type: ignore[return-value]
    return templates.TemplateResponse(request, "login.html", _ctx(request, active="login"))


@app.post("/login")
async def login_submit(request: Request, token: str = Form(...)) -> Any:
    if not check_token(token):
        log.warning("cockpit: failed login attempt")
        return templates.TemplateResponse(
            request,
            "login.html",
            _ctx(request, active="login", error="Token mismatch — check MAHIKA_COCKPIT_TOKEN in .env"),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    resp = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        SESSION_COOKIE,
        issue_session_cookie(),
        httponly=True,
        samesite="strict",
        secure=False,   # cockpit binds 127.0.0.1 — no HTTPS needed for local
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return resp


@app.get("/logout")
async def logout() -> RedirectResponse:
    resp = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ─── Health (no auth) ────────────────────────────────────────────────────


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok", "runner_id": settings.runner_id, "mode": settings.mode}


# ─── Dashboard ───────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, _: None = Depends(require_session)
) -> HTMLResponse:
    with get_session() as s:
        state_counts = {
            row[0]: int(row[1])
            for row in s.execute(text("SELECT state::text, count(*) FROM orders GROUP BY state")).all()
        }
        in_flight = s.execute(
            text(
                "SELECT count(*) FROM orders WHERE state IN "
                "('claim_filed','claim_under_review','claim_info_requested','claim_appealed')"
            )
        ).scalar() or 0
        worklist_rows = s.execute(
            text(
                """
                SELECT order_id, state::text, verdict::text, refund_processed_at, captured_at
                FROM orders
                WHERE state IN ('captured','pending_refund','claim_queued','claim_info_requested','claim_rejected')
                ORDER BY refund_processed_at NULLS LAST, captured_at ASC
                LIMIT 25
                """
            )
        ).all()
        recent_audit = s.execute(
            text(
                """
                SELECT event_at, actor, event_type, order_id
                FROM audit_log ORDER BY event_at DESC LIMIT 10
                """
            )
        ).all()
        heartbeat_row = s.execute(
            text(
                "SELECT runner_id, last_seen_at FROM runner_heartbeat "
                "ORDER BY last_seen_at DESC LIMIT 1"
            )
        ).first()

    now = datetime.now(UTC)
    worklist = []
    for order_id, state, verdict, refund_processed_at, captured_at in worklist_rows:
        days_left: int | None = None
        urgency_class = "info"
        urgency_label = "monitor"
        if state in ("claim_queued", "claim_filed", "claim_info_requested", "claim_rejected") and refund_processed_at:
            deadline = refund_processed_at + timedelta(days=SAFE_T_WINDOW_DAYS)
            days_left = (deadline - now).days
            if days_left <= 3:
                urgency_class = "warn"
                urgency_label = f"FILE TODAY ({days_left}d left)"
            elif days_left <= 7:
                urgency_class = "caution"
                urgency_label = f"file soon ({days_left}d left)"
        elif state == "pending_refund" and captured_at:
            age_days = (now - captured_at).days
            if age_days >= 7:
                urgency_class = "caution"
                urgency_label = f"refund pending {age_days}d"
            elif age_days >= 14:
                urgency_class = "warn"
                urgency_label = f"refund pending {age_days}d — chase Amazon"

        worklist.append({
            "order_id": order_id,
            "state": state,
            "verdict": verdict,
            "refund_processed_at_str": _fmt_short(refund_processed_at),
            "days_left": days_left,
            "urgency_class": urgency_class,
            "urgency_label": urgency_label,
            "state_pill": _state_pill(state),
        })

    heartbeat = None
    if heartbeat_row is not None:
        runner_id, last_seen = heartbeat_row
        stale = last_seen is None or (now - last_seen) > timedelta(minutes=5)
        heartbeat = {
            "runner_id": runner_id,
            "last_seen_str": _fmt_dt(last_seen),
            "stale": stale,
        }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(
            request,
            active="dashboard",
            states=state_counts,
            in_flight_count=int(in_flight),
            worklist=worklist,
            recent_audit=[
                {
                    "event_at_str": _fmt_dt(r[0]),
                    "actor": r[1],
                    "event_type": r[2],
                    "order_id": r[3],
                }
                for r in recent_audit
            ],
            heartbeat=heartbeat,
        ),
    )


# ─── Orders ──────────────────────────────────────────────────────────────


_ORDER_STATES = [
    "captured", "pending_refund", "claim_queued", "claim_filed",
    "claim_under_review", "claim_info_requested",
    "claim_approved", "claim_rejected", "claim_appealed",
    "claim_closed", "claim_ineligible",
]
_VERDICTS = ["ok", "damaged", "different", "damaged_different"]


@app.get("/orders", response_class=HTMLResponse)
async def orders_list(
    request: Request,
    _: None = Depends(require_session),
    state: str | None = Query(default=None),
    verdict: str | None = Query(default=None),
    limit: int = Query(default=100, ge=10, le=500),
) -> HTMLResponse:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if state:
        clauses.append("state = CAST(:state AS order_state)")
        params["state"] = state
    if verdict:
        clauses.append("verdict = CAST(:verdict AS qc_verdict)")
        params["verdict"] = verdict
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_session() as s:
        rows = s.execute(
            text(
                f"""
                SELECT order_id, state::text, verdict::text, captured_at,
                       refund_processed_at, refund_amount_paise, updated_at
                FROM orders
                {where}
                ORDER BY captured_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).all()
        total = s.execute(
            text(f"SELECT count(*) FROM orders {where}"),
            {k: v for k, v in params.items() if k != "limit"},
        ).scalar() or 0

    orders = []
    for r in rows:
        orders.append({
            "order_id": r[0],
            "state": r[1],
            "verdict": r[2],
            "captured_at_str": _fmt_short(r[3]),
            "refund_processed_at_str": _fmt_short(r[4]),
            "refund_amount_paise": r[5],
            "updated_at_str": _fmt_short(r[6]),
            "state_pill": _state_pill(r[1]),
        })

    return templates.TemplateResponse(
        request,
        "orders.html",
        _ctx(
            request,
            active="orders",
            orders=orders,
            total=int(total),
            state=state,
            verdict=verdict,
            limit=limit,
            all_states=_ORDER_STATES,
            all_verdicts=_VERDICTS,
        ),
    )


# ─── Claims ──────────────────────────────────────────────────────────────


@app.get("/claims", response_class=HTMLResponse)
async def claims_page(
    request: Request, _: None = Depends(require_session)
) -> HTMLResponse:
    with get_session() as s:
        depth = s.execute(text("SELECT count(*) FROM claims WHERE filed_at IS NULL")).scalar() or 0
        in_flight = s.execute(
            text(
                "SELECT count(*) FROM orders WHERE state IN "
                "('claim_filed','claim_under_review','claim_info_requested','claim_appealed')"
            )
        ).scalar() or 0
        closed = s.execute(
            text("SELECT count(*) FROM orders WHERE state = 'claim_closed'")
        ).scalar() or 0

        queued = s.execute(
            text(
                """
                SELECT order_id, template_version, attempt_count, queued_at, last_error
                FROM claims
                WHERE filed_at IS NULL
                ORDER BY attempt_count ASC, queued_at ASC
                LIMIT 50
                """
            )
        ).all()
        filed = s.execute(
            text(
                """
                SELECT c.order_id, c.amazon_claim_id, c.filed_at, o.state::text
                FROM claims c
                LEFT JOIN orders o ON o.order_id = c.order_id
                WHERE c.filed_at IS NOT NULL
                ORDER BY c.filed_at DESC
                LIMIT 25
                """
            )
        ).all()

    return templates.TemplateResponse(
        request,
        "claims.html",
        _ctx(
            request,
            active="claims",
            depth=int(depth),
            in_flight=int(in_flight),
            closed=int(closed),
            queued=[
                {
                    "order_id": r[0],
                    "template_version": r[1],
                    "attempt_count": r[2],
                    "queued_at_str": _fmt_short(r[3]),
                    "last_error": r[4],
                }
                for r in queued
            ],
            filed=[
                {
                    "order_id": r[0],
                    "amazon_claim_id": r[1],
                    "filed_at_str": _fmt_short(r[2]),
                    "state": r[3] or "—",
                    "state_pill": _state_pill(r[3]),
                }
                for r in filed
            ],
        ),
    )


# ─── Audit log ───────────────────────────────────────────────────────────


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    _: None = Depends(require_session),
    event_type: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=20, le=1000),
) -> HTMLResponse:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if event_type:
        clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if order_id:
        clauses.append("order_id = :order_id")
        params["order_id"] = order_id
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_session() as s:
        rows = s.execute(
            text(
                f"""
                SELECT event_at, actor, event_type, order_id,
                       state_before::text, state_after::text, reason
                FROM audit_log
                {where}
                ORDER BY event_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).all()

    return templates.TemplateResponse(
        request,
        "audit.html",
        _ctx(
            request,
            active="audit",
            event_type=event_type,
            order_id=order_id,
            limit=limit,
            rows=[
                {
                    "event_at_str": _fmt_dt(r[0]),
                    "actor": r[1],
                    "event_type": r[2],
                    "order_id": r[3],
                    "state_before": r[4],
                    "state_after": r[5],
                    "reason": r[6],
                }
                for r in rows
            ],
        ),
    )


# ─── Insights + suggestion approval ──────────────────────────────────────


@app.get("/insights", response_class=HTMLResponse)
async def insights_page(
    request: Request, _: None = Depends(require_session)
) -> HTMLResponse:
    with get_session() as s:
        pending = s.execute(
            text(
                "SELECT id::text, title, body, rationale, suggested_at "
                "FROM suggestions WHERE status = 'pending' ORDER BY suggested_at DESC"
            )
        ).all()
        decided = s.execute(
            text(
                """
                SELECT title, status, decided_at, decided_by, rejection_reason
                FROM suggestions WHERE status IN ('approved','rejected','implemented')
                ORDER BY decided_at DESC NULLS LAST LIMIT 20
                """
            )
        ).all()
        insights = s.execute(
            text(
                """
                SELECT generated_at, period_start, period_end, pattern_type,
                       metric_label, metric_value, sample_size
                FROM insights ORDER BY generated_at DESC LIMIT 40
                """
            )
        ).all()

    return templates.TemplateResponse(
        request,
        "insights.html",
        _ctx(
            request,
            active="insights",
            pending=[
                {
                    "id": r[0],
                    "title": r[1],
                    "body": r[2],
                    "rationale": r[3],
                    "suggested_at_str": _fmt_short(r[4]),
                }
                for r in pending
            ],
            decided=[
                {
                    "title": r[0],
                    "status": r[1],
                    "decided_at_str": _fmt_short(r[2]),
                    "decided_by": r[3],
                    "rejection_reason": r[4],
                }
                for r in decided
            ],
            insights=[
                {
                    "generated_at_str": _fmt_short(r[0]),
                    "period_start": r[1],
                    "period_end": r[2],
                    "pattern_type": r[3],
                    "metric_label": r[4],
                    "metric_value": float(r[5]) if r[5] is not None else None,
                    "sample_size": r[6],
                }
                for r in insights
            ],
        ),
    )


@app.post("/insights/decide")
async def insights_decide(
    _: None = Depends(require_session),
    suggestion_id: str = Form(...),
    decision: str = Form(...),
) -> RedirectResponse:
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    with get_session() as s:
        s.execute(
            text(
                """
                UPDATE suggestions
                SET status = :status,
                    decided_at = now(),
                    decided_by = 'sir.cockpit'
                WHERE id = :sid AND status = 'pending'
                """
            ),
            {"sid": suggestion_id, "status": decision},
        )
    # Audit the decision — Sir's call must be on the court-grade trail too
    from mahika.utils.audit import audit
    audit(
        "suggestion.decided",
        reason=f"suggestion {suggestion_id[:8]} marked {decision}",
        payload={"suggestion_id": suggestion_id, "decision": decision},
        actor="sir.cockpit",
        human_intervention=True,
    )
    return RedirectResponse("/insights", status_code=status.HTTP_303_SEE_OTHER)
