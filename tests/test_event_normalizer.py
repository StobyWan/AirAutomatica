"""Tests for event normalizer."""

from airautomatica.ai.detection_models import Detection, DetectionBBox
from airautomatica.ai.event_normalizer import (
    get_event_type,
    normalize_detections_to_events,
)


def test_get_event_type_person() -> None:
    """person -> person_detected."""
    assert get_event_type("person") == "person_detected"
    assert get_event_type("PERSON") == "person_detected"


def test_get_event_type_vehicle() -> None:
    """car, truck, bus -> vehicle_detected."""
    assert get_event_type("car") == "vehicle_detected"
    assert get_event_type("truck") == "vehicle_detected"
    assert get_event_type("bus") == "vehicle_detected"
    assert get_event_type("VEHICLE") == "vehicle_detected"


def test_get_event_type_aircraft() -> None:
    """airplane -> aircraft_detected."""
    assert get_event_type("airplane") == "aircraft_detected"


def test_get_event_type_unknown() -> None:
    """Unknown label -> object_detected."""
    assert get_event_type("class_99") == "object_detected"
    assert get_event_type("unknown") == "object_detected"


def test_normalize_empty_detections() -> None:
    """Empty list returns object_count with count 0."""
    events = normalize_detections_to_events([])
    assert len(events) == 1
    assert events[0].event_type == "object_count"
    assert events[0].count == 0
    assert events[0].metadata == {"labels": []}


def test_normalize_single_detection() -> None:
    """Single person detection -> person_detected + object_count."""
    bbox = DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4)
    det = Detection(label="person", confidence=0.9, bbox=bbox)
    events = normalize_detections_to_events([det])
    assert len(events) == 2
    assert events[0].event_type == "person_detected"
    assert events[0].label == "person"
    assert events[0].confidence == 0.9
    assert events[0].count == 1
    assert events[1].event_type == "object_count"
    assert events[1].count == 1
    assert events[1].metadata == {"labels": ["person"]}


def test_normalize_aggregates_same_label() -> None:
    """Multiple same detections aggregate count and max confidence."""
    bbox = DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4)
    dets = [
        Detection(label="car", confidence=0.7, bbox=bbox),
        Detection(label="car", confidence=0.9, bbox=bbox),
    ]
    events = normalize_detections_to_events(dets)
    assert len(events) == 2
    assert events[0].event_type == "vehicle_detected"
    assert events[0].label == "car"
    assert events[0].confidence == 0.9
    assert events[0].count == 2
    assert events[1].event_type == "object_count"
    assert events[1].count == 2


def test_normalize_mixed_labels() -> None:
    """Mixed labels produce separate events."""
    bbox = DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4)
    dets = [
        Detection(label="person", confidence=0.91, bbox=bbox),
        Detection(label="car", confidence=0.85, bbox=bbox),
    ]
    events = normalize_detections_to_events(dets)
    assert len(events) == 3
    event_types = {e.event_type for e in events}
    assert "person_detected" in event_types
    assert "vehicle_detected" in event_types
    assert "object_count" in event_types
    obj_count = next(e for e in events if e.event_type == "object_count")
    assert obj_count.count == 2
    assert obj_count.metadata is not None
    assert set(obj_count.metadata["labels"]) == {"person", "car"}
