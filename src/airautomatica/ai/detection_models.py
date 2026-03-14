"""Structured detection result contract for AI HAT object detection.

Bounding box coordinates are normalized 0..1 (x, y = top-left; width, height = size).
"""

from dataclasses import dataclass
from typing import Any, Literal

DetectionState = Literal[
    "ready",
    "no_detections",
    "error",
    "disabled",
    "unavailable",
]


@dataclass
class DetectionBBox:
    """Normalized bounding box (0..1). x,y = top-left; width,height = size."""

    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class Detection:
    """Single object detection."""

    label: str
    confidence: float
    bbox: DetectionBBox
    timestamp: str | float | None = None
    source: str = "camera"
    track_id: int | None = None
    frame_id: int | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox.to_dict(),
            "source": self.source,
        }
        if self.timestamp is not None:
            d["timestamp"] = self.timestamp
        if self.track_id is not None:
            d["track_id"] = self.track_id
        if self.frame_id is not None:
            d["frame_id"] = self.frame_id
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class DetectionResult:
    """Result of one-shot object detection."""

    backend: str
    model: str | None
    state: DetectionState
    structured_output_supported: bool
    detections: list[Detection]
    frame_width: int | None
    frame_height: int | None
    inference_time_ms: float | None
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "model": self.model,
            "state": self.state,
            "structured_output_supported": self.structured_output_supported,
            "detections": [d.to_dict() for d in self.detections],
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "inference_time_ms": self.inference_time_ms,
            "errors": self.errors,
        }
