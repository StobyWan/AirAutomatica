"""Shared camera status helper. Centralizes camera-specific state for health and status API."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from airautomatica.camera.backends.csi import csi_still_capture_argv
from airautomatica.camera.backends.usb import usb_still_capture_argv
from airautomatica.camera.descriptor import CameraDescriptor
from airautomatica.config import get_camera_source_auto_fallback, get_camera_source_id

if TYPE_CHECKING:
    from airautomatica.camera.registry import CameraRegistry
    from airautomatica.camera.selector import CameraSelector
    from airautomatica.services.camera_recording import CameraRecordingService

_DUMMY_PATH = Path("/tmp/camera_status_check")


def is_still_capture_available(descriptor: Optional[CameraDescriptor]) -> bool:
    """True if csi or usb still capture argv is non-None for the descriptor. No subprocess."""
    if descriptor is None:
        return False
    if csi_still_capture_argv(descriptor, _DUMMY_PATH) is not None:
        return True
    if usb_still_capture_argv(descriptor, _DUMMY_PATH) is not None:
        return True
    return False


def get_camera_status_summary(
    registry: "CameraRegistry",
    selector: "CameraSelector",
    recording_service: Optional["CameraRecordingService"],
    *,
    refresh_registry: bool = False,
) -> dict:
    """Build camera status dict for health (lightweight) or status endpoint (full).

    When refresh_registry=True, runs full discovery. Use only for GET /camera/status.
    When False, uses selector only (no registry.refresh). Use for health payload.
    """
    if refresh_registry:
        registry.refresh()

    cameras = registry.list_cameras()
    selected = selector.resolve()
    configured_id = get_camera_source_id()
    configured_auto_fallback = get_camera_source_auto_fallback()

    active_camera_id: Optional[str] = None
    active_camera_label: Optional[str] = None
    active_camera_kind: Optional[str] = None
    if selected is not None:
        active_camera_id = selected.id
        active_camera_label = selected.display_name
        active_camera_kind = selected.source_type

    still_capture_available = is_still_capture_available(selected)

    recording_available = False
    recording_active = False
    preview_available = False
    if recording_service is not None:
        recording_available = recording_service.is_available()
        rec_state = recording_service.get_recording_state()
        recording_active = rec_state.recording
        preview_available = recording_available

    # Lightweight for health: no cameras list
    lightweight: dict = {
        "active_camera_id": active_camera_id,
        "active_camera_label": active_camera_label,
        "active_camera_kind": active_camera_kind,
        "configured_source_id": configured_id or "",
        "configured_auto_fallback": configured_auto_fallback,
        "still_capture_available": still_capture_available,
        "recording_available": recording_available,
        "recording_active": recording_active,
        "preview_available": preview_available,
    }

    # Full for status endpoint: cameras list with is_selected
    cameras_list = [
        {
            "id": c.id,
            "display_name": c.display_name,
            "source_type": c.source_type,
            "is_selected": c.id == active_camera_id if active_camera_id else False,
        }
        for c in cameras
    ]

    return {
        **lightweight,
        "cameras": cameras_list,
    }
