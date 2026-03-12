"""Connection and session state for UX flow. v1: explicit session creation only."""

from enum import Enum


class ConnectionState(str, Enum):
    """Connection/setup screen state."""

    SETUP = "setup"  # Landing; no mode selected
    DETECTING = "detecting"  # Auto-detect in progress
    NOT_DETECTED = "not_detected"  # Detection completed, nothing found
    CONNECTED_ARDUPILOT = "connected_ardupilot"
    CONNECTED_INAV = "connected_inav"
    MOCK_IDLE = "mock_idle"


class SessionState(str, Enum):
    """Session lifecycle (independent of connection)."""

    NONE = "none"  # No session; user must click Start
    ACTIVE = "active"  # Session running
    STOPPED = "stopped"  # Session ended


class ConnectionMode(str, Enum):
    """User-facing mode choices."""

    MOCK = "mock"
    ARDUPILOT = "ardupilot"
    INAV = "inav"
