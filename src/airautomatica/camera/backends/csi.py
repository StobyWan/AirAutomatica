"""CSI (libcamera) backend helpers. Build -c N args for rpicam-* tools."""

import shutil
from pathlib import Path
from typing import Optional

from airautomatica.camera.descriptor import CameraDescriptor

_CSI_STILL_COMMANDS = ("rpicam-still", "libcamera-still")


def _get_csi_still_command() -> Optional[str]:
    """Return rpicam-still or libcamera-still path if available."""
    for cmd in _CSI_STILL_COMMANDS:
        path = shutil.which(cmd)
        if path is not None:
            return path
    return None


def csi_camera_index_args(descriptor: Optional[CameraDescriptor]) -> list[str]:
    """Return -c N args for rpicam-vid/libcamera-vid when descriptor is CSI.

    For csi:0 returns ["-c", "0"]. For None or non-CSI, returns [].
    Preserves existing behavior (no -c, libcamera default) when descriptor is None.
    """
    if descriptor is None or descriptor.source_type != "csi":
        return []
    if not descriptor.id.startswith("csi:"):
        return []
    try:
        index = int(descriptor.id.split(":", 1)[1])
        return ["-c", str(index)]
    except (ValueError, IndexError):
        return []


def csi_still_capture_argv(
    descriptor: Optional[CameraDescriptor],
    output_path: Path,
) -> Optional[list[str]]:
    """Build argv for CSI still capture. Returns None if not CSI or rpicam-still missing."""
    if descriptor is None or descriptor.source_type != "csi":
        return None
    cmd = _get_csi_still_command()
    if not cmd:
        return None
    index_args = csi_camera_index_args(descriptor)
    return [cmd] + index_args + ["-t", "1", "--immediate", "-n", "-o", str(output_path)]
