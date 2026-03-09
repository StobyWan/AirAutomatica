"""Thread-safe in-memory state store."""

import threading
from typing import Optional

from airautomatica.models.state import AircraftState


class StateStore:
    """Shared in-memory store for aircraft state. Thread-safe."""

    def __init__(self) -> None:
        self._state: Optional[AircraftState] = None
        self._lock = threading.Lock()

    def update(self, state: AircraftState) -> None:
        """Replace current state."""
        with self._lock:
            self._state = state

    def get(self) -> Optional[AircraftState]:
        """Return current state or None if never set."""
        with self._lock:
            return self._state
