"""Tests for camera descriptor and registry (Phase 1: CSI discovery)."""

from unittest.mock import patch

import pytest

from airautomatica.camera import CameraDescriptor, CameraRegistry
from airautomatica.camera.registry import _parse_csi_list_cameras_output

_SAMPLE_LIST_CAMERAS = """Available cameras
-----------------
0 : imx477 [4056x3040] (/base/soc/i2c0mux/i2c@1/imx477@1a)
    Modes: 'SRGGB10_CSI2P' : 1332x990 [120.05 fps - (696, 528)/2664x1980 crop]
           'SRGGB12_CSI2P' : 2028x1080 [50.03 fps - (0, 440)/4056x2160 crop]
"""

_SAMPLE_LIST_CAMERAS_TWO = """Available cameras
-----------------
0 : imx477 [4056x3040] (/base/soc/i2c0mux/i2c@1/imx477@1a)
    Modes: 'SRGGB10_CSI2P' : 1332x990 [120.05 fps - (696, 528)/2664x1980 crop]
1 : imx219 [3280x2464] (/base/soc/i2c0mux/i2c@1/imx219@10)
    Modes: 'SRGGB10_CSI2P' : 640x480 [166.67 fps - (0, 0)/640x480 crop]
"""

_SAMPLE_NO_CAMERAS = """No cameras available!
"""


def test_parse_csi_list_cameras_single() -> None:
    """Parse single CSI camera from --list-cameras output."""
    result = _parse_csi_list_cameras_output(_SAMPLE_LIST_CAMERAS)
    assert len(result) == 1
    cam = result[0]
    assert cam.id == "csi:0"
    assert cam.source_type == "csi"
    assert "imx477" in cam.display_name
    assert cam.path is None
    assert cam.available is True
    assert (4056, 3040) in cam.capabilities.resolutions


def test_parse_csi_list_cameras_two() -> None:
    """Parse two CSI cameras from --list-cameras output."""
    result = _parse_csi_list_cameras_output(_SAMPLE_LIST_CAMERAS_TWO)
    assert len(result) == 2
    assert result[0].id == "csi:0"
    assert "imx477" in result[0].display_name
    assert result[1].id == "csi:1"
    assert "imx219" in result[1].display_name


def test_parse_csi_list_cameras_none() -> None:
    """Parse 'No cameras available!' returns empty list."""
    result = _parse_csi_list_cameras_output(_SAMPLE_NO_CAMERAS)
    assert result == []


def test_parse_csi_list_cameras_empty() -> None:
    """Parse empty output returns empty list."""
    result = _parse_csi_list_cameras_output("")
    assert result == []


def test_camera_descriptor_validation() -> None:
    """CameraDescriptor rejects empty id or display_name."""
    with pytest.raises(ValueError):
        CameraDescriptor(id="", source_type="csi", display_name="x")
    with pytest.raises(ValueError):
        CameraDescriptor(id="csi:0", source_type="csi", display_name="")


def test_camera_registry_list_cameras_mocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registry returns CSI cameras when subprocess succeeds."""
    mock_result = type("Result", (), {})()
    mock_result.returncode = 0
    mock_result.stdout = _SAMPLE_LIST_CAMERAS
    mock_result.stderr = ""

    def fake_run(*args: object, **kwargs: object) -> object:
        return mock_result

    with patch(
        "airautomatica.camera.registry._get_csi_command",
        return_value="/usr/bin/rpicam-vid",
    ):
        with patch("subprocess.run", side_effect=fake_run):
            registry = CameraRegistry()
            cameras = registry.list_cameras()
    assert len(cameras) == 1
    assert cameras[0].id == "csi:0"


def test_camera_registry_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry returns empty list when rpicam-vid/libcamera-vid not found."""
    with patch("airautomatica.camera.registry._get_csi_command", return_value=None):
        registry = CameraRegistry()
        cameras = registry.list_cameras()
    assert cameras == []


def test_camera_registry_get_camera(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_camera returns descriptor for known id, None for unknown."""
    mock_result = type("Result", (), {})()
    mock_result.returncode = 0
    mock_result.stdout = _SAMPLE_LIST_CAMERAS
    mock_result.stderr = ""

    with patch(
        "airautomatica.camera.registry._get_csi_command",
        return_value="/usr/bin/rpicam-vid",
    ):
        with patch("subprocess.run", return_value=mock_result):
            registry = CameraRegistry()
            cam = registry.get_camera("csi:0")
    assert cam is not None
    assert cam.id == "csi:0"
    assert registry.get_camera("csi:99") is None


def test_camera_registry_includes_usb_when_discovered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registry returns CSI + USB when both are discovered."""
    mock_result = type("Result", (), {})()
    mock_result.returncode = 0
    mock_result.stdout = _SAMPLE_LIST_CAMERAS
    mock_result.stderr = ""

    v4l2_output = "Logitech C920 (usb-0000:00:1d.0-1.4):\n\t/dev/video1\n"

    def fake_run(cmd, *args, **kwargs):
        if "v4l2-ctl" in str(cmd):
            r = type("Result", (), {})()
            r.returncode = 0
            r.stdout = v4l2_output
            r.stderr = ""
            return r
        return mock_result

    with patch(
        "airautomatica.camera.registry._get_csi_command",
        return_value="/usr/bin/rpicam-vid",
    ):
        with patch(
            "airautomatica.camera.usb_discovery._get_v4l2_ctl",
            return_value="/usr/bin/v4l2-ctl",
        ):
            with patch("pathlib.Path.exists", return_value=False):
                with patch("subprocess.run", side_effect=fake_run):
                    registry = CameraRegistry()
                    cameras = registry.list_cameras()
    assert len(cameras) >= 2
    csi_cams = [c for c in cameras if c.source_type == "csi"]
    usb_cams = [c for c in cameras if c.source_type == "usb"]
    assert len(csi_cams) == 1
    assert len(usb_cams) >= 1
    assert registry.get_camera("usb:/dev/video1") is not None


def test_camera_registry_refresh_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh() updates cameras; list_cameras uses cached result after first refresh."""
    mock_result = type("Result", (), {})()
    mock_result.returncode = 0
    mock_result.stdout = _SAMPLE_LIST_CAMERAS
    mock_result.stderr = ""

    run_calls: list[list[str]] = []

    def capture_run(cmd: list[str], *args: object, **kwargs: object) -> object:
        run_calls.append(cmd)
        return mock_result

    with patch(
        "airautomatica.camera.registry._get_csi_command",
        return_value="/usr/bin/rpicam-vid",
    ):
        with patch("subprocess.run", side_effect=capture_run):
            registry = CameraRegistry()
            _ = registry.list_cameras()
            _ = registry.list_cameras()
    assert len(run_calls) == 1
    assert run_calls[0][0].endswith("rpicam-vid")
    assert "--list-cameras" in run_calls[0]
