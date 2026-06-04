"""End-to-end Phase 3 orchestrator.

Public entry point:

    from mahika.services.pipeline import process_order
    result = process_order("407-1234567-1234567")

Workflow per `mahika_capture_specs.md §6-§8`:

    1. Read the 4 source images + meta.json from the order folder
    2. Run OCR on PK_back + RT_back → FPC codes
    3. Run 4-layer diff detector → DiffScores
    4. Suggest verdict from scores → VerdictSuggestion
    5. Render single composite → {OrderID}_compare.jpg
    6. Update meta.json with processing artefacts
    7. Write evidence row in Postgres (audit log + downstream queryable state)

The function is idempotent — re-running on the same order overwrites the
composite, updates meta.json's `processed_at`, and upserts the evidence row.

CLI:
    python -m mahika.services.pipeline 407-1234567-1234567

Forbidden behaviors (per mahika.md §9):
    - This module NEVER files a SAFE-T claim (that's Phase 5 Playwright).
    - Suggested verdict is informational — Sir's app captured the authoritative
      human verdict at capture time.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from mahika.config import settings
from mahika.db.connection import get_session
from mahika.services.composite import build_composite
from mahika.services.diff_detector import DiffScores, score_order
from mahika.services.verdict import VerdictSuggestion, suggest_verdict
from mahika.utils.audit import audit_safe


# ─── Filename convention (spec §3.1) ─────────────────────────────────────
def order_dir(order_id: str) -> Path:
    return settings.orders_dir / order_id


def asset_path(order_id: str, suffix: str, ext: str = "jpg") -> Path:
    return order_dir(order_id) / f"{order_id}_{suffix}.{ext}"


def meta_path(order_id: str) -> Path:
    return order_dir(order_id) / f"{order_id}_meta.json"


def composite_path(order_id: str) -> Path:
    return order_dir(order_id) / f"{order_id}_compare.jpg"


# ─── Result dataclass ────────────────────────────────────────────────────


@dataclass
class ProcessingResult:
    """Outcome of `process_order()` — returned to caller + persisted to meta.json."""

    order_id: str
    composite_path: Path
    scores: DiffScores
    suggested: VerdictSuggestion
    human_verdict: str | None = None
    processed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_meta_dict(self) -> dict:
        """Serialise for inclusion in `{OrderID}_meta.json`."""
        return {
            "processed_at": self.processed_at,
            "human_verdict": self.human_verdict,
            "suggested_verdict": self.suggested.verdict.value,
            "suggested_confidence": round(self.suggested.confidence, 3),
            "reasoning": self.suggested.reasoning,
            "scores": {
                "ssim_front": round(self.scores.front.ssim, 4),
                "ssim_back": round(self.scores.back.ssim, 4),
                "ssim_mean": round(self.scores.mean_ssim, 4),
                "orb_ratio_front": round(self.scores.front.orb_match_ratio, 4),
                "orb_ratio_back": round(self.scores.back.orb_match_ratio, 4),
                "histogram_corr_front": round(self.scores.front.histogram_corr, 4),
                "histogram_corr_back": round(self.scores.back.histogram_corr, 4),
                "fpc_match": self.scores.fpc_match,
                "fpc_sent": self.scores.pk_ocr.fpc_code,
                "fpc_received": self.scores.rt_ocr.fpc_code,
                "fpc_ocr_available": self.scores.pk_ocr.available and self.scores.rt_ocr.available,
            },
            "composite_path": str(self.composite_path),
        }


# ─── Public API ──────────────────────────────────────────────────────────


class OrderNotReady(RuntimeError):
    """Order folder doesn't have all 4 source images yet."""


def process_order(order_id: str, *, write_db: bool = True) -> ProcessingResult:
    """Run the full Phase 3 pipeline on `order_id`.

    Parameters
    ----------
    order_id:  Amazon Order ID, e.g. `407-1234567-1234567`. Folder must exist
               at `{storage_root}/orders/{order_id}/`.
    write_db:  When False, skip the Postgres write. Used by smoke tests that
               run without a live DB.

    Raises
    ------
    OrderNotReady     — at least one of the 4 source JPGs is missing.

    Returns
    -------
    ProcessingResult with the composite path + all scores + suggested verdict.
    """
    pk_front = asset_path(order_id, "PK_front")
    pk_back = asset_path(order_id, "PK_back")
    rt_front = asset_path(order_id, "RT_front")
    rt_back = asset_path(order_id, "RT_back")

    missing = [p for p in (pk_front, pk_back, rt_front, rt_back) if not p.exists()]
    if missing:
        raise OrderNotReady(
            f"Order {order_id} is missing {len(missing)} required asset(s): "
            + ", ".join(p.name for p in missing)
        )

    # Load meta (or seed a fresh one)
    meta = _read_meta(order_id)
    human_verdict = meta.get("verdict") or meta.get("human_verdict")

    # Layer 1-4: detect
    scores = score_order(pk_front, pk_back, rt_front, rt_back)
    suggested = suggest_verdict(scores)

    # Render composite
    out_path = composite_path(order_id)
    build_composite(
        order_id=order_id,
        pk_front=pk_front,
        pk_back=pk_back,
        rt_front=rt_front,
        rt_back=rt_back,
        dispatched_at=meta.get("dispatched_at"),
        returned_at=meta.get("returned_at"),
        fpc_sent=scores.pk_ocr.fpc_code,
        fpc_received=scores.rt_ocr.fpc_code,
        suggested=suggested,
        output_path=out_path,
    )

    result = ProcessingResult(
        order_id=order_id,
        composite_path=out_path,
        scores=scores,
        suggested=suggested,
        human_verdict=human_verdict,
    )

    # Update meta.json (idempotent merge)
    meta.update(result.to_meta_dict())
    _write_meta(order_id, meta)

    # Persist to Postgres evidence table
    if write_db:
        _upsert_evidence_row(result)

    # Court-grade audit event — Insights Engine queries audit_log for this
    # event type with `fpc_sent` in payload to compute approval-rate-by-FPC
    # patterns (see services/insights.py _approval_rate_by_fpc_visibility).
    if write_db:
        audit_safe(
            "pipeline.processed",
            order_id=order_id,
            reason=f"verdict suggestion {suggested.verdict.value} (confidence {suggested.confidence:.2f})",
            payload={
                "suggested_verdict": suggested.verdict.value,
                "suggested_confidence": round(suggested.confidence, 4),
                "human_verdict": human_verdict,
                "ssim_mean": round(scores.mean_ssim, 4),
                "ssim_front": round(scores.front.ssim, 4),
                "ssim_back": round(scores.back.ssim, 4),
                "orb_ratio_mean": round(scores.mean_orb_match_ratio, 4),
                "histogram_corr_mean": round(scores.mean_histogram_corr, 4),
                "fpc_sent": scores.pk_ocr.fpc_code,
                "fpc_received": scores.rt_ocr.fpc_code,
                "fpc_match": scores.fpc_match,
                "ocr_available": scores.pk_ocr.available and scores.rt_ocr.available,
                "composite_path": str(out_path),
            },
            actor="mahika.pipeline",
        )

    return result


# ─── meta.json helpers ───────────────────────────────────────────────────


def _read_meta(order_id: str) -> dict:
    p = meta_path(order_id)
    if not p.exists():
        return {"order_id": order_id, "created_at": datetime.now(UTC).isoformat()}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"order_id": order_id, "meta_read_error": True}


def _write_meta(order_id: str, meta: dict) -> None:
    p = meta_path(order_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Postgres persistence ────────────────────────────────────────────────


_UPSERT_SQL = text(
    """
    INSERT INTO evidence (
        order_id, composite_path, ssim_front, ssim_back,
        orb_ratio_front, orb_ratio_back,
        histogram_corr_front, histogram_corr_back,
        fpc_sent, fpc_received, fpc_match,
        suggested_verdict, suggested_confidence,
        reasoning_json, processed_at
    ) VALUES (
        :order_id, :composite_path, :ssim_front, :ssim_back,
        :orb_ratio_front, :orb_ratio_back,
        :histogram_corr_front, :histogram_corr_back,
        :fpc_sent, :fpc_received, :fpc_match,
        :suggested_verdict, :suggested_confidence,
        :reasoning_json, :processed_at
    )
    ON CONFLICT (order_id) DO UPDATE SET
        composite_path        = EXCLUDED.composite_path,
        ssim_front            = EXCLUDED.ssim_front,
        ssim_back             = EXCLUDED.ssim_back,
        orb_ratio_front       = EXCLUDED.orb_ratio_front,
        orb_ratio_back        = EXCLUDED.orb_ratio_back,
        histogram_corr_front  = EXCLUDED.histogram_corr_front,
        histogram_corr_back   = EXCLUDED.histogram_corr_back,
        fpc_sent              = EXCLUDED.fpc_sent,
        fpc_received          = EXCLUDED.fpc_received,
        fpc_match             = EXCLUDED.fpc_match,
        suggested_verdict     = EXCLUDED.suggested_verdict,
        suggested_confidence  = EXCLUDED.suggested_confidence,
        reasoning_json        = EXCLUDED.reasoning_json,
        processed_at          = EXCLUDED.processed_at
    """
)


def _upsert_evidence_row(result: ProcessingResult) -> None:
    """Insert/update the `evidence` row for this order. Silently no-ops if the
    `evidence` table doesn't have the expected columns (Phase 1 schema is
    intentionally narrower — fields will be filled when Phase 4 expands it).

    To avoid coupling Phase 3 to a schema migration we don't ship yet, this
    function catches the SQL error and logs it rather than crashing. Sir will
    see the meta.json side of the writes either way.
    """
    s = result.scores
    params = {
        "order_id": result.order_id,
        "composite_path": str(result.composite_path),
        "ssim_front": s.front.ssim,
        "ssim_back": s.back.ssim,
        "orb_ratio_front": s.front.orb_match_ratio,
        "orb_ratio_back": s.back.orb_match_ratio,
        "histogram_corr_front": s.front.histogram_corr,
        "histogram_corr_back": s.back.histogram_corr,
        "fpc_sent": s.pk_ocr.fpc_code,
        "fpc_received": s.rt_ocr.fpc_code,
        "fpc_match": s.fpc_match,
        "suggested_verdict": result.suggested.verdict.value,
        "suggested_confidence": result.suggested.confidence,
        "reasoning_json": json.dumps(result.suggested.reasoning),
        "processed_at": result.processed_at,
    }
    try:
        with get_session() as sess:
            sess.execute(_UPSERT_SQL, params)
    except Exception as exc:
        # Schema mismatch is expected until Phase 4 schema migration lands.
        # Log via stderr; meta.json is still written successfully.
        print(
            f"Mahika pipeline: DB upsert skipped for {result.order_id} "
            f"({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )


# ─── CLI ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 3 evidence pipeline on a specific order.",
    )
    parser.add_argument("order_id", help="Amazon order ID, e.g. 407-1234567-1234567")
    parser.add_argument("--no-db", action="store_true", help="Skip Postgres write")
    args = parser.parse_args()

    try:
        result = process_order(args.order_id, write_db=not args.no_db)
    except OrderNotReady as exc:
        print(f"Mahika pipeline: {exc}", file=sys.stderr)
        return 2

    print(f"Mahika pipeline: processed {args.order_id}")
    print(f"  Suggested verdict: {result.suggested.verdict.value} "
          f"(confidence {result.suggested.confidence:.0%})")
    if result.human_verdict:
        match = "matches" if result.human_verdict.upper() == result.suggested.verdict.value else "DIFFERS from"
        print(f"  Human verdict:     {result.human_verdict} ({match} suggestion)")
    print(f"  Composite saved:   {result.composite_path}")
    print("  Reasoning:")
    for line in result.suggested.reasoning:
        print(f"    - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
