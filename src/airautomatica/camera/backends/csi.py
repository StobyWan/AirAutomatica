"""CSI (libcamera) backend helpers. Build -c N args for rpicam-* tools."""

from typing import Optional

from airautomatica.camera.descriptor import CameraDescriptor


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
