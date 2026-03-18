"""Camera module. Frame acquisition for future AI HAT vision integration."""

from airautomatica.camera.capture import capture_still
from airautomatica.camera.descriptor import (
    CameraCapabilities,
    CameraDescriptor,
    SourceType,
)
from airautomatica.camera.interface import CameraFrameProvider
from airautomatica.camera.registry import CameraRegistry
from airautomatica.camera.selector import CameraSelector

__all__ = [
    "CameraCapabilities",
    "CameraDescriptor",
    "CameraFrameProvider",
    "CameraRegistry",
    "CameraSelector",
    "SourceType",
    "capture_still",
]
