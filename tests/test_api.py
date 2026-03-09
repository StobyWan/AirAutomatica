"""Tests for API endpoints."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airautomatica.ai.models import AiResult
from airautomatica.api.server import create_app
from airautomatica.db import init_db
from airautomatica.db.base import get_engine
from airautomatica.models.state import AircraftState
from airautomatica.services.persistence import PersistenceService
from airautomatica.services.state_store import StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore()


@pytest.fixture
def client(store: StateStore) -> TestClient:
    return TestClient(create_app(store))


def test_health(client: TestClient) -> None:
    """GET /health returns ok with telemetry_status, ai_mode, and persistence block when no state."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "ai_mode" in data
    assert data["ai_mode"] in ("mock", "lmstudio", "aihat")
    assert data["telemetry"]["telemetry_status"] == "disconnected"
    assert data["telemetry"]["connected"] is False
    assert "persistence" in data
    assert "persistence_enabled" in data["persistence"]
    assert "sqlite_db_path" in data["persistence"]
    assert "session_id" in data["persistence"]
    assert "last_persistence_error" in data["persistence"]


def test_health_with_connected_state(client: TestClient, store: StateStore) -> None:
    """GET /health includes telemetry connection status when state exists."""
    now = datetime.now(timezone.utc)
    state = AircraftState(
        connected=True,
        heartbeat=5,
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
        last_heartbeat_at=now,
        heartbeat_age_s=0.5,
    )
    store.update(state)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["telemetry"]["telemetry_status"] == "connected"
    assert data["telemetry"]["connected"] is True
    assert data["telemetry"]["heartbeat_age_s"] == 0.5


def test_state_heartbeat_age_null_when_unknown(client: TestClient, store: StateStore) -> None:
    """GET /state returns heartbeat_age_s as null when unknown (no heartbeat yet)."""
    now = datetime.now(timezone.utc)
    state = AircraftState(
        connected=False,
        heartbeat=0,
        mode="UNKNOWN",
        lat=float("nan"),
        lon=float("nan"),
        rel_alt_m=float("nan"),
        heading_deg=float("nan"),
        roll_rad=float("nan"),
        pitch_rad=float("nan"),
        yaw_rad=float("nan"),
        voltage_v=float("nan"),
        current_a=float("nan"),
        groundspeed_m_s=float("nan"),
        airspeed_m_s=float("nan"),
        timestamp=now,
        last_heartbeat_at=None,
        heartbeat_age_s=float("nan"),
        telemetry_status="starting",
        reconnect_count=0,
        last_disconnect_reason=None,
    )
    store.update(state)
    r = client.get("/state")
    assert r.status_code == 200
    data = r.json()
    assert data["state"]["heartbeat_age_s"] is None
    assert data["state"]["telemetry_status"] == "starting"


def test_state_empty(client: TestClient, store: StateStore) -> None:
    """GET /state returns null when no state yet."""
    r = client.get("/state")
    assert r.status_code == 200
    assert r.json() == {"state": None}


def test_state_with_data(client: TestClient, store: StateStore) -> None:
    """GET /state returns state when store has data."""
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
        last_heartbeat_at=now,
        heartbeat_age_s=0.0,
    )
    store.update(state)
    r = client.get("/state")
    assert r.status_code == 200
    data = r.json()
    assert data["state"] is not None
    assert data["state"]["lat"] == 37.0
    assert data["state"]["mode"] == "GUIDED"
    assert data["state"]["telemetry_status"] == "connected"
    assert data["state"]["last_heartbeat_at"] is not None
    assert data["state"]["heartbeat_age_s"] == 0.0


def test_health_includes_persistence_info_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health includes persistence block with DB path and session_id when DB is enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        db_path = str(path)
        monkeypatch.setenv("SQLITE_DB_PATH", db_path)
        init_db(db_path)
        assert get_engine() is not None

        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        client = TestClient(create_app(store, persistence=persistence, session_id=session_id))
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["persistence"]["persistence_enabled"] is True
        assert data["persistence"]["sqlite_db_path"] == db_path
        assert data["persistence"]["session_id"] == session_id
        assert data["persistence"]["last_persistence_error"] is None


def test_recent_detections_empty_when_no_persistence(client: TestClient) -> None:
    """GET /recent-detections returns empty when persistence not configured."""
    r = client.get("/recent-detections")
    assert r.status_code == 200
    data = r.json()
    assert data["detections"] == []
    assert data["session_id"] is None


def test_recent_detections_empty_when_no_session(store: StateStore) -> None:
    """GET /recent-detections returns empty when session_id is None."""
    persistence = PersistenceService()
    client = TestClient(create_app(store, persistence=persistence, session_id=None))
    r = client.get("/recent-detections")
    assert r.status_code == 200
    data = r.json()
    assert data["detections"] == []
    assert data["session_id"] is None


def test_recent_detections_returns_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /recent-detections returns persisted detections."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        assert get_engine() is not None

        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        result = AiResult(
            label="person",
            confidence=0.9,
            summary="Person detected",
            source_backend="mock",
            timestamp=datetime.now(timezone.utc),
            metadata={"call_count": 1},
        )
        persistence.insert_detection(session_id, result, 37.0, -122.0, 100.0)

        client = TestClient(create_app(store, persistence=persistence, session_id=session_id))
        r = client.get("/recent-detections")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert len(data["detections"]) == 1
        d = data["detections"][0]
        assert d["label"] == "person"
        assert d["confidence"] == 0.9
        assert d["summary"] == "Person detected"
        assert d["source_backend"] == "mock"
        assert d["lat"] == 37.0
        assert d["lon"] == -122.0
        assert d["rel_alt_m"] == 100.0
        assert d["metadata"] == {"call_count": 1}
        assert "id" in d
        assert "timestamp" in d


def test_recent_detections_newest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /recent-detections returns detections newest first."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        assert get_engine() is not None

        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        base = datetime.now(timezone.utc)
        persistence.insert_detection(
            session_id,
            AiResult("old", 0.8, "Old", "mock", base, metadata={"n": 1}),
            37.0, -122.0, 100.0,
        )
        persistence.insert_detection(
            session_id,
            AiResult("new", 0.9, "New", "mock", base + timedelta(seconds=10), metadata={"n": 2}),
            37.0, -122.0, 100.0,
        )

        client = TestClient(create_app(store, persistence=persistence, session_id=session_id))
        r = client.get("/recent-detections")
        assert r.status_code == 200
        data = r.json()
        assert len(data["detections"]) == 2
        assert data["detections"][0]["label"] == "new"
        assert data["detections"][1]["label"] == "old"


def test_recent_detections_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /recent-detections returns at most 20 detections."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        assert get_engine() is not None

        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        base = datetime.now(timezone.utc)
        for i in range(25):
            persistence.insert_detection(
                session_id,
                AiResult(f"det_{i}", 0.8, f"Detection {i}", "mock", base + timedelta(seconds=i)),
                37.0, -122.0, 100.0,
            )

        client = TestClient(create_app(store, persistence=persistence, session_id=session_id))
        r = client.get("/recent-detections")
        assert r.status_code == 200
        data = r.json()
        assert len(data["detections"]) == 20
        assert data["detections"][0]["label"] == "det_24"
        assert data["detections"][19]["label"] == "det_5"
