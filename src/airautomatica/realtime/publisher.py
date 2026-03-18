"""Background publisher that emits Socket.IO events for the dashboard."""

import asyncio
import logging
from collections import deque
from typing import TYPE_CHECKING, Optional

import socketio

from airautomatica.ai.ollama_tasks import get_telemetry_summary_counts
from airautomatica.camera.registry import CameraRegistry
from airautomatica.camera.selector import CameraSelector
from airautomatica.camera.status import get_camera_status_summary
from airautomatica.config import (
    get_camera_recording_mode,
    get_sqlite_db_path,
    get_telemetry_backend,
)
from airautomatica.db.base import get_engine, get_last_init_error
from airautomatica.models.state import AircraftState, nan_to_none
from airautomatica.services.camera_ready_state import get as get_camera_ready
from airautomatica.services.mission_logic import get_perception_counts
from airautomatica.system.observability import get_ai_observability_rates
from airautomatica.system.thermal import get_thermal_state, read_temperature_c

if TYPE_CHECKING:
    from airautomatica.services.app_home_store import AppHomeStore
    from airautomatica.services.camera_recording import CameraRecordingService
    from airautomatica.services.persistence import PersistenceService
    from airautomatica.services.state_store import StateStore

logger = logging.getLogger(__name__)

_HEARTBEAT_BUFFER_MAX = 60
_THROTTLE_INTERVAL = 5


def _build_health_payload(
    state: Optional[AircraftState],
    ai_mode: str,
    telemetry_backend: str,
    session_id: Optional[int],
    persistence_enabled: bool,
    last_persistence_error: Optional[str],
    capabilities: Optional[dict] = None,
) -> dict:
    """Build null-safe health payload for Socket.IO."""
    payload: dict = {
        "status": "ok",
        "ai_mode": ai_mode,
        "telemetry_backend": telemetry_backend,
        "session_id": session_id,
        "thermal": {
            "temp_c": read_temperature_c(),
            "state": get_thermal_state().value,
        },
        "persistence": {
            "persistence_enabled": persistence_enabled,
            "sqlite_db_path": get_sqlite_db_path() if persistence_enabled else None,
            "last_persistence_error": last_persistence_error,
        },
    }
    if state is None:
        payload["telemetry"] = {
            "telemetry_status": "disconnected",
            "connected": False,
            "reconnect_count": 0,
            "last_disconnect_reason": None,
            "heartbeat_age_s": None,
        }
    else:
        payload["telemetry"] = {
            "telemetry_status": state.telemetry_status,
            "connected": state.connected,
            "reconnect_count": state.reconnect_count,
            "last_disconnect_reason": state.last_disconnect_reason,
            "heartbeat_age_s": nan_to_none(state.heartbeat_age_s),
            "last_heartbeat_at": (
                state.last_heartbeat_at.isoformat() if state.last_heartbeat_at else None
            ),
        }
    if capabilities is not None:
        payload["capabilities"] = capabilities
    perception_counts = get_perception_counts()
    telemetry_summary_counts = get_telemetry_summary_counts()
    payload["perception_counts"] = perception_counts
    payload["telemetry_summary_counts"] = telemetry_summary_counts
    rates = get_ai_observability_rates(perception_counts, telemetry_summary_counts)
    payload["perception_acceptance_rate"] = rates["perception_acceptance_rate"]
    payload["telemetry_meaningful_rate"] = rates["telemetry_meaningful_rate"]
    return payload


def _build_state_payload(
    state: Optional[AircraftState],
    app_home_store: Optional["AppHomeStore"] = None,
) -> dict:
    """Build state payload. Reuses AircraftState.to_dict(). Applies app home override when set."""
    if state is None:
        return {"state": None, "app_home_source": "fallback"}
    state_dict = state.to_dict()
    if app_home_store is not None and app_home_store.has_override():
        lat, lon = app_home_store.get_override()
        if lat is not None and lon is not None:
            state_dict["home_lat"] = lat
            state_dict["home_lon"] = lon
            return {"state": state_dict, "app_home_source": "manual_live"}
    if state.home_lat is not None and state.home_lon is not None:
        return {"state": state_dict, "app_home_source": "autopilot"}
    return {"state": state_dict, "app_home_source": "fallback"}


def _build_detections_payload(
    detections: list[dict],
    session_id: Optional[int],
) -> dict:
    """Build detections payload."""
    return {"detections": detections, "session_id": session_id}


def _build_sessions_payload(
    sessions: list[dict],
    current_session_id: Optional[int],
) -> dict:
    """Build sessions payload."""
    return {"sessions": sessions, "current_session_id": current_session_id}


class DashboardPublisher:
    """Emits health, state, and detections updates to Socket.IO clients."""

    def __init__(
        self,
        store: "StateStore",
        persistence: Optional["PersistenceService"],
        session_ref: list[int | None],
        ai_mode: str,
        telemetry_backend: str,
        sio: socketio.AsyncServer,
        interval_sec: float = 1.0,
        camera_recording_service: Optional["CameraRecordingService"] = None,
        app_home_store: Optional["AppHomeStore"] = None,
    ) -> None:
        self._store = store
        self._persistence = persistence
        self._session_ref = session_ref
        self._ai_mode = ai_mode
        self._telemetry_backend = telemetry_backend
        self._sio = sio
        self._interval_sec = interval_sec
        self._camera_recording_service = camera_recording_service
        self._app_home_store = app_home_store
        self._heartbeat_buffer: deque[dict] = deque(maxlen=_HEARTBEAT_BUFFER_MAX)
        self._loop_count = 0
        self._camera_registry = CameraRegistry() if camera_recording_service else None
        self._camera_selector = (
            CameraSelector(registry=self._camera_registry)
            if self._camera_registry
            else None
        )

    async def run(self) -> None:
        """Emit updates at interval. Runs until cancelled."""
        while True:
            try:
                state = self._store.get()
                persistence_enabled = get_engine() is not None
                last_error = (
                    get_last_init_error()
                    if not persistence_enabled
                    else (
                        self._persistence.get_last_persistence_error()
                        if self._persistence is not None
                        else None
                    )
                )

                # Update heartbeat buffer for sparklines
                if state is not None:
                    hb = nan_to_none(state.heartbeat_age_s)
                    if hb is not None:
                        self._heartbeat_buffer.append(
                            {
                                "timestamp": state.timestamp.isoformat(),
                                "heartbeat_age_s": hb,
                            }
                        )

                session_id = self._session_ref[0] if self._session_ref else None
                caps = self._store.get_capabilities()
                caps_dict = caps.to_dict() if caps is not None else None
                health = _build_health_payload(
                    state,
                    self._ai_mode,
                    get_telemetry_backend(),
                    session_id,
                    persistence_enabled,
                    last_error,
                    capabilities=caps_dict,
                )
                health["camera_ready"] = get_camera_ready()
                if self._camera_recording_service is not None:
                    rec_state = self._camera_recording_service.get_recording_state()
                    health["camera_recording_available"] = (
                        self._camera_recording_service.is_available()
                    )
                    health["camera_recording_mode"] = get_camera_recording_mode()
                    health["camera_recording"] = rec_state.recording
                    health["camera_recording_file"] = rec_state.output_file
                    health["camera_recording_last_file"] = rec_state.last_recorded_file
                    health["recordings_dir"] = (
                        self._camera_recording_service.recordings_dir
                    )
                    health["camera_recording_started_at"] = (
                        rec_state.started_at.isoformat()
                        if rec_state.started_at
                        else None
                    )
                    if (
                        self._camera_registry is not None
                        and self._camera_selector is not None
                    ):
                        status = get_camera_status_summary(
                            self._camera_registry,
                            self._camera_selector,
                            self._camera_recording_service,
                            refresh_registry=False,
                        )
                        health["active_camera_id"] = status.get("active_camera_id")
                        health["active_camera_label"] = status.get(
                            "active_camera_label"
                        )
                        health["active_camera_kind"] = status.get("active_camera_kind")
                        health["still_capture_available"] = status.get(
                            "still_capture_available", False
                        )
                        health["configured_source_id"] = status.get(
                            "configured_source_id", ""
                        )
                await self._sio.emit("health_update", health)

                state_payload = _build_state_payload(state, self._app_home_store)
                await self._sio.emit("state_update", state_payload)

                detections: list[dict] = []
                if self._persistence is not None and session_id is not None:
                    detections = self._persistence.get_recent_detections(
                        session_id, limit=20
                    )
                det_payload = _build_detections_payload(detections, session_id)
                await self._sio.emit("detections_update", det_payload)

                sessions: list[dict] = []
                if self._persistence is not None:
                    sessions = self._persistence.get_recent_sessions(
                        limit=10, include_detection_count=True
                    )
                sessions_payload = _build_sessions_payload(sessions, session_id)
                await self._sio.emit("sessions_update", sessions_payload)

                # Throttled events (every 5s)
                self._loop_count += 1
                if self._loop_count % _THROTTLE_INTERVAL == 0:
                    events: list[dict] = []
                    if self._persistence is not None:
                        events = self._persistence.get_recent_system_events(limit=30)
                    await self._sio.emit("events_update", {"events": events})

                    path: list[dict] = []
                    current_position = None
                    if self._persistence is not None and session_id is not None:
                        path = self._persistence.get_session_path(session_id, limit=500)
                    if state is not None:
                        lat = nan_to_none(state.lat)
                        lon = nan_to_none(state.lon)
                        if lat is not None and lon is not None:
                            current_position = {
                                "lat": lat,
                                "lon": lon,
                                "rel_alt_m": nan_to_none(state.rel_alt_m),
                            }
                    path_payload = {
                        "path": path,
                        "current_position": current_position,
                        "detections": detections,
                        "session_id": session_id,
                    }
                    await self._sio.emit("telemetry_path_update", path_payload)

                    # Trends: telemetry from DB + heartbeat from buffer
                    voltage: list[float] = []
                    rel_alt_m_list: list[float] = []
                    groundspeed_m_s: list[float] = []
                    heartbeat_age_s: list[float] = []
                    if self._persistence is not None and session_id is not None:
                        samples = self._persistence.get_recent_telemetry_samples(
                            session_id, limit=30
                        )
                        # Samples are newest first; reverse for oldest-first
                        for s in reversed(samples):
                            v = s.get("voltage_v")
                            voltage.append(v if v is not None else 0.0)
                            a = s.get("rel_alt_m")
                            rel_alt_m_list.append(a if a is not None else 0.0)
                            g = s.get("groundspeed_m_s")
                            groundspeed_m_s.append(g if g is not None else 0.0)
                            hb = s.get("heartbeat_age_s")
                            heartbeat_age_s.append(hb if hb is not None else 0.0)
                    if not heartbeat_age_s:
                        hb_list = list(self._heartbeat_buffer)[-30:]
                        for h in reversed(hb_list):
                            heartbeat_age_s.append(h["heartbeat_age_s"])
                    trends_payload = {
                        "voltage": voltage,
                        "rel_alt_m": rel_alt_m_list,
                        "groundspeed_m_s": groundspeed_m_s,
                        "heartbeat_age_s": heartbeat_age_s,
                    }
                    await self._sio.emit("trends_update", trends_payload)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Dashboard publisher error: %s", e)

            await asyncio.sleep(self._interval_sec)


def _ports_fingerprint(
    ports: list[dict],
) -> tuple[tuple[str, str, bool, str | None], ...]:
    """Fingerprint for duplicate detection. Returns comparable tuple."""
    return tuple(
        (
            p.get("path", ""),
            p.get("status", ""),
            p.get("mavlink_active", False),
            p.get("autopilot"),
        )
        for p in ports
    )


class PortsPublisher:
    """Emits ports_update via Socket.IO when port list/status changes. Lightweight scan loop."""

    def __init__(
        self,
        sio: socketio.AsyncServer,
        interval_sec: float = 15.0,
    ) -> None:
        self._sio = sio
        self._interval_sec = interval_sec
        self._last_fingerprint: tuple[tuple[str, str, bool, str | None], ...] | None = (
            None
        )

    async def run(self) -> None:
        """Scan ports at interval, emit only when changed. Runs until cancelled."""
        while True:
            try:
                ports = await asyncio.to_thread(_list_ports_safe)
                payload = {
                    "ports": [
                        {
                            "path": p.path,
                            "mavlink_active": p.mavlink_active,
                            "autopilot": p.autopilot,
                            "baud": p.baud,
                            "status": p.status,
                        }
                        for p in ports
                    ]
                }
                fingerprint = _ports_fingerprint(payload["ports"])
                if self._last_fingerprint != fingerprint:
                    self._last_fingerprint = fingerprint
                    await self._sio.emit("ports_update", payload)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Ports publisher error: %s", e)

            await asyncio.sleep(self._interval_sec)


def _list_ports_safe() -> list:
    """Call list_ports_with_status in thread. Lazy import to avoid pymavlink at startup."""
    from airautomatica.telemetry.detector import list_ports_with_status

    return list(list_ports_with_status())
