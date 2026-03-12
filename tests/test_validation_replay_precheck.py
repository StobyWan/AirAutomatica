"""Tests for replay sample order pre-check (Real-Flight Replay Validation Plan Section 0)."""

import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from airautomatica.db import init_db
from airautomatica.db.base import get_engine
from airautomatica.models.state import AircraftState
from airautomatica.services.persistence import PersistenceService
from airautomatica.validation.replay_precheck import (
    ReplaySampleOrderResult,
    validate_replay_sample_order,
)


@pytest.fixture
def persistence(monkeypatch: pytest.MonkeyPatch) -> PersistenceService:
    """Create persistence with temp DB. Keep tmp dir alive for test duration."""
    tmp = tempfile.mkdtemp()
    try:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        yield PersistenceService()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def session_with_monotonic_samples(
    persistence: PersistenceService,
) -> tuple[PersistenceService, int]:
    """Create a session with 5 monotonic samples (oldest-first)."""
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    base = datetime.now(timezone.utc)
    for i in range(5):
        state = AircraftState(
            connected=True,
            heartbeat=1,
            mode="GUIDED",
            lat=37.5 + i * 0.001,
            lon=-122.2,
            rel_alt_m=100.0 + i,
            heading_deg=90.0,
            roll_rad=0.0,
            pitch_rad=0.0,
            yaw_rad=0.0,
            voltage_v=12.5,
            current_a=2.0,
            groundspeed_m_s=10.0,
            airspeed_m_s=12.0,
            timestamp=base + timedelta(seconds=i),
            telemetry_status="connected",
        )
        persistence.insert_telemetry_sample(session_id, state)
    return persistence, session_id


def test_validate_replay_sample_order_pass(
    session_with_monotonic_samples: tuple[PersistenceService, int],
) -> None:
    """Monotonic oldest-first samples pass validation."""
    persistence, session_id = session_with_monotonic_samples
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is True
    assert result.session_id == session_id
    assert result.sample_count == 5
    assert result.first_timestamp is not None
    assert result.last_timestamp is not None
    assert result.non_monotonic_indices == []
    assert result.duplicate_timestamps == []
    assert result.message == "OK"


def test_validate_replay_sample_order_no_samples(
    persistence: PersistenceService,
) -> None:
    """Empty session fails with 'No samples returned'."""
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is False
    assert result.sample_count == 0
    assert result.message == "No samples returned"


def test_validate_replay_sample_order_non_monotonic(
    persistence: PersistenceService,
) -> None:
    """Samples with timestamp going backward fail."""
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    base = datetime.now(timezone.utc)
    # Insert out of order: we can't easily do that via insert_telemetry_sample
    # since it inserts one at a time. Instead, mock get_recent_telemetry_samples
    # to return non-monotonic data.
    mock_samples = [
        {"timestamp": (base + timedelta(seconds=i)).isoformat(), "lat": 37.5}
        for i in [0, 1, 3, 2, 4]  # index 3 has ts < index 2
    ]
    persistence.get_recent_telemetry_samples = MagicMock(  # type: ignore[method-assign]
        return_value=mock_samples
    )
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is False
    assert 3 in result.non_monotonic_indices


def test_validate_replay_sample_order_duplicates(
    persistence: PersistenceService,
) -> None:
    """Samples with duplicate timestamps fail."""
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    base = datetime.now(timezone.utc)
    ts_str = (base + timedelta(seconds=1)).isoformat()
    mock_samples = [
        {"timestamp": (base + timedelta(seconds=i)).isoformat(), "lat": 37.5}
        for i in [0, 1, 1, 2, 3]  # duplicate at index 2
    ]
    persistence.get_recent_telemetry_samples = MagicMock(  # type: ignore[method-assign]
        return_value=mock_samples
    )
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is False
    assert 2 in result.duplicate_timestamps


def test_validate_replay_sample_order_not_oldest_first(
    persistence: PersistenceService,
) -> None:
    """Samples with first > last (desc order) fail."""
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    base = datetime.now(timezone.utc)
    mock_samples = [
        {"timestamp": (base + timedelta(seconds=4 - i)).isoformat(), "lat": 37.5}
        for i in range(5)  # 4,3,2,1,0 - newest first
    ]
    persistence.get_recent_telemetry_samples = MagicMock(  # type: ignore[method-assign]
        return_value=mock_samples
    )
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is False
    assert "not oldest-first" in result.message


def test_validate_replay_sample_order_single_sample(
    session_with_monotonic_samples: tuple[PersistenceService, int],
) -> None:
    """Single sample passes (trivially monotonic)."""
    persistence, session_id = session_with_monotonic_samples
    # Override to return only 1 sample
    samples = persistence.get_recent_telemetry_samples(
        session_id, limit=5000, order="asc"
    )
    persistence.get_recent_telemetry_samples = MagicMock(  # type: ignore[method-assign]
        return_value=samples[:1]
    )
    result = validate_replay_sample_order(session_id, persistence)
    assert result.passed is True
    assert result.sample_count == 1
