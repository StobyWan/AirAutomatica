"""Tests for realtime payload builders and publisher."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.realtime.publisher import (
    DashboardPublisher,
    _build_detections_payload,
    _build_health_payload,
    _build_sessions_payload,
    _build_state_payload,
)


def test_health_payload_builder_null_state() -> None:
    """Health payload is null-safe when state is None."""
    payload = _build_health_payload(
        state=None,
        ai_mode="mock",
        telemetry_backend="mock",
        session_id=1,
        persistence_enabled=True,
        last_persistence_error=None,
    )
    assert payload["status"] == "ok"
    assert payload["ai_mode"] == "mock"
    assert payload["telemetry_backend"] == "mock"
    assert payload["session_id"] == 1
    assert payload["telemetry"]["telemetry_status"] == "disconnected"
    assert payload["telemetry"]["connected"] is False
    assert payload["telemetry"]["reconnect_count"] == 0
    assert payload["telemetry"]["last_disconnect_reason"] is None
    assert payload["telemetry"]["heartbeat_age_s"] is None
    assert "perception_counts" in payload
    assert "telemetry_summary_counts" in payload
    assert "perception_acceptance_rate" in payload
    assert "telemetry_meaningful_rate" in payload


def test_health_payload_builder_with_state() -> None:
    """Health payload includes telemetry fields when state exists."""
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
        telemetry_status="connected",
        reconnect_count=2,
        last_disconnect_reason="timeout",
    )
    payload = _build_health_payload(
        state=state,
        ai_mode="mock",
        telemetry_backend="serial",
        session_id=42,
        persistence_enabled=True,
        last_persistence_error=None,
    )
    assert payload["telemetry"]["telemetry_status"] == "connected"
    assert payload["telemetry"]["connected"] is True
    assert payload["telemetry"]["reconnect_count"] == 2
    assert payload["telemetry"]["last_disconnect_reason"] == "timeout"
    assert payload["telemetry"]["heartbeat_age_s"] == 0.5
    assert payload["telemetry"]["last_heartbeat_at"] == now.isoformat()


def test_state_payload_builder_null() -> None:
    """State payload has state=null when no state."""
    payload = _build_state_payload(None)
    assert payload["state"] is None


def test_state_payload_builder_with_state() -> None:
    """State payload reuses AircraftState.to_dict()."""
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
    payload = _build_state_payload(state)
    assert payload["state"] is not None
    assert payload["state"]["mode"] == "GUIDED"
    assert payload["state"]["lat"] == 37.0
    assert payload["state"]["voltage_v"] == 12.5


def test_detections_payload_empty_when_no_persistence() -> None:
    """Detections payload has empty list when session_id is None."""
    payload = _build_detections_payload([], None)
    assert payload["detections"] == []
    assert payload["session_id"] is None


def test_detections_payload_with_detections() -> None:
    """Detections payload includes session_id and detections."""
    detections = [
        {"id": 1, "label": "person", "confidence": 0.9, "summary": "Person detected"},
    ]
    payload = _build_detections_payload(detections, 5)
    assert payload["detections"] == detections
    assert payload["session_id"] == 5


def test_sessions_payload_empty() -> None:
    """Sessions payload has empty list when no sessions."""
    payload = _build_sessions_payload([], None)
    assert payload["sessions"] == []
    assert payload["current_session_id"] is None


def test_sessions_payload_with_sessions() -> None:
    """Sessions payload includes sessions and current_session_id."""
    sessions = [
        {
            "id": 20,
            "started_at": "2025-03-09T18:30:00.000Z",
            "ended_at": None,
            "telemetry_backend": "mock",
            "ai_backend": "mock",
        },
    ]
    payload = _build_sessions_payload(sessions, 20)
    assert payload["sessions"] == sessions
    assert payload["current_session_id"] == 20


def test_health_payload_includes_capabilities_with_firmware_and_profile() -> None:
    """Health payload capabilities include firmware_name and profile_id when provided."""
    capabilities = {
        "firmware_name": "ArduPilot",
        "profile_id": "ardupilot",
        "supports_params_read": True,
        "supports_params_write": True,
        "supports_command_long": True,
        "supports_message_interval": True,
        "supports_missions": True,
        "supports_guided_actions": True,
        "supports_rc_over_mavlink": True,
        "notes": "",
        "downgrade_reasons": ["parameter read probe timeout"],
    }
    payload = _build_health_payload(
        state=None,
        ai_mode="mock",
        telemetry_backend="serial",
        session_id=None,
        persistence_enabled=False,
        last_persistence_error=None,
        capabilities=capabilities,
    )
    assert payload["capabilities"] == capabilities
    assert payload["capabilities"]["firmware_name"] == "ArduPilot"
    assert payload["capabilities"]["profile_id"] == "ardupilot"
    assert payload["capabilities"]["downgrade_reasons"] == [
        "parameter read probe timeout"
    ]
    assert "perception_counts" in payload
    assert "telemetry_summary_counts" in payload
    assert "perception_acceptance_rate" in payload
    assert "telemetry_meaningful_rate" in payload


@pytest.mark.asyncio
async def test_dashboard_publisher_emits_camera_fields_when_service_provided(
    tmp_path,
) -> None:
    """When camera_recording_service is provided, health_update includes camera fields."""
    from airautomatica.services.camera_recording import CameraRecordingService
    from airautomatica.services.state_store import StateStore

    store = StateStore()
    camera_svc = CameraRecordingService(recordings_dir=str(tmp_path / "recordings"))
    emitted: list[tuple[str, dict]] = []

    async def capture_emit(event: str, data: dict) -> None:
        emitted.append((event, data))

    sio = MagicMock()
    sio.emit = AsyncMock(side_effect=capture_emit)
    publisher = DashboardPublisher(
        store,
        persistence=None,
        session_ref=[None],
        ai_mode="mock",
        telemetry_backend="mock",
        sio=sio,
        interval_sec=999.0,
        camera_recording_service=camera_svc,
    )
    task = asyncio.create_task(publisher.run())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    health_emits = [e for e in emitted if e[0] == "health_update"]
    assert len(health_emits) >= 1
    health = health_emits[0][1]
    assert "camera_recording_available" in health
    assert "camera_recording_mode" in health
    assert "camera_recording" in health
    assert "camera_recording_file" in health
    assert "camera_recording_started_at" in health
    assert "active_camera_id" in health
    assert "active_camera_label" in health
    assert "active_camera_kind" in health
    assert "still_capture_available" in health
