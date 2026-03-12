"""FastAPI server."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, cast

if TYPE_CHECKING:
    from airautomatica.services.mission_logic import MissionLogic
    from airautomatica.telemetry.preprocessing import TelemetryPreprocessor

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from airautomatica.ai.ollama_readiness import check_ollama_ready
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import (
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    get_telemetry_summary_counts,
)
from airautomatica.config import (
    get_ai_duplicate_window_sec,
    get_ai_hat_enabled,
    get_ai_min_confidence,
    get_camera_recording_mode,
    get_effective_ai_backend,
    get_local_llm_base_url,
    get_local_llm_model,
    get_local_llm_provider,
    get_serial_baud,
    get_serial_port,
    get_sqlite_db_path,
    get_telemetry_backend,
    validate_serial_config,
)
from airautomatica.db.base import get_engine, get_last_init_error
from airautomatica.logging_config import setup_logging
from airautomatica.models.connection_state import (
    ConnectionMode,
    ConnectionState,
    SessionState,
)
from airautomatica.models.state import AircraftState, nan_to_none
from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
from airautomatica.runtime.telemetry_subsystem import TelemetryReconnectResult
from airautomatica.services.camera_ready_state import get as get_camera_ready
from airautomatica.services.camera_ready_state import set_ready as set_camera_ready
from airautomatica.services.camera_recording import CameraRecordingService
from airautomatica.services.connection_state_store import (
    ConnectionStateStore,
)
from airautomatica.services.connection_state_store import (
    DetectionResult as StoreDetectionResult,
)
from airautomatica.services.debrief_service import (
    get_session_debrief,
    get_session_debrief_with_llm,
)
from airautomatica.services.mission_logic import get_perception_counts
from airautomatica.services.persistence import (
    PersistenceService,
    build_session_start_params,
)
from airautomatica.services.recordings_service import RecordingsService
from airautomatica.services.state_store import StateStore
from airautomatica.settings import (
    SETTING_APPLY_MODES,
    get_apply_modes,
    get_effective_settings,
    get_provider_reason,
    get_raw_settings,
    save_settings,
)
from airautomatica.system.observability import get_ai_observability_rates
from airautomatica.system.thermal import get_thermal_state, read_temperature_c
from airautomatica.telemetry.detector import scan_and_detect
from airautomatica.ui.dashboard import get_dashboard_html, get_session_detail_html

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Reapply our logging config after uvicorn initializes (fixes logging being overridden)."""
    setup_logging(force=True)
    yield


def create_app(
    store: StateStore,
    connection_store: Optional[ConnectionStateStore] = None,
    session_ref: Optional[list[int | None]] = None,
    persistence: Optional[PersistenceService] = None,
    task_service: Optional[OllamaTaskService] = None,
    ai_holder: Optional[AiSubsystemHolder] = None,
    camera_recording_service: Optional[CameraRecordingService] = None,
    preprocessor: Optional["TelemetryPreprocessor"] = None,
    mission_logic: Optional["MissionLogic"] = None,
    reload_ai_fn: Optional[Callable[[str], ReloadResult]] = None,
    reload_telemetry_fn: Optional[
        Callable[[], Awaitable[TelemetryReconnectResult]]
    ] = None,
) -> FastAPI:
    """Create FastAPI app with state store dependency.
    When ai_holder is provided, task_service is read from it (supports hot-reload).
    reload_ai_fn(provider_before) -> ReloadResult when AI hot-reload is available.
    reload_telemetry_fn() -> TelemetryReconnectResult when telemetry reconnect is available.
    """
    app = FastAPI(title="AIRAUTOMATICA", version="0.1.0", lifespan=_lifespan)
    _session_ref = session_ref or [None]
    _connection_store = connection_store
    _preprocessor = preprocessor
    _mission_logic = mission_logic
    _ai_holder = ai_holder
    _task_service_fallback = task_service
    _reload_ai_fn = reload_ai_fn
    _reload_telemetry_fn = reload_telemetry_fn

    def _get_task_service() -> Optional[OllamaTaskService]:
        if _ai_holder is not None:
            return _ai_holder.get_task_service()
        return _task_service_fallback

    @app.get("/")
    def root() -> RedirectResponse:
        """Redirect root to dashboard."""
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.get("/connection/state")
    def get_connection_state() -> dict:
        """Return connection/session state for frontend. Primary source of truth for v1."""
        session_id = _session_ref[0]
        if _connection_store is None:
            return {
                "connection_state": "setup",
                "session_state": "none",
                "mode": None,
                "session_id": session_id,
                "detection_result": None,
            }
        conn = _connection_store.get_connection_state()
        sess = _connection_store.get_session_state()
        mode = _connection_store.get_mode()
        det = _connection_store.get_detection_result()
        return {
            "connection_state": conn.value if hasattr(conn, "value") else conn,
            "session_state": sess.value if hasattr(sess, "value") else sess,
            "mode": mode.value if mode is not None and hasattr(mode, "value") else mode,
            "session_id": session_id,
            "detection_result": (
                {
                    "detected": det.detected,
                    "port": det.port,
                    "baud": det.baud,
                    "autopilot": det.autopilot,
                    "message": det.message,
                    "heartbeat_age_ms": det.heartbeat_age_ms,
                }
                if det is not None
                else None
            ),
        }

    @app.post("/connection/detect")
    def post_connection_detect() -> dict:
        """Scan serial ports for MAVLink HEARTBEAT. Updates connection_store state."""
        # State transition: setup → detecting
        if _connection_store is not None:
            _connection_store.set_connection_state(ConnectionState.DETECTING)
        try:
            r = scan_and_detect()
            if _connection_store is not None:
                store_result = StoreDetectionResult(
                    detected=r.detected,
                    port=r.port,
                    baud=r.baud,
                    autopilot=r.autopilot,
                    message=r.message,
                    heartbeat_age_ms=r.heartbeat_age_ms,
                )
                _connection_store.set_detection_result(store_result)
                # State transition: detecting → connected_ardupilot | connected_inav | not_detected
                if r.detected:
                    if r.autopilot == "ardupilot":
                        _connection_store.set_connection_state(
                            ConnectionState.CONNECTED_ARDUPILOT
                        )
                    else:
                        _connection_store.set_connection_state(
                            ConnectionState.CONNECTED_INAV
                        )
                else:
                    _connection_store.set_connection_state(ConnectionState.NOT_DETECTED)
            mode = r.autopilot if r.autopilot else "inav"
            if r.autopilot == "generic":
                mode = "inav"
            conn_state = (
                "not_detected"
                if not r.detected
                else (
                    "connected_ardupilot"
                    if r.autopilot == "ardupilot"
                    else "connected_inav"
                )
            )
            return {
                "connection_state": conn_state,
                "detected": r.detected,
                "mode": mode,
                "port": r.port,
                "baud": r.baud,
                "autopilot": r.autopilot,
                "message": r.message,
                "heartbeat_age_ms": r.heartbeat_age_ms,
            }
        except Exception as e:
            logger.exception("Detection failed: %s", e)
            if _connection_store is not None:
                _connection_store.set_connection_state(ConnectionState.NOT_DETECTED)
                _connection_store.set_detection_result(
                    StoreDetectionResult(
                        detected=False,
                        port=None,
                        baud=None,
                        autopilot=None,
                        message=str(e),
                        heartbeat_age_ms=None,
                    )
                )
            return {
                "connection_state": "not_detected",
                "detected": False,
                "mode": "inav",
                "port": None,
                "baud": None,
                "autopilot": None,
                "message": str(e),
                "heartbeat_age_ms": None,
            }

    @app.post("/connection/mode")
    def post_connection_mode(body: dict = Body(...)) -> dict:
        """Set connection mode. Persists to settings. Serial modes require restart."""
        mode = (body.get("mode") or "").lower()
        port = body.get("port") or get_serial_port()
        baud = body.get("baud") or get_serial_baud()
        if mode not in ("mock", "ardupilot", "inav"):
            return {"ok": False, "error": "Invalid mode. Use mock, ardupilot, or inav."}
        updates = {
            "TELEMETRY_BACKEND": "mock" if mode == "mock" else "serial",
            "SERIAL_PORT": str(port),
            "SERIAL_BAUD": str(int(baud)),
        }
        save_settings(updates)
        restart_required = mode in ("ardupilot", "inav")
        # State transition: setup → mock_idle | connected_ardupilot | connected_inav
        if _connection_store is not None:
            if mode == "mock":
                _connection_store.set_connection_state(ConnectionState.MOCK_IDLE)
                _connection_store.set_mode(ConnectionMode.MOCK)
            elif mode == "ardupilot":
                _connection_store.set_connection_state(
                    ConnectionState.CONNECTED_ARDUPILOT
                )
                _connection_store.set_mode(ConnectionMode.ARDUPILOT)
            else:
                _connection_store.set_connection_state(ConnectionState.CONNECTED_INAV)
                _connection_store.set_mode(ConnectionMode.INAV)
        return {"ok": True, "restart_required": restart_required}

    @app.post("/connection/disconnect")
    def post_connection_disconnect() -> dict:
        """Return to setup. Clear mode. Preserve detection_result for diagnostics."""
        # State transition: * → setup
        if _connection_store is not None:
            _connection_store.set_connection_state(ConnectionState.SETUP)
            _connection_store.set_mode(None)
        return {"ok": True}

    @app.post("/session/start")
    def post_session_start(body: dict = Body(...)) -> dict:
        """Start a session. Requires connection_state in mock_idle or connected_*."""
        if _session_ref[0] is not None:
            return {
                "ok": True,
                "already_active": True,
                "session_id": _session_ref[0],
            }
        if persistence is None:
            return {"ok": False, "error": "Persistence not available"}
        params = build_session_start_params(_connection_store)
        sid = persistence.start_session(**params)
        if sid is None:
            return {"ok": False, "error": "Failed to start session"}
        _session_ref[0] = sid
        # State transition: session_state none → active
        if _connection_store is not None:
            _connection_store.set_session_state(SessionState.ACTIVE)
        return {
            "ok": True,
            "session_id": sid,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/session/stop")
    def post_session_stop() -> dict:
        """End current session. Idempotent when no session active."""
        sid = _session_ref[0]
        if sid is not None and persistence is not None:
            persistence.end_session(sid)
        _session_ref[0] = None
        # State transition: session_state active → none
        if _connection_store is not None:
            _connection_store.set_session_state(SessionState.NONE)
        return {"ok": True}

    @app.get("/health")
    def health() -> dict:
        """Health check. Includes telemetry_status, connection details, and DB health when available."""
        state = store.get()
        persistence_enabled = get_engine() is not None
        session_id = _session_ref[0]
        health_data: dict = {
            "status": "ok",
            "ai_mode": get_effective_ai_backend(),
            "telemetry_backend": get_telemetry_backend(),
            "thermal": {
                "temp_c": read_temperature_c(),
                "state": get_thermal_state().value,
            },
            "persistence": {
                "persistence_enabled": persistence_enabled,
                "sqlite_db_path": get_sqlite_db_path() if persistence_enabled else None,
                "session_id": session_id,
                "last_persistence_error": (
                    get_last_init_error()
                    if not persistence_enabled
                    else (
                        persistence.get_last_persistence_error()
                        if persistence is not None
                        else None
                    )
                ),
            },
        }
        health_data["telemetry_summary_counts"] = get_telemetry_summary_counts()
        health_data["perception_counts"] = get_perception_counts()
        rates = get_ai_observability_rates(
            health_data["perception_counts"],
            health_data["telemetry_summary_counts"],
        )
        health_data["perception_acceptance_rate"] = rates["perception_acceptance_rate"]
        health_data["telemetry_meaningful_rate"] = rates["telemetry_meaningful_rate"]
        health_data["camera_ready"] = get_camera_ready()
        if get_local_llm_provider() == "ollama":
            health_data["ollama_ready"] = check_ollama_ready(
                get_local_llm_base_url("ollama"),
                model=get_local_llm_model("ollama"),
                timeout_sec=3.0,
            ).ready
        if camera_recording_service is not None:
            rec_state = camera_recording_service.get_recording_state()
            health_data["camera_recording_available"] = (
                camera_recording_service.is_available()
            )
            health_data["camera_recording_mode"] = get_camera_recording_mode()
            health_data["camera_recording"] = rec_state.recording
            health_data["camera_recording_file"] = rec_state.output_file
            health_data["camera_recording_last_file"] = rec_state.last_recorded_file
            health_data["recordings_dir"] = camera_recording_service.recordings_dir
            health_data["camera_recording_started_at"] = (
                rec_state.started_at.isoformat() if rec_state.started_at else None
            )
        if state is None:
            health_data["telemetry"] = {
                "telemetry_status": "disconnected",
                "connected": False,
                "reconnect_count": 0,
                "last_disconnect_reason": None,
            }
            caps = store.get_capabilities()
            if caps is not None:
                health_data["capabilities"] = caps.to_dict()
            return health_data
        age = nan_to_none(state.heartbeat_age_s)
        health_data["telemetry"] = {
            "telemetry_status": state.telemetry_status,
            "connected": state.connected,
            "reconnect_count": state.reconnect_count,
            "last_disconnect_reason": state.last_disconnect_reason,
            "last_heartbeat_at": (
                state.last_heartbeat_at.isoformat() if state.last_heartbeat_at else None
            ),
            "heartbeat_age_s": age,
        }
        caps = store.get_capabilities()
        if caps is not None:
            health_data["capabilities"] = caps.to_dict()
        return health_data

    @app.get("/state")
    def get_state() -> dict:
        """Return current aircraft state."""
        state: Optional[AircraftState] = store.get()
        if state is None:
            return {"state": None}
        return {"state": state.to_dict()}

    @app.post("/ai/telemetry-summary")
    async def post_telemetry_summary() -> dict:
        """Request AI interpretation of current telemetry. Returns TelemetrySummaryResult."""
        ts = _get_task_service()
        if ts is None:
            return {"error": "AI task service not available"}
        if _preprocessor is None and ts.provider == "ollama":
            return {
                "error": "Preprocessing required for Ollama telemetry summary. Enable AIRAUTOMATICA_PREPROCESSING_ENABLED=1.",
            }
        state = store.get()
        samples: list = []
        sid = _session_ref[0]
        if persistence is not None and sid is not None:
            samples = persistence.get_recent_telemetry_samples(sid, limit=30)
        if _preprocessor is not None:
            llm_ctx = _preprocessor.get_llm_context()
            context = cast(dict[str, Any], {"llm_context": llm_ctx.to_dict()})
        else:
            # Fallback: mock only (ollama rejected above). Minimal state summary.
            context = cast(
                dict[str, Any], {"state": state, "telemetry_samples": samples}
            )
        result = await ts.infer_task(
            OllamaTaskType.TELEMETRY_SUMMARY,
            context,
        )
        if not isinstance(result, TelemetrySummaryResult):
            return {"error": "Unexpected result type"}
        return {
            "status": result.status,
            "summary": result.summary,
            "concerns": list(result.concerns),
            "recommendations": list(result.recommendations),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "telemetry_sample_count": (
                _preprocessor.get_summary().buffer_sample_count
                if _preprocessor is not None
                else len(samples)
            ),
            "provider": ts.provider,
        }

    @app.post("/ai/event-classification")
    async def post_event_classification() -> dict:
        """Request AI classification of recent system events. Returns EventClassificationResult."""
        ts = _get_task_service()
        if ts is None:
            return {"error": "AI task service not available"}
        events: list = []
        if persistence is not None:
            events = persistence.get_recent_system_events(limit=30)
        result = await ts.infer_task(
            OllamaTaskType.EVENT_CLASSIFICATION,
            {"events": events},
        )
        if not isinstance(result, EventClassificationResult):
            return {"error": "Unexpected result type"}
        return {
            "severity": result.severity,
            "category": result.category,
            "summary": result.summary,
            "likely_causes": list(result.likely_causes),
            "recommended_checks": list(result.recommended_checks),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "event_count": len(events),
            "provider": ts.provider,
        }

    @app.get("/recent-detections")
    def get_recent_detections() -> dict:
        """Return recent persisted detections for current session. For bench testing."""
        sid = _session_ref[0]
        if persistence is None or sid is None:
            return {"detections": [], "session_id": None}
        detections = persistence.get_recent_detections(sid, limit=20)
        return {"detections": detections, "session_id": sid}

    @app.get("/sessions/{sid:int}")
    def get_session(sid: int) -> dict:
        """Return session metadata for a single session. 404 if not found."""
        if persistence is None:
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = persistence.get_session(sid)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_data

    @app.get("/sessions/{sid:int}/path")
    def get_session_path(sid: int) -> dict:
        """Return flight path for a session (lat/lon points, oldest first). For map display or export."""
        if persistence is None:
            return {"path": [], "session_id": sid}
        path = persistence.get_session_path(sid)
        return {"path": path, "session_id": sid}

    @app.get("/sessions/{sid:int}/detections")
    def get_session_detections(sid: int) -> dict:
        """Return detections for a session. For session detail page."""
        if persistence is None:
            return {"detections": [], "session_id": sid}
        detections = persistence.get_recent_detections(sid, limit=50)
        return {"detections": detections, "session_id": sid}

    @app.get("/recent-events")
    def get_recent_events() -> dict:
        """Return recent system events for dashboard. Degrades to [] when persistence disabled."""
        if persistence is None:
            return {"events": []}
        events = persistence.get_recent_system_events(limit=50)
        return {"events": events}

    @app.get("/sessions/{sid:int}/telemetry-samples")
    def get_session_telemetry_samples(sid: int) -> dict:
        """Return recent telemetry samples for a session (path + sparklines)."""
        if persistence is None:
            return {"samples": [], "session_id": sid}
        samples = persistence.get_recent_telemetry_samples(sid, limit=60)
        return {"samples": samples, "session_id": sid}

    @app.get("/sessions/{sid:int}/debrief")
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
            "compact": compact.to_dict(),  # compact is not None after check above
        }
        ts = _get_task_service()
        if generate_summary and ts is not None:
            _, _, generated = await get_session_debrief_with_llm(sid, persistence, ts)
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

    @app.get("/sessions")
    def get_sessions(
        autopilot: str | None = Query(None, alias="autopilot"),
        connection_mode: str | None = Query(None, alias="connection_mode"),
    ) -> dict:
        """Return recent flight sessions with detection counts. For dashboard initial load."""
        sid = _session_ref[0]
        if persistence is None:
            return {"sessions": [], "current_session_id": sid}
        sessions = persistence.get_recent_sessions(
            limit=10,
            include_detection_count=True,
            autopilot_filter=autopilot,
            connection_mode_filter=connection_mode,
        )
        return {"sessions": sessions, "current_session_id": sid}

    @app.get("/settings")
    def get_settings_endpoint() -> dict:
        """Return raw saved settings, effective runtime settings, apply modes, and Ollama status."""
        raw = get_raw_settings()
        effective = get_effective_settings()
        apply_modes = dict(get_apply_modes())
        if _mission_logic is not None:
            apply_modes["AI_MIN_CONFIDENCE"] = "live"
            apply_modes["AI_DUPLICATE_WINDOW_SEC"] = "live"
        if _reload_ai_fn is not None:
            for k in (
                "LOCAL_LLM_PROVIDER",
                "LOCAL_LLM_BASE_URL",
                "LOCAL_LLM_MODEL",
                "LOCAL_LLM_TIMEOUT",
                "OLLAMA_NUM_THREAD",
            ):
                apply_modes[k] = "live"
        if _reload_telemetry_fn is not None:
            for k in ("TELEMETRY_BACKEND", "SERIAL_PORT", "SERIAL_BAUD"):
                apply_modes[k] = "live"
        provider_reason = get_provider_reason()

        ollama_result = check_ollama_ready(
            get_local_llm_base_url("ollama"),
            model=get_local_llm_model("ollama"),
            timeout_sec=2.0,
        )
        ollama_ready = ollama_result.ready
        ollama_available = ollama_result.reason != "unreachable"

        backend = get_telemetry_backend()
        provider = get_local_llm_provider()
        if backend == "serial":
            active_telemetry = f"serial @ {get_serial_port()}"
        else:
            active_telemetry = backend
        if provider == "ollama":
            active_ai = f"ollama ({get_local_llm_model('ollama')})"
        else:
            active_ai = provider
        if get_ai_hat_enabled():
            active_ai = f"{active_ai} + AI HAT (perception)"
        active_summary = f"Telemetry: {active_telemetry} · AI: {active_ai}"

        return {
            "settings": raw,
            "effective_settings": effective,
            "apply_modes": apply_modes,
            "ollama_available": ollama_available,
            "ollama_ready": ollama_ready,
            "provider_reason": provider_reason,
            "active_summary": active_summary,
        }

    AI_SUBSYSTEM_KEYS = frozenset(
        {
            "LOCAL_LLM_PROVIDER",
            "LOCAL_LLM_BASE_URL",
            "LOCAL_LLM_MODEL",
            "LOCAL_LLM_TIMEOUT",
            "OLLAMA_NUM_THREAD",
        }
    )
    TELEMETRY_SUBSYSTEM_KEYS = frozenset(
        {"TELEMETRY_BACKEND", "SERIAL_PORT", "SERIAL_BAUD"}
    )

    @app.post("/settings")
    async def post_settings(updates: dict = Body(...)) -> dict:
        """Save settings to file. Returns structured result with apply-mode info."""
        from airautomatica.settings import CANONICAL_SETTINGS_KEYS

        changed_keys = [k for k in updates if k in CANONICAL_SETTINGS_KEYS]
        provider_before = get_local_llm_provider()
        save_settings(updates)

        reconfigured_keys: list[str] = []
        if _mission_logic is not None:
            mission_keys = {"AI_MIN_CONFIDENCE", "AI_DUPLICATE_WINDOW_SEC"}
            if mission_keys & set(changed_keys):
                min_conf = (
                    get_ai_min_confidence() if "AI_MIN_CONFIDENCE" in updates else None
                )
                dup_win = (
                    get_ai_duplicate_window_sec()
                    if "AI_DUPLICATE_WINDOW_SEC" in updates
                    else None
                )
                _mission_logic.reconfigure(
                    min_confidence=min_conf,
                    duplicate_window_sec=dup_win,
                )
                reconfigured_keys = [k for k in changed_keys if k in mission_keys]

        ai_reloaded_keys: list[str] = []
        ai_reload_error: Optional[str] = None
        ai_subsystem_changed = AI_SUBSYSTEM_KEYS & set(changed_keys)
        if _reload_ai_fn is not None and ai_subsystem_changed:
            result = _reload_ai_fn(provider_before)
            if isinstance(result, ReloadResult):
                if result.success:
                    ai_reloaded_keys = [
                        k for k in changed_keys if k in AI_SUBSYSTEM_KEYS
                    ]
                else:
                    ai_reload_error = result.error

        telemetry_reloaded_keys: list[str] = []
        telemetry_reload_error: Optional[str] = None
        telemetry_subsystem_changed = TELEMETRY_SUBSYSTEM_KEYS & set(changed_keys)
        if _reload_telemetry_fn is not None and telemetry_subsystem_changed:
            backend = get_telemetry_backend()
            port = get_serial_port()
            valid, validation_err = validate_serial_config(backend, port)
            if not valid:
                telemetry_reload_error = validation_err
            else:
                tel_result = await _reload_telemetry_fn()
                if isinstance(tel_result, TelemetryReconnectResult):
                    if tel_result.success:
                        telemetry_reloaded_keys = [
                            k for k in changed_keys if k in TELEMETRY_SUBSYSTEM_KEYS
                        ]
                    else:
                        telemetry_reload_error = tel_result.error

        live_keys = [k for k in changed_keys if SETTING_APPLY_MODES.get(k) == "live"]
        live_keys.extend(reconfigured_keys)
        live_keys.extend(ai_reloaded_keys)
        live_keys.extend(telemetry_reloaded_keys)
        reconnect_keys = [
            k
            for k in changed_keys
            if SETTING_APPLY_MODES.get(k) == "reconnect"
            and k not in reconfigured_keys
            and k not in ai_reloaded_keys
            and k not in telemetry_reloaded_keys
        ]
        restart_keys = [
            k
            for k in changed_keys
            if SETTING_APPLY_MODES.get(k) == "restart"
            and k not in telemetry_reloaded_keys
        ]

        restart_required = len(restart_keys) > 0
        reconnect_required = len(reconnect_keys) > 0

        if live_keys and not reconnect_required and not restart_required:
            message = "Settings saved. Changes apply immediately."
        elif ai_reload_error or telemetry_reload_error:
            errors = []
            if ai_reload_error:
                errors.append(f"AI reload failed: {ai_reload_error}")
            if telemetry_reload_error:
                errors.append(f"Telemetry reconnect failed: {telemetry_reload_error}")
            message = "Settings saved. " + "; ".join(errors)
            if live_keys:
                message += f" {len(live_keys)} other changes apply immediately."
        elif reconnect_required and not restart_required:
            message = "Settings saved. Some changes take effect after reconnect support is added."
        elif restart_required:
            parts = ["Settings saved."]
            if live_keys:
                parts.append(f"{len(live_keys)} apply immediately.")
            if ai_reload_error:
                parts.append(f"AI reload failed: {ai_reload_error}.")
            if telemetry_reload_error:
                parts.append(f"Telemetry reconnect failed: {telemetry_reload_error}.")
            if reconnect_required:
                parts.append(
                    f"{len(reconnect_keys)} take effect after reconnect support is added."
                )
            parts.append(f"{len(restart_keys)} require app restart.")
            message = " ".join(parts)
        else:
            message = "Settings saved."

        backend = get_telemetry_backend()
        provider = get_local_llm_provider()
        if backend == "serial":
            active_telemetry = f"serial @ {get_serial_port()}"
        else:
            active_telemetry = backend
        if provider == "ollama":
            active_ai = f"ollama ({get_local_llm_model('ollama')})"
        else:
            active_ai = provider
        if get_ai_hat_enabled():
            active_ai = f"{active_ai} + AI HAT (perception)"
        active_summary = f"Telemetry: {active_telemetry} · AI: {active_ai}"

        return {
            "ok": True,
            "message": message,
            "changed_keys": changed_keys,
            "live": live_keys,
            "reconnect": reconnect_keys,
            "restart": restart_keys,
            "restart_required": restart_required,
            "reconnect_required": reconnect_required,
            "active_telemetry_backend": backend,
            "active_ai_provider": provider,
            "active_summary": active_summary,
        }

    @app.post("/camera/ready")
    def post_camera_ready(body: dict = Body(...)) -> dict:
        """Set camera ready state. Body: {ready: true|false}. Independent of aircraft armed."""
        ready = body.get("ready", False)
        set_camera_ready(bool(ready))
        return {"ok": True, "ready": get_camera_ready()}

    @app.post("/camera/recording/start")
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

    @app.post("/camera/recording/stop")
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

    recordings_service: RecordingsService | None = None
    if camera_recording_service is not None:
        recordings_service = RecordingsService(
            recordings_dir=camera_recording_service.recordings_dir,
            persistence=persistence,
        )

    def _recordings_to_dict(recordings: list) -> list[dict]:
        return [
            {
                "filename": r.filename,
                "timestamp": r.timestamp_iso,
                "size_bytes": r.size_bytes,
                "duration_sec": r.duration_sec,
            }
            for r in recordings
        ]

    @app.get("/recordings")
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

    @app.get("/sessions/{sid:int}/recordings")
    def get_session_recordings(sid: int) -> dict:
        """Return recordings for a session. Session detail: no fallback when unresolved."""
        if recordings_service is None:
            return {
                "session_id": sid,
                "session_resolved": False,
                "fallback_used": False,
                "count": 0,
                "recordings": [],
                "recordings_dir": None,
            }
        result = recordings_service.get_recordings(session_id=sid, allow_fallback=False)
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

    @app.delete("/recordings/{filename}")
    def delete_recording(filename: str) -> dict:
        """Delete a recording by basename. Path traversal protected."""
        if recordings_service is None:
            raise HTTPException(503, "Recordings service not available")
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        if not recordings_service.delete_recording(filename):
            raise HTTPException(404, "File not found or delete failed")
        return {"ok": True}

    @app.get("/recordings/{filename}")
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

    @app.get("/dashboard")
    def dashboard() -> Response:
        """Serve the real-time flight dashboard. No-cache to ensure upgrades show new UI."""
        return Response(
            content=get_dashboard_html(),
            media_type="text/html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    @app.get("/dashboard/sessions/{sid:int}")
    def session_detail(sid: int) -> Response:
        """Serve session detail page with lat/lon path. No-cache for upgrade consistency."""
        return Response(
            content=get_session_detail_html(),
            media_type="text/html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    return app
