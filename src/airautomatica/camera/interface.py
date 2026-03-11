"""Minimal camera frame provider interface.

Future: Picamera2 / rpicam will implement this.
Used by AiHatAiService when hardware is available.
Do not over-specify yet. Avoid committing to numpy, RGB/BGR, sync/async, or metadata shapes.
"""

# HARDWARE_INTEGRATION: Picamera2 implementation will live here when camera is in hand.

from typing import Protocol, runtime_checkable


@runtime_checkable
class CameraFrameProvider(Protocol):
    """Lightly typed frame provider. get_frame returns a frame or None.

    Implementations (Picamera2, etc.) determine format, shape, and metadata.
    """

    def get_frame(self) -> object | None:
        """Return one frame, or None if unavailable."""
        ...
