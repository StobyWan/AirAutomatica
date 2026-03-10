"""Background publisher that emits Socket.IO events for the dashboard."""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import socketio

from airautomatica.config import get_sqlite_db_path
from airautomatica.db.base import get_engine
from airautomatica.models.state import AircraftState, nan_to_none

if TYPE_CHECKING:
    from airautomatica.services.persistence import PersistenceService
    from airautomatica.services.state_store import StateStore

logger = logging.getLogger(__name__)


def _build_health_payload(
    state: Optional[AircraftState],
    ai_mode: str,
    telemetry_backend: str,
    session_id: Optional[int],
    persistence_enabled: bool,
    last_persistence_error: Optional[str],
) -> dict:
    """Build null-safe health payload for Socket.IO."""
    payload: dict = {
        "status": "ok",
        "ai_mode": ai_mode,
        "telemetry_backend": telemetry_backend,
        "session_id": session_id,
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
        }
    return payload


def _build_state_payload(state: Optional[AircraftState]) -> dict:
    """Build state payload. Reuses AircraftState.to_dict()."""
    return {"state": state.to_dict() if state is not None else None}


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
        session_id: Optional[int],
        ai_mode: str,
        telemetry_backend: str,
        sio: socketio.AsyncServer,
        interval_sec: float = 1.0,
    ) -> None:
        self._store = store
        self._persistence = persistence
        self._session_id = session_id
        self._ai_mode = ai_mode
        self._telemetry_backend = telemetry_backend
        self._sio = sio
        self._interval_sec = interval_sec

    async def run(self) -> None:
        """Emit updates at interval. Runs until cancelled."""
        while True:
            try:
                state = self._store.get()
                persistence_enabled = get_engine() is not None
                last_error = (
                    self._persistence.get_last_persistence_error()
                    if self._persistence is not None
                    else None
                )

                health = _build_health_payload(
                    state,
                    self._ai_mode,
                    self._telemetry_backend,
                    self._session_id,
                    persistence_enabled,
                    last_error,
                )
                await self._sio.emit("health_update", health)

                state_payload = _build_state_payload(state)
                await self._sio.emit("state_update", state_payload)

                detections: list[dict] = []
                if self._persistence is not None and self._session_id is not None:
                    detections = self._persistence.get_recent_detections(
                        self._session_id, limit=20
                    )
                det_payload = _build_detections_payload(detections, self._session_id)
                await self._sio.emit("detections_update", det_payload)

                sessions: list[dict] = []
                if self._persistence is not None:
                    sessions = self._persistence.get_recent_sessions(limit=10)
                sessions_payload = _build_sessions_payload(sessions, self._session_id)
                await self._sio.emit("sessions_update", sessions_payload)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Dashboard publisher error: %s", e)

            await asyncio.sleep(self._interval_sec)
