"""Thread-safe in-memory state store."""

import threading
from typing import TYPE_CHECKING, Optional

from airautomatica.models.state import AircraftState

if TYPE_CHECKING:
    from airautomatica.telemetry.capabilities import CapabilityInfo


class StateStore:
    """Shared in-memory store for aircraft state. Thread-safe."""

    def __init__(self) -> None:
        self._state: Optional[AircraftState] = None
        self._capability_info: Optional["CapabilityInfo"] = None
        self._lock = threading.Lock()

    def update(self, state: AircraftState) -> None:
        """Replace current state."""
        with self._lock:
            self._state = state

    def get(self) -> Optional[AircraftState]:
        """Return current state or None if never set."""
        with self._lock:
            return self._state

    def set_capabilities(self, info: "CapabilityInfo") -> None:
        """Set capability info (e.g. from MAVLink adapter selection)."""
        with self._lock:
            self._capability_info = info

    def get_capabilities(self) -> Optional["CapabilityInfo"]:
        """Return capability info or None (mock mode has no profile)."""
        with self._lock:
            return self._capability_info
