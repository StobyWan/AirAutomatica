"""Tests for SQLite persistence layer."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from airautomatica.db.base import create_db_engine, enable_wal, get_engine, init_db
from airautomatica.db.models import PathPoint, SystemEvent, TelemetrySample
from airautomatica.db.session import get_session
from airautomatica.models.state import AircraftState, TelemetryStatus
from airautomatica.services.persistence import (
    PathRecorder,
    PersistenceService,
    TelemetryLifecycleLogger,
    _haversine_m,
)


def test_haversine_m() -> None:
    """Haversine distance is reasonable for known points."""
    # Same point
    assert _haversine_m(37.0, -122.0, 37.0, -122.0) < 1.0
    # ~1 degree lat ≈ 111 km
    d = _haversine_m(37.0, -122.0, 38.0, -122.0)
    assert 110_000 < d < 112_000
    # ~0.0001 deg ≈ 11 m
    d = _haversine_m(37.0, -122.0, 37.0 + 0.0001, -122.0)
    assert 10 < d < 12


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


def test_get_recent_system_events() -> None:
    """get_recent_system_events returns events newest first, empty when no DB."""
    with patch("airautomatica.services.persistence.get_engine", return_value=None):
        persistence = PersistenceService()
        assert persistence.get_recent_system_events(limit=10) == []

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        persistence.insert_system_event(
            session_id,
            "info",
            "telemetry_status_transition",
            "Telemetry connected -> disconnected",
            {"from": "connected", "to": "disconnected"},
        )
        persistence.insert_system_event(
            session_id, "info", "app_shutdown", "Application shutdown", None
        )

        events = persistence.get_recent_system_events(limit=10)
        assert len(events) == 2
        assert events[0]["event_type"] == "app_shutdown"
        assert events[1]["event_type"] == "telemetry_status_transition"
        assert "timestamp" in events[0]
        assert "metadata" in events[0]
        assert events[1]["metadata"] == {"from": "connected", "to": "disconnected"}


def test_get_recent_telemetry_samples() -> None:
    """get_recent_telemetry_samples returns samples for session, empty when no DB/session."""
    with patch("airautomatica.services.persistence.get_engine", return_value=None):
        persistence = PersistenceService()
        assert persistence.get_recent_telemetry_samples(1, limit=10) == []

    persistence = PersistenceService()
    assert persistence.get_recent_telemetry_samples(None, limit=10) == []

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
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

        samples = persistence.get_recent_telemetry_samples(session_id, limit=10)
        assert len(samples) == 1
        assert samples[0]["lat"] == 37.5
        assert samples[0]["lon"] == -122.2
        assert samples[0]["voltage_v"] == 12.5
        assert samples[0]["groundspeed_m_s"] == 10.0
        assert "timestamp" in samples[0]


def test_get_recent_sessions_includes_detection_count() -> None:
    """get_recent_sessions includes detection_count when include_detection_count=True."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        from airautomatica.ai.models import AiResult

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        persistence.insert_detection(
            session_id,
            AiResult(
                "person", 0.9, "Person detected", "mock", datetime.now(timezone.utc)
            ),
            37.0,
            -122.0,
            100.0,
        )
        persistence.insert_detection(
            session_id,
            AiResult("vehicle", 0.8, "Vehicle", "mock", datetime.now(timezone.utc)),
            37.0,
            -122.0,
            100.0,
        )

        sessions = persistence.get_recent_sessions(
            limit=10, include_detection_count=True
        )
        assert len(sessions) >= 1
        assert sessions[0]["detection_count"] == 2

        sessions_no_count = persistence.get_recent_sessions(
            limit=10, include_detection_count=False
        )
        assert "detection_count" not in sessions_no_count[0]


def test_get_recent_sessions_returns_sessions() -> None:
    """get_recent_sessions returns sessions newest first with expected fields."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        assert get_engine() is not None

        persistence = PersistenceService()
        s1 = persistence.start_session("mock", "mock")
        s2 = persistence.start_session("serial", "mock")
        assert s1 is not None and s2 is not None

        sessions = persistence.get_recent_sessions(limit=10)
        assert len(sessions) >= 2
        assert sessions[0]["id"] == s2
        assert sessions[1]["id"] == s1
        assert sessions[0]["telemetry_backend"] == "serial"
        assert sessions[0]["ai_backend"] == "mock"
        assert "started_at" in sessions[0]
        assert "ended_at" in sessions[0]
        assert sessions[0]["ended_at"] is None


def test_insert_path_point_and_get_session_path() -> None:
    """insert_path_point stores points; get_session_path returns them oldest first."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        assert get_engine() is not None

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        t1 = datetime.now(timezone.utc)
        t2 = t1 + timedelta(seconds=1)
        t3 = t2 + timedelta(seconds=1)
        persistence.insert_path_point(session_id, t1, 37.0, -122.0, 100.0)
        persistence.insert_path_point(session_id, t2, 37.001, -122.001, 105.0)
        persistence.insert_path_point(session_id, t3, 37.002, -122.002, 110.0)

        path_data = persistence.get_session_path(session_id)
        assert len(path_data) == 3
        assert path_data[0]["lat"] == 37.0
        assert path_data[0]["lon"] == -122.0
        assert path_data[0]["rel_alt_m"] == 100.0
        assert path_data[2]["lat"] == 37.002
        assert path_data[2]["lon"] == -122.002


def test_get_session_path_fallback_to_telemetry_samples() -> None:
    """get_session_path falls back to telemetry_samples when path_points is empty."""
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
            lon=-122.5,
            rel_alt_m=50.0,
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

        path_data = persistence.get_session_path(session_id)
        assert len(path_data) == 1
        assert path_data[0]["lat"] == 37.5
        assert path_data[0]["lon"] == -122.5
        assert path_data[0]["rel_alt_m"] == 50.0


def test_path_recorder_distance_based() -> None:
    """PathRecorder stores first point, then only when moved > min_distance_m."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        init_db(str(path))
        assert get_engine() is not None

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        recorder = PathRecorder(persistence, session_id, min_distance_m=100.0)
        now = datetime.now(timezone.utc)

        def make_state(lat: float, lon: float) -> AircraftState:
            return AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=lat,
                lon=lon,
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

        recorder.maybe_record(make_state(37.0, -122.0))
        recorder.maybe_record(make_state(37.0, -122.0))
        recorder.maybe_record(make_state(37.001, -122.0))
        recorder.maybe_record(make_state(37.002, -122.0))

        path_data = persistence.get_session_path(session_id)
        assert len(path_data) == 3
        assert path_data[0]["lat"] == 37.0
        assert path_data[1]["lat"] == 37.001
        assert path_data[2]["lat"] == 37.002


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


def _make_state(
    telemetry_status: TelemetryStatus,
    reconnect_count: int = 0,
    last_disconnect_reason: str | None = None,
) -> AircraftState:
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
            _make_state(
                "connected",
                reconnect_count=2,
                last_disconnect_reason="Connection refused",
            )
        )

        with get_session() as session:
            assert session is not None
            result = session.execute(
                select(SystemEvent)
                .where(
                    SystemEvent.session_id == session_id,
                    SystemEvent.event_type == "telemetry_status_transition",
                )
                .order_by(SystemEvent.id)
            )
            events = result.scalars().all()
            assert len(events) >= 2
            reconnected = next(
                e for e in events if "disconnected -> connected" in e.message
            )
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
