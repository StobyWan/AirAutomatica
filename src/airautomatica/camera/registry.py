"""Camera registry: discovers and exposes available cameras for selection."""

import logging
import re
import shutil
import subprocess
from typing import Optional

from airautomatica.camera.descriptor import (
    CameraCapabilities,
    CameraDescriptor,
    SourceType,
)

logger = logging.getLogger(__name__)

_CSI_COMMANDS = ("rpicam-vid", "libcamera-vid")
_LIST_CAMERAS_ARGS = ["--list-cameras"]
_CAMERA_LINE_RE = re.compile(r"^\s*(\d+)\s*:\s*([^\s\[]+)\s+\[([^\]]+)\]")
_NO_CAMERAS_MSG = "No cameras available!"


def _get_csi_command() -> Optional[str]:
    """Return rpicam-vid or libcamera-vid path if available. Matches camera_recording logic."""
    for cmd in _CSI_COMMANDS:
        path = shutil.which(cmd)
        if path is not None:
            return path
    return None


def _parse_csi_list_cameras_output(stdout: str) -> list[CameraDescriptor]:
    """Parse rpicam-vid/libcamera-vid --list-cameras output into descriptors."""
    descriptors: list[CameraDescriptor] = []
    lines = stdout.splitlines()

    for line in lines:
        line_stripped = line.strip()
        if line_stripped == _NO_CAMERAS_MSG:
            return []
        match = _CAMERA_LINE_RE.match(line)
        if match:
            index_str, model, size_part = match.groups()
            index = int(index_str)
            camera_id = f"csi:{index}"
            display_name = f"CSI Camera {index} ({model})"
            resolutions: list[tuple[int, int]] = []
            size_match = re.search(r"(\d+)\s*x\s*(\d+)", size_part)
            if size_match:
                w, h = int(size_match.group(1)), int(size_match.group(2))
                resolutions.append((w, h))
            capabilities = CameraCapabilities(
                resolutions=tuple(resolutions) if resolutions else ()
            )
            descriptors.append(
                CameraDescriptor(
                    id=camera_id,
                    source_type="csi",
                    display_name=display_name,
                    path=None,
                    capabilities=capabilities,
                    available=True,
                )
            )
    return descriptors


class CameraRegistry:
    """Discovers cameras and exposes them for selection. Phase 1: CSI only."""

    def __init__(self) -> None:
        self._cameras: list[CameraDescriptor] = []
        self._refreshed = False

    def list_cameras(self) -> list[CameraDescriptor]:
        """Return discovered cameras. Refreshes from system if not yet refreshed."""
        if not self._refreshed:
            self.refresh()
        return list(self._cameras)

    def refresh(self) -> None:
        """Re-run discovery and update internal camera list."""
        self._cameras = self._discover_csi_cameras()
        self._refreshed = True
        logger.debug("CameraRegistry refreshed: %d cameras", len(self._cameras))

    def get_camera(self, camera_id: str) -> Optional[CameraDescriptor]:
        """Return descriptor for given id, or None if not found."""
        for cam in self.list_cameras():
            if cam.id == camera_id:
                return cam
        return None

    def _discover_csi_cameras(self) -> list[CameraDescriptor]:
        """Discover CSI cameras via rpicam-vid or libcamera-vid --list-cameras."""
        cmd = _get_csi_command()
        if cmd is None:
            logger.debug("No rpicam-vid/libcamera-vid found; no CSI cameras")
            return []

        try:
            result = subprocess.run(
                [cmd] + _LIST_CAMERAS_ARGS,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.debug(
                    "list-cameras failed: rc=%s stderr=%s",
                    result.returncode,
                    (result.stderr or "")[:200],
                )
                return []
            stdout = result.stdout or ""
            return _parse_csi_list_cameras_output(stdout)
        except subprocess.TimeoutExpired:
            logger.warning("list-cameras timed out")
            return []
        except OSError as e:
            logger.debug("list-cameras failed: %s", e)
            return []
