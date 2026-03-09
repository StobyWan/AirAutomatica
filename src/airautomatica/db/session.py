"""Database session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from airautomatica.db.base import get_engine


@contextmanager
def get_session() -> Generator[Session | None, None, None]:
    """Context manager yielding a session. Yields None if engine unavailable."""
    engine = get_engine()
    if engine is None:
        yield None
        return
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
