"""Tests for Hailo provider object detection."""

from unittest.mock import patch

import pytest

from airautomatica.ai.detection_models import DetectionResult
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
