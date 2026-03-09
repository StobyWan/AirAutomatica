"""Database module for SQLite persistence."""

from airautomatica.db.base import create_db_engine, enable_wal, get_engine, init_db
from airautomatica.db.models import (
    Base,
    CommandSent,
    Detection,
    FlightSession,
    SystemEvent,
    TelemetrySample,
)
from airautomatica.db.session import get_session

__all__ = [
    "Base",
    "CommandSent",
    "Detection",
    "FlightSession",
    "SystemEvent",
    "TelemetrySample",
    "create_db_engine",
    "enable_wal",
    "get_engine",
    "get_session",
    "init_db",
]
