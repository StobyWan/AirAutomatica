"""Tests for camera status helper and GET /camera/status endpoint."""

from pathlib import Path
from unittest.mock import patch

import pytest

from airautomatica.camera.descriptor import CameraDescriptor
from airautomatica.camera.registry import CameraRegistry
from airautomatica.camera.selector import CameraSelector
from airautomatica.camera.status import (
    get_camera_status_summary,
    is_still_capture_available,
)


def test_is_still_capture_available_none() -> None:
    """is_still_capture_available returns False for None."""
    assert is_still_capture_available(None) is False


def test_is_still_capture_available_csi_when_rpicam_present() -> None:
    """is_still_capture_available returns True for CSI when rpicam-still found."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    with patch(
        "airautomatica.camera.backends.csi.shutil.which",
        return_value="/usr/bin/rpicam-still",
    ):
        assert is_still_capture_available(desc) is True


def test_is_still_capture_available_csi_when_rpicam_missing() -> None:
    """is_still_capture_available returns False for CSI when rpicam-still missing."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    with patch(
        "airautomatica.camera.backends.csi.shutil.which",
        return_value=None,
    ):
        assert is_still_capture_available(desc) is False


def test_is_still_capture_available_usb_when_ffmpeg_present() -> None:
    """is_still_capture_available returns True for USB when ffmpeg found."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB",
        path="/dev/video0",
    )
    with patch(
        "airautomatica.camera.backends.usb._get_ffmpeg",
        return_value="/usr/bin/ffmpeg",
    ):
        assert is_still_capture_available(desc) is True


def test_get_camera_status_summary_no_cameras() -> None:
    """get_camera_status_summary returns empty cameras when registry has none."""
    registry = CameraRegistry()
    selector = CameraSelector(registry=registry)
    registry._cameras = []
    registry._refreshed = True
    with patch.object(selector, "resolve", return_value=None):
        status = get_camera_status_summary(
            registry, selector, None, refresh_registry=False
        )
    assert status["cameras"] == []
    assert status["active_camera_id"] is None
    assert status["active_camera_label"] is None
    assert status["still_capture_available"] is False


def test_get_camera_status_summary_with_csi_selected() -> None:
    """get_camera_status_summary returns correct fields when CSI camera selected."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI Camera 0",
        path=None,
    )
    registry = CameraRegistry()
    selector = CameraSelector(registry=registry)
    registry._cameras = [desc]
    registry._refreshed = True
    with patch.object(selector, "resolve", return_value=desc):
        with patch(
            "airautomatica.camera.status.is_still_capture_available",
            return_value=True,
        ):
            status = get_camera_status_summary(
                registry, selector, None, refresh_registry=False
            )
    assert status["cameras"] == [
        {
            "id": "csi:0",
            "display_name": "CSI Camera 0",
            "source_type": "csi",
            "is_selected": True,
        }
    ]
    assert status["active_camera_id"] == "csi:0"
    assert status["active_camera_label"] == "CSI Camera 0"
    assert status["active_camera_kind"] == "csi"
    assert status["still_capture_available"] is True
