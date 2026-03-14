"""Tests for detection models."""

from airautomatica.ai.detection_models import (
    Detection,
    DetectionBBox,
    DetectionResult,
)


def test_detection_bbox_to_dict() -> None:
    bbox = DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4)
    d = bbox.to_dict()
    assert d["x"] == 0.1
    assert d["y"] == 0.2
    assert d["width"] == 0.3
    assert d["height"] == 0.4


def test_detection_to_dict() -> None:
    bbox = DetectionBBox(x=0.12, y=0.18, width=0.34, height=0.52)
    det = Detection(label="person", confidence=0.91, bbox=bbox, source="camera")
    d = det.to_dict()
    assert d["label"] == "person"
    assert d["confidence"] == 0.91
    assert d["bbox"]["x"] == 0.12
    assert d["source"] == "camera"


def test_detection_result_to_dict() -> None:
    bbox = DetectionBBox(x=0.1, y=0.2, width=0.3, height=0.4)
    det = Detection(label="car", confidence=0.8, bbox=bbox)
    result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="ready",
        structured_output_supported=True,
        detections=[det],
        frame_width=640,
        frame_height=480,
        inference_time_ms=23.4,
        errors=[],
    )
    d = result.to_dict()
    assert d["backend"] == "hailo"
    assert d["model"] == "yolov6n"
    assert d["state"] == "ready"
    assert d["structured_output_supported"] is True
    assert len(d["detections"]) == 1
    assert d["detections"][0]["label"] == "car"
    assert d["frame_width"] == 640
    assert d["inference_time_ms"] == 23.4
    assert d["errors"] == []
