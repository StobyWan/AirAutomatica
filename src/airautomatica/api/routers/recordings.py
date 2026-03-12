"""Recordings routes: list, session recordings, delete, file."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from airautomatica.services.camera_recording import CameraRecordingService
from airautomatica.services.recordings_service import RecordingsService

logger = logging.getLogger(__name__)


def create_recordings_router(
    recordings_service: Optional[RecordingsService],
    camera_recording_service: Optional[CameraRecordingService],
) -> APIRouter:
    """Create recordings router with injected dependencies."""

    def _recordings_to_dict(recordings: list) -> list[dict]:
        out = []
        for r in recordings:
            d: dict = {
                "filename": r.filename,
                "timestamp": r.timestamp_iso,
                "size_bytes": r.size_bytes,
                "duration_sec": r.duration_sec,
            }
            if r.trigger is not None:
                d["trigger"] = r.trigger
            if r.session_id is not None:
                d["session_id"] = r.session_id
            out.append(d)
        return out

    router = APIRouter(tags=["recordings"])

    @router.get("/recordings")
    def get_recordings(
        session_id_query: int | None = Query(None, alias="session_id"),
    ) -> dict:
        """List recordings. Optional session_id filters by session. Live tab: allow_fallback when unresolved."""
        if recordings_service is None:
            return {
                "session_id": session_id_query,
                "session_resolved": False,
                "fallback_used": False,
                "count": 0,
                "recordings": [],
                "recordings_dir": None,
            }
        sid = session_id_query
        result = recordings_service.get_recordings(session_id=sid, allow_fallback=True)
        recordings_dir = (
            camera_recording_service.recordings_dir
            if camera_recording_service
            else None
        )
        return {
            "session_id": result.session_id,
            "session_resolved": result.session_resolved,
            "fallback_used": result.fallback_used,
            "count": result.count,
            "recordings": _recordings_to_dict(result.recordings),
            "recordings_dir": recordings_dir,
        }

    @router.delete("/recordings/{filename}")
    def delete_recording(filename: str) -> dict:
        """Delete a recording by basename. Path traversal protected."""
        if recordings_service is None:
            raise HTTPException(503, "Recordings service not available")
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        if not recordings_service.delete_recording(filename):
            raise HTTPException(404, "File not found or delete failed")
        return {"ok": True}

    @router.get("/recordings/{filename}")
    def get_recording_file(filename: str) -> FileResponse:
        """Serve a recording file for preview or download. Filename must be a basename (no path traversal)."""
        if camera_recording_service is None:
            raise HTTPException(503, "Camera recording service not available")
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        path = Path(camera_recording_service.recordings_dir) / filename
        if not path.is_file():
            logger.warning(
                "Recording file not found: path=%s recordings_dir=%s filename=%s",
                str(path.resolve()),
                camera_recording_service.recordings_dir,
                filename,
            )
            raise HTTPException(404, "File not found")
        media_type = "video/mp4" if filename.lower().endswith(".mp4") else "video/H264"
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="inline",
        )

    return router
