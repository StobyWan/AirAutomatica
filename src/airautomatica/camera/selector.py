"""Camera selector: resolves config to descriptor with fallback logic."""

import logging
from typing import Optional

from airautomatica.camera.descriptor import CameraDescriptor
from airautomatica.camera.registry import CameraRegistry
from airautomatica.config import (
    get_camera_source_auto_fallback,
    get_camera_source_id,
)

logger = logging.getLogger(__name__)


class CameraSelector:
    """Resolves CAMERA_SOURCE_ID to a CameraDescriptor with fallback behavior.

    When CAMERA_SOURCE_ID is missing or empty: treat as auto, use first available.
    When set and camera found: return that descriptor.
    When set and camera not found: if auto_fallback, use first available; else None.
    """

    def __init__(self, registry: Optional[CameraRegistry] = None) -> None:
        self._registry = registry or CameraRegistry()

    def resolve(self) -> Optional[CameraDescriptor]:
        """Return the camera to use, or None if none available."""
        cameras = self._registry.list_cameras()
        if not cameras:
            return None

        source_id = get_camera_source_id()
        auto_fallback = get_camera_source_auto_fallback()

        if not source_id:
            first = cameras[0]
            logger.debug("Camera source auto: using first available %s", first.id)
            return first

        selected = self._registry.get_camera(source_id)
        if selected is not None:
            return selected

        if auto_fallback:
            first = cameras[0]
            logger.info(
                "Camera %s not found; falling back to first available %s",
                source_id,
                first.id,
            )
            return first

        logger.warning(
            "Camera %s not found and auto_fallback disabled; no camera available",
            source_id,
        )
        return None
