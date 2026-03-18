"""Tests for CSI backend (csi_camera_index_args)."""

import pytest

from airautomatica.camera import CameraDescriptor
from airautomatica.camera.backends.csi import csi_camera_index_args


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
