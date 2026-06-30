"""Database engine and sessions.

Every request gets its own `Session`. Services open a transaction with
`with session.begin():` and keep it as short as they can: no network calls
while a transaction is open (see docs/adr/0002-outbox.md).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from carob.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )
    timeout = settings.db_statement_timeout_ms

    @event.listens_for(engine, "connect")
    def _set_timeouts(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        with dbapi_connection.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(timeout)}")
        dbapi_connection.commit()

    return engine


@lru_cache
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transaction(session: Session) -> Iterator[Session]:
    """Begin a write transaction on a request's session.

    Reads earlier in the request (authentication, ownership checks) open an
    implicit transaction; it is committed first so this block is the only
    one that writes. Loaded objects stay usable (expire_on_commit=False).
    """
    if session.in_transaction():
        session.commit()
    with session.begin():
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """For scripts and the worker: a session with a transaction that commits on success."""
    session = session_factory()()
    try:
        with session.begin():
            yield session
    finally:
        session.close()
