"""Tests for USB camera discovery and backend (Phase 4)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from airautomatica.camera import CameraDescriptor
from airautomatica.camera.backends.usb import (
    usb_preview_argv,
    usb_recording_argv,
    usb_still_capture_argv,
)
from airautomatica.camera.usb_discovery import (
    _parse_v4l2_list_devices,
    discover_usb_cameras,
)

_SAMPLE_V4L2_OUTPUT = """Integrated Camera (usb-0000:00:1a.0-1.6):
	/dev/video0

Logitech Webcam C920 (usb-0000:00:1d.0-1.4):
	/dev/video1
	/dev/video2

bcm2835-codec-decode (platform:bcm2835-codec-decode):
	/dev/video10
"""


def test_parse_v4l2_list_devices_usb_only() -> None:
    """Parse v4l2 output returns only USB devices (bus-info contains usb)."""
    result = _parse_v4l2_list_devices(_SAMPLE_V4L2_OUTPUT)
    assert len(result) == 2
    assert result[0] == ("Integrated Camera", "/dev/video0")
    assert result[1] == ("Logitech Webcam C920", "/dev/video1")


def test_parse_v4l2_list_devices_empty() -> None:
    """Empty output returns empty list."""
    assert _parse_v4l2_list_devices("") == []


def test_parse_v4l2_list_devices_platform_excluded() -> None:
    """Platform devices are excluded."""
    result = _parse_v4l2_list_devices(_SAMPLE_V4L2_OUTPUT)
    assert not any("/dev/video10" in p for (_, p) in result)


def test_discover_usb_cameras_mocked() -> None:
    """discover_usb_cameras returns USB descriptors from v4l2-ctl output."""
    mock_result = type("Result", (), {})()
    mock_result.returncode = 0
    mock_result.stdout = _SAMPLE_V4L2_OUTPUT
    mock_result.stderr = ""

    with patch("pathlib.Path.exists", return_value=False):
        with patch("subprocess.run", return_value=mock_result):
            with patch(
                "airautomatica.camera.usb_discovery._get_v4l2_ctl",
                return_value="/usr/bin/v4l2-ctl",
            ):
                cameras = discover_usb_cameras()
    assert len(cameras) >= 2
    ids = [c.id for c in cameras]
    assert any("usb:/dev/video0" in id or id == "usb:/dev/video0" for id in ids)
    assert all(c.source_type == "usb" for c in cameras)
    assert all(c.path is not None for c in cameras)


def test_usb_preview_argv_returns_none_for_csi() -> None:
    """usb_preview_argv returns None for CSI descriptor."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI Camera 0",
        path=None,
    )
    assert usb_preview_argv(desc) is None


def test_usb_preview_argv_returns_none_for_none() -> None:
    """usb_preview_argv returns None for None."""
    assert usb_preview_argv(None) is None


def test_usb_preview_argv_builds_argv_for_usb() -> None:
    """usb_preview_argv builds ffmpeg v4l2 args for USB descriptor."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/video0",
    )
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        argv = usb_preview_argv(desc)
    assert argv is not None
    assert argv[0].endswith("ffmpeg")
    assert "-f" in argv
    assert "v4l2" in argv
    assert "-i" in argv
    assert "/dev/video0" in argv
    assert "mjpeg" in argv
    assert "pipe:1" in argv


def test_usb_preview_argv_returns_none_when_ffmpeg_missing() -> None:
    """usb_preview_argv returns None when ffmpeg not found."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/video0",
    )
    with patch("shutil.which", return_value=None):
        assert usb_preview_argv(desc) is None


def test_usb_recording_argv_builds_argv_for_usb() -> None:
    """usb_recording_argv builds ffmpeg v4l2 recording args."""
    desc = CameraDescriptor(
        id="usb:/dev/v4l/by-id/usb-Company_Product-video-index0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/v4l/by-id/usb-Company_Product-video-index0",
    )
    output = Path("/tmp/rec.mp4")
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        argv = usb_recording_argv(desc, output)
    assert argv is not None
    assert "-f" in argv
    assert "v4l2" in argv
    assert "/dev/v4l/by-id/usb-Company_Product-video-index0" in argv
    assert "libx264" in argv
    assert str(output) in argv


def test_usb_still_capture_argv_returns_none_for_csi() -> None:
    """usb_still_capture_argv returns None for CSI descriptor."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    assert usb_still_capture_argv(desc, Path("/tmp/out.jpg")) is None


def test_usb_still_capture_argv_returns_none_for_none() -> None:
    """usb_still_capture_argv returns None for None."""
    assert usb_still_capture_argv(None, Path("/tmp/out.jpg")) is None


def test_usb_still_capture_argv_returns_none_when_ffmpeg_missing() -> None:
    """usb_still_capture_argv returns None when ffmpeg not found."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB",
        path="/dev/video0",
    )
    with patch("airautomatica.camera.backends.usb._get_ffmpeg", return_value=None):
        assert usb_still_capture_argv(desc, Path("/tmp/out.jpg")) is None


def test_usb_still_capture_argv_builds_argv_for_usb() -> None:
    """usb_still_capture_argv builds ffmpeg v4l2 single-frame args."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/video0",
    )
    out = Path("/tmp/still.jpg")
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        argv = usb_still_capture_argv(desc, out)
    assert argv is not None
    assert argv[0].endswith("ffmpeg")
    assert "-f" in argv
    assert "v4l2" in argv
    assert "-i" in argv
    assert "/dev/video0" in argv
    assert "-vframes" in argv
    assert "1" in argv
    assert "-f" in argv
    assert "image2" in argv
    assert str(out) in argv
