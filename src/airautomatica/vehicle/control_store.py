"""In-memory store for the latest validated rover control message.

The bridge (Phase 3) reads from this store to send commands to the FC/Arduino.
"""

from threading import Lock
from typing import Optional

from airautomatica.vehicle.control import RoverControlMessage, validate_and_normalize

_lock = Lock()
_last_control: Optional[RoverControlMessage] = None


def update_control(raw: dict) -> None:
    """Update the store with a validated control message. Invalid messages are ignored."""
    global _last_control
    from airautomatica.vehicle.failsafe import on_valid_command

    msg = validate_and_normalize(raw)
    if msg is not None:
        on_valid_command()
        with _lock:
            _last_control = msg


def get_last_control() -> Optional[RoverControlMessage]:
    """Return the latest validated control message, or None."""
    with _lock:
        return _last_control


def clear_control() -> None:
    """Clear the stored control."""
    global _last_control
    with _lock:
        _last_control = None
