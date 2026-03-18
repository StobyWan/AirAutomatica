"""Tests for CSI backend (csi_camera_index_args, csi_still_capture_argv)."""

from pathlib import Path
from unittest.mock import patch

from airautomatica.camera import CameraDescriptor
from airautomatica.camera.backends.csi import (
    csi_camera_index_args,
    csi_still_capture_argv,
)


def test_csi_camera_index_args_none() -> None:
    """None descriptor returns empty list (preserve default behavior)."""
    assert csi_camera_index_args(None) == []


def test_csi_camera_index_args_csi0() -> None:
    """csi:0 returns -c 0."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI Camera 0",
        path=None,
    )
    assert csi_camera_index_args(desc) == ["-c", "0"]


def test_csi_camera_index_args_csi1() -> None:
    """csi:1 returns -c 1."""
    desc = CameraDescriptor(
        id="csi:1",
        source_type="csi",
        display_name="CSI Camera 1",
        path=None,
    )
    assert csi_camera_index_args(desc) == ["-c", "1"]


def test_csi_camera_index_args_usb_returns_empty() -> None:
    """USB descriptor returns empty (no -c for rpicam)."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/video0",
    )
    assert csi_camera_index_args(desc) == []


def test_csi_camera_index_args_invalid_id_returns_empty() -> None:
    """Malformed csi id returns empty."""
    desc = CameraDescriptor(
        id="csi:bad",
        source_type="csi",
        display_name="CSI",
        path=None,
    )
    assert csi_camera_index_args(desc) == []


def test_csi_still_capture_argv_none() -> None:
    """csi_still_capture_argv returns None for None descriptor."""
    assert csi_still_capture_argv(None, Path("/tmp/out.jpg")) is None


def test_csi_still_capture_argv_usb_returns_none() -> None:
    """csi_still_capture_argv returns None for USB descriptor."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB",
        path="/dev/video0",
    )
    assert csi_still_capture_argv(desc, Path("/tmp/out.jpg")) is None


def test_csi_still_capture_argv_returns_none_when_rpicam_missing() -> None:
    """csi_still_capture_argv returns None when rpicam-still not found."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    with patch("airautomatica.camera.backends.csi.shutil.which", return_value=None):
        assert csi_still_capture_argv(desc, Path("/tmp/out.jpg")) is None


def test_csi_still_capture_argv_builds_argv_for_csi0() -> None:
    """csi_still_capture_argv builds rpicam-still args for csi:0."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    out = Path("/tmp/still.jpg")
    with patch(
        "airautomatica.camera.backends.csi.shutil.which",
        return_value="/usr/bin/rpicam-still",
    ):
        argv = csi_still_capture_argv(desc, out)
    assert argv is not None
    assert argv[0].endswith("rpicam-still")
    assert "-c" in argv
    assert "0" in argv
    assert "-t" in argv
    assert "1" in argv
    assert "--immediate" in argv
    assert "-n" in argv
    assert "-o" in argv
    assert str(out) in argv


def test_csi_still_capture_argv_includes_camera_index_for_csi1() -> None:
    """csi_still_capture_argv includes -c 1 for csi:1."""
    desc = CameraDescriptor(
        id="csi:1",
        source_type="csi",
        display_name="CSI 1",
        path=None,
    )
    out = Path("/tmp/still.jpg")
    with patch(
        "airautomatica.camera.backends.csi.shutil.which",
        return_value="/usr/bin/rpicam-still",
    ):
        argv = csi_still_capture_argv(desc, out)
    assert argv is not None
    idx = argv.index("-c")
    assert argv[idx + 1] == "1"
