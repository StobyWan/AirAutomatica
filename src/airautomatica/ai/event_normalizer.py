"""Normalize raw detections into compact, app-friendly events."""

from dataclasses import dataclass
from typing import Any

from airautomatica.ai.detection_models import Detection

# Map raw COCO/YOLO labels to canonical event types.
# Labels not in this map are emitted as "object_detected" with label in metadata.
# Includes mission logic labels (PERSON, VEHICLE, etc.) - normalized to lowercase for lookup.
_LABEL_TO_EVENT: dict[str, str] = {
    "person": "person_detected",
    "vehicle": "vehicle_detected",
    "ground_vehicle": "vehicle_detected",
    "aircraft": "aircraft_detected",
    "building": "object_detected",
    "tree": "object_detected",
    "road": "object_detected",
    "obstacle": "object_detected",
    "tower": "object_detected",
    "pole": "object_detected",
    "target": "object_detected",
    "water": "object_detected",
    "structure": "object_detected",
    "bicycle": "vehicle_detected",
    "car": "vehicle_detected",
    "motorcycle": "vehicle_detected",
    "airplane": "aircraft_detected",
    "bus": "vehicle_detected",
    "train": "vehicle_detected",
    "truck": "vehicle_detected",
    "boat": "vehicle_detected",
    "bird": "object_detected",
    "cat": "object_detected",
    "dog": "object_detected",
    "horse": "object_detected",
    "sheep": "object_detected",
    "cow": "object_detected",
    "elephant": "object_detected",
    "bear": "object_detected",
    "zebra": "object_detected",
    "giraffe": "object_detected",
    "traffic light": "object_detected",
    "fire hydrant": "object_detected",
    "stop sign": "object_detected",
    "parking meter": "object_detected",
    "bench": "object_detected",
    "chair": "object_detected",
    "couch": "object_detected",
    "potted plant": "object_detected",
    "bed": "object_detected",
    "dining table": "object_detected",
    "toilet": "object_detected",
    "tv": "object_detected",
    "laptop": "object_detected",
    "mouse": "object_detected",
    "remote": "object_detected",
    "keyboard": "object_detected",
    "cell phone": "object_detected",
    "microwave": "object_detected",
    "oven": "object_detected",
    "toaster": "object_detected",
    "sink": "object_detected",
    "refrigerator": "object_detected",
    "book": "object_detected",
    "clock": "object_detected",
    "vase": "object_detected",
    "scissors": "object_detected",
    "teddy bear": "object_detected",
    "hair drier": "object_detected",
    "toothbrush": "object_detected",
    "backpack": "object_detected",
    "umbrella": "object_detected",
    "handbag": "object_detected",
    "tie": "object_detected",
    "suitcase": "object_detected",
    "frisbee": "object_detected",
    "skis": "object_detected",
    "snowboard": "object_detected",
    "sports ball": "object_detected",
    "kite": "object_detected",
    "baseball bat": "object_detected",
    "baseball glove": "object_detected",
    "skateboard": "object_detected",
    "surfboard": "object_detected",
    "tennis racket": "object_detected",
    "bottle": "object_detected",
    "wine glass": "object_detected",
    "cup": "object_detected",
    "fork": "object_detected",
    "knife": "object_detected",
    "spoon": "object_detected",
    "bowl": "object_detected",
    "banana": "object_detected",
    "apple": "object_detected",
    "sandwich": "object_detected",
    "orange": "object_detected",
    "broccoli": "object_detected",
    "carrot": "object_detected",
    "hot dog": "object_detected",
    "pizza": "object_detected",
    "donut": "object_detected",
    "cake": "object_detected",
}


@dataclass
class DetectionEvent:
    """Compact event from normalized detection."""

    event_type: str
    label: str
    confidence: float
    count: int = 1
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "event_type": self.event_type,
            "label": self.label,
            "confidence": self.confidence,
            "count": self.count,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d


def _normalize_label(label: str) -> str:
    """Lowercase, strip, collapse spaces."""
    return label.strip().lower().replace("  ", " ")


def get_event_type(label: str) -> str:
    """Map raw label to canonical event type (person_detected, vehicle_detected, etc.)."""
    norm = _normalize_label(label)
    return _LABEL_TO_EVENT.get(norm, "object_detected")


def normalize_detections_to_events(
    detections: list[Detection],
) -> list[DetectionEvent]:
    """Turn raw detections into compact events.

    Returns:
        - One event per unique (event_type, label) with aggregated count and max confidence.
        - One object_count event at the end with total count and label summary.
    """
    if not detections:
        return [
            DetectionEvent(
                event_type="object_count",
                label="",
                confidence=0.0,
                count=0,
                metadata={"labels": []},
            )
        ]

    # Aggregate by (event_type, label): max confidence, sum count
    agg: dict[tuple[str, str], tuple[float, int]] = {}
    for d in detections:
        event_type = get_event_type(d.label)
        key = (event_type, _normalize_label(d.label))
        if key not in agg:
            agg[key] = (d.confidence, 1)
        else:
            old_conf, old_count = agg[key]
            agg[key] = (max(old_conf, d.confidence), old_count + 1)

    events: list[DetectionEvent] = []
    labels_seen: list[str] = []
    for (event_type, label), (confidence, count) in agg.items():
        events.append(
            DetectionEvent(
                event_type=event_type,
                label=label,
                confidence=confidence,
                count=count,
            )
        )
        labels_seen.append(label)

    total = sum(c for _, (_, c) in agg.items())
    events.append(
        DetectionEvent(
            event_type="object_count",
            label="",
            confidence=0.0,
            count=total,
            metadata={"labels": labels_seen},
        )
    )
    return events
