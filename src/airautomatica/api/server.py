"""FastAPI server."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, cast

if TYPE_CHECKING:
    from airautomatica.services.ai_detection_store import AiDetectionStore
    from airautomatica.services.app_home_store import AppHomeStore
    from airautomatica.services.mission_logic import MissionLogic
    from airautomatica.telemetry.preprocessing import TelemetryPreprocessor

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from airautomatica.ai.ollama_readiness import check_ollama_ready
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import (
    EventClassificationResult,
    OllamaTaskType,
    TelemetrySummaryResult,
    get_telemetry_summary_counts,
)
from airautomatica.api.helpers import build_active_summary
from airautomatica.api.routers import ai as ai_router_mod
from airautomatica.api.routers import camera as camera_router_mod
from airautomatica.api.routers import connection as connection_router_mod
from airautomatica.api.routers import dashboard as dashboard_router_mod
from airautomatica.api.routers import recordings as recordings_router_mod
from airautomatica.api.routers import session as session_router_mod
from airautomatica.api.routers import sessions as sessions_router_mod
from airautomatica.api.routers import settings as settings_router_mod
from airautomatica.api.routers import vehicle as vehicle_router_mod
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
    get_spa_index_path,
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
from airautomatica.services.ai_detection_store import AiDetectionStore
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
    AI_SUBSYSTEM_KEYS,
    SETTING_APPLY_MODES,
    TELEMETRY_SUBSYSTEM_KEYS,
    get_apply_modes,
    get_effective_settings,
    get_provider_reason,
    get_raw_settings,
    save_settings,
)
from airautomatica.system.observability import get_ai_observability_rates
from airautomatica.system.thermal import get_thermal_state, read_temperature_c

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Reapply our logging config after uvicorn initializes (fixes logging being overridden)."""
    setup_logging(force=True)
    yield


def create_app(
    store: StateStore,
    connection_store: Optional[ConnectionStateStore] = None,
    ai_detection_store: Optional[AiDetectionStore] = None,
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
    app_home_store: Optional["AppHomeStore"] = None,
) -> FastAPI:
    """Create FastAPI app with state store dependency.
    When ai_holder is provided, task_service is read from it (supports hot-reload).
    reload_ai_fn(provider_before) -> ReloadResult when AI hot-reload is available.
    reload_telemetry_fn() -> TelemetryReconnectResult when telemetry reconnect is available.
    """
    app = FastAPI(title="AIRAUTOMATICA", version="0.1.0", lifespan=_lifespan)
    _static_dir = Path(__file__).resolve().parent.parent / "ui" / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
    _session_ref = session_ref or [None]
    _connection_store = connection_store
    _preprocessor = preprocessor
    _mission_logic = mission_logic
    _ai_holder = ai_holder
    _task_service_fallback = task_service
    _reload_ai_fn = reload_ai_fn
    _reload_telemetry_fn = reload_telemetry_fn
    _app_home_store = app_home_store

    def _get_task_service() -> Optional[OllamaTaskService]:
        if _ai_holder is not None:
            return _ai_holder.get_task_service()
        return _task_service_fallback

    @app.get("/")
    def root() -> RedirectResponse:
        """Redirect root to dashboard."""
        return RedirectResponse(url="/dashboard", status_code=302)

    app.include_router(
        connection_router_mod.create_connection_router(
            _session_ref, _connection_store, reload_telemetry_fn=_reload_telemetry_fn
        )
    )
    app.include_router(
        session_router_mod.create_session_router(
            store,
            _session_ref,
            _connection_store,
            persistence,
            _app_home_store,
            camera_recording_service=camera_recording_service,
            get_camera_recording_mode=get_camera_recording_mode,
        )
    )

    recordings_service: RecordingsService | None = None
    if camera_recording_service is not None:
        recordings_service = RecordingsService(
            recordings_dir=camera_recording_service.recordings_dir,
            persistence=persistence,
        )

    app.include_router(
        sessions_router_mod.create_sessions_router(
            _session_ref,
            persistence,
            _get_task_service,
            recordings_service,
            recordings_dir=(
                camera_recording_service.recordings_dir
                if camera_recording_service
                else None
            ),
            camera_recording_service=camera_recording_service,
        )
    )
    app.include_router(
        settings_router_mod.create_settings_router(
            _mission_logic, _reload_ai_fn, _reload_telemetry_fn
        )
    )
    app.include_router(
        ai_router_mod.create_ai_router(
            ai_detection_store=ai_detection_store,
            persistence=persistence,
            session_ref=_session_ref,
            camera_recording_service=camera_recording_service,
        )
    )
    app.include_router(camera_router_mod.create_camera_router(camera_recording_service))
    app.include_router(vehicle_router_mod.router)
    app.include_router(
        recordings_router_mod.create_recordings_router(
            recordings_service,
            camera_recording_service,
            session_ref=_session_ref,
        )
    )
    app.include_router(dashboard_router_mod.create_dashboard_router())

    # Mount SPA static assets when Vue frontend is built
    _spa_index = get_spa_index_path()
    if _spa_index is not None:
        _spa_dist = _spa_index.parent
        _spa_assets = _spa_dist / "assets"
        if _spa_assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(_spa_assets)),
                name="dashboard-spa-assets",
            )
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(_spa_dist), html=True),
            name="dashboard-spa",
        )
        logger.info("Dashboard: serving Vue SPA from %s", _spa_dist)
    else:
        logger.info("Dashboard: SPA not built; /dashboard will show build instructions")

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
    async def post_telemetry_summary(
        body: dict = Body(default_factory=dict),
    ) -> dict:
        """Request AI interpretation of telemetry. Optional session_id for session detail."""
        ts = _get_task_service()
        if ts is None:
            return {"error": "AI task service not available"}
        if _preprocessor is None and ts.provider == "ollama":
            return {
                "error": "Preprocessing required for Ollama telemetry summary. Enable AIRAUTOMATICA_PREPROCESSING_ENABLED=1.",
            }
        state = store.get()
        samples: list = []
        sid = (
            body.get("session_id") if isinstance(body.get("session_id"), int) else None
        )
        if sid is None:
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
    async def post_event_classification(
        body: dict = Body(default_factory=dict),
    ) -> dict:
        """Request AI classification of system events. Optional session_id for session detail."""
        ts = _get_task_service()
        if ts is None:
            return {"error": "AI task service not available"}
        events: list = []
        sid = (
            body.get("session_id") if isinstance(body.get("session_id"), int) else None
        )
        if persistence is not None:
            events = persistence.get_session_system_events(session_id=sid, limit=30)
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

    @app.get("/recent-events")
    def get_recent_events() -> dict:
        """Return recent system events for dashboard. Degrades to [] when persistence disabled."""
        if persistence is None:
            return {"events": []}
        events = persistence.get_recent_system_events(limit=50)
        return {"events": events}

    return app
