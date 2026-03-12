"""Camera routes: ready, recording start/stop."""

from typing import Optional

from fastapi import APIRouter, Body

from airautomatica.config import get_camera_recording_mode
from airautomatica.services.camera_ready_state import get as get_camera_ready
from airautomatica.services.camera_ready_state import set_ready as set_camera_ready
from airautomatica.services.camera_recording import CameraRecordingService


def create_camera_router(
    camera_recording_service: Optional[CameraRecordingService],
) -> APIRouter:
    """Create camera router with injected dependencies."""
    router = APIRouter(prefix="/camera", tags=["camera"])

    @router.post("/ready")
    def post_camera_ready(body: dict = Body(...)) -> dict:
        """Set camera ready state. Body: {ready: true|false}. Independent of aircraft armed."""
        ready = body.get("ready", False)
        set_camera_ready(bool(ready))
        return {"ok": True, "ready": get_camera_ready()}

    @router.post("/recording/start")
    def post_camera_recording_start() -> dict:
        """Start camera recording. Rejected when mode=off."""
        if camera_recording_service is None:
            return {"ok": False, "error": "Camera recording service not available"}
        if get_camera_recording_mode() == "off":
            return {"ok": False, "error": "Recording disabled (mode=off)"}
        state, err = camera_recording_service.start_recording()
        if err is not None:
            return {"ok": False, "error": err}
        return {
            "ok": True,
            "recording": state.recording,
            "output_file": state.output_file,
            "started_at": state.started_at.isoformat() if state.started_at else None,
        }

    @router.post("/recording/stop")
    def post_camera_recording_stop() -> dict:
        """Stop camera recording."""
        if camera_recording_service is None:
            return {"ok": False, "error": "Camera recording service not available"}
        state, err = camera_recording_service.stop_recording()
        if err is not None:
            return {"ok": False, "error": err}
        return {
            "ok": True,
            "recording": state.recording,
            "output_file": state.output_file,
            "last_recorded_file": state.last_recorded_file,
            "started_at": state.started_at.isoformat() if state.started_at else None,
        }

    return router
