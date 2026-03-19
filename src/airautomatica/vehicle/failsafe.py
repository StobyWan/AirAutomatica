"""Advisory failsafe for rover control.

Pi-side failsafe is advisory: it stops command forwarding when stale or invalid
input is detected. The authoritative neutral-on-loss and watchdog behavior must
live in the control layer (FC or Arduino).
"""

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT_SEC = 0.5
_last_valid_at: float = 0.0
_lock = Lock()


def on_valid_command() -> None:
    """Record that a valid command was received."""
    global _last_valid_at
    with _lock:
        _last_valid_at = time.monotonic()


def is_stale() -> bool:
    """True if no valid command received within timeout. Advisory: bridge should stop forwarding."""
    with _lock:
        elapsed = time.monotonic() - _last_valid_at
        return elapsed > COMMAND_TIMEOUT_SEC


def reset() -> None:
    """Reset failsafe state."""
    global _last_valid_at
    with _lock:
        _last_valid_at = 0.0
