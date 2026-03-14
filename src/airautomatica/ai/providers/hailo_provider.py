"""Hailo AI HAT provider. Status and availability; real one-shot object detection."""

import logging
from typing import Protocol, runtime_checkable

from airautomatica.ai.detection_models import DetectionResult
from airautomatica.ai.hailo_detection import HailoStatusResult, get_hailo_status
from airautomatica.ai.hailo_detection_impl import run_one_shot_detection
from airautomatica.config import (
    get_ai_hat_camera_pipeline_enabled,
    get_ai_hat_enabled,
    get_ai_hat_object_detection_enabled,
)

logger = logging.getLogger(__name__)


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
    """Hailo AI HAT+ (Hailo-8L) provider. Real structured detection via hailo-apps."""

    def get_status(self) -> HailoStatusResult:
        """Return Hailo hardware status."""
        return get_hailo_status()

    def is_available(self) -> bool:
        """True if Hailo device is detected and ready."""
        return get_hailo_status().available

    def run_object_detection(self) -> DetectionResult:
        """Run one-shot object detection. Never raises; returns structured result."""
        if not get_ai_hat_enabled():
            return DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="disabled",
                structured_output_supported=True,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[],
            )
        if not get_ai_hat_object_detection_enabled():
            return DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="disabled",
                structured_output_supported=True,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=[],
            )
        if not get_ai_hat_camera_pipeline_enabled():
            return DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="disabled",
                structured_output_supported=True,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=["Camera pipeline disabled"],
            )
        status = get_hailo_status()
        if not status.available:
            return DetectionResult(
                backend="hailo",
                model="yolov6n",
                state="unavailable",
                structured_output_supported=True,
                detections=[],
                frame_width=None,
                frame_height=None,
                inference_time_ms=None,
                errors=status.errors or ["Hailo hardware not available"],
            )
        logger.info("Running one-shot AI HAT object detection")
        return run_one_shot_detection()
