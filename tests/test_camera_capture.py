"""Tests for backend-neutral still capture (Phase 5)."""

from pathlib import Path
from unittest.mock import patch

from airautomatica.camera import CameraDescriptor, capture_still


def test_capture_still_uses_selector_when_descriptor_not_provided() -> None:
    """capture_still uses CameraSelector when descriptor is None."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB",
        path="/dev/video0",
    )
    fake_jpeg = b"\xff\xd8\xff"
    with patch("airautomatica.camera.capture.CameraSelector") as mock_selector_cls:
        mock_selector = mock_selector_cls.return_value
        mock_selector.resolve.return_value = desc
        with patch(
            "airautomatica.camera.backends.usb.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0})()
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.read_bytes", return_value=fake_jpeg):
                        with patch("pathlib.Path.unlink"):
                            data, err = capture_still()
    assert data == fake_jpeg
    mock_selector.resolve.assert_called_once()
    call_argv = mock_run.call_args[0][0]
    assert "ffmpeg" in call_argv[0] or call_argv[0].endswith("ffmpeg")


def test_capture_still_returns_error_when_no_camera() -> None:
    """capture_still returns (None, error) when selector returns None."""
    with patch("airautomatica.camera.capture.CameraSelector") as mock_selector_cls:
        mock_selector = mock_selector_cls.return_value
        mock_selector.resolve.return_value = None
        data, err = capture_still()
    assert data is None
    assert err is not None
    assert "No camera" in err


def test_capture_still_dispatches_to_csi_when_selector_returns_csi() -> None:
    """capture_still uses CSI backend when descriptor is CSI."""
    desc = CameraDescriptor(
        id="csi:0",
        source_type="csi",
        display_name="CSI 0",
        path=None,
    )
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    with patch("airautomatica.camera.capture.CameraSelector") as mock_selector_cls:
        mock_selector = mock_selector_cls.return_value
        mock_selector.resolve.return_value = desc
        with patch(
            "airautomatica.camera.backends.csi.shutil.which",
            return_value="/usr/bin/rpicam-still",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0})()
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.read_bytes", return_value=fake_jpeg):
                        with patch("pathlib.Path.unlink"):
                            data, err = capture_still(descriptor=desc)
    assert data == fake_jpeg
    assert err is None
    call_argv = mock_run.call_args[0][0]
    assert "rpicam-still" in call_argv[0] or call_argv[0].endswith("rpicam-still")
    assert "-c" in call_argv
    assert "0" in call_argv


def test_capture_still_dispatches_to_usb_when_selector_returns_usb() -> None:
    """capture_still uses USB backend when descriptor is USB."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB Webcam",
        path="/dev/video0",
    )
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    with patch(
        "airautomatica.camera.backends.usb.shutil.which",
        return_value="/usr/bin/ffmpeg",
    ):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 0})()
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_bytes", return_value=fake_jpeg):
                    with patch("pathlib.Path.unlink"):
                        data, err = capture_still(descriptor=desc)
    assert data == fake_jpeg
    assert err is None
    call_argv = mock_run.call_args[0][0]
    assert "ffmpeg" in call_argv[0] or call_argv[0].endswith("ffmpeg")
    assert "/dev/video0" in call_argv
    assert "-vframes" in call_argv
    assert "1" in call_argv


def test_capture_still_returns_error_when_csi_tool_missing() -> None:
    """capture_still returns (None, error) when CSI descriptor but rpicam-still missing."""
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
        data, err = capture_still(descriptor=desc)
    assert data is None
    assert err is not None
    assert "not available" in err or "Still capture" in err


def test_capture_still_returns_error_when_usb_ffmpeg_missing() -> None:
    """capture_still returns (None, error) when USB descriptor but ffmpeg missing."""
    desc = CameraDescriptor(
        id="usb:/dev/video0",
        source_type="usb",
        display_name="USB",
        path="/dev/video0",
    )
    with patch(
        "airautomatica.camera.backends.usb._get_ffmpeg",
        return_value=None,
    ):
        data, err = capture_still(descriptor=desc)
    assert data is None
    assert err is not None
    assert "not available" in err or "Still capture" in err


def test_capture_still_returns_error_on_subprocess_failure() -> None:
    """capture_still returns (None, error) when subprocess returns non-zero."""
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
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type(
                "R", (), {"returncode": 1, "stderr": "device busy", "stdout": ""}
            )()
            data, err = capture_still(descriptor=desc)
    assert data is None
    assert err is not None
    assert "failed" in err.lower() or "device busy" in err
