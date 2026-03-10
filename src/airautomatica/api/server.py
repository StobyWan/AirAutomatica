"""FastAPI server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from airautomatica.config import get_ai_mode, get_sqlite_db_path, get_telemetry_backend
from airautomatica.db.base import get_engine
from airautomatica.logging_config import setup_logging
from airautomatica.models.state import AircraftState, nan_to_none
from airautomatica.services.persistence import PersistenceService
from airautomatica.services.state_store import StateStore
from airautomatica.ui.dashboard import get_dashboard_html


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

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        """Serve the real-time flight dashboard."""
        return HTMLResponse(content=get_dashboard_html())

    return app
