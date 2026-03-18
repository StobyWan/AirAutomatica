"""Camera backends for CSI, USB, etc."""

from airautomatica.camera.backends.csi import csi_camera_index_args
from airautomatica.camera.backends.usb import (
    usb_preview_argv,
    usb_recording_argv,
)

__all__ = [
    "csi_camera_index_args",
    "usb_preview_argv",
    "usb_recording_argv",
]
