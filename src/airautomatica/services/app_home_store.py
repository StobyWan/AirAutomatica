"""In-memory store for live app home override. Separate from StateStore.

App home is used for AirAutomatica's distance, bearing, return margin, and UI.
It does not change the flight controller's RTL home.
"""

import threading
from typing import Literal

AppHomeSource = Literal["autopilot", "manual_live", "fallback"]


class AppHomeStore:
    """Thread-safe store for live app home override. Operator intent / app policy."""

    def __init__(self) -> None:
        self._lat: float | None = None
        self._lon: float | None = None
        self._lock = threading.Lock()

    def set_app_home(self, lat: float, lon: float) -> None:
        """Set manual app home override."""
        with self._lock:
            self._lat = lat
            self._lon = lon

    def clear_app_home(self) -> None:
        """Clear manual override. Effective home will revert to autopilot or fallback."""
        with self._lock:
            self._lat = None
            self._lon = None

    def get_override(self) -> tuple[float | None, float | None]:
        """Return (lat, lon) if override set, else (None, None)."""
        with self._lock:
            return (self._lat, self._lon)

    def has_override(self) -> bool:
        """True if manual override is set."""
        with self._lock:
            return self._lat is not None and self._lon is not None
