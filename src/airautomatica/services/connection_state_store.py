"""In-memory store for connection/session UX state. Does NOT hold session_id."""

import threading
from dataclasses import dataclass

from airautomatica.models.connection_state import (
    ConnectionMode,
    ConnectionState,
    SessionState,
)


@dataclass
class DetectionResult:
    """Cached detection result for GET /connection/state."""

    detected: bool
    port: str | None
    baud: int | None
    autopilot: str | None
    message: str
    heartbeat_age_ms: float | None = None


class ConnectionStateStore:
    """Thread-safe store. Holds: connection_state, session_state, mode, detection_result."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection_state = ConnectionState.SETUP
        self._session_state = SessionState.NONE
        self._mode: ConnectionMode | None = None
        self._detection_result: DetectionResult | None = None

    def get_connection_state(self) -> ConnectionState:
        with self._lock:
            return self._connection_state

    def set_connection_state(self, state: ConnectionState) -> None:
        with self._lock:
            self._connection_state = state

    def get_session_state(self) -> SessionState:
        with self._lock:
            return self._session_state

    def set_session_state(self, state: SessionState) -> None:
        with self._lock:
            self._session_state = state

    def get_mode(self) -> ConnectionMode | None:
        with self._lock:
            return self._mode

    def set_mode(self, mode: ConnectionMode | None) -> None:
        with self._lock:
            self._mode = mode

    def get_detection_result(self) -> DetectionResult | None:
        with self._lock:
            return self._detection_result

    def set_detection_result(self, result: DetectionResult | None) -> None:
        with self._lock:
            self._detection_result = result
