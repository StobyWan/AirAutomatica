"""Hailo AI HAT provider. Status and availability; inference stubs for future integration."""

from typing import Protocol, runtime_checkable

from airautomatica.ai.detection_models import DetectionResult
from airautomatica.ai.hailo_detection import HailoStatusResult, get_hailo_status


@runtime_checkable
class AiHatProvider(Protocol):
    """Protocol for AI HAT hardware providers. Enables future Hailo/other backends."""

    def get_status(self) -> HailoStatusResult:
        """Return current hardware status."""
        ...

    def is_available(self) -> bool:
        """True if hardware is detected and ready."""
        ...

    def run_object_detection(self, *args: object, **kwargs: object) -> DetectionResult:
        """Run object detection on frame. Returns DetectionResult."""
        ...


class HailoAiHatProvider:
    """Hailo AI HAT+ (Hailo-8L) provider. Uses get_hailo_status for detection."""

    def get_status(self) -> HailoStatusResult:
        """Return Hailo hardware status."""
        return get_hailo_status()

    def is_available(self) -> bool:
        """True if Hailo device is detected and ready."""
        return get_hailo_status().available

    def run_object_detection(self, *args: object, **kwargs: object) -> DetectionResult:
        """Run object detection on frame. Stub for future camera integration."""
        status = get_hailo_status()
        return DetectionResult(
            backend="hailo",
            model=None,
            state="unavailable" if not status.available else "error",
            structured_output_supported=False,
            detections=[],
            frame_width=None,
            frame_height=None,
            inference_time_ms=None,
            errors=(
                status.errors
                if status.errors
                else ["Hailo object detection not yet implemented"]
            ),
        )
