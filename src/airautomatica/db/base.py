"""Database engine and initialization."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from airautomatica.db.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def _sqlite_url(path: str) -> str:
    """Build SQLite URL for absolute path."""
    p = Path(path).resolve()
    return f"sqlite:///{p}"


def create_db_engine(db_path: str) -> Engine:
    """Create SQLite engine with check_same_thread=False."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        _sqlite_url(db_path), connect_args={"check_same_thread": False}
    )


def enable_wal(engine: Engine) -> None:
    """Execute PRAGMA journal_mode=WAL on first connection."""
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()


def init_db(db_path: str) -> Engine | None:
    """Create engine, enable WAL, run alembic upgrade head. Return engine or None on failure."""
    global _engine
    try:
        _engine = create_db_engine(db_path)
        enable_wal(_engine)

        from alembic import command
        from alembic.config import Config

        # Prefer project root (from __file__) over cwd for systemd/arbitrary launch dir
        _project_root = Path(__file__).resolve().parent.parent.parent.parent
        alembic_ini = _project_root / "alembic.ini"
        if not alembic_ini.exists():
            alembic_ini = Path.cwd() / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", _sqlite_url(db_path))
        command.upgrade(alembic_cfg, "head")

        logger.info("Database initialized at %s", db_path)
        return _engine
    except Exception as e:
        logger.exception("Database init failed: %s", e)
        _engine = None
        return None


def get_engine() -> Engine | None:
    """Return the module-level engine, or None if init failed."""
    return _engine
