"""Tests for camera selector and config integration (Phase 2)."""

from unittest.mock import patch

import pytest

from airautomatica.camera import CameraDescriptor, CameraRegistry, CameraSelector
from airautomatica.config import get_camera_source_auto_fallback, get_camera_source_id


def _make_csi_descriptor(index: int, model: str = "imx477") -> CameraDescriptor:
    return CameraDescriptor(
        id=f"csi:{index}",
        source_type="csi",
        display_name=f"CSI Camera {index} ({model})",
        path=None,
        available=True,
    )


def test_selector_auto_when_source_id_empty() -> None:
    """When CAMERA_SOURCE_ID is empty, selector returns first available."""
    cam0 = _make_csi_descriptor(0)
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = [cam0]
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=True,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is not None
    assert result.id == "csi:0"


def test_selector_auto_when_source_id_missing() -> None:
    """When CAMERA_SOURCE_ID is effectively missing (whitespace), treat as auto."""
    cam0 = _make_csi_descriptor(0)
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = [cam0]
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="   ",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=True,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is not None
    assert result.id == "csi:0"


def test_selector_returns_selected_when_found() -> None:
    """When CAMERA_SOURCE_ID is set and camera exists, return that descriptor."""
    cam0 = _make_csi_descriptor(0)
    cam1 = _make_csi_descriptor(1, "imx219")
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = [cam0, cam1]
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="csi:1",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=False,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is not None
    assert result.id == "csi:1"
    assert "imx219" in result.display_name


def test_selector_fallback_when_selected_not_found() -> None:
    """When selected not found and auto_fallback=1, return first available."""
    cam0 = _make_csi_descriptor(0)
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = [cam0]
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="csi:99",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=True,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is not None
    assert result.id == "csi:0"


def test_selector_none_when_selected_not_found_no_fallback() -> None:
    """When selected not found and auto_fallback=0, return None."""
    cam0 = _make_csi_descriptor(0)
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = [cam0]
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="usb:/dev/video99",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=False,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is None


def test_selector_none_when_no_cameras() -> None:
    """When no cameras discovered, return None."""
    mock_registry = CameraRegistry.__new__(CameraRegistry)
    mock_registry._cameras = []
    mock_registry._refreshed = True

    with patch(
        "airautomatica.camera.selector.get_camera_source_id",
        return_value="",
    ):
        with patch(
            "airautomatica.camera.selector.get_camera_source_auto_fallback",
            return_value=True,
        ):
            selector = CameraSelector(registry=mock_registry)
            result = selector.resolve()
    assert result is None


def test_get_camera_source_id_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_camera_source_id returns empty string when unset (migration default)."""
    monkeypatch.delenv("CAMERA_SOURCE_ID", raising=False)
    with patch(
        "airautomatica.settings.get_raw_settings",
        return_value={"CAMERA_SOURCE_ID": ""},
    ):
        assert get_camera_source_id() == ""


def test_get_camera_source_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_camera_source_id returns env value when set."""
    monkeypatch.setenv("CAMERA_SOURCE_ID", "csi:1")
    with patch(
        "airautomatica.settings.get_raw_settings",
        return_value={"CAMERA_SOURCE_ID": "csi:1"},
    ):
        result = get_camera_source_id()
    assert result == "csi:1"


def test_get_camera_source_auto_fallback_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_camera_source_auto_fallback returns True when unset (default)."""
    monkeypatch.delenv("CAMERA_SOURCE_AUTO_FALLBACK", raising=False)
    with patch(
        "airautomatica.settings.get_raw_settings",
        return_value={"CAMERA_SOURCE_AUTO_FALLBACK": "1"},
    ):
        assert get_camera_source_auto_fallback() is True


def test_get_camera_source_auto_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_camera_source_auto_fallback returns False when set to 0."""
    monkeypatch.setenv("CAMERA_SOURCE_AUTO_FALLBACK", "0")
    with patch(
        "airautomatica.settings.get_raw_settings",
        return_value={"CAMERA_SOURCE_AUTO_FALLBACK": "0"},
    ):
        assert get_camera_source_auto_fallback() is False


def test_settings_defaults_include_camera_keys() -> None:
    """get_raw_settings defaults include CAMERA_SOURCE_ID and CAMERA_SOURCE_AUTO_FALLBACK."""
    from airautomatica.settings import CANONICAL_SETTINGS_KEYS, get_raw_settings

    assert "CAMERA_SOURCE_ID" in CANONICAL_SETTINGS_KEYS
    assert "CAMERA_SOURCE_AUTO_FALLBACK" in CANONICAL_SETTINGS_KEYS
    raw = get_raw_settings()
    assert "CAMERA_SOURCE_ID" in raw
    assert "CAMERA_SOURCE_AUTO_FALLBACK" in raw
    assert raw["CAMERA_SOURCE_ID"] == ""
    assert raw["CAMERA_SOURCE_AUTO_FALLBACK"] == "1"
