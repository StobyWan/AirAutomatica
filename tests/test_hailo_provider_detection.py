"""Tests for Hailo provider object detection."""

from unittest.mock import patch

import pytest

from airautomatica.ai.detection_models import DetectionResult
from airautomatica.ai.hailo_detection_impl import DetectionMode, run_one_shot_detection
from airautomatica.ai.providers.hailo_provider import HailoAiHatProvider


def test_run_object_detection_disabled_when_ai_hat_disabled() -> None:
    with patch(
        "airautomatica.ai.providers.hailo_provider.get_ai_hat_enabled",
        return_value=False,
    ):
        provider = HailoAiHatProvider()
        result = provider.run_object_detection()
    assert isinstance(result, DetectionResult)
    assert result.state == "disabled"
    assert result.detections == []
    assert result.errors == []


def test_run_object_detection_disabled_when_object_detection_disabled() -> None:
    with patch(
        "airautomatica.ai.providers.hailo_provider.get_ai_hat_enabled",
        return_value=True,
    ):
        with patch(
            "airautomatica.ai.providers.hailo_provider.get_ai_hat_object_detection_enabled",
            return_value=False,
        ):
            provider = HailoAiHatProvider()
            result = provider.run_object_detection()
    assert result.state == "disabled"
    assert result.detections == []


def test_run_object_detection_disabled_when_camera_pipeline_disabled() -> None:
    with patch(
        "airautomatica.ai.providers.hailo_provider.get_ai_hat_enabled",
        return_value=True,
    ):
        with patch(
            "airautomatica.ai.providers.hailo_provider.get_ai_hat_object_detection_enabled",
            return_value=True,
        ):
            with patch(
                "airautomatica.ai.providers.hailo_provider.get_ai_hat_camera_pipeline_enabled",
                return_value=False,
            ):
                provider = HailoAiHatProvider()
                result = provider.run_object_detection()
    assert result.state == "disabled"
    assert "Camera pipeline disabled" in result.errors


def test_run_object_detection_unavailable_when_hardware_missing() -> None:
    with patch(
        "airautomatica.ai.providers.hailo_provider.get_ai_hat_enabled",
        return_value=True,
    ):
        with patch(
            "airautomatica.ai.providers.hailo_provider.get_ai_hat_object_detection_enabled",
            return_value=True,
        ):
            with patch(
                "airautomatica.ai.providers.hailo_provider.get_ai_hat_camera_pipeline_enabled",
                return_value=True,
            ):
                with patch(
                    "airautomatica.ai.providers.hailo_provider.get_hailo_status",
                ) as m:
                    m.return_value = type(
                        "R", (), {"available": False, "errors": ["no hardware"]}
                    )()
                    provider = HailoAiHatProvider()
                    result = provider.run_object_detection()
    assert result.state == "unavailable"
    assert result.detections == []


def test_run_object_detection_calls_impl_when_available() -> None:
    fake_result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="no_detections",
        structured_output_supported=True,
        detections=[],
        frame_width=640,
        frame_height=480,
        inference_time_ms=25.0,
        errors=[],
    )

    with patch(
        "airautomatica.ai.providers.hailo_provider.get_ai_hat_enabled",
        return_value=True,
    ):
        with patch(
            "airautomatica.ai.providers.hailo_provider.get_ai_hat_object_detection_enabled",
            return_value=True,
        ):
            with patch(
                "airautomatica.ai.providers.hailo_provider.get_ai_hat_camera_pipeline_enabled",
                return_value=True,
            ):
                with patch(
                    "airautomatica.ai.providers.hailo_provider.get_hailo_status",
                ) as m:
                    m.return_value = type("R", (), {"available": True, "errors": []})()
                    with patch(
                        "airautomatica.ai.providers.hailo_provider.run_one_shot_detection",
                        return_value=fake_result,
                    ):
                        provider = HailoAiHatProvider()
                        result = provider.run_object_detection()
    assert result.state == "no_detections"
    assert result.structured_output_supported is True
    assert result.frame_width == 640


def test_run_one_shot_detection_uses_detection_pipeline_with_one_shot_mode() -> None:
    """One-shot detection uses run_detection_pipeline with ONE_SHOT mode."""
    fake_frame = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    fake_result = DetectionResult(
        backend="hailo",
        model="yolov6n",
        state="no_detections",
        structured_output_supported=True,
        detections=[],
        frame_width=640,
        frame_height=480,
        inference_time_ms=25.0,
        errors=[],
    )
    with patch(
        "airautomatica.ai.hailo_detection_impl.capture_still",
        return_value=(fake_frame, None),
    ):
        with patch(
            "airautomatica.ai.hailo_detection_impl.run_detection_pipeline",
        ) as mock_pipeline:
            mock_pipeline.return_value = (fake_result, True)
            run_one_shot_detection()
    mock_pipeline.assert_called_once()
    args = mock_pipeline.call_args[0]
    assert args[0] == fake_frame
    assert args[1] == DetectionMode.ONE_SHOT


def test_run_one_shot_detection_returns_error_when_capture_fails() -> None:
    """run_one_shot_detection returns error result when capture_still fails."""
    with patch(
        "airautomatica.ai.hailo_detection_impl.capture_still",
        return_value=(None, "No camera available"),
    ):
        result = run_one_shot_detection()
    assert result.state == "error"
    assert result.detections == []
    assert "No camera" in result.errors[0]
