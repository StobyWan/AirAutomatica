"""Tests for API endpoints."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from airautomatica.ai.mock_service import MockAiService
from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_readiness import OllamaReadinessResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.api.server import create_app
from airautomatica.db import init_db
from airautomatica.db.base import get_engine
from airautomatica.models.state import AircraftState
from airautomatica.services.app_home_store import AppHomeStore
from airautomatica.services.camera_recording import CameraRecordingService
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
    assert "telemetry_summary_counts" in data
    assert "perception_counts" in data
    assert "perception_acceptance_rate" in data
    assert "telemetry_meaningful_rate" in data
    assert data["perception_acceptance_rate"] is None
    assert data["telemetry_meaningful_rate"] is None
    counts = data["perception_counts"]
    assert "accepted" in counts
    assert "suppressed" in counts
    assert "no_detection" in counts
    assert "non_perception_label" in counts
    assert "unknown_label" in counts
    assert "parse_error" in counts


def test_post_ai_detect_returns_detection_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/ai/detect returns 200 with DetectionResult schema."""
    monkeypatch.setenv("AI_HAT_ENABLED", "0")
    monkeypatch.delenv("AI_MODE", raising=False)
    r = client.post("/api/ai/detect")
    assert r.status_code == 200
    d = r.json()
    assert "backend" in d
    assert "model" in d
    assert "state" in d
    assert d["state"] in (
        "ready",
        "no_detections",
        "error",
        "disabled",
        "unavailable",
    )
    assert "structured_output_supported" in d
    assert "detections" in d
    assert isinstance(d["detections"], list)
    assert "errors" in d
    assert isinstance(d["errors"], list)
    assert d["state"] == "disabled"
    assert "events" in d
    assert isinstance(d["events"], list)


def test_post_ai_detect_includes_events(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/ai/detect response includes events from normalization."""
    from unittest.mock import MagicMock

    from airautomatica.ai.detection_models import (
        Detection,
        DetectionBBox,
        DetectionResult,
    )
    from airautomatica.services.ai_detection_store import AiDetectionStore

    monkeypatch.setenv("AI_HAT_ENABLED", "0")
    ai_store = AiDetectionStore()
    det = Detection(
        label="person",
        confidence=0.9,
        bbox=DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4),
    )
    mock_result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="ready",
        structured_output_supported=True,
        detections=[det],
        frame_width=640,
        frame_height=480,
        inference_time_ms=50.0,
        errors=[],
    )
    with patch("airautomatica.api.routers.ai.HailoAiHatProvider") as mock_provider_cls:
        mock_provider = MagicMock()
        mock_provider.run_object_detection.return_value = mock_result
        mock_provider_cls.return_value = mock_provider
        test_client = TestClient(create_app(store=store, ai_detection_store=ai_store))
        r = test_client.post("/api/ai/detect")
    assert r.status_code == 200
    d = r.json()
    assert "events" in d
    events = d["events"]
    assert isinstance(events, list)
    assert len(events) >= 1
    person_ev = next(
        (e for e in events if e.get("event_type") == "person_detected"), None
    )
    assert person_ev is not None
    assert person_ev["label"] == "person"
    assert person_ev["confidence"] == 0.9
    obj_count = next((e for e in events if e.get("event_type") == "object_count"), None)
    assert obj_count is not None
    assert obj_count["count"] == 1


def test_post_ai_detect_person_detected_hook_inserts_system_event(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """person_detected from AI HAT one-shot triggers system event when persistence available."""
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from airautomatica.ai.detection_models import (
        Detection,
        DetectionBBox,
        DetectionResult,
    )
    from airautomatica.services.ai_detection_store import AiDetectionStore

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        monkeypatch.setenv("AI_HAT_ENABLED", "0")
        init_db(str(path))
        assert get_engine() is not None

        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        session_ref: list[int | None] = [session_id]
        ai_store = AiDetectionStore()

        det = Detection(
            label="person",
            confidence=0.85,
            bbox=DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4),
        )
        mock_result = DetectionResult(
            backend="hailo",
            model="yolov6n",
            state="ready",
            structured_output_supported=True,
            detections=[det],
            frame_width=640,
            frame_height=480,
            inference_time_ms=50.0,
            errors=[],
        )
        with patch("airautomatica.api.routers.ai.HailoAiHatProvider") as mock_cls:
            mock_cls.return_value = MagicMock(
                run_object_detection=MagicMock(return_value=mock_result)
            )
            client = TestClient(
                create_app(
                    store=store,
                    ai_detection_store=ai_store,
                    persistence=persistence,
                    session_ref=session_ref,
                )
            )
            r = client.post("/api/ai/detect")
        assert r.status_code == 200
        events = persistence.get_recent_system_events(limit=5)
        person_events = [e for e in events if e.get("event_type") == "person_detected"]
        assert len(person_events) == 1
        assert person_events[0]["message"] == "Person detected (AI HAT one-shot)"
        assert person_events[0].get("metadata", {}).get("confidence") == 0.85
        # Session-linking: one-shot detections persisted when session active
        sessions = persistence.get_recent_sessions(
            limit=5, include_detection_count=True
        )
        assert len(sessions) >= 1
        assert sessions[0]["detection_count"] == 1


def test_post_ai_detect_returns_error_when_recording_active(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """POST /api/ai/detect returns state=error when camera recording is active (camera contention)."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("AI_HAT_ENABLED", "0")
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "manual")
    load_settings()

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: "libcamera-vid",
    )
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.subprocess.Popen",
        lambda *a, **k: mock_proc,
    )
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.time.sleep", lambda *a, **k: None
    )

    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))

    # Start recording so camera is "busy"
    r_start = client.post("/camera/recording/start")
    assert r_start.status_code == 200
    assert r_start.json().get("recording") is True

    # Detection should short-circuit with clear error, not attempt rpicam-still
    r = client.post("/api/ai/detect")
    assert r.status_code == 200
    d = r.json()
    assert d["state"] == "error"
    errors = d.get("errors", [])
    assert len(errors) == 1
    assert "Camera busy" in errors[0]
    assert "recording is active" in errors[0]


def test_get_ai_last_detection_empty_when_no_store(
    client: TestClient,
) -> None:
    """GET /api/ai/last-detection returns cached=False when no store."""
    r = client.get("/api/ai/last-detection")
    assert r.status_code == 200
    d = r.json()
    assert d["cached"] is False
    assert d["result"] is None
    assert d["timestamp"] is None


def test_get_ai_last_detection_empty_when_no_cache(
    store: StateStore,
) -> None:
    """GET /api/ai/last-detection returns cached=False when store has no result."""
    from airautomatica.services.ai_detection_store import AiDetectionStore

    ai_store = AiDetectionStore()
    client = TestClient(create_app(store, ai_detection_store=ai_store))
    r = client.get("/api/ai/last-detection")
    assert r.status_code == 200
    d = r.json()
    assert d["cached"] is False
    assert d["result"] is None
    assert d["timestamp"] is None


def test_get_ai_last_detection_returns_cached(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/ai/last-detection returns cached result when store has one."""
    from airautomatica.ai.detection_models import (
        Detection,
        DetectionBBox,
        DetectionResult,
    )
    from airautomatica.services.ai_detection_store import AiDetectionStore

    monkeypatch.setenv("AI_HAT_ENABLED", "0")
    ai_store = AiDetectionStore()
    det = Detection(
        label="person",
        confidence=0.9,
        bbox=DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4),
    )
    result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="ready",
        structured_output_supported=True,
        detections=[det],
        frame_width=640,
        frame_height=480,
        inference_time_ms=50.0,
        errors=[],
    )
    ai_store.set_last_detection(result, session_id=42)
    client = TestClient(create_app(store, ai_detection_store=ai_store))
    r = client.get("/api/ai/last-detection")
    assert r.status_code == 200
    d = r.json()
    assert d["cached"] is True
    assert d["result"] is not None
    assert d["result"]["state"] == "ready"
    assert len(d["result"]["detections"]) == 1
    assert d["result"]["detections"][0]["label"] == "person"
    assert d["timestamp"] is not None
    assert d["source"] == "camera"
    assert d["session_id"] == 42


def test_health_includes_ollama_ready_when_provider_ollama(
    store: StateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /health includes ollama_ready when LOCAL_LLM_PROVIDER=ollama."""
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "ollama")
    ollama_svc = OllamaAiService(
        base_url="http://127.0.0.1:11434",
        model="gemma3:1b",
        timeout_sec=5.0,
    )
    task_service = OllamaTaskService(provider="ollama", ollama_service=ollama_svc)
    with patch(
        "airautomatica.api.server.check_ollama_ready",
        return_value=OllamaReadinessResult(ready=True, reason="ready", detail=None),
    ):
        client = TestClient(create_app(store, task_service=task_service))
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ollama_ready"] is True

    with patch(
        "airautomatica.api.server.check_ollama_ready",
        return_value=OllamaReadinessResult(
            ready=False, reason="unreachable", detail=None
        ),
    ):
        client = TestClient(create_app(store, task_service=task_service))
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ollama_ready"] is False


def test_health_omits_ollama_ready_when_provider_mock(
    store: StateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /health omits ollama_ready when LOCAL_LLM_PROVIDER=mock."""
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")
    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    client = TestClient(create_app(store, task_service=task_service))
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "ollama_ready" not in data


def test_health_includes_telemetry_summary_counts_when_task_service_exists(
    store: StateStore,
) -> None:
    """GET /health includes telemetry_summary_counts when task_service is provided."""
    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    client = TestClient(create_app(store, task_service=task_service))
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "telemetry_summary_counts" in data
    counts = data["telemetry_summary_counts"]
    assert "accepted_meaningful" in counts
    assert "normalized_to_nominal" in counts
    assert "parse_error" in counts


def test_health_includes_derived_rates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /health includes perception_acceptance_rate and telemetry_meaningful_rate."""
    from airautomatica.api import server

    def mock_perception_counts():
        return {
            "accepted": 4,
            "suppressed": 2,
            "no_detection": 2,
            "non_perception_label": 0,
            "unknown_label": 0,
            "parse_error": 0,
        }

    def mock_telemetry_summary_counts():
        return {
            "accepted_meaningful": 2,
            "normalized_to_nominal": 2,
            "parse_error": 0,
        }

    monkeypatch.setattr(server, "get_perception_counts", mock_perception_counts)
    monkeypatch.setattr(
        server, "get_telemetry_summary_counts", mock_telemetry_summary_counts
    )
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["perception_acceptance_rate"] == 0.5  # 4/8
    assert data["telemetry_meaningful_rate"] == 0.5  # 2/4


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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
    client = TestClient(create_app(store, session_ref=[None], persistence=persistence))
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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
            create_app(store, session_ref=[session_id], persistence=persistence)
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


def test_sessions_telemetry_limit_and_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /sessions/{id}/telemetry-samples accepts limit and order query params."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
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
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r_desc = client.get(
            f"/sessions/{session_id}/telemetry-samples?limit=3&order=desc"
        )
        assert r_desc.status_code == 200
        samples_desc = r_desc.json()["samples"]
        assert len(samples_desc) == 3
        assert samples_desc[0]["rel_alt_m"] == 104.0
        assert samples_desc[2]["rel_alt_m"] == 102.0
        r_asc = client.get(
            f"/sessions/{session_id}/telemetry-samples?limit=3&order=asc"
        )
        assert r_asc.status_code == 200
        samples_asc = r_asc.json()["samples"]
        assert len(samples_asc) == 3
        assert samples_asc[0]["rel_alt_m"] == 100.0
        assert samples_asc[2]["rel_alt_m"] == 102.0


def test_get_session_flight_events_empty_when_no_persistence(
    client: TestClient,
) -> None:
    """GET /sessions/{id}/flight-events returns empty when persistence not configured."""
    r = client.get("/sessions/1/flight-events")
    assert r.status_code == 200
    assert r.json() == {"events": [], "session_id": 1}


def test_get_session_flight_events_returns_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/flight-events returns persisted flight events."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        base = datetime.now(timezone.utc)
        persistence.insert_flight_event(
            session_id=session_id,
            event_name="gps_degraded",
            severity="warn",
            started_at=base,
            ended_at=base + timedelta(seconds=10),
            evidence={"satellites_visible": 4},
        )
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r = client.get(f"/sessions/{session_id}/flight-events")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert len(data["events"]) == 1
        assert data["events"][0]["event_name"] == "gps_degraded"
        assert data["events"][0]["severity"] == "warn"
        assert "started_at" in data["events"][0]
        assert "ended_at" in data["events"][0]


def test_get_session_phase_intervals_empty_when_no_persistence(
    client: TestClient,
) -> None:
    """GET /sessions/{id}/phase-intervals returns empty when persistence not configured."""
    r = client.get("/sessions/1/phase-intervals")
    assert r.status_code == 200
    assert r.json() == {"intervals": [], "session_id": 1}


def test_get_session_phase_intervals_returns_intervals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/phase-intervals returns persisted phase intervals."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        base = datetime.now(timezone.utc)
        persistence.insert_phase_interval(
            session_id=session_id,
            phase="cruise",
            started_at=base,
            ended_at=base + timedelta(seconds=60),
        )
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r = client.get(f"/sessions/{session_id}/phase-intervals")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert len(data["intervals"]) == 1
        assert data["intervals"][0]["phase"] == "cruise"
        assert "started_at" in data["intervals"][0]
        assert "ended_at" in data["intervals"][0]


def test_session_debrief_404_when_no_persistence(client: TestClient) -> None:
    """GET /sessions/{id}/debrief returns 404 when persistence not configured."""
    r = client.get("/sessions/1/debrief")
    assert r.status_code == 404


def test_session_debrief_404_when_no_samples(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /sessions/{id}/debrief returns 404 when session has no telemetry."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r = client.get(f"/sessions/{session_id}/debrief")
        assert r.status_code == 404
        assert "No telemetry" in r.json()["detail"]


def test_session_debrief_returns_summary_and_compact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/debrief returns summary and compact payload when samples exist."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        now = datetime.now(timezone.utc)
        for i in range(5):
            state = AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=37.5 + i * 0.0001,
                lon=-122.2 + i * 0.0001,
                rel_alt_m=100.0 + i * 10,
                heading_deg=90.0,
                roll_rad=0.0,
                pitch_rad=0.0,
                yaw_rad=0.0,
                voltage_v=12.5,
                current_a=2.0,
                groundspeed_m_s=10.0,
                airspeed_m_s=12.0,
                timestamp=now + timedelta(seconds=i),
                telemetry_status="connected",
            )
            persistence.insert_telemetry_sample(session_id, state)
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r = client.get(f"/sessions/{session_id}/debrief")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert "summary" in data
        assert "compact" in data
        assert "session_duration_sec" in data["summary"]
        assert "phase_duration_sec" in data["summary"]
        assert "top_events" in data["summary"]
        assert "assessment_tags" in data["summary"]
        assert "total_duration_sec" in data["compact"]
        assert "dominant_phase" in data["compact"]
        assert "top_3_event_summaries" in data["compact"]
        assert "top_5_metrics" in data["compact"]
        assert "assessment_sentence" in data["compact"]


def test_session_debrief_without_generate_summary_no_llm_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/debrief without generate_summary does not include generated_summary."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        now = datetime.now(timezone.utc)
        for i in range(3):
            state = AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=37.5 + i * 0.0001,
                lon=-122.2,
                rel_alt_m=100.0 + i * 10,
                heading_deg=90.0,
                roll_rad=0.0,
                pitch_rad=0.0,
                yaw_rad=0.0,
                voltage_v=12.5,
                current_a=2.0,
                groundspeed_m_s=10.0,
                airspeed_m_s=12.0,
                timestamp=now + timedelta(seconds=i),
                telemetry_status="connected",
            )
            persistence.insert_telemetry_sample(session_id, state)
        task_service = OllamaTaskService(provider="mock")
        client = TestClient(
            create_app(
                store,
                session_ref=[session_id],
                persistence=persistence,
                task_service=task_service,
            )
        )
        r = client.get(f"/sessions/{session_id}/debrief")
        assert r.status_code == 200
        data = r.json()
        assert "generated_summary" not in data


def test_session_debrief_with_generate_summary_includes_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/debrief?generate_summary=true returns generated_summary when task_service available."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        now = datetime.now(timezone.utc)
        for i in range(3):
            state = AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=37.5 + i * 0.0001,
                lon=-122.2,
                rel_alt_m=100.0 + i * 10,
                heading_deg=90.0,
                roll_rad=0.0,
                pitch_rad=0.0,
                yaw_rad=0.0,
                voltage_v=12.5,
                current_a=2.0,
                groundspeed_m_s=10.0,
                airspeed_m_s=12.0,
                timestamp=now + timedelta(seconds=i),
                telemetry_status="connected",
            )
            persistence.insert_telemetry_sample(session_id, state)
        task_service = OllamaTaskService(provider="mock")
        client = TestClient(
            create_app(
                store,
                session_ref=[session_id],
                persistence=persistence,
                task_service=task_service,
            )
        )
        r = client.get(f"/sessions/{session_id}/debrief?generate_summary=true")
        assert r.status_code == 200
        data = r.json()
        assert "generated_summary" in data
        assert data["generated_summary"] is not None
        assert (
            "Mock" in data["generated_summary"]
            or "post-flight" in data["generated_summary"].lower()
        )


def test_session_debrief_persists_and_returns_generated_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated summary is persisted; normal fetch returns it without LLM call."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        now = datetime.now(timezone.utc)
        for i in range(3):
            state = AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=37.5 + i * 0.0001,
                lon=-122.2,
                rel_alt_m=100.0 + i * 10,
                heading_deg=90.0,
                roll_rad=0.0,
                pitch_rad=0.0,
                yaw_rad=0.0,
                voltage_v=12.5,
                current_a=2.0,
                groundspeed_m_s=10.0,
                airspeed_m_s=12.0,
                timestamp=now + timedelta(seconds=i),
                telemetry_status="connected",
            )
            persistence.insert_telemetry_sample(session_id, state)
        task_service = OllamaTaskService(provider="mock")
        client = TestClient(
            create_app(
                store,
                session_ref=[session_id],
                persistence=persistence,
                task_service=task_service,
            )
        )
        r1 = client.get(f"/sessions/{session_id}/debrief?generate_summary=true")
        assert r1.status_code == 200
        data1 = r1.json()
        assert "generated_summary" in data1
        generated = data1["generated_summary"]
        assert generated is not None
        assert "generated_debrief_at" in data1
        assert data1["generated_debrief_at"] is not None

        r2 = client.get(f"/sessions/{session_id}/debrief")
        assert r2.status_code == 200
        data2 = r2.json()
        assert "generated_summary" in data2
        assert data2["generated_summary"] == generated
        assert "generated_debrief_at" in data2
        assert data2["generated_debrief_at"] is not None


def test_session_debrief_generate_summary_no_task_service_no_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/debrief?generate_summary=true without task_service returns 200, no generated_summary."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        now = datetime.now(timezone.utc)
        for i in range(3):
            state = AircraftState(
                connected=True,
                heartbeat=1,
                mode="GUIDED",
                lat=37.5 + i * 0.0001,
                lon=-122.2,
                rel_alt_m=100.0 + i * 10,
                heading_deg=90.0,
                roll_rad=0.0,
                pitch_rad=0.0,
                yaw_rad=0.0,
                voltage_v=12.5,
                current_a=2.0,
                groundspeed_m_s=10.0,
                airspeed_m_s=12.0,
                timestamp=now + timedelta(seconds=i),
                telemetry_status="connected",
            )
            persistence.insert_telemetry_sample(session_id, state)
        client = TestClient(
            create_app(store, session_ref=[session_id], persistence=persistence)
        )
        r = client.get(f"/sessions/{session_id}/debrief?generate_summary=true")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "compact" in data
        assert "generated_summary" not in data


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
            create_app(store, session_ref=[session_id], persistence=persistence)
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
    """GET /settings returns raw settings, effective_settings, apply_modes, Ollama status."""
    r = client.get("/settings")
    assert r.status_code == 200
    data = r.json()
    assert "settings" in data
    assert "effective_settings" in data
    assert "apply_modes" in data
    assert "ollama_available" in data
    assert "ollama_ready" in data
    assert "provider_reason" in data
    s = data["settings"]
    assert "TELEMETRY_BACKEND" in s
    assert "LOCAL_LLM_PROVIDER" in s
    assert "OLLAMA_NUM_THREAD" in s
    assert "AI_HAT_ENABLED" in s
    assert "AI_MODE" not in s
    assert s["TELEMETRY_BACKEND"] in ("mock", "serial")
    assert s["LOCAL_LLM_PROVIDER"] in ("mock", "ollama", "")
    assert s["AI_HAT_ENABLED"] in ("0", "1")
    assert data["provider_reason"] in (
        "explicit_mock",
        "explicit_ollama",
        "discovered_ollama_ready",
        "discovered_mock_ollama_unavailable",
    )


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
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
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
                "OLLAMA_NUM_THREAD": "4",
                "AI_HAT_ENABLED": "1",
            },
        )
        assert r.status_code == 200
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("TELEMETRY_BACKEND") == "serial"
        assert saved.get("LOCAL_LLM_PROVIDER") == "ollama"
        assert saved.get("OLLAMA_NUM_THREAD") == "4"
        assert saved.get("AI_HAT_ENABLED") == "1"
        for legacy in ("AI_MODE", "AI_BACKEND"):
            assert legacy not in saved


def test_post_settings_ollama_num_thread_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST OLLAMA_NUM_THREAD outside 1-8 is clamped on save."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)

        store = StateStore()
        client = TestClient(create_app(store))
        r = client.post("/settings", json={"OLLAMA_NUM_THREAD": "99"})
        assert r.status_code == 200
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("OLLAMA_NUM_THREAD") == "8"


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
        assert "changed_keys" in data
        assert "restart_required" in data
        assert "reconnect_required" in data
        assert settings_file.exists()
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("TELEMETRY_BACKEND") == "mock"
        assert saved.get("LOCAL_LLM_PROVIDER") == "mock"
        assert "AI_MODE" not in saved


def test_post_settings_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /settings returns structured result with live/reconnect/restart classification."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )

        store = StateStore()
        client = TestClient(create_app(store))

        r = client.post(
            "/settings",
            json={
                "CAMERA_RECORDING_MODE": "manual",
                "SESSION_AUTO_START_ON_ARM": "0",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "live" in data
        assert "reconnect" in data
        assert "restart" in data
        assert "restart_required" in data
        assert "reconnect_required" in data
        assert "message" in data
        assert data["restart_required"] is False
        assert "CAMERA_RECORDING_MODE" in data["live"]
        assert "SESSION_AUTO_START_ON_ARM" in data["live"]


def test_load_settings_discovers_provider_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When LOCAL_LLM_PROVIDER is unset, load_settings discovers Ollama and sets effective provider."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
        monkeypatch.delenv("LOCAL_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("AI_MODE", raising=False)
        monkeypatch.delenv("AI_BACKEND", raising=False)

        with patch(
            "airautomatica.ai.ollama_readiness.check_ollama_ready",
            return_value=OllamaReadinessResult(ready=False, reason="unreachable"),
        ):
            load_settings()

        import os

        assert os.environ.get("LOCAL_LLM_PROVIDER") == "mock"
        assert not settings_file.exists()


def test_load_settings_does_not_override_explicit_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When LOCAL_LLM_PROVIDER is explicitly set, load_settings does not run discovery."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text('{"LOCAL_LLM_PROVIDER": "ollama"}')
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
        monkeypatch.delenv("LOCAL_LLM_PROVIDER", raising=False)

        load_settings()

        import os

        assert os.environ.get("LOCAL_LLM_PROVIDER") == "ollama"


def test_post_settings_reconfigures_mission_logic(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """POST /settings with AI_MIN_CONFIDENCE/AI_DUPLICATE_WINDOW_SEC reconfigures MissionLogic when available."""
    from airautomatica.services.mission_logic import MissionLogic

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("AI_MIN_CONFIDENCE", "0.5")
        monkeypatch.setenv("AI_DUPLICATE_WINDOW_SEC", "30")

        mission_logic = MissionLogic(
            store=store,
            min_confidence=0.5,
            duplicate_window_sec=30.0,
        )
        client = TestClient(create_app(store, mission_logic=mission_logic))

        r = client.post(
            "/settings",
            json={
                "AI_MIN_CONFIDENCE": "0.7",
                "AI_DUPLICATE_WINDOW_SEC": "45",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "AI_MIN_CONFIDENCE" in data["live"]
        assert "AI_DUPLICATE_WINDOW_SEC" in data["live"]
        assert data["reconnect_required"] is False
        assert "apply immediately" in data["message"].lower()


def test_post_settings_mission_logic_unavailable_reports_reconnect(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When MissionLogic is unavailable, AI_MIN_CONFIDENCE/AI_DUPLICATE_WINDOW_SEC report as reconnect."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )

        client = TestClient(create_app(store))

        r = client.post(
            "/settings",
            json={
                "AI_MIN_CONFIDENCE": "0.7",
                "AI_DUPLICATE_WINDOW_SEC": "45",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "AI_MIN_CONFIDENCE" in data["reconnect"]
        assert "AI_DUPLICATE_WINDOW_SEC" in data["reconnect"]
        assert "AI_MIN_CONFIDENCE" not in data["live"]
        assert "AI_DUPLICATE_WINDOW_SEC" not in data["live"]
        assert "reconnect" in data["message"].lower()


def test_post_settings_reloads_ai_subsystem_when_holder_available(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When ai_holder and reload_ai_fn are provided, POST with AI settings reloads and reports live."""
    from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
    from airautomatica.services.mission_logic import MissionLogic

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")

        task_service = OllamaTaskService(provider="mock", ollama_service=None)
        ai_service = MockAiService()
        holder = AiSubsystemHolder(ai_service, task_service)
        mission_logic = MissionLogic(
            store, ai_service=ai_service, min_confidence=0.5, duplicate_window_sec=30.0
        )

        def reload_fn(provider_before: str) -> ReloadResult:
            from airautomatica.main import _reload_ai_subsystem

            return _reload_ai_subsystem(holder, mission_logic, None, provider_before)

        client = TestClient(
            create_app(
                store,
                ai_holder=holder,
                mission_logic=mission_logic,
                reload_ai_fn=reload_fn,
            )
        )

        r = client.post(
            "/settings",
            json={
                "LOCAL_LLM_MODEL": "gemma3:2b",
                "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "LOCAL_LLM_MODEL" in data["live"]
        assert "LOCAL_LLM_BASE_URL" in data["live"]
        assert "apply immediately" in data["message"].lower()


def test_get_settings_ai_live_when_reload_available(
    store: StateStore,
) -> None:
    """GET /settings returns AI subsystem keys as live when reload_ai_fn is provided."""
    from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
    from airautomatica.services.mission_logic import MissionLogic

    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    ai_service = MockAiService()
    holder = AiSubsystemHolder(ai_service, task_service)
    mission_logic = MissionLogic(store, ai_service=ai_service)

    def reload_fn(provider_before: str) -> ReloadResult:
        from airautomatica.main import _reload_ai_subsystem

        return _reload_ai_subsystem(holder, mission_logic, None, provider_before)

    client = TestClient(
        create_app(
            store,
            ai_holder=holder,
            mission_logic=mission_logic,
            reload_ai_fn=reload_fn,
        )
    )
    r = client.get("/settings")
    assert r.status_code == 200
    apply_modes = r.json()["apply_modes"]
    assert apply_modes["LOCAL_LLM_PROVIDER"] == "live"
    assert apply_modes["LOCAL_LLM_MODEL"] == "live"
    assert apply_modes["LOCAL_LLM_BASE_URL"] == "live"


def test_post_settings_ai_reload_failure_reports_truthfully(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When AI reload fails (e.g. provider change), POST reports failure and AI keys stay in reconnect."""
    from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
    from airautomatica.services.mission_logic import MissionLogic

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")

        task_service = OllamaTaskService(provider="mock", ollama_service=None)
        ai_service = MockAiService()
        holder = AiSubsystemHolder(ai_service, task_service)
        mission_logic = MissionLogic(store, ai_service=ai_service)

        def reload_fn(provider_before: str) -> ReloadResult:
            from airautomatica.main import _reload_ai_subsystem

            return _reload_ai_subsystem(holder, mission_logic, None, provider_before)

        client = TestClient(
            create_app(
                store,
                ai_holder=holder,
                mission_logic=mission_logic,
                reload_ai_fn=reload_fn,
            )
        )

        r = client.post(
            "/settings",
            json={"LOCAL_LLM_PROVIDER": "ollama", "LOCAL_LLM_MODEL": "gemma3:2b"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "LOCAL_LLM_PROVIDER" in data["reconnect"] or "restart" in data["restart"]
        assert (
            "ai reload failed" in data["message"].lower()
            or "restart" in data["message"].lower()
        )
        assert holder.get_ai_service() is ai_service


def test_get_settings_telemetry_live_when_reload_available(
    store: StateStore,
) -> None:
    """GET /settings returns telemetry keys as live when reload_telemetry_fn is provided."""
    from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult

    async def mock_reload() -> TelemetryReconnectResult:
        return TelemetryReconnectResult(
            success=True, backend_before="mock", backend_after="mock"
        )

    client = TestClient(
        create_app(store, reload_telemetry_fn=mock_reload),
    )
    r = client.get("/settings")
    assert r.status_code == 200
    apply_modes = r.json()["apply_modes"]
    assert apply_modes["TELEMETRY_BACKEND"] == "live"
    assert apply_modes["SERIAL_PORT"] == "live"
    assert apply_modes["SERIAL_BAUD"] == "live"


@pytest.mark.asyncio
async def test_post_settings_telemetry_reconnect_success(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When reload_telemetry_fn is provided and succeeds, POST reports telemetry keys as live."""
    from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("TELEMETRY_BACKEND", "mock")

        async def mock_reload() -> TelemetryReconnectResult:
            return TelemetryReconnectResult(
                success=True, backend_before="mock", backend_after="mock"
            )

        client = TestClient(
            create_app(store, reload_telemetry_fn=mock_reload),
        )
        r = client.post(
            "/settings",
            json={"TELEMETRY_BACKEND": "mock", "SERIAL_PORT": "/dev/ttyUSB0"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "TELEMETRY_BACKEND" in data["live"]
        assert "SERIAL_PORT" in data["live"]
        assert "apply immediately" in data["message"].lower()


@pytest.mark.asyncio
async def test_post_settings_telemetry_reconnect_failure_reports_truthfully(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When telemetry reconnect fails, POST reports failure truthfully."""
    from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("TELEMETRY_BACKEND", "mock")

        async def mock_reload_fail() -> TelemetryReconnectResult:
            return TelemetryReconnectResult(
                success=False,
                error="Port /dev/nonexistent not found",
                backend_before="mock",
                backend_after="serial",
            )

        client = TestClient(
            create_app(store, reload_telemetry_fn=mock_reload_fail),
        )
        r = client.post(
            "/settings",
            json={"TELEMETRY_BACKEND": "serial", "SERIAL_PORT": "/dev/nonexistent"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "telemetry reconnect failed" in data["message"].lower()
        assert (
            "TELEMETRY_BACKEND" in data["reconnect"]
            or "TELEMETRY_BACKEND" in data["restart"]
        )


def test_post_settings_serial_validation_blocks_reconnect(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """When switching to serial with non-existent port, validation fails before reconnect."""
    from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult

    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("TELEMETRY_BACKEND", "mock")

        reload_called = []

        async def track_reload() -> TelemetryReconnectResult:
            reload_called.append(True)
            return TelemetryReconnectResult(success=True)

        client = TestClient(
            create_app(store, reload_telemetry_fn=track_reload),
        )
        r = client.post(
            "/settings",
            json={"TELEMETRY_BACKEND": "serial", "SERIAL_PORT": "/dev/nonexistent999"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert (
            "not found" in data["message"].lower() or "port" in data["message"].lower()
        )
        assert len(reload_called) == 0


def test_post_settings_returns_active_summary(
    monkeypatch: pytest.MonkeyPatch,
    store: StateStore,
) -> None:
    """POST /settings returns active_summary with current backend and provider."""
    with tempfile.TemporaryDirectory() as tmp:
        settings_dir = Path(tmp) / ".airautomatica"
        settings_dir.mkdir()
        monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(
            "airautomatica.settings._SETTINGS_FILE", settings_dir / "settings.json"
        )
        monkeypatch.setenv("TELEMETRY_BACKEND", "mock")
        monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")

        client = TestClient(create_app(store))
        r = client.post("/settings", json={"CAMERA_RECORDING_MODE": "manual"})
        assert r.status_code == 200
        data = r.json()
        assert "active_summary" in data
        assert "Telemetry:" in data["active_summary"]
        assert "AI:" in data["active_summary"]


def test_get_settings_returns_active_summary(store: StateStore) -> None:
    """GET /settings returns active_summary with current backend and provider."""
    client = TestClient(create_app(store))
    r = client.get("/settings")
    assert r.status_code == 200
    data = r.json()
    assert "active_summary" in data
    assert "Telemetry:" in data["active_summary"]
    assert "AI:" in data["active_summary"]


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
            create_app(store, session_ref=[session_id], persistence=persistence)
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


def test_post_telemetry_summary_with_preprocessor(
    store: StateStore,
) -> None:
    """POST /ai/telemetry-summary uses preprocessor context when available."""
    from datetime import datetime, timezone

    from airautomatica.telemetry.preprocessing import TelemetryPreprocessor

    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    preprocessor = TelemetryPreprocessor()
    state = AircraftState(
        connected=True,
        heartbeat=1,
        mode="GUIDED",
        lat=37.0,
        lon=-122.0,
        rel_alt_m=100.0,
        heading_deg=45.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=12.5,
        current_a=2.0,
        groundspeed_m_s=5.0,
        airspeed_m_s=6.0,
        timestamp=datetime.now(timezone.utc),
        armed=True,
        climb_rate_m_s=0.0,
    )
    for _ in range(5):
        preprocessor.on_state(state)
    client = TestClient(
        create_app(
            store,
            task_service=task_service,
            preprocessor=preprocessor,
        )
    )
    r = client.post("/ai/telemetry-summary")
    assert r.status_code == 200
    data = r.json()
    assert "error" not in data
    assert data["status"] == "ok"
    assert data["telemetry_sample_count"] == 5
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


def test_post_telemetry_summary_error_when_ollama_no_preprocessor(
    store: StateStore,
) -> None:
    """POST /ai/telemetry-summary returns error when provider=ollama and preprocessor is None."""
    ollama_svc = OllamaAiService(
        base_url="http://127.0.0.1:11434",
        model="gemma3:1b",
        timeout_sec=5.0,
    )
    task_service = OllamaTaskService(provider="ollama", ollama_service=ollama_svc)
    client = TestClient(
        create_app(
            store,
            task_service=task_service,
            preprocessor=None,
        )
    )
    r = client.post("/ai/telemetry-summary")
    assert r.status_code == 200
    data = r.json()
    assert "error" in data
    assert "Preprocessing required" in data["error"]


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


def test_health_includes_camera_recording_when_service_provided(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /health includes camera_recording fields when camera_recording_service provided."""
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "camera_recording_available" in data
    assert "camera_recording_mode" in data
    assert "camera_recording" in data
    assert "camera_recording_file" in data
    assert "camera_recording_started_at" in data
    assert data["camera_recording_mode"] in ("off", "manual", "auto")


def test_off_mode_rejects_api_start(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When mode=off, POST /camera/recording/start returns error."""
    monkeypatch.setenv("CAMERA_RECORDING_MODE", "off")
    load_settings()
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.post("/camera/recording/start")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is False
    assert "Recording disabled" in data.get("error", "")


def test_post_camera_recording_start(
    store: StateStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """POST /camera/recording/start returns ok when mode allows and camera command available."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("CAMERA_RECORDING_MODE", "manual")
    load_settings()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.get_camera_video_command",
        lambda: "libcamera-vid",
    )
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.subprocess.Popen",
        lambda *a, **k: mock_proc,
    )
    monkeypatch.setattr(
        "airautomatica.services.camera_recording.time.sleep", lambda *a, **k: None
    )
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.post("/camera/recording/start")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("recording") is True
    assert "output_file" in data


def test_post_camera_recording_stop(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """POST /camera/recording/stop returns ok."""
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.post("/camera/recording/stop")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("recording") is False
    assert "last_recorded_file" in data


def test_get_recording_file_not_found(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /recordings/{filename} returns 404 when file does not exist."""
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    tmp_path.joinpath("recordings").mkdir(exist_ok=True)
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings/nonexistent.mp4")
    assert r.status_code == 404


def test_get_recording_file_rejects_path_traversal(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /recordings/{filename} returns 400 for path traversal attempts."""
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    # Filename containing ".." should be rejected
    r = client.get("/recordings/foo..bar")
    assert r.status_code == 400


def test_get_recording_file_serves_file(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /recordings/{filename} serves the file when it exists."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "test_rec.mp4").write_bytes(b"fake video content")
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings/test_rec.mp4")
    assert r.status_code == 200
    assert r.content == b"fake video content"


def test_get_recording_file_cwd_independent(
    store: StateStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /recordings/{filename} serves file when cwd is / (systemd-like). Path resolution must not depend on cwd."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "cwd_test.mp4").write_bytes(b"fake video")
    # Use absolute path for recordings_dir, simulate systemd cwd
    monkeypatch.chdir("/")
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir.resolve()))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings/cwd_test.mp4")
    assert r.status_code == 200
    assert r.content == b"fake video"


def test_recordings_path_resolution_absolute(
    store: StateStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API serves from recordings_dir when it is absolute, regardless of cwd."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "abs_test.mp4").write_bytes(b"content")
    monkeypatch.chdir("/tmp")  # Different cwd
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir.resolve()))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings/abs_test.mp4")
    assert r.status_code == 200
    assert r.content == b"content"


def test_get_recordings_list_empty(client: TestClient) -> None:
    """GET /recordings returns empty list when no recordings service."""
    r = client.get("/recordings")
    assert r.status_code == 200
    data = r.json()
    assert data["recordings"] == []
    assert data["recordings_dir"] is None


def test_get_recordings_list_with_files(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /recordings returns list of recordings with metadata."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "2025-03-11_120000_cam.mp4").write_bytes(b"video1")
    (rec_dir / "2025-03-11_120100_cam.mp4").write_bytes(b"video2")
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings")
    assert r.status_code == 200
    data = r.json()
    assert len(data["recordings"]) == 2
    assert data["recordings_dir"] is not None
    filenames = [rec["filename"] for rec in data["recordings"]]
    assert "2025-03-11_120000_cam.mp4" in filenames
    assert "2025-03-11_120100_cam.mp4" in filenames


def test_get_recordings_returns_trigger_session_id_when_meta_exists(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """GET /recordings returns trigger and session_id when recording has .meta file."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "2025-03-11_120000_cam.mp4").write_bytes(b"video")
    (rec_dir / "2025-03-11_120000_cam.mp4.meta").write_text(
        '{"trigger":"auto","session_id":42}', encoding="utf-8"
    )
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings")
    assert r.status_code == 200
    data = r.json()
    assert len(data["recordings"]) == 1
    rec = data["recordings"][0]
    assert rec["trigger"] == "auto"
    assert rec["session_id"] == 42


def test_get_session_recordings_returns_trigger_session_id_when_meta_exists(
    store: StateStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /sessions/{id}/recordings returns trigger and session_id when recording has .meta."""
    import time
    from datetime import datetime, timezone

    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    init_db(str(tmp_path / "test.db"))
    persistence = PersistenceService()
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    time.sleep(1.1)  # Ensure recording timestamp is after session started_at

    now = datetime.now(timezone.utc)
    filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}_cam.mp4"
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / filename).write_bytes(b"video")
    (rec_dir / f"{filename}.meta").write_text(
        '{"trigger":"auto","session_id":' + str(session_id) + "}", encoding="utf-8"
    )

    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(
        create_app(
            store,
            camera_recording_service=camera_svc,
            persistence=persistence,
        )
    )
    r = client.get(f"/sessions/{session_id}/recordings")
    assert r.status_code == 200
    data = r.json()
    assert data["session_resolved"] is True
    assert len(data["recordings"]) == 1
    rec = data["recordings"][0]
    assert rec["trigger"] == "auto"
    assert rec["session_id"] == session_id


def test_delete_recording(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """DELETE /recordings/{filename} removes file and returns ok."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "to_delete.mp4").write_bytes(b"content")
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.delete("/recordings/to_delete.mp4")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert not (rec_dir / "to_delete.mp4").exists()


def test_delete_recording_rejects_path_traversal(
    store: StateStore,
    tmp_path: Path,
) -> None:
    """DELETE /recordings/{filename} rejects path traversal (.. or / in filename)."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.delete("/recordings/foo..bar.mp4")  # ".." in filename triggers rejection
    assert r.status_code == 400


def test_post_camera_ready(client: TestClient) -> None:
    """POST /camera/ready sets and returns camera ready state."""
    r = client.post("/camera/ready", json={"ready": True})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["ready"] is True
    r2 = client.get("/health")
    assert r2.json()["camera_ready"] is True
    r3 = client.post("/camera/ready", json={"ready": False})
    assert r3.json()["ready"] is False


def test_post_live_home_503_when_no_store(store: StateStore) -> None:
    """POST /live/home returns 503 when app_home_store not provided."""
    client = TestClient(create_app(store))
    r = client.post("/live/home", json={"lat": 37.0, "lon": -122.0})
    assert r.status_code == 503


def test_post_live_home_set_lat_lon(store: StateStore) -> None:
    """POST /live/home with lat/lon sets app home override."""
    app_home_store = AppHomeStore()
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={"lat": 37.0, "lon": -122.0})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert app_home_store.get_override() == (37.0, -122.0)


def test_post_live_home_use_current(store: StateStore) -> None:
    """POST /live/home with use_current uses current position from store."""
    app_home_store = AppHomeStore()
    state = AircraftState(
        connected=True,
        heartbeat=1,
        mode="GUIDED",
        lat=37.5,
        lon=-122.5,
        rel_alt_m=100.0,
        heading_deg=90.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=12.5,
        current_a=2.0,
        groundspeed_m_s=10.0,
        airspeed_m_s=12.0,
        timestamp=datetime.now(timezone.utc),
    )
    store.update(state)
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={"use_current": True})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert app_home_store.get_override() == (37.5, -122.5)


def test_post_live_home_use_current_no_state(store: StateStore) -> None:
    """POST /live/home with use_current returns 400 when no telemetry state."""
    app_home_store = AppHomeStore()
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={"use_current": True})
    assert r.status_code == 400


def test_post_live_home_clear(store: StateStore) -> None:
    """POST /live/home with clear=true clears app home override."""
    app_home_store = AppHomeStore()
    app_home_store.set_app_home(37.0, -122.0)
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={"clear": True})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert app_home_store.get_override() == (None, None)


def test_post_live_home_invalid_lat_lon(store: StateStore) -> None:
    """POST /live/home with invalid lat/lon returns 400."""
    app_home_store = AppHomeStore()
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={"lat": 100.0, "lon": -122.0})
    assert r.status_code == 400
    r2 = client.post("/live/home", json={"lat": 37.0, "lon": 200.0})
    assert r2.status_code == 400


def test_post_live_home_empty_body_400(store: StateStore) -> None:
    """POST /live/home with no valid body returns 400."""
    app_home_store = AppHomeStore()
    client = TestClient(create_app(store, app_home_store=app_home_store))
    r = client.post("/live/home", json={})
    assert r.status_code == 400


def test_delete_session_404_when_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /sessions/{sid} returns 404 when session does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        client = TestClient(
            create_app(store, session_ref=[None], persistence=persistence)
        )
        r = client.delete("/sessions/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


def test_delete_session_rejects_active_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /sessions/{sid} returns 400 when deleting the current active session."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "airautomatica.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(path))
        init_db(str(path))
        store = StateStore()
        persistence = PersistenceService()
        session_id = persistence.start_session("mock", "mock")
        assert session_id is not None
        client = TestClient(
            create_app(
                store,
                session_ref=[session_id],
                persistence=persistence,
            )
        )
        r = client.delete(f"/sessions/{session_id}")
        assert r.status_code == 400
        assert "active" in r.json()["detail"].lower()
        assert "stop" in r.json()["detail"].lower()


def test_delete_session_removes_db_and_recordings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DELETE /sessions/{sid} removes session from DB and deletes associated recordings."""
    import time

    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "airautomatica.db"))
    init_db(str(tmp_path / "airautomatica.db"))
    store = StateStore()
    persistence = PersistenceService()
    session_id = persistence.start_session("mock", "mock")
    assert session_id is not None
    time.sleep(2.1)  # Ensure session has duration for recording timestamp
    persistence.end_session(session_id)

    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    session_data = persistence.get_session(session_id)
    assert session_data is not None
    started = session_data["started_at"]
    ended = session_data["ended_at"]
    assert started and ended
    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    mid_dt = start_dt + timedelta(seconds=1)
    filename = f"{mid_dt.strftime('%Y-%m-%d_%H%M%S')}_cam.mp4"
    (rec_dir / filename).write_bytes(b"fake video")
    assert (rec_dir / filename).exists()

    camera_svc = CameraRecordingService(recordings_dir=str(rec_dir))
    client = TestClient(
        create_app(
            store,
            session_ref=[None],
            persistence=persistence,
            camera_recording_service=camera_svc,
        )
    )
    r = client.delete(f"/sessions/{session_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["recordings_deleted"] == 1
    assert data["recordings_failed"] == 0

    assert not (rec_dir / filename).exists()
    assert persistence.get_session(session_id) is None
