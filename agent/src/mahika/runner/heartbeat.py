"""Runner heartbeat service — only one machine actively runs Mahika at a time.

The model (per `mahika_capture_specs.md §1.3` + `mahika.md §6.2`):
  - Mahika is hardware-agnostic. Any Windows laptop with the NVMe + Oracle
    Cloud access can become the active runner.
  - The "active runner" is whichever machine currently:
      1. Has the 2TB NVMe connected (folder structure detected)
      2. Has a fresh heartbeat row in Postgres `runner_heartbeat`
  - Heartbeat refresh interval: 60 seconds.
  - Grace period for failover: 120 seconds (2x heartbeat). If the active
    runner's heartbeat is stale by > grace period, another machine can
    claim active status.
  - Prevents double-filing: every claim-filing path calls
    [am_i_active()] before submitting to Seller Central.

Threading model:
  [HeartbeatService.start()] launches a daemon thread that refreshes the
  heartbeat every 60s in the background. The main process can call
  [am_i_active()] cheaply (single-row SELECT) before any destructive
  action.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from mahika import __version__ as MAHIKA_VERSION
from mahika.config import settings
from mahika.db.connection import db_engine, get_session

# Tunables. Stale-threshold > interval so a brief network blip doesn't
# cause failover.
HEARTBEAT_INTERVAL_S = 60
HEARTBEAT_STALE_AFTER_S = 120


def claim_active(notes: str = "") -> bool:
    """Mark THIS machine as the active runner.

    Idempotent. If another machine already holds an active heartbeat that
    is NOT stale, this call refuses and returns False — Sir's existing
    runner stays in charge.

    Returns:
        True if this runner now holds active status; False if blocked.
    """
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(seconds=HEARTBEAT_STALE_AFTER_S)
    with get_session() as s:
        # Are any OTHER runners currently active + fresh?
        existing = s.execute(
            text(
                """
                SELECT runner_id, last_seen_at FROM runner_heartbeat
                WHERE runner_id != :me AND is_active = true
                  AND last_seen_at > :cutoff
                """
            ),
            {"me": settings.runner_id, "cutoff": stale_cutoff},
        ).first()
        if existing is not None:
            return False

        # Demote any stale active runners — they crashed or were unplugged.
        s.execute(
            text(
                """
                UPDATE runner_heartbeat
                SET is_active = false,
                    notes = COALESCE(notes, '') || ' [demoted: stale at ' || :now || ']'
                WHERE is_active = true
                  AND runner_id != :me
                  AND last_seen_at <= :cutoff
                """
            ),
            {"me": settings.runner_id, "cutoff": stale_cutoff, "now": now.isoformat()},
        )

        # Upsert ourselves as active.
        s.execute(
            text(
                """
                INSERT INTO runner_heartbeat (runner_id, last_seen_at, mahika_version, is_active, notes)
                VALUES (:rid, :now, :ver, true, :notes)
                ON CONFLICT (runner_id) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    mahika_version = EXCLUDED.mahika_version,
                    is_active = true,
                    notes = EXCLUDED.notes
                """
            ),
            {
                "rid": settings.runner_id,
                "now": now,
                "ver": MAHIKA_VERSION,
                "notes": notes,
            },
        )
    return True


def refresh_heartbeat() -> None:
    """Update last_seen_at for this runner. Call every HEARTBEAT_INTERVAL_S."""
    now = datetime.now(UTC)
    with get_session() as s:
        s.execute(
            text(
                """
                UPDATE runner_heartbeat
                SET last_seen_at = :now, mahika_version = :ver
                WHERE runner_id = :rid
                """
            ),
            {"rid": settings.runner_id, "now": now, "ver": MAHIKA_VERSION},
        )


def release_active() -> None:
    """Mark this runner as inactive (graceful shutdown / NVMe unplug)."""
    with get_session() as s:
        s.execute(
            text(
                """
                UPDATE runner_heartbeat
                SET is_active = false
                WHERE runner_id = :rid
                """
            ),
            {"rid": settings.runner_id},
        )


def am_i_active() -> bool:
    """Cheap check: is THIS machine the current active runner?

    Returns False if another fresh heartbeat owns active status. Every
    destructive action (claim submission, refund event processing, ...)
    should gate on this so two laptops can't both file the same claim.
    """
    stale_cutoff = datetime.now(UTC) - timedelta(seconds=HEARTBEAT_STALE_AFTER_S)
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT runner_id FROM runner_heartbeat
                WHERE is_active = true AND last_seen_at > :cutoff
                ORDER BY last_seen_at DESC LIMIT 1
                """
            ),
            {"cutoff": stale_cutoff},
        ).first()
    return bool(row and row[0] == settings.runner_id)


class HeartbeatService:
    """Background daemon-thread that keeps this runner's heartbeat fresh.

    Usage:
        svc = HeartbeatService()
        svc.start()         # at agent boot
        ...                 # agent runs, claims active periodically
        svc.stop()          # at shutdown
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        claim_active(notes="HeartbeatService.start")
        self._thread = threading.Thread(target=self._loop, daemon=True, name="mahika-heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        release_active()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                refresh_heartbeat()
            except Exception:
                # Heartbeat is best-effort. If the DB is unreachable, the
                # active flag will go stale on its own; another runner can
                # take over after 120s.
                pass
            # Sleep with early wake on stop signal.
            self._stop.wait(HEARTBEAT_INTERVAL_S)
