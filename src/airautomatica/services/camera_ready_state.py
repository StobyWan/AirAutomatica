"""Camera ready state: independent of aircraft armed. UI/UX indicator for 'ready to record'."""

import threading

_ready: bool = False
_lock = threading.Lock()


def get() -> bool:
    """Return current camera ready state."""
    with _lock:
        return _ready


def set_ready(value: bool) -> None:
    """Set camera ready state."""
    global _ready
    with _lock:
        _ready = value
