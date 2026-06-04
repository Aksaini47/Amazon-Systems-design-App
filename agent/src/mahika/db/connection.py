"""SQLAlchemy engine + session factory.

One global engine instance per process. Sessions are obtained via the
[get_session] context manager — never construct sessions directly.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from mahika.config import settings

# ─── Engine ──────────────────────────────────────────────────────────────
# pool_pre_ping detects dropped connections (Oracle VM may NAT-timeout the
# pool after idle). pool_recycle bounces the connection every 30min so we
# never hand out a half-broken connection from the pool.
db_engine: Engine = create_engine(
    settings.db_dsn,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    echo=False,  # flip to True for SQL debugging
)

_SessionFactory = sessionmaker(bind=db_engine, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-manager wrapper around SQLAlchemy session.

    Commits on clean exit, rolls back on exception, always closes. Use as:

        with get_session() as s:
            s.execute(text("UPDATE orders SET state=:s WHERE order_id=:o"),
                      {"s": "claim_filed", "o": "407-1234567-1234567"})
    """
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
