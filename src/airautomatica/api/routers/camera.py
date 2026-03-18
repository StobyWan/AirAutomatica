"""Camera routes: ready, recording start/stop, preview stream, status."""

import logging
from typing import Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, StreamingResponse

from airautomatica.camera.registry import CameraRegistry
from airautomatica.camera.selector import CameraSelector
from airautomatica.camera.status import get_camera_status_summary
from airautomatica.config import get_camera_recording_mode
from airautomatica.services.camera_preview import stream_preview_frames
from airautomatica.services.camera_ready_state import get as get_camera_ready
from airautomatica.services.camera_ready_state import set_ready as set_camera_ready
from airautomatica.services.camera_recording import CameraRecordingService

logger = logging.getLogger(__name__)


def create_camera_router(
    camera_recording_service: Optional[CameraRecordingService],
) -> APIRouter:
    """Create camera router with injected dependencies."""
    router = APIRouter(prefix="/camera", tags=["camera"])
    registry = CameraRegistry()
    selector = CameraSelector(registry=registry)

    @router.get("/status")
    def get_camera_status() -> dict:
        """Full camera status: discovered cameras, configured/active source, capabilities."""
        status = get_camera_status_summary(
            registry,
            selector,
            camera_recording_service,
            refresh_registry=True,
        )
        return status

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

    @router.get("/preview/stream")
    def get_camera_preview_stream():
        """Stream live camera preview as MJPEG. Returns 503 when recording."""
        if camera_recording_service is None:
            return JSONResponse(
                status_code=503,
                content={"error": "Camera not available"},
            )
        state = camera_recording_service.get_recording_state()
        if state.recording:
            return JSONResponse(
                status_code=503,
                content={"error": "Camera busy (recording)"},
            )
        if not camera_recording_service.is_available():
            return JSONResponse(
                status_code=503,
                content={"error": "Camera not available"},
            )
        if not get_camera_ready():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Camera not ready. Turn on Camera Ready in Operations."
                },
            )

        def is_recording() -> bool:
            s = camera_recording_service.get_recording_state()
            return s.recording

        return StreamingResponse(
            stream_preview_frames(is_recording),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/recording/stream")
    def get_camera_recording_stream():
        """Stream live MJPEG from recording pipeline when recording with overlay. Returns 503 otherwise."""
        if camera_recording_service is None:
            return JSONResponse(
                status_code=503,
                content={"error": "Camera not available"},
            )
        stream = camera_recording_service.get_recording_stream()
        if stream is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Recording stream unavailable (not recording or overlay disabled)",
                },
            )
        return StreamingResponse(
            stream,
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return router
