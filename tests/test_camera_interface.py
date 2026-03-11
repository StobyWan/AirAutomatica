"""Smoke test for camera interface. Import works; protocol exists."""

from airautomatica.camera import CameraFrameProvider


def test_camera_frame_provider_exists() -> None:
    """CameraFrameProvider protocol is importable and usable as a type."""
    assert CameraFrameProvider is not None
