"""Tests for API endpoints."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.api.server import create_app
from airautomatica.db import init_db
from airautomatica.db.base import get_engine
from airautomatica.models.state import AircraftState
from airautomatica.services.persistence import PersistenceService
from airautomatica.services.state_store import StateStore
from airautomatica.settings import load_settings


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
    assert data["ai_mode"] in (
        "mock",
        "lmstudio",
        "ollama",
        "aihat",
        "mock+aihat",
        "ollama+aihat",
    )
    assert data["telemetry_backend"] in ("mock", "serial")
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


def test_state_heartbeat_age_null_when_unknown(
    client: TestClient, store: StateStore
) -> None:
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


def test_health_includes_persistence_info_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
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

        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
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
            37.0,
            -122.0,
            100.0,
        )
        persistence.insert_detection(
            session_id,
            AiResult(
                "new",
                0.9,
                "New",
                "mock",
                base + timedelta(seconds=10),
                metadata={"n": 2},
            ),
            37.0,
            -122.0,
            100.0,
        )

        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
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
                AiResult(
                    f"det_{i}",
                    0.8,
                    f"Detection {i}",
                    "mock",
                    base + timedelta(seconds=i),
                ),
                37.0,
                -122.0,
                100.0,
            )

        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
        r = client.get("/recent-detections")
        assert r.status_code == 200
        data = r.json()
        assert len(data["detections"]) == 20
        assert data["detections"][0]["label"] == "det_24"
        assert data["detections"][19]["label"] == "det_5"


def test_get_session_path_empty_when_no_persistence(client: TestClient) -> None:
    """GET /sessions/{id}/path returns empty path when persistence not configured."""
    r = client.get("/sessions/1/path")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == 1
    assert data["path"] == []


def test_recent_events_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /recent-events returns 200 and list of events."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        persistence.insert_system_event(
            session_id,
            "info",
            "telemetry_status_transition",
            "Test event",
            {"from": "connected", "to": "disconnected"},
        )
        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
        r = client.get("/recent-events")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert len(data["events"]) >= 1
        assert data["events"][0]["event_type"] == "telemetry_status_transition"


def test_recent_events_empty_when_no_persistence(client: TestClient) -> None:
    """GET /recent-events returns empty list when persistence not configured."""
    r = client.get("/recent-events")
    assert r.status_code == 200
    assert r.json() == {"events": []}


def test_sessions_telemetry_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /sessions/{id}/telemetry-samples returns 200 and list of samples."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
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
        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
        r = client.get(f"/sessions/{session_id}/telemetry-samples")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert "samples" in data
        assert len(data["samples"]) == 1
        assert data["samples"][0]["voltage_v"] == 12.5


def test_sessions_telemetry_empty_when_no_persistence(client: TestClient) -> None:
    """GET /sessions/{id}/telemetry-samples returns empty when persistence not configured."""
    r = client.get("/sessions/1/telemetry-samples")
    assert r.status_code == 200
    assert r.json() == {"samples": [], "session_id": 1}


def test_sessions_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /sessions returns 200 and list of sessions with detection_count."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
        r = client.get("/sessions")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data
        assert data["current_session_id"] == session_id
        assert len(data["sessions"]) >= 1
        assert "detection_count" in data["sessions"][0]


def test_sessions_empty_when_no_persistence(client: TestClient) -> None:
    """GET /sessions returns empty when persistence not configured."""
    r = client.get("/sessions")
    assert r.status_code == 200
    assert r.json() == {"sessions": [], "current_session_id": None}


def test_get_settings(client: TestClient) -> None:
    """GET /settings returns canonical keys only (no AI_MODE)."""
    r = client.get("/settings")
    assert r.status_code == 200
    data = r.json()
    assert "settings" in data
    s = data["settings"]
    assert "TELEMETRY_BACKEND" in s
    assert "LOCAL_LLM_PROVIDER" in s
    assert "AI_HAT_ENABLED" in s
    assert "AI_MODE" not in s
    assert s["TELEMETRY_BACKEND"] in ("mock", "serial")
    assert s["LOCAL_LLM_PROVIDER"] in ("mock", "lmstudio", "ollama")
    assert s["AI_HAT_ENABLED"] in ("0", "1")


def test_load_settings_with_legacy_file_then_get_returns_canonical(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When settings.json has AI_MODE=ollama, load then GET /settings returns LOCAL_LLM_PROVIDER."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text('{"AI_MODE": "ollama"}')
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)

        monkeypatch.delenv("LOCAL_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("AI_MODE", raising=False)
        load_settings()

        client = TestClient(create_app(store))
        r = client.get("/settings")
        assert r.status_code == 200
        s = r.json()["settings"]
        assert s.get("LOCAL_LLM_PROVIDER") == "ollama"
        assert "AI_MODE" not in s


def test_get_settings_returns_canonical_when_legacy_in_env(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When AI_MODE is set (legacy), GET /settings returns LOCAL_LLM_PROVIDER, not AI_MODE."""
    monkeypatch.setenv("AI_MODE", "ollama")
    monkeypatch.delenv("LOCAL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_BACKEND", raising=False)
    monkeypatch.delenv("AI_HAT_ENABLED", raising=False)

    client = TestClient(create_app(store))
    r = client.get("/settings")
    assert r.status_code == 200
    s = r.json()["settings"]
    assert s.get("LOCAL_LLM_PROVIDER") == "ollama"
    assert "AI_MODE" not in s


def test_get_settings_ai_hat_enabled_when_aihat_mode(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When AI_MODE=aihat, GET /settings returns AI_HAT_ENABLED=1, LOCAL_LLM_PROVIDER=mock."""
    monkeypatch.setenv("AI_MODE", "aihat")
    monkeypatch.delenv("LOCAL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_HAT_ENABLED", raising=False)
    monkeypatch.delenv("AI_BACKEND", raising=False)

    client = TestClient(create_app(store))
    r = client.get("/settings")
    assert r.status_code == 200
    s = r.json()["settings"]
    assert s.get("AI_HAT_ENABLED") == "1"
    assert s.get("LOCAL_LLM_PROVIDER") == "mock"


def test_post_settings_persists_canonical_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST with canonical keys; file contains only canonical keys."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)

        store = StateStore()
        client = TestClient(create_app(store))
        r = client.post(
            "/settings",
            json={
                "TELEMETRY_BACKEND": "serial",
                "LOCAL_LLM_PROVIDER": "ollama",
                "AI_HAT_ENABLED": "1",
            },
        )
        assert r.status_code == 200
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("TELEMETRY_BACKEND") == "serial"
        assert saved.get("LOCAL_LLM_PROVIDER") == "ollama"
        assert saved.get("AI_HAT_ENABLED") == "1"
        for legacy in ("AI_MODE", "AI_BACKEND"):
            assert legacy not in saved


def test_post_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /settings saves canonical keys only; legacy AI_MODE is mapped, not persisted."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)

        store = StateStore()
        client = TestClient(create_app(store))
        r = client.post(
            "/settings",
            json={"TELEMETRY_BACKEND": "mock", "AI_MODE": "lmstudio"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "restart" in data.get("message", "").lower()
        assert settings_file.exists()
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("TELEMETRY_BACKEND") == "mock"
        assert saved.get("LOCAL_LLM_PROVIDER") == "lmstudio"
        assert "AI_MODE" not in saved


def test_get_session_path_returns_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /sessions/{id}/path returns path points when available."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        assert get_engine() is not None

        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None

        now = datetime.now(timezone.utc)
        persistence.insert_path_point(session_id, now, 37.5, -122.5, 100.0)
        persistence.insert_path_point(
            session_id, now + timedelta(seconds=10), 37.51, -122.51, 105.0
        )

        client = TestClient(
            create_app(store, persistence=persistence, session_id=session_id)
        )
        r = client.get(f"/sessions/{session_id}/path")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert len(data["path"]) == 2
        assert data["path"][0]["lat"] == 37.5
        assert data["path"][0]["lon"] == -122.5
        assert data["path"][1]["lat"] == 37.51
        assert data["path"][1]["lon"] == -122.51


def test_post_telemetry_summary_returns_structured_result(
    store: StateStore,
) -> None:
    """POST /ai/telemetry-summary returns TelemetrySummaryResult when task_service provided."""
    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    client = TestClient(create_app(store, task_service=task_service))
    r = client.post("/ai/telemetry-summary")
    assert r.status_code == 200
    data = r.json()
    assert "error" not in data
    assert data["status"] == "ok"
    assert data["summary"] == "Mock telemetry summary"
    assert data["concerns"] == []
    assert data["recommendations"] == []
    assert "generated_at" in data
    assert data["telemetry_sample_count"] == 0
    assert data["provider"] == "mock"


def test_post_telemetry_summary_error_when_no_task_service(
    store: StateStore,
) -> None:
    """POST /ai/telemetry-summary returns error when task_service is None."""
    client = TestClient(create_app(store))
    r = client.post("/ai/telemetry-summary")
    assert r.status_code == 200
    data = r.json()
    assert data.get("error") == "AI task service not available"


def test_post_event_classification_returns_structured_result(
    store: StateStore,
) -> None:
    """POST /ai/event-classification returns EventClassificationResult when task_service provided."""
    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    client = TestClient(create_app(store, task_service=task_service))
    r = client.post("/ai/event-classification")
    assert r.status_code == 200
    data = r.json()
    assert "error" not in data
    assert data["severity"] == "info"
    assert data["category"] == "general"
    assert data["summary"] == "No significant events"
    assert data["likely_causes"] == []
    assert data["recommended_checks"] == []
    assert "generated_at" in data
    assert data["event_count"] == 0
    assert data["provider"] == "mock"


def test_post_event_classification_error_when_no_task_service(
    store: StateStore,
) -> None:
    """POST /ai/event-classification returns error when task_service is None."""
    client = TestClient(create_app(store))
    r = client.post("/ai/event-classification")
    assert r.status_code == 200
    data = r.json()
    assert data.get("error") == "AI task service not available"
