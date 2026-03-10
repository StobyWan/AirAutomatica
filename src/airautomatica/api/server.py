"""FastAPI server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse

from airautomatica.config import get_ai_mode, get_sqlite_db_path, get_telemetry_backend
from airautomatica.db.base import get_engine
from airautomatica.logging_config import setup_logging
from airautomatica.models.state import AircraftState, nan_to_none
from airautomatica.services.persistence import PersistenceService
from airautomatica.services.state_store import StateStore
from airautomatica.settings import get_settings, save_settings
from airautomatica.ui.dashboard import get_dashboard_html, get_session_detail_html


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Reapply our logging config after uvicorn initializes (fixes logging being overridden)."""
    setup_logging(force=True)
    yield


def create_app(
    store: StateStore,
    persistence: Optional[PersistenceService] = None,
    session_id: Optional[int] = None,
) -> FastAPI:
    """Create FastAPI app with state store dependency."""
    app = FastAPI(title="AIRAUTOMATICA", version="0.1.0", lifespan=_lifespan)

    @app.get("/health")
    def health() -> dict:
        """Health check. Includes telemetry_status, connection details, and DB health when available."""
        state = store.get()
        persistence_enabled = get_engine() is not None
        health_data: dict = {
            "status": "ok",
            "ai_mode": get_ai_mode(),
            "telemetry_backend": get_telemetry_backend(),
            "persistence": {
                "persistence_enabled": persistence_enabled,
                "sqlite_db_path": get_sqlite_db_path() if persistence_enabled else None,
                "session_id": session_id,
                "last_persistence_error": (
                    persistence.get_last_persistence_error()
                    if persistence is not None
                    else None
                ),
            },
        }
        if state is None:
            health_data["telemetry"] = {
                "telemetry_status": "disconnected",
                "connected": False,
                "reconnect_count": 0,
                "last_disconnect_reason": None,
            }
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
        return health_data

    @app.get("/state")
    def get_state() -> dict:
        """Return current aircraft state."""
        state: Optional[AircraftState] = store.get()
        if state is None:
            return {"state": None}
        return {"state": state.to_dict()}

    @app.get("/recent-detections")
    def get_recent_detections() -> dict:
        """Return recent persisted detections for current session. For bench testing."""
        if persistence is None or session_id is None:
            return {"detections": [], "session_id": None}
        detections = persistence.get_recent_detections(session_id, limit=20)
        return {"detections": detections, "session_id": session_id}

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

    @app.get("/sessions")
    def get_sessions() -> dict:
        """Return recent flight sessions with detection counts. For dashboard initial load."""
        if persistence is None:
            return {"sessions": [], "current_session_id": session_id}
        sessions = persistence.get_recent_sessions(
            limit=10, include_detection_count=True
        )
        return {"sessions": sessions, "current_session_id": session_id}

    @app.get("/settings")
    def get_settings_endpoint() -> dict:
        """Return current settings (telemetry, AI, serial, etc.)."""
        return {"settings": get_settings(), "restart_required": True}

    @app.post("/settings")
    def post_settings(updates: dict = Body(...)) -> dict:
        """Save settings to file. Restart the app to apply changes."""
        save_settings(updates)
        return {"ok": True, "message": "Settings saved. Restart the app to apply."}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        """Serve the real-time flight dashboard."""
        return HTMLResponse(content=get_dashboard_html())

    @app.get("/dashboard/sessions/{sid:int}", response_class=HTMLResponse)
    def session_detail(sid: int) -> HTMLResponse:
        """Serve session detail page with lat/lon path."""
        return HTMLResponse(content=get_session_detail_html())

    return app
