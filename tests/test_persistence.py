"""Tests for SQLite persistence layer."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlalchemy import select

from airautomatica.db.base import create_db_engine, enable_wal, get_engine, init_db
from airautomatica.db.models import SystemEvent, TelemetrySample
from airautomatica.db.session import get_session
from airautomatica.models.state import AircraftState
from airautomatica.services.persistence import PersistenceService, TelemetryLifecycleLogger


def test_db_init_and_wal() -> None:
    """Enable WAL and verify PRAGMA journal_mode returns wal."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.db"
        engine = create_db_engine(str(path))
        enable_wal(engine)
        with engine.connect() as conn:
            from sqlalchemy import text

            r = conn.execute(text("PRAGMA journal_mode"))
            mode = r.scalar()
        assert mode and mode.lower() == "wal"


def test_insert_telemetry_sample() -> None:
    """Init DB, start session, insert telemetry sample, verify row exists."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        assert get_engine() is not None

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        now = datetime.now(timezone.utc)
        state = AircraftState(
            connected=True,
            heartbeat=1,
            mode="GUIDED",
            lat=37.5,
            lon=-122.2,
            rel_alt_m=100.0,
            heading_deg=90.0,
            roll_rad=0.0,
            pitch_rad=0.0,
            yaw_rad=0.0,
            voltage_v=12.5,
            current_a=2.0,
            groundspeed_m_s=10.0,
            airspeed_m_s=12.0,
            timestamp=now,
            telemetry_status="connected",
        )
        persistence.insert_telemetry_sample(session_id, state)

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(TelemetrySample).where(TelemetrySample.session_id == session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].lat == 37.5
            assert rows[0].lon == -122.2
            assert rows[0].rel_alt_m == 100.0
            assert rows[0].telemetry_status == "connected"


def test_insert_telemetry_sample_nan_to_none() -> None:
    """NaN values in AircraftState are stored as None in DB."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        now = datetime.now(timezone.utc)
        state = AircraftState(
            connected=False,
            heartbeat=0,
            mode="UNKNOWN",
            lat=float("nan"),
            lon=float("nan"),
            rel_alt_m=float("nan"),
            heading_deg=float("nan"),
            roll_rad=0.0,
            pitch_rad=0.0,
            yaw_rad=0.0,
            voltage_v=float("nan"),
            current_a=float("nan"),
            groundspeed_m_s=float("nan"),
            airspeed_m_s=float("nan"),
            timestamp=now,
            telemetry_status="disconnected",
        )
        persistence.insert_telemetry_sample(session_id, state)

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(TelemetrySample).where(TelemetrySample.session_id == session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].lat is None
            assert rows[0].lon is None
            assert rows[0].rel_alt_m is None


def test_get_recent_detections_empty_when_no_engine() -> None:
    """get_recent_detections returns [] when DB engine is disabled."""
    with patch("airautomatica.services.persistence.get_engine", return_value=None):
        persistence = PersistenceService()
        assert persistence.get_recent_detections(1) == []


def test_persistence_no_op_when_engine_none() -> None:
    """When get_engine() returns None, insert_telemetry_sample does not raise."""
    with patch("airautomatica.services.persistence.get_engine", return_value=None):
        persistence = PersistenceService()
        now = datetime.now(timezone.utc)
        state = AircraftState(
            connected=True,
            heartbeat=1,
            mode="GUIDED",
            lat=37.0,
            lon=-122.0,
            rel_alt_m=100.0,
            heading_deg=90.0,
            roll_rad=0.0,
            pitch_rad=0.0,
            yaw_rad=0.0,
            voltage_v=12.5,
            current_a=2.0,
            groundspeed_m_s=10.0,
            airspeed_m_s=12.0,
            timestamp=now,
        )
        persistence.insert_telemetry_sample(1, state)


def _make_state(telemetry_status: str, reconnect_count: int = 0, last_disconnect_reason: str | None = None) -> AircraftState:
    """Helper to create AircraftState with given telemetry_status."""
    now = datetime.now(timezone.utc)
    return AircraftState(
        connected=telemetry_status == "connected",
        heartbeat=1 if telemetry_status == "connected" else 0,
        mode="GUIDED" if telemetry_status == "connected" else "UNKNOWN",
        lat=37.0,
        lon=-122.0,
        rel_alt_m=100.0,
        heading_deg=90.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=12.5,
        current_a=2.0,
        groundspeed_m_s=10.0,
        airspeed_m_s=12.0,
        timestamp=now,
        telemetry_status=telemetry_status,
        reconnect_count=reconnect_count,
        last_disconnect_reason=last_disconnect_reason,
    )


def test_lifecycle_logger_logs_on_status_change() -> None:
    """TelemetryLifecycleLogger logs system_event only when telemetry_status changes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        logger = TelemetryLifecycleLogger(persistence, session_id)

        logger.maybe_log_transition(_make_state("starting"))
        logger.maybe_log_transition(_make_state("connecting"))
        logger.maybe_log_transition(_make_state("connected"))
        logger.maybe_log_transition(_make_state("connected"))

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(SystemEvent).where(
                    SystemEvent.session_id == session_id,
                    SystemEvent.event_type == "telemetry_status_transition",
                )
            )
            events = result.scalars().all()
            assert len(events) == 3
            messages = [e.message for e in events]
            assert "initial -> starting" in messages[0]
            assert "starting -> connecting" in messages[1]
            assert "connecting -> connected" in messages[2]


def test_lifecycle_logger_includes_reconnect_metadata() -> None:
    """Lifecycle events include reconnect_count and last_disconnect_reason when relevant."""
    import json

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        logger = TelemetryLifecycleLogger(persistence, session_id)

        logger.maybe_log_transition(_make_state("disconnected"))
        logger.maybe_log_transition(
            _make_state("connected", reconnect_count=2, last_disconnect_reason="Connection refused")
        )

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(SystemEvent).where(
                    SystemEvent.session_id == session_id,
                    SystemEvent.event_type == "telemetry_status_transition",
                ).order_by(SystemEvent.id)
            )
            events = result.scalars().all()
            assert len(events) >= 2
            reconnected = next(e for e in events if "disconnected -> connected" in e.message)
            assert reconnected.metadata_json is not None
            meta = json.loads(reconnected.metadata_json)
            assert meta.get("reconnect_count") == 2
            assert meta.get("last_disconnect_reason") == "Connection refused"


def test_lifecycle_logger_no_duplicate_when_status_unchanged() -> None:
    """No duplicate events when status has not changed."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        logger = TelemetryLifecycleLogger(persistence, session_id)

        for _ in range(5):
            logger.maybe_log_transition(_make_state("connected"))

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(SystemEvent).where(
                    SystemEvent.session_id == session_id,
                    SystemEvent.event_type == "telemetry_status_transition",
                )
            )
            events = result.scalars().all()
            assert len(events) == 1
