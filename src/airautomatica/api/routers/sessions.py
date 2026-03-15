"""Sessions routes: CRUD, path, detections, telemetry, events, phases, debrief, recordings."""

from typing import TYPE_CHECKING, Callable, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.services.camera_recording import CameraRecordingService
from airautomatica.services.debrief_service import (
    get_session_debrief,
    get_session_debrief_with_llm,
)
from airautomatica.services.persistence import PersistenceService
from airautomatica.services.recordings_service import RecordingsService

if TYPE_CHECKING:
    pass


def create_sessions_router(
    session_ref: list[int | None],
    persistence: Optional[PersistenceService],
    get_task_service: Callable[[], Optional[OllamaTaskService]],
    recordings_service: Optional[RecordingsService],
    recordings_dir: Optional[str] = None,
    camera_recording_service: Optional[CameraRecordingService] = None,
) -> APIRouter:
    """Create sessions router with injected dependencies."""
    router = APIRouter(tags=["sessions"])

    @router.get("/sessions/{sid:int}")
    def get_session(sid: int) -> dict:
        """Return session metadata for a single session. 404 if not found."""
        if persistence is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = persistence.get_session(sid)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        current_sid = session_ref[0] if session_ref else None
        if current_sid is not None:
            session_data["current_session_id"] = current_sid
        return session_data

    @router.delete("/sessions/{sid:int}")
    def delete_session(sid: int) -> dict:
        """Delete session and all associated recordings. 400 if active session."""
        if persistence is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = persistence.get_session(sid)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        current_sid = session_ref[0] if session_ref else None
        if current_sid is not None and sid == current_sid:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete active session. Stop the session first.",
            )
        recordings_deleted = 0
        recordings_failed = 0
        if recordings_service is not None:
            recordings_deleted, recordings_failed = (
                recordings_service.delete_recordings_for_session(sid)
            )
        if not persistence.delete_session(sid):
            raise HTTPException(
                status_code=500, detail="Failed to delete session from database"
            )
        return {
            "ok": True,
            "recordings_deleted": recordings_deleted,
            "recordings_failed": recordings_failed,
        }

    @router.patch("/sessions/{sid:int}")
    def patch_session(
        sid: int,
        home_lat: Optional[float] = Body(None),
        home_lon: Optional[float] = Body(None),
        clear_home: bool = Body(False),
    ) -> dict:
        """Update session. Set home_lat/home_lon to set manual home; clear_home=true to clear."""
        if persistence is None:
            raise HTTPException(status_code=404, detail="Persistence not available")
        session_data = persistence.get_session(sid)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if clear_home:
            persistence.clear_session_home(sid)
        elif home_lat is not None and home_lon is not None:
            if not (-90 <= home_lat <= 90) or not (-180 <= home_lon <= 180):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid coordinates: lat in [-90,90], lon in [-180,180]",
                )
            if not persistence.update_session_home(sid, home_lat, home_lon):
                raise HTTPException(
                    status_code=500, detail="Failed to update session home"
                )
        return persistence.get_session(sid) or session_data

    @router.get("/sessions/{sid:int}/path")
    def get_session_path(sid: int) -> dict:
        """Return flight path for a session (lat/lon points, oldest first). For map display or export."""
        if persistence is None:
            return {"path": [], "session_id": sid}
        path = persistence.get_session_path(sid)
        home_lat, home_lon, home_source = persistence.get_session_home(sid)
        out: dict = {"path": path, "session_id": sid}
        if home_lat is not None and home_lon is not None:
            out["home_lat"] = home_lat
            out["home_lon"] = home_lon
        if home_source is not None:
            out["home_source"] = home_source
        return out

    @router.get("/sessions/{sid:int}/detections")
    def get_session_detections(sid: int) -> dict:
        """Return detections for a session. For session detail page."""
        if persistence is None:
            return {"detections": [], "session_id": sid}
        detections = persistence.get_recent_detections(sid, limit=50)
        return {"detections": detections, "session_id": sid}

    @router.get("/sessions/{sid:int}/telemetry-samples")
    def get_session_telemetry_samples(
        sid: int,
        limit: int = Query(60, ge=1, le=10000),
        order: str = Query("desc"),
    ) -> dict:
        """Return telemetry samples for a session. Default: 60 newest (sparklines). Use limit=5000&order=asc for replay."""
        if persistence is None:
            return {"samples": [], "session_id": sid}
        samples = persistence.get_recent_telemetry_samples(
            sid,
            limit=limit,
            order=order if order.lower() in ("asc", "desc") else "desc",
        )
        return {"samples": samples, "session_id": sid}

    @router.get("/sessions/{sid:int}/flight-events")
    def get_session_flight_events(sid: int) -> dict:
        """Return flight events for a session (EventEngine output). For replay timeline."""
        if persistence is None:
            return {"events": [], "session_id": sid}
        events = persistence.get_session_flight_events(sid, limit=200)
        return {"events": events, "session_id": sid}

    @router.get("/sessions/{sid:int}/phase-intervals")
    def get_session_phase_intervals(sid: int) -> dict:
        """Return phase intervals for a session (FlightPhaseEngine output). For replay timeline bands."""
        if persistence is None:
            return {"intervals": [], "session_id": sid}
        intervals = persistence.get_session_phase_intervals(sid, limit=500)
        return {"intervals": intervals, "session_id": sid}

    @router.get("/sessions/{sid:int}/debrief")
    async def get_session_debrief_route(
        sid: int,
        generate_summary: bool = Query(False, alias="generate_summary"),
    ) -> dict:
        """Return post-flight debrief for a session. 404 if no telemetry.
        Set generate_summary=true to request LLM summary (requires task_service)."""
        if persistence is None:
            raise HTTPException(status_code=404, detail="Persistence not available")
        summary, compact = get_session_debrief(sid, persistence)
        if summary is None or compact is None:
            raise HTTPException(
                status_code=404,
                detail="No telemetry samples for session",
            )
        out: dict = {
            "session_id": sid,
            "summary": {
                "session_duration_sec": summary.session_duration_sec,
                "phase_duration_sec": summary.phase_duration_sec,
                "peak_distance_from_home_m": summary.peak_distance_from_home_m,
                "average_power_w": summary.average_power_w,
                "peak_power_w": summary.peak_power_w,
                "minimum_voltage_v": summary.minimum_voltage_v,
                "top_events": [
                    {
                        "name": e.name,
                        "count": e.count,
                        "duration_sec": e.duration_sec,
                    }
                    for e in summary.top_events
                ],
                "weak_return_margin_occurred": summary.weak_return_margin_occurred,
                "gps_degraded_occurred": summary.gps_degraded_occurred,
                "unstable_attitude_occurred": summary.unstable_attitude_occurred,
                "assessment_tags": summary.assessment_tags,
            },
            "compact": compact.to_dict(),
        }
        ts = get_task_service()
        recordings_count = 0
        if recordings_service is not None:
            rec_result = recordings_service.get_recordings(
                session_id=sid, allow_fallback=False
            )
            recordings_count = len(rec_result.recordings)
        if generate_summary and ts is not None:
            _, _, generated = await get_session_debrief_with_llm(
                sid, persistence, ts, recordings_count=recordings_count
            )
            if generated and not str(generated).startswith(
                "Debrief summary unavailable:"
            ):
                persistence.save_generated_debrief(sid, generated)
            out["generated_summary"] = generated
        else:
            persisted = persistence.get_generated_debrief(sid)
            if persisted is not None:
                out["generated_summary"] = persisted

        if out.get("generated_summary"):
            at = persistence.get_generated_debrief_at(sid)
            if at is not None:
                out["generated_debrief_at"] = at.isoformat()

        return out

    @router.get("/sessions")
    def get_sessions(
        autopilot: str | None = Query(None, alias="autopilot"),
        connection_mode: str | None = Query(None, alias="connection_mode"),
        limit: int = Query(12, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> dict:
        """Return recent flight sessions with detection counts. For dashboard initial load."""
        sid = session_ref[0]
        if persistence is None:
            return {"sessions": [], "current_session_id": sid, "total": 0}
        total = persistence.get_sessions_count(
            autopilot_filter=autopilot,
            connection_mode_filter=connection_mode,
        )
        sessions = persistence.get_recent_sessions(
            limit=limit,
            offset=offset,
            include_detection_count=True,
            autopilot_filter=autopilot,
            connection_mode_filter=connection_mode,
        )
        return {"sessions": sessions, "current_session_id": sid, "total": total}

    @router.get("/sessions/{sid:int}/recordings")
    def get_session_recordings(sid: int) -> dict:
        """Return recordings for a session. Uses fallback (recent N) when session time range has no matches."""
        if recordings_service is None:
            return {
                "session_id": sid,
                "session_resolved": False,
                "fallback_used": False,
                "count": 0,
                "recordings": [],
                "recordings_dir": None,
            }
        result = recordings_service.get_recordings(session_id=sid, allow_fallback=True)
        recordings_list = []
        for r in result.recordings:
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
            recordings_list.append(d)
        # Merge in-progress recording when viewing current session (fixes videos not visible)
        current_sid = session_ref[0] if session_ref else None
        if (
            camera_recording_service is not None
            and current_sid is not None
            and sid == current_sid
        ):
            rec_state = camera_recording_service.get_recording_state()
            if (
                rec_state.recording
                and rec_state.output_file
                and rec_state.started_at
                and not any(
                    r["filename"] == rec_state.output_file for r in recordings_list
                )
            ):
                recordings_list.insert(
                    0,
                    {
                        "filename": rec_state.output_file,
                        "timestamp": rec_state.started_at.isoformat(),
                        "size_bytes": None,
                        "duration_sec": None,
                        "trigger": None,
                        "session_id": sid,
                    },
                )
        return {
            "session_id": result.session_id,
            "session_resolved": result.session_resolved,
            "fallback_used": result.fallback_used,
            "count": len(recordings_list),
            "recordings": recordings_list,
            "recordings_dir": recordings_dir,
        }

    return router
