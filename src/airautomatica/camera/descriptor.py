"""Camera descriptor and capability model for user-selectable camera sources."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class CameraCapabilities:
    """Minimal capability info for a camera. Supports validation and UI hints."""

    resolutions: tuple[tuple[int, int], ...] = ()
    """Supported (width, height) pairs. Empty if unknown."""

    formats: tuple[str, ...] = ()
    """Supported pixel formats (e.g. MJPEG, YUYV). Empty if unknown."""


SourceType = Literal["csi", "usb", "mock", "file"]


@dataclass
class CameraDescriptor:
    """Identifies a discovered camera for selection and backend routing."""

    id: str
    """Stable identifier: csi:0, csi:1, usb:/dev/video0, mock:test."""

    source_type: SourceType
    """Backend type: csi (libcamera), usb (V4L2), mock, file."""

    display_name: str
    """Human-readable name for UI: CSI Camera 0, USB Webcam (Logitech)."""

    path: str | None = None
    """Device path for USB (/dev/video0); None for CSI (use -c index)."""

    capabilities: CameraCapabilities = field(default_factory=CameraCapabilities)
    """Resolutions, formats. May be empty if unknown."""

    available: bool = True
    """True if the camera can be opened right now."""

    def __post_init__(self) -> None:
        if not self.id or not self.display_name:
            raise ValueError("id and display_name must be non-empty")
